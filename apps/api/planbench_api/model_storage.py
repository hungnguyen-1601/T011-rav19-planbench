"""Where uploaded model files live.

Same shape as the artifact store (decision D15): the database keeps
metadata and a storage key, the bytes live somewhere a database should
not. The interface exists so the local filesystem backend and an
S3-compatible one are interchangeable — production on R2 and a laptop
on disk must not need different calling code.

**Nothing here deserialises an uploaded file.** Reading a `.zip`'s table
of contents does not run anything; `pickle.load` does, and
Stable-Baselines3 checkpoints are pickles. So the deepest check this
module performs is structural — is this archive shaped like an SB3
checkpoint? — and actually loading the weights is left to a separate
process (see `model_validation.py`). That split is the security story,
and it is why `ValidationStatus` distinguishes STRUCTURAL from LOADED.
"""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from planbench_api.model_registry import RegistryError

#: Read in chunks so a 200 MB upload never sits in memory whole.
CHUNK = 1024 * 1024

#: A zip file starts with "PK\x03\x04". Checked because an extension is
#: a claim by whoever uploaded the file, and this is the file itself
#: disagreeing with that claim.
ZIP_MAGIC = b"PK\x03\x04"

#: What Stable-Baselines3 puts in a checkpoint. `data` is the algorithm
#: config; the `.pth` members are the weights. An archive with none of
#: them is not an SB3 model, whatever it is named.
SB3_MEMBERS = frozenset({"data", "policy.pth", "pytorch_variables.pth"})


class StoredFile(BaseModel):
    """Where a file went and how to recognise it again."""

    model_config = ConfigDict(frozen=True)

    storage_key: str
    size_bytes: int
    checksum: str


class ModelStorage(ABC):
    """Persist uploaded files and hand back a verifiable reference."""

    @abstractmethod
    def save(self, key: str, source: Iterator[bytes], *, max_bytes: int) -> StoredFile: ...

    @abstractmethod
    def open(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def checksum(self, key: str) -> str: ...

    @abstractmethod
    def internal_location(self, key: str) -> str:
        """A path the *runner* can open.

        Deliberately named `internal_`: it is for the process that loads
        the model, never for an API response. An object-store backend
        would materialise a temporary file here.
        """


class UploadTooLarge(RegistryError):
    """The upload exceeded the configured limit."""


def storage_key(user_id: str, model_id: str, version: str, filename: str) -> str:
    """Where a file belongs.

    Built entirely from ids, never from user input: the filename is
    carried alongside for display, but it does not choose a location, so
    a hostile name cannot escape the directory it was given.
    """
    safe_version = version.replace("/", "_").replace("\\", "_") or "1"
    return f"models/{user_id or 'anonymous'}/{model_id}/{safe_version}/{filename}"


class LocalModelStorage(ModelStorage):
    """Files under a root directory. The default everywhere but production."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Belt and braces: keys are built from ids, but resolving and
        # then checking containment means even a malformed key cannot
        # write outside the root.
        candidate = (self._root / key).resolve()
        root = self._root.resolve()
        if not candidate.is_relative_to(root):
            raise RegistryError("refusing a storage key that points outside the model directory")
        return candidate

    def save(self, key: str, source: Iterator[bytes], *, max_bytes: int) -> StoredFile:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("wb") as handle:
                for chunk in source:
                    size += len(chunk)
                    if size > max_bytes:
                        # Stop reading *and* remove the partial file:
                        # the limit is there to bound disk use, so a
                        # rejected upload must not leave its bytes behind.
                        raise UploadTooLarge(
                            f"file is larger than the {max_bytes // (1024 * 1024)} MB limit"
                        )
                    digest.update(chunk)
                    handle.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return StoredFile(storage_key=key, size_bytes=size, checksum=digest.hexdigest())

    def open(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return bool(key) and self._path(key).is_file()

    def delete(self, key: str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True)
        # Take the now-empty version and model directories with it, so
        # deleting a model does not leave a tree of empty folders.
        for parent in (path.parent, path.parent.parent):
            try:
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                break

    def checksum(self, key: str) -> str:
        digest = hashlib.sha256()
        with self._path(key).open("rb") as handle:
            for chunk in iter(lambda: handle.read(CHUNK), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def internal_location(self, key: str) -> str:
        return str(self._path(key))

    def purge_model(self, user_id: str, model_id: str) -> None:
        """Remove everything stored for one model."""
        directory = self._path(f"models/{user_id or 'anonymous'}/{model_id}")
        if directory.is_dir():
            shutil.rmtree(directory, ignore_errors=True)


def inspect_archive(data: bytes) -> list[str]:
    """Structural check of an uploaded `.zip`. Executes nothing.

    Reads the archive's table of contents, which is metadata parsing,
    not deserialisation. Returns problems as messages; an empty list
    means it looks like an SB3 checkpoint.

    Members are also checked for absolute paths and `..` segments. This
    code never extracts the archive, so those cannot hurt *it* — but an
    archive carrying them is either malicious or broken, and either way
    is not something to run a benchmark against.
    """
    problems: list[str] = []
    if not data.startswith(ZIP_MAGIC):
        return [
            "this file is not a zip archive. A PPO model is the .zip that "
            "Stable-Baselines3 writes with model.save()"
        ]

    import io

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            broken = archive.testzip()
    except zipfile.BadZipFile:
        return ["the zip archive is corrupt and cannot be read"]

    if broken is not None:
        problems.append(f"the archive contains a corrupt member: {broken}")

    unsafe = [
        name for name in names if name.startswith("/") or ".." in Path(name).parts or "\\" in name
    ]
    if unsafe:
        problems.append(f"the archive contains unsafe member paths: {sorted(unsafe)[:3]}")

    # Members can be nested (`model/data`), so match on the tail.
    tails = {Path(name).name for name in names}
    if not (SB3_MEMBERS & tails):
        problems.append(
            "the archive does not look like a Stable-Baselines3 checkpoint "
            f"(expected one of {sorted(SB3_MEMBERS)}, found {sorted(tails)[:5]})"
        )
    return problems


__all__ = [
    "CHUNK",
    "SB3_MEMBERS",
    "ZIP_MAGIC",
    "LocalModelStorage",
    "ModelStorage",
    "StoredFile",
    "UploadTooLarge",
    "inspect_archive",
    "storage_key",
]

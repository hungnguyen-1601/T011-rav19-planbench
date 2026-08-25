"""Offer the next version, and never take it without being asked.

The shape of this is decided by two facts about who runs it.

**Nobody here reads release notes on a website.** The app is installed on
a colleague's laptop from a file somebody sent them, and if it does not
tell them a new version exists, they will run the old one for months.
So it checks.

**And nobody here wants their machine to change under them.** An update
that installs itself while somebody is mid-comparison closes the window
they were reading. So it asks, once per launch, and No is a real answer.

Three things are verified before anything is executed. The release must
be one of *ours* (the tag prefix), it must be *newer* (a version compare,
not a string compare — `0.10.0` is not older than `0.9.0`), and the
downloaded installer must hash to what the release's manifest says. The
last one is the one that matters: everything else is convenience, and
that is the check standing between a download and running an unknown
executable with the user's privileges.

The releases are public, so no credential is needed and none is asked
for: an installation checks anonymously and updates itself. A token in
the data directory's `.env` is honoured when present — it raises the
anonymous rate limit, and it is what would keep this working if the
repository were ever made private — but requiring one would have meant
every person who installed the app had to paste a credential before it
would ever notice a new version, which is the same as not having an
updater at all.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("planbench.desktop")

#: Where releases live. Not configurable: an updater that could be
#: pointed at another repository by a file in the data directory would
#: be a way to make this app install anything at all.
REPOSITORY = "hungnguyen-1601/T011-rav19-planbench"

#: Desktop releases are tagged `desktop-vX.Y.Z`. The repository also
#: carries tags that are not this application, and running one of those
#: through the installer would be a category error rather than an
#: upgrade.
TAG_PREFIX = "desktop-v"

#: Names the JSON asset carrying the installer's hash. Written by the
#: release workflow beside the installer it describes.
MANIFEST_ASSET = "latest.json"

TOKEN_ENV = "PLANBENCH_UPDATE_TOKEN"

API = "https://api.github.com"
TIMEOUT_S = 10.0


class UpdateError(RuntimeError):
    """Something went wrong updating. Never fatal to the application."""


@dataclass(frozen=True)
class Release:
    version: str
    tag: str
    installer_url: str
    installer_name: str
    manifest_url: str
    notes: str


def parse_version(text: str) -> tuple[int, ...]:
    """`1.2.3` as a tuple of numbers, ignoring any suffix.

    A string compare would put `0.10.0` before `0.9.0`, which is the
    classic way an updater stops offering updates a year in.
    """
    head = text.strip().lstrip("v").split("-", 1)[0].split("+", 1)[0]
    parts: list[int] = []
    for chunk in head.split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            break
    return tuple(parts) or (0,)


def _request(url: str, token: str = "", *, accept: str) -> bytes:
    """Fetch ``url``, signed only if there is a credential to sign with.

    An empty `Authorization: Bearer` header is worse than no header:
    GitHub rejects a malformed credential with 401 rather than falling
    back to anonymous access, so sending one unconditionally would turn
    "no token configured" into "updates are broken".
    """
    request = urllib.request.Request(url)  # noqa: S310 - https, built from constants
    request.add_header("Accept", accept)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as answer:  # noqa: S310
            return answer.read()
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"{url} answered {exc.code}") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise UpdateError(f"could not reach {url}: {exc}") from exc


def token() -> str:
    """An optional read-only credential. Empty is the normal case.

    Worth setting on a machine that opens the app many times a day —
    anonymous GitHub API access is capped per IP — and required only if
    the repository stops being public.
    """
    return os.environ.get(TOKEN_ENV, "").strip()


def latest_release(current: str, credential: str) -> Release | None:
    """The newest desktop release above ``current``, if there is one.

    The releases list rather than `/releases/latest`: that endpoint
    answers with the newest release of *any* kind, which in a repository
    that tags other things is not necessarily this application.
    """
    payload = json.loads(
        _request(
            f"{API}/repos/{REPOSITORY}/releases?per_page=30",
            credential,
            accept="application/vnd.github+json",
        )
    )
    here = parse_version(current)
    best: Release | None = None
    for entry in payload:
        tag = entry.get("tag_name", "")
        if not tag.startswith(TAG_PREFIX) or entry.get("draft"):
            continue
        version = tag[len(TAG_PREFIX) :]
        if parse_version(version) <= here:
            continue
        if best is not None and parse_version(version) <= parse_version(best.version):
            continue
        assets = {asset["name"]: asset for asset in entry.get("assets", [])}
        installer = next(
            (name for name in assets if name.lower().endswith(".exe")),
            "",
        )
        if not installer or MANIFEST_ASSET not in assets:
            logger.warning("release %s has no installer and manifest pair; skipped", tag)
            continue
        best = Release(
            version=version,
            tag=tag,
            installer_url=assets[installer]["url"],
            installer_name=installer,
            manifest_url=assets[MANIFEST_ASSET]["url"],
            notes=(entry.get("body") or "").strip(),
        )
    return best


def download(release: Release, credential: str, into: Path) -> Path:
    """Fetch the installer and refuse it unless it hashes as promised.

    The hash comes from the release's own manifest rather than from
    anything alongside the download, and it is checked before the file is
    ever named `.exe` on disk — a half-written or substituted installer
    should not be something a stray double-click can run.
    """
    # `application/octet-stream`, not `application/json`. Asking the
    # asset endpoint for JSON returns the asset's *metadata* — name,
    # size, uploader — which parses perfectly and contains no `sha256`,
    # so the update failed with "carries no usable sha256" against a
    # release whose manifest was correct all along. Only octet-stream
    # returns the file's bytes.
    manifest = json.loads(
        _request(release.manifest_url, credential, accept="application/octet-stream")
    )
    expected = str(manifest.get("sha256", "")).lower()
    if len(expected) != 64:
        raise UpdateError(f"release {release.tag} carries no usable sha256")
    if manifest.get("version") and manifest["version"] != release.version:
        raise UpdateError(f"release {release.tag} contains a manifest for {manifest['version']}")

    payload = _request(release.installer_url, credential, accept="application/octet-stream")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise UpdateError(
            f"the downloaded installer for {release.tag} hashes to {actual}, "
            f"not the {expected} its release declares"
        )

    into.mkdir(parents=True, exist_ok=True)
    target = into / release.installer_name
    target.write_bytes(payload)
    logger.info("downloaded %s (%.1f MB, hash verified)", target.name, len(payload) / 1e6)
    return target


def ask(release: Release) -> bool:
    """A yes/no box, or False when there is nobody to ask.

    `ctypes` rather than a toolkit: this runs before the window exists,
    and the fallback for a machine where it does not work is simply not
    updating this time.
    """
    if sys.platform != "win32":  # pragma: no cover - the installer is Windows-only
        return False
    try:
        import ctypes

        notes = release.notes.splitlines()[:6]
        body = f"PlanBench {release.version} is available.\n\n"
        if notes:
            body += "\n".join(notes) + "\n\n"
        body += "Install it now? PlanBench will close and reopen."
        # 4 = Yes/No, 0x20 = question icon, 6 = the user chose Yes.
        return ctypes.windll.user32.MessageBoxW(None, body, "PlanBench update", 0x24) == 6
    except Exception as exc:  # noqa: BLE001 - never let the prompt be fatal
        logger.warning("could not ask about the update (%s); skipping it", exc)
        return False


def apply(installer: Path, relaunch: list[str], log: Path | None = None) -> None:
    """Run the installer, then reopen the app, then leave.

    The application has to **exit** for this to work: it is running out
    of the directory the installer is about to replace, and Windows will
    not overwrite a file a live process holds open. So the sequence is
    handed to a detached shell and this process returns to shut down.

    Three details are what make that survivable rather than a race:

    **A pause before the installer starts.** Handing off and exiting are
    not simultaneous — the interpreter still has to tear down — and the
    file most in the way is `pythonw.exe`, which *is* this process. A
    few seconds costs nothing and removes the overlap.

    **`/FORCECLOSEAPPLICATIONS`.** For whatever is still holding a file
    when the installer looks. Without it, silent mode's answer to a
    locked file is to give up, and `/SUPPRESSMSGBOXES` means giving up
    looks exactly like succeeding.

    **`&` rather than `&&` for the relaunch.** A failed install must
    still bring the app back: leaving somebody with no window at all is
    worse than leaving them on the version they had. Which one happened
    is answered by the installer log and by the version on the System
    page, not by guessing.
    """
    quoted = " ".join(f'"{part}"' for part in relaunch)
    log_option = f' /LOG="{log}"' if log is not None else ""
    command = (
        "timeout /t 4 /nobreak >nul & "
        f'"{installer}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART '
        f"/FORCECLOSEAPPLICATIONS{log_option}"
        f' & start "" {quoted}'
    )
    subprocess.Popen(  # noqa: S602 - the command is built here, not supplied
        ["cmd", "/c", command],
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        close_fds=True,
    )
    logger.info("handed off to the installer for %s", installer.name)
    if log is not None:
        logger.info("the installer will write its own log to %s", log)


def offer(current: str, cache: Path, relaunch: list[str]) -> bool:
    """The whole flow. Returns whether the app should now close.

    Every failure is a log line and a False: an updater that could stop
    the application from opening would be a worse problem than an old
    version of it.
    """
    credential = token()
    logger.info(
        "checking for updates (%s)",
        "signed in" if credential else "anonymously",
    )
    try:
        release = latest_release(current, credential)
        if release is None:
            logger.info("PlanBench %s is the newest release", current)
            return False
        logger.info("PlanBench %s is available (running %s)", release.version, current)
        if not ask(release):
            logger.info("the update was declined")
            return False
        installer = download(release, credential, cache)
        apply(installer, relaunch, log=cache / "installer.log")
    except UpdateError as exc:
        logger.warning("update check failed: %s", exc)
        return False
    except Exception:  # noqa: BLE001 - the app must open regardless
        logger.exception("update check failed unexpectedly")
        return False
    return True


__all__ = [
    "MANIFEST_ASSET",
    "REPOSITORY",
    "TAG_PREFIX",
    "TOKEN_ENV",
    "Release",
    "UpdateError",
    "apply",
    "ask",
    "download",
    "latest_release",
    "offer",
    "parse_version",
    "token",
]

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
the data directory's `.env` is honoured when present — it is what would
keep this working if the repository were ever made private — but
requiring one would have meant every person who installed the app had to
paste a credential before it would ever notice a new version, which is
the same as not having an updater at all.

**The check no longer goes through the API, and that is a bug fix.**
Anonymous API access is capped at sixty calls an hour *per IP* — a
budget the app shares with git, with CI checks, with everything else on
the machine that talks to GitHub. The app's own share is one call per
launch, so it is almost never the thing that exhausts the budget; it is
simply the thing that notices. When the budget is gone the API answers
403, the check fails, and the person is told nothing is available.

That is measured, not imagined: 0.1.13 shipped, and the 0.1.12 running
beside it went on reporting itself current with two 403s in its log.
Setting a token fixes it for one machine. Not spending the budget fixes
it for everyone, including the colleague who installs this from a file
somebody sent them and will never edit a `.env`.

So the ordinary path reads the release's own published manifest, which
is served by the release CDN and is not rate limited at all. The API
stays as the fallback, because only it can filter releases by tag
prefix — see :func:`_latest_from_manifest` for when that matters.
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
from collections.abc import Callable
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

#: Where a release's own files are served from, as opposed to the API
#: that describes them. **This host applies no rate limit**, which is the
#: whole reason the check below prefers it: that check runs once per
#: launch on every machine the app is installed on.
DOWNLOADS = "https://github.com"

TIMEOUT_S = 10.0

#: Read size while streaming the installer. Small enough that the
#: progress bar moves, large enough not to make a syscall per pixel.
CHUNK = 256 * 1024


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


def _request(
    url: str,
    token: str = "",
    *,
    accept: str,
    on_progress: Callable[[int, int | None], None] | None = None,
) -> bytes:
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
            if on_progress is None:
                return answer.read()
            # Read in chunks so the caller can say how far along it is.
            # `Content-Length` is absent often enough that None has to
            # mean "no total" rather than zero — a bar computed from a
            # zero total is a bar that lies.
            declared = answer.headers.get("Content-Length")
            total = int(declared) if declared and declared.isdigit() else None
            chunks: list[bytes] = []
            read = 0
            while True:
                chunk = answer.read(CHUNK)
                if not chunk:
                    break
                chunks.append(chunk)
                read += len(chunk)
                on_progress(read, total)
            return b"".join(chunks)
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


def _asset_url(tag: str, asset: str) -> str:
    """A release file by tag and name, straight from the CDN."""
    return f"{DOWNLOADS}/{REPOSITORY}/releases/download/{tag}/{asset}"


def latest_release(current: str, credential: str) -> Release | None:
    """The newest desktop release above ``current``, if there is one.

    The manifest first and the API only if that fails. The module
    docstring says why: the API path costs a call against a sixty-an-hour
    budget shared with everything else on the machine, and when it runs
    out this reports "up to date" for a version that is not.
    """
    try:
        return _latest_from_manifest(current)
    except UpdateError as exc:
        # Info rather than warning: the fallback below is the path that
        # was here before this one existed, and it is still correct.
        logger.info("the published manifest was unusable (%s); asking the API", exc)
    return _latest_from_api(current, credential)


def _latest_from_manifest(current: str) -> Release | None:
    """What the newest release publishes about itself, read without the API.

    **Sent unsigned, deliberately.** The CDN answers with a redirect to a
    pre-signed storage URL, and that URL refuses a request arriving with
    a second credential — so passing the optional token here would break
    the ordinary path for exactly the people who bothered to configure
    one. It is not needed either: the releases are public.

    **`releases/latest` is the newest release of *any* kind**, and this
    repository carries tags that are not this application. So the
    manifest is not trusted for being the latest thing — it has to name a
    version and an installer, and if it does not, this raises and the
    caller falls back to the API, which can filter by tag prefix.

    The URLs handed back are pinned to the tag the manifest named, never
    to `latest`. Between this check and the download a release could
    publish; pinning means what gets hashed and what gets installed are
    the same file.
    """
    payload = json.loads(
        _request(
            f"{DOWNLOADS}/{REPOSITORY}/releases/latest/download/{MANIFEST_ASSET}",
            accept="application/octet-stream",
        )
    )
    version = str(payload.get("version", "")).strip()
    asset = str(payload.get("asset", "")).strip()
    if not version or not asset.lower().endswith(".exe"):
        raise UpdateError(f"{MANIFEST_ASSET} names no installer for a version")
    if parse_version(version) <= parse_version(current):
        return None
    tag = f"{TAG_PREFIX}{version}"
    return Release(
        version=version,
        tag=tag,
        installer_url=_asset_url(tag, asset),
        installer_name=asset,
        manifest_url=_asset_url(tag, MANIFEST_ASSET),
        # The manifest carries no release body, and the dialog needs a
        # version and a question rather than notes. `ask` handles "".
        notes="",
    )


def _latest_from_api(current: str, credential: str) -> Release | None:
    """The fallback, and the one thing it can do that the manifest cannot.

    The releases list rather than `/releases/latest`: that endpoint
    answers with the newest release of *any* kind, which in a repository
    that tags other things is not necessarily this application. Filtering
    the list by tag prefix is the only way to be certain, and it is why
    this path is kept rather than deleted.
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


def download(
    release: Release,
    credential: str,
    into: Path,
    on_progress: Callable[[int, int | None], None] | None = None,
) -> Path:
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

    payload = _request(
        release.installer_url,
        credential,
        accept="application/octet-stream",
        on_progress=on_progress,
    )
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
    """Install the update and reopen the app, through a script on disk.

    The application has to **exit** for this to work: it is running out
    of the directory the installer replaces, and Windows will not
    overwrite a file a live process holds open. So the work is handed to
    a detached shell and this process returns to shut down.

    **A `.cmd` file rather than a command string**, and that is a
    correction rather than a preference. The string version chained
    three commands with `&` through `cmd /c`, and one of the three —
    the installer — silently did not run: the app closed, reopened on
    the version it started with, and left no installer log to explain
    why, because the installer had never been reached. Quoting rules
    across `subprocess` and `cmd /c` are where that went, and a file
    removes the layer instead of guessing at it. It also leaves the
    exact commands on disk, next to their log, for the next time
    something does not add up.

    The steps, and why each is there:

    * a pause, because handing off and exiting are not simultaneous and
      the file most in the way is this interpreter;
    * `/FORCECLOSEAPPLICATIONS`, for whatever still holds a file — in
      silent mode, giving up on a lock looks exactly like succeeding;
    * the exit code recorded, so a failure leaves something to read;
    * the relaunch **unconditional**, because leaving somebody with no
      window at all is worse than leaving them on the version they had.
    """
    script = installer.with_name("apply-update.cmd")
    receipt = installer.with_name("apply-update.txt")
    # `/SILENT`, not `/VERYSILENT`: the difference is a progress bar.
    # This runs after the app has exited, so it is the only thing on
    # screen — and with nothing on screen, an update and a crash look
    # exactly alike from the outside. No wizard pages either way.
    options = "/SILENT /SUPPRESSMSGBOXES /NORESTART /FORCECLOSEAPPLICATIONS"
    if log is not None:
        options += f' /LOG="{log}"'
    relaunch_command = " ".join(f'"{part}"' for part in relaunch)
    body = "\r\n".join(
        [
            "@echo off",
            "rem Written by PlanBench's updater. Safe to delete.",
            "timeout /t 4 /nobreak >nul",
            # `call`, so control comes back. Without it a batch-file
            # installer would take the rest of this script with it, and
            # the app would never be restarted.
            f'call "{installer}" {options}',
            f'echo installer exit code: %ERRORLEVEL% > "{receipt}"',
            f'start "" {relaunch_command}',
            "",
        ]
    )
    # The console codepage, not UTF-8: `cmd` reads a batch file in the
    # system encoding, and a user profile with a non-ASCII name would
    # otherwise produce a path the shell cannot find.
    script.write_text(body, encoding="mbcs", errors="replace")

    subprocess.Popen(  # noqa: S602 - the script is written here, not supplied
        ["cmd", "/c", str(script)],
        creationflags=(
            getattr(subprocess, "DETACHED_PROCESS", 0)
            # Without this a console window opens over whatever the
            # person was doing, sits there counting down, and gives no
            # hint whether the app is updating or has crashed.
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        ),
        close_fds=True,
    )
    logger.info("handed off to %s", script)
    if log is not None:
        logger.info("the installer will write its own log to %s", log)


def _download_visibly(release: Release, credential: str, cache: Path) -> Path:
    """Fetch the installer with a window saying so.

    The window is the whole point and is also the part allowed to fail:
    `Progress.run` falls back to running the work plainly when no
    toolkit will start, so a machine that cannot draw still updates.
    """
    from planbench_desktop.progress import Progress

    screen = Progress(
        f"Updating PlanBench to {release.version}",
        "Starting the download…",
    )
    result: dict[str, Path] = {}

    def work(view: Progress) -> None:
        def report(read: int, total: int | None) -> None:
            done = read / 1e6
            if total:
                view.update(
                    f"Downloading… {done:.0f} of {total / 1e6:.0f} MB",
                    100.0 * read / total,
                )
            else:
                view.update(f"Downloading… {done:.0f} MB")

        result["installer"] = download(release, credential, cache, report)
        # Hashing eighty megabytes is not instant, and a bar that sits
        # at 100% while something unnamed happens is the gap this whole
        # window exists to close.
        view.update("Checking the download…", 100.0)

    screen.run(work)
    return result["installer"]


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
        installer = _download_visibly(release, credential, cache)
        apply(installer, relaunch, log=cache / "installer.log")
    except UpdateError as exc:
        logger.warning("update check failed: %s", exc)
        return False
    except Exception:  # noqa: BLE001 - the app must open regardless
        logger.exception("update check failed unexpectedly")
        return False
    return True


__all__ = [
    "DOWNLOADS",
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

"""Where the desktop build keeps its code and where it keeps its data.

Two roots, and keeping them apart is the whole of this module.

The **install root** holds code and read-only assets. It is whatever
directory the installer wrote, and after an upgrade it is a *different*
set of files — anything of the user's that lived there would be gone.

The **data root** holds the database, the artifacts, the maps somebody
edited and the `.env` carrying their API key. It survives upgrades and
survives uninstall unless the user asks otherwise.

The install root is derived from this file's location rather than
configured, because the layout it describes is the same in a checkout
and in an installation: `apps/desktop/planbench_desktop/paths.py` is
three levels below the root in both. That is not a coincidence to be
grateful for — it is why the packaging step copies the source tree with
its directories intact instead of flattening it, and the same property
`contracts/metric_anchors.yaml` depends on from the other direction.
"""

from __future__ import annotations

import os
from pathlib import Path

#: The directory holding `apps/`, `packages/`, `contracts/`, `alembic/`.
INSTALL_ROOT: Path = Path(__file__).resolve().parents[3]

#: Overrides the data root. Exists for the tests and for running two
#: profiles side by side; not something the installer sets.
DATA_ROOT_ENV = "PLANBENCH_DESKTOP_DATA_ROOT"


def data_root() -> Path:
    """The per-user directory this installation reads and writes.

    Read as a function rather than frozen at import: the tests point it
    at a temporary directory, and a module-level constant would be
    resolved before they got the chance.
    """
    override = os.environ.get(DATA_ROOT_ENV)
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "PlanBench"
    # Not Windows. The installer only targets Windows, but the launcher
    # is run directly from a checkout during development and must not
    # fall over on the machine doing the developing.
    return Path.home() / ".planbench"


def web_root() -> Path:
    """The exported web UI, served by the API process.

    Two layouts, because there are two ways to run this.

    **Installed**, `web/` is a *sibling* of `app/`, not a child of it —
    `INSTALL_ROOT` points at `app/`, so the export is one level up. That
    is not a detail: the first version of this looked inside
    `INSTALL_ROOT` and would have shipped an application that could not
    find its own interface, on a path no test covered because the
    checkout has no `web/` at all.

    **From a checkout**, it is wherever `next build` left it, under
    `apps/web/out`. Supporting that is what lets the launcher and the
    packaging smoke test be rehearsed from a working tree.

    When neither exists the installed path is returned anyway, so the
    warning the API logs names where a shipped build would look.
    """
    installed = INSTALL_ROOT.parent / "web"
    if (installed / "index.html").is_file():
        return installed
    from_checkout = INSTALL_ROOT / "apps" / "web" / "out"
    if (from_checkout / "index.html").is_file():
        return from_checkout
    return installed


def version() -> str:
    """The build's version, from the file the installer stamps.

    One source of truth: the packaging script reads the same file for
    the installer's `AppVersion`, and the updater compares against it.
    Missing means "running from a checkout", which is not a release and
    should never look newer or older than one.
    """
    stamp = Path(__file__).with_name("VERSION")
    if not stamp.exists():
        return "0.0.0-dev"
    return stamp.read_text(encoding="utf-8").strip() or "0.0.0-dev"


__all__ = ["DATA_ROOT_ENV", "INSTALL_ROOT", "data_root", "version", "web_root"]

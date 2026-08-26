"""Prove a staged desktop build works, using the staged interpreter.

    runtime\\python.exe app\\scripts\\desktop\\smoke_stage.py

Run by `build_desktop.ps1` between assembling the stage and building the
installer, and a failure here stops the release. Every check corresponds
to something the packaging can break without any other test noticing,
because the whole suite runs on a normal CPython from a checkout and
none of these mechanisms exist there.

The checks, in the order a failure would cascade:

1. **The source roots resolve.** Proves `python3xx._pth` names all of
   them. A miss here is an app that will not open at all.
2. **A child process still sees PYTHONPATH.** An embeddable Python with
   a `._pth` ignores that variable, and the plugin subprocess lane uses
   it to tell its worker where an imported algorithm lives. Nothing else
   in the build exercises this, and the failure it prevents does not look
   like a path problem — it looks like an algorithm that stops the robot.
3. **A plugin really runs out of process.** The end-to-end version of
   check 2, through the lane's own code rather than a stand-in.
4. **The launcher provisions, migrates, serves, and stops.**
5. **The window toolkit imports.** The one check allowed to fail without
   failing the build: the fallback is a browser window, and refusing to
   ship over it would be refusing to ship a working application.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

#: `app/scripts/desktop/smoke_stage.py` in a stage, `scripts/desktop/…`
#: in a checkout — the same two levels up either way.
APP_ROOT = Path(__file__).resolve().parents[2]

FAILURES: list[str] = []
NOTES: list[str] = []


def check(name: str):
    """Run a check, record the outcome, never let one abort the rest."""

    def run(fn):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - reporting every failure is the point
            FAILURES.append(f"{name}: {exc!r}")
            print(f"  FAIL  {name}: {exc!r}")
        else:
            print(f"  ok    {name}")
        return fn

    return run


def main() -> int:
    print(f"smoke test of {APP_ROOT}")
    print(f"interpreter: {sys.executable}")

    @check("the API package resolves")
    def _() -> None:
        # Resolved, deliberately not imported. `planbench_api.main`
        # builds the application at module scope, reading configuration
        # as it goes — so importing it here, before the launcher check
        # has provisioned anything, would freeze an app with no data
        # root and no web directory, and the launcher check further down
        # would then be handed that cached module rather than a fresh
        # one. Finding the spec proves the path resolves, which is what
        # this check is for.
        import importlib.util

        if importlib.util.find_spec("planbench_api.main") is None:
            raise AssertionError("planbench_api.main is not on the interpreter's path")

    @check("every declared source root imports")
    def _() -> None:
        for module in (
            "planbench_schemas",
            "planbench_planning",
            "planbench_metrics",
            "planbench_benchmark",
            "planbench_decision",
            "planbench_explanation",
            "planbench_plugin_sdk",
            "planbench_simulator",
            "planbench_tracking",
            "planbench_agent",
            "planbench_desktop",
        ):
            __import__(module)

    @check("the heavy wheels load")
    def _() -> None:
        # pyarrow is the one that breaks quietly: every episode writes a
        # Parquet file and that file is the metrics engine's only input.
        import numpy  # noqa: F401

        # Imported inside a function in decision_xlsx, so a packager
        # scanning top-level imports never sees it.
        import openpyxl  # noqa: F401
        import pyarrow.parquet  # noqa: F401
        import scipy.stats  # noqa: F401

    @check("a child process still honours PYTHONPATH")
    def _() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "smoke_marker_pkg.py"
            marker.write_text("VALUE = 'reached'\n", encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = tmp
            result = subprocess.run(
                [sys.executable, "-c", "import smoke_marker_pkg;print(smoke_marker_pkg.VALUE)"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            if result.stdout.strip() != "reached":
                raise AssertionError(
                    "sitecustomize.py did not put PYTHONPATH back on sys.path; "
                    "the plugin subprocess lane cannot reach an imported algorithm. "
                    f"stderr: {result.stderr.strip()[:400]}"
                )

    @check("a plugin runs out of process through the subprocess lane")
    def _() -> None:
        from planbench_plugin_sdk import (
            ChannelEnvelope,
            LocalResetRequest,
            LocalStepRequest,
            load_manifest,
        )

        from planbench_schemas.episode import Observation
        from planbench_schemas.geometry import Pose2D
        from planbench_simulator.host.compatibility import resolve_compatibility
        from planbench_simulator.host.provider_graph import ProviderGraph
        from planbench_simulator.host.providers import (
            LEGACY_OBSERVATION,
            builtin_providers,
            builtin_registry,
        )
        from planbench_simulator.host.runtimes import SubprocessRuntime

        examples = APP_ROOT / "examples" / "plugins"
        bundle = examples / "remote_wanderer"
        manifest, _ = load_manifest(bundle / ".planbench-plugin" / "plugin.json")
        report = resolve_compatibility(
            manifest,
            available_capabilities=frozenset({LEGACY_OBSERVATION}),
            graph=ProviderGraph(builtin_providers(), builtin_registry()),
        )
        runtime = SubprocessRuntime(search_paths=(str(examples),))
        plugin = runtime.load(manifest, report, control_period_s=0.05)
        try:
            plugin.reset(LocalResetRequest(robot={}, declared={}))
            result = plugin.step(
                LocalStepRequest(
                    state={"robot_state": None},
                    channels=(
                        ChannelEnvelope(
                            capability=LEGACY_OBSERVATION,
                            cadence="per_tick",
                            produced_at=0.0,
                            provenance="deployment",
                            payload=Observation(
                                time=0.0,
                                pose=Pose2D(x=1.0, y=1.0, theta=0.0),
                                linear_velocity=0.0,
                                angular_velocity=0.0,
                                goal_distance=4.0,
                                goal_bearing=0.3,
                                lidar_ranges=(3.0,) * 72,
                            ),
                        ),
                    ),
                )
            )
            if result.failure_reason:
                raise AssertionError(f"the worker reported {result.failure_reason!r}")
            if result.action.linear_velocity <= 0.0:
                raise AssertionError("the worker answered but the robot would not move")
        finally:
            plugin.close()

    @check("the launcher provisions, migrates, serves and stops")
    def _() -> None:
        # `ignore_cleanup_errors` and the restored working directory are
        # both about the same Windows rule: a directory that is a live
        # process's cwd cannot be deleted, and provisioning deliberately
        # chdirs into the data root. SQLite holds the database open a
        # moment longer than the server does, too.
        origin = Path.cwd()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            os.environ["PLANBENCH_DESKTOP_DATA_ROOT"] = str(Path(tmp) / "PlanBench")
            from planbench_desktop import migrate, paths
            from planbench_desktop.provision import provision
            from planbench_desktop.server import DesktopServer, free_port

            provisioned = provision()
            if not provisioned.created:
                raise AssertionError("a fresh data root did not report itself as new")
            migrate.upgrade(paths.INSTALL_ROOT, provisioned.root / "planbench.db")

            server = DesktopServer(free_port())
            server.start()
            try:
                with urllib.request.urlopen(f"{server.url}/api/v1/health", timeout=5) as answer:
                    payload = json.loads(answer.read())
                if answer.status != 200:
                    raise AssertionError(f"health answered {answer.status}")
                if not payload:
                    raise AssertionError("health answered with an empty body")
                _check_web_ui(server.url)
            finally:
                server.stop()
                os.chdir(origin)

    @check("a decision card could name the commit that produced it")
    def _() -> None:
        # The decision layer refuses to write a card whose manifest
        # cannot say which code produced it, and an installation has no
        # `.git` to ask. Without the stamped commit every selection run
        # dies at the moment it writes its card — after doing all the
        # work, which is the most expensive place to fail.
        from planbench_decision.card import resolve_git_sha

        sha = resolve_git_sha()
        if len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha):
            raise AssertionError(f"resolved git sha is not a commit: {sha!r}")

    @check("pywebview imports (falls back to a browser window if not)")
    def _() -> None:
        try:
            import webview  # noqa: F401
        except Exception as exc:  # noqa: BLE001 - a note, not a failure
            NOTES.append(
                f"pywebview did not import ({exc!r}); the app will open a browser "
                "window instead. Not a release blocker."
            )

    print()
    for note in NOTES:
        print(f"note: {note}")
    if FAILURES:
        print(f"\n{len(FAILURES)} check(s) failed; this stage is not shippable.")
        return 1
    print("\nall checks passed.")
    return 0


def _check_web_ui(base: str) -> None:
    """The exported UI, if this stage has one.

    A stage assembled without `web/` is still a valid thing to smoke —
    the launcher opens onto the API — so a missing directory is skipped
    rather than failed. A *present* one has to actually serve.
    """
    # `stage/web` beside `stage/app` when packaged; `apps/web/out` when
    # this is run from a checkout to rehearse the gate.
    candidates = (APP_ROOT.parent / "web", APP_ROOT / "apps" / "web" / "out")
    web = next((path for path in candidates if (path / "index.html").exists()), None)
    if web is None:
        NOTES.append("no exported web UI in this stage; skipped the UI checks")
        return
    with urllib.request.urlopen(base + "/", timeout=5) as answer:
        if answer.status != 200:
            raise AssertionError(f"the web UI index answered {answer.status}")
    with urllib.request.urlopen(base + "/decisions/smoke-not-a-real-id", timeout=5) as answer:
        if answer.status != 200:
            raise AssertionError(
                "a deep link into /decisions/<id> did not serve the exported shell; "
                "check that the export wrote decisions/_.html"
            )


if __name__ == "__main__":
    raise SystemExit(main())

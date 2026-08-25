"""The packaging artefacts, checked without building an installer.

Everything here is a claim that only becomes false on a build machine —
a path file missing a source root, a shortcut pointing at a launcher
that moved, an interpreter downloaded without a hash to check it
against. The suite runs on a normal CPython from a checkout, so none of
these mechanisms exist while it runs, and none of them would fail
anywhere else until somebody installed the result.

The smoke gate (`scripts/desktop/smoke_stage.py`) covers the other half:
whether a staged build actually runs. These are the checks that can be
made cheaply and continuously; that one needs a stage.
"""

from __future__ import annotations

import json
import struct
import tomllib

import pytest

from planbench_desktop.paths import INSTALL_ROOT


def _load_path_generator():
    """Load `scripts/desktop/make_runtime_paths.py` without importing it.

    `scripts/desktop/` is deliberately absent from every path list: it is
    build tooling, and nothing the application runs should be able to
    import it. Adding a `conftest.py` here to put it on `sys.path` had a
    second cost that showed up immediately — `tests/api/` and
    `tests/desktop/` are not packages, so pytest imports both files as
    the top-level module `conftest`, and whichever loads first wins.
    That broke every `from conftest import ...` in the API tests.
    """
    import importlib.util

    source = INSTALL_ROOT / "scripts" / "desktop" / "make_runtime_paths.py"
    spec = importlib.util.spec_from_file_location("planbench_make_runtime_paths", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_paths = _load_path_generator()
SITECUSTOMIZE = _paths.SITECUSTOMIZE
pth_contents = _paths.pth_contents
source_roots = _paths.source_roots


INSTALLER = INSTALL_ROOT / "installer"
LAUNCHER = INSTALL_ROOT / "apps" / "desktop" / "planbench_desktop" / "main.py"


class TestTheInterpreterPathFile:
    def test_it_names_every_source_root_the_project_declares(self) -> None:
        """`._pth` is the *only* path mechanism an embeddable Python has.

        A root missing from it is a module the shipped app cannot import,
        and the first symptom is a window that never opens.
        """
        declared = tomllib.loads((INSTALL_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        expected = [
            entry
            for entry in declared["tool"]["pytest"]["ini_options"]["pythonpath"]
            if entry not in (".", "tests")
        ]
        body = pth_contents("python312")

        for entry in expected:
            assert f"..\\app\\{entry.replace('/', chr(92))}" in body, entry
        assert len(expected) == len(source_roots())

    def test_it_keeps_the_scaffold_and_the_test_helpers_out(self) -> None:
        """`.` resolves the retired `src.*` tree and `tests` would let a
        test helper shadow a real module in the shipped application."""
        body = pth_contents("python312")

        assert "..\\app\\tests" not in body
        assert "\n..\\app\\.\n" not in body

    def test_it_asks_for_site_so_that_sitecustomize_runs(self) -> None:
        """Without `import site`, `site-packages/*.pth` and sitecustomize
        are both skipped — and sitecustomize is what hands PYTHONPATH
        back to the plugin subprocess lane."""
        assert pth_contents("python312").rstrip().endswith("import site")

    def test_it_puts_the_standard_library_and_site_packages_first(self) -> None:
        lines = [line for line in pth_contents("python312").splitlines() if line]

        assert lines[0] == "python312.zip"
        assert "Lib\\site-packages" in lines[:3]

    def test_the_tag_names_the_stdlib_zip(self) -> None:
        """A 3.13 runtime looks for python313.zip, not python312.zip."""
        assert pth_contents("python313").startswith("python313.zip")


class TestSitecustomize:
    def test_it_restores_pythonpath(self) -> None:
        """The lane passes an imported algorithm's location this way.

        `subprocess_lane._environment` builds PYTHONPATH for the worker,
        and an embeddable interpreter with a `._pth` ignores it. Nothing
        else in the packaging exercises this, and the failure reads as an
        algorithm that halts the robot rather than as a path problem.
        """
        assert 'os.environ.get("PYTHONPATH", "")' in SITECUSTOMIZE
        assert "sys.path.insert" in SITECUSTOMIZE

    def test_it_is_valid_python(self) -> None:
        compile(SITECUSTOMIZE, "sitecustomize.py", "exec")


class TestTheInterpreterPin:
    @pytest.fixture(scope="class")
    @staticmethod
    def spec() -> dict:
        return json.loads((INSTALLER / "python-embed.json").read_text(encoding="utf-8"))

    def test_the_declared_version_matches_the_url_and_the_tag(self, spec) -> None:
        """Three places name the version, and they have to agree.

        A URL fetching 3.12 with a tag saying `python313` produces a
        runtime whose path file names a stdlib zip that is not there.
        """
        version = spec["version"]
        major, minor, _ = version.split(".", 2)

        assert version in spec["url"]
        assert spec["python_tag"] == f"python{major}{minor}"

    def test_the_minor_version_matches_what_the_project_requires(self, spec) -> None:
        """pip installs C extensions for the interpreter it runs on, so
        a mismatch here ships wheels the shipped Python cannot load."""
        pyproject = tomllib.loads((INSTALL_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        requires = pyproject["project"]["requires-python"]

        assert requires.replace(">=", "").strip() in spec["version"]

    def test_the_download_comes_from_python_org(self, spec) -> None:
        assert spec["url"].startswith("https://www.python.org/ftp/python/")


class TestTheInstallerScript:
    @pytest.fixture(scope="class")
    @staticmethod
    def script() -> str:
        return (INSTALLER / "planbench.iss").read_text(encoding="utf-8")

    def test_the_shortcut_points_at_a_launcher_that_exists(self, script) -> None:
        """The one line nothing else would catch: rename the launcher and
        the build still succeeds, the installer still installs, and the
        shortcut does nothing at all."""
        relative = LAUNCHER.relative_to(INSTALL_ROOT).as_posix().replace("/", "\\")

        assert f"{{app}}\\app\\{relative}" in script
        assert LAUNCHER.is_file()

    def test_it_launches_with_pythonw_so_no_console_flashes(self, script) -> None:
        """python.exe would open a console for the app and another for
        every plugin subprocess it starts."""
        assert "runtime\\pythonw.exe" in script
        assert "runtime\\python.exe" not in script

    def test_the_application_id_is_fixed(self, script) -> None:
        """A regenerated AppId turns the next version into a second
        installation sitting beside the first."""
        assert "AppId={{7F1B4A62-3C9E-4E58-9E1D-2A6F0B5C8D31}" in script

    def test_it_installs_per_user_without_asking_for_administrator(self, script) -> None:
        assert "PrivilegesRequired=lowest" in script
        assert "DefaultDirName={localappdata}\\Programs\\PlanBench" in script

    def test_it_clears_the_old_code_before_writing_the_new(self, script) -> None:
        """An upgrade that renames a module would otherwise leave the old
        file behind — still importable, and now stale."""
        for directory in ("{app}\\app", "{app}\\runtime", "{app}\\web"):
            assert f'Type: filesandordirs; Name: "{directory}"' in script

    def test_uninstall_asks_before_deleting_a_persons_runs(self, script) -> None:
        """Comparison runs cost machine-hours; the default answer is No."""
        assert "MB_DEFBUTTON2" in script
        assert "DelTree" in script

    def test_the_icon_it_names_is_staged_by_the_build(self, script) -> None:
        build = (INSTALL_ROOT / "scripts" / "build_desktop.ps1").read_text(encoding="utf-8")

        assert "{app}\\planbench.ico" in script
        assert "installer\\planbench.ico') $Stage" in build


class TestTheBuildScript:
    @pytest.fixture(scope="class")
    @staticmethod
    def build() -> str:
        return (INSTALL_ROOT / "scripts" / "build_desktop.ps1").read_text(encoding="utf-8")

    def test_it_refuses_to_ship_an_unpinned_interpreter(self, build) -> None:
        """An unpinned download is a supply chain owned by whoever can
        answer for the host, and a hash the build computed for itself
        would pin nothing."""
        assert "refusing to ship an unpinned interpreter" in build
        assert "interpreter hash mismatch" in build

    def test_the_smoke_gate_runs_before_the_installer(self, build) -> None:
        """The gate is the only thing that looks at the mechanisms
        packaging introduces. Running it afterwards would mean shipping
        first and finding out second."""
        gate = build.index("smoke_stage.py")
        installer = build.index("Building the installer")

        assert gate < installer
        assert "refusing to package it" in build

    def test_it_stages_the_directories_the_app_resolves_by_walking_up(self, build) -> None:
        """`anchors.py` finds `contracts/` three levels above itself, so
        the copy has to keep the tree rather than flatten it."""
        for directory in ("'packages'", "'contracts'", "'apps\\desktop'", "'alembic'"):
            assert directory in build

    def test_it_checks_the_export_wrote_every_dynamic_route_shell(self, build) -> None:
        """Without the shells, reloading on /decisions/<id> is a 404 —
        and it is a 404 nobody sees until somebody presses F5."""
        for shell in ("decisions\\_.html", "maps\\_.html", "scenarios\\_.html"):
            assert shell in build


class TestTheIcon:
    def test_it_is_a_valid_multi_size_icon(self) -> None:
        raw = (INSTALLER / "planbench.ico").read_bytes()
        reserved, kind, count = struct.unpack("<HHH", raw[:6])

        assert (reserved, kind) == (0, 1)
        assert count >= 4
        for index in range(count):
            entry = raw[6 + 16 * index : 22 + 16 * index]
            _, _, _, _, _, bpp, size, offset = struct.unpack("<BBBBHHII", entry)
            assert bpp == 32
            assert raw[offset : offset + 8] == b"\x89PNG\r\n\x1a\n"
            assert size > 0

    def test_it_can_be_regenerated_from_the_script(self) -> None:
        """A checked-in binary nobody can rebuild is a dead end the first
        time it needs changing."""
        assert (INSTALL_ROOT / "scripts" / "desktop" / "make_icon.py").is_file()


class TestTheWebRoot:
    """Where the launcher looks for the exported UI.

    Nothing else covers this: the checkout has no installed layout to
    look at, so a path that is wrong only once packaged fails for the
    first time on somebody's machine. It did — the first version looked
    *inside* the app directory, and `web/` is its sibling.
    """

    def test_the_installed_layout_puts_web_beside_app_not_inside_it(self, tmp_path) -> None:
        import planbench_desktop.paths as paths_module

        install = tmp_path / "PlanBench"
        (install / "app").mkdir(parents=True)
        (install / "web").mkdir()
        (install / "web" / "index.html").write_text("<html></html>", encoding="utf-8")

        original = paths_module.INSTALL_ROOT
        paths_module.INSTALL_ROOT = install / "app"
        try:
            assert paths_module.web_root() == install / "web"
        finally:
            paths_module.INSTALL_ROOT = original

    def test_a_checkout_uses_the_next_build_output(self, tmp_path) -> None:
        import planbench_desktop.paths as paths_module

        repo = tmp_path / "repo"
        out = repo / "apps" / "web" / "out"
        out.mkdir(parents=True)
        (out / "index.html").write_text("<html></html>", encoding="utf-8")

        original = paths_module.INSTALL_ROOT
        paths_module.INSTALL_ROOT = repo
        try:
            assert paths_module.web_root() == out
        finally:
            paths_module.INSTALL_ROOT = original

    def test_with_no_export_anywhere_it_names_the_installed_path(self, tmp_path) -> None:
        """So the API's warning tells an operator where to put it."""
        import planbench_desktop.paths as paths_module

        original = paths_module.INSTALL_ROOT
        paths_module.INSTALL_ROOT = tmp_path / "nothing" / "app"
        try:
            assert paths_module.web_root() == tmp_path / "nothing" / "web"
        finally:
            paths_module.INSTALL_ROOT = original


class TestTheDownloadLinkStaysValid:
    """The asset name is part of the URL people are given.

    `/releases/latest/download/PlanBench-Setup.exe` resolves only while
    every release publishes an asset under that exact name. Putting the
    version back in the file name silently invalidates the link the day
    the next version ships — and the person who finds out is whoever
    clicked it.
    """

    def test_the_installer_is_named_without_a_version(self) -> None:
        script = (INSTALLER / "planbench.iss").read_text(encoding="utf-8")

        names = [ln for ln in script.splitlines() if ln.startswith("OutputBaseFilename")]

        assert names == ["OutputBaseFilename=PlanBench-Setup"]

    def test_the_version_is_still_reachable_from_inside_the_app(self) -> None:
        """Dropping it from the file name is only safe because the build
        reports it: the System page reads it from the API, which the
        launcher sets from the stamp the installer wrote."""
        provision = (
            INSTALL_ROOT / "apps" / "desktop" / "planbench_desktop" / "provision.py"
        ).read_text(encoding="utf-8")

        assert 'os.environ["PLANBENCH_VERSION"] = paths.version()' in provision

"""The SDK behind the settings page has to travel with the installer.

The Settings page offers a field for an API key. `AgentSettings.ready`
turns true only when a key is present **and** the SDK is importable —
`provider_status()` decides the second half with `_can_import("openai")`.

From source that is a fair split: whoever pastes the key can also run
`pip install openai`. In the packaged desktop app it is not. The build
installs `requirements.txt` into an embeddable Python that reads a
`._pth`, not a virtualenv, and a person running the installer has no way
to add a package to it. With the SDK left out, that field accepted a
key, saved it, and could never use it — a button that cannot succeed on
the artifact it ships in.

These tests pin the fix rather than the wiring: the SDK is a hard
dependency, and the file that ships it is the one the desktop build
reads.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _requirements() -> str:
    return (REPO / "requirements.txt").read_text(encoding="utf-8")


class TestTheSdkShipsWithTheApp:
    def test_openai_is_a_hard_dependency(self) -> None:
        assert re.search(r"^openai==", _requirements(), re.MULTILINE), (
            "the settings page offers a key field that cannot work without it"
        )

    def test_it_is_pinned_rather_than_ranged(self) -> None:
        """Every other line in this file pins exactly. A range would let
        the installer and the machine it was built on ship different
        clients, which is the shape of the bug this fixes."""
        line = next(row for row in _requirements().splitlines() if row.strip().startswith("openai"))
        assert "==" in line and ">=" not in line, line

    def test_it_is_not_also_offered_as_optional(self) -> None:
        """`requirements-optional.txt` used to carry it under "LLM thật
        cho Trợ lý AI". Two files disagreeing about whether a dependency
        is required is how it went missing from the build."""
        optional = (REPO / "requirements-optional.txt").read_text(encoding="utf-8")
        offers = [
            row
            for row in optional.splitlines()
            if re.match(r"^\s*#?\s*openai\s*==", row) and "requirements.txt" not in row
        ]
        assert offers == [], offers


class TestTheDesktopBuildInstallsThatFile:
    """The pin is only worth anything if the build reads it. This is the
    link between the two, and it is a single line in a PowerShell script
    that nothing else would notice changing."""

    def test_the_build_installs_requirements_txt_into_the_runtime(self) -> None:
        script = (REPO / "scripts" / "build_desktop.ps1").read_text(encoding="utf-8")
        assert "-r (Join-Path $RepoRoot 'requirements.txt')" in script
        assert "--target $SitePackages" in script

    def test_the_runtime_is_not_a_virtualenv(self) -> None:
        """Why the user cannot fix a missing package themselves, stated
        where somebody deciding to move a dependency back out would read
        it."""
        script = (REPO / "scripts" / "build_desktop.ps1").read_text(encoding="utf-8")
        assert "._pth" in script


class TestSettingsStillReportsWhatIsMissing:
    """Shipping the SDK does not make the readiness check redundant: a
    key can still be absent, and `anthropic` is still not shipped."""

    def test_readiness_needs_both_a_key_and_the_sdk(self) -> None:
        source = (REPO / "services" / "agent_service" / "planbench_agent" / "factory.py").read_text(
            encoding="utf-8"
        )
        assert '_can_import("openai")' in source
        assert '_can_import("anthropic")' in source

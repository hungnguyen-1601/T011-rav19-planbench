"""The code's contract version must match the contract document.

A card stamped with the wrong ``contracts_version`` claims to have been
produced under rules it was not produced under, which breaks HĐ-13's
acceptance criterion without breaking anything visible.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from planbench_schemas.contracts import CONTRACTS_VERSION

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "CONTRACTS.md"
_HEADER = re.compile(r"`contracts_version:\s*(?P<version>\d+\.\d+\.\d+)`")
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


@pytest.fixture(scope="module")
def contract_text() -> str:
    assert CONTRACT_PATH.is_file(), f"contract document missing at {CONTRACT_PATH}"
    return CONTRACT_PATH.read_text(encoding="utf-8")


def test_code_version_is_semver() -> None:
    assert _SEMVER.match(CONTRACTS_VERSION), CONTRACTS_VERSION


def test_code_matches_document(contract_text: str) -> None:
    match = _HEADER.search(contract_text)
    assert match is not None, "no `contracts_version: x.y.z` in the contract header"
    assert match.group("version") == CONTRACTS_VERSION, (
        f"contracts/CONTRACTS.md says {match.group('version')} but "
        f"planbench_schemas.contracts says {CONTRACTS_VERSION}; bump both in one PR"
    )


def test_version_history_records_this_version(contract_text: str) -> None:
    """HĐ-0 requires a reason for every bump, and section 18 is where it
    goes — a version with no entry cannot be reviewed."""
    history = contract_text.split("## 18. Lịch sử phiên bản", 1)
    assert len(history) == 2, "section 18 (version history) is missing"
    assert f"| {CONTRACTS_VERSION} |" in history[1], (
        f"version {CONTRACTS_VERSION} has no row in the version-history table"
    )


def test_json_examples_quote_the_current_version(contract_text: str) -> None:
    """Someone copying the Decision Card or manifest example must not
    paste a stale version string into new code."""
    quoted = set(re.findall(r'"contracts_version":\s*"([^"]+)"', contract_text))
    assert quoted, "no JSON example carries contracts_version"
    assert quoted == {CONTRACTS_VERSION}, f"stale versions in JSON examples: {quoted}"

"""The English Markdown export, frozen byte for byte.

**What this guards and why it is worth a file on disk.** The export is
about to grow a second language, three new sheets and a numeric layer.
Every one of those changes reaches into `decision_export`, which both
renderers read from — so every one of them can move the Markdown without
anybody meaning to.

That matters because the Markdown is a document people *keep*. Somebody
pastes it into a ticket and somebody else re-exports the same run six
months later; if the two differ, the diff is read as the run having
changed. It did not.

So: `locale="en"` output is frozen here, and the default must equal it.
Vietnamese is output that is *added*, never output that *replaces*. A
failure in this file is not a stale snapshot to refresh — it is the
question "did you mean to change what an English reader receives?", and
the answer is almost always no.

Regenerate deliberately, never reflexively:

    WRITE_GOLDEN=1 pytest tests/api/test_decision_export_golden.py

Through pytest rather than a standalone script because `planbench_api`
resolves off the ``pythonpath`` in ``pyproject.toml``; a script run with
plain ``python`` would need its own copy of that list.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from planbench_api.decision_markdown import render_decision_markdown
from tests.api.golden_run import golden_run, unranked_run

GOLDEN = Path(__file__).resolve().parents[1] / "golden"

#: Both branches, because they take different paths through the renderer
#: and a snapshot of only the ranked one leaves the branch most runs
#: actually take unguarded.
CASES = {
    "decision_report_en.md": golden_run,
    "decision_report_unranked_en.md": unranked_run,
}


def _render(build) -> str:
    return render_decision_markdown(build())


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_english_markdown_has_not_moved(name: str) -> None:
    rendered = _render(CASES[name])
    path = GOLDEN / name
    if os.environ.get("WRITE_GOLDEN"):
        GOLDEN.mkdir(parents=True, exist_ok=True)
        # `newline=""` so the file lands with the "\n" the renderer wrote
        # rather than the platform's. A snapshot that gains "\r\n" on
        # Windows and loses it on CI is a diff about the machine.
        path.write_text(rendered, encoding="utf-8", newline="")
        pytest.skip(f"rewrote {name}")
    assert rendered == path.read_text(encoding="utf-8", newline=""), (
        f"{name} changed. If that was deliberate, regenerate with "
        "`WRITE_GOLDEN=1 pytest tests/api/test_decision_export_golden.py` and say so in "
        "the commit; if it was not, the change reached the English export by accident."
    )

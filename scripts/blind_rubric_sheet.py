"""Turn a sweep artifact into a scoring sheet nobody can read the arm off.

The endpoint this experiment is about cannot be computed. These episodes
carry no planted mechanism, so whether a hypothesis holds up is read by
a person against the packet — and a person who can see which arm wrote a
sentence is not reading the sentence.

Two files come out: the sheet, which carries statements and nothing
identifying, and the key, which maps each item back. The order is fixed
by a hash of the item's own identity rather than by chance, so the same
artifact always produces the same sheet and a re-run cannot be quietly
reordered until it reads better.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

RUBRIC = "r0.1.0"


def item_order(item: dict[str, Any]) -> str:
    seed = f"{item['episode']}|{item['hypothesis_id']}|{item['arm']}|{item['repeat']}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    source = Path(args.artifact)
    payload = json.loads(source.read_text(encoding="utf-8"))
    out = Path(args.out) if args.out else source.with_suffix("")

    items: list[dict[str, Any]] = []
    for row in payload["results"]:
        if "model_failed" in row:
            continue
        if row["abstained"]:
            items.append(
                {
                    "arm": row["arm"],
                    "cluster": row["cluster"],
                    "episode": row["episode"],
                    "role": row["role"],
                    "repeat": row["repeat"],
                    "hypothesis_id": "-abstained-",
                    "statement": "",
                    "bearing": "",
                    "subject": "",
                    "supports": [],
                    "abstention_reason": row["abstention_reason"],
                }
            )
            continue
        for proposal in row["proposals"]:
            items.append(
                {
                    "arm": row["arm"],
                    "cluster": row["cluster"],
                    "episode": row["episode"],
                    "role": row["role"],
                    "repeat": row["repeat"],
                    "hypothesis_id": proposal["hypothesis_id"],
                    "statement": proposal["statement"],
                    "bearing": proposal["bearing"],
                    "subject": proposal["subject"],
                    "proposition_type": proposal["proposition_type"],
                    "supports": proposal["supports"],
                    "contract": proposal.get("contract", []),
                    "abstention_reason": "",
                }
            )

    items.sort(key=item_order)

    lines = [
        f"# Chấm tay, mù arm — {payload['label']} (rubric {RUBRIC})",
        "",
        f"Nguồn: `{source.name}` · {len(items)} mục · "
        f"preregistration `{payload['preregistration_checksum'][:12]}`",
        "",
        "Mỗi mục: mở packet của episode đó ra đọc, rồi điền. **R1** hypothesis",
        "có đứng vững trước packet không (`holds` / `plausible_other` / `wrong`);",
        "**R2** `subject` có đúng thành phần câu nói tới không (`yes`/`no`);",
        "**R3** mọi ref mở được và nói về đúng mechanism (`all`/`some`/`none`);",
        "**R5** chỗ abstain có đúng chỗ không (`correct`/`should_have`/`should_not`).",
        "",
        "Không có mục nào nói arm nào viết nó. Đừng đoán.",
        "",
    ]
    for index, item in enumerate(items, start=1):
        lines.append(f"## {index:03d} · episode `{item['episode']}` · {item['role']}")
        lines.append("")
        if item["hypothesis_id"] == "-abstained-":
            lines.append("**Không đề xuất gì.** Lý do analyst đưa ra:")
            lines.append("")
            lines.append(f"> {item['abstention_reason']}")
            lines.append("")
            lines.append("| R1 | R2 | R3 | R5 |")
            lines.append("|---|---|---|---|")
            lines.append("| n/a | n/a | n/a |  |")
        else:
            lines.append(f"> {item['statement']}")
            lines.append("")
            lines.append(
                f"- register: `{item['bearing']}` · subject: `{item['subject']}` · "
                f"type: `{item['proposition_type']}`"
            )
            lines.append(f"- refs: {', '.join(f'`{ref}`' for ref in item['supports']) or '—'}")
            if item["contract"]:
                lines.append(f"- contract: {', '.join(f'`{term}`' for term in item['contract'])}")
            lines.append("")
            lines.append("| R1 | R2 | R3 | R5 |")
            lines.append("|---|---|---|---|")
            lines.append("|  |  |  | n/a |")
        lines.append("")

    sheet = out.with_name(out.name + "-rubric-sheet.md")
    key = out.with_name(out.name + "-rubric-key.json")
    sheet.write_text("\n".join(lines), encoding="utf-8")
    key.write_text(
        json.dumps(
            [
                {
                    "index": index,
                    "arm": item["arm"],
                    "episode": item["episode"],
                    "cluster": item["cluster"],
                    "repeat": item["repeat"],
                    "hypothesis_id": item["hypothesis_id"],
                }
                for index, item in enumerate(items, start=1)
            ],
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"wrote {sheet}\nwrote {key}\n{len(items)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

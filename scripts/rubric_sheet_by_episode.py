"""One page per episode: the packet once, then every claim made about it.

The first sheet ordered items by a hash of their own identity, which hid
the arm and also scattered the episodes — item 1 about one episode, item
2 about another, item 3 about a third. A person scoring that opens a
packet, reads it, judges one sentence, and opens a different packet.
Three hundred and fifty two times.

The episode id was printed on every item all along, so ordering by
episode reveals nothing the sheet did not already show. Grouping by it
turns three hundred packet lookups into seventeen: read the episode
once, judge everything said about it, move on.

What still has to stay hidden is the arm, so items are shuffled inside
each group by the same hash as before, and several artifacts fold into
one sheet — which hides not only which arm wrote a sentence but which
sweep it came from.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
RUBRIC = "r0.1.0"


def _sweep():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "run_episode_experiments", REPO / "scripts" / "run_episode_experiments.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def order_key(item: dict[str, Any]) -> str:
    """Stable, and blind to everything a scorer must not see."""
    seed = "|".join(
        (
            item["episode"],
            item["hypothesis_id"],
            item["arm"],
            str(item["repeat"]),
            item["stage"],
        )
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def items_from(payload: dict[str, Any], stage: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in payload["results"]:
        if "model_failed" in row:
            continue
        common = {
            "stage": stage,
            "arm": row["arm"],
            "cluster": row["cluster"],
            "episode": row["episode"],
            "role": row["role"],
            "repeat": row["repeat"],
        }
        if row["abstained"]:
            items.append(
                {
                    **common,
                    "hypothesis_id": "-abstained-",
                    "abstention_reason": row["abstention_reason"],
                }
            )
            continue
        for proposal in row["proposals"]:
            items.append(
                {
                    **common,
                    "hypothesis_id": proposal["hypothesis_id"],
                    "statement": proposal["statement"],
                    "bearing": proposal["bearing"],
                    "subject": proposal["subject"],
                    "proposition_type": proposal["proposition_type"],
                    "supports": proposal["supports"],
                    "contract": proposal.get("contract", []),
                }
            )
    return items


def header(items: list[dict[str, Any]], episodes: int, sources: list[str]) -> list[str]:
    named = ", ".join("`" + Path(path).stem + "`" for path in sources)
    return [
        "# Cham tay, mu arm - gom theo episode (rubric " + RUBRIC + ")",
        "",
        f"{len(items)} muc | {episodes} episode | nguon: {named}",
        "",
        "Moi episode: doc khoi **PACKET** mot lan, roi cham moi muc duoi no.",
        "",
        "- **R1** hypothesis dung vung truoc packet khong - `holds` / `plausible_other` / `wrong`",
        "- **R2** `subject` co dung thanh phan cau noi toi khong - `yes` / `no`",
        "- **R3** moi ref mo duoc trong packet **va** noi ve dung mechanism"
        " - `all` / `some` / `none`",
        "- **R5** cho khong de xuat gi: im lang co dung cho khong - `correct` / `should_have`",
        "",
        "Khong muc nao noi arm nao viet no, cung khong noi no thuoc luot chay nao.",
        "Dung doan.",
        "",
    ]


def _number(value: Any) -> str:
    """Rounded, because a scorer reads these and 51.54999999999869 is
    the same fact as 51.55 with eleven digits of noise in front of it."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "" if value is None else str(value)
    return f"{value:g}" if abs(value - round(value)) > 1e-9 else str(int(round(value)))


def packet_table(view: Any) -> list[str]:
    """The packet as a person reads it, not as the model receives it.

    The model gets one line of JSON and that is correct for the model.
    A scorer given the same line is being asked to parse it by eye,
    which is where a scoring pass stops happening. Same facts, same
    refs, arranged so the verdict is at the top and each contrast sits
    above the numbers behind it.
    """
    facts = json.loads(view.serialize())["facts"]
    by_ref = {fact["ref"]: fact for fact in facts}

    def rows_for(prefix: str) -> list[dict[str, Any]]:
        return [fact for fact in facts if fact["ref"].startswith(prefix) and "/" not in fact["ref"]]

    lines = ["<details open><summary><b>PACKET</b></summary>", ""]

    verdict = {fact["ref"]: fact["value"] for fact in facts if fact["ref"].startswith("verdict:")}
    if verdict:
        lines += [
            "**Phan quyet**: "
            + str(verdict.get("verdict:basis", "?"))
            + " | thang: `"
            + str(verdict.get("verdict:winner", "-"))
            + "` | thua: `"
            + str(verdict.get("verdict:loser", "-"))
            + "`",
            "",
        ]

    contrasts = rows_for("contrast:")
    if contrasts:
        lines += [
            "**Khac biet giua hai ben**",
            "",
            "| ref | strength | noi gi | so kem theo |",
            "|---|---|---|---|",
        ]
        for fact in contrasts:
            children = [
                other["label"].replace(" behind that difference", "")
                + " = "
                + _number(other["value"])
                for ref, other in by_ref.items()
                if ref.startswith(fact["ref"] + "/")
            ]
            lines.append(
                "| `"
                + fact["ref"]
                + "` | **"
                + str(fact["value"])
                + "** | "
                + fact["label"]
                + " | "
                + ("; ".join(children) or "-")
                + " |"
            )
        lines.append("")

    observations = rows_for("obs:")
    if observations:
        lines += ["**Detector da ban**", "", "| ref | tren ai | so kem theo |", "|---|---|---|"]
        for fact in observations:
            children = [
                # The tail of the ref rather than the label: the labels
                # for a window all read "where that stuck_cluster sits",
                # so four of them side by side name nothing.
                ref.split("/", 1)[1] + " = " + _number(other["value"])
                for ref, other in by_ref.items()
                if ref.startswith(fact["ref"] + "/")
            ]
            lines.append(
                "| `"
                + fact["ref"]
                + "` | `"
                + str(fact["candidate_id"])
                + "` | "
                + ("; ".join(children) or "-")
                + " |"
            )
        lines.append("")

    diag = [fact for fact in facts if fact["ref"].startswith("diag:")]
    if diag:
        per: dict[str, list[str]] = defaultdict(list)
        for fact in diag:
            name = fact["ref"].split(".", 1)[-1]
            per[str(fact["candidate_id"])].append(f"{name} = {_number(fact['value'])}")
        lines += ["**So do duoc cua tung ben**", ""]
        for candidate in sorted(per):
            lines.append("- `" + candidate + "`: " + " | ".join(per[candidate]))
        lines.append("")

    unknowns = [fact for fact in facts if fact["ref"].startswith("unknown:")]
    if unknowns:
        lines += ["**Khong biet duoc tu episode nay**", ""]
        lines += ["- " + fact["label"] for fact in unknowns]
        lines.append("")

    components = [fact for fact in facts if fact["ref"].startswith("fact:candidate:")]
    if components:
        per_c: dict[str, list[str]] = defaultdict(list)
        for fact in components:
            per_c[str(fact["candidate_id"])].append(
                fact["label"].split(" of ")[0] + " = `" + str(fact["value"]) + "`"
            )
        lines += ["**Thanh phan moi ben**", ""]
        for candidate in sorted(per_c):
            lines.append("- `" + candidate + "`: " + " | ".join(per_c[candidate]))
        lines.append("")

    caveat = verdict.get("verdict:caveat")
    if caveat:
        lines += ["> " + str(caveat), ""]
    lines += ["</details>", ""]
    return lines


def render_item(number: int, item: dict[str, Any]) -> list[str]:
    if item["hypothesis_id"] == "-abstained-":
        return [
            f"### {number:03d} - **khong de xuat gi**",
            "",
            "> " + item["abstention_reason"],
            "",
            "| R1 | R2 | R3 | R5 |",
            "|---|---|---|---|",
            "| n/a | n/a | n/a |  |",
            "",
        ]
    refs = ", ".join("`" + ref + "`" for ref in item["supports"]) or "-"
    lines = [
        f"### {number:03d}",
        "",
        "> " + item["statement"],
        "",
        "- register: `"
        + item["bearing"]
        + "` | subject: `"
        + item["subject"]
        + "` | type: `"
        + item["proposition_type"]
        + "`",
        "- refs: " + refs,
    ]
    if item["contract"]:
        lines.append("- contract: " + ", ".join("`" + term + "`" for term in item["contract"]))
    lines += ["", "| R1 | R2 | R3 | R5 |", "|---|---|---|---|", "|  |  |  | n/a |", ""]
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="+")
    parser.add_argument("--runs", required=True, help="Where the comparison reports are.")
    parser.add_argument("--traces", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    items: list[dict[str, Any]] = []
    for path in args.artifacts:
        source = Path(path)
        items.extend(items_from(json.loads(source.read_text(encoding="utf-8")), source.stem))

    sweep = _sweep()
    views: dict[str, Any] = {}
    for report in sorted(Path(args.runs).glob("*/*/comparison_report.json")):
        for case in sweep.cases_from(report, Path(args.traces)):
            views[case["episode"]] = (case, sweep.build_episode_view(case["packet"]))

    by_episode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_episode[item["episode"]].append(item)

    lines = header(items, len(by_episode), args.artifacts)
    key_rows: list[dict[str, Any]] = []
    number = 0
    for episode in sorted(by_episode):
        group = sorted(by_episode[episode], key=order_key)
        lines += ["---", "", "# Episode `" + episode + "`", ""]
        entry = views.get(episode)
        if entry is None:
            # Said rather than skipped: a scorer who cannot see the packet
            # is guessing, and a blank here reads as nothing to judge.
            lines += ["> **Khong dung lai duoc packet cho episode nay.**", ""]
        else:
            case, view = entry
            lines += [
                "*cluster: " + case["cluster"] + " | vai: " + case["role"] + "*",
                "",
            ]
            lines += packet_table(view)
        for item in group:
            number += 1
            lines += render_item(number, item)
            key_rows.append(
                {
                    "index": number,
                    "stage": item["stage"],
                    "arm": item["arm"],
                    "episode": item["episode"],
                    "cluster": item["cluster"],
                    "repeat": item["repeat"],
                    "hypothesis_id": item["hypothesis_id"],
                }
            )

    out = Path(args.out)
    out.write_text("\n".join(lines), encoding="utf-8")
    key = out.with_name(out.stem + "-key.json")
    key.write_text(json.dumps(key_rows, indent=1), encoding="utf-8")
    print("wrote " + str(out))
    print("wrote " + str(key))
    print(f"{number} muc | {len(by_episode)} episode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

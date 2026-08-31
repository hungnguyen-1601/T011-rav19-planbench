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
RUBRIC = "r0.2.0"
RUBRIC_COLUMNS = ["R1", "R2", "R3", "R5"]


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
            # **Who is speaking.** With the floor fallback on, a round
            # whose every proposal was refused still returns sentences —
            # deterministic ones built from the packet, reporting what
            # fired. A scorer shown those without being told would credit
            # the analyst for statements no model wrote, and the number
            # that matters most — `explains` over the episodes a packet
            # could answer — would be inflated by exactly the rounds
            # where the analyst failed hardest.
            "by_floor": any(flag[0] == "answered_by_floor" for flag in (row.get("flags") or [])),
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
        "**R6 cham theo episode, khong theo cau.** R1-R5 hoi *cau nay co dung khong*;"
        " mot arm im lang ca episode van dat diem cao, va do la chuyen da xay ra."
        " R6 hoi dung cau hoi cua thi nghiem: **episode nay, no co noi duoc vi sao"
        " ben thang hon ben thua khong**.",
        "",
        "- `explains` - neu mot mechanism khac nhau giua hai ben **va** noi vao"
        " ket qua, co ref mo duoc",
        "- `describes_only` - dung, nhung chi ta chuyen gi xay ra; khong tra loi"
        " vi sao ben nay hon",
        "- `silent_wrongly` - packet co du de tra loi ma khong noi gi",
        "- `silent_correctly` - packet that su khong do duoc cau why",
        "- `wrong` - khang dinh mot why ma packet phan lai",
        "",
        "Mau so **do sheet tinh, khong phai nguoi cham quyet**: episode nao co it"
        " nhat mot contrast `support` thi duoi tieu de co dong"
        " `packet co the tra loi why`. Cham `silent_correctly` o mot episode nhu"
        " the la mau thuan voi packet.",
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


def marks_already_given(path: Path) -> dict[tuple[str, int], list[str]]:
    """R1-R5 as a previous sheet was scored, keyed by episode and block.

    **So an amended rubric does not cost a re-read of what was already
    read.** r0.2.0 adds one judgement per episode and changes none of
    the per-statement ones, so asking for all thirty-seven blocks again
    would be asking somebody to re-derive marks they have already made,
    with the previous answers visible on the next monitor. The parts
    that did not change are carried, and the sheet only leaves blank
    what is genuinely new.

    Ordering is what makes the key safe: blocks are numbered from a
    hash of the item's own identity, so the same artifacts regenerate in
    the same order and block 007 of an episode is the same sentence it
    was. The episode id is carried alongside the number anyway, so a
    sheet built from a *different* set of artifacts fails to match
    rather than silently pasting one episode's marks onto another's.
    """
    carried: dict[tuple[str, int], list[str]] = {}
    episode = ""
    number = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# Episode `"):
            episode = line.split("`")[1]
            # The packet under this heading is itself a four-column
            # table. Without this the first block of the episode after
            # it would inherit the previous episode's number and claim
            # rows out of a packet as somebody's marks.
            number = 0
        elif line.startswith("### "):
            digits = line[4:7]
            number = int(digits) if digits.isdigit() else 0
        elif line.startswith("|") and number and episode:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            # The header names the columns and the rule below it is all
            # dashes; neither is somebody's judgement, and the first row
            # that is wins because `setdefault` keeps it.
            if len(cells) != 4 or cells == RUBRIC_COLUMNS or not set("".join(cells)) - set("-"):
                continue
            carried[(episode, number)] = cells
            # One table per block, and it is the one directly under the
            # heading. Anything below it belongs to something else.
            number = 0
    return carried


def answerable(view: Any) -> bool:
    """Did this episode's packet carry an answer to *why one side won*.

    **The sheet decides this, not the scorer.** R6 asks whether an arm
    explained the difference, and an arm that says nothing has two very
    different excuses: the packet held a mechanism and it missed it, or
    the packet held none and silence was the only honest move. Leaving
    that to the person scoring makes them re-derive the denominator by
    eye, thirty times, from the same table the sheet already printed —
    and a denominator somebody eyeballs is one an arm can be flattered
    by.

    `support` is the strength the packet itself assigns to a contrast
    that carries evidence, as against `context`, which only says the two
    stacks differ somewhere. So the predicate is the packet's own word
    for "this one can be leaned on", not a second opinion about it.
    """
    return any(
        fact.ref.startswith("contrast:") and str(fact.value) == "support" for fact in view.facts
    )


def episode_mark(view: Any | None, by_floor: bool = False) -> list[str]:
    """The one judgement that is about the episode rather than a sentence.

    Carries who wrote the sentences below it. The floor answers from the
    packet when a round loses everything, and what it produces reads like
    an analyst's output while being neither a mechanism nor an
    explanation — "stuck cluster was detected on C1". Scored blind
    against `explains` it would count as the analyst succeeding on the
    rounds where the analyst was refused outright.
    """
    if view is None:
        return []
    note = (
        "> **packet co the tra loi why** - co contrast `support`."
        if answerable(view)
        else "> packet khong co contrast `support`."
    )
    lines = [
        "**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**",
        "",
        note,
    ]
    if by_floor:
        lines += [
            ">",
            "> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi;"
            " cac cau duoi day do floor sinh tu packet. Voi R6 day la"
            " analyst **im lang** - `explains` khong the cham o day.",
        ]
    return lines + ["", "| R6 |", "|---|", "|  |", ""]


def readable(statement: str, view: Any) -> str:
    """The sentence as a reader meets it, slots filled.

    A statement may name a magnitude as a ref in braces rather than
    writing the figure; the platform fills it in when somebody opens the
    episode. A scorer shown the raw slot is judging a sentence nobody is
    ever served, so this fills them the same way the API does — and
    leaves the slot visible when it cannot, because a scorer owed a
    number should see that one is missing rather than a tidied sentence.
    """
    from planbench_explanation.magnitudes import render, unresolvable

    facts = {fact.ref: fact.value for fact in view.facts}
    if unresolvable(statement, facts):
        return statement
    return render(statement, facts)


def render_item(number: int, item: dict[str, Any], carried: list[str] | None = None) -> list[str]:
    def row(default: list[str]) -> str:
        return "| " + " | ".join(carried or default) + " |"

    if item["hypothesis_id"] == "-abstained-":
        return [
            f"### {number:03d} - **khong de xuat gi**",
            "",
            "> " + item["abstention_reason"],
            "",
            "| R1 | R2 | R3 | R5 |",
            "|---|---|---|---|",
            row(["n/a", "n/a", "n/a", ""]),
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
    lines += [
        "",
        "| R1 | R2 | R3 | R5 |",
        "|---|---|---|---|",
        row(["", "", "", "n/a"]),
        "",
    ]
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="+")
    parser.add_argument("--runs", required=True, help="Where the comparison reports are.")
    parser.add_argument("--traces", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--carry",
        help="A sheet already scored under the previous rubric: its R1-R5 marks "
        "are copied in, so only what the amendment added is left blank.",
    )
    args = parser.parse_args()
    carried = marks_already_given(Path(args.carry)) if args.carry else {}

    items: list[dict[str, Any]] = []
    for path in args.artifacts:
        source = Path(path)
        items.extend(items_from(json.loads(source.read_text(encoding="utf-8")), source.stem))

    sweep = _sweep()
    views: dict[str, Any] = {}
    for report in sorted(Path(args.runs).glob("*/*/comparison_report.json")):
        # **Every episode, not the four exemplars.** A sheet is built
        # from whatever a sweep read, and a sweep run with
        # --every-episode reads all thirty; asking for the exemplars
        # here left twenty-seven episodes with items to score and no
        # packet above them to score against. It did not even say so
        # until later, so the first sheet built this way was scored by
        # somebody reading three packets and judging thirty episodes.
        for case in sweep.cases_from(report, Path(args.traces), every_episode=True):
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
        # **One R6 per round, not per episode.** With repeats above one
        # an episode is several rounds, and they disagree: on the
        # three-reading sweep the model spoke on some readings of an
        # episode and was refused outright on others, twelve times out
        # of eighteen. A single mark for the episode would ask the
        # scorer to average that by eye, and the majority — the whole
        # reason for reading three times — would never be written down.
        #
        # The round number is not the arm, so showing it hides nothing
        # the sheet is meant to hide.
        rounds = sorted({item["repeat"] for item in group})
        for repeat in rounds:
            batch = [item for item in group if item["repeat"] == repeat]
            if len(rounds) > 1:
                lines += ["## Luot " + str(repeat + 1) + "/" + str(len(rounds)), ""]
            lines += episode_mark(
                entry[1] if entry is not None else None,
                by_floor=any(item.get("by_floor") for item in batch),
            )
            for item in batch:
                number += 1
                if entry is not None and item.get("statement"):
                    item = {**item, "statement": readable(item["statement"], entry[1])}
                lines += render_item(number, item, carried.get((episode, number)))
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
    if args.carry:
        print(f"{len(carried)} muc mang sang tu {args.carry}; R6 con trong")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

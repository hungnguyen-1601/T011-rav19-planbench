"""Every word an export prints, in both languages, in one table.

**Why the strings left the code they were written in.** The platform is
bilingual and the exports were not: a reader working in Vietnamese
pressed Export and received an English document. That is not a
formatting complaint. The caveats are the part of these files that does
the most work — the scope limit, the unpinned host, "null means not
measured" — and a caveat in a language the reader does not use is a
caveat that does not travel.

**English is the anchor, Vietnamese is added.** The Markdown export is a
document people keep: pasted into a ticket, re-exported six months
later, diffed against the copy already filed. So ``locale="en"`` output
is frozen byte for byte by the golden snapshots, and every entry here
carries the English exactly as it was before this table existed. Adding
a language must not change what an English reader receives.

**No fallback.** A missing key raises rather than quietly serving the
English. A document half-translated is worse than one consistently in
the wrong language: the reader cannot tell which half was a translation
choice and which half is a hole, and a caveat is exactly the kind of
sentence that would go missing first.

**The Vietnamese is not shorter than the English.** Several of these are
three-sentence paragraphs explaining why a number may not be read the
way it looks. Compressing them in translation would remove the part
that does the work and leave the part that decorates.
"""

from __future__ import annotations

from typing import Final, Literal

Locale = Literal["en", "vi"]

#: The languages an export can be rendered in. ``en`` first because it
#: is the default and the frozen one.
LOCALES: Final[tuple[Locale, ...]] = ("en", "vi")

DEFAULT_LOCALE: Final[Locale] = "en"


class MissingTranslation(KeyError):
    """A key with no entry, or an entry missing a language.

    Raised rather than resolved: see the module docstring. This is a
    programming error surfaced at the moment the document is built, not
    a condition a reader should ever be shown.
    """


#: key -> {locale -> string}. Grouped by what the string is, not by
#: which module prints it, because several are printed by both renderers
#: and a grouping by caller would have to pick one.
TEXT: Final[dict[str, dict[Locale, str]]] = {
    # --- Words that stand in for a value ---------------------------------
    "value.not_measured": {"en": "not measured", "vi": "chưa đo"},
    "value.not_recorded": {"en": "not recorded", "vi": "không được ghi lại"},
    "value.yes": {"en": "yes", "vi": "có"},
    "value.no": {"en": "no", "vi": "không"},
    "value.passed": {"en": "passed", "vi": "đạt"},
    "value.blocked": {"en": "blocked: {gates}", "vi": "bị chặn: {gates}"},
    # --- Provenance -------------------------------------------------------
    "label.run_id": {"en": "Run id", "vi": "Mã lần chạy"},
    "label.deployment": {"en": "Deployment", "vi": "Điểm triển khai"},
    "label.experiment_scope": {"en": "Experiment scope", "vi": "Phạm vi thí nghiệm"},
    "label.contracts_version": {"en": "Contracts version", "vi": "Phiên bản hợp đồng"},
    "label.code_version": {"en": "Code version", "vi": "Phiên bản mã nguồn"},
    "label.anchor_config": {"en": "Anchor config", "vi": "Cấu hình mốc chuẩn"},
    "label.run_at": {"en": "Run", "vi": "Thời điểm chạy"},
    # --- Sample -----------------------------------------------------------
    "label.episodes_measured": {"en": "Episodes measured", "vi": "Số episode đã đo"},
    "label.episodes_requested": {"en": "Episodes requested", "vi": "Số episode đã yêu cầu"},
    "label.interrupted": {"en": "Interrupted", "vi": "Bị ngắt giữa chừng"},
    "label.minimum_required": {
        "en": "Minimum required (HĐ-7.1)",
        "vi": "Số tối thiểu bắt buộc (HĐ-7.1)",
    },
    # --- Gate table -------------------------------------------------------
    "column.gate.candidate": {"en": "Candidate", "vi": "Ứng viên"},
    "column.gate.config": {"en": "Config", "vi": "Cấu hình"},
    "column.gate.shown": {"en": "Shown", "vi": "Được nhìn thấy"},
    "column.gate.distinct_episodes": {"en": "Distinct episodes", "vi": "Episode khác biệt"},
    "column.gate.success": {"en": "Success", "vi": "Tỉ lệ thành công"},
    "column.gate.p99": {"en": "p99 latency", "vi": "Độ trễ p99"},
    "column.gate.replans": {"en": "Replans", "vi": "Số lần lập lại lộ trình"},
    "column.gate.verdict": {"en": "Verdict", "vi": "Phán quyết"},
    # --- Outcome table ----------------------------------------------------
    "column.outcome.candidate": {"en": "Candidate", "vi": "Ứng viên"},
    "column.outcome.config": {"en": "Config", "vi": "Cấu hình"},
    "column.outcome.utility": {"en": "Utility /100", "vi": "Điểm tổng /100"},
    "column.outcome.u_r": {"en": "U_R", "vi": "U_R"},
    "column.outcome.u_s": {"en": "U_S", "vi": "U_S"},
    "column.outcome.u_e": {"en": "U_E", "vi": "U_E"},
    "column.outcome.u_c": {"en": "U_C", "vi": "U_C"},
    "column.outcome.success": {"en": "Success", "vi": "Tỉ lệ thành công"},
    "column.outcome.collisions": {"en": "Collisions", "vi": "Va chạm"},
    "column.outcome.collision_bound": {
        "en": "Collision bound 95%",
        "vi": "Cận trên va chạm 95%",
    },
    "column.outcome.no_route": {"en": "No route found", "vi": "Không tìm được lộ trình"},
    "column.outcome.worst_clearance": {"en": "Worst clearance", "vi": "Khoảng hở tệ nhất"},
    "column.outcome.median_episode": {"en": "Median episode", "vi": "Episode trung vị"},
    "column.outcome.p99": {"en": "p99 latency", "vi": "Độ trễ p99"},
    "column.outcome.memory": {"en": "Memory estimate", "vi": "Ước lượng bộ nhớ"},
    "column.outcome.distinct_episodes": {"en": "Distinct episodes", "vi": "Episode khác biệt"},
    "column.outcome.replans": {"en": "Replans", "vi": "Số lần lập lại lộ trình"},
    "column.outcome.eligible": {
        "en": "Eligible to recommend",
        "vi": "Đủ điều kiện được khuyến nghị",
    },
    # --- Episode table ----------------------------------------------------
    "column.episode.candidate": {"en": "Candidate", "vi": "Ứng viên"},
    "column.episode.episode": {"en": "Episode", "vi": "Episode"},
    "column.episode.outcome": {"en": "Outcome", "vi": "Kết quả"},
    "column.episode.collisions": {"en": "Collisions", "vi": "Va chạm"},
    "column.episode.min_clearance": {"en": "Min clearance", "vi": "Khoảng hở nhỏ nhất"},
    "column.episode.travel_time": {"en": "Travel time", "vi": "Thời gian di chuyển"},
    "column.episode.p99": {"en": "p99 latency", "vi": "Độ trễ p99"},
    "column.episode.replans": {"en": "Replans", "vi": "Số lần lập lại lộ trình"},
    "column.episode.utility": {"en": "Episode utility", "vi": "Điểm của episode"},
    # --- Decision card ----------------------------------------------------
    "label.recommended": {"en": "Recommended", "vi": "Được khuyến nghị"},
    "label.recommended_config": {"en": "Recommended config", "vi": "Cấu hình được khuyến nghị"},
    "label.candidate_id": {"en": "Candidate id", "vi": "Mã ứng viên"},
    "label.alternative": {"en": "Alternative", "vi": "Phương án thay thế"},
    "label.status": {"en": "Status", "vi": "Trạng thái"},
    "label.decision_utility": {"en": "Decision utility", "vi": "Điểm quyết định"},
    "label.pareto_label": {"en": "Pareto label", "vi": "Nhãn Pareto"},
    "label.decision_mode": {"en": "Decision mode", "vi": "Chế độ quyết định"},
    "label.delta_u_vs_second": {"en": "ΔU vs the runner-up", "vi": "ΔU so với á quân"},
    "label.delta_u_mean": {"en": "ΔU mean", "vi": "ΔU trung bình"},
    "label.delta_u_ci": {"en": "ΔU 95% interval", "vi": "Khoảng tin cậy 95% của ΔU"},
    "label.effect_size": {"en": "Effect size", "vi": "Cỡ hiệu ứng"},
    "label.episodes_compared": {"en": "Episodes compared", "vi": "Số episode đem so"},
    "label.objective": {"en": "Objective {name}", "vi": "Mục tiêu {name}"},
    "label.weight_stability": {
        "en": "Weight stability margin",
        "vi": "Biên ổn định theo trọng số",
    },
    "label.anchor_stability": {"en": "Anchor stability", "vi": "Độ ổn định của mốc chuẩn"},
    "label.robustness_margin": {"en": "Robustness margin", "vi": "Biên bền vững"},
    # --- Human record -----------------------------------------------------
    "label.review_state": {"en": "Review state", "vi": "Trạng thái duyệt đọc"},
    "label.reviewed_by": {"en": "Reviewed by", "vi": "Người đã đọc"},
    "label.reviewed_at": {"en": "Reviewed at", "vi": "Thời điểm đọc"},
    "label.config_state": {"en": "Configuration decision", "vi": "Quyết định về cấu hình"},
    "label.decided_by": {"en": "Decided by", "vi": "Người quyết định"},
    "label.decided_at": {"en": "Decided at", "vi": "Thời điểm quyết định"},
    # --- Headings ---------------------------------------------------------
    "heading.document": {"en": "Selection run — {profile}", "vi": "Lần chạy chọn lựa — {profile}"},
    "heading.provenance": {"en": "Provenance", "vi": "Nguồn gốc"},
    "heading.sample": {"en": "Sample", "vi": "Mẫu"},
    "heading.gates": {"en": "Gates", "vi": "Các cổng sàng lọc"},
    "heading.outcome": {"en": "Outcome by candidate", "vi": "Kết quả theo từng ứng viên"},
    "heading.card": {"en": "Decision Card", "vi": "Thẻ quyết định"},
    "heading.no_card": {"en": "No Decision Card", "vi": "Không có Thẻ quyết định"},
    "heading.episodes": {"en": "Episodes", "vi": "Các episode"},
    "heading.human": {"en": "Human record", "vi": "Ghi nhận của con người"},
    "heading.margin": {"en": "The margin", "vi": "Khoảng cách"},
    "heading.sensitivity": {"en": "Sensitivity", "vi": "Độ nhạy"},
    "heading.retired_early": {"en": "Retired early", "vi": "Bị loại sớm"},
    "heading.unlike_inputs": {"en": "Unlike inputs", "vi": "Đầu vào không giống nhau"},
    "heading.measurement_environment": {
        "en": "Measurement environment",
        "vi": "Môi trường đo",
    },
    "heading.reason": {"en": "Reason", "vi": "Lý do"},
    "heading.what_this_means": {"en": "What this means", "vi": "Điều này có nghĩa là"},
    "heading.scope": {"en": "Scope", "vi": "Phạm vi áp dụng"},
    "heading.reading_delta_u": {"en": "Reading ΔU", "vi": "Cách đọc ΔU"},
    "heading.two_acts": {"en": "Two acts", "vi": "Hai hành động"},
    # --- Prose that qualifies numbers ------------------------------------
    "prose.gates": {
        "en": (
            "Six feasibility gates run before anything is scored (HĐ-7). A candidate that\n"
            "failed one was never ranked, which is a result rather than an error."
        ),
        "vi": (
            "Sáu cổng sàng lọc khả thi chạy trước khi bất cứ thứ gì được chấm điểm (HĐ-7).\n"
            "Ứng viên trượt một cổng thì chưa từng được xếp hạng — đó là một kết quả, không\n"
            "phải một lỗi."
        ),
    },
    "prose.retired": {
        "en": "Retired before the sweep ended, so their rows rest on fewer episodes:",
        "vi": (
            "Bị loại trước khi đợt quét kết thúc, nên các dòng của họ dựa trên ít episode hơn:"
        ),
    },
    "prose.eligible": {
        "en": (
            "`Eligible to recommend` is stated rather than left to be read off the gate\n"
            "column: a gate failure can leave no mark on the utility at all — collisions are\n"
            "excluded from `U_S` by contract (HĐ-6), so that they cannot be traded against\n"
            "speed — and the mark alone therefore does not compare across that line."
        ),
        "vi": (
            "`Đủ điều kiện được khuyến nghị` được nói thẳng chứ không để người đọc tự suy từ\n"
            "cột phán quyết: một cổng bị trượt có thể không để lại dấu vết nào trên điểm tổng\n"
            "— va chạm bị loại khỏi `U_S` theo hợp đồng (HĐ-6), để chúng không thể đem đổi lấy\n"
            "tốc độ — nên riêng cột phán quyết không so sánh được qua ranh giới đó."
        ),
    },
    "prose.eligible_sheet": {
        "en": (
            "Stated rather than left to be read off the gate column. A gate failure can "
            "leave no mark on the utility at all — collisions are excluded from U_S by "
            "contract (HĐ-6) so that they cannot be traded against speed — so the mark "
            "does not compare across that line."
        ),
        "vi": (
            "Được nói thẳng chứ không để người đọc tự suy từ cột phán quyết. Một cổng bị "
            "trượt có thể không để lại dấu vết nào trên điểm tổng — va chạm bị loại khỏi U_S "
            "theo hợp đồng (HĐ-6) để chúng không thể đem đổi lấy tốc độ — nên cột phán quyết "
            "không so sánh được qua ranh giới đó."
        ),
    },
    "prose.no_card": {
        "en": (
            "Fewer than two candidates cleared the gates, so ΔU does not exist and no card\n"
            "was produced. The gate table above is the result."
        ),
        "vi": (
            "Chưa tới hai ứng viên vượt qua các cổng, nên ΔU không tồn tại và không thẻ nào\n"
            "được tạo. Bảng cổng phía trên chính là kết quả."
        ),
    },
    "prose.no_card_sheet": {
        "en": (
            "Fewer than two candidates cleared the gates, so ΔU does not exist and no "
            "card was produced. The gate table is the result."
        ),
        "vi": (
            "Chưa tới hai ứng viên vượt qua các cổng, nên ΔU không tồn tại và không thẻ nào "
            "được tạo. Bảng cổng chính là kết quả."
        ),
    },
    "prose.gate_only_deployment": {
        "en": "This deployment cannot rank (HĐ-8.4): {reason}",
        "vi": "Điểm triển khai này không thể xếp hạng (HĐ-8.4): {reason}",
    },
    "prose.scope": {
        "en": (
            "this recommendation applies to `{scope}` and to nothing else\n"
            "(HĐ-1.4). Carrying it to another deployment is a claim this run did not make."
        ),
        "vi": (
            "khuyến nghị này áp dụng cho `{scope}` và không cho bất cứ thứ gì khác\n"
            "(HĐ-1.4). Mang nó sang một điểm triển khai khác là một khẳng định mà lần chạy này\n"
            "chưa từng đưa ra."
        ),
    },
    "prose.scope_sheet": {
        "en": (
            "This recommendation applies to {scope} and to nothing else (HĐ-1.4). Carrying "
            "it to another deployment is a claim this run did not make."
        ),
        "vi": (
            "Khuyến nghị này áp dụng cho {scope} và không cho bất cứ thứ gì khác (HĐ-1.4). "
            "Mang nó sang một điểm triển khai khác là một khẳng định mà lần chạy này chưa "
            "từng đưa ra."
        ),
    },
    "prose.delta_u": {
        "en": (
            "ΔU is printed with its interval and never without it. A margin whose interval\n"
            "includes zero is consistent with the two candidates being equal."
        ),
        "vi": (
            "ΔU luôn được in kèm khoảng tin cậy và không bao giờ in một mình. Một khoảng cách\n"
            "mà khoảng tin cậy của nó chứa số không thì hoàn toàn phù hợp với việc hai ứng\n"
            "viên ngang nhau."
        ),
    },
    "prose.delta_u_sheet": {
        "en": (
            "Printed with its interval and never without it: a margin whose interval "
            "includes zero is consistent with the two candidates being equal."
        ),
        "vi": (
            "Luôn in kèm khoảng tin cậy và không bao giờ in một mình: một khoảng cách mà "
            "khoảng tin cậy của nó chứa số không thì hoàn toàn phù hợp với việc hai ứng viên "
            "ngang nhau."
        ),
    },
    "prose.no_sensitivity": {
        "en": (
            "None of the sensitivity margins were measured. That is not the same as their\n"
            "being wide (HĐ-12)."
        ),
        "vi": (
            "Không biên độ nhạy nào được đo. Điều đó không đồng nghĩa với việc chúng rộng\n"
            "(HĐ-12)."
        ),
    },
    "prose.no_sensitivity_sheet": {
        "en": (
            "None of the sensitivity margins were measured. That is not the same as their "
            "being wide (HĐ-12)."
        ),
        "vi": (
            "Không biên độ nhạy nào được đo. Điều đó không đồng nghĩa với việc chúng rộng "
            "(HĐ-12)."
        ),
    },
    "prose.two_acts": {
        "en": (
            "Reading the evidence and approving the configuration are separate acts (HĐ-14).\n"
            "A run that was read and never approved is an ordinary state, not an omission."
        ),
        "vi": (
            "Đọc bằng chứng và phê duyệt cấu hình là hai hành động tách biệt (HĐ-14). Một lần\n"
            "chạy đã được đọc mà chưa từng được phê duyệt là một trạng thái bình thường,\n"
            "không phải một thiếu sót."
        ),
    },
    "prose.two_acts_sheet": {
        "en": (
            "Reading the evidence and approving the configuration are separate acts (HĐ-14). "
            "A run that was read and never approved is an ordinary state, not an omission."
        ),
        "vi": (
            "Đọc bằng chứng và phê duyệt cấu hình là hai hành động tách biệt (HĐ-14). Một lần "
            "chạy đã được đọc mà chưa từng được phê duyệt là một trạng thái bình thường, "
            "không phải một thiếu sót."
        ),
    },
    # --- The unlike-inputs caveat, in the two pieces every renderer needs --
    "caveat.mixed.lead": {
        "en": "These candidates were shown different things ({classes}).",
        "vi": "Những ứng viên này được cho nhìn thấy những thứ khác nhau ({classes}).",
    },
    "caveat.mixed.body": {
        "en": (
            "Most of the gap\n"
            "between their numbers is the gap between their inputs, so any ranking below\n"
            "is measuring the privilege as much as the planner."
        ),
        "vi": (
            "Phần lớn khoảng cách\n"
            "giữa các con số của họ là khoảng cách giữa các đầu vào, nên mọi xếp hạng phía\n"
            "dưới đang đo cái đặc quyền đó nhiều ngang với đo bản thân bộ lập lộ trình."
        ),
    },
    "caveat.retired_detail": {
        "en": "{gate} after {run} of {planned} episodes ({rule})",
        "vi": "{gate} sau {run} trên {planned} episode ({rule})",
    },
}


def text(key: str, locale: Locale = DEFAULT_LOCALE, /, **fields: object) -> str:
    """One string, in one language, with its placeholders filled.

    Raises :class:`MissingTranslation` for an unknown key or a language
    the entry does not carry — never falls back to English. See the
    module docstring for why a half-translated document is the worse
    outcome.
    """
    entry = TEXT.get(key)
    if entry is None:
        raise MissingTranslation(f"no export text for {key!r}")
    value = entry.get(locale)
    if value is None:
        raise MissingTranslation(f"export text {key!r} has no {locale!r}")
    return value.format(**fields) if fields else value


def lines(key: str, locale: Locale = DEFAULT_LOCALE, /, **fields: object) -> list[str]:
    """The same string, split at the line breaks it carries.

    Several of these are paragraphs whose wrapping is part of the
    layout: Markdown quotes them line by line and a spreadsheet joins
    them with spaces. Keeping the breaks in the string means the words
    and the shape of them stay together instead of one copy per format.
    """
    return text(key, locale, **fields).split("\n")

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
    # --- Detailed comparison ----------------------------------------------
    "heading.comparison": {"en": "Detailed Comparison", "vi": "So sánh chi tiết"},
    "column.compare.metric": {"en": "Metric", "vi": "Chỉ số"},
    "column.compare.unit": {"en": "Unit", "vi": "Đơn vị"},
    "column.compare.delta": {"en": "Delta", "vi": "Chênh lệch"},
    "column.compare.delta_unit": {"en": "Delta unit", "vi": "Đơn vị chênh lệch"},
    "column.compare.winner": {"en": "Winner", "vi": "Bên dẫn"},
    "column.compare.limit": {"en": "Limit", "vi": "Ngưỡng khai báo"},
    "column.compare.weight": {"en": "Weight", "vi": "Trọng số"},
    "column.compare.note": {"en": "Note", "vi": "Ghi chú"},
    "value.tie": {"en": "tie", "vi": "ngang nhau"},
    "value.no_direction": {"en": "no direction", "vi": "không có chiều tốt"},
    # --- The ten metrics, and why each is or is not scored ----------------
    "metric.successRate": {"en": "Success rate", "vi": "Tỉ lệ thành công"},
    "metric.collisions": {"en": "Collisions observed", "vi": "Số va chạm quan sát được"},
    "metric.collisionBound": {
        "en": "Collision probability, 95% upper bound",
        "vi": "Xác suất va chạm, cận trên 95%",
    },
    "metric.noPathRate": {
        "en": "Episodes with no route found",
        "vi": "Số episode không tìm được lộ trình",
    },
    "metric.worstClearance": {
        "en": "Worst clearance in the whole run",
        "vi": "Khoảng hở tệ nhất trong cả lần chạy",
    },
    "metric.medianTravel": {"en": "Median episode duration", "vi": "Thời lượng episode trung vị"},
    "metric.p99": {"en": "Planner latency, pooled p99", "vi": "Độ trễ bộ lập lộ trình, p99 gộp"},
    "metric.memory": {
        "en": "Memory estimate on the target board",
        "vi": "Ước lượng bộ nhớ trên bo mạch đích",
    },
    "metric.distinctEpisodes": {"en": "Distinct episodes", "vi": "Số episode khác biệt"},
    "metric.replans": {"en": "Replans across the run", "vi": "Số lần lập lại lộ trình cả lần chạy"},
    "note.successRate": {
        "en": (
            "The share of episodes that reached the goal, however the rest failed. G3 judges "
            "it against the deployment's declared floor, and U_R scores the margin over that "
            "floor — which is why this row carries the reliability weight."
        ),
        "vi": (
            "Tỉ lệ episode tới được đích, bất kể phần còn lại hỏng theo cách nào. G3 xét nó "
            "với sàn mà điểm triển khai đã khai, và U_R chấm phần vượt sàn đó — vì vậy dòng "
            "này mang trọng số độ tin cậy."
        ),
    },
    "note.collisions": {
        "en": (
            "Taken from G2's own count. One collision ends the gate, so this is a "
            "zero-or-eliminated column rather than a scale. No weight, and that is a "
            "contract rather than an omission: HĐ-6 excludes collisions from U_S so they "
            "cannot be traded against speed."
        ),
        "vi": (
            "Lấy từ chính số đếm của G2. Một va chạm là kết thúc cổng, nên đây là cột "
            "không-hoặc-bị-loại chứ không phải một thang đo. Không có trọng số, và đó là "
            "hợp đồng chứ không phải thiếu sót: HĐ-6 loại va chạm khỏi U_S để chúng không "
            "thể đem đổi lấy tốc độ."
        ),
    },
    "note.collisionBound": {
        "en": (
            "What the clean record actually supports. Zero collisions in 10 distinct runs is "
            "consistent with a 26% collision rate; the bound is 3/N, so a lower number here "
            "means a larger evidence base, not a safer robot. A property of the sample, so "
            "no weight."
        ),
        "vi": (
            "Điều mà một hồ sơ sạch thực sự chống đỡ được. Không va chạm nào trong 10 lần "
            "chạy khác biệt vẫn phù hợp với tỉ lệ va chạm 26%; cận trên là 3/N, nên số nhỏ "
            "hơn ở đây nghĩa là nền bằng chứng lớn hơn, không phải robot an toàn hơn. Đây là "
            "thuộc tính của cỡ mẫu, nên không có trọng số."
        ),
    },
    "note.noPathRate": {
        "en": (
            "How often the global planner returned nothing at all. G1 keeps this apart from a "
            "general failure rate because not finding a route and having a route not survive "
            "traffic are fixed on different layers. Decided at the gate, so no weight."
        ),
        "vi": (
            "Bộ lập lộ trình toàn cục trả về rỗng bao nhiêu lần. G1 tách nó khỏi tỉ lệ hỏng "
            "chung vì không tìm ra lộ trình và có lộ trình nhưng không sống nổi qua giao "
            "thông được sửa ở hai tầng khác nhau. Do cổng quyết, nên không có trọng số."
        ),
    },
    "note.worstClearance": {
        "en": (
            "The closest the robot ever came to anything, across every episode. A run whose "
            "typical clearance is comfortable can still hold one near miss, and an average "
            "would hide it. No weight: U_S scores the *mean* clearance, which is a different "
            "quantity from the worst one."
        ),
        "vi": (
            "Khoảng cách gần nhất robot từng tới bất cứ vật gì, trên toàn bộ episode. Một lần "
            "chạy có khoảng hở điển hình thoải mái vẫn có thể chứa một lần suýt va, và số "
            "trung bình sẽ giấu nó đi. Không có trọng số: U_S chấm khoảng hở **trung bình**, "
            "một đại lượng khác với khoảng hở tệ nhất."
        ),
    },
    "note.medianTravel": {
        "en": (
            "How long a typical episode took. The median rather than the mean: one timeout "
            "parked at the deployment's cap drags a mean by tens of seconds, and the number "
            "then describes the cap rather than the stack. What U_E scores is time "
            "efficiency, a different quantity, so this row carries no weight."
        ),
        "vi": (
            "Một episode điển hình mất bao lâu. Trung vị chứ không phải trung bình: một lần "
            "hết giờ nằm ở trần của điểm triển khai kéo số trung bình đi hàng chục giây, và "
            "con số khi đó mô tả cái trần chứ không mô tả stack. Thứ U_E chấm là hiệu suất "
            "thời gian, một đại lượng khác, nên dòng này không mang trọng số."
        ),
    },
    "note.p99": {
        "en": (
            "The 99th percentile over every control step of the evaluation set, pooled. G4 "
            "judges it against one control period and measures on the benchmark host — there "
            "is no conversion factor to the target board. Weighted inside U_C."
        ),
        "vi": (
            "Bách phân vị thứ 99 trên mọi bước điều khiển của tập đánh giá, gộp lại. G4 xét "
            "nó với một chu kỳ điều khiển và đo trên máy chủ benchmark — không có hệ số quy "
            "đổi sang bo mạch đích. Có trọng số bên trong U_C."
        ),
    },
    "note.memory": {
        "en": (
            "G5's estimate from data-structure counts at the target implementation's byte "
            "sizes, never the Python process's RSS. Under budget is an elimination test that "
            "came out negative, not a certificate of fit. Weighted inside U_C."
        ),
        "vi": (
            "Ước lượng của G5 từ số lượng cấu trúc dữ liệu theo kích thước byte của bản cài "
            "đặt đích, không bao giờ là RSS của tiến trình Python. Dưới ngân sách là một phép "
            "thử loại trừ cho kết quả âm tính, không phải giấy chứng nhận vừa vặn. Có trọng "
            "số bên trong U_C."
        ),
    },
    "note.distinctEpisodes": {
        "en": (
            "How many of the episodes were actually different from each other. A "
            "deterministic stack on traffic that never crosses its route produces the same "
            "episode once per seed, and a hundred copies bound a risk exactly as well as one "
            "does. The evidence base, not an achievement, so no weight."
        ),
        "vi": (
            "Bao nhiêu episode thực sự khác nhau. Một stack tất định trên dòng giao thông "
            "không bao giờ cắt qua lộ trình của nó sinh ra cùng một episode mỗi seed, và một "
            "trăm bản sao chặn rủi ro đúng bằng một bản. Đây là nền bằng chứng, không phải "
            "thành tích, nên không có trọng số."
        ),
    },
    "note.replans": {
        "en": (
            "Evidence, not a score — which is why no candidate is marked ahead on this row. "
            "Replanning already costs travel time and latency, and both are charged; there is "
            "no separate replan budget to come in under."
        ),
        "vi": (
            "Bằng chứng, không phải điểm số — vì vậy không ứng viên nào được đánh dấu dẫn "
            "trước ở dòng này. Việc lập lại lộ trình đã tốn thời gian di chuyển và độ trễ, cả "
            "hai đều đã bị tính; không có ngân sách lập lại lộ trình riêng để mà đạt dưới."
        ),
    },
    # --- Objective breakdown ----------------------------------------------
    "heading.objectives": {"en": "Objective Breakdown", "vi": "Phân rã theo mục tiêu"},
    "column.objective.name": {"en": "Objective", "vi": "Mục tiêu"},
    "column.objective.contribution": {"en": "Contribution", "vi": "Đóng góp"},
    "objective.cpu_time": {"en": "CPU time per mission", "vi": "Thời gian CPU mỗi nhiệm vụ"},
    "objective.engineering_cost": {"en": "Engineering cost", "vi": "Chi phí kỹ thuật"},
    "note.component_measured": {
        "en": "Its input is on the comparison sheet.",
        "vi": "Đầu vào của nó nằm trên sheet so sánh.",
    },
    "note.component_unmeasured": {
        "en": (
            "Weighted, but its input is not recorded in the report at any level — so this "
            "share of U_C cannot be traced back to a measurement from this file."
        ),
        "vi": (
            "Có trọng số, nhưng đầu vào của nó không được ghi trong report ở bất kỳ cấp nào "
            "— nên phần này của U_C không thể truy ngược về một số đo nào từ file này."
        ),
    },
    "note.total_is_the_sum": {
        "en": (
            "The sum of the Contribution column above. Add it up: it is the card's own "
            "utility, and a total that does not match means one of the weights, one of the "
            "objectives, or the mapping between them is wrong."
        ),
        "vi": (
            "Tổng của cột Đóng góp phía trên. Hãy cộng lại: đó chính là điểm tổng của thẻ, "
            "và một tổng không khớp nghĩa là một trong các trọng số, một trong các mục tiêu, "
            "hoặc ánh xạ giữa chúng đang sai."
        ),
    },
    "caveat.weights_perturbed": {
        "en": (
            "This run was scored under weights perturbed from {profile} for the HĐ-11.5 "
            "stability sweep. The replacements are not recorded, so no weight is printed — the "
            "named profile's numbers would attribute the card to weights it was not scored "
            "under."
        ),
        "vi": (
            "Lần chạy này được chấm dưới bộ trọng số đã nhiễu đi từ {profile} cho phép quét "
            "ổn định HĐ-11.5. Bộ thay thế không được ghi lại, nên không trọng số nào được in "
            "ra — in số của hồ sơ được nêu tên sẽ gán cho thẻ một bộ trọng số mà nó không "
            "được chấm dưới đó."
        ),
    },
    "caveat.weights_unknown_profile": {
        "en": (
            "The run names preference profile {profile}, which the weight table no longer "
            "carries. The weights are therefore not printed rather than guessed."
        ),
        "vi": (
            "Lần chạy nêu tên hồ sơ ưu tiên {profile}, thứ mà bảng trọng số không còn giữ. "
            "Vì vậy các trọng số không được in ra thay vì đoán."
        ),
    },
    "caveat.weights_table_unavailable": {
        "en": (
            "The weight table could not be loaded in this deployment, so the weights for "
            "profile {profile} are unavailable here. This is a property of the build, not of "
            "the run — the card was scored under real weights and this file cannot reach them."
        ),
        "vi": (
            "Bảng trọng số không nạp được trong bản triển khai này, nên trọng số của hồ sơ "
            "{profile} không lấy được ở đây. Đây là thuộc tính của bản dựng chứ không phải "
            "của lần chạy — thẻ đã được chấm dưới trọng số thật và file này không với tới được."
        ),
    },
    "heading.weights": {"en": "Weights", "vi": "Trọng số"},
    # --- Summary ----------------------------------------------------------
    "label.candidate_n": {"en": "Candidate {index}", "vi": "Ứng viên {index}"},
    "label.winner": {"en": "Winner", "vi": "Bên thắng"},
    "label.overall_score": {"en": "Overall score", "vi": "Điểm tổng"},
    "label.confidence_low": {"en": "ΔU 95% lower bound", "vi": "Cận dưới 95% của ΔU"},
    "label.confidence_high": {"en": "ΔU 95% upper bound", "vi": "Cận trên 95% của ΔU"},
    "label.final_recommendation": {"en": "Final recommendation", "vi": "Khuyến nghị cuối cùng"},
    "label.preference_profile": {"en": "Preference profile", "vi": "Hồ sơ ưu tiên"},
    "heading.summary": {"en": "Summary", "vi": "Tóm tắt"},
    "value.candidate_stack": {"en": "{stack} ({config})", "vi": "{stack} ({config})"},
    "prose.final_recommendation": {
        "en": "{stack} ({config}), for {scope} and for nothing else (HĐ-1.4).",
        "vi": (
            "{stack} ({config}), áp dụng cho {scope} và không cho bất cứ thứ gì khác (HĐ-1.4)."
        ),
    },
    "prose.final_recommendation_none": {
        "en": (
            "None. Fewer than two candidates cleared the gates, so this run ranked nobody "
            "and the gate sheet is the result."
        ),
        "vi": (
            "Không có. Chưa tới hai ứng viên vượt qua các cổng, nên lần chạy này không xếp "
            "hạng ai và bảng cổng chính là kết quả."
        ),
    },
    "prose.summary_precision": {
        "en": (
            "Numbers on this sheet and the two after it are stored as values, not as text, "
            "so they sort, sum and chart. They are shown to a fixed number of decimals — the "
            "same the comparison grid on screen uses — which can differ from the Markdown "
            "export's three significant digits. Click a cell for the full value."
        ),
        "vi": (
            "Các con số trên sheet này và hai sheet kế tiếp được lưu dưới dạng giá trị chứ "
            "không phải văn bản, nên có thể sắp xếp, cộng và vẽ biểu đồ. Chúng hiển thị với "
            "số chữ số thập phân cố định — đúng bằng lưới so sánh trên màn hình — và có thể "
            "khác với ba chữ số có nghĩa của bản Markdown. Bấm vào ô để thấy giá trị đầy đủ."
        ),
    },
    "heading.precision": {"en": "Precision", "vi": "Độ chính xác hiển thị"},
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

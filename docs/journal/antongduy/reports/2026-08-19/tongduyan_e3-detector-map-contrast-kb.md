# E3 — detector, map feature, contrast graph, và KB v1

**Ngày:** 2026-08-19
**Plan:** `plans/2026-08-18/tang-giai-thich-vi-sao.md` §5, đợt **E3**
**Thiết kế nguồn:** `notes/2026-08-18/tongduyan_giai-phap-giai-thich-vi-sao-thuat-toan-thang.md` §5
**Tiền đề:** E0 (`d28ff20`), E1 (`cf7967c`), E2 (`1d93d05`)
**Trạng thái:** xong, **đã qua hai vòng rà của An** (mục 9: năm điểm; mục 11: ba
điểm — tất cả đã sửa). 64 test mới xanh. **Chưa commit.** Full suite chưa chạy.

---

## 1. Giao cái gì

| Module | Nội dung |
|---|---|
| `detectors.py` | bảy detector thuần hàm trên trace + `Observation` có prevalence |
| `map_features.py` | bề rộng khe hẹp nhất và mật độ vật cản **quanh tuyến** |
| `contrast.py` | đọc chéo lattice, bốn verdict, ba trong đó là từ chối |
| `knowledge.py` | KB v1 curated + matcher deterministic + resolver theo version |

Cộng một field mới trong report: `components` typed cho từng candidate
(`selection.py`).

## 2. Detector nói *cái gì xảy ra*, không nói *vì sao*

`stuck_cluster` nói robot dừng bốn lần trong cùng một đoạn hành lang. Nó **không**
nói local minimum gây ra chuyện đó. Ranh giới này là toàn bộ kiến trúc: detector
nuôi case packet, analyst đề xuất cơ chế, checker kiểm, promotion matrix quyết
định được nói gì. Một detector đoán nguyên nhân là đặt một claim không kiểm được
lên **thượng nguồn** của cả bốn cổng đó.

Bảy detector: `detour` · `stuck_cluster` · `near_miss_cluster` · `replan_storm` ·
`oscillation` · `latency_spike` · `narrow_gap_refusal`.

**Ngưỡng nằm trong `DetectorSettings`**, một chỗ đọc được và chỉnh được — detector
mà độ nhạy là một literal chôn ba tầng hàm là detector không ai hiệu chỉnh nổi.
Có test khẳng định một run đi thẳng, đều tốc độ **không kích hoạt gì cả**: detector
kêu trên lái xe bình thường sẽ nhồi packet đầy nhiễu, và analyst đọc ba mươi
detection mỗi episode thì không học được gì từ cái nào.

**Ba quyết định đáng ghi:**

- **`latency_spike` dùng ngưỡng tuyệt đối, không phải phân vị.** Phân vị **luôn**
  tìm ra một "spike", kể cả trong run mà tick tệ nhất là 8 ms.
- **`narrow_gap_refusal` báo hai sự thật cạnh nhau, không phải một cơ chế**: có
  refusal, và khe hẹp hơn clearance robot cần. Đó đúng hình dạng thứ mà
  `gap_vs_footprint` (E5/E6) tồn tại để biến thành cơ chế đã kiểm chứng. Thiếu
  map feature hoặc thiếu clearance thì detector **không chạy** — một nửa của cặp
  này không phải là phiên bản yếu hơn của nó.
- **Vị trí báo bằng cửa sổ arc-length, không bịa tên vùng.** Note thiết kế viết
  `region: aisle_B7`; platform không có vocabulary vùng, và tự đặt tên là gắn một
  nhãn tự tin lên một hộp tùy ý. Detection mang **cửa sổ arc-length** trên tuyến
  tham chiếu (E2), kèm `projection_quality` đi theo — đo được. Đặt tên vùng là
  việc riêng sau này, và nó cắm được vào đúng các cửa sổ này.

**Prevalence là phép gộp, không phải một detection.** `summarise()` nhận
`episodes_total` **từ ngoài** chứ không đếm từ chính các detection: mẫu số là *số
episode đã soi*, đếm từ detection sẽ làm mọi pattern thành phổ quát. Số "điển
hình" là **median** — một episode chạy loạn không được đặt con số mà người đọc
coi là bình thường.

## 3. Map feature — chỉ đo thứ đo được

`narrowest_passage_m` là **mặt cắt ngang tuyến**: bắn tia sang hai bên theo pháp
tuyến và cộng lại. Bản đầu lấy gấp đôi khoảng cách tới vật cản gần nhất — xem
mục 9, đó là đường kính đường tròn nội tiếp, chỉ bằng bề rộng hành lang khi
tuyến chạy đúng giữa.

Lấy mẫu dọc tuyến theo `sample_spacing_m` (mặc định 10 cm) — độ phân giải của
*câu trả lời*, không phải của bản đồ: hai waypoint cách nhau 0,7 m sẽ bước qua
đúng cái cửa cần tìm.

`obstacle_density` đo **quanh tuyến**, không phải toàn bản đồ: một tuyến đi dọc
lối trống trong kho chật không phải tuyến chật, và con số nói ngược lại là đang
mô tả toà nhà chứ không mô tả lượt chạy.

**`topology` và số ngã rẽ tách sang E3.5** (plan đã cập nhật, không chỉ ghi ở
đây). Chúng cần một phép phân tích Voronoi/skeleton riêng, và một nhãn thay thế
thô sẽ tệ hơn không có: `corridor_with_side_aisles` là loại nhãn người đọc coi là
sự thật đã xác lập, mà nó lại đến từ phỏng đoán, đặt cạnh những con số đo thật.

## 4. Contrast graph — chủ yếu là một cỗ máy từ chối

Bốn verdict, ba là từ chối. Điểm dễ đọc sai nhất được viết thẳng vào `reason`:
`rules_out_component_specific_attribution` **không** chứng minh thành phần dùng
chung là thủ phạm — task geometry, costmap, provider dùng chung và tương tác
global–local đều sinh ra pattern chung.

`interaction_not_isolated` bắt ca hai cặp swap mâu thuẫn nhau, và **không** giải
quyết bằng đa số: hai cặp bất đồng chính là bằng chứng rằng hai tầng chưa tách
được ở đây.

Chỉ so những candidate khác nhau **đúng một** thành phần. Hai stack khác cả
planner lẫn controller không nói gì về bên nào, và coi chúng là một swap là biến
phép đọc lattice thành tung đồng xu có trích dẫn.

**Candidate chưa được soi thì không tham gia**: vắng mặt của một phép soi không
phải vắng mặt của pattern.

## 5. Một field mới trong report: `components`

Contrast graph cần biết candidate nào khác nhau ở đâu. Report chỉ có
`stack_label` (`"astar+dwa"`) và tách nó bằng dấu `+` chạy đúng cho tới khi một
tên stack có dấu cộng — lúc đó phép so **đổi nghĩa trong im lặng**. Nên
`selection.py` ghi khối typed:

```json
"components": {"global_planner": "astar", "local_controller": "dwa",
               "local_controller_config": "dwa_coarse"}
```

Lấy thẳng từ object `Candidate`. Candidate **monolithic** ⇒ `null`, không phải
tên giữ chỗ: một policy không phải "một thành phần" của cái gì, và nói vậy giữ nó
ra khỏi các phép so swap thay vì cho nó tên trông swap được.

`components_from_report()` bỏ qua candidate không có khối này — run cũ **không có
lattice**, chứ không phải có một lattice đoán ra.

## 6. KB v1 — và vì sao nó ship ở `draft`

Năm entry curated: inflation đóng khe · local minimum trong hốc lõm · RRT\* hết
sample · expansion kéo latency · replan thrash quanh vật cản động. Mỗi entry có
id, version, điều kiện kích hoạt **hẹp**, `source_refs`, `source_strength`, và
`does_not_explain` — cách đọc chệch là cách người đọc tự nghĩ ra, nên viết sẵn ra.

**Mọi entry là `review_status: draft`.** Chúng do một người viết và **chưa ai
duyệt**; E0 quy định entry chưa approved không được back một claim đã promote.
Ship chúng ở `approved` vì tác giả thấy chúng đúng chính là nước đi mà trường
review status sinh ra để chặn. Hôm nay chúng hữu ích như tài liệu đọc kèm một
detection; chúng thành promotable khi có người thật sự đọc và ký.

`match()` **deterministic và cố tình nhạt**: so literal theo detection type,
subject và cận số, thứ tự theo entry id. Không embedding, không similarity, không
model — retrieval *gần đúng* chính là thứ biến một entry hẹp thành lời giải thích
sai nghe rất hợp lý. Không match gì ⇒ **trả rỗng**, và đó là câu trả lời: triệu
chứng trần, không bịa cơ chế.

`resolve("kb:<id>@<version>")` từ chối id lạ **và** lệch version — đúng hợp đồng
knowledge của E0: RAG chỉ được đề xuất khóa, còn platform tin bản canonical.

## 7. Kiểm chứng

- `tests/test_explanation_detectors.py` — 28 test.
- `tests/test_explanation_map_features.py` — 13 test.
- `tests/test_explanation_knowledge_contrast.py` — 18 test.
- **218 passed** trên toàn bộ test explanation; `test_explanation_report_wiring.py`
  thêm một test chạy **run thật** khẳng định `components` có mặt và hai candidate
  của run khác nhau đúng một thành phần (5 passed).
- `test_decision_card.py` + `test_early_stop_run.py` — **61 passed** (chạy vì
  `selection.py` bị sửa).
- `ruff check` sạch.
- **Full suite chưa chạy.**

**Một fixture của tôi từng sai và test bắt được:** bản đầu của bản đồ fixture có
tường gần nhau tới mức cả hành lang hẹp **đúng bằng** cái cửa, nên test "tìm ra
cửa" xanh mà không chứng minh gì. Sửa fixture để cửa là điểm hẹp **duy nhất**.

## 8. Chưa làm — nói rõ

- **`topology` / số ngã rẽ**: tách thành **E3.5** trong plan (đã cập nhật plan,
  không chỉ ghi trong report) — xem mục 9, MEDIUM-5.
- **Tên vùng** (`aisle_B7`): cửa sổ arc-length là thứ thay thế đo được; đặt tên
  vùng là việc riêng.
- **KB chưa ai duyệt** ⇒ chưa entry nào promote được claim. Đây là trạng thái
  đúng, không phải nợ kỹ thuật — nhưng cần một người đọc và ký để E4 dùng được.
- **Chưa nối API/UI.** E3 giao tầng deterministic; case packet ghép detector +
  map feature + contrast + KB là **E4**.
- **Prevalence theo detector cho exemplar** (bộ thứ năm của công thức E2) giờ đã
  có nguyên liệu, nhưng nối vào exemplar vẫn thuộc E4.

## 9. Vòng rà của An — năm điểm

**HIGH-1 — contrast quy nguyên nhân theo thứ tự chữ cái.** Khi nhiều component
cùng "move", code lấy `sorted(by_field)[0]` rồi kết luận
`supports_component_specific_attribution`. Tức nó quy cho global planner vì "g"
đứng trước "l" — một cú tung đồng xu đội tên component. Nay `len(by_field) > 1` ⇒
`interaction_not_isolated`, **giữ toàn bộ pairs** để người đọc thấy cái gì bất
đồng với cái gì. Có test ca tối thiểu ba candidate của An, và test ngược khẳng
định một trục duy nhất vẫn cho attribution.

**HIGH-2 — `Observation` chọn episode an toàn nhất làm "worst".** Đúng, và đây là
loại lỗi tệ nhất trong nhóm: với `near_miss_cluster`, key đầu theo alphabet là
`min_clearance_m`, mà `max()` trên clearance chọn episode **an toàn nhất**
(0,14 m thắng 0,01 m) rồi gắn nhãn "worst". Nay có bảng `SEVERITY` khai **hướng**
cho từng detection type (`near_miss`/`narrow_gap` là "nhỏ hơn thì tệ hơn", còn
lại "lớn hơn thì tệ hơn") và `severity_of()` chuẩn hoá về thang **lớn = tệ**.

Điểm thứ hai của An trong cùng mục cũng đúng: median tính trên **detection** chứ
không trên **episode**, nên một episode sinh bốn cluster có trọng số gấp bốn — trái
đúng câu docstring của chính nó. Nay gộp về **một detection tệ nhất mỗi episode**
trước, rồi mới median và chọn worst. Test dựng đúng ca 1 episode bận + 3 episode
yên.

**HIGH-3 — `narrowest_passage_m` chưa phải bề rộng lối đi.** Đúng. Gấp đôi khoảng
cách tới vật cản gần nhất là đường kính đường tròn nội tiếp, chỉ bằng bề rộng khi
tuyến nằm giữa; tuyến bám sát một tường trong sảnh rộng bị báo là "khe hẹp" — và
con số đó đang được đưa thẳng vào `narrow_gap_refusal`. Chọn hướng sửa **đo thật**
thay vì đổi tên: bắn tia hai phía theo pháp tuyến của tuyến và cộng lại.

Hai vấn đề coverage An nêu cũng sửa cùng chỗ: **UNKNOWN và mép grid chặn tia**,
không còn coi là trống. Route nằm hoàn toàn ngoài map ⇒ **từ chối**.

> **Đính chính:** bản đầu của đoạn này viết cận dưới là "hướng an toàn cho một
> con số mà phép kiểm khe sẽ đọc". **Sai** — xem mục 11, HIGH-2.

**MEDIUM-4 — `int()` kéo điểm ngoài map vào trong, và spacing không giữ đúng.**
Cả hai đúng: `int()` làm tròn về 0 nên `x = −0.1` rơi vào cột 0, và
`int(segment / spacing)` làm khoảng lấy mẫu **thưa hơn** mức đã khai — đúng cái
khiến một ô cửa nằm lọt giữa hai mẫu. Nay `math.floor` cho world→map và
`math.ceil` cho số bước, có test khẳng định khoảng mẫu thực tế không vượt mức
khai. Về `origin.theta`: `MapData` **từ chối** origin xoay ngay lúc parse, nên
phép biến đổi chỉ là tịnh tiến + tỉ lệ — đã ghi vào docstring thay vì thêm nhánh
xử lý một trạng thái schema không cho phép tồn tại.

**MEDIUM-5 — phạm vi E3 lệch tài liệu thiết kế.** Đúng, và đây là lỗi quy trình
chứ không phải lỗi code: tôi tự loại hai hạng mục rồi vẫn viết "E3 xong". Nay
**plan đã sửa**: dòng E3 ghi rõ topology/số ngã rẽ hoãn, và có dòng **E3.5** mới
(Voronoi/skeleton, sau E4) — cùng chỗ mà detector "chọn nhánh khác tại ngã rẽ"
đang chờ. Mục "Đã chốt thêm (19-08)" trong plan ghi lại cả bốn quyết định của
hai ngày qua.

## 10. Kiểm chứng sau vòng rà

- **218 passed** trên toàn bộ test explanation (thêm 10 test hồi quy: hai trục
  cùng move, hướng severity, một episode bận, tuyến bám tường, unknown chặn tia,
  route ngoài map, spacing).
- `ruff check` sạch.
- **Full suite chưa chạy.**

## 11. Vòng rà thứ hai — ba điểm

**HIGH-1 — severity bằng 0,0 bị coi như không có.** `severity_of(item) or -math.inf`
— và `0.0` là falsy. Với near miss, clearance **0,00 m** là tiếp xúc, tức ca nguy
hiểm nhất, mà nó bị biến thành `-inf` và thua một episode 0,10 m. Nay có
`severity_key()` kiểm `None` tường minh; phép so phải phân biệt **"không có số"**
với **"con số tệ nhất có thể"**. Hai test hồi quy: clearance đúng 0,0, và một
detection thiếu hẳn measurement.

**HIGH-2 — cận dưới vẫn kích hoạt được `narrow_gap_refusal`.** Đây là **lỗi suy
luận của tôi**, không chỉ lỗi code, và report vòng trước còn viết ngược hẳn: tôi
gọi cận dưới là "hướng an toàn". Không phải. `width ≥ 0.3` cộng `0.3 < 0.74`
**không** suy ra `width < 0.74` — vùng UNKNOWN có thể mở ra thành hành lang 5 m.
Cận dưới chứng minh được "đủ rộng" và **không bao giờ** chứng minh được "quá hẹp",
tức đúng cái kết luận detector này đưa ra.

Chọn cách thứ nhất trong hai cách An nêu: `narrowest_passage_m` **chỉ đếm mặt cắt
bị chặn hai phía bởi vật cản thật**, và là `None` khi không có mẫu nào như vậy.
Cận dưới đi riêng ở `narrowest_lower_bound_m` — để đọc, không để quyết định — cộng
`passage_width_is_measurable`. Validator từ chối cận dưới **lớn hơn** giá trị nó
chặn: một cận nằm dưới giá trị mới là cận.

Sửa xong thì lộ một regression tôi vừa tạo trong cùng lượt: `obstacle_density` bị
tính chỉ trên mẫu có mặt cắt chặn hai phía. Mật độ là chuyện tuyến đi qua đâu, còn
mặt cắt có bị tường chặn hay không là chuyện của **bề rộng** — đã tách lại.

**LOW-3 — comment lỗi thời.** `worst_episode_context_id` vẫn tả là "largest first
measurement" trong khi implementation đã dùng severity typed. Đã sửa.

## 12. Kiểm chứng sau vòng rà thứ hai

- **223 passed** trên toàn bộ test explanation (thêm 5 test: contact 0,0 m,
  detection thiếu measurement, cận dưới không vào phép kiểm khe, và hai invariant
  của `RouteFeatures`).
- `ruff check` sạch.
- **Full suite chưa chạy.**

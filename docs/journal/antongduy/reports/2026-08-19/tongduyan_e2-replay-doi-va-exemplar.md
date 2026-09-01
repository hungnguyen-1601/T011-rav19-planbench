# E2 — replay đôi có chế độ thứ hai, và bộ exemplar không ai chọn tay

**Ngày:** 2026-08-19
**Plan:** `plans/2026-08-18/tang-giai-thich-vi-sao.md` §5, đợt **E2**
**Thiết kế nguồn:** `notes/2026-08-18/tongduyan_giai-phap-giai-thich-vi-sao-thuat-toan-thang.md` §4
**Audit tiền đề:** `notes/2026-08-19/tongduyan_audit-ui-hai-canvas-cho-e2.md`
**Tiền đề:** E0 (`d28ff20`), E1 (`cf7967c`)
**Trạng thái:** **E2 xong**, đã qua một vòng rà của An (mục 11, bốn điểm, cả bốn
đã sửa). 61 test Python mới + 18 test web mới, xanh. **Chưa commit.** Full suite
chưa chạy.

---

## 1. Giao cái gì

Hai module mới trong `packages/explanation/planbench_explanation/`:

| Module | Nội dung |
|---|---|
| `replay_sync.py` | chọn tuyến tham chiếu + `ProjectionQuality`, chiếu quỹ đạo, `ProgressSyncPlan` (kèm cảnh báo không gỡ được), phát hiện điểm phân kỳ |
| `exemplars.py` | công thức preregistered bốn vai + tie-break báo ra được |
| `replay_view.py` | ghép hai trace payload thành một `ReplaySyncView` — chỗ duy nhất API gọi |

Khoản treo "tên branch replay" đã đóng ở note audit: đối tượng audit là UI hai
canvas vừa merge (`d3ba3b6`), và **time-sync đã có sẵn** ở đó — một playhead
chung cho hai `TraceViewer`. E2 vì vậy không dựng lại time-sync, chỉ thêm chế độ
thứ hai và những thứ quanh nó.

## 2. Tuyến tham chiếu: chọn thì được, giấu thì không

Progress-sync giả định có "tuyến đường", mà trace chỉ chứa **thứ robot đã đi**.
Global plan nằm ở episode JSON và **vắng mặt với mọi run ghi trước khi trường đó
được giữ**. Nên tuyến tham chiếu được *chọn*, và lựa chọn được *khai*:

| `quality` | Là gì | Hệ quả phải nói ra |
|---|---|---|
| `reference_plan` | đường của chính planner | đúng nghĩa "chiếu lên tuyến" |
| `degraded_candidate_path` | quỹ đạo một candidate, làm thước cho cả hai | **thiên vị theo cấu tạo**: bên cho mượn tuyến có cross-track bằng 0 ở mọi nơi |
| `degraded_straight_line` | start → goal | không nói gì về cấu trúc hành lang |

`quality` **không có giá trị mặc định**. "Không khai" mà đọc ra thành
`reference_plan` là đúng loại im lặng tầng này tồn tại để chặn.
`choose_reference()` đi xuống theo thứ tự ưu tiên và **ghi lại từng bậc** thay vì
ném lỗi — người gọi vẫn có tuyến dùng được, kèm nhãn thật.

## 3. Cảnh báo là một field, không phải một ghi chú

`ProgressSyncPlan` mang `warning` với **đúng một giá trị hợp lệ**
(`PROGRESS_SYNC_WARNING`), validator từ chối mọi cách viết lại. Lý do: một cảnh
báo mà người gọi sửa lời được là một cảnh báo người gọi pha loãng được. Panel
muốn lấy `rows` thì buộc phải cầm luôn câu qualifier đi kèm.

Nội dung: *hai robot tới cùng chỗ đó ở hai thời điểm khác nhau, nên vật cản động
quanh chúng không giống nhau; progress-sync chỉ hợp lệ cho nguyên nhân hình học
tĩnh.* Đúng câu §4.2 của note.

## 4. Chiếu quỹ đạo — ba quyết định đáng ghi

**Cross-track có dấu.** Dương về bên trái hướng đi. Hai run tránh vật cản về
**hai phía đối nhau** mới là ca đáng xem, mà `|e|` xoá đúng ca đó.

**Lùi được ghi nhận, không bị giấu.** Robot lùi ra khỏi ngõ cụt là chuyện có
thật; `monotone_progress` (running max) là thứ nội suy chạy trên, còn
`backward_samples` đếm số mẫu đi lùi — một run nhiều mẫu lùi đang bị nhìn qua
một lăng kính không biểu diễn được nó.

**Nội suy cả cross-track, không chỉ thời gian.** Bản đầu lấy "giá trị của mẫu kế
tiếp"; với mẫu cách nhau 1 m, nó báo lệch 2 m **sớm hơn cả mét** so với lúc run
thật sự rời tuyến, và phép tìm phân kỳ đặt tên cho một chỗ hai run còn đi cạnh
nhau. Test bắt đúng chỗ này: kỳ vọng ban đầu tôi viết là 4,0 m — sai; đáp số đúng
là **3,25 m**, vì đoạn rời tuyến bắt đầu giữa hai mẫu.

**Run đi ngắn hơn không được bịa timestamp.** `time_at_progress` trả `None` cho
phần bản đồ nó chưa tới; vẽ một robot ở chỗ nó chưa từng tới là chuyện panel
tuyệt đối không được làm.

## 5. Điểm phân kỳ: duy trì, và đo bằng mét

Ngưỡng đơn lẻ vô dụng — hai run lượn trong cùng hành lang vượt nửa mét liên tục.
Điều kiện là **vượt ngưỡng và duy trì**, và cửa sổ duy trì đo bằng **arc length
chứ không bằng số mẫu**: cửa sổ đếm mẫu sẽ kết luận run chậm là "phân kỳ" chỉ vì
nó đi chậm. Có test riêng cho việc này: cùng quỹ đạo, chậm gấp bốn, ra **cùng
một vị trí phân kỳ**.

Cộng **mốc rẻ từ event** — `replan`, `stuck`, `collision`, `no_path` — lấy lần
đầu tiên của mỗi loại, đặt lên thang progress. `detour` **cố ý không có**: nó
cần detector của E3, và viết một bản yếu hơn bây giờ là đặt định nghĩa thứ hai
của "detour" vào codebase để sau này phải hoà giải.

`DivergenceReport.earliest` trả mốc sớm nhất — thứ người đọc nên được đưa tới.

## 6. Exemplar preregistered

Bốn vai, luôn đủ bốn, luôn đúng thứ tự (`ExemplarSet` từ chối nếu thiếu vai):
`typical` (ΔU gần median nhất) · `strongest_for_winner` / `strongest_for_runnerup`
(hai cực, **đi thành một cặp** — trưng cực này mà giấu cực kia đúng là
cherry-pick công thức này sinh ra để chặn) · `safety_critical`.

`safety_critical` **đọc chéo cả hai candidate**, va chạm xếp trên mọi mức
clearance (một near miss 2 cm vẫn không phải một cú đâm). Test dựng đúng ca mà
xếp hạng theo ΔU **không bao giờ** tìm ra: cả hai stack cùng va chạm ở episode 3,
nên ΔU ở đó tầm thường, mà đó lại là episode duy nhất có robot đâm vào cái gì.

**Tie-break luôn theo episode id, và được báo ra.** Không phải "cái gặp trước" —
công thức phụ thuộc thứ tự trả về từ database thì không phải preregistered, chỉ
trông giống tái lập được. `tie_break_over` liệt kê các episode đồng hạng, để
người đọc phân biệt "tệ nhất rõ ràng" với "tệ nhất do công thức tung đồng xu hộ".

Prevalence theo detector vẫn chờ E3, đúng như note đã khai.

## 7. Nối vào API và UI

**Endpoint:** `GET /decisions/{run_id}/replay-sync/{episode_context_id}?candidate_a=&candidate_b=`.
Mỏng có chủ ý: hai trace lấy qua `service.trace()` — vốn đã từ chối episode hoặc
candidate không thuộc run này và đã áp policy trace production — phần còn lại là
`build_replay_sync_view()`.

**Phép chiếu tính ở server, không ở browser.** Quỹ đạo đã nằm sẵn trong payload
nên chiếu ở client là cám dỗ hiển nhiên, nhưng nó đặt **bản sao thứ hai** của
luật arc-length vào TypeScript; hai bản sẽ lệch ngay lần đầu một bên được sửa, và
lệch đó hiện ra dưới dạng panel vẽ một điểm phân kỳ mà report không nhắc tới.
`replay_view.py` là chỗ duy nhất biến payload thành input, nên nó test được **mà
không cần file Parquet** — phần không test được co lại còn ba dòng trong service.

**Ghép cặp được kiểm ở đây, không giả định.** Hai trace khác episode ⇒ từ chối:
hai canvas cạnh nhau tự nó tuyên bố một phép so ghép cặp (HĐ-3.2), và dựng nó từ
hai episode khác nhau là bức tranh sai thuyết phục nhất hệ này có thể vẽ. Cột
lệch độ dài cũng từ chối — ghép timestamp với pose của mẫu khác là đặt robot vào
chỗ nó chưa từng ở.

**UI:** trang decisions có toggle **`syncMode`** (`time` | `progress`) — **đặt
tên khác `mode`** đúng như note audit yêu cầu, vì `mode` là cách *vẽ* (2D/2.5D).
Ở chế độ progress:

- thanh trượt chạy theo **mét arc length**, giữ ở state riêng (`scan`) chứ không
  mượn `playback.time` vốn tính bằng giây — một biến mang hai đơn vị là lỗi chờ
  người đọc;
- hai panel nhận **hai timestamp khác nhau** (`sideTime(view, scan.time, side)`),
  đó chính là khác biệt giữa hai chế độ;
- cảnh báo render **nguyên văn từ payload**, kèm badge chất lượng chiếu và tên
  candidate cho mượn tuyến;
- chip "chỗ hai bên tách nhau" (lệch duy trì + mốc event) bấm được để nhảy tới
  đúng vị trí đó.

Hai test cũ khẳng định `playbackTime={playback.time}` đã **đổi**, không phải bỏ:
bất biến "một đồng hồ duy nhất điều khiển cả hai panel" vẫn đúng, nhưng ở chế độ
progress đồng hồ đó là `scan`, và việc hai bên ở hai timestamp là **cố ý**. Test
mới khẳng định đúng điều đó thay vì khẳng định câu chữ cũ.

## 8. Blocker ΔU-theo-episode, và cách gỡ

Bốn vai exemplar dựng xong từ đầu, nhưng **ba trong bốn định nghĩa trên ΔU từng
episode**, mà report đã lưu không có con số đó: hàng episode
(`_episode_outcomes`) cố ý hẹp bảy trường — đủ cho `safety_critical`, không đủ
dựng lại objective (thiếu path_efficiency, smoothness, memory_estimate_mb…).

An chốt **phương án ghi thẳng vào report lúc chấm**. Đã làm:

- `selection.py` lấy `episode_utilities` từ chính `CandidateEvidence` vừa dùng để
  xếp hạng, và hàng episode có thêm **`episode_decision_utility`**. Tên nói rõ
  **mức episode**, không phải số trên card: hai mức lệch nhau ở U_R nên người đọc
  trung bình cột này sẽ **không** ra số trên card — đúng, và đó là lý do tên phải
  nói mức.
- Candidate bị loại ở cổng **không có** entry (không phải `0.0`): nó chưa từng
  được chấm, còn `0.0` đọc ra thành "đã chấm, và tệ".
- `exemplars.py` tách làm hai tầng: `select_exemplars_from_series()` là công thức
  thật (chỉ cần utility + safety theo episode), còn `select_exemplars()` thành
  adapter cho evidence đang nằm trong bộ nhớ. Nhờ vậy `select_exemplars_from_report()`
  chọn được đúng bốn vai từ một report đọc lại **nhiều tháng sau**, bằng code
  không có `CandidateEvidence` và không dựng lại được.

**Run cũ: từ chối, không xấp xỉ.** Report ghi trước khi có cột này ⇒
`ReportExemplarRefusal` với thông điệp nói rõ phải chấm lại. Thay ΔU bằng
travel_time, hoặc chỉ trưng mỗi vai `safety_critical` còn sống, là đặt **một cặp
episode được chọn theo cách khác** dưới cái nhãn nói rằng công thức đã chọn
chúng. UI bắt lỗi đó và rơi về danh sách episode thường — trạng thái trung thực,
không phải bộ exemplar giả.

**Endpoint:** `GET /decisions/{run_id}/exemplars`. UI hiện bốn chip trong thanh
công cụ, bấm để nhảy tới episode, chip đang mở được tô, và chip nào chọn bằng
tie-break thì ghi `(đồng hạng)` ngay trên nhãn.

## 9. Kiểm chứng

- Python: `test_explanation_replay_sync.py` (24), `test_explanation_exemplars.py`
  (18), `test_explanation_replay_view.py` (12). **232 passed** trên toàn bộ test
  explanation + `test_api` + `test_decision_card` + `test_stats`.
- Web: `npx vitest run` — **965 passed**, gồm 8 test mới: toggle tách tên khỏi
  `mode`, cảnh báo render nguyên văn, tên tuyến tham chiếu, chip phân kỳ, luật
  "không tự chiếu ở client", bốn vai exemplar, và fallback khi không có bộ nào.
- `npx tsc --noEmit` sạch; `ruff check` sạch trên `packages/`, `apps/api`, test.
- **Full suite Python chưa chạy** (theo yêu cầu). `test_decision_card.py` +
  `test_vertical_slice.py` đã chạy riêng vì `selection.py` bị sửa — 64 passed.

## 10. Chưa làm — nói rõ

- **`reference_plan` chưa lấy được từ đâu**, nên hôm nay mọi tuyến là
  `degraded_*`. Đường đã chốt: fallback trước, API sau. Tham số `planned_path`
  đã có sẵn và có test, ngày API trả được global plan thì không đổi gì khác.
- **Cảnh báo hiện chỉ có tiếng Anh** vì nó là văn bản do platform sở hữu và
  render nguyên văn. Muốn song ngữ thì phải dịch **ở platform** (một nguồn), không
  phải ở client — client dịch được nghĩa là client sửa lời được.
- **Prevalence theo detector** vẫn chờ E3.
- **Run cũ không có exemplar** cho tới khi được chấm lại — hệ quả đã biết của
  phương án đã chọn, và là hệ quả fail-closed đúng hướng.
- **`projection_quality` chưa vào artifact có header E0** — chỗ nối là E4.

## 11. Vòng rà của An — bốn điểm

**HIGH-1 — cặp winner/runner-up có thể sai.** Đúng. Hệ quả đúng như An liệt kê
— nhãn `strongest_for_winner` đảo nghĩa, và canvas có thể vẽ một cặp trong khi
exemplar tính cho cặp khác.

> **Đính chính:** bản đầu của mục này viết rằng cặp đó "đã được ghi sẵn ở
> `decision_card.recommended` / `.alternative`". **Sai** — xem mục 12.

Sửa ở cả ba chỗ, đọc **cùng một nguồn**:
- `compared_pair(report)` đọc `comparison_pair` (mục 12); không có ⇒ **từ chối**
  (không có xếp hạng thì không có winner, và chọn bừa hai cái là cách "best for
  A" rơi trúng candidate đã thua).
- UI có `panelCandidates(run, candidates)` cùng luật, **winner bên trái**; chỉ
  rơi về `slice(0,2)` khi run không ghi cặp nào.
- Trang còn **fail-closed**: nếu cặp trong `ExemplarSet` khác cặp đang vẽ thì
  **không hiện chip nào** — bốn chip gắn nhãn episode của cặp khác tệ hơn không
  có chip.

Regression đúng ca An mô tả: ba candidate, thứ tự report ngược ranking, candidate
bị loại đứng đầu và **không có utility** — cả ở tầng Python lẫn qua HTTP.

**HIGH-2 — `steps` không chặn.** Đúng. Nay `Annotated[int, Query(ge=2, le=2000)]`.
Một tham số vừa định cỡ vòng lặp vừa định cỡ payload, trên một route không cần
đăng nhập, thì `?steps=1000000000` không phải "client muốn biểu đồ mịn hơn".
Test cho cả cận trên lẫn cận dưới.

**MEDIUM-3 — refusal trả 500.** Đúng, và docstring client của tôi còn hứa "4xx".
Nay dịch ở ranh giới service: `ExemplarRefusal` ⇒ **409** (trạng thái dữ liệu —
không có card, hoặc chấm trước khi có cột utility; hỏi cách nào cũng cùng câu trả
lời), `ReplaySyncRefusal` ⇒ **422** (yêu cầu đòi thứ dữ liệu không đáp được).

**MEDIUM-4 — test UI chỉ soi chuỗi.** Đúng, và đó chính là lý do HIGH-1 lọt: cả
hai phiên bản đều chứa mọi chuỗi mà test đi tìm. Một ràng buộc phải nói rõ: suite
web này **cố ý không có jsdom/testing-library** (`vitest.config.ts`,
`docs/KNOWN_LIMITATIONS.md`), nên "click đổi frame" không mô phỏng được. Thay vào
đó:
- tách logic thuần sang `lib/replaySync.ts` và test **hành vi**: 10 test cho
  chọn cặp, thứ tự winner, và `sideTime` trả **hai timestamp khác nhau** cho hai
  bên;
- tách panel sang `components/ProgressSync.tsx` (page của Next không được export
  thêm gì) và test bằng `renderToStaticMarkup`: cảnh báo có mặt, badge chất lượng
  chiếu, chip phân kỳ, lỗi hiện ra như lỗi;
- bốn test soi-chuỗi cũ **bị xoá** thay vì sửa cho khớp — chúng đã được thay bằng
  test chạy thật;
- pytest cho hai endpoint: cặp lấy từ card, 409 cho run không card, 409 cho run
  cũ, 404 cho candidate lạ, 422 cho `steps` ngoài biên.

**Một quan sát ngoài lề, không sửa:** chạy pytest với thứ tự tham số
`tests/api/... tests/<root>... tests/api/...` làm pytest mất `tests/api/conftest.py`
("fixture 'client' not found"). Tái hiện được **chỉ bằng file có sẵn** (`test_api_auth.py`
+ `test_stats.py` + `test_api_decisions.py`), nên là wart hạ tầng có từ trước —
`tests/` là package còn `tests/api/` thì không. Chạy cả thư mục thì không sao.

## 12. Vòng rà thứ hai — `alternative` không phải runner-up

An chỉ ra bản sửa HIGH-1 của tôi **sai đúng loại lỗi mà nó tự nhận là đang sửa**:
tôi thay "hai candidate đầu danh sách" bằng `decision_card.alternative`, mà
`alternative` **không phải** statistical runner-up.

Kiểm lại trong code, An đúng từng chữ:

- `card.py` §HĐ-12 ghi thẳng trong comment: *"only ever a PARETO_FRONTIER
  candidate. The statistical runner-up is a different claim"*;
- `tests/test_decision_card.py::test_the_runner_up_is_not_promoted_to_alternative`
  khẳng định `card.alternative is None` trong khi `recommendation.runner_up_id`
  vẫn tồn tại;
- và test chạy thật của tôi (mục 13) xác nhận trên một run 6 episode: card có
  `alternative: null`, còn winner/runner-up thì có thật.

Nghĩa là bản sửa trước **tệ hơn** ở ca phổ biến: run bình thường không chạy
Pareto ⇒ `compared_pair()` trả `None` ⇒ endpoint trả 409 dù run có winner hợp lệ
⇒ UI rơi về `slice(0,2)` ⇒ **lỗi registration-order quay lại nguyên vẹn**. Còn
khi `alternative` có giá trị, nó vẫn có thể là candidate mà ΔU chưa từng so.

**Sửa đúng:** run lúc chấm ghi thẳng cặp thống kê vào report, nguồn là
`recommendation.recommended_id` / `.runner_up_id`:

```json
"comparison_pair": {
  "recommended_candidate_id": "...",
  "runner_up_candidate_id": "..."
}
```

Python `compared_pair()`, `comparedPair()` phía UI và canvas replay đọc **cùng
một field này**. Không chỗ nào đọc `alternative` nữa, và có test khẳng định điều
đó ngay cả khi `alternative` đang trỏ vào một candidate khác.

## 13. Kiểm chứng bổ sung — một test chạy thật thay vì fixture

Hai vòng rà vừa rồi đều lọt vì **fixture đồng ý với code sai**. Nên thêm
`tests/test_explanation_report_wiring.py`: chạy `run_comparison` thật trên 6
episode rồi hỏi report đúng những câu tầng giải thích sẽ hỏi —

- `comparison_pair` **có mặt** và khớp `decision_card.recommended`;
- `decision_card.alternative` **là null** trên chính run đó (bằng chứng thực
  nghiệm cho mục 12);
- mọi episode của mọi candidate được chấm đều có `episode_decision_utility`
  trong `[0, 1]`;
- `select_exemplars_from_report()` chạy được end-to-end trên report đó.

Đây là thứ duy nhất trong bộ test không thể bị một fixture nói dối hộ.

**Tổng:** Python 159 (unit) + 7 (API) + 4 (wiring) passed; web 975 passed;
`tsc --noEmit` sạch; `ruff` sạch trên phần của tôi. Full suite chưa chạy.

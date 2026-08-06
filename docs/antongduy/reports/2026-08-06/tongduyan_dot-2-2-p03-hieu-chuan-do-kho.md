# Báo cáo — Đợt 2.2: P03 Hiệu chuẩn độ khó thực nghiệm

> **Ngày:** 2026-08-06
> **Plan nguồn:** `docs/antongduy/plans/2026-08-05/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`, mục **2.2**
> **Nhánh:** `tongduyan`
> **Tiền đề:** Đợt 1 (P02 + P04) và Đợt 2.1 (P05) đã xong cùng ngày.
> **Phạm vi:** chỉ 2.2. Mục 2.3 (Scenario Editor) **chưa** làm.

---

## 1. Vấn đề đang giải

Trước đợt này, "độ khó" của một scenario là **thứ tự người viết xếp ra**:
`CURRICULUM_ORDER` đi từ `open_space` tới `dynamic_warehouse`, và mọi
chỗ khác trong hệ thống coi thứ tự đó là độ khó. Không ai từng đo xem nó
có đúng không.

Hệ quả nặng hơn vẻ ngoài của nó. Giới hạn số 1 của báo cáo P05 là: tập
holdout được chọn tay, và **chưa loại trừ được** khả năng chênh lệch
dev/holdout chỉ phản ánh độ khó chứ không phải khả năng tổng quát hóa.
Không có thang độ khó đo được thì không tách được hai nguyên nhân đó.

P03 thay câu "scenario này khó" bằng một phép đo:

```text
difficulty(scenario) = 1 - success_rate(baseline đã ghim, seed cố định)
```

---

## 2. Quyết định lớn: baseline là toàn bộ nội dung của con số

Ghi `"astar+dwa"` không phải là ghi baseline. Cùng stack đó trên robot
bán kính khác, với DWA weight khác, trên tập seed khác, hay ở commit
khác, đo ra một **thang khác** — và người đọc so hai cache sẽ không có
cách nào nhận ra. Nên cache ghim đủ: thuật toán, config, robot profile,
danh sách seed đầy đủ, `replanning_enabled`, `benchmark_spec_version`,
`protocol_version`, `git_sha`. Test bắt buộc từng trường: xóa bất kỳ
trường nào thì cache bị **từ chối**.

Ba hệ quả thiết kế đi theo, giống hệt lý do của P05:

1. **Không thêm `difficulty` vào `Scenario`.** Độ khó là kết quả của
   việc chạy scenario, không phải đặc tính của nó. Nếu nằm trong schema
   thì nó vào `conditions_checksum`, và hiệu chuẩn lại sẽ khiến mọi
   benchmark cũ trên scenario đó trông như đã chạy dưới điều kiện vật lý
   khác. Có test khẳng định checksum không đổi khi cài cache.
2. **Cache có version, không ghi đè.** Baseline đổi thì
   `calibration_version` mới; hai thang đo dưới hai baseline là hai đại
   lượng khác nhau chỉ trùng tên.
3. **Chưa hiệu chuẩn thì không có độ khó.** `get_difficulty()` trả
   `None`, không raise, và **không** rơi về curriculum order. Việc hai
   thứ đó lệch nhau chính là cái cần nhìn thấy (xem mục 5).

Và: **không có endpoint ghi.** Một độ khó đặt được từ form không phải là
số đo.

---

## 3. Đã làm gì

### 3.1. `packages/benchmark/planbench_benchmark/difficulty.py` (mới)

| Thành phần | Ghi chú thiết kế |
|---|---|
| `BaselineSpec` | Mọi thứ phải ghim, `extra="forbid"`, mọi trường bắt buộc. |
| `ScenarioCalibration` | `difficulty`, `ci95`, `success_rate`, `episodes`, `status_counts`, `map_checksum`, `scenario_checksum`, `scenario_split`. |
| `DifficultyCalibration` | version + baseline + scenarios. Sai schema là **lỗi**, không phải "mất nhãn". |
| `get_difficulty(name, version=None)` | Trả `DifficultyLabel \| None`. Version không khớp → `None`, không phải số của version khác. |
| `difficulty_band()` | `easy ≤ 0.2 < moderate ≤ 0.6 < hard ≤ 0.999 < unsolved`. |
| `difficulty_coverage()` | Báo cáo dải difficulty + cảnh báo. |

Ba chi tiết đáng nêu:

- **`unsolved` tách riêng khỏi `hard`.** Baseline chưa từng giải được
  thì độ khó ghim ở 1.0, và hai scenario như vậy **không xếp thứ tự với
  nhau được**. Gộp chung vào "hard" sẽ giấu mất việc thang đo đã hết độ
  phân giải. Đây không phải chuyện lý thuyết: 4/10 scenario rơi vào đó.
- **`stale`.** Entry lưu checksum của map và scenario lúc đo. Scenario
  bị sửa thì label trả `stale=true` — **vẫn trả số, có cờ**. Ẩn đi sẽ
  thành ô trống, mà ô trống nghĩa là "chưa đo", một vấn đề khác hẳn với
  cách sửa khác hẳn.
- **Kiểm tra khoảng giữa, tách khỏi kiểm tra biên độ.** Ban đầu coverage
  chỉ đo `max - min`. Kết quả chạy thật cho thấy phép kiểm đó **không đủ**:
  bộ scenario hiện tại đạt biên độ 1.000 — điểm tuyệt đối — mà vẫn không
  phân biệt được gì, vì các giá trị dồn về hai đầu 0.0 và 1.0. Nên có
  thêm `midrange_count`: số scenario nằm trong `(0.2, 0.8)`, tức khoảng
  duy nhất mà hai stack đều khá có thể khác điểm nhau. Cache hiện tại có
  **1**, và coverage cảnh báo đúng điều đó.

### 3.2. `scripts/calibrate_difficulty.py` (mới)

Chạy baseline qua **chính `run_benchmark()`**, không qua vòng lặp riêng:
độ khó phải được đo bằng đúng bộ máy sinh ra kết quả benchmark, nếu
không thang đo sẽ mô tả một đường code không ai bị chấm điểm trên đó.

- `--dry-run` (ít seed, không ghi, và version bị gắn hậu tố `-dryrun` để
  không ai chép nhầm output của nó thành thang thật);
- `--write` mới ghi; mặc định chỉ in;
- `--scenarios`, `--seeds`, `--algorithm`, `--algorithm-config`,
  `--calibration-version`, `--notes`;
- in bảng kết quả + **báo cáo dải difficulty** + cảnh báo;
- in thêm dòng nhắc mỗi khi chạm scenario holdout (mục 6).

**Không có timestamp trong cache.** Cùng code, cùng baseline, cùng seed
cho ra file **byte-identical** — có test. Đó là thứ khiến "chạy lại mà
xem" trở thành câu trả lời dùng được cho "số này còn đúng không?".

Ràng buộc thêm: mọi scenario trong một lần hiệu chuẩn phải dùng **cùng
robot**, nếu không script raise. Độ khó đo trên robot to nhỏ khác nhau
không phải các điểm trên cùng một thang.

### 3.3. API

| Endpoint | Nội dung |
|---|---|
| `GET /difficulty-calibration` | Thang đang cài + baseline + coverage + cảnh báo |
| `GET /scenario-library` | mỗi entry thêm `difficulty: DifficultyLabel \| null` |

Chưa hiệu chuẩn → `200` với thang rỗng và cảnh báo bằng chữ, **không
phải lỗi**: "chưa đo" là trạng thái bình thường của nền tảng.

Không thêm dependency nào trong đợt này, và cache là JSON nằm trong
`packages/` — thứ `Dockerfile.api` đã copy sẵn — nên image API không cần
đổi gì.

### 3.4. Frontend

- `DifficultyBadge` mới: **không bao giờ in số trần** — luôn kèm CI95,
  band, và tooltip ghi baseline + version + số seed; `stale` và số liệu
  tạm (ít seed) có badge riêng; chưa đo thì in "chưa đo", không phải dấu
  gạch.
- Trang library: **hai cột cạnh nhau** — "Vị trí trong curriculum" và
  "Độ khó đo được". Cố ý: chỗ hai cột lệch nhau là phát hiện chính của
  đợt này.
- Panel hiệu chuẩn: version, baseline, số seed, commit, dải difficulty,
  và **mọi cảnh báo coverage hiện ra màn hình** chứ không nằm trong log.

---

## 4. Test

**`tests/test_difficulty.py` — 45 test.** Hai test quan trọng nhất nằm
đầu file:

- `test_calibrating_changes_no_conditions_checksum` — tính checksum
  trước, cài cache, tính lại, khẳng định không đổi. Đây là test sẽ đỏ
  nếu có người chuyển difficulty vào `Scenario`.
- `test_scenario_schema_has_no_difficulty_field`.

Còn lại: biên của band (kể cả 0.999 vs 1.0), cache hỏng/thiếu/thừa key
đều bị **từ chối** (không phải "mất nhãn im lặng"), baseline thiếu bất
kỳ trường nào cũng bị từ chối, version không khớp trả `None`, scenario
bị sửa → `stale`, ít seed → `adequate=false`, coverage cảnh báo đúng cho
dải hẹp / toàn dễ / toàn khó / có `unsolved` / thiếu scenario, và cache
đang nằm trong repo phải hợp lệ và phủ đủ 10 scenario (chặn cache bị sửa
tay lọt vào git).

Về script: dry-run không ghi kể cả khi kèm `--write`, version dry-run
gắn hậu tố, **hai lần build cho file giống hệt nhau**, `difficulty` đúng
bằng `1 - success_rate`, CI bao lấy giá trị và **không suy biến thành
một điểm** khi chỉ có 2 seed, entry ghi đúng checksum đã đo, scenario lạ
bị từ chối.

**`tests/api/test_api_difficulty.py` — 7 test:** library entry mang độ
khó; scenario chưa hiệu chuẩn trả `null` **và** `curriculum_index` vẫn
còn nguyên bên cạnh (hai thứ không được lẫn); nền tảng chưa hiệu chuẩn
trả 200; coverage nêu tên scenario còn thiếu; endpoint từ chối `POST`.

**`apps/web/src/app/__tests__/difficulty-calibration.test.tsx` — 41
test:** số luôn đi kèm CI và baseline, `unsolved` khác màu `hard`, chưa
đo thì nói "chưa đo", cờ `stale`/tạm hiện, hai cột curriculum và độ khó
tách bạch, mọi cảnh báo coverage được render, mất calibration không biến
thành lỗi trang, i18n đủ hai ngôn ngữ và giữ đủ placeholder.

**Kết quả chạy:**

```
pytest (toàn bộ)                        1317 passed, 4 skipped (11:04)
  tests/test_difficulty.py              45 passed
  tests/api/test_api_difficulty.py       7 passed
ruff check .                            All checks passed
ruff format --check                     sạch
npx tsc --noEmit (apps/web)             sạch
npx vitest run (apps/web)               355 passed / 2 file fail có sẵn
```

Baseline sau Đợt 2.1 là 1265 passed; +52 test backend, +41 test frontend.

Hai fail frontend **có sẵn từ trước và không liên quan** (đã nêu ở ba
báo cáo trước): `dashboard-page.test.tsx` so đường dẫn kiểu POSIX trên
Windows, `assistant-page.test.tsx` đọc `src/app/models/page.tsx` chưa
tồn tại.

---

## 5. Kiểm chứng: chạy hiệu chuẩn thật

`astar+dwa`, 30 seed cố định (0–29), replanning tắt, commit `800b241`,
10 scenario, ~7 phút:

```
scenario                 split     difficulty   ci95           band       trạng thái
bidirectional_corridor   holdout        1.000   (0.89, 1.00)   unsolved   collision 30
crossing_obstacle        dev            0.267   (0.14, 0.44)   moderate   collision 8, success 22
doorway                  dev            0.000   (0.00, 0.11)   easy       success 30
dynamic_warehouse        holdout        1.000   (0.89, 1.00)   unsolved   collision 30
intersection             holdout        0.033   (0.01, 0.17)   easy       collision 1, success 29
narrow_corridor          dev            1.000   (0.89, 1.00)   unsolved   stuck 30
open_space               dev            0.000   (0.00, 0.11)   easy       success 30
static_obstacles         dev            0.000   (0.00, 0.11)   easy       success 30
sudden_stop              dev            1.000   (0.89, 1.00)   unsolved   stuck 30
wide_corridor            dev            0.000   (0.00, 0.11)   easy       success 30

dải: 0.000 .. 1.000 (spread 1.000)
band: easy=5, moderate=1, unsolved=4
scenario nằm trong (0.2, 0.8): 1
CẢNH BÁO: chỉ 1 scenario nằm giữa 0.2 và 0.8; ngoài khoảng đó baseline
hoặc luôn thành công hoặc luôn thất bại, nên bộ scenario không phân biệt
được hai stack đều khá.
CẢNH BÁO: 4 scenario baseline chưa từng giải được; độ khó ghim ở 1.0 và
không xếp thứ tự với nhau được.
```

Bốn điều đáng đọc kỹ:

**1. `open_space` đúng là dễ** — như plan yêu cầu kiểm. Nhưng CI95 vẫn
là `(0.00, 0.11)` chứ không phải `(0, 0)`: 30 lần thành công không phải
là bằng chứng không bao giờ thất bại.

**2. Thang đo lưỡng cực, rỗng ở giữa.** Dải trải đủ 0→1 nhưng chỉ có
**một** scenario nằm giữa (`crossing_obstacle`, 0.267). Nghĩa là bộ
scenario hiện tại hầu như không phân biệt được hai stack đều khá: hoặc
cả hai qua hết, hoặc cả hai chết hết. Đây chính là lỗ hổng Scenario
Editor (Đợt 2.3) sinh ra để lấp — bằng cách **viết thêm scenario**,
không phải sửa tay cache.

Đáng nói là phép kiểm biên độ ban đầu **không bắt được lỗi này**: bộ
scenario này đạt spread 1.000, điểm cao nhất có thể. Đó là lý do
`midrange_count` được thêm vào sau khi nhìn số liệu thật — một phép kiểm
chỉ đo hai đầu mút sẽ chấm điểm tuyệt đối cho đúng cái tập không đo được
gì.

**3. Curriculum order sai đáng kể so với số đo.** `intersection` được
xếp thứ 8/10 (gần khó nhất) nhưng đo ra **0.033 — thuộc nhóm dễ**, trong
khi `narrow_corridor` (thứ 3) và `sudden_stop` (thứ 6) đo ra **1.000**.
Thứ tự người viết ra và độ khó thật lệch nhau, và đó là lý do hai cột
nằm cạnh nhau trong UI thay vì cột này thay cột kia.

**4. Kết quả này nói ngược lại giới hạn số 1 của P05.** Tập holdout
(`bidirectional_corridor` 1.000, `dynamic_warehouse` 1.000,
`intersection` **0.033**) **không** phải "ba cái khó nhất": một trong ba
là scenario dễ thứ nhì của cả bộ. Nghi ngờ rằng chênh lệch dev/holdout
chỉ là chênh lệch độ khó vì thế **yếu đi** — nhưng chưa bị bác bỏ, vì
hai scenario holdout còn lại vẫn nằm ở đỉnh thang.

Ngoài ra, phân loại trạng thái thất bại tách được hai kiểu "khó" hoàn
toàn khác nhau: `narrow_corridor` và `sudden_stop` chết vì **stuck**
(30/30), còn `bidirectional_corridor` và `dynamic_warehouse` chết vì
**collision** (30/30). Chỉ nhìn con số 1.000 thì hai nhóm này giống hệt
nhau; chúng không giống nhau, và `status_counts` trong cache giữ lại
khác biệt đó.

**Tái lập:** chạy lại cùng baseline và cùng seed cho ra file y hệt (có
test tự động khẳng định điều này).

---

## 6. Chi phí đã trả cho tập holdout

Hiệu chuẩn phải chạy cả scenario holdout — không đo thì không biết tập
holdout nằm ở đâu trên thang, mà đó lại là câu hỏi P03 sinh ra để trả
lời. Nên lần chạy này là **3 lần "nhìn" vào tập held-out**. Script in
cảnh báo cho từng lần.

Điểm chưa khép kín: các lần nhìn này **chưa** vào `holdout_usage[]` của
`GET /generalization`, vì calibration không tạo benchmark lưu trữ. Đã
ghi vào `KNOWN_LIMITATIONS.md` mục 126.

---

## 7. Definition of Done (plan mục 2.2)

- [x] Có script chạy được (`scripts/calibrate_difficulty.py`, có `--dry-run`).
- [x] Có cache versioned (`difficulty_calibration.json`, `calibration_version` 1.0.0).
- [x] Có CI95 (Wilson, lấy gương từ khoảng của success rate).
- [x] Có baseline metadata đầy đủ — và test bắt buộc từng trường.
- [x] Cache tái tạo được — không timestamp, có test byte-identical.
- [x] Không thêm difficulty vào `Scenario` — có test checksum không đổi.
- [x] API xử lý scenario chưa hiệu chuẩn (`null`, không raise, không
      mượn `curriculum_index`).
- [x] Có báo cáo dải difficulty — trong script, trong
      `GET /difficulty-calibration`, và trên trang library.

---

## 8. Giới hạn đã ghi vào `KNOWN_LIMITATIONS.md` (mục 119–126)

1. Thang lưỡng cực, gần như rỗng ở giữa (5 easy / 1 moderate / 4 unsolved).
2. Bốn scenario ghim ở 1.0 **không xếp thứ tự với nhau được**; thang
   đang bị chặn trên bởi năng lực baseline.
3. Curriculum order và độ khó đo được lệch nhau; curriculum của PPO vẫn
   dùng thứ tự cũ.
4. Một baseline duy nhất định nghĩa thang — đo "khó với A*+DWA", không
   phải "khó nói chung".
5. Replanning tắt; bật lên phải tạo calibration version mới.
6. Cache phát hiện được scenario đổi (`stale`) nhưng **không** phát hiện
   được code planner/simulator đổi.
7. Độ khó chưa nối vào leaderboard/report/biểu đồ (thuộc F09, Đợt 3).
8. Calibration đã "nhìn" tập holdout 3 lần, chưa vào `holdout_usage[]`.

---

## 9. File đã đổi

**Mới:**
- `packages/benchmark/planbench_benchmark/difficulty.py`
- `packages/benchmark/planbench_benchmark/difficulty_calibration.json`
- `scripts/calibrate_difficulty.py`
- `apps/web/src/components/DifficultyBadge.tsx`
- `tests/test_difficulty.py`
- `tests/api/test_api_difficulty.py`
- `apps/web/src/app/__tests__/difficulty-calibration.test.tsx`

**Sửa:**
- `packages/benchmark/planbench_benchmark/__init__.py`
- `apps/api/planbench_api/routers/library.py`
- `apps/web/src/lib/platformTypes.ts`
- `apps/web/src/app/library/page.tsx`
- `apps/web/src/lib/i18n/locales/en.json`, `vi.json`
- `docs/API_CONTRACT.md`, `docs/KNOWN_LIMITATIONS.md`

---

## 10. Bước tiếp theo

**2.3 — Scenario Editor**, và bây giờ nó có một mục tiêu đo được thay vì
"cho phép tạo scenario": lấp khoảng difficulty 0.2–0.8 đang trống, rồi
chạy lại `calibrate_difficulty.py` để xác nhận đã lấp được.

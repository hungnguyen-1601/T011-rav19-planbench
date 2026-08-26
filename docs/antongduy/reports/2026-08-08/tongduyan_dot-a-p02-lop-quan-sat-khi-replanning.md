# Báo cáo — Đợt A: Sửa khai báo cân bằng thông tin (P02) khi replanning bật

> **Ngày:** 2026-08-08
> **Plan nguồn:** `docs/antongduy/plans/2026-08-07/replanning-lien-tuc-va-noi-day-vao-simulate.md`, **Đợt A**
> **Lựa chọn đã chốt:** **Lựa chọn 1** — nâng lớp quan sát theo điều kiện chạy.
> **Nhánh:** `integrate-tongduyan`
> **Phạm vi:** chỉ Đợt A. **Không** đụng Đợt B (nối dây `/simulate` + UI bật replanning),
> **không** đụng Đợt C (replan chu kỳ), **không** đụng Đợt D (hiệu chuẩn lại difficulty).

---

## 1. Vấn đề đang sửa

Sau Đợt 4.1, `_replan()` (`nav_stack.py`) lấy vị trí vật cản động qua
`engine.dynamic_obstacles_now()` — **ground truth**: chính xác tuyệt đối,
không nhiễu, không che khuất, không cần cảm biến. Trong khi đó registry
vẫn khai báo cả 5 stack là:

```python
global_observation_class="full_static_map"
```

Khi replanning bật, câu khai báo đó **sai**. Global planner lúc ấy nhận
đúng thứ mà lớp `human_states` mô tả.

Đây không phải chi tiết nhỏ. **P02 là differentiator của cả dự án.**
Mục 0.3 của đề bài phê phán Alyassi et al. (lỗ hổng S1) đúng vì chuyện
này — cấp cho baseline đặc quyền đọc vị trí người thật rồi xếp chung
bảng với planner chỉ có LiDAR. Nếu ta bật replanning với ground truth mà
vẫn dán nhãn `full_static_map`, ta **lặp lại đúng lỗi ta đang phê phán**,
và tệ hơn vì ta có sẵn cơ chế khai báo mà không dùng.

Cửa sổ rủi ro đang hẹp: replanning mặc định tắt và chưa có UI, nên
**chưa report nào bị dán nhãn sai**. Sửa trước Đợt B là đúng thứ tự —
Đợt B chính là thứ giúp người ta tạo ra số bị dán nhãn sai nhanh hơn.

## 2. Hai quyết định đã chốt với user

### 2.1. Tên lớp quan sát mới: `full_static_map+human_states`

Khớp pattern đã có (`lidar+human_states`) và nói đủ hai vế: global
planner vẫn thấy map tĩnh đầy đủ **và** thêm vị trí thật của vật cản
động. Phương án loại: dùng lại `human_states` có sẵn — nó nói **ít hơn**
sự thật, vì bỏ mất vế map tĩnh.

### 2.2. Khóa nhóm leaderboard gồm **cả hai** lớp, không chỉ lớp local

Phát hiện khi đọc code, **không có trong plan**:
`build_leaderboard()` nhóm theo `(conditions_checksum, local_observation_class)`.
Replanning nâng lớp **global**. Nên nếu chỉ dựa vào cơ chế cũ, việc tách
nhóm hoàn toàn nhờ `conditions_checksum` (đã khác vì `FairnessRecord`
hash replanning khi bật) — lớp quan sát chỉ còn là đồ trang trí.

Đã đổi khóa nhóm thành `(conditions_checksum, global_class|local_class)`.
Ràng buộc trực tiếp thay vì gián tiếp: đổi luật hash checksum sau này
cũng không làm hai run rơi chung nhóm.

Dữ liệu cũ **không đổi nhóm** — mọi aggregate cũ đều `full_static_map`,
nên phần mới của khóa là hằng số trên toàn bộ dữ liệu đang có.

## 3. Cái đã làm

### 3.1. `observation.py` — lớp mới + hàm suy ra

```python
ObservationClass = Literal[
    "full_static_map",
    "lidar_only",
    "human_states",
    "lidar+human_states",
    "full_static_map+human_states",   # mới
]

def global_class_under_replanning(
    declared: ObservationClass | None, *, replanning_enabled: bool
) -> ObservationClass | None: ...
```

Ba chi tiết có chủ ý:

- **Bảng tra cố định, không nối chuỗi.** `_UNDER_REPLANNING` ánh xạ từng
  giá trị. Thêm một lớp quan sát mới mà quên thêm vào bảng sẽ `KeyError`
  ngay lúc chạy — im lặng bịa ra một tên lớp không ai nhận là đúng thứ
  P02 sinh ra để chặn. Có test quét toàn bộ `OBSERVATION_CLASSES`.
- **`None` vào, `None` ra.** Stack không có khai báo thì không có gì để
  nâng; bịa một nhãn cho nó chính là hành vi mà trường nullable tồn tại
  để ngăn.
- **`lidar_only` nâng thành `lidar+human_states`,** không thành
  `full_static_map+human_states`. Hiện chưa stack nào khai `lidar_only` ở
  tầng global, nhưng nhánh này phải đúng sẵn.

### 3.2. `runner.py` — lấy nhãn từ điều kiện chạy

```python
def aggregate_algorithm(
    algorithm_id: str,
    runs: Sequence[RunRecord],
    *,
    replanning: ReplanningConfig | None = None,   # mới, có default
) -> AlgorithmAggregate:
```

`global_observation_class` trong `AlgorithmAggregate` giờ là giá trị
**đã nâng**, không phải `info.global_observation_class` thô. Tham số có
default nên mọi caller cũ (7 chỗ trong test) không vỡ và cho đúng kết
quả cũ.

Cơ chế **snapshot** giữ nguyên như P02 đã thiết kế — chỉ đổi *nguồn* của
giá trị được chụp. Quan trọng: nếu leaderboard suy lại nhãn lúc đọc thì
run có replan sẽ **âm thầm mất phần nâng** ngay khi hiển thị, vì registry
vĩnh viễn nói `full_static_map`. Có test riêng cho đúng chuyện này.

### 3.3. `leaderboard.py` — khóa nhóm và trường mới

- `class_key = f"{global_class or ''}|{local_class or ''}"`.
- `LeaderboardGroup.global_observation_class` — lớp global chung của
  nhóm, `null` khi nhóm bị trộn.
- `cross_observation_class_warning` bật khi **một trong hai** lớp không
  thống nhất (trước chỉ xét lớp local).

### 3.4. `report_markdown.py` — nói rõ vì sao nhãn khác registry

Bảng Algorithms in lớp đã nâng. Nhưng nhãn trần sẽ trông như bug: người
đọc tra `astar+dwa` trong registry thấy `full_static_map`, tra report
thấy thứ khác. Nên khi và chỉ khi `fairness.replanning_enabled`, mục
"Algorithms under test" in thêm đoạn giải thích: replanning bật, replan
tính từ vị trí ground-truth của vật cản động, registry mô tả một stack
lập đường một lần trên map tĩnh và những run này không phải như vậy; lớp
local **không đổi** vì bộ điều khiển vẫn chỉ có LiDAR.

Report không bật replanning: **không có đoạn này**, không có chuỗi
`full_static_map+human_states`. Có test cho cả hai chiều.

### 3.5. Frontend

- `ObservationClass` thêm giá trị mới; `LeaderboardGroup` thêm
  `global_observation_class`.
- Trang leaderboard in dòng lớp global riêng, tách khỏi dòng lớp
  controller — hai lớp giờ có thể khác nhau, và nếu chỉ in lớp
  controller thì nhóm có replan với nhóm không replan **trông y hệt
  nhau** trên UI.
- Khi lớp global chứa `human_states`, dòng đó đổi sang câu dài hơn nói
  rõ replanning đã bật và các dòng này không so được với run không
  replan. Key mới ở cả `en.json` và `vi.json`.

### 3.6. Docs

- `API_CONTRACT.md`: bảng "điều kiện chạy → nhãn", giá trị hợp lệ mới,
  và giải thích vì sao khóa nhóm leaderboard lấy cả hai lớp.
- `KNOWN_LIMITATIONS.md`: **#158** (nhãn đã đúng nhưng *nguồn dữ liệu*
  vẫn là ground truth — Lựa chọn 2, costmap từ LiDAR, mới là lời giải
  thật và cần plan riêng ~3 ngày), **#159** (bảng tra cố định + đổi khóa
  nhóm). Sửa **#156**: bản cũ chỉ nói thiếu ô chọn ở form benchmark, bỏ
  sót nửa quan trọng hơn là `/simulate` chưa được nối dây chút nào.
- `IMPLEMENTATION_STATUS.md`: mục Đợt A.

## 4. File thay đổi

| File | Thay đổi |
|---|---|
| `packages/benchmark/planbench_benchmark/observation.py` | lớp `full_static_map+human_states`, `global_class_under_replanning()`, bảng `_UNDER_REPLANNING` |
| `packages/benchmark/planbench_benchmark/runner.py` | `aggregate_algorithm(..., replanning=)`; `run_benchmark` truyền `spec.replanning` xuống |
| `apps/api/planbench_api/leaderboard.py` | khóa nhóm 2 lớp, `LeaderboardGroup.global_observation_class`, warning xét cả 2 lớp |
| `apps/api/planbench_api/report_markdown.py` | `_replanning_observation_note()` |
| `apps/web/src/lib/benchmarkTypes.ts` | giá trị `ObservationClass` mới |
| `apps/web/src/lib/platformTypes.ts` | `LeaderboardGroup.global_observation_class` |
| `apps/web/src/app/leaderboard/page.tsx` | dòng lớp global ở header nhóm |
| `apps/web/src/lib/i18n/locales/{en,vi}.json` | 2 key mới |
| `apps/web/src/lib/__tests__/charts.test.ts` | fixture thêm trường mới |
| `tests/test_observation_class.py` | **+3 class test** (10 test mới) |
| `tests/api/test_api_report_export.py` | **+2 test** |
| `docs/{API_CONTRACT,KNOWN_LIMITATIONS,IMPLEMENTATION_STATUS}.md` | contract + giới hạn #158–#159 + sửa #156 |

## 5. Test — đối chiếu danh sách bắt buộc của plan (A.5)

| Plan A.5 yêu cầu | Test |
|---|---|
| Replanning tắt → `global_observation_class` giữ `full_static_map` | `test_replanning_off_keeps_the_registry_label` (kiểm cả 3 dạng: `None`, `NO_REPLANNING`, `enabled=False`) |
| Replanning bật → lớp quan sát được nâng | `test_replanning_on_upgrades_the_global_half_only` |
| Report cũ đọc ra `full_static_map`, không raise, không đoán | `test_a_pre_replanning_report_reads_as_full_static_map` |
| Leaderboard: hai aggregate khác lớp không cùng nhóm mặc định | `test_they_do_not_share_a_default_group` |
| Ép xem chung → `cross_observation_class_warning = True` | `test_forcing_them_together_raises_the_cross_class_warning` |
| Snapshot: đổi registry sau khi chạy không đổi nhãn số đã lưu | `test_the_upgraded_label_is_a_snapshot` |

Thêm ngoài danh sách:

- **Không lớp nào rơi vào tên bịa.** `test_enabled_upgrades_every_known_class`
  quét toàn bộ `OBSERVATION_CLASSES`; giá trị nâng phải nằm trong
  `OBSERVATION_CLASSES` và phải chứa `human_states`. Đây là test bắt lỗi
  cho người thêm lớp quan sát mới sau này.
- **`None` không bị nâng** — `test_an_undeclared_stack_is_not_given_one`.
- **Report không bật replanning không tự nhận đã nâng** —
  `test_a_report_without_replanning_claims_no_upgrade` (khẳng định
  *vắng mặt*, không chỉ khẳng định có mặt).
- **Report bật replanning có nhãn mới VÀ có lời giải thích** —
  `test_replanning_upgrades_the_global_class_and_says_why`, chạy qua API
  thật (`POST /benchmarks` với `replanning`, rồi `GET .../report.md`).

Điểm đáng nói ở `TestLeaderboardSeparatesReplanningRuns`: hai
`StoredBenchmark` được dựng với **cùng `conditions_checksum`**. Trong
production replanning luôn đổi checksum nên hai run đó tách nhóm sẵn —
nhưng khi ấy lớp quan sát chỉ là đồ trang trí. Ghim checksum bằng nhau
chứng minh **riêng lớp quan sát** đủ giữ chúng tách nhau, đúng điều P02
tuyên bố.

## 6. Kiểm chứng

### 6.1. Backend

```text
python -m pytest tests/ -q --ignore=tests/api    981 passed, 4 skipped in 74s
python -m pytest tests/api -q                    443 passed, 1 skipped in 404s
                                       tổng:    1424 passed, 5 skipped
ruff format + ruff check                         sạch
```

Baseline sau Đợt 4.1 là `1412 passed, 5 skipped` (`971 passed, 4 skipped`
cho `tests/` trừ `tests/api`; `441 passed, 1 skipped` cho `tests/api`).
Chênh đúng **+12**: **+10** test mới trong `test_observation_class.py` và
**+2** trong `test_api_report_export.py`. **Không có fail mới.**

### 6.2. Frontend

```text
npm run typecheck    sạch
npm run build        Compiled successfully
npm test             443 passed / 1 failed + 1 suite fail — CẢ HAI PRE-EXISTING
```

Hai failure y hệt đã ghi ở report Đợt 3.2 và 4.1, không liên quan đợt
này (không file nào trong diff chạm tới chúng):

1. `assistant-page.test.tsx` — đọc `src/app/models/page.tsx`, file không
   tồn tại trên nhánh (artifact của merge `integrate-tongduyan`).
2. `dashboard-page.test.tsx` — so path cứng `"/system/page.tsx"` với
   path Windows `"\system\page.tsx"`. Bug separator của test.

Số **giống hệt baseline 4.1** (`443 passed / 1 failed`), tức đợt này
không thêm và không sửa failure nào.

## 7. Definition of Done của plan (A.6) — đối chiếu

- [x] Lớp quan sát phản ánh đúng điều kiện chạy, không phải chỉ stack id.
- [x] Report cũ không đổi nhãn (test 3 dạng config tắt + report không snapshot).
- [x] Leaderboard không trộn chung (khóa nhóm gồm cả lớp global).
- [x] Report Markdown nói rõ vì sao lớp bị nâng.
- [x] Có mục KNOWN_LIMITATIONS cho ground truth ở tầng replan (#158).
- [x] Không đụng `conditions_checksum` — `FairnessRecord` không đổi một
      dòng trong đợt này; lớp quan sát là thuộc tính của *kết quả*,
      không phải của điều kiện mô phỏng.

## 8. Rủi ro còn lại

| Rủi ro | Ghi chú |
|---|---|
| Nhãn đúng **không** làm dữ liệu công bằng hơn — global planner vẫn đọc ground truth | Đây là ranh giới của Lựa chọn 1 và đã ghi rõ ở #158. Lời giải thật là Lựa chọn 2 (costmap tích luỹ từ LiDAR scan), ~3 ngày, cần plan riêng |
| Run có replan **không so được** với run không replan trong cùng bảng | Đúng theo thiết kế, nhưng là hệ quả thật: muốn có bảng so sánh có replanning thì mọi stack trong bảng phải cùng bật |
| Thêm lớp quan sát mới mà quên cập nhật `_UNDER_REPLANNING` | `KeyError` ngay + test quét toàn bộ `OBSERVATION_CLASSES`. #159 |
| Đợt C (replan chu kỳ) sẽ làm mức độ nghiêm trọng của #158 tăng hẳn | Replan chu kỳ nghĩa là global planner **liên tục** đọc ground truth, không phải vài lần. Đây là lý do A phải làm trước C — quyết định của A đã có, C thừa hưởng |

## 9. Việc kế tiếp theo plan

**Đợt B** — nối dây `/simulate` + nút bật ở UI (~1,5–2 ngày). Giờ an
toàn để làm: tính năng có dễ tiếp cận hơn cũng không sinh ra số bị dán
nhãn sai nữa.

**Đợt C** vẫn chờ user chốt sáu câu hỏi ở mục C.3 của plan — đặc biệt
câu về ngân sách tune `replan_period` và câu về chi phí chạy benchmark.

**Đợt D** chỉ sau A–C.

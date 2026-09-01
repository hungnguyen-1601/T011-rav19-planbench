# Báo cáo — Đợt 3.2: F05 Sửa Metrics Engine

> **Ngày:** 2026-08-07
> **Plan nguồn:** `docs/antongduy/plans/2026-08-05/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`, mục **3.2**
> **Nhánh:** `integrate-tongduyan`
> **Tiền đề:** Đợt 0–3.1 đã xong (RRT\*, Docker, P02, P04, P05, P03, Scenario Editor, F09).
> **Phạm vi:** chỉ 3.2. Với đợt này, toàn bộ phạm vi approve Đợt 0–3 của plan **đã hoàn thành**.

---

## 1. Vấn đề đang giải

Metrics engine trước đợt này có ba loại lỗi, mỗi loại một mức nghiêm trọng:

1. **Sai công thức so spec.** Field `smoothness` tính `Σ|Δθ|/L`
   (heading-change rate), trong khi đề bài mục 8.2 định nghĩa
   `S = Σ(Δθ)²`. Hai công thức xếp hạng khác nhau: rate chia cho chiều
   dài nên một đường dài ngoằn ngoèo nhẹ có thể "mượt" hơn một đường
   ngắn có một cú bẻ lái gắt — trong khi tổng bình phương phạt cú bẻ
   lái gắt đúng như cảm giác ngồi trên xe.
2. **Che giấu rủi ro bằng trung bình.** Latency của local planner chỉ có
   mean và max. Đề bài mục 8.3 dành nguyên một đoạn giải thích vì sao
   p99 là con số sống còn: robot chạy vòng điều khiển 10–20 Hz, một
   bước "đơ" 200 ms là 200 ms robot đi mù. Mean 10 ms với p99 200 ms
   trông giống hệ thống khỏe.
3. **Thiếu hẳn nhóm chỉ báo sớm.** Không stop-and-go (chỉ báo dao động
   local planner), không near-miss (thuật toán 0 va chạm nhưng 50 lần
   cà sát tường là thuật toán đang gặp may), không time-to-first-collision.

## 2. Quyết định thiết kế

### 2.1. Thêm cạnh field cũ, không đổi nghĩa field cũ

Đúng quy tắc 7 của plan: `smoothness` cũ **giữ nguyên công thức, giữ
nguyên tên**, chỉ đổi docstring thành "deprecated heading-change rate".
Field mới `smoothness_squared` mang công thức spec. Lý do không sửa tại
chỗ: mọi benchmark đã lưu, mọi client đang đọc, và một field đổi nghĩa
âm thầm tệ hơn một field thiếu — người đọc không có cách nào biết số
mình đang nhìn được tính bằng công thức nào.

Hệ quả cần biết: `smoothness_squared` **không chuẩn hóa theo L** (đúng
spec), nên chỉ so được giữa các trajectory cùng scenario. Ghi ở
KNOWN_LIMITATIONS #147.

### 2.2. Ngưỡng nằm trong `MetricConfig` versioned, snapshot vào từng episode

Plan yêu cầu "ngưỡng không hard-code theo thuật toán; phải nằm trong
metric config versioned". Cài đúng như vậy:

```python
class MetricConfig(BaseModel):          # frozen
    version: str = "1.0.0"
    stop_speed_threshold: float = 0.05      # m/s
    resume_speed_threshold: float = 0.10    # m/s — hysteresis
    near_miss_clearance_threshold: float = 0.30  # m
```

- Một config cho **mọi** stack — một lần dừng của DWA phải được đếm y
  hệt cho PPO. Đây là fairness ở tầng đo, cùng tinh thần P02.
- Config được **snapshot vào `EpisodeMetrics.metric_config`** của từng
  run. Đổi ngưỡng sau này tạo version mới; số cũ vẫn tự khai nó được
  tính dưới ngưỡng nào. Cùng lý do khiến P02 snapshot observation class
  thay vì tra registry lúc đọc.
- Validator chặn hysteresis ngược (`resume < stop` → ValueError).

### 2.3. Stop-and-go có hysteresis, không phải một ngưỡng

Plan gợi ý một ngưỡng nhưng test bắt buộc lại ghi "không đếm rung quanh
ngưỡng nhiều lần nếu chưa có hysteresis" — hai yêu cầu này chỉ thỏa
đồng thời khi có hysteresis thật. Nên máy trạng thái là:

```text
chưa từng chạy (ever_moved=False)
    → vượt resume_threshold lần đầu: bắt đầu theo dõi, KHÔNG đếm
đang chạy → tụt dưới stop_threshold (0.05): sang trạng thái dừng
đang dừng → vượt resume_threshold (0.10): +1 stop-and-go
```

Tốc độ lởn vởn trong dải (0.05, 0.10) không đổi trạng thái theo cả hai
chiều. Trạng thái đứng yên ban đầu không bao giờ được đếm (guard
`ever_moved` đúng theo plan).

### 2.4. Near-miss không đếm trùng va chạm

`near_miss_count` = số trajectory point có `0 < clearance < 0.30 m`.
Điểm xuyên vật cản (clearance ≤ 0) là va chạm, đã có field `collision`
riêng — đếm nó thêm lần nữa là biến một sự kiện thành hai. Đếm theo
**frame** chứ không theo sự kiện: cà sát tường 40 frame ra 40, phải đọc
là "số frame dưới ngưỡng an toàn" (KNOWN_LIMITATIONS #149).

### 2.5. Time-to-first-collision đọc từ event, không suy từ status

Lấy `min(time)` của các event `type == "collision"`; `None` khi không
có. Hôm nay engine kết thúc episode ngay va chạm đầu nên giá trị luôn
trùng `elapsed_time` — field tồn tại để giữ đúng nghĩa khi có chế độ
multi-collision sau này (KNOWN_LIMITATIONS #150).

### 2.6. Percentile latency

`local_planning_latency_p50/p95/p99` bằng `np.percentile` (nội suy
tuyến tính), `None` khi không có latency — không bao giờ là 0 giả.
Mean/max cũ giữ nguyên.

### 2.7. Peak memory: chủ ý không làm

Đúng plan: phụ thuộc máy, có overhead, phá tính tái lập nếu không ghi
môi trường đo. Không field nào được thêm. `replan_count` cũng không —
thuộc plan Replanning (Đợt 4, chưa approve). KNOWN_LIMITATIONS #151.

## 3. File thay đổi

| File | Thay đổi |
|---|---|
| `packages/metrics/planbench_metrics/episode_metrics.py` | `MetricConfig` + 8 field mới + 3 hàm tính; docstring contract viết lại |
| `packages/metrics/planbench_metrics/__init__.py` | export `MetricConfig`, `DEFAULT_METRIC_CONFIG`, `METRIC_CONFIG_VERSION` |
| `apps/api/planbench_api/report_markdown.py` | bảng Runs thêm cột Near misses + Stop-and-go; đoạn `_metric_thresholds` ghi ngưỡng và version vào report (report cũ không có config in dòng "not computed") |
| `apps/web/src/lib/types.ts` | `EpisodeMetrics` thêm field mới dạng `?: number \| null` + interface `MetricConfig` |
| `tests/test_metrics.py` | +23 test mới (31 tổng) |
| `docs/API_CONTRACT.md`, `docs/KNOWN_LIMITATIONS.md` (#146–#151), `docs/IMPLEMENTATION_STATUS.md` | cập nhật contract + giới hạn |

Không file nào bị xóa field. `nav_stack.py` / `episode_runner.py` /
`runner.py` **không cần sửa** — tham số mới có default, config mặc định
tự áp.

## 4. Điều KHÔNG làm trong đợt này (chủ ý)

**`AlgorithmAggregate`, leaderboard và biểu đồ chưa tổng hợp metric
mới.** Metric mới dừng ở cấp episode (`runs[].metrics` + bảng Runs của
report Markdown). Lý do: đưa lên aggregate đụng contract leaderboard,
overall score và `lib/charts.ts` — đổi trọng số xếp hạng là quyết định
phải review riêng, không nhét vào đợt sửa công thức đo. Overall score
vẫn dùng `mean_smoothness_successful` cũ (đã deprecated). Ghi ở
KNOWN_LIMITATIONS #146.

## 5. Test

23 test mới trong `tests/test_metrics.py`, đúng danh sách plan:

- **Smoothness:** tính tay `(π/2)² + (π/4)²`; đường thẳng = 0; field cũ
  vẫn ra đúng giá trị cũ trên cùng input; wraparound 350°→10° tính là
  20° chứ không phải 340°.
- **Percentile:** tính tay trên [1..10] (p50=5.5, p95=9.55, p99=9.91);
  một giá trị; rỗng trả `None` không phải 0.
- **Stop-and-go:** đứng yên ban đầu không đếm; chưa từng chạy = 0; một
  chu kỳ dừng-chạy = 1; hai chu kỳ = 2; rung trong dải hysteresis = 0;
  hồi phục nửa vời dưới resume threshold vẫn chỉ 1; ngưỡng lấy từ
  config (cùng input, config khác ra số khác); config ngược bị reject.
- **Near-miss:** đếm đúng điểm dưới ngưỡng; điểm xuyên vật cản không
  đếm (không nhầm với collision); `None` khi không có grid.
- **TTFC:** trả đúng thời điểm event collision đầu; `None` khi không có.
- **Snapshot:** config mặc định và config tùy chỉnh đều được ghi lại.
- **Backward compatibility:** payload metrics lưu trước F05 (không có
  field mới) deserialize sạch, toàn bộ field mới = `None`.

## 6. Kiểm chứng

### 6.1. Test suite

```text
tests/test_metrics.py                              31 passed
tests/test_benchmark_engine.py + tests/api/test_api_benchmarks.py
  + tests/api/test_api_report_export.py            71 passed
tests/api/test_api_report_export.py (chạy lại sau ruff format)
                                                   20 passed
ruff format + ruff check                           sạch
```

Full suite `pytest tests/ -q`: đang chạy nền lúc viết báo cáo — kết quả
chốt ghi ở mục 6.4.

### 6.2. Frontend

```text
npm run typecheck    sạch
npm run build        production build pass
npm test             435 passed / 1 failed + 1 suite fail — CẢ HAI PRE-EXISTING
```

Hai failure **không liên quan 3.2** (không file nào trong diff chạm
tới chúng, và chúng fail từ trước đợt này):

1. `assistant-page.test.tsx` — đọc `src/app/models/page.tsx`, file này
   **không tồn tại trên nhánh** (`git ls-files` rỗng). Artifact của
   merge `integrate-tongduyan`: test đến từ nhánh có Model Registry
   page, file thì không.
2. `dashboard-page.test.tsx` — so sánh path cứng `"/system/page.tsx"`
   với path Windows trả về `"\system\page.tsx"`. Bug separator của
   test, chỉ lộ trên Windows.

Cả hai cần fix ở việc riêng (một thuộc về merge, một là test-bug
platform), không thuộc phạm vi metrics.

### 6.3. End-to-end trên benchmark thật

Chạy `run_benchmark` thật (`astar+dwa`) trên 3 scenario:

```text
open_space         success | sq=0.0    | old=0.0    | p99=0.00606 | stopgo=0 | nearmiss=0 | ttfc=None
doorway            success | sq=0.0003 | old=0.0122 | p99=0.00654 | stopgo=0 | nearmiss=0 | ttfc=None
crossing_obstacle  success | sq=0.0    | old=0.0    | p99=0.00744 | stopgo=0 | nearmiss=0 | ttfc=None
narrow_corridor    stuck   | metric mới vẫn tính được trên episode thất bại
```

Đối chiếu hợp lý: nơi field cũ = 0 (đi thẳng) thì `smoothness_squared`
cũng 0; doorway có rẽ nhẹ → sq nhỏ hơn rate nhiều bậc (bình phương của
góc nhỏ) — đúng toán. Serialization JSON của report chứa đủ 6 nhóm
field mới + `metric_config`.

### 6.4. Full suite

```text
python -m pytest tests/ -q
1388 passed, 4 skipped, 1 warning in 531.89s (0:08:51)
```

Baseline lúc lập plan là `1085 passed, 4 skipped`; sau Đợt 0–3.2 là
1388 — không fail mới, 4 skip vẫn là 4 skip cũ (torch optional). Lưu ý
quy trình: lần chạy này khởi động trước khi `ruff format` chạm 3 file;
format chỉ đổi whitespace, và các suite liên quan
(`test_metrics.py`, `test_api_report_export.py`) đã được chạy lại sau
format, đều xanh.

## 7. Definition of Done của plan 3.2 — đối chiếu

- [x] Có `smoothness_squared`.
- [x] Field smoothness cũ vẫn tồn tại, không đổi công thức.
- [x] Có latency p50, p95, p99.
- [x] Có stop-and-go count đúng (ever_moved + hysteresis + ngưỡng trong config versioned).
- [x] Có near-miss count (không đếm trùng collision; ngưỡng ghi trong report Markdown).
- [x] Có time-to-first-collision (`None` khi không va chạm).
- [x] Không dùng peak memory trong overall score (không đo).
- [x] Benchmark cũ vẫn đọc được (test backward compatibility).

## 8. Rủi ro còn lại

| Rủi ro | Ghi chú |
|---|---|
| Metric mới chưa lên aggregate/leaderboard | Chủ ý, KNOWN_LIMITATIONS #146; cần plan riêng khi đổi overall score |
| Ngưỡng mặc định 0.05/0.10/0.30 chưa được hiệu chuẩn thực nghiệm | Chọn theo lẽ thường (robot radius ~0.3 m, v_max ~1 m/s); đổi = bump `MetricConfig` version, số cũ không đổi nghĩa |
| Near-miss đếm frame, phụ thuộc `simulation_dt` | So sánh giữa stack cùng benchmark vẫn công bằng (cùng dt trong FairnessRecord) |
| 2 frontend test fail pre-existing | Thuộc việc riêng: merge artifact `models/page.tsx` + path separator Windows |

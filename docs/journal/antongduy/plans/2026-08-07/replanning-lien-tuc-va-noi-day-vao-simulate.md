# Plan — Replanning liên tục, nối dây vào `/simulate`, và lỗ hổng P02 do replanning tạo ra

> **Lập ngày:** 2026-08-07.
> **Trạng thái:** CHỜ APPROVE, chưa triển khai.
> **Nhánh:** `integrate-tongduyan`.
> **HEAD lúc lập plan:** `462d2cd TongDuyAn: Sua loi map` + diff chưa commit của Đợt 4.1.
> **Test baseline lúc lập plan:** `1412 passed, 5 skipped`
> (`971 passed, 4 skipped` cho `tests/` trừ `tests/api`; `441 passed, 1 skipped` cho `tests/api`).
>
> **Tiền đề:** Đợt 4.1 (replanning) đã code xong và test xong — xem
> `docs/antongduy/reports/2026-08-07/tongduyan_dot-4-1-replanning.md`.
> Plan này xử lý **phần còn thiếu và phần làm sai** của 4.1, không lặp lại 4.1.
>
> **Plan gốc của roadmap:** `docs/antongduy/plans/2026-08-05/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`.
> Plan này **không** thay thế nó; 4.2 (map loader ROS) vẫn nằm ở đó, chưa làm.

---

# 0. Đọc cái này trước — trạng thái thật sau Đợt 4.1

Nếu bạn vào phiên mới và không có ngữ cảnh, đây là bốn sự thật cần nắm
trước khi đụng vào code.

### 0.1. Replanning đã chạy thật, không phải schema suông

Bằng chứng chạy được, cùng map / cùng scenario / cùng seed:

```text
off  stuck    t=13.9  replans=0  moved only 0.049 m in the last 5.0s
on   success  t=32.7  replans=1  goal reached (distance 0.390 m)
```

Code thực thi nằm ở `services/simulator/planbench_simulator/nav_stack.py`
dòng **249–267** (vòng replan) và **123–160** (`_replan()` +
`_with_free_start_cell()`). `ReplanningConfig`
(`packages/schemas/planbench_schemas/replanning.py`) chỉ là **công tắc**,
không phải phần thân.

### 0.2. Nhưng mở app lên thì không thấy gì — vì `/simulate` chưa được nối dây

Chỉ có **một** chỗ gọi `run_stack()` cho live simulation:

| Nơi gọi | Có truyền replanning? |
|---|---|
| `packages/benchmark/planbench_benchmark/runner.py:68` | **Có** — `spec.replanning` |
| `apps/api/planbench_api/services.py:214` (`SimulationService.run`) | **KHÔNG** |

`StoredSimulation` (`apps/api/planbench_api/repositories.py:55-63`) không
có trường replanning; `SimulationCreateRequest`
(`apps/api/planbench_api/schemas.py:113-117`) cũng không. Nên trang
`/simulate` — đúng cái trang người ta ngồi xem robot bị kẹt — **không bao
giờ replan được**. WebSocket (`routers/ws.py:30`) chỉ phát lại trajectory
đã ghi, nên sửa đúng một chỗ `services.py:214` là đủ cho cả luồng live.

Ngoài ra **không có nút bật ở UI** cho cả benchmark lẫn simulate — hiện
chỉ bật được bằng cách gọi API tay với body JSON có `replanning`.

Báo cáo 4.1 mục 8 có ghi giới hạn này (KNOWN_LIMITATIONS #156) nhưng ghi
thiếu: chỉ nói "form benchmark chưa có ô chọn", **không nói `/simulate`
chưa được nối dây chút nào**. Nửa sau mới là nửa quan trọng.

### 0.3. Replanning hiện tại KHÔNG phải replanning liên tục

Đây là câu hỏi user đặt ra và câu trả lời là: **đúng, nó không liên
tục.** Cơ chế hiện tại là **replan hồi phục sau khi episode đã bị kết
luận thất bại**, không phải replan chủ động khi thấy vật cản.

Luồng thật hôm nay:

```text
t=0     global planner lập đường MỘT LẦN, trên grid CHỈ CÓ VẬT CẢN TĨNH
        (nav_stack.plan_global_path → _planning_grid, extra_obstacles rỗng)
          ↓
        robot chạy; DWA né vật cản động bằng LiDAR ở tầng local
          ↓
        gặp vật cản chắn hẳn đường → DWA không tìm được lệnh tiến
          ↓
        robot đứng yên... 5 giây (scenario.stuck_time_window = 5.0)
          ↓
        ENGINE KẾT LUẬN STUCK → episode FINISHED, is_done() = True
          ↓
        stack thấy is_done() + status STUCK → mới bắt đầu replan
          ↓
        engine.resume_after_replan() hồi sinh episode
```

Ba hệ quả cần nói thẳng:

1. **Global planner không bao giờ "nhìn thấy" vật cản động trong lúc
   chạy bình thường.** Nó chỉ thấy chúng đúng tại khoảnh khắc replan.
2. **Trigger không phải "phát hiện đường bị chặn" mà là "phát hiện robot
   không nhúc nhích".** Engine đo triệu chứng (`displacement <
   stuck_min_displacement` = 0.05 m trong `stuck_time_window` = 5.0 s),
   không đo nguyên nhân.
3. **Mỗi lần bị chặn tốn trọn 5 giây đứng chờ**, và 5 giây đó nằm trong
   `travel_time` của run. Trong ví dụ trên: 13.9 s là lúc bị kết luận
   stuck, 32.7 s là lúc tới đích — gần một nửa thời gian chờ + đi vòng.

Nav2 thật làm khác: `planner_server` replan theo chu kỳ (thường 1 Hz)
trong suốt hành trình, và cây hành vi có nhánh recovery riêng. Cái MVP
đang có tương ứng với **nhánh recovery**, chưa có **vòng replan chu kỳ**.

### 0.4. Replanning đang làm hỏng khai báo P02 — lỗi của tôi, chưa được ghi ở đâu

Đây là phần nghiêm trọng nhất của plan này và nó **không** nằm trong
KNOWN_LIMITATIONS hiện tại.

`_replan()` (`nav_stack.py:141-160`) lấy vị trí vật cản động qua
`engine.dynamic_obstacles_now()` — **ground truth, chính xác tuyệt đối**.
Trong khi đó registry vẫn khai báo mọi stack là:

```python
global_observation_class="full_static_map"   # registry.py, cả 5 stack
```

Khi replanning bật, câu khai báo đó **sai**. Global planner lúc ấy nhận
đúng thứ mà lớp `human_states` mô tả: vị trí thật của vật cản động,
không nhiễu, không che khuất, không cần cảm biến.

Vì sao đây là vấn đề chứ không phải chi tiết: **P02 là differentiator
của cả dự án.** Mục 0.3 của đề bài (`phan-tich-de-bai-benchmark-planning.md`,
lỗ hổng S1) chỉ trích Alyassi et al. đúng vì chuyện này — cho baseline
đặc quyền đọc vị trí người thật rồi xếp chung bảng với planner chỉ có
LiDAR. Nếu ta bật replanning với ground truth mà vẫn dán nhãn
`full_static_map`, ta **lặp lại đúng lỗi ta đang phê phán**, và tệ hơn vì
ta có sẵn cơ chế khai báo mà không dùng.

Trong lúc replanning còn **tắt mặc định**, chưa có report nào bị dán nhãn
sai. Nhưng phải sửa **trước khi** ai đó bật nó và công bố số.

---

# 1. Phạm vi plan này

| Đợt | Nội dung | Ước lượng | Vì sao ưu tiên thế |
| --- | --- | ---: | --- |
| **A** | Sửa khai báo P02 khi replanning bật | ~1 ngày | Sai về phương pháp luận, chặn mọi việc công bố số có replanning |
| **B** | Nối dây `/simulate` + nút bật ở UI | ~1,5–2 ngày | Tính năng đang vô hình với người dùng |
| **C** | Replanning theo chu kỳ (câu hỏi của user) | ~3–4 ngày | Đúng hành vi Nav2, nhưng là thay đổi ngữ nghĩa lớn |
| **D** | Hiệu chuẩn lại difficulty với replanning | ~0,5 ngày + thời gian chạy | Chỉ làm sau khi A–C chốt |

**Thứ tự bắt buộc: A trước B trước C.** Lý do: B làm tính năng dễ tiếp
cận hơn, nên nếu A chưa xong thì B chính là thứ giúp người ta tạo ra số
bị dán nhãn sai nhanh hơn. C xây trên quyết định của A.

**Ngoài phạm vi plan này:** Đợt 4.2 (map loader ROS `map_server`), Đợt
5A–5D, RBAC, và mọi thay đổi về `AlgorithmAggregate`/leaderboard/overall
score.

---

# Đợt A — Sửa khai báo cân bằng thông tin khi replanning bật

## A.1. Vấn đề chính xác

Một stack chạy với `replanning.enabled = True` nhìn thấy nhiều hơn cùng
stack đó chạy với replanning tắt. Khai báo trong registry là **tĩnh**
(gắn với stack id), nên nó không diễn tả được sự khác biệt này.

## A.2. Ba lựa chọn, kèm đánh giá

### Lựa chọn 1 — Nâng lớp quan sát theo điều kiện chạy (khuyến nghị)

Lớp quan sát của global planner được **suy ra lúc chạy**, không phải đọc
cứng từ registry:

```text
replanning tắt  → global_observation_class = <giá trị registry>   (full_static_map)
replanning bật  → global_observation_class = "full_static_map+human_states"
```

Cần thêm một giá trị vào `ObservationClass`
(`packages/benchmark/planbench_benchmark/observation.py`). Kiểm tra danh
sách hiện có trước khi thêm; plan 08-05 mục 1.1 định nghĩa
`full_static_map | lidar_only | human_states | lidar+human_states`.

- **Ưu:** trung thực tuyệt đối, rẻ, dùng đúng cơ chế đã có; leaderboard
  tự động **không** xếp chung run có replan với run không replan (nó
  nhóm theo observation class — xem `apps/api/planbench_api/leaderboard.py`).
- **Nhược:** một stack id sinh ra hai lớp quan sát tuỳ điều kiện. Phải
  kiểm tra `AlgorithmAggregate` snapshot đúng giá trị **lúc chạy** chứ
  không tra registry lúc đọc (cơ chế snapshot đã có sẵn từ P02, chỉ cần
  đổi nguồn giá trị).

### Lựa chọn 2 — Replan trên vật cản ước lượng từ LiDAR, không dùng ground truth

Giữ nhãn `full_static_map` bằng cách **không** đưa ground truth vào:
dựng lớp vật cản từ chính LiDAR scan của robot, rasterize cái đó.

- **Ưu:** đúng cách Nav2 làm (costmap layer từ sensor); không phải đụng
  vào lớp quan sát; kết quả đáng tin hơn về mặt khoa học.
- **Nhược:** đắt hơn nhiều — cần một costmap tích luỹ theo thời gian
  (LiDAR chỉ thấy phần vật cản không bị che), cần quyết định vật cản cũ
  bao lâu thì quên. Đây thực chất là làm một `local_costmap` của Nav2.
  Ước lượng riêng ~3 ngày, và nó nên là plan riêng.
- **Rủi ro thật:** LiDAR thấy vật cản chắn đường thì thấy *một cung*,
  không thấy toàn bộ hình tròn. Rasterize cung đó có thể không chặn hẳn
  ô cửa, planner lại trả về đúng đường cũ, và ta quay lại đúng bug đã gặp
  ở 4.1 (mục 2.3 của report).

### Lựa chọn 3 — Cấm replanning cho tới khi có costmap từ sensor

Trung thực nhưng vứt bỏ công việc đã chạy được. Không khuyến nghị.

## A.3. Khuyến nghị

**Làm Lựa chọn 1 ngay** (rẻ, đúng, không chặn ai), và **ghi Lựa chọn 2
vào roadmap như một plan riêng** — vì về lâu dài nó mới là câu trả lời
đúng, và nó chính là thứ biến "replanning" thành "Nav2-like costmap
replanning" thật sự.

## A.4. Việc cần làm

1. `observation.py`: thêm giá trị lớp quan sát cho trường hợp global
   planner đọc được vị trí vật cản động. Kiểm tra tên đã có để không đẻ
   ra hai tên cho một khái niệm.
2. `runner.py::aggregate_algorithm()`: `global_observation_class` lấy từ
   **điều kiện chạy** (registry + replanning config), không phải chỉ từ
   `algorithm_info()`. Chữ ký hàm phải nhận thêm replanning config.
3. `report_markdown.py`: bảng Algorithms phải hiện đúng lớp đã nâng, và
   nên có một dòng giải thích ngắn vì sao nó khác registry.
4. `leaderboard.py`: xác nhận (bằng test) rằng run có replan và run không
   replan **không** rơi vào cùng một nhóm xếp hạng mặc định.
5. KNOWN_LIMITATIONS: thêm mục mô tả chính xác chuyện này; sửa #152–#157
   nếu số bị lệch.

## A.5. Test bắt buộc

- Replanning tắt → `global_observation_class` giữ nguyên `full_static_map`
  (không được đổi nhãn của bất kỳ report cũ nào).
- Replanning bật → lớp quan sát được nâng.
- Report cũ (không có field replanning trong fairness) đọc ra `full_static_map`,
  không raise, không đoán.
- Leaderboard: hai aggregate khác lớp quan sát không cùng nhóm mặc định;
  ép xem chung thì `cross_observation_class_warning = True`.
- Snapshot: đổi registry sau khi chạy không đổi nhãn của số đã lưu.

## A.6. Definition of Done

- [ ] Lớp quan sát phản ánh đúng điều kiện chạy, không phải chỉ stack id.
- [ ] Report cũ không đổi nhãn.
- [ ] Leaderboard không trộn chung.
- [ ] Report Markdown nói rõ vì sao lớp bị nâng.
- [ ] Có mục KNOWN_LIMITATIONS cho ground truth ở tầng replan.
- [ ] Không đụng `conditions_checksum` (lớp quan sát không phải điều kiện mô phỏng).

---

# Đợt B — Nối dây `/simulate` và thêm nút bật ở UI

## B.1. Backend — `/simulate`

Đây là **một lát cắt dọc mỏng**, không phải một dòng:

| File | Thay đổi |
|---|---|
| `apps/api/planbench_api/repositories.py:55` | `StoredSimulation` thêm `replanning: ReplanningConfig` (default `NO_REPLANNING`) |
| `apps/api/planbench_api/repository_ports.py` | chữ ký `simulations.create()` |
| `apps/api/planbench_api/db/repositories.py` | bản SQL tương ứng — **kiểm tra có cần migration Alembic không** |
| `apps/api/planbench_api/schemas.py:113` | `SimulationCreateRequest.replanning` |
| `apps/api/planbench_api/services.py:214` | truyền xuống `run_stack(...)` |

Ràng buộc: **default phải là tắt**, và simulation cũ trong DB (không có
cột/field) phải đọc ra tắt, không được raise.

## B.2. Frontend

- `/simulate`: một checkbox "Replanning" + ô số `max_replans`. Khi bật,
  hiển thị cảnh báo ngắn: robot phải đứng chờ hết cửa sổ stuck trước khi
  được cấp đường mới, nên thời gian chạy sẽ dài hơn (đây là hành vi thật,
  không phải lag của UI — nếu không nói, người xem sẽ tưởng app treo).
- Trang benchmark detail / form tạo benchmark: ô tương ứng, ghi rõ đây là
  **luật chung cho cả benchmark**, không phải tham số của một thuật toán.
- Replay: đánh dấu thời điểm replan trên timeline. Event `replan` đã có
  sẵn trong `result.events` từ 4.1, và `ReplayViewer` đã biết vẽ marker
  cho collision (xem report F08 mục 2.2) — dùng lại đúng cơ chế đó.
- i18n: thêm key ở cả `en.json` và `vi.json`.

## B.3. Test bắt buộc

- Backend: tạo simulation có replanning → `run` thật sự replan
  (`metrics.replan_count >= 1`) trên scenario bị chặn.
- Backend: simulation cũ (payload không có field) chạy được, `replan_count = 0`.
- Backend: `enabled=true, max_replans=0` bị API từ chối với thông báo đọc được.
- Frontend: form gửi đúng payload; replay hiện marker replan.
- Frontend: mặc định tắt (không có ai vô tình bật).

## B.4. Definition of Done

- [ ] Bật replanning từ UI `/simulate` và thấy robot đi đường vòng.
- [ ] Bật từ form benchmark.
- [ ] Simulation/benchmark cũ vẫn đọc và chạy được.
- [ ] Marker replan hiện trên timeline replay.
- [ ] `npm run typecheck` + `npm run build` sạch.

---

# Đợt C — Replanning theo chu kỳ (trả lời trực tiếp câu hỏi của user)

## C.1. Mục tiêu

Chuyển từ **replan hồi phục** (chỉ chạy sau khi engine đã kết luận thất
bại) sang **replan theo chu kỳ** (chạy đều đặn trong suốt hành trình,
giống `planner_server` của Nav2), sao cho robot đổi đường **trước khi**
bị kẹt chứ không phải sau khi đã đứng chờ 5 giây.

## C.2. Thiết kế đề xuất

Thêm vào `ReplanningConfig`:

```python
replan_period: float | None = None   # giây; None = chỉ replan hồi phục (hành vi 4.1)
```

Vòng lặp trong `run_stack()` nhận thêm một nhánh, **trước** nhánh hồi
phục hiện có:

```text
mỗi bước:
    nếu replan_period != None và engine.time >= next_replan_time:
        replan trên grid có vật cản động hiện tại
        nếu đường mới hợp lệ VÀ khác đáng kể đường đang đi:
            local_planner.reset(đường mới)   ← KHÔNG gọi resume_after_replan
        next_replan_time += replan_period
    ... phần điều khiển như cũ ...
    ... nhánh hồi phục STUCK/NO_PROGRESS như 4.1 giữ nguyên ...
```

Khác biệt then chốt so với 4.1: replan chu kỳ xảy ra khi episode **đang
chạy**, nên **không** gọi `resume_after_replan()` và **không** đụng cửa
sổ stuck. `resume_after_replan()` chỉ dành cho nhánh hồi phục.

## C.3. Sáu câu hỏi phải trả lời trước khi code

Không câu nào có đáp án hiển nhiên. Đây là phần cần thảo luận với user,
không phải phần tự quyết.

1. **`replan_period` có được tune không?** Nếu có, nó phải vào
   `SEARCH_SPACES` của P01 (Đợt 5A) với cùng ngân sách cho mọi planner —
   nếu không, cho một stack chu kỳ 0.5 s và stack kia 2 s là bất công
   bằng đúng kiểu S2 mà đề bài phê phán. **Khuyến nghị MVP: cố định,
   không tune, ghi rõ trong report.**
2. **Đường mới "khác đáng kể" nghĩa là gì?** Nếu nhận mọi đường mới,
   DWA bị reset liên tục (`_path_index = 0`, `_previous = None` — xem
   `dwa/planner.py:119-125`) và có thể dao động mãi mãi. Cần một ngưỡng,
   và ngưỡng đó lại là một tham số nữa → lại là câu hỏi 1.
3. **`replan_count` còn nghĩa gì?** Với chu kỳ 1 s trên episode 60 s,
   con số sẽ là ~60 và không nói lên điều gì. Có lẽ cần tách
   `replan_count` (số lần *đổi đường*) khỏi `replan_attempts` (số lần
   *gọi planner*). Phải quyết trước khi ghi số vào report.
4. **`global_planning_time` cộng dồn có còn công bằng không?** Replan
   chu kỳ khiến tổng thời gian lập đường tăng tuyến tính theo độ dài
   episode. So A\* với RRT\* dưới chế độ này là so chi phí lập đường
   nhân với thời gian sống — có thể đúng ý, có thể không. Phải nói rõ
   trong định nghĩa metric.
5. **Chi phí chạy benchmark tăng bao nhiêu?** Mỗi replan là một lần chạy
   A\*/RRT\* đầy đủ. 30 seed × N scenario × chu kỳ 1 Hz là một bậc độ
   lớn nhiều hơn hiện tại. **Phải đo trước bằng một scenario rồi mới
   quyết chu kỳ mặc định.**
6. **Lớp quan sát:** replan chu kỳ với ground truth nghĩa là global
   planner **liên tục** đọc vị trí thật của vật cản động — nặng hơn hẳn
   trường hợp 4.1 (chỉ đọc vài lần). Quyết định của Đợt A áp dụng ở đây
   với mức độ nghiêm trọng cao hơn nhiều. Đây là lý do A phải làm trước C.

## C.4. Test bắt buộc

- Chu kỳ tắt (`replan_period = None`) → hành vi **giống hệt** 4.1, kể cả
  trajectory.
- Chu kỳ bật trên scenario bị chặn → robot đổi đường **trước** khi engine
  kết luận STUCK (khẳng định bằng: không có event `stuck` nào, và
  `travel_time` nhỏ hơn đáng kể so với chế độ hồi phục).
- Chu kỳ bật trên scenario trống → không đổi đường vô cớ, không dao động,
  kết quả vẫn SUCCESS với thời gian tương đương.
- Cùng seed hai lần → cùng kết quả (replan chu kỳ không được phá tính
  tái lập; chú ý RRT\* — mỗi lần replan phải lấy seed xác định, không lấy
  từ đồng hồ).
- `conditions_checksum` đổi khi `replan_period` đổi.
- DWA bị reset nhiều lần giữa episode vẫn không rò state.

## C.5. Definition of Done

- [ ] Sáu câu hỏi ở C.3 đã có đáp án được user chốt.
- [ ] Chu kỳ tắt = hành vi 4.1, byte-identical.
- [ ] Có test chứng minh robot tránh được STUCK, không chỉ hồi phục sau STUCK.
- [ ] Tái lập theo seed còn nguyên.
- [ ] Chi phí chạy đã được đo và ghi vào report.
- [ ] Định nghĩa `replan_count` / `global_planning_time` dưới chế độ chu kỳ được ghi rõ.

---

# Đợt D — Hiệu chuẩn lại độ khó với replanning

Chỉ làm **sau khi** A–C chốt, vì mỗi thay đổi ở trên đều đổi thang đo.

- `scripts/calibrate_difficulty.py --max-replans N --calibration-version <mới>`
  đã hoạt động (làm ở 4.1) và đã **bắt buộc** version riêng.
- Chạy thật 30 seed, so bảng difficulty với thang không-replanning.
- Kỳ vọng: scenario có vật cản động dễ đi hẳn; scenario tĩnh gần như
  không đổi. Nếu scenario tĩnh cũng đổi nhiều → có bug, dừng lại điều
  tra, **không** sửa tay cache.
- Không ghi đè `difficulty_calibration.json` cũ.

---

# 2. Rủi ro của bản plan này

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Ai đó bật replanning và công bố số trước khi Đợt A xong | **Cao** | Làm A trước B; hiện tại mặc định tắt và không có UI, nên cửa sổ rủi ro đang hẹp |
| Đợt C biến `replan_period` thành tham số bất công bằng | Cao | Cố định ở MVP, không tune; nếu tune thì bắt buộc qua P01 |
| Đợt C làm chi phí benchmark tăng một bậc độ lớn | Trung bình-cao | Đo trước trên 1 scenario rồi mới chốt chu kỳ mặc định |
| Replan chu kỳ làm DWA dao động | Trung bình | Ngưỡng "đường mới khác đáng kể"; test scenario trống |
| Đợt B đụng migration DB | Trung bình | Kiểm tra `db/repositories.py` trước khi ước lượng lại |
| Ground truth ở tầng replan là gian lận về phương pháp luận | **Cao** | Đợt A nhãn đúng; Lựa chọn 2 (costmap từ LiDAR) là lời giải thật, lập plan riêng |
| Sửa `aggregate_algorithm()` chữ ký làm vỡ caller | Trung bình | Tham số mới có default; chạy full suite |

---

# 3. Điểm cần quyết định khi approve

1. Chọn Lựa chọn 1 hay Lựa chọn 2 cho Đợt A (khuyến nghị: 1 ngay, 2 thành plan riêng).
2. Tên chính xác của lớp quan sát mới.
3. Có làm Đợt C trong đợt nộp này không, hay chốt MVP ở replan hồi phục.
4. Nếu làm C: `replan_period` mặc định là bao nhiêu, và có tune không.
5. `replan_count` dưới chế độ chu kỳ: một số hay tách hai số.
6. Đợt B có cần migration DB không (phải kiểm `db/repositories.py` trước).
7. Có nới `stuck_time_window` cho chế độ hồi phục không — 5 giây chờ là
   rất lâu, nhưng đổi nó là đổi `conditions_checksum` của mọi scenario.
   **Cảnh báo: đây là field của `Scenario`, đổi mặc định sẽ làm stale
   toàn bộ cache difficulty.** Nhiều khả năng câu trả lời là "không đổi,
   làm Đợt C thay thế".

---

# 4. Quyết định đề xuất

**Approve Đợt A và Đợt B ngay.** A vì nó sửa một sai sót về phương pháp
luận đúng ở chỗ dự án tuyên bố là điểm mạnh nhất của mình; B vì tính năng
hiện không ai chạm tới được.

**Đợt C tách riêng, approve sau khi trả lời xong sáu câu hỏi ở C.3** —
đặc biệt câu về ngân sách tune và câu về chi phí chạy. Không code C
trước khi chốt, vì đổi ngữ nghĩa `replan_count` và `global_planning_time`
sau khi đã có report là việc phải sửa ngược ở nhiều nơi.

**Đợt D chỉ sau A–C.**

# Test Report — Agentic AI PlanBench

Output thật từ các lần chạy kiểm thử. Cập nhật sau mỗi milestone.

## M5 — 2026-07-30

```
$ .venv/bin/ruff check .
All checks passed!
$ PYTHONPATH= .venv/bin/pytest tests/ -q
530 passed, 1 warning in 120.98s
```

Test mới: `test_dynamic_obstacles.py` (26), `test_scenario_library.py` (53),
`test_failure_analysis.py` (15), `tests/api/test_api_m5.py` (13).

### Kết quả DWA trên scenario library (output thật)

```
open_space           success      t= 10.40s clear=0.950
wide_corridor        success      t= 13.40s clear=0.450
narrow_corridor      stuck        t=  9.90s clear=0.450
doorway              success      t=  9.50s clear=0.486
```

`narrow_corridor` (1.5 m) là **kết quả benchmark hợp lệ**, không phải bug:
A* tìm được đường (test khẳng định), nhưng DWA với cấu hình mặc định không
qua được hành lang chỉ rộng gấp 2.5 lần đường kính robot. Đây chính là loại
phát hiện mà benchmark tồn tại để tạo ra.

### Lỗi đã gặp và sửa trong M5

1. **DWA đỗ cách goal 0.56 m** (phát hiện khi chạy `wide_corridor`): cost
   thiếu số hạng "tiến tới goal". Khi robot đã thẳng hàng và bám path,
   `heading` = `path` = 0, nên clearance một mình quyết định và v=0 rẻ hơn
   mọi lựa chọn tiến lên gần tường. Sửa: thêm cost `goal` (weight 2.0) +
   giới hạn vận tốc theo quãng đường phanh `sqrt(2·a·d)` + giảm
   `clearance_cap` 1.0 → 0.6 m. Bằng chứng: 12.44 m → tới goal 13.0 m.
2. **`doorway` không có đường đi**: khe 1.0 m nhỏ hơn 2×inflation
   (0.65 m). Mở rộng thành 1.6 m và ghi rõ lý do trong docstring.
3. **Test LiDAR sai kỳ vọng**: giả định quét thấy bề mặt hình tròn chính
   xác, thực tế thấy cell đã rasterize (1 m). Sửa test so sánh có/không có
   obstacle và khẳng định đúng biên cell.
4. **`ObstacleSnapshot` khai báo sau `TrajectoryPoint`** → forward
   reference không resolve; sắp xếp lại thứ tự class.

## M4 — 2026-07-30

### Lint + tests

```
$ .venv/bin/ruff check .
All checks passed!
$ PYTHONPATH= .venv/bin/pytest tests/ -q
423 passed, 1 warning in 93.44s
$ cd apps/web && npm run typecheck   # clean
$ npm run test
 Test Files  3 passed (3) | Tests 18 passed (18)
$ npm run build
 ✓ Compiled successfully | ✓ Generating static pages (8/8)
   /benchmarks 2.66 kB · /benchmarks/[id] 5.41 kB · /login 1.98 kB
```

### MLflow tracking (output thật, file store)

```
tracker: mlflow | experiment: planbench-verify | last run: 5c22c90d54a3
experiment: planbench-verify | runs: 2
  run dwa-vs-reference:astar+pure_pursuit
    tags: algorithm=astar+pure_pursuit conditions=7c7ec7bc0ea6 benchmark_id=bench-demo-1
    params: seeds=[1, 2, 3] map=mlflow-demo timeout=90.0 radius=0.3
    metrics: success_rate=1.0 episodes=3.0 travel=14.40 clearance=1.200
    per-seed travel times: [(1, 14.4), (2, 14.4), (3, 14.4)]
  run dwa-vs-reference:astar+dwa
    tags: algorithm=astar+dwa conditions=7c7ec7bc0ea6 benchmark_id=bench-demo-1
    metrics: success_rate=1.0 episodes=3.0 travel=15.70 clearance=1.200
    per-seed travel times: [(1, 15.7), (2, 15.7), (3, 15.7)]
```

Cả hai stack có cùng `conditions_checksum` → so sánh hợp lệ.

### Human-in-the-loop end-to-end qua HTTP thật

```
login: alice=operator  carol=reviewer
map: ac34a0d2f07e | scenario: e1740e091c79
create -> 201 state=draft
run before approval -> 409 invalid_state: cannot run a benchmark in state 'draft'
operator self-approve -> 403 forbidden
reviewer approve -> 200 state=approved
run -> 200 state=pending_review

fairness checksum: 344ab16e33d2d923f97f  seeds=[1, 2]
stack                   succ  coll   travel   clear  lat_ms
astar+dwa               1.00  0.00   17.45s   0.491    6.23
astar+pure_pursuit      1.00  0.00   15.85s   0.603    0.00

episodes stored: 4 (artifact f2e7f3a1e749.json, 58727 bytes, sha256 a06fa0951f0e)
replay: astar+dwa seed=1 points=350 plan_waypoints=4

accept-result -> 200 state=accepted
audit trail: submit(operator) -> approve(reviewer) -> run(operator) -> complete(operator) -> accept_result(reviewer)
```

Ghi chú đọc số liệu: pure-pursuit nhanh hơn DWA ở map trống này vì nó bám
thẳng đường A* và bỏ qua cảm biến; **không** được kết luận nó "tốt hơn" —
nó là adapter tham chiếu (`benchmarkable=false`), không dùng LiDAR nên
không an toàn với vật cản chưa biết.

### Lỗi đã gặp và sửa trong M4

1. **DWA không bao giờ tăng tốc**: cost `smoothness` chuẩn hóa theo cửa sổ
   gia tốc nên phạt 0.15 cho một lần tăng tốc đầy, trong khi lợi ích
   `velocity` chỉ 0.06 → luôn chọn v nhỏ nhất. Sửa: chuẩn hóa smoothness
   theo giới hạn vận tốc robot (cùng thang với velocity). Bằng chứng
   trước/sau: v giữ ở 0.014 m/s → đạt 1.00 m/s.
2. **DWA quá chậm** (53 s cho 8 test): rollout thuần Python
   135 ứng viên × 15 bước × ~72 điểm LiDAR. Sửa: vectorize bằng numpy +
   giữ lệnh giữa các chu kỳ điều khiển → 12 s.
3. **Test sai giả định** (không phải lỗi code): DWA xoay tại chỗ trong hốc
   0.5 m là hợp lệ; clearance bão hòa khi tường cách 1.5 m > cap 1.0 m.
   Sửa test cho đúng vật lý, thêm test hốc hẹp hơn robot để kiểm tra
   fallback dừng.
4. **Failure-to-progress báo nhầm khi đi vòng**: đo bằng khoảng cách Euclid
   nên đường vòng dài hợp lệ bị coi là thất bại. Nới mặc định 15 s → 30 s,
   ghi rõ giới hạn trong KNOWN_LIMITATIONS, scenario đi vòng phải tự nới.
5. **passlib 1.7.4 không tương thích bcrypt 5.x** → bỏ passlib, dùng
   `bcrypt` trực tiếp (có cắt 72 byte tường minh).
6. **MLflow 3 từ chối file store** → tracker tự bật `MLFLOW_ALLOW_FILE_STORE`
   cho URI `file:`; production dùng MLflow server qua http.
7. **Chạy benchmark 2 lần** (bản nháp đầu lưu episode bằng vòng lặp riêng)
   → callback `on_run(record, stack_run)` trả về cả episode, chạy một lần.

## M3 — 2026-07-30

### Frontend

```
$ npm run typecheck    # tsc --noEmit
(no output = clean)

$ npm run test
 ✓ src/lib/__tests__/playback.test.ts (8 tests)
 ✓ src/lib/__tests__/transform.test.ts (6 tests)
 ✓ src/lib/__tests__/demoMap.test.ts (4 tests)
 Test Files  3 passed (3)
      Tests  18 passed (18)

$ npm run build
 ✓ Compiled successfully
 ✓ Generating static pages (6/6)
Route (app)                     Size  First Load JS
┌ ○ /                        1.75 kB         108 kB
├ ○ /_not-found                993 B         103 kB
├ ○ /maps                    2.02 kB         108 kB
├ ƒ /maps/[id]               3.68 kB         110 kB
└ ○ /simulate                6.05 kB         112 kB
```

### Backend (sau khi thêm WS pace mode)

```
$ PYTHONPATH= .venv/bin/pytest tests/ -q
324 passed, 1 warning in 2.43s
$ .venv/bin/ruff check .
All checks passed!
```

### Smoke test hệ thống thật (backend + frontend cùng chạy)

```
$ curl -s http://127.0.0.1:8000/api/v1/health
{"status":"ok","app":"PlanBench API","version":"0.1.0"}

# Luồng E2E qua REST:
map: 37fc92179f0d checksum 70727ee9ac
scenario: 8a0c608c6996
episode: success steps 272
metrics: length 12.56 m, efficiency 1.037, min_clearance 0.250 m
benchmark: 3 runs, success_rate 1.00, mean_travel_time 13.60 s

# WebSocket (episode 177 frame):
pace=false -> waypoints=2 states= 177 final=result/success
pace=true  -> waypoints=2 states=   2 final=result/success   (speed=1000, rate cap)

# Frontend production server:
GET /         -> 200
GET /maps     -> 200
GET /simulate -> 200   (chứa "Run simulation", "Playback timeline", "Global path")
```

Lỗi đã gặp và sửa trong M3:
1. WS chỉ giao 4/177 frame khi client pace cục bộ (rate cap server bỏ
   frame) → thêm tham số `pace=false`; UI dùng chế độ này; thêm test
   `test_unpaced_stream_delivers_every_frame` và
   `test_paced_stream_skips_frames_at_high_speed`.
2. `next start` lần hai lỗi EADDRINUSE do server cũ còn chạy → kill pid
   cũ rồi khởi động lại, xác nhận build mới được phục vụ.

## M2 — 2026-07-30

```
$ .venv/bin/ruff check .
All checks passed!
$ PYTHONPATH= .venv/bin/pytest tests/ -q
322 passed, 1 warning in 1.40s
```

Warning duy nhất: websockets deprecation từ uvicorn (thư viện ngoài).

Smoke test server thật:

```
$ curl -s http://127.0.0.1:8123/api/v1/health
{"status":"ok","app":"PlanBench API","version":"0.1.0"}
openapi paths: 16
```

Lỗi đã gặp và sửa trong M2:
1. Handler 422 crash 500 vì `RequestValidationError.errors()` chứa
   object ValueError không serialize được → dùng jsonable_encoder với
   custom_encoder {Exception: str}.
2. WS test speed=1000 bị rate-cap 60 Hz bỏ gần hết frame → test dùng
   speed=50 (~14 frame, chạy 0.23s).

## M1B — 2026-07-30

### Ruff

```
$ .venv/bin/ruff format .   # 39 files left unchanged (sau khi format)
$ .venv/bin/ruff check .
All checks passed!
```

### Pytest

```
$ PYTHONPATH= .venv/bin/pytest tests/ -q
296 passed in 0.31s
```

Coverage (chạy với --cov, branch coverage bật):

```
TOTAL  893 stmts, 27 miss, 218 branch, 11 partial — 95%
```

Các phần miss chính: `grid.rasterize_obstacles` nhánh lỗi hiếm (78%
file grid do rasterize mới thêm test gián tiếp), vài nhánh phòng thủ
trong engine. Không bỏ file nào khỏi báo cáo.

### Demo headless (output thật)

```
$ PYTHONPATH= .venv/bin/python scripts/demo_astar_episode.py
map: demo-warehouse (48x36 @ 0.25 m)
scenario: demo-astar-pure-pursuit
plan: success=True waypoints=6 length=13.26 m expanded=288 time=4.8 ms
episode: status=success reason='goal reached (distance 0.288 m) after 14.40s'
  steps=288 sim_time=14.40 s
metrics:
  trajectory_length = 12.82 m
  path_efficiency   = 1.0341715682303163
  average_speed     = 0.89 m/s
  max_speed         = 1.00 m/s
  smoothness        = 0.452 rad/m
  min_clearance     = 0.073 m
  mean_clearance    = 0.508 m
artifact: artifacts/demo/astar_episode.json
```

Ghi chú: path_efficiency > 1 vì đường thực tế cắt cua ngắn hơn polyline
kế hoạch (đã ghi trong docstring metric).

## M1A — 2026-07-30

- Ruff: sạch. Pytest: 220 passed. Coverage 99% (chi tiết trong lịch sử
  phiên làm việc; bị thay thế bởi số liệu M1B ở trên).

## Lỗi môi trường đã biết

- Shell source ROS2 Jazzy → PYTHONPATH chứa /opt/ros/... làm pytest nạp
  plugin `launch_testing` và crash import yaml. Fix: chạy test với
  `PYTHONPATH=` hoặc `env -u PYTHONPATH`.

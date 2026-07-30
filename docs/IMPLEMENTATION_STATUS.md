# Implementation Status — Agentic AI PlanBench

> Nguồn sự thật về tiến độ. Cập nhật sau mỗi milestone để tiếp tục được
> công việc khi session đóng hoặc context bị rút gọn.

## Milestone hiện tại

**M5 hoàn thành** (trừ PostgreSQL/Alembic và frontend cho M5 — xem
"Nợ kỹ thuật"). Tiếp theo: **M6 — PPO reinforcement learning**.

## Bản đồ mã nguồn

| Đường dẫn | Vai trò |
|---|---|
| `packages/schemas/planbench_schemas/` | Pydantic domain models (geometry, robot, map, sensor, scenario, episode) |
| `packages/planning/planbench_planning/` | `common/` (GlobalPlanner, LocalPlanner, PlanResult, path_utils), `astar/`, `dwa/` |
| `packages/metrics/planbench_metrics/` | `episode_metrics.py` — công thức metric ghi trong docstring |
| `packages/benchmark/planbench_benchmark/` | `registry.py` (stack registry), `spec.py` (BenchmarkSpec/FairnessRecord/aggregate), `runner.py` |
| `services/simulator/planbench_simulator/` | grid, kinematics, collision, lidar, engine, path_follower, `nav_stack.py`, `episode_runner.py` |
| `services/tracking/planbench_tracking/` | ExperimentTracker interface + MLflow adapter + NullTracker |
| `apps/api/planbench_api/` | FastAPI: config, errors, logging, auth, approval, artifacts, repositories, services, routers/ |
| `apps/web/` | Next.js 15 + React 19 + TS: lib/, components/, app/ |
| `tests/` | pytest (core + `tests/api/`) |
| `scripts/demo_astar_episode.py` | demo headless |

## Đã hoàn thành

### M0 — Kiến trúc (docs/architecture.md, decision log D01–D16)
### M1A — schemas, OccupancyGrid, kinematics, collision
### M1B — LiDAR (DDA), A*, pure-pursuit (adapter tạm), SimulationEngine, metrics, demo
### M2 — FastAPI MVP: maps/scenarios/simulations, WebSocket, in-memory repo
### M3 — Next.js MVP: Canvas 2D, map editor, live simulation, metric panel

### M4 — DWA + benchmark + human-in-the-loop + MLflow

- **DWA** (`packages/planning/planbench_planning/dwa/planner.py`): dynamic
  window từ giới hạn vận tốc/gia tốc, sample lưới cố định (deterministic),
  rollout **vectorized bằng numpy**, loại ứng viên va chạm dựa trên point
  cloud từ LiDAR (không dùng ground-truth map), cost 6 thành phần
  (heading/path/clearance/velocity/smoothness/oscillation) trọng số cấu
  hình được, fallback dừng an toàn kèm `failure_reason`.
- **LocalPlanner interface** + `control_period`: `nav_stack` giữ lệnh giữa
  các chu kỳ điều khiển (controller 10 Hz, sim 20 Hz — như /cmd_vel thật).
- **nav_stack**: `run_stack()` chạy A* + local planner bất kỳ;
  `PurePursuitLocalPlanner` chỉ là adapter tham chiếu.
- **Benchmark engine** (`packages/benchmark/`): `BenchmarkSpec` (chặn
  trùng algorithm/seed), `FairnessRecord` (hash map + scenario + seeds →
  `conditions_checksum` làm bằng chứng công bằng), runner chạy mọi cặp
  (algorithm × seed) với controller mới mỗi run, aggregate phân biệt rõ
  rate (mọi episode) vs mean (chỉ episode thành công).
- **Approval workflow** (`apps/api/planbench_api/approval.py`): 11 state,
  9 action, phân quyền theo role, **separation of duties** (người tạo
  không tự duyệt; admin miễn trừ, có ghi chú).
- **Auth**: JWT (PyJWT) + bcrypt; secret từ `PLANBENCH_JWT_SECRET` (thiếu
  → sinh ngẫu nhiên mỗi process); user từ `PLANBENCH_SEED_USERS` (thiếu →
  sinh mật khẩu ngẫu nhiên, log một lần). Không có secret trong source.
- **Artifact storage** (D15): `ArtifactStore` interface + FileSystem/
  InMemory; episode và report lưu JSON canonical + SHA-256 + size; DB chỉ
  giữ metadata + URI.
- **MLflow tracking** (`services/tracking/`): một MLflow run cho mỗi
  (benchmark, algorithm); log params (fairness identity + config), metric
  aggregate, và metric từng seed qua `step=seed`; tag
  `conditions_checksum`. Thiếu URI hoặc backend lỗi → NullTracker.
- **API mới**: `/auth/login`, `/auth/me`, `/algorithms[/{id}]`,
  `/benchmarks` (create/submit/approve/reject/cancel/run/accept-result/
  reject-result/results), `/benchmarks/{id}/episodes`,
  `/episodes/{id}[/result|/plan|/replay]`.
- **Frontend mới**: `/login`, `/benchmarks` (tạo + danh sách),
  `/benchmarks/[id]` (nút approval theo role, bảng audit, fairness
  evidence, bảng so sánh, danh sách episode + replay trên Canvas).

### M5 — Dynamic obstacle + scenario library + failure analysis + leaderboard

- **Dynamic obstacle** (`packages/schemas/planbench_schemas/dynamic.py`):
  4 kiểu chuyển động — `waypoint` (loop/ping-pong), `periodic` (sin),
  `random_walk` (hash splitmix64 từ seed, phản xạ khi vượt max_radius),
  `sudden_stop`. Vị trí là **hàm thuần của (spec, time, seed)** — không
  trạng thái ẩn, không RNG toàn cục → replay khớp tuyệt đối.
- **Engine**: collision phân biệt static/dynamic (ghi vào reason), LiDAR
  rasterize obstacle động theo từng observation, `TrajectoryPoint` ghi
  `ObstacleSnapshot` (ground truth cho replay/phân tích — planner **không**
  thấy, chỉ thấy qua LiDAR), validate start/goal ở t=0.
- **Scenario library** (`packages/benchmark/.../scenarios.py`): 10 scenario
  theo thứ tự curriculum: open_space, static_obstacles, wide_corridor,
  narrow_corridor, doorway, crossing_obstacle, sudden_stop,
  bidirectional_corridor, intersection, dynamic_warehouse. Mọi scenario
  dùng chung robot + LiDAR + dt → so sánh chéo có nghĩa.
- **Failure analysis** (`packages/benchmark/.../failure.py`): phân loại
  primary + contributing findings, mỗi finding kèm `Evidence` trích từ dữ
  liệu đã ghi; confidence high/medium/low có định nghĩa rõ. Phân biệt
  collision tĩnh/động (dùng ObstacleSnapshot), timeout gần/xa goal, phát
  hiện oscillation, low clearance, local planner failure.
- **Background worker** (`apps/api/planbench_api/worker.py`): thread pool
  có `PLANBENCH_WORKER_CONCURRENCY` (mặc định 2), job có progress/state,
  cancel hợp tác (dừng giữa các episode, không giết giữa chừng).
- **Leaderboard** (`apps/api/planbench_api/leaderboard.py`): chỉ xếp hạng
  benchmark đã ACCEPTED (mặc định), **nhóm theo `conditions_checksum`** để
  không bao giờ trộn kết quả không so sánh được; overall score là tổng có
  trọng số minh bạch, công thức trả kèm response.
- **API mới**: `GET /scenario-library`, `POST /scenario-library/{name}/import`,
  `GET /leaderboard` (lọc + trọng số qua query), `POST /benchmarks/{id}/run-async`,
  `GET /benchmarks/{id}/job`, `POST /benchmarks/{id}/job/cancel`,
  `GET /episodes/{id}/failures`.
- **DWA cải tiến** (phát hiện qua scenario library): thêm cost `goal`
  (khoảng cách cuối rollout tới local goal) và giới hạn vận tốc theo
  quãng đường phanh. Trước đó robot đỗ cách goal 0.56 m vì khi đã thẳng
  hàng thì `heading` và `path` đều = 0, chỉ còn clearance quyết định.
  `clearance_cap` giảm 1.0 → 0.6 m để không phạt khoảng trống an toàn.

## Nợ kỹ thuật (cập nhật sau M5)

- **Frontend cho M5**: scenario library, leaderboard, failure analysis và
  job progress mới có API, chưa có trang UI → gộp vào M9.
- **PostgreSQL + SQLAlchemy + Alembic**: chưa làm. Repository hiện in-memory
  nhưng interface đã tách sạch (`repositories.py`) và artifact đã nằm ngoài
  DB, nên thay thế là việc cục bộ → M10.
- **Parallel benchmark**: worker đã có concurrency limit nhưng mỗi benchmark
  vẫn chạy tuần tự bên trong (nhiều benchmark chạy song song được, các
  episode trong một benchmark thì chưa).
- **Resource monitoring** (CPU/memory per job): chưa có.
- `pause/resume` benchmark: state PAUSED có trong enum nhưng chưa có
  transition; hiện chỉ có cancel hợp tác.
- **RRT***: chưa triển khai (spec ghi rõ không bắt buộc cho MVP).

## Kiểm thử

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
PYTHONPATH= .venv/bin/pytest tests/ -q
PYTHONPATH= .venv/bin/python scripts/demo_astar_episode.py
cd apps/web && npm run test && npm run typecheck && npm run build
```

Chạy hệ thống:

```bash
PLANBENCH_SEED_USERS="alice:operator:alicepw,carol:reviewer:carolpw" \
PLANBENCH_JWT_SECRET="<secret thật khi production>" \
PLANBENCH_MLFLOW_TRACKING_URI="file://$PWD/mlruns" \
PYTHONPATH="packages/schemas:packages/planning:packages/metrics:packages/benchmark:services/simulator:services/tracking:apps/api" \
  .venv/bin/uvicorn planbench_api.main:app --port 8000

cd apps/web && NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev
```

## Ràng buộc bắt buộc (từ người dùng)

- Không commit/push/staging Git; làm trên branch `main`.
- Không sudo, không cài global. Python: `.venv`; frontend: node_modules.
- Benchmark so sánh **stack**: A*+DWA vs A*+PPO vs Nav2. Không so A* với DWA.
- LLM không điều khiển /cmd_vel; không Gazebo.
- Không bịa output test/benchmark.
- Chỉ dừng hỏi khi: cần secret thật, dịch vụ tính phí, thao tác xóa dữ
  liệu, lựa chọn kiến trúc lớn ngoài đặc tả, lỗi môi trường ngoài repo,
  cần sudo.

## Bước tiếp theo (M6 — PPO)

1. `ml/environments/`: Gymnasium env bọc `SimulationEngine`; observation
   (LiDAR chuẩn hóa + goal distance/bearing + vận tốc + waypoint phía
   trước), action liên tục (v, ω) có clamp + kiểm tra NaN/inf.
2. `ml/rewards/`: reward có version (goal/collision/progress/stuck/
   oscillation/smoothness/clearance/path-tracking).
3. `ml/training/`: script PPO (Stable-Baselines3) + checkpoint + MLflow;
   smoke training timestep nhỏ trên CPU, ghi rõ **không phải model
   production**.
4. `ml/evaluation/`: deterministic evaluation, model registry metadata.
5. `PPOLocalPlanner` đăng ký thành stack `astar+ppo` (benchmarkable) để
   so sánh A*+DWA vs A*+PPO.
6. Curriculum theo `CURRICULUM_ORDER` của scenario library.

# Implementation Status — Agentic AI PlanBench

> Nguồn sự thật về tiến độ. Cập nhật sau mỗi milestone để tiếp tục được
> công việc khi session đóng hoặc context bị rút gọn.

## Milestone hiện tại

**M13 hoàn thành** — Model Registry (upload PPO qua web thay cho
`model_path`), Robot Profile, kiểm tra tương thích, và trợ lý hội thoại
thay cho ba biểu mẫu kỹ thuật. **Toàn bộ M0–M13 đã xong.**

Còn nợ (xem "Nợ kỹ thuật" và KNOWN_LIMITATIONS #77–#89): chưa gọi
provider LLM thật, **và việc nạp model upload chưa chạy trong sandbox
container** — hạn chế bảo mật quan trọng nhất của M13, ghi rõ ở
KNOWN_LIMITATIONS #77.

**Docker + PostgreSQL: đã chạy thật (2026-08-05, Đợt 0.2).** Cả 4
service `db`/`migrate`/`api`/`web` lên healthy, migration chạy trên
`postgres:17-alpine` tạo đủ 10 bảng, và một benchmark 2 stack × 5 seed
chạy end-to-end **trong container** với dữ liệu ghi xuống PostgreSQL —
số liệu trùng khít lần chạy trên host. Hai lỗi chặn được phát hiện và
sửa trong lúc kiểm chứng (`model_dir` tương đối gây `PermissionError`
lúc import; vai trò legacy `engineer`/`approver` làm mọi endpoint danh
sách trả 500). Báo cáo:
`docs/antongduy/reports/2026-08-05/tongduyan_docker-compose-chay-that.md`.

## Bản đồ mã nguồn

| Đường dẫn | Vai trò |
|---|---|
| `packages/schemas/planbench_schemas/` | Pydantic domain models (geometry, robot, map, sensor, scenario, episode) |
| `packages/planning/planbench_planning/` | `common/` (GlobalPlanner, LocalPlanner, PlanResult, path_utils), `astar/`, `dwa/` |
| `packages/metrics/planbench_metrics/` | `episode_metrics.py` — công thức metric ghi trong docstring |
| `packages/benchmark/planbench_benchmark/` | `registry.py` (stack registry), `spec.py` (BenchmarkSpec/FairnessRecord/aggregate), `runner.py` |
| `services/simulator/planbench_simulator/` | grid, kinematics, collision, lidar, engine, path_follower, `nav_stack.py`, `episode_runner.py` |
| `services/tracking/planbench_tracking/` | ExperimentTracker interface + MLflow adapter + NullTracker |
| `apps/api/planbench_api/` | FastAPI: config, errors, logging, auth, approval, artifacts, repositories, repository_ports, services, routers/, `db/` (SQLAlchemy) |
| `apps/api/planbench_api/model_registry.py` | Model là bản ghi có chủ sở hữu, checksum và schema quan sát — không phải đường dẫn file |
| `apps/api/planbench_api/model_storage.py` | `ModelStorage` (interface cho S3/R2) + backend cục bộ + soi zip **không giải tuần tự** |
| `apps/api/planbench_api/registry_service.py` | Upload, tương thích, tài liệu đính kèm, sidecar cho loader |
| `apps/api/planbench_api/chat_service.py` | Hội thoại: đề xuất → người bấm → **bản nháp**. Không có đường chạy. |
| `alembic/` | Migration schema — `docs/DEPLOYMENT.md` |
| `docker/`, `docker-compose.yml` | Image API/web + stack local (db, migrate, api, web) |
| `services/agent_service/planbench_agent/` | Agentic AI: provider abstraction, specs, gateway, tools, evidence, rag, report, workflow |
| `apps/web/` | Next.js 15 + React 19 + TS: lib/, components/, app/ — xem `docs/FRONTEND.md` |
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

### M6 — PPO reinforcement learning

- **`ml/planbench_rl/`** (tách khỏi core: simulator không bao giờ phụ
  thuộc framework RL):
  - `observation.py` — encoding có version (`v1`), 35 chiều: LiDAR
    down-sample **lấy min từng bin** (lấy mean sẽ che mất tia đơn lẻ phát
    hiện vật mỏng), goal distance/bearing, vận tốc, 3 waypoint phía trước
    **trong hệ toạ độ robot** (để policy generalize sang map khác), sai số
    cross-track. Policy **không** thấy pose ground-truth của obstacle —
    chỉ thấy qua LiDAR, đúng như robot thật.
  - `rewards.py` — reward có version (`v1`): terminal (goal +200,
    collision −200, timeout/stuck/no-progress −50) áp đảo shaping;
    shaping theo *progress* (mét rút ngắn tới goal) + phạt time,
    path-tracking, clearance thấp (scale theo mức thiếu hụt),
    oscillation, control effort, đi lùi.
  - `env.py` — `PlanBenchNavEnv` (Gymnasium): action `Box[-1,1]²` chuẩn
    hoá theo giới hạn robot; **kiểm tra NaN/inf → dừng an toàn và đếm**
    (`info["invalid_actions"]`), không bao giờ nuốt lỗi; `reset(seed=)`
    quyết định seed scenario nên episode replay khớp tuyệt đối.
  - `policy.py` — `PPOLocalPlanner` implement `LocalPlanner` (stack
    `astar+ppo`); `ModelMetadata` sidecar ghi observation/reward version,
    seed, curriculum, cờ `is_smoke_test`; **load kiểm tra version khớp**
    (`VersionMismatch`) vì policy train trên encoding khác sẽ nhận rác mà
    vẫn trông bình thường. Thiếu sidecar là lỗi, không phải mặc định.
  - `training.py` — curriculum theo `CURRICULUM_ORDER` (mỗi stage train
    trên tất cả scenario dễ hơn để không quên), PPO/SB3 trên CPU,
    checkpoint + metadata + MLflow (params, hyperparameter, reward
    version); `evaluate()` deterministic.
- **`scripts/train_ppo.py`** — CLI có `--smoke` cho CPU.
- **Đăng ký `astar+ppo`** trong benchmark registry với `PPOStackConfig`
  (bắt buộc `model_path` — benchmark phải nói rõ model nào tạo ra số).
- **Sửa lỗi seed thật**: seed trước đây **không đổi gì** với scenario chỉ
  có motion tất định (periodic/waypoint/sudden_stop) → 5 seed cho ra 5
  episode y hệt, variance giả bằng 0. Thêm `seed_time_offset`: lệch đồng
  hồ obstacle theo hash(seed, name). Kiểm chứng: pedestrian ở
  y=2.274/2.209/2.004/5.362/4.580 cho seed 1..5.

## Nợ kỹ thuật (cập nhật sau M6)

- **Frontend cho M5/M6**: scenario library, leaderboard, failure analysis,
  job progress và model registry mới có API/CLI, chưa có trang UI → M9.
- **Chưa có model PPO thật**: mới chỉ chạy smoke 4096 timestep để kiểm
  chứng pipeline (success_rate 0.00 — đúng như kỳ vọng cho model chưa
  train). Cần chạy dài (hàng triệu timestep) mới có số liệu PPO có nghĩa.
- **Chưa có API model registry**: upload/liệt kê checkpoint qua HTTP.
- **PostgreSQL + SQLAlchemy + Alembic**: chưa làm. Repository hiện in-memory
  nhưng interface đã tách sạch (`repositories.py`) và artifact đã nằm ngoài
  DB, nên thay thế là việc cục bộ → M10.
- **Parallel benchmark**: worker đã có concurrency limit nhưng mỗi benchmark
  vẫn chạy tuần tự bên trong (nhiều benchmark chạy song song được, các
  episode trong một benchmark thì chưa).
- **Resource monitoring** (CPU/memory per job): chưa có.
- `pause/resume` benchmark: state PAUSED có trong enum nhưng chưa có
  transition; hiện chỉ có cancel hợp tác.
- ~~**RRT***: chưa triển khai~~ — đã xong (Đợt 0.1, 2026-08-05):
  `packages/planning/planbench_planning/rrtstar/`, stack `rrtstar+dwa`
  benchmarkable, tái lập theo seed.
- **Metric F05 cấp aggregate**: Đợt 3.2 (2026-08-07) thêm
  `smoothness_squared` (đúng spec 8.2 `Σ(Δθ)²`), latency p50/p95/p99,
  `stop_and_go_count` (hysteresis, `MetricConfig` v1.0.0),
  `near_miss_count`, `time_to_first_collision` vào `EpisodeMetrics` +
  bảng Runs của report Markdown (kèm ngưỡng). `AlgorithmAggregate`,
  leaderboard và biểu đồ **chưa** tổng hợp các metric mới — xem
  KNOWN_LIMITATIONS #146–#151.
- **Replanning khi bị vật cản động chặn**: Đợt 4.1 (2026-08-07) — xong.
  `ReplanningConfig` (`packages/schemas/.../replanning.py`) nằm trên
  `BenchmarkSpec`, **không** nằm trên `Scenario` (thêm field vào
  `Scenario` sẽ đổi `scenario_checksum` của mọi scenario cũ) và **không**
  nằm trong config của thuật toán nào. Logic cắm ở
  `nav_stack.run_stack()` — nơi mọi stack đều đi qua. Engine có thêm
  `resume_after_replan()` (reseed cửa sổ stuck, không chỉ đổi state) và
  `dynamic_obstacles_now()`; khi replan, vị trí vật cản động hiện tại
  được rasterize vào grid quy hoạch tạm, nếu không thì planner trả lại
  đúng đường cũ. Mặc định **tắt**: run tắt cho trajectory và checksum
  giống hệt trước khi có tính năng. Giới hạn: KNOWN_LIMITATIONS
  #152–#157.
- **Khai báo cân bằng thông tin khi replanning bật (P02)**: Đợt A
  (2026-08-08) — xong. Lớp quan sát của global planner được **suy ra lúc
  chạy** thay vì chép nguyên từ registry:
  `global_class_under_replanning()`
  (`packages/benchmark/planbench_benchmark/observation.py`) nâng
  `full_static_map` thành `full_static_map+human_states` khi
  `replanning.enabled`, vì `_replan()` đọc ground truth qua
  `engine.dynamic_obstacles_now()`. `aggregate_algorithm()` nhận thêm
  tham số `replanning` và **chụp** giá trị đã nâng vào
  `AlgorithmAggregate`, nên sửa registry sau này không dán nhãn khác lên
  số đã đo. Khóa nhóm của leaderboard giờ gồm cả hai lớp (global +
  local), nên run có replan không bao giờ bị xếp chung run không replan;
  report Markdown in kèm đoạn giải thích vì sao nhãn khác registry.
  Replanning tắt → nhãn **không đổi một bit**, mọi report cũ giữ nguyên.
  Giới hạn còn lại: KNOWN_LIMITATIONS #158–#159.

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

### M7 — ROS2/Nav2 closed-loop (hoàn thành)

5 package trong `ros2_ws/src/`: `planbench_msgs`, `planbench_ros_bridge`,
`planbench_simulator_node`, `planbench_nav2_bringup`,
`planbench_benchmark_runner`. Không Gazebo, không AMCL (simulator có
ground truth nên `map→odom` là identity).

Chi tiết kiến trúc, cách chạy và các quyết định: **docs/ROS2_INTEGRATION.md**.
Output kiểm chứng thật: docs/TEST_REPORT.md mục M7.

## Bước tiếp theo (M8 — Agentic AI + RAG)

1. `services/agent_service/`: LLM provider abstraction + mock provider
   deterministic (chưa có API key thật → không chặn cả dự án).
2. Natural-language → `BenchmarkSpec` với structured output + validate
   Pydantic; từ chối thực thi nếu sai schema.
3. Tool calling trên các API đã có (list/create map, scenario, benchmark,
   approve, run, get metrics, replay, failure analysis).
4. Approval gate: agent **không** được chạy benchmark chưa duyệt.
5. RAG trên tài liệu + log + kết quả benchmark, trả về source ID; từ chối
   trả lời khi không đủ evidence.
6. Report generation chỉ trích dẫn benchmark_id/episode_id/metric có thật.

## (Đã xong) M7 — kế hoạch gốc

1. `ros2_ws/src/planbench_msgs`: message/service (ResetSimulator, LoadMap,
   LoadScenario, StartEpisode, EpisodeStatus, BenchmarkEvent).
2. `planbench_simulator` node: publish `/map`, `/scan`, `/odom`, `/tf`,
   `/tf_static`, `/clock`; subscribe `/cmd_vel`. Bọc `SimulationEngine`,
   không viết lại vật lý.
3. `planbench_nav2_bringup`: params + lifecycle bringup (không Gazebo).
4. `planbench_benchmark_runner`: gửi NavigateToPose, thu kết quả, xử lý
   TF timeout / lifecycle chưa active / action server unavailable /
   goal rejected / controller-planner failure.
5. Chạy closed-loop thật và ghi output vào TEST_REPORT.

Lưu ý môi trường: shell đã source ROS2 Jazzy nên phải chạy pytest với
`PYTHONPATH=`; ngược lại khi build colcon thì cần môi trường ROS đầy đủ
(không dùng `.venv` cho node ROS).

## (Đã xong) M6 — PPO

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

### M8 — Agentic AI + RAG

Chi tiết đầy đủ: `docs/AGENT_AI.md`.

1. **Provider abstraction** (`provider.py`): `LLMProvider` ABC, message/
   tool/response types. Không có tên vendor nào trong domain code.
   `anthropic_provider.py` là module **duy nhất** biết đến một vendor —
   import SDK lazy nên `pip install anthropic` là tùy chọn.
2. **Mock tất định** (`deterministic.py`): responder rule-based, chạy
   được toàn bộ M8 khi không có API key. Nó khớp từ khóa chứ không hiểu
   ngôn ngữ; giá trị của nó là làm cho mọi lớp bảo vệ xung quanh được
   chạy thật. Mọi response mang cờ `deterministic` để không ai nhầm.
3. **Mission → spec** (`specs.py`): structured output → `MissionDraft`
   (`extra="forbid"`) → `validate_draft()` đối chiếu registry thật.
   Trượt bất kỳ lớp nào là refusal, không tạo gì cả.
4. **Gateway protocol** (`gateway.py`): đúng bằng những gì agent được
   phép làm. Không có method nào cho `/cmd_vel`, sửa map, hay approve —
   sự vắng mặt chính là cơ chế cưỡng chế.
5. **Tool calling** (`tools.py`): registry phân loại `READ`/`WRITE`,
   `ToolPolicy` chặn tool ghi trong phiên read-only, trần episode,
   `FORBIDDEN_CAPABILITIES` ghi tường minh những gì bị cấm.
6. **Cổng approval hai lớp**: tool `run_benchmark` kiểm tra state
   `approved` trước, gateway kiểm tra lần hai. Xóa một lớp vẫn còn lớp
   kia. Không có tool nào approve được.
7. **Evidence + citation** (`evidence.py`, `report.py`): citation
   `[kind:locator]`; id không có trong bundle → `FabricatedCitation`,
   hủy toàn bộ báo cáo. Báo cáo chưa được reviewer accept mang nhãn
   PROVISIONAL + safety disclaimer.
8. **RAG** (`rag.py`): chunk theo heading Markdown, TF-IDF, tất định,
   offline. Chunk id `<file>#<section>` để trích dẫn được.
9. **API**: 6 endpoint dưới `/api/v1/agent/`, chạy dưới danh nghĩa user
   đang gọi nên separation of duties vẫn áp dụng.

Ràng buộc phát hiện khi làm M8: **`astar+ppo` không nằm trong menu của
agent** vì cần `model_path`. Agent không biết checkpoint nào đúng, và
bịa đường dẫn là đúng kiểu bịa mà spec cấm — nên mọi stack có config
bắt buộc đều bị loại khỏi `agent_selectable_algorithms()`.

### M9 — 2.5D + UI cho M5/M6/M8

Chi tiết đầy đủ: `docs/FRONTEND.md`.

1. **2.5D** tách làm hai: `src/lib/scene25d.ts` là hình học thuần (phép
   chiếu trực giao, thứ tự vẽ, đùn tường, marker robot) — 23 unit test;
   `src/components/Scene25D.tsx` chỉ chọn màu và nét vẽ. Renderer là
   Canvas 2D: cảnh là vài nghìn quad lồi có thứ tự độ sâu toàn phần nên
   painter's algorithm xử lý chính xác, không thêm dependency. Đổi sang
   WebGL sau này chỉ thay đúng file renderer.
2. **`/library`** — 10 scenario theo thứ tự curriculum, import tạo map +
   scenario server-side (client không bao giờ tự dựng geometry, nếu
   không hai máy import cùng entry sẽ ra map khác nhau).
3. **`/leaderboard`** — nhóm theo `conditions_checksum`, chỉnh trọng số
   tại chỗ, cảnh báo đỏ khi xem kết quả chưa được accept.
4. **`/algorithms`** — registry stack: `benchmarkable=false` (reference
   adapter) và config bắt buộc (`astar+ppo` cần `model_path`) đều hiển
   thị rõ.
5. **`/agent`** — console M8: bảng provider readiness, chat có tool,
   mission → draft/refusal, evidence bundle, report có trích dẫn.
6. **`/benchmarks/[id]`** thêm: toggle top-down ↔ 2.5D cho replay, panel
   **failure analysis** (finding + evidence + confidence), panel **job
   progress** (poll khi chạy, cancel hợp tác).

Toàn bộ 41 vitest pass, `tsc --noEmit` sạch, `next build` ra 12 route.
Đã chạy thật backend + frontend và kiểm chứng end-to-end (xem
TEST_REPORT).

### M13 — Model Registry + trợ lý hội thoại

**Vấn đề đã giải quyết.** Chạy `astar+ppo` trước đây nghĩa là gõ một
đường dẫn filesystem vào cấu hình benchmark. Điều đó bắt người dùng biết
file nằm ở đâu trên server, không kiểm tra được gì trước khi chạy, và
bản ghi "model nào đã sinh ra con số này" chỉ là một chuỗi có thể trỏ
sang chỗ khác vào ngày mai.

**Model Registry.** Một bản ghi mang theo checksum (nên câu hỏi "model
nào?" có câu trả lời không trôi được), mang theo hình dạng quan sát và
hành động (nên sai lệch bị bắt *trước* khi chạy chứ không thành số rác
*trong* khi chạy), và mang theo chủ sở hữu (nên chia sẻ là một quyết
định chứ không phải tai nạn của filesystem).

Ba loại file, phân biệt có ý nghĩa: `.zip` của Stable-Baselines3 là thứ
duy nhất chạy được như một policy; `.json` là metadata *về* nó; `.pdf`
là văn xuôi cho người đọc. **Upload PDF không cho bạn một model chạy
được**, và mã nguồn từ chối giả vờ ngược lại.

**Robot Profile.** Tham số robot là dữ liệu chứ không phải hằng số trong
adapter PPO. Một model huấn luyện cho robot bán kính 0.3 m không nói gì
về robot 0.8 m, và trước M13 sự khác biệt đó không ở đâu ghi lại.

**Tương thích** trả về `compatible` / `warning` / `incompatible` kèm câu
tiếng người. Cùng một hàm thuần trả lời cả "tôi chọn được model này
không?" lẫn "model này chạy được không?" — nên câu trả lời không thể
lệch giữa lúc chọn và lúc chạy.

**Trợ lý.** Thay ba biểu mẫu ("Hỏi về kết quả", "Biến yêu cầu thành
benchmark", "Bằng chứng và báo cáo"), bảng trạng thái provider, danh
sách tool nội bộ, danh sách hành động bị cấm, và hướng dẫn `pip install`
— tất cả đều đúng, và không thứ nào thuộc về trước mặt người muốn thử
một con robot. Phần chẩn đoán chuyển sang `/system`; cái còn lại là một
cuộc trò chuyện.

Hai hành vi chịu lực: đề xuất hiện ra dưới dạng **thẻ có nút bấm**, và
không gì được tạo cho tới khi nút đó được bấm — bấm rồi thì tạo ra một
**bản nháp**. Không có nút "chạy" ở đâu trên trang đó.

Chi tiết endpoint: `docs/API_CONTRACT.md`. Hạn chế bảo mật:
`docs/KNOWN_LIMITATIONS.md` #77–#89.

### M12 — App shell, theme, ngôn ngữ, Dashboard

Chỉ frontend. Backend không đổi một dòng — mọi số liệu Dashboard ghép từ
endpoint đã có, nên không thêm `/dashboard/summary`: một endpoint mới sẽ
là định nghĩa thứ hai của "có bao nhiêu benchmark", và hai định nghĩa
rồi sẽ lệch nhau.

1. **`AppShell`** sở hữu sidebar + top bar + badge duyệt. Trước đó
   `layout.tsx` tự viết sidebar và không có chỗ nào để thêm một control
   cho mọi trang. `/login`, `/welcome`, `/auth/callback` cố tình nằm
   ngoài shell.
2. **Sidebar thu gọn được**, và trạng thái là **một attribute trên
   `<html>`**, chiều rộng nằm trong CSS. React không set pixel — đó là
   thứ cho phép script trong `<head>` áp trạng thái đã nhớ trước lần
   paint đầu. Dưới 900px thành drawer (hamburger mở; overlay hoặc Escape
   đóng; đổi route tự đóng).
3. **Theme Light/Dark/System, không nháy.** Script chặn render đóng dấu
   theme đã resolve lên `<html data-theme>`; mọi màu key theo attribute
   đó. `System` có listener `prefers-color-scheme` nên nó giữ đúng nghĩa
   "theo hệ thống", không phải "theo hệ thống lúc mở tab".
4. **Token màu tập trung**: `globals.css` không còn hex nào nằm ngoài
   khối `:root`. Hai bộ token đầy đủ cho sáng và tối, cộng
   `prefers-color-scheme` cho người chưa chọn gì.
5. **i18n EN/VI**, ~370 key trong hai file JSON. Locale nằm ở **cookie**
   chứ không phải localStorage: chữ do React render, nên chỉ cookie mới
   giúp *server* render đúng ngôn ngữ ngay lần đầu. Hệ quả kiến trúc:
   `lib/i18n/shared.ts` và `lib/theme-script.ts` **không** phải module
   `"use client"` — nhầm chỗ này thì `tsc` và `next build` đều không bắt
   được, chỉ chạy server thật mới lộ (đã xảy ra, xem TEST_REPORT).
6. **Dashboard mới**: bỏ card BACKEND (phiên bản + URL API — vô dụng với
   người dùng thường, và chỉ cho người lạ biết chỗ gõ cửa). Thay bằng
   sáu stat card, quick actions, ba khối hoạt động gần đây, empty state
   cho từng khối, và một dòng "System online" nhỏ. Số nào không tải được
   hiện `—`, **không bao giờ hiện `0`**.
7. **`/system`** là nơi duy nhất còn hiện phiên bản và API URL — và URL
   chỉ hiện trong development.
8. **Icon là bộ SVG inline**, không thêm dependency (project chưa cài
   thư viện icon nào). Vẽ theo quy ước Lucide nên đổi sau này là
   find-and-replace.

Test: 6 file frontend mới, **229 test** (trước: 78), chạy 20 lần liên
tiếp không flaky. Backend chạy lại đầy đủ: **1038 passed**, không đổi.

### M11 — Tài khoản, OAuth và review tùy chọn

Bỏ hẳn role `operator`/`reviewer`. Trước đây một người phải có hai tài
khoản mới đi hết được quy trình của chính mình — điều đó không mô tả
đúng ai đang dùng hệ thống, và biến "đã được review" thành thao tác
đăng xuất đăng nhập.

1. **Quyền lực = quyền sở hữu** (`approval.py`). `Capability{OWNER,
   REVIEWER, ADMIN}` thay cho kiểm tra role. State machine giữ nguyên
   9 state nên benchmark cũ vẫn đọc được và vẫn mang đúng nghĩa; chỉ
   **ai** được đi mỗi cạnh là đổi. Machine vẫn thuần (không biết gì về
   review request): *caller* tính capability set, nên test được nó mà
   không cần database.
2. **Review là tùy chọn** (`review.py`, `review_service.py`). Mặc định
   không ai trong quy trình: tạo → Run → tự Accept. Nhờ review là hành
   động chủ động, và **khi đã nhờ thì chính chủ mất quyền tự quyết ở
   giai đoạn đó** — đó là toàn bộ giá trị của tính năng này. Hai stage:
   `spec` chặn Run, `result` chặn Accept.
3. **`self_approved` khác `approve`** trong audit trail. Chủ sở hữu tự
   mở gate của mình được ghi bằng action riêng, nên đọc lịch sử luôn
   phân biệt được benchmark nào thật sự có người thứ hai xem.
4. **Nickname là khóa tra cứu, không phải khóa phân quyền**
   (`accounts.py`). Unique không phân biệt hoa thường qua cột
   `nickname_key` đã casefold + unique index thường (portable giữa
   SQLite và PostgreSQL, khác với functional index trên `lower()`). JWT
   mang **user ID**, không mang nickname: khóa phân quyền mà người dùng
   tự đổi được thì không phải khóa.
5. **OAuth với FastAPI là authority** (`oauth.py`, `routers/auth.py`).
   Authorization code + PKCE S256 (Google; GitHub OAuth App không hỗ
   trợ), state ký HMAC trong cookie httpOnly (sống qua nhiều worker, không
   cần state server-side), đổi code lấy token **phía server**. JWT
   **không bao giờ vào URL** — callback trả code dùng một lần, đổi qua
   POST.
6. **Không tự động gộp tài khoản trùng email** (`account_service.py`).
   Khóa tra cứu là `(provider, provider_account_id)`. Liên kết Google +
   GitHub vào một tài khoản là hành động chủ động khi đã đăng nhập. Chỉ
   tin email provider đã xác minh — email chưa xác minh không chứng minh
   được gì.
7. **Dev login tắt mặc định** (`PLANBENCH_ENABLE_DEV_LOGIN`). Tài khoản
   password chỉ được tạo khi cờ bật, nên không để lại hash cho tài khoản
   không ai vào được.
8. **Migration 0002** thuần thêm mới: `users`, `oauth_accounts`,
   `review_requests`, cộng `benchmarks.owner_user_id` và
   `approvals.user_id` / `approvals.review_request_id` (đều nullable).
   Benchmark cũ không mất, và có fallback quyền sở hữu theo tên cho
   riêng những row không có `owner_user_id`.
9. **Gate được áp trước khi vào hàng đợi**. `run-async` trước đây nhận
   job rồi mới hỏng bên trong worker — một 403 mà người gọi xử lý được
   biến thành job chết trong log không ai xem. Giờ `check_runnable()`
   raise ngay tại request.

Test: 5 file mới (`test_api_reviews.py`, `test_api_oauth.py`,
`test_api_users.py`, cộng repository và frontend), và toàn bộ test cũ
được viết lại theo mô hình mới. Không gọi OAuth thật lần nào — provider
giả trả đúng payload Google/GitHub gửi, `normalise_identity` test riêng
trên payload đó. Giới hạn của cách này ghi ở KNOWN_LIMITATIONS #59.

### M10 — PostgreSQL + Docker Compose

Chi tiết đầy đủ: `docs/DEPLOYMENT.md`.

1. **Repository ports** (`repository_ports.py`): Protocol structural cho
   5 repository. Trước M10 chỉ có một implementation nên hai lớp "khớp
   nhau" bằng may mắn; giờ đổi tên một tham số là type error chứ không
   phải lỗi runtime ở deployment nào đó.
2. **Tầng SQL** (`db/models.py`, `db/repositories.py`, `db/session.py`):
   6 bảng, JSONB trên PostgreSQL và JSON ở nơi khác. Timestamp là chuỗi
   ISO-8601 (không phải DATETIME) để hai backend không bất đồng ở giá
   trị client nhìn thấy.
3. **Episode đọc lại từ artifact store**: row giữ URI + checksum + size
   (D15); `StackRun` được dựng lại khi replay. Mất volume artifact = mất
   replay dù database còn nguyên — và code báo đúng episode nào.
4. **Alembic**: migration đầu viết tay, `alembic.ini` **không** chứa
   connection string (`env.py` chỉ đọc `PLANBENCH_DATABASE_URL`).
5. **Docker Compose**: `db` (healthcheck `pg_isready -U <user>`),
   `migrate` (one-shot, phải exit 0), `api`, `web`. Migration là service
   riêng vì hai replica cùng `upgrade head` lúc boot là một race.
   **Đã chạy thật ngày 2026-08-05**: thứ tự phụ thuộc hoạt động đúng —
   `api` chỉ khởi động sau khi `migrate` exit 0 và `db` báo healthy.
6. **In-memory vẫn là mặc định**: checkout không có database vẫn chạy
   toàn bộ API và toàn bộ test.

Test: 74 test mới (SQL repositories chạy **cùng assertion qua cả hai
backend**, migration upgrade/downgrade/drift, API end-to-end trên SQL).
Tổng **864 passed**.

FK phát hiện một lỗi thật trong chính test của tôi: episode tạo với
`benchmark_id` không tồn tại. In-memory không diễn đạt được ràng buộc
này nên nó im lặng; SQLite thì không.

> ⚠️ **LỖI THỜI — không dùng để hiểu hệ hiện tại.**
> Tài liệu dừng ở "Giai đoạn 1A", viết **trước** lần chuyển hướng sang
> Planner Selector (2026-08-08). Nội dung giữ nguyên văn để tra lịch sử.
>
> Đọc thay bằng: [`../../01-architecture.md`](../../01-architecture.md) ·
> [`../../../ARCHITECTURE.md`](../../../ARCHITECTURE.md)

---

# Kiến trúc Agentic AI PlanBench

Tài liệu này chính thức hóa kết quả Giai đoạn 0 (audit + thiết kế) và
được cập nhật theo từng giai đoạn. Trạng thái hiện tại: **Giai đoạn 1A**.

## 1. Mục tiêu

Nền tảng web cho kỹ sư robotics/AI: tạo map và scenario, chạy nhiều
thuật toán path/motion planning trên cùng điều kiện (map, start/goal,
obstacle, seed, timeout), đo metric định lượng, phát hiện
collision/stuck/timeout, lưu và replay episode, phân tích thất bại dựa
trên evidence, điều phối bằng LLM Agent có approval gate, tích hợp
ROS2/Nav2 closed-loop. Chỉ mô phỏng; không Gazebo; không robot thật.

## 2. Nguyên tắc kiến trúc

1. **Core-first** — simulator, planning, metrics là thư viện Python
   thuần, không phụ thuộc FastAPI/ROS2/frontend. Mọi tầng khác (API,
   ROS bridge, Gym env, worker) là adapter mỏng trên core. Điều kiện
   để cùng một engine chạy ở 3 chế độ: internal, headless benchmark,
   ROS2 node.
2. **Contract-first** — Pydantic schemas trong `packages/schemas/` là
   nguồn sự thật duy nhất cho domain model, dùng chung bởi API, worker,
   ROS bridge và agent tools.
3. **Determinism-first** — mọi thành phần nhận seed/config tường minh,
   không global random state; cùng input ⇒ cùng output. Đây là nền tảng
   của tính công bằng và khả năng tái lập benchmark.

## 3. Sơ đồ thành phần (mục tiêu cuối)

```
apps/web (Next.js + TS: Canvas 2D → React Three Fiber 2.5D)
        │  HTTP /api/v1 + WebSocket /ws/*
apps/api (FastAPI: auth │ maps │ scenarios │ benchmarks │ episodes │ agent)
        │
Benchmark Orchestrator ──► PostgreSQL │ Artifact storage │ MLflow
        │
CORE (Python thuần)
  services/simulator  : grid, kinematics, collision, lidar, engine
  packages/planning   : astar │ dwa │ rrtstar │ common
  packages/metrics    : per-episode + aggregate
  packages/schemas    : Pydantic domain models
        │
  ml/ (Gym env → PPO)          ros2_ws (simulator node ↔ Nav2)
```

Luồng benchmark: Người dùng → Web → API → Orchestrator → Worker
(simulator nội bộ hoặc ROS2/Nav2) → Planner → Metrics → DB/MLflow →
Dashboard → Failure analysis → LLM report → Reviewer phê duyệt.

## 4. Quy ước kỹ thuật toàn dự án

| Quy ước | Giá trị |
|---|---|
| Đơn vị | SI: mét, giây, radian |
| Chuẩn hóa góc | (-π, π], qua `normalize_angle` |
| Float tolerance | `EPS = 1e-9`, định nghĩa một nơi duy nhất (`planbench_schemas.geometry`) |
| Tiếp xúc biên | Được tính là collision (`clearance <= EPS`) — bảo thủ về an toàn |
| Giá trị cell | Chuẩn ROS: FREE=0, OCCUPIED=100, UNKNOWN=-1 |
| Bố cục grid | Row-major, index = `row * width + col`; row theo +y, col theo +x; cell (0,0) có góc dưới-trái tại origin |
| Robot footprint (MVP) | Hình tròn, thuộc tính `radius` |
| Kinematics | Euler tường minh: `x += v·cosθ·dt`, `y += v·sinθ·dt`, `θ = normalize(θ + ω·dt)`; thứ tự: clamp velocity → giới hạn acceleration → tích phân |

## 5. Quyết định thiết kế (decision log)

| ID | Quyết định | Lý do / Trade-off |
|---|---|---|
| D01 | Branch chính `main` (đổi từ `master` trước commit đầu) | Khớp quy ước GitHub của dự án |
| D02 | Python 3.12, venv `.venv` + pip | Tương thích ROS2 Jazzy/Ubuntu 24.04; chưa dùng uv |
| D03 | Monorepo; chỉ tạo folder khi có file thật | Tránh cấu trúc rỗng |
| D04 | Frontend: Canvas 2D trước, R3F 2.5D sau | Giảm rủi ro Giai đoạn 3; logic điều hướng vẫn 2D |
| D05 | Storage: in-memory trước, PostgreSQL + Alembic sau (M4) | MVP nhanh; schema DB chốt khi domain ổn định |
| D06 | Map nội bộ JSON; import PGM/YAML (ROS map_server) sau | Định dạng nội bộ ổn định trước khi thêm converter |
| D07 | Cell value theo chuẩn ROS (0/100/-1) ngay từ đầu | ROS2 bridge (GĐ 7) không cần phiên dịch giá trị |
| D08 | Tiếp xúc biên = collision | Bảo thủ về an toàn cho hệ benchmark robot |
| D09 | Origin xoay chưa hỗ trợ: validator từ chối `origin.theta ≠ 0` (trong EPS), không âm thầm bỏ qua | Tránh sai lệch tọa độ ngầm; hỗ trợ rotation ở giai đoạn sau |
| D10 | Inflation: chỉ cell OCCUPIED là nguồn; UNKNOWN giữ nguyên trừ khi bị đĩa inflation của OCCUPIED phủ lên; khi truy vấn, UNKNOWN mặc định bị coi là occupied (`unknown_as_occupied=True`) | Phân biệt rõ "không biết" và "chắc chắn có vật cản" |
| D11 | Pytest `pythonpath` thay vì editable install (GĐ 1) | Đơn giản; đóng gói per-package khi service khác cần install (GĐ 2+) |
| D12 | Pure-pursuit follower (GĐ 1B) chỉ là adapter tạm để test episode A* hoàn chỉnh, không phải thuật toán benchmark | Tránh nhầm lẫn khi so sánh |
| D13 | Benchmark so sánh theo stack: A*+DWA vs A*+PPO; không so trực tiếp global planner với local planner | Công bằng về vai trò thuật toán |
| D14 | LLM Agent chỉ ở tầng điều phối; tuyệt đối không xuất `/cmd_vel`; mọi output qua structured schema + validation; kết luận phải trích evidence thật | An toàn + chống hallucination |
| D15 | Trajectory/artifact lớn lưu file/object storage/MLflow; DB chỉ giữ metadata, URI, checksum | Tránh phình DB, dễ replay |

## 6. Roadmap milestone

| Milestone | Nội dung | Trạng thái |
|---|---|---|
| M0 | Audit + kiến trúc | ✅ |
| M1a | Schemas, grid, kinematics, collision + unit test | ✅ (giai đoạn hiện tại) |
| M1b | LiDAR, A*, pure-pursuit (tạm), SimulationEngine, metrics cơ bản | Chờ phê duyệt |
| M2 | FastAPI MVP: map/scenario/simulation API, WebSocket, in-memory repo | — |
| M3 | Frontend MVP: Canvas 2D, map editor, live view | — |
| M4 | DWA + benchmark engine + approval workflow + PostgreSQL + MLflow → đạt MVP | — |
| M5 | Dynamic obstacle, failure detector, leaderboard, parallel headless | — |
| M6 | PPO: Gym env, training, evaluation, curriculum | — |
| M7 | ROS2/Nav2 closed-loop (simulator phát /map /scan /odom /tf, nhận /cmd_vel) | — |
| M8 | Agentic AI + tool calling + RAG + evidence-based report | — |
| M9 | Deployment: Docker Compose, queue, worker separation | — |

## 7. Phạm vi đã triển khai (Giai đoạn 1A)

- `planbench_schemas`: `Point2D`, `Pose2D`, `normalize_angle`,
  `euclidean_distance`, `EPS`; `RobotConfig`, `RobotState`, `SimAction`;
  `CellState`, `MapData` (checksum SHA-256, validator kích thước/giá trị
  cell/origin không xoay); `CircleObstacle`, `RectangleObstacle`,
  `StaticObstacle` (discriminated union).
- `planbench_simulator`: `OccupancyGrid` (world↔grid, truy vấn occupancy,
  inflation thuần không mutate), `kinematics.step` (Euler + clamp +
  acceleration limit), `collision` (robot tròn vs grid/circle/AABB,
  clearance, quy tắc tiếp xúc = collision).
- Unit tests cho toàn bộ phần trên.

Mọi model Pydantic đều `frozen=True` (immutable) và `allow_inf_nan=False`
(từ chối NaN/∞ tại tầng validation).

## 8. Chưa triển khai / hạn chế hiện tại

- Chưa có LiDAR, A*, engine, metrics (GĐ 1B) và mọi thứ từ M2 trở đi.
- `clearance_to_grid` quét toàn bộ cell — đủ cho test/metrics; sẽ thêm
  distance field cache nếu profiling yêu cầu.
- Độ sâu xuyên thấu (penetration depth) với rectangle/grid cell bão hòa
  tại `-radius` khi tâm robot nằm trong vật cản (đủ cho phát hiện
  collision; không dùng cho physics response).
- Inflation dùng khoảng cách tâm-cell tới tâm-cell (disk kernel trên
  cell centre) — tài liệu hóa để metric clearance nhất quán.

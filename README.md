# Agentic AI PlanBench

Nền tảng mô phỏng và benchmark path/motion planning cho robot di động
AMR/AGV. Hệ thống cho phép so sánh công bằng các thuật toán điều hướng
(A*, DWA, PPO, Nav2, ...) trên cùng map, scenario, seed và metric, với
quy trình phê duyệt human-in-the-loop.

**Chỉ dùng cho mô phỏng — không điều khiển robot thật. Không dùng Gazebo.**

## Chạy nhanh

**Windows** — nháy đúp `start.bat`, hoặc từ cmd:

```
start.bat            khởi động API + web UI rồi mở trình duyệt
start.bat stop       dừng cả hai
start.bat status     kiểm tra đang chạy hay không
start.bat logs       xem log
```

**Linux / WSL / macOS** — cùng logic, chạy trực tiếp:

```bash
./scripts/dev_stack.sh start      # http://localhost:3000
./scripts/dev_stack.sh stop
```

Không có `.env`, API tự sinh user dev với mật khẩu ngẫu nhiên và script
in ra màn hình (đổi mỗi lần khởi động). Muốn cố định: copy
`.env.example` sang `.env` rồi đặt `PLANBENCH_SEED_USERS`.

Ba thứ chạy ở chế độ giảm cho tới khi được cấu hình, không phải lỗi:

| Mặc định | Hệ quả | Bật đầy đủ |
|---|---|---|
| Lưu trữ in-memory | mất dữ liệu khi restart | đặt `PLANBENCH_DATABASE_URL` + `alembic upgrade head` |
| Agent dùng mock tất định | trả lời bằng khớp từ khóa, không phải model | dán API key, xem `.env.example` |
| Chưa có model PPO đã train | stack `astar+ppo` không chạy được | train rồi truyền `model_path` |

## Trạng thái

**M0–M10 đã hoàn thành.** Chi tiết:
[docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) ·
kết quả chạy thật: [docs/TEST_REPORT.md](docs/TEST_REPORT.md) ·
**điều chưa kiểm chứng**: [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)

| Thành phần | Trạng thái |
|---|---|
| Schemas, occupancy grid, kinematics, collision, LiDAR | ✅ |
| A*, DWA, pure-pursuit (adapter tham chiếu), SimulationEngine, metrics | ✅ |
| Benchmark engine + fairness checksum + human-in-the-loop | ✅ |
| FastAPI (43 endpoint), WebSocket, background worker | ✅ |
| Next.js UI: map editor, 2.5D, leaderboard, failure analysis, agent console | ✅ |
| Vật cản động, thư viện 10 scenario, MLflow | ✅ |
| PPO (Gymnasium + SB3) | ✅ pipeline — chỉ có smoke model, chưa train thật |
| ROS2 Jazzy + Nav2 closed-loop | ✅ 6/6 episode, chạy tay |
| Agentic AI + RAG, 8 LLM provider | ✅ — chưa gọi provider ngoài lần nào |
| PostgreSQL + Alembic + Docker Compose | ✅ code — **chưa build image, chưa chạy Postgres thật** |

Xem [docs/architecture.md](docs/architecture.md) cho kiến trúc và các
quyết định thiết kế.

## Yêu cầu môi trường

- Python 3.12, Node.js 20+

## Cài đặt

```bash
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r docker/requirements-api.txt
.venv/bin/pip install pytest pytest-cov ruff

cd apps/web && npm install && cd ../..
```

## Chạy kiểm thử

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
PYTHONPATH= .venv/bin/pytest tests/ -v \
  --cov=planbench_schemas \
  --cov=planbench_simulator \
  --cov-report=term-missing
```

Lưu ý `PYTHONPATH=`: nếu shell đã source ROS2 (ví dụ trong
`~/.bashrc`), `PYTHONPATH` chứa `/opt/ros/...` khiến pytest tự nạp
plugin `launch_testing` của ROS và lỗi import. Xóa `PYTHONPATH` khi
chạy test giữ cho `.venv` được cô lập; điều này không ảnh hưởng tới
các giai đoạn ROS2 sau (chúng chạy trong môi trường ROS riêng).

Ghi chú: ở giai đoạn này các package được import trực tiếp từ source
qua cấu hình `pythonpath` của pytest (xem `pyproject.toml`), chưa cần
`pip install -e`.

## Cấu trúc thư mục

```
packages/            schemas, planning (A*/DWA), metrics, benchmark  — thư viện Python thuần
services/simulator/  SimulationEngine, LiDAR, collision, nav_stack
services/tracking/   MLflow adapter + null tracker
services/agent_service/  Agentic AI: provider abstraction, tools, evidence, RAG
apps/api/            FastAPI (thin adapter over the core) + db/ (SQLAlchemy)
apps/web/            Next.js 15 + React 19
ml/                  Gymnasium env, reward, PPO training
ros2_ws/             5 ROS2 package (simulator node, Nav2 bringup, runner)
alembic/             Migration schema
docker/              Image API + web
tests/               pytest — 864 test
scripts/             demo, kiểm tra provider, dev_stack.sh
docs/                architecture, API contract, deployment, frontend, agent, ROS2
```

## Quy ước cốt lõi

- Đơn vị SI: mét, giây, radian; góc chuẩn hóa trong **(-π, π]**.
- `EPS = 1e-9` dùng chung cho so sánh float.
- Tiếp xúc biên **được tính là collision** (quy tắc bảo thủ về an toàn).
- Giá trị cell theo chuẩn ROS: FREE=0, OCCUPIED=100, UNKNOWN=-1.
- Mọi thành phần deterministic với cùng input; không dùng global random state.

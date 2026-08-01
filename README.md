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

`start.bat` tự chạy `alembic upgrade head` trước khi khởi động API, và
in ra phương thức đăng nhập nào đang bật. Migration lỗi thì script dừng
và báo rõ, không khởi động API với schema cũ.

### Đăng nhập

Copy `.env.example` sang `.env` rồi điền **đúng năm biến** này:

```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
AUTH_SECRET=
```

Callback URL cần đăng ký với provider (copy nguyên văn):

| Provider | Callback URL |
|---|---|
| Google — [console](https://console.cloud.google.com/apis/credentials) | `http://localhost:8000/api/v1/auth/oauth/google/callback` |
| GitHub — [settings](https://github.com/settings/developers) | `http://localhost:8000/api/v1/auth/oauth/github/callback` |

Sinh `AUTH_SECRET`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Điền xong chỉ cần chạy lại `start.bat` — không sửa code, không lệnh phụ.

Bỏ trống Google hoặc GitHub cũng được: nút đó không hiện, phần còn lại
vẫn chạy. Bỏ trống cả hai cũng được — đặt
`PLANBENCH_ENABLE_DEV_LOGIN=true` để dùng đăng nhập username/password
cho phát triển cục bộ (mặc định tắt, không dùng cho production).

Lần đăng nhập đầu tiên sẽ hỏi **nickname** (3–30 ký tự, chữ/số/`_`/`-`).
Nickname là cách người khác gửi review cho bạn — không phải khóa phân
quyền, phân quyền luôn dựa trên user ID.

### Giao diện

Thanh bên thu gọn được (nhớ trạng thái), và thành drawer trên màn hình
nhỏ. Trên top bar có nút đổi **ngôn ngữ** (Tiếng Việt / English) và
**giao diện** (Sáng / Tối / Theo hệ thống) — cả hai đều được nhớ, và đổi
theme không bị nháy sai màu lúc tải trang.

Thông tin kỹ thuật (phiên bản, địa chỉ API) nằm ở trang **Thông tin hệ
thống**, không nằm trên Dashboard; địa chỉ API chỉ hiện khi chạy
development.

### Quy trình

Một người làm được toàn bộ việc của mình: tạo map/scenario/benchmark →
**Run** → **Accept results** → lên leaderboard. Không cần tài khoản thứ
hai, không cần đổi tài khoản.

Review là **tùy chọn**. Bấm *Send for review*, nhập nickname người khác,
chọn *spec* (trước khi chạy) hoặc *result* (sau khi chạy). Khi đang chờ,
chính chủ **không** tự duyệt được — đó là toàn bộ ý nghĩa của việc nhờ
review. Có thể hủy yêu cầu bất cứ lúc nào.

Ba thứ chạy ở chế độ giảm cho tới khi được cấu hình, không phải lỗi:

| Mặc định | Hệ quả | Bật đầy đủ |
|---|---|---|
| Chưa cấu hình OAuth | trang login báo rõ, không có nút | điền 5 biến ở trên |
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

- Cách chạy nhanh bằng 1 câu lệnh:
bash scripts/dev_stack.sh start
- Cách stop chương trình 
bash scripts/dev_stack.sh stop

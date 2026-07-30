# Agentic AI PlanBench

Nền tảng mô phỏng và benchmark path/motion planning cho robot di động
AMR/AGV. Hệ thống cho phép so sánh công bằng các thuật toán điều hướng
(A*, DWA, PPO, Nav2, ...) trên cùng map, scenario, seed và metric, với
quy trình phê duyệt human-in-the-loop.

**Chỉ dùng cho mô phỏng — không điều khiển robot thật. Không dùng Gazebo.**

## Trạng thái

Dự án đang ở **Giai đoạn 1A — Core Simulator (phần nền)**:

| Thành phần | Trạng thái |
|---|---|
| Domain schemas (geometry, robot, map, obstacle) | ✅ |
| Occupancy grid + obstacle inflation | ✅ |
| Differential-drive kinematics (Euler) | ✅ |
| Static collision detection + clearance | ✅ |
| LiDAR giả lập, A*, SimulationEngine, metrics | Giai đoạn 1B |
| DWA, benchmark engine, FastAPI, frontend | Giai đoạn sau |
| PPO, ROS2/Nav2 closed-loop, Agentic AI, RAG | Giai đoạn sau |

Xem [docs/architecture.md](docs/architecture.md) cho kiến trúc và các
quyết định thiết kế.

## Yêu cầu môi trường

- Python 3.12

## Cài đặt

```bash
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install "pydantic>=2.7,<3" pytest pytest-cov ruff
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
packages/schemas/planbench_schemas/    # Pydantic domain schemas (contract-first)
services/simulator/planbench_simulator/# Simulator core (Python thuần, không framework)
tests/                                 # Unit tests
docs/                                  # Tài liệu kiến trúc
```

## Quy ước cốt lõi

- Đơn vị SI: mét, giây, radian; góc chuẩn hóa trong **(-π, π]**.
- `EPS = 1e-9` dùng chung cho so sánh float.
- Tiếp xúc biên **được tính là collision** (quy tắc bảo thủ về an toàn).
- Giá trị cell theo chuẩn ROS: FREE=0, OCCUPIED=100, UNKNOWN=-1.
- Mọi thành phần deterministic với cùng input; không dùng global random state.

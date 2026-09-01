> ⚠️ **LỖI THỜI** — bản tổng hợp 2026-08-03, viết trước lần chuyển hướng
> sang Planner Selector (2026-08-08). Giữ nguyên văn để tra lịch sử.
>
> Đọc thay bằng: [`../../02-features.md`](../../02-features.md)

---

# Workflow — tổng hợp công việc đã làm

> Bản tổng hợp toàn bộ tính năng và công việc trên RAV19 – PlanBench.
> Cập nhật 2026-08-03.
>
> Đây là bản **tóm tắt**. Chi tiết nằm ở:
> [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) (tiến độ) ·
> [TEST_REPORT.md](../../reference/TEST_REPORT.md) (output test thật) ·
> [KNOWN_LIMITATIONS.md](../../reference/KNOWN_LIMITATIONS.md) (điều chưa kiểm chứng) ·
> [API_CONTRACT.md](./API_CONTRACT.md) · [architecture.md](./architecture.md)

## Mục lục

- [1. Sản phẩm là gì](#1-sản-phẩm-là-gì)
- [2. Quy mô hiện tại](#2-quy-mô-hiện-tại)
- [3. Các milestone đã làm](#3-các-milestone-đã-làm)
- [4. Tính năng theo nhóm](#4-tính-năng-theo-nhóm)
- [5. Kiến trúc](#5-kiến-trúc)
- [6. Kết quả kiểm thử](#6-kết-quả-kiểm-thử)
- [7. Việc đã làm ngoài tính năng](#7-việc-đã-làm-ngoài-tính-năng)
- [8. Đang dang dở](#8-đang-dang-dở)
- [9. Chưa kiểm chứng được](#9-chưa-kiểm-chứng-được)

---

## 1. Sản phẩm là gì

Nền tảng web **chỉ mô phỏng** để thiết lập, chạy và đánh giá benchmark cho
thuật toán điều hướng robot AMR/AGV. Người dùng dựng map và scenario,
chạy benchmark trên nhiều seed trong điều kiện bị khóa, xem lại quỹ đạo,
đọc metrics do simulator tính. Một trợ lý AI giúp chuyển yêu cầu bằng lời
thành cấu hình có cấu trúc và giải thích kết quả đã lưu — người dùng là
người bấm nút chạy.

Không điều khiển robot thật, không cấp chứng nhận an toàn.

## 2. Quy mô hiện tại

| Hạng mục | Số lượng |
|---|---|
| Route frontend | 17 |
| Router API | 15 |
| Endpoint | 91 |
| Migration Alembic | 3 (16 bảng) |
| Scenario dựng sẵn | 10 |
| Stack thuật toán | 5 (`astar+dwa`, `astar+ppo`, `astar+pure_pursuit`, `rrtstar+dwa`, `rrtstar+pure_pursuit`) |
| Test backend | 1116 passed, 2 skipped |
| Test frontend | 274 passed (18 file) |

## 3. Các milestone đã làm

| # | Nội dung |
|---|---|
| **M0** | Kiến trúc, decision log D01–D16 |
| **M1A** | Pydantic schemas, OccupancyGrid, kinematics, collision |
| **M1B** | LiDAR (DDA), A*, Pure Pursuit, SimulationEngine, metrics |
| **M2** | FastAPI: maps/scenarios/simulations, WebSocket |
| **M3** | Next.js: Canvas 2D, map editor, live simulation |
| **M4** | DWA, benchmark engine, human-in-the-loop, MLflow |
| **M5** | Vật cản động, thư viện scenario, failure analysis, leaderboard |
| **M6** | PPO: Gymnasium env, reward, training script |
| **M7** | ROS2/Nav2 closed-loop (chạy tay) |
| **M8** | Agentic AI + RAG, nhiều LLM provider |
| **M9** | Hiển thị 2.5D, UI cho M5/M6/M8 |
| **M10** | PostgreSQL, Alembic, Docker Compose |
| **M11** | Tài khoản, Google/GitHub OAuth, nickname, review tùy chọn |
| **M12** | App shell, sidebar thu gọn, theme Light/Dark/System, VI/EN, Dashboard |
| **M13** | Model Registry, Robot Profile, trợ lý hội thoại |

## 4. Tính năng theo nhóm

### Mô phỏng và thuật toán

| Tính năng | Trạng thái | Nơi chứa |
|---|---|---|
| Occupancy grid, kinematics, collision | Completed | `services/simulator/planbench_simulator/` |
| LiDAR (ray casting DDA) | Completed | `.../lidar.py` |
| A* global planner | Completed | `packages/planning/planbench_planning/astar/` |
| RRT* global planner | Completed | `packages/planning/planbench_planning/rrtstar/` |
| Đọc map ROS (`map_server`) | Completed | `packages/schemas/planbench_schemas/map_io.py` |
| DWA local planner | Completed | `.../dwa/` |
| Pure Pursuit (tham chiếu, không dự benchmark) | Completed | `.../path_follower.py` |
| PPO adapter | Completed | `ml/planbench_rl/policy.py` |
| Vật cản động | Completed | `packages/schemas/planbench_schemas/dynamic.py` |
| Deterministic seed | Completed | seed tường minh, không có trạng thái toàn cục |

### Benchmark

| Tính năng | Trạng thái | Nơi chứa |
|---|---|---|
| Benchmark nhiều seed, nhiều stack | Completed | `packages/benchmark/` |
| `conditions_checksum` (khóa điều kiện, so sánh công bằng) | Completed | `.../spec.py` |
| State machine + hai cổng con người | Completed | `apps/api/planbench_api/approval.py` |
| Metrics (9 chỉ số + latency p50/p95/p99, stop-and-go) | Completed | `packages/metrics/episode_metrics.py` |
| Thống kê so sánh: median/IQR, bootstrap CI, Wilcoxon | Completed | `packages/metrics/planbench_metrics/statistics.py` |
| So sánh theo cặp giữa các stack | Completed | `packages/benchmark/planbench_benchmark/runner.py` |
| Xuất report Markdown | Completed | `apps/api/planbench_api/report_markdown.py` |
| Độ khó scenario đo được | Completed | `packages/benchmark/planbench_benchmark/difficulty.py` |
| Tuning siêu tham số (Optuna) | Completed | `packages/benchmark/planbench_benchmark/tuning.py` |
| Episode replay từ artifact | Completed | `.../routers/episodes.py` |
| Failure analysis | Completed | `.../routers/episodes.py` |
| Leaderboard | Completed | `.../leaderboard.py` |

### Model Registry (M13)

| Tính năng | Trạng thái | Nơi chứa |
|---|---|---|
| Upload model PPO qua web (`.zip`) | Completed | `.../routers/models.py` |
| Metadata `.json`, tài liệu `.pdf` | Completed | `.../model_registry.py` |
| Kiểm tra tương thích với Robot Profile | Completed | `check_compatibility()` |
| SHA-256, chống path traversal, giới hạn kích thước | Completed | `.../model_storage.py` |
| Robot Profile (tham số robot là dữ liệu) | Completed | `.../registry_service.py` |
| Chọn model theo ID trong benchmark | Completed | `packages/benchmark/planbench_benchmark/registry.py` |

Ba loại file phân biệt rõ: `.zip` là thứ duy nhất chạy được như policy,
`.json` là metadata, `.pdf` là tài liệu. Upload PDF ở ô model bị từ chối.

### Trợ lý AI

| Tính năng | Trạng thái | Nơi chứa |
|---|---|---|
| Hội thoại nhiều lượt, hỏi làm rõ | Completed | `.../chat_service.py` |
| Thẻ đề xuất → người dùng bấm → tạo bản nháp | Completed | `.../routers/chat.py` |
| Đọc và giải thích kết quả đã lưu | Completed | |
| Evidence + citation được validate | Completed | `services/agent_service/planbench_agent/evidence.py` |
| Nhiều LLM provider (Gemini, OpenAI, Anthropic…) | Completed | `.../factory.py` |

Ranh giới được thực thi ở **tầng API**, không chỉ ở prompt: không tồn tại
endpoint `/ai/**` nào cho phép chạy, duyệt hay chấp nhận kết quả. Ghi duy
nhất là tạo bản nháp.

### Tài khoản và review

| Tính năng | Trạng thái | Nơi chứa |
|---|---|---|
| Google / GitHub OAuth | Completed | `.../routers/auth.py` |
| Nickname (chỉ hiển thị, không phải khóa phân quyền) | Completed | `.../routers/users.py` |
| Review tùy chọn bằng nickname | Completed | `.../routers/reviews.py` |
| Audit log append-only | Completed | `.../approval.py` |

### Giao diện

| Tính năng | Trạng thái | Nơi chứa |
|---|---|---|
| App shell, sidebar thu gọn, drawer mobile | Completed | `apps/web/src/components/AppShell.tsx` |
| Theme Light/Dark/System, không nháy màu | Completed | `.../ThemeSwitcher.tsx` |
| Song ngữ VI/EN | Completed | `apps/web/src/lib/i18n/` |
| Map editor Canvas 2D | Completed | `.../MapCanvas.tsx` |
| Hiển thị 2.5D | Completed | `.../Scene25D.tsx` |
| Trang Model Registry + upload có tiến độ | Completed | `apps/web/src/app/models/` |
| Trang trợ lý dạng chatbot | Completed | `apps/web/src/app/agent/` |
| Lịch sử hội thoại (liệt kê, mở lại, xoá) | Completed | `apps/web/src/app/agent/page.tsx` |

### Lưu trữ

| Tính năng | Trạng thái | Nơi chứa |
|---|---|---|
| SQLAlchemy + Alembic, 16 bảng | Completed | `apps/api/planbench_api/db/`, `alembic/` |
| SQLite cho phát triển | Completed, đã kiểm chứng | |
| Artifact storage (trajectory, report, model) | Completed | `.../artifacts.py`, `.../model_storage.py` |
| PostgreSQL | Completed, đã kiểm chứng | migration chạy trên PostgreSQL 17 trong Docker |
| Docker Compose | Completed, đã kiểm chứng | image build được, cả stack chạy thật |

## 5. Kiến trúc

Ba nguyên tắc xuyên suốt:

- **Core-first** — `packages/` và `services/simulator/` là thư viện Python
  thuần, không import FastAPI, ROS2 hay frontend. API là adapter mỏng.
- **Contract-first** — Pydantic models trong `packages/schemas/` là nguồn
  sự thật cho kiểu dữ liệu.
- **Determinism-first** — mọi thành phần nhận seed và config tường minh;
  cùng đầu vào cho cùng đầu ra.

Quyết định D15: payload lớn (trajectory, report, model) nằm **ngoài**
database; bảng chỉ giữ URI + SHA-256 + kích thước.

## 6. Kết quả kiểm thử

```
ruff format --check .    204 files already formatted
ruff check .             All checks passed!
pytest tests/ -q         1195 passed, 3 skipped
tsc --noEmit             không lỗi
vitest run               274 passed (18 file)
next build               thành công
```

pytest được chạy thêm một lượt với **7 gói tùy chọn bị chặn**, mô phỏng
đúng môi trường CI chỉ cài `requirements.txt`. Hai skip là hai module
scaffold của template T-011.

## 7. Việc đã làm ngoài tính năng

### Tài liệu Gate G1

Bốn deliverable trong `docs/docs/`: Brief, PRD (32 mục), Wireframe & UI
Flow (20 mục, 13 sơ đồ Mermaid), GitHub & AI Log Setup (51 mục). Mỗi
tính năng được ghi trạng thái đều dẫn về file thật trong repository.

### Sửa CI sau khi tích hợp T-011

Template T-011 mang vào `ruff.toml` ở gốc — file này **thay thế hoàn
toàn** `[tool.ruff]` trong `pyproject.toml` chứ không hợp nhất, nên
`known-first-party` bị bỏ và 36 khối import bị báo sai thứ tự. Đã hợp
nhất về một nguồn cấu hình duy nhất.

Cùng lúc phát hiện một lỗi nặng hơn: `tests/__init__.py` biến `tests/`
thành package, làm `import agent_fakes` gãy ở 4 module — **gãy cả ở máy
local, không chỉ CI**. Sửa bằng cách khai `pythonpath` tường minh.

Ngoài ra: bỏ credential giả `OPENAI_API_KEY: test-key` khỏi workflow,
đưa CI về Python 3.12 cho khớp `requires-python`, khôi phục fixture
`client` bị mất khi merge.

### Sửa lỗi không lưu dữ liệu

`.env` có `PLANBENCH_DATABASE_URL=` (rỗng). "Đặt bằng rỗng" khác "không
đặt": nó chọn thẳng backend trong bộ nhớ, và không migration nào chạy —
nên benchmark biến mất sau mỗi lần khởi động lại. `.env.example` tự mâu
thuẫn: chú thích nói để trống thì tự dùng SQLite, trong khi chính nó ship
dòng gán rỗng.

Đã sửa `.env.example`, thêm cảnh báo rõ trong `dev_stack.sh`, và kiểm
chứng bằng **hai tiến trình riêng biệt** rằng dữ liệu sống sót thật.

## 8. Đang dang dở

| Việc | Tình trạng |
|---|---|
| ROS2 / Nav2 | 5 package chạy tay, chưa tích hợp vào giao diện web |
| MLflow | Có adapter, chưa dùng trong luồng web |
| Huấn luyện PPO | Chạy được bằng dòng lệnh, không có giao diện web |
| Object storage S3/R2 | Interface `ModelStorage` có sẵn, mới cài bản cục bộ |

## 9. Chưa kiểm chứng được

Danh sách đầy đủ ở [KNOWN_LIMITATIONS.md](../../reference/KNOWN_LIMITATIONS.md). Ba
điều quan trọng nhất:

**Model upload không chạy trong sandbox.** Đã kiểm extension, magic
bytes, bảng mục lục zip, làm sạch tên file, chống path traversal, giới
hạn kích thước khi ghi, SHA-256, và **không `pickle.load` trong tiến
trình API**. Nhưng khi benchmark PPO chạy thật, checkpoint được giải tuần
tự trong tiến trình worker — không có container, không có giới hạn
CPU/RAM. **Không được kết luận model upload là an toàn tuyệt đối.**

**Chưa chạy nhiều người dùng đồng thời** trên PostgreSQL. Transaction
tranh chấp và connection pool dưới tải thật vẫn là ẩn số.

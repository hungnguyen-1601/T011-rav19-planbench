# Đánh giá lại hiện trạng PlanBench — 2026-08-04

> **Mục đích:** kiểm chứng lại bản `docs/antongduy/plan/BAO_CAO_DANH_GIA_HIEN_TRANG.md`
> (báo cáo cũ) so với repo **hiện tại**, đối chiếu với đề bài
> `docs/antongduy/phan-tich-de-bai-benchmark-planning.md`.
> **Cách làm:** grep toàn repo (loại `.venv`/`node_modules`) cho từng
> hạng mục, đọc trực tiếp code, và **chạy thật** toàn bộ test suite.
> **Bằng chứng chạy:** `python -m pytest tests/ -q` →
> `1085 passed, 4 skipped, 1 warning in 318.17s`.
> HEAD tại thời điểm đánh giá: `9807db5 sql`.

---

## 0. Kết luận một câu

**Báo cáo cũ vẫn đúng ở phần quan trọng nhất, và sai ở vài chi tiết phụ.**
Toàn bộ P01–P05 **vẫn bị bỏ trắng 5/5** — không một dòng code nào được
thêm cho nhóm này kể từ báo cáo cũ. Cái đã thay đổi là dự án tiếp tục
đầu tư vào tầng sản phẩm (Model Registry, trợ lý hội thoại, OAuth,
SQLAlchemy + Alembic), tức **độ lệch phạm vi mà báo cáo cũ cảnh báo đã
nới rộng thêm, không thu hẹp lại**.

Phát hiện mới nghiêm trọng hơn cả báo cáo cũ: **hệ thống hiện chỉ có
đúng 1 thuật toán chạy được ngay sau khi clone** (`astar+dwa`).
`astar+ppo` cần torch (vài GB, optional) **và** một model đã huấn luyện
do người chọn; `astar+pure_pursuit` bị gắn cứng `benchmarkable=False`.
Một nền tảng benchmark so sánh thuật toán mà mặc định chỉ so sánh được
một thuật toán — đây là lỗ hổng đứng trên cả P01–P05 về mức độ hiển
nhiên khi bị chấm.

---

## 1. Bảng phán quyết: báo cáo cũ còn đúng không?

| Mục báo cáo cũ | Phán quyết | Bằng chứng hiện tại |
|---|---|---|
| P01–P05 bỏ trắng 5/5 | ✅ **Vẫn đúng nguyên vẹn** | `grep -ri` toàn repo: `optuna` = 0, `wilcoxon` = 0, `bootstrap` = 0 (ngoài pip vendor), `observation_class` = 0, `holdout` = 0, `generalization_gap` = 0, `SEARCH_SPACES` = 0. `scipy` không có trong `requirements.txt` lẫn `requirements-optional.txt`. |
| RRT* không tồn tại | ✅ Vẫn đúng | `grep -ri rrt` = 0 kết quả trong source. Registry chỉ có `astar+dwa`, `astar+ppo`, `astar+pure_pursuit`. |
| F01 map loader PGM/YAML thiếu | ✅ Vẫn đúng | `grep -i pgm` = 0, `occupied_thresh` = 0, `yaml.safe_load` = 0. Không có `PyYAML` trong dependency. Map vẫn chỉ dựng bằng code hoặc JSON qua API. |
| Không có thư viện biểu đồ, không export MD/PDF (F09) | ✅ Vẫn đúng | `apps/web/package.json` chỉ có `next`/`react`/`react-dom`. Không recharts/d3/chart.js/plotly. Toàn bộ `<svg>`/`canvas` trong repo chỉ ở `Icon.tsx`, `MapCanvas.tsx`, `Scene25D.tsx`, `login/page.tsx` — không có cái nào là biểu đồ số liệu. `export_report`/`to_markdown` = 0. |
| Không chạy song song episode (F16) | ✅ Vẫn đúng | `multiprocessing`/`ProcessPool`/`ray` = 0 trong source. |
| Không regression guard (F17) | ✅ Vẫn đúng | Không có code nào. |
| MLflow thiếu git SHA | ✅ Vẫn đúng | `git_sha`/`git_commit` = 0. |
| Smoothness lệch công thức spec | ✅ Vẫn đúng | `episode_metrics.py:88` — `smoothness = heading_change / trajectory_length` (Σ\|Δθ\|/L), spec mục 8.2 yêu cầu `S = Σ(Δθ)²`. |
| Thiếu p50/p95/p99, peak memory, stop-and-go | ✅ Vẫn đúng | `percentile`/`p95`/`peak_memory`/`stop_and_go` = 0. `AlgorithmAggregate` chỉ có `mean_*` / `max_*` / `worst_*`. |
| `BenchmarkSpec.seeds` cho phép 1 seed | ✅ Vẫn đúng | `spec.py:39` — `seeds: tuple[int, ...] = Field(min_length=1)`. |
| Aggregate không có median/IQR/CI/p-value/rank | ✅ Vẫn đúng | `spec.py:138-166` — `AlgorithmAggregate` toàn `mean_*`, không median, không IQR, không CI, không effect size. |
| MapCanvas không vẽ vật cản tĩnh/động | ✅ Vẫn đúng | `grep -n "obstacle" MapCanvas.tsx` = 0 kết quả. |
| Không có Social Force Model | ✅ Vẫn đúng | 4 motion model (waypoint/periodic/random-walk/sudden-stop), không có SFM. |
| Scenario Pack thiếu maze/dead-end | ✅ Vẫn đúng | `SCENARIO_LIBRARY` 10 mục: `open_space`, `static_obstacles`, `wide_corridor`, `narrow_corridor`, `doorway`, `crossing_obstacle`, `sudden_stop`, `bidirectional_corridor`, `intersection`, `dynamic_warehouse`. |
| Commit `2e8a993` ghi "Three.js" nhưng code là Canvas 2D | ✅ Vẫn đúng | `package.json` không có `three`. `Scene25D.tsx` là canvas 2D thuần (painter's algorithm, slider elevation). |
| `difficulty` chỉ là `CURRICULUM_ORDER` gán tay | ✅ Vẫn đúng | `scenarios.py:318` — `CURRICULUM_ORDER = tuple(SCENARIO_LIBRARY)`, tức đúng thứ tự khai báo dict, không phải số đo thực nghiệm. |
| Docker Compose chưa từng chạy | ✅ Vẫn đúng | `docs/IMPLEMENTATION_STATUS.md`: "chưa chạy Docker lần nào và chưa kết nối PostgreSQL thật". |
| LiDAR không có noise model (F23) | ✅ Vẫn đúng | KNOWN_LIMITATIONS #7. |
| Sim-only safety gate đạt | ✅ Vẫn đúng | Gateway agent không có method điều khiển; ROS2 chỉ nối phần mềm. Giữ nguyên đánh giá tích cực. |
| **878 test pass** | ❌ **Lỗi thời** | Đã chạy thật: **1085 passed, 4 skipped**. Bộ test tăng ~24%. |
| **"PPO nằm trong registry như thuật toán khả dụng, dễ gây hiểu nhầm"** (mục 7.3 / khuyến nghị #12) | ❌ **Đã được xử lý** | `AlgorithmInfo.requires_model: bool = True` cho `astar+ppo`, kèm docstring giải thích rõ vì sao không suy ra từ config schema. `astar+pure_pursuit` gắn `benchmarkable=False`. Khuyến nghị #12 của báo cáo cũ coi như đã xong. |
| **"Replay chỉ hiện khung cuối, chưa tua thời gian"** (F08) | 🟡 **Đúng một nửa** | Trang `/simulate` **đã có tua thời gian đầy đủ**: `<input type="range">` playhead + `stream.seek()` + chọn tốc độ 0.25×–8× qua WebSocket (`simulate/page.tsx:195-225`). Nhưng replay của **episode đã lưu** (`benchmarks/[id]/page.tsx:524-556`) vẫn chỉ đặt `robotPose = trajectory[trajectory.length - 1]` — tức vẫn là khung cuối. |
| **"DWA (lidar-only) và PPO (35-dim gồm cả vị trí) thực chất khác lớp quan sát"** | ❌ **Sai** | Đọc code thì hai stack **cùng lớp quan sát**, và điều đó được schema cưỡng chế. `episode.py:64` — `class Observation`, docstring *"What a local planner may see at one step (no ground-truth map)"*, chỉ có `pose`/`velocity`/`goal_distance`/`goal_bearing`/`lidar_ranges`, **không có vị trí vật cản**. `ml/planbench_rl/observation.py` docstring: *"Ground-truth obstacle poses are never included."* `dwa/planner.py` docstring: *"Obstacles come from the LiDAR scan in the observation, not from the ground-truth map."* → cân bằng thông tin **đã đúng sẵn**, chỉ thiếu phần *khai báo và kiểm chứng* — tức P02 rẻ hơn dự tính và cho phép tuyên bố mạnh hơn dự tính. |
| **"PostgreSQL mới chỉ nằm trong compose"** | ❌ **Lỗi thời** | Đã có `alembic/` + `alembic/versions/`, `apps/api/planbench_api/db/` (SQLAlchemy), `repositories.py`/`repository_ports.py`, và test thật: `tests/api/test_api_sql_backend.py`, `test_sql_repositories.py`, `test_migrations.py`. Mặc định SQLite, PostgreSQL qua `psycopg` optional. |

---

## 2. Những gì đã thay đổi kể từ báo cáo cũ

Tất cả đều nằm **ngoài** nhóm P01–P05:

1. **M13 — Model Registry** (`model_registry.py`, `model_storage.py`,
   `registry_service.py`): model là bản ghi có chủ sở hữu + checksum +
   schema quan sát, upload qua web thay cho `model_path` trần. Có soi
   zip **không giải tuần tự** (chống pickle RCE) — thiết kế an toàn tốt.
2. **Trợ lý hội thoại** (`chat_service.py`, `routers/chat.py`) thay ba
   biểu mẫu kỹ thuật. Có test khẳng định *không có* endpoint `run` trên
   trợ lý (`test_api_chat.py::test_there_is_no_run_endpoint_on_the_assistant`)
   — đúng tinh thần sim-only.
3. **OAuth Google/GitHub** + dev login (`routers/oauth`, `auth/callback`).
4. **Tầng lưu trữ thật**: SQLAlchemy + Alembic migration, SQLite mặc
   định, PostgreSQL tùy chọn.
5. **Dependency được ghim `==` và tách optional/required** với chế độ
   suy giảm có kiểm soát (MLflow thiếu → null tracker; torch thiếu →
   PPO không xuất hiện). Đây là một điểm cộng thật cho trụ
   *reproducibility* của đề bài, dù chưa phải P01–P05.
6. **docker-compose.yml** giờ 4 service (`db`, `migrate`, `api`, `web`)
   — có bước migrate riêng, đúng hơn trước. Vẫn chưa chạy lần nào.

---

## 3. Phát hiện mới (không có trong báo cáo cũ)

### 3.1. 🔴 Chỉ 1 thuật toán chạy được ngay — nghiêm trọng nhất

`packages/benchmark/planbench_benchmark/registry.py:155-201`:

| Stack | `benchmarkable` | Điều kiện chạy |
|---|---|---|
| `astar+dwa` | ✅ true | Chạy ngay |
| `astar+ppo` | ✅ true | Cần `torch`+`gymnasium`+`sb3` (optional, vài GB) **và** `requires_model=True` — phải có checkpoint đã train do người chọn |
| `astar+pure_pursuit` | ❌ **false** | Bị cấm dùng để kết luận benchmark (đúng, vì nó bỏ qua sensing) |

Đề bài F04 yêu cầu "A* + DWA làm cặp mặc định; **RRT\* là thuật toán thứ
ba**". Hiện tại: cặp mặc định đúng, thuật toán thứ ba không tồn tại, và
thuật toán thứ hai thì không chạy được nếu không cài thêm vài GB + tự
train. **Một demo sạch trên máy mới sẽ chỉ so sánh được `astar+dwa` với
chính nó ở các seed khác nhau.** Đây là lỗ hổng dễ bị chỉ ra nhất khi
chấm, và cũng là lý do vì sao RRT* (thuần Python, không dependency) nên
được ưu tiên cao hơn nhiều so với vị trí "ưu tiên 3, mục 13" mà báo cáo
cũ xếp cho nó.

### 3.2. 🟠 Độ lệch phạm vi đã nới rộng thêm

Báo cáo cũ (mục 7, ý 8) cảnh báo "mất cân đối phạm vi nghiêm trọng:
đầu tư lớn vào Pha 3 trong khi P01–P05 bỏ trắng". Kể từ đó, dự án làm
thêm M13 (registry, chat, OAuth, SQL) — **toàn bộ nằm ở tầng sản phẩm,
không hạng mục nào thuộc P01–P05**. Cảnh báo đó không những còn đúng mà
đã trở nên nặng hơn: khoảng cách giữa "hạ tầng đã làm" và "phương pháp
luận đánh giá" đang giãn ra theo thời gian, không thu lại.

### 3.3. 🟡 Đề bài mục 8.6(a) yêu cầu median + IQR, code chỉ có mean

Chi tiết này báo cáo cũ có nhắc gộp, nhưng đáng tách riêng vì nó là lỗi
**định hướng sai ngay trong tên field**: `mean_travel_time_successful`,
`mean_path_efficiency_successful`, `mean_smoothness_successful`… Đề bài
nói rõ dữ liệu robot lệch phải mạnh nên **mean bị outlier kéo**, phải
dùng median + IQR. Sửa việc này đụng vào tên field công khai của
`AlgorithmAggregate` → càng để lâu càng đắt (API contract, frontend
types, test). Nên làm sớm.

### 3.4. 🟢 Điểm tích cực mới cần ghi nhận

- Bộ test 1085 case chạy **thật**, xanh hoàn toàn, 5 phút 18 giây — không
  phải test rỗng.
- `requirements.txt` có comment giải thích **vì sao** ghim version:
  "Một nền tảng benchmark mà dependency của chính nó trôi âm thầm thì
  không còn đo đúng thứ nó tuyên bố đo nữa." Đây đúng tinh thần trụ
  *reproducibility*.
- Thiết kế an toàn tiếp tục được giữ khi mở rộng: model upload soi zip
  không giải tuần tự; trợ lý không có đường chạy.

---

## 4. Trạng thái hiện tại theo đề bài (bảng gọn)

**Nhóm giao thức đánh giá — mục 7.0, differentiator cốt lõi**

| ID | Trạng thái | Ghi chú |
|---|---|---|
| P01 Cân bằng ngân sách tinh chỉnh | ❌ 0% | Không có Optuna, không log lịch sử tune |
| P02 `observation_class` | ❌ 0% | `AlgorithmInfo` không có field này |
| P03 Hiệu chuẩn độ khó thực nghiệm | ❌ 0% | Chỉ có `CURRICULUM_ORDER` gán tay |
| P04 Thống kê chặt | ❌ 0% | Không scipy, không median/IQR/CI/p-value/rank |
| P05 Held-out & generalization gap | ❌ 0% | Không có khái niệm split |

**MVP F01–F12**

| ID | Trạng thái | So báo cáo cũ |
|---|---|---|
| F01 Map loader PGM/YAML | ❌ | không đổi |
| F02 Scenario Spec YAML | 🟡 (schema đủ, không có YAML) | không đổi |
| F03 Sim core 2D | ✅ | không đổi |
| F04 Registry ≥2 thuật toán | 🟡 → **🔴** | **xấu đi về mặt đánh giá**: chỉ 1 stack chạy ngay |
| F05 Metrics 5 nhóm | 🟡 | không đổi (smoothness lệch, thiếu p95/mem/stop-and-go) |
| F06 Batch Runner | 🟡 | không đổi (tuần tự) |
| F07 MLflow tracking | ✅ thiếu git SHA | không đổi |
| F08 Trajectory Viewer | 🟡 → **🟢/🟡** | **tốt lên**: `/simulate` đã tua được; replay đã lưu vẫn khung cuối |
| F09 Comparison Report | ❌ export, ❌ biểu đồ | không đổi |
| F10 RBAC | ✅ | không đổi (3 vai trò) |
| F11 Approval Workflow | ✅ | không đổi (chống tự duyệt) |
| F12 Docker Compose | 🟡 chưa chạy | compose tốt hơn (thêm `migrate`), vẫn chưa chạy |

**Pha 2–3:** F13 🟡 (không SFM), F14 🟡, F15 🟡 (không CI/test),
F16 ❌, F17 ❌, F18 🟢, F19 🟡, F20 🟢, F21 ❌, F22 🟡, F23 ❌ — **không
mục nào đổi trạng thái** so với báo cáo cũ.

---

## 5. Plan xử lý — đã tách ra file riêng

Phần plan chi tiết (6 đợt, kèm file cụ thể, test, kiểm chứng, sơ đồ phụ
thuộc, thứ tự cắt phạm vi) nằm ở:

**`docs/antongduy/plans/2026-08-04/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`**
— *chờ approve, chưa triển khai.*

Tóm tắt đợt:

| Đợt | Nội dung |
|---|---|
| 0 | RRT\* + chạy Docker thật (chặn máu) |
| 1 | **P02** (`observation_class`) + **P04** (thống kê) — đề bài cấm cắt |
| 2 | **P05** (dev/holdout) + **P03** (hiệu chuẩn độ khó) + **Plan A** (Scenario Editor) |
| 3 | F09 (biểu đồ + export) + F05 (sửa metric) — nơi P03/P04 nhìn thấy được |
| 4 | **Plan B** (Replanning) + F01 (map loader) + F08 (replay scrubbing) |
| 5 | **P01** (Optuna) + F16/F17/F23 + dọn dẹp |

Hai plan đang treo ở `plans/2026-08-03/` (Plan A: Scenario Editor;
Plan B: Replanning công bằng) **đã được gộp vào cùng hệ thống đợt** —
Plan A vào Đợt 2 (là công cụ lấp dải difficulty cho P03), Plan B vào
Đợt 4 (đụng cùng `episode_metrics.py` với F05, và làm sớm sẽ vô hiệu
hóa bộ hiệu chuẩn difficulty của P03). Research trong hai plan đó đã
kiểm lại ngày 2026-08-04 và **vẫn đúng với repo hiện tại**.

---

## 6. Khuyến nghị đóng khung khi báo cáo/demo

Giữ nguyên khuyến nghị của báo cáo cũ, siết thêm một ý:

- **(a) Hạ tầng kỹ thuật** — làm tốt và thật (sim core, A*/DWA viết tay,
  RBAC + approval chống tự duyệt, ROS2/Nav2, RL pipeline, agent có chống
  fabricate citation, 1085 test xanh, dependency ghim version có lý do).
  Đây là phần ghi điểm năng lực kỹ thuật.
- **(b) Phương pháp luận đánh giá (P01–P05)** — hiện **0%**. Đây là
  phần quyết định tính mới. Nếu đến ngày nộp vẫn 0%, đề tài sẽ bị đọc
  đúng như rủi ro mục 11 của đề bài: "làm lại PathBench/Arena bản nhỏ".
- **(c) Bổ sung mới:** trước khi nói bất cứ điều gì về "so sánh thuật
  toán", phải có ≥2 thuật toán chạy được ngay. Đợt 0 (RRT*) tốn ~1 ngày
  và gỡ được câu hỏi khó chịu nhất mà người chấm chắc chắn sẽ hỏi.

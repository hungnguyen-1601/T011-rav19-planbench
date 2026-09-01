# Plan — Khôi phục giao thức đánh giá P01–P05 & hoàn thiện MVP

> **Lập ngày:** 2026-08-04. **Trạng thái: CHỜ APPROVE, chưa triển khai.**
> **Nguồn:** tách ra từ mục 5 của
> `docs/antongduy/notes/2026-08-04/tongduyan_danh-gia-lai-hien-trang.md`,
> viết chi tiết thêm và **gộp luôn 2 plan đang treo** ở
> `docs/antongduy/plans/2026-08-03/scenario-editor-va-replanning-cong-bang.md`
> vào cùng hệ thống đợt.
> **Đề bài đối chiếu:** `docs/antongduy/phan-tich-de-bai-benchmark-planning.md`.
> **HEAD lúc lập plan:** `9807db5 sql`. Test baseline: `1085 passed, 4 skipped`.

---

## 0. Nguyên tắc sắp xếp

1. Theo đúng **"thứ tự không được cắt"** của đề bài mục 10:
   *không bao giờ cắt P02 và P04*. Chúng lên Đợt 1.
2. Việc nào **gỡ được câu hỏi khó chịu nhất khi bị chấm** mà tốn ít nhất
   thì lên trước — đó là Đợt 0.
3. Việc nào **đụng cùng một file** thì gộp một đợt, tránh sửa 2 lần
   (ví dụ: `MapCanvas.tsx` bị cả Plan A lẫn F08 đụng → làm 1 lần).
4. Mỗi mục phải có **kiểm chứng chạy được**, không nhận "code xong" làm
   bằng chứng hoàn thành.

### Bảng đợt

| Đợt | Nội dung | Ước lượng | Chặn cái gì phía sau |
|---|---|---|---|
| **0** | RRT\* + chạy Docker thật | ~1,5 ngày | Không chặn gì, nhưng gỡ 2 rủi ro demo lớn nhất |
| **1** | **P02** + **P04** | ~3–4 ngày | Chặn Đợt 2 (P03 cần bootstrap CI), Đợt 3 (biểu đồ cần CI để vẽ) |
| **2** | **P05** + **P03** + **Plan A (Scenario Editor)** | ~4–5 ngày | Chặn Đợt 3 (đường cong độ khó cần nhãn difficulty) |
| **3** | **F09** (biểu đồ + export) + **F05** (sửa metric) | ~3–4 ngày | Nơi P03/P04 lần đầu *nhìn thấy được* |
| **4** | **Plan B (Replanning)** + F01 + F08 | ~4–5 ngày | — |
| **5** | **P01** (Optuna) + F16/F17/F23 + dọn dẹp | ~4 ngày | — |

### Sơ đồ phụ thuộc

```
Đợt 0 (RRT*, docker) ──── độc lập, làm bất cứ lúc nào ────┐
                                                          │
Đợt 1 ── P02 (observation_class) ─────────────────────────┤
      └─ P04 (statistics.py: median/IQR/bootstrap/Wilcoxon)┤
              │                                           │
              ├──► Đợt 2 ── P05 (dev/holdout split)        │
              │          └─ P03 (difficulty calibration) ──┤ cần bootstrap CI của P04
              │          └─ Plan A (Scenario Editor) ──────┤ công cụ tạo scenario lấp dải difficulty
              │                                           │
              └──► Đợt 3 ── F09 (biểu đồ + export MD) ◄────┘ vẽ CI (P04) + đường cong difficulty (P03)
                         └─ F05 (Σ(Δθ)², p95, stop-and-go, peak mem)
                                    │
                                    ▼
                         Đợt 4 ── Plan B (Replanning) ── đụng cùng episode_metrics.py, làm SAU F05
                                └─ F01 (map loader PGM/YAML)
                                └─ F08 (replay scrubbing + vẽ vật cản) ── tái dùng MapCanvas của Plan A
                                    │
                                    ▼
                         Đợt 5 ── P01 (Optuna) ── tune trên tập dev của P05, ngân sách bằng nhau
                                └─ F16 parallel, F17 regression guard, F23 sensor noise
```

**Thứ tự cắt phạm vi khi thiếu thời gian** (cắt từ dưới lên, theo đề bài
mục 10): Đợt 5 → Đợt 4 → F09 export (giữ biểu đồ) → Plan A → P03 →
**dừng, không cắt tiếp**. P02 và P04 (Đợt 1) và RRT\* (Đợt 0) là sàn
tuyệt đối.

---

# Đợt 0 — Chặn máu

Hai việc độc lập nhau, làm được song song, không phụ thuộc gì.

## 0.1. Cài RRT\* thật

### Vì sao đây là việc số 1

Registry hiện có 3 stack nhưng **chỉ 1 chạy được ngay sau khi clone**:

| Stack | `benchmarkable` | Điều kiện chạy thật |
|---|---|---|
| `astar+dwa` | ✅ | Chạy ngay |
| `astar+ppo` | ✅ | Cần `torch`+`gymnasium`+`sb3` (optional, vài GB) **và** `requires_model=True` — phải có checkpoint đã train |
| `astar+pure_pursuit` | ❌ | `benchmarkable=False`, cấm dùng để kết luận |

Một nền tảng benchmark so sánh thuật toán mà demo sạch chỉ so được
`astar+dwa` với chính nó ở seed khác nhau — đây là câu hỏi đầu tiên
người chấm sẽ hỏi. RRT\* là thuần Python + numpy, **không thêm
dependency nào**, và đề bài F04 gọi đích danh nó.

### Hợp đồng đã có sẵn, không cần sửa gì

`packages/planning/planbench_planning/common/base.py`:

```python
class GlobalPlanner(ABC):
    @abstractmethod
    def plan(self, grid: OccupancyGrid, start: Point2D, goal: Point2D) -> PlanResult: ...
```

`PlanResult` có sẵn đủ trường RRT\* cần: `success`, `path`,
`path_length`, `cost`, `planning_time_seconds`, `expanded_nodes`,
`failure_reason`. Grid truyền vào **đã inflate theo bán kính robot**
(docstring `GlobalPlanner` ghi rõ) — RRT\* chỉ cần kiểm tra collision
theo ô lưới, không tự lo footprint.

### Thay đổi

1. **File mới** `packages/planning/planbench_planning/rrt_star/planner.py`
   + `__init__.py`, theo đúng bố cục `astar/`.
2. `RRTStarConfig` (Pydantic, `frozen=True`) — khai báo trước để Đợt 5
   (Optuna) có sẵn không gian tham số:
   - `max_iterations: int = 3000`
   - `step_size: float = 0.5` (mét)
   - `goal_sample_rate: float = 0.05`
   - `rewire_radius: float = 1.5` (mét)
   - `goal_tolerance: float = 0.3` (mét)
   - `seed: int = 0`
3. **Tính xác định là ràng buộc cứng.** Docstring `GlobalPlanner` ghi
   "Planners must be deterministic for identical inputs". RRT\* ngẫu
   nhiên, nên **bắt buộc** dùng `numpy.random.Generator` khởi tạo từ
   `config.seed`, **không** dùng `random` module toàn cục (state toàn
   cục sẽ phá tính tái lập khi chạy nhiều episode trong 1 tiến trình).
   Ghi rõ trong docstring: "deterministic *given the config seed*".
4. Đăng ký 2 stack mới trong `registry.py`:
   `rrt_star+dwa` và `rrt_star+pure_pursuit` (cái sau
   `benchmarkable=False`, giống `astar+pure_pursuit`).
   → Sau bước này: **2 stack benchmarkable chạy ngay**, không cần cài
   thêm gì.
5. `expanded_nodes` = số node đã thêm vào cây (tương đương ý nghĩa với
   A*), để chỉ số này so sánh được giữa 2 global planner.

### Điểm dễ sai — phải xử lý

- **Seed của RRT\* vs seed của benchmark.** `BenchmarkSpec.seeds` điều
  khiển vật cản động; `RRTStarConfig.seed` điều khiển cây ngẫu nhiên.
  Nếu để `RRTStarConfig.seed` cố định thì mọi episode dùng chung 1 cây
  → mất hoàn toàn ý nghĩa "RRT\* là thuật toán ngẫu nhiên, cần nhiều
  seed" mà đề bài nhấn mạnh (phụ lục, mục "Seed"). **Quyết định: seed
  của planner phải được dẫn xuất từ seed episode**, ví dụ
  `rng = np.random.default_rng(config.seed ^ episode_seed)`. Cần kiểm
  tra `nav_stack.py`/`runner.py` xem episode seed có được truyền xuống
  global planner không — nếu chưa, phải thêm đường truyền. **Đây là
  phần việc kỹ thuật thật, không phải chi tiết phụ**, và nó là lý do
  RRT\* đắt hơn "copy A* rồi sửa".
- `conditions_checksum` **không** hash config thuật toán (chỉ hash map +
  scenario + seeds) — đúng thiết kế, vì checksum để xác nhận *cùng điều
  kiện*, còn thuật toán là biến độc lập. Không cần sửa.

### Test — `tests/test_rrt_star.py`

Theo pattern `tests/test_astar.py`:
- Map trống: tìm được đường, `path[0] ≈ start`, `path[-1]` trong
  `goal_tolerance`.
- Có tường chắn: đường không đi qua ô occupied (kiểm từng đoạn, không
  chỉ từng đỉnh).
- Không có đường: `success=False`, `failure_reason` không rỗng, không
  raise.
- **Tái lập:** cùng `(grid, start, goal, seed)` → 2 lần chạy ra path
  **giống hệt** (so sánh từng điểm).
- **Khác seed → khác path** (chứng minh tính ngẫu nhiên còn thật, chưa
  bị vô tình khử).
- **Tính chất RRT\*:** tăng `max_iterations` từ 500 lên 5000 →
  `path_length` **không tăng** (asymptotic optimality). Đây là test
  phân biệt RRT\* thật với RRT thường.

### Kiểm chứng

Chạy benchmark thật `astar+dwa` vs `rrt_star+dwa` trên `narrow_corridor`
và `doorway`, 5 seed, xem bảng so sánh trên web ra 2 hàng số khác nhau.
Xem replay của `rrt_star+dwa` — đường phải "gấp khúc kiểu sampling", rõ
ràng khác đường A*.

---

## 0.2. Chạy `docker compose up` thật một lần

### Vì sao

`docs/IMPLEMENTATION_STATUS.md` tự thừa nhận "chưa chạy Docker lần nào
và chưa kết nối PostgreSQL thật". `docker-compose.yml` có 4 service
(`db`, `migrate`, `api`, `web`) + healthcheck + `depends_on` — viết
đúng nhưng **zero bằng chứng chạy được**. Đây là rủi ro "demo sập tại
chỗ" lớn nhất còn tồn.

### Việc cần làm

1. `docker compose build` rồi `docker compose up`, sửa lỗi phát sinh
   cho tới khi cả 4 service healthy.
2. Kiểm tra `migrate` chạy đúng thứ tự trước `api` (Alembic lên
   PostgreSQL thật, không phải SQLite).
3. Vào web, đăng nhập, chạy 1 benchmark nhỏ (1 scenario × 1 stack ×
   3 seed) end-to-end.
4. Lưu log làm bằng chứng vào
   `docs/antongduy/reports/<ngày>/tongduyan_docker-compose-chay-that.md`.
5. Cập nhật `docs/IMPLEMENTATION_STATUS.md` và `KNOWN_LIMITATIONS.md`
   xóa mục "chưa chạy Docker".

### Kiểm chứng

`docker compose ps` cho thấy 4 service `healthy`; ảnh chụp 1 benchmark
chạy xong trong stack container; log migrate hiện các revision Alembic.

---

# Đợt 1 — Khôi phục differentiator (P02 + P04)

Đề bài mục 10 nói thẳng: **"Không bao giờ cắt P02 và P04 — chúng gần
như miễn phí và là toàn bộ lý do dự án này khác với ba nền tảng ở mục 0."**
Hiện cả hai đều 0%.

## 1.1. P02 — Khai báo cân bằng thông tin (`observation_class`)

### Phát hiện quan trọng — sửa lại nhận định của báo cáo cũ

Báo cáo cũ viết: *"DWA (lidar-only) và PPO (35-dim gồm cả vị trí) thực
chất khác lớp quan sát"*. **Đọc code thì điều này SAI.**

`packages/schemas/planbench_schemas/episode.py:64` —
`class Observation` có docstring *"What a local planner may see at one
step (no ground-truth map)"*, và các trường chỉ gồm: `time`, `pose`,
`linear_velocity`, `angular_velocity`, `goal_distance`, `goal_bearing`,
`lidar_ranges`. **Không có vị trí vật cản.**

`ml/planbench_rl/observation.py` docstring: *"The policy sees only what
the robot could sense: LiDAR, its own state and the global path it was
given. Ground-truth obstacle poses are never included — that would let a
policy cheat in a way no real robot can."*

`packages/planning/planbench_planning/dwa/planner.py` docstring:
*"Obstacles come from the LiDAR scan in the observation, not from the
ground-truth map."*

→ **Cân bằng thông tin đã đúng sẵn ở tầng local planner, và được
schema `Observation` cưỡng chế về mặt cấu trúc.** Đây là điểm mạnh thật
của dự án so với Alyassi et al. (lỗ hổng S1: baseline được đặc quyền
xem toàn bộ vị trí người).

**Nhưng P02 vẫn chưa đạt**, vì P02 không phải "có công bằng không" mà là
**"có khai báo và kiểm chứng được là công bằng không"**. Hiện không có
trường nào ghi lại điều này, không có test nào chặn ai đó tương lai thêm
một planner đọc lén ground truth, và báo cáo không nhóm theo lớp quan
sát. Việc cần làm vì vậy **rẻ hơn dự tính, và cho phép tuyên bố mạnh
hơn dự tính**.

### Thiết kế: stack có HAI tầng, cần HAI trường

Benchmark so sánh *stack* (global + local, decision D13 trong
`local_base.py`). Hai tầng thấy hai thứ khác nhau:

- **Global planner** (A\*, RRT\*) nhận `OccupancyGrid` — thấy **toàn bộ
  bản đồ tĩnh** đã inflate. Không thấy vật cản động (xác nhận:
  `plan_global_path()` chỉ rasterize `scenario.static_obstacles`).
- **Local planner** (DWA, PPO, pure-pursuit) nhận `Observation` —
  **chỉ LiDAR + trạng thái bản thân + global path**.

Vậy một trường duy nhất sẽ nói dối. Thêm **hai** trường vào
`AlgorithmInfo` (`packages/benchmark/planbench_benchmark/registry.py:126`):

```python
ObservationClass = Literal[
    "full_static_map",   # thấy toàn bộ bản đồ tĩnh (global planner)
    "lidar_only",        # chỉ LiDAR + trạng thái bản thân
    "human_states",      # thấy vị trí ground-truth của vật cản động
    "lidar+human_states",
]

class AlgorithmInfo(BaseModel):
    ...
    global_observation_class: ObservationClass
    local_observation_class: ObservationClass
    requires_global_path: bool
```

Điền cho 5 stack (sau Đợt 0):

| Stack | global | local | `requires_global_path` |
|---|---|---|---|
| `astar+dwa` | `full_static_map` | `lidar_only` | true |
| `astar+ppo` | `full_static_map` | `lidar_only` | true |
| `astar+pure_pursuit` | `full_static_map` | `lidar_only` | true |
| `rrt_star+dwa` | `full_static_map` | `lidar_only` | true |
| `rrt_star+pure_pursuit` | `full_static_map` | `lidar_only` | true |

Hiện **mọi stack cùng lớp** — đó chính là kết quả tốt và là thứ đáng
đem đi báo cáo. Trường này tồn tại để (a) chứng minh được điều đó,
(b) bắt buộc bất kỳ planner nào thêm sau này phải khai báo, (c) khi
nào có planner `human_states` thật thì leaderboard tự tách nhóm.

### Thay đổi

1. `registry.py`: thêm `ObservationClass` + 3 trường vào `AlgorithmInfo`,
   điền cho toàn bộ entry. **Không đặt giá trị mặc định** cho 2 trường
   observation — buộc mọi entry mới phải khai báo tường minh (đây là
   toàn bộ điểm của P02; một default sẽ khiến người thêm planner mới im
   lặng bỏ qua).
2. `AlgorithmAggregate` (`spec.py`) + `LeaderboardEntry`
   (`apps/api/planbench_api/leaderboard.py:41`): mang theo 2 trường này.
3. `build_leaderboard()`: **nhóm theo `(conditions_checksum,
   local_observation_class)`** thay vì chỉ `conditions_checksum`. Cho
   phép xem chéo lớp nhưng response phải kèm cờ
   `cross_observation_class_warning: bool`.
4. `apps/web/src/app/leaderboard/page.tsx`: hiện nhãn lớp quan sát cho
   mỗi hàng; hiện banner cảnh báo khi bảng đang trộn lớp.
5. `apps/web/src/lib/types.ts`: cập nhật `AlgorithmInfo` /
   `LeaderboardEntry`.
6. Cập nhật `docs/API_CONTRACT.md`.

### Test

- Test khẳng định **mọi entry trong `ALGORITHMS` đều có 2 trường
  observation không rỗng** — đây là test bảo vệ giao thức, chặn hồi quy
  khi ai đó thêm planner mới.
- Test: 2 stack khác `local_observation_class` không rơi chung 1 nhóm
  xếp hạng mặc định; khi ép xem chung thì
  `cross_observation_class_warning=True`.
- **Test chống gian lận thông tin:** khẳng định `Observation` không có
  trường nào chứa vị trí vật cản (kiểm tên field), và
  `LocalPlanner.compute()` chỉ nhận `(RobotState, Observation)`. Test
  này biến thiết kế tốt hiện tại thành **cam kết được kiểm chứng tự
  động**, thay vì một sự thật ngẫu nhiên có thể bị phá âm thầm.

### Kiểm chứng

Mở `/leaderboard`, thấy cột lớp quan sát; thêm tay 1 entry giả có
`local_observation_class="human_states"` trong test → thấy nhóm tách ra
và banner cảnh báo hiện lên.

---

## 1.2. P04 — Quy trình thống kê

### Quyết định: dùng numpy thuần, KHÔNG thêm scipy

Lý do:
- Bootstrap 1000× trên vài trăm mẫu là `rng.choice` + `np.percentile` —
  numpy thuần, khoảng 15 dòng.
- Wilcoxon signed-rank cho mẫu ghép cặp: rank + thống kê W + xấp xỉ
  chuẩn có hiệu chỉnh liên tục — khoảng 40 dòng, kiểm chứng được bằng
  bảng giá trị đã biết.
- `requirements.txt` của dự án ghim `==` và có comment giải thích triết
  lý "dependency của benchmark không được trôi âm thầm". Thêm scipy
  (kéo theo cả một stack build) đi ngược tinh thần đó cho ~60 dòng code.
- **Nếu team thấy rủi ro tự cài test thống kê sai** thì đảo lại: thêm
  `scipy==1.14.*` và dùng `scipy.stats.wilcoxon` + `scipy.stats.bootstrap`.
  **Đây là điểm cần dev quyết lúc approve.**

### Thay đổi

**File mới** `packages/metrics/planbench_metrics/statistics.py`:

```python
def median_iqr(values: Sequence[float]) -> tuple[float, float, float]:
    """Trả (median, q1, q3). Đề bài 8.6(a): dữ liệu robot lệch phải mạnh."""

def bootstrap_ci(
    values: Sequence[float], *, statistic=np.median, n_resamples: int = 1000,
    level: float = 0.95, seed: int = 0,
) -> tuple[float, float]:
    """CI percentile bootstrap. seed cố định → CI tái lập được."""

def wilcoxon_signed_rank(a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    """Ghép cặp theo seed. Trả (statistic, p_value)."""

def cliffs_delta(a: Sequence[float], b: Sequence[float]) -> float:
    """Effect size phi tham số, [-1, 1]. Hợp dữ liệu lệch hơn Cohen's d."""

def average_rank_score(per_scenario_ranks: Mapping[str, Sequence[int]]) -> dict[str, float]:
    """Xếp hạng tổng hợp nhiều kịch bản (đề bài 8.6a: KHÔNG trung bình
    các chỉ số khác đơn vị)."""
```

**Ràng buộc thiết kế bắt buộc:** mọi hàm ngẫu nhiên nhận `seed` tường
minh. Một CI bootstrap không tái lập được thì mâu thuẫn với chính trụ
*reproducibility* của đề bài.

**Ghép cặp theo seed cho Wilcoxon.** `BenchmarkSpec` chạy *cùng bộ
seed* cho mọi thuật toán, nên hai thuật toán có mẫu ghép cặp tự nhiên
theo seed → dùng **signed-rank** (đúng), không dùng Mann-Whitney. Phải
assert 2 danh sách cùng độ dài và cùng thứ tự seed trước khi tính,
raise nếu không — sai chỗ này là sai âm thầm.

**Sửa `AlgorithmAggregate` (`spec.py:138`)** — thêm bên cạnh, không xóa:

```python
median_travel_time_successful: float | None = None
iqr_travel_time_successful: tuple[float, float] | None = None
ci95_travel_time_successful: tuple[float, float] | None = None
# ... tương tự cho path_efficiency, smoothness, min_clearance
ci95_success_rate: tuple[float, float] | None = None   # bootstrap trên biến nhị phân
```

Giữ nguyên `mean_*` trong **cùng một commit** để frontend/test không vỡ;
đánh dấu deprecated trong docstring; gỡ ở commit riêng sau khi UI đã
chuyển sang median.

**File mới** `packages/benchmark/planbench_benchmark/comparison.py`:
`compare_algorithms(report) -> ComparisonResult` — chọn thuật toán tốt
nhất theo success rate, chạy Wilcoxon + Cliff's delta so nó với **từng**
thuật toán còn lại (đúng đề bài P04), trả `p_value` + `effect_size` +
`significant: bool` cho mỗi cặp.

**Cảnh báo số seed** — `BenchmarkSpec.seeds` giữ `min_length=1`:
- Cấm cứng `< 30` sẽ phá toàn bộ test hiện có và làm việc thử nhanh trở
  nên khổ sở.
- Thay vào đó: `BenchmarkReport.statistically_valid: bool` =
  `len(seeds) >= 30`, và **UI phải hiện cảnh báo đỏ** ở trang benchmark
  detail + leaderboard khi cờ này `False`; báo cáo export cũng phải in
  cảnh báo. Đạt đúng mục tiêu đề bài mà không phá gì.

### Test — `tests/test_statistics.py` (mới)

Dữ liệu tổng hợp có đáp án biết trước, seed cố định:
- Phân phối lệch phải (lognormal): assert `median < mean` rõ rệt →
  chứng minh vì sao đề bài đòi median.
- `bootstrap_ci` trên mẫu từ phân phối đã biết: CI phủ giá trị thật;
  chạy 2 lần cùng seed ra **CI giống hệt**.
- `wilcoxon_signed_rank`: 2 phân phối tách rời → `p < 0.05`; 2 mẫu cùng
  phân phối → `p > 0.05`. Đối chiếu thêm với **ít nhất 1 ví dụ có bảng
  giá trị chuẩn** trong sách thống kê để chắc công thức không sai.
- `cliffs_delta`: mẫu giống hệt → ≈ 0; tách hoàn toàn → ≈ ±1.
- `average_rank_score`: ví dụ tay 3 thuật toán × 3 kịch bản, tính tay
  đáp án, so khớp.
- Ghép cặp: gọi Wilcoxon với 2 list khác độ dài → phải raise.

### Kiểm chứng

Chạy benchmark thật `astar+dwa` vs `rrt_star+dwa` trên `doorway`,
**30 seed**, xem bảng ra median + IQR + CI95 và một dòng kết luận dạng
*"astar+dwa nhanh hơn rrt_star+dwa, p = 0.003, Cliff's δ = 0.62"*.
Chạy lại 1 seed → thấy cảnh báo đỏ "không đủ mẫu thống kê".

---

# Đợt 2 — P05, P03 và công cụ tạo kịch bản

## 2.1. P05 — Tập held-out & generalization gap

Làm trước P03 vì rẻ hơn nhiều và P03 sẽ dùng luôn nhãn split.

### Thay đổi

1. `packages/schemas/planbench_schemas/scenario.py`: thêm
   `split: Literal["dev", "holdout"] = "dev"` vào `Scenario`.
   ⚠️ **Trường này tự động đi vào `_scenario_checksum()`** (nó dump toàn
   bộ scenario trừ `random_seed`/`description`) → đổi split sẽ đổi
   `conditions_checksum`. Đây là **đúng ý muốn** (dev và holdout không
   được trộn bảng), nhưng phải ghi rõ trong `KNOWN_LIMITATIONS.md`: mọi
   benchmark cũ sẽ có checksum khác sau thay đổi này.
2. Gán nhãn 10 kịch bản có sẵn (`scenarios.py:305`). Đề xuất **7 dev /
   3 holdout**, chọn holdout là 3 cái **khác họ nhất** so với phần dev —
   không phải 3 cái khó nhất, vì mục tiêu là đo *generalization*, không
   phải đo *độ khó*:
   - **holdout:** `bidirectional_corridor` (duy nhất có 2 luồng ngược
     chiều), `intersection` (duy nhất có giao cắt), `dynamic_warehouse`
     (duy nhất nhiều vật cản động hỗn hợp).
   - **dev:** 7 cái còn lại.
3. `BenchmarkReport`: thêm `generalization_gap: dict[str, float] | None`
   — hiệu `metric_dev − metric_holdout` cho từng chỉ số chính. Chỉ tính
   được khi một lượt chạy phủ cả 2 split.
4. `BenchmarkSpec`: thêm `splits: tuple[Literal["dev","holdout"], ...] = ("dev",)`
   — **mặc định chỉ chạy dev**. Holdout phải được yêu cầu tường minh.
5. **Quy tắc vận hành (ghi vào `docs/` và vào UI):** holdout chỉ chạy
   **một lần, ở cuối**. UI phải cảnh báo khi người dùng chọn holdout:
   *"Mỗi lần xem kết quả holdout là một lần tiêu tốn tính khách quan của
   nó."* Đây là quy tắc con người, không cưỡng chế được bằng code —
   nhưng phải hiện ra, không giấu trong tài liệu.

### Test

- Khẳng định đúng 3 kịch bản mang nhãn `holdout` (test này cố tình
  "cứng" — đổi nhãn phải là quyết định có ý thức, kèm sửa test).
- `_scenario_checksum` khác nhau giữa 2 scenario chỉ khác `split`.
- `generalization_gap` = `None` khi chỉ chạy 1 split; có giá trị đúng
  khi chạy cả 2 (dựng dữ liệu tay, tính tay).

---

## 2.2. P03 — Hiệu chuẩn độ khó thực nghiệm

### Định nghĩa (đề bài 8.6d)

`difficulty(scenario) = 1 − success_rate(baseline_reference, scenario, 30 seeds)`

`baseline_reference` = **cấu hình ghim version**, đề xuất `astar+dwa`
với config mặc định. Ghim luôn cả:
- `replanning_enabled = False` (mặc định — xem cảnh báo dưới),
- git SHA của lần hiệu chuẩn,
- checksum của map + scenario.

### ⚠️ Tương tác với Plan B (Đợt 4) — phải xử lý

Nếu Đợt 4 bật replanning, `success_rate` của baseline sẽ tăng →
**mọi nhãn difficulty đã hiệu chuẩn trở nên vô hiệu**. Hai lựa chọn:

- **(chọn cái này)** Hiệu chuẩn với `replanning_enabled=False`, ghi rõ
  điều kiện đó vào file hiệu chuẩn. Khi Đợt 4 xong, **chạy lại hiệu
  chuẩn** thành một bộ nhãn thứ hai (`difficulty_replan_on`). Hai bộ
  nhãn tồn tại song song, mỗi báo cáo dùng bộ khớp với chế độ của nó.
- Hoãn P03 tới sau Đợt 4. Không khuyến nghị — P03 chặn Đợt 3 (biểu đồ).

### Thay đổi

1. **Script mới** `scripts/calibrate_difficulty.py`:
   - Với mỗi kịch bản trong `SCENARIO_LIBRARY`: chạy `astar+dwa`,
     30 seed, headless.
   - Tính `difficulty = 1 − success_rate`, kèm **CI95 bootstrap** của
     difficulty (dùng `statistics.py` của Đợt 1 — đây là chỗ P04 chặn P03).
   - Ghi ra `packages/benchmark/planbench_benchmark/difficulty_calibration.json`,
     **có version + git SHA + checksum baseline**, được commit vào git.
2. `Scenario` **không** chứa difficulty (nó là thuộc tính đo được, không
   phải thuộc tính khai báo — nhét vào schema sẽ khiến người ta sửa tay,
   đúng lỗi A2 của Arena 4.0 mà đề bài chỉ trích). Thay vào đó
   `scenarios.py` cung cấp `get_difficulty(name) -> DifficultyLabel | None`
   đọc từ file hiệu chuẩn.
3. `BenchmarkReport`: đính kèm difficulty của kịch bản + version của bộ
   hiệu chuẩn đã dùng.
4. Báo cáo đổi từ *một con số trung bình* sang **đường cong
   `success_rate(difficulty)`** cho từng thuật toán — phần vẽ nằm ở
   Đợt 3 (F09).

### Vấn đề: 10 kịch bản có phủ đều dải 0.0–0.9 không?

Gần như chắc là **không** — chúng được viết tay để minh họa tình huống,
không phải để phủ đều độ khó. Sau khi chạy hiệu chuẩn sẽ biết. Đề bài
8.6(d) yêu cầu **hiệu chuẩn ngược**: chỉnh các trục sinh kịch bản (độ
rộng khe / bán kính robot, mật độ vật cản, mật độ vật cản động, độ
ngoằn ngoèo) để lấp dải còn trống.

→ **Đây chính là lý do Plan A (Scenario Editor) được kéo vào đợt này.**

### Test

- Script chạy được ở chế độ `--dry-run` với 3 seed (cho CI nhanh).
- `get_difficulty` trả `None` gọn gàng khi kịch bản chưa hiệu chuẩn,
  không raise.
- Test khẳng định file hiệu chuẩn có đủ trường version/git SHA/baseline
  checksum — chống việc ai đó sửa tay file JSON.

### Kiểm chứng

Chạy script thật, in bảng 10 kịch bản kèm difficulty + CI. Kiểm bằng
mắt: `open_space` phải gần 0.0, `narrow_corridor`/`dynamic_warehouse`
phải cao hơn hẳn. Nếu **tất cả** đều 0.0 hoặc tất cả đều 1.0 → bộ kịch
bản không phân biệt được thuật toán, đó là phát hiện quan trọng và phải
báo cáo ngay, không giấu.

---

## 2.3. Plan A — Scenario Editor tùy chỉnh

> Plan gốc chi tiết: `docs/antongduy/plans/2026-08-03/scenario-editor-va-replanning-cong-bang.md`,
> mục "Plan A". Phần research trong đó **đã kiểm lại ngày 2026-08-04 và
> vẫn đúng** (chưa có `apps/web/src/app/scenarios/`, `MapCanvas.tsx` vẫn
> không vẽ vật cản nào, `api.ts` vẫn thiếu 4 hàm scenario).

### Vì sao xếp vào Đợt 2 chứ không phải "làm sau khi rảnh"

Ba lý do, đều là lý do kỹ thuật chứ không phải tiện tay:

1. **P03 cần nó.** Muốn lấp dải difficulty còn trống thì phải tạo được
   kịch bản mới nhanh. Hiện tạo kịch bản = viết Python trong
   `scenarios.py`. Với Scenario Editor thì đó là việc vài phút trên web.
2. **P05 cần nó.** Tập holdout đúng nghĩa nên là kịch bản *chưa từng
   thấy*, khác họ với dev. 3 kịch bản holdout lấy từ thư viện có sẵn là
   giải pháp tạm; kịch bản holdout tự soạn mới thì mạnh hơn hẳn.
3. **Backend đã xong 100%.** `routers/scenarios.py` đã có đủ
   `POST/GET/PUT/DELETE /scenarios` + `POST /scenarios/validate`, và
   validate chạy qua **chính engine thật**
   (`ScenarioService.validate_against_map()` gọi
   `SimulationEngine.load_scenario()`). Đây gần như thuần việc frontend
   — tỉ lệ giá trị/công sức rất cao.

### Điều chỉnh so với plan gốc

- **Thêm ô chọn `split` (dev/holdout)** vào form — trường mới của P05
  (mục 2.1). Plan gốc chưa có vì P05 chưa tồn tại lúc đó.
- **Phần vẽ vật cản trong `MapCanvas.tsx` phải làm sao cho F08 (Đợt 4)
  dùng lại được**, không viết riêng cho editor. Cụ thể: prop
  `staticObstacles` / `dynamicObstacles` + một prop `previewTime?: number`
  — editor truyền `undefined` (vẽ hình dạng quỹ đạo tĩnh), replay của
  F08 truyền playhead (vẽ vị trí tại thời điểm đó). Một component, hai
  chỗ dùng. **Nếu bỏ qua điểm này sẽ phải sửa `MapCanvas` hai lần.**

### Các bước còn lại giữ nguyên plan gốc

`types.ts` (7 field thiếu + 10 interface mới) → `api.ts` (4 hàm thiếu) →
`MapCanvas.tsx` (heading cho start/goal + overlay vật cản) →
`scenarios/page.tsx` (danh sách) → `scenarios/[id]/page.tsx` (editor,
`id === "new"` để tạo mới) → locale `en.json`/`vi.json` làm cuối.

Quyết định MVP giữ nguyên: chỉnh hướng bằng **ô nhập số (độ)**, không
làm kéo-chuột-xoay; waypoint đặt bằng **click liên tiếp** trên canvas.

### Kiểm chứng (bổ sung so với plan gốc)

Ngoài 5 mục kiểm chứng của plan gốc, thêm:
6. Dùng editor tạo 2 kịch bản mới nhằm **lấp dải difficulty còn trống**
   mà bước 2.2 phát hiện được; chạy `calibrate_difficulty.py` lại và xác
   nhận 2 kịch bản mới rơi đúng vào khoảng difficulty mong muốn.

---

# Đợt 3 — Làm cho kết quả nhìn thấy được

Đợt 1 và 2 sinh ra CI, p-value, đường cong difficulty, generalization
gap — nhưng **hiện không có chỗ nào hiển thị chúng**: repo có **0 thư
viện biểu đồ** (`package.json` chỉ có next/react/react-dom) và **0 chức
năng export**. Đợt này là nơi công sức Đợt 1–2 lần đầu nhìn thấy được.

## 3.1. F09 — Biểu đồ + xuất báo cáo

1. **Thêm `recharts`** vào `apps/web/package.json` (nhẹ nhất, hợp React
   19, API khai báo). Cân nhắc thay thế: vẽ tay SVG — khả thi cho 3 loại
   biểu đồ dưới đây và giữ zero-dependency, nhưng tốn khoảng 2 ngày
   thay vì nửa ngày. **Điểm cần dev quyết lúc approve.**
2. Ba biểu đồ, đúng ba thứ đề bài đòi:
   - **Đường cong `success_rate(difficulty)`** cho từng thuật toán
     (P03) — đề bài mục 7.0 giải thích rõ vì sao đường cong quan trọng
     hơn số trung bình.
   - **Thanh median + IQR + CI95** cho từng chỉ số (P04).
   - **Biểu đồ generalization gap** dev vs holdout (P05).
3. **Export Markdown** — endpoint mới `GET /benchmarks/{id}/report.md`,
   sinh từ `BenchmarkReport`. Nội dung bắt buộc có:
   - Bảng median/IQR/CI95 (không phải mean).
   - Kết quả Wilcoxon + effect size.
   - Lớp quan sát của từng stack (P02).
   - Nhãn difficulty + version bộ hiệu chuẩn (P03).
   - Generalization gap nếu có (P05).
   - **Cảnh báo in đậm khi `statistically_valid == False`**.
   - `conditions_checksum`, git SHA, danh sách seed — để tái lập.
   PDF để sau (in từ trình duyệt là đủ cho MVP).

## 3.2. F05 — Sửa Metrics Engine cho khớp đề bài

`packages/metrics/planbench_metrics/episode_metrics.py`:

| Việc | Hiện tại | Đề bài | Cách làm |
|---|---|---|---|
| Smoothness | `Σ\|Δθ\| / L` (dòng 88) | `S = Σ(Δθ)²` (mục 8.2) | Thêm field **mới** `smoothness_squared`, **giữ** field cũ đổi tên ý nghĩa trong docstring thành `heading_change_rate`. Không xóa — dữ liệu benchmark cũ vẫn đọc được. |
| Latency | chỉ `mean_` / `max_` | p50/p95/**p99** (mục 8.3) | Thêm `local_planning_latency_p50/p95/p99`. Đề bài giải thích rõ: robot 20 Hz, mean 10 ms nhưng p99 200 ms = cứ 100 bước có 1 bước robot đi mù. |
| Peak memory | không có | mục 8.3 | `tracemalloc` quanh vòng episode. ⚠️ có overhead — bật qua cờ, mặc định tắt, và **ghi rõ là đã bật hay chưa** trong report (một con số memory không kèm điều kiện đo thì vô nghĩa). |
| Stop-and-go count | không có | mục 8.5 | Đếm số lần `linear_velocity` xuống dưới ngưỡng rồi lên lại. Ngưỡng phải là **tham số của scenario**, không hard-code — nếu không sẽ thành một dạng bất công bằng ẩn. |
| Near-miss count | không có | mục 8.4 | Số bước có `clearance < ngưỡng cảnh báo`. Đề bài: *"thuật toán 0 va chạm nhưng 50 near-miss là thuật toán đang gặp may"*. |
| Time-to-first-collision | không có | mục 8.4 | Có sẵn trong events, chỉ cần trích ra. |

**Cảnh báo hồi quy:** đổi `AlgorithmAggregate` đụng `leaderboard.py`,
`types.ts`, và nhiều test. Làm theo đúng nguyên tắc "thêm bên cạnh,
không xóa" như Đợt 1.2, gỡ field cũ ở commit riêng.

---

# Đợt 4 — Replanning, map loader, replay

## 4.1. Plan B — Replanning khi bị vật cản động chặn

> Plan gốc chi tiết: `docs/antongduy/plans/2026-08-03/scenario-editor-va-replanning-cong-bang.md`,
> mục "Plan B". Research trong đó **đã kiểm lại ngày 2026-08-04 và vẫn
> đúng** (`Scenario` chưa có `replanning_enabled`; `engine.py` chưa có
> đường hồi sinh episode sau `FINISHED`).

### Vì sao xếp Đợt 4 chứ không sớm hơn

1. **Đụng cùng file với F05.** Plan B sửa `episode_metrics.py`
   (`replan_count`, đổi `global_planning_time`/`expanded_nodes` thành
   tổng dồn). F05 (Đợt 3) cũng sửa file đó. Làm Plan B trước sẽ phải
   sửa hai lần và merge hai cách đổi nghĩa của cùng một field.
2. **Làm hỏng hiệu chuẩn P03** nếu làm trước — xem cảnh báo mục 2.2.
   Làm sau thì chỉ cần chạy lại script hiệu chuẩn, sinh bộ nhãn thứ hai.
3. Nó là **tính năng**, không phải giao thức — theo thứ tự ưu tiên của
   đề bài, giao thức đi trước.

### 3 điều kiện công bằng (đã thống nhất, giữ nguyên)

1. **Replanning là thuộc tính của stack, áp dụng đều mọi thuật toán** →
   cắm vào `nav_stack.py::run_stack()` (nơi mọi stack đều đi qua),
   **tuyệt đối không** cắm vào `dwa/planner.py` hay file của một thuật
   toán.
2. **Trigger dùng ngưỡng chung, hash vào `conditions_checksum`** →
   `replanning_enabled` và `max_replans` là field của **`Scenario`**,
   không phải config per-algorithm. Nhờ vậy chúng tự động vào
   `_scenario_checksum()` (hàm này dump toàn bộ scenario trừ
   `random_seed`/`description`) — hai report cùng checksum chắc chắn
   cùng luật replan, **không cần viết thêm dòng code nào** để đảm bảo.
3. **Tham số replan không được tune riêng** → MVP không đưa
   `max_replans` vào Optuna. Nếu sau này muốn, phải vào chung
   `SEARCH_SPACES` với cùng ngân sách (Đợt 5).

### Hai rủi ro kỹ thuật đã xác định

- **Replan ngây thơ sẽ vô dụng.** `plan_global_path()` chỉ rasterize
  `scenario.static_obstacles` — **không biết vật cản động ở đâu**. Gọi
  lại y hệt sẽ ra đúng đường cũ. **Bắt buộc** phải rasterize vị trí vật
  cản động *hiện tại* vào grid trước khi gọi lại global planner. Đây là
  phần việc cốt lõi, không phải chi tiết phụ.
- **Cửa sổ phát hiện stuck phải được reseed.** `_check_termination()`
  dùng `_sample_at_age()` trên `_window`. Nếu chỉ set
  `_state = RUNNING` mà không xóa mẫu cũ, điều kiện STUCK sẽ kích hoạt
  lại **ngay bước kế tiếp**. Method recover mới bắt buộc reseed cửa sổ,
  không chỉ đổi state.

### Điều chỉnh so với plan gốc

- **RRT\* giờ đã tồn tại (Đợt 0)** → phải test replan với RRT\* nữa,
  không chỉ A\*. RRT\* recompute là một cây ngẫu nhiên mới, khác hẳn A\*
  recompute (nhanh, xác định). Đây là **khác biệt thật giữa hai thuật
  toán**, không phải thiên vị, vì luật trigger giống hệt nhau — nhưng
  phải ghi vào `KNOWN_LIMITATIONS.md`.
- **`replan_count` phải vào `AlgorithmAggregate`** với median + IQR
  (P04 đã có sẵn từ Đợt 1), không chỉ mean.

### Test bắt buộc (giữ nguyên plan gốc)

- **Test "tiền đề"** — chứng minh feature có giá trị thật, không chỉ
  chạy không lỗi: dựng scenario mà đường global duy nhất bị một vật cản
  động chắn tạm thời đúng lúc robot tới gần. Assert: **tắt**
  `replanning_enabled` → `STUCK`; **bật** → `SUCCESS`.
- Test cửa sổ stuck được reseed đúng (không STUCK lại ngay bước kế).
- Test công bằng: cùng scenario khác algorithm → checksum **giống**;
  đổi `max_replans` → checksum **khác**.
- Test `local_planner.reset()` gọi lại giữa episode an toàn với **cả
  DWA và PPO** (mới xác nhận `PurePursuitLocalPlanner` an toàn).

## 4.2. F01 — Map loader chuẩn `map_server`

Đề bài F01, tuần 1 của roadmap — vẫn thiếu hoàn toàn (`pgm` = 0,
`occupied_thresh` = 0, không có PyYAML). Mọi thứ phía sau (schema, sim,
planner) đều giả định map đã tồn tại sẵn.

- Thêm `PyYAML` vào `requirements.txt`.
- Parser PGM (P2 ASCII + **P5 binary**, bản binary mới là bản
  `map_server` thật sự xuất ra) + PNG, đọc YAML sidecar với đúng các
  khóa `image`, `resolution`, `origin`, `negate`, `occupied_thresh`,
  `free_thresh`.
- Áp đúng semantics ROS: `negate` đảo thang xám; ô là occupied khi
  `(255 − pixel)/255 > occupied_thresh`.
- Endpoint upload map dạng file thay vì JSON.
- Test với file PGM+YAML thật, đối chiếu grid dựng ra với grid dựng bằng
  `_MapBuilder` cho cùng một hình.

## 4.3. F08 — Replay episode đã lưu

- Trang `/simulate` **đã có tua thời gian đầy đủ** (playhead + `seek()` +
  tốc độ 0.25×–8×, `simulate/page.tsx:195-225`). Trang
  `benchmarks/[id]` thì **chưa** — vẫn đặt
  `robotPose = trajectory[trajectory.length - 1]`, tức khung cuối.
- Việc cần làm: tách logic playhead của `/simulate` thành hook dùng
  chung, cho nó chạy trên **mảng trajectory tĩnh** (không WebSocket),
  rồi cắm vào `benchmarks/[id]`.
- Vẽ vật cản động theo thời gian: dùng prop `previewTime` của
  `MapCanvas` **đã thêm ở Plan A (Đợt 2)** — đây là chỗ khoản đầu tư ở
  mục 2.3 được thu hồi.
- Đánh dấu điểm va chạm trên timeline (đề bài F08 yêu cầu rõ).

---

# Đợt 5 — P01 và phần còn lại

## 5.1. P01 — Cân bằng ngân sách tinh chỉnh

- Thêm `optuna` vào `requirements-optional.txt` (chỉ cần khi tune,
  không cần để chạy benchmark → đúng triết lý optional của repo).
- **File mới** `packages/benchmark/planbench_benchmark/tuning.py` với
  `SEARCH_SPACES: dict[str, dict]` — **khai báo trước** không gian tham
  số cho từng stack. Tên và vị trí này đã được plan 2026-08-03 dự trù.
- **Quy tắc bất di bất dịch (đề bài 8.6c):** cùng số trial cho mọi
  planner; **không sửa kiến trúc hay thêm module cho một planner giữa
  chừng vì nó chạy kém** — nếu phải làm, đó là planner mới, đăng ký lại
  từ đầu với ngân sách riêng. Đây chính là lỗ hổng S2 mà đề bài chỉ
  trích ở Alyassi et al.
- Tune **trên tập dev** (P05), đánh giá trên holdout.
- Log toàn bộ lịch sử tìm kiếm; báo cáo kèm **đường cong hiệu năng theo
  ngân sách** — đề bài mục 7.0: *"nếu DWA bão hòa sau 20 lần thử còn RL
  vẫn tăng ở lần 200, đó là thông tin không ai đang báo cáo"*.
- Ngân sách MVP: 30 trial/planner.

## 5.2. Phần còn lại

- **F16 parallel** — `multiprocessing.Pool` ở mức episode. Hiện chỉ có
  `ThreadPoolExecutor` ở mức job, episode vẫn tuần tự. Điều kiện tiên
  quyết: episode phải thật sự thuần hàm theo seed (kiểm bằng test so
  khớp kết quả chạy tuần tự với chạy song song).
- **F17 regression guard** — so kết quả với baseline đã lưu, cảnh báo
  khi tụt. Dùng luôn Wilcoxon của Đợt 1: "tụt" phải là *tụt có ý nghĩa
  thống kê*, không phải lệch một chút do nhiễu.
- **F23 sensor noise** — noise model có seed cho LiDAR (`lidar.py` đã có
  raycasting DDA thật, chỉ thiếu noise).
- **MLflow git SHA** — đề bài F07 yêu cầu rõ, hiện thiếu (`git_sha` = 0
  kết quả).
- **Dọn dẹp:** ghi chú lại commit `2e8a993` (message ghi "Three.js"
  nhưng code là Canvas 2D thuần — `package.json` không có `three`).

---

# Rủi ro của chính bản plan này

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Thêm `split` vào `Scenario` làm đổi `conditions_checksum` của mọi benchmark cũ | Cao | Chấp nhận có chủ ý; ghi vào `KNOWN_LIMITATIONS.md`; làm sớm (Đợt 2) để càng ít dữ liệu cũ bị ảnh hưởng |
| Tự cài Wilcoxon/bootstrap sai công thức → số liệu sai mà trông vẫn hợp lý | **Cao** | Test đối chiếu với **bảng giá trị chuẩn có sẵn**, không chỉ test tính chất. Nếu team không thoải mái, đổi sang scipy — quyết lúc approve |
| Đợt 1–2 kéo dài, không kịp Đợt 3 → có số nhưng không ai nhìn thấy | Trung bình | F09 export Markdown rẻ hơn biểu đồ nhiều; nếu kẹt, làm export trước, biểu đồ sau |
| RRT\* seed không được truyền xuống → mọi episode dùng chung 1 cây | Trung bình | Đã nêu ở mục 0.1; test "khác seed → khác path" bắt được lỗi này |
| 10 kịch bản không phủ được dải difficulty → P03 ra bảng vô nghĩa | Trung bình | Plan A (Đợt 2) là công cụ lấp dải; nếu Plan A trượt, chấp nhận báo cáo dải hẹp và **nói rõ** giới hạn |
| Sửa `AlgorithmAggregate` nhiều lần (Đợt 1, 3, 4) gây vỡ frontend/test | Trung bình | Nguyên tắc "thêm bên cạnh, không xóa"; gỡ field cũ ở commit riêng sau khi UI đã chuyển |

---

# Điểm cần dev quyết lúc approve

1. **P04: numpy thuần hay scipy?** Plan đề xuất numpy thuần (~60 dòng,
   giữ dependency mỏng đúng triết lý `requirements.txt`). Đổi lại là
   rủi ro tự cài sai công thức thống kê.
2. **F09: `recharts` hay tự vẽ SVG?** Plan đề xuất recharts (nửa ngày
   so với ~2 ngày).
3. **Tập holdout:** chấp nhận đề xuất 7 dev / 3 holdout
   (`bidirectional_corridor`, `intersection`, `dynamic_warehouse`)?
4. **Có làm Đợt 5 (P01/Optuna) không**, hay chấp nhận nêu giới hạn này
   trong báo cáo cuối như đề bài mục 11 cho phép?
5. **Thứ tự Đợt 0:** RRT\* trước hay Docker trước? Hai việc độc lập,
   chia được cho 2 người.

# Plan — Khôi phục giao thức đánh giá P01–P05 & hoàn thiện MVP

> **Lập ngày:** 2026-08-04.  
> **Trạng thái:** CHỜ APPROVE, chưa triển khai.
>
> **Nguồn:** tách ra từ mục 5 của  
> `docs/antongduy/notes/2026-08-04/tongduyan_danh-gia-lai-hien-trang.md`,  
> viết chi tiết thêm và gộp 2 plan đang treo ở  
> `docs/antongduy/plans/2026-08-03/scenario-editor-va-replanning-cong-bang.md`.
>
> **Đề bài đối chiếu:**  
> `docs/antongduy/phan-tich-de-bai-benchmark-planning.md`.
>
> **HEAD lúc lập plan:** `9807db5 sql`.  
> **Test baseline:** `1085 passed, 4 skipped`.
>
> **Phạm vi approve hiện tại:** chỉ Đợt 0 đến Đợt 3.  
> Đợt 4 và các phần P01/Optuna, parallel execution, regression guard, sensor noise phải được review và approve riêng trước khi triển khai.
>
> **Ngoài phạm vi:** plan này không approve hoặc thay đổi mô hình role `Engineer/Approver`. RBAC và workflow review benchmark phải có plan riêng.

---

# 0. Nguyên tắc sắp xếp

1. Theo đúng thứ tự ưu tiên của đề bài: **không cắt P02 và P04**.
2. Việc nào giải quyết câu hỏi lớn khi demo với chi phí thấp thì làm trước.
3. Việc nào đụng cùng file thì có thể gộp cùng đợt để giảm conflict.
4. Không gộp quá nhiều tính năng độc lập vào một đợt.
5. Mỗi mục phải có:
   - code;
   - test;
   - kiểm chứng qua API, web hoặc Docker;
   - báo cáo kết quả;
   - Definition of Done rõ ràng.
6. Không chấp nhận “code xong” nếu chưa chạy kiểm chứng.
7. Không xóa field cũ trong cùng commit khi thêm metric hoặc schema mới.
8. Mọi thành phần ngẫu nhiên phải nhận seed tường minh.
9. Không tự cài lại thuật toán thống kê chuẩn nếu thư viện đáng tin cậy đã có.
10. Không triển khai đợt tiếp theo trước khi đợt hiện tại được nghiệm thu.

## Bảng đợt

| Đợt    | Nội dung                    | Ước lượng | Trạng thái approve                              |
| ------ | --------------------------- | --------: | ----------------------------------------------- |
| **0**  | RRT\* + chạy Docker thật    | ~1,5 ngày | Có thể approve                                  |
| **1**  | P02 + P04                   | ~3–4 ngày | Có thể approve sau khi dùng SciPy               |
| **2**  | P05 + P03 + Scenario Editor | ~4–5 ngày | Có thể approve sau khi tách split khỏi Scenario |
| **3**  | F09 + F05                   | ~3–4 ngày | Có thể approve                                  |
| **4**  | Replanning + F01 + F08      | ~4–5 ngày | Chưa approve, cần review riêng                  |
| **5A** | P01 — Optuna                | ~2–3 ngày | Chưa approve, plan riêng                        |
| **5B** | F16 — Parallel execution    | ~2–3 ngày | Chưa approve, plan riêng                        |
| **5C** | F17 — Regression guard      |   ~2 ngày | Chưa approve, plan riêng                        |
| **5D** | F23 — Sensor noise          |   ~2 ngày | Chưa approve, plan riêng                        |

## Sơ đồ phụ thuộc

```text
Đợt 0 ── RRT* + Docker ───────────────────────────────┐
                                                     │
Đợt 1 ── P02                                         │
       └─ P04 ──────────────┬─────────────────────────┤
                            │                         │
                            ├── Đợt 2 ── P05          │
                            │          ├─ P03          │
                            │          └─ Scenario Editor
                            │                         │
                            └── Đợt 3 ── F09 + F05 ◄──┘

Sau khi Đợt 0–3 hoàn thành và được nghiệm thu:

Đợt 4 ── Replanning + Map Loader + Replay
Đợt 5A ── P01/Optuna
Đợt 5B ── Parallel execution
Đợt 5C ── Regression guard
Đợt 5D ── Sensor noise
```

## Thứ tự cắt phạm vi khi thiếu thời gian

Cắt theo thứ tự:

1. Scenario Editor nâng cao.
2. Biểu đồ nâng cao nhưng vẫn giữ export Markdown.
3. Mở rộng dải difficulty.
4. Dừng cắt.

Không cắt:

- RRT\*;
- Docker verify;
- P02;
- P04;
- metadata dev/holdout tối thiểu;
- export Markdown tối thiểu.

---

# Đợt 0 — Chặn rủi ro demo

Hai việc độc lập, có thể làm song song.

---

## 0.1. Cài RRT\* thật

### Vì sao đây là việc ưu tiên

Registry hiện có các stack:

| Stack                | `benchmarkable` | Điều kiện chạy                          |
| -------------------- | --------------- | --------------------------------------- |
| `astar+dwa`          | Có              | Chạy ngay                               |
| `astar+ppo`          | Có              | Cần Torch, Gymnasium, SB3 và checkpoint |
| `astar+pure_pursuit` | Không           | Chỉ dùng làm reference                  |

Sau khi clone sạch, chỉ `astar+dwa` chạy ngay.

Một nền tảng benchmark nhưng chỉ có một global planner chạy được sẽ khó chứng minh khả năng so sánh thuật toán lập đường đi tổng thể.

RRT\*:

- thuần Python và NumPy;
- không cần checkpoint;
- khác cách tiếp cận với A\*;
- được đề bài nhắc trực tiếp;
- giúp hệ thống có hai global planner thực sự.

### Hợp đồng đã có

`packages/planning/planbench_planning/common/base.py`:

```python
class GlobalPlanner(ABC):
    @abstractmethod
    def plan(
        self,
        grid: OccupancyGrid,
        start: Point2D,
        goal: Point2D,
    ) -> PlanResult:
        ...
```

`PlanResult` đã có:

- `success`;
- `path`;
- `path_length`;
- `cost`;
- `planning_time_seconds`;
- `expanded_nodes`;
- `failure_reason`.

Grid truyền vào đã được inflate theo bán kính robot.

### Thay đổi

Tạo:

```text
packages/planning/planbench_planning/rrtstar/
├── __init__.py
└── planner.py
```

Cấu hình:

```python
class RRTStarConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_iterations: int = 3000
    step_size: float = 0.5
    goal_bias: float = 0.05
    rewire_radius: float = 1.5
    goal_tolerance: float = 0.3
    seed: int = 0
```

RRT\* phải có:

- sampling;
- nearest node;
- steer;
- collision check trên toàn bộ đoạn nối;
- choose-parent;
- rewire;
- kết nối goal;
- tạo `PlanResult`;
- giới hạn số iteration;
- failure reason rõ ràng.

### Tính xác định

RRT\* là thuật toán ngẫu nhiên nhưng phải tái lập được khi cùng seed.

Không dùng random state toàn cục:

```python
random.seed(...)
np.random.seed(...)
```

Sử dụng generator riêng:

```python
rng = np.random.default_rng(effective_seed)
```

### Seed của planner và seed của episode

Phân biệt:

- `episode_seed`: điều khiển vật cản động và yếu tố ngẫu nhiên của scenario;
- `planner_seed`: điều khiển cây RRT\*.

Seed hiệu lực:

```python
effective_seed = config.seed ^ episode_seed
```

Nếu `episode_seed` chưa được truyền xuống global planner thì phải bổ sung đường truyền:

```text
Benchmark runner
    ↓
nav_stack.run_stack()
    ↓
plan_global_path()
    ↓
RRTStarPlanner.plan()
```

### Registry

Đăng ký:

```text
rrtstar+dwa
rrtstar+pure_pursuit
```

Trong đó:

```text
rrtstar+dwa
→ benchmarkable=True
```

```text
rrtstar+pure_pursuit
→ benchmarkable=False
```

Không đăng ký `rrtstar+ppo` cho tới khi kiểm chứng PPO policy tương thích với global path từ RRT\*.

### `expanded_nodes`

`expanded_nodes` bằng số node hợp lệ được thêm vào cây.

Ý nghĩa phải được ghi rõ vì cách đếm này không hoàn toàn giống số node A\* mở rộng.

Không được dùng `expanded_nodes` để kết luận trực tiếp thuật toán nào tốt hơn nếu chưa giải thích khác biệt ngữ nghĩa.

### Test — `tests/test_rrtstar.py`

#### Test 1 — Map trống

- Tìm được đường.
- `path[0]` gần start.
- Điểm cuối nằm trong `goal_tolerance`.
- Path length lớn hơn hoặc bằng khoảng cách Euclidean.

#### Test 2 — Có tường

- Đường không đi qua ô occupied.
- Kiểm tra từng đoạn, không chỉ từng node.
- Không chấp nhận path xuyên góc obstacle.

#### Test 3 — Không có đường

- `success=False`.
- `failure_reason` không rỗng.
- Không raise exception.
- Không chạy vô hạn.

#### Test 4 — Tái lập

Cùng:

- grid;
- start;
- goal;
- config;
- seed;

thì hai lần chạy phải cho:

- cùng trạng thái thành công;
- cùng path;
- cùng path length;
- cùng số node.

#### Test 5 — Khác seed

Chạy nhiều seed trên một map không tầm thường.

Yêu cầu:

- các path đều hợp lệ;
- có ít nhất hai path khác nhau;
- không bắt buộc mọi seed phải thành công.

#### Test 6 — Giới hạn iteration

- Không vượt `max_iterations`.
- Không loop vô hạn.
- Failure được trả rõ ràng khi hết ngân sách.

### Test phải bỏ

Không dùng test cứng:

```text
Tăng max_iterations từ 500 lên 5000
→ path_length bắt buộc không tăng
```

Lý do:

- RRT\* là thuật toán sampling;
- một seed cụ thể có thể không cải thiện đơn điệu;
- test dễ flaky;
- asymptotic optimality là tính chất dài hạn, không phù hợp làm unit test cứng trên một lần chạy.

Thay thế bằng benchmark:

1. Chạy tập seed cố định.
2. So median path length.
3. So success rate.
4. So thời gian lập đường.
5. Ghi kết quả vào report.
6. Không assert từng seed phải tốt hơn.

### Kiểm chứng end-to-end

Chạy:

```text
astar+dwa
rrtstar+dwa
```

Trên:

```text
narrow_corridor
doorway
```

Với tối thiểu 5 seed.

Kiểm tra:

- API trả cả hai stack;
- benchmark có hai hàng kết quả;
- replay hợp lệ;
- RRT\* không xuyên obstacle;
- cùng seed chạy lại cho cùng kết quả;
- khác seed có thể tạo path khác.

### Definition of Done

- [ ] Unit test RRT\* pass.
- [ ] API trả stack mới.
- [ ] Benchmark end-to-end chạy được.
- [ ] Không phá A\*.
- [ ] Không thêm dependency không cần thiết.
- [ ] Không có test asymptotic flaky.
- [ ] Có ghi chú giới hạn trong `KNOWN_LIMITATIONS.md`.

---

## 0.2. Chạy Docker Compose thật

### Vì sao

`docker-compose.yml` có:

- database;
- migration;
- API;
- web;
- health check;
- dependency order.

Nhưng nếu chưa từng chạy thật thì chưa có bằng chứng stack hoạt động.

Đây là rủi ro demo lớn.

### Việc cần làm

Chạy:

```bash
docker compose build
docker compose up
```

Kiểm tra:

```bash
docker compose ps
docker compose logs db
docker compose logs migrate
docker compose logs api
docker compose logs web
```

Sửa lỗi cho tới khi:

- database healthy;
- migration chạy xong;
- API healthy;
- web truy cập được;
- API chỉ khởi động sau migration.

### Kiểm tra end-to-end

1. Mở web.
2. Đăng nhập.
3. Chọn map.
4. Chọn scenario.
5. Tạo benchmark nhỏ.
6. Chạy benchmark.
7. Xem kết quả.
8. Kiểm tra dữ liệu được lưu vào PostgreSQL.

### Lưu bằng chứng

Tạo:

```text
docs/antongduy/reports/<ngày>/tongduyan_docker-compose-chay-that.md
```

Báo cáo gồm:

- kết quả `docker compose ps`;
- log migration;
- log API;
- benchmark đã chạy;
- lỗi gặp phải;
- cách sửa;
- trạng thái cuối.

Cập nhật:

```text
docs/IMPLEMENTATION_STATUS.md
docs/KNOWN_LIMITATIONS.md
```

### Definition of Done

- [ ] Database healthy.
- [ ] Migration hoàn thành.
- [ ] API healthy.
- [ ] Web truy cập được.
- [ ] Benchmark chạy thành công trong container.
- [ ] Dữ liệu được lưu trên PostgreSQL.
- [ ] Có báo cáo verify.

---

# Đợt 1 — Khôi phục differentiator P02 và P04

---

## 1.1. P02 — Khai báo cân bằng thông tin

### Hiện trạng

Local planner nhận `Observation` gồm:

- thời gian;
- pose robot;
- linear velocity;
- angular velocity;
- goal distance;
- goal bearing;
- LiDAR ranges;
- global path.

Local planner không nhận trực tiếp ground-truth obstacle position.

Đây là nền tảng tốt nhưng P02 vẫn chưa đạt vì:

- chưa có metadata chính thức;
- chưa có test chống planner đọc thêm ground truth;
- leaderboard chưa nhóm theo lớp quan sát;
- report chưa ghi thuật toán nhìn thấy dữ liệu gì.

### Stack có hai tầng

Một stack gồm:

1. Global planner.
2. Local planner.

Hai tầng nhìn thấy dữ liệu khác nhau:

- Global planner:
  - nhận full static map;
  - không nhận ground-truth obstacle động.
- Local planner:
  - nhận LiDAR;
  - nhận trạng thái robot;
  - nhận global path;
  - không nhận ground-truth obstacle động.

Vì vậy cần hai field riêng.

### Schema

```python
ObservationClass = Literal[
    "full_static_map",
    "lidar_only",
    "human_states",
    "lidar+human_states",
]
```

Cập nhật:

```python
class AlgorithmInfo(BaseModel):
    ...
    global_observation_class: ObservationClass
    local_observation_class: ObservationClass
    requires_global_path: bool
```

Không đặt default cho observation class.

Planner mới bắt buộc phải khai báo tường minh.

### Giá trị ban đầu

| Stack                  | Global observation | Local observation | Requires global path |
| ---------------------- | ------------------ | ----------------- | -------------------- |
| `astar+dwa`            | `full_static_map`  | `lidar_only`      | true                 |
| `astar+ppo`            | `full_static_map`  | `lidar_only`      | true                 |
| `astar+pure_pursuit`   | `full_static_map`  | `lidar_only`      | true                 |
| `rrtstar+dwa`          | `full_static_map`  | `lidar_only`      | true                 |
| `rrtstar+pure_pursuit` | `full_static_map`  | `lidar_only`      | true                 |

### Backend

Cập nhật:

```text
packages/benchmark/planbench_benchmark/registry.py
packages/benchmark/planbench_benchmark/spec.py
apps/api/planbench_api/leaderboard.py
apps/api/planbench_api/report_markdown.py
```

Mang metadata sang:

- algorithm registry;
- aggregate;
- leaderboard;
- benchmark report;
- export report.

### Leaderboard

Nhóm mặc định theo:

```text
conditions_checksum
local_observation_class
```

Không xếp hạng chung các thuật toán có lớp quan sát khác nhau.

Khi người dùng yêu cầu xem chung:

- vẫn cho phép hiển thị;
- trả warning;
- không đưa ra thứ hạng chung mặc định.

Field cảnh báo:

```python
cross_observation_class_warning: bool
```

### Frontend

Cập nhật:

```text
apps/web/src/lib/types.ts
apps/web/src/lib/benchmarkTypes.ts
apps/web/src/app/leaderboard/page.tsx
```

Hiển thị:

- global observation;
- local observation;
- cảnh báo trộn lớp;
- tooltip giải thích.

### Test

- Mọi registry entry có đủ observation metadata.
- Không có default âm thầm.
- Hai stack khác local observation không vào cùng nhóm mặc định.
- Forced mixed view trả warning.
- `Observation` không có ground-truth obstacle position.
- `LocalPlanner.compute()` không nhận trực tiếp scenario hoặc map.
- API serialization có đủ field.
- Frontend type không lỗi.

### Kiểm chứng

1. Mở `/leaderboard`.
2. Kiểm tra cột observation class.
3. Tạo entry giả trong test có `human_states`.
4. Xác nhận entry bị tách nhóm.
5. Xác nhận warning hiện khi ép xem chung.

### Definition of Done

- [ ] API hiển thị observation class.
- [ ] UI hiển thị observation class.
- [ ] Leaderboard không âm thầm trộn lớp.
- [ ] Report ghi observation class.
- [ ] Test chống hồi quy thông tin pass.
- [ ] Không thay đổi RBAC.

---

## 1.2. P04 — Quy trình thống kê

### Quyết định đã sửa

**Dùng SciPy.**

Không tự viết Wilcoxon signed-rank bằng NumPy.

Lý do:

- thuật toán thống kê dễ cài sai;
- lỗi không nhất thiết gây exception;
- kết quả sai vẫn có thể trông hợp lý;
- SciPy đã được kiểm chứng rộng rãi;
- độ tin cậy của benchmark quan trọng hơn giảm một dependency.

### Dependency

Cập nhật:

```text
requirements.txt
docker/requirements-api.txt
```

Thêm phiên bản SciPy được pin và tương thích với Python, NumPy của repo:

```text
scipy==<compatible-version>
```

Không dùng dependency không pin.

### Module thống kê

Tạo:

```text
packages/metrics/planbench_metrics/statistics.py
```

Các hàm:

```python
def median_iqr(
    values: Sequence[float],
) -> tuple[float, float, float]:
    ...
```

```python
def bootstrap_ci(
    values: Sequence[float],
    *,
    statistic: Callable,
    n_resamples: int = 1000,
    level: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    ...
```

```python
def wilcoxon_compare(
    a: Sequence[float],
    b: Sequence[float],
) -> tuple[float, float]:
    ...
```

```python
def cliffs_delta(
    a: Sequence[float],
    b: Sequence[float],
) -> float:
    ...
```

```python
def average_rank_score(
    per_scenario_ranks: Mapping[str, Sequence[int]],
) -> dict[str, float]:
    ...
```

Sử dụng:

```python
scipy.stats.bootstrap
scipy.stats.wilcoxon
```

### Ràng buộc

Mọi hàm phải xử lý:

- empty input;
- NaN;
- infinity;
- sample khác độ dài;
- sample quá nhỏ;
- toàn bộ difference bằng 0;
- confidence level không hợp lệ;
- bootstrap không đủ dữ liệu.

Không được trả kết quả giả khi dữ liệu không hợp lệ.

### Ghép cặp theo seed

Wilcoxon phải ghép cặp đúng theo seed.

Không được chỉ truyền hai list dựa vào thứ tự hiện có.

Quy trình:

```text
Run của thuật toán A
        ↓
Map seed → metric
        ↓
Run của thuật toán B
        ↓
Map seed → metric
        ↓
Kiểm tra hai tập seed giống nhau
        ↓
Sắp cùng thứ tự seed
        ↓
Gọi scipy.stats.wilcoxon
```

Nếu thiếu seed:

- không tự bỏ qua âm thầm;
- trả warning hoặc lỗi rõ ràng;
- report ghi số cặp thực tế.

### AlgorithmAggregate

Thêm field mới, không xóa field cũ:

```python
median_travel_time_successful: float | None = None
iqr_travel_time_successful: tuple[float, float] | None = None
ci95_travel_time_successful: tuple[float, float] | None = None
```

```python
median_path_efficiency_successful: float | None = None
iqr_path_efficiency_successful: tuple[float, float] | None = None
ci95_path_efficiency_successful: tuple[float, float] | None = None
```

```python
median_smoothness_successful: float | None = None
iqr_smoothness_successful: tuple[float, float] | None = None
ci95_smoothness_successful: tuple[float, float] | None = None
```

```python
ci95_success_rate: tuple[float, float] | None = None
```

Các field mean cũ:

- vẫn được trả trong API;
- được đánh dấu deprecated trong docstring;
- không xóa trong đợt này;
- chỉ xem xét xóa ở API version khác.

### Pairwise comparison

Tạo:

```text
packages/benchmark/planbench_benchmark/comparison.py
```

Schema:

```python
class PairwiseComparison(BaseModel):
    algorithm_a: str
    algorithm_b: str
    metric: str
    statistic: float | None
    p_value: float | None
    effect_size: float | None
    significant: bool
    paired_seed_count: int
    warning: str | None
```

MVP:

- chọn thuật toán có success rate cao nhất;
- so với từng thuật toán còn lại;
- API phải có khả năng mở rộng full pairwise sau này.

### Effect size

P-value không đủ để kết luận mức chênh lệch.

Bổ sung:

```text
Cliff's delta
```

Report phải có:

- p-value;
- effect size;
- paired seed count;
- confidence interval;
- cảnh báo thiếu dữ liệu.

Không dùng câu:

```text
Thuật toán A chắc chắn tốt hơn thuật toán B.
```

Dùng:

```text
Trong tập benchmark và điều kiện đã chạy, A có kết quả cao hơn B.
Chênh lệch có hoặc không có ý nghĩa thống kê theo kiểm định đã chọn.
```

### Cảnh báo số seed

Không chặn benchmark ít seed.

Thêm:

```python
statistically_adequate: bool
seed_count: int
```

Quy tắc:

```text
seed_count < 30
→ vẫn chạy
→ hiện cảnh báo
→ không đưa ra kết luận mạnh
```

```text
seed_count >= 30
→ hiển thị đầy đủ kiểm định
→ vẫn kèm CI và effect size
```

### Test — `tests/test_statistics.py`

#### Median và IQR

- Dữ liệu tính tay.
- Dữ liệu số lượng lẻ.
- Dữ liệu số lượng chẵn.
- Dữ liệu lệch.
- Empty input.

#### Bootstrap

- Cùng seed cho cùng CI.
- CI hợp lệ.
- Confidence level sai phải lỗi.
- Không có NaN âm thầm.
- Đối chiếu với kết quả SciPy trực tiếp.

#### Wilcoxon

- Đối chiếu ví dụ chuẩn.
- Hai sample khác độ dài phải lỗi.
- Thiếu cặp seed phải lỗi hoặc warning.
- Hai sample giống nhau xử lý đúng.
- Đảo thứ tự A/B giữ p-value đúng.
- Không tự tính công thức Wilcoxon.

#### Cliff’s delta

- Hai sample giống nhau gần 0.
- A hoàn toàn lớn hơn B gần 1.
- A hoàn toàn nhỏ hơn B gần -1.

#### Average rank

- Dùng bảng nhỏ tính tay.
- Kết quả phải khớp.

#### Compatibility

- API cũ vẫn deserialize được.
- Field mean cũ vẫn tồn tại.
- Frontend không lỗi khi field mới là `null`.

### Kiểm chứng end-to-end

Chạy:

```text
astar+dwa
rrtstar+dwa
```

Trên ít nhất một scenario khó với:

```text
30 seed
```

Kiểm tra:

- median;
- IQR;
- CI95;
- p-value;
- effect size;
- paired seed count.

Sau đó chạy lại với:

```text
1–5 seed
```

Kiểm tra cảnh báo thiếu dữ liệu.

### Definition of Done

- [ ] Dùng SciPy.
- [ ] Không tự viết Wilcoxon.
- [ ] Ghép cặp đúng theo seed.
- [ ] Có median, IQR và CI.
- [ ] Có effect size.
- [ ] Có warning khi thiếu seed.
- [ ] Field cũ vẫn tồn tại.
- [ ] Test đối chiếu dữ liệu chuẩn.
- [ ] Docker build được với SciPy.

---

# Đợt 2 — P05, P03 và Scenario Editor

---

## 2.1. P05 — Tập held-out và generalization gap

### Quyết định đã sửa

**Không thêm `split` trực tiếp vào `Scenario`.**

Lý do:

- split là metadata của giao thức đánh giá;
- split không phải đặc tính vật lý của scenario;
- đổi split không nên đổi `conditions_checksum`;
- tránh làm checksum của benchmark cũ thay đổi;
- tránh việc chỉnh sửa scenario vô tình thay đổi protocol.

### Metadata riêng

Tạo:

```text
packages/benchmark/planbench_benchmark/scenario_protocol.json
```

Ví dụ:

```json
{
  "protocol_version": "1.0.0",
  "scenarios": {
    "open_space": {
      "split": "dev",
      "notes": null
    },
    "intersection": {
      "split": "holdout",
      "notes": "Held-out scenario for final evaluation"
    }
  }
}
```

Hoặc dùng schema:

```python
class ScenarioProtocolMetadata(BaseModel):
    scenario_name: str
    split: Literal["dev", "holdout", "unassigned"]
    protocol_version: str
    notes: str | None = None
```

### Quy tắc

- `conditions_checksum` chỉ phản ánh điều kiện mô phỏng.
- Đổi split không đổi `conditions_checksum`.
- Report lưu snapshot:
  - split;
  - protocol version.
- Scenario mới mặc định `unassigned`.
- Không tự coi scenario mới là dev.
- Scenario Editor không được tự gán holdout.
- Benchmark cũ không có metadata được đọc là `unassigned`.

### Tập holdout đề xuất

Đề xuất:

```text
Holdout:
- bidirectional_corridor
- intersection
- dynamic_warehouse
```

```text
Dev:
- các scenario còn lại
```

Danh sách cuối phải được team approve.

Không chọn holdout chỉ vì đó là các scenario khó nhất.

Mục tiêu là kiểm tra khả năng tổng quát hóa trên nhóm tình huống khác với tập dev.

### BenchmarkSpec

Có thể thêm:

```python
splits: tuple[
    Literal["dev", "holdout"],
    ...
] = ("dev",)
```

Backend resolve split qua protocol metadata, không qua `Scenario`.

### BenchmarkReport

Thêm:

```python
protocol_version: str
scenario_split: Literal["dev", "holdout", "unassigned"]
generalization_gap: dict[str, float] | None
```

Report phải lưu snapshot metadata tại thời điểm chạy.

Không đọc metadata mới rồi áp ngược cho benchmark cũ.

### Generalization gap

Chỉ tính khi có đủ dữ liệu dev và holdout.

Ví dụ:

```text
generalization_gap
= metric_dev - metric_holdout
```

Phải ghi rõ metric nào đang được tính.

Không gộp nhiều metric khác đơn vị thành một số duy nhất.

### Quy tắc vận hành holdout

- Holdout dùng cho đánh giá cuối.
- UI cảnh báo trước khi chạy.
- Mỗi lần xem kết quả holdout làm giảm tính khách quan.
- MVP không chặn cứng.
- Ghi lại benchmark nào đã sử dụng holdout.
- Không tuyên bố “chưa từng xem” nếu đã chạy holdout nhiều lần.

### Test

- Đổi split không đổi conditions checksum.
- Report lưu đúng protocol version.
- Scenario không có metadata trả `unassigned`.
- Generalization gap là `None` nếu thiếu một nhóm.
- Benchmark cũ vẫn đọc được.
- Protocol metadata sai schema bị từ chối.
- Scenario Editor không sửa trực tiếp split.

### Definition of Done

- [ ] Không thêm `split` vào `Scenario`.
- [ ] Không đổi checksum benchmark cũ.
- [ ] Có protocol metadata versioned.
- [ ] Có trạng thái `unassigned`.
- [ ] UI có cảnh báo holdout.
- [ ] Report lưu snapshot split.
- [ ] Có test backward compatibility.

---

## 2.2. P03 — Hiệu chuẩn độ khó thực nghiệm

### Định nghĩa

```text
difficulty(scenario)
= 1 - success_rate(baseline_reference, scenario, fixed_seeds)
```

### Baseline phải được ghim

Baseline gồm:

- algorithm stack;
- algorithm config;
- robot profile;
- seed list;
- git SHA;
- map checksum;
- scenario checksum;
- protocol version;
- replanning mode;
- simulator version.

Không chỉ lưu tên `astar+dwa`.

### Script

Tạo:

```text
scripts/calibrate_difficulty.py
```

Script:

1. Đọc scenario library.
2. Chạy baseline.
3. Dùng 30 seed cố định.
4. Tính success rate.
5. Tính difficulty.
6. Tính CI95 bằng P04.
7. Lưu cache versioned.
8. In báo cáo tổng hợp.

### Cache

Tạo:

```text
packages/benchmark/planbench_benchmark/difficulty_calibration.json
```

Ví dụ:

```json
{
  "calibration_version": "1.0.0",
  "git_sha": "abc123",
  "baseline": {
    "algorithm": "astar+dwa",
    "replanning_enabled": false,
    "seeds": [0, 1, 2]
  },
  "scenarios": {
    "open_space": {
      "difficulty": 0.05,
      "ci95": [0.0, 0.15]
    }
  }
}
```

### Không thêm difficulty vào Scenario

Difficulty là kết quả đo.

Không thêm:

```python
scenario.difficulty
```

Thay bằng:

```python
get_difficulty(
    scenario_name: str,
    calibration_version: str | None = None,
) -> DifficultyLabel | None
```

### Replanning

Trong plan hiện tại:

```text
replanning_enabled = false
```

Nếu replanning được triển khai sau này:

- tạo calibration version mới;
- không ghi đè cache cũ;
- report chọn đúng calibration theo điều kiện chạy.

### API

Scenario library có thể trả:

```python
class DifficultyLabel(BaseModel):
    value: float
    ci95: tuple[float, float]
    calibration_version: str
    baseline_algorithm: str
```

Nếu chưa hiệu chuẩn:

```text
difficulty = null
```

Không raise.

### Vấn đề dải difficulty

10 scenario hiện có có thể không phủ đều dải difficulty.

Sau calibration:

- nếu tất cả gần 0 thì scenario quá dễ;
- nếu tất cả gần 1 thì scenario quá khó;
- nếu dải quá hẹp thì phải báo rõ;
- không sửa tay cache để tạo đường cong đẹp.

Scenario Editor được dùng để tạo thêm scenario lấp dải còn thiếu.

### Test

- Script có `--dry-run`.
- Dry-run dùng ít seed.
- Cache có version.
- Cache có git SHA.
- Cache có baseline config.
- Cache có seed list.
- Cache có checksum.
- Cache sai cấu trúc bị từ chối.
- Scenario chưa hiệu chuẩn trả `None`.
- Cùng config và seed cho cùng kết quả.

### Kiểm chứng

Chạy calibration thật.

Kiểm tra:

- `open_space` thuộc nhóm dễ;
- scenario hẹp hoặc có obstacle động khó hơn;
- nếu tất cả gần 0 hoặc gần 1 thì báo giới hạn;
- không sửa tay kết quả;
- lưu log thời gian chạy.

### Definition of Done

- [ ] Có script chạy được.
- [ ] Có cache versioned.
- [ ] Có CI95.
- [ ] Có baseline metadata đầy đủ.
- [ ] Cache tái tạo được.
- [ ] Không thêm difficulty vào Scenario.
- [ ] API xử lý scenario chưa hiệu chuẩn.
- [ ] Có báo cáo dải difficulty.

---

## 2.3. Scenario Editor tùy chỉnh

### Vì sao xếp vào Đợt 2

1. P03 cần công cụ tạo scenario để lấp dải difficulty.
2. P05 cần scenario mới và khác nhóm dev.
3. Backend CRUD và validation đã có phần lớn.
4. Giá trị nhận được cao so với công sức frontend.

### Phạm vi MVP

1. Danh sách scenario.
2. Tạo scenario mới.
3. Chỉnh start.
4. Chỉnh goal.
5. Chỉnh heading.
6. Thêm static obstacle.
7. Thêm dynamic obstacle.
8. Thêm waypoint.
9. Validate bằng engine thật.
10. Preview trên map.
11. Lưu scenario.

### Không thuộc phạm vi MVP

- Kéo chuột xoay heading nâng cao.
- Version history đầy đủ.
- Collaborative editing.
- Sinh scenario bằng AI.
- Procedural generation nâng cao.
- Gán split trực tiếp trong form.
- Tự động đưa scenario vào holdout.

### Protocol metadata

Scenario mới:

```text
split = unassigned
```

Nhưng giá trị này nằm trong metadata riêng, không nằm trong `Scenario`.

Việc chuyển scenario sang dev hoặc holdout phải là thao tác protocol riêng sau review.

### Frontend

Cập nhật:

```text
apps/web/src/lib/types.ts
apps/web/src/lib/api.ts
apps/web/src/components/MapCanvas.tsx
apps/web/src/app/scenarios/page.tsx
apps/web/src/app/scenarios/[id]/page.tsx
apps/web/src/lib/i18n/locales/en.json
apps/web/src/lib/i18n/locales/vi.json
```

### MapCanvas dùng lại

Thiết kế:

```typescript
type MapCanvasProps = {
  staticObstacles?: StaticObstacle[];
  dynamicObstacles?: DynamicObstacle[];
  previewTime?: number;
};
```

Scenario Editor dùng:

```text
previewTime = undefined
```

Replay sau này có thể dùng:

```text
previewTime = playhead
```

### Validation

Frontend không tự coi scenario hợp lệ.

Phải gọi:

```text
POST /scenarios/validate
```

Backend dùng engine thật để kiểm tra:

- start hợp lệ;
- goal hợp lệ;
- obstacle nằm trong map;
- robot không xuất phát trong obstacle;
- waypoint hợp lệ;
- dynamic obstacle trajectory hợp lệ.

### Luồng giao diện

```text
Scenario list
    ↓
Create scenario
    ↓
Edit start/goal/obstacles
    ↓
Validate
    ↓
Save
    ↓
Run benchmark
    ↓
Calibrate difficulty
```

### Test

Backend:

- create;
- update;
- delete;
- validate;
- invalid obstacle;
- invalid start;
- invalid goal.

Frontend:

- render list;
- create form;
- map click;
- submit;
- hiển thị validation error;
- hiển thị obstacle.

### Kiểm chứng

1. Tạo scenario mới.
2. Validate thành công.
3. Chạy benchmark.
4. Chạy calibration.
5. Xác nhận difficulty được sinh.
6. Xác nhận scenario vẫn `unassigned`.
7. Chỉ gán dev/holdout qua metadata riêng sau review.

### Definition of Done

- [ ] CRUD hoạt động.
- [ ] Validation dùng engine thật.
- [ ] Map preview hoạt động.
- [ ] Scenario mới không tự vào dev hoặc holdout.
- [ ] Không đổi checksum benchmark cũ.
- [ ] Component visualization tái sử dụng được.
- [ ] Có test frontend và backend.

---

# Đợt 3 — Làm cho kết quả nhìn thấy được

---

## 3.1. F09 — Biểu đồ và xuất báo cáo

### Mục tiêu

P02, P03, P04 và P05 tạo ra:

- observation class;
- difficulty;
- confidence interval;
- p-value;
- effect size;
- generalization gap.

Nếu không hiển thị thì người dùng không nhận được giá trị của các phần này.

### Quyết định thư viện biểu đồ

Hai lựa chọn:

1. `recharts`.
2. SVG thủ công.

Khuyến nghị MVP:

```text
recharts
```

Lý do:

- nhanh triển khai;
- phù hợp React;
- dễ bảo trì;
- giảm code vẽ biểu đồ thủ công.

Phải pin version tương thích với React hiện tại.

### Biểu đồ

#### Biểu đồ 1 — Difficulty curve

```text
success_rate(difficulty)
```

Cho từng thuật toán.

Mục đích:

- không chỉ nhìn một success rate trung bình;
- thấy thuật toán giảm hiệu năng như thế nào khi scenario khó hơn.

#### Biểu đồ 2 — Median, IQR và CI95

Hiển thị cho:

- travel time;
- path efficiency;
- smoothness;
- clearance;
- latency.

#### Biểu đồ 3 — Generalization gap

So sánh:

```text
dev
holdout
```

Cho từng thuật toán.

### Export Markdown

Endpoint:

```text
GET /benchmarks/{id}/report.md
```

Nội dung bắt buộc:

- benchmark ID;
- created time;
- git SHA;
- seed list;
- conditions checksum;
- algorithm config;
- observation classes;
- protocol version;
- scenario split;
- difficulty calibration version;
- median;
- IQR;
- CI95;
- Wilcoxon;
- effect size;
- paired seed count;
- generalization gap;
- bảng runs;
- cảnh báo thiếu seed;
- giới hạn đã biết.

PDF không thuộc MVP hiện tại.

Người dùng có thể in Markdown hoặc trang web thành PDF tạm thời.

### Download trên frontend

Do endpoint cần authentication:

- không dùng `<a href>` trực tiếp nếu token nằm trong header;
- dùng fetch;
- nhận Blob;
- tạo Blob URL;
- kích hoạt download;
- revoke URL sau khi hoàn thành.

### Test

- Benchmark chưa hoàn thành trả lỗi rõ ràng.
- Response có content type đúng.
- Có `Content-Disposition`.
- Filename hợp lệ.
- Report có warning nếu thiếu seed.
- Report có observation class.
- Report có protocol version.
- Report có calibration version.
- Field `null` không làm render lỗi.
- Ký tự đặc biệt không phá Markdown.

### Definition of Done

- [ ] Người dùng tải được Markdown report.
- [ ] UI hiển thị difficulty curve.
- [ ] UI hiển thị median, IQR và CI.
- [ ] UI hiển thị generalization gap.
- [ ] Report có metadata tái lập.
- [ ] Report không kết luận mạnh khi thiếu dữ liệu.

---

## 3.2. F05 — Sửa Metrics Engine

### Nguyên tắc tương thích

Thêm field mới bên cạnh field cũ.

Không:

- đổi nghĩa field cũ âm thầm;
- xóa field cũ;
- làm benchmark cũ không đọc được.

### Smoothness

Hiện tại:

```text
Σ|Δθ| / path_length
```

Đề bài yêu cầu:

```text
Σ(Δθ)²
```

Cách sửa:

- giữ metric cũ;
- đổi docstring metric cũ thành `heading_change_rate`;
- thêm field mới:

```python
smoothness_squared: float
```

Không thay field cũ bằng công thức mới trong cùng commit.

### Latency

Thêm:

```python
local_planning_latency_p50: float | None
local_planning_latency_p95: float | None
local_planning_latency_p99: float | None
```

Không chỉ dùng mean và max.

### Stop-and-go count

Đếm số lần robot:

```text
đang di chuyển
→ giảm xuống dưới ngưỡng
→ tăng trở lại trên ngưỡng
```

Không đếm trạng thái đứng yên ban đầu là một stop-and-go.

Cần guard:

```text
ever_moved
```

Ngưỡng không hard-code theo thuật toán.

Ngưỡng phải nằm trong:

- metric config versioned; hoặc
- benchmark conditions.

### Near-miss count

Đếm số frame có:

```text
clearance < warning_threshold
```

Không tính collision frame hai lần nếu metric đã có collision count riêng.

Ngưỡng phải được ghi trong report.

### Time to first collision

Nếu có collision:

```python
time_to_first_collision: float
```

Nếu không:

```python
time_to_first_collision = None
```

### Peak memory

Không đưa peak memory vào leaderboard mặc định trong đợt này.

Lý do:

- phụ thuộc máy;
- phụ thuộc runtime;
- có overhead;
- khó so sánh công bằng;
- mâu thuẫn với tính tái lập nếu không ghi môi trường đo.

Nếu vẫn cần đo thì chỉ là optional metric:

```python
memory_measurement_enabled: bool
measurement_environment: str | None
peak_memory_bytes: int | None
```

Không dùng trong overall score.

### Replanning metric

`replan_count` chưa làm trong đợt này.

Nó thuộc plan Replanning riêng sau khi Đợt 0–3 hoàn thành.

### Test

#### Smoothness

- Dùng path nhỏ tính tay.
- So đúng `Σ(Δθ)²`.
- Field cũ vẫn tồn tại.

#### Percentile

- Dữ liệu tính tay.
- Kiểm tra p50, p95, p99.
- Empty input trả `None` hoặc hành vi đã quy định.

#### Stop-and-go

- Không đếm trạng thái đứng yên lúc bắt đầu.
- Đếm đúng khi robot dừng rồi đi lại.
- Không đếm rung quanh ngưỡng nhiều lần nếu chưa có hysteresis.

#### Near miss

- Đếm đúng frame dưới ngưỡng.
- Không nhầm với collision count.

#### Time to first collision

- Trả thời điểm collision đầu tiên.
- Trả `None` nếu không collision.

#### Compatibility

- Benchmark cũ vẫn deserialize.
- Field mới có default.
- Frontend không lỗi khi field mới `null`.

### Definition of Done

- [ ] Có `smoothness_squared`.
- [ ] Field smoothness cũ vẫn tồn tại.
- [ ] Có latency p50, p95, p99.
- [ ] Có stop-and-go count đúng.
- [ ] Có near-miss count.
- [ ] Có time-to-first-collision.
- [ ] Không dùng peak memory trong overall score.
- [ ] Benchmark cũ vẫn đọc được.

---

# Đợt 4 — Replanning, Map Loader và Replay

> **Trạng thái:** chưa approve trong plan hiện tại.  
> Phải review lại sau khi Đợt 0–3 hoàn thành.

---

## 4.1. Replanning khi bị vật cản động chặn

### Mục tiêu

Cho phép robot lập lại global path khi đường hiện tại bị vật cản động chặn.

### Điều kiện công bằng

1. Replanning phải được đặt trong stack chung, không đặt riêng trong DWA.
2. Cùng luật trigger cho mọi thuật toán.
3. Cấu hình replanning phải nằm trong benchmark conditions.
4. Cùng scenario và cùng replanning config phải có cùng checksum.
5. Không tune replanning riêng cho một thuật toán.

### Field dự kiến

```python
replanning_enabled: bool = False
max_replans: int = 0
```

Cần quyết định vị trí lưu field trước khi triển khai.

Không tự động thêm vào `Scenario` nếu điều đó làm thay đổi dữ liệu cũ mà chưa có migration hoặc versioning rõ ràng.

### Rủi ro kỹ thuật

#### Replan ngây thơ

Nếu global planner chỉ rasterize static obstacle thì gọi lại planner sẽ tạo đúng đường cũ.

Khi replanning phải:

- lấy vị trí obstacle động hiện tại;
- rasterize chúng vào temporary grid;
- gọi global planner trên grid mới.

#### Stuck window

Sau khi recover:

- phải reset hoặc reseed stuck window;
- không chỉ đổi state;
- tránh robot bị đánh dấu STUCK lại ngay bước tiếp theo.

### Test bắt buộc

- Replanning off → robot STUCK.
- Replanning on → robot có thể SUCCESS.
- Stuck window được reset.
- Cùng config khác thuật toán → conditions checksum giống nhau.
- Đổi replanning config → checksum khác.
- DWA reset an toàn.
- PPO reset an toàn.
- RRT\* replanning hợp lệ.

### Calibration

Khi replanning được bật:

- tạo calibration version mới;
- không ghi đè difficulty cũ;
- report phải ghi rõ replanning mode.

---

## 4.2. F01 — Map loader chuẩn ROS `map_server`

### Phạm vi

- PGM P2 ASCII.
- PGM P5 binary.
- YAML sidecar.
- `resolution`.
- `origin`.
- `negate`.
- `occupied_thresh`.
- `free_thresh`.
- upload endpoint.
- test bằng file ROS thật.

### Dependency

Thêm:

```text
PyYAML
```

Pin version tương thích.

### PNG

PNG không bắt buộc cho MVP đầu tiên.

Ưu tiên PGM vì đây là định dạng phổ biến của ROS map server.

Nếu thêm PNG thì phải có dependency xử lý ảnh và test riêng.

### Test

- PGM P2.
- PGM P5.
- YAML hợp lệ.
- YAML thiếu field.
- Negate.
- Threshold.
- Lật trục tọa độ đúng.
- So grid với map được tạo bằng builder.

---

## 4.3. F08 — Replay episode đã lưu

### Hiện trạng

Trang live simulation đã có playhead nhưng benchmark detail chỉ hiển thị robot ở frame cuối.

### Việc cần làm

- Tách playback logic thành hook dùng chung.
- Hỗ trợ trajectory tĩnh.
- Thêm playhead.
- Thêm tốc độ phát.
- Vẽ obstacle động theo thời gian.
- Đánh dấu collision trên timeline.
- Dùng lại `MapCanvas`.

### Definition of Done

- [ ] Replay chạy được.
- [ ] Có scrubber.
- [ ] Robot di chuyển theo frame.
- [ ] Obstacle động đúng thời gian.
- [ ] Có collision marker.
- [ ] Không ảnh hưởng live simulation.

---

# Đợt 5A — P01: Cân bằng ngân sách tinh chỉnh

> **Plan riêng, chưa approve trong tài liệu này.**

### Mục tiêu

Đảm bảo mọi thuật toán được tune với cùng ngân sách.

### Dependency

Thêm vào:

```text
requirements-optional.txt
```

```text
optuna
```

Không đưa Optuna vào core runtime nếu API chỉ đọc cache.

### Search space

Tạo:

```text
packages/benchmark/planbench_benchmark/tuning.py
```

Khai báo:

```python
SEARCH_SPACES: dict[str, dict]
```

### Quy tắc

- Cùng số trial cho mọi planner.
- Tune trên dev.
- Đánh giá trên holdout.
- Không tự động thay default production.
- Log toàn bộ trial.
- Ghi best-so-far curve.
- Ghi seed.
- Ghi git SHA.
- Ghi search-space version.

### Ngân sách MVP

```text
30 trial/planner
```

### Không gộp

Không gộp P01 với:

- parallel execution;
- regression guard;
- sensor noise.

Mỗi phần phải được review riêng.

---

# Đợt 5B — F16: Parallel execution

> **Plan riêng, chưa approve trong tài liệu này.**

### Mục tiêu

Chạy episode song song mà không thay đổi kết quả benchmark.

### Yêu cầu

- Song song theo episode.
- Giới hạn worker.
- Có timeout.
- Có cancel.
- Không chia sẻ random state.
- Không chia sẻ mutable planner state.
- Kết quả song song phải giống chạy tuần tự với cùng seed.

### Test

- Sequential và parallel cho cùng kết quả.
- Không mất episode.
- Không trùng episode.
- Thứ tự lưu kết quả ổn định.
- Worker exception được trả rõ ràng.
- Không deadlock.

---

# Đợt 5C — F17: Regression guard

> **Plan riêng, chưa approve trong tài liệu này.**

### Mục tiêu

Cảnh báo khi thuật toán giảm hiệu năng so với baseline đã lưu.

### Yêu cầu

- Baseline versioned.
- Cùng conditions checksum.
- Cùng observation class.
- Cùng seed hoặc seed pairing phù hợp.
- Dùng thống kê P04.
- Không cảnh báo chỉ vì dao động nhỏ.
- Có effect size.
- Có threshold có thể cấu hình.

### Kết quả

```text
PASS
WARNING
REGRESSION
INSUFFICIENT_DATA
```

---

# Đợt 5D — F23: Sensor noise

> **Plan riêng, chưa approve trong tài liệu này.**

### Mục tiêu

Đánh giá độ bền của thuật toán khi cảm biến có nhiễu.

### Phạm vi

- LiDAR noise.
- Có thể thêm odometry noise sau.
- Seed riêng.
- Noise config versioned.
- Noise config đi vào conditions checksum.
- Report robustness.

### Không được làm

- Không dùng noise khác nhau cho từng thuật toán.
- Không tune noise theo planner.
- Không dùng global random state.
- Không trộn kết quả noise và no-noise trong cùng leaderboard group.

---

# Kiểm thử chung cho Đợt 0–3

## Backend

Chạy:

```bash
pytest
```

Yêu cầu:

- không có fail mới;
- skipped có lý do;
- test deterministic chạy lặp lại được;
- test thống kê không flaky;
- backward compatibility pass.

## Frontend

Chạy:

```bash
pnpm test
pnpm typecheck
pnpm build
```

Yêu cầu:

- test pass;
- TypeScript sạch;
- production build sạch;
- download report hoạt động;
- biểu đồ render được.

## Docker

Chạy:

```bash
docker compose build
docker compose up
docker compose ps
```

Yêu cầu:

- migration thành công;
- database healthy;
- API healthy;
- web truy cập được;
- benchmark end-to-end chạy được.

## Regression flow

Chạy tối thiểu:

1. `astar+dwa`.
2. `rrtstar+dwa`.
3. Benchmark 1–5 seed có warning.
4. Benchmark 30 seed có kết quả thống kê.
5. Export Markdown.
6. Leaderboard.
7. Scenario Editor.
8. Calibration script.
9. Đọc benchmark cũ.
10. Chạy lại cùng seed cho cùng kết quả.

---

# Definition of Done cho phạm vi approve

Đợt 0–3 chỉ hoàn thành khi:

- [ ] RRT\* chạy hợp lệ.
- [ ] RRT\* tái lập theo seed.
- [ ] Không có test RRT\* đơn điệu cứng theo iteration.
- [ ] Docker Compose được chạy thật.
- [ ] P02 có metadata cho global và local planner.
- [ ] P04 dùng SciPy.
- [ ] Wilcoxon ghép đúng theo seed.
- [ ] Có median, IQR, CI và effect size.
- [ ] Field cũ không bị xóa.
- [ ] P05 dùng metadata riêng.
- [ ] Không thêm `split` vào `Scenario`.
- [ ] Đổi split không đổi conditions checksum.
- [ ] Scenario mới mặc định `unassigned`.
- [ ] P03 có calibration versioned.
- [ ] Difficulty không nằm trong Scenario schema.
- [ ] UI cảnh báo thiếu seed.
- [ ] UI cảnh báo khi dùng holdout.
- [ ] Export Markdown hoạt động.
- [ ] Metrics mới đúng công thức.
- [ ] Benchmark cũ vẫn đọc được.
- [ ] Backend test pass.
- [ ] Frontend test pass.
- [ ] Typecheck pass.
- [ ] Production build pass.
- [ ] Có báo cáo kiểm chứng từng đợt.

---

# Rủi ro của bản plan

| Rủi ro                                        | Mức        | Giảm thiểu                                             |
| --------------------------------------------- | ---------- | ------------------------------------------------------ |
| SciPy làm dependency và Docker image nặng hơn | Trung bình | Pin version, chạy Docker build thật                    |
| RRT\* không ổn định ở map khó                 | Trung bình | Seed cố định, giới hạn iteration, benchmark nhiều seed |
| RRT\* test bị flaky                           | Cao        | Bỏ assert đơn điệu theo iteration                      |
| Metadata split và Scenario bị lệch            | Trung bình | Protocol version, snapshot metadata, `unassigned`      |
| Calibration cache bị sửa tay                  | Cao        | Schema validation, git SHA, checksum, script tái tạo   |
| Metric mới làm vỡ API                         | Cao        | Thêm field bên cạnh, không xóa field cũ                |
| Benchmark cũ đổi checksum                     | Cao        | Không thêm split vào Scenario                          |
| Đợt 1–2 kéo dài nhưng chưa có UI              | Trung bình | Export Markdown là deliverable bắt buộc                |
| Holdout bị dùng nhiều lần                     | Trung bình | Warning, audit record, tài liệu protocol               |
| Biểu đồ bị diễn giải quá mức                  | Trung bình | Hiện seed count, CI, p-value và effect size            |
| Đợt 5 quá rộng                                | Cao        | Tách thành 5A, 5B, 5C và 5D                            |
| Role Engineer/Approver chưa phù hợp           | Cao        | Không approve trong plan này, lập plan RBAC riêng      |

---

# Điểm cần quyết định khi approve

1. Chấp nhận dùng SciPy cho P04.
2. Chọn `recharts` hay SVG thủ công.
3. Chốt tập holdout 7 dev / 3 holdout.
4. Chốt tên và vị trí file protocol metadata.
5. Chốt thứ tự làm RRT\* và Docker nếu chỉ có một người.
6. Xác nhận phạm vi approve chỉ gồm Đợt 0–3.
7. Xác nhận Đợt 4 phải review lại.
8. Xác nhận P01, parallel, regression guard và sensor noise là các plan riêng.
9. Xác nhận RBAC và role không nằm trong plan này.
10. Xác nhận không merge toàn bộ roadmap trong một lần.

---

# Quyết định đề xuất

**Approve with changes** cho Đợt 0–3 với các điều kiện:

1. P04 dùng SciPy.
2. Không tự viết Wilcoxon bằng NumPy.
3. Bỏ test RRT\* cứng kiểu `5000 iterations` bắt buộc tốt hơn `500 iterations`.
4. P05 lưu split bằng metadata riêng.
5. Không thêm `split` trực tiếp vào `Scenario`.
6. Không làm đổi checksum benchmark cũ chỉ vì thay đổi split.
7. Giữ field cũ khi thêm metric mới.
8. Scenario mới mặc định `unassigned`.
9. Đợt 4 phải review riêng.
10. P01, parallel execution, regression guard và sensor noise phải có plan riêng.
11. Việc approve plan này không đồng nghĩa approve mô hình role `Engineer/Approver`.
12. Không triển khai hoặc merge đồng loạt toàn bộ roadmap trong một nhánh duy nhất.

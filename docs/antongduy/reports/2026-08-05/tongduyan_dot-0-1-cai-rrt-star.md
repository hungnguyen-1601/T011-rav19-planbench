# Report — Đợt 0.1: cài RRT\* thật

> **Ngày làm:** 2026-08-05.
> **Plan:** `docs/antongduy/plans/2026-08-05/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`
> (bản team approve), mục 0.1.
> **Trạng thái: XONG.** Test: `1120 passed, 4 skipped` (baseline trước đó
> `1085 passed, 4 skipped` — thêm 35 test).

> **Cập nhật 2026-08-05 (sau approve):** bản đầu tiên được code theo plan
> nháp ngày 2026-08-04, dùng định danh `rrt_star` và trường
> `goal_sample_rate`. Bản plan team approve (2026-08-05) chốt
> **`rrtstar`** và **`goal_bias`**. Đã đổi toàn bộ để khớp: thư mục
> package, module path, id stack (`rrtstar+dwa`, `rrtstar+pure_pursuit`),
> `global_planner="rrtstar"`, `planner.name`, tên file test
> (`tests/test_rrtstar.py`) và tài liệu. Tên class `RRTStarConfig` /
> `RRTStarPlanner` **giữ nguyên** — bản approve dùng đúng tên đó.
> Số liệu benchmark bên dưới là **của chính lần chạy gốc**, chỉ nhãn
> thuật toán được đổi tên theo, không chạy lại.

---

## 1. Đã làm gì

### 1.1. Planner mới

`packages/planning/planbench_planning/rrtstar/planner.py` (+ `__init__.py`),
bố cục theo đúng `astar/`. Thuần Python + numpy, **không thêm dependency
nào** (`numpy==2.5.1` đã có sẵn trong `requirements.txt`).

`RRTStarConfig` (Pydantic, `frozen=True`) đúng 6 trường như plan chốt:
`max_iterations=3000`, `step_size=0.5`, `goal_bias=0.05`,
`rewire_radius=1.5`, `goal_tolerance=0.3`, `seed=0`. Mỗi trường có ràng
buộc miền giá trị (`gt=0`, `le=1.0`…) nên Optuna ở Đợt 5 cắm vào được ngay
mà không cần sửa planner.

Ba điểm thiết kế đáng ghi lại:

- **Không dừng ở lời giải đầu tiên.** Vòng lặp chạy hết ngân sách
  iteration và rewire liên tục. Đây chính là chỗ phân biệt RRT\* với RRT
  thường, và là lý do test "tăng `max_iterations` thì `path_length` không
  tăng" có nghĩa.
- **Va chạm kiểm theo đoạn, không theo đỉnh.** Dùng lại
  `has_line_of_sight()` (lấy mẫu mỗi `resolution/4`), nên một cạnh không
  thể nhảy qua tường mỏng.
- **Cost lan xuống cả nhánh khi rewire** (`_propagate_cost`). Bỏ bước này
  là lỗi RRT\* kinh điển: cây giữ cost cũ, các lần chọn cha sau so sánh
  với con số không còn đúng, và đường ngừng cải thiện theo ngân sách.

### 1.2. Tính xác định và đường truyền seed — phần việc thật

`GlobalPlanner` yêu cầu "deterministic for identical inputs". RRT\* đáp ứng
bằng `numpy.random.Generator` khởi tạo từ seed, **không đụng module
`random` toàn cục** (state toàn cục sẽ làm các episode chạy chung tiến
trình nhiễm nhau). Generator được dựng lại **trong mỗi lần gọi `plan()`**,
nên một instance dùng lại nhiều lần không bị trôi.

Plan đã cảnh báo đúng: nếu seed planner cố định thì mọi episode dùng chung
1 cây. Kiểm code thì **đường truyền seed chưa hề tồn tại** — `run_stack()`
gắn cứng `AStarPlanner` và tự đặt tên stack là `f"astar+{local.name}"`.
Đã sửa:

| File | Thay đổi |
|---|---|
| `common/base.py` | `GlobalPlanner` thêm property trừu tượng `name` — nửa trái của stack id giờ do planner khai, không phải chuỗi gắn cứng |
| `nav_stack.py` | `plan_global_path()` / `run_stack()` nhận `global_planner`, mặc định A\* (giữ nguyên hành vi cũ cho RL env và test cũ); tên stack thành `f"{global.name}+{local.name}"` |
| `registry.py` | `_Entry` thêm `global_factory: Callable[[int], GlobalPlanner]`; thêm `build_global_planner(id, *, episode_seed)` |
| `runner.py` | `run_single()` truyền **cùng seed episode** cho cả scenario lẫn global planner |
| `services.py` | Simulation đơn lẻ truyền `scenario.random_seed` xuống planner, nên chạy lại một simulation đã lưu ra đúng đường cũ |

**Trộn 2 seed bằng `SeedSequence([config.seed, episode_seed])`, không XOR.**
Plan gợi ý XOR làm ví dụ, nhưng XOR đụng nhau: `1^2 == 3^0`, tức hai cặp
seed lẽ ra độc lập lại cho đúng một cây. Có test riêng chặn việc này
(`test_config_seed_and_episode_seed_do_not_collide`).

`expanded_nodes` = số node đã thêm vào cây, so sánh được về ý nghĩa với A\*
(công sức tìm kiếm đã bỏ ra).

### 1.3. Registry — 2 stack mới

`rrtstar+dwa` (`benchmarkable=True`) và `rrtstar+pure_pursuit`
(`benchmarkable=False`, giống `astar+pure_pursuit`).

Thêm 2 trường vào `AlgorithmInfo`, và đây là phần **vượt ngoài chữ của
plan nhưng đúng tinh thần P02** (khai báo được, kiểm chứng được):

- `global_planner: str` — id global planner, registry **khai tường minh**
  chứ không tách chuỗi `id`. Có test khẳng định hai thứ luôn khớp nhau.
- `stochastic_global_planner: bool` — `true` khi global planner lấy mẫu
  ngẫu nhiên. Một stack ngẫu nhiên mà báo cáo im lặng thì mời người đọc so
  một cây may mắn với A\*.

Frontend: `benchmarkTypes.ts` thêm 2 trường, trang `/algorithms` hiện badge
"Randomised" + câu cảnh báo phải đọc qua nhiều seed (đã thêm khóa
`algorithms.randomised*` cho cả `en.json` và `vi.json`).
`chat_service.py` thêm từ khóa `rrt`/`rrt*`/`rrt star` — riêng "dwa" trơ
trọi vẫn ra `astar+dwa` (stack cũ, xác định, là cái người ta mặc định nói
tới); muốn RRT\* thì phải gọi tên.

`conditions_checksum` **không sửa** — đúng như plan phân tích: checksum xác
nhận *cùng điều kiện*, thuật toán là biến độc lập.

### 1.4. Test — `tests/test_rrtstar.py` (25 test) + 10 test tích hợp

Đủ 6 nhóm plan yêu cầu:

| Yêu cầu của plan | Test |
|---|---|
| Map trống: tìm được đường, đầu/cuối đúng | `test_empty_map`, `test_goal_is_reached_within_tolerance` |
| Có tường: đường không cắt ô occupied, **kiểm từng đoạn** | `assert_path_valid` (dùng `has_line_of_sight` cho mọi cặp điểm liên tiếp) |
| Không có đường: `success=False`, có `failure_reason`, không raise | `TestRRTStarFailures` (6 test) |
| Tái lập: cùng seed → path **giống hệt** | `test_same_seed_gives_the_identical_path`, `test_replanning_with_one_instance_repeats_itself` |
| Khác seed → khác path | `test_different_episode_seeds_give_different_paths` (4 seed, 4 path khác nhau), `test_different_config_seeds_give_different_paths` |
| Tính chất RRT\*: 500 → 5000 iteration, `path_length` không tăng | `test_more_iterations_never_lengthen_the_path` |

Thêm ở tầng tích hợp: `run_single()` với `rrtstar+dwa` — khác seed ra khác
global path, cùng seed tái lập cả `plan.path` lẫn `trajectory`; và
`astar+dwa` **không** đổi path theo seed (chứng minh seed planner chỉ chạm
vào stack ngẫu nhiên).

---

## 2. Kiểm chứng — benchmark thật

Chạy `run_benchmark` thật, `astar+dwa` vs `rrtstar+dwa`, 5 seed, headless:

```
=== narrow_corridor (seeds (1, 2, 3, 4, 5)) ===
conditions_checksum = 65dbf372ffba39362387abe28fc5d3067de58fce700cb29d0778e9cc2a16b879
algorithm        success collision  travel_s  path_eff  plan_ms   nodes
astar+dwa           0.00      0.00         —         —      1.2       5
rrtstar+dwa        1.00      0.00     14.32     1.026     50.8       5
  planned path length per seed [astar+dwa]:    12.00, 12.00, 12.00, 12.00, 12.00
  planned path length per seed [rrtstar+dwa]: 12.00, 12.00, 12.00, 12.01, 12.02

=== doorway (seeds (1, 2, 3, 4, 5)) ===
conditions_checksum = 2c67300aa580c997271db33afb56673f9c9e8f20fc57cfaa75166141f743e887
algorithm        success collision  travel_s  path_eff  plan_ms   nodes
astar+dwa           1.00      0.00      9.50     1.038      1.3       5
rrtstar+dwa        1.00      0.00      9.83     1.040    308.9       5
  planned path length per seed [astar+dwa]:    8.00, 8.00, 8.00, 8.00, 8.00
  planned path length per seed [rrtstar+dwa]: 8.00, 8.01, 8.01, 8.04, 8.04
```

Đọc bảng:

- **Hai hàng số khác nhau thật** — mục tiêu chính của Đợt 0 đạt. Nền tảng
  không còn chỉ so `astar+dwa` với chính nó ở seed khác.
- **Path length của RRT\* dao động theo seed** (8.00 → 8.04), của A\* thì
  đứng yên. Đường truyền seed hoạt động; nếu seed không xuống tới planner
  thì 5 seed sẽ ra 5 con số giống hệt nhau.
- **`plan_ms` lệch 40–240 lần.** RRT\* chạy hết ngân sách iteration kể cả
  khi đã có đường (đổi lấy tối ưu tiệm cận). Đây là bản chất thuật toán,
  không phải cấu hình bất công — đã ghi vào `KNOWN_LIMITATIONS.md` #97.

### Phát hiện phụ — cần báo, không giấu

**`astar+dwa` trượt `narrow_corridor` ở cả 5/5 seed**, lý do
`stuck: moved only 0.050 m in the last 5.0s`; `rrtstar+dwa` qua được 5/5.

Đây **không phải hồi quy do đợt này gây ra** — code A\* không đổi gì ngoài
việc thêm property `name`, và path A\* vẫn dài đúng 12.00 m như trước.
Nguyên nhân nhiều khả năng: A\* rút gọn đường bằng line-of-sight nên ép sát
mép hành lang hẹp, DWA hết không gian xoay; RRT\* lấy mẫu nên đường nằm
lệch vào giữa hành lang hơn. Cần điều tra riêng — đây là kiểu khác biệt
thuật toán mà nền tảng sinh ra để phát hiện, nhưng cũng có thể là một tương
tác A\*-simplify + DWA đáng sửa. **Chưa xử lý trong đợt này.**

---

## 3. Đã cập nhật tài liệu

- `docs/API_CONTRACT.md`: mục Algorithms mô tả `global_planner` /
  `stochastic_global_planner`, quy tắc dẫn xuất seed, và ghi rõ
  `config_schema` là schema của **local** planner.
- `docs/KNOWN_LIMITATIONS.md`: thêm mục 94–97 (tái lập cần cả 2 seed; một
  lần chạy RRT\* không kết luận được gì; config global planner chưa vào
  `BenchmarkSpec`; RRT\* đắt hơn A\* theo bản chất).

## 4. Còn nợ, chuyển tiếp

1. **Config RRT\* chưa vào `BenchmarkSpec`.** `AlgorithmSpec.config` hiện
   chỉ cấu hình local planner; RRT\* luôn chạy mặc định. Chỗ cắm đã dọn sẵn
   (`_Entry.global_factory`) — việc của **Đợt 5 / P01**.
2. **Xem replay `rrtstar+dwa` bằng mắt** để xác nhận đường "gấp khúc kiểu
   sampling": chưa làm, cần UI chạy (gộp với Đợt 0.2 — `docker compose up`).
3. **Điều tra `astar+dwa` stuck ở `narrow_corridor`** (mục 2).
4. Test frontend có **2 lỗi sẵn có, không liên quan đợt này**:
   `assistant-page.test.tsx` đọc file `src/app/models/page.tsx` không tồn
   tại, và một assert so đường dẫn `\` vs `/` (hỏng trên Windows). Đã xác
   nhận bằng cách stash toàn bộ thay đổi: vẫn hỏng y hệt.

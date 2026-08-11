# Kiểm toán tính công bằng của simulator — sáu bất biến

> **Ngày:** 2026-08-11 · **Loại:** đánh giá hiện trạng, không đổi thuật toán
> **Yêu cầu nguồn:** dev chốt lại mục tiêu — *"một môi trường benchmark công bằng, không thiên
> vị; không thay simulator theo thuật toán để chạy qua task"* — và nêu sáu yếu tố phải giữ khi
> so hai thuật toán trong cùng một episode.
> **Kết luận ngắn:** cả sáu **đang được giữ**, phần lớn là do cấu trúc chứ không do quy ước. Tìm
> được **một khiếm khuyết tiềm ẩn** chưa kích hoạt, đã cài chốt chặn.

---

## 0. Đọc lại mục tiêu trước khi kết luận điều gì

Tài liệu mẹ §1.1: hệ thống trả lời *"candidate nào đáng dùng nhất cho deployment này"*. Tầng
quyết định đứng **trên** một giao thức đánh giá — và giao thức đó chỉ có nghĩa nếu hai candidate
được đo trong cùng một thế giới.

HĐ-4 gọi tên đúng kiểu gian lận cần chặn:

> *"một planner gọi thẳng vào nội tại của `SimBackend` để lấy vị trí vật cản, thay vì qua
> `Observation`. Đây vừa là vi phạm kiến trúc, vừa là gian lận về lớp quan sát (HĐ-7, G6)."*

Sáu bất biến dev nêu là cách kiểm được câu đó, và chúng không phải sáu điều rời rạc — mỗi cái là
**một cách khác nhau để một phép so trở nên vô nghĩa trong khi mọi con số trong đó trông hợp lý**.

---

## 1. Kết quả kiểm — sáu bất biến

Điểm tựa của gần như toàn bộ là **một dòng** trong `packages/benchmark/planbench_benchmark/episode.py`:

```python
def scenario_for(profile: TaskProfile, context: EpisodeContext) -> Scenario:
```

Nó **không nhận candidate**. Thế giới là hàm thuần của `(deployment, episode)`. Candidate chỉ
chạm vào episode ở đúng hai chỗ: `build_planners(...)` và hai bộ đếm tài nguyên đi vào ước lượng
bộ nhớ G5.

| # | Bất biến | Được giữ bằng gì | Trạng thái |
|---|---|---|---|
| 1 | **Cùng ground-truth world** | `scenario.dynamic_obstacles` lấy từ profile; `position_at(obstacle, time, seed)` là hàm thuần ba tham số | ✅ |
| 2 | **Cùng robot embodiment** | `_robot_config(profile)` — chỉ nhận profile; `control_period` **cố ý bị loại** khỏi `RobotConfig` của simulator | ✅ |
| 3 | **Cùng external randomness** | `scenario.random_seed = context.seed`; engine/lidar/dynamic **không có một lệnh ngẫu nhiên nào**; RRT\* dùng `Generator` riêng qua `SeedSequence` | ✅ (xem cảnh báo dưới) |
| 4 | **Cùng vật lý và thời gian** | `simulation_dt = min(MAX_SIMULATION_DT, profile.robot.control_period)` — từ **profile**, không từ tham số DWA của candidate | ✅ |
| 5 | **Cùng success/failure semantics** | `goal_tolerance`, `timeout`, `stuck_window` từ profile; `compute_metrics(trace, profile, context, map_data, resource_profile)` không nhận candidate | ✅ |
| 6 | **Cùng scenario distribution** | `build_evaluation_contexts(profile, ...)` không nhận candidate; `iter_run_plan` phát cùng một tập cho mọi candidate | ✅ |

`tests/test_simulator_fairness.py` — **31 test** khoá cả sáu, bằng cả kiểm chữ ký hàm lẫn kiểm
hành vi.

### Vì sao kiểm chữ ký hàm chứ không chỉ kiểm hành vi

Một test hành vi nói *"hôm nay hai candidate nhận cùng scenario"*. Một test chữ ký nói *"không
ai thêm được tham số `candidate` vào hàm dựng thế giới"*. Cái thứ hai mới là thứ sống sót qua
refactor — và tham số đó chính là thứ người ta thêm khi một planner cần "chỉ một gợi ý nhỏ" từ
thế giới.

### Cảnh báo về bất biến 3

Nó đang đúng **một cách tầm thường**: thế giới không rút số ngẫu nhiên nào cả. Vật cản chuyển
động theo hàm đóng của `(thời gian, seed)`.

Đó chính là lý do phải cài chốt **bây giờ**. Việc thêm nhiễu cảm biến
([kế hoạch](../../plans/2026-08-11/nhieu-cam-bien-theo-seed.md)) sẽ đưa vào **nguồn ngẫu nhiên
theo bước đầu tiên của dự án**. Nếu nó với tay vào một generator dùng chung, thì việc đổi A\*
sang RRT\* sẽ **làm dịch chuyển vật cản** — và phép so ghép cặp sẽ là hai episode khác nhau đội
chung một id. Test `test_a_planners_draws_cannot_move_the_world` và
`test_planning_leaves_the_global_streams_untouched` là thứ sẽ nói điều đó ra.

---

## 2. Khiếm khuyết tiềm ẩn: lưới replan cho global planner **ground truth**

Đây là phát hiện đáng giá nhất của lượt kiểm, và nó tìm được bằng đọc code chứ không bằng một
lần chạy hỏng.

Khi robot bị chặn, `nav_stack._replan` dựng một lưới quy hoạch tạm với **vị trí thật** của vật
cản động nung vào:

```python
grid = _planning_grid(map_data, scenario, engine.dynamic_obstacles_now())
```

Lý do được ghi rõ và hợp lý: một planner chỉ nhận bản đồ tĩnh sẽ replan ra đúng lộ trình vừa bị
chặn, vì không đầu vào nào của nó thay đổi.

**Hôm nay điều này công bằng**, vì chỉ candidate `modular` chạy được — adapter `MonolithicPolicy`
của HĐ-4 chưa tồn tại. Mọi stack đang chạy đều nhận cùng một lưới.

**Ngày adapter đó tồn tại thì nó hết công bằng.** Một policy end-to-end chỉ thấy `Observation`;
global planner của stack modular thấy vật cản **thật sự** ở đâu. Đó đúng là đặc quyền thông tin
mà P02 và G6 sinh ra để định giá, và nó sẽ ưu ái stack modular vì một lý do **không liên quan gì
tới chất lượng điều hướng**.

Chốt chặn đã cài: `test_only_modular_stacks_can_run_today` **sẽ đỏ** đúng ngày adapter được thêm,
kèm thông điệp chỉ thẳng vào vấn đề phải giải trước khi so hai loại candidate. Đó là cách rẻ nhất
để bắt người thêm adapter phải đọc.

Kèm một test nữa khẳng định cái cửa ground truth **không** với tới được qua `get_observation` —
tức mọi candidate vẫn thấy đúng một thứ qua lớp quan sát.

---

## 3. Điều bất biến **không** che được: công bằng về tài nguyên tính toán

Sáu bất biến đều nói về **thế giới**. Có một trục thứ bảy nằm ngoài simulator và không schema nào
cưỡng chế được: HĐ-7.4 đòi mọi candidate chạy trên **cùng máy, cùng mức cấp CPU**.

Đó là tính chất của **quy trình chạy**, không phải của mô hình dữ liệu. Nó đã bị vi phạm một lần
thật (contract 3.0.0: A\* bị loại nhầm ở G4 vì đo dưới tải) và giờ được giữ bằng hai thứ:

- **Xen kẽ context-outer** (`iter_run_plan`) — tải máy trở thành nhiễu chung và triệt tiêu trong
  hiệu số ghép cặp. Có test khoá thứ tự này.
- **Ghim nhân khi chạy** — quy trình vận hành, hiện chưa được cưỡng chế bằng code.

Đo được ở Phase 5.1: cùng bộ candidate, không ghim nhân cho `rrtstar` p99 gộp **59,30 ms**, ghim
nhân cho **16,10 ms**. Chênh 3,7 lần, và nó từng bị đọc thành một tính chất của candidate.

**Đề xuất:** manifest (HĐ-13) đã ghi `benchmark_host` gồm `cores_allocated`. Nên bổ sung việc ghi
**affinity thật** và một cảnh báo trên card khi hai candidate không chạy xen kẽ. Chưa làm — ghi
lại để quyết.

---

## 4. Map dễ và bộ kiểm tầng chấm điểm

Kèm theo lượt này, đã dựng deployment kiểm công bằng riêng:

- `maps/open_hall.{pgm,yaml}` — sảnh 24 × 16 m, một khối giữa, **6,20 m lối trống mỗi bên**,
  **đối xứng gương** quanh cả đường nhiệm vụ lẫn trục dọc. Sinh bằng
  `scripts/make_fairness_map.py` để tái lập được, và tính đối xứng **được test khẳng định**.
  Bản đầu tiên **không** đối xứng: `int(15.7 / 0.05)` cho 313 chứ không phải 314, nên tường trên
  dày hơn tường dưới một ô. Sảnh "đối xứng" lệch 5 cm sẽ ưu ái planner nào thích phía rộng hơn,
  và phát hiện sẽ đọc như tính chất của planner.
- `profiles/open_hall_v1.yaml` — deployment tương ứng, cùng robot với kho để hai bộ kết quả đọc
  được cạnh nhau.
- `tests/test_fairness.py` — **22 test** về đối xứng của **tầng chấm điểm**: định danh (hai
  candidate hành xử giống hệt ⇒ ΔU = 0 tuyệt đối, CI = (0, 0), effect size `None` chứ không phải
  vô cùng), thứ tự, nhãn, thước đo, hình học.

Hai bộ test trả lời hai câu hỏi khác nhau và cần cả hai: `test_fairness` hỏi *tầng chấm điểm có
mù với danh tính không*; `test_simulator_fairness` hỏi *hai candidate có chạy trong cùng một thế
giới không*.

---

## 5. Trạng thái

Full suite: **2037 passed, 6 skipped** (9 phút 09). Baseline trước lượt này 1984 — thêm 53
test, không vỡ test nào. Ruff sạch. Không đổi contract: kiểm toán không phát hiện vi phạm
nào cần sửa hợp đồng, chỉ một khiếm khuyết tiềm ẩn đã được cài chốt chặn (mục 2).

**Việc còn treo, theo thứ tự dev đã chốt:**

1. **Nhiễu cảm biến theo seed** — sửa độ trung thực của simulator, và là nguồn ngẫu nhiên theo
   bước đầu tiên. Phải đi qua bất biến 3: generator riêng, seed từ context, không đụng phán quyết
   va chạm.
2. **Ghi affinity vào manifest** + cảnh báo khi không xen kẽ (mục 3).
3. **Giải quyết bất cân xứng replan trước khi adapter monolithic chạy** (mục 2).

Chỉ sau khi ba việc trên xong mới nên quay lại chuyện cải thiện thuật toán — và khi đó, cách đúng
là **đăng ký candidate mới rồi để nền tảng chấm cả bản cũ lẫn bản mới**, chứ không sửa cấu hình
cũ tại chỗ.

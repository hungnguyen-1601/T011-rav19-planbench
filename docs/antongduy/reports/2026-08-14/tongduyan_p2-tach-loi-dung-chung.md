# P2 — tách lõi DWA dùng chung, không đổi một hành vi nào

**Ngày:** 2026-08-14
**Plan:** `docs/antongduy/plans/2026-08-14/du-doan-chuyen-dong-vat-can.md`, P2
**Trạng thái:** xong · **chưa chạy full suite — chờ lệnh**

---

## 1. Làm gì, và không làm gì

`dwa` và `dwa_predictive` khác nhau **đúng một ý tưởng** — có lăn thế
giới về phía trước cùng robot hay không — và giống nhau ở mọi thứ còn
lại: dựng cửa sổ vận tốc khả đạt, lăn quỹ đạo ứng viên, biến lần quét
LiDAR thành điểm, đo khoảng cách tới đường toàn cục. Chỗ giống nhau đó
chuyển vào `packages/planning/planbench_planning/common/dwa_core.py`.

**Pha này không thêm tính năng nào.** Giá trị của nó nằm hoàn toàn ở chỗ
nó *không* đổi gì — và ở bằng chứng cho điều đó.

---

## 2. Hàm, không phải lớp cha

Plan chốt cấm kế thừa, và lý do là danh tính candidate chứ không phải
khẩu vị thiết kế:

> `StackComponent.version` là **một phần của candidate id**, và nền tảng
> hứa *"cùng một DWA sau khi sửa lỗi là một candidate khác"*. Một lớp cha
> dùng chung phá lời hứa đó theo đúng chiều không ai kiểm: một bản sửa ở
> lớp cha đổi **cả hai** controller, trong khi artifact ghi lại hai id
> **không hề dịch**.

Hai lớp gọi vào cùng một tập hàm thuần có đúng lợi ích chia sẻ code đó,
mà checksum vẫn trung thực — và P6 việc 4 sẽ băm module này **cạnh**
module controller để điều đó thành cưỡng chế chứ không phải lời dặn.

Mọi hàm nhận **primitive**, không nhận config object. Đây cũng không phải
phong cách: một helper nhận `DWAConfig` là helper mà `dwa_predictive`
chỉ dùng được bằng cách kế thừa schema của controller kia.

---

## 3. Cái gì chuyển, cái gì ở lại

| chuyển vào `dwa_core.py` | vì sao |
|---|---|
| `linspace` | lưới lấy mẫu, dùng chung nguyên vẹn |
| `reachable_window` | cửa sổ động **đúng nghĩa**: cơ cấu chấp hành với tới đâu trong một chu kỳ |
| `sample_window` | thứ tự lấy mẫu **là** một phần hành vi candidate — hoà thì lấy chi phí thấp nhất **trước** theo thứ tự này |
| `rollout_batch` | lăn quỹ đạo, khớp từng bit với tích phân của simulator |
| `obstacle_points` | scan → điểm thế giới, dựng từ **pose robot tin là** |
| `final_heading`, `distance_to_polyline` | hình học của hàm chi phí |

| ở lại `dwa/planner.py` | vì sao |
|---|---|
| `_speed_that_stops_within` | **quyết định của An.** Nó là ràng buộc cứng lớp 2, thời gian phản ứng là control period **của chính controller này**, và số học đã nằm ở `feasibility.admissible_speed`. Kéo thêm một bản sao vào lõi là tạo bản sao thứ ba |
| `_score` và toàn bộ trọng số | **hàm chi phí chính là candidate.** Hai controller chấm điểm giống hệt nhau thì không phải hai candidate |
| `keep_out` / phép từ chối cứng | lớp 2, đọc `hard_clearance`, không thuộc phần mềm dùng chung |
| `_nearest_obstacle_distance`, `_advance_local_goal` | trạng thái riêng của controller (`_envelope`, `_path_index`) |

`reachable_window` **cố ý không** nhận `obstacle_speed` hay khe hở. Nếu
nó áp luôn giới hạn phanh thì ràng buộc cứng L2 sẽ nằm trong một hàm mà
mọi tham số còn lại đều do candidate sở hữu — đúng cách bố trí mà tầng
lớp sinh ra để chặn.

---

## 4. Bằng chứng: golden trajectory, sinh **trước** khi tách

`tests/golden/dwa_trajectories.json` (258 KB) được sinh từ bản code
**trước** khi tách, và **commit riêng một lần** (`0dc3bed`) trước commit
refactor. Thứ tự đó có chủ đích: nó làm câu *"fixture sinh trước khi
tách"* thành thứ đọc được từ lịch sử git, không phải thứ phải tin.

Mỗi ca lưu **lệnh điều khiển** (`v`, `ω` từng bước) **và** quỹ đạo, và
so **repr từng float**, không phải `pytest.approx`:

> Một refactor làm dịch bit cuối của một vận tốc **không phải** refactor
> không đổi gì — nó là refactor đổi một thứ quá nhỏ để cảnh này lộ ra, và
> cảnh sau có thể không tử tế như vậy.

Lệnh được so **trước** quỹ đạo: nếu lệnh dịch thì quỹ đạo dịch vì một lý
do gọi tên được, còn báo "robot đi chỗ khác" trước sẽ chôn mất lý do đó.

### 4.1. Bảy ca, và cả bảy đều bị kiểm là **thật sự** làm điều nó khai

| ca | phủ cái gì |
|---|---|
| `doorway_astar` | căn khe hẹp — heading, polyline distance, goal lookahead cùng cắn một lúc |
| `corridor_rrtstar` | đường toàn cục nhiều đoạn ngắn, bearing đảo chiều — chỗ một `distance_to_polyline` viết lại "tương đương" sẽ sai |
| `oncoming_traffic_astar` | traffic ngược chiều trong hành lang 2 m, gặp nhau ở **0.000 m** khe hở, 90 heading khác nhau |
| `warehouse_three_movers` | **ba** vật cản động ⇒ point cloud nhiều cụm; và episode kết thúc bằng **collision** — nhánh terminal không ca nào khác đi qua |
| `sudden_stop_noisy_replanning` | đủ 7 luồng nhiễu + replanning: pose tin-là vào point cloud trong khi pose thật lăn quỹ đạo, và replan vào lại `reset` |
| `sudden_stop_declared_bound` | nhánh P1 qua cửa sổ động — code mới nhất, ít được thói quen bảo vệ nhất |
| `pillars_coarse` | mật độ lấy mẫu `dwa_coarse` + `allow_reverse`, trên sân có cột để robot phải lách |

**Hai ca đã bị loại sau khi đo, và cả hai là cùng một lỗi.**

*`crossing_obstacle`* nghe như ca traffic và **không phải**: robot đi lướt
qua người đi bộ ở **1.29 m** mà không đổi hướng, cả episode có đúng **ba**
heading khác nhau. Một golden case đi đường thẳng thì ghim một đường
thẳng. Thay bằng `bidirectional_corridor`, đo được khe hở 0.000 m.

*`open_space` + `allow_reverse`* — đo ra **1** heading duy nhất, và tệ
hơn: chạy với `allow_reverse=True` cho quỹ đạo **giống hệt từng byte** với
`allow_reverse=False`. Tức nhãn "reverse" của ca đó là nhãn suông.

Đây đúng loại lỗi đã mắc ở P1 hai lần: **một phép đo trông sạch sẽ mà
không đo thứ nó khai**. Nên cả hai được thay, và tiêu chí phủ trở thành
**assertion đọc từ chính fixture** chứ không phải câu trong comment:

- `min_dynamic_gap` được ghi vào fixture, và ca traffic phải có khe hở
  **< 0.2 m** — con số này là thứ loại `crossing_obstacle`;
- tập status phải chứa **cả** `success` lẫn `collision`;
- phải có ca **replan** (`plans` > 1);
- phải có ca **không** có vật cản động, nếu không nhánh point-cloud-rỗng
  không được đi qua.

### 4.2. `allow_reverse` — ghim bằng thứ nó **không** làm

Bản đầu của file test khẳng định *"có ca đi lùi"*. **Sai**: bật cờ lên nới
sàn cửa sổ vận tốc xuống, nhưng `weight_velocity` ưu tiên tiến và không
gì trả giá cao hơn, nên controller **không bao giờ** chọn vận tốc âm trên
bất cứ cảnh nào đang ship.

Khẳng định đúng, và mạnh hơn: **hai lượt chạy giống hệt nhau từng byte.**
Một refactor làm hỏng phép kẹp `-max_linear_velocity if allow_reverse
else 0.0` sẽ đổi sàn cửa sổ, đổi sàn thì đổi lưới lấy mẫu, và đổi lưới thì
hiện ra ngay ở đây.

---

## 5. Kết quả

**Cả bảy ca giống hệt từng float sau khi tách.** Không lệnh nào, không
điểm quỹ đạo nào, không plan nào dịch.

Refactor này là thứ dễ nhất để lặng lẽ làm hỏng mọi số đo đã có, và cách
duy nhất để biết nó không xảy ra là đo — không phải đọc lại diff.

---

## 6. Kiểm chứng

| Việc | Kết quả |
|---|---|
| `tests/test_dwa_core_refactor.py` | **19 passed** — 7 ca × (lệnh, episode) + 5 test về chất lượng fixture |
| `tests/test_dwa.py` · `test_hard_feasible_set.py` · `test_admissible_stopping.py` · `test_nav_stack.py` · `test_recovery.py` · `test_replanning.py` · `test_fairness.py` (gồm cả golden) | **209 passed, 1 skipped** (7m18s) |
| `ruff check .` | sạch |
| Full backend suite | **chưa chạy — chờ lệnh** |

---

## 7. Còn lại

Tiếp theo là **P3 — rollout không-thời gian**: `dwa_predictive/planner.py`
mới, `DWAPredictiveConfig`, giao diện nội bộ nhận
`tuple[ObstacleTrack, ...]`, và phép broadcast `(N,K,2) − (1,K,M,2)`. Ở
pha đó tracks **được tiêm vào từ tham số**, chưa có tracker — đó chính là
thứ cho phép P4 cắm oracle vào.

Hai việc P2 để lại:

- **`local_version` vẫn cứng `"v1"`.** Giờ hai controller sắp dùng chung
  `dwa_core.py`, món nợ này đắt hơn hẳn: một bản sửa ở lõi sẽ đổi **cả
  hai** ứng viên mà không artifact nào ghi lại. Trả ở **P6 việc 4**, bằng
  checksum của module controller **cộng** lõi dùng chung.
- **Golden fixture là hợp đồng, không phải ảnh chụp.** Nó chỉ có nghĩa
  chừng nào không ai regenerate nó để test hết đỏ. Điều đó ghi thẳng
  trong docstring của file test, kèm cách regenerate và câu *"lý do
  không bao giờ là test vừa đỏ"*.

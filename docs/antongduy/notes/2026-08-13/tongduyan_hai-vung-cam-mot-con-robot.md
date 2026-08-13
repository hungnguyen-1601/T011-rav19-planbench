# Hai vùng cấm, một con robot — vì sao replan 55 lần vẫn không thoát

**Ngày:** 2026-08-13 · **Loại:** quan sát/điều tra, không đổi dòng code nào
trong lúc điều tra · **Trạng thái:** đã tìm ra gốc rễ, chưa sửa

---

## 0. Tóm tắt một đoạn

Trên `sudden_stop`, robot dừng cách xe đẩy **0.31 m** — hợp lệ theo đúng
phép kiểm của bộ điều khiển cục bộ — rồi replan **55 lần trong 120 giây**
mà lần nào cũng nhận `"no path exists between start and goal"`.

Nguyên nhân **không phải** simulator khắt khe, **không phải** thế giới bị
chặn, và **không phải** thuật toán tồi. Nguyên nhân là trong hệ đang tồn
tại **hai vùng cấm khác nhau quanh cùng một vật cản**, chênh nhau
**0.30 m**, và **bộ điều khiển cục bộ không biết vùng của bộ lập kế hoạch
toàn cục tồn tại**:

| | ngưỡng | đo bằng gì |
|---|---|---|
| DWA từ chối một quỹ đạo khi khoảng hở ≤ | **0.31 m** | khoảng cách **liên tục** tới hình học vật cản |
| A* coi ô là cấm trong bán kính | **0.61 m** | **ô lưới**, sau khi nới rộng |

`0.31 = robot.radius (0.26) + safety_margin (0.05)`
`0.61 = robot.radius (0.26) + √2 × resolution (0.354)`

Toàn bộ phần chênh là số hạng `√2 × resolution` — một **đệm chống lượng
tử hoá lưới**, không phải khoảng an toàn vật lý.

Robot đỗ ở nơi **chính nó cho là hợp lệ**, và nơi đó nằm **sâu 0.30 m bên
trong** vành cấm của bộ lập kế hoạch. Nó không phớt lờ vùng cấm — vùng
cấm ấy **không phải một đầu vào của nó**.

---

## 1. Triệu chứng, đúng như dev nhìn thấy

- Sân thử, `astar+dwa` + `dwa_balanced`, `sudden_stop`, replanning **bật**
- `Replanning: on` hiện đúng trên bảng điều kiện ⇒ cài đặt tới nơi
- Kết thúc `stuck`, `moved only 0.042 m in the last 10.0s`
- Sau khi bật hiển thị: **55 lần replan** trong 120 s, không lần nào ra đường
- Đã **tắt localization noise** — vẫn thế

---

## 2. Chuỗi đo, và hai chẩn đoán sai của tôi trên đường đi

Ghi lại cả hai lần sai, vì mỗi lần sai loại bỏ được một giả thuyết và
lần thứ ba mới đúng. Bỏ chúng đi thì bản ghi này đọc như thể tôi nhìn
phát ra ngay, mà không phải.

### Đo 1 — engine có chạy không?

Chạy `run_stack` độc lập với chính profile đó: `dwa_coarse`,
`dwa_balanced`, `dwa_default` đều **success, 1 replan**. Engine không sai.

### Đo 2 — khác biệt nằm ở nhiễu

Deployment tạo qua form bật **cả 7 luồng nhiễu**; profile shipped chỉ có
2. Chạy lại với 7 luồng: **tái hiện chính xác** — 378 bước, đúng câu
*"moved only 0.042 m in the last 10.0s"*.

### Đo 3 — `_replan` có bắn không?

Bọc `_replan` để ghi lại:

```
_replan runs: 1
   status=stuck  success=False  reason=no path exists between start and goal
```

**Có bắn, và thất bại.** Không sự kiện nào ghi lại. → phát hiện phụ #1
(mục 4).

### ❌ Chẩn đoán sai lần 1: "điểm xuất phát bị chặn"

Tôi đo `collides_with_grid(pose, robot_radius, grid)` = True và kết luận
A* từ chối start.

**Sai.** A* có nhánh riêng trả `"start is inside an obstacle"`; lỗi ta
nhận là `"no path exists"`. Và `free()` của A* cho thấy nó coi robot là
**một điểm**, không nới bán kính — nên phép đo tôi dùng đo một thứ A*
không hề dùng.

### ❌ Chẩn đoán sai lần 2: "lưới replan chặn kín lối"

Flood fill lưới `_map_as_the_robot_sees_it` với robot-điểm:

```
marked cells: 180 -> 208
start cell (17,24) blocked: False
goal  cell (18,50) blocked: False
reachable cells from start: 1808 | goal reachable: True
```

**Đích tới được.** Nên lưới đó không phải thứ A* nhận.

### ✅ Đọc hết `_replan` — mắt xích còn thiếu

```python
believed = _map_as_the_robot_sees_it(...)   # lưới tôi vừa flood fill
grid     = _planning_grid(believed, scenario)   # ← NỚI RỘNG ở đây
return global_planner.plan(_with_free_start_cell(grid, position), ...)
```

`_planning_grid` nới rộng `robot.radius + √2 × resolution`. Đó mới là
lưới A* nhận.

### ✅ Đo cuối — robot bị quây kín

```
bán kính robot   0.26 m
DWA keep-out     0.31 m
A* inflation     0.61 m
ô robot đứng     đã được _with_free_start_cell giải phóng
láng giềng trống 0 / 8
```

**Đây là toàn bộ câu chuyện.** `_with_free_start_cell` đã tồn tại từ
trước và làm đúng việc của nó — giải phóng ô robot đứng. Nhưng **cả 8
láng giềng đều bị nới-chặn**, nên A* vào được ô xuất phát và **không bước
nổi một bước**. Vì thế lỗi là `"no path exists"` chứ không phải
`"start is inside an obstacle"`.

Robot không nhúc nhích giữa các lần thử, nên **cả 55 lần replan đều gặp
đúng một cấu hình** và cho đúng một kết quả.

---

## 3. Vì sao đây là khuyết tật của bộ khung, không phải của thuật toán

Cần phân biệt rõ, vì hai thứ này dẫn tới hai hành động khác nhau:

- **Không có phép so nào bị lệch.** Mọi ứng viên đều đâm vào cùng bức
  tường, cùng một cách. Con số đo ra vẫn công bằng giữa các ứng viên.
- **Nhưng mọi ứng viên đều bị tước khả năng phục hồi.** Câu hỏi *"stack
  này có tự thoát được khi bị chặn không"* trở thành **không trả lời
  được** — mọi câu trả lời đều là "không", vì lý do nằm ở harness.

Đây **cùng hình dạng** với hai thứ đã gỡ trước đó trong dự án:

| | tạo tác | hệ quả |
|---|---|---|
| HĐ-4.1 | lưới replan từng được cấp ground truth | điều kiện đánh giá quyết định kết quả |
| 6.8.0 | trần `max_replans` do người chọn | stack thoát ở lần thứ 4 bị chấm là hỏng vì cái trần |
| **cái này** | hai vùng cấm lệch nhau 0.30 m | không stack nào phục hồi được, vì lý do của lưới |

Cả ba đều là **một điều kiện của bộ khung lặng lẽ quyết định kết quả**.

---

## 4. Ba phát hiện phụ, đã sửa trong lúc điều tra

### 4.1. Replan thất bại hoàn toàn im lặng

`replan_count` chỉ đếm lần **thành công**; không sự kiện nào ghi lần thất
bại. Nên *"chưa từng thử"* và *"đã thử, planner từ chối"* ra **cùng một
khoảng trống** — mà đó là **hai chẩn đoán ngược nhau**: cái đầu chỉ vào
cài đặt, cái sau chỉ vào thế giới. Đã thêm sự kiện `replan_failed`.

### 4.2. Một lần từ chối kết thúc cả episode

Trái thẳng luật đã chốt (*"replan bao nhiêu lần tùy ý, miễn thoát được
hoặc bị timeout"*). *"Giờ không có đường"* không phải *"không có đường"*,
và xe cộ thì di chuyển. Đã sửa: chạy tiếp tới hết timeout. Không sợ quay
vòng — bộ dò stuck cần trọn một cửa sổ nữa mới kích lại, nên các lần thử
cách nhau ~10 s thời gian mô phỏng và mỗi lần đều bị tính tiền A*.

### 4.3. `replan_count` đếm sai thứ

Đếm lần thành công báo `3` cho một episode hỏi global planner **11 lần**
— giấu mất 8 lần từ chối, tức **nửa đắt tiền** và cũng là nửa **giải
thích vì sao robot vẫn đứng đó**. Đã đổi sang đếm **lần thử**.

---

## 5. UI: vành cấm thật gấp 2.5 lần hình đang vẽ

| | bán kính |
|---|---|
| Hình tròn xe đẩy đang vẽ trên canvas | **0.40 m** |
| Vành cấm thật với A* | **1.01 m** (= 0.40 + 0.61) |

Chênh **0.61 m**, và **hoàn toàn vô hình**.

Đây là lý do câu hỏi này khó chẩn đoán từ màn hình chứ không phải người
dùng nhìn sót. Trên ảnh chụp, robot trông như đang đứng giữa một khoảng
trống rộng rãi cách xe đẩy nửa mét — và theo hình học thì đúng thế thật.
Cái không vẽ ra mới là cái chặn nó.

---

## 6. Điều đáng ghi nhớ ngoài ca bệnh này

**Khi hai tầng cùng có khái niệm "vùng cấm", chúng phải hoặc là một, hoặc
biết về nhau.** Ở đây chúng không phải một (0.31 vs 0.61) và không biết
về nhau (DWA không hề lập kế hoạch trên lưới nới rộng). Khoảng chênh
không tự biểu hiện thành lỗi ở đâu cả — nó chỉ biểu hiện thành **một con
robot đứng im ở một chỗ trông hoàn toàn hợp lệ**.

Và số hạng gây ra toàn bộ chênh lệch — `√2 × resolution` — là một **đại
lượng của lưới**, không phải của thế giới. Đổi độ phân giải bản đồ là đổi
kích thước vùng cấm mà không ai khai báo gì. Trên bản đồ 0.05 m/ô thì
chênh lệch chỉ còn 0.07 m và ca bệnh này gần như không xảy ra; trên
0.25 m/ô thì nó xảy ra chắc chắn.

---

## 7. Bảng số để tra nhanh

```
sudden_stop      : phòng trống 14.0 × 9.0 m, lưới 56 × 36 ô, resolution 0.25 m
mission          : (1.5, 4.5) → (12.5, 4.5)
xe đẩy 'cart'    : r = 0.40 m, dừng hẳn tại (7.0, 4.5) sau 3.5 s
robot            : r = 0.26 m (deployment), v_max 0.8 m/s
robot dừng tại   : x = 6.07, y = 4.50  (mặt robot ở 6.33; mặt xe ở 6.60)
DWA keep-out     : 0.31 m = 0.26 + safety_margin 0.05
A* inflation     : 0.61 m = 0.26 + √2 × 0.25
chênh lệch       : 0.30 m — toàn bộ là đệm lượng tử hoá lưới
láng giềng trống : 0 / 8
```

Hướng xử lý xem `docs/antongduy/plans/2026-08-14/vung-cam-va-kha-nang-phuc-hoi.md`.

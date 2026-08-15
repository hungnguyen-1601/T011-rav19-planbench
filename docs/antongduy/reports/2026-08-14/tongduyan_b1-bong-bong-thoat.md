# B1 — nới lớp đệm quanh robot, không nới bức tường

**Ngày:** 2026-08-14 · **Nền:**
`docs/antongduy/plans/2026-08-14/vung-cam-va-kha-nang-phuc-hoi.md` ·
`docs/antongduy/notes/2026-08-13/tongduyan_hai-vung-cam-mot-con-robot.md`

---

## 1. Đã làm gì

`_with_free_start_cell` (giải phóng **một** ô) thành `_with_room_to_leave`
(giải phóng **một bong bóng**), với đúng một luật:

> Giải phóng những ô bị chặn **trên lưới đã nới**, nhưng **trống trên lưới
> chưa nới**. Tức chỉ gỡ thứ do lớp đệm sinh ra, **không bao giờ** gỡ một
> ô đang giữ một tia LiDAR thật.

Bong bóng giới hạn trong bán kính inflation quanh robot — ngoài đó bản đồ
giữ nguyên lớp đệm như cũ.

Thêm `_inflation_radius(map_data, scenario)` làm **định nghĩa duy nhất**
của `robot.radius + √2 × resolution`. Trước đó con số này viết inline; hai
bản sao của nó chính là cách hai tầng lệch nhau ngay từ đầu.

**Điều được phép khẳng định**, không phải tiện tay: engine kết thúc episode
**ngay khi** robot chồng lên vật cản, nên một robot còn đang lăn bánh là
robot **chứng minh được** không nằm trong vật cản. Lập luận này đã có sẵn
trong docstring cũ; B1 chỉ áp dụng nó cho đúng phạm vi thay vì cho một ô.

---

## 2. Đo lại — đúng ba kết cục plan đã liệt kê

| cảnh | trước B1 | sau B1 |
|---|---|---|
| 7 luồng nhiễu (form) | replan **hỏng 10/10** | replan **ra đường 10/10**, `failed=0` |
| nhiễu shipped (2 luồng) | success 582 bước | success **556 bước** — không hồi quy |
| lưới 0.125 m thay vì 0.25 | — | `failed=0` |

**Khuyết tật harness đã hết.** Nhưng episode 7-nhiễu vẫn `timeout`, tức
rơi vào **hàng thứ hai** của bảng trong plan: *replan ra được đường nhưng
vẫn không qua → giới hạn thật của ứng viên*.

### Cô lập được thủ phạm còn lại

```
7 luồng nhiễu           timeout   gần đích nhất 6.27 m   10 lần replan
bỏ command_latency      success   gần đích nhất 0.18 m    1 lần replan
bỏ odometry_bias        timeout   gần đích nhất 6.26 m
bỏ lidar_dropout        timeout   gần đích nhất 6.27 m
```

**`command_latency_steps: 2`** là thứ giữ robot lại. Ở `control_period`
0.05 s đó là **100 ms trễ chấp hành**: DWA tính quỹ đạo với giả định lệnh
có hiệu lực ngay, rồi luôn hành động trên một quyết định cũ 100 ms. Sát
vật cản, ở đúng vành keep-out 0.31 m, chừng đó đủ để nó không thao tác nổi
động tác lách.

Đây là **một kết quả thật về ứng viên**, không phải lỗi — và đúng loại câu
hỏi mà B1 sinh ra để làm cho trả lời được. Trước B1 mọi ứng viên đều tắc ở
harness nên câu hỏi này không tồn tại.

---

## 3. Test

`tests/test_b1_room_to_leave.py`, 8 test, chia theo ba nhóm khẳng định:

**Robot rời được chỗ nó đứng**
- cảnh từng từ chối 55 lần nay **không từ chối lần nào** — khẳng định trên
  *số lần từ chối*, **không** trên `success`: robot có qua được xe đẩy hay
  không là câu hỏi về ứng viên, và B1 chỉ nói về việc harness thôi trả lời
  hộ. Khẳng định dừng đúng chỗ thay đổi dừng.
- ca vốn chạy được **vẫn chạy** — nới rộng mà làm hỏng ca đang chạy là đổi
  chác tồi
- **giữ đúng ở lưới 0.125 m**: toàn bộ khoảng chênh sinh ra từ một số hạng
  tỉ lệ với kích thước ô, nên bản vá chỉ đúng ở 0.25 m là bản vá gọt theo
  đúng một bản đồ tình cờ lộ lỗi

**Chỉ nới lớp đệm, không nới gì khác**
- **không ô nào giữ tia thật bị giải phóng** — hàng rào duy nhất chống
  việc "sửa" bằng cách nới quá tay. Bong bóng xoá ô có vật sẽ trả về một
  đường xuyên thẳng qua xe đẩy: trông như một lần cứu hộ, thực chất là một
  vụ va chạm đợi bộ điều khiển từ chối
- **nới cục bộ**: không ô nào ngoài bong bóng bị đổi. Nới toàn cục là một
  thay đổi khác mang tên thay đổi này — mọi đường đi trong episode sẽ chạy
  sát mọi bức tường, không riêng đường rời khỏi chỗ đang kẹt
- `√2 × resolution` **chỉ có một định nghĩa** trong `nav_stack.py`

**Đường thất bại vẫn còn nguyên dây**
- B1 gỡ **lý do harness** khiến replan về tay không; nó không làm việc từ
  chối trở nên bất khả, và không được phép thế. Robot bị quây kín thật thì
  vẫn không có đường, và điều đó vẫn phải lên tới màn hình
- `replan_count` vẫn đếm **lần thử**, không đếm lần thành công

---

## 4. Ba test cũ bị xoá, và lý do

`TestAReplanThatFindsNothingIsNotSilent` ghim **triệu chứng của lỗi** —
rằng `sudden_stop` sinh ra sự kiện `replan_failed`. B1 làm lỗi hết, nên
triệu chứng hết, nên chúng đỏ.

Không xoá cho xanh: hai khẳng định **còn sống** của chúng (đường thất bại
còn nguyên dây; `replan_count` đếm lần thử) chuyển sang
`TestAReplanThatStillFindsNothingIsRecorded` trong file mới, khẳng định
trên chính mã nguồn thay vì trên một cảnh không còn thất bại nữa.

---

## 5. Còn lại

- **B4 (vẽ vành cấm lên UI) chưa làm.** Vẫn đáng làm: canvas vẽ xe đẩy
  r=0.40 m trong khi vành planner tránh là r=1.01 m. `_inflation_radius`
  giờ đã là một hàm để phía vẽ trích dẫn đúng con số đó.
- **B3 (hợp nhất hai vùng cấm) chưa bàn.** Sau B1 nó trở thành câu hỏi
  thiết kế thong thả đúng như plan dự đoán, không còn là bản vá gấp.
- **`command_latency_steps` là câu hỏi thật tiếp theo.** Nếu muốn
  `sudden_stop` qua được với trễ 100 ms thì đó là câu hỏi về `safety_margin`
  / `weight_clearance` — tức **một ứng viên mới** trong `CONTROLLER_CONFIGS`,
  không phải một núm vặn trên deployment.

---

# B4 — vẽ vành cấm, nhạt

## 1. Vấn đề

Canvas vẽ xe đẩy **r = 0.40 m**; vành planner tránh là **r = 1.01 m** —
gấp hai lần rưỡi, và vô hình. Một con robot đỗ cách xe nửa mét **trông
như đang đứng giữa khoảng trống**, còn lý do nó không replan nổi từ đó
thì không được vẽ ở đâu cả.

Chuyện đó ngốn trọn một phiên để suy ra từ đầu. Vẽ nó ra là thứ khiến lần
sau gặp cùng lớp vấn đề thì **đọc được** thay vì phải đi dò.

## 2. Nguồn duy nhất của con số

`apps/web/src/lib/keepOut.ts` — `inflationRadius(resolution, robotRadius)`
và `keepOutRadius(...)`. Đây **là một bản sao của định nghĩa Python**, và
không có cách nào tránh được điều đó (hai ngôn ngữ khác nhau). Nên bản sao
được **đặt tên, để một chỗ, và ghim bằng test đọc thẳng `nav_stack.py`**
để đối chiếu.

Hai bản sao gõ tay của một bán kính inflation trôi khỏi nhau **chính là**
cách keep-out của bộ điều khiển và của planner lệch nhau 0.30 m ngay từ
đầu. Không lặp lại chuyện đó bằng cách gõ lại lần thứ ba.

Thiếu `resolution` hoặc `robotRadius` thì trả `null` và **không vẽ gì** —
một vành tính từ bán kính robot đoán mò là bức tranh về một keep-out
không ai có, **tệ hơn không vẽ**, vì nó trông có thẩm quyền.

## 3. Nhạt, và nằm dưới

Đúng yêu cầu: đủ nhận ra, không át hình thật.

| | |
|---|---|
| Nền | `rgba(240, 180, 41, 0.07)` |
| Viền | `rgba(240, 180, 41, 0.35)`, **nét đứt**, dày 1 px |
| Thứ tự vẽ | **trước** vật cản, nên vật cản luôn nằm **trên** vành của chính nó |
| Màu | **cùng tông** với vật cản — màu khác sẽ đọc thành một vật thứ hai trong cảnh |

**Nét đứt chứ không nét liền**, vì vành liền đọc thành một bức tường — mà
đó đúng là thứ nó không phải: bộ điều khiển **đi qua nó** mỗi lần lách sát
vật, chỉ planner mới từ chối vạch đường xuyên qua.

Ở 2.5D vành nằm **phẳng trên mặt sàn, không đùn cao**: đùn lên sẽ thành
một hình trụ, mà hình trụ đọc thành một vật thứ hai đang đứng đó chứ không
phải một biên trên sàn.

## 4. Test

`apps/web/src/app/__tests__/keep-out-ring.test.tsx`, 10 test:

- công thức khớp `robot.radius + √2 × resolution`, và **đối chiếu với
  chính `nav_stack.py`** đọc từ đĩa — kèm khẳng định biểu thức đó chỉ xuất
  hiện **một lần** trong file Python
- thiếu đầu vào thì **trả `null`**, không đoán
- alpha nền < 0.15, alpha viền < 0.5, cùng tông với vật cản
- nét đứt, **và có trả `setLineDash([])` về** — bỏ quên sẽ làm nét đứt
  lây sang thứ vẽ kế tiếp
- **thứ tự**: vành trước vật cản, ở cả hai chế độ xem
- 2.5D giữ vành **phẳng** (không dùng `COLOR.obstacleSide`)
- **không chế độ xem nào tự tính bán kính** — không file nào chứa
  `Math.SQRT2 *` ngoài `keepOut.ts`

Suite web: **663 passed**.

## 5. Còn lại

- Vành vẽ cho vật cản **tĩnh và động như nhau**, vì planner nới rộng mọi
  thứ nó vạch đường quanh. Với hình chữ nhật thì vẽ từ tâm theo bán kính
  đường tròn ngoại tiếp — một biên bo góc chính xác sẽ trung thực hơn và
  **khó đọc hơn**, mà điều cần nói ở đây là *"có một khoảng đệm, cỡ chừng
  này"*, không phải một đường biên để ai đó đo trên màn hình.
- **Chưa có chú giải trên UI** nói vành đó là gì. Đáng thêm một dòng: vẽ
  mà không nói sẽ khiến người đọc tưởng robot suýt đâm. Đây là việc nhỏ
  còn thiếu của B4.

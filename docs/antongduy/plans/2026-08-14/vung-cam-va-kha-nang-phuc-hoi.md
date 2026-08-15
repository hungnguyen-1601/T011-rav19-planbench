# Kế hoạch 14-08 — vùng cấm và khả năng phục hồi

**Nền:** `docs/antongduy/notes/2026-08-13/tongduyan_hai-vung-cam-mot-con-robot.md`
**Trạng thái:** chờ dev duyệt · chưa động vào code

---

## 0. Vấn đề, gọn lại

Hai vùng cấm quanh cùng một vật cản, lệch **0.30 m**, và tầng cục bộ
không biết vùng của tầng toàn cục tồn tại:

```
DWA keep-out   0.31 m = robot.radius + safety_margin
A* inflation   0.61 m = robot.radius + √2 × resolution
```

Robot đỗ ở nơi nó cho là hợp lệ (0.31 m), nơi đó nằm sâu 0.30 m trong
vành cấm của planner, và A* **không bước nổi một ô** — `0/8` láng giềng
trống. Kết quả: replan 55 lần, không lần nào ra đường.

**Không phép so nào bị lệch** (mọi ứng viên đâm cùng một tường), nhưng
**không ứng viên nào phục hồi được**, nên câu hỏi *"stack này có tự thoát
khi bị chặn không"* hiện **không trả lời được**.

---

## 1. Bốn hướng, và điều mỗi hướng thực sự khẳng định

### B1 — Giải phóng vùng lân cận, không chỉ một ô

`_with_free_start_cell` đã giải phóng ô robot đứng. Mở rộng thành: giải
phóng mọi ô nằm trong bán kính inflation quanh robot, tức đúng phần lưới
đang cấm robot chỉ vì **chính robot đang ở đó**.

**Khẳng định:** *"một robot đang lăn bánh thì chứng minh được là nó không
nằm trong vật cản"* — engine kết thúc episode ngay khi robot chồng lên
vật cản, nên robot còn chạy nghĩa là chỗ nó đứng trống. Lập luận này đã
được viết sẵn trong docstring của `_with_free_start_cell`; B1 chỉ áp dụng
nó cho đúng phạm vi thay vì cho một ô.

- ✅ **Không đổi thứ đang được đo** — hành vi ứng viên nguyên vẹn
- ✅ Chuẩn công nghiệp (nav2 và tương tự đều nới điểm xuất phát)
- ⚠️ Vài mét đầu của đường trả về đi qua vùng nới. Chấp nhận được: DWA
  vẫn kiểm va chạm liên tục trên từng bước, nên đường đi qua vùng nới
  **không** đồng nghĩa với đi qua vật cản
- ⚠️ Phải chặn được trường hợp thoái hoá: nếu giải phóng quá tay thì
  đường trả về có thể xuyên qua chính cái xe đẩy. Ràng buộc: **chỉ giải
  phóng ô bị chặn do nới rộng, không bao giờ giải phóng ô bị chặn do có
  vật thật**

**Ước lượng:** 2–3 giờ kể cả test.

---

### B2 — Giảm số hạng `√2 × resolution` riêng cho lưới replan

Số hạng này là **đệm chống lượng tử hoá lưới**, không phải khoảng an toàn
vật lý. Nó tồn tại để một đường đi chéo qua góc ô không cắt vào vật cản.

- ✅ Sửa đúng chỗ gốc của khoảng chênh
- ❌ Con số thay thế lại là **một số do người chọn** — đúng loại núm vặn
  mà bỏ `max_replans` là để tránh
- ❌ Giảm đệm là **giảm biên an toàn của đường đi**, không chỉ giảm biên
  của điểm xuất phát. Đổi một khuyết tật cục bộ lấy một rủi ro toàn cục

**Đánh giá: không nên làm một mình.** Có thể cân nhắc kèm B1 nếu đo thấy
B1 chưa đủ.

---

### B3 — Cho DWA keep-out **bằng đúng** inflation của A*

Đặt `keep_out = robot.radius + √2 × resolution` thay vì
`robot.radius + safety_margin`. Robot sẽ dừng ở 0.61 m và **không bao giờ
đỗ vào chỗ planner không lập kế hoạch nổi**.

- ✅ **Xoá tận gốc sự bất đồng** thay vì vá hệ quả. Hai tầng dùng chung
  một định nghĩa "vùng cấm" — đúng nguyên tắc rút ra ở mục 6 của note
- ✅ Số dùng có **nguồn gốc**, không phải do ai chọn: nó là inflation của
  planner
- ❌ **Đổi hành vi của mọi ứng viên.** Robot đi thận trọng hơn, qua khe
  hẹp kém hơn, `travel_time` dài hơn. Đây là đổi thứ đang được đo
- ❌ Kéo theo: mọi lượt chạy đã lưu mô tả một robot khác ⇒ theo đúng logic
  đã áp dụng cho `sensor_noise` và `replanning`, sẽ cần **`task_profile_id`
  mới** cho các deployment muốn so với số cũ

**Đánh giá: đúng về nguyên lý, đắt về hệ quả.** Là quyết định của dev chứ
không phải của tôi, vì nó đổi phép đo chứ không sửa lỗi đo.

---

### B4 — Vẽ vành cấm lên UI *(không loại trừ ba hướng trên)*

Canvas vẽ xe đẩy **r = 0.40 m**; vành cấm thật là **r = 1.01 m**. Chênh
0.61 m và vô hình — đó là lý do ca này không chẩn đoán được từ màn hình.

Vẽ thêm một vòng mờ bán kính `r_vật + inflation` quanh mỗi vật cản, ở cả
2D lẫn 2.5D (đi qua `MapView` nên làm một lần).

- ✅ Trả lại cho người dùng khả năng **tự nhìn ra** lớp lỗi này
- ✅ Không đổi gì đang được đo
- ⚠️ Cần nhãn rõ: đây là **vùng planner tránh**, không phải vùng va chạm.
  Vẽ mà không nói sẽ khiến người đọc tưởng robot suýt đâm

**Ước lượng:** 2 giờ.

---

## 2. Đề xuất

**Làm B1 + B4 trước.**

Lý do xếp thứ tự này chứ không phải thứ tự khác:

1. **B1 sửa khuyết tật của bộ khung mà không đụng vào thứ đang được đo.**
   Ca này là harness ngăn mọi ứng viên phục hồi; sửa harness trước, rồi
   mới hỏi ứng viên làm được gì.
2. **B4 là điều kiện để lần sau tự chẩn đoán được.** Nếu chỉ sửa B1 mà
   không vẽ, lần tới gặp biến thể khác của cùng lớp lỗi thì lại mất một
   buổi đi dò.
3. **B3 chỉ nên bàn sau khi B1 chạy.** Nếu B1 đủ để `sudden_stop` thoát,
   thì câu hỏi "có nên hợp nhất hai vùng cấm không" trở thành một câu hỏi
   thiết kế thong thả, không phải một bản vá gấp.

**Sau B1, đo lại `sudden_stop` với đủ 7 luồng nhiễu.** Có ba kết cục và
mỗi kết cục nói một điều khác nhau:

| kết cục | nghĩa là | làm gì tiếp |
|---|---|---|
| `success` | harness từng là thứ duy nhất chặn | xong; B3 thành câu hỏi thong thả |
| `stuck`/`timeout`, replan **ra được đường** nhưng vẫn không qua | giới hạn thật của DWA trong khe hẹp | câu hỏi thật về ứng viên — chỉnh `safety_margin`/`weight_clearance` là hợp lệ |
| vẫn `no path` | còn một tầng nữa chưa lộ | quay lại đo, đừng vá |

Cột thứ ba là lý do phải **đo lại** chứ không tuyên bố xong sau khi code
chạy.

---

## 3. Test phải có

Không đo bằng test tổng hợp — ca này chỉ tái hiện được với **đủ 7 luồng
nhiễu của form**, và đó chính là lý do nó sống sót qua mọi test cũ.

1. **Test tái hiện:** `sudden_stop` + 7 nhiễu + replanning bật ⇒ khẳng
   định replan **ra được đường** (không khẳng định `success` — xem bảng
   trên, đó là câu hỏi khác).
2. **Test không thoái hoá:** đường trả về **không** đi xuyên qua ô có vật
   thật. Đây là hàng rào duy nhất chống việc "sửa" bằng cách nới quá tay.
3. **Test bất biến theo lưới:** cùng cảnh trên resolution 0.05 m và
   0.25 m đều phải replan ra đường. Ca này sinh ra từ một đại lượng của
   lưới, nên hàng rào phải bắt được chuyện đó.
4. **Nếu làm B4:** khẳng định vòng vẽ dùng đúng `robot.radius + √2 ×
   resolution`, không phải một số gõ tay — hai định nghĩa của cùng một
   vành là cách chúng lệch nhau lần sau.

---

## 4. Việc còn treo, không thuộc kế hoạch này

- **`/deployments` và sân thử chưa khai được `safety_margin`.** Ba config
  DWA hiện có (`dwa_coarse/balanced/default`) **chỉ khác nhau mật độ lấy
  mẫu**; không config nào đụng tới `safety_margin`, `weight_clearance`,
  `clearance_cap`. Nếu sau B1 hoá ra cần chỉnh chúng, sẽ cần thêm config
  có tên vào `CONTROLLER_CONFIGS` — một **ứng viên mới**, không phải một
  núm vặn trên deployment.
- **Chưa có test bench nào chạy được deployment cũ.** Deployment tạo
  trước khi có trường `replanning` lưu không có khối đó nên đọc ra là
  tắt; đúng sự thật, nhưng đáng có một dòng trên UI nói *"deployment này
  tạo trước khi có tính năng"* thay vì chỉ hiện `tắt`.

# Báo cáo — Sửa 2 vấn đề UI từ chạy thử (replay benchmark + heading editor)

> **Ngày:** 2026-08-07
> **Nguồn:** phản hồi chạy thử của user sau Đợt 3.1/3.2, không thuộc plan 05-08.
> **Nhánh:** `integrate-tongduyan`

---

## 1. Vấn đề 1 — "Mô phỏng 2D/2.5D biến mất" ở trang kết quả benchmark

### Chẩn đoán

Panel replay (MapCanvas 2D + Scene25D) **không bị xóa** — diff commit
3.1 (`7ce4681`) chỉ thêm 103 dòng vào `benchmarks/[id]/page.tsx`, không
bớt dòng nào. Nguyên nhân là tổ hợp hai điều:

1. Panel replay chỉ render **sau khi bấm nút "Replay"** ở từng dòng
   bảng episodes — trước 3.1 đã vậy.
2. 3.1 chèn thêm 2 panel lớn (Distributions + Export) phía trên bảng
   episodes, đẩy bảng và panel replay xuống rất sâu. Bấm "Replay" thì
   panel hiện ở **cuối trang, ngoài viewport**, không có scroll — nhìn
   như không có gì xảy ra.

Tức không phải regression chức năng mà là regression khả năng nhìn
thấy: tính năng còn nguyên nhưng đường dẫn tới nó gãy.

### Sửa (`apps/web/src/app/benchmarks/[id]/page.tsx`)

1. **Tự mở replay của episode đầu tiên** ngay khi danh sách episodes
   về (`useEffect`, chỉ khi chưa có replay nào mở). Người dùng vào
   trang kết quả là thấy ngay hình robot tương tác với map, không phải
   biết trước rằng có nút để bấm. Không scroll lúc auto-open — nhảy
   trang lúc load sẽ cướp vị trí đọc.
2. **Scroll tới panel khi bấm "Replay" thủ công**: `ref` trên panel +
   `scrollIntoView({ behavior: "smooth" })` qua
   `requestAnimationFrame` (đợi panel render xong mới cuộn).

Toggle 2D / 2.5D giữ nguyên. Replay episode đã lưu vẫn hiển thị robot ở
frame cuối + toàn bộ đường đi (trajectory + planned path) — scrubbing
theo thời gian là F08, thuộc Đợt 4 chưa approve, không làm lẫn vào đây.

## 2. Vấn đề 2 — Chọn góc trong Scenario Editor không trực quan

### Chẩn đoán

Editor có input số (độ) cho start heading và goal heading, nhưng
`MapCanvas.marker()` chỉ vẽ **vòng tròn + nhãn** cho start/goal — theta
không xuất hiện trên hình. Mũi tên hướng chỉ được vẽ cho `robotPose`
(lúc replay). Người dùng gõ 45° mà không có gì trên map xác nhận robot
sẽ nhìn về đâu.

### Sửa (`apps/web/src/components/MapCanvas.tsx`)

`marker()` giờ vẽ thêm **mũi tên hướng** (đoạn thẳng + đầu mũi tên tam
giác) từ tâm marker theo `pose.theta`, cùng màu với marker (xanh cho
start, hồng cho goal):

- chiều dài `max(16px, bán_kính × 2.2)` — luôn nhìn thấy được kể cả khi
  zoom nhỏ;
- quy ước tọa độ đúng với simulator: theta ngược chiều kim đồng hồ từ
  trục +x, canvas y hướng xuống nên dùng `-sin(theta)`— cùng công thức
  với heading của robotPose đang có, hai hình không thể lệch nhau;
- cập nhật trực tiếp: `startPose`/`goalPose` đã nằm trong dependency
  của effect vẽ, nên gõ số độ là mũi tên quay ngay.

Hiệu ứng lan tỏa (chủ ý, có lợi): mọi nơi dùng `MapCanvas` với
start/goal — trang replay benchmark, trang simulate — giờ cũng thấy
hướng xuất phát/đích, không chỉ editor.

## 3. File thay đổi

| File | Thay đổi |
|---|---|
| `apps/web/src/components/MapCanvas.tsx` | `marker()` vẽ mũi tên theta |
| `apps/web/src/app/benchmarks/[id]/page.tsx` | auto-open replay episode đầu; `ref` + `scrollIntoView` khi bấm Replay |

Backend không đổi. Không schema nào đổi.

## 4. Kiểm chứng

```text
npm run typecheck    sạch
npm test             435 passed / 1 failed + 1 suite fail — pre-existing,
                     đúng 2 lỗi đã ghi ở report Đợt 3.2 (models/page.tsx
                     thiếu do merge; path separator Windows), không liên
                     quan diff này
npm run build        Compiled successfully
```

## 5. Giới hạn còn lại

- Replay episode đã lưu vẫn là **ảnh tĩnh frame cuối** (robot đứng ở vị
  trí kết thúc, đường đi vẽ đầy đủ). Tua thời gian + vật cản động theo
  playhead là F08 — cần approve Đợt 4.
- Mũi tên goal heading vẽ cả khi goal heading không ảnh hưởng kết quả
  (simulator hiện chỉ kiểm tra vị trí + tolerance khi về đích). Vẫn vẽ
  vì schema `Pose2D` có theta và người dùng đặt được nó; ẩn đi sẽ gây
  câu hỏi ngược "tôi đặt goal heading để làm gì".
- Chưa có drag-để-xoay heading trên map (plan 2.3 đã loại khỏi phạm vi
  MVP editor); nhập số độ + mũi tên phản hồi tức thời là mức của đợt
  này.

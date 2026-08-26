# Audit UI hai canvas — dùng được cho E2, và thiếu đúng một thứ

**Ngày:** 2026-08-19 · **Loại:** đánh giá hiện trạng, không đổi dòng code nào
**Bối cảnh:** plan `plans/2026-08-18/tang-giai-thich-vi-sao.md` §5 đợt E2 ghi phụ
thuộc là "audit/merge **branch replay**", và §9 để treo "tên branch replay (An
đưa lúc thi hành)". An xác nhận **không có branch replay nào**; thay vào đó vừa
merge `d3ba3b6` (nhánh UI của Tùng) mang giao diện so sánh hai thuật toán bằng
hai canvas.

**Kết luận: khoản treo đó đóng lại được.** Đối tượng audit của E2 không phải một
branch chưa biết tên mà là trang `apps/web/src/app/decisions/[id]/page.tsx` sau
merge. Nó phủ **đúng một nửa** E2.

---

## 1. Những gì merge đã cho, và tại sao nó đúng thứ E2 cần

- **Hai canvas, cùng một `episodeId`.** `CandidateEpisode` render một
  `TraceViewer` mỗi bên, cả hai nhận cùng `episodeId` — tức phép so đang ghép
  cặp theo HĐ-3 chứ không phải đặt cạnh nhau hai episode khác nhau. Đây là điều
  kiện tiên quyết của mọi phép đối chiếu trong tầng "vì sao".
- **Một playhead chung.** `playback.time` truyền xuống cả hai viewer, và
  `frameIndexAt(frames, playbackTime)` tra khung theo **thời gian tuyệt đối**.
  Đó chính là **time-sync** — chế độ 1 trong bảng §4.2 của note thiết kế — đã
  chạy, không phải làm lại.
- **Dropdown chọn episode** (`page.tsx:244`) liệt kê
  `report.sample.episode_context_ids`. Đây đúng chỗ để cắm công thức exemplar
  preregistered của E2; không phải dựng thêm surface mới.
- **Trace payload** có `t`, `x`, `y`, `theta`, `clearance_m`,
  `planner_latency_ms`, `events` thưa, map bit-packed, missions.

## 2. Một cái bẫy tên gọi

`mode` trên trang đó là `"flat" | "raised"` — chế độ **vẽ** 2D/2.5D, **không
phải** chế độ đồng bộ. Khi thêm progress-sync tuyệt đối không chồng lên biến
này: hai khái niệm khác hẳn nhau mà trùng tên là cách nhanh nhất để một người
đọc code sau này nghĩ rằng đã có hai chế độ sync.

## 3. Thiếu gì — và một chỗ thiếu là dữ liệu, không phải UI

| Hạng mục E2 | Trạng thái |
|---|---|
| Time-sync | **đã có** |
| Progress-sync (chiếu arc-length lên L_ref) | chưa có |
| **Polyline L_ref để chiếu lên** | **không có trong `TracePayload`** |
| `projection_quality` + fallback | chưa có |
| Cảnh báo bắt buộc "cùng chỗ ≠ cùng tình huống" | chưa có |
| Điểm phân kỳ (cross-track duy trì + mốc từ event) | chưa có |
| Exemplar preregistered (typical / strongest A / strongest B / safety-critical) | chưa có |
| Evidence chip → nhảy timestamp/region | chưa có |
| Regression | chưa có |

**Chỗ thiếu thật sự là L_ref.** `TracePayload` không mang tuyến tham chiếu;
`l_ref_m` bên metrics chỉ là một **số vô hướng** (độ dài), không chiếu được. Tuyến
thật — global plan — nằm ở episode JSON trường `plans`, và theo đúng sự thật dữ
liệu đã ghi ở E0: `plans` **rỗng với run cũ**, và rỗng nghĩa là "không ghi lại"
chứ không phải "không có plan".

Đây chính là lý do plan viết `projection_quality` **kèm** fallback thay vì chỉ
viết "progress-sync": có tuyến tham chiếu thật thì chiếu lên nó và khai chất
lượng cao; không có thì vẫn chiếu được lên tuyến dự phòng nhưng **phải khai ra**
rằng chất lượng chiếu bị giảm. Im lặng dùng tuyến tạm rồi vẽ hai robot "ở cùng
một chỗ" là đúng loại bằng chứng nghe mạnh hơn dữ liệu mà cả tầng này tồn tại để
chặn.

## 4. Đường đã chốt cùng An (2026-08-19)

**Fallback trước, API sau.** Làm progress-sync ngay với tuyến tham chiếu dự
phòng, khai `projection_quality: degraded` + cảnh báo; khi API trả được global
plan thì nâng lên `reference_plan` mà **không đổi UI**. Lý do chọn: không đụng
`apps/api` trong lúc H-series còn đang chạy, và ngay cả khi API mở rộng xong thì
run cũ vẫn cần đúng nhánh fallback đó — tức nó không phải việc làm tạm rồi vứt.

Hệ quả phải giữ đúng: `projection_quality` là **trường bắt buộc**, không có mặc
định "tốt". Một artifact không nói được nó chiếu lên cái gì thì không được vẽ
progress-sync.

## 5. Việc E2 còn lại sau audit

1. Chọn tuyến tham chiếu + `projection_quality` (`reference_plan` /
   `degraded_candidate_path` / `degraded_straight_line`) + luật fallback.
2. Progress-sync: chiếu arc-length, hai canvas đi theo `s` thay vì `t`, cảnh báo
   bắt buộc gắn liền chế độ.
3. Điểm phân kỳ: cross-track offset vượt ngưỡng **và duy trì** (lọc chênh tốc
   độ), cộng mốc rẻ từ event — replan đầu tiên, dừng đầu tiên, detour bắt đầu.
4. Exemplar preregistered, công thức cứng + tie-break, thay cho thứ tự sample.
5. Evidence chip → nhảy timestamp/region.
6. Regression cho cả bốn.

Prevalence theo detector (mục 5 trong công thức exemplar của note) **vẫn chờ
E3** — exemplar v1 ship bộ tứ, prevalence nối sau, đúng như note đã khai.

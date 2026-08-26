# docs/antongduy — ghi chú làm việc của An (Tống Duy An)

Thư mục này **được commit** để cả team theo dõi được tiến độ và những
thay đổi đã làm.

| Folder | Chứa gì |
|---|---|
| `reports/` | Báo cáo **việc đã làm với code**: ship feature, fix bug, refactor, migration |
| `notes/` | Báo cáo **quan sát/đánh giá**: đánh giá repo, đánh giá feature, phân tích hiện trạng, research |
| `plans/` | **Kế hoạch chờ approve** trước khi triển khai |

Phân biệt: `reports/` = *đã thay đổi gì*; `notes/` = *đã nhìn thấy gì*.

Quy ước đặt tên: `<folder>/<YYYY-MM-DD>/tongduyan_<mô-tả-ngắn>.md`
(riêng `plans/` không bắt buộc tiền tố `tongduyan_`).

## File nền tảng

Đề tài đã **chuyển hướng** (2026-08-08): từ "nền tảng benchmark công
bằng" sang "**Planner Selector** — chọn cấu hình điều hướng tối ưu cho
một deployment cụ thể". Ràng buộc và prior art giữ nguyên; câu hỏi
nghiệp vụ và đầu ra đổi hẳn.

| File | Vai |
|---|---|
| `de-tai-moi-planner-selector.md` | **Đề tài hiện hành.** Lý do, pain point N1–N10, hệ chỉ số, roadmap |
| `../../contracts/CONTRACTS.md` | **Luật.** Khi mâu thuẫn với đề tài, contract thắng. Đã move ra gốc repo (trước đây là `CONTRACTS_1.md` trong thư mục này) |
| `phan-tich-de-bai-benchmark-planning.md` | Đề bài gốc. Vẫn là nguồn cho **ràng buộc** (nhóm 3–4 người, 4–6 tuần, sim-only, không Gazebo) và cho mục 0 prior art. Mục 1–8 đã bị `de-tai-moi` thay thế |

## Đang mở

- `plans/2026-08-08/ke-hoach-chuyen-huong-planner-selector.md` — plan
  tổng 4 tuần cho hướng mới, kèm đánh giá retrofit-vs-rebuild.
- `plans/2026-08-08/backlog-uu-tien-planner-selector.md` — cùng nội dung
  nhưng xếp theo **thứ tự ưu tiên/độ lan tỏa** thay vì theo tuần. Đây là
  bản đang dùng để triển khai.
- Phase 1 (schema gốc) **đã xong**: xem `reports/2026-08-08/` (1.1
  TaskProfile, 1.2 Candidate, 1.3 EpisodeContext) và `reports/2026-08-09/`
  (1.4 chốt hợp đồng).

## Đã đóng băng (giữ lại, không xóa)

Plan và report của hướng cũ vẫn nằm nguyên trong `plans/2026-08-03..07/`
và `reports/2026-08-05..08/`. Chúng ghi lại việc **đã làm thật** (RRT\*,
P02, P03, P04, P05, F09, replanning, Docker) và phần lớn tài sản đó được
tái dùng hoặc đổi vai trong hướng mới — bảng đối chiếu ở mục 1.4 của
plan tổng. Riêng **P05 (held-out + generalization gap)** bị đề tài mới
thay vai bằng Task Neighborhood: code giữ nguyên, không port sang tầng
decision, không quảng bá trên UI mới.

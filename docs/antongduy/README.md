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

`phan-tich-de-bai-benchmark-planning.md` — phân tích đề bài + khảo sát
prior art + roadmap. Đây là **nguồn sự thật** để đối chiếu mọi báo cáo
đánh giá hiện trạng.

## Đang mở

- `notes/2026-08-04/tongduyan_danh-gia-lai-hien-trang.md` — đánh giá
  hiện trạng mới nhất (đối chiếu repo với đề bài).
- `plans/2026-08-04/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`
  — **plan chính, chờ approve**: 6 đợt, từ RRT\* và Docker (Đợt 0) tới
  P01/Optuna (Đợt 5). Đã gộp cả 2 plan treo bên dưới vào hệ thống đợt.
- `plans/2026-08-03/scenario-editor-va-replanning-cong-bang.md` —
  2 plan **chưa triển khai** (Plan A: Scenario Editor → Đợt 2;
  Plan B: Replanning công bằng → Đợt 4). Giữ lại vì chứa phần research
  chi tiết mà plan chính chỉ tóm tắt.

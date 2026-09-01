# Nhật ký An — tra theo chủ đề

278 file, xếp theo ngày trong `reports/`, `notes/`, `plans/`. File này xếp
lại **theo chủ đề**, và chỉ nêu **file mốc** — cái trả lời được câu hỏi
chính của chủ đề đó. Muốn đủ thì duyệt theo ngày.

Quy ước đọc, và vì sao ngày ≠ mức tin cậy: [`../README.md`](../README.md).

---

## 0. Nền tảng — đọc trước nếu muốn hiểu đề tài

| File | Nội dung |
|---|---|
| [de-tai-moi-planner-selector.md](de-tai-moi-planner-selector.md) | **Đề tài hiện hành.** Lý do chuyển hướng, pain point N1–N10, hệ chỉ số, roadmap. 73 KB |
| [phan-tich-de-bai-benchmark-planning.md](phan-tich-de-bai-benchmark-planning.md) | Đề bài gốc. Còn là nguồn cho **ràng buộc** (nhóm 3–4 người, 4–6 tuần, sim-only, không Gazebo) và prior art. Mục 1–8 đã bị `de-tai-moi` thay |
| [plans/2026-08-08/ke-hoach-chuyen-huong-planner-selector.md](plans/2026-08-08/ke-hoach-chuyen-huong-planner-selector.md) | Plan chuyển hướng, kèm đánh giá retrofit-vs-rebuild và bảng đối chiếu tài sản cũ |
| [plans/2026-08-08/backlog-uu-tien-planner-selector.md](plans/2026-08-08/backlog-uu-tien-planner-selector.md) | Cùng nội dung, xếp theo **độ lan toả** thay vì theo tuần. Đây là bản đã dùng để triển khai |

> **Chuyển hướng 2026-08-08.** Từ "nền tảng benchmark công bằng" sang
> "Planner Selector — chọn cấu hình điều hướng tối ưu cho một deployment
> cụ thể". Ràng buộc và prior art giữ nguyên; câu hỏi nghiệp vụ và đầu ra
> đổi hẳn. Mọi thứ ghi trước ngày này đọc với giả định đó.

---

## 1. Nền công bằng — thứ mọi phép so dựa vào

| File | Nội dung |
|---|---|
| [notes/2026-08-11/tongduyan_kiem-toan-tinh-cong-bang-simulator.md](notes/2026-08-11/tongduyan_kiem-toan-tinh-cong-bang-simulator.md) | Kiểm toán: simulator có thật sự cho hai stack cùng điều kiện không |
| [reports/2026-08-11/tongduyan_kiem-tinh-cong-bang-va-mot-lan-di-sai-huong.md](reports/2026-08-11/tongduyan_kiem-tinh-cong-bang-va-mot-lan-di-sai-huong.md) | Sửa, kèm ghi lại **một lần đi sai hướng** — đọc để khỏi lặp |
| [reports/2026-08-08/tongduyan_phase-1-3-episode-context-va-ghep-cap.md](reports/2026-08-08/tongduyan_phase-1-3-episode-context-va-ghep-cap.md) | `EpisodeContext` và cơ chế ghép cặp |
| [reports/2026-08-09/tongduyan_phase-1-4-chot-hop-dong-va-dynamic-obstacles.md](reports/2026-08-09/tongduyan_phase-1-4-chot-hop-dong-va-dynamic-obstacles.md) | Chốt hợp đồng + vật cản động |
| [reports/2026-08-08/tongduyan_dot-b-noi-day-replanning-vao-simulate-va-ui.md](reports/2026-08-08/tongduyan_dot-b-noi-day-replanning-vao-simulate-va-ui.md) | Replanning nối vào `nav_stack` — **bất biến dễ phá nhất trong repo** |
| [notes/2026-08-16/tongduyan_q0-do-lai-do-phan-giai-lidar.md](notes/2026-08-16/tongduyan_q0-do-lai-do-phan-giai-lidar.md) | Đo lại độ phân giải LiDAR |

## 2. Tầng quyết định — cổng, ΔU, Decision Card

| File | Nội dung |
|---|---|
| [reports/2026-08-10/tongduyan_phase-3-2-gates.md](reports/2026-08-10/tongduyan_phase-3-2-gates.md) | Cổng G1–G6 |
| [reports/2026-08-10/tongduyan_phase-3-3-objectives.md](reports/2026-08-10/tongduyan_phase-3-3-objectives.md) | Hàm mục tiêu |
| [reports/2026-08-10/tongduyan_phase-3-4-paired-bootstrap.md](reports/2026-08-10/tongduyan_phase-3-4-paired-bootstrap.md) | Bootstrap ghép cặp và khoảng tin cậy |
| [reports/2026-08-10/tongduyan_phase-3-5-decision-card-manifest.md](reports/2026-08-10/tongduyan_phase-3-5-decision-card-manifest.md) | Decision Card + manifest |
| [reports/2026-08-11/tongduyan_phase-5-1-mot-tam-card-noi-doi.md](reports/2026-08-11/tongduyan_phase-5-1-mot-tam-card-noi-doi.md) | **Một tấm card nói dối** — nên đọc: cách một card đúng kỹ thuật vẫn sai |
| [reports/2026-08-12/tongduyan_success-rate-min-sanh-giu-co-che-lui-nguong.md](reports/2026-08-12/tongduyan_success-rate-min-sanh-giu-co-che-lui-nguong.md) | Cơ chế lùi ngưỡng |
| [reports/2026-08-12/tongduyan_early-stop-dung-som-candidate-da-truot-cong.md](reports/2026-08-12/tongduyan_early-stop-dung-som-candidate-da-truot-cong.md) | Dừng sớm candidate đã trượt cổng |

## 3. Thuật toán và perception

| File | Nội dung |
|---|---|
| [reports/2026-08-14/tongduyan_p0-lo-hong-phanh-vat-can-lai-gan.md](reports/2026-08-14/tongduyan_p0-lo-hong-phanh-vat-can-lai-gan.md) | Lỗ hổng phanh khi vật cản lại gần |
| [reports/2026-08-14/tongduyan_p3-rollout-khong-thoi-gian.md](reports/2026-08-14/tongduyan_p3-rollout-khong-thoi-gian.md) | Rollout không thời gian |
| [reports/2026-08-15/tongduyan_p5-tracker-va-gia-cua-tri-giac.md](reports/2026-08-15/tongduyan_p5-tracker-va-gia-cua-tri-giac.md) | Tracker và **giá của tri giác** |
| [reports/2026-08-15/tongduyan_tong-ket-p0-p6.md](reports/2026-08-15/tongduyan_tong-ket-p0-p6.md) | **Tổng kết P0–P6** — vào đây trước nếu chỉ đọc một file mảng này |
| [reports/2026-08-16/tongduyan_rut-dwa-predictive-ket-qua-am.md](reports/2026-08-16/tongduyan_rut-dwa-predictive-ket-qua-am.md) | **Kết quả âm** của DWA predictive — đọc để thấy cách dự án xử lý kết quả không như mong đợi |
| [reports/2026-08-14/tongduyan_recovery-phase-3.md](reports/2026-08-14/tongduyan_recovery-phase-3.md) | Recovery behaviour |

## 4. Algorithm Host và plugin

| File | Nội dung |
|---|---|
| [notes/2026-08-18/tongduyan_cau-truc-plugin-algorithm-host.md](notes/2026-08-18/tongduyan_cau-truc-plugin-algorithm-host.md) | Cấu trúc plugin |
| [reports/2026-08-18/tongduyan_tong-ket-h0-h8-va-doi-chieu-dod.md](reports/2026-08-18/tongduyan_tong-ket-h0-h8-va-doi-chieu-dod.md) | **Tổng kết H0–H8** — vào đây trước |
| [reports/2026-08-18/tongduyan_h7-subprocess-lane.md](reports/2026-08-18/tongduyan_h7-subprocess-lane.md) | Lane subprocess: deadline thật, kill được khi treo |
| [reports/2026-08-18/tongduyan_h5-discovery-va-trusted-runtime.md](reports/2026-08-18/tongduyan_h5-discovery-va-trusted-runtime.md) | Discovery đọc manifest **không import code** |
| [reports/2026-08-25/tongduyan_sua-loi-algorithm-host-sau-khi-dung-that.md](reports/2026-08-25/tongduyan_sua-loi-algorithm-host-sau-khi-dung-that.md) | Lỗi chỉ lộ ra khi dùng thật |
| [reports/2026-08-26/tongduyan_them-thuat-toan-mppi-dang-plugin.md](reports/2026-08-26/tongduyan_them-thuat-toan-mppi-dang-plugin.md) | Import MPPI thật dưới dạng plugin |
| [reports/2026-08-24/tongduyan_import-thuat-toan-tren-ui-p0-p4.md](reports/2026-08-24/tongduyan_import-thuat-toan-tren-ui-p0-p4.md) | Đường vào qua UI — **chưa đủ**, xem [`../../03-gaps.md`](../../03-gaps.md) §2.1 |

## 5. Tầng giải thích "vì sao"

| File | Nội dung |
|---|---|
| [notes/2026-08-18/tongduyan_giai-phap-giai-thich-vi-sao-thuat-toan-thang.md](notes/2026-08-18/tongduyan_giai-phap-giai-thich-vi-sao-thuat-toan-thang.md) | Thiết kế gốc của tầng giải thích |
| [reports/2026-08-18/tongduyan_e0-contract-tang-giai-thich.md](reports/2026-08-18/tongduyan_e0-contract-tang-giai-thich.md) | Contract tầng giải thích |
| [reports/2026-08-18/tongduyan_e1-waterfall-delta-u.md](reports/2026-08-18/tongduyan_e1-waterfall-delta-u.md) | Waterfall ΔU |
| [reports/2026-08-19/tongduyan_e3-detector-map-contrast-kb.md](reports/2026-08-19/tongduyan_e3-detector-map-contrast-kb.md) | Detector + map contrast + cơ sở tri thức |
| [reports/2026-08-19/tongduyan_e6a-tool-host-va-hai-checker.md](reports/2026-08-19/tongduyan_e6a-tool-host-va-hai-checker.md) | Tool host + checker |
| [reports/2026-08-19/tongduyan_e2-replay-doi-va-exemplar.md](reports/2026-08-19/tongduyan_e2-replay-doi-va-exemplar.md) | Replay đôi + exemplar |

## 6. AI Analyst — công việc mới nhất, đọc **ngược từ dưới lên**

Đây là mảng đổi nhanh nhất. **Đọc file mới nhất trước**; file cũ nhiều chỗ
đã bị thay.

| File | Nội dung |
|---|---|
| ⭐ [reports/2026-08-31/tongduyan_hieu-nang-that-va-tuong-guard-v2.md](reports/2026-08-31/tongduyan_hieu-nang-that-va-tuong-guard-v2.md) | **Bản hiệu lực.** 90 lượt chấm mù, `explains` 0.56, 0 vi phạm ràng buộc cứng. Thay thế bản 08-30 |
| [reports/2026-08-30/tongduyan_hai-luat-guard-chan-quy-ket-khong-co-cho-dua.md](reports/2026-08-30/tongduyan_hai-luat-guard-chan-quy-ket-khong-co-cho-dua.md) | Hai luật guard chặn quy kết không có chỗ dựa |
| [reports/2026-08-30/tongduyan_rubric-r020-them-truc-episode.md](reports/2026-08-30/tongduyan_rubric-r020-them-truc-episode.md) | Rubric r0.2.0 |
| [notes/2026-08-30/tongduyan_ra-soat-toan-bo-guard.md](notes/2026-08-30/tongduyan_ra-soat-toan-bo-guard.md) | Rà soát toàn bộ guard |
| [notes/2026-08-30/tongduyan_rubric-cu-khong-nhin-thay-loi-chinh.md](notes/2026-08-30/tongduyan_rubric-cu-khong-nhin-thay-loi-chinh.md) | **Rubric cũ không nhìn thấy lỗi chính** — bài học về cách một thước đo hỏng |
| [reports/2026-08-27/tongduyan_ai-analyst-theo-episode.md](reports/2026-08-27/tongduyan_ai-analyst-theo-episode.md) | Chuyển analyst sang scope episode |
| [plans/2026-08-27/ai-analyst-theo-episode.md](plans/2026-08-27/ai-analyst-theo-episode.md) | Plan tương ứng |
| [notes/2026-08-26/tongduyan_preregistration-va-phan-vung-du-lieu.md](notes/2026-08-26/tongduyan_preregistration-va-phan-vung-du-lieu.md) | Preregistration và phân vùng dữ liệu — vì sao holdout tách riêng |
| [notes/2026-08-24/tongduyan_danh-gia-chat-luong-ai-advisor.md](notes/2026-08-24/tongduyan_danh-gia-chat-luong-ai-advisor.md) | Đánh giá chất lượng advisor, model thật |

## 7. Giao diện và trải nghiệm

| File | Nội dung |
|---|---|
| [notes/2026-08-13/tongduyan_danh-gia-ui-hai-luong.md](notes/2026-08-13/tongduyan_danh-gia-ui-hai-luong.md) | Đánh giá UI hai luồng |
| [plans/2026-08-13/refactor-ui-mot-luong.md](plans/2026-08-13/refactor-ui-mot-luong.md) | Refactor về một luồng |
| [notes/2026-08-21/tongduyan_danh-gia-ui-trang-decision-detail.md](notes/2026-08-21/tongduyan_danh-gia-ui-trang-decision-detail.md) | Đánh giá trang Decision, kèm 3 mock HTML cạnh nó |
| [plans/2026-08-21/03-design-system-va-sidebar.md](plans/2026-08-21/03-design-system-va-sidebar.md) | Design system + sidebar |
| [reports/2026-08-22/tongduyan_sua-ui-trang-decision.md](reports/2026-08-22/tongduyan_sua-ui-trang-decision.md) | Thực thi |
| [reports/2026-08-28/tongduyan_bo-sung-81-khoa-i18n-thieu.md](reports/2026-08-28/tongduyan_bo-sung-81-khoa-i18n-thieu.md) | 81 khoá i18n thiếu — nhắc vì sao phải thêm cả `en.json` và `vi.json` |
| [reports/2026-08-27/tongduyan_trang-huong-dan-van-hanh-guide.md](reports/2026-08-27/tongduyan_trang-huong-dan-van-hanh-guide.md) | Trang `/guide` |

## 8. Phân quyền và duyệt

| File | Nội dung |
|---|---|
| [plans/2026-08-27/thiet-ke-role-engineer-reviewer-admin.md](plans/2026-08-27/thiet-ke-role-engineer-reviewer-admin.md) | Thiết kế ba gói quyền — **vì sao không xếp bậc thang** |
| [reports/2026-08-27/tongduyan_role-capabilities-p0-p2.md](reports/2026-08-27/tongduyan_role-capabilities-p0-p2.md) | Thực thi |
| [reports/2026-08-28/tongduyan_sua-401-tren-nhanh-role.md](reports/2026-08-28/tongduyan_sua-401-tren-nhanh-role.md) | Sửa 401 |

## 9. Desktop, release, hạ tầng

| File | Nội dung |
|---|---|
| [plans/2026-08-24/desktop-app-windows.md](plans/2026-08-24/desktop-app-windows.md) | Plan desktop app |
| [reports/2026-08-24/tongduyan_desktop-app-windows-phase-0-den-7.md](reports/2026-08-24/tongduyan_desktop-app-windows-phase-0-den-7.md) | Phase 0–7 |
| [reports/2026-08-25/tongduyan_deploy-desktop-va-runbook.md](reports/2026-08-25/tongduyan_deploy-desktop-va-runbook.md) | Deploy + runbook |
| [reports/2026-08-26/tongduyan_tach-noi-code-va-noi-phat-hanh.md](reports/2026-08-26/tongduyan_tach-noi-code-va-noi-phat-hanh.md) | **Vì sao hai remote** — `origin` public giữ release, `org` private nộp bài |
| [reports/2026-08-26/tongduyan_chot-giu-release-o-repo-public.md](reports/2026-08-26/tongduyan_chot-giu-release-o-repo-public.md) | Chốt giữ release ở repo public. Đọc trước khi đề xuất gộp hai repo |
| [reports/2026-08-26/tongduyan_updater-doc-manifest-qua-cdn.md](reports/2026-08-26/tongduyan_updater-doc-manifest-qua-cdn.md) | Updater đọc manifest qua CDN |
| [reports/2026-08-05/tongduyan_docker-compose-chay-that.md](reports/2026-08-05/tongduyan_docker-compose-chay-that.md) | Docker Compose chạy thật với PostgreSQL |

## 10. Nợ kỹ thuật và rà soát

| File | Nội dung |
|---|---|
| [notes/2026-08-13/tongduyan_no-ky-thuat-ton-dong.md](notes/2026-08-13/tongduyan_no-ky-thuat-ton-dong.md) | Nợ kỹ thuật tồn đọng |
| [reports/2026-08-13/tongduyan_tra-no-ky-thuat.md](reports/2026-08-13/tongduyan_tra-no-ky-thuat.md) | Trả nợ |
| [reports/2026-08-10/tongduyan_don-no-truoc-phase-5.md](reports/2026-08-10/tongduyan_don-no-truoc-phase-5.md) | Dọn nợ trước phase 5 |
| [notes/2026-08-11/tongduyan_ra-soat-commit-cu-co-can-revert-khong.md](notes/2026-08-11/tongduyan_ra-soat-commit-cu-co-can-revert-khong.md) | Rà soát commit cũ |
| [notes/2026-08-13/tongduyan_tinh-nang-co-the-them.md](notes/2026-08-13/tongduyan_tinh-nang-co-the-them.md) | Tính năng có thể thêm — nguồn ý tưởng cho roadmap |
| [notes/2026-08-11/tongduyan_xac-minh-lech-huong-muc-tieu.md](notes/2026-08-11/tongduyan_xac-minh-lech-huong-muc-tieu.md) | Xác minh lệch hướng mục tiêu |

---

## Đọc gì nếu chỉ có 30 phút

1. [de-tai-moi-planner-selector.md](de-tai-moi-planner-selector.md) — mục 1–3
2. [reports/2026-08-15/tongduyan_tong-ket-p0-p6.md](reports/2026-08-15/tongduyan_tong-ket-p0-p6.md)
3. [reports/2026-08-18/tongduyan_tong-ket-h0-h8-va-doi-chieu-dod.md](reports/2026-08-18/tongduyan_tong-ket-h0-h8-va-doi-chieu-dod.md)
4. [reports/2026-08-31/tongduyan_hieu-nang-that-va-tuong-guard-v2.md](reports/2026-08-31/tongduyan_hieu-nang-that-va-tuong-guard-v2.md)
5. [reports/2026-08-11/tongduyan_phase-5-1-mot-tam-card-noi-doi.md](reports/2026-08-11/tongduyan_phase-5-1-mot-tam-card-noi-doi.md)

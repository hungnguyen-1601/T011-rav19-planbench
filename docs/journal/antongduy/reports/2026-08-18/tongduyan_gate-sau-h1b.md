# Gate sau H1b — đo, đối chiếu, verdict

**Ngày:** 2026-08-18
**Prereg:** `plans/2026-08-17/algorithm-host-gate-preregistration.md`
(commit `f15ee25`, **trước** khi H0 bắt đầu — công thức và tiêu chí không
đổi từ đó).
**Trạng thái:** mục 5 của prereg đã điền; verdict **chốt khi An commit**.

---

## 1. Phép đo

| Đại lượng | Giá trị | Cơ sở |
|---|---|---|
| H1_ideal | 2.5–3 ngày | prereg mục 1, khoá từ f15ee25 |
| H1_actual | **1 ngày kỹ thuật** | H1a (SDK, 28 test) + H1b (loader + A5, 21 test) hoàn thành trọn 18-08; thực tế ~0.5 ngày, lấy tròn 1 nghiêng khắt khe |
| schedule_factor | **0.33–0.40** | 1 / (2.5–3.0) |
| ideal(H2..H8) | 10–13 ngày | prereg mục 1 |
| projected_remaining | **3.3–5.2 ngày kỹ thuật ≈ 1.3–2.1 tuần lịch** | factor × ideal, hệ số lịch ×2 đã khai trước |

Vì sao H1_actual thấp hơn ideal nhiều: ideal ước cho người chưa cầm sẵn
bối cảnh; phiên này đi liền sau bốn vòng phản biện nên mọi quyết định
thiết kế đã chốt trước khi gõ dòng code đầu. Hệ số 0.33–0.40 vì thế
**không nên ngoại suy** cho H2–H8 như một kỳ vọng, chỉ dùng đúng vai
công thức gate; trần 3 tuần mới là ràng buộc thật.

## 2. Ba điều kiện

| # | Điều kiện | Kết quả |
|---|---|---|
| 1 | projected ≤ budget | 2.1 tuần ≤ 3 tuần — **đạt** |
| 2 | chiến lược ∨ external demand | An khai "Có" (chiến lược); external "Chưa có" — **đạt** qua vế OR |
| 3 | không blocker research ưu tiên cao hơn | F1 trên critical path nhưng không tranh ngân sách host (10 − 2 = 8 tuần còn cho research; allocation 3 tuần trong prereg là hành vi xếp hạng của An) — **đạt có điều kiện** |

## 3. Verdict

**ĐẠT — tiếp H2–H8**, kèm hai ràng buộc ghi thẳng vào prereg mục 5:

1. Trần 3 tuần cứng — chạm trần là dừng tại phase đang dở, không thương
   lượng lại.
2. F1 không bị đẩy lùi: remaining tụt dưới ~8 tuần trước khi host xong ⇒
   F1 thắng, host dừng ở phase gần nhất hoàn tất.

## 4. Trình tự commit đề xuất (An commit thủ công)

1. H1a — `packages/plugin_sdk/` + `tests/test_plugin_sdk.py` +
   `pyproject.toml` + report H1a.
2. H1b — `policies.py`, `legacy_plugins.py`, sửa `candidates.py`,
   `tests/test_legacy_plugins.py`, `test_candidate_bridge.py` + report
   H1b.
3. Gate — prereg (mục 5 đã điền) + report này. Commit này **là** chữ ký
   verdict.

Full suite vẫn **chưa chạy** (theo lệnh) — khuyến nghị chạy trước chuỗi
commit trên, vì H1b có sửa `candidates.py` (message từ chối) và đăng ký
policy mới, bán kính nhỏ nhưng khác không.

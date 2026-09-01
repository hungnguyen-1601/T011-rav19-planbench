# Rà soát plan AI Analyst (AI1–AI5) — đối chiếu với mã trên nhánh

**Ngày:** 2026-08-19 · **Nguồn:** `docs/antongduy/plans/2026-08-19/ai-analyst-subsystem.md` (bản 2)
**Người rà:** Hùng · **Mục đích:** kiểm tính khả thi trước khi An approve

---

## 1. Mọi con số plan trích dẫn đều khớp mã thật

| Plan nói | Kiểm được |
|---|---|
| `TOOL_CATALOG` 16 card | **16** ✅ |
| `VISIBLE_SUITE` 6 họ × 2 | **12 case** ✅ |
| 6 metric calibration | `precision=0.9 · recall@3=0.7 · abstention=0.9 · component_attribution=0.85 · checker_selection=0.9 · structural_violations=0` ✅ **đúng từng giá trị** |
| `score_case`/`score_suite`, `MockToolHost`, `reference_analyst`, `run_round` | có đủ ✅ |
| `packages/explanation` (E0–E6) | 36 module, đã vào nhánh qua merge `145b688` ✅ |

Một plan trích đúng sáu ngưỡng đến từng chữ số thập phân là plan viết từ
mã nguồn, không phải từ trí nhớ. **Kết luận: khả thi cao.**

## 2. Ba vấn đề tìm được

### 2.1 🔴 `Dockerfile.api` đang hỏng ngay lúc này — nặng hơn plan nói

Plan xếp đây là "Điểm 9, Docker là task chứ không phải ghi chú". Thực tế
gấp hơn:

```
apps/api import : planbench_decision, planbench_agent, planbench_benchmark, ...
Dockerfile.api  : KHÔNG có packages/decision
```

**Image API hiện không khởi động được** — `ModuleNotFoundError:
planbench_decision`. `DEPLOYMENT.md` ghi Docker chạy được ngày 03-08,
nhưng `packages/decision` ra đời sau đó và không ai chạy lại Docker.

Đề nghị: **tách khỏi A0, sửa ngay** — nó chặn cả deploy lẫn A7.

### 2.2 🟠 `planbench_agent/rag.py` không còn tồn tại

Phase A5 viết *"tokenizer `planbench_agent/rag.py` nếu cần scoring"*. File
đó đã bị xoá ở commit `64db00a` khi gỡ kho tài liệu của agent.

Không nghiêm trọng — A5 chỉ cần một tokenizer lexical. Nhưng nếu không
biết, người làm A5 sẽ import và gãy. Đây là hệ quả từ thay đổi nhánh này,
người viết plan không có cách nào biết.

### 2.3 🟡 `OFFICIAL_GOLDEN_READY` không ở chỗ plan chỉ

Plan nói cờ này trong `golden_fixtures`; không tìm thấy ở đó. Kiểm trước
khi A6 dựa vào.

## 3. Chồng lấn cần chốt ranh giới

Plan tránh va vào "AI paper-import của đồng nghiệp" — đúng. Nhưng còn một
chỗ va plan chưa thấy: `outcome.py` (`faf7443`) trả lời **đúng câu hỏi
ấy**.

| | `outcome.py` (đã ship) | Plan AI Analyst |
|---|---|---|
| Câu hỏi | Vì sao thắng/thua | Vì sao thắng/thua |
| Mức | Số liệu + bản chất thuật toán | Giả thuyết nhân quả có kiểm chứng |
| Cơ chế | 7 luật tất định + LLM xếp hạng | Agent + tool calling + ledger + gate |

Không trùng về chiều sâu — cái đầu **mô tả**, cái sau **suy luận nhân quả
có bằng chứng**. Nhưng người dùng sẽ thấy hai panel cùng nói "vì sao
thắng" trên cùng một trang. **Chốt trước A2**: đổi tên, gộp, hay xếp
tầng.

## 4. Ba điểm mạnh đáng học

**"LLM không bao giờ là nguồn của một con số"** → cấm chữ số trong
`hypothesis_statement` bằng regex. Nhánh này cũng theo nguyên tắc đó
nhưng nhẹ hơn: đếm trích dẫn bịa (`fabricated`). Plan **chặn ngay ở cú
pháp**, chặt hơn.

**Critic hạ xuống advisory + phải qua ablation mới bật.** Lý do nêu đúng:
cùng model thì lỗi tương quan, critic có thể âm thầm giết hypothesis
đúng. Chống được bản năng "thêm một lớp AI nữa cho chắc" là hiếm.

**`reference_analyst` model-free làm sàn** — *"LLM không thắng floor thì
không có lý do ship"*.

## 5. Ba rủi ro chưa có trong bảng rủi ro

**Chi phí và hạn mức model.** A6 bắt buộc live ≥2 lần trên 12 case, cộng
ablation, cộng mỗi round tới 2 vòng revise → hàng trăm lượt gọi. Nhánh
này vừa chạm trần Gemini free tier **20 lượt/ngày** (19-08). Xác nhận
ngân sách **trước** A6.

**Calibration đo trên packet do chính mình dựng.** Plan trung thực khai
A6.5 chưa xong, 4/6 họ `CANNOT_STAGE_YET`. Hệ quả cần nói to hơn: những
con số `precision ≥ 0,90` ban đầu là **đo trên đề tự ra**.

**Lịch.** 6–9 ngày kỹ thuật + A8 2–3 ngày. Preregistration của chính An
dùng hệ số lịch ×2 → **3–5 tuần lịch**.

## 6. Đề nghị trước khi approve

1. Sửa `Dockerfile.api` ngay, tách khỏi A0
2. Chốt ranh giới với `outcome.py` trước A2
3. Xác nhận ngân sách API trước khi cam kết A6

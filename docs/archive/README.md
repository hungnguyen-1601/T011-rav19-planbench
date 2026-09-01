# Lưu trữ

**Đừng trích số từ thư mục này.** Mọi thứ ở đây đã bị thay thế. Giữ lại vì
chúng giải thích *vì sao hệ ngày nay như vậy* — và vì một phần là hồ sơ nộp
bài, không được xoá.

Nội dung file giữ **nguyên văn**, không sửa. Chỉ thêm banner ở đầu file nói
nó bị thay bởi cái gì.

---

## `superseded/` — bị thay bởi tài liệu mới hơn

| File | Vì sao thay | Đọc thay bằng |
|---|---|---|
| `architecture.md` | Dừng ở "Giai đoạn 1A", viết **trước** lần chuyển hướng sang Planner Selector (2026-08-08) | [`../01-architecture.md`](../01-architecture.md), [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) |
| `IMPLEMENTATION_STATUS.md` | Dùng từ vựng milestone **M0–M13 đã chết**. Tuyên bố "đã xong" cho một sản phẩm không còn tồn tại | [`../02-features.md`](../02-features.md), [`../03-gaps.md`](../03-gaps.md) |
| `workflow.md` | Bản tổng hợp 2026-08-03, trước chuyển hướng | [`../02-features.md`](../02-features.md) |

## `gate-g1/` — hồ sơ nộp bài Gate G1 (2026-08-02)

Bốn deliverable chốt đề tài: brief, PRD, wireframe, AI log setup.

**Vẫn còn giá trị:** đây là chỗ duy nhất có **persona và tệp người dùng
viết tường minh** — PRD §7–8. Nội dung đó đã được trích và cập nhật vào
[`../00-product.md`](../00-product.md) §3.

**Đã lỗi thời:** phạm vi MVP, feature status (§31), kiến trúc (§26), và
roadmap (§32) — tất cả viết trước lần chuyển hướng 2026-08-08. Sản phẩm mô
tả trong PRD là "nền tảng benchmark công bằng"; sản phẩm hôm nay là
"Planner Selector".

## `course-guide/` — sách khoá học cohort

46 file: chapter 01–10, LangGraph, BMAD, RAG pattern, hướng dẫn mở tài
khoản miễn phí (Cohere, Groq, Gemini…), anti-pattern của cohort 1.

**Đây là tài liệu của chương trình đào tạo, không phải của sản phẩm.**
Repo này **không dùng** LangGraph và **không dùng** ChromaDB, dù sách nói
nhiều về cả hai. Đừng đọc nó để hiểu PlanBench.

Giữ lại vì nó giải thích một số quy ước (AI log, cấu trúc deliverable,
Gate) mà repo vẫn đang tuân theo.

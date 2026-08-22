# Gỡ kho tài liệu của agent — vì corpus là nhật ký của chính team

**Ngày:** 2026-08-18 · **Commit:** `64db00a`
**Quy mô:** 18 file, +99 −542

---

## 1. Vì sao gỡ

Tầng agent có một corpus TF-IDF trên `docs/` và `contracts/`: **136 tài
liệu, 3.023 chunk**. Đo phân bố thì hơn một nửa là tài liệu thiết kế nội
bộ:

| Nguồn | Chunk |
|---|---|
| `docs/antongduy/` | 1.529 |
| `docs/guide/` | 873 |
| `docs/` gốc | 288 |
| `docs/docs/` | 269 |
| `contracts/CONTRACTS.md` | 64 |

Vấn đề không phải kích thước. Một tài liệu lệch khỏi code **không làm
agent dốt đi — nó làm agent sai một cách tự tin**, và câu trả lời sai đó
kèm citation id trông y như đã được kiểm chứng.

Không phải giả định: một tài liệu kiến trúc trong `docs/` ghi bảy stack
và một `dwa_predictive` mà lúc đó registry không có.

## 2. Gỡ những gì

Xoá hẳn `services/agent_service/planbench_agent/rag.py` (232 dòng) và
`tests/test_agent_rag.py` (20 test). Gỡ khỏi 14 file khác: công cụ
`search_knowledge`, `agent_knowledge_dirs`, trường `knowledge_documents`
trên `/agent/capabilities`, biến `PLANBENCH_AGENT_KNOWLEDGE_DIRS`.

Còn đúng ba chỗ nhắc tên cũ — cả ba đều là **test khẳng định nó không
tồn tại**.

## 3. Hai hồi quy tự gây ra và tự bắt

Gỡ corpus xong, hai câu gợi ý trên trang `/agent` **không còn trả lời
được** vì chúng đọc từ bản `CONTRACTS.md` đã index:

- *"Cổng G2 kiểm gì, và vì sao nó cần số episode tối thiểu?"*
- *"Dự án này giữ công bằng giữa các ứng viên bằng cách nào?"*

Bấm vào là agent trả lời rỗng. Thay bằng hai câu công cụ trả lời được
(`list_candidates`, `get_critique`).

Và dòng chữ giữa trang vẫn ghi *"Mọi câu trả lời đến từ kết quả tool
**hoặc tài liệu đã index**"* — nói dối mọi người đọc sau khi corpus biến
mất. Đã sửa cả hai ngôn ngữ.

## 4. Hợp đồng thay thế

Agent còn 9 công cụ, **mọi tên bắt đầu bằng `list_` hoặc `get_`** — có
test giữ điều đó thành ràng buộc: một động từ không phải tra cứu là một
công cụ *làm* gì đó.

Kiến thức ngoài vào hệ thống qua đúng một cửa: **paper người dùng cung
cấp**, mỗi tham số kèm câu nguồn kiểm được.

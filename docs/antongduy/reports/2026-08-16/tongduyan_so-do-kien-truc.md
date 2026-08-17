# Sơ đồ kiến trúc — file mới, và ba file cũ không đè

**Ngày:** 2026-08-16 · **Nhánh:** `tongduyan_plannerselector`
**Yêu cầu:** vẽ sơ đồ kiến trúc thể hiện các thành phần tương tác với nhau.
**Chưa commit.**

---

## 1. Đã tạo

`docs/architecture_planner_selector.md` — Mermaid, sáu sơ đồ, mỗi cái trả
lời một câu hỏi khác nhau chứ không phải sáu cách vẽ lại cùng một thứ:

| # | Sơ đồ | Trả lời |
|---|---|---|
| 1 | Bối cảnh (Level 1) | Ai dùng; bốn phụ thuộc ngoài (LLM, MLflow, OAuth, ROS2) **đều tùy chọn** — vẽ nét đứt để nói điều đó |
| 2 | Thành phần (Level 2) | 6 khối lõi + API + web + lưu trữ; mũi tên không bao giờ đi ngược từ lõi lên FastAPI |
| 3 | Chuỗi giá trị | TaskProfile → context → trace → metric → **gates** → Pareto → utility → ΔU → Card → Approval |
| 4 | Vòng lặp episode | Bốn interface HĐ-4, ranh giới `Observation` |
| 5 | Request thật | Browser → router → JobQueue → pipeline → artifacts → DB, kèm WS phát lại |
| 6 | Hai chế độ chạy | dev/SQLite · docker-compose 4 service · headless scripts |

Cộng ba bảng: vì sao thứ tự gate→score→ΔU không đảo được, ba khoá cứng của
contract, và bảng tra thành phần theo đường dẫn.

Bản rendered: https://claude.ai/code/artifact/e41c44fd-e41d-4cdd-a3a0-72b36e26d408

## 2. Ba quyết định khi vẽ

**(a) Sơ đồ 3 là trung tâm, không phải sơ đồ 2.** Sơ đồ hộp-và-mũi-tên
thông thường vẽ *cái gì gọi cái gì*. Nhưng thứ dễ làm sai nhất ở dự án này
là **thứ tự**: gate trước score, Pareto trước utility, objective per-episode
trước bootstrap. Nên chuỗi giá trị được vẽ thành flowchart riêng, kèm bảng
"đảo thì hỏng gì".

**(b) Vẽ trace Parquet thành nút thắt cổ chai có chủ ý.** HĐ-5 nói file là
đầu vào **duy nhất** của Metrics Engine. Một sơ đồ vẽ mũi tên từ simulator
thẳng sang metrics sẽ hợp lý về mặt hình ảnh và sai về mặt hợp đồng — caller
đọc số từ `StackRun` là đã lặng lẽ tạo nguồn thứ hai.

**(c) Ghi cả cái sơ đồ KHÔNG vẽ** (mục 9): L2/L3 scope, racing, Target
Verifier, registry policy monolithic, ROS2 closed-loop. Một sơ đồ kiến trúc
không nói rõ ranh giới sẽ được đọc như tuyên bố mọi thứ trong đó đã chạy.

## 3. Ba file kiến trúc cũ — **không đè, chờ An chốt**

| File | Trạng thái | Vấn đề |
|---|---|---|
| `ARCHITECTURE.md` | template T-011 chưa điền | Vẽ LangGraph Agent + Vector Store ChromaDB. Repo **không dùng cái nào**. Toàn placeholder `[mô tả]` |
| `docs/architecture_diagram.md` | template T-011 chưa điền | Cùng vấn đề: ChromaDB, GPT-4o, agent flow không tồn tại |
| `docs/architecture.md` | thật, nhưng cũ | Đúng ở thời điểm Giai đoạn 1A; viết trước cú chuyển hướng Planner Selector 08-08 nên không có Decision Card, gates, anchors, paired ΔU |

Cả ba đều **đang được git theo dõi**. Tôi không đè vì hai file đầu tuy sai
nhưng là tài sản chung, và xoá/ghi đè file team là quyết định của An chứ
không phải của tôi. Ba lựa chọn:

1. Thay nội dung hai file scaffold bằng bản mới (hoặc bằng một dòng trỏ sang file mới).
2. Xoá hẳn hai file scaffold, giữ `docs/architecture.md` làm hồ sơ lịch sử.
3. Giữ nguyên cả ba — nhưng khi đó repo có bốn file kiến trúc, hai trong đó nói sai về chính nó.

Đề xuất của tôi: **(1)** — hai file scaffold đổi thành trỏ sang, và
`docs/architecture.md` thêm một dòng đầu ghi rõ nó chép lại Giai đoạn 1A.

## 4. Bằng chứng

| Kiểm | Kết quả |
|---|---|
| Cấu trúc đọc từ | `contracts/CONTRACTS.md` HĐ-1…HĐ-15, `pipeline.py`, `episode.py`, `registry.py`, `main.py`, `docker-compose.yml` |
| `pytest tests` toàn bộ backend, trên `.venv` | **2815 passed, 8 skipped, 0 failed** — 42 phút 17 giây |
| Đổi code | **Không.** Chỉ thêm file `.md` |

Rà soát dependency đi kèm phiên này nằm ở
`notes/2026-08-16/tongduyan_ra-soat-requirements-tren-venv.md`.

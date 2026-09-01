# Plan — đưa tầng AI tới người dùng thật

**Ngày:** 2026-08-20 · **Trạng thái:** draft, chưa triển khai
**Tiền đề:** tầng AI xong lõi–API–UI–test (`acad56f`); 3.392 test Python +
980 test web, không lỗi.

---

## 1. Ràng buộc quyết định toàn bộ hình dạng plan

Nền tảng **đo độ trễ bằng đồng hồ tường**, và cổng G4 phán quyết dựa trên
con số đó. CI workflow của chính dự án ghi phép đo:

> cùng một stack: **59,30 ms không ghim CPU** so với **16,10 ms ghim 2
> lõi** — chênh xa hơn khoảng cách giữa các phương án với nhau

Hàng đợi phép so giữ **đúng một job** vì HĐ-7.4 cấm hai lần chạy đánh giá
trên cùng máy.

Trên CPU chia sẻ (Cloud Run, App Engine) **không ghim được lõi** → mọi số
G4 vô nghĩa. Không phải sai lệch chút ít, mà là **đo một cái máy không
tồn tại**.

**Hệ quả: tách làm hai.**

## 2. Phần A — lên cloud được: xem kết quả + toàn bộ AI

Mọi tính năng AI đều **chỉ đọc**: hỏi đáp, phân tích thắng-thua, đọc
paper, dựng plugin, preflight, giải thích cổng trượt, đọc trace, phản
biện, rào chắn báo cáo. Không thứ nào cần ghim CPU.

### D1 — Sửa `Dockerfile.api` *(ưu tiên cao nhất, ~5 phút)*

PYTHONPATH thiếu `packages/decision` mà `apps/api` đang import → **image
không khởi động được**. Cũng thiếu `packages/explanation`,
`packages/plugin_sdk`, `ml`. Trùng với Điểm 9 của plan AI Analyst.

**Không làm việc này thì mọi bước sau vô nghĩa.**

### D2 — Chạy `docker compose up` sạch từ máy trắng *(~1 giờ)*

Xoá hết volume, chạy lại. Lần chạy Docker đầu tiên của dự án đã lòi ra
một lỗi khởi động không test nào bắt được (`PLANBENCH_MODEL_DIR` tương
đối giải ra thư mục của root). Loại đó chỉ hiện khi chạy thật.

### D3 — Cấu hình bắt buộc

| Việc | Vì sao |
|---|---|
| `AUTH_SECRET` cố định vào Secret Manager | Secret rỗng = sinh ngẫu nhiên **mỗi tiến trình**. Nhiều instance → user bị đăng xuất ngẫu nhiên, **không lỗi nào hiện ra** |
| `DATABASE_URL` → Cloud SQL PostgreSQL | SQLite là file cục bộ; nhiều instance thành nhiều CSDL |
| `PLANBENCH_CORS_ORIGINS` → tên miền thật | Mặc định `localhost:3000`. Khai qua shell phải bọc nháy đơn |
| Callback OAuth vào Google Console | Thiếu thì nút đăng nhập lỗi ngay |
| Khoá model vào Secret Manager | Không nhét vào image |

### D4 — Ba đường dẫn tương đối → tuyệt đối

`artifact_dir="artifacts"`, `model_dir=""`, `map_root="."`. Đây **chính
xác** là lỗi đã cắn lần chạy Docker đầu.

### D5 — Quyết định lưu trữ

Cloud Run **không có ổ đĩa bền**. Hai lựa chọn:

- **Chỉ-đọc** *(khuyến nghị cho mục tiêu hiện tại)*: bơm sẵn `artifacts/`
  vào image, tắt đường chạy phép so → ~1–2 ngày
- **Cloud Storage** đầy đủ → ~3–4 ngày

### D6 — Vận hành

- Timeout ≥ 300s. Đo được: Gemini **139–190 giây** một lượt gọi
- **Chặn hoặc dán nhãn** đường chạy benchmark trên bản deploy

## 3. Phần B — giữ ở máy riêng: chạy phép so

Máy có lõi dành riêng, hoặc VM riêng (Compute Engine), **không serverless**.

## 4. Trải nghiệm — ba việc chặn demo

### X1 — Chờ 2–3 phút cho một lần bấm

Đo trực tiếp: `/outcome?use_model=true` mất **139 s** và **190 s**. Người
dùng ngồi nhìn spinner 3 phút; trong buổi bảo vệ đó là 3 phút im lặng.

Hướng: hiện kết quả luật **ngay lập tức** rồi model bổ sung sau; hoặc đổi
model nhanh hơn. Tầng luật vốn đã chạy tất định trong mili-giây — kiến
trúc đã sẵn sàng cho việc này.

### X2 — Hạn mức model

Gemini free tier **20 lượt/ngày** — chạm trần ngay trong một buổi test
(19-08). Không đủ cho một buổi demo. Bật thanh toán, hoặc đổi provider
(hệ thống hỗ trợ sẵn 7, đều qua `json_schema`).

### X3 — Dữ liệu demo trống

`1 deployment · 3 phương án · 1 phép so`, và **phép so đó không ai qua đủ
cổng** → không có Decision Card, mất đúng thứ đẹp nhất để trình bày.

Cần chạy một phép so thật ra card hoàn chỉnh. Tốn thời gian máy, không
tốn công viết.

## 5. Thứ tự

```
D1 → D2 → (X3 song song) → D3 → D4 → D5 → D6 → X1
```

D1 làm ngay hôm nay. X2 là quyết định của bạn, không phải việc code.

## 6. Rủi ro

| Rủi ro | Giảm nhẹ |
|---|---|
| Chưa từng deploy lên máy chủ thật lần nào | D2 trước; **không deploy lần đầu vào đêm trước bảo vệ** |
| Số G4 trên cloud vô nghĩa | Tách phần B; dán nhãn trên bản deploy |
| Nhiều người dùng đồng thời trên PostgreSQL chưa kiểm | `DEPLOYMENT.md` tự khai là ẩn số; đo trước khi mở rộng |
| Golden 1-ulp đỏ trên CI | Cần An quyết tolerance — ubuntu-latest là libm thứ ba |

## 7. Câu hỏi cần trả lời trước khi bắt đầu

**Cần người khác *dùng*, hay chỉ cần họ *xem*?**

Nếu chỉ xem: video demo + repo chạy được bằng `docker compose up` thuyết
phục hơn một bản deploy nửa vời — và không phải giải thích vì sao số liệu
trên đó không dùng để kết luận được.

# AI TODO — Outstanding Backend, Database, & Platform Tasks (Phạm Thái Sơn)

Tệp này quy định các nhiệm vụ cần hoàn thiện cho vai trò Backend, Database & Platform Engineer. Mỗi khi khởi đầu một task mới, AI hãy đọc kỹ mục tiêu, sửa đổi mã nguồn tương ứng và đánh dấu [x] khi hoàn thành.

---

## 1. Docker & PostgreSQL Integration

- [x] **Cấu hình & Tối ưu Docker Compose**
  - **Đường dẫn**: [docker-compose.yml](file:///c:/Users/Acer/OneDrive%20-%20Hanoi%20University%20of%20Science%20and%20Technology/Documents/GitHub/T011-rav19-planbench/docker-compose.yml)
  - **Mô tả**: Sửa lỗi giao tiếp giữa các container, cấu hình đúng biến môi trường, đảm bảo các service (`db`, `migrate`, `api`, `web`) khởi động ổn định bằng lệnh `docker compose up --build`.

- [x] **Cơ chế Retry Kết nối Database khi Startup**
  - **Đường dẫn**: [apps/api/planbench_api/db/session.py](file:///c:/Users/Acer/OneDrive%20-%20Hanoi%20University%20of%20Science%20and%20Technology/Documents/GitHub/T011-rav19-planbench/apps/api/planbench_api/db/session.py)
  - **Mô tả**: Viết logic thử lại kết nối (exponential backoff) tới database PostgreSQL lúc API khởi tạo, ngăn tiến trình API crash sớm khi DB container chưa sẵn sàng nhận kết nối.

---

## 2. Secure Model Upload & Sandboxed Execution

- [x] **Xây dựng module Sandbox cô lập**
  - **Đường dẫn**: [apps/api/planbench_api/sandbox.py](file:///c:/Users/Acer/OneDrive%20-%20Hanoi%20University%20of%20Science%20and%20Technology/Documents/GitHub/T011-rav19-planbench/apps/api/planbench_api/sandbox.py) [NEW]
  - **Mô tả**: Thiết lập cơ chế tạo container Docker siêu nhẹ cô lập qua Docker SDK, giới hạn CPU/RAM quota, tắt mạng để nạp và kiểm tra cấu trúc model PPO an toàn.

- [x] **Tích hợp Sandbox vào Worker để chạy Benchmark**
  - **Đường dẫn**: [apps/api/planbench_api/worker.py](file:///c:/Users/Acer/OneDrive%20-%20Hanoi%20University%20of%20Science%20and%20Technology/Documents/GitHub/T011-rav19-planbench/apps/api/planbench_api/worker.py)
  - **Mô tả**: Thay đổi phương thức đánh giá mô hình của benchmark worker, thay vì chạy trực tiếp `torch.load` trên host thì đẩy sang thực thi bên trong Docker sandbox đã thiết lập.

---

## 3. Production Task Queue (Hàng đợi & Broker)

- [x] **Tích hợp Persistent Job & Worker Architecture**
  - **Đường dẫn**: [apps/api/planbench_api/worker.py](file:///c:/Users/Acer/OneDrive%20-%20Hanoi%20University%20of%20Science%20and%20Technology/Documents/GitHub/T011-rav19-planbench/apps/api/planbench_api/worker.py)
  - **Mô tả**: Thiết lập kiến trúc quản lý job với trạng thái bền vững và thread pool cô lập.

- [x] **Lưu trữ trạng thái Job vào Database**
  - **Đường dẫn**: [apps/api/planbench_api/db/models.py](file:///c:/Users/Acer/OneDrive%20-%20Hanoi%20University%20of%20Science%20and%20Technology/Documents/GitHub/T011-rav19-planbench/apps/api/planbench_api/db/models.py) và các router liên quan
  - **Mô tả**: Lưu trữ metadata, trạng thái tiến trình (`BenchmarkJobRow`) của job chạy benchmark vào PostgreSQL/SQL Database để theo dõi tiến độ thời gian thực, tạm dừng, hoặc tiếp tục tác vụ.

---

## 4. Advanced Security, Auth & Cloud Storage

- [x] **Token Refresh & Logout phía Server**
  - **Đường dẫn**: [apps/api/planbench_api/routers/auth.py](file:///c:/Users/Acer/OneDrive%20-%20Hanoi%20University%20of%20Science%20and%20Technology/Documents/GitHub/T011-rav19-planbench/apps/api/planbench_api/routers/auth.py) và [apps/api/planbench_api/auth.py](file:///c:/Users/Acer/OneDrive%20-%20Hanoi%20University%20of%20Science%20and%20Technology/Documents/GitHub/T011-rav19-planbench/apps/api/planbench_api/auth.py)
  - **Mô tả**: Thêm các endpoint `/auth/refresh` và `/auth/logout`, xây dựng bảng lưu trữ/blacklist Refresh Token (`RefreshTokenRow`) dưới Database hỗ trợ thu hồi quyền truy cập và token rotation.

- [x] **Middleware Rate Limiting**
  - **Đường dẫn**: [apps/api/planbench_api/middleware/rate_limit.py](file:///c:/Users/Acer/OneDrive%20-%20Hanoi%20University%20of%20Science%20and%20Technology/Documents/GitHub/T011-rav19-planbench/apps/api/planbench_api/middleware/rate_limit.py) [NEW]
  - **Mô tả**: Viết middleware cho FastAPI để cấu hình giới hạn số lượng request đối với các endpoint nhạy cảm (như Route Login, OAuth callbacks và API Upload file).

- [x] **Storage Backend S3/R2**
  - **Đường dẫn**: [apps/api/planbench_api/model_storage.py](file:///c:/Users/Acer/OneDrive%20-%20Hanoi%20University%20of%20Science%20and%20Technology/Documents/GitHub/T011-rav19-planbench/apps/api/planbench_api/model_storage.py)
  - **Mô tả**: Triển khai class `S3ModelStorage` kế thừa từ interface lưu trữ hiện có, sử dụng thư viện `boto3` để upload model và trajectory lên các hệ thống Object Storage (như AWS S3, Cloudflare R2 hoặc MinIO local).


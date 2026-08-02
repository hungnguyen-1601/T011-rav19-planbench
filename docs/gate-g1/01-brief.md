# RAV19 – PlanBench: 1-page Brief

> Deliverable 1/4 – [Gate G1](./README.md)

## 1. Bối cảnh

Robot tự hành trong nhà kho và nhà máy (AMR/AGV) phải liên tục quyết
định đi đường nào và đi ra sao. Có nhiều họ thuật toán làm việc đó: A*
cho lập đường toàn cục, DWA và Pure Pursuit cho điều khiển cục bộ, PPO
và các phương pháp Reinforcement Learning khác cho chính sách học được.
Chọn thuật toán nào là câu hỏi phải trả lời bằng đo đạc, và muốn đo đạc
thì cần một môi trường mà mọi thuật toán gặp đúng cùng một bài toán.

## 2. Vấn đề

Việc đo đạc hiện gặp các khó khăn sau:

- **Không có môi trường benchmark thống nhất.** Mỗi người tự dựng bản
  đồ, tự chọn điểm xuất phát, tự đặt timeout.
- **So sánh không công bằng.** Hai thuật toán chạy trên hai bản đồ khác
  nhau, hoặc cùng bản đồ nhưng khác seed, cho ra hai con số không nói
  lên điều gì khi đặt cạnh nhau.
- **Khó tái hiện lỗi.** Robot kẹt ở một góc tường nhưng chạy lại thì
  không kẹt, vì trạng thái ngẫu nhiên không được ghi lại.
- **Thiếu công cụ quan sát.** Biết tỉ lệ thành công 60% mà không xem
  được 40% còn lại hỏng ở đâu thì không sửa được.
- **Kết quả kỹ thuật khó hiểu với người mới.** `min_clearance = 0.04 m`
  không tự nói lên điều gì với người chưa từng làm robotics.
- **Model PPO khó tích hợp.** Muốn thử một checkpoint đã huấn luyện,
  người dùng phải sửa đường dẫn file trong code, và không có gì bảo đảm
  kết quả gắn với đúng file nào.

## 3. Người dùng mục tiêu

- Sinh viên robotics làm đồ án, luận văn.
- Nhóm nghiên cứu cần số liệu so sánh có thể tái lập.
- Kỹ sư AMR/AGV chọn thuật toán cho một môi trường triển khai cụ thể.
- Người phát triển thuật toán planning cần baseline để đối chiếu.
- Người đánh giá model Reinforcement Learning đã huấn luyện.

## 4. Giải pháp

PlanBench là một nền tảng web **chỉ mô phỏng**, gồm:

- **Map và Scenario** — vẽ bản đồ hoặc import từ thư viện 10 scenario
  dựng sẵn (hành lang hẹp, cửa ra vào, ngã tư, nhà kho có vật cản
  động…).
- **Live Simulation** — chạy một lượt, xem đường đi toàn cục và quỹ đạo
  thực tế, phát lại từng bước.
- **Benchmark** — chạy có hệ thống trên nhiều seed và nhiều stack trong
  điều kiện bị khóa; kết quả được tổng hợp và ghi kèm checksum điều kiện
  để biết hai benchmark có so sánh được với nhau không.
- **Metrics và failure analysis** — số liệu do simulator tính, kèm chẩn
  đoán vì sao một episode thất bại.
- **PPO Model Registry** — tải model đã huấn luyện lên qua web thay vì
  sửa đường dẫn trong code.
- **AI chatbot** — trợ lý hội thoại giúp chuẩn bị và đọc hiểu benchmark.
- **Report có evidence** — mọi khẳng định phải trỏ về một bản ghi có
  thật.

## 5. Vai trò của AI

Ranh giới: **AI chuẩn bị và giải thích, backend thực thi, con người
quyết định.**

Người dùng mô tả nhu cầu bằng lời → AI hỏi lại cho rõ → AI trình bày cấu
hình đề xuất dưới dạng một **thẻ có nút bấm** → người dùng xác nhận → AI
chuyển thành `BenchmarkSpec` có cấu trúc → backend kiểm tra dữ liệu và
tạo **bản nháp** → **người dùng tự bấm Run** → simulator chạy → backend
lưu kết quả thật → AI đọc kết quả đã lưu và giải thích.

AI **không** điều khiển robot, không tạo hay sửa metric, không sửa quỹ
đạo, không tự tuyên bố an toàn, không tự duyệt benchmark, không tự chấp
nhận hay từ chối kết quả, không chạy benchmark khi người dùng chưa xác
nhận, và không trả lời bằng dữ liệu không tồn tại.

## 6. Điểm khác biệt

- **Cùng điều kiện, cùng seed** — điều kiện được khóa và băm thành
  checksum, nên tính công bằng kiểm chứng được.
- **Tái lập được** — cùng đầu vào cho cùng đầu ra; seed là tham số tường
  minh, không có trạng thái ngẫu nhiên toàn cục.
- **Classic planning và RL trong cùng một khung** — A*+DWA và A*+PPO là
  hai stack được so sánh với nhau.
- **Chatbot hạ rào cản kỹ thuật** — người chưa quen thuật ngữ vẫn dựng
  được một benchmark đúng.
- **Human-in-the-loop** — người dùng bấm chạy, người dùng chấp nhận kết
  quả.
- **Evidence-based** — báo cáo có citation được kiểm tra; citation trỏ
  vào chỗ không tồn tại thì báo cáo bị loại.
- **Không điều khiển robot thật.**

## 7. Phạm vi MVP

Thuộc MVP (đã có mã nguồn và test trong repository):

- Map và Scenario, thư viện 10 scenario, vật cản tĩnh và động.
- Stack **A\* + DWA**; **A\* + Pure Pursuit** làm tham chiếu, không dự
  benchmark.
- Live Simulation với phát lại quỹ đạo.
- Benchmark nhiều seed, metrics, failure analysis, leaderboard.
- Đăng nhập Google/GitHub, nickname, review tùy chọn.
- AI đề xuất cấu hình và giải thích kết quả.
- **PPO Model Registry** — tải model qua web, kiểm tra tương thích,
  chọn model theo ID trong benchmark. Đã có mã nguồn và 50 test.

Chưa thuộc MVP: huấn luyện PPO ngay trên web, tích hợp ROS2/Nav2 vào
giao diện (mã nguồn có, mới chạy tay), triển khai production.

## 8. Metrics

Simulator tính, backend lưu: **success rate**, **collision rate**,
**timeout rate**, **travel time**, **path length**, **path efficiency**
(tỉ số giữa đường đi thực tế và đường tối ưu), **smoothness**,
**minimum clearance** (khoảng cách gần nhất tới vật cản), và
**inference latency** của local planner.

## 9. Ràng buộc

- Chỉ mô phỏng; không kết nối và không điều khiển robot thật.
- Người dùng phải xác nhận trước mọi hành động quan trọng.
- AI không tạo, không sửa, không xóa kết quả đã ghi.
- Hệ thống không cấp chứng nhận an toàn.
- Người dùng chịu trách nhiệm về kết luận cuối cùng.

## 10. Kết quả đầu ra

Một web application chạy được, gồm simulator, các bản ghi benchmark kèm
quỹ đạo và metrics, công cụ phân tích lỗi, báo cáo có evidence, và một
demo end-to-end từ lúc đăng nhập tới lúc đọc kết quả.

## 11. Công nghệ chính

Xác nhận từ repository: **Next.js 15 + React 19 + TypeScript** (giao
diện, Canvas 2D/2.5D), **FastAPI + Python 3.12 + Pydantic v2** (API),
**WebSocket** (stream mô phỏng trực tiếp), **SQLAlchemy 2.0 + Alembic**
với **SQLite** (local) và **PostgreSQL** (triển khai), **A\***, **DWA**,
**Pure Pursuit**, **PPO** qua **Gymnasium + Stable-Baselines3**,
**MLflow** (theo dõi huấn luyện), và một lớp trừu tượng LLM provider
trong đó **Gemini** cùng vài provider khác được cấu hình ở phía server.

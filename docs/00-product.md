# PlanBench là gì, và phục vụ ai

> Đọc đầu tiên. Sau file này bạn trả lời được: sản phẩm bán lời hứa gì,
> ai là người trả tiền cho lời hứa đó, và điều gì sản phẩm cố ý từ chối làm.

---

## 1. Một câu

PlanBench trả lời câu hỏi **"nên triển khai thuật toán điều hướng nào cho
kho hàng này"** bằng bằng chứng người khác kiểm lại được — chứ không phải
bằng một con số trong paper hay một lần demo may mắn.

**Chỉ mô phỏng. Không điều khiển robot thật.**

Sản phẩm có hai hình dạng từ cùng một cây mã: một **web app**
(FastAPI + Next.js) và một **desktop app Windows** đóng gói
(hiện `0.1.16`, tải qua installer, tự cập nhật).

---

## 2. Vấn đề nó tồn tại để giải

Chọn thuật toán điều hướng cho một kho cụ thể là quyết định tốn kém và
khó rút lại. Cơ sở để chọn hôm nay đến từ những thứ **không so được với
nhau**.

**Đo trên robot thật thì đắt, chậm, và không lặp lại được.** Mỗi lượt
chạy tốn hàng chục phút; một phép so tử tế cần hàng chục lượt. Cần robot
rảnh, kho trống, người trực. Một lần va chạm là hỏng cảm biến hoặc hỏng
hàng. Và tình huống vừa hỏng thì **không dựng lại được** — sàn hôm nay
khác hôm qua.

**Ngay cả khi đã đo, phép so vẫn hỏng theo ba cách:**

| Cách hỏng | Biểu hiện |
|---|---|
| Không cùng điều kiện | Hai thuật toán chạy trên hai bộ seed / hai cấu hình LiDAR khác nhau, rồi hiệu số được đọc như thể nó đo thuật toán |
| Không đủ số lần | "Không va chạm lần nào" trên 5 lượt không phải lời hứa an toàn — nó là một quan sát trên 5 lượt |
| Kết luận nghe mạnh hơn dữ liệu | "A tốt hơn B" nói ra dễ hơn nhiều so với "A hơn B 0,039 utility, CI 95% [0,036; 0,042], trên 30 episode ghép cặp" |

**PlanBench tồn tại để câu thứ ba là câu duy nhất hệ thống cho phép nói.**
Đây không phải khẩu hiệu: có hàm kiểm ngôn ngữ cấm và test CI canh nó
(xem [01-architecture.md](01-architecture.md) §4).

---

## 3. Tệp người dùng

### 3.1. Năm nhóm

| Nhóm | Nhu cầu chính | Mức kỹ thuật |
|---|---|---|
| **Kỹ sư AMR/AGV** | Chọn stack cho một môi trường triển khai cụ thể, và có bằng chứng bảo vệ được trước nhóm kỹ thuật | Cao |
| **Người phát triển thuật toán planning** | Baseline để đối chiếu thuật toán mới của mình, chạy trên **đúng** thế giới mà đối thủ đã chạy | Rất cao |
| **Nhóm nghiên cứu** | Kết quả tái lập được, xuất báo cáo có dẫn chứng | Cao |
| **Sinh viên robotics** | Số liệu so sánh cho đồ án, và hiểu **vì sao** một thuật toán thất bại | Trung bình |
| **Người đánh giá model RL** | Đánh giá checkpoint PPO mà không phải đọc code nền tảng | TB–cao về ML, thấp về nền tảng |

**Nhóm đầu là người dùng trung tâm.** Bốn nhóm còn lại dùng được cùng một
bộ công cụ, nhưng mọi đánh đổi thiết kế — cổng khả thi trước điểm số,
ngôn ngữ cấm, quy trình ký duyệt hai người — được chọn cho tình huống
*một người phải bảo vệ một quyết định triển khai trước người khác*.

### 3.2. Ba persona

**Hà — kỹ sư điều hướng AMR** *(persona trung tâm)*
Chọn cấu hình local planner cho một nhà kho hành lang hẹp, có người đi
lại. Khó khăn: cần bằng chứng đủ chắc để bảo vệ trước nhóm kỹ thuật;
"chạy thử thấy ổn" không đủ. Cần: nhiều seed, biết chắc điều kiện giống
hệt nhau, xem được từng lượt thất bại, xuất báo cáo có dẫn chứng.

**Minh — sinh viên năm cuối robotics**
So sánh A\*+DWA với một chính sách PPO trong đồ án, và giải thích được vì
sao cái này thắng. Khó khăn: chưa từng dựng môi trường benchmark; mỗi lần
chạy lại ra số khác nhau. Cần: scenario dựng sẵn, chạy được ngay, xem lại
quỹ đạo, và lời giải thích bằng tiếng người.

**Tuấn — người đánh giá model PPO**
Đánh giá checkpoint do nhóm ML huấn luyện, không phải người viết ra chúng.
Khó khăn: không biết checkpoint được huấn luyện với bố cục quan sát nào.
Cần: tải `.zip` lên qua web, được cảnh báo khi model không khớp robot
profile, và biết chắc kết quả gắn với đúng file nào.

> **Lưu ý về nguồn.** Ba persona trên trích từ PRD Gate G1
> ([archive/gate-g1/02-prd.md](archive/gate-g1/02-prd.md) §8, 2026-08-02),
> viết **trước** khi đề tài chuyển hướng sang Planner Selector
> (2026-08-08). Nhu cầu của họ giữ nguyên qua lần chuyển hướng đó; cái đổi
> là **đầu ra** hệ thống trả về — từ "một bảng benchmark" thành "một
> khuyến nghị kèm biên sai số của chính khuyến nghị đó".

### 3.3. Ba gói quyền — ai được làm gì

Người dùng thật được chia quyền thành **ba gói độc lập**, **không lồng
nhau**: `engineer`, `reviewer`, `admin`. Reviewer không phải engineer cấp
cao; admin không phải reviewer cấp cao.

| Việc | engineer | reviewer | admin |
|---|:---:|:---:|:---:|
| Đọc map, scenario, deployment, kết quả | ✅ | ✅ | ✅ |
| Tạo/sửa map, scenario, deployment | ✅ | | |
| Chạy mô phỏng, chạy so sánh | ✅ | ✅ | |
| Gửi một run đi duyệt | ✅ | | |
| Nhận, đọc và **ký duyệt** một run | | ✅ | |
| Import thuật toán, **xuất bản** | | ✅ | |
| Kill switch lúc sự cố | | | ✅ |
| Cấp/thu quyền, khoá tài khoản | | | ✅ |

**Vì sao không xếp bậc thang:** publish một thuật toán là **chữ ký của
reviewer**, không phải đặc quyền quản trị. Cho admin quyền đó vì "admin
làm gì cũng được" là biến một chữ ký thành một cấp bậc.

Chi tiết đầy đủ (bốn bước duyệt, tách trách nhiệm `strict`/`relaxed`, ba
deployment profile): [`../README.md` §4.11](../README.md) và
[reference/DEMO-PROFILE.md](reference/DEMO-PROFILE.md).

---

## 4. Cố ý **không** làm gì

Đây không phải danh sách việc chưa làm — đó là [03-gaps.md](03-gaps.md).
Đây là những thứ sản phẩm **từ chối** làm, và mỗi cái có lý do.

| Không làm | Vì sao |
|---|---|
| **Điều khiển robot thật** | Ngoài phạm vi đề tài; sim-only là ràng buộc gốc |
| **Dùng Gazebo** | Ràng buộc đề bài; simulator tự viết để tất định hoàn toàn |
| **Tự duyệt, tự áp dụng, tự đưa lên production** | Chấp nhận một kết quả là hành động của **con người**. Không uỷ quyền được |
| **LLM sinh ra một con số** | LLM đọc số đã có và chất vấn kết luận. Nó không bao giờ là nguồn của một con số, một dấu xác nhận, hay một kết luận nhân quả |
| **Nói "an toàn", "sẵn sàng production", "TCO"** cạnh một con số hệ sinh ra | Nền tảng đo utility dưới một phân phối kịch bản mô phỏng. Nó không có tư cách nói mấy chữ đó. Có hàm kiểm và test canh |
| **Ra Decision Card khi dưới 2 candidate qua cổng** | Không có ngoại lệ. Một "so sánh" một phía không phải một so sánh |
| **Hằng số ngưỡng viết cứng trong code** | Một ngưỡng viết cứng là ngưỡng **không ai đặt ra**. Mọi ngưỡng đọc từ deployment |

---

## 5. Ràng buộc dự án

Đây là đồ án nhóm 3–4 người, 4–6 tuần, trong chương trình cohort. Điều đó
giải thích một số lựa chọn trông lạ: TF-IDF thay vì vector DB (chạy
offline, trích nguồn ổn định), SQLite mặc định thay vì bắt buộc
PostgreSQL, không dependency nào là điều kiện để chạy — thiếu thì **giảm
chế độ có báo**, không crash.

Xem tiếp: [01-architecture.md](01-architecture.md)

# Robot Planning Benchmark Platform — Phân tích nghiệp vụ & Định hướng kiến trúc

> **Tài liệu giai đoạn:** Discovery / Pre-build
> **Bối cảnh:** Nhóm 2–4 người, 4–6 tuần. Mục tiêu lần nộp: **MVP đúng yêu cầu cơ bản**. Mục tiêu dài hạn: **full có ROS2/Nav2 closed-loop**.
> **Nguyên tắc xuyên suốt tài liệu:** mọi lựa chọn kiến trúc dưới đây được chọn để **MVP hôm nay là tập con của hệ full ngày mai** — không đập đi xây lại.

---

## 0. Bối cảnh nghiên cứu (Prior Art) & Định vị sản phẩm

Ba nền tảng dưới đây phủ phần lớn không gian bài toán. Mục này tóm lược từng công trình theo dạng abstract, rồi chỉ ra lỗ hổng phương pháp luận mà dự án của chúng ta khai thác. **Kết luận đi trước: cả ba đều tạo ra *năng lực*; không công trình nào tạo ra *bằng chứng đáng tin*.** Đó là khoảng trống chúng ta chiếm.

---

### 0.1. PathBench — Toma, Hsueh, Jaafar, Murai, Kelly, Saeedi (Imperial College London & Ryerson, 2021)
*arXiv:2105.01777 — "A Benchmarking Platform for Classical and Learned Path Planning Algorithms"*

**Tóm lược.** PathBench là nền tảng mã nguồn mở để phát triển, trực quan hóa, huấn luyện, kiểm thử và benchmark các thuật toán lập quỹ đạo 2D/3D, cả cổ điển lẫn học máy, kèm phần mở rộng ROS để điều khiển robot thật. Hệ thống gồm bốn mô-đun: *Simulator* (mô phỏng và hiển thị), *Generator* (sinh và gán nhãn bản đồ huấn luyện), *Trainer* (pipeline huấn luyện PyTorch), *Analyzer* (thống kê và so sánh). Thuật toán cổ điển được hỗ trợ gồm A*, Dijkstra, wavefront, RRT/RRT*/RRT-Connect, sPRM, Bug1/Bug2, potential field và các bộ sampling từ OMPL; thuật toán học gồm VIN, GPPN, MPNet, Online LSTM, CAE-LSTM, Bagging LSTM và WPN. Chín chỉ số được định nghĩa: success rate, path length, distance-left-to-goal, time, path deviation, search space, peak memory, obstacle clearance và smoothness. Bản đồ đến từ ba nguồn: sinh thủ tục (uniform fill, block, house), bản đồ thật qua RosMap/gmapping, và bộ dữ liệu ngoài (HouseExpo, bản đồ game của Sturtevant, bản đồ thành phố OpenStreetMap). Kết quả cho thấy nhóm graph-based luôn tìm được lời giải khi tồn tại, còn nhóm học máy suy giảm nghiêm trọng khi bản đồ lớn lên — VIN và GPPN đạt **0% success rate** trên bản đồ thành phố và bản đồ game.

**Lỗ hổng khai thác được**

| # | Lỗ hổng | Bằng chứng trong paper |
|---|---|---|
| L1 | **Không có chướng ngại động.** Toàn bộ bản đồ là lưới tĩnh. | Không mục nào mô tả vật cản di chuyển |
| L2 | **Không có local planner, không closed-loop.** Không có DWA/TEB/MPPI; agent di chuyển trên ô lưới, không có động học robot. | Danh sách thuật toán mục IV |
| L3 | **Không đếm va chạm.** | Paper dẫn Nowak et al. như nguồn *chỉ số tiềm năng có thể bổ sung*, trong đó có số va chạm — tức thừa nhận là việc tương lai |
| L4 | **Không có kiểm định thống kê.** Báo cáo trung bình trần cho cả RRT* — một thuật toán ngẫu nhiên. | Table II–IV |
| L5 | **Không kiểm soát ngân sách tinh chỉnh.** Thừa nhận số mẫu là tham số ảnh hưởng hành vi nhóm sampling nhưng không chuẩn hóa. | Mục VII.A |
| L6 | **Không leaderboard, không experiment tracking, không manifest tái lập.** | Kết quả chỉ được in ra và vẽ biểu đồ |
| L7 | **Không có tầng sản phẩm** — không phân quyền, không phê duyệt, không audit. Giao diện là Panda3D desktop, không phải web. | Toàn bộ paper |

---

### 0.2. Arena 4.0 — Shcherbyna, Kästner, Diaz et al. (TU Berlin & NUS, ICRA 2025)
*arXiv:2409.12471 — "A Comprehensive ROS2 Development and Benchmarking Platform for Human-centric Navigation Using Generative-Model-based Environment Generation"*

**Tóm lược.** Arena 4.0 là bản kế thừa của Arena 1.0/2.0/3.0 và Arena-Bench, với ba đóng góp: (1) **Arena-gen** — pipeline sinh thế giới hai giai đoạn dùng LLM và diffusion model, biến prompt ngôn ngữ tự nhiên hoặc floorplan 2D thành môi trường 3D thông qua biểu diễn trung gian 3D Scene Graph và một GNN huấn luyện trên CubiCasa5K (~5000 bản quét mặt bằng thật); (2) **Arena-Models** — cơ sở dữ liệu ngữ nghĩa hơn 100 vật cản và hơn 15 mô hình người, truy vấn được bằng ngôn ngữ tự nhiên, kèm GUI quản trị; (3) **migrate hoàn toàn sang ROS 2 và Nav2**, mở đường cho triển khai trên phần cứng hiện đại. Nền tảng trừu tượng hóa trên cả Gazebo Garden và Unity, tích hợp HuNavSim cho hành vi người đi bộ, hỗ trợ 25+ planner và nhiều loại động học robot. Chi phí sinh thế giới khoảng 8 giây/môi trường trên RTX 4080, cho phép tạo hàng trăm biến thể cùng mức độ khó. Arena 4.0 được chọn làm nền tảng tổ chức competition SocialNav2025. Phần kiểm chứng gồm một **user study về tính khả dụng với 20 người tham gia** và một **phân tích thống kê scene-graph của các thế giới được sinh ra**.

**Lỗ hổng khai thác được**

| # | Lỗ hổng | Bằng chứng trong paper |
|---|---|---|
| A1 | **Paper không chứa bất kỳ kết quả so sánh planner nào.** Tuyên bố 25+ planner nhưng không có một bảng nào đối chiếu planner A với planner B. "Benchmarking platform" ở đây nghĩa là *hạ tầng chạy benchmark*, không phải *kết quả benchmark*. | Mục IV — Validation and Evaluation |
| A2 | **Định nghĩa độ khó bị vòng lặp logic.** Độ khó do LLM ước lượng từ số phòng và số vật cản; sau đó Fig. 6 kiểm chứng bằng cách vẽ số phòng và số vật cản theo độ khó đó. Chưa bao giờ kiểm chứng rằng "level 5" thực sự làm planner thất bại nhiều hơn "level 3". | Fig. 6 và chú thích |
| A3 | **Tầng phân tích là điểm yếu do chính user study chỉ ra.** Người dùng thấy pipeline đánh giá và vẽ biểu đồ phản trực giác, thích notebook của phiên bản cũ hơn giao diện web mới. | Mục IV.A |
| A4 | **Không có kiểm định thống kê, không có giao thức seed.** | Toàn bộ paper |
| A5 | **Không có tầng governance** — không vai trò, không phê duyệt, không audit trail. | Toàn bộ paper |
| A6 | **Chi phí gia nhập rất cao.** Ubuntu 22 + ROS2 Humble + Gazebo Garden + Unity + Docker + LLM + diffusion + GNN, cần GPU rời cho khâu sinh thế giới. | Table I, Fig. 7 |

> **Ghi chú định vị:** cách tiếp cận 2D nhẹ của chúng ta **không phải "Arena phiên bản nghèo"**. Nó là một điểm khác trên trục đánh đổi tốc độ ↔ độ chân thực. Với benchmark cần hàng nghìn episode, tốc độ là ràng buộc chi phối.

---

### 0.3. Alyassi, Cadena, Riener, Paez-Granados (ETH Zurich, Frontiers in Robotics and AI, 12/2025)
*doi:10.3389/frobt.2025.1658643 — "Social robot navigation: a review and benchmarking of learning-based methods"*

**Tóm lược.** Công trình kết hợp khảo sát và benchmark thực nghiệm cho điều hướng xã hội dựa trên học máy. Nhóm tác giả đề xuất taxonomy năm nhóm phương pháp — End-to-End, Human Position-based, Human Attention-based, Human Prediction-based và Safety-aware — rồi phân tích các thành phần hệ thống (hàm mục tiêu, mô phỏng đám đông, phát hiện/bám/dự đoán người). Phần benchmark so sánh ba baseline model-based (ORCA, Social Force Model, **DWA**) với sáu planner học đại diện cho năm nhóm, cộng một phương pháp imitation learning, trên **sáu kịch bản**: static, doorway, corridor, intersection, open-space ngẫu nhiên và open-space dùng dữ liệu người đi bộ thật (ETH/UCY). Hạ tầng mô phỏng chạy song song trên GPU với Habitat Sim, đạt khoảng **600 FPS cho đám đông 40 người**. Bảng chỉ số gồm khoảng 25 mục, chia hai nhóm điều hướng và xã hội. Kết luận: planner học **vượt trội một cách nhất quán** so với model-based về success rate và an toàn; planner prediction-based đạt kết quả tổng thể tốt nhất.

**Lỗ hổng khai thác được**

| # | Lỗ hổng | Bằng chứng trong paper |
|---|---|---|
| S1 | **Bất đối xứng thông tin đầu vào.** Baseline (ORCA/SFM/DWA) được cấp đặc quyền truy cập bố cục bản đồ và toàn bộ vị trí người; planner học chỉ nhận LiDAR. Hai nhóm giải hai bài toán khác nhau, nhưng được xếp chung một bảng. | Mục 4.3.1 |
| S2 | **Bất đối xứng ngân sách kỹ thuật — nghiêm trọng hơn PathBench.** Planner học nhận curriculum learning, được huấn luyện tập trung vào kịch bản làm kém, và **được nâng cấp kiến trúc khi hiệu năng chưa tốt** (thay CNN+MLP bằng kiến trúc tăng cường RNN). Baseline cổ điển nhận zero tinh chỉnh. | Mục 4.1, 4.3.2 |
| S3 | **Không kiểm định ý nghĩa thống kê.** Có error bar ở Fig. 4–5 nhưng không có test nào cho câu hỏi "chênh lệch thứ hạng này có ý nghĩa không". | Mục 4.4 |
| S4 | **Không có tập held-out thực sự.** Huấn luyện dùng curriculum trên cùng họ kịch bản; đánh giá lấy mẫu tham số ngẫu nhiên đều trong cùng họ đó. | Mục 4.1 |
| S5 | **Chỉ có local planner.** Paper nói rõ các phương pháp này cần tích hợp với global planner — A*, RRT*, Dijkstra nằm ngoài phạm vi. | Mục 2 |
| S6 | **Chính họ nêu nhu cầu chưa được đáp ứng**: cần phương pháp benchmark đáng tin cậy phản ánh đúng hiệu năng planner (5.1.5); và một crowd simulation hỗ trợ RL hiệu quả với kịch bản đa dạng vẫn còn thiếu (3.2.2). | Mục 3.2.2, 5.1.5 |

---

### 0.4. Ma trận tổng hợp

| Tiêu chí | PathBench 2021 | Arena 4.0 2025 | Alyassi 2025 | **Dự án này** |
|---|:---:|:---:|:---:|:---:|
| Global planner (A*, RRT*) | ✅ lõi | một phần (Nav2) | ❌ | ✅ |
| Local planner (DWA) | ❌ | ✅ 25+ | ✅ | ✅ |
| Chướng ngại động / người | ❌ | ✅ HuNavSim | ✅ SFM/ORCA/dữ liệu thật | ✅ |
| Sinh kịch bản | thủ tục | LLM + diffusion | tham số hóa | thủ tục |
| **Hiệu chuẩn độ khó thực nghiệm** | ❌ | ❌ (LLM ước lượng, chưa kiểm chứng) | ❌ | 🎯 |
| **Báo cáo kết quả so sánh** | ✅ | ❌ **không có** | ✅ | 🎯 |
| **Kiểm định thống kê** | ❌ | ❌ | một phần | 🎯 |
| **Cân bằng ngân sách tinh chỉnh** | ❌ | ❌ | ❌ (bất đối xứng công khai) | 🎯 |
| **Cân bằng thông tin đầu vào** | — | ❌ | ❌ (baseline đặc quyền) | 🎯 |
| **Tập held-out & generalization gap** | một phần | ❌ | ❌ | 🎯 |
| Manifest tái lập | ❌ | ❌ | ❌ | 🎯 |
| Vai trò / phê duyệt / audit | ❌ | ❌ | ❌ | 🎯 |
| Chất lượng tầng phân tích & báo cáo | GUI desktop | web (user chê) | biểu đồ tĩnh | 🎯 |
| Chi phí cài đặt | thấp | rất cao | cao (GPU) | thấp |

### 0.5. Một mâu thuẫn chưa ai giải quyết được — và đó là cơ hội

PathBench (2021) phát hiện planner học **sụp đổ hoàn toàn ngoài phân phối**: VIN và GPPN đạt 0% trên bản đồ thành phố. Alyassi et al. (2025) kết luận planner học **vượt trội nhất quán** so với cổ điển.

Một phần khác biệt đến từ khác bài toán (global grid planning ↔ local social navigation). Nhưng phần lớn hơn: **không bên nào kiểm soát công sức kỹ thuật đã bỏ ra, không bên nào kiểm định ý nghĩa thống kê.** Câu hỏi *"thuật toán học có thực sự tốt hơn cổ điển, hay chỉ được chăm sóc kỹ hơn?"* hiện **không thể trả lời bằng văn liệu đang tồn tại**.

### 0.6. Câu định vị

> **Arena 4.0 khiến việc *sinh kịch bản* trở nên dễ. Alyassi et al. khiến việc *chạy chúng* trở nên nhanh. PathBench khiến việc *cắm thuật toán mới* trở nên đơn giản.**
> **Không ai khiến kết quả so sánh trở nên *đáng tin*. Chúng ta xây tầng giao thức đánh giá.**

Điểm mạnh của định vị này: **nó không yêu cầu thắng ai về hạ tầng.** Đóng góp nằm ở phương pháp luận, mà phương pháp luận chạy được trên một simulator 2D Python cũng như trên Gazebo. Đây cũng là lý do khuyến nghị simulator ở mục 9.3 không thay đổi sau khi khảo sát prior art.

### 0.7. Ranh giới cạnh tranh — những gì dứt khoát không làm

- **Không** sinh thế giới bằng LLM/diffusion — Arena 4.0 sở hữu, không thắng nổi trong 6 tuần.
- **Không** làm 3D photorealistic — Alyassi đã có Habitat ở 600 FPS.
- **Không** đua số lượng planner (25+).
- **Không** đụng vào chỉ số xã hội chuyên sâu (proxemics, legibility, predictability) — đó là một văn liệu HRI riêng, làm hời hợt sẽ phản tác dụng.
- **Không** tuyên bố tính mới ở "unified interface cho planner" — PathBench đã claim từ 2021.

---

## 1. Tóm tắt điều hành (Executive Summary)

Đội kỹ sư robot đang có nhiều thuật toán lập quỹ đạo (A*, RRT*, DWA, RL) nhưng **không có một "sân chơi chung"** để so sánh chúng. Kết quả là việc chọn thuật toán cho một môi trường cụ thể (kho hàng, bệnh viện, nhà máy) dựa nhiều vào cảm tính và kinh nghiệm cá nhân, dẫn tới rủi ro chọn sai — mà cái giá của chọn sai chỉ lộ ra khi robot đã chạy thật.

Sản phẩm đề xuất là một **nền tảng benchmark có kiểm soát**: nạp bản đồ + kịch bản → chạy N thuật toán trên **cùng một điều kiện, cùng seed ngẫu nhiên** → đo bộ chỉ số chuẩn hóa → trực quan hóa quỹ đạo/va chạm → sinh báo cáo so sánh → **kỹ sư trưởng review và phê duyệt** trước khi cho phép triển khai.

Giá trị cốt lõi không phải là "viết được A* và RRT*" (những thứ này đã có thư viện). Giá trị cốt lõi là **tính công bằng, tính tái lập (reproducibility) và bằng chứng để ra quyết định**.

**Sau khi khảo sát prior art (mục 0), định vị được siết lại một bậc:** đã tồn tại những nền tảng mạnh hơn ta rất nhiều về hạ tầng — Arena 4.0 sinh môi trường bằng LLM+diffusion, Alyassi et al. chạy 600 FPS trên GPU, PathBench có sẵn 15+ thuật toán. Nhưng **không nền tảng nào trong số đó kiểm soát ngân sách tinh chỉnh, cân bằng thông tin đầu vào, hiệu chuẩn độ khó bằng thực nghiệm, hay kiểm định ý nghĩa thống kê**. Đóng góp của dự án này vì vậy **không phải hạ tầng mà là giao thức đánh giá** — bộ quy tắc khiến một phép so sánh trở nên đáng tin. Xem mục 7.0 và 8.6.

---

## 2. Bài toán nghiệp vụ

### 2.1. Doanh nghiệp đang gặp vấn đề gì?

Hình dung một công ty làm AMR (Autonomous Mobile Robot) giao hàng trong kho. Họ có 4 kỹ sư, mỗi người "quen tay" một thuật toán:

- Kỹ sư A tin A* là đủ, vì kho là lưới kệ vuông vắn.
- Kỹ sư B đẩy RRT*, vì có khách hàng yêu cầu robot chui qua khe hẹp.
- Kỹ sư C bảo phải có DWA, vì kho có người đi bộ.
- Kỹ sư D muốn thử RL, vì "đang là xu hướng".

Khi có dự án mới ở một môi trường mục tiêu khác (ví dụ: hành lang bệnh viện, đông người, nhiều cửa hẹp), cuộc họp chọn thuật toán biến thành **tranh luận dựa trên giai thoại** thay vì dựa trên số liệu. Mỗi người test trên máy mình, bản đồ mình tự vẽ, tham số mình tự chỉnh, thước đo mình tự định nghĩa. Không ai bác bỏ được ai vì **không có kết quả nào so sánh được với kết quả nào**.

> **Ví dụ dễ hình dung về sự "không công bằng":**
> Kỹ sư A báo cáo "A* chạy 12 ms". Kỹ sư B báo cáo "RRT* chạy 340 ms". Nghe thì A* thắng áp đảo.
> Nhưng: A đo trên bản đồ 200×200 ô, B đo trên bản đồ 1000×1000 ô. A tính từ lúc gọi hàm plan, B tính cả thời gian dựng costmap. A chạy trên máy M3 Pro, B chạy trên con laptop 5 năm tuổi. A đặt goal cách 5 m, B đặt goal cách 40 m.
> **Con số có thật, nhưng phép so sánh thì vô nghĩa.** Đây chính xác là vấn đề mà nền tảng này giải quyết.

### 2.2. Quy trình hiện tại (As-Is)

| # | Bước | Ai làm | Vấn đề |
|---|------|--------|--------|
| 1 | Nhận yêu cầu môi trường mới từ khách hàng | PM / Solution | Mô tả môi trường bằng lời, không có bản đồ chuẩn |
| 2 | Mỗi kỹ sư tự viết script test thuật toán mình quen | Robotics Engineer | Code rời rạc, nằm trong notebook cá nhân, không tái sử dụng |
| 3 | Tự vẽ vài bản đồ ad-hoc để thử | Robotics Engineer | Bản đồ không đại diện cho môi trường thật, mỗi người một kiểu |
| 4 | Chạy tay vài lần, chụp màn hình quỹ đạo | Robotics Engineer | Chạy 3–5 lần, không đủ mẫu thống kê; kết quả phụ thuộc seed |
| 5 | Ghi số liệu vào Excel / Slack | Robotics Engineer | Không có metadata (seed, tham số, version code) → không tái lập được |
| 6 | Họp chốt thuật toán | Tech Lead + team | Tranh luận cảm tính, mất 1–2 buổi họp |
| 7 | Tích hợp vào robot thật, test tại hiện trường | Field Engineer | **Đây là nơi lỗi mới lộ ra** — tốn kém nhất |
| 8 | Phát hiện không phù hợp → quay lại bước 2 | Cả team | Vòng lặp đắt đỏ |

### 2.3. Điều gì gây tốn thời gian và chi phí?

Chia làm 4 nhóm chi phí:

**(a) Chi phí lặp lại công việc (rework)**
Mỗi kỹ sư viết lại lớp môi trường, lớp đo đạc, lớp vẽ hình cho riêng mình. Ước tính 2–3 ngày/người/dự án chỉ để dựng lại thứ đã tồn tại.

**(b) Chi phí quyết định sai phát hiện muộn**
Lỗi phát hiện ở bước 7 (test hiện trường) đắt hơn phát hiện ở bước 4 (mô phỏng) khoảng 1–2 bậc độ lớn: phải huy động robot thật, kỹ sư đi hiện trường, thuê mặt bằng, rủi ro hỏng thiết bị, và tệ nhất là mất uy tín với khách hàng.

**(c) Chi phí không tái lập được (non-reproducibility)**
Ba tháng sau, khách hỏi "vì sao chọn DWA?", không ai dựng lại được kết quả cũ. Phải chạy lại từ đầu.

**(d) Chi phí cơ hội**
Thuật toán mới (RL, MPPI, Hybrid A*) không được đánh giá vì chi phí đưa vào so sánh quá cao. Team bị kẹt trong vùng an toàn.

---

## 3. Pain Points (điểm đau) — xếp theo mức độ nghiêm trọng

| ID | Pain point | Ai chịu đau | Mức độ | Tính năng nào giải quyết |
|----|-----------|-------------|--------|--------------------------|
| P1 | **So sánh không công bằng** — khác bản đồ, khác tham số, khác máy, khác cách đo | Robotics Engineer, Tech Lead | 🔴 Cao | Scenario chuẩn hóa + Runner đồng nhất + Metric chuẩn hóa |
| P2 | **Không tái lập được kết quả** — thiếu seed, version, tham số | Tech Lead, QA | 🔴 Cao | Experiment tracking (MLflow), snapshot config + git SHA |
| P3 | **Không đủ mẫu thống kê** — chạy 3 lần rồi kết luận | Robotics Engineer | 🔴 Cao | Batch runner đa seed + báo cáo có khoảng tin cậy |
| P4 | **Quyết định không có bằng chứng, không có dấu vết phê duyệt** | Tech Lead, PM | 🟠 Trung bình-cao | Approval workflow (human-in-the-loop) + audit log |
| P5 | **Debug bằng mắt rất khó** — không biết robot va chạm ở đâu, lúc nào, vì sao | Robotics Engineer | 🟠 Trung bình-cao | Visualization quỹ đạo + replay theo thời gian + đánh dấu va chạm |
| P6 | **Rework lớp hạ tầng** — mỗi người viết lại env/metric/plot | Robotics Engineer | 🟠 Trung bình | Framework có plugin interface chung |
| P7 | **Benchmark chạy chậm/tốn** — hàng nghìn episode chạy tuần tự | Robotics Engineer | 🟡 Trung bình | Headless + parallel + caching |
| P8 | **Thuật toán mới khó đưa vào đánh giá** | Team | 🟡 Trung bình | Plugin registry — thêm thuật toán = thêm 1 file |
| P9 | **Rủi ro chạy thử trên robot thật khi chưa validate** | Field Engineer, PM | 🔴 Cao (an toàn) | Gate phê duyệt bắt buộc + chế độ sim-only |

---

## 4. Target Audience & Personas

Đề bài yêu cầu **≥2 vai trò**. Đề xuất mô hình 4 vai trò (RBAC), trong đó MVP bắt buộc làm 2 vai in đậm.

### 4.1. Người dùng chính (Primary)

**① Robotics / Planning Engineer — "Người chạy thí nghiệm"** ⭐ *(vai trò bắt buộc MVP)*
- **Là ai:** Kỹ sư 1–5 năm kinh nghiệm, mạnh Python/C++, hiểu thuật toán.
- **Cần gì:** Đăng ký thuật toán mới nhanh, chạy benchmark, xem quỹ đạo, tinh chỉnh tham số, so sánh phiên bản.
- **Đo thành công bằng:** "Tôi thêm thuật toán mới và có kết quả so sánh trong dưới 1 giờ."
- **Quyền:** tạo/chạy/xem experiment, upload map & scenario, **không** được phê duyệt.

**② Tech Lead / Robotics Manager — "Người phê duyệt"** ⭐ *(vai trò bắt buộc MVP)*
- **Là ai:** Kỹ sư trưởng, chịu trách nhiệm kỹ thuật và an toàn.
- **Cần gì:** Bảng xếp hạng dễ đọc, xem bằng chứng, ghi nhận xét, **Approve / Reject** một cấu hình thuật toán cho một môi trường mục tiêu.
- **Đo thành công bằng:** "Tôi ra quyết định trong 15 phút và quyết định đó có dấu vết kiểm toán."
- **Quyền:** toàn bộ quyền của ①, cộng thêm quyền phê duyệt và khóa kết quả.

### 4.2. Người dùng phụ (Secondary — pha sau)

**③ QA / Validation Engineer** — thiết kế bộ kịch bản khắc nghiệt (edge case: hành lang hẹp, ngõ cụt, người cắt ngang đột ngột), chạy regression test khi code thay đổi, đảm bảo không bị "tụt lùi hiệu năng".

**④ PM / Solution Architect / Presales** — chỉ đọc. Cần biểu đồ và báo cáo xuất được để nói chuyện với khách hàng: "với môi trường của anh, cấu hình này đạt tỷ lệ tới đích 97,3%".

### 4.3. Ai KHÔNG phải người dùng
Không nhắm tới người dùng cuối vận hành robot, không nhắm tới nghiên cứu sinh cần môi trường vật lý độ chính xác cao (chỗ đó là Isaac Sim/Gazebo thuần). Xác định rõ điều này giúp tránh phình phạm vi.

---

## 5. Core Value Proposition

> **"Một sân chơi công bằng, tái lập được, để chọn đúng thuật toán lập quỹ đạo cho đúng môi trường — trước khi robot chạm mặt đất."**

Ba trụ giá trị:

**① Fairness (Công bằng)**
Cùng bản đồ, cùng điểm xuất phát/đích, cùng seed, cùng mô hình động học robot, cùng máy chạy, cùng định nghĩa chỉ số. Mọi khác biệt trong kết quả **chỉ đến từ thuật toán**.

**② Reproducibility (Tái lập)**
Mỗi lần chạy được đóng gói: `scenario_id + algorithm_version + params_hash + seed + git_sha + docker_image`. Ba tháng sau bấm nút là dựng lại y hệt.

**③ Decision Support with Accountability (Hỗ trợ quyết định có trách nhiệm)**
Không chỉ ra số, mà ra **khuyến nghị có điều kiện** ("môi trường đông người → ưu tiên DWA; môi trường tĩnh, khe hẹp → ưu tiên RRT* + shortcut smoothing") và bắt buộc có chữ ký phê duyệt của con người.

**④ Protocol-first Evaluation (Đánh giá theo giao thức) — trụ mới sau khảo sát prior art**
Ba nền tảng lớn nhất trong lĩnh vực đều dừng ở "chạy được nhiều thuật toán". Trụ này đi xa hơn: mỗi phép so sánh phải khai báo **thuật toán thấy gì** (cân bằng thông tin), **đã được tinh chỉnh bao nhiêu** (cân bằng ngân sách), **trên độ khó nào đo bằng thực nghiệm** (không phải bằng số vật cản), và **chênh lệch có ý nghĩa thống kê không**. Đây là thứ biến bảng số thành bằng chứng.

### Điều gì làm sản phẩm này khác với "chạy tay vài script"?
| | Chạy tay | Nền tảng này |
|---|---|---|
| Số lần chạy | 3–5 | 100–1000 episode/thuật toán |
| Khác biệt điều kiện | Có | Bị loại bỏ theo thiết kế |
| Truy vết | Không | Đầy đủ |
| Thời gian ra quyết định | 1–2 tuần | 1–2 ngày |
| Dấu vết phê duyệt | Không | Có |

---

## 6. Quy trình mục tiêu (To-Be)

```
[1] Định nghĩa môi trường mục tiêu
     PM/Solution mô tả → chọn/tạo Scenario Pack (bản đồ + mật độ chướng ngại + luồng người đi)
              ↓
[2] Đăng ký thuật toán ứng viên
     Engineer chọn từ registry: A*, RRT*, DWA, (RL) + bộ tham số
              ↓
[3] Chạy benchmark (headless, song song, nhiều seed)
     Runner sinh N episode = scenarios × algorithms × seeds
              ↓
[4] Thu thập chỉ số + lưu trace
     Metrics → MLflow/DB;  Trace quỹ đạo → object storage
              ↓
[5] Trực quan hóa & phân tích
     Leaderboard + biểu đồ + replay quỹ đạo, đánh dấu điểm va chạm
              ↓
[6] ⭐ HUMAN-IN-THE-LOOP: Tech Lead review
     Xem bằng chứng → comment → APPROVE / REJECT
              ↓
[7] Xuất báo cáo + "Approved Config" (JSON/YAML đã ký)
              ↓
[8] (Pha sau) Chỉ config đã Approved mới được nạp vào Nav2/robot thật
```

**Chốt chặn an toàn (safety gate):** hệ thống ở chế độ **sim-only**. Không có bất kỳ đường dẫn kỹ thuật nào từ giao diện tới robot thật. Việc "triển khai" chỉ là xuất ra một file cấu hình đã được phê duyệt — con người mang file đó đi nạp ở một quy trình khác. Đây là ràng buộc kiến trúc, không phải chỉ là quy tắc trên giấy.

---

## 7. Danh mục tính năng đề xuất

Ưu tiên theo **MoSCoW**. Cột "Pha" ánh xạ trực tiếp sang roadmap ở mục 10.

### 7.0. Bộ giao thức đánh giá — differentiator cốt lõi ⭐

Đây là nhóm tính năng **không nền tảng nào trong mục 0 có**. Chúng rẻ về công sức, nhưng phải được thiết kế vào Scenario Spec và Planner interface **ngay từ tuần 0.5** — để sau sẽ phải sửa xuyên suốt.

| ID | Giao thức | Nội dung | Lỗ hổng bị đánh |
|----|-----------|----------|-----------------|
| **P01** | **Cân bằng ngân sách tinh chỉnh** | Mỗi planner nhận đúng *N* lần thử Optuna trên tập dev, không gian tham số khai báo trước, log toàn bộ. Không planner nào được nâng cấp kiến trúc giữa chừng. Báo cáo kèm **đường cong hiệu năng theo ngân sách** — nếu DWA bão hòa sau 20 lần thử còn RL vẫn tăng ở lần 200, đó là thông tin không ai đang báo cáo. | L5, S2 |
| **P02** | **Khai báo cân bằng thông tin** | Mỗi planner khai báo nó *thấy gì*: bản đồ đầy đủ? vị trí người chính xác? chỉ LiDAR? Kết quả được **nhóm theo lớp thông tin**, không trộn chung bảng. | S1 |
| **P03** | **Hiệu chuẩn độ khó thực nghiệm** | Độ khó **không** định nghĩa bằng số vật cản, mà bằng **tỷ lệ thất bại đo được của một bộ baseline tham chiếu**. Hiệu năng báo cáo dưới dạng **đường cong theo độ khó**, không phải một con số trung bình. | A2 |
| **P04** | **Quy trình thống kê** | ≥30 seed mỗi cặp (scenario, algorithm); bootstrap 1000 lần lấy CI 95%; Wilcoxon signed-rank so planner tốt nhất với từng planner còn lại; báo cáo p-value; xếp hạng bằng average rank score. | L4, A4, S3 |
| **P05** | **Tập held-out & generalization gap** | Tinh chỉnh trên tập bản đồ dev, đánh giá trên **tập kịch bản chưa từng thấy**, báo cáo hiệu số dev − held-out như một chỉ số hạng nhất. | L1, A2, S4 |

> **Vì sao P03 quan trọng hơn vẻ ngoài của nó:** một bảng "success rate 87%" che giấu mọi thứ. Một đường cong cho thấy planner A giữ 95% đến độ khó 0.6 rồi rơi thẳng xuống 20%, còn planner B suy giảm đều từ 88% xuống 60% — hai đường cong đó dẫn tới **hai quyết định triển khai hoàn toàn khác nhau**, dù trung bình gộp có thể bằng nhau.

> **Vì sao P02 rẻ mà mạnh:** so sánh một planner biết trước toàn bộ vị trí người với một planner chỉ có LiDAR, rồi kết luận cái sau thắng — giống so kỳ thủ được xem bài đối thủ với kỳ thủ chơi bịt mắt. Kết quả có thể vẫn đúng, nhưng nó không nói lên điều ta tưởng. Chi phí để sửa: thêm một trường `observation_class` vào metadata của planner.

**Phạm vi MVP:** P02 và P04 làm đầy đủ ngay pha 1 (rẻ nhất, phòng thủ tốt nhất). P03 và P05 làm ở pha 2. P01 làm ở pha 2 với ngân sách nhỏ (ví dụ 30 trial/planner), mở rộng ở pha 3.

### 7.1. MVP — Must have (Pha 1, tuần 1–4)

| ID | Tính năng | Mô tả ngắn | Giải quyết pain |
|----|-----------|-----------|-----------------|
| F01 | **Map Loader** | Nạp bản đồ dạng ảnh PGM/PNG + file YAML metadata (resolution, origin) — **dùng đúng định dạng của ROS `map_server`** | P1, P6 |
| F02 | **Scenario Spec** | File YAML mô tả: map, start, goal, robot model, chướng ngại tĩnh/động, seed, timeout | P1, P2 |
| F03 | **Simulator core 2D** | Vòng lặp mô phỏng thời gian rời rạc, mô hình robot differential drive, phát hiện va chạm | P1 |
| F04 | **Planner Registry + ≥2 thuật toán** | A* (global) + DWA (local) làm cặp mặc định; RRT* là thuật toán thứ 3 | P6, P8 |
| F05 | **Metrics Engine** | Tính đủ 5 nhóm chỉ số bắt buộc từ trace | P1 |
| F06 | **Batch Runner** | Chạy tổ hợp scenarios × algorithms × seeds, headless | P3, P7 |
| F07 | **Experiment Tracking** | MLflow: log params, metrics, artifacts, git SHA | P2 |
| F08 | **Web UI: Trajectory Viewer** | Canvas 2D vẽ bản đồ + quỹ đạo nhiều thuật toán chồng lên nhau, tua thời gian, đánh dấu va chạm | P5 |
| F09 | **Comparison Report** | Bảng so sánh + biểu đồ, xuất Markdown/PDF | P1, P4 |
| F10 | **RBAC 2 vai trò** | Engineer / Approver | P4 |
| F11 | **Approval Workflow** | Nút Approve/Reject + comment + audit log bất biến | P4, P9 |
| F12 | **Docker Compose** | Chạy toàn hệ thống bằng 1 lệnh | — |

### 7.2. Nên có — Should have (Pha 2, tuần 5–6)

| ID | Tính năng | Mô tả |
|----|-----------|-------|
| F13 | **Dynamic obstacles** | Chướng ngại di chuyển theo waypoint hoặc mô hình Social Force (mô phỏng người đi bộ) |
| F14 | **Scenario Pack** | Bộ kịch bản chuẩn: kho hàng, hành lang hẹp, mê cung, không gian mở đông người, ngõ cụt |
| F15 | **Leaderboard định lượng** | Xếp hạng đa tiêu chí có trọng số điều chỉnh được + kiểm định thống kê |
| F16 | **Parallel execution** | `multiprocessing` / Ray, chạy song song theo số core |
| F17 | **Regression guard** | Cảnh báo khi thuật toán tụt hiệu năng so với baseline đã lưu |

### 7.3. Có thì tốt — Could have (Pha 3, sau khóa học)

| ID | Tính năng | Mô tả |
|----|-----------|-------|
| F18 | **ROS2/Nav2 backend** | Chạy closed-loop thật với Nav2 stack, so sánh trực tiếp với plugin Nav2 |
| F19 | **RL planner (PyTorch)** | Huấn luyện agent với môi trường Gymnasium bọc quanh chính simulator này |
| F20 | **2.5D elevation layer** | Lớp độ cao + chi phí địa hình (dốc, gờ, bậc) |
| F21 | **Param auto-tuning** | Optuna tìm bộ tham số tốt nhất cho mỗi thuật toán trên mỗi môi trường |
| F22 | **LLM Report Assistant** | Sinh diễn giải ngôn ngữ tự nhiên từ bảng chỉ số ("RRT* thua ở đây vì...") |
| F23 | **Sensor noise / localization error** | Mô phỏng nhiễu odometry, LiDAR để test tính bền |

### 7.4. Không làm — Won't have (chốt phạm vi rõ ràng)
Vật lý độ chính xác cao (contact dynamics), mô phỏng 3D đầy đủ, multi-robot fleet, điều khiển robot thật, xử lý dữ liệu người dùng thật.

---

## 8. Định nghĩa chỉ số (Metrics) — phần dễ làm sai nhất

Đây là **trái tim của tính công bằng**. Nếu định nghĩa chỉ số mơ hồ, cả hệ thống mất giá trị. Mỗi chỉ số cần một định nghĩa toán học duy nhất, viết trong code một chỗ duy nhất.

### 8.1. Hiệu quả (Effectiveness)

**Success Rate (tỷ lệ tới đích)**
`success = (đến trong bán kính goal_tolerance) AND (không va chạm) AND (không quá timeout)`
> ⚠️ Bẫy thường gặp: coi "đến đích nhưng có va chạm" là thành công. Phải định nghĩa cứng ngay từ đầu.

**Failure breakdown:** phân loại lý do thất bại — `no_path_found` / `collision` / `timeout` / `stuck` (đứng yên quá T giây). Chỉ số này giá trị hơn con số tổng nhiều: 20% fail vì timeout khác hoàn toàn 20% fail vì đâm vào tường.

### 8.2. Chất lượng đường đi (Path Quality)

**Path Length:** `L = Σ ||p_{i+1} - p_i||`

**Path Optimality Ratio:** `L / L_ref`, với `L_ref` là đường ngắn nhất tìm bằng Dijkstra trên grid.
> Vì sao cần tỷ lệ này? Vì so sánh "đường dài 42 m" giữa hai bản đồ khác nhau là vô nghĩa. Chuẩn hóa theo đường tối ưu lý thuyết mới cho phép gộp kết quả nhiều bản đồ lại.

**Smoothness (độ mượt)** — đây là khái niệm hay bị định nghĩa lơ mơ nhất:
> **Giải thích dễ hiểu:** Tưởng tượng bạn ngồi trên xe. Hai xe đi cùng quãng đường, cùng thời gian. Xe A đi một đường cong đều. Xe B đi zig-zag giật cục. Quãng đường như nhau, nhưng xe B làm bạn say xe, hao pin hơn, mòn bánh hơn. "Smoothness" chính là đại lượng phân biệt A với B.
>
> **Cách đo:** dùng tổng bình phương độ thay đổi hướng giữa các đoạn liên tiếp:
> `S = Σ (Δθ_i)²` — càng nhỏ càng mượt.
> Bổ sung: **jerk trung bình** (đạo hàm bậc 3 của vị trí) cho quỹ đạo thực thi. Hai chỉ số này bổ trợ nhau: cái đầu đo hình dạng đường đi, cái sau đo cảm giác chuyển động.

**Clearance (khoảng cách an toàn):** khoảng cách nhỏ nhất và trung bình tới chướng ngại gần nhất. Một đường đi ngắn nhưng cà sát tường là đường đi tệ trong thực tế.

### 8.3. Hiệu năng tính toán (Computational)

- **Planning time:** thời gian sinh đường đi toàn cục lần đầu (ms).
- **Control loop latency:** thời gian tính mỗi bước của local planner — báo cáo **p50 / p95 / p99**, không phải trung bình.
> **Vì sao là p99 chứ không phải trung bình?** Robot chạy vòng điều khiển 20 Hz, tức mỗi bước có 50 ms. Nếu trung bình 10 ms nhưng p99 là 200 ms, thì cứ 100 bước lại có 1 bước robot "đơ" — và trong 200 ms đó robot đi mù, đủ để đâm vào người. Trung bình che giấu đúng cái rủi ro mình cần thấy.
- **Peak memory, số node mở rộng** (đặc thù thuật toán tìm kiếm).

### 8.4. An toàn (Safety)
- **Collision count** và **time-to-first-collision**.
- **Near-miss count:** số lần clearance < ngưỡng cảnh báo. Chỉ báo sớm quan trọng — thuật toán 0 va chạm nhưng 50 near-miss là thuật toán đang gặp may.

### 8.5. Nhiệm vụ (Task)
- **Travel time** (thời gian mô phỏng), **average/max speed**, **stop-and-go count** (số lần dừng hẳn rồi đi tiếp — chỉ báo dao động của local planner).

### 8.6. Giao thức so sánh công bằng — hiện thực hóa P01–P05

Mục 8.1–8.5 định nghĩa **đo cái gì**. Mục này định nghĩa **đo trong điều kiện nào** — và đây chính là phần mà cả PathBench, Arena 4.0 lẫn Alyassi et al. đều bỏ trống.

**(a) Thống kê — P04**
Mỗi cặp (scenario, algorithm) chạy tối thiểu **30 seed**. Báo cáo **median + IQR** thay vì mean + std (dữ liệu robot thường lệch phải mạnh, mean bị outlier kéo). Lấy **khoảng tin cậy 95% bằng bootstrap 1000 lần**. Khi tuyên bố "A tốt hơn B", dùng kiểm định phi tham số (Wilcoxon signed-rank hoặc Mann-Whitney U tùy thiết kế ghép cặp), báo cáo p-value **và** effect size. Xếp hạng tổng hợp nhiều kịch bản bằng **average rank score**, không phải bằng trung bình của các chỉ số khác đơn vị.

**(b) Cân bằng thông tin đầu vào — P02**
Mỗi planner khai báo lớp quan sát trong metadata:

```yaml
planner:
  name: dwa_v1
  observation_class: lidar_only      # full_map | human_states | lidar_only | lidar+human_states
  requires_global_path: true
```

Leaderboard **nhóm theo `observation_class`**. So sánh chéo lớp vẫn được phép nhưng phải gắn nhãn cảnh báo rõ ràng trong báo cáo.

**(c) Cân bằng ngân sách tinh chỉnh — P01**
Khai báo trước không gian tham số cho từng planner, cấp **cùng số trial** cho tất cả, log toàn bộ lịch sử tìm kiếm. Quy tắc bất di bất dịch: **không sửa kiến trúc hay thêm module cho một planner giữa chừng vì nó chạy kém** — nếu phải làm, đó là một planner mới, đăng ký lại từ đầu với ngân sách riêng.

**(d) Hiệu chuẩn độ khó — P03**
Định nghĩa: `difficulty(scenario) = 1 − success_rate(baseline_reference, scenario, 30 seeds)`, với `baseline_reference` là một cấu hình cố định được ghim version (đề xuất: A* + DWA với tham số mặc định). Các trục sinh kịch bản (độ rộng khe / độ rộng robot, mật độ vật cản, mật độ người, độ ngoằn ngoèo) được **hiệu chuẩn ngược** để phủ đều dải độ khó 0.0–0.9. Kết quả báo cáo dưới dạng đường cong `success_rate(difficulty)` cho từng planner.

**(e) Tập held-out — P05**
Chia kịch bản thành `dev` (dùng để tinh chỉnh, xem tự do) và `holdout` (chỉ chạy một lần ở cuối, không được xem trước). Báo cáo bắt buộc có cột **generalization gap = metric_dev − metric_holdout**. Đây là chỉ số phát hiện overfit vào bộ benchmark — chính là hiện tượng PathBench quan sát được khi VIN/GPPN rơi từ hoạt động bình thường xuống 0% khi đổi họ bản đồ.

---

## 9. Kiến trúc công nghệ sơ bộ

### 9.1. Nguyên tắc số 1: Contract-First để MVP nâng cấp được lên full

Đây là câu trả lời trực tiếp cho yêu cầu *"làm MVP rồi lên full mà không đập đi xây lại"*.

**Ý tưởng cốt lõi:** Thứ dễ bị vứt bỏ nhất khi nâng cấp là **cái lõi mô phỏng**. Vậy thì đừng để bất cứ thứ gì phụ thuộc trực tiếp vào nó. Thay vào đó, định nghĩa **4 hợp đồng (interface)** và mọi thành phần chỉ nói chuyện qua hợp đồng.

> **Ví dụ dễ hiểu — ổ cắm điện:**
> Bạn không nối thẳng dây tủ lạnh vào lưới điện quốc gia. Bạn cắm vào **ổ cắm**. Nhờ vậy, khi chuyển nhà (đổi hạ tầng điện), tủ lạnh vẫn dùng được — miễn ổ cắm cùng chuẩn.
> Ở đây: `SimBackend` là ổ cắm. MVP cắm vào "ổ" tự dựng bằng Python. Pha 3 cắm vào "ổ" Gazebo/ROS2. Thuật toán, metrics, UI, MLflow — **không đổi một dòng code**.

**Bốn hợp đồng cần chốt trước khi viết dòng code đầu tiên:**

```python
# ① Backend mô phỏng — thay được: Simple2D → Gazebo/ROS2
class SimBackend(Protocol):
    def reset(self, scenario: Scenario) -> Observation: ...
    def step(self, cmd: Twist) -> tuple[Observation, StepInfo]: ...
    def get_costmap(self) -> Costmap2D: ...

# ② Global planner — thay được: A*, Dijkstra, RRT*, Hybrid A*, Nav2 planner plugin
class GlobalPlanner(Protocol):
    def plan(self, start: Pose2D, goal: Pose2D, costmap: Costmap2D) -> Path: ...

# ③ Local planner / controller — thay được: DWA, TEB, MPPI, RL policy, Nav2 controller plugin
class LocalPlanner(Protocol):
    def compute_velocity(self, pose: Pose2D, path: Path, obs: Observation) -> Twist: ...

# ④ Ghi nhận — không đổi dù backend là gì
class TraceRecorder(Protocol):
    def record(self, t: float, state: RobotState, event: Event | None) -> None: ...
```

**Ba quyết định thiết kế "trả tiền về sau" (mỗi cái tốn thêm ~nửa ngày ở MVP, tiết kiệm hàng tuần ở pha 3):**

1. **Tách rõ Global planner và Local planner ngay từ MVP.** Đây chính xác là cách Nav2 tổ chức (`nav2_planner` + `nav2_controller`). Khi lên ROS2, A* của bạn map 1-1 sang một `nav2_core::GlobalPlanner` plugin. Nếu MVP gộp chung "một hàm chạy từ start tới goal", pha 3 phải viết lại.

2. **Dùng schema dữ liệu kiểu ROS ngay từ đầu, nhưng KHÔNG phụ thuộc ROS.**
   Tự định nghĩa dataclass `Pose2D`, `Path`, `Twist`, `OccupancyGrid`, `LaserScan` với đúng tên trường và đơn vị như `geometry_msgs` / `nav_msgs`. Bản đồ dùng đúng định dạng `map_server` (PGM + YAML với `resolution`, `origin`, `negate`, `occupied_thresh`).
   → Khi lên ROS2, việc chuyển đổi chỉ là một lớp adapter mỏng ~100 dòng, không phải viết lại logic.

3. **Vòng lặp mô phỏng đi theo thời gian, không theo bước.**
   MVP có thể mô phỏng tức thì, nhưng hãy để mọi thứ nhận `dt` và timestamp. Closed-loop thật chạy theo thời gian thực. Nếu MVP giả định "mỗi bước là một đơn vị", pha 3 phải sửa xuyên suốt.

### 9.2. Sơ đồ kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND — Next.js + React + Canvas 2D                     │
│  · Map/Scenario Editor  · Trajectory Viewer & Replay        │
│  · Leaderboard          · Approval Console (Tech Lead)      │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST / WebSocket (stream replay)
┌───────────────────────────▼─────────────────────────────────┐
│  API LAYER — FastAPI                                        │
│  · Auth + RBAC (Engineer / Approver)                        │
│  · Scenario CRUD  · Job submit  · Results query             │
│  · Approval endpoints + audit log                           │
└───────────────────────────┬─────────────────────────────────┘
                            │ job queue (Celery/RQ + Redis)
┌───────────────────────────▼─────────────────────────────────┐
│  BENCHMARK ORCHESTRATOR (Python)                            │
│  · Sinh ma trận: scenarios × algorithms × seeds             │
│  · Chạy song song (multiprocessing → Ray khi cần)           │
│  · Đảm bảo tính xác định: seed cố định, ghim version        │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┴────────────────────┐
        ▼                                        ▼
┌───────────────────────┐          ┌──────────────────────────┐
│  SIMULATION CORE      │          │  PLANNER REGISTRY        │
│  (interface SimBackend)│◄────────►│  (Global + Local)        │
│                       │          │                          │
│  MVP:  Simple2D (numpy)│          │  A*, Dijkstra, RRT*      │
│  P3 :  Gazebo/ROS2     │          │  DWA, (MPPI), (RL policy)│
│                       │          │  Nav2 plugins (P3)       │
│  · robot kinematics   │          └──────────────────────────┘
│  · collision detection│
│  · dynamic obstacles  │
│  · costmap layers     │
└───────────┬───────────┘
            │ trace stream
┌───────────▼─────────────────────────────────────────────────┐
│  METRICS & STORAGE                                          │
│  · Metrics Engine (tính từ trace — độc lập backend)         │
│  · MLflow: params/metrics/artifacts   · PostgreSQL: metadata│
│  · Object store (MinIO/local): trace + video replay         │
└─────────────────────────────────────────────────────────────┘

           ⟨ Toàn bộ đóng gói bằng Docker Compose ⟩
```

### 9.3. Khuyến nghị lựa chọn Simulator (bạn nhờ tôi tư vấn)

**Khuyến nghị: tự dựng simulator 2D bằng Python (numpy), thiết kế sẵn cổng cắm ROS2 — tức phương án lai.**

Lý do:

| Tiêu chí | Tự dựng 2D | Gazebo/ROS2 ngay từ đầu |
|---|---|---|
| Thời gian đến kết quả đầu tiên | 3–5 ngày | 1,5–2,5 tuần (chỉ để dựng môi trường) |
| Tốc độ chạy benchmark | **Rất nhanh** — 1000+ episode/phút, headless, song song dễ | Chậm — Gazebo chạy gần thời gian thực, nặng, khó song song hàng loạt |
| Chi phí hạ tầng | Thấp, chạy trên laptop | Cao, cần GPU/nhiều RAM |
| Tính xác định (determinism) | **Kiểm soát hoàn toàn** | Khó — physics engine có yếu tố không xác định |
| Độ chân thực vật lý | Thấp | Cao |
| Rủi ro với deadline 4–6 tuần | Thấp | **Cao — dễ hết thời gian ở khâu setup** |

Yếu tố quyết định: **mục tiêu của dự án là so sánh *thuật toán lập quỹ đạo*, không phải kiểm chứng *động lực học*.** Với câu hỏi "A* hay DWA phù hợp hơn cho hành lang đông người", độ chân thực vật lý của Gazebo hầu như không thay đổi thứ hạng, trong khi nó lấy đi tốc độ — mà tốc độ chính là thứ cho phép chạy 30 seed × 5 kịch bản × 4 thuật toán.

Gazebo/Nav2 vẫn cần thiết, nhưng ở **vai trò khác**: không phải để benchmark hàng loạt, mà để **validation cuối** trên 2–3 cấu hình đã lọt vòng chung kết. Đó là lý do kiến trúc `SimBackend` ở trên: MVP dùng backend nhanh để sàng lọc, pha 3 thêm backend chân thực để xác nhận. Hai backend cùng tồn tại, không thay thế nhau.

### 9.4. Tech stack đề xuất

| Lớp | MVP (Pha 1–2) | Bổ sung Pha 3 | Ghi chú chọn lựa |
|---|---|---|---|
| Ngôn ngữ | Python 3.11 | + C++ nếu cần tối ưu | Đủ nhanh nếu vector hóa bằng numpy |
| Sim core | numpy + shapely (collision) | Gazebo Harmonic + ROS2 Jazzy | shapely lo hình học 2D, khỏi tự viết |
| Planning | Tự cài A*, RRT*, DWA | Nav2 plugins | **Tự cài là chủ ý** — để hiểu và để chuẩn hóa cách đo, không dùng thư viện hộp đen |
| RL (tùy chọn) | — | PyTorch + Gymnasium wrapper + SB3 | Bọc chính SimBackend thành `gym.Env` |
| API | FastAPI + Pydantic v2 | — | Pydantic dùng luôn làm schema cho Scenario Spec |
| Job queue | Celery/RQ + Redis | Ray | MVP có thể chạy đồng bộ trước, thêm queue sau |
| Frontend | Next.js + React + **Canvas 2D** | WebGL (deck.gl) khi >10k điểm | Canvas 2D đủ và đơn giản hơn nhiều cho MVP |
| Tracking | MLflow | + DVC cho dữ liệu bản đồ | MLflow lo params/metrics/artifacts |
| DB | PostgreSQL | TimescaleDB nếu trace lớn | |
| Storage | Local FS / MinIO | S3 | Trace nén Parquet, không JSON |
| Đóng gói | Docker Compose | Kubernetes (nếu thật sự cần) | Không over-engineer |
| CI | GitHub Actions | + nightly regression benchmark | |

### 9.5. Ghi chú về "2.5D"

> **Giải thích:** 2D là bản đồ mặt phẳng — mỗi ô chỉ có 2 trạng thái: đi được / không đi được. 3D là mô phỏng khối đầy đủ. **2.5D nằm giữa:** vẫn là lưới phẳng, nhưng mỗi ô mang thêm một giá trị — thường là **độ cao** hoặc **chi phí di chuyển**.
>
> **Ví dụ:** Robot đi trong kho. Ô A là sàn phẳng (cost 1). Ô B là tấm thảm dày (cost 3 — đi được nhưng chậm và hao pin). Ô C là bậc thềm cao 8 cm (cost ∞ với robot bánh nhỏ, nhưng cost 5 với robot bánh xích). Bản đồ 2D thuần không diễn tả được sự khác biệt này; 2.5D thì được, mà không phải trả giá tính toán của 3D.

**Khuyến nghị:** MVP làm 2D thuần, nhưng **thiết kế costmap dạng nhiều lớp (multi-layer)** ngay từ đầu — giống `nav2_costmap_2d`: lớp static, lớp obstacle, lớp inflation. Khi cần 2.5D chỉ việc thêm một lớp `elevation`. Đây là ví dụ nữa của nguyên tắc "MVP là tập con của full".

---

## 10. Roadmap sơ bộ — 6 tuần, nhóm 3 người

Giả định phân vai: **Dev A** (sim core + planning), **Dev B** (backend/API + orchestrator + MLflow), **Dev C** (frontend + visualization). Ai cũng viết test cho phần mình.

| Tuần | Mục tiêu | Giao thức nhúng vào | Đầu ra kiểm chứng được |
|---|---|---|---|
| **0.5** | **Chốt hợp đồng** — 4 interface, Scenario Spec schema, định nghĩa từng metric bằng công thức | **P02** (trường `observation_class`), **P05** (trường `split: dev/holdout`) phải có mặt trong schema ngay | `CONTRACTS.md` + skeleton code, cả nhóm review và ký |
| **1** | Sim core 2D chạy được; A* hoạt động; ghi trace | — | CLI chạy 1 scenario, xuất file trace |
| **2** | DWA + RRT*; Metrics Engine đủ 5 nhóm; MLflow log | **P04** (seed protocol + bootstrap CI trong Metrics Engine) | Chạy 3 thuật toán trên 1 map, ra bảng số **kèm CI** |
| **3** | FastAPI + RBAC 2 vai trò; Batch Runner; PostgreSQL | **P02** hiển thị nhóm theo lớp quan sát | Submit job qua API, xem kết quả qua API |
| **4** | Frontend: Trajectory Viewer + Leaderboard + Approval UI; Docker Compose | — | **🎯 MVP demo được đầu-cuối** |
| **5** | Chướng ngại động; Scenario Pack; chạy song song; **hiệu chuẩn độ khó** | **P03** (chạy baseline tham chiếu để gán difficulty cho từng kịch bản), **P01** (Optuna 30 trial/planner) | Benchmark 4 thuật toán × 5 kịch bản × 30 seed; bộ kịch bản đã có nhãn độ khó đo được |
| **6** | Chạy tập held-out; báo cáo so sánh + kiểm định; tài liệu; đệm rủi ro | **P05** (chạy holdout đúng một lần), **P04** (Wilcoxon + rank score) | Báo cáo cuối có **đường cong theo độ khó** + **generalization gap** + video demo |

**Điểm kiểm soát quan trọng:** cuối tuần 4 phải có demo chạy được đầu-cuối, dù thô. Nếu đến tuần 4 vẫn đang "hoàn thiện sim core", cắt phạm vi ngay (bỏ RRT*, bỏ Approval UI xuống dạng đơn giản nhất) thay vì kéo dài.

**Thứ tự cắt phạm vi khi thiếu thời gian** (cắt từ dưới lên): F22 LLM report → F17 regression guard → RRT* → P01 (ngân sách tinh chỉnh) → P03 (hiệu chuẩn độ khó). **Không bao giờ cắt P02 và P04** — chúng gần như miễn phí và là toàn bộ lý do dự án này khác với ba nền tảng ở mục 0.

**Tuần 0.5 nghe có vẻ phí, nhưng đây là tuần quan trọng nhất.** Nhóm 3 người mà không chốt interface trước sẽ mất cả tuần 3 để ghép code. Và chính tuần này là thứ quyết định bạn có phải "đập đi xây lại" ở pha 3 hay không.

---

## 11. Rủi ro & cách giảm thiểu

| Rủi ro | Xác suất | Tác động | Giảm thiểu |
|---|---|---|---|
| Sa đà vào sim core, hết thời gian cho benchmark | Cao | Cao | Timebox sim core 5 ngày; ưu tiên "chạy được" hơn "chính xác" |
| So sánh vẫn không công bằng vì tham số mỗi thuật toán chưa được tinh chỉnh tương đương | **Cao** | **Cao** | ✅ **Đã có giải pháp thiết kế:** P01 (ngân sách Optuna bằng nhau) + P02 (khai báo lớp quan sát). Nếu tuần 5 không kịp chạy P01, vẫn phải nêu rõ giới hạn này trong báo cáo — đây chính là lỗi mà Alyassi et al. mắc phải |
| Bị đánh giá là "làm lại PathBench / Arena" | **Cao** | **Cao** | Mục 0 đưa vào báo cáo và slide mở đầu; mọi tuyên bố đóng góp bám vào P01–P05, không bám vào số lượng thuật toán hay độ chân thực mô phỏng |
| Cố đua tính năng với Arena 4.0 → phình phạm vi | Trung bình | Cao | Mục 0.7 là ranh giới cứng; mọi đề xuất tính năng phải trả lời được "cái này đánh vào lỗ hổng nào trong mục 0?" |
| Ôm ROS2 quá sớm → kẹt setup | Trung bình | Cao | Đã xử lý bằng kiến trúc `SimBackend`; ROS2 để pha 3 |
| Nhóm ghép code không khớp | Trung bình | Cao | Tuần 0.5 chốt interface + CI chạy test từ ngày đầu |
| Benchmark chạy quá lâu | Trung bình | Trung bình | Headless, vectorize numpy, cache costmap, song song theo core |
| Phình phạm vi vì "thêm RL cho ngầu" | Cao | Trung bình | RL nằm ở Could-have; chỉ làm khi MVP đã xong hoàn toàn |

---

## 12. Giả định & câu hỏi mở cần chốt với giảng viên/khách hàng

**Giả định đang dùng:**
1. Robot mục tiêu là AMR trong nhà, differential drive, có LiDAR 2D.
2. Bản đồ đã biết trước (không cần SLAM); định vị coi như hoàn hảo ở MVP.
3. Single-robot, không có phối hợp đội hình.
4. "Doanh nghiệp" là công ty tích hợp robot có 5–20 kỹ sư.

**Câu hỏi cần làm rõ:**
- **Giảng viên đánh giá theo tiêu chí nào: tính mới học thuật hay năng lực kỹ thuật + tư duy sản phẩm?** Nếu là vế đầu, cần đẩy P01/P03 lên thành đóng góp chính và viết kèm một báo cáo dạng paper ngắn. Nếu là vế sau, giữ nguyên trọng số hiện tại.
- Có được phép **dùng lại mã nguồn mở của PathBench hoặc Arena** làm nền, thay vì tự viết sim core? Điều này giải phóng 1–1,5 tuần để dồn vào P01–P05 — nhưng đánh đổi bằng chi phí học và ràng buộc kiến trúc của họ.
- Bộ chỉ số có cần khớp với một chuẩn cụ thể nào (BARN Challenge, Nav2 benchmark) để đối chiếu với kết quả công bố không?
- Quy mô bản đồ mục tiêu tối đa là bao nhiêu (100×100 hay 2000×2000 ô)? Ảnh hưởng trực tiếp tới lựa chọn cấu trúc dữ liệu.
- "≥2 vai trò" có bắt buộc kèm xác thực thật (JWT, hash mật khẩu) hay chỉ cần phân quyền ở tầng logic?
- Có yêu cầu deploy lên môi trường public không, hay demo local là đủ?

---

## Phụ lục: Bảng thuật ngữ

| Thuật ngữ | Giải thích ngắn kèm ví dụ |
|---|---|
| **A\*** | Thuật toán tìm đường trên lưới, luôn cho đường ngắn nhất. Như tìm đường trên bàn cờ, có "linh cảm" hướng về đích để đỡ phải dò khắp nơi. Nhanh, tối ưu, nhưng chỉ hoạt động trên bản đồ tĩnh đã biết. |
| **RRT\*** | Gieo ngẫu nhiên các điểm rồi nối dần thành cây đường đi, càng chạy lâu càng tối ưu. Giống người mò đường trong bóng tối bằng cách quăng dây thăm dò tứ phía. Mạnh ở không gian nhiều chiều và khe hẹp, nhưng kết quả thay đổi theo lần chạy. |
| **DWA** (Dynamic Window Approach) | Thuật toán **cục bộ**: mỗi vòng điều khiển, thử vài chục cặp (vận tốc, góc quay) khả thi trong 1 giây tới, mô phỏng nhanh xem cái nào an toàn và tiến gần đích nhất, rồi chọn. Như người lái xe liên tục ước lượng "rẽ thế này có kịp tránh không". Xử lý được vật cản động, nhưng dễ kẹt ở ngõ cụt vì chỉ nhìn gần. |
| **Global vs Local planner** | Global = bản đồ Google Maps vẽ lộ trình tổng thể từ nhà tới công ty. Local = phản xạ của bạn khi có xe máy tạt đầu. Hệ điều hướng thật cần cả hai. |
| **Closed-loop** | Vòng kín: robot ra lệnh → cảm biến đọc kết quả thật → điều chỉnh lệnh tiếp theo. Ngược lại open-loop chỉ vẽ ra đường rồi giả định robot đi đúng y hệt — thực tế không bao giờ vậy (trượt bánh, sai số cơ khí). |
| **Human-in-the-loop** | Bắt buộc có con người xét duyệt tại một điểm trong quy trình tự động. Ở đây: máy chạy benchmark và xếp hạng, nhưng máy **không** được tự quyết định thuật toán nào lên robot. |
| **Costmap** | Bản đồ mà mỗi ô mang một "giá" thay vì chỉ đi được/không đi được. Sát tường thì giá cao (đi được nhưng không nên), giữa lối đi thì giá thấp. Nhờ vậy robot tự nhiên đi giữa hành lang thay vì cà sát mép. |
| **Seed** | Con số khởi tạo bộ sinh số ngẫu nhiên. Cùng seed → cùng chuỗi ngẫu nhiên → cùng kết quả. Đây là chìa khóa để RRT* (vốn ngẫu nhiên) vẫn tái lập được. |
| **Reproducibility** | Khả năng dựng lại y hệt kết quả cũ. Cần lưu đủ: seed, tham số, phiên bản code, môi trường chạy. |
| **Held-out set** | Tập kịch bản được giấu đi, chỉ chạy đúng một lần ở cuối. Giống đề thi thật so với đề ôn: nếu ôn và thi cùng một đề thì điểm số không nói lên năng lực. |
| **Generalization gap** | Hiệu số hiệu năng giữa tập dev và tập held-out. Gap lớn = thuật toán (hoặc bộ tham số) đã bị điều chỉnh quá khớp với chính bộ benchmark, sẽ hụt khi gặp môi trường thật. |
| **Bootstrap CI** | Cách ước lượng khoảng tin cậy bằng cách lấy mẫu có hoàn lại từ chính dữ liệu đã đo, hàng nghìn lần. Không cần giả định phân phối chuẩn — phù hợp với dữ liệu robot vốn lệch mạnh. |
| **Effect size** | Độ lớn của chênh lệch, tách biệt với việc nó có ý nghĩa thống kê hay không. Với 10.000 mẫu, một chênh lệch 0,1% cũng có thể "có ý nghĩa" mà chẳng có giá trị thực tiễn nào. |
| **Observation class** | Lớp thông tin mà một planner được phép nhìn thấy (bản đồ đầy đủ / vị trí người / chỉ LiDAR). Dùng để đảm bảo các planner được so sánh cùng điều kiện thông tin. |

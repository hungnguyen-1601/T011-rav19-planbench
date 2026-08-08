# Planner Selector — Chọn cấu hình điều hướng tối ưu cho một deployment cụ thể

> **Trạng thái:** bản viết lại đề tài (thay thế mục 1–8 của `phan-tich-de-bai-benchmark-planning.md`).
> **Bối cảnh không đổi:** nhóm 3–4 người, 4–6 tuần, MVP trước, kiến trúc mở đường lên ROS2/Nav2.
> **Ba quyết định đã chốt:** ① đầu ra là **một khuyến nghị duy nhất**, chấm bằng điểm tổng hợp có trọng số; ② "chi phí" gồm **cả ba loại** (tính toán, vận hành, kỹ thuật) gộp thành một hàm; ③ một "task" là **một instance cụ thể** — 1 bản đồ + 1 cặp start/goal, có đường mở rộng lên cấp triển khai.
> **Nguyên tắc xuyên suốt:** hệ thống luôn đưa đúng một khuyến nghị, nhưng không bao giờ được để bằng chứng nghe mạnh hơn dữ liệu thực tế cho phép.

---

## 0. Bản đồ thay đổi so với tài liệu cũ

Đọc mục này trước để biết cái gì bỏ, cái gì giữ, cái gì đổi vai. **Không có gì trong tài liệu cũ bị vứt đi — nhưng gần một nửa đổi vai trò.**

| Thành phần cũ | Số phận | Lý do |
|---|---|---|
| Mục 0 — Prior art (PathBench, Arena 4.0, Alyassi) | **Giữ nguyên** | Vẫn cần để phòng thủ "làm lại của người ta". Chỉ đổi câu định vị ở 0.6 |
| Câu định vị 0.6 | **Viết lại** | Từ *"chúng ta xây tầng giao thức đánh giá"* → *"chúng ta xây tầng **ra quyết định**, đứng trên nền giao thức đánh giá"* |
| Mục 2 — Bài toán nghiệp vụ | **Viết lại** (mục 1–2 dưới đây) | Câu hỏi nghiệp vụ đã đổi |
| Mục 3 — Pain point P1–P9 | **Xuống nền móng** | Vẫn đúng, nhưng không còn là điểm bán. Pain point mới N1–N10 ở mục 3 |
| Mục 5 — Core value | **Viết lại** | Từ "sân chơi công bằng" → "khuyến nghị dám chịu trách nhiệm" |
| **P01** cân bằng ngân sách tinh chỉnh | **Đổi vai → thành chi phí đo được** | Không còn là quy tắc fairness. Công tinh chỉnh là tiền thật, đo bằng số trial đã dùng và wall-clock. Đường cong bão hòa (`trials_to_90`) lùi xuống pha 2 vì muốn đo nó phải chạy tới bão hòa |
| **P02** cân bằng thông tin đầu vào | **Đổi vai → thành ràng buộc tương thích (G6)** | Candidate khai *cần gì*, deployment khai *có gì*. Thiếu ⇒ loại. Tiền chỉ tính khi người dùng khai giá nâng cấp — không tự quy thành tiền |
| **P03** hiệu chuẩn độ khó | **Thu hẹp** | Không cần đường cong độ khó nữa. Giữ **một con số độ khó của instance** để chọn số episode và cảnh báo người dùng |
| **P04** quy trình thống kê | **Giữ, siết chặt** | Bỏ so CI chồng lấn, thay bằng **bootstrap ghép cặp trên hiệu utility** — xem N8 |
| **P05** tập held-out | **Thay bằng Task Neighborhood** | Held-out mất nghĩa khi phạm vi là một deployment. Thay bằng kiểm tra độ bền của *khuyến nghị* trước sai số dữ liệu đầu vào — xem N5 |
| Mục 8 — Metrics 8.1–8.5 | **Giữ làm nguyên liệu, gom thành 4 objective** | Mỗi metric chỉ được có **đúng một vai** để tránh tính hai lần — xem mục 5 |
| Mục 9 — Kiến trúc, 4 interface | **Giữ nguyên, thêm 4 tầng phía sau Metrics Engine** | Xem mục 8 |
| F10/F11 — RBAC + Approval | **Giữ nguyên, không hạ ưu tiên** | Đề bài yêu cầu ≥2 vai trò, và đây là chốt an toàn cuối của một hệ thống dám khuyến nghị |

---

## 1. Phát biểu bài toán mới

### 1.1. Một câu

> **Cho một deployment profile (môi trường, nhiệm vụ, robot, phần cứng, ràng buộc vận hành) và một tập candidate mà project đang có, hãy chỉ ra candidate nào đáng dùng nhất trong số các candidate *khả thi* — cân bằng độ tin cậy, an toàn, hiệu quả di chuyển và chi phí theo ưu tiên người dùng khai báo — đồng thời định lượng xem chính khuyến nghị đó đáng tin đến đâu.**

Ký hiệu hình thức:

```
c* = argmax  U(c | T, H, P)
     c ∈ C_feasible
```

- `c` — candidate = (thuật toán, bộ tham số, version, yêu cầu quan sát)
- `T` — task/deployment profile · `H` — ràng buộc phần cứng · `P` — preference profile
- `U` — **Decision Utility**, không phải "chất lượng nội tại của thuật toán"

Hệ quả phải nói rõ trong báo cáo: **cùng một candidate có thể được khuyến nghị cho kho A và bị bác cho bệnh viện B.** Đó không phải mâu thuẫn, đó là đúng bản chất bài toán.

### 1.2. Hai phạm vi tuyên bố

Quyết định "task = 1 instance" được giữ nguyên làm mặc định, nhưng hệ thống phải **tự hạ hoặc nâng phạm vi tuyên bố** theo lượng dữ liệu người dùng đưa vào.

| Mức | Đầu vào | Tuyên bố được phép | Chi phí chạy |
|---|---|---|---|
| **L1 — Mission-level** (MVP, mặc định) | 1 bản đồ + 1 cặp start/goal | *"Cho tuyến Dock A → Kệ 12, dùng C2."* | 1× |
| **L2 — Deployment-level** (pha 2) | + phân bố nhiệm vụ có xác suất | *"Cho vận hành hiện tại của kho A, dùng C2."* | ~M× (M = số mission mẫu) |
| **L3 — Robust deployment** (pha 2) | + Task Neighborhood | *"C2 vẫn là lựa chọn trên phần lớn biến thể hợp lý quanh deployment này."* | ~M×K× |

Mức đạt được **in ngay trên đầu Decision Card** (`Scope: ROBUST DEPLOYMENT-LEVEL`). Người dùng thấy ngay mình đang đứng ở đâu và cần thêm dữ liệu gì để lên mức cao hơn.

```yaml
task:
  environment: warehouse_A
  mode: deployment_level          # hoặc mission_level
  missions:
    - {start_zone: receiving, goal_zone: shelf_A, probability: 0.40}
    - {start_zone: receiving, goal_zone: shelf_B, probability: 0.35}
    - {start_zone: shelf_A,   goal_zone: packing, probability: 0.25}
```

Về code, chế độ hai chỉ thêm một `MissionSampler`; toàn bộ phần sau (metrics, gate, objective, utility) không đổi một dòng — đây là lý do nó rẻ.

> **Vì sao vẫn giữ chế độ hẹp:** ở giai đoạn tiền bán hàng, khách hàng đưa được bản đồ nhưng thường **chưa có** thống kê tuyến. Ép nhập mission distribution là ép bịa số. Cho phép chế độ hẹp, nhưng bắt hệ thống hạ phạm vi tuyên bố xuống theo.

### 1.3. Hợp đồng đầu vào / đầu ra

```
ĐẦU VÀO
  ├── Task Profile:   map + mission(s) + robot spec
  ├── Hardware spec:  RAM khả dụng, tần số vòng điều khiển, cảm biến CÓ SẴN
  ├── Constraints:    success_rate_min, mức rủi ro va chạm chấp nhận, deadline, throughput
  ├── Candidates:     (thuật toán, tham số, version, yêu cầu quan sát)
  └── Preference:     profile trọng số + hệ số chi phí + deployment horizon

ĐẦU RA — Decision Card
  ├── 🏆 Khuyến nghị:      candidate_id + bộ tham số
  ├── Nhãn:                CLEAR | NEAR-EQUIVALENT
  ├── Phương án thay thế:  candidate gần tương đương (nếu có)
  ├── Bằng chứng thống kê: ΔU ghép cặp so với hạng nhì + CI 95%
  ├── Bảng cổng:           ai bị loại ở cổng nào, kèm số lần chạy
  ├── Biên ổn định trọng số + biên ổn định anchor
  ├── Robustness:          % biến thể neighborhood mà khuyến nghị không đổi
  └── Manifest:            seed, params_hash, anchor_config_version, git_sha, docker_image
```

### 1.4. Đơn vị đánh giá: candidate là một cấu hình điều hướng hoàn chỉnh

**Không được xếp A\*, RRT\* và DWA ngang hàng trên cùng một bảng.** A\* và RRT\* là *global planner*, DWA là *local planner/controller* — chúng giải hai bài toán khác nhau và không thay thế nhau được. Xếp chung rồi tuyên bố "DWA thắng A\*" là một sai lầm phương pháp mà hội đồng sẽ bắt ngay.

```
candidate = global planner + local planner/controller + bộ tham số + code version
          + observation_requirements

C1 = A*    + DWA(config_A)
C2 = RRT*  + DWA(config_A)
C3 = A*    + DWA(config_B)
```

Hai biến thể hợp lệ khác của hợp đồng candidate:

- **Monolithic policy** (RL end-to-end): không có tách global/local. Khai `global_planner: null`, `policy: <checkpoint_id>`. Vẫn là một candidate hợp lệ, vẫn đi qua đúng sáu cổng.
- **Nghiên cứu một tầng duy nhất**: nếu chỉ muốn so A\* / Dijkstra / RRT\* thì phải **giữ local planner cố định và tuyên bố rõ phạm vi** — *"Scope = Global Planner Selection, local planner cố định DWA(config_A)"*. Trường này in ngay trên Decision Card.

`candidate_id = hash(global_planner + local_planner + params + code_version + observation_requirements)`

### 1.5. Vì sao câu hỏi này Google không trả lời được

Đây là điểm phải nói ngay trong slide đầu.

- **Câu hỏi cũ:** "A\* khác RRT\* thế nào?" → Google trả lời được. Đó là kiến thức sách vở, không phụ thuộc dữ liệu, và câu trả lời vô dụng cho việc triển khai.
- **Câu hỏi mới:** "Với bản đồ kho của khách hàng X, robot rộng 0,52 m, khe kệ hẹp nhất 0,68 m, chạy trên Jetson Orin Nano 2 GB ở 20 Hz, 200 nhiệm vụ/ngày trong 250 ngày — dùng candidate nào?" → **không tồn tại câu trả lời sẵn**, vì nó phụ thuộc vào tỷ số 0,52/0,68, vào ngân sách 50 ms mỗi vòng lặp, vào việc 3 ngày công tinh chỉnh có được hoàn vốn qua 6 giây tiết kiệm mỗi nhiệm vụ hay không.

> **Ví dụ dễ hình dung:** hỏi "xe điện hay xe xăng tốt hơn?" thì báo chí trả lời được, và câu trả lời vô dụng. Hỏi "tôi đi 18 km/ngày, có sạc ở nhà, giữ xe 4 năm — nên mua xe nào?" thì phải tính, và câu trả lời mới dùng được. Đề tài mới chuyển từ câu hỏi thứ nhất sang câu hỏi thứ hai.

---

## 2. Điều gì đổi trong nghiệp vụ

Kịch bản cũ (4 kỹ sư cãi nhau trong phòng họp) vẫn đúng, nhưng **vai của sản phẩm đổi hẳn**:

| | Đề bài cũ | Đề bài mới |
|---|---|---|
| Sản phẩm là gì | Cái cân | Người ra quyết định có cân trong tay |
| Đầu ra | Bảng số + biểu đồ | **Một cái tên + bộ tham số + bằng chứng + biên sai số của chính kết luận** |
| Ai đọc | Kỹ sư | Kỹ sư trưởng, PM, khách hàng |
| Sai thì sao | Bảng số sai, kỹ sư tự nhận ra | **Robot chạy sai ngoài hiện trường** |
| Rủi ro chính | Không ai dùng vì nhàm | **Bị tin quá mức** |

Dòng cuối là dòng quan trọng nhất, và nó sinh ra gần như toàn bộ pain point ở mục 3. Một hệ thống in ra bảng số thì người đọc tự biết phải hoài nghi. Một hệ thống in ra chữ **"Dùng DWA"** thì người đọc sẽ tin — kể cả khi nó thắng 51/49 nhờ may mắn của một seed.

---

## 3. Pain point riêng của bài toán tuyển chọn

Mười điểm đau dưới đây **không phải điểm đau của bài toán so sánh**. Chúng chỉ xuất hiện khi hệ thống dám nêu tên một người thắng.

### N1 — Trọng số quyết định người thắng, nhưng không ai biết trọng số của mình

Hỏi một kỹ sư "an toàn quan trọng gấp mấy lần thời gian di chuyển?" thì câu trả lời sẽ là một con số bịa ra trong 5 giây. Nhưng chính con số bịa đó quyết định ai thắng. Đây là lỗ hổng lớn nhất của mọi hệ thống chấm điểm tổng hợp.

**Giải pháp — 3 lớp:**
1. **Không bắt nhập số.** Cho chọn **profile** dựng sẵn: `kho_ban_dem`, `benh_vien_gio_cao_diem`, `pilot_demo`, `measured_only`. Mỗi profile là một vector trọng số công khai, sửa được.
2. **Biên ổn định trọng số (weight stability margin)** — tính năng quan trọng nhất của cả dự án. Thay vì hỏi "trọng số của bạn là bao nhiêu", hệ trả lời: *"Candidate A thắng. Để B lật ngược được A, trọng số an toàn phải giảm từ 0,40 xuống dưới 0,17 — tức bạn phải coi an toàn kém quan trọng hơn 2,4 lần so với hiện tại."* Nếu biên rộng, người dùng không cần biết trọng số chính xác của mình nữa.
3. **Lọc Pareto trước** (N10) — candidate bị lấn át bị loại **mà không cần dùng đến trọng số nào cả**, nên phần kết luận phụ thuộc trọng số bị thu nhỏ lại.

> **Ví dụ dễ hiểu:** bạn phân vân mua nhà A hay nhà B, không biết mình coi trọng "gần chỗ làm" bao nhiêu phần trăm. Thay vì ép bạn tự chấm, môi giới nói: *"Nhà A hơn, và nó chỉ thua nếu anh coi việc đi làm gần quan trọng gấp 3 lần diện tích — mà nghe anh nói thì không phải vậy."* Bạn ra quyết định được ngay mà không cần biết con số của mình.

### N2 — Cách chuẩn hóa đơn vị có thể tự nó lật ngược người thắng

Không thể cộng 42 mét với 18 ms với 7 triệu đồng. Phải chuẩn hóa về thang [0,1] trước. Nhưng cách chuẩn hóa quen thuộc nhất — min-max theo tập ứng viên — có một lỗi chết người: **thêm một ứng viên tệ vào có thể đổi thứ hạng của hai ứng viên đầu** (hiện tượng *rank reversal*).

> **Ví dụ số cụ thể:** hai ứng viên có latency 10 ms và 20 ms. Min-max cho ra 1,00 và 0,00 — chênh lệch tối đa. Giờ thêm ứng viên thứ ba, 200 ms. Min-max mới: 1,00 và 0,95 — hai ứng viên đầu bỗng gần như bằng nhau ở hạng mục này, và người thắng chung cuộc có thể đổi. **Hai ứng viên đầu không hề thay đổi một dòng code nào.**

**Giải pháp — chuẩn hóa theo mốc tuyệt đối ngoại sinh, không theo tập ứng viên:**

```
u(m) = clip( (m_bad − m) / (m_bad − m_good), 0, 1 )
```

| Metric | m_good (u=1) | m_bad (u=0) | Mốc lấy từ đâu |
|---|---|---|---|
| Path efficiency `L_ref/L` | 1,00 | 0,65 | Vật lý bài toán (Dijkstra trên grid) |
| Time efficiency `T_ideal/T` | 1,00 | 0,35 | Giới hạn động học |
| p99 control latency | `0,2 × T_cycle` | `1,0 × T_cycle` | Chu kỳ điều khiển người dùng nhập |
| Min clearance | `2,0 × bán kính robot` | `1,05 × bán kính robot` | Hình học robot |
| Near-miss rate | 0 | 0,5 lần/mét | Ngưỡng cảnh báo khai báo |
| Success rate | 1,00 | **= `success_rate_min`** (ngưỡng cổng G3) | Ràng buộc vận hành, không phải hằng số |

**Anchor của một metric có cổng phải neo vào chính ngưỡng cổng đó, không phải một hằng số trong file anchor.** Nếu `metric_anchors.yaml` ghi cứng `success_rate.bad = 0,90` trong khi khách hàng khai `success_rate_min = 0,95`, thì nguyên tắc "điểm chấm trên phần dôi" (N4) bị phá: candidate đạt 0,96 được chấm như vượt ngưỡng 0,90 chứ không phải vượt ngưỡng thật của họ. File anchor và ràng buộc deployment sẽ trôi khỏi nhau mà không ai thấy. Quy định: với `success_rate`, `p99_latency`, `peak_RAM` và mọi metric có cổng, trường `bad` **phải** là tham chiếu `${constraints.<tên>}`, không được là số.

**Anchor cũng là một giả định, nên phải được đối xử như giả định:**
- File `metric_anchors.yaml` có trường `version`, và `anchor_config_version` **bắt buộc nằm trong manifest** — nếu không, khuyến nghị không tái lập được.
- Chạy **kiểm tra độ nhạy anchor**: xê dịch mọi anchor ±10%, xem khuyến nghị có đổi không. Đổi quá dễ ⇒ dán nhãn cảnh báo lên Decision Card.

**Lợi ích kép:** thêm hay bớt ứng viên không đổi điểm của ai, và điểm số trở nên **có nghĩa vật lý** — u = 0,7 ở clearance nghĩa là "cách vật cản bằng 1,7 lần bán kính robot", chứ không phải "tốt thứ nhì trong nhóm này".

### N3 — Trộn chi phí một lần với chi phí lặp lại là sai về bản chất

Bạn chọn gộp cả ba loại chi phí. Nhưng chúng khác nhau về **bản chất thời gian**:

- Tinh chỉnh tham số: 3 người-ngày, **trả một lần**.
- Latency vòng điều khiển: 18 ms, **trả 20 lần mỗi giây, suốt vòng đời robot**.
- Thời gian di chuyển: 94 giây, **trả mỗi nhiệm vụ**.

Cộng thẳng ba con số này vào một tổng có trọng số là lỗi mô hình hóa, không phải lỗi chọn trọng số.

**Giải pháp — quy tất cả về chi phí trên một nhiệm vụ, theo chân trời triển khai khai báo trước:**

```yaml
deployment_horizon:
  missions_per_day: 200
  operating_days:   250          # ⇒ N = 50.000 nhiệm vụ
```

```
C_per_mission = C_engineering / N          (một lần, khấu hao)
              + C_compute_per_mission       (lặp lại, đo được)
```

**Quy tắc khóa trước khi code — thời gian di chuyển được tính đúng MỘT lần.** Bản trước của tài liệu này còn một số hạng `C_operational_per_mission` trong công thức chi phí, trong khi `time_efficiency` đã nằm ở objective E. Đó là double-count ngay trong công thức, dù bảng metric ở mục 5 đã xếp đúng vai. Quy định:

```yaml
travel_time_accounting: efficiency        # efficiency | monetized_cost — chọn MỘT
```

- `efficiency` (mặc định, chế độ Technical): thời gian di chuyển chỉ vào `U_E`. `U_C` chỉ gồm chi phí tính toán và chi phí kỹ thuật.
- `monetized_cost` (chỉ ở chế độ Business-adjusted): thời gian di chuyển được **chuyển** thành throughput rồi thành tiền và **rời khỏi** `U_E` sang `U_C`. Decision Card phải in rõ đây là một phép quy đổi kinh doanh, không phải một phép đo mới.

Không bao giờ bật cả hai. Đại lượng vật lý xuất hiện ở đúng một objective.

**Tách rõ hai loại số liệu — đây là chỗ dễ bị chê "bịa số" nhất, nên phải phòng thủ ngay trong thiết kế:**

| Loại | Ví dụ | Trạng thái |
|---|---|---|
| **Measured** | CPU time, p99 latency, RAM, travel time, path length, số trial tinh chỉnh, wall-clock tinh chỉnh, GPU-hours | Đo trực tiếp từ trace. Luôn nằm trong core |
| **Declared** | giá điện, đơn giá giờ công, giá nâng cấp bo mạch, số robot trong đội | **Là một phần của preference profile** — người dùng khai, có mặc định, sửa được trên UI |

> **Vì sao xếp Declared vào preference chứ không vào "dữ liệu":** không ai đòi kiểm chứng ground truth cho một *vector trọng số*, vì nó là phát biểu về ưu tiên của người dùng chứ không phải về thế giới. Hệ số chi phí có đúng bản chất đó. Điều bị cấm là gọi nó là **"TCO thực tế"** — chữ đó mới là chỗ overclaim. Trong báo cáo gọi là *cost model có giả định khai báo*, và luôn hiện độ nhạy bên cạnh.
>
**Hai chế độ khuyến nghị, và Decision Card bắt buộc ghi rõ đang ở chế độ nào:**

| Chế độ | Dùng gì | Nhãn in trên Decision Card |
|---|---|---|
| **A — Technical** | chỉ số liệu Measured | *"Khuyến nghị kỹ thuật — chỉ dựa trên số liệu đo được"* |
| **B — Business-adjusted** | Measured + hệ số Declared | *"Khuyến nghị đã hiệu chỉnh theo giả định kinh doanh do người dùng khai"* |

> Profile `measured_only` (chế độ A) đặt trọng số chi phí kỹ thuật = 0 ⇒ người dùng không có số liệu kinh doanh vẫn nhận được khuyến nghị hợp lệ mà không phải bịa con số nào. Việc gắn nhãn là bắt buộc: một khuyến nghị chế độ B mà không nói rõ nó dựa trên giả định của ai thì đúng là loại overclaim cần tránh.

> **Vì sao chi tiết này là toàn bộ câu trả lời cho "cân bằng chính xác ↔ chi phí":**
> Cùng một cặp ứng viên, cùng một bộ trọng số, **hai chân trời khác nhau cho hai người thắng khác nhau.**
> — Triển khai chính thức (50.000 nhiệm vụ): 3 người-ngày tinh chỉnh ≈ 0,5 giây/nhiệm vụ. Không đáng kể. Ứng viên đã tinh chỉnh thắng.
> — Pilot demo cho khách (200 nhiệm vụ): 3 người-ngày ≈ 432 giây/nhiệm vụ. Áp đảo mọi thứ khác. Ứng viên chạy tham số mặc định thắng.
> Không hệ thống nào trong mục 0 của tài liệu cũ mô hình hóa điều này. Nó cũng chính là thứ phân biệt một dự án *kỹ thuật* với một dự án *sản phẩm* — và hội đồng gồm người triển khai thật sẽ nhận ra ngay.

### N4 — Có những thứ tuyệt đối không được đem ra đánh đổi

Điểm tổng hợp có trọng số có một khuyết tật nguy hiểm: **mọi thứ đều đổi được lấy mọi thứ**. Một ứng viên va chạm 1,7% số lần nhưng nhanh gấp 3 hoàn toàn có thể thắng điểm. Đó là kết quả không được phép xảy ra.

**Giải pháp — kiến trúc hai tầng: Feasibility Gate → Scoring.** Chỉ ai qua cổng mới được chấm điểm; qua cổng rồi thì mọi ứng viên đều "đủ dùng", và lúc đó việc đánh đổi mới hợp lệ.

> **Ví dụ dễ hiểu:** tuyển tài xế. Vòng lọc hồ sơ là nhị phân — không có bằng lái thì không thể bù bằng việc nói năng lưu loát. Qua được vòng đó rồi, giữa các ứng viên hợp lệ mới đem kinh nghiệm ra đổi lấy mức lương. Trộn hai vòng vào một bảng điểm là cách tuyển nhầm người.

**Sáu cổng bắt buộc, ngưỡng lấy từ deployment requirements chứ không hardcode:**

| ID | Cổng | Điều kiện | Nguồn ngưỡng |
|----|------|-----------|--------------|
| G1 | Tìm được đường | `no_path_rate ≤ ngưỡng` | Constraint |
| G2 | **An toàn quan sát được** | `collision_quan_sát = 0` **AND** `N_runs ≥ N_min` | Mức rủi ro chấp nhận (xem dưới) |
| G3 | Độ tin cậy | `success_rate ≥ success_rate_min` | Constraint |
| G4 | Thời gian thực | `p99(control_latency) ≤ T_cycle` | Hardware spec |
| G5 | Bộ nhớ | `peak_RAM ≤ RAM_khả_dụng` | Hardware spec |
| G6 | **Tương thích quan sát** | `observation_requirements` của candidate ⊆ `available_observations` của deployment, HOẶC người dùng cho phép bổ sung kèm chi phí | Hardware spec |

> **Vì sao G4 dùng p99 chứ không dùng trung bình:** robot chạy 20 Hz, mỗi bước có 50 ms. Trung bình 10 ms nhưng p99 = 200 ms nghĩa là cứ 100 bước lại có 1 bước robot đi mù trong 200 ms — đủ để đâm vào người. **Trung bình che giấu đúng cái rủi ro cần thấy.**

**Lỗ hổng ở G4 và G5 — đo trên máy benchmark, nhưng ngưỡng là của bo mạch đích.** Benchmark chạy trên laptop x86 3,5 GHz; robot chạy trên Jetson Orin Nano ARM 1,5 GHz. `p99 = 23 ms` đo trên laptop **không phải** `p99` trên Jetson.

Cách chữa **không phải** nhân với một hệ số quy đổi duy nhất: A\* là tìm kiếm đồ thị nặng về truy cập bộ nhớ, DWA là vòng lặp mô phỏng nặng về tính toán — hai loại tải này co giãn khác nhau giữa x86 và ARM (khác cache, khác băng thông bộ nhớ, khác tập lệnh vector). Một hệ số `2,8` dùng chung cho cả hai là con số bịa được gắn nhãn khoa học.

**Giải pháp — sàng lọc hai pha, mỗi pha có tư cách logic riêng:**

| Pha | Đo ở đâu | Tư cách logic | Hệ quả |
|---|---|---|---|
| **P1 — Sàng lọc** | máy benchmark | **điều kiện cần**: máy benchmark *nhanh hơn* bo mạch đích, nên `p99_host > T_cycle` ⇒ chắc chắn cũng trượt trên đích | Loại thẳng. Kết luận này đúng, không cần hệ số nào |
| **P2 — Xác nhận** | chạy trực tiếp trên bo mạch đích, chỉ **2–3 candidate lọt chung kết**, ~20 episode mỗi cái | **điều kiện đủ** | Gate cứng thật sự |

Đây là lý do phép sàng lọc pha 1 vẫn hợp lệ dù đo sai máy: nó chỉ dùng theo **một chiều duy nhất** — chiều loại bỏ. Không bao giờ dùng để kết luận "candidate này chạy được trên Jetson".

Trường trạng thái bắt buộc trên Decision Card:

```yaml
realtime_gate:
  status: verified_on_target | screened_on_host | unverified
  host_p99_ms: 23
  target_p99_ms: 61          # chỉ có khi status = verified_on_target
```

- `screened_on_host` ⇒ Decision Card in **"G4 mới qua vòng sàng lọc — chưa xác nhận trên bo mạch đích"**. Không được phát biểu candidate đạt thời gian thực.
- Chi phí của P2 rất nhỏ vì chỉ áp cho 2–3 candidate chung kết, mỗi cái ~20 episode — vài phút trên một con Jetson. **Đo thật rẻ hơn nhiều so với việc bảo vệ một hệ số quy đổi bịa.**
- `peak_RAM` ít phụ thuộc kiến trúc hơn nhiều so với tốc độ CPU, nên sàng lọc trên host là dự báo tương đối tốt — nhưng vẫn phải xác nhận ở P2 cùng lúc, vì cùng một lần chạy.
- Điều kiện tiên quyết chung: **mọi candidate chạy trên cùng một máy, cùng một Docker image, cùng mức cấp phát CPU và cùng số luồng** — nếu không thì cả phép so tương đối cũng vô nghĩa.

**Cách phát biểu G2 — chỗ dễ tự lừa mình nhất.** Quan sát 0 va chạm trong N lần chạy **không** chứng minh xác suất va chạm bằng 0. Theo **quy tắc số 3**, cận trên 95% của xác suất thật ≈ `3/N`:

| N lần chạy | 0 va chạm quan sát được ⇒ xác suất thật vẫn có thể tới |
|---|---|
| 30 | **10%** |
| 100 | 3% |
| 300 | **1%** |
| 3.000 | 0,1% |

Nghĩa là một cổng an toàn chạy 30 seed là **cổng an toàn giả**. Quy định:
- `N_min` **suy ngược từ mức rủi ro người dùng chấp nhận**: cần dưới 1% ⇒ phải có ≥ 300 lần chạy sạch.
- Decision Card in nguyên văn: **"0 va chạm quan sát trong 300 lần chạy; cận trên 95% dưới phân phối kịch bản đã mô phỏng: 1,0%"** — không bao giờ in chữ "an toàn", và **luôn kèm mệnh đề "dưới phân phối kịch bản đã mô phỏng"**. Cận trên này nói về simulator, không phải về nhà kho thật: nếu mô hình vật cản động của ta hiền hơn thực tế thì con số 1% cũng lạc quan theo.
- **Quy tắc số 3 giả định các lần chạy độc lập cùng phân phối, nên hai mục đích lấy mẫu phải tách hẳn ra:**

| Bộ mẫu | Cách sinh | Dùng để ước lượng |
|---|---|---|
| **Evaluation distribution** | lấy mẫu độc lập: mission × lần hiện thực vật cản × seed | success rate, bằng chứng va chạm, phân phối hiệu năng |
| **Task Neighborhood** | nhiễu có cấu trúc quanh profile gốc (N5) | **độ ổn định của khuyến nghị** — không phải xác suất va chạm |

  Trộn hai bộ này là lỗi: 300 lần chạy đến từ 20 biến thể × 15 seed thì bị **phân cụm theo biến thể**, số mẫu hiệu dụng nhỏ hơn 300 nhiều, và `3/300 = 1%` trở thành con số quá lạc quan. Quy tắc cứng: **cận trên va chạm chỉ được tính trên evaluation distribution**, không bao giờ tính trên tập neighborhood gộp lại.
- Chi phí thêm nhỏ ở MVP vì episode 2D chạy rất nhanh (xem tính toán ở N9); nó chỉ trở thành ràng buộc thật khi đổi sang backend chậm hoặc khi nhân với ngân sách tinh chỉnh.

**Nguyên tắc thống nhất cho cả sáu cổng — gate chấm trên ngưỡng, điểm chấm trên phần dôi:**

```
Gate:  metric có vượt ngưỡng deployment không?     (nhị phân)
Score: vượt ngưỡng đó BAO NHIÊU?                   (liên tục, qua anchor)
```

Anchor của latency ở N2 đã ngầm làm đúng việc này (`m_bad = T_cycle` chính là ngưỡng gate). Áp luật này cho cả sáu cổng thì không metric nào bị tính điểm hai lần.

### N5 — Khuyến nghị có thể mong manh trước sai số của chính dữ liệu đầu vào

Trên đúng một cặp start/goal, thứ hạng có thể lật khi dời đích 2 mét, hoặc khi một pallet bị đặt lệch 30 cm.

**Giải pháp — Task Neighborhood (vùng lân cận của task), thay thế vai trò của tập held-out cũ.**

Lưu ý phân biệt — hai thứ này hay bị nhầm là một:

| | Trả lời câu hỏi gì | Loại bất định |
|---|---|---|
| **Mission distribution** (§1.2) | "Trung bình trên những nhiệm vụ tôi sẽ thật sự chạy?" | Bất định về **khối lượng công việc** |
| **Task Neighborhood** | "Nếu bản đồ và mô hình cảm biến tôi đưa bị lệch chút thì sao?" | Bất định về **chính dữ liệu đầu vào** |

Có mission distribution hoàn hảo bạn vẫn cần neighborhood, vì bản đồ là một phép đo có sai số và pallet không nằm đúng chỗ trên bản vẽ.

Hệ tự sinh **K biến thể quanh profile gốc** (đề xuất K = 20):

| Trục nhiễu | Biên độ đề xuất | Mô phỏng rủi ro thật nào |
|---|---|---|
| Dịch start/goal | ±1,0 m, ±15° | Điểm giao/nhận hàng không cố định tuyệt đối |
| Dịch vật cản tĩnh | ±0,3 m, xoay ±10° | Pallet, kệ bị đặt lệch |
| Mật độ vật cản động | ±20%, tốc độ 0,8–1,4 m/s | Ca làm việc khác nhau |
| Nhiễu cảm biến & odometry | LiDAR σ = 2 cm, trượt bánh 2% | Sàn ướt, bánh mòn |
| `v_max` | ±10% | Robot tải nặng, pin yếu |

**Recommendation Robustness** `R = (số biến thể khuyến nghị không đổi) / K`. Dưới 60% ⇒ Decision Card đổi nhãn thành **"NEAR-EQUIVALENT — deployment này nhạy cảm, nên đo lại bản đồ thực địa trước khi chốt"**.

> **Đây là điểm khác biệt học thuật mạnh nhất của dự án.** Không nền tảng nào trong mục 0 của tài liệu cũ đo độ bền của *kết luận* trước nhiễu đầu vào; họ chỉ đo hiệu năng của *thuật toán* trước nhiễu môi trường. Hai thứ khác nhau: cái sau hỏi "robot có đi được không", cái trước hỏi "lời khuyên của tôi có còn đúng không".

### N6 — Yêu cầu quan sát là ràng buộc trước, là tiền sau

Một planner cần biết vị trí từng người thì không miễn phí — nhưng cũng **không mặc định là một khoản tiền cố định**, vì robot có thể đã sẵn camera và GPU cho perception. Cách đúng là khai báo hai chiều:

```yaml
candidate:
  observation_requirements: [lidar_2d, human_state_estimates]

deployment:
  available_observations:   [lidar_2d]
  allow_subsystem_addition: true
  subsystem_costs:
    human_state_estimates: {hardware: <người dùng khai>, integration_days: 15}
```

- Thiếu mà **không** cho phép bổ sung ⇒ **loại tại G6**. Kết thúc, không cần định giá gì.
- Thiếu nhưng **cho phép** bổ sung ⇒ vào chi phí kỹ thuật, dùng đúng con số người dùng khai, và Decision Card ghi rõ *"candidate này đòi thêm một hệ thống con"*.

Cách này đạt đúng mục tiêu mà P02 cũ nhắm tới — đặc quyền thông tin không còn miễn phí — nhưng **cái giá do người dùng định, không do hệ thống giả định**.

### N7 — Công tinh chỉnh là chi phí thật, nhưng phải đo bằng thứ đo được

Ở đề bài cũ, P01 (cấp cùng số trial Optuna cho mọi planner) tồn tại để so sánh cho công bằng. Ở đề bài mới nó đổi vai hoàn toàn: nếu một thuật toán cần 200 trial mới đạt phong độ trong khi thuật toán khác chỉ cần 10, thì thuật toán đầu **đắt hơn thật**, và cái đắt đó phải nằm trong hàm chi phí.

Nhưng metric `trials_to_90` (số trial để đạt 90% mức bão hòa) **không đo được ở MVP**: muốn biết mức bão hòa thì phải chạy tới bão hòa, tức đã trả xong đúng cái chi phí cần đo. Vòng luẩn quẩn.

| Pha | Đo gì |
|---|---|
| **MVP** | `tuning_trials_used`, `tuning_wall_clock_h`, `n_tunable_params`, `training_required`, `training_wall_clock_h` |
| **Pha 2** | đường cong hiệu năng theo ngân sách tinh chỉnh, `trials_to_90` |

Các số ở MVP đều **đo trực tiếp**, không giả định gì, và đã đủ trả lời câu nghiệp vụ quan trọng nhất: *"thuật toán này ngốn bao nhiêu công của đội tôi mỗi lần triển khai kho mới?"*

### N8 — Người dùng không phân biệt được "thắng có ý nghĩa" và "thắng do may"

Rủi ro lớn nhất của việc chọn phương án một khuyến nghị duy nhất. Nếu điểm của top-1 là 0,834 và top-2 là 0,829, in ra một cái tên là **nói dối bằng độ chính xác giả**.

**Giải pháp — bootstrap ghép cặp trên hiệu utility.** Vì các candidate chạy trên **cùng scenario, cùng seed, cùng lần hiện thực vật cản**, phần lớn phương sai là *chung*. So hai khoảng tin cậy rời rạc xem chúng có chồng lấn không sẽ vứt bỏ đúng lợi thế đó và cho kết luận quá bảo thủ — hai CI chồng nhau vẫn hoàn toàn có thể đi kèm một hiệu số ghép cặp khác 0 rõ rệt.

```
Bước 1 — Thiết kế ghép cặp:  mọi candidate chạy trên CÙNG episode
                              (cùng scenario + seed + obstacle realization)
Bước 2 — Tính hiệu:          ΔU_k = U_A(episode k) − U_B(episode k)
Bước 3 — Bootstrap 1000 lần TRÊN ΔU ⇒ CI 95% của chính hiệu số
Bước 4 — Kết luận:
           0 ∉ CI  ⇒ CLEAR RECOMMENDATION
           0 ∈ CI  ⇒ NEAR-EQUIVALENT
Bước 5 — Nếu NEAR-EQUIVALENT: vẫn trả về ĐÚNG MỘT khuyến nghị, phân định bằng
           thứ tự tiêu chí phụ khai báo trước, và HIỆN phương án thay thế:
           chi phí thấp hơn → phương sai thấp hơn → ít tham số hơn → đơn giản hơn
```

Báo cáo tối thiểu: **median, IQR, CI ghép cặp của ΔU, effect size, số episode.** Không báo cáo p-value trần trụi.

> Nói *"C2 và C1 chưa phân biệt được rõ; tôi chọn C2 vì rẻ hơn và ít tham số hơn"* là câu trả lời **mạnh hơn**, không yếu hơn, so với *"C2 thắng"*. Nó cho thấy hệ thống biết giới hạn của chính mình — và đó chính xác là thứ kỹ sư triển khai thật đánh giá cao nhất.

### N9 — Chi phí của chính việc chạy tuyển chọn

Nếu chọn thuật toán mất 6 tiếng benchmark trong khi họp tay mất 1 buổi, sẽ không ai dùng sản phẩm. Đây là bài toán "cân bằng chính xác ↔ chi phí" lặp lại ở **tầng meta**, và giải nó là phần AI/tối ưu hóa đáng khoe nhất của dự án.

**Giải pháp — Racing / Successive Halving (kiểu Hyperband):**

```
Vòng 1: tất cả candidate × 5 episode    → loại candidate có CI của ΔU nằm hoàn toàn dưới 0
Vòng 2: candidate còn lại × 25 episode  → loại tiếp
Vòng 3: 2–3 candidate cuối × N_min episode (từ G2) → chốt, kèm kiểm định
```

Ngân sách dồn vào chỗ còn tranh chấp, không rải đều cho ứng viên đã thua rõ.

**Nhưng phải trung thực về việc khi nào thứ này thật sự cần — làm phép tính trước khi làm tính năng:**

| Cấu hình | Số episode | Thời gian ở 1.000 episode/phút |
|---|---:|---|
| MVP: 4 candidate × 300 lần (L1) | 1.200 | ~1 phút |
| L3: 4 candidate × 300 × 20 biến thể × 3 mission | 72.000 | ~72 phút |
| L3 + Optuna 30 trial mỗi candidate | ~2.160.000 | **~36 giờ** |
| Backend ROS2/Gazebo (~thời gian thực, 60 s/episode) | 1.200 | **20 giờ** |

Kết luận: **ở quy mô MVP, racing không cần thiết** — 1.200 episode chạy trong khoảng một phút. Nó chỉ trở thành bắt buộc ở hai điều kiện, và cả hai đều thuộc pha 2 trở đi: (a) nhân với ngân sách tinh chỉnh Optuna, hoặc (b) đổi sang `SimBackend` chậm (Gazebo/ROS2). Vì vậy N9 nằm ở **pha 2, có điều kiện kích hoạt rõ ràng**, không phải hạng mục bắt buộc của MVP.

Ràng buộc an toàn khi hiện thực: **không được loại candidate quá sớm khi ước lượng còn quá nhiễu.** Chỉ loại ở vòng 1 khi CI của `ΔU` so với đương kim dẫn đầu nằm **hoàn toàn** dưới 0.

### N10 — Candidate bị lấn át vẫn có thể ngoi lên nhờ trọng số

Nếu A không tệ hơn B ở **mọi** objective và tốt hơn ở ít nhất một, thì B không đáng được khuyến nghị dưới **bất kỳ** bộ trọng số không âm nào. Chấm điểm B là lãng phí, và tệ hơn: nếu trọng số bị chỉnh lệch, B có thể ngoi lên.

**Giải pháp — phân tích Pareto trước khi tính Decision Utility, và *gắn nhãn* chứ không xóa:**

```
Gate → Pareto analysis (gắn nhãn) → Decision Utility → paired ΔU → sensitivity → recommendation
```

Ba nhãn, không candidate nào biến mất khỏi báo cáo:

| Nhãn | Nghĩa | Xử lý |
|---|---|---|
| `PARETO FRONTIER` | không bị ai lấn át | ứng viên chính, được xét làm "phương án gần tương đương" |
| `LIKELY DOMINATED` | có bằng chứng bị lấn át | vẫn chấm điểm, hiển thị mờ, không được đề xuất |
| `UNCERTAIN DOMINANCE` | dữ liệu chưa đủ để kết luận | vẫn chấm điểm bình thường, kèm cảnh báo thiếu mẫu |

**Cách xét lấn át — dùng non-inferiority, không dùng "CI không nằm hoàn toàn dưới 0".** Hai bản trước của tài liệu này đều sai ở đây, theo hai kiểu ngược nhau:

- *Sai kiểu 1 (bản đầu):* "A phải hơn B ≥ ε ở **mọi** objective". Quá chặt — chỉ cần A và B hòa ở đúng một objective (`ΔU = 0`) là quy tắc không kích hoạt, dù A hơn 0,10 ở tất cả chỗ còn lại. Bộ lọc gần như không bao giờ chạy.
- *Sai kiểu 2 (bản trước):* "với mọi j, `CI₉₅(ΔU_j)` không nằm hoàn toàn dưới 0". Quá lỏng, và sai về bản chất logic — nó lẫn lộn **không có bằng chứng A tệ hơn** với **có bằng chứng A không tệ hơn**. Với ít episode, `CI = [−0,30; +0,35]` vẫn thỏa điều kiện đó, trong khi A hoàn toàn có thể đang tệ hơn rất nhiều ở objective ấy. Càng ít dữ liệu thì càng dễ tuyên bố lấn át — đúng chiều sai nguy hiểm nhất.

Dạng đúng là kiểm định **không thua kém (non-inferiority)** trên cận dưới của khoảng tin cậy ghép cặp:

```
A lấn át B  ⟺  ∀j:  LCB₉₅(ΔU_j) ≥ −ε_j      (có BẰNG CHỨNG A không tệ hơn quá dung sai)
              ∧  ∃k:  LCB₉₅(ΔU_k) >  +ε_k      (và hơn hẳn ở ít nhất một chỗ)
```

với `ΔU_j = U_j(A) − U_j(B)` tính ghép cặp theo từng episode, `LCB` là cận dưới của CI 95% bootstrap.

> **Vì sao dạng này đạt đúng mục tiêu mà hai dạng kia trượt:** dữ liệu ít ⇒ CI rộng ⇒ `LCB` rất âm ⇒ **không** kết luận lấn át ⇒ candidate được giữ lại và gắn nhãn `UNCERTAIN DOMINANCE`. Nghĩa là thiếu dữ liệu tự động đẩy hệ thống về phía thận trọng, thay vì về phía loại bỏ. Đây chính là hành vi tôi muốn khi viết quy tắc có dung sai, nhưng hai lần trước đều đặt sai chỗ.

`ε` cố định (không dùng CI) chỉ giữ làm phương án dự phòng khi số episode quá ít để bootstrap có nghĩa — và khi đó mọi kết luận lấn át đều mang nhãn `UNCERTAIN`.

**Lợi ích phụ rất đẹp cho UI:** candidate mang nhãn `PARETO FRONTIER` nhưng thua điểm chính là "phương án gần tương đương" cần hiện ở Decision Card. Hai tính năng dùng chung một phép tính.

---

## 4. Bảng tổng hợp pain point → giải pháp → tính năng

| ID | Pain point | Giải pháp cốt lõi | Tính năng | Pha |
|----|-----------|-------------------|-----------|-----|
| N1 | Trọng số bịa quyết định người thắng | Profile dựng sẵn + **biên ổn định trọng số** | Sensitivity Panel + waterfall | 2 |
| N2 | Chuẩn hóa lật ngược thứ hạng | **Anchor tuyệt đối** + version hóa + độ nhạy anchor | Normalizer + `metric_anchors.yaml` | 1 |
| N3 | Trộn chi phí một lần & lặp lại | **Chi phí/nhiệm vụ theo horizon**; tách Measured / Declared | Cost Model + What-if Panel | 1 (measured) / 2 (declared) |
| N4 | Ràng buộc an toàn bị hòa tan vào trọng số | **6 cổng khả thi** + quy tắc số 3 + *gate trên ngưỡng, điểm trên phần dôi* | Feasibility Engine + Gate Report | 1 |
| N5 | Khuyến nghị mong manh trước sai số dữ liệu đầu vào | **Task Neighborhood, K = 20** | Perturbation Generator | 2 |
| N6 | Yêu cầu quan sát bị quy tiền vô căn cứ | **Ràng buộc tương thích hai chiều (G6)**, tiền do người dùng khai | Observation Compatibility Check | 1 |
| N7 | Công tinh chỉnh không được tính là chi phí | MVP đo trực tiếp; `trials_to_90` xuống pha 2 | Tuning Cost Recorder | 1 / 2 |
| N8 | Không phân biệt thắng thật / thắng may | **Bootstrap ghép cặp trên ΔU** + nhãn + phương án thay thế | Decision Card | 1 |
| N9 | Chạy tuyển chọn quá tốn (chỉ khi episode đắt) | **Racing / successive halving**, kích hoạt có điều kiện | Adaptive Scheduler | 2 |
| N10 | Candidate bị lấn át vẫn ngoi lên nhờ trọng số | **Phân tích Pareto gắn nhãn** + non-inferiority trên `LCB₉₅(ΔU)` | Pareto Analyzer | 1 |

---

## 5. Hệ chỉ số — ba tầng

Đây là phần dễ làm sai nhất. Hai nguyên tắc chi phối:

1. **Mỗi chỉ số phải trả lời được câu "nếu chỉ số này xấu đi thì ai chịu thiệt, thiệt cái gì".** Không trả lời được thì loại khỏi hệ.
2. **Mỗi chỉ số chỉ được giữ đúng một vai** — `Gate`, `Score` hoặc `Diagnostic`. Một chỉ số vừa làm cổng vừa được chấm điểm là bị tính hai lần; hai chỉ số đo cùng một đại lượng vật lý (quãng đường và thời gian di chuyển) mà cùng vào Score là nhân đôi trọng số của hạng mục đó.

### Tầng 0 — Cổng khả thi: nhị phân, không đánh đổi, không trọng số

Sáu cổng G1–G6 đã đặc tả ở N4. Nhắc lại điểm mấu chốt: **ngưỡng suy ra từ spec phần cứng và ràng buộc vận hành người dùng nhập**, không phải hằng số cứng trong code; và G2 luôn được phát biểu kèm số lần chạy cùng cận trên tin cậy.

### Tầng 1 — Bốn objective được chấm điểm

⚠️ **Ghi chú thuật ngữ quan trọng.** Trong lập quỹ đạo **không tồn tại khái niệm "accuracy"** như trong nhận dạng ảnh — không có nhãn đúng/sai để đối chiếu. Cái bạn gọi là "độ chính xác" được diễn giải thành **R + S + E**; "chi phí" là **C**. Nếu bạn hiểu khác, đây là chỗ cần chỉnh trước tiên vì nó quyết định toàn bộ bảng xếp hạng.

| Objective | Metric | Vai | Ghi chú |
|---|---|---|---|
| **R — Reliability** | `success_rate` | Gate G3 + Score **trên phần dôi** | Gate: ≥ ngưỡng. Score: anchor đặt `m_bad` = chính ngưỡng đó |
| | `failure_breakdown` (no_path / collision / timeout / stuck) | Diagnostic | 20% fail vì timeout khác hoàn toàn 20% fail vì đâm tường |
| **S — Safety** | `collision_observed` + `N_runs` | **Gate G2 duy nhất** | Không vào Score ⇒ không bị tính hai lần |
| | `near_miss_rate` | Score | Candidate 0 va chạm nhưng 50 near-miss là candidate **đang gặp may** |
| | `min_clearance`, `mean_clearance` | Score + evidence | Đường ngắn nhưng cà sát tường là đường tệ |
| **E — Efficiency** | `path_efficiency = L_ref / L` | Score | `L_ref` = Dijkstra trên grid |
| | `time_efficiency = T_ideal / T` | Score | `T_ideal = L_ref / v_max` |
| | `smoothness Σ(Δθ)²`, `jerk`, `stop_and_go` | Diagnostic (pha 2 mới vào Score) | Tương quan mạnh với E; vào Score sớm là tính hai lần |
| **C — Cost** | `p99_latency` | Gate G4 + Score trên phần dôi | |
| | `peak_RAM` | Gate G5 + Score trên phần dôi | **Hàm bậc thang**, không nội suy tuyến tính |
| | `cpu_time_per_mission` | Score | |
| | `tuning_trials_used`, `tuning_wall_clock_h`, `n_tunable_params` | Score (chi phí kỹ thuật, khấu hao theo horizon) | |
| | `observation_requirements` | Gate G6 + Score nếu người dùng khai chi phí bổ sung | |

`U_E = α·u(path_efficiency) + (1−α)·u(time_efficiency)`, mặc định α = 0,5.

> **Giải thích "smoothness" bằng ví dụ:** hai xe đi cùng quãng đường, cùng thời gian. Xe A đi đường cong đều, xe B đi zig-zag giật cục. Quãng đường như nhau, nhưng xe B làm bạn say xe, hao pin hơn, mòn bánh hơn. Smoothness là đại lượng phân biệt A với B. Nó **không** vào Score ở MVP vì nó tương quan mạnh với hiệu quả di chuyển vốn đã được chấm.

> **`peak_RAM` là hàm bậc thang, không phải biến liên tục.** Vượt 2 GB thì phải đổi Jetson Orin Nano lên Orin NX — chênh tiền thật × số robot trong đội. Cost Model phải mô hình hóa bước nhảy này. Đây là một trong ít chỗ mà chi phí khai báo có ground truth rất chắc (bảng giá công khai).

### Tầng 2 — Chỉ số về độ tin cậy của chính kết luận (không vào điểm, bắt buộc hiển thị)

| Metric | Định nghĩa | Dùng để |
|---|---|---|
| `paired_ΔU_CI` | CI 95% của hiệu utility ghép cặp so với hạng nhì | Nhãn CLEAR / NEAR-EQUIVALENT |
| `weight_stability_margin` | Trọng số phải đổi bao nhiêu để lật kết quả | Trả lời "tôi có cần biết trọng số của mình không" |
| `anchor_stability` | Xê dịch anchor ±10%, khuyến nghị có đổi không | Anchor cũng là giả định |
| `robustness_margin` | % biến thể neighborhood mà khuyến nghị không đổi | Độ bền trước sai số dữ liệu đầu vào |
| `collision_UCB` | `3 / N_runs` khi quan sát 0 va chạm | Biến "0 va chạm" thành phát biểu trung thực |
| `seed_IQR` mỗi metric | Khoảng tứ phân vị qua các episode | Phát hiện candidate "hên xui" (RRT\* hay dính) |
| `instance_difficulty` | `1 − success_rate(baseline tham chiếu)` | Cảnh báo người dùng + tự chọn số episode cần chạy |

---

## 6. Decision Utility và quy trình quyết định

### 6.1. Quy trình

```
Bước 1 — GATE:       loại candidate vi phạm G1–G6. Không chấm điểm.          [N4]
Bước 2 — OBJECTIVE:  gộp metric thành 4 giá trị U_R, U_S, U_E, U_C
                     chuẩn hóa bằng anchor tuyệt đối đã version hóa           [N2]
Bước 3 — PARETO:     loại candidate bị lấn át, có dung sai ε = 0,02           [N10]
Bước 4 — UTILITY:    U(c|T,H,P) = w_R·U_R + w_S·U_S + w_E·U_E + w_C·U_C, Σw = 1
Bước 5 — GHÉP CẶP:   bootstrap 1000 lần trên ΔU so với hạng nhì               [N8]
Bước 6 — NHÃN:       0 ∉ CI ⇒ CLEAR;  0 ∈ CI ⇒ NEAR-EQUIVALENT + tie-break
Bước 7 — ĐỘ NHẠY:    quét trọng số, quét anchor ±10%                          [N1, N2]
Bước 8 — ROBUSTNESS: chạy lại trên K biến thể neighborhood                    [N5]
```

**Gọi tên cho đúng:** đại lượng ở bước 4 là **Decision Utility `U(c | T, H, P)`**, không phải "điểm chất lượng của thuật toán". `U = 0,84` không có nghĩa "tốt 84%"; nó có nghĩa *"dưới task profile, phần cứng, anchor v1.2 và preference profile hiện tại, candidate này đạt utility 0,84"*.

**Bốn preference profile đề xuất** (công khai, sửa được):

| Profile | w_R tin cậy | w_S an toàn | w_E hiệu quả | w_C chi phí | Chi phí kỹ thuật |
|---|:---:|:---:|:---:|:---:|:---:|
| `kho_ban_dem` | 0,30 | 0,10 | 0,25 | 0,35 | bật |
| `benh_vien_gio_cao_diem` | 0,25 | 0,50 | 0,10 | 0,15 | bật |
| `pilot_demo` | 0,35 | 0,20 | 0,30 | 0,15 | bật, horizon ngắn |
| `measured_only` | 0,30 | 0,25 | 0,25 | 0,20 | **tắt** (không cần khai số kinh doanh) |

### 6.2. Ví dụ chạy tay từ đầu đến cuối

**Deployment:** kho 40×25 m · robot diff-drive rộng 0,52 m · khe kệ hẹp nhất 0,68 m · Jetson Orin Nano, RAM khả dụng 2 GB · vòng điều khiển 20 Hz ⇒ `T_cycle = 50 ms` · cảm biến có sẵn: LiDAR 2D · yêu cầu: `success_rate_min = 0,95`, rủi ro va chạm chấp nhận < 1% ⇒ `N_min = 300` · profile `kho_ban_dem`.

**Bốn ứng viên:**

| Candidate | Mô tả |
|---|---|
| K1 | A\* + DWA, tham số mặc định |
| K2 | A\* + DWA, đã tinh chỉnh Optuna 30 trial (tốn 3 người-ngày) |
| K3 | RRT\* + DWA |
| K4 | PPO end-to-end (checkpoint có sẵn) |

**Bước 1 — Gate:**

| | G1 đường | G2 va chạm | G3 success ≥ 95% | G4 p99 ≤ 50 ms | G5 RAM ≤ 2 GB | G6 quan sát | Kết quả |
|---|---|---|---|---|---|---|---|
| K1 | ✅ 0% | ✅ 0/300 (UCB 1,0%) | ✅ 96,7% | ✅ 21 ms | ✅ 340 MB | ✅ lidar | **Qua** |
| K2 | ✅ 0% | ✅ 0/300 (UCB 1,0%) | ✅ 99,3% | ✅ 23 ms | ✅ 350 MB | ✅ lidar | **Qua** |
| K3 | ✅ 0% | ✅ 0/300 | ✅ 96,0% | ❌ **68 ms** (replan khi gặp vật cản động) | ✅ 410 MB | ✅ lidar | ❌ Loại G4 |
| K4 | ✅ 0% | ❌ **5/300 va chạm** | ✅ 96,2% | ✅ 9 ms | ❌ **2,4 GB** | ✅ lidar | ❌ Loại G2 + G5 |

> **Trạng thái cổng thời gian thực trong ví dụ này là `screened_on_host`.** K3 bị loại hợp lệ dù đo trên laptop, vì laptop nhanh hơn Jetson — trượt ở đây thì chắc chắn trượt ở đó. Ngược lại, K1 và K2 **chưa** được phép tuyên bố đạt 20 Hz trên bo mạch đích: hai ứng viên này đi tiếp tới pha xác nhận, chạy ~20 episode trực tiếp trên Jetson trước khi Decision Card đổi nhãn thành `verified_on_target`.
>
> Chú ý K4: **nhanh nhất trong cả bốn** (9 ms), nhưng bị loại thẳng. Nếu dùng điểm tổng hợp một tầng, tốc độ vượt trội đó hoàn toàn có thể kéo nó lên hạng nhất. Đây chính là lý do phải có Gate — và cũng là một slide demo rất thuyết phục.
>
> **Ghi chú diễn đạt bắt buộc:** với K1 và K2, Decision Card in *"0 va chạm quan sát trong 300 lần chạy, cận trên 95% của xác suất va chạm: 1,0%"* — **không bao giờ** in chữ *"an toàn"*. Nếu chỉ chạy 30 lần, cùng dữ liệu đó chỉ cho phép nói cận trên **10%**, không đủ để qua yêu cầu 1% của khách hàng.

**Bước 2–4 — Objective, Pareto, Utility** (chân trời **50.000 nhiệm vụ**):

| | U_R | U_S | U_E | U_C | Pareto | **U** (0,30/0,10/0,25/0,35) |
|---|---:|---:|---:|---:|---|---:|
| K1 | 0,34 | 0,55 | 0,62 | 0,74 | trên biên | **0,608** |
| K2 | 0,86 | 0,78 | 0,84 | 0,71 | trên biên | **0,792** |

*(U_R chấm trên phần dôi so với ngưỡng 95%: K1 đạt 96,7% ⇒ dôi 1,7 điểm phần trăm; K2 đạt 99,3% ⇒ dôi 4,3.)*

Không candidate nào bị lấn át — K1 rẻ hơn về chi phí kỹ thuật, K2 hơn ở mọi mặt còn lại — nên cả hai đi tiếp.

**Bước 5–6 — Ghép cặp:** chạy trên **cùng 300 episode** (cùng seed, cùng lần hiện thực vật cản). `ΔU(K2, K1)` trung vị = **+0,184**, CI 95% ghép cặp = **[+0,151; +0,216]**. `0 ∉ CI` ⇒ **CLEAR RECOMMENDATION: K2.**

**Bước 7–8 — Độ nhạy và độ bền:**
- **Trọng số:** để K1 lật ngược K2, `w_C` phải tăng từ 0,35 lên **trên 0,84**. Rất vững.
- **Anchor:** xê dịch toàn bộ anchor ±10% ⇒ khuyến nghị không đổi ở 100% trường hợp.
- **Neighborhood:** K2 giữ ngôi ở **19/20** biến thể (95%). Biến thể duy nhất lật là khi `v_max` giảm 10% *và* mật độ vật cản động tăng 20% cùng lúc.

**Đổi chân trời sang 200 nhiệm vụ (pilot demo):** chi phí tinh chỉnh 3 người-ngày giờ là **432 giây/nhiệm vụ** thay vì 0,5 giây, trong khi K2 chỉ tiết kiệm 6 giây/nhiệm vụ. `U_C(K2)` rơi từ 0,71 xuống 0,08 ⇒ **U(K2) = 0,571 < U(K1) = 0,608 ⇒ khuyến nghị đổi thành K1**, nhãn NEAR-EQUIVALENT (CI của ΔU chứa 0), phương án thay thế: K2.

> **Đây là toàn bộ luận điểm của đề tài mới gói trong một ví dụ.** Cùng bản đồ, cùng candidate, cùng trọng số, cùng dữ liệu đo — **hai bối cảnh triển khai cho hai câu trả lời trái ngược nhau.** Không có Google, không có AI agent nào trả lời thay được, vì câu trả lời phụ thuộc vào con số 50.000 và con số 200 mà chỉ khách hàng mới biết.

---

## 7. Định vị lại trước prior art (thay cho mục 0.6 cũ)

> **PathBench khiến việc cắm thuật toán mới trở nên dễ. Arena 4.0 khiến việc sinh kịch bản trở nên dễ. Alyassi et al. khiến việc chạy chúng trở nên nhanh. Cả ba đều dừng lại ở một bảng số.**
> **Chúng ta đi tiếp một bước mà không ai đi: biến bảng số thành một quyết định — có cổng khả thi lấy ngưỡng từ phần cứng thật, có mô hình chi phí theo chân trời triển khai, và có biên sai số của chính quyết định đó.**

Ba đóng góp chốt lại:

**① Constraint-aware selection.** Candidate phải qua ràng buộc *triển khai được* — tin cậy, an toàn quan sát được, thời gian thực, bộ nhớ, tương thích cảm biến — trước khi được chấm điểm. Không nền tảng nào ở mục 0 mô hình hóa "bo mạch của bạn có 2 GB RAM và 50 ms mỗi vòng lặp".

**② Task-conditioned multi-objective recommendation.** Không tồn tại "planner tốt nhất"; chỉ tồn tại `argmax U(c | T, H, P)`. Kèm mô hình chi phí có chân trời triển khai — chưa ai coi công tinh chỉnh là chi phí định lượng được.

**③ Recommendation trustworthiness — điểm nhấn học thuật mạnh nhất.** Không chỉ đo hiệu năng planner mà đo **độ bền của chính quyết định**: CI ghép cặp của hiệu utility, biên ổn định trọng số, biên ổn định anchor, robustness trước nhiễu dữ liệu đầu vào.

**Ưu điểm lớn của định vị này:** nó không yêu cầu thắng ai về hạ tầng. Cả ba đóng góp chạy tốt trên một simulator 2D Python thuần cũng như trên Gazebo. Ranh giới "dứt khoát không làm" ở mục 0.7 tài liệu cũ giữ nguyên toàn bộ.

---

## 8. Ảnh hưởng tới kiến trúc và roadmap

Bốn interface `SimBackend` / `GlobalPlanner` / `LocalPlanner` / `TraceRecorder` **giữ nguyên không sửa một dòng**. Thêm bốn tầng, tất cả nằm *sau* Metrics Engine nên không đụng vào sim core:

```
Metrics Engine  (giữ nguyên)
        │
        ▼
┌─────────────────────────────────────────────┐
│  FEASIBILITY ENGINE      G1–G6              │  ngưỡng từ deployment, không hardcode
└──────────────────┬──────────────────────────┘
                   │ candidate khả thi
                   ▼
┌─────────────────────────────────────────────┐
│  OBJECTIVE ENGINE        R / S / E / C      │  anchor tuyệt đối, có version
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  DECISION ENGINE                            │
│   ① Pareto filter (có dung sai)             │
│   ② Decision Utility U(c|T,H,P)             │
│   ③ Paired bootstrap trên ΔU                │
│   ④ Sensitivity: trọng số + anchor          │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  RECOMMENDATION VALIDATOR                   │
│   Task Neighborhood · robustness margin     │
└──────────────────┬──────────────────────────┘
                   ▼
        DECISION CARD ──► Approval (Tech Lead) ──► approved_config.yaml
```

Ba module hỗ trợ: **Mission Sampler** (§1.2), **Adaptive Scheduler** (N9), và **Target Verifier** — chạy 2–3 candidate chung kết trực tiếp trên bo mạch đích để nâng `realtime_gate.status` từ `screened_on_host` lên `verified_on_target` (N4). Target Verifier nằm ngoài đường tới hạn của MVP: thiếu nó thì Decision Card vẫn ra, chỉ mang nhãn chưa xác nhận.

**Đổi ở frontend:** `Leaderboard` cũ **không đủ nữa**. Màn hình chính đổi thành **Decision Card** — một cái tên lớn, nhãn CLEAR/NEAR-EQUIVALENT, phương án thay thế, biểu đồ waterfall phân rã điểm, thanh trượt trọng số cập nhật thứ hạng theo thời gian thực, biểu đồ Pareto 2 chiều chọn được trục, và bảng "ai bị loại ở cổng nào, sau bao nhiêu lần chạy". Trajectory Viewer giữ nguyên, xuống vai trò "xem bằng chứng".

**Giữ nguyên RBAC + Approval workflow.** Đề bài yêu cầu ≥2 vai trò, và đây là chốt an toàn cuối của một hệ thống dám khuyến nghị: chỉ config đã Approve mới xuất ra file, vẫn ở chế độ sim-only, không có đường kỹ thuật nào từ UI tới robot thật.

**Roadmap 6 tuần:**

| Tuần | Mục tiêu | Deliverable kiểm chứng được |
|---|---|---|
| 0.5 | Chốt hợp đồng: 4 interface + Task Profile schema + `metric_anchors.yaml` v1 + định nghĩa 4 objective | `CONTRACTS.md`, cả nhóm review và ký |
| 1 | Sim core 2D + candidate interface + A\* | Chạy 1 mission đầu-cuối, xuất trace |
| 2 | DWA + RRT\* + Metrics Engine + Batch Runner **ghép cặp theo seed** | Bảng metrics ghép cặp |
| 3 | Feasibility Engine (G1–G6) + Objective Engine + anchor + Pareto filter | Lọc candidate, in bảng gate |
| 4 | Decision Utility + paired bootstrap + Decision Card + FastAPI + RBAC + Docker Compose | **🎯 MVP demo được đầu-cuối** |
| 5 | Sensitivity (trọng số + anchor) + Task Neighborhood + Approval UI | Decision Card có đủ 4 trường tin cậy |
| 6 | Mission distribution + Adaptive Scheduler + báo cáo + video demo | Báo cáo cuối + demo |

**Bốn thứ phải có mặt trong schema ngay từ tuần 0.5** — thêm sau sẽ phải sửa xuyên suốt: `hardware_spec` (nguồn của G4, G5, G6), `deployment_horizon` (nguồn của chi phí kỹ thuật), `candidate_id = hash(algo + params + version + observation_requirements)`, và `metric_anchors.yaml` tách riêng có `version`.

**Thứ tự cắt phạm vi khi thiếu thời gian** (cắt từ trên xuống): Mission distribution → Adaptive Scheduler → giảm K của neighborhood → độ nhạy anchor → chi phí kỹ thuật khai báo.

**Lát cắt dọc phải chạy được trước khi thiết kế thêm bất cứ thứ gì.** Đây là chốt chặn quan trọng nhất của cả roadmap, và nó chống lại đúng cái rủi ro mà bốn vòng phản biện tài liệu này đã tạo ra: *thiết kế đẹp dần lên mà không có dòng code nào chứng minh giả định nào đúng.*

```
1 bản đồ · 1 cặp start/goal · 1 robot tham chiếu · 2 candidate stack · 30–100 episode ghép cặp
        ↓  trace → metrics → gate → 4 objective → Decision Utility → CI của ΔU → Decision Card
```

Chạy được lát cắt này (mục tiêu: **hết tuần 2**, dù thô) thì phương pháp luận coi như đã được kiểm chứng đủ để mở rộng. **Không quay lại sửa phương pháp luận trừ khi lát cắt dọc phát hiện một giả định sai** — ví dụ: metric tính ra toàn 0, hai candidate cho kết quả giống hệt nhau, hay `L_ref` từ Dijkstra không khớp với đường thực đi. Những thứ đó chỉ lộ ra khi chạy, không lộ ra khi bàn.

**Không bao giờ cắt:** Feasibility Gate · chạy ghép cặp theo seed · anchor tuyệt đối · Decision Utility · paired ΔU kèm nhãn tin cậy · Approval. Bốn cái đầu gần như miễn phí về công sức; hai cái cuối là toàn bộ lý do khuyến nghị của hệ thống đáng tin, và là yêu cầu của đề bài.

---

## 9. Rủi ro mới của đề bài này

### 9.1. Bảng rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| **Bị tin quá mức** — người dùng deploy thẳng theo khuyến nghị | 🔴 Cao | Nhãn tin cậy bắt buộc + bảng ngôn ngữ ở 9.2 + robustness margin + gate phê duyệt của con người + chế độ sim-only |
| `N_min = 300` làm benchmark chậm | 🟠 TB | Adaptive Scheduler: chỉ 2–3 candidate chung kết mới chạy đủ; episode 2D chạy hàng nghìn lần mỗi phút |
| Cost Model bị coi là bịa số | 🟠 TB-cao | Hệ số nằm trong preference profile người dùng sửa được; có profile `measured_only`; luôn kèm độ nhạy; **không dùng chữ "TCO"** |
| Sa đà vào Decision Engine, sim core chưa chạy | 🔴 Cao | Decision Engine **chỉ ăn output của Metrics Engine** ⇒ làm sau được, không chặn đường tới hạn. Mốc cứng: cuối tuần 4 phải demo đầu-cuối |
| Anchor bị chọn tùy tiện | 🟠 TB | Anchor suy từ vật lý bài toán (N2), version hóa, có kiểm tra độ nhạy ±10% |
| Phạm vi một instance bị chê hẹp | 🟠 TB | Đây là **lựa chọn có chủ đích**: hẹp về phạm vi, sâu về độ tin cậy. Task Neighborhood và chế độ deployment-level là câu trả lời trực tiếp |
| "Độ chính xác" hiểu khác nhau giữa các bên | 🟠 TB | Chốt định nghĩa R/S/E/C với giảng viên **trước tuần 1** |

### 9.2. Ngôn ngữ được phép dùng trong báo cáo

Một hệ thống dám nêu tên candidate phải kỷ luật về câu chữ. Đưa bảng này vào `CONTRACTS.md` và dùng nó để rà slide trước khi bảo vệ.

| ✅ Nên nói | ❌ Không được nói |
|---|---|
| "Candidate phù hợp nhất **trong tập đã đánh giá**, dưới task profile, ràng buộc phần cứng và preference profile này" | "Hệ thống tìm ra thuật toán tốt nhất" |
| "0 va chạm quan sát trong 300 lần chạy; cận trên 95%: 1,0%" | "Candidate này an toàn" / "xác suất va chạm = 0" |
| "Utility 0,79 dưới profile `kho_ban_dem` và anchor v1.2" | "Candidate này tốt 79%" |
| "Mô hình chi phí với giả định khai báo; độ nhạy xem bảng bên" | "Đây là TCO thực tế của bạn" |
| "Khuyến nghị kèm CI ghép cặp, độ nhạy và bằng chứng robustness" | "Kết quả này đã được chứng minh" |
| "Cận trên 1,0% **dưới phân phối kịch bản đã mô phỏng**" | "Xác suất va chạm ngoài thực tế là 1%" |
| "p99 = 23 ms trên môi trường benchmark; G4 mới qua vòng sàng lọc, chưa xác nhận trên bo mạch đích" | "p99 trên laptop chứng minh chạy được 20 Hz trên Jetson" |
| "Cận trên va chạm tính trên evaluation distribution, không tính trên tập neighborhood" | gộp mọi lần chạy vào một công thức rule-of-three |
| "C1 mang nhãn UNCERTAIN DOMINANCE — chưa đủ dữ liệu để kết luận" | im lặng loại C1 khỏi báo cáo |
| "Scope: Global Planner Selection, local planner cố định DWA(config_A)" | "DWA thắng A\*" |

---

## 10. Bổ sung bảng thuật ngữ

| Thuật ngữ | Giải thích ngắn kèm ví dụ |
|---|---|
| **Decision Utility** `U(c\|T,H,P)` | Mức phù hợp của candidate với *deployment cụ thể này*, không phải chất lượng nội tại của thuật toán. 0,84 không nghĩa là "tốt 84%". |
| **Feasibility Gate** | Vòng loại nhị phân trước khi chấm điểm. Như tuyển tài xế: không có bằng lái thì không thể bù bằng việc nói năng lưu loát. |
| **Gate trên ngưỡng, điểm trên phần dôi** | Cổng hỏi "có vượt ngưỡng không"; điểm hỏi "vượt bao nhiêu". Nhờ vậy một metric không bị tính hai lần. |
| **Bootstrap ghép cặp (paired)** | Cho mọi candidate chạy đúng cùng episode, rồi bootstrap trên *hiệu số* thay vì trên từng candidate riêng. Như so hai loại phân bón trên cùng một thửa ruộng thay vì hai thửa khác nhau. |
| **Quy tắc số 3** | Quan sát 0 sự kiện trong N lần ⇒ cận trên 95% của xác suất thật ≈ 3/N. 30 lần sạch chỉ chứng minh được "dưới 10%", không phải "bằng 0". |
| **Lấn át Pareto (dominance)** | A không tệ hơn B ở mọi mặt và hơn ít nhất một mặt ⇒ B không đáng được chọn dưới bất kỳ trọng số không âm nào. |
| **Rank reversal** | Thêm một ứng viên mới làm đổi thứ hạng các ứng viên cũ dù họ không thay đổi gì. Dấu hiệu của chuẩn hóa sai. |
| **Anchor (mốc tuyệt đối)** | Giá trị "tốt"/"tệ" định nghĩa từ vật lý bài toán, không từ tập ứng viên. Chấm theo thang điểm 10 cố định thay vì xếp hạng trong lớp. |
| **Measured vs Declared cost** | Measured đo trực tiếp từ trace (CPU, RAM, thời gian). Declared do người dùng khai (giá điện, giờ công) và là *một phần của preference*, không phải tuyên bố về thế giới. |
| **Deployment horizon** | Số nhiệm vụ hệ sẽ chạy trong đời triển khai. Là mẫu số để khấu hao chi phí một lần. |
| **Task Neighborhood** | Biến thể nhỏ quanh task gốc (dời đích, lệch pallet, nhiễu cảm biến). Đo bất định của **dữ liệu đầu vào** — khác với mission distribution vốn đo bất định của **khối lượng công việc**. |
| **Recommendation Robustness** | % biến thể mà khuyến nghị không đổi. Dưới 60% ⇒ khuyến nghị mong manh. |
| **Weight stability margin** | Trọng số phải sai lệch bao nhiêu thì kết luận mới lật. Biên rộng ⇒ không cần biết chính xác ưu tiên của mình. |
| **Candidate configuration** | Đơn vị được xếp hạng: global planner + local planner + tham số + version. Không phải "thuật toán". So A\* với DWA giống so động cơ với vô-lăng. |
| **ε-dominance** | Lấn át có dung sai. Dung sai đặt ở vế "không tệ hơn"; đặt nhầm sang vế "tốt hơn" thì quy tắc không bao giờ kích hoạt khi hai bên hòa ở một objective. |
| **Sàng lọc một chiều** | Đo trên máy nhanh hơn chỉ dùng để **loại**: trượt trên máy nhanh thì chắc chắn trượt trên máy chậm. Không bao giờ dùng theo chiều ngược lại để kết luận "chạy được". |
| **Non-inferiority** | Kiểm định "có bằng chứng A không tệ hơn B quá ε", khác hẳn với "không có bằng chứng A tệ hơn B". Dữ liệu ít thì kiểm định này tự động không kết luận — đúng chiều thận trọng. |
| **Evaluation distribution** | Bộ mẫu độc lập dùng để ước lượng success rate và bằng chứng va chạm. Tách hẳn khỏi Task Neighborhood, vốn chỉ đo độ ổn định của khuyến nghị. |
| **Lát cắt dọc (vertical slice)** | Phiên bản mỏng nhất chạy xuyên toàn bộ pipeline từ bản đồ tới Decision Card. Dùng để kiểm chứng giả định trước khi mở rộng bề ngang. |
| **Successive halving / racing** | Chạy tất cả ứng viên với ít mẫu, loại sớm kẻ thua rõ, dồn mẫu cho nhóm còn tranh chấp. Như vòng loại giải đấu thay vì đấu vòng tròn. |
| **Hòa thống kê (NEAR-EQUIVALENT)** | CI của hiệu utility ghép cặp có chứa 0. Nói "A thắng" trong trường hợp này là nói dối bằng độ chính xác giả. |

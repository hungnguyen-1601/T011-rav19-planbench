# Kế hoạch (xếp hàng): thêm Theta\* và Regulated Pure Pursuit

> **Ngày lập:** 2026-08-11 · **Người lập:** An (cùng Claude) · **Trạng thái:** chờ approve
> **Lịch:** **chưa lên lịch** — chạy sau khi MVP hiện tại xong **và UI cơ bản đã có** (dev chốt
> 2026-08-11). Đây là plan đầu tiên của dự án nói về **thuật toán**; mọi plan trước nói về
> **dụng cụ đo**.
> **Điều kiện vào:** MVP v1 chốt (đã xong) · A1/A2/A4 xong · **B1 (kho ở 1%) đã có số** (mục 1) ·
> **UI cơ bản (Phase 7) chạy được**.
> **Dev đã chốt:** đồng ý cả năm rủi ro ở mục 4; với rủi ro ⑤ — **chỉ đưa 1–2 tổ hợp vào so
> sánh**, không đăng ký hết ma trận. Xem P3.

---

## 0. Vì sao đúng hai thuật toán này, và nền tảng được gì

Cặp này không phải "thêm cho nhiều". Mỗi cái mở một **chiều đo mà nền tảng hiện chưa dùng được**.

### Theta\* — global planner đi góc tự do

A\* trên lưới 8-liên thông chỉ đi được tám hướng, nên đường của nó là bậc thang; Theta\* cho phép
cha của một node là **bất kỳ node nào nhìn thấy được**, sinh ra đường gần tối ưu ở góc tự do.

**Vì sao điều đó quan trọng với chính dự án này:** `L_ref` được tính bằng Dijkstra rồi **kéo căng
đa tỉ lệ** (sửa hôm 08-11, sai số 0,0027%). Nó là một đường **góc tự do**. Nên `path_efficiency`
= `L_ref / path_length` hiện đang chấm A\* trên một thang mà A\* **không thể** đạt gần — mọi
candidate global hiện có đều thua vì cùng một lý do hình học, và O3 vì thế **không phân biệt
được gì** giữa chúng. Theta\* là candidate đầu tiên làm O3 nói lên điều gì.

**Một giả thuyết cụ thể, đáng kiểm:** `astar+dwa` trượt G3 trên sảnh vì kẹt ở **góc lồi**. Đường
Theta\* không ôm góc theo cùng kiểu. Nó **có thể** không kẹt — và nếu vậy thì đó là **phát hiện
về A\***, không phải bản vá cho A\*. Cả ba cấu hình `astar+dwa` ở lại nguyên, vẫn được chấm.

### Regulated Pure Pursuit — local controller **khác họ**

Mọi phép so tới giờ đều có DWA ở **cả hai** phía. Ba cấu hình `dwa_coarse`/`balanced`/`default`
chỉ khác nhau **mật độ lấy mẫu**, nên `local_controller_selection` tới giờ mới trả lời được câu
*"lấy mẫu bao nhiêu là đủ"*, chưa bao giờ trả lời *"dùng bộ điều khiển nào"*.

RPP là mặc định của Nav2 từ 2021: pure pursuit có **điều tiết** — giảm tốc theo độ cong, giảm tốc
khi gần vật cản, giữ tốc độ tối thiểu lúc tiếp cận. Hai hệ quả:

1. **Nó đọc cảm biến.** Đây là chỗ phải tách bạch tuyệt đối với `pure_pursuit` đang có trong
   repo, vốn khai `benchmarkable=False` **chính vì nó bỏ qua cảm biến** (D12, KNOWN_LIMITATIONS
   mục 12). RPP là **stack mới**, không phải một cờ trên stack cũ — nếu không, một kết luận có
   thể vô tình tựa lên cái không benchmarkable được.
2. **Nó rẻ hơn DWA rất nhiều.** Không có rollout lấy mẫu, nên p99 nhiều khả năng dưới 1 ms so với
   6,06 ms của `dwa_coarse`. Đó là phép thử thật đầu tiên xem **U_C có làm việc gì không** — tới
   giờ chi phí tính toán chỉ chênh nhau trong một họ.

Thêm một lý lẽ ngoài kỹ thuật: RPP là mặc định của Nav2, nên một kết luận về RPP **chuyển được**
sang triển khai thật, còn kết luận về DWA của repo này thì không.

---

## 1. Vì sao phải đợi B1

Không phải thủ tục. B1 là lần đầu kho chạy dưới nhiễu, và nó trả lời **hai ẩn số** mà cả hai đều
đổi cách đọc kết quả của plan này:

- `n_distinct` của một stack tất định trên kho. Nếu nhiễu vẫn chưa đủ chạm tới kho thì G2 sẽ từ
  chối **mọi** candidate mới trên deployment thật, và ta sẽ tưởng đó là tính chất của Theta\*.
- Có candidate nào qua đủ sáu cổng trên kho không. Nếu **không**, thì thêm hai thuật toán vào một
  deployment chưa ai qua nổi là đo trong bóng tối.

Thêm nữa: A1/A2/A4 làm card đầy đủ. Thêm thuật toán **trước** khi card có độ nhạy nghĩa là mọi
kết luận mới cũng thiếu đúng trường mà HĐ-11.5 gọi là quan trọng nhất.

---

## P1. Theta\* — global planner *(≈1 ngày)*

### P1.1 Hiện thực

`packages/planning/planbench_planning/thetastar/planner.py`, theo interface `GlobalPlanner` của
HĐ-4 (`plan(grid, start, goal) -> PlanResult`).

Lõi khác A\* đúng một chỗ — bước cập nhật cha:

```
nếu line_of_sight(parent(s), s'):        # đường thẳng không cắt ô bị chặn
    ứng viên cha của s' là parent(s), chi phí = g(parent(s)) + dist(parent(s), s')
ngược lại:
    như A* thường
```

**Dùng lại `has_line_of_sight`** trong `planbench_planning.common.path_utils` — cùng hàm mà
`simplify_path` và `L_ref` dùng. Viết bản kiểm tia thứ hai là tạo hai định nghĩa "nhìn thấy
được" tự do bất đồng, và chúng sẽ bất đồng đúng ở các ô biên.

**Lập kế hoạch trên lưới đã inflate**, như A\* và RRT\* (`_planning_grid`). Điều này giữ một tính
chất phải giữ: `L_ref` tính trên lưới **không** inflate, nên **không candidate nào có thể thắng
`L_ref`** và `path_efficiency` ở lại trong (0, 1].

### P1.2 Registry và định danh

- `packages/benchmark/planbench_benchmark/registry.py`: `thetastar+dwa` (và `thetastar+rpp` sau
  P2), `benchmarkable=True`, `global_planner="thetastar"`.
- Khai `observation_class` cho P02/G6: giống A\* — `full_static_map`. Theta\* không đọc thêm gì.
- `StructuralResourceProfile`: `bytes_per_search_node` khai theo **hiện thực đích** (C++/ROS2),
  không theo Python (HĐ-7.3 luật 1). Theta\* giữ thêm một con trỏ cha cho mỗi node so với A\*.

### P1.3 Test

| Test | Khẳng định |
|---|---|
| Đường Theta\* **không dài hơn** đường A\* trên cùng lưới | tính chất định nghĩa của any-angle |
| Trong phòng trống: **một đoạn thẳng** | A\* cho bậc thang, đây là khác biệt dễ thấy nhất |
| Mọi đoạn của đường trả về **có line-of-sight** | đường không hợp lệ mà ngắn hơn thì tệ hơn không có đường |
| `L_ref ≤ path_length` vẫn giữ trên map đối xứng | lưới inflate so với lưới không inflate |
| Tất định: cùng grid + cùng start/goal ⇒ cùng đường | HĐ-13, và Theta\* không có nguồn ngẫu nhiên nào |
| `peak_search_nodes ≤ costmap_cells` | HĐ-15.1(6), G5 dựa vào bộ đếm này |

### P1.4 Đo

`measure.py --candidate thetastar+dwa --local dwa_coarse` trên `open_hall_v2` (30 ep) rồi
`warehouse_a_v2`. Ghi **dự đoán trước khi chạy**, như đã làm với `dwa_balanced`:

- `path_efficiency` **cao hơn** A\* rõ rệt — đây là điều Theta\* sinh ra để làm;
- p99 **cao hơn** A\* (mỗi lần mở node có thêm một phép kiểm tia), nhưng vẫn xa dưới 50 ms;
- success trên sảnh: **không đoán**. Đó là câu hỏi, không phải kỳ vọng.

---

## P2. Regulated Pure Pursuit — local controller *(≈1–1,5 ngày)*

### P2.1 Hiện thực

`packages/planning/planbench_planning/rpp/planner.py`, theo `LocalPlanner` của HĐ-4.

Ba luật điều tiết, và mỗi cái phải là một **tham số khai báo được**, không phải hằng số:

| Điều tiết | Ý nghĩa |
|---|---|
| theo **độ cong** | vòng gấp ⇒ chậm lại; giữ bám đường ở khúc cua |
| theo **khoảng cách vật cản** | gần vật cản ⇒ chậm lại; đây là chỗ nó **đọc `Observation`** |
| **tốc độ tiếp cận tối thiểu** | không bò về 0 khi tới gần đích |

Cộng `lookahead_distance` (có thể theo tốc độ, như Nav2).

**`control_period` phải khai tường minh**, không thừa kế. `validate_control_rate` đòi nhịp
controller ≤ `T_cycle` của deployment; RPP rẻ nên 20 Hz dễ, nhưng dễ không phải lý do để im lặng.

### P2.2 Tách bạch tuyệt đối với `pure_pursuit` đang có

`astar+pure_pursuit` khai `benchmarkable=False` vì nó **bỏ qua cảm biến** — nó tồn tại để kiểm
đường ống, không để kết luận. RPP:

- là **stack mới** (`astar+rpp`, `rrtstar+rpp`, `thetastar+rpp`), không phải cờ trên cái cũ;
- khai `observation_class = lidar_only` ⇒ `observation_requirements = ("lidar_2d",)` cho G6;
- `benchmarkable=True`.

Cần một test khẳng định RPP **thật sự đọc** `Observation`: cùng pose, hai quét LiDAR khác nhau ⇒
hai lệnh khác nhau. Nếu không có test đó, một RPP hiện thực sai thành pure pursuit thường sẽ qua
G6 bằng lời khai chứ không bằng hành vi — đúng kiểu gian lận lớp quan sát mà HĐ-4 gọi tên.

### P2.3 Cấu hình có tên, không phải hằng số

Như `dwa_coarse`: mọi cấu hình RPP là mục có tên trong `LOCAL_CONTROLLER_CONFIGS`, và mỗi con số
phải trả lời được câu HĐ-15.3 — *"đến từ hiện trường, hay từ thứ máy/code tôi chạy nổi?"*

Đề xuất **một** cấu hình duy nhất lúc đầu: `rpp_default`, lấy **nguyên mặc định của Nav2**. Lý do
mạnh: nó là con số ngoại sinh, không do ta chọn, và nó khớp với `tuning_trials_used = 0` mà DWA
đang khai. Muốn thêm điểm trên trục thì **đăng ký candidate mới**, như `dwa_balanced` đã làm.

### P2.4 Test

| Test | Khẳng định |
|---|---|
| Giảm tốc theo độ cong | đường cong gấp ⇒ `linear_velocity` thấp hơn đường thẳng |
| Giảm tốc theo vật cản | quét LiDAR gần ⇒ chậm hơn, cùng đường |
| **Đọc Observation thật** | cùng pose, hai quét khác ⇒ hai lệnh khác |
| Tốc độ tiếp cận tối thiểu | không về 0 trước khi vào dung sai đích |
| Tất định | cùng state + observation ⇒ cùng lệnh (`LocalPlanner` yêu cầu) |
| `control_period` khai đúng | `validate_control_rate` nhận nó trên deployment 20 Hz |

---

## P3. Hai phép so, hai stack mới *(≈nửa ngày + giờ máy)*

Dev đã chốt: **không đăng ký hết ma trận**. Ba global × hai local là sáu stack; cái cần là số
stack **nhỏ nhất trả lời được cả hai câu hỏi mà cặp thuật toán này mở ra**. Đó là **hai**.

| # | Set | Scope | Stack mới | Câu hỏi |
|---|---|---|---|---|
| 1 | `astar+dwa`, `rrtstar+dwa`, **`thetastar+dwa`** — tất cả `dwa_coarse` | `global_planner_selection` | `thetastar+dwa` | Đường góc tự do đổi được gì? **O3 lần đầu phân biệt được.** |
| 2 | `rrtstar+dwa:dwa_coarse`, **`rrtstar+rpp:rpp_default`** | `local_controller_selection` | `rrtstar+rpp` | Đổi **họ** controller đổi được gì? **U_C lần đầu bị thử thật.** |

Cả hai giữ **một** tầng cố định, nên mỗi cái nói được điều gì đó về đúng tầng kia (HĐ-1.4). Phép
so ba-candidate ở (1) dùng lại hoàn toàn trace của `astar+dwa` và `rrtstar+dwa` đã có — chỉ
`thetastar+dwa` phải mô phỏng mới.

### Vì sao ghép RPP với RRT\*, không với A\*

Đây là một **đánh đổi có thật**, không phải mặc định:

- `rrtstar+dwa` qua **đủ sáu cổng** trên sảnh (100% success, 6,06 ms). Nên phép so (2) có một
  đường cơ sở lành, và **có thể ra Decision Card**.
- `astar+dwa` **trượt G3** ở cả ba mật độ lấy mẫu. Ghép RPP với A\* sẽ nhiều khả năng rơi nhánh
  B — không card, chỉ bảng cổng.

Nhưng phải nói rõ cái bị đánh đổi: `astar+dwa` so `astar+rpp` là phép so **chẩn đoán** trực tiếp
cho câu *"kẹt góc lồi là lỗi của controller hay của planner?"* — cùng hình dạng câu hỏi mà lần
đo `dwa_coarse` so `dwa_default` đã trả lời ở mức **mật độ lấy mẫu**, giờ hỏi ở mức **họ
controller**. Chọn RRT\* là đổi câu chẩn đoán đó lấy khả năng ra một tấm card.

**Nếu dev thấy câu chẩn đoán đáng hơn tấm card**, đổi (2) thành `astar+dwa` so `astar+rpp` — vẫn
đúng một stack mới, vẫn đúng ngân sách.

### Cố ý không xây

| Không xây | Vì sao |
|---|---|
| `thetastar+rpp` | Cần cả hai tầng mới cùng lúc ⇒ scope buộc phải là `full_stack_selection`, mà scope đó **không cho** kết luận về riêng tầng nào. Card ra được nhưng nói được ít hơn hai phép so hẹp ở trên |
| `astar+rpp`, `rrtstar+rpp` **cùng lúc** | Chưa có câu hỏi nào cần cả hai |
| `thetastar+dwa_balanced`, `thetastar+dwa_default` | Trục mật độ lấy mẫu đã đo xong trên hai global planner; đo lần ba chỉ để có ba đường cong |

Nguyên tắc để thêm về sau: **một stack mới cần một câu hỏi cụ thể mà nó là cách rẻ nhất để trả
lời.** Không có câu hỏi thì đừng đăng ký — mỗi stack là 30–300 episode trên mỗi deployment, và
một ma trận đầy đủ là hàng chục giờ máy đổi lấy những ô không ai hỏi.

## 4. Năm cái bẫy, viết trước vì cả năm đều đã có tiền lệ trong dự án này

### 4.1. Ngân sách tinh chỉnh — bẫy nguy hiểm nhất

DWA chạy ở **mặc định thư viện** và khai `tuning_trials_used = 0`. Nếu ta tinh chỉnh RPP còn DWA
thì không, U_C đang so một stack **đã tinh chỉnh** với một stack **chưa** — và bảng xếp hạng sẽ
báo "thuật toán tốt hơn" cho một bài toán đã được ưu ái. Đó đúng lỗ hổng S2 mà tài liệu mẹ phê
phán ở Alyassi et al., và là luật P01.

Luật cho plan này: **cả hai bên ở mặc định thư viện**. Mọi bản tinh chỉnh là **candidate riêng**
với `tuning_trials_used` và `tuning_wall_clock_h` khai thật kèm log bằng chứng (HĐ-1.6).

### 4.2. `path_efficiency` bão hoà

Nếu Theta\* lập kế hoạch rất gần `L_ref` thì O3 sẽ bị **clip về 1,0** và thôi phân biệt ở đoạn
trên — đúng hiệu ứng HĐ-15.1(5) đã ghi cho nhiệm vụ ngắn. Phải **nhìn phân phối
`path_efficiency`, không chỉ trung bình**. Nếu bão hoà thật thì đó là phát hiện về **thang đo**,
và cách sửa đúng là đo `L_ref` tới quả cầu dung sai — một thay đổi ngữ nghĩa HĐ-6, tức MAJOR, tức
**không** làm lén trong plan này.

### 4.3. G5 và bộ đếm của thuật toán mới

`memory_estimate_mb` là **bộ đếm nhân kích thước byte khai theo hiện thực đích**, không phải RSS.
Theta\* giữ thêm con trỏ cha; RPP **không có** open/closed lẫn cây, nên
`peak_search_nodes = peak_tree_nodes = 0` và ước lượng của nó gần như chỉ còn costmap. Cả hai phải
khai `StructuralResourceProfile` đúng, nếu không G5 **nói dối một cách hợp lệ**.

### 4.4. Bùng nổ tổ hợp — **dev đã chốt cách chặn**

Registry khoá theo stack `<global>+<local>`. Ba global × hai local = **sáu** stack, và mỗi local
config nhân thêm lần nữa.

**Quyết định:** chỉ đưa **1–2 tổ hợp** vào so sánh. P3 đã thu về **đúng hai stack mới**
(`thetastar+dwa`, `rrtstar+rpp`) — số nhỏ nhất trả lời được cả hai câu hỏi mà cặp thuật toán này
mở ra, mỗi phép so giữ một tầng cố định để còn kết luận được về tầng kia.

Chi phí của việc không chặn: mỗi stack là 30 episode trên sảnh **cộng** 300 trên kho, mỗi
deployment, cho mỗi phép so nó tham gia. Một ma trận đầy đủ là hàng chục giờ máy đổi lấy những ô
không ai đặt câu hỏi cho.

### 4.5. Không chỉnh nền tảng cho thuật toán mới chạy được

Đây là plan đầu tiên **thêm thuật toán**, nên là lần đầu áp lực đó xuất hiện đúng hình dạng cũ.
Nếu Theta\* hay RPP trượt một cổng, bốn thứ **không** được đụng: map, mission,
`collision_probability_max`, và ngưỡng của cổng đó. Bốn thứ đó là đúng bốn thay đổi đã bị hoàn
nguyên hôm 2026-08-11.

---

## 5. Nghiệm thu

1. Cả hai đăng ký được qua `POST /candidates`, id do server tính (HĐ-1.3).
2. **Bộ kiểm công bằng xanh trước khi công bố phép so nào** (HĐ-15.1 tiêu chí 7).
3. **Hai** phép so ở P3 chạy xong, mỗi cái ra **card hoặc bảng cổng** — cả hai đều là kết quả đạt.
4. **Không số nào của candidate cũ đổi.** `decision_utility` của `rrtstar+dwa:dwa_coarse` trên
   `open_hall_v2` phải vẫn là `0,852213`. Thêm thuật toán không được đổi điểm của thuật toán cũ;
   nếu đổi thì thứ vừa thêm đã chạm vào tầng đo.
5. Mỗi kết luận mới đi kèm dự đoán **ghi trước khi đo**, và báo cáo đối chiếu hai bên.

---

## 6. Cố ý ngoài phạm vi

- **Tinh chỉnh** bất kỳ candidate nào — xem 4.1.
- Sửa `L_ref` sang thang quả cầu dung sai — MAJOR, cần plan riêng (xem 4.2).
- Nav2/ROS2 thật. RPP ở đây là **hiện thực lại luật điều tiết** trong simulator này, không phải
  bọc Nav2. Ghi rõ trong docstring để không ai đọc kết quả như một phép đo về Nav2.
- Adapter `MonolithicPolicy` và lưới replan ground truth — nợ riêng, cả hai candidate mới đều là
  `modular` nên **không** vướng.

---

## 7. Câu hỏi mở

1. **Theta\* dùng lazy hay bản gốc?** Lazy Theta\* rẻ hơn (hoãn kiểm tia tới lúc mở node) nhưng
   đường hơi dài hơn. Đề xuất: **bản gốc trước** — nó là định nghĩa sạch, và Lazy là candidate
   thứ hai nếu G4 thành vấn đề. Đúng nước "đăng ký candidate mới" thay vì chỉnh cái cũ.
2. **RPP lấy `lookahead_distance` cố định hay theo tốc độ?** Nav2 mặc định theo tốc độ. Đề xuất
   theo Nav2, vì lý do ở P2.3: con số ngoại sinh.
3. **Chạy hai deployment hay chỉ kho?** Sảnh rẻ và là acceptance deployment (`success_rate_min =
   1.00`), nên nó bắt lỗi cấu hình trước khi tiêu ba giờ máy trên kho. Đề xuất: **sảnh trước,
   luôn luôn.**
4. **Phép so (2) ghép RPP với RRT\* hay với A\*?** Đề xuất RRT\* — nó qua đủ sáu cổng nên phép so
   có thể ra card. Đổi lại là mất câu chẩn đoán *"kẹt góc lồi là lỗi của controller hay của
   planner?"*. Xem P3; đổi hướng không tốn thêm stack nào.

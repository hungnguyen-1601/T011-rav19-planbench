# Rút `dwa_predictive` — đóng bằng kết quả âm

**Ngày:** 2026-08-16
**Phạm vi:** Q0, R1, R1b, một bản sửa đã xây rồi thu hồi, và việc rút
candidate khỏi tập production.
**Kết quả:** `dwa_predictive` **không ship**. Mô hình đúng, tri giác
không nuôi nổi nó.

---

## 1. Vào phiên với cái gì

Plan `plans/2026-08-16/sua-tri-giac-dwa-predictive.md` (8 ngày, 8 quyết
định dev đã chốt) đặt cược vào một luận điểm: *tăng độ phân giải LiDAR là
đòn bẩy chính; Q2 chỉ cần làm các ngưỡng co giãn theo để việc tăng tia
thôi phản tác dụng*.

Luận điểm đó dựa trên một bảng đo **một seed**, trung vị lấy trên 2–17
khung. Pha Q0 tồn tại để chạy lại ở N ≥ 20 **trước khi** sửa gì, và plan
ghi sẵn: *"Q0 có thể huỷ toàn bộ phần còn lại. Đó là mục đích của nó."*

Nó đã huỷ.

---

## 2. Q0 — độ phân giải không phải đòn bẩy

`scripts/diagnose_resolution.py` (mới, đã commit-ready). 160 episode,
27.6 phút, seed calibration A = 1000..1019, hai nhánh: nhà kho có
traffic và **cùng deployment rút hết traffic** (mọi vận tốc báo ra ở
nhánh sau đều là ảo theo định nghĩa).

```
 tia   phát hiện thật   sai số trung vị   vận tốc ma (cảnh TĨNH)
  72       0.9%             0.429              14.2%
 144       3.5%             0.935              78.6%
 271       4.1%             0.813              97.5%
 360       4.5%             0.864              99.2%
```

**Bảng một-seed bị bác bỏ.** Không có "đỉnh ở 144 rồi thoái lui" —
`vel_out` tăng đơn điệu. Con số `err_med 0.164` ở 144 tia từng là bằng
chứng mạnh nhất cho "144 là điểm ngọt"; ở N = 20 nó là **0.935**, tức
sai số cỡ chính đại lượng cần đo. Ăn may với n nhỏ.

**Objective khai trước khi bảng tồn tại** (ràng buộc cứng: ảo ≤ baseline
72 tia) loại sạch mọi cấu hình trừ 72 tia — chính cái đang chạy.

Ở 360 tia tracker báo có vật đang chuyển động ở **99.2% số khung của một
nhà kho đứng yên hoàn toàn**.

---

## 3. R1 — sàn vận tốc không phải cổng đang gánh việc

`scripts/diagnose_phantom.py` (mới). Không chạy planner: engine được
step trực tiếp bằng `SimAction`, ego-motion là kịch bản, nên mỗi hàng cô
lập đúng một nguồn. 6 hàng × 4 độ phân giải × 4 hình học.

Phân rã lý do mỗi record bị đưa về 0 (nhà kho, đứng yên + nhiễu):

```
 tia   coasting  warmup  floored   kept
  72     84.7%     6.9%     1.9%    6.5%
 360     71.9%     4.8%     2.8%   20.4%
```

**Sàn loại 2–5%.** Thứ giữ tracker im lặng là `coasting` — track không
được nhìn thấy — 72–85%.

Nghĩa là `dwa_predictive` đang an toàn **nhờ tri giác kém**, không nhờ
cổng lọc nào. Và hệ quả nghịch đảo: tri giác tốt lên thì an toàn tệ đi.
Một thiết kế mà cải thiện cảm biến làm nó nguy hiểm hơn là thiết kế sai.

Đối chứng quyết định — cùng chuyển động, cảm biến **hoàn hảo**:

```
tỉ lệ raw fit vượt 0.1 m/s   72 tia   144 tia   271 tia
isolated_object                9.7%      0.0%      0.0%
warehouse                     84.3%     83.1%     84.6%
```

Vật cô lập gọn gàng gần như không sinh ảo. Nhà kho sinh 84%, **phẳng**
theo độ phân giải. Cùng tracker, cùng cảm biến, cùng chuyển động — khác
mỗi hình học.

---

## 4. R1b — cơ chế, truy đến tận điểm quét

Hai giả thuyết đầu của tôi **đều bị chính dữ liệu bác**: (a) gộp do
ngưỡng tách quá rộng — bác vì `straightness` không đổi theo độ phân giải
dù ngưỡng chặt gấp 5 lần; (b) góc tường nói chung — bác vì hình học
`corner` tổng hợp cho **0 ảo**.

Nên dump điểm quét thật thay vì suy tiếp:

```
robot (3.86, 3.00, 0.000)   reach 4.13 m   out_speed 0.436   tia 44-48

  (7.438, 6.000)   range 4.667      ┐
  (6.862, 6.000)   range 4.243      ├ ba điểm trên y = 6.000
  (6.380, 6.000)   range 3.916      ┘
  (6.000, 6.053)   range 3.727      ┐ hai điểm trên x = 6.000
  (6.000, 6.702)   range 4.275      ┘
```

**Góc vuông của hai mặt kệ tại (6.000, 6.000).** Bậc range lớn nhất qua
góc: 0.55 m. Ngưỡng tách ở tầm đó: ≈1.05 m. Không đủ tách — một cụm, hai
mặt phẳng.

Quỹ đạo centroid: dịch 0.305 m trong 0.70 s = **0.436 m/s**, khớp đúng
`out_speed`. Robot đi `+x` nên tỉ lệ nhìn thấy giữa hai mặt đổi dần,
centroid của hợp hai mặt trượt dọc góc.

**Trơn tru là chỗ chết.** Centroid đi thẳng, đều. Least-squares 15 khung
cho một vận tốc ổn định, tự tin. Trong bản thân tín hiệu vận tốc **không
có gì** phân biệt nó với vật thật đi 0.436 m/s — nên không sàn, không làm
mượt, không confidence tính từ vận tốc nào tách được.

---

## 5. Bản sửa: đã xây, đã đo, đã thu hồi

Tách cụm tại chỗ đổi hướng bên trong nó (Ramer–Douglas–Peucker + ngưỡng
góc + dung sai suy từ khoảng cách tia), trước bước phân loại. Kèm 21 test
mới và bộ đếm `corners_split`.

Đo bằng chính harness R1b:

| | trước | sau |
|---|---|---|
| nhà kho 271 tia | 55 ảo | **6** |
| nhà kho 72 tia | 19 ảo | 14 |
| vật cô lập 271 tia | — | **0** |

271 tia giảm 89%. Nhưng ở 72 tia gần như không đổi, và khi truy tiếp thì
lý do là giới hạn cứng:

```
góc kệ ở 4.6 m, 72 tia:   residual/spacing = 0.77
vật tròn ở 2.0 m, 72 tia: residual/spacing = 1.43
```

Ở đơn vị chuẩn hoá theo cảm biến, **vật thật lệch nhiều hơn góc tường**.
Hạ dung sai để bắt góc sẽ cắt vật thật **trước**. Hai loại không tách
được bằng hình dạng ở mật độ lấy mẫu này.

**Đã thu hồi toàn bộ** — `tracking.py`, `planner.py` và file test trở về
trạng thái HEAD. Giữ lại một bản sửa chỉ hiệu quả ở độ phân giải mà Q0
vừa loại là thêm ngưỡng, thêm bề mặt hỏng, không thêm giá trị.

---

## 6. Việc đã làm: rút candidate (nhánh (c) của Q4)

Dev chốt không chạy cổng Q4. **Ghi rõ:** verdict đến từ bằng chứng
thượng nguồn (P5, P7, Q0, R1, bản sửa thất bại), **không** từ một lần
chạy cổng. Chạy 120 seed để xác nhận thứ đã biết là tốn công vô ích, và
tiền lệ P4 cho thấy cổng chỉ có giá trị khi kết quả còn mở.

Thay đổi:

- `registry.py` — `astar+dwa_predictive` và `rrtstar+dwa_predictive`
  chuyển `benchmarkable=False`.
- `AlgorithmInfo.withdrawn` — trường mới. `benchmarkable=False` từ D12
  tới nay chỉ có **một** nghĩa (*reference adapter, không bao giờ là
  contender*); giờ có hai. Một lời từ chối nói với loại thứ hai rằng nó
  là "reference stack only" là nói sai. Lý do đi cùng entry, và
  `candidate_from_stack` trích dẫn nó.
- Mô tả stack mở đầu bằng `**WITHDRAWN 2026-08-16 — experimental, not
  recommendable.**` — chuỗi này tới `/algorithms` nguyên văn.
- `tests/test_benchmark_engine.py` — tập fresh-clone về lại
  `{astar+dwa, rrtstar+dwa}`. Test này là **exact set**, nên nó tự gãy
  nếu ai đó thêm stack mà không quyết định — guard đó đã làm đúng việc
  hai lần trong phiên.
- `tests/test_candidate_identity.py` — thay
  `test_the_stack_is_registered_and_benchmarkable` bằng cặp
  *vẫn-đăng-ký-nhưng-đã-rút* và *không-dựng-được-thành-candidate*.
- `docs/KNOWN_LIMITATIONS.md` — **L19** (việc rút, đủ số liệu và cơ chế)
  và **L20** (hai nợ hạ tầng, xem mục 7).

**Giữ nguyên:** implementation, oracle, diagnostics, mọi test cũ. Kết quả
âm chỉ có giá trị nếu tái lập được.

---

## 7. Hai nợ hạ tầng lộ ra — **chưa sửa**, đã ghi L20

Không liên quan `dwa_predictive`; chúng chỉ tình cờ lộ ra.

**(a) Trace của thế giới cũ được dùng lại âm thầm.** Trace định địa chỉ
chỉ bằng `(candidate_id, episode_context_id)`; `--reuse-traces` chỉ kiểm
file tồn tại. Bằng chứng thật: `run_journal.jsonl` **120 dòng** — 60
`stuck` rồi 60 `success`, **cùng** `episode_context_id b408516ece7f`.
Hai thế giới, một id. Ảnh hưởng **mọi** phép so.

**(b) `angle_span ≠ 2π` làm hỏng mọi candidate `lidar_only`.** Không chỉ
tracker — `dwa_core.obstacle_points` cũng hardcode `2π`. Deployment khai
LiDAR 180° sẽ khiến **`dwa` thường** dựng đám mây điểm lệch một phép
quay. Đây là bug của candidate đang ship.

---

## 8. Sai lầm quy trình, ghi để không lặp

Tiền đề *"một candidate `lidar_only` ước lượng được vận tốc vật cản"*
**chưa bao giờ được kiểm trước khi xây**. P4 kiểm mô hình *giả sử tri
giác hoàn hảo* và kiểm rất kỹ; không ai kiểm tri giác có khả thi không.
P5, P7, Q0, R1 đều là hoá đơn cho bước bị bỏ.

Bài học cụ thể hơn "nên kiểm tiền đề": P4 là một cổng quyết định được
thiết kế tốt, và **nó vẫn không bắt được điều này**, vì nó hỏi *"mô hình
có đáng không"* chứ không hỏi *"đầu vào mô hình có lấy được không"*. Cổng
tốt cho câu hỏi sai vẫn là cổng sai.

Điểm sáng: Q0 tốn **hai ngày** để giết một plan tám ngày. Đó đúng là thứ
nó được viết ra để làm.

---

## 9. Hướng còn mở

Hỏi *"chỗ này trước đây có gì không"* — trừ nền tự dựng từ chính scan
của robot — thay vì *"cụm này hình dạng có phải vật không"*. Vật cản động
là thứ **xuất hiện ở nơi vốn trống**; đó là thuộc tính thời gian, không
phải hình dạng. Hợp lệ với `lidar_only` vì không đọc map ground truth.

Vướng đúng một chỗ: **L17** (rollout dùng pose thật, đám mây điểm dùng
pose robot tin là). Dựng nền qua nhiều khung thì sai lệch đó thành vận
tốc — tường đứng yên sẽ trôi. L17 vốn là nợ của `dwa` **thường**, không
riêng candidate này.

---

## 10. Trạng thái

| | |
|---|---|
| Full suite | chạy lại sau khi rút — kết quả ở mục dưới |
| Code sản phẩm đổi | `registry.py`, `candidates.py` |
| Test đổi | `test_benchmark_engine.py`, `test_candidate_identity.py` |
| Script mới | `diagnose_resolution.py`, `diagnose_phantom.py` |
| Docs | L19, L20, hai note 16-08, plan cập nhật |
| Commit | chưa — chờ dev |

Plan `sua-tri-giac-dwa-predictive.md` giữ nguyên văn bản, có khối cảnh
báo đầu file và các khối Q0/R1/R1b ghi kết quả. Không xoá để đối chiếu
được luận điểm ban đầu với thứ đo được.

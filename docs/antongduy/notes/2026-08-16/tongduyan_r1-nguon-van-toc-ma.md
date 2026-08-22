# R1 — nguồn vận tốc ma, và sàn không phải cái cần sửa

**Loại:** quan sát/đánh giá. Không đổi dòng code sản phẩm nào.
**Ngày:** 2026-08-16
**Tiếp nối:** `tongduyan_q0-do-lai-do-phan-giai-lidar.md`
**Script:** `scripts/diagnose_phantom.py` · **Dữ liệu:** `artifacts/r1_phantom/records.json`

---

## 0. Câu hỏi và cách trả lời

Q0 để lại một ngã ba: mức ảo bùng nổ theo độ phân giải là do **số track
tăng** hay **mỗi track tệ đi**? Đo ra: **cả hai**. Nên R1 hỏi tiếp — ảo
đến từ **nguồn vật lý nào**, để biết sàn vận tốc có sửa được không.

Thiết kế (theo góp ý của dev): **không chạy planner**. Engine được step
trực tiếp bằng `SimAction`, ego-motion là kịch bản. Mỗi hàng thêm đúng
một nguồn:

| hàng | robot | nhiễu | cô lập cái gì |
|---|---|---|---|
| 1 | đứng yên | tắt | sàn lý tưởng — có gì ở đây là bug tracker |
| 2 | đứng yên | range | đóng góp của σ_range một mình |
| 3 | chạy thẳng | tắt | trượt điểm nhìn do tịnh tiến |
| 4 | quay tại chỗ | tắt | do quay — quét tập tia mà không đổi range |
| 5 | chạy + quay | tắt | tương tác |
| 6 | chạy + quay | range | tổng hợp — hàng Q0 đã đo |

× 4 độ phân giải × 4 hình học (`straight_wall`, `corner`,
`isolated_object`, `warehouse` thật). Mọi cảnh **tĩnh hoàn toàn**: mọi
vận tốc dưới đây đều sai theo định nghĩa.

Ghi mỗi (track, frame): **raw least-squares trước mọi gate**, sàn của
frame, giá trị sống sót, `misses`, `history`, tuổi, `robot_v`,
`robot_omega`, `Δθ`, `reach`, và geometry cụm (`points`/`width`/
`straightness`/`clipped`). Q0 chỉ thấy được giá trị **sau** gate nên
không phân biệt được "ước lượng tốt bị sàn cắt" với "không có ước lượng".

---

## 1. Chốt cơ sở: không có bug tracker

Robot đứng yên, nhiễu tắt — mọi hình học:

```
isolated_object  still  off   240 record   raw p50 0.000   p99 0.000
                                            exceedance > 0.1 m/s: 0.0%
straight_wall / corner / warehouse: KHÔNG track nào được tạo
```

Raw fit **đúng bằng 0**. Thế giới đứng yên, cảm biến hoàn hảo, tracker
im lặng. Mọi thứ sau đây là phản ứng với một nguồn thật, không phải lỗi
số học.

---

## 2. Phát hiện chính: **hình học** quyết định, không phải độ phân giải

Cùng ego-motion (chạy thẳng), cùng cảm biến **hoàn hảo** (nhiễu tắt),
chỉ khác hình học:

```
tỉ lệ raw fit vượt 0.1 m/s
                       72 tia   144 tia   271 tia
isolated_object          9.7%      0.0%      0.0%
warehouse               84.3%     83.1%     84.6%
```

Một vật cô lập gọn gàng cho vận tốc ma **gần bằng 0** ở mọi độ phân
giải. Nhà kho cho **84%** raw fit vượt 0.1 m/s, và tỉ lệ đó **không đổi
theo độ phân giải**.

Cùng tracker, cùng cảm biến, cùng chuyển động. Khác nhau: có tường và kệ
hay không.

---

## 3. Sàn vận tốc **không phải** cổng đang gánh việc

Phân rã lý do mỗi record bị đưa về 0 — nhà kho, đứng yên + nhiễu:

```
rays   coasting  warmup  floored   kept
  72     84.7%     6.9%     1.9%    6.5%
 144     77.6%     4.3%     4.7%   13.4%
 271     72.7%     3.8%     3.4%   20.2%
 360     71.9%     4.8%     2.8%   20.4%
```

**Sàn loại được 2–5%.** Thứ giữ cho tracker im lặng là `coasting` —
track không được nhìn thấy ở frame đó — chiếm 72–85%. Nói cách khác:
`dwa_predictive` hiện an toàn **nhờ tri giác kém**, không nhờ cổng lọc.

Và khi độ phân giải tăng, coasting giảm (track được thấy thường xuyên
hơn) ⇒ nhiều record sống sót hơn ⇒ ảo tăng. Đó là cơ chế thật của Q0.

---

## 4. Nơi sàn thất bại, nó thất bại vì **tụt lại**, không vì sai loại

Nhà kho, chạy thẳng, **nhiễu tắt**:

```
rays    floor   raw p50   floored     kept
  72    0.270     0.221     38.6%    22.9%
 144    0.143     0.166      1.3%    67.5%
 271    0.076     0.158      0.0%    70.5%
 360    0.058     0.163      0.0%    71.2%
```

Sàn tụt **4.7×** (0.270 → 0.058); biên độ ảo chỉ tụt **1.35×**
(0.221 → 0.163). Ở 271 và 360 tia sàn loại **đúng 0%**, và **71% số
track-frame báo vận tốc giả với một cảm biến hoàn hảo**.

Đây là bằng chứng trực tiếp cho nghi vấn nêu ở Q0: số hạng `reach·Δθ`
mô hình hoá sai đại lượng. Nhưng nó **không** phải kết luận cuối, vì mục
3 cho thấy sàn chưa bao giờ là cổng chính.

---

## 5. Cụm sống sót trông như thế nào — và nó chỉ đúng thủ phạm

Geometry của cụm mà vận tốc ma **lọt tới hàm cost**:

```
                                 width  straightness  points
warehouse    chạy thẳng, off      1.14–1.28   0.56–0.62   11–15
isolated_object  chạy thẳng, off  0.62–0.78   0.15–0.25    5–13
```

`cluster_straightness = 0.08` là ngưỡng phán "đây là tường". Cụm sống
sót ở nhà kho có residual **0.56–0.62** — cao gấp 7 lần ngưỡng, nên test
tường **không bao giờ kích hoạt**.

Một mặt kệ phẳng, **không nhiễu range**, phải có residual ≈ 0. Residual
nửa mét nghĩa là cụm đó **trải qua nhiều hơn một bề mặt**. Đến đây thì
chắc chắn.

**Nhưng cơ chế cụ thể thì CHƯA xác định, và hai quan sát bác bỏ giả
thuyết đầu tiên của tôi.**

Giả thuyết đó là: ngưỡng tách cụm quá rộng (≈1 m ở tầm 3.5 m) nên gộp
mặt kệ với nền phía sau. Ngưỡng tách tỉ lệ `Δθ`, nên ở 360 tia nó chặt
gấp 5 lần (≈0.2 m). Nếu gộp-do-ngưỡng là cơ chế thì `straightness` phải
giảm mạnh theo độ phân giải. Đo được:

```
straightness của cụm sống sót, nhà kho, chạy thẳng, nhiễu tắt
  72 tia 0.382    144 tia 0.620    271 tia 0.558    360 tia 0.586
```

Không đổi. Giả thuyết sai.

Quan sát thứ hai, mạnh hơn: **hai hình học tổng hợp cho 0 ảo** dưới cùng
chuyển động và cùng cảm biến hoàn hảo —

```
straight_wall  chạy thẳng, off:  23 record, raw toàn 0.000
corner         chạy thẳng, off:  24 record, raw toàn 0.000
warehouse      chạy thẳng, off:  83 record, raw p50 0.221, 22.9% sống sót
```

`corner` **có góc tường** và vẫn không sinh ảo. Nên giả thuyết thay thế
("cụm trải qua một góc") cũng chưa được dữ liệu này chống lưng.

Có thứ gì đó trong nhà kho thật mà ba hình học tổng hợp không tái tạo —
mật độ kệ, khoảng cách gần, nhiều bề mặt cùng lúc trong tầm, hoặc thứ
khác. **Chưa biết nó là gì**, và một bản sửa dựng trên phỏng đoán ở đây
sẽ là bản sửa nhắm sai chỗ.

Đây là việc của R1b: dump geometry điểm thật của các cụm sinh ảo sống
sót trên chính bản đồ nhà kho, thay vì suy từ ba con số tổng hợp.

---

## 5b. R1b — nhìn thẳng vào cụm, và cơ chế hiện ra

`scripts/diagnose_phantom.py --dump`, nhà kho, nhiễu tắt, chạy thẳng.
Điểm quét thật của cụm sinh ảo mạnh nhất (72 tia):

```
robot (3.86, 3.00, 0.000 rad)   reach 4.13 m   out_speed 0.436   tia 44-48

  (7.438, 6.000)   range 4.667   bearing 40°
  (6.862, 6.000)   range 4.243   bearing 45°
  (6.380, 6.000)   range 3.916   bearing 50°
  (6.000, 6.053)   range 3.727   bearing 55°
  (6.000, 6.702)   range 4.275   bearing 60°
```

Ba điểm đầu nằm đúng trên `y = 6.000`. Hai điểm cuối nằm đúng trên
`x = 6.000`. **Đây là một góc vuông của kệ tại (6.000, 6.000)**, và
LiDAR quét liên tục qua nó.

Bậc range lớn nhất giữa hai tia kề là 0.55 m; ngưỡng tách ở tầm 4 m với
72 tia là `3.0 · 4 · 0.0873 + 3·0 ≈ 1.05 m`. **Không đủ để tách.** Một
cụm, hai mặt phẳng.

Và quỹ đạo centroid của track đó:

```
t=3.50  (6.326, 6.372)      ...      t=4.20  (6.536, 6.151)
```

Dịch chuyển 0.305 m trong 0.70 s = **0.436 m/s** — khớp đúng
`out_speed`. Robot đi `+x` ở 0.5 m/s; càng đi thì thấy nhiều mặt `y=6`
hơn và ít mặt `x=6` hơn, nên **centroid của hợp hai mặt trượt dọc góc**.

**Điều nguy hiểm nhất: nó trơn tru.** Centroid đi thẳng, đều, không
nhiễu. Least-squares trên 15 khung cho ra một vận tốc **ổn định và tự
tin**. Trong bản thân tín hiệu vận tốc **không có gì** phân biệt nó với
một vật thật đang đi 0.436 m/s. Không sàn, không làm mượt, không
confidence tính từ vận tốc nào tách được hai thứ đó.

Chữ ký nhất quán trên **toàn bộ** cụm sống sót, cả 72 lẫn 271 tia:

```
residual đạt đỉnh ở giữa cụm   peak@ 0.40–0.59
path/chord                      1.20–1.41
số cụm lân cận trong 2.5 m      0
```

Đối chứng: `isolated_object` — vật tròn, cụm cong đều — cho ảo gần bằng
0. Nên `path/chord` là biến phân biệt được: góc gãy cho 1.2–1.4, cung
tròn thoải cho ≈ 1.0.

**Kết luận cơ chế:** cụm **trải qua một góc** vì không có bậc range nào
đủ lớn để tách hai mặt. Centroid của cụm gãy là thuộc tính của tỉ lệ
nhìn thấy giữa hai mặt, và tỉ lệ đó thay đổi trơn tru khi robot đi.

**Sửa ở đâu:** tách cụm tại **chỗ đổi hướng bên trong nó**, trước bước
phân loại. Tách xong thì mỗi chân là một mặt phẳng dài và thẳng — test
tường **hiện có** loại được cả hai, không cần họ ngưỡng mới nào.

Điều này sửa cả đặc tả Q2b: nó đang hỏi *"các cụm lân cận có nối tiếp
cùng đường thẳng không"* (giữa các cụm). Cái cần là *"chính cụm này có
phải một đường thẳng không"* (trong một cụm). Đơn giản hơn hẳn.

---

## 5c. Bản sửa đã được xây, đo, và **thu hồi**

Đã hiện thực `_split_at_corners` (bước Ramer–Douglas–Peucker) với ba
điều kiện: độ lệch vượt mức một mặt phẳng có thể tạo ở tầm đó; hai chân
hướng khác nhau; và **cả hai chân tự nó thẳng**.

Điều kiện thứ ba không phải trang trí — bỏ nó thì **đĩa tròn bị cắt đôi
ở 271 và 360 tia**: mặt nhìn thấy của đĩa lệch khỏi chord cỡ bán kính
của chính nó, nhiều hơn góc, và hai chân của nó cũng gặp nhau ở góc
rộng. Đúng thất bại đang sửa, tái sinh bởi chính bản sửa.

Trên **hình học sạch** bản sửa chạy đúng hoàn toàn:

```
CORNER   72 tia không tách (giới hạn 3 tia), 144/271/360 tách đúng 1 lần
SHALLOW  không bao giờ tách
WALL     không bao giờ tách
DISC     không bao giờ tách
```

**Trên bản đồ thật thì không có tác dụng:**

```
phantom_rate  trước → sau        vel_out  trước → sau
  72:  14.17% → 14.18%             1.1% → 1.1%
 144:  78.56% → 78.49%             3.5% → 3.3%
 271:  97.52% → 97.51%             3.5% → 2.1%
 360:  99.19% → 99.19%             4.2% → 2.4%
```

Ảo không đổi; phát hiện thật giảm. Splitter **có** chạy (165–222 lần
trên 240 frame) — nhưng chạy trên những cụm khác, không phải cụm sinh
ảo.

### Vì sao — và đây là phần đáng giữ lại

Đo lý do bị chặn trên chính các cụm sinh ảo:

```
 rays  pts  resid  tol_main  angle   legL   legR   verdict
   72    6  0.702     0.479   1.30  0.000  0.209  chân cong
   72    4  0.512     0.513   1.56  0.000  0.000  resid<=tol   (trượt 0.001)
  271    6  0.233     0.163   1.42  0.088  0.000  chân cong
  271    5  0.162     0.165   1.23  0.228  0.000  resid<=tol   (trượt 0.003)
  271    7  0.284     0.160   1.39  0.148  0.000  chân cong
```

Cả hai điều kiện đều **sát vạch**. Nhưng nới ra thì:

```
tol=1.5 leg=0.08   CORNER [0,1,1,1]   DISC [0,0,0,0]
tol=1.0 leg=0.15   CORNER [0,1,1,1]   DISC [0,1,1,1]
tol=0.8 leg=0.15   CORNER [0,1,1,1]   DISC [0,1,1,3]
```

Chân góc thật ở nhà kho có tỉ lệ cong **0.088–0.228**; chân đĩa tròn
**0.207**. **Chồng lấn.** Không tồn tại điểm vận hành nào vừa bắt được
góc thật vừa tha vật tròn.

Lý do gốc: mỗi đặc trưng chỉ được **3–7 tia** lấy mẫu. Khớp "hai đoạn
thẳng" vào 6 điểm mà một chân chỉ có 2–3 điểm không phải một phép đo có
ý nghĩa thống kê. Chữ ký hình học tồn tại; cảm biến không đủ độ phân
giải để đọc nó.

### Quyết định

**Thu hồi code sản phẩm** (dev chốt 16-08). Không ship thứ tốn hiệu
năng mà lợi ích đo được bằng 0. Giữ lại: `scripts/diagnose_phantom.py`,
hai note này, và phần plan cập nhật.

Đây đúng "khả năng phải chấp nhận" mà plan đã ghi trước ở §Q0-KQ.4 —
giờ nó là số đo chứ không còn là dự đoán: **`_is_free_standing` đang
giải sai bài toán phân biệt bề mặt với vật, và ở độ phân giải này bài
toán đó không giải được bằng hình dạng.**

---

## 6. Trả lời ngã ba — **không nhánh nào trong hai nhánh tôi đặt ra**

Tôi đã đặt: *"per-track không đổi ⇒ lỗi số lượng track, Q2b còn cửa"*
so với *"per-track cũng tăng ⇒ sàn sai bản chất, thiết kế lại sàn"*.

Đo xong: **sàn không phải cái cần sửa, nhưng cũng không phải vì nó
đúng.** Nó chỉ chưa bao giờ là cổng chính (mục 3), và không một sàn vô
hướng nào cứu được một cụm mà centroid vốn vô nghĩa (mục 5).

Hai giới hạn cứng của hướng "thiết kế lại sàn":

- **Ảo do nhiễu range đạt p99 = 8.6 m/s** (đứng yên + nhiễu, 72 tia).
  Không sàn hợp lý nào chặn được — chặn được thì cũng chặn luôn mọi
  traffic thật.
- **Ảo do chuyển động toàn dưới 0.6 m/s** (exceedance tại 0.6 m/s =
  0.0% ở mọi độ phân giải, nhà kho, nhiễu tắt). Một sàn 0.6 m/s sẽ dọn
  sạch nhóm này — nhưng crosser thật đi **0.8 m/s**, biên còn 0.2 m/s,
  quá mỏng để gọi là ràng buộc.

---

## 7. Hệ quả: **Q2b sống lại, vì một lý do khác**

Lập luận cũ cho Q2b: độ phân giải mịn làm **tường vỡ vụn** thành mảnh
hẹp lọt qua test bề rộng.

Đo được: ở **mọi** độ phân giải, vấn đề là **gộp** nhiều bề mặt thành
một cụm lọt qua test độ thẳng. Ngược chiều với lập luận cũ, cùng một
chỗ hỏng: **`_is_free_standing` nhận vào những thứ không phải vật**.

Nên hướng sửa là **khâu nhận cụm**, không phải sàn:

1. Ngưỡng tách cụm (`cluster_gap_factor = 3.0`) quá rộng ở tầm xa —
   gộp mặt kệ với nền phía sau.
2. Test tường theo **chuỗi cụm** (Q2b như đã đặc tả) tấn công đúng cụm
   gộp này.
3. `clipped` (Q3) cùng họ vấn đề.

Sàn giữ nguyên vai trò hiện tại: lớp chặn cuối, không phải lớp chính.
Việc sửa `reach·Δθ` vẫn đáng làm nhưng **không** là điều kiện tiên
quyết, và một mình nó không cứu được gì.

---

## 8. Cái note này không kết luận

- Không nói `dwa_predictive` nên rút. Nhánh (c) của Q4 chưa chạy.
- Không đo với vật cản **thật sự chuyển động** — mọi cảnh đều tĩnh. Câu
  "sửa khâu nhận cụm có làm tăng phát hiện thật không" là câu của R3.
- Một seed (1000), 12 s mỗi ô. Đủ để tách nguồn vì các hiệu ứng chênh
  nhau hàng chục lần, **không** đủ để chốt giá trị ngưỡng nào.
- `localization_drift_m = 0` ở mọi hàng. L17 vẫn treo, và nó là nguồn
  ảo thứ tư chưa được đo ở đây.

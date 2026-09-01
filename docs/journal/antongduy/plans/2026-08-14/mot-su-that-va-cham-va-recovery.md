# Kế hoạch — miền khả thi cứng dùng chung, inflation theo bậc, và recovery

**Trạng thái:** **đã duyệt 14-08** (sáu quyết định ở mục 8) · **pha
riêng**, không nhét vào `vung-cam-va-kha-nang-phuc-hoi.md` cùng ngày —
phiên lập kế hoạch khác, phạm vi khác, và pha này **thay thế một phần
việc pha kia vừa làm**

**Nền:**
`docs/antongduy/notes/2026-08-13/tongduyan_hai-vung-cam-mot-con-robot.md`
· `docs/antongduy/reports/2026-08-14/tongduyan_b1-bong-bong-thoat.md`

---

## 0. Vì sao có pha này

Chuỗi nhân quả **đã đo được**, không phải suy đoán:

1. Hai tầng giữ **hai vùng cấm khác nhau** quanh cùng một vật cản —
   0.31 m (bộ điều khiển, hình học liên tục) và 0.61 m (bộ lập kế hoạch,
   ô lưới). Toàn bộ chênh lệch là số hạng lượng tử hoá lưới.
2. Robot đỗ ở nơi **chính nó cho là hợp lệ**, nằm sâu trong vành cấm của
   planner. Lưới **nhị phân** ⇒ A* không bước nổi một ô ⇒ `"no path"`,
   55 lần giống hệt nhau.
3. **B1** giải phóng một bong bóng quanh robot. Sửa được triệu chứng.
4. Nhưng B1 **không trung lập giữa hai họ planner**: RRT* tối ưu độ dài,
   khai thác bong bóng triệt để, trả về đường cách xe đẩy **0.13 m** —
   *dưới* ngưỡng 0.31 m mà DWA bị cấm đi. A* đi từng ô nên vô tình đi
   vòng rộng (0.59 m) và qua được.
5. Rà lại trong lúc bàn thiết kế, tìm thêm: **an toàn phanh hiện không
   phải một bảo đảm** — xem 1.5, có va chạm tái hiện được.

**B1 là một cái vá cho tính nhị phân của lưới.** Pha này gỡ nguyên nhân,
và **xoá B1**.

Một quan sát riêng, cũng đo được:

> Replan mà không có recovery chỉ là **hỏi lại đúng câu hỏi cũ**. Kẹt →
> replan → cùng một lưới → cùng một câu trả lời. Bản sửa "thử lại tới hết
> timeout" khiến nó không chết ngay, nhưng vẫn là 10 lần hỏi giống nhau.

---

## 1. Ba lớp biên, và hợp đồng giữa hai tầng

### 1.1. Ba lớp

| Lớp | Ý nghĩa | Cứng/mềm | Nguồn |
|---|---|---|---|
| **1. Collision footprint** | Chắc chắn va chạm hình học | **Cứng** | Robot / engine |
| **2. Safety envelope** | Bù sai số định vị, trượt bánh, và **ràng buộc phanh** | **Cứng** | **Deployment** |
| **3. Comfort / preference** | Muốn đi thoáng hơn | **Mềm** | Candidate / config |

Điểm mấu chốt: **"ai sở hữu" và "cứng hay mềm" là hai trục khác nhau.**
Mâu thuẫn trong bản trước sinh ra vì một con số (`safety_margin`) làm cả
hai việc — vừa là tham số candidate, vừa là ngưỡng từ chối cứng.

**Sai của tôi ở bản trước:** tôi kết luận ngưỡng cứng nên hạ về
`robot.radius`. Sai. Dự án này khai LiDAR noise, localisation drift và
wheel slip, nên bán kính hình học **không phải** biên an toàn thật — tôi
đã đánh đồng *"cứng"* với *"hình học"*.

### 1.2. Hợp đồng L1–L4

| | luật |
|---|---|
| **L1** | Global chỉ được trả về đường **nằm trong miền khả thi cứng** mà local có thể thực thi |
| **L2** | Local được thận trọng hơn bằng cách **chấm cost cao hơn**, nhưng **không được âm thầm thu hẹp miền khả thi cứng** bằng tham số candidate mà global không biết |
| **L3** | Mọi tầng dùng chung **collision footprint** và **safety envelope** chung nếu có |
| **L4** | Test tích hợp chạy **cả** `astar+dwa` **và** `rrtstar+dwa`; đường của global phải **vượt qua validator khả thi của local** |

```
Miền khả thi CỨNG   : chung giữa global và local
Ưu tiên/xếp hạng MỀM: được phép khác nhau
```

L1 và L2 **không còn kéo nhau**, vì sự thận trọng thêm của local nằm ở
tầng **mềm** và không thu hẹp miền cứng.

**L1 chính là luật B1 vi phạm**, và **L4 chính là hàng rào lẽ ra bắt được
nó**: B1 nới lớp đệm cục bộ, RRT* khai thác chỗ nới và trả về đường
0.13 m — global đưa local một con đường local **bị cấm đi**.

### 1.3. Lượng tử hoá lưới **không thuộc lớp nào**

`√2 × resolution` = **0.354 m** ở lưới 0.25 m — **lớn hơn cả localisation
drift**. Nó không phải hình học robot, không phải bất định cảm biến,
không phải sở thích. Nó là **tạo tác của biểu diễn**.

Nguyên tắc:

- Miền khả thi cứng định nghĩa **liên tục**.
- Lưới là **xấp xỉ bảo thủ** của nó; phần bảo thủ dư ra do lượng tử hoá
  vào **chi phí mềm**, **không vào cấm**.
- **Validator của L1/L4 chạy trên miền liên tục**, không chạy trên lưới —
  kiểm trên lưới sẽ trộn lẫn *"không khả thi"* với *"lưới thô"*.

Để lượng tử hoá cấm cứng là quay lại đúng con bug ban đầu, chỉ khác là có
tên gọi đẹp hơn.

### 1.4. `safety_margin` hiện tại là **một vi phạm L2 đang tồn tại**

```python
safety_margin: float = Field(
    default=0.05, ge=0, description="Extra metres required beyond the robot radius."
)
```

Mô tả **không nói vì sao** — không nói bù nhiễu, không nói thích thoáng.
Ý định chưa từng được ghi. Nhưng vị trí thì nói rõ:

| | hiện tại |
|---|---|
| Sở hữu | `DWAConfig` → **lớp 3** (candidate) |
| Hành vi | `if clearances[index] <= keep_out: continue` → **cứng** |

Tức **một tham số candidate đang âm thầm thu hẹp miền khả thi cứng** —
đúng thứ L2 cấm.

**Cách sửa: tách đôi, không chọn một lớp.**

- **Phần cứng → lớp 2, *suy ra* từ thứ deployment đã khai.**
  `localization_drift_m` + đóng góp của `wheel_slip_fraction` là **sai số
  vị trí** — đúng thứ envelope cần bù. Deployment khai sẵn rồi, nên
  **không thêm một "con số do người chọn" nào**.
- **Phần mềm → ở lại lớp 3.** *"Muốn thoáng thêm 5 cm"* vẫn là lựa chọn
  hợp lệ của ứng viên và vẫn phân biệt được hai ứng viên — bằng **cost**,
  không bằng thu hẹp miền khả thi.

**Phản biện một mục trong lớp 2: quãng phanh không nên là hằng số tĩnh.**

`v_max` 0.8 m/s, `a_max` 0.5 m/s² ⇒ quãng phanh **0.64 m**. Gộp vào
envelope tĩnh:

```
0.26 (radius) + 0.10 (drift) + 0.64 (phanh) = 1.00 m
```

so với inflation hiện tại 0.61 m. Robot **bò 0.1 m/s** qua khe hẹp sẽ bị
cấm y như robot **lao 0.8 m/s** — trong khi quãng phanh ở 0.1 m/s chỉ là
**0.01 m**.

Quãng phanh **phụ thuộc tốc độ**; một lưới tĩnh không diễn đạt được nó.
Nên: envelope tĩnh bù **bất định vị trí**; ràng buộc phanh là **ràng buộc
động**, thuộc 1.5.

### 1.5. Admissible stopping — bảo đảm đang **thiếu**, có va chạm tái hiện được

Hiện thực **có** một tiêu chuẩn mang tên admissibility, nhưng nó **đo sai
khoảng cách**:

```python
# "never travel faster than the robot can brake before the end of the path"
remaining = hypot(self._path[-1] - state.pose)      # <- ĐÍCH
stopping_limit = sqrt(2 * a_max * remaining)
```

Công thức gốc (Fox–Burgard–Thrun 1997) dùng `dist(v, ω)` = khoảng cách
tới **vật cản gần nhất trên đường cong đó**. Đây dùng khoảng cách tới
**đích**. Docstring tự khai mục đích: *"charges the goal at full speed and
orbits it"* — thiết bị **cập đích**, không phải thiết bị **an toàn**. Hai
thứ trùng nhau **chỉ khi đích là vật gần nhất**.

**Dynamic window không thay thế được nó.** Nó giới hạn `(v, ω)` theo cửa
sổ gia tốc, không trả lời *"tới đây rồi thì còn dừng kịp không"*. Và
rollout chỉ nhìn trong `horizon_seconds`: quỹ đạo **chưa va chạm trong
horizon** nhưng **sau horizon không còn đủ chỗ để dừng**.

**Đo trên `sudden_stop`, tắt hết nhiễu, chỉ đổi trọng số của candidate:**

| cấu hình | kết cục | gap nhỏ nhất | số bước không phanh kịp |
|---|---|---|---|
| `weight_clearance=1.2` (mặc định) | stuck | 0.701 m | 0 |
| `weight_clearance=0.3` | stuck | 0.152 m | 0 |
| `weight_clearance=0.0` | stuck | 0.152 m | 0 |
| **`weight_clearance=0`, `horizon 0.5`** | **collision** | **−0.002 m** | **23** |

Dòng cuối là **va chạm thật**: 23 bước liên tiếp ở tốc độ không phanh kịp,
tệ nhất **v = 0.80 m/s tại gap = 0.00 m** (cần 0.64 m để dừng).

**Kết luận, và nó nặng hơn 1.4:**

> An toàn hiện tại **không đến từ một bảo đảm**. Nó đến từ
> `weight_clearance` tình cờ đủ lớn để làm robot chậm lại — **một tham số
> của candidate**. `horizon` cũng vậy: nó quyết định rollout nhìn xa bao
> nhiêu, tức quyết định luôn khoảng phanh có được xét hay không.
>
> Miền khả thi cứng đang phụ thuộc **lớp 3**. Một ứng viên hợp lệ, chỉ
> bằng cách chỉnh trọng số của chính mình, tự nới miền cứng tới mức va
> chạm.

**Sửa:** `stopping_limit` lấy
`min(khoảng-cách-tới-đích, khoảng-hở-tới-vật-cản-trên-đường-cong-đó)` —
đúng công thức gốc. Nó biến admissibility từ một mẹo cập đích thành
**ràng buộc cứng thuộc lớp 2**, suy ra từ `a_max` deployment đã khai,
**không thêm knob nào**. Cộng `reaction_distance = v × control_period`
cho độ trễ một chu kỳ.

### 1.6. Cưỡng chế L2 bằng **cấu trúc**, không bằng kỷ luật

Hàm tính miền khả thi cứng chỉ nhận
`(footprint, envelope_của_deployment, a_max)` — **không nhận config của
candidate**. Một ứng viên muốn thu hẹp miền cứng sẽ **không có tham số
nào để làm**, thay vì "được yêu cầu đừng làm".

**Ước lượng:** 2 ngày (1 cho lớp + hợp đồng, 1 cho admissible stopping).

---

## 2. Inflation theo bậc, và điều kiện để nó có nghĩa

Thay lưới nhị phân bằng **trường chi phí**: gần vật cản thì đắt, xa thì
rẻ; **chỉ miền khả thi cứng mới là cấm tuyệt đối**.

Cái này **hoà tan con bug gốc**: robot nằm sâu trong vùng nới vẫn có
đường ra, chỉ là đắt. **Không cần bong bóng.**

Và nó **xoá luôn vấn đề công bằng** của B1: gradient không thiên vị họ
planner nào, vì cả hai đều **trả cùng một giá** cho việc đi sát.

### ⚠ Điều kiện, đã kiểm tra và hiện **chưa thoả**

```
A*    step cost = 1.0 / √2            -> thuần khoảng cách
RRT*  rewire theo euclidean_distance  -> thuần khoảng cách
```

**Không planner nào hiện đọc trường chi phí.** Nên đây **không phải** việc
sửa lớp lưới — nó là **sửa hàm mục tiêu của cả hai planner**:

- **A\***: `step_cost` thành `khoảng_cách × (1 + λ · cost(ô))`. Mã đổi
  nhỏ, nhưng đổi đường đi ⇒ đổi mọi số đo.
- **RRT\***: chi phí cạnh và điều kiện rewire phải **tích phân trường chi
  phí dọc cạnh**, không chỉ lấy độ dài. Phần **khó nhất** của cả pha.

  *(dev chốt)* **Chấp nhận triển khai với objective mới mà chưa xác minh
  các điều kiện bảo đảm tiệm cận tối ưu còn giữ được.** Ghi thành hạn chế
  **đã biết**, không phải thứ bị bỏ quên: từ đây **"RRT\*" trong dự án
  này là một biến thể cost-aware**, và mọi so sánh phải đọc nó như thế.
  Ghi vào `docs/KNOWN_LIMITATIONS.md` **và** vào mô tả stack trong
  registry, để nó lên tới `/candidates` chứ không nằm trong một comment.

- **DWA**: *(dev chốt)* **được phép đọc riêng** khoảng hở liên tục của
  nó — không bắt dùng chung trường chi phí. Đọc riêng là lựa chọn tốt vì
  bộ điều khiển phản ứng với **thứ cảm biến thấy ngay lúc đó**, còn
  trường chi phí là ảnh chụp lúc lập kế hoạch; ép chung sẽ làm local chậm
  một nhịp so với thế giới. Nhưng **phải thoả L1–L4**, và 1.4 + 1.5 là
  hai thứ phải sửa để điều đó đúng.

**λ (hệ số quy đổi chi phí ↔ khoảng cách) là một con số do người chọn.**
Không tránh được. Nên: khai trên **deployment**, giống nhau cho mọi ứng
viên, ghi vào manifest — đúng cách đã xử lý `sensor_noise` và
`replanning`.

**Xoá B1** ngay khi (2) chạy. Giữ cả hai là giữ một cái vá đã hết lý do
tồn tại, và cái vá đó có **thiên vị đã biết**.

**Ước lượng:** 2–3 ngày (RRT* chiếm phần lớn).

---

## 3. Recovery behaviours

Bốn hành vi, theo thứ tự leo thang. Ba cái đầu đổi **trạng thái thế
giới**, cái cuối đổi **niềm tin**:

| | hành vi | đổi cái gì | dùng khi |
|---|---|---|---|
| R1 | **Chờ** tại chỗ | thời gian trôi, vật cản động đi qua | vật chặn đang di chuyển |
| R2 | **Lùi** một đoạn an toàn | robot rời khỏi chỗ kẹt | đứng quá sát để xoay xở |
| R3 | **Xoay tại chỗ** | hướng, và **quét lại LiDAR ở góc khác** | tầm nhìn bị che |
| R4 | **Clear costmap** | niềm tin, không phải thế giới | nghi perception sai |

**R4 phải là cuối cùng, và phải có giới hạn.** Nó không đổi thế giới — nó
**xoá bằng chứng**. Một hệ clear costmap thoải mái là hệ tự cho phép mình
quên vật cản nó vừa nhìn thấy. Trong bối cảnh dự án này, đó là đường
thẳng dẫn tới va chạm mà **không cổng nào bắt được**.

**Recovery phải bị tính tiền**, đúng như replan: R1 tiêu thời gian mô
phỏng (timeout); R2/R3 tiêu thời gian **và** quãng đường
(`travel_time_s`, `path_length_m`). Không cần số hạng phạt riêng — cùng
lập luận đã dùng cho `replan_count`.

### Recovery thuộc về ai — **đã chốt: theo scope**

Cả hai cách đều có lý. Ngoài đời recovery *là* một phần của stack, và
stack có recovery tốt hơn *là* stack tốt hơn. Nhưng nếu một ứng viên được
lùi còn ứng viên kia không, phép so đo **recovery** chứ không đo planner.

Nền tảng đã có sẵn từ vựng: **`experiment_scope`**.

- `global_planner_selection` / `local_controller_selection` → recovery
  **dùng chung**, khai trên deployment, áp trên đường mọi ứng viên đều đi
  qua. Đúng lập luận HĐ-4.1.
- Muốn so recovery với nhau → **một scope mới** (`recovery_selection`),
  và khi đó recovery chuyển sang candidate.

**Ước lượng:** 2 ngày (R1–R3), +0.5 ngày R4 kèm giới hạn.

---

## 4. Thứ tự, và lý do

```
(1)  miền khả thi cứng dùng chung
(1b) admissible stopping
(2)  inflation theo bậc          ← rồi XOÁ B1
(3)  recovery behaviours
```

**Vì sao (1) trước hết:** nó là bất biến mà (2) và (3) đều dựa vào, và
(1b) chứa **lỗ hổng an toàn duy nhất có va chạm tái hiện được**.

**Vì sao (2) trước (3): công bằng trước năng lực.** Recovery dựng trên
một bộ khung **đã biết là thiên vị** giữa hai họ planner thì đáng giá kém
hơn recovery dựng trên bộ khung đã công bằng. Mọi số đo thu ở (3) trên
nền chưa sửa sẽ phải đo lại.

Cám dỗ làm ngược — (3) trước vì nó cho hiệu quả nhìn thấy nhanh nhất, và
R1/R2 chạy được ngay cả trên lưới nhị phân. Vẫn khuyên không.

---

## 5. Hệ quả hợp đồng

Cả (1), (2) và (3) **đổi *episode là cái gì***: thời gian, quãng đường,
khoảng hở, phơi nhiễm va chạm đều khác. Theo đúng luật đã áp cho
`sensor_noise` và `replanning`:

- `episode_context_id` **không** băm chúng ⇒ hai lượt chạy cùng seed, một
  bên có recovery một bên không, **dùng chung mọi context id** mà là hai
  thí nghiệm.
- ⇒ **`task_profile_id` mới** cho bất cứ deployment nào muốn đo dưới
  chúng. Không sửa tại chỗ; `same_deployment` đã chặn sẵn.
- ⇒ **manifest phải ghi** safety envelope, λ, profile chi phí, tập
  recovery và ngưỡng kích hoạt.
- ⇒ bump hợp đồng, cập nhật `manifest.schema.json`
  (`additionalProperties: false` đã bắt hụt một lần ở A3).

---

## 6. Thứ **không** bê từ Nav2

Cây hành vi mặc định của Nav2 đầy hằng số đã tinh chỉnh: thứ tự recovery,
số lần thử, timeout, bán kính clear. **Mỗi hằng số là một con số do người
chọn** — đúng loại núm vặn vừa gỡ khi bỏ `max_replans`, và đúng loại tạo
tác khiến một ứng viên lẽ ra thoát được bị chấm là hỏng.

Lấy **cấu trúc**; hằng số thì **khai trên deployment**, **giống nhau cho
mọi ứng viên**, **ghi vào manifest**.

---

## 7. Test bắt buộc

1. **Một sự thật**: test tham số hoá — không tầng nào tự khai lại
   footprint/envelope; cùng tư thế cho cùng phán quyết va chạm ở mọi tầng.

2. **Hàng rào L4 — quan trọng nhất.** Test tích hợp lấy **mọi** đường
   global trả về (kế hoạch đầu **và** mọi lần replan), kiểm **trên miền
   liên tục** (không trên lưới), và đánh dấu **"không lái được"** nếu nó
   ra ngoài miền khả thi cứng của local.

   Chạy cho **cả** `astar+dwa` **và** `rrtstar+dwa`. Đây đúng chỗ B1 hỏng
   và **chỉ lộ ra ở họ planner lấy mẫu**: A* đi vòng 0.59 m và qua được,
   RRT* cắt sát 0.13 m và không. **Một hàng rào chỉ chạy A\* sẽ xanh
   trong khi hệ đang hỏng.**

3. **Admissible stopping — test tính chất, không phải test tình huống.**
   `sudden_stop` với cấu hình mặc định **xanh** (an toàn nhờ trọng số,
   không nhờ bảo đảm), nên một test tình huống sẽ không bắt được gì.

   Tính chất, ở **mọi** bước:
   `v²/(2·a_max) + v·control_period ≤ khoảng hở tới vật cản gần nhất`.

   Ba ràng buộc:
   - chạy với **trọng số đối kháng** (`weight_clearance=0`, horizon
     ngắn) — một bảo đảm cứng phải đứng vững **kể cả khi mọi số hạng mềm
     bị tắt**, nếu không thì nó không phải bảo đảm cứng;
   - tính bằng **pose thật**, không phải pose robot tin là — với
     localisation drift robot phanh theo chỗ nó *nghĩ* nó đứng, và đây
     chính là chỗ envelope lớp 2 phải bù;
   - `weight_clearance=0, horizon=0.5` hiện cho **collision, min_gap
     −0.002 m, 23 bước không phanh kịp** — dùng làm ca hồi quy.

4. **Bất biến theo độ phân giải**: cùng cảnh ở 0.05 / 0.125 / 0.25 m phải
   cho cùng *kết luận* (không nhất thiết cùng đường). Con bug gốc sinh ra
   từ một đại lượng của lưới, nên hàng rào phải bắt đúng chuyện đó.

5. **Recovery đổi trạng thái, không đổi kết quả**: sau R1–R3 episode phải
   ở trạng thái **khác** (vị trí, hướng, hoặc thời gian) — một recovery
   không đổi gì là recovery vô nghĩa và phải đỏ.

6. **R4 có trần**: số lần clear costmap hữu hạn và **ghi lại**; không
   đường nào clear vô hạn.

7. **Tái hiện với đủ 7 luồng nhiễu của form** — ca gốc chỉ lộ ra ở đó.

---

## 8. Quyết định của dev — chốt 14-08

| # | câu hỏi | quyết định |
|---|---|---|
| 1 | Recovery theo scope hay phẳng? | **Theo scope** |
| 2 | DWA đọc chung trường chi phí? | **Đọc riêng được**, nhưng phải thoả L1–L4 |
| 3 | RRT* mất tiệm cận tối ưu? | **Chấp nhận**, ghi thành hạn chế đã biết và đưa lên UI |
| 4 | Footprint đa giác? | **Không ở MVP** — giữ hình tròn, nâng cấp sau |
| 5 | Ba lớp biên + L1–L4 bản mới | **Chốt** (mục 1) |
| 6 | Admissible stopping | **Chốt** — `min(đích, vật cản)`, có test tính chất riêng |

### Về (4): giữ hình tròn, nhưng **đừng khoá cứng vào hình tròn**

Đúng cho MVP — footprint đa giác kéo theo kiểm va chạm đa giác ở **mọi**
tầng, một pha riêng nữa.

Nhưng mục 1 nói *"lưới là biểu diễn **dẫn xuất** từ footprint"*. Viết
nguyên tắc đó dưới dạng **một hàm nhận footprint** ngay từ đầu — dù MVP
chỉ có một hiện thực hình tròn — thì lần nâng cấp sau là **thêm một hiện
thực**, không phải đi khái quát hoá lại bốn tầng. Chi phí thêm bây giờ
gần bằng không; chi phí khái quát hoá lần hai là đúng công việc mục 1
đang làm, làm lại lần nữa.

---

## 9. Tổng ước lượng

| pha | ngày |
|---|---|
| (1) miền khả thi cứng + hợp đồng L1–L4 | 1–1.5 |
| (1b) admissible stopping + test tính chất | 1 |
| (2) inflation theo bậc + xoá B1 | 2–3 |
| (3) recovery R1–R4 | 2.5 |
| hợp đồng + manifest + UI + test | 1.5 |
| **tổng** | **8–9 ngày** |

Nếu chỉ có một ngày: làm **(1b)** — nó là lỗ hổng duy nhất có **va chạm
tái hiện được**, và nó không bị xoá bỏ bởi bất cứ quyết định nào ở (2)
hay (3).

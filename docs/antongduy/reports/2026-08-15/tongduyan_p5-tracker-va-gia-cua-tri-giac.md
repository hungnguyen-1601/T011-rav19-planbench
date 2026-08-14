# P5 — tracker LiDAR, và giá của tri giác hoá ra là **toàn bộ**

**Ngày:** 2026-08-15
**Plan:** `docs/antongduy/plans/2026-08-14/du-doan-chuyen-dong-vat-can.md`, P5
**Trạng thái:** **P5 ĐÓNG bằng KẾT QUẢ ÂM** *(An chốt 15-08)* — tracker
xong, có test, và **không** giành lại được lợi ích của oracle. Test 7.2 đã
được **sửa trong plan** kèm số đo, không phải bỏ qua.

---

## 1. Việc của pha này

P4 chứng minh mô hình vận tốc hằng **đáng giá** khi tri giác hoàn hảo:
11/11 cặp bất đồng nghiêng về oracle, `p = 0.00049`. P5 phải giành lại
một phần của con số đó từ hai lần quét LiDAR liên tiếp — và **sai số ước
lượng là một phần của thuật toán**, không phải thứ được miễn.

Khoảng cách giữa hai đường **là** giá của việc phải tự ước lượng. Đó là
con số đáng giá nhất plan này sinh ra, và pha này sinh ra nó.

---

## 2. Đã xây gì

`packages/planning/planbench_planning/dwa_predictive/tracking.py`:

```
scan -> [1] phân cụm     tia liền kề, cắt khi bước nhảy tầm vượt ngưỡng
        [2] phân loại    tường / lát cắt của bề mặt lớn / vật thể rời
        [3] ghép cặp     tâm gần nhất trong cổng
        [4] ước lượng    bình phương tối thiểu trên cửa sổ vài khung
        [5] sàn nhiễu    dưới đó "chuyển động" chỉ là nhiễu
        [6] vòng đời     khởi động, mất dấu, mơ hồ
```

**Mọi chế độ hỏng trả về vận tốc 0.** Track không vận tốc đóng góp đúng
số 0 vào chi phí dự đoán, tức chính là `dwa`. Đoán bừa sẽ làm một
estimator hỏng **tệ hơn** không có estimator, và cả tầng lớp sinh ra để
điều đó không xảy ra được.

**Ngưỡng suy từ cảm biến, không từ scenario.** Không ngưỡng nào lấy từ
`DynamicObstacle.radius` — một ứng viên `lidar_only` đọc con số đó là
biết trước *trong phòng này có vật to cỡ nào*.

`association_speed_limit` là **của candidate**, không phải
`v_obstacle_max`: sai cái đầu thì ghép cặp hỏng và tracker thoái lui về
`dwa`; sai cái sau thì bảo đảm phanh thủng và robot đâm. Hai chế độ hỏng
khác nhau không dùng chung một trường.

---

## 3. Vận tốc ma: có thật, lớn, và **đo được**

Trên ba cảnh **hoàn toàn tĩnh**, tắt **mọi** luồng nhiễu:

| cảnh | trung vị | lớn nhất |
|---|---|---|
| `doorway` | 0.28 m/s | **1.01** |
| `static_obstacles` | 0.41 m/s | **1.27** |
| `narrow_corridor` | 0.04 m/s | 0.35 |

Traffic thật của thư viện chạy 0.6–0.8 m/s. **Vận tốc ma cùng bậc độ lớn
với tín hiệu thật.**

Không phải nhiễu cảm biến — không có nhiễu nào. Đó là **tâm cụm dịch khi
góc nhìn của robot đổi**, không phải khi vật thể đổi.

### Sàn nhiễu của plan **bằng đúng 0** ở đây

Plan §[2] khai:

```
v_floor ≈ (2·position_uncertainty_m + k·lidar_range_sigma_m) / window
```

Trên một deployment không nhiễu, **cả hai số hạng bằng 0**, nên sàn bằng
0 và **mọi** vận tốc ma ở trên lọt thẳng vào hàm chi phí.

Số hạng còn thiếu, và nó suy ra được chứ không phải chỉnh tay: một cụm
được lấy mẫu bằng **tia rời rạc**, nên tâm của nó dịch khi *tập tia chạm
vào nó* đổi — điều xảy ra mỗi khi robot di chuyển, **với cảm biến hoàn
hảo**. Bậc độ lớn là **một khoảng cách tia ở tầm đó**:

```
v_floor = (2·position_uncertainty + k·σ_range + reach·Δθ) / window
```

**Cửa sổ ước lượng chọn bằng đo, không bằng khẩu vị.** Quét 5/9/15/21
khung trên ba cảnh tĩnh cộng một cảnh có traffic thật:

| cửa sổ | ma p90 | thật p90 |
|---|---|---|
| 5 | 0.595 | 1.000 |
| 9 | 0.447 | 1.000 |
| **15** | **0.275** | 1.000 |
| 21 | 0.317 | 1.000 |

15 là chỗ cửa sổ ngắn hơn thôi mua được sự tách bạch và dài hơn bắt đầu
tốn thời gian phản ứng.

Sàn mới giúp `narrow_corridor` (95 → 31 track có vận tốc) nhưng **không
đóng được** `doorway` và `static_obstacles`.

### Test 7.2 của plan: **CHƯA ĐẠT** — trạng thái công việc, không phải diễn giải

Plan đòi *"cảnh tĩnh ⇒ quỹ đạo giống `dwa`"*. Với vận tốc ma 1.0 m/s thì
không. Tôi **không** chỉnh ngưỡng cho tới khi test xanh — đó đúng là
nước đi mà plan này đã bắt được năm lần. Thay vào đó:

- phát biểu lại test theo thứ **thật sự** được bảo đảm: provider rỗng ⇒
  lệnh giống hệt từng byte;
- **đặc tả hoá** hiệu ứng ma thành một phép đo có ghi số, không phải một
  số 0 được chỉnh tới.

**Và phải ghi rõ điều này ở mức quản lý công việc, không giấu trong một
đoạn giải thích:**

| | |
|---|---|
| Test 7.2 theo plan gốc | **KHÔNG ĐẠT ĐƯỢC** với thiết kế MVP |
| Yêu cầu đã bị đổi | **có, có chủ ý** — sửa thẳng vào plan, kèm số đo |
| P5 | **ĐÓNG bằng kết quả âm** (An chốt 15-08) |

Sửa nằm ở `plans/2026-08-14/du-doan-chuyen-dong-vat-can.md`, ngay dưới
test 7.2, để tiêu chí gốc và lý do đổi nằm cạnh nhau chứ không phải một
cái thay thế cái kia.

Bản thay thế **yếu hơn hẳn**: provider rỗng thì dĩ nhiên không có dự đoán
nào đi vào — nó không kiểm được điều 7.2 thật sự hỏi, là *tracker có phân
biệt nổi vật tĩnh hay không*. Câu trả lời đo được cho câu hỏi đó là
**không**.

Thứ vẫn đứng vững: **ràng buộc cứng không bị chạm**. Ma đi vào **chi
phí**, không bao giờ vào phép từ chối hay giới hạn phanh — đã kiểm bằng
mutation từ P3.

**Nhưng câu "nên tệ nhất nó chỉ làm robot đi kém, không làm nó đâm" là
SAI, và tôi đã viết nó ở bản trước.** Việc dự đoán không đụng miền cứng
chỉ chứng minh nó không **trực tiếp** nới một vận tốc đang bị cấm. Nó
**không** chứng minh một ước lượng sai không thể dẫn tới va chạm: chi phí
mềm vẫn chọn một lệnh khác, và lệnh khác đó có thể đưa robot vào một thế
xấu hơn ở bước sau, nơi miền cứng — vẫn đúng đắn — chỉ còn cách dừng lại.

Phát biểu đúng:

> Ước lượng sai **không nới ràng buộc cứng**, nhưng vẫn có thể làm hành
> vi và `collision_rate` xấu đi. Điều đó phải được **đo bằng benchmark**,
> không suy ra từ tầng lớp.

---

## 4. Phép đối chiếu cuối pha — và đây là kết quả của pha

`intersection`, 40 seed ghép cặp, cùng bộ cảnh của cổng P4:

```
dwa       collisions   2/40   successes  37/40
oracle    collisions   0/40   successes  38/40
tracker   collisions   2/40   successes  37/40

oracle    vs dwa: better 3, worse 0
tracker   vs dwa: better 0, worse 0

oracle và tracker đồng ý ở 37/40 seed
```

Tracker không tốt hơn `dwa` ở seed nào, và cũng không tệ hơn ở seed nào.

**Nhưng "0%" là một tỉ lệ trên mẫu số 3, và không được đọc như một kết
luận.** Oracle chỉ tạo ra khác biệt ở **3/40** seed; tracker lấy 0 trong
3 cơ hội đó. Với 0/3, khoảng bất định còn rất rộng — nó **không** chứng
minh tracker luôn thu lại 0%. Đọc nó như một **đếm**, không phải một phần
trăm:

> 3 cơ hội, tracker lấy 0.

Cần chạy trên toàn bộ 120 seed của cổng P4 — và tốt hơn là một miền seed
khác — trước khi phát biểu bất cứ điều gì mạnh hơn. Đang chạy;
`scripts/diagnose_tracker.py` đã commit nên phép so này **tái lập được**,
khác với bản trước chỉ tồn tại dưới dạng output dán vào report.

**Kèm một điều kiện phải nói:** lần chạy 40 seed ở trên diễn ra **trước**
khi sửa lỗi vận tốc stale (mục 4b). Nó đo một tracker phát vận tốc cũ
trong lúc mất dấu. Con số sau khi sửa có thể khác, theo chiều nào cũng
được — và đó là lý do lần chạy 120 seed mới là con số được ghi.

### 4a. Phép so 120 seed — **con số chính thức của pha này**

Chạy bằng `scripts/diagnose_tracker.py` (đã commit ⇒ tái lập được), tại
commit **`63c5d7d`** — tức **sau** bản sửa vận tốc stale ở 4b, nên nó đo
đúng hành vi điều khiển hiện tại. Commit `3b750bc` sau đó chỉ thêm event
log, không đụng điều khiển.

```
=== intersection, 120 paired seeds ===
  dwa       collisions    9/120   successes  107/120
  oracle    collisions    2/120   successes  112/120
  tracker   collisions    9/120   successes  107/120

=== discordant pairs against dwa ===
  oracle    better  11   worse   0
  tracker   better   0   worse   0

  seeds where prediction could help (oracle beat dwa) : 11
  ...of which the tracker also took                   : 0
```

| | dwa | oracle | tracker |
|---|---|---|---|
| collision | 9/120 | **2/120** | 9/120 |
| success | 107/120 | **112/120** | 107/120 |
| better vs dwa | — | **11** | **0** |
| worse vs dwa | — | 0 | 0 |

**11 cơ hội, tracker lấy 0.** Ở n = 40 con số là 3 cơ hội / 0 — quá mỏng
để kết luận. Ở **11/0** thì kết luận đứng được: tracker **không** giành
lại được lợi ích của oracle trên cảnh này, ở cấu hình cảm biến này.

Nó cũng **không tệ hơn** `dwa` ở seed nào — luật thoái lui hoạt động
đúng như thiết kế.

### 4a-2. Bộ đếm tracker, cộng dồn 120 episode

```
frames             29807
clusters_seen     129095
clusters_tracked    6631      <- 5.1% số cụm được coi là đáng theo dõi
associations        6027
coasting            9409      <- NHIỀU HƠN số lần ghép được
floored             3429
tracks_started       604
tracks_timed_out     584      <- 97% số track sinh ra rồi chết
ambiguous_drops        0
```

**Hai dòng nói hết câu chuyện.** `coasting` (9409) **lớn hơn**
`associations` (6027): track dành nhiều khung **không nhìn thấy** hơn là
nhìn thấy. Và 584/604 track sinh ra rồi hết hạn — gần như không track nào
sống đủ lâu để có ích.

### 4a-3. Điều bất ngờ: khi tracker **có** nói, nó nói khá đúng

Đo dọc theo một episode (seed 0):

```
số bước vật cản trong tầm LiDAR : 182
  ...có track nằm lên nó        :  37   (20%)
  ...báo vận tốc KHÁC 0         :   3   (1.6% của 182)
  trung vị |ước lượng − thật|   : 0.119 m/s   (tốc độ thật 0.800)
```

**Sai số 0.119 m/s trên 0.800 là ước lượng tốt** — 15%. Vấn đề **không
phải độ chính xác mà là tần suất**: tracker chỉ mở miệng ở **1.6%** số
bước mà vật cản nằm trong tầm.

Đây là chẩn đoán chính xác nhất của cả pha, và nó khác với cả hai lần
trước tôi đoán:

- **không** phải "không thấy vật cản" (thấy 20%);
- **không** phải "ước lượng sai" (khi nói thì sai 15%);
- mà là **phát hiện chập chờn ⇒ track chết trước khi kịp có ích**.

Nói cách khác: nếu sửa được tính liên tục của phát hiện, chất lượng ước
lượng **đã đủ tốt rồi**. Đó là thông tin đáng giá cho bất cứ ai làm tiếp
— và nó chỉ ra rằng nút thắt nằm ở **phân giải/phân cụm**, không ở khâu
ước lượng vận tốc.

### 4b. Một lỗi hành vi An bắt được: tracker **không** thoái lui về `dwa`

Module khai *"mọi bất định trả vận tốc 0"*. Code thì không. Khi mất ghép
cặp hoặc ghép mơ hồ, `_associate` chỉ tăng `track.misses`; `_velocity_of`
vẫn khớp bình phương tối thiểu trên lịch sử cũ và **trả vận tốc đó**, chỉ
hạ một trường `confidence` mà **không ai đọc** — chính comment trong code
thừa nhận *"does not gate anything yet"*, và planner quả thật không dùng
nó.

Hệ quả: một vật cản robot đã **thôi nhìn thấy** vẫn lái chi phí dự đoán ở
**toàn bộ cường độ**, tới tận `track_timeout` = 0.5 s. Đó là đúng thứ mà
cả module viết ra để không xảy ra.

**Vì sao test không bắt:** các test chỉ kiểm **bộ đếm** `ambiguous_drops`
và `tracks_timed_out`, không bao giờ kiểm **vận tốc trả ra** sau một lần
mất dấu. Lần thứ bảy trong plan này một phép đo xanh mà không đo thứ nó
khai.

**Đã sửa theo đúng đề xuất của An:**

- giữ `history` qua lần mất dấu ⇒ vật quay lại **không** phải warm-up lại;
- nhưng `misses > 0` ⇒ vận tốc trả ra **bằng 0**, `confidence` = 0.

Hai test hồi quy mới: một cho vận tốc stale không thoát ra, một cho việc
lịch sử vẫn sống để tái bắt không mất warm-up.

**Và điều này sửa lại mô tả phương án (a2) ở mục 6.** Bản trước tôi viết
"giữ track sống qua lúc mất dấu" như thể chưa có coasting. Thực ra đã có:
track sống 0.5 s, `history` được giữ, cổng ghép cặp nới theo thời gian
mất dấu. Vấn đề đúng là **hai** thứ khác: gap dài hơn 0.5 s giết track,
và trong gap ngắn vận tốc stale được dùng. Nửa sau vừa sửa. Nửa trước —
tái bắt sau gap dài — vẫn còn.

### Nguyên nhân — và **bản đầu của mục này tôi chẩn đoán sai**

Bản đầu viết: *"`cluster_min_points = 3` loại vật cản ở 3–5 m, nên tracker
không bao giờ thấy nó"*. Nghe hợp lý, và **sai** — đo lại với
`cluster_min_points = 2`:

```
cluster_min_points=3: collisions 1/25 (dwa 1/25)  better 0  worse 0
cluster_min_points=2: collisions 1/25 (dwa 1/25)  better 0  worse 0
```

Không đổi một seed nào. Ngưỡng điểm **không phải** chỗ thắt.

Đo thẳng vào đường đi của một episode — theo dõi vật cản thật suốt cả
episode và hỏi tracker nói gì về nó:

```
số bước AMR nằm trong tầm LiDAR        : 182
  ...trong đó có track nằm lên nó      :  37   (20%)
  tốc độ thật                          : 0.800 m/s
  trung vị |ước lượng − thật|          : 0.800 m/s
  ...trong đó ước lượng KHÁC 0         :   9/37 (24%)
```

Trung vị sai số **bằng đúng tốc độ thật** — nghĩa là ước lượng điển hình
là **0** ở chỗ đáng lẽ phải là 0.8.

**Chuỗi nhân quả thật, và nó có ba mắt chứ không phải một:**

```
phân giải 2 tia ở 4 m
   -> phát hiện CHẬP CHỜN: chỉ 20% số bước có cụm nằm trên vật cản
      -> track liên tục chết rồi sinh lại
         -> không bao giờ tích đủ velocity_min_samples = 3
            -> vĩnh viễn ở pha warm-up -> vận tốc 0 (76% số lần thấy)
               -> ~5% số bước có ước lượng dùng được (9/182)
                  -> không đổi được hành vi ở seed nào
```

Mắt xích quyết định **không phải** "không thấy vật cản" mà là **"thấy
không liên tục"**. Luật warm-up — đúng đắn và cố ý — biến sự chập chờn
thành im lặng hoàn toàn: mỗi lần mất dấu là một lần đếm lại từ đầu.

Phân giải vẫn là nguyên nhân **gốc** (2 tia ở 4 m thì cụm lúc có lúc
không), nhưng cơ chế khuếch đại là tương tác giữa **mất dấu** và
**warm-up**, và đó là thứ chỉ nhìn ra được bằng cách đo từng bước.

LiDAR: 72 tia trên 2π ⇒ **5.00°/tia**. `crossing-amr` bán kính 0.35 m:

| tầm | góc chắn | số tia |
|---|---|---|
| 2 m | 20.2° | 4.0 |
| 3 m | 13.4° | 2.7 |
| 4 m | 10.0° | 2.0 |
| 5 m | 8.0° | 1.6 |

**Bài học về phương pháp, lần thứ sáu trong plan này:** tôi công bố một
chẩn đoán rồi mới kiểm nó. Phép kiểm bác bỏ nó. Chẩn đoán đúng cần một
phép đo *dọc theo đường đi* chứ không phải một bảng hình học — và bảng
hình học thì trông thuyết phục hơn hẳn.

## 5. Kiểm chứng

| Việc | Kết quả |
|---|---|
| `tests/test_dwa_tracking.py` | **20 passed** — phân cụm, phân loại, ước lượng (7.1), năm dòng vòng đời, sàn nhiễu, tất định (7.6), đặc tả hoá vận tốc ma |
| `tests/test_dwa_predictive.py` · `test_dwa_oracle.py` | 48 passed |
| Đối chiếu tracker vs oracle (7.9b) | mục 4 |
| `ruff check .` | sạch |
| Full backend suite | **chưa chạy — chờ lệnh** |

Một lỗi hiện thực đáng ghi: phép phân loại `clipped` bị **ngược cực**.
Một vật thể đứng riêng **luôn** có hai bên là tia không trả về — đó chính
là dấu hiệu *bị chặn hai đầu*, tức đáng theo dõi — mà tôi lại đọc thành
"cụt". Nó loại đúng những vật đáng theo dõi nhất. Chín test bắt được.

---

## 6. Quyết định thuộc về An

Plan không có cổng ở P5, nhưng kết quả này có sức nặng của một cổng: nếu
tracker thu lại 0% thì **phép so P7 giữa `dwa` và `dwa_predictive` sẽ ra
phẳng**, và một tấm Decision Card nói *"hai ứng viên như nhau"* là một
tấm card đúng nhưng vô ích — nó không đo được ý tưởng, nó đo được cảm
biến.

| # | phương án | hệ quả |
|---|---|---|
| a | ~~Hạ `cluster_min_points` xuống 2~~ | **đã đo, không đổi gì** — 0 better, 0 worse. Không phải chỗ thắt |
| a2 | **Cho track sống qua lúc mất dấu** — giữ `velocity_min_samples` đã tích được thay vì đếm lại từ đầu | nhắm đúng mắt xích đã đo: 20% phát hiện nhưng chỉ 24% trong số đó có vận tốc. Rẻ, nằm trong `tracking.py`, và không đụng thế giới. Rủi ro: một track coasting lâu mang vận tốc cũ — phải giới hạn bằng `confidence` và `track_timeout` |
| b | **Khai LiDAR phân giải cao hơn** trong deployment dùng để đo | 0.35 m ở 4 m cần ~2° / tia, tức **180 tia**. Đổi thế giới ⇒ `task_profile_id` mới, và mọi số cũ đo lại. Nhưng nó biến câu hỏi thành *"dự đoán đáng không"* thay vì *"72 tia có đủ không"* |
| c | **Chạy P7 và công bố kết quả phẳng** | trung thực, rẻ, và plan đã nói trước rằng một card *"đừng dùng predictive ở deployment này"* là một card thành công. Nhưng nó công bố một giới hạn **cảm biến** dưới nhãn một giới hạn **thuật toán** |
| d | **Dừng plan** | oracle đã trả lời câu hỏi khoa học (dự đoán đáng giá); tracker trả lời câu hỏi kỹ thuật (không giành lại được ở cấu hình này). Cả hai đều là kết quả |

Khuyến nghị: **(a2) trước, rồi (b) nếu vẫn không đủ**. Đổi so với bản
trước của mục này: phép đo từng bước chỉ ra mắt xích là *mất dấu ⇒ đếm
lại warm-up*, và đó là thứ sửa được trong tracker mà không cần đổi cảm
biến. Chỉ khi (a2) vẫn không giành lại được gì thì kết luận "72 tia
không đủ" mới đứng vững. Lý do: kết quả hiện tại **trộn hai câu hỏi**
— *mô hình vận tốc hằng có đáng không* (P4 đã trả lời: có) và *72 tia có
đủ để ước lượng nó không* (P5 vừa trả lời: không). Công bố phép so trên
cấu hình 72 tia sẽ gán giới hạn cảm biến cho thuật toán, và đó là đúng
loại nhầm lẫn mà nền tảng này sinh ra để chặn.

Nếu An chọn (c) hoặc (d), tôi ghi kết quả âm đúng như nó là — plan nói rõ
kết quả âm là một kết quả.

---

## 7. Còn lại

- **Quyết định mục 6.**
- **`local_version` vẫn `"v1"`** → P6 việc 4. Nay hai controller dùng
  chung `dwa_core.py` **và** `dwa_predictive` có tracker riêng, nên món nợ
  này đã thành hiện thực.
- **Đăng ký registry + `CONTROLLER_CONFIGS`** → P6.
- **L8** (độ trung thực `kinematics.py`) và **§8 của plan** (bộ metric mục
  tiêu chĩa nhầm trục — P4 mục 7) vẫn treo.

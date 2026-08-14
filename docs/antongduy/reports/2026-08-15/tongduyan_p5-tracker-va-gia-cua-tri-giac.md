# P5 — tracker LiDAR, và giá của tri giác hoá ra là **toàn bộ**

**Ngày:** 2026-08-15
**Plan:** `docs/antongduy/plans/2026-08-14/du-doan-chuyen-dong-vat-can.md`, P5
**Trạng thái:** tracker xong và có test · **phép đối chiếu cuối pha cho kết
quả âm: tracker thu lại 0% lợi ích của oracle** — cần An quyết trước P6

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

### Test 7.2 của plan **không thể đạt** với thiết kế này

Plan đòi *"cảnh tĩnh ⇒ quỹ đạo giống `dwa`"*. Với vận tốc ma 1.0 m/s thì
không. Tôi **không** chỉnh ngưỡng cho tới khi test xanh — đó đúng là
nước đi mà plan này đã bắt được năm lần. Thay vào đó:

- phát biểu lại test theo thứ **thật sự** được bảo đảm: provider rỗng ⇒
  lệnh giống hệt từng byte;
- **đặc tả hoá** hiệu ứng ma thành một phép đo có ghi số, không phải một
  số 0 được chỉnh tới.

Thứ vẫn đứng vững: **ràng buộc cứng không bị chạm**. Ma đi vào **chi
phí**, không bao giờ vào phép từ chối hay giới hạn phanh — đã kiểm bằng
mutation từ P3. Nên tệ nhất một ước lượng hỏng làm robot **đi kém**, không
làm nó **đâm**.

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

**Tracker thu lại 0% lợi ích của oracle.** Nó không tệ hơn `dwa` ở seed
nào — luật thoái lui hoạt động — nhưng cũng không tốt hơn ở seed nào.

Và 37/40 đồng ý nghĩa là hai bên chỉ khác nhau ở **đúng 3 seed** mà oracle
giúp được. Tracker im lặng chính xác ở chỗ dự đoán có ích.

### Nguyên nhân: **tường phân giải cảm biến**, không phải lỗi chỉnh tham số

LiDAR: 72 tia trên 2π ⇒ **5.00°/tia**. `crossing-amr` bán kính 0.35 m:

| tầm | góc chắn | số tia | `cluster_min_points = 3` |
|---|---|---|---|
| 1 m | 41.0° | 8.2 | theo dõi |
| 2 m | 20.2° | 4.0 | theo dõi |
| **3 m** | 13.4° | **2.7** | **loại** |
| **4 m** | 10.0° | **2.0** | **loại** |
| 5 m | 8.0° | 1.6 | loại |
| 6 m | 6.7° | 1.3 | loại |

Robot cần phản ứng ở **3–5 m** — đó là nơi biên phanh và dự đoán có ý
nghĩa. Ở đúng dải đó vật cản rộng **2 tia**. Không tính được tâm, bề
rộng hay độ thẳng từ 2 điểm, nên mọi phép phân loại theo hình dạng là bất
khả ở đó.

Đây là giới hạn **vật lý của cấu hình cảm biến**, không phải ngưỡng đặt
sai. Một vật 0.35 m ở 4 m trên LiDAR 72 tia đơn giản là không đủ điểm để
nói nó là gì hay nó đi đâu.

---

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
| a | **Hạ `cluster_min_points` xuống 2** | 2 điểm là tối thiểu để có bất kỳ ước lượng bề rộng nào. Đang đo (chạy nền). Rủi ro: nhận thêm ma, và tâm của 2 điểm ở 4 m có lượng tử ±13 cm |
| b | **Khai LiDAR phân giải cao hơn** trong deployment dùng để đo | 0.35 m ở 4 m cần ~2° / tia, tức **180 tia**. Đổi thế giới ⇒ `task_profile_id` mới, và mọi số cũ đo lại. Nhưng nó biến câu hỏi thành *"dự đoán đáng không"* thay vì *"72 tia có đủ không"* |
| c | **Chạy P7 và công bố kết quả phẳng** | trung thực, rẻ, và plan đã nói trước rằng một card *"đừng dùng predictive ở deployment này"* là một card thành công. Nhưng nó công bố một giới hạn **cảm biến** dưới nhãn một giới hạn **thuật toán** |
| d | **Dừng plan** | oracle đã trả lời câu hỏi khoa học (dự đoán đáng giá); tracker trả lời câu hỏi kỹ thuật (không giành lại được ở cấu hình này). Cả hai đều là kết quả |

Khuyến nghị: **(b) rồi (c)**. Lý do: kết quả hiện tại **trộn hai câu hỏi**
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

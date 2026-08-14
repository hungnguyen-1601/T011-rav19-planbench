# P4 — oracle tri giác hoàn hảo, và cổng quyết định 2

**Ngày:** 2026-08-14
**Plan:** `docs/antongduy/plans/2026-08-14/du-doan-chuyen-dong-vat-can.md`, P4
**Trạng thái:** oracle xong · **cổng: luật đã khai TRƯỢT, nhưng luật đó
không đo được thứ đang xảy ra — cần An quyết**

---

## 1. Oracle để làm gì

`dwa_predictive` sẽ ước lượng vận tốc từ LiDAR, và **sai số ước lượng là
một phần của thuật toán**. Nên nếu phép so với `dwa` ra kết quả phẳng thì
có hai cách giải thích và không cách nào phân biệt được: *mô hình vận tốc
hằng không đáng gì ở đây*, hay *mô hình ổn nhưng tracker tệ*.

Oracle gỡ khả năng thứ hai bằng cách đưa cho controller đúng vận tốc mà
simulator đang dùng. Dự đoán đáng giá bao nhiêu thì **nhiều nhất** cũng
chỉ bằng chỗ này.

Đó là **cổng quyết định 2**, và là chỗ rẻ nhất để huỷ cả plan.

---

## 2. Oracle được biết **hiện tại**, không được biết **tương lai**

```
vị trí:   position_at(obstacle, t, seed)
vận tốc:  (position_at(t) − position_at(t − dt)) / dt      <- sai phân LÙI
```

Sai phân **một phía, nhìn về quá khứ**, có chủ đích. `position_at(t + ε)`
là đọc tương lai, và một oracle đọc tương lai thôi đo **tri giác** mà
chuyển sang đo **tiên tri** — khi đó khoảng cách giữa nó và tracker trộn
sai số ước lượng với sai số mô hình, không đọc được nửa nào.

**Ba pha quanh `stop_time`** (test 7.9a), và ranh giới là **quan sát**,
không phải **sự kiện**:

| pha | provider trả | oracle làm |
|---|---|---|
| `t < stop_time` | vận tốc trước-dừng, khác 0 | ngoại suy **xuyên qua** cú dừng |
| `t = stop_time` | vẫn đủ tốc độ (cửa sổ lùi phủ trọn đoạn đã đi) | theo con số đó |
| `stop_time < t < stop_time+dt` | **tắt dần** (cửa sổ ăn một phần cú dừng) | theo con số đó |
| `t ≥ stop_time+dt` | **0** | thôi ngoại suy |

Pha đầu chứng minh nó **không** đọc tương lai; pha cuối chứng minh nó
**có** biết hiện tại. Báo 0 ở pha cuối không phải vi phạm — vật đã đứng
yên trọn một `dt` và sai phân nói đúng điều đó; một tracker hoàn hảo cũng
kết luận vậy.

**Warm-up dùng chung luật với tracker:** `t < dt` ⇒ vận tốc 0. Chưa có
quá khứ để sai phân thì đoán từ một mẫu là **bịa**. Hai bên phải đồng ý ở
chỗ **cả hai đều không có thông tin**, nếu không khoảng cách giữa chúng
thôi là sai số ước lượng.

---

## 3. Không bao giờ thành candidate — bằng **cấu trúc**

| đường | vì sao bị chặn |
|---|---|
| Đăng ký registry | **không đăng ký nổi**: factory có chữ ký `config -> LocalPlanner`, không có scenario nào để đóng provider ground-truth vào |
| Ground truth vào `Observation` | `Observation` là hợp đồng "robot thấy gì" — test khẳng định tập trường của nó không đổi |
| Nhầm với candidate trong artifact | `name` là `dwa_oracle_predictive`, khác hẳn `dwa_predictive` |

Không có đường nào từ đây tới `/candidates`, Decision Card hay UI, và
không ai phải **nhớ** đừng tạo ra một đường như thế.

---

## 4. Kiểm tra cảnh trước khi chọn cảnh cổng

Plan yêu cầu cổng chỉ chạy trên cảnh **gần-hằng trong một prediction
horizon**. Tôi đo trực tiếp thứ quan trọng: **sai số của phép ngoại suy
vận tốc hằng sau 1.5 s** — chính là sai số mô hình mà oracle mang.

| cảnh | luật | sai số trung vị @1.5 s | dùng làm cổng? |
|---|---|---|---|
| `bidirectional_corridor` | waypoint | **0.000 m** | có |
| `intersection` | waypoint | **0.000 m** | có |
| `sudden_stop` | sudden_stop | 0.000 (max 1.497) | không — ca đối kháng |
| `crossing_obstacle` | periodic | **0.949 m** | **không** |
| `dynamic_warehouse` | hỗn hợp | 0.583–0.669 m, max **41 m** | **không** |

**`crossing_obstacle` đúng là cái bẫy plan đã cảnh báo**: nghe như ca cắt
ngang kinh điển, nhưng người đi bộ là **hình sin** chu kỳ 10 s và sai số
ngoại suy trung vị gần **một mét**. May là `intersection` đã sẵn là cảnh
cắt ngang **vận tốc hằng**, nên không cần dựng cảnh mới.

---

## 5. Cổng: luật đã khai, và kết quả

**Luật khai trước khi chạy**, viết thẳng thành hằng số trong
`scripts/diagnose_oracle.py` và **commit trước** lần chạy (`0f9641a`), để
"khai trước" là thứ đọc được từ lịch sử git:

> Đạt nếu **CI 95% bootstrap theo cặp** của trung vị Δ`travel_time` hoặc
> Δ`stop_and_go` **nằm hẳn dưới 0**, và không metric cổng nào (success,
> collision, near-miss) xấu đi. ≥20 seed mỗi cảnh, ghép theo seed, điều
> kiện trên **cả hai cùng tới đích**.

**Dự đoán ghi trước:** *"cải thiện travel-time trung vị 5–15% trên
`intersection`; gần như không gì trên `bidirectional_corridor`; không
metric nào xấu đi."*

**Kết quả (20 seed/cảnh):**

```
=== GATE bidirectional_corridor ===
  success_rate     dwa 0.000   oracle 0.000
  collision_rate   dwa 0.800   oracle 0.750
  near_miss_rate   dwa 1.000   oracle 0.800
  paired on 0 of 20 contexts where both reached the goal

=== GATE intersection ===
  success_rate     dwa 0.900   oracle 0.950
  collision_rate   dwa 0.050   oracle 0.000
  near_miss_rate   dwa 0.050   oracle 0.000
  paired on 18 of 20
  dtravel_time   median +0.000   95% CI [+0.000, +0.000]   no effect
  dstop_and_go   median +0.000   95% CI [+0.000, +0.000]   no effect

VERDICT: FAIL
```

**Theo luật đã khai: TRƯỢT.** Tôi ghi đúng như vậy và không đổi luật.

---

## 6. Nhưng luật đó **không thể** đo được thứ đang xảy ra

`+0.000` với CI `[+0.000, +0.000]` không phải "hiệu ứng nhỏ" — nó là
**giống hệt nhau**. Kiểm trực tiếp:

| cảnh | seed | dwa | oracle | quỹ đạo |
|---|---|---|---|---|
| `intersection` | 0, 1 | success 12.7 s | success 12.7 s | **giống hệt từng byte** |
| `crossing_obstacle` | 0, 1 | success 11.7 s | success 11.7 s | **giống hệt từng byte** |
| `crossing_obstacle` | 2 | **collision 5.5 s** | **success 13.6 s** | lệch từ bước 87 |

**Cơ chế:** dự đoán chỉ tác động khi sắp có va chạm. Trong đúng những
episode đó, `dwa` **hỏng**. Nên phép điều kiện *"cả hai cùng tới đích"*
**loại bỏ chính xác mọi episode mà can thiệp có tác dụng**, và để lại một
tập con mà trên đó hai bên chạy giống hệt nhau. Δ bằng 0 là **do cấu
trúc**, không phải do đo.

Plan §8 đã cảnh báo đúng chuyện này — *"điều kiện trên 'cả hai cùng thành
công' là chọn mẫu, và nếu hai ứng viên có success rate lệch nhau thì tập
giao không đại diện"* — nhưng cảnh báo đó nằm ở mục **báo cáo**, còn tôi
lại xây **tiêu chí đạt/trượt** trên chính tập bị chọn mẫu. Đó là lỗi
thiết kế cổng, của tôi.

**Số dưới đây là PILOT, không phải bằng chứng cổng.** Nó chạy bằng một
script tạm, **không có luật khai trước**, không có commit nào chốt
endpoint/thống kê/điều kiện PASS. Theo đúng kỷ luật mà chính report này
áp cho mọi thứ khác, nó **không được dùng làm bằng chứng**, và nó không
được dùng: vai trò duy nhất của nó là **ước lượng công suất** cho lần
khai lại (bao nhiêu cặp bất đồng ⇒ cần bao nhiêu seed). Bằng chứng chính
thức chỉ đến từ lần chạy có luật commit trước (mục 9b).

Pilot, 40 seed ghép cặp, tập không điều kiện:

| cảnh | collision | Δ | CI 95% | outcome đổi |
|---|---|---|---|---|
| `intersection` | 0.050 → **0.000** | −0.050 | [−0.125, +0.000] | **3/40** |
| `crossing_obstacle` | 0.275 → **0.200** | −0.075 | [−0.175, +0.000] | **3/40** |
| `bidirectional_corridor` | 0.875 → **0.800** | −0.075 | [−0.175, +0.000] | **3/40** |

Ba điều phải đọc cùng nhau:

1. **Hiệu ứng hiếm.** Outcome chỉ đổi ở **3/40 seed** (7.5%) ở cả ba
   cảnh. Trên 92.5% seed còn lại oracle làm **đúng không gì cả** — quỹ
   đạo giống hệt từng byte.
2. **Chưa có ý nghĩa thống kê** ở n = 40: mọi CI đều chạm 0 ở cận trên.
3. **Nhưng cận trên bằng đúng +0.000 ở cả ba cảnh**, nghĩa là **không một
   lần bootstrap resample nào** cho hiệu số dương. Chiều nhất quán, và
   chưa lần nào có hại.

Điểm 1 giải thích luôn điểm 2: một hiệu ứng chỉ xuất hiện ở 7.5% mẫu thì
n = 40 không đủ để chứng minh, dù nó có thật. Đây là bài toán **sự kiện
hiếm**, và CI bootstrap trên hiệu hai tỉ lệ là công cụ yếu cho loại đó.

Và đó chính là thứ duy nhất pilot được phép nói: *"thước cũ sai loại, và
cần khoảng 3x số seed"*. Nó **không** được phép nói *"dự đoán có tác
dụng"* — câu đó phải do lần chạy có luật khai trước trả lời.

## 7. Điều này **mâu thuẫn với tiền đề của plan**, và cần nói thẳng

Plan §10 quyết định 1 ghi: *"với quyết định này, `dwa_predictive` **không
an toàn hơn** `dwa`"*, và §8 xếp `stop_and_go_count` và `travel_time_s`
làm **mục tiêu**, còn `collision_count`/`near_miss_rate` chỉ là **ràng
buộc không được tệ đi**.

Phép đo nói **ngược lại**: dự đoán mua **an toàn**, và **không mua tốc độ
gì cả**.

**Điều đó có hợp lệ không?** Có. Miền cứng **không** bị nới — P3 khẳng
định tập `(v, ω)` bị từ chối và giới hạn phanh **bằng đúng** của `dwa`, và
tôi đã kiểm bằng mutation (đổi phép từ chối sang đọc khoảng hở dự đoán ⇒
test đỏ). Nên việc giảm va chạm đến từ **lái tránh**, không từ **được
phép đi vào chỗ cấm**. Đó là chi phí mềm làm đúng việc của nó.

Nhưng nó có nghĩa là **bộ metric mục tiêu của plan đang chĩa nhầm chỗ**.

---

## 8. Hai lỗi chọn cảnh của tôi, cả hai kiểm được trước khi chạy

1. **`bidirectional_corridor` có success rate 0.000 cho cả hai bên.** Một
   cảnh mà mọi episode đều hỏng thì không sinh nổi một cặp nào, nên nó
   đóng góp **0** vào cổng. Tôi đã kiểm sai số mô hình của cảnh nhưng
   **không kiểm cảnh có thắng nổi không**.
2. **`intersection` hầu như không cho dự đoán cơ hội tác động** — 18/20
   context hai bên chạy giống hệt. Tôi kiểm "cảnh có gần-hằng không" mà
   không kiểm "cảnh có **dịp** để dự đoán làm gì không".

Cùng một bài học đã lặp lại suốt plan này, lần thứ sáu: **một phép đo
trông sạch sẽ mà không đo thứ nó khai.** Lần này nó suýt làm huỷ cả một
plan.

---

## 9. Quyết định thuộc về An

Tôi **không** tự đổi luật cổng sau khi nhìn số — đó đúng là nước đi
HĐ-15.3 sinh ra để hỏi. Trình bày cả ba sự thật:

- **Theo luật đã khai: TRƯỢT.** Và luật đó **không thể** đo được hiệu ứng
  đang tồn tại, vì phép điều kiện loại đúng những episode có can thiệp.
- **Trên tập không điều kiện, n = 40: cũng chưa đạt ý nghĩa.** Chiều nhất
  quán ở cả ba cảnh, chưa metric nào xấu đi, nhưng CI đều chạm 0.
- **Hiệu ứng hiếm: 3/40 seed.** Đó là lý do n = 40 không kết luận được,
  không phải bằng chứng rằng hiệu ứng không có.

**Một phép kiểm phù hợp hơn cho sự kiện hiếm, và tôi khai rõ là nó
KHÔNG phải luật đã khai trước:** với kết cục nhị phân ghép cặp, thứ mang
thông tin là **các cặp bất đồng**, và phép kiểm dấu (sign test /
McNemar) dùng đúng chúng thay vì hoà tan chúng vào tỉ lệ. Nếu mọi cặp
bất đồng đều nghiêng về một phía thì `k` cặp cho `p = 0.5^k` một phía —
9 cặp cùng chiều đã cho `p ≈ 0.002`.

Con số cặp bất đồng theo chiều đang được đo (chạy nền). Nhưng **chọn phép
kiểm sau khi thấy dữ liệu là chọn mẫu ở tầng phương pháp**, nên nó chỉ
được dùng nếu An khai lại cổng và chạy lại — không được dùng để cứu lần
chạy này.

Ba đường đi, quyết định của An:

| # | phương án | hệ quả |
|---|---|---|
| a | **Dừng plan** theo đúng luật đã khai | trung thực với kỷ luật khai-trước. Cái mất: một hiệu ứng nhất quán về chiều, chưa lần nào có hại, bị bỏ vì đo bằng thước sai và bằng cỡ mẫu thiếu |
| b | **Khai lại cổng** — sự kiện hiếm, tập không điều kiện, sign test trên cặp bất đồng, **n ≥ 120** — commit luật **trước**, rồi chạy | giữ kỷ luật nếu lần trượt cũ ở mục 5 được giữ nguyên trong hồ sơ. ~3x số episode; ước lượng từ 3/40 thì n = 120 cho ~9 cặp bất đồng, đủ để `p ≈ 0.002` **nếu** chúng vẫn cùng chiều |
| c | **Đổi cảnh cổng** sang cảnh dự đoán có dịp tác động | chọn cảnh sau khi biết kết quả cũng là chọn mẫu; và không cảnh nào trong thư viện vừa gần-hằng vừa cho dự đoán nhiều dịp |

Khuyến nghị: **(b)**, và tôi muốn nói rõ vì sao nó không phải là "vặn
luật cho tới khi đạt". Luật cũ hỏng vì hai lý do **kiểm được trước khi
chạy** và cả hai là lỗi thiết kế của tôi: điều kiện trên "cả hai cùng
thành công" loại bỏ can thiệp, và CI bootstrap trên tỉ lệ là thước sai
cho sự kiện 7.5%. Sửa thước rồi chạy lại với luật khai trước là sửa lỗi
đo; nếu lần chạy mới vẫn trượt thì plan dừng, và lần đó sẽ là một câu trả
lời về **thuật toán** chứ không phải về **phép đo**.

Nếu An chọn (a), tôi ghi kết quả âm và dừng — plan nói rõ một kết quả âm
là một kết quả.

## 10. Một lỗi P1 phát hiện dọc đường: `RandomWalkMotion` **nhảy vị trí**

Trong lúc kiểm sai số mô hình từng cảnh, `dynamic_warehouse` cho sai số
tối đa **41 m** — vô lý với một vật cản khai 0.5 m/s. Truy ra:

```
t=13.50  đi 1.4075 m trong MỘT bước 0.05 s  ->  28.15 m/s
t=19.15  đi 1.1025 m                        ->  22.05 m/s
t= 4.10  đi 1.0750 m                        ->  21.50 m/s
```

**Nguyên nhân, không phải nhiễu mà là gián đoạn:** phép phản xạ ở
`max_radius` được quyết định từ **thời gian đã trôi *một phần*** của
interval đang chạy. Khi thời gian đó lớn dần, nhánh **lật**, và vị trí
nhảy từ đường ngoại suy hướng ra sang đường hướng vào.

**Hệ quả cho P1, và nó là lỗi của tôi:** `max_speed(RandomWalkMotion)`
trả `motion.speed`. Đó là tốc độ **khai**, còn tốc độ **thực hiện** vượt
nó **56 lần**. Một deployment khai `v_obstacle_max` cạnh một random walk
sẽ tính quãng phanh cho traffic chậm hơn 56 lần thứ nó gặp — đúng thất
bại mà validator sinh ra để chặn.

**Đã sửa phần tuyên bố an toàn:** `max_speed` nay **từ chối** random walk
với thông điệp nêu con số đo được, và validator dịch nó thành lời từ chối
**lúc nạp deployment** cho người đang chọn. Profile **không** khai gì thì
không đổi — validator không chạy.

**Chưa sửa bản thân luật chuyển động**: làm cho nó liên tục sẽ **đổi thế
giới**, tức đổi mọi số đã lưu cho mọi cảnh có random walk. Đó là thay đổi
độ trung thực, cùng loại với lần bật `sensor_noise`, và là quyết định của
An. Ghi thành **L12**.

---

## 11. Kiểm chứng

| Việc | Kết quả |
|---|---|
| `tests/test_dwa_oracle.py` | **21 passed** — ba pha 7.9a, tái lập ground truth, ba đường cấm, chạy end-to-end |
| `tests/test_task_profile.py` | **67 passed** (thêm 3 cho random walk) |
| `tests/test_dwa_predictive.py` | 27 passed |
| `ruff check .` | sạch |
| Cổng 20 seed × 4 cảnh | chạy xong, kết quả ở mục 5–6 |
| Cổng 40 seed, tập **không điều kiện** | **đang chạy** |
| Full backend suite | **chưa chạy — chờ lệnh** |

---

## 12. Còn lại

- **Quyết định cổng** — mục 9, chờ An.
- **L12** — `RandomWalkMotion` gián đoạn. Sửa là đổi thế giới.
- **`local_version` vẫn `"v1"`** → P6 việc 4.
- Nếu đi tiếp: **P5 tracker**, và oracle này trở thành đường so sánh —
  khoảng cách giữa hai bên **là** giá của việc phải tự ước lượng.

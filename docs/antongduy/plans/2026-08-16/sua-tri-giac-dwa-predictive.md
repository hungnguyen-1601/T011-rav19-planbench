# Sửa tầng tri giác của `dwa_predictive`

> ## ⚠ Q0 ĐÃ CHẠY VÀ BÁC BỎ TIỀN ĐỀ CỦA PLAN NÀY
>
> Đo lại ở N = 20 (`notes/2026-08-16/tongduyan_q0-do-lai-do-phan-giai-lidar.md`,
> dữ liệu `artifacts/q0_resolution/`):
>
> 1. **Bảng §1.4 sai.** Không có "đỉnh ở 144 tia rồi thoái lui" —
>    `vel_out` tăng đơn điệu 0.9 → 3.5 → 4.1 → 4.5%. Con số `err_med
>    0.164` ở 144 tia là ăn may với n nhỏ; ở N = 20 nó là **0.935**.
> 2. **Tăng độ phân giải mua ×5 phát hiện thật kèm ×7 ảo giác.**
>    Vận tốc ma trên cảnh tĩnh: 14.17% → **99.19%** số frame ở 360 tia.
>    Objective khai trước loại sạch mọi cấu hình trừ 72 tia.
> 3. **Nguyên nhân là sàn vận tốc mô hình sai đại lượng**, không phải
>    ngưỡng cụm chưa co giãn. Xem §Q0-KQ bên dưới.
>
> **Hệ quả:** §1.4, §3 vế 1 và 2, Q1, Q2, Q5 **không còn hiệu lực như
> đang viết**. Giữ nguyên văn bản để đối chiếu, không xoá. Đề xuất sửa
> hướng ở §Q0-KQ.
>
> Q3, Q4, Q6 và toàn bộ §2 (ba nước đi bị cấm), §5 (release gate), §6
> (tám quyết định) **vẫn còn hiệu lực**.

**Trạng thái:** Q0 xong, kết quả âm. Tám quyết định §6 đã chốt 16-08.
Chưa viết dòng code sản phẩm nào. Chờ dev chốt hướng sửa ở §Q0-KQ.
**Ngày lập:** 2026-08-16
**Tiền đề:** plan `2026-08-14/du-doan-chuyen-dong-vat-can.md` đã chạy hết
P0–P7. Plan này xử lý **kết quả âm của P5 và P7**, không mở tính năng mới.

---

## 0. Câu hỏi plan này trả lời

> `dwa_predictive` đã dự đoán được đường đi vật cản và né được chưa?

Chưa. Và plan `14-08` đã đo đúng chỗ hỏng — L16 nói thẳng nút thắt là
**tần suất phát hiện**, không phải độ chính xác mô hình. Plan này không
phát hiện lại điều đó. Nó trả lời câu tiếp theo:

> Sửa được không, sửa ở đâu, và **giá bao nhiêu**?

Câu trả lời ngắn, và nó **không** phải cái tôi tưởng khi bắt đầu khảo sát:
tăng độ phân giải LiDAR giúp rất nhiều **nhưng chỉ tới một điểm**, sau đó
**làm mọi thứ tệ đi**. Nên đây không phải việc "đổi cảm biến", mà là
"đổi cảm biến **và** làm các ngưỡng của tracker tự co giãn theo cảm biến".
Bỏ vế sau thì vế trước phản tác dụng.

---

## 1. Bằng chứng — khảo sát 16-08

Tất cả đo trên `profiles/warehouse_crossing_v1.yaml`, seed 0, AMR cắt
ngang bán kính 0.4 m, vận tốc hằng 0.8 m/s. Script khảo sát nằm ở
scratchpad, **chưa commit** — pha Q0 dưới đây tồn tại để đưa nó vào repo.

### 1.1 Chuỗi tổn thất, tính theo frame mà AMR nằm trong tầm LiDAR

```
crosser trong tầm            141 frame  (10.8% của 1305 frame episode)
  ├─ bị che khuất hoàn toàn   56  39.7%   0 tia chạm
  └─ có tia chạm              85  60.3%   trung bình 1.05 tia/frame
       ├─ gộp vào cụm khác    46  32.6%   centroid lệch > 0.75 m
       └─ có cụm riêng        39  27.7%
            ├─ loại: clipped  23  16.3%
            └─ qua bộ lọc      5   3.5%
                 └─ ra vận tốc  2   1.4%
```

**1.4%** khớp con số 1.6% mà L16 đo độc lập trên `intersection`. Hai bản
đồ khác nhau, cùng một kết quả.

### 1.2 Theo khoảng cách — chỗ cần né nhất là chỗ mù nhất

| | frame | che khuất | tia/frame | qua lọc | ra vận tốc |
|---|---|---|---|---|---|
| 3–4 m | 63 | 41 (65%) | 0.56 | **0** | **0** |
| 4–5 m | 58 | 13 (22%) | 1.53 | 5 | 2 |
| 5–6 m | 20 | 2 (10%) | 1.20 | 0 | 0 |

Ở 3–4 m — khoảng cách mà một quyết định né còn kịp có ý nghĩa — **không
một frame nào qua nổi bộ lọc**.

### 1.3 Bốn cơ chế

**(a) Độ phân giải góc.** 72 tia / 360° = 5.00°/tia. Ngưỡng tách cụm là
`cluster_gap_factor · d · Δθ + cluster_range_margin · σ`:

| tầm | ngưỡng phải vượt để tách AMR khỏi nền |
|---|---|
| 2.0 m | 0.584 m |
| 3.0 m | 0.845 m |
| 4.0 m | 1.107 m |
| 5.0 m | 1.369 m |

Ở 3.5 m cần bậc range **0.98 m**. Kệ cách AMR dưới 1 m ⇒ dính liền. Ví
dụ thật trong log: 1 tia chạm AMR rơi vào cụm **33 điểm, rộng 9.81 m**,
centroid lệch **2.84 m**.

Và `cluster_min_points = 3` trong khi đo được **1.05 tia/frame**. Vật thể
gần như không bao giờ đủ điều kiện tạo cụm của chính nó.

**(b) `clipped` sai giả định môi trường.** Test hiện tại loại cụm có tia
lân cận trả về giá trị bất kỳ:

```python
before = ranges[(run[0] - 1) % rays]
after = ranges[(run[-1] + 1) % rays]
clipped = before < limit - EPS or after < limit - EPS
```

Đúng trong **sảnh trống** — vật cô lập luôn được viền bởi tia không trả
về. Trong **lối đi kho** thì mọi thứ đều có kệ phía sau, nên gần như mọi
cụm đều `clipped`. Mất 23/39 cụm riêng.

Docstring của nó đã cảnh báo đúng chiều phân cực và vẫn sai ở chiều khác:
nó phòng trường hợp "một lát của cấu trúc lớn hơn", nhưng không phân biệt
được **"lát của bức tường"** với **"vật đứng trước bức tường"**.

**(c) Che khuất 39.7%.** Hình học bản đồ. Không phải bug, nhưng là trần
cứng: tracker giỏi đến mấy cũng không thấy vật sau kệ.

**(d) Sàn vận tốc tỉ lệ với tầm.** `reach · Δθ / window`:

| tầm | sàn (72 tia) |
|---|---|
| 3 m | 0.460 m/s |
| 4 m | 0.584 m/s |
| 5 m | 0.709 m/s |

So với tốc độ thật **0.800 m/s**. Ở 5 m biên chỉ còn 0.09 m/s. Sàn này là
**đúng và cần thiết** (không có nó, `dwa_predictive` tệ hơn `dwa` trên mọi
cảnh tĩnh — xem docstring `velocity_floor`), nhưng nó ăn gần hết tín hiệu
ở tầm xa khi Δθ thô.

### 1.4 Phát hiện then chốt: **không đơn điệu**

Cùng một tracker, chỉ đổi số tia:

| tia | °/tia | tia/frame | qua lọc | **ra vận tốc** | **sai số trung vị** | wall_s |
|---|---|---|---|---|---|---|
| 72 | 5.00 | 1.05 | 3.5% | 1.4% | 1.986 m/s | 29.9 |
| **144** | **2.50** | **2.39** | **16.7%** | **11.8%** | **0.164 m/s** | 43.0 |
| 271 | 1.33 | 4.47 | 14.6% | 9.0% | 1.380 m/s | 60.5 |
| 360 | 1.00 | 6.63 | 13.4% | 8.7% | 1.422 m/s | 78.3 |

**Đỉnh ở 144 tia, sau đó thoái lui.** `tia/frame` vẫn tăng đều tới 6.63,
nên đây **không** còn là vấn đề nhìn thấy hay không — mà là logic lọc và
liên kết bị hỏng ở độ phân giải mịn.

Cơ chế, đo trên cùng 25 s đầu mỗi episode nên các cột đếm so được với nhau:

| tia | cụm/frame | **cụm-"động"/frame** | track sinh ra | **ambiguous_drops** |
|---|---|---|---|---|
| 72 | 9.84 | 0.75 | 140 | 2 |
| 144 | 18.54 | 2.76 | 188 | 23 |
| 271 | 33.30 | 6.34 | 307 | **328** |
| 360 | 42.94 | 8.76 | 455 | **894** |

Δθ nhỏ ⇒ ngưỡng tách nhỏ ⇒ **tường vỡ vụn thành nhiều cụm hẹp**. Cụm hẹp
thì lọt qua test tường (`cluster_wall_width = 0.9 m` — mảnh vỡ hẹp hơn thế)
⇒ được tính là "vật thể động".

Bản đồ này có **đúng một** vật thể động. Ở 360 tia tracker thấy **8.76
vật thể động mỗi frame**. Gần như toàn bộ là mảnh tường.

Và hậu quả nằm ở cột cuối: `ambiguous_drops` đi **2 → 23 → 328 → 894**,
tức **447×**. `_associate` bỏ hẳn track nào có ≥2 cụm trong cổng liên
kết, nên càng nhiều cụm rác thì **chính track thật càng bị hi sinh vì
"nhập nhằng"**. Đó là lý do 271 và 360 tia tệ hơn 144.

Đây là chẩn đoán quan trọng nhất của cả khảo sát: **các ngưỡng của tracker
được hiệu chỉnh ngầm cho 72 tia.** Ba ngưỡng là **tuyệt đối** trong khi
lẽ ra phải co giãn theo cảm biến:

| ngưỡng | giá trị | vấn đề |
|---|---|---|
| `cluster_min_points` | 3 (đếm tia) | ở 72 tia là bất khả thi; ở 360 tia là vô nghĩa |
| `cluster_wall_width` | 0.9 m | mảnh tường ở Δθ mịn hẹp hơn ngưỡng ⇒ lọt |
| `association_margin` | 0.25 m | mật độ cụm tăng ⇒ nhiều cụm trong cổng ⇒ nhập nhằng |

**Cảnh báo về độ tin cậy của bảng 1.4:** một seed, trung vị lấy trên
2–17 frame. Đủ để thấy hướng và thấy tính không đơn điệu, **không đủ** để
chốt con số 144. Pha Q0 tồn tại chính vì lý do này — không được lấy bảng
này làm căn cứ chọn cấu hình.

---

## 2. Ba nước đi **không** được phép

Ghi trước để pha sau khỏi lạc.

**(a) Trừ nền theo bản đồ tĩnh.** `Observation` khai rõ *"no ground-truth
map"* — chỉ có `pose`, `lidar_ranges`, `goal_distance`, `goal_bearing`.
Cho local planner cầm map là đổi `local_observation_class` từ
`lidar_only`, và G6 sẽ (đúng đắn) từ chối so nó với `dwa`. Biến thể hợp
lệ là **tự dựng nền từ chính scan của robot** — nhưng nó phụ thuộc L17
(hai hệ toạ độ) chưa xong, nên không nằm trong plan này.

**(b) Lấy ngưỡng từ vật cản mà kịch bản khai.** Đã có nguyên một đoạn
docstring ở đầu `tracking.py` về việc này. Mọi ngưỡng mới phải suy ra từ
**đặc tả cảm biến** (`num_rays`, `max_range`, `lidar_range_sigma_m`) hoặc
từ `SafetyEnvelope`, không từ `DynamicObstacle.radius`.

**(c) Nới sàn vận tốc để "ra được nhiều số hơn".** Sàn là thứ chặn
`dwa_predictive` tệ hơn `dwa` trên cảnh tĩnh. Nếu độ phân giải mịn hơn
thì sàn **tự động** hạ (nó tỉ lệ `reach · Δθ`) — đó là cách đúng để nó
giảm. Hạ tay là mở lại đúng lỗ đã bịt.

---

## 3. Kiến trúc sửa — hai vế, bắt buộc đi cùng nhau

```
vế 1: cảm biến trở thành thứ DEPLOYMENT khai
      EnvironmentSpec.lidar  ->  scenario_for()  ->  episode

vế 2: ngưỡng tracker CO GIÃN theo cảm biến
      cluster_min_points, cluster_wall_width, association_margin
      chuyển từ hằng số sang hàm của (Δθ, σ, reach)
```

Làm vế 1 mà bỏ vế 2 = bảng 1.4 = tăng tia làm tệ đi. Làm vế 2 mà bỏ vế 1 =
vẫn kẹt ở 1.05 tia/frame. **Không pha nào ship riêng được.**

Cộng thêm một sửa độc lập với độ phân giải:

```
vế 3: `clipped` phân biệt "lát của tường" với "vật đứng trước tường"
```

---

## 4. Các pha

### Q0 — Đưa phép đo vào repo, trước khi sửa gì · **0.5 ngày**

Lý do tồn tại: mọi số ở §1 hiện nằm trong scratchpad, một seed. Đúng cái
sai mà `diagnose_tracker.py` được commit để tránh — *"an earlier version
of these figures existed only as pasted output, which is a result nobody
else can re-run."*

1. `scripts/diagnose_resolution.py` — quét (số tia) × (N seed) trên một
   profile, in: `tia/frame`, tỉ lệ qua lọc, tỉ lệ ra vận tốc, sai số vận
   tốc so với ground truth, **và tỉ lệ vận tốc ma trên một cảnh tĩnh**.
   Cột cuối bắt buộc: nếu chỉ đo cảnh có traffic thì mọi thay đổi làm
   tracker "nhạy hơn" đều trông như cải thiện.
2. Chạy lại toàn bộ §1.4 với **N ≥ 20 seed**, thay bảng một-seed.
3. Ghi lại kết quả vào `notes/2026-08-16/`.
4. **Kỷ luật seed — calibration tách khỏi evaluation, khai từ bây giờ:**

   ```
   Calibration A: {1000..1119}   Q0 + mọi hiệu chuẩn factor của Q2
                                 (wall_continuity_factor, ε_wall,
                                  association_ambiguity_margin, kiểm w_min)
   Evaluation  B: {2000..2119}   cổng Q4; mở rộng một-lần: {2000..2359}
   Đã cháy     : {0..119} và mọi seed lẻ đã dùng trong khảo sát §1
   ```

   Dải `{0..119}` **không được làm evaluation** dù ghi chú contamination
   — khảo sát §1 chạy trên seed 0 thuộc dải đó, và P4/P5 đã nhìn toàn
   dải khi thiết kế. Ghi nhận vết bẩn không biến seed đã nhìn thành
   held-out; đổi dải mới là cách duy nhất. Hệ quả phải trả: **baseline
   `dwa` và oracle phải chạy lại trên B mới** — số 11/120 opportunity
   của P4 là số của dải cũ, không được mang sang so.

   Không chỉnh bất kỳ parameter nào sau khi đã nhìn số liệu trên B —
   seed đã dùng để chọn factor là training data, để nó lọt vào cổng là
   tự chấm bài mình ra đề.
5. **Objective chọn factor, khai trước để "đo ở Q0" không thoái hoá
   thành chọn-bằng-mắt cấu hình đẹp:**

   ```
   ràng buộc cứng:  phantom-velocity rate (cảnh tĩnh) ≤ baseline 72-tia hiện tại
   tối đa hoá:      tỉ lệ ra vận tốc trên cảnh có traffic
   tie-break:       margin bảo thủ hơn (factor continuation nhỏ hơn,
                    ambiguity margin lớn hơn); còn hoà thì cấu hình đơn giản hơn
   ```

**Không đổi một dòng code sản phẩm nào ở pha này.**

**Ra khỏi pha khi:** bảng 1.4 được tái lập (hoặc bác bỏ) ở N ≥ 20 trên
seed set A, script đã commit, và objective + seed split đã nằm trong
chính script (in ra ở đầu output, không phải trong trí nhớ ai đó).

#### Ba điều lộ ra khi dựng harness — ghi lại vì chúng đổi cách đọc mọi bảng sau

**(1) `reset()` dựng tracker MỚI, nên đo bằng instance wrap là đo hư.**
`DWAPredictivePlanner.reset` tạo `LidarTracker` mới (có chủ đích: "hai
episode trên một instance phải bằng hai instance"), và `run_stack` gọi
`reset` sau khi caller kịp bọc. Bản đầu của script bọc ở mức instance ⇒
bị vứt trước scan đầu tiên ⇒ episode chạy thành công, **mọi counter
bằng 0**, và bảng đọc ra "tracker không thấy gì" thay vì "không ai
đang đo". Script giờ bọc ở mức class, khôi phục trong `finally`, và
**ném lỗi nếu `frames == 0`** — im lặng là chế độ hỏng nguy hiểm nhất
của một công cụ chẩn đoán.

**(2) Không phải seed nào cũng có cuộc gặp.** Đo trên 8 seed calibration:
**6/8 seed** robot mới vào tầm cảm biến của crosser; 2 seed còn lại
`in_range = 0` cả episode. Có seed vào tầm 83 frame mà **0 tia** chạm
được (che khuất hoàn toàn). Nên "N seed" **không phải** cỡ mẫu — cỡ mẫu
là số seed có gặp, và bảng phải in cột `enc/eps`. Với N = 20 kỳ vọng
~15 cuộc gặp, ~2300 frame in-range: đủ, nhưng phải nói ra chứ không để
người đọc suy từ chữ "20 seed".

**(3) Baseline vận tốc ma cao hơn dự đoán, và đây là ràng buộc cứng của
objective.** Trên **cảnh tĩnh** (cùng deployment, rút hết traffic), 72
tia, 8 seed:

```
phantom_rate  14.17%      p90 phantom speed  1.868 m/s
```

Nghĩa là trong một nhà kho **không có gì chuyển động**, tracker báo có
vận tốc ở 1 trong 7 frame, và 10% số đó nhanh hơn 1.87 m/s — **hơn gấp
đôi** tốc độ traffic thật (0.8 m/s). Sàn vận tốc đang chặn biên độ chứ
không chặn được hiện tượng.

Hệ quả cho Q2/Q3, phải nhớ khi chọn ngưỡng: mọi thay đổi làm tracker
nhạy hơn sẽ **được thưởng ở cột traffic và bị phạt ở cột tĩnh**, và
ràng buộc cứng là cột tĩnh. Con số 14.17% là mốc phải không vượt.

**Rủi ro thật:** N=20 có thể cho thấy 144 không phải đỉnh, hoặc tính không
đơn điệu là artefact của một seed. Nếu vậy **plan này phải viết lại** —
và đó là lý do Q0 đứng trước.

---

### Q1 — Cảm biến trở thành thứ deployment khai · **1.5 ngày**

Hôm nay `LidarConfig(num_rays=72, max_range=5.0)` là **default cứng** ở
`scenario.py:78`, không profile nào khai được. Hệ quả: không thể có hai
deployment cùng bản đồ khác cảm biến, tức không thể so được.

1. `EnvironmentSpec.lidar: LidarConfig | None = None` — `None` giữ nguyên
   default, nên **mọi profile đã có không đổi một float nào**.
2. Nối qua `scenario_for()` trong `episode.py`.

**Q1.a — `angle_span` bị chặn ở `2π`, có validator, có bằng chứng.**

`LidarConfig` cho khai `angle_span` bất kỳ, và simulator tôn trọng nó
(`lidar.py:89`: `increment = angle_span / num_rays`, tia đầu ở
`-span/2`). Nhưng **hai** nơi phía tiêu thụ hardcode vòng tròn đầy:

- tracker: `spacing = 2π / rays`, `start_angle = pose.theta - π`
  (`tracking.py:209-210`);
- **và cả `dwa` thường**: `obstacle_points` trong `dwa_core.py:216-218`
  cũng `span = 2.0 * math.pi`.

Nghĩa là deployment khai LiDAR 180° hôm nay không chỉ làm tracker chiếu
sai centroid — nó làm **mọi candidate lidar_only** dựng đám mây điểm sai
toạ độ, lệch một phép quay + phản chiếu. Đây là bug tồn tại sẵn, Q1 chỉ
làm nó **khả khai** nên phải chặn trước.

Quyết định: **phương án hẹp** — validator trên `EnvironmentSpec.lidar`
từ chối `angle_span ≠ 2π` với thông điệp nói rõ vì sao (kể cả tên hai
hàm hardcode). Truyền `LidarConfig` xuyên xuống planner/tracker là việc
đúng dài hạn nhưng chạm `scenario_for → nav_stack → planner.reset →
LidarTracker` + `dwa_core` + test golden của cả hai controller — scope
đó là một pha riêng, không nhét vào plan sửa tri giác. Ghi thành nợ
trong L19. Regression test: profile khai 180° phải bị từ chối **khi
load**, không phải chạy sai âm thầm.

**Q1.b — ghi đủ mọi điểm chạm, liệt kê tường minh.**

`FairnessRecord` (luồng benchmark cũ) đã có `lidar_num_rays` /
`lidar_max_range` và scenario checksum đã băm LiDAR. Nhưng luồng
deployment thì **chưa**: HĐ-13 `Manifest` chỉ ghi `sensor_noise`
(`card.py:363`), không có `lidar`. Danh sách phải sửa — đủ, không phải
"manifest" chung chung:

*Backend:*
- [ ] `Manifest.lidar` (schema + field)
- [ ] `Manifest.to_json_dict()`
- [ ] `build_manifest()` — nằm ở **`card.py:555`**, `selection.py` chỉ
      là caller (bản nháp trước ghi sai chỗ)
- [ ] `identity` của comparison report (`selection.py:599` — nơi ghi
      `sensor_noise` để run không sinh card vẫn nhận diện được môi
      trường; LiDAR cùng lý do)
- [ ] report của run bị ngắt trước episode đầu (cùng identity)
- [ ] round-trip test manifest: dump → load → so bytes

*Web form + preview — thiếu là preview nói dối:*
- [ ] TypeScript `LidarConfig` + field `lidar` trên `Scenario` phía TS
- [ ] control `num_rays` / `max_range` trên Deployment Form (angle_span
      **không** có control — bị validator Q1.a chặn ở 2π)
- [ ] `previewRequestOf()` gửi LiDAR của draft — preview adapter dựng
      scenario bằng tay (`traffic.ts:590`); bỏ sót thì deployment chạy
      144 tia nhưng preview vẫn vẽ thế giới 72 tia, đúng loại sai lệch
      mà endpoint preview tồn tại để tránh
- [ ] `ADAPTER_FIELDS` thêm `lidar`
- [ ] mở rộng drift guard `test_the_adapter_fills_what_an_episode_fills`
      (`test_api_profile_validation.py:298`) — và sửa docstring của nó:
      hiện viết *"the LiDAR the platform fixes"*, mệnh đề hết đúng ngay
      khi Q1 land

**Danh sách trên KHÔNG phải thứ phải nhớ — có test cưỡng chế nó.**
`tests/test_form_covers_the_contract.py` đọc thẳng `DeploymentForm.tsx`
và đối chiếu với mọi field của `TaskProfile`: thêm `EnvironmentSpec.lidar`
mà không bind ⇒ test **đỏ ngay**. Escape hatch duy nhất là ghi tên field
vào `NOT_IN_THE_FORM` **kèm lý do** — và lý do đó là thứ người sau tranh
luận được. Nghĩa là Q1 phải chọn tường minh một trong hai:

- bind `environment.lidar.num_rays` và `environment.lidar.max_range` vào
  form; **hoặc**
- khai vào `NOT_IN_THE_FORM` rằng deployment chưa được chọn cảm biến
  qua UI ở pha này, kèm lý do thật.

`environment.lidar.angle_span` **thuộc nhóm thứ hai chắc chắn**, và lý
do đã có sẵn từ Q1.a: validator chỉ nhận `2π`, nên một control cho nó là
control không dùng được — cùng dạng lập luận mà `robot.type` đang dùng
trong chính danh sách đó ("dropdown một lựa chọn là control không dùng
được").

**Q1.c — `execution_conditions_fingerprint`, thay cho checksum-cả-profile.**

Bản nháp đầu của plan đề xuất checksum nội dung profile và đối chiếu với
run đã lưu. **Sai hai chiều, bỏ.**

*Chiều thứ nhất — quá hẹp về phạm vi bảo vệ.* Trace không nằm trong thư
mục run. Nó được định địa chỉ chỉ bằng
`trace_root / candidate_id / episode_context_id.parquet`
(`pipeline.py:224`), và `--reuse-traces` chỉ kiểm **file có tồn tại
không** rồi bỏ qua simulation; `--score-only` cũng tìm theo đúng hai id
đó. `TraceMetadata` hiện chỉ lưu 4 id, không lưu điều kiện. Nên guard
đặt ở mức run-directory không đỡ được: reuse trace của thế giới cũ,
score-only trên trace ngày hôm trước, run directory đã xoá nhưng trace
còn. Đây chính là cơ chế đã sinh ra journal 120 dòng ở P7:

```
run_journal.jsonl:  120 bản ghi
  60 đầu:  toàn 'stuck'   (profile có v_obstacle_max)
  60 sau:  toàn 'success' (profile đã rút)
  episode_context_id block 1 == block 2 == b408516ece7f
```

*Chiều thứ hai — quá rộng về nội dung băm.* Đổi `success_rate_min` chỉ
đổi verdict, không đổi một sample nào của episode; bắt chạy lại toàn bộ
vì nó là phạt sai chỗ.

Thiết kế thay thế — **suy từ đúng object mà simulator nhận, không phải
danh sách field duy trì song song:**

```python
execution_conditions_fingerprint = sha256(
    map_data.checksum(),
    normalize(scenario_for(profile, context)),   # trừ name, description,
                                                 # random_seed (context id
                                                 # đã mang seed)
    profile.replanning,                          # ba thứ run_stack nhận
    profile.recovery,                            # NGOÀI scenario
    profile.environment.v_obstacle_max,
)
```

Vì sao suy-từ-object thay vì liệt-kê-field — bản liệt kê đầu tiên của
chính plan này đã mắc **cả hai chiều lỗi** trong một lần viết:

- **bỏ sót `clearance_preference`** — nó đổi planning grid và quỹ đạo
  (`episode.py:114` đưa nó vào scenario), tức đổi thế giới, mà danh
  sách tay không có;
- **đưa nhầm `clearance_warning_m` vào** — tưởng nó sinh event trong
  trace; thực tế chỉ Metrics Engine đọc để tính near-miss
  (`definitions.py:407`), scoring-only, đổi nó không việc gì phải chạy
  lại episode.

`scenario_for` **là** định nghĩa "cái gì đi vào simulator" — field mới
thêm vào scenario tự động vào fingerprint, không cần ai nhớ. Ba tham số
`run_stack` nhận ngoài scenario (`replanning`, `recovery`,
`obstacle_speed`) băm riêng, và **chỉ** ba cái đó — có test khẳng định
chữ ký `run_stack` không mọc thêm tham số điều kiện nào chưa được băm.

Luật phân loại giữ nguyên cho người đọc sau: **vào fingerprint nếu đổi
nó có thể đổi quỹ đạo hoặc nội dung trace; ở ngoài nếu chỉ đổi cách
phán xử trace.** Nhưng cơ chế thi hành là dẫn xuất từ object, không
phải kỷ luật con người.

Thi hành:
- Lưu fingerprint trong `TraceMetadata` (footer Parquet). Đây là schema
  bump — gộp chung với bump của Q5 (counter tracker) thành **một** lần
  đổi schema, không hai.
- Kiểm fingerprint **trước mọi nhánh reuse**: `--reuse-traces` so
  fingerprint của trace với fingerprint tính từ profile hiện tại, lệch ⇒
  chạy lại episode đó (không phải lỗi — trace cũ đơn giản là không dùng
  được). `--score-only` lệch ⇒ **từ chối**, vì không còn đường tái mô
  phỏng đúng.
- Trace cũ không có fingerprint: **fail-closed** — coi như lệch. Giá là
  mất khả năng reuse kho trace hiện có một lần; rẻ hơn một kết luận sai.
- Thư mục run: `run_journal.jsonl` mở với chế độ ghi đè khi bắt đầu run
  mới thay vì append vô điều kiện — sửa một dòng, chặn đúng vụ 120 dòng.

**Ra khỏi pha khi:** một profile khai được 144 tia và bị từ chối nếu
khai 180°; manifest + report identity ghi LiDAR ở mọi điểm trong danh
sách Q1.b; trace của thế giới cũ không thể được reuse/score âm thầm
(có regression test cho cả `--reuse-traces` lẫn `--score-only`).

---

### Q2 — Ngưỡng co giãn theo cảm biến · **2.5 ngày** · ba pha con, đo sau từng pha

Đây là pha làm cho việc tăng tia thôi phản tác dụng. Tách ba pha con
**độc lập, land tuần tự, chạy harness Q0 sau mỗi pha** — để nếu vận tốc
ma tăng thì biết chính xác thay đổi nào gây ra. Không land gộp.

#### Q2a — `cluster_min_points` theo tầm · 0.5 ngày

Hôm nay: hằng số `3` tia, bất khả thi ở 72 tia (đo được 1.05 tia/frame),
vô nghĩa ở 360 tia.

Thiết kế chốt, không để người triển khai tự chọn:

```python
n_required(d) = max(2, floor(w_min / (d · Δθ)))
với  d  = max(khoảng cách từ observation.pose tới centroid cụm, EPS)
     Δθ = angle_span / num_rays   # xem khoá bên dưới
```

- Tính **theo từng cụm** tại tầm `d` của chính cụm đó — không phải một
  hằng số toàn cục tại `max_range` (tại 72 tia, hằng số đó ra 0).
  `d` đo từ **believed pose** — pose duy nhất controller có.
- **Khoá Δθ, và một ràng buộc thực tế phải nói thẳng:** tracker chỉ nhận
  `Observation`, không có kênh nào mang `LidarConfig` xuống — đó chính
  là phần plumbing đã hoãn ở Q1.a. Nên trong code tracker, Δθ vẫn tính
  bằng `2π / len(lidar_ranges)`; đẳng thức `2π / num_rays ==
  angle_span / num_rays` được **validator Q1.a bảo đảm** (từ chối mọi
  profile khai `angle_span ≠ 2π`). Bất biến này phải được khoá bằng
  test: một test load profile 180° và khẳng định bị từ chối, kèm comment
  trong tracker trỏ về validator. Ngày nào trả nợ plumbing (truyền
  `LidarConfig` xuống planner/tracker) thì đổi công thức sang
  `angle_span / num_rays` cùng lúc — ghi trong L19.
- `w_min = 0.3 m`, hằng số **candidate-owned**, cùng loại sở hữu với
  `association_speed_limit` — không đọc từ `DynamicObstacle.radius`
  (§2b), không phải deployment khai. Nằm trong config ⇒ đi vào
  `candidate_id`. Dev phê chuẩn trước phép đo (§6, quyết định #6),
  **không chọn lại sau khi thấy Q4**.
- **Phát biểu cho đúng phạm vi của tuyên bố:** `w_min` là *apparent
  width tối thiểu mà cổng đếm-điểm được thiết kế để chấp nhận khi vật
  được quan sát đầy đủ* — **không phải** bảo đảm mọi vật ≥ 0.3 m luôn
  được phát hiện. Vật rộng vẫn có thể bị che, chỉ lộ một phần, dính vào
  nền, hoặc rơi giữa hai tia. Đây là phạm vi năng lực của khâu
  sampling/lọc, không phải detection guarantee — docstring phải viết
  đúng như vậy, vì người đọc config sẽ đọc nhầm theo hướng mạnh hơn.
- Clamp dưới ở **2**: một tia không bao giờ đủ (centroid của 1 điểm là
  nhiễu thuần), và vật một-tia-ở-xa bị loại **có chủ đích** — nó sẽ được
  theo khi lại gần, đó là hành vi đúng của sàn tri thức, không phải bug.
- Rủi ro đo trước/sau: cụm 2 điểm có centroid nhiễu chi phối; cột "vận
  tốc ma cảnh tĩnh" của Q0 là tiêu chí chặn.
- **Boundary test quanh các điểm gãy của floor**, vì `floor` nhảy bậc:
  `w_min/(d·Δθ) = 1.99 → 2`; `= 2.00 → 2`; `= 2.99 → 2`; `= 3.00 → 3`;
  và cùng một vật ở cùng khoảng cách chạy qua 72/144/271/360 tia phải
  cho `n_required` tăng đúng tỉ lệ.

#### Q2b — Test tường bằng tính liên tục, thay bề rộng đơn cụm · 1 ngày

Nguyên nhân thoái lui 271/360 tia. Định nghĩa cụ thể, trả lời đủ các
câu hỏi mở:

- **"Lân cận" = theo chỉ số tia, và CHỈ giữa hai run kề trực tiếp do
  range split** — run sau bắt đầu ngay ở tia kế tiếp của run trước.
  **Không nối qua bất kỳ tia no-return nào**: no-return nghĩa là *không
  quan sát thấy bề mặt*, và bắc cầu qua nó là khẳng định một tính liên
  tục không có bằng chứng — hai bức tường hai bên một khoảng trống sẽ
  bị dán thành một. Bridging qua dropout là pha riêng, chỉ mở khi có
  bằng chứng cần (khi đó phải thêm `max_missing_rays` + ownership +
  objective hiệu chuẩn + test không-nối-hai-tường-qua-vùng-trống — ghi
  nợ, không làm ở đây). Không dùng khoảng cách Cartesian — hai vật xa
  nhau trong không gian có thể gần nhau qua phép chiếu.
- **Khoảng trống tối đa**: ranh giới giữa hai run là *continuation* khi
  bậc range tại đó `|r_a − r_b| ≤ wall_continuity_factor · (d·Δθ) +
  cluster_range_margin · σ` — cùng dạng công thức với ngưỡng split,
  hệ số riêng (`wall_continuity_factor`, đo ở Q0, dự kiến quanh 6–10:
  lớn hơn split factor 3 vì tường nghiêng tạo bậc lớn hơn bậc của mặt
  vuông góc, nhỏ hơn nhiều so với bậc vật-đứng-trước-tường vốn là hiệu
  khoảng cách vật–nền, cỡ mét).

  **Ràng buộc thứ tự, phải thành validator chứ không phải quy ước:**
  hai cụm kề nhau tồn tại **chính vì** bậc range giữa chúng đã vượt
  ngưỡng split. Nếu continuation dùng đúng ngưỡng đó thì hai điều kiện
  loại trừ nhau và không cặp cụm nào nối được — test tường mới chết
  lặng lẽ ngay ngày đầu. Nên bắt buộc:

  ```
  cluster_gap_factor < wall_continuity_factor    # validator trong config
  ```

  và Q0 hiệu chuẩn **khoảng cách giữa hai factor** (dải bậc range nằm
  giữa "đủ để tách cụm" và "đủ để kết luận khác bề mặt"), không hiệu
  chuẩn từng factor cô lập.
- **Đồng tuyến**: góc giữa hai chord ≤ `ε_wall` **và** khoảng cách
  vuông góc từ centroid cụm này tới đường chord của cụm kia ≤
  `k·(d·Δθ) + m·σ`. `ε_wall` đo ở Q0.
- **Phán quyết**: nếu chuỗi các run nối tiếp nhau (liên tục + đồng
  tuyến) có **tổng** bề rộng > `cluster_wall_width` và straightness gộp
  nhỏ ⇒ cả chuỗi là tường, mọi mảnh bị loại. Test tường chuyển từ thuộc
  tính **một cụm** sang thuộc tính **chuỗi cụm** — bất biến theo Δθ.

  **Quy tắc cho cụm ngắn — bắt buộc, vì Q2a vừa mở cửa cho cụm 2
  điểm:** hai điểm xác định một đường *tuyệt đối*, residual luôn bằng 0
  — "thẳng hoàn hảo" của cụm 2 điểm không phải bằng chứng nó là tường.
  Nên: (i) cụm dưới 3 điểm **không bao giờ tự phân loại** là tường;
  (ii) nó chỉ nhận nhãn tường khi **nối vào một chuỗi** mà tổng số điểm
  và tổng bề rộng của cả chuỗi vượt ngưỡng; (iii) straightness của
  chuỗi tính bằng **fit một đường trên toàn bộ điểm của chuỗi gộp**,
  không suy từ residual của từng mảnh — từng mảnh ngắn thẳng tuyệt đối
  là tautology, cả chuỗi thẳng mới là thông tin.
- **Góc tường / kệ cong**: hai cạnh của góc không đồng tuyến ⇒ không
  merge ⇒ mỗi cạnh tự xét riêng — đúng hành vi mong muốn. Kệ cong bán
  kính lớn: các chord kề nhau lệch góc nhỏ, vẫn nối được từng đoạn;
  bán kính nhỏ cỡ vật thật thì **không được** nối — và không nối là
  đúng, vì nó chính là hình dạng của vật đáng theo.
- **Vật đứng trước tường có bị nuốt không?** Không: ranh giới
  vật–tường là bậc range bằng hiệu khoảng cách vật–nền (cỡ mét), vượt
  xa ngưỡng continuation (cỡ cm). Vật **chạm sát tường cùng tầm** thì
  nhập nhằng thật — chấp nhận là hạn chế, ghi vào docstring.

#### Q2c — Gán toàn cục tất định + quyền từ chối · 1 ngày

`_associate` hiện duyệt track theo thứ tự list và **bỏ hẳn** track có ≥2
cụm trong cổng ⇒ `ambiguous_drops` 2 → 894 (§1.4) ⇒ track thật bị hi
sinh giữa đám mảnh tường.

Thứ tự phụ thuộc: Q2b hạ mật độ cụm-"động" từ 8.76 về gần 1 và phần lớn
nhập nhằng biến mất theo. Q2c là lớp phòng thủ thứ hai, **không** phải
cách vá cho test tường sai — land sau Q2b, đo riêng.

Thiết kế chốt — **greedy toàn cục tất định, không phải Hungarian**, và
**từ chối được xét trên cạnh, TRƯỚC khi greedy tiêu thụ bất kỳ cụm nào**:

```
1. Sinh mọi cạnh (track, cluster, distance) có distance ≤ gate
   (gate trước assignment, như hiện tại).
2. Đánh dấu cạnh NHẬP NHẰNG nếu tồn tại cạnh cạnh tranh đủ gần
   (chênh distance < association_ambiguity_margin) ở MỘT TRONG HAI phía:
     - cùng track, cluster khác;  HOẶC
     - cùng cluster, track khác.
3. Loại mọi cạnh nhập nhằng. KHÔNG đụng misses ở bước này — chỉ ghi
   nhận tập track bị mất cạnh vì nhập nhằng, và
   ambiguous_drops += (số TRACK trong tập đó)     # đếm track, không đếm cạnh
4. Sắp cạnh còn lại theo (distance, track.identity, cluster.first_ray_index).
5. Duyệt tăng dần, nhận cạnh nếu cả track lẫn cluster chưa bị dùng.
6. MỘT lần duy nhất, cuối frame: mọi track không được ghép
   (vì nhập nhằng, vì hết cạnh, hay vì cụm bị lấy mất) → misses += 1.
```

Bước 3 và 6 tách bạch có chủ đích — bản nháp trước tăng `misses` ở cả
hai chỗ, nghĩa là track nhập nhằng bị **đếm hai lần trong một frame** và
timeout sớm gấp đôi thiết kế. `misses` chỉ được tăng ở đúng một điểm;
`ambiguous_drops` đếm **track nhập nhằng mỗi frame** (không phải cạnh bị
loại) để so được trước/sau với chuỗi số liệu §1.4 hiện có, vốn cùng
semantics track-một-lần-mỗi-frame.

Hai điểm trong đặc tả này tồn tại vì hai lỗi cụ thể mà bản nháp trước
sẽ mắc:

- **Xét nhập nhằng trước tiêu thụ, không phải trong lúc duyệt.** Nếu xét
  sau từng assignment, một track nhập nhằng có thể "giả vờ" thành rõ
  ràng chỉ vì cụm cạnh tranh vừa bị track khác lấy mất — verdict phụ
  thuộc thứ tự duyệt, tức không còn là tính chất của frame.
- **Nhập nhằng hai phía.** Track A và track B mỗi bên chỉ có một ứng
  viên duy nhất là cụm X ⇒ nhìn từng track thì "rõ ràng", nhưng danh
  tính của X đang tranh chấp. So best/second-best chỉ theo phía track
  sẽ gán bừa. Phía cluster phải được kiểm cùng lúc.

**Field riêng, không mượn `association_margin`.** Margin hiện tại trả
lời *"cạnh có khả thi không"* (nằm trong gate); đại lượng mới trả lời
*"cạnh khả thi có đủ phân biệt không"*. Cùng đơn vị mét, hai câu hỏi
khác nhau — dùng chung một field là coupling ngầm hai bán kính không có
lý do gì phải bằng nhau. Đặt:

- `association_margin` — giữ nguyên tên, nguyên nghĩa (đệm gate);
- `association_ambiguity_margin` — mới, hiệu chuẩn ở Q0 theo seed set A.

**`Cluster` phải mang `first_ray_index`.** Hiện `Cluster` không lưu chỉ
số tia (`tracking.py:59`) nên khoá tie-break ở bước 4 chưa có chỗ đứng.
Thêm field `first_ray_index: int` — với run nối qua seam (ray 0 + ray
cuối), lấy chỉ số tia đầu của **đoạn sau khi nối**, tức phần tử đầu của
run gộp, để ordinal ổn định giữa hai frame liên tiếp.

Vì sao **không** Hungarian: (a) tối ưu toàn cục không cần — sai số ở
đây do nhập nhằng thật, không do greedy kém; (b) Hungarian gán **bắt
buộc**, phá đúng semantics từ chối mà test 203 khoá; ghép thêm tầng
abstention lên trên nó là phức tạp hơn greedy-với-abstention mà không
mua thêm gì; (c) không thêm dependency, không tự triển khai thuật toán
O(n³) để giải bài toán không có. Test hiện có (track đứng giữa hai cụm
phải từ chối — `test_dwa_tracking.py:203`) giữ nguyên và phải tiếp tục
pass: hai cạnh cùng track chênh ≈ 0 < ambiguity margin ⇒ cả hai bị loại
ở bước 3.

Cost = khoảng cách tới **vị trí quan sát cuối** của track, không phải
vị trí ngoại suy: vận tốc bị zero-gate khi `misses > 0`, nên "predicted
position" sẽ dùng chính đại lượng mà module này tuyên bố không tin khi
chưa nhìn thấy — output nói *"tôi không tin vận tốc này"* trong khi
association lại dùng nó để quyết danh tính. Ngoại suy vị trí trong gate
chỉ được xét lại khi có đủ bốn thứ: confidence được downstream đọc
thật; trạng thái track tách bạch observed/coasting/lost; luật "vận tốc
còn tin được trong bao lâu"; và bằng chứng đo được rằng nó thắng
last-observation. Ghi nợ.

**Ra khỏi Q2 (cả ba pha con) khi:** bảng Q0 chạy lại cho thấy tỉ lệ ra
vận tốc **đơn điệu không giảm** theo số tia trong dải 72–360, và vận
tốc ma trên cảnh tĩnh không tăng ở **từng** pha con (đo ba lần, không
một lần cuối).

---

### Q3 — `clipped` cho môi trường lộn xộn · **0.5 ngày**

Hiện: có tia lân cận trả về ⇒ `clipped` ⇒ loại. Mất 16.3% số frame.

Đề xuất: `clipped` chỉ khi tia lân cận **liên tục** với run này — tức
hiệu range nhỏ so với bậc `d · Δθ` cục bộ. Nếu tia lân cận xa hơn hẳn
(một bậc lùi về sau), thì vật **đứng trước** nền, centroid của nó là đại
lượng thật và theo được.

Đây là test **bất liên tục range**, suy từ cảm biến, không từ ground
truth — hợp lệ theo §2(b).

**Rủi ro:** nới `clipped` là nới thứ đang chặn "centroid trượt dọc tường".
Bắt buộc đo lại vận tốc ma trên cảnh tĩnh.

**Ra khỏi pha khi:** tỉ lệ qua lọc ở dải 3–4 m > 0 (hôm nay bằng 0), và
vận tốc ma trên cảnh tĩnh không xấu đi.

---

### Q4 — Cổng quyết định · **1 ngày** · **khai trước khi chạy, đủ để tái lập verdict**

Lặp lại thiết kế cổng của P4, vì nó đã bắt được một kết luận sai một lần
rồi. Bản đầu của mục này chưa đủ định nghĩa để hai người chạy ra cùng
một verdict — dưới đây là đặc tả đầy đủ. Mọi con số phải chốt **trước**
lần chạy đầu; §6 liệt kê cái nào cần dev phê chuẩn.

Ba nhánh, cùng seed, ghép cặp: `dwa` — oracle (tri giác hoàn hảo) —
`dwa_predictive` (tracker thật, cảm biến mới, ngưỡng mới).

**Harness và môi trường — ghim tường minh, vì harness hiện tại không
chạy được cổng này:** `scripts/diagnose_tracker.py` hardcode scene
built-in `intersection`, không nạp `TaskProfile`, không đi qua đường
`EnvironmentSpec.lidar` — tức nếu không sửa nó thì LiDAR
deployment-owned của Q1 **không hề được kiểm ở Q4**, cổng sẽ đo default
72 tia và dán nhãn cấu hình mới. Việc phải làm:

- Mở rộng `diagnose_tracker.py`: nhận `--profile <yaml>` (nạp qua
  `load_profile` + `scenario_for`, cùng đường với comparison thật) và
  `--seeds-from/--seeds-to`. Ba arm nhận **cùng một** scenario object;
  oracle bọc `GroundTruthObstacleProvider` quanh đúng scenario đó chứ
  không dựng thế giới riêng.
- **Môi trường chính của cổng:** profile mới
  `warehouse_crossing_v2` = `warehouse_crossing_v1` + `lidar` khai cấu
  hình được chọn ở Q0. Khai `lidar` là đổi thế giới ⇒ **id mới**, đúng
  luật đã dùng hai lần (`sensor_noise`, `v_obstacle_max`) — không sửa
  `_v1` tại chỗ.
- **Môi trường đối chứng, báo cáo không gate:** `intersection` với cùng
  cấu hình tia (qua override scenario trong harness) — để nối tiếp
  chuỗi số P4/P5 và tách "tracker khá lên" khỏi "bản đồ dễ hơn". Chỉ
  primary + harm trên `warehouse_crossing_v2` quyết định verdict.

```
ĐỊNH NGHĨA
  outcome rank:      theo OUTCOME_RANK của diagnose_tracker.py
                     (collision=0 < mọi non-arrival=1 < success=2)
  opportunity:       seed mà rank(oracle) > rank(dwa)
  recovered:         opportunity mà đồng thời rank(tracker) > rank(dwa)
  tracker-worse:     seed mà rank(tracker) < rank(dwa)

PRIMARY (cả hai phải đạt)
  P-a  sign test một phía trên các cặp bất đồng tracker-vs-dwa,
       H1: tracker tốt hơn, exact binomial, α = 0.05
  P-b  recovered / opportunities ≥ 0.40, với opportunities ≥ K = 15
       báo kèm Clopper-Pearson 95% CI của tỉ lệ (báo, không gate)

CỠ MẪU (khai trước, không quyết sau khi nhìn số)
  seed set B = {2000..2119}, disjoint với set A = {1000..1119} của
    Q0/Q2; dải {0..119} đã cháy (khảo sát §1 + lịch sử P4/P5) —
    không parameter nào được chỉnh sau khi nhìn số liệu trên B
  baseline dwa và oracle CHẠY LẠI trên B — số 11/120 của P4 thuộc
    dải cũ, chỉ dùng để ước lượng kỳ vọng, không để so
  bắt đầu n = 120 seed ghép cặp
  nếu opportunities < 15: mở rộng MỘT lần duy nhất lên n = 360
    (B mở rộng {2000..2359}; oracle P4 ~11/120 ⇒ kỳ vọng ~33/360)
  nếu vẫn < 15 sau 360: verdict = "không đủ cơ hội để đo" —
    tính là KHÔNG ĐẠT, không chạy thêm
  lý do K = 15: với K = 11, một cơ hội đổi phía xê dịch tỉ lệ 9 điểm
    phần trăm (4/11 = 36% vs 5/11 = 45% vắt qua ngưỡng 40%);
    K = 15 hạ bước nhảy xuống 6.7 điểm và, quan trọng hơn, buộc
    verdict phải kèm CI thay vì một phân số mỏng

HARM — vi phạm bất kỳ dòng nào ⇒ KHÔNG ĐẠT, bất kể primary
  va chạm:       số seed (tracker va, dwa không va) = 0 — tuyệt đối,
                 không margin: đây là trục an toàn, một va chạm mới
                 là một va chạm câu "về sau không tệ hơn dwa" không đỡ được
  thành công:    (số seed tracker-worse về success) ≤ (số tracker-better
                 về success) — success ròng không giảm; tracker được
                 phép hỏng một seed nếu cứu được ít nhất một seed khác.
                 [Mệnh đề "drop ≤ 1/120" của bản nháp đã BỎ theo review
                  16-08: nó mâu thuẫn margin với mệnh đề ròng — điều
                  kiện ròng đã cấm giảm, thêm "được phép giảm 1" là
                  hai định nghĩa cho một câu hỏi]
  min-clearance: HAI lớp, vì median một mình che được một nhóm nhỏ seed
                 bị giảm clearance rất mạnh:
                 (i)  median của Δ ghép cặp ≥ −5 mm
                      (5 mm = trên mức nhiễu float, dưới mức hành vi;
                      1 mm lệch do số thực KHÔNG phải fail)
                 (ii) near-miss rate của tracker ≤ near-miss rate của
                      dwa trên cùng seed set — dùng near-miss thay
                      percentile mới vì nó đã là metric của dự án
                      (clearance_warning_m, definitions.py:407), có
                      nghĩa an toàn đọc được sẵn
  p99 latency:   TUYỆT ĐỐI < 50 ms trên host đã ghim affinity,
                 ở cấu hình tia được chọn — không phải "không tăng"
```

**Kết quả âm là kết quả hợp lệ.** Plan này **không** cam kết một kết
quả dương.

**Định đoạt sau cổng — ba nhánh, chốt trước khi chạy (dev duyệt 16-08).**
"Rút" không có nghĩa xoá code; cả ba nhánh giữ implementation, oracle
test và diagnostics. Khác nhau ở chỗ candidate được **quảng bá** thế nào:

```
(a) Q4 ĐẠT
    giữ candidate; trạng thái ghi trong registry description:
      experimental — pass under zero localization noise
    bước kế tiếp bắt buộc: pha L17
    KHÔNG được ship — xem release gate bên dưới

(b) KHÔNG ĐỦ OPPORTUNITIES (< 15 sau 360 seed)
    giữ code cho nghiên cứu; trạng thái: inconclusive
    Decision Card không được recommend candidate này
    (cơ chế: hạ khỏi tập benchmarkable mặc định — xem dưới)

(c) PRIMARY hoặc HARM FAIL
    giữ code + test để tái lập nghiên cứu
    bỏ khỏi tập candidate production/default:
      registry hạ `benchmarkable` của astar+dwa_predictive và
      rrtstar+dwa_predictive (hoặc flag experimental tương đương),
      cập nhật test test_every_stack_a_fresh_clone_can_compare
      về đúng tập mới — test đó là exact set, tự nó sẽ gãy nếu quên
    đánh dấu: experimental / not recommendable
```

Lý do nhánh (b)/(c) mạnh hơn "giữ + ghi chú": một candidate không cải
thiện gì so với `dwa`, tốn latency và memory hơn, mà vẫn hiện diện như
lựa chọn bình thường trong registry — người dùng sẽ đọc nó là candidate
production hợp lệ. Ghi chú trong KNOWN_LIMITATIONS không đỡ được cách
đọc đó; vị trí trong registry mới đỡ được.

**Release gate — Q4 đạt ≠ được ship (dev duyệt 16-08).** Verdict dương
của Q4 chỉ có nghĩa: *candidate có tiềm năng khi pose không drift*.
Không được chuyển thành *candidate hoạt động trong warehouse thực*.
Chuỗi bắt buộc:

```
Q4 đạt → đáng đầu tư pha L17 (hệ toạ độ + localization noise)
       → chạy lại cổng dưới localization noise thật
       → chỉ SAU đó mới xét production-ready
```

Card và report của Q4 phải mang câu này nguyên văn, không phải chú
thích cuối trang.

---

### Q5 — G4 và G5, và G4 có thể tự mình giết plan · **1 ngày**

**G4 — latency.** `obstacle_points(observation)` là O(số tia);
`rollout_batch` là O(candidate × bước × điểm). Tăng tia làm tăng chi phí
local planner **tuyến tính theo điểm**.

Hiện trạng từ run P7: p99 = **27.42 ms** trên ngân sách **50 ms**. Biên
chỉ 1.8×. Wall-clock episode đo được 29.9 → 43.0 s khi đi từ 72 sang 144
tia (1.44×), nhưng **wall-clock không phải p99 latency** và không được
dùng thay.

Phải đo p99 thật ở cấu hình được chọn, **trước** Q4. Nếu 144 tia đẩy p99
qua 50 ms thì candidate rớt G4, và đó lại là một kết quả âm hợp lệ cần
ghi chứ không phải lý do nới ngưỡng.

**G5 — bộ nhớ, và hiện trạng là nó không nhìn thấy tri giác.** Ước lượng
cấu trúc của G5 hôm nay đếm search nodes, tree nodes, costmap cells và
một overhead cố định — **không có** số tia, không có cluster, không có
track history, và `perception_stack_mb` là ngân sách deployment khai
sẵn, không tự đổi khi tia 72 → 144. Nói "kiểm lại G5" mà không sửa gì
là kiểm bằng con số không chứa đại lượng vừa tăng.

Sửa cụ thể — mở rộng ước lượng cấu trúc bằng các số hạng tất định của
tracker, cùng kỷ luật "structure counters × byte size" mà G5 đã dùng.
Mọi ký hiệu định nghĩa tại chỗ, không để executor tự đoán:

```
bytes_tracker =
    num_rays × B_point                    # đám mây điểm world-frame
  + T_max × velocity_window × B_sample    # lịch sử track
  + T_max × C_max × B_pair                # cạnh (track, cluster) của Q2c

với (bytes theo hiện thực đích cpp_ros2, cùng quy ước
     bytes_per_search_node = 40 hiện có của G5):
  B_point  = 16   # (x, y) float64
  B_sample = 24   # (t, x, y) float64
  B_pair   = 24   # (track_ref 8, cluster_index 8, distance 8)

  C_max         = ceil(num_rays / 2)      # run xen kẽ tối đa;
                                          # num_rays/2 trần SAI với số
                                          # tia lẻ (271 ⇒ 136, không 135.5)
  C_movable_max = C_max                   # trần thô: mọi cụm đều qua lọc;
                                          # trần chặt hơn cần giả định về
                                          # scene — không được phép (§2b)
  frames_alive  = ceil(track_timeout / control_period) + 1
  T_max         = C_movable_max × frames_alive
```

**Không thêm runtime cap trong plan này.** `_tracks` đã có trần cấu
trúc: tối đa `C_movable_max` track mới mỗi frame, mỗi track sống tối đa
`frames_alive` frame trước khi `_expire` dọn ⇒ `len(_tracks) ≤ T_max`
là **định lý về code hiện tại**, không phải chính sách mới. Cap là thay
đổi hành vi tracker (phải có drop policy tất định, phải chạy lại Q0) để
giải một bài toán chưa được chứng minh tồn tại. Thay vào đó:

- viết công thức trần vào docstring của `LidarTracker`;
- counter `max_live_tracks` trong diagnostics + **test bất biến**:
  chạy các probe Q0 và khẳng định `max_live_tracks ≤ T_max`;
- chỉ nâng lên cap nếu phép đo bác được định lý — lúc đó nó là bug fix
  của `_expire`, có drop policy khai báo, và Q0 chạy lại.

**Thứ tự schema — gỡ mâu thuẫn của bản nháp trước:** "Q1 và Q5 chung
một schema bump" không khả thi vì Q1 land trước khi Q5 định nghĩa xong
counter. Chốt: **Q1 định nghĩa trọn bộ field mới của `TraceMetadata`
một lần** — `execution_conditions_fingerprint` (Q1 ghi ngay) và các
field counter tracker (`max_live_tracks`, `clusters_peak`, optional,
default `None`; Q5 bắt đầu ghi giá trị). Schema đổi một lần, giá trị
đến theo pha; field `None` đọc là "chưa đo", không phải "bằng không".

Nếu sau tất cả vẫn không muốn đưa tracker vào ước lượng cấu trúc, phương
án lùi hợp lệ duy nhất là **ghi thẳng vào card**: G5 của candidate này
chỉ được sàng bằng RSS chẩn đoán, chưa chứng nhận được — chứ không im
lặng để con số cũ đứng tên một tải mới.

---

### Q6 — Report + cập nhật hạn chế · **0.5 ngày**

- Report ở `docs/antongduy/reports/<ngày>/tongduyan_*.md`, phủ **mọi** pha
  gồm cả pha âm.
- Cập nhật **L16** (không còn đúng nếu Q4 đạt; đúng hơn nếu Q4 không đạt).
- **L19** mới: `episode_context_id` không băm environment; trace được
  định địa chỉ chỉ bằng `(candidate_id, episode_context_id)` nên
  reuse/score-only tin nhầm trace của thế giới cũ; `angle_span ≠ 2π`
  bị chặn ở validator vì cả tracker lẫn `dwa_core.obstacle_points`
  hardcode vòng tròn đầy — kèm bằng chứng `run_journal.jsonl` 120 dòng
  ở trên. Mục nào Q1.c đã vá thì ghi là đã vá, phần sửa hợp đồng còn
  lại ghi là nợ.
- L17 (hai hệ toạ độ) **vẫn treo** và trở nên gấp hơn: xem §5.

---

## 5. Cái plan này làm **tệ đi** — nói trước

Sàn vận tốc tỉ lệ `reach · Δθ`. Tăng gấp đôi số tia ⇒ **sàn giảm một
nửa**. Sàn đang là thứ che các vận tốc ma do **nhiễu định vị** sinh ra
(L17: rollout dùng pose thật, đám mây điểm dùng pose robot tin là).

Hôm nay điều đó bị che vì `warehouse_crossing_v1` khai
`localization_drift_m = 0`. Sau plan này, **khoảng cách giữa cấu hình đo
được và cấu hình team chạy thật sẽ rộng hơn**, không hẹp lại.

Nói thẳng: plan này làm `dwa_predictive` tốt hơn **trong một cấu hình
không có nhiễu định vị**, và đồng thời làm nó **nhạy hơn** với nhiễu định
vị. Pha hệ toạ độ (§2c của plan 14-08) đáng lẽ đứng trước. Tôi vẫn đề
xuất chạy plan này trước vì nó rẻ hơn và trả lời được câu hỏi "có đáng
theo tiếp không" — nhưng đây là **đánh đổi của dev**, không phải của tôi.

---

## 6. Quyết định cần dev chốt

**Cả tám quyết định đã được dev chốt ngày 2026-08-16**, ba mục có điều
chỉnh so với đề xuất (ghi ở cột cuối):

| # | Quyết định | Chốt | Điều chỉnh của dev |
|---|---|---|---|
| 1 | Thứ tự với pha L17 | plan này trước | **Kèm release gate**: Q4 đạt ≠ ship; Q4 đạt → đầu tư L17 → chạy lại dưới localization noise → mới xét production-ready. Đã ghi thành block trong Q4 |
| 2 | Ngưỡng cổng Q4 | ≥ 40% cơ hội oracle, K = 15, α = 0.05, mở rộng một-lần 120 → 360 | — |
| 3 | Trần latency tri giác | giữ 50 ms G4 | — |
| 4 | `episode_context_id` | fingerprint Q1.c trước, sửa hợp đồng ghi nợ | — |
| 5 | Định đoạt khi Q4 không đạt | **ba nhánh** thay cho "giữ + ghi" | (a) đạt: experimental-pass-under-zero-localization-noise, tiếp L17; (b) thiếu opportunities: inconclusive, card không recommend; (c) primary/harm fail: giữ code/test, **bỏ khỏi tập candidate production**, đánh dấu not-recommendable. Đã ghi thành block trong Q4 |
| 6 | `w_min = 0.3 m` (Q2a) | 0.3 m, candidate-owned, vào `candidate_id` | — |
| 7 | Biên harm Q4 | va chạm mới = 0; latency < 50 ms tuyệt đối | **Success**: bỏ mệnh đề "drop ≤ 1/120" (mâu thuẫn margin), giữ duy nhất điều kiện ròng ghép cặp. **Clearance**: thêm lớp hai — near-miss rate tracker ≤ dwa, vì median che được đuôi xấu. Đã sửa trong block Q4 |
| 8 | Trace thiếu fingerprint | fail-closed | — |

---

## 7. Ước lượng

| pha | ngày | chặn bởi |
|---|---|---|
| Q0 đo lại, commit script | 0.5 | — |
| Q1 cảm biến deployment-owned + fingerprint | 1.5 | Q0 |
| Q2a min_points theo tầm | 0.5 | Q0, Q1 |
| Q2b test tường liên tục | 1.0 | Q2a |
| Q2c gán toàn cục + từ chối | 1.0 | Q2b |
| Q3 `clipped` trong clutter | 0.5 | Q0 |
| Q5 G4 + G5 accounting | 1.0 | Q1, Q2 |
| Q4 cổng quyết định (gồm mở rộng harness + `warehouse_crossing_v2` + chạy lại baseline/oracle trên seed set mới) | 1.5 | tất cả |
| Q6 report | 0.5 | Q4 |
| **tổng** | **8.0** | |

Q0 có thể huỷ toàn bộ phần còn lại (§4, Q0 "rủi ro thật"). Đó là mục
đích của nó.

---

## Q0-KQ. Kết quả Q0 và đề xuất sửa hướng — **chờ dev chốt**

Chi tiết ở `notes/2026-08-16/tongduyan_q0-do-lai-do-phan-giai-lidar.md`.
Dưới đây là phần đổi plan.

### Q0-KQ.1 — Số

N = 20, seed A = 1000..1019, 17/20 seed có cuộc gặp.

```
                traffic                    |        cảnh tĩnh
 rays   vel_out   err_med    n  | phantom_rate  p90     tracks/f  per-track
   72     0.9%     0.429    22  |     14.17%   1.868      4.32      3.54%
  144     3.5%     0.935    84  |     78.56%   1.515     11.02     14.53%
  271     4.1%     0.813    97  |     97.52%   1.820     19.39     21.98%
  360     4.5%     0.864   107  |     99.19%   2.023     25.72     22.88%
```

### Q0-KQ.2 — Cơ chế, và vì sao Q2 không giải được

Ảo tăng do **cả hai** thừa số: `tracks/frame` ×6.0 **và** `per-track`
×6.5. Q2b (test tường) chỉ tấn công thừa số thứ nhất. Kể cả nếu nó hoàn
hảo — đưa 25.72 track/frame về 4.32 — thì `per-track` vẫn 22.88% thay
vì 3.54%, và ảo vẫn cao hơn baseline nhiều lần.

Bằng chứng quyết định nằm ở cột `p90`: biên độ vận tốc ảo **phẳng**
(1.5–2.0 m/s) qua mọi độ phân giải, trong khi sàn chặn nó co tuyến tính
theo `Δθ`:

```
velocity_floor = (2·σ_pose + margin·σ_range + reach·Δθ) / window
tại 4 m:  72 tia -> 0.584 m/s      360 tia -> 0.186 m/s
```

Số hạng `reach·Δθ` (thêm ở P5) giả định **biên độ ảo tỉ lệ khoảng cách
tia**. Phép đo nói **không**. Sàn đúng ở 72 tia vì trùng hợp độ lớn,
không vì mô hình đúng. Nguồn ảo trội thật sự là centroid trượt dọc bề
mặt khi robot di chuyển — phụ thuộc chuyển động robot, không phụ thuộc
`Δθ`.

### Q0-KQ.3 — Đề xuất sửa hướng

**Đảo thứ tự. Sàn vận tốc phải thiết kế lại TRƯỚC, trước cả chuyện độ
phân giải.** Plan mới đề xuất:

| pha | việc | vì sao trước |
|---|---|---|
| **R1** | Đo nguồn ảo trội: tách đóng góp của (i) lượng tử hoá tia, (ii) centroid trượt theo chuyển động robot, (iii) nhiễu range. Cảnh tĩnh, robot **đứng yên** vs **di chuyển** | `p90` phẳng nói mô hình hiện tại sai; phải biết sai ở đâu trước khi viết công thức mới |
| **R2** | Thiết kế lại sàn từ mô hình đo được ở R1. Nhiều khả năng có số hạng tỉ lệ **tốc độ robot**, không tỉ lệ `Δθ` | Đây là thứ chặn ảo; sửa nó là điều kiện cần cho mọi việc sau |
| **R3** | Chạy lại harness Q0 với sàn mới. **Chỉ khi** ảo không còn bùng nổ theo độ phân giải mới xét tiếp Q1/Q2 | Q0 là cổng, không phải thủ tục |

> ### R1 ĐÃ CHẠY — R2 như trên KHÔNG còn là bước đúng
>
> `notes/2026-08-16/tongduyan_r1-nguon-van-toc-ma.md`, dữ liệu
> `artifacts/r1_phantom/`. Ba số đổi hướng:
>
> **(1) Sàn chưa bao giờ là cổng chính.** Phân rã lý do bị zero (nhà kho,
> đứng yên + nhiễu): `coasting` 72–85%, `warmup` 4–7%, **`floored`
> 2–5%**. Thứ giữ tracker im lặng là track không được nhìn thấy, không
> phải sàn. `dwa_predictive` đang an toàn **nhờ tri giác kém**.
>
> **(2) Hình học quyết định, không phải độ phân giải.** Cùng ego-motion,
> cảm biến **hoàn hảo**, tỉ lệ raw fit vượt 0.1 m/s: `isolated_object`
> 9.7% → 0.0%; `warehouse` **84.3% → 84.6%**, phẳng theo độ phân giải.
> Một vật cô lập gọn gàng gần như không sinh ảo ở bất kỳ độ phân giải nào.
>
> **(3) Cụm sống sót trải qua nhiều hơn một bề mặt — nhưng CƠ CHẾ chưa
> xác định.** Survivor ở nhà kho: `width` 1.14–1.28 m, `straightness`
> **0.56–0.62** — gấp 7 lần ngưỡng tường 0.08, nên test tường không bao
> giờ kích hoạt. Mặt kệ phẳng không nhiễu phải có residual ≈ 0, nên
> residual nửa mét chứng minh cụm trải qua nhiều bề mặt.
>
> Hai giả thuyết đầu **đều bị dữ liệu bác**: (a) *gộp do ngưỡng tách quá
> rộng* — ngưỡng tỉ lệ `Δθ` nên ở 360 tia chặt gấp 5 lần, mà
> `straightness` không đổi (0.382/0.620/0.558/0.586); (b) *cụm trải qua
> góc tường* — hình học `corner` tổng hợp **có góc** và cho **0 ảo**
> (24 record raw toàn 0.000), y như `straight_wall`. Chỉ bản đồ nhà kho
> thật sinh ảo.
>
> **R1b ĐÃ CHẠY — cơ chế đã xác định: CỤM TRẢI QUA MỘT GÓC.**
> Điểm quét thật của cụm sinh ảo mạnh nhất (72 tia, nhiễu tắt):
> ba điểm trên `y = 6.000`, hai điểm trên `x = 6.000` — một góc vuông kệ
> tại (6.000, 6.000). Bậc range lớn nhất giữa hai tia kề: 0.55 m; ngưỡng
> tách ở 4 m: ≈1.05 m. **Không đủ tách.** Một cụm, hai mặt phẳng.
>
> Centroid trượt 0.305 m trong 0.70 s = **0.436 m/s**, khớp đúng
> `out_speed`. Robot đi `+x` nên tỉ lệ nhìn thấy giữa hai mặt đổi trơn
> tru, centroid của hợp hai mặt trượt dọc góc.
>
> **Và nó TRƠN TRU** — least-squares 15 khung cho một vận tốc ổn định,
> tự tin. Trong bản thân tín hiệu vận tốc không có gì phân biệt nó với
> vật thật đi 0.436 m/s. Đây là lý do cuối cùng và đủ để bỏ hướng
> "thiết kế lại sàn": **không đại lượng nào tính từ vận tốc tách được
> hai thứ này.**
>
> Chữ ký nhất quán toàn bộ cụm sống sót (72 và 271 tia): residual đỉnh ở
> giữa cụm (`peak@` 0.40–0.59), `path/chord` 1.20–1.41, **0** cụm lân
> cận trong 2.5 m. Đối chứng `isolated_object` (vật tròn, cung thoải,
> `path/chord` ≈ 1.0) cho ảo ≈ 0.
>
> **Bản sửa, và nó đơn giản hơn Q2b đang viết:** tách cụm tại **chỗ đổi
> hướng bên trong nó**, trước bước phân loại. Tách xong mỗi chân là mặt
> phẳng dài và thẳng ⇒ **test tường hiện có** loại được cả hai. Không
> cần họ ngưỡng mới.
>
> Q2b hiện hỏi *"các cụm lân cận có nối tiếp cùng đường thẳng không"*
> (giữa các cụm). Cái cần là *"chính cụm này có phải một đường thẳng
> không"* (trong một cụm). Đặc tả Q2b phải viết lại theo hướng đó —
> phần continuation/`wall_continuity_factor` không còn cần thiết.

> ### BẢN SỬA ĐÃ XÂY, ĐO, VÀ THU HỒI — Q2b ĐÓNG BẰNG KẾT QUẢ ÂM
>
> Hiện thực đầy đủ, 24 test, đúng hoàn toàn trên hình học sạch (góc tách,
> tường/góc-thoải/đĩa-tròn không tách). **Trên bản đồ thật: ảo không đổi
> (14.17% → 14.18%, 99.19% → 99.19%), phát hiện thật giảm (271 tia
> 3.5% → 2.1%).** Splitter có chạy 165–222 lần/240 frame — trên những cụm
> khác, không phải cụm sinh ảo.
>
> **Lý do, đo trực tiếp:** chân góc thật ở nhà kho có tỉ lệ cong
> 0.088–0.228; chân đĩa tròn 0.207. **Chồng lấn.** Quét ngưỡng xác nhận
> không tồn tại điểm vận hành nào vừa bắt góc thật vừa tha vật tròn:
>
> ```
> tol=1.5 leg=0.08   CORNER [0,1,1,1]   DISC [0,0,0,0]   ← an toàn, vô dụng
> tol=1.0 leg=0.15   CORNER [0,1,1,1]   DISC [0,1,1,1]   ← hữu dụng, cắt vật tròn
> ```
>
> Gốc rễ: mỗi đặc trưng chỉ được **3–7 tia** lấy mẫu. Khớp "hai đoạn
> thẳng" vào 6 điểm với một chân 2–3 điểm không phải phép đo có ý nghĩa.
> Chữ ký hình học **tồn tại**; cảm biến không đủ độ phân giải để đọc.
>
> **Đây là §Q0-KQ.4 xảy ra.** Ghi trước như "khả năng phải chấp nhận",
> giờ là số đo. Code sản phẩm đã thu hồi (dev chốt 16-08); giữ
> `scripts/diagnose_phantom.py` và hai note.
>
> **Hệ quả cho phần còn lại của plan:** Q2a/Q2b/Q2c và Q3 đều tấn công
> khâu nhận cụm bằng hình dạng. Q2b là cái có bằng chứng mạnh nhất và nó
> vừa thất bại vì lý do **áp dụng cho cả bốn**: không đủ tia trên mỗi đặc
> trưng. Chạy tiếp Q2a/Q2c/Q3 mà không có bằng chứng mới là lặp lại cùng
> một thất bại ba lần nữa.
>
> **Kết luận:** hướng sửa là **khâu nhận cụm**, không phải sàn. Hai giới
> hạn cứng của hướng thiết-kế-lại-sàn: ảo do nhiễu range đạt p99 **8.6
> m/s** (không sàn hợp lý nào chặn nổi), còn ảo do chuyển động toàn dưới
> **0.6 m/s** (một sàn 0.6 sẽ dọn sạch, nhưng crosser thật đi 0.8 m/s —
> biên 0.2 m/s quá mỏng để gọi là ràng buộc).
>
> **R2 thay bằng: Q2b + Q3 — nhưng ngược chiều lập luận cũ.** Lập luận
> cũ: độ phân giải mịn làm tường **vỡ vụn** thành mảnh hẹp lọt test bề
> rộng. Đo được: ở **mọi** độ phân giải vấn đề là **gộp** nhiều bề mặt
> thành một cụm lọt test độ thẳng. Ngược chiều, cùng một chỗ hỏng —
> `_is_free_standing` nhận vào những thứ không phải vật. Đặc tả Q2b
> (test tường theo **chuỗi cụm**) và Q3 (`clipped`) vẫn dùng được nguyên
> văn; chỉ phần *vì sao* trong plan phải viết lại.
>
> Sửa `reach·Δθ` vẫn đáng làm nhưng **không** là tiên quyết, và một mình
> nó không cứu được gì.

Q1 (cảm biến deployment-owned) **vẫn có giá trị độc lập** — nó là điều
kiện để so hai cảm biến ở bất kỳ phép đo nào, kể cả R3, và nó đi kèm
`execution_conditions_fingerprint` là món nợ thật cần trả. Nhưng nó
**không còn là đường tới kết quả**, mà là hạ tầng đo.

Q2a/Q2b/Q2c chuyển thành **có điều kiện**: chỉ có nghĩa sau khi R2 xong
và R3 cho thấy độ phân giải cao trở nên dùng được.

### Q0-KQ.4 — Khả năng phải chấp nhận

Nếu R1 cho thấy nguồn ảo trội là centroid trượt dọc tường theo chuyển
động robot, thì đó **không phải** thứ một cái sàn vô hướng chặn được —
nó cần phân biệt "cụm này là bề mặt tĩnh" với "cụm này là vật", tức
đúng bài toán mà `_is_free_standing` đang giải sai. Khi đó câu trả lời
trung thực có thể là: **tri giác 2D LiDAR đơn thuần không đủ để ước
lượng vận tốc vật cản trong môi trường có tường gần**, và
`dwa_predictive` nên đóng bằng kết quả âm theo nhánh (c) của §Q4.

Ghi trước ở đây để nhánh đó không bị coi là thất bại của người thực hiện
khi nó xảy ra.

---

## 8. Cái plan này **không** làm

- Không tái thu nhận track sau khoảng trống > `track_timeout`. Vẫn là
  bài toán re-identification, vẫn ngoài phạm vi MVP.
- Không ngoại suy qua khoảng che khuất. Cần một `confidence` mà hàm cost
  thật sự đọc — pha riêng.
- Không đụng mô hình vận tốc hằng (L13). Vật rẽ hoặc dừng vẫn sai.
- Không sửa `v_obstacle_max` / L18. Bài toán khác: cần phân biệt vật
  **có thể** lại gần với vật đứng yên, và nó phụ thuộc chính tracker này
  chạy được đã.
- Không sửa L8 (`kinematics.step` zero-order hold, lạc quan ~20 mm).

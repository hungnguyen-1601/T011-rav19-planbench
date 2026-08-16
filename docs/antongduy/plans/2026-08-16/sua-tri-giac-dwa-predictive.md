# Sửa tầng tri giác của `dwa_predictive`

**Trạng thái:** chờ dev duyệt. Chưa viết dòng code sửa nào.
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

**Không đổi một dòng code sản phẩm nào ở pha này.**

**Ra khỏi pha khi:** bảng 1.4 được tái lập (hoặc bác bỏ) ở N ≥ 20, và
script đã commit.

**Rủi ro thật:** N=20 có thể cho thấy 144 không phải đỉnh, hoặc tính không
đơn điệu là artefact của một seed. Nếu vậy **plan này phải viết lại** —
và đó là lý do Q0 đứng trước.

---

### Q1 — Cảm biến trở thành thứ deployment khai · **1 ngày**

Hôm nay `LidarConfig(num_rays=72, max_range=5.0)` là **default cứng** ở
`scenario.py:78`, không profile nào khai được. Hệ quả: không thể có hai
deployment cùng bản đồ khác cảm biến, tức không thể so được.

1. `EnvironmentSpec.lidar: LidarConfig | None = None` — `None` giữ nguyên
   default, nên **mọi profile đã có không đổi một float nào**.
2. Nối qua `scenario_for()` trong `episode.py`.
3. Ghi vào manifest (HĐ-13) cạnh `sensor_noise`.

**Điểm bắt buộc, và nó là bài học vừa trả giá:** `episode_context_id` bị
HĐ-3.1 đóng băng ở *(task profile, mission, variant, seed)*. Cảm biến
**không** nằm trong payload. Codebase đã ghi cái bẫy này hai lần
(`sensor_noise`, `replanning`) với cùng một lời giải: *đổi profile ⇒
`task_profile_id` mới*.

Nhưng lời giải đó **có lỗ, và tôi vừa rơi vào nó ở P7**. Chạy lại
`warehouse_crossing_v1` sau khi rút `v_obstacle_max` cho ra:

```
run_journal.jsonl:  120 bản ghi
  60 đầu:  toàn 'stuck'   (profile có v_obstacle_max)
  60 sau:  toàn 'success' (profile đã rút)
  episode_context_id block 1 == block 2 == b408516ece7f
```

Hai thế giới khác nhau, **cùng context id, cùng thư mục run, journal nối
đuôi nhau**. Người đọc file này sẽ kết luận episode đó chập chờn. Guard
"từ chối nộp lại profile đã đổi dưới id cũ" nằm ở luồng API; `compare.py`
nạp YAML thẳng từ path nên **đi vòng qua guard**.

4. Thêm đúng phép kiểm đó vào `compare.py`: checksum nội dung profile,
   đối chiếu với run đã lưu dưới cùng `task_profile_id`, **từ chối** nếu
   khác. Kèm regression test.
5. Ghi hạn chế mới (L19) cho tới khi (4) xong.

**Ra khỏi pha khi:** một profile khai được 144 tia, manifest ghi đúng, và
chạy lại profile đã sửa dưới id cũ bị **từ chối** chứ không ghi đè.

---

### Q2 — Ngưỡng co giãn theo cảm biến · **1.5 ngày**

Đây là pha làm cho việc tăng tia thôi phản tác dụng.

| ngưỡng | hôm nay | đề xuất | suy ra từ |
|---|---|---|---|
| `cluster_min_points` | `3` tia | số tia tối thiểu để một vật rộng `w_min` ở tầm `max_range` còn phân giải được | `Δθ`, `max_range` |
| `cluster_wall_width` | `0.9` m | test tường không dựa vào bề rộng **một** cụm, mà vào việc **các cụm lân cận có nối tiếp cùng đường thẳng không** | hình học cụm |
| `association_margin` | `0.25` m | giữ margin, nhưng thay veto-nhập-nhằng bằng **gán toàn cục** (nearest-neighbour toàn cục hoặc Hungarian) | — |

Ghi chú về từng cái:

- **`cluster_min_points`**: đây là ngưỡng duy nhất mà việc "hạ xuống 2"
  nghe hợp lý và **có thể sai**. Cụm 2 điểm có centroid do nhiễu range
  chi phối; sàn vận tốc sẽ dập phần lớn, nhưng phần lọt qua là vận tốc
  rác. Phải đo cột "vận tốc ma trên cảnh tĩnh" của Q0 trước và sau.
- **Test tường**: nguyên nhân thoái lui ở 271/360 tia. Mảnh tường hẹp
  hiện lọt vì test chỉ nhìn bề rộng của **chính** cụm đó. Sửa đúng là hỏi
  *"cụm bên cạnh có tiếp tục cùng một đường thẳng không"* — bất biến
  theo độ phân giải.
- **Gán toàn cục**: `_associate` hiện duyệt từng track theo thứ tự list,
  và **bỏ hẳn** track nào có ≥2 cụm trong cổng. Ở Δθ mịn, mật độ cụm tăng
  ⇒ `ambiguous_drops` đi **2 → 894** (72 → 360 tia, bảng §1.4) ⇒ track
  thật bị hi sinh. Gán toàn cục giải đúng bài toán này và **không** làm
  yếu nguyên tắc "nhập nhằng thì trả zero": nhập nhằng thật vẫn còn sau
  khi gán tối ưu.

  Lưu ý thứ tự sửa: nếu Q2 sửa được test tường thì `cụm-"động"/frame` tụt
  từ 8.76 xuống gần 1, và phần lớn nhập nhằng biến mất theo. Gán toàn cục
  là lớp phòng thủ thứ hai, **không** phải cách vá cho test tường sai.

**Ra khỏi pha khi:** bảng Q0 chạy lại cho thấy tỉ lệ ra vận tốc **đơn
điệu tăng** theo số tia, hoặc ít nhất phẳng — không còn thoái lui — và
vận tốc ma trên cảnh tĩnh **không tăng**.

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

### Q4 — Cổng quyết định · **1 ngày** · **khai trước khi chạy**

Lặp lại đúng thiết kế cổng của P4, vì nó đã bắt được một kết luận sai một
lần rồi.

Ba nhánh, cùng seed, ghép cặp: `dwa` — oracle (tri giác hoàn hảo) —
`dwa_predictive` (tracker thật, cảm biến mới, ngưỡng mới).

**Khai trước, trước khi chạy:**
- n ≥ 120 seed ghép cặp
- Thống kê: sign test một phía trên **các cặp bất đồng**, không phải hiệu
  tỉ lệ trên toàn bộ — đúng sai lầm mà cổng P4 mắc lần đầu.
- **Ngưỡng đạt:** tracker giành lại **≥ 40%** số cơ hội mà oracle giành
  được. Hôm nay là **0/11**. Con số 40% là ngưỡng do dev chốt, không phải
  do tôi suy ra — xem §6.
- Metric bảo vệ (bất kỳ cái nào xấu đi ⇒ **không đạt**, bất kể p-value):
  va chạm, tỉ lệ thành công, khoảng hở nhỏ nhất, p99 latency.

**Kết quả âm là kết quả hợp lệ.** Nếu tracker vẫn không giành lại được
phần đáng kể, kết luận đúng là: `dwa_predictive` bị giới hạn bởi tri giác
2D ở mọi độ phân giải khả thi, và nên **rút** hoặc ghi vĩnh viễn là
sensor-limited. Plan này **không** cam kết một kết quả dương.

---

### Q5 — G4, và nó có thể tự mình giết plan · **0.5 ngày**

`obstacle_points(observation)` là O(số tia); `rollout_batch` là
O(candidate × bước × điểm). Tăng tia làm tăng chi phí local planner
**tuyến tính theo điểm**.

Hiện trạng từ run P7: p99 = **27.42 ms** trên ngân sách **50 ms**. Biên
chỉ 1.8×. Wall-clock episode đo được 29.9 → 43.0 s khi đi từ 72 sang 144
tia (1.44×), nhưng **wall-clock không phải p99 latency** và không được
dùng thay.

Phải đo p99 thật ở cấu hình được chọn, **trước** Q4. Nếu 144 tia đẩy p99
qua 50 ms thì candidate rớt G4, và đó lại là một kết quả âm hợp lệ cần
ghi chứ không phải lý do nới ngưỡng.

Ghi chú: `perception_stack_mb` trong `hardware` cũng đang giả định một
tải tri giác; tăng tia 2× nên kiểm lại G5.

---

### Q6 — Report + cập nhật hạn chế · **0.5 ngày**

- Report ở `docs/antongduy/reports/<ngày>/tongduyan_*.md`, phủ **mọi** pha
  gồm cả pha âm.
- Cập nhật **L16** (không còn đúng nếu Q4 đạt; đúng hơn nếu Q4 không đạt).
- **L19** mới: `episode_context_id` không băm environment, và
  `compare.py` đi vòng qua guard nộp-lại-profile — kèm bằng chứng
  `run_journal.jsonl` 120 dòng ở trên.
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

| # | Quyết định | Đề xuất của tôi | Vì sao cần dev |
|---|---|---|---|
| 1 | Chạy plan này trước, hay làm pha hệ toạ độ (L17) trước | plan này trước | §5 — đây là đánh đổi ưu tiên, không phải kỹ thuật |
| 2 | Ngưỡng đạt của cổng Q4 | ≥ 40% cơ hội oracle | Số này quyết định "thành công" nghĩa là gì. Không được chốt sau khi thấy kết quả |
| 3 | Trần latency chấp nhận được cho tri giác | giữ nguyên 50 ms G4 | Nới ngân sách là quyết định phần cứng |
| 4 | `episode_context_id`: sửa hợp đồng (băm environment, MAJOR, mọi id cũ đổi) hay giữ luật "profile đổi ⇒ id mới" + vá `compare.py` | vá `compare.py` trước, ghi sửa hợp đồng là nợ | Sửa hợp đồng làm mọi run đã lưu bất khả so |
| 5 | Nếu Q4 không đạt: rút `dwa_predictive` hay giữ và ghi sensor-limited | giữ + ghi | Ảnh hưởng thứ team ship |

---

## 7. Ước lượng

| pha | ngày | chặn bởi |
|---|---|---|
| Q0 đo lại, commit script | 0.5 | — |
| Q1 cảm biến deployment-owned + guard | 1.0 | Q0 |
| Q2 ngưỡng co giãn | 1.5 | Q0, Q1 |
| Q3 `clipped` trong clutter | 0.5 | Q0 |
| Q5 G4/G5 | 0.5 | Q1, Q2 |
| Q4 cổng quyết định | 1.0 | tất cả |
| Q6 report | 0.5 | Q4 |
| **tổng** | **5.5** | |

Q0 có thể huỷ toàn bộ phần còn lại (§4, Q0 "rủi ro thật"). Đó là mục
đích của nó.

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

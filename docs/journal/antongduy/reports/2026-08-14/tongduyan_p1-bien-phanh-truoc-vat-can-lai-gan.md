# P1 — `v_obstacle_max` ở lớp 2: biên phanh trước vật cản đang lại gần

**Ngày:** 2026-08-14
**Plan:** `docs/antongduy/plans/2026-08-14/du-doan-chuyen-dong-vat-can.md`, P1
**Tiền đề:** P0 dương tính — xem
`tongduyan_p0-lo-hong-phanh-vat-can-lai-gan.md`
**Trạng thái:** xong · **chưa commit, chưa chạy full suite — chờ lệnh**

---

## 1. Làm gì

P0 đo được: bảo đảm phanh của phase 1b phát biểu trên **lần quét hiện
tại**, tức chỉ hứa *dừng kịp trước vật cản **đang đứng***. P1 mở rộng nó
để phủ luôn quãng vật cản đi trong lúc robot phanh, **áp cho cả hai
controller như nhau**, và bắt con số đó phải **được kiểm chứng** chứ
không chỉ được khai.

Biên mới, thay cho `v·T + v²/(2a)`:

```
(v + u)·T  +  v²/(2a)  +  u·v/a  ≤  headroom
```

- `u·v/a` — quãng vật cản đi trong `t_stop = v/a` giây robot phanh. Với
  robot mặc định (`v` 0.8, `a` 0.5) đó là **1.6 giây**, trong đó một xe
  đẩy 1.0 m/s đi thêm **1.6 m**. Đây là số hạng đắt nhất.
- `(v + u)·T` — quãng **cả hai** cùng khép trong chu kỳ phản ứng.

Giải đóng dạng theo `v` (vẫn bậc hai, không lặp điểm cố định):

```
A = 1/(2a),  B = T + u/a,  C = u·T − headroom
v = a·(√(B² + (2/a)·(headroom − u·T)) − B)
```

**Với `u = 0` biểu thức trở về đúng công thức cũ, từng float một.** Đó
không phải tiện lợi mà là điều kiện: deployment không khai gì phải giữ
nguyên hành vi, nếu không mọi lượt chạy đã lưu mất hiệu lực.

---

## 2. Đã đổi gì

| file | việc |
|---|---|
| `packages/schemas/planbench_schemas/dynamic.py` | `max_speed(motion) -> float` cho bốn luật, cộng nhánh `NotImplementedError` tường minh cho luật tương lai |
| `packages/schemas/planbench_schemas/feasibility.py` | `admissible_speed(headroom, robot, reaction_seconds, obstacle_speed=0.0)` — **mới**, và nó là chỗ số học này lẽ ra phải ở từ đầu |
| `packages/schemas/planbench_schemas/task_profile.py` | `EnvironmentSpec.v_obstacle_max: float \| None = None` + validator lúc nạp |
| `packages/planning/planbench_planning/dwa/planner.py` | `reset()` nhận `obstacle_speed`; `_speed_that_stops_within` thành uỷ nhiệm cho `admissible_speed` |
| `services/simulator/planbench_simulator/nav_stack.py` | `run_stack(..., obstacle_speed=None)`; `_reset_local` dò chữ ký cho **hai** tham số độc lập |
| `packages/benchmark/planbench_benchmark/episode.py` | truyền `profile.environment.v_obstacle_max` xuống |
| `packages/decision/planbench_decision/card.py` | `Manifest.v_obstacle_max`, và **`replanning` nay mới thật sự được ghi** — xem 4.4 |
| `contracts/CONTRACTS.md` · `contracts/schemas/manifest.schema.json` | HĐ-2.6 mới, manifest schema, bump **6.8.0 → 6.9.0** (MINOR) |
| `apps/web/.../DeploymentForm.tsx` + hai file locale | control khai biên, có công tắc bật/tắt |
| `docs/KNOWN_LIMITATIONS.md` | L7–L11 |

### 2.1. Ba quyết định đáng nói

**`admissible_speed` chuyển từ planner sang `feasibility.py`.** Trước
đây `_speed_that_stops_within` là method của `DWAPlanner`, tức số học
quyết định *robot được đi nhanh tới đâu* nằm trong lớp mà config của
candidate với tới được. Chuyển sang `feasibility.py` làm chữ ký chỉ còn
`(RobotConfig, ba float deployment sở hữu)` — **L2 được cưỡng chế bằng
hệ kiểu**, đúng cách `hard_clearance` đã làm. Method cũ giữ lại thành
một dòng uỷ nhiệm nên chỉ có **một** hiện thực.

**Trường đặt ở `EnvironmentSpec`, không ở top level.** Nó là một tuyên
bố *về hiện trường* và validator của nó cần đọc `dynamic_obstacles` nằm
ngay cạnh — không phải với qua model khác. Cùng chỗ với `sensor_noise`,
cùng lý lẽ 2.3/2.5.

**Đi tới `run_stack` bằng tham số, không qua `Scenario`.** Đây là điểm
tôi cân nhắc lâu nhất và nó không phải chuyện phong cách:

| | đổi cái gì | hệ quả |
|---|---|---|
| `sensor_noise` (trên `Scenario`) | **thế giới** | `_scenario_checksum` **phải** đổi, và mọi report đã lưu bị mồ côi — cái giá đã chấp nhận ở 6.2.0 |
| `replanning`, `recovery` (tham số `run_stack`) | **luật áp lên** thế giới | checksum không đổi, không report nào mồ côi |

`v_obstacle_max` **không đổi thế giới** — mọi vật cản chuyển động y hệt.
Nó đổi thứ robot được phép làm. Nên nó thuộc nhóm thứ hai, và đi đường
đó thì `_scenario_checksum` đứng yên, cache độ khó P03 không bị stale,
không report cũ nào mất id. Hệ quả hợp đồng vẫn giống `replanning`:
`episode_context_id` không băm nó ⇒ khai nó là **`task_profile_id`
mới**, và manifest phải ghi.

---

## 3. Ba nghĩa của trường, và vì sao `None` chứ không phải `0.0`

| giá trị | nghĩa | validator |
|---|---|---|
| `None` *(mặc định)* | chưa khai. Hành vi **y hệt** trước bản này, **không mang** tuyên bố an toàn phanh trước vật cản động | không chạy — không có tuyên bố để kiểm |
| số dương | đã khai | kiểm với mọi luật chuyển động khai cạnh nó |
| `0.0` | tuyên bố *"ở đây không gì chuyển động"* | **từ chối** nếu environment khai vật cản động |

Bản vòng 4 của plan bắt được điều này và nó đúng: mặc định `0.0` sẽ
**mâu thuẫn với chính validator của pha này** — mọi profile đang ship
đều khai traffic, nên chúng sẽ trượt lúc nạp và pha này hết
backward-compatible ngay tại chỗ. `None` mang nghĩa *"chưa đo"*, đúng
tiền lệ `robustness_margin: float | None`.

`default=0.0` trên `max(...)` cũng không phải trang trí: thiếu nó,
deployment **không có** vật cản động ném `ValueError` ngay trong
validator — tức khai `0.0` trung thực lại là ca duy nhất bị crash.

---

## 4. Đo được

### 4.1. Trước và sau, cùng một dụng cụ

`astar+dwa`, sảnh trống, xe đẩy lao thẳng vào robot, tắt hết nhiễu, robot
`v_max` 0.8 / `a` 0.5. Tốc độ lúc chạm đo bằng **phép quét trong bước**,
lấy vận tốc theo đúng mô hình tích phân của engine — xem 4.7:

| tốc độ xe đẩy | **không khai** | | **có khai** | |
|---|---|---|---|---|
| (m/s) | bước vượt biên | tốc độ lúc chạm | bước vượt biên | tốc độ lúc chạm |
| 0.20 | 16 | 0.350 m/s | **0** | **0.000 m/s** |
| 0.30 | 12 | 0.378 m/s | **0** | **0.000 m/s** |
| 0.60 | 9 | 0.440 m/s | **0** | **0.000 m/s** |
| 1.00 | 8 | 0.575 m/s | **0** | **0.000 m/s** |
| 1.50 | 6 | 0.638 m/s | **0** | **0.000 m/s** |

Với **trọng số đang ship**: cột không khai đọc 0.155–0.575 m/s, cột có
khai bằng **0** ở mọi hàng, và 0 bước vượt biên. Biên không phải số hạng
mềm mà một cấu hình vặn xuống được — đó chính là lý do nó ở deployment.

"Bước vượt biên" = bước mà tốc độ robot vượt quá thứ khe hở đo được cho
phép, chừa **một bước giảm tốc** (`a·T` = 0.025 m/s) làm dung sai. Dung
sai đó **có dùng tới và dùng sát**: mức vượt lớn nhất đo được là
0.0215–0.0248 m/s, tức tới 99% của một bước, và **không bao giờ quá**.
Nhỏ hơn thì sẽ đỏ vì vật lý controller không thắng được; lớn hơn thì
thôi phát hiện được vi phạm thật.

### 4.2. Tuyên bố được kiểm chứng

*Controller tuân thủ biên vận tốc ở mọi bước*, không bao giờ vượt quá
đúng một bước giảm tốc mà nó không thể đã áp — và từ đó: **robot đứng
yên khi xe đẩy tới**, ở mọi tốc độ, thay vì lao vào ở tới 0.638 m/s.

Một điều kiện đọc kèm, thuộc simulator chứ không thuộc P1: đây là vật lý
**rời rạc** của `kinematics.py`, giữ một vận tốc cho cả bước. Robot giảm
tốc **liên tục** sẽ đi thêm `½·a·dt²` mỗi bước — 0.625 mm, ≈ 20 mm qua
một lần phanh đầy từ 0.8 m/s — nên simulator **lạc quan** về quãng phanh
đúng chừng đó. Ghi thành L8.

### 4.3. Cơ chế, `u` = 1.0 m/s

Hai cột đọc trên **cùng một mốc quy chiếu** — mẫu đầu tiên có tốc độ
dưới `v_max`. Trộn hai mốc là chỗ bản trước ghi sai "1.16 s":

```
                       không khai                  có khai
bắt đầu phanh    t=5.20, gap 0.601 m         t=4.45, gap 2.175 m
                                             sớm hơn 0.75 s, dư 1.574 m khe hở
chạm             t=5.5595, v = 0.575 m/s     t=6.0294, v = 0.000 m/s
                 lao vào                     robot đi 0 mm trong bước đó
```

Lấy mốc "mẫu cuối còn ở `v_max`" (5.15 / 4.40, gap 0.690 / 2.264) ra
**đúng cùng hiệu**: 0.75 s và 1.574 m. Hiệu là bất biến; chỉ mốc tuyệt
đối đổi.

Ở bước chứa điểm chạm, robot **không dịch chuyển chút nào** — xe đẩy tự
đi vào nó. Đó vẫn là **va chạm**, và không giới hạn tốc độ nào với tới
được — xem 4.5.

### 4.4. Hai lỗ hổng manifest gặp dọc đường, đã vá

**(a) `replanning` chưa bao giờ được ghi ra.** Có trong model từ 6.4.0,
có trong `manifest.schema.json`, và `to_json_dict` **không hề serialise
nó**. `additionalProperties: false` không bắt được một thuộc tính **vắng
mặt**, nên mọi manifest từng viết đều thiếu đúng cái điều kiện mà
docstring của chính nó gọi là bắt buộc.

**(b) Danh sách `required` thiếu ba trường.** `sensor_noise`,
`replanning`, `v_obstacle_max` chỉ được khai dưới `properties`, tức
schema **vẫn chấp nhận** một manifest không có chúng. Khai một trường
không phải là **bắt buộc** một trường, và chỉ một test phân biệt được hai
việc đó. Đã thêm cả ba vào `required` kèm test hồi quy: xoá từng trường
khỏi payload thì schema phải từ chối.

**Về artifact cũ:** manifest đã lưu trong `artifacts/runs/` **vốn đã**
không hợp lệ với schema hiện tại — bản 2026-08-10 thiếu `constraints` và
`sensor_noise` (bắt buộc từ 6.4.0), bản cũ hơn còn mang
`episode_context_ids` đã bỏ từ 5.0.0. Schema này **luôn** mô tả thứ phiên
bản hiện tại phải ghi, không mô tả thứ artifact cũ chứa, và không chỗ nào
trong code kiểm lại manifest đã lưu. Nên siết `required` **không phá gì**
— nó theo đúng tiền lệ `constraints` đã đặt.

### 4.5. **Hạn chế phải đọc: bảo đảm này không hứa không va chạm**

Nó hứa robot **luôn còn dừng được trước thứ nó nhìn thấy**. Nó không hứa
episode kết thúc không chạm — và trong cảnh đo này nó không thể: xe đẩy
lao xuống làn rồi đâm vào một robot **đang đứng yên**. Chỉ tránh đường
mới cứu được, và với `weight_clearance = 0` không gì bảo robot tránh.

Nên **mọi hàng từ 0.15 m/s trở lên vẫn `collision`** sau khi khai biên.
Thứ đổi là tốc độ lúc bị chạm rơi từ 0.35–0.64 m/s xuống **0**.
Đọc `collision_count` và kỳ vọng nó về 0 là đang đọc một tuyên bố khác
với tuyên bố đã đo. Ghi vào `KNOWN_LIMITATIONS.md` L9.

### 4.6. Một dư lượng — **đã rút lại phần lớn sau phản biện**

Bản trước của mục này nói robot dừng muộn (21/54 mm, rồi 5.8/5.0 mm/s),
và quy cho việc biên tính phí `v_candidate·T` trong khi "robot chạy bước
đó ở `v_current`". **Cả hai đều sai, và cái sau sai về engine.**

`kinematics.step` giải vận tốc mới **trước** — kẹp theo giới hạn, rồi
kẹp theo một bước gia tốc — rồi mới tích phân **toàn bộ `dt`** bằng vận
tốc đó. Kiểm trên trace: quãng đi giữa hai mẫu bằng đúng
`after.speed × dt` tới float cuối, mọi bước. Nên khi lệnh nằm trong tầm
một bước gia tốc — cửa sổ động luôn bảo đảm, vì nó chỉ lấy mẫu trong
`±a·T` — số hạng phản ứng **tính đúng bằng** quãng thật sự đi.

Phần thật sự còn dư, nhỏ và đã đo: khi `stopping_limit` tụt dưới sàn
ramp, lệnh phát ra thấp hơn thứ engine với tới được trong một bước, nên
bước đó robot đi nhanh hơn mức đã tính phí — tối đa **0.0248 m/s**, tức
99% của một bước giảm tốc, không bao giờ quá. Nó **không** gây dừng
muộn: tốc độ lúc chạm bằng 0 ở mọi tốc độ.

Cái còn lại là **hạn chế độ trung thực của `kinematics.py`**, không phải
lỗi của P1: engine giữ bậc không nên đi ít hơn robot giảm tốc liên tục
`½·a·dt²` mỗi bước, ≈ 20 mm qua một lần phanh đầy, tức **lạc quan** về
quãng phanh. Áp cho **mọi** phép đo của nền tảng. L8 đã viết lại theo
đúng nghĩa đó.

### 4.7. Phép đo va chạm: hai lỗi đọc chồng nhau, cả hai đều làm test xanh

1. **Lấy mẫu ở biên bước.** Đọc tốc độ ở mẫu đầu tiên có `gap ≤ 0`. Mẫu
   đó ở **cuối** bước, va chạm xảy ra **bên trong** bước. Cho ra "dừng
   sạch ở mọi tốc độ" — mạnh hơn sự thật.
2. **Nội suy vận tốc qua bước.** Bản sửa thứ nhất tính
   `before.v + s·(after.v − before.v)`, ra 5.8/5.0 mm/s. Sai, vì engine
   **không** đổi vận tốc tuyến tính trong bước. Vận tốc đúng tại mọi
   thời điểm bên trong bước là **`after.speed`**, và ở bước chứa tiếp
   xúc nó bằng **0**.

Phép đo đúng có **hai** phần: *thời điểm* là nghiệm đầu tiên trong
`[0,1]` của `|d₀ + s·Δ|² = R²`; *vận tốc* là `after.speed`, hằng số.

Cả hai lỗi đều **không đỏ** — chúng chỉ đổi con số trong report. Đó là
lý do có thêm `TestTheStepModelIsZeroOrderHold`, ghim mô hình bước bằng
cách đối chiếu quãng đi trên trace, **không** đối chiếu với docstring:
docstring là thứ ai đó *định* làm, mà lỗi đọc ở đây cũng là thứ ai đó
định.

## 5. Validator: một con số khai mà không ai kiểm thì không phải bảo đảm

Cả bốn luật chuyển động có cận trên **đóng dạng**, nên phép kiểm là
**toàn phần** — không có nhánh "không chứng minh được":

| motion | cận trên |
|---|---|
| `waypoint` | `speed` |
| `random_walk` | `speed` |
| `sudden_stop` | `speed` |
| `periodic` | `π · \|end − start\| / period` |

Chỉ `periodic` không hiển nhiên: quỹ đạo là `0.5·(1 − cos(2πt/T + φ))`
dọc dây cung, đạo hàm cực đại `π/T` lần độ dài dây cung, **tại điểm
giữa** — cũng đúng chỗ một vật cản cắt ngang dễ nằm trước mặt robot
nhất.

Từ chối **lúc nạp deployment** bằng `model_validator(mode="after")` trên
`EnvironmentSpec`, nên nó bắt ở mọi đường vào (API, YAML, form) chứ
không chỉ ở một endpoint. Thông điệp viết cho **người đang chọn**: nêu
tên vật cản, tốc độ thật của nó, và con số nhỏ nhất chạy được.

Luật chuyển động **tương lai** không chứng minh được cận trên chạm
`NotImplementedError` tường minh — deployment mất tuyên bố an toàn chứ
không lặng lẽ nhận một biên rộng rãi.

---

## 6. UI

Form deployment có control mới, và nó **không** dùng `noiseField`. Công
tắc nhiễu ghi `0` cho "tắt"; ở đây `0` là một **tuyên bố** — *"không gì
ở đây chuyển động"* — mà loader từ chối ngay khi có traffic. "Tắt" bắt
buộc phải là `null`. Hai nghĩa khác nhau không được dùng chung một giá
trị.

Ghi chú dưới control đổi theo trạng thái: bật thì giải thích biên đo
được cái gì; tắt thì nói thẳng *"chưa khai, không phải bằng 0 —
deployment này không mang bảo đảm phanh trước vật cản động"*.

---

## 7. Test

| file | nội dung |
|---|---|
| `tests/test_admissible_stopping.py` | **64 test.** Mang **cả hai** lần đọc: P0 (không khai) và P1 (có khai). Cộng: biên `u = 0` bằng đúng biên cũ; `None` cho quỹ đạo **giống hệt từng float** với `0.0`; robot phanh sớm hơn **đúng 0.75 s và 1.574 m**, khẳng định trên **cả hai** mốc quy chiếu để một off-by-a-step không đọc thành chênh lệch thật; trọng số ship cũng được biên; dung sai một bước giảm tốc **có dùng tới và không bao giờ vượt**; và một lớp mới ghim mô hình bước bậc-không của engine |
| `tests/test_task_profile.py` | **+14 test.** Một ca *từ chối* và một ca *chấp nhận* cho **mỗi** luật trong bốn luật; biên **đúng bằng** tốc độ traffic phải được nhận; `None` không kiểm gì; `0.0` bị từ chối cạnh traffic **và** được nhận khi không có traffic; số âm bị từ chối; và một test đối chiếu tập luật chuyển động đã phủ với `Motion` |
| `tests/test_decision_card.py` | **+4 test.** Xoá từng trường trong `{sensor_noise, replanning, v_obstacle_max, constraints}` khỏi payload thì schema **phải** từ chối |

**`TestTheStepModelIsZeroOrderHold` — lớp quan trọng nhất thêm ở vòng
này.** Nó ghim rằng quãng đi giữa hai mẫu bằng `after.speed × dt` và
**không** bằng `before.speed × dt` ở mọi bước đang phanh, cộng một test
riêng cho bước robot về 0: bước đó robot đi **đúng 0 mm**, toàn bộ thay
đổi khoảng hở là do xe đẩy. Đối chiếu với **trace**, không với docstring.

Bốn nhận thức sai đã mắc và sửa trong pha này, ghi ra vì cả bốn đều là
loại lỗi **không đỏ**:

1. **Đo P1 bằng "số bước kẹp về 0"** như plan viết. Không về 0 được:
   `moving_required_gap` với `v = 0` vẫn đòi `u·T`, nên robot **đã dừng**
   bị xe đẩy lao vào vẫn bị đếm là kẹp. Bất biến đúng là *tốc độ ≤ thứ
   khe hở cho phép*.
2. **Đọc tốc độ ở mẫu cuối bước.** Cho ra "dừng sạch" — mạnh hơn sự thật,
   và test **xanh**.
3. **Nội suy tốc độ qua bước.** Cho ra 5.8/5.0 mm/s — yếu hơn sự thật, và
   sai về engine. Test cũng **xanh**.
4. **Quy dư lượng cho công thức phản ứng.** Sai chủ thể: engine áp vận
   tốc mới cho cả bước, nên số hạng đó tính đúng. Thứ còn lại là độ trung
   thực của tích phân, thuộc `kinematics.py`.

Hai lần liên tiếp một phép đo sai mà bộ test vẫn xanh là lý do lớp ghim
mô hình bước tồn tại.

## 8. Kiểm chứng

| Việc | Kết quả |
|---|---|
| `tests/test_admissible_stopping.py` | **64 passed** |
| `tests/test_task_profile.py` | **67 passed** (14 mới) |
| `tests/test_hard_feasible_set.py` (phase 1b) | 25 passed |
| `tests/test_dwa.py` | passed |
| `tests/test_nav_stack.py` · `test_decision_card.py` · `test_replanning.py` · `test_recovery.py` · `test_dynamic_obstacles.py` · `test_form_covers_the_contract.py` | 149 passed, 1 skipped |
| `tests/test_contract_version.py` | 4 passed (sau khi thêm dòng 6.9.0 và cập nhật ví dụ JSON) |
| `tests/test_decision_card.py` | **46 passed** (4 mới) |
| `tests/api` + `test_candidate` / `test_fairness` / `test_episode_context` / `test_measure` (lát cắt lớn, 14m37s) | **877 passed, 1 skipped** |
| Web suite (`vitest run`) | **670 passed**, 32 file |
| `tsc --noEmit` | sạch |
| `ruff check .` | sạch |
| Full backend suite | **chưa chạy — chờ lệnh** |

---

## 9. Còn lại

Theo đồ thị phụ thuộc của plan (mục 11.0), cổng quyết định 1 đã qua và
P1 đã xong ⇒ tiếp theo là **P2 — tách lõi dùng chung** (`dwa_core.py`),
pha *không đổi hành vi*, và plan bắt nó **đứng riêng một commit** kèm
**golden trajectory test**.

Bốn việc treo lại, không thuộc P1:

- **L8 — độ trung thực của `kinematics.py`.** Tích phân bậc không làm
  simulator **lạc quan** về quãng phanh ≈ 20 mm mỗi lần phanh đầy. Áp cho
  **mọi** phép đo của nền tảng, không riêng P1. Sửa là đổi tích phân của
  simulator ⇒ đổi mọi số đã lưu ⇒ phải cân nhắc như một thay đổi độ trung
  thực (giống lần bật `sensor_noise`), không phải một bản vá. **Quyết
  định của An.**
- **Phạm vi hiệu lực (L11).** `v_obstacle_max` chỉ đi qua **luồng
  deployment** (`run_contract_episode`). Luồng benchmark cũ
  (`run_benchmark`/`run_single`), `/simulate`, `tuning.py` và
  `calibrate_difficulty.py` nhận `Scenario` chứ không nhận `TaskProfile`,
  nên **không có gì để truyền** — chúng chạy hành vi cũ. Cùng tình trạng
  với `recovery`. Nếu luồng benchmark cũ còn hiện trên UI, số nó sinh ra
  không mang bảo đảm này.
- **Không profile nào đang khai `v_obstacle_max`.** Mặc định `None` nên
  hôm nay chưa deployment nào mang bảo đảm. Khai nó là tạo
  `task_profile_id` mới — P7 sẽ cần một profile như thế.
- **Artifact cũ không hợp lệ với manifest schema.** Đã đúng như vậy từ
  trước bản này (thiếu `constraints`/`sensor_noise` từ 6.4.0); không code
  nào kiểm lại chúng.

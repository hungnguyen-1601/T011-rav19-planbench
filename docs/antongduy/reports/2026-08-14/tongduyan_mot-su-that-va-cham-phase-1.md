# Phase 1 — một sự thật va chạm cho mọi tầng

**Ngày:** 2026-08-14
**Plan:** `docs/antongduy/plans/2026-08-14/mot-su-that-va-cham-va-recovery.md`, phase 1
**Trạng thái:** xong

> **Đã bị phase 2 sửa một phần — đọc kèm.** Ba con số về *inflation* ở
> mục 3.5 và mục 4 (0.614 m / 1.005 m) là của mô hình nhị phân, và phase
> 2 đã tách lệnh cấm khỏi phần tính tiền, nên chúng không còn là vành
> planner đang dùng. Phần L1–L4, safety envelope, `safety_margin` xuống
> làm cost và admissible stopping thì **không đổi**. Xem
> `tongduyan_inflation-theo-bac-phase-2.md`.

---

## 1. Việc cần làm là gì

Trước phase này, hai tầng của cùng một stack trả lời khác nhau cho câu
hỏi *"robot có được đứng ở đây không"*:

| Tầng | Ngưỡng cứng | Công thức |
|---|---|---|
| DWA (local) | **0.31 m** | `robot.radius + safety_margin` |
| A* (global) | **0.61 m** | `robot.radius + √2 × resolution` |

Cả 0.30 m chênh lệch là **số hạng lượng tử hoá lưới** — một thuộc tính
của độ phân giải bản đồ, không phải của thế giới. Robot đỗ ở chỗ hợp lệ
theo chính test của nó, và nằm sâu 0.30 m trong vành cấm của planner:
55 lần replan trong 120 s đều trả về "no path exists".

Phase 1 làm ba việc: dựng **một** định nghĩa miền khả thi cứng, dời
`safety_margin` từ "từ chối" sang "chi phí", và bịt lỗ hổng phanh gấp.

---

## 2. Ba lớp ranh giới, hai trục khác nhau

Điểm mấu chốt (An chốt trong phiên trước): **"ai sở hữu" và "cứng hay
mềm" là hai trục độc lập.**

| Lớp | Ý nghĩa | Cứng/mềm | Nguồn |
|---|---|---|---|
| Collision footprint | tiếp xúc hình học chắc chắn | cứng | robot |
| **Safety envelope** | pose ước lượng có thể sai bao nhiêu | **cứng** | **deployment** |
| Comfort margin | muốn rộng hơn mức cần | mềm | candidate |

Từ đó ra hợp đồng L1–L4:

- **L1** — global chỉ được trả đường nằm trong miền khả thi cứng mà local
  thi hành được.
- **L2** — local được thận trọng hơn bằng **cost**, không được âm thầm
  thu hẹp miền cứng bằng tham số candidate mà global không thấy.
- **L3** — mọi tầng dùng chung footprint và safety envelope.
- **L4** — test tích hợp chạy **cả** `astar+dwa` **và** `rrtstar+dwa`,
  mọi đường global phải qua validator khả thi của local.

---

## 3. Đã thay đổi gì

### 3.1 `packages/schemas/planbench_schemas/feasibility.py` (mới)

Một chỗ duy nhất định nghĩa miền cứng.

```python
SafetyEnvelope.for_noise(noise)   # suy ra, không ai chọn
hard_clearance(robot, envelope)   # = radius + position_uncertainty
stopping_distance(speed, robot)   # v² / (2a)
reaction_distance(speed, period, latency_steps)
```

**Envelope là suy ra, không phải một nút bấm mới.** Mọi đầu vào đều là
thứ deployment đã khai. Lấy **worst case** chứ không phải percentile:
percentile cần ai đó chọn con số, và một ràng buộc cứng bị vượt 5% thời
gian thì không còn là cứng.

Hai nguồn, và chỉ hai:

- **Drift** — tổng có trọng số các sin, trọng số cộng lại bằng 1 mỗi
  trục, nên cả hai trục bị chặn bởi `biên độ × √2`.
- **Jump** — cộng `max(drift, 0.25)` bất cứ khi nào xác suất khác 0.
  Qua một episode có nhiều cửa sổ tái định vị, "hiếm mỗi cửa sổ" là "nó
  xảy ra".

**Không có trong envelope:**

- *Wheel slip* — trượt làm robot dịch **thật**, nên đã nằm trong pose
  thật mà test va chạm đọc. Nó không mở khe hở nào giữa sự thật và niềm
  tin, mà khe hở đó mới là thứ envelope che.
- *Quãng phanh* — tỉ lệ với **bình phương** tốc độ. Nhét vào một envelope
  tĩnh sẽ cấm robot bò 0.1 m/s y hệt robot lao 0.8 m/s: 0.64 m biên an
  toàn cho một nhu cầu thật 0.01 m.

**L2 được bảo đảm bằng chữ ký hàm, không bằng kỷ luật.** Mọi hàm ở đây
nhận `(RobotConfig, SafetyEnvelope)` và không hàm nào nhận config của
candidate. Controller muốn thu hẹp miền cứng cũng **không có tham số nào
để làm việc đó**.

### 3.2 DWA — `safety_margin` xuống làm chi phí

```python
# trước
keep_out = robot.radius + config.safety_margin      # candidate từ chối
# sau
keep_out = hard_clearance(robot, self._envelope)    # deployment từ chối
```

Nguyện vọng không bị xoá, chỉ đổi chỗ — thêm số hạng mềm `comfort` trong
`_score`: đi gần hơn `hard + safety_margin` thì đắt dần theo bình
phương. Muốn rộng hơn mức an toàn đòi hỏi vẫn là nguyện vọng chính đáng
và vẫn phân biệt được hai candidate.

`reset()` nhận thêm `envelope`; `nav_stack._reset_local` truyền envelope
của deployment vào controller nào có nhận (dò bằng `inspect.signature`,
nên controller cũ không gãy).

### 3.3 Admissible stopping — lỗ hổng có va chạm thật

Đây là phần An bổ sung vào plan, và nó đúng: **dynamic window không tự
động bảo đảm quãng phanh.** Window chặn cái *cơ cấu chấp hành* với tới
được trong một chu kỳ; điều kiện khả nhận (Fox–Burgard–Thrun 1997) là
thứ khác và đọc khoảng cách tới **vật cản gần nhất**.

Code cũ đọc khoảng cách tới **goal** — một cơ chế hãm khi sắp tới đích,
đội tên an toàn.

```python
# sau
to_goal     = khoảng cách tới cuối đường
to_obstacle = self._nearest_obstacle_distance(obstacles, state)
headroom    = max(0.0, min(to_goal, to_obstacle))
stopping_limit = self._speed_that_stops_within(headroom, robot)
```

`_speed_that_stops_within` **giải** `v·t + v²/(2a) = headroom` chứ không
thử từng ứng viên: `v = a·(√(t² + 2·headroom/a) − t)`.

Đo lại chính ca đã tái hiện được:

| Cấu hình | Trước | Sau |
|---|---|---|
| mặc định | stuck, min_gap 0.701 | stuck, min_gap 0.701, 0 bước không phanh kịp |
| `weight_clearance=0` | stuck, min_gap 0.102 | stuck, min_gap 0.102, 0 bước |
| `weight_clearance=0`, `horizon=0.5` | **collision, min_gap −0.002 m, 23 bước không phanh kịp** | stuck, min_gap 0.100, **0 bước** |

Cả hai đều là nút chỉnh candidate hợp lệ. Trước phase này, an toàn dựa
vào `weight_clearance` — một trọng số **mềm** do candidate sở hữu.

### 3.4 `services/simulator/planbench_simulator/drivable.py` (mới) — hàng rào L4

`path_is_drivable(path, robot, envelope, obstacles, grid)` trả
`DrivabilityReport(drivable, required_clearance, worst_clearance,
worst_point)`.

- **Đo trên miền liên tục, không trên lưới.** Hỏi lưới sẽ lẫn "không khả
  thi" với "rasterise thô" — đúng cái nhầm đã làm robot kẹt 55 lần.
- **Lấy mẫu bước 1/5 hard clearance, và luôn lấy mọi waypoint.** Waypoint
  là chỗ đường dễ cắt góc nhất.
- Chữ ký cũng chính là hợp đồng: robot + envelope của **deployment**,
  không có config candidate nào chạm tới được.

`StackRun` có thêm `plans: tuple[PlanResult, ...]` — **mọi** đường global
trả về, không chỉ đường đầu. Không có nó thì L1 không kiểm được: replan
mới là chỗ một đường ngoài miền cứng có thể sinh ra, vì nó lập từ pose
**tin là** trên lưới đã được nới quanh robot. Trường này được ghi vào
artifact và DB; hàng cũ đọc lên là rỗng, và **rỗng nghĩa là "không được
ghi lại", không phải "không có plan nào"** — dựng lại `(plan,)` sẽ là
khai rằng episode đó chưa từng replan.

### 3.5 UI — vành cấm đang vẽ sai

Test web bắt được: `keepOutRadius` vẫn vẽ `radius + √2×resolution`, bỏ
mất safety envelope. Với noise mà form khai mặc định, vành thật là
**1.005 m** chứ không phải 0.614 m — sai gần 40%.

Đã port `safetyEnvelope(noise)` sang `lib/keepOut.ts` và luồn
`positionUncertainty` qua `MapCanvas`, `scene25d`, `Scene25D`,
`MapView`, `MissionPlacer`, tới `simulate/page.tsx` và
`DeploymentForm.tsx`. Trang chỉ có scenario (library, scenario editor)
nhận 0 — đó là **sự thật**, không phải giá trị đoán: một scenario đứng
một mình không khai sai số định vị nào.

Bản sao TS được ghim bằng test đọc thẳng `feasibility.py`,
`sensor.py` và `nav_stack.py`.

---

## 4. Con số đo được

```
             envelope   hard_clearance   inflation (res 0.25)
form 7 luồng   0.391 m      0.651 m           1.005 m
profile ship   0.000 m      0.260 m           0.614 m
DWA cũ            —         0.310 m              —
```

Đọc bảng này: deployment nào khai `localization_jump_probability` sẽ
**mất thêm 0.25 m** clearance cứng. Đây là **siết chặt có chủ ý** —
simulator trước đây lạc quan hơn thực tế, và envelope chỉ nói ra điều
robot đã phải chịu.

Với profile đang ship (chỉ 2 luồng nhiễu), `hard_clearance` là 0.260 m,
**thấp hơn** ngưỡng cũ 0.310 m. Nghĩa là: chỗ nào không khai sai số định
vị thì `safety_margin` từng đang giả làm an toàn, còn giờ nó nói thật —
là sở thích.

---

## 5. Test

`tests/test_hard_feasible_set.py` — 25 test, chia bốn nhóm:

1. **Envelope là suy ra** — không nhiễu thì không envelope; drift chặn cả
   hai trục; jump tính như chắc chắn; slip **không** làm rộng; phanh
   **không** nằm trong.
2. **L2 ghim bằng chữ ký** — `hard_clearance` chỉ có `{robot, envelope}`;
   DWA không còn từ chối theo `safety_margin`; nguyện vọng vẫn sống (chạy
   hai episode `safety_margin` 0.45 và 0.01, đòi cái nhát đi xa hơn).
3. **L4** — mọi plan đầu và **mọi replan** của **cả hai** stack; validator
   từ chối đường xuyên tường và đường mà hai đầu sạch còn giữa thì không;
   và ngưỡng không mang số hạng nào tỉ lệ với kích thước ô.
4. **Admissible stopping** — test **tính chất** trên toàn quỹ đạo, không
   phải test tình huống, chạy với **trọng số đối kháng** và đo trên
   **pose thật**.

Ba điểm về cách viết test, vì cả ba đều là bẫy đã sập trước đây:

- **Test quét source giờ đọc token, không đọc text.** Hai lần trong repo
  này, một test đã khớp phải chính đoạn văn giải thích nằm ngay cạnh nó
  và báo ngược sự thật. `_executable_source()` bóc comment và docstring
  trước khi quét.
- **Đo trên pose thật.** Có drift thì robot phanh theo chỗ nó *tưởng*
  đang đứng; đo trên pose tin là sẽ là tự chấm bài mình.
- **Ca `weight_clearance=0, horizon=0.5` giữ làm test hồi quy**, kèm số
  đo cũ ghi thẳng trong docstring.

---

## 6. Phạm vi test L4 — nói rõ chỗ nó không phủ

Hàng rào L4 kiểm đường global với **bản đồ + static obstacle**, tức phần
hình học mà global planner chịu trách nhiệm. **Cố ý bỏ dynamic
obstacle**: ở t=0 planner không nhìn thấy xe đẩy, nên một đường đầu đi
thẳng qua chỗ xe đẩy sẽ tới là **hành vi đúng** và là việc của
controller, không phải vi phạm hợp đồng.

Khả năng từ chối đường xuyên **hình tròn** được chứng minh bằng hình học
dựng sẵn chứ không phải từ episode thật, vì một `StackRun` đã kết thúc
không trả lời được câu "xe đẩy đứng đâu vào đúng lúc replan thứ *k*".
Muốn phủ chỗ đó phải ghi lại vị trí obstacle tại thời điểm replan —
việc của phase sau, không lặng lẽ bỏ qua.

---

## 7. Một phát hiện chưa sửa

DWA rollout từ `engine.get_state()` (**pose thật**) nhưng đặt điểm vật
cản từ `observation.pose` (**pose tin là**). Hai cái lệch nhau đúng bằng
toàn bộ sai số định vị.

Không sửa trong phase này — nó không phải lỗi của phase 1 và sửa nó là
thay đổi ngữ nghĩa của cả mô phỏng. Nhưng nó **chính là lý do envelope
cần thiết chứ không thừa**: nếu controller đã lái hoàn toàn trên pose tin
là, sai số đó vẫn không biến mất, chỉ chuyển chỗ.

---

## 8. Kiểm chứng

| Việc | Kết quả |
|---|---|
| `tests/test_hard_feasible_set.py` | 25 passed |
| Web suite (`vitest run`) | 668 passed, 32 files |
| `tsc --noEmit` | sạch |
| `ruff check .` | sạch |
| Full backend suite | **2549 passed, 7 skipped** (chạy sau phase 2) |

---

## 9. Còn lại trong plan

- **Phase 2** — inflation theo bậc (cost, không phải cấm), rồi xoá B1
  (`_with_room_to_leave`) vì nó là miếng vá cho đúng vấn đề phase 2 giải.
- **Phase 3** — recovery R1–R4.

Chưa commit. Chờ lệnh.

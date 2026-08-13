# Nợ kỹ thuật còn tồn đọng — kiểm kê 2026-08-13

**Nguồn:** `docs/KNOWN_LIMITATIONS.md` (L1–L6) · plan 12-08 mục C và E · report 12-08 mục 5 ·
report 13-08 mục 8 · quét mã và artifact ngày 13-08.

**Cách đọc:** xếp theo **cái gì hỏng nếu không trả**, không theo thứ tự thời gian. Cột "ai gây"
phân biệt nợ có từ trước với nợ tôi vừa tạo ra — để không ai phải đoán.

Quét mã: **không có `TODO`/`FIXME`/`XXX`/`HACK` nào** trong `packages/`, `apps/`, `services/`,
`scripts/`. Bốn `pytest.skip` đều có điều kiện môi trường, không phải test rỗng. Nợ dưới đây là
nợ **thiết kế và đo lường**, không phải mã bỏ dở.

---

## A. Nợ làm yếu tuyên bố khoa học *(nặng nhất)*

### A1. Chưa có adapter `MonolithicPolicy` — và bất cân xứng lưới replan đi kèm

`build_planners` từ chối candidate `monolithic`; chỉ `modular` chạy được. Hệ quả: tuyên bố
*"nền tảng công bằng cho mọi thuật toán"* mới được chứng minh trên **hai global planner cùng
kiểu tìm đường trên lưới với một local controller**. Phép thử thật của tuyên bố đó chưa chạy.

Đi kèm và **phải làm cùng lượt**: `nav_stack._replan` dựng lưới quy hoạch tạm với **vị trí thật**
của vật cản động. Hôm nay công bằng vì mọi candidate đều `modular`. Ngày adapter chạy được, một
policy end-to-end chỉ thấy `Observation` còn stack modular thấy vật cản **thật sự ở đâu** — đúng
đặc quyền G6 sinh ra để định giá, và nó ưu ái stack modular vì lý do không liên quan tới chất
lượng điều hướng. HĐ-4.1 đã ghi luật: gỡ đặc quyền **trước** khi chấm candidate `monolithic`.

`test_only_modular_stacks_can_run_today` sẽ đỏ đúng ngày adapter được thêm — hàng rào đã đặt sẵn.

| | |
|---|---|
| Nguồn | L2 · plan 12-08 mục C1 |
| Ai gây | có từ trước |
| Ước lượng | 1–2 ngày |

### A2. `robustness_margin` null trên **mọi** Decision Card

Kiểm tám card trong `artifacts/runs/`: `robustness_margin: None` ở tất cả. Theo HĐ-12 null nghĩa
là *"chưa đo"*, nên các card **trung thực nhưng thiếu**.

Cần **Task Neighborhood** (N5): sinh K biến thể quanh profile gốc (đề xuất K = 20), đo
`R = (số biến thể khuyến nghị không đổi) / K`. Dưới 60% ⇒ card đổi nhãn thành
`NEAR-EQUIVALENT`. Tài liệu đề tài gọi đây là **điểm khác biệt học thuật mạnh nhất của dự án** —
không nền tảng nào khác đo độ bền của *kết luận* trước nhiễu đầu vào.

Bốn trục nhiễu còn thiếu của bảng N5: dịch start/goal ±1 m ±15° · dịch vật cản tĩnh ±0,3 m xoay
±10° · mật độ vật cản động ±20% tốc độ 0,8–1,4 m/s · `v_max` ±10%.

| | |
|---|---|
| Nguồn | N5 · plan 12-08 mục E |
| Ai gây | có từ trước |

### A3. Robot đang định vị **hoàn hảo** *(phát hiện 13-08)*

`engine.py:262-268` — `Observation(pose=self._robot.pose)`. Stack nhận **pose thật**. LiDAR đọc
sai, bánh trượt thật, nhưng robot **luôn biết chính xác mình ở đâu**.

Cả một họ thất bại có thật không tồn tại trong mô phỏng: localisation nhảy, drift tích luỹ,
robot tự tin lái vào tường. Đây là **lỗ hổng của mô hình**, không phải tính năng còn thiếu — nó
làm simulator lạc quan hơn thực tế theo đúng cách `noise.py` được viết ra để sửa.

Kèm theo, cùng họ: **LiDAR chưa có mất tia**. Kính, bề mặt tối, gương trả về **không gì cả**;
costmap đọc "trống" và lái thẳng vào. Đây là cách robot thật đâm cửa kính.

Và: trượt bánh hiện **zero-mean mỗi bước** nên sai số **triệt tiêu**. Bánh mòn không đều là lệch
**một chiều**, nó **tích luỹ** — hai kiểu hỏng khác nhau hoàn toàn, mới mô phỏng một.

| | |
|---|---|
| Nguồn | quét mã 13-08 |
| Ai gây | có từ trước, chưa ai ghi ra |
| Ghi chú | dev chốt 13-08: đưa vào plan dài hạn, làm sau nợ kỹ thuật |

### A4. Chưa có map **vừa khó vừa đối xứng** — và map đối xứng hiện có **không nằm trong repo**

`open_hall` đối xứng nhưng dễ; kho khó nhưng **chưa có kiểm đối xứng nào**. Một map vừa khó vừa
đối xứng là phép kiểm mạnh hơn cả hai.

Nặng hơn thế, và chưa ai ghi ra: `tests/test_fairness.py:310` **skip** với thông điệp
*"run scripts/make_fairness_map.py to generate the fairness map"*, và `maps/` không có file đó.
Nghĩa là **bộ test công bằng đang không chạy** ở checkout sạch — nó xanh vì bị bỏ qua, không vì
đã kiểm.

| | |
|---|---|
| Nguồn | plan 12-08 mục C2 · quét test 13-08 |
| Ai gây | có từ trước |
| Ước lượng | nửa ngày cho map; sinh lại map công bằng thì vài phút |

---

## B. Nợ về con số và ngưỡng

### B1. `success_rate_min` của sảnh = 0.95, **và con số đó được biết là sai** (L6)

Giá trị đúng theo lập luận là **1.00** — sảnh là deployment nghiệm thu, một failure là tín hiệu
chẩn đoán chứ không phải thống kê. Ngày 11-08 đã đổi sang 1.00, ngày 12-08 **lùi lại**: luật 2
của HĐ-8.3 buộc `bad` của anchor trỏ vào chính ngưỡng ấy, nên 1.00 làm `good == bad`, thang sập,
deployment mất khả năng xếp hạng (HĐ-8.4), và tấm Decision Card duy nhất không tái lập được.

**Cơ chế đã có** (HĐ-8.4 xử lý 1.00 tử tế, có test). **Việc còn lại là quyết định**, không phải
hiện thực. Ba hướng chưa xét kỹ: tách ngưỡng cổng khỏi neo `bad`; cho anchor khai `bad` dự
phòng khi ngưỡng chạm trần; hoặc chấp nhận sảnh chỉ gác cổng và chuyển xếp hạng sang A4.

**Không được đọc 0.95 như một câu trả lời.**

### B2. Kho chưa khai `sensor_noise` — σ = 0

Kiểm `warehouse_a_v2.yaml`: khối `sensor_noise` **không tồn tại**. Với planner tất định, khai
vào là phải sinh `warehouse_a_v3` (HĐ-13: đổi nhiễu là đổi thế giới, đổi id).

Đáng lo hơn con số: kho **có** vật cản động nên episode vẫn phân biệt được — nhưng đó là may,
không phải thiết kế. Sảnh không có traffic và sống nhờ nhiễu; kho có traffic và sống nhờ nó. Hai
deployment đang dựa vào hai cơ chế khác nhau mà không ai khai điều đó ra.

---

## C. Nợ đo lường — phép đo chưa chạy

| nợ | trạng thái | chặn cái gì |
|---|---|---|
| **Kho ở mức 1%** | dừng ở **245/300**, dev chủ động dừng; cả hai candidate trượt G2+G3 | Chưa có kết luận nào trên deployment **thật** duy nhất. Mọi kết luận hiện có đều trên sảnh, mà sảnh là **dụng cụ đo** chứ không phải khách hàng |
| **`astar+ppo`** | trong registry, `benchmarkable=True`, **chưa từng vào phép so nào** | Candidate đầu tiên có **lớp quan sát khác** hai stack cổ điển ⇒ phép thử thật đầu tiên của G6 và P02. Cần `torch` + checkpoint |
| **G4/G5 trên bo mạch đích** | chỉ xác nhận trên máy benchmark | Dự án **không có** Jetson Orin Nano hay board ARM nào. Bảo lưu HĐ-7.2/7.3 |
| **Decision Card trên nền đã kiểm** | bốn candidate, **một** qua cổng | L3 |

---

## D. Nợ trong mã và giao diện

### ~~D1. Test chống trôi lược đồ~~ — **đã trả 2026-08-13**

`tests/test_form_covers_the_contract.py`, 10 test. Chi tiết ở report 13-08 mục 9. Đã chứng minh
nó đỏ khi phải đỏ bằng cách thêm tạm một trường vào `TaskProfile`, không chỉ tin là nó sẽ đỏ.

Năm trường được miễn trừ, mỗi trường kèm lý do trong `NOT_IN_THE_FORM`, và ba test phụ giữ cho
chính danh sách đó không mục.

<details><summary>Nguyên văn mục nợ ban đầu</summary>

Plan 13-08 mục 4 gọi đây là **test đáng giá nhất của cả đợt**, và tôi không làm.

Thêm một trường vào `TaskProfile` mà form lặng lẽ bỏ sót là kiểu hỏng **không gì bắt được**:
suite vẫn xanh, form vẫn khai được, và deployment sinh ra thiếu đúng trường mới. Cần một test
duyệt `TaskProfile.model_fields` (kể cả model lồng) và bắt mọi trường **hoặc** có trong form
**hoặc** nằm trong danh sách hoãn kèm lý do.

**Ước lượng:** 1–1,5 giờ. Nên trả trước tiên trong nhóm D.

</details>

### D2. Hai test web đỏ, tôi đã gọi là "có sẵn từ trước" ba lần liên tiếp

- `dashboard-page.test.tsx` — so `'\system\page.tsx'` với `'/system/page.tsx'`. Lỗi **dấu phân
  cách Windows**, test viết giả định POSIX.
- `assistant-page.test.tsx` — không collect được.

Không phải nợ của loạt việc này, nhưng **báo cáo mãi mà không sửa thì thành nợ**: một suite có
hai vệt đỏ thường trực là suite người ta thôi đọc. Cái thứ nhất sửa trong mười phút.

### D3. Không có gì **chặn** hai run đánh giá chạy song song

Ghim nhân đã cưỡng chế trong mã, nhưng ràng buộc HĐ-7.4 chỉ tồn tại như một **điều khoản**.
Hàng đợi API giữ đúng một job, nhưng CLI thì không biết gì về hàng đợi đó. Hai tiến trình cùng
ghim sẽ giành đúng hai nhân đầu và G4 đo một cái máy không tồn tại. Một cờ file khoá là rẻ.

### D4. Nợ nhỏ hơn, ghi để không rơi

| | |
|---|---|
| `instance_difficulty` | chưa nối vào tầng quyết định (cache P03 khoá theo `scenario_name` cũ) |
| `business_adjusted` | có anchor tiền nhưng **chưa demo được** hai chân trời lật khuyến nghị (N3) |
| `dynamic_obstacles` trong form | hoãn theo chốt của dev; lối thoát là tab YAML |
| `available_observations` | mọi profile khai `[lidar_2d]`, form chưa có ô |
| Luồng cũ | 80 endpoint vẫn sống song song. Lý do kỹ thuật cản việc thay thế **đã hết**; còn lại là việc phải làm, và ba câu hỏi chưa trả lời: dữ liệu benchmark cũ migrate hay đóng băng · `leaderboard` dựng trên Decision Card thì nghĩa là gì (xếp hạng xuyên deployment mâu thuẫn HĐ-1.4) · `robot-profiles` trùng khối `robot` trong task profile, một trong hai phải thành nguồn sự thật |

---

## Thứ tự đề xuất

Xếp theo **rẻ × chặn nhiều**, không theo mức độ hấp dẫn:

```
D1 test chống trôi lược đồ   ✅ TRẢ 13-08
D2 sửa test đường dẫn Windows (~10 phút) ← xoá vệt đỏ thường trực
A4 sinh lại map công bằng    (~vài phút) ← test công bằng đang bị SKIP, không phải xanh
        │
B1 quyết định ngưỡng sảnh    (quyết định, không phải code)
B2 warehouse_a_v3 khai nhiễu (~1 h + giờ máy)
        │
C  chạy cho đủ: kho 300 episode, astar+ppo
        │
A1 adapter monolithic + lưới replan   (1–2 ngày)
A2 Task Neighborhood ⇒ robustness_margin
A3 định vị + mất tia + lệch odometry  ← dev chốt: plan dài hạn
```

Ba dòng đầu cộng lại **dưới hai giờ** và mỗi dòng đóng một lỗ hổng mà suite hiện không nhìn
thấy. A4 đặc biệt đáng làm sớm: một bộ test công bằng đang **skip** thì nó không bảo vệ gì cả,
mà cả dự án dựa trên tuyên bố công bằng.

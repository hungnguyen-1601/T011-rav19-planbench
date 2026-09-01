# Báo cáo — Phase 5.1: Lần chạy 100 episode, và một tấm card nói dối

> **Ngày:** 2026-08-11 · **Nhánh:** `plannerselector_p2`
> **Plan nguồn:** `plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **Phase 5.1**
> **Contract:** `5.0.0` → **`6.0.0`** (MAJOR)
> **Run:** 100 context × 2 candidate, xen kẽ, ghim 2 nhân, 46 phút.
> **Kết quả quan trọng nhất:** run chạy sạch, sáu tiêu chí HĐ-15.1 xanh — và tấm card nó
> sinh ra tuyên bố một điều dữ liệu không đỡ được.

---

## 1. Ba thứ sửa **trước** khi chạy, hai trong số đó là lỗi thật

| # | Vấn đề | Vì sao phải sửa trước |
|---|---|---|
| 1 | `simulate()` lặp candidate-outer, **không dùng** `iter_run_plan` | Ở quy mô này, một candidate chiếm nửa đầu đồng hồ, nửa sau candidate kia |
| 2 | `--episodes` mặc định 30, **ghi đè** số suy từ rủi ro khai báo | HĐ-7.1: số episode là *hệ quả* của `collision_probability_max`, không phải tuỳ chọn |
| 3 | Profile khai rủi ro 10% | Bộ 30 episode cũ chỉ tuyên bố được cận trên 10% |

**Về (1).** Contract HĐ-3.2 viết rõ vòng ngoài là context; `iter_run_plan` hiện thực đúng từ
Phase 1.3 và có cả một đoạn docstring giải thích tại sao; `simulate()` thì không gọi nó. Ở 30
episode/10 phút, vô hình. Ở 200 episode/46 phút thì đó đúng là cơ chế đã loại nhầm A\* ở G4
(contract 3.0.0). Sửa xong, tải máy trở thành nhiễu **chung** và triệt tiêu trong ΔU ghép cặp.

Bằng chứng nó hoạt động: một phần năm cuối của run chậm hơn hẳn (17,3 s so với 13,4 s ở đầu,
hai episode cuối 34,6 / 32,5 s) — nhưng **đập vào cả hai candidate gần như bằng nhau**
(A 17,80 s / R 16,79 s, tỷ lệ 1,06 so với 1,078 của toàn run).

**Về (3).** Đặt ở 3% ⇒ `N_min = 100`. Ghi thẳng thang bậc chi phí vào profile để lần sau khỏi
tính lại: `0,1 → 30 ep → ~17 phút` · `0,03 → 100 ep → ~57 phút` · `0,01 → 300 ep → ~2,9 giờ`.
Nâng lên 1% không cần đổi code, chỉ cần máy rảnh.

### 1.1. Ghim nhân: rẻ, và nó sửa một phát hiện cũ

Ghim mô phỏng vào 2 nhân trong 20, người dùng giữ 18 nhân còn lại. Episode còn **nhanh hơn**
(13,95 s so với 17,15 s không ghim — bớt di trú giữa các nhân). Nhưng kết quả đáng chú ý hơn:

| G4 p99 gộp | 30 ep, không ghim | 100 ep, ghim |
|---|---:|---:|
| `astar+dwa` | 13,91 ms | **10,81 ms** |
| `rrtstar+dwa` | **59,30 ms** | **16,10 ms** |

Phase 4 kết luận RRT\* sát ngân sách G4 (*"max p99 99,6 ms — dưới ngưỡng 100 ms đúng 0,4 ms"*).
Đó **là hiện vật của phép đo bị tranh chấp CPU**, không phải tính chất của candidate. Một phép
đo được cấp tài nguyên ổn định cho con số nhỏ hơn 3,7 lần.

---

## 2. Lỗi chính: cận trên va chạm 3,0% tính từ **một** mẫu

Card in ra, cho `astar+dwa`:

```
G2: 0 va chạm quan sát trong 100 lần chạy; cận trên 95%: 3,0%
```

Sáu tiêu chí HĐ-15.1 xanh. **Không có gì trên tấm card đó trông sai.**

Đo lại: cả 100 episode của A\* **giống hệt nhau tới chữ số float cuối**.

```
astar+dwa      utility per-episode:   1 giá trị khác nhau /100
rrtstar+dwa    utility per-episode: 100 giá trị khác nhau /100
```

RRT\* biến thiên vì nó là planner ngẫu nhiên. A\* tất định, và môi trường không cho nó gì để
phản ứng khác đi. Số mẫu hiệu dụng là **1**; quy tắc số 3 cho `3/1` — run không chặn được gì.

Dấu hiệu đầu tiên là `decision_utility` **giống hệt tới 16 chữ số** giữa run 30 và run 100
episode: `0.8205179005094823`. Với 70 episode mới, trung bình theo tập phải xê dịch ít nhất ở
chữ số thứ tư. Trùng khớp tuyệt đối là thứ không thể bỏ qua.

### 2.1. Truy nguyên nhân: ba giả thuyết, loại từng cái

| Giả thuyết | Kiểm | Kết quả |
|---|---|---|
| Seed không tới được vật cản | Đọc `position_at` | **Sai** — `_seed_time_shift` được áp |
| Vật cản không đổi theo seed | Tính vị trí tại t=30 s, seed 0–5 | **Sai** — y = 17,0 / 16,6 / 17,5 / 17,7 / 12,3 / 14,5 |
| Robot không đi qua đó | Đo khoảng cách tới hành lang xe nâng | **Sai** — 0,01 m, 75 bước trong vùng |

Cả ba đều đúng như thiết kế. Cái sai là **biên độ**. Đo khoảng cách thật giữa robot và xe nâng
**theo thời gian khớp**:

```
gần nhất qua 100 seed: 2,53 m       (chạm nhau ở 0,66 m)
số seed vào trong 2 m: 0/100
```

`seed_time_offset = 6 s` trên chu kỳ **24 s** chỉ quét **một phần tư** pha. Robot cắt qua lane
đó trong cửa sổ ~2 giây quanh t = 20 s. Hai điều đó cộng lại: xe nâng có thật, biến thiên có
thật, và **chưa bao giờ gặp tuyến đường này**.

### 2.2. Vì sao nó lọt tới tận đây

Phase 1.4 đã đọc `DynamicObstacle`, **dự đoán chính xác lỗi này**, viết validator, và ghi lại:

> *"cùng vấn đề số mẫu hiệu dụng tồn tại ở đó: planner tất định + không traffic ⇒ mọi seed cho
> cùng một episode. [...] ghi vào contract rằng bảng cổng (3.2) là nơi phải nói thẳng điều đó.
> **Đây là việc phải làm khi hiện thực G2, đã ghi lại để không rơi.**"*

Nó rơi. Và nó rơi theo cách tệ hơn "quên":

- Validator được viết — nhưng chỉ bắt `offset = 0`.
- **Lời khuyên của chính validator** — *"Set seed_time_offset > 0 (a few seconds)"* — là cái
  profile đã làm theo. Sáu giây. Đúng lời khuyên, sai kết quả.
- Phép kiểm ở G2 thì không bao giờ được viết.

Bài học, và tôi ghi nó vào cả contract: **một ghi chú "nhớ làm ở phase sau" không phải một biện
pháp bảo vệ. Chỉ code mới là.**

### 2.3. Ba sửa chữa, ở ba tầng, vì lỗi lọt qua cả ba

**Tầng cổng — G2 đếm episode phân biệt.** Mẫu số của cận trên là số episode **khác nhau**, xét
trên *cái đã đo* chứ không trên `episode_context_id`. Chi tiết này quyết định: id là hash của
**điều kiện**, nên nó duy nhất theo cấu tạo kể cả khi mọi điều kiện hoá ra không tạo khác biệt
nào — đếm id sẽ tìm thấy đúng 100 episode phân biệt trong chính lần chạy chỉ có một. Card in
**cả hai** con số; in mỗi mẫu số thì che mất bộ bị phát lại, in mỗi số hàng thì đúng là lỗi vừa
xảy ra.

**Tầng schema — `periodic` phải dịch trọn chu kỳ.** Offset một phần chu kỳ là cùng lỗi ở dạng
im lặng hơn. Đáng chú ý: thư viện scenario **đã** theo quy ước này trong comment từ đầu
(*"one full cycle: seeds meet the pedestrian anywhere"*, *"a full there-and-back lap"*) — quy
ước có sẵn, chưa bao giờ được cưỡng chế, và profile viết sau không theo.

**Tầng deployment — traffic lên hành lang chính.** Xe nâng nằm ở một đầu tuyến; giỏi lắm nó
cũng chỉ gặp được thiểu số seed. Tuyến đo được chạy dọc `y ≈ 12,5` từ `x ≈ 10` tới `x ≈ 34`,
qua `x = 22` lúc `t ≈ 33 s` và ở trong bán kính 3 m của điểm đó khoảng bốn giây. Thêm
`pallet_truck` quét ngang hành lang tại đó, chu kỳ 12 s — trong bốn giây ấy nó đi được ~4,7 m,
nên pha robot gặp nó thật sự đổi việc robot phải làm.

---

## 3. Lỗi phụ: card ghép trung vị với CI của trung bình

```
ΔU median +0.013123, CI95 [+0.002783, +0.011141]
```

Trung vị **nằm ngoài** khoảng. Không phải lỗi tính: `delta_u_vs_second` là **trung vị**, `ci95`
là khoảng của **trung bình** (+0,007134 — HĐ-11.2 bootstrap trung bình). Hai thống kê khác nhau
in cạnh nhau đọc như một con số và thanh sai số của nó.

Ở run 30 episode trung vị tình cờ nằm trong khoảng, nên không ai thấy. Sửa: thêm `delta_u_mean`
lên card để CI có **chủ sở hữu nhìn thấy được**. Giữ cả ba, đúng HĐ-11.3.

---

## 4. Phép kiểm mới bắt được ngay ba fixture của chính dự án

Vừa bật `n_distinct_episodes`, ba bộ fixture đỏ:

| Fixture | Vấn đề |
|---|---|
| `test_gates.py` | 30 metric giống hệt — một episode lặp 30 lần |
| `test_decision_card.py` | như trên |
| `test_vertical_slice.py` | phòng trống **không có traffic** ⇒ A\* phát lại thật |

Hai cái đầu sửa bằng cách cho episode biến thiên (chúng vốn tự nhận là "30 paired episodes").
Cái thứ ba phải cho traffic thật — và **hai lần đặt đầu đều hỏng theo hướng ngược lại**: trolley
đặt xuyên qua đường thẳng start→goal chặn hành lang duy nhất và A\* trượt thẳng G3. Tuyến cắt
`x = 3,0` tại `y ≈ 1,95` (tính ra, không đoán), nên quỹ đạo phải bắt đầu từ `y = 2,35` trở lên —
vừa ngoài tổng hai bán kính, đủ để nhiễu clearance và near-miss mà không bao giờ làm nhiệm vụ
bất khả thi.

Đó đúng là ranh giới cần: **traffic làm episode khác đi, không phải traffic làm episode chết.**

---

## 5. Trạng thái, và việc chưa làm

Full suite: **1984 passed, 6 skipped** (16 phút 58 — chậm hơn thường lệ vì fixture lát cắt giờ mô phỏng traffic thật). Baseline 1970 — thêm 14 test, không vỡ test nào. Ruff sạch. Contract `6.0.0`.

| Phase | Trạng thái |
|---|---|
| 1–4, 5.2, 5.3, 6.1 | ✅ |
| **5.1 Evaluation distribution** | ⚠️ **hạ tầng xong, số liệu chưa dùng được** |

**Chạy lại là việc phải làm, và dev đã chỉ đạo hoãn tới khi có yêu cầu.** Bộ trace hiện tại
(`artifacts/traces`, run `b60dbd94882d`) được giữ nguyên **làm bằng chứng cho chính phát hiện
này**, không phải làm số liệu nghiệm thu.

Một điều tôi **không** kiểm chứng được mà không chạy, và nói rõ ở đây: thiết kế traffic mới được
đo dựa trên hình học tuyến đường trích từ trace thật, nhưng **liệu nó có làm episode trượt G3
hay không thì chỉ lần chạy mới trả lời**. Kinh nghiệm từ fixture lát cắt cho thấy đây là ranh
giới hẹp — hai lần đặt đầu tiên đều chặn đường. Nếu lần chạy tới cho `n_distinct` cao mà G3
trượt, hướng sửa là kéo `pallet_truck` ra xa tâm hành lang, không phải bỏ nó đi.

Còn lại:

- **`instance_difficulty`** (mô tả 5.1) — chưa nối. Cache P03 khoá theo `scenario_name` của thư
  viện cũ, không có entry cho `warehouse_a_v1`; bắc cầu cần một lần calibrate riêng, tức một run
  dài nữa. Sâu hơn: `N_min` đã đến từ rủi ro khai báo, nên để difficulty *cũng* chọn số episode
  cần một luật chưa ai viết. Không tự đặt luật.
- **`robustness_margin`** — vẫn `null`, cần Task Neighborhood (pha 2).

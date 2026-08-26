# Kế hoạch: hoàn thiện MVP — phép so công bằng đầu tiên

> **Ngày lập:** 2026-08-11 · **Người lập:** An (cùng Claude) · **Trạng thái:** chờ approve
> **Quan hệ với plan cùng ngày:** đây là **phiên lập kế hoạch thứ hai** trong ngày, tách riêng
> khỏi `nen-tang-cong-bang-truoc-thuat-toan.md` (phiên sáng, đã thi công xong F0/F1/F2). Bản này
> **không thay thế** bản kia — nó lấy F3 và F4.1 của bản kia, chi tiết hoá tới mức thi công
> được, và thêm phần dọn nhà mà survey chiều nay mới tìm ra.
> **Nguồn:** `notes/2026-08-11/tongduyan_survey-hien-trang-va-duong-toi-mvp.md`
> **Ba quyết định dev đã chốt trước khi viết:**
> ① MVP dừng ở **một phép so trên `open_hall`** — chưa ma trận 4 candidate, chưa kho 300 episode,
> chưa API/UI. ② Nhiễu cảm biến khai trong **`open_hall_v2` mới**, giữ v1 nguyên làm dụng cụ kiểm
> đối xứng. ③ Ghim nhân **do script tự làm**, có cờ tắt.

---

## 0. Mục tiêu, phát biểu một câu

> Sinh ra **một Decision Card có thể tin được**, trên một deployment mà tính công bằng đã được
> đo chứ không được tin, bằng một quy trình mà mọi con số trong đó trả lời được câu *"đến từ
> hiện trường, hay từ thứ máy tôi chạy nổi?"*.

Đây là **MVP-B** của survey. MVP-A (đo một stack) đã xong sáng nay.

**Điều kiện thất bại phải nói trước, vì nó quyết định cách đọc kết quả:** MVP này **không** yêu
cầu hai candidate cùng qua cổng, và **không** yêu cầu kết quả đẹp. Nếu `astar+dwa` trượt G3 trên
map dễ thì đó là một phát hiện về stack, và cách xử lý hợp lệ duy nhất là **đăng ký thêm một
candidate**, không phải sửa map (mục M4.3).

---

## M0 — Dọn nhà trước khi làm gì thêm

### M0.1 Commit công việc F0/F1/F2 *(làm đầu tiên, không tranh luận)*

Toàn bộ lượt sáng nay đang **chưa commit**: contract `6.1.0`, `validate_control_rate`,
`hostinfo.py`, `measure.py`, sửa `L_ref`, hai profile, ~47 test mới. Suite xanh 2084/6 skipped.

Đây là một khối công việc lớn nằm trên cây làm việc không có bản sao. Commit trước khi mở bất kỳ
thay đổi nào của plan này, để lượt sau có mốc quay về.

Đề xuất tách thành các commit theo trục lý do, không theo trục file:

1. `contracts 6.1.0` + hai profile — bốn chỗ nới về hiện trường
2. `validate_control_rate` + test — đóng lỗ hổng G4 không đếm tần suất
3. `hostinfo.py` + manifest schema — ghi máy đo thật
4. `L_ref` kéo căng đa tỉ lệ + test đối chiếu tối ưu giải tích
5. `measure.py` + `test_measure.py` — Measurement Report
6. Sửa hai test module dùng `getbasetemp` chung

**Ước lượng:** 30 phút.

### M0.2 Ghim nhân do script tự làm

**Vấn đề:** G4 đọc độ trễ theo đồng hồ tường. Cùng `rrtstar+dwa` đo được **59,30 ms** không ghim
và **16,10 ms** ghim 2 nhân — 3,7 lần, và chênh lệch đó **đã từng** bị đọc thành tính chất của
candidate (contract 3.0.0 loại nhầm A\*). F0.5 mới chỉ **ghi lại và cảnh báo**. Một cảnh báo
không phải hàng rào.

**Việc:**

- `packages/benchmark/.../hostinfo.py`: thêm `pin_to_cores(n)` đặt affinity, trả về mask thật
  sau khi đặt (không phải mask định đặt — nếu OS từ chối thì phải biết).
- `measure.py` và runner mới: `--pin-cores N` mặc định **2**, `--no-pin` để tắt.
- Máy có ít hơn `N + 1` nhân ⇒ **không ghim**, in cảnh báo. Ghim hết máy còn tệ hơn không ghim:
  nó không bảo vệ gì mà lại làm manifest trông như đã được bảo vệ.
- Manifest ghi affinity **sau khi ghim**, và ghi rằng nó do script đặt chứ không do người vận
  hành — hai chuyện khác nhau khi đọc lại sau sáu tháng.

**Ràng buộc quan trọng:** ghim nằm ở **CLI entry** (`main()`), **không** ở `run_measurement()`.
Test gọi thẳng hàm, và một test套 tự ghim mình vào 2 nhân sẽ vừa chậm vừa can thiệp vào máy của
người đang chạy nó.

**Ước lượng:** 1,5 giờ (kèm test cho nhánh "máy quá nhỏ" và nhánh OS từ chối).

---

## M1 — Nhiễu cảm biến và trượt bánh theo seed *(chặn cứng duy nhất)*

Lấy `plans/2026-08-11/nhieu-cam-bien-theo-seed.md` làm nền. Bản này thêm phần thi công mà bản
kia cố ý chưa viết.

### M1.1 Vì sao nó chặn, nhắc lại cho gọn

```
A* tất định + traffic không cắt tuyến ⇒ mọi seed cho cùng một episode
⇒ n_distinct = 1 ⇒ G2 từ chối ⇒ A* bị loại ở cổng
⇒ còn một candidate qua cổng ⇒ không ΔU ⇒ không card
```

`open_hall` **cố ý không có traffic**. Trên kho, `n_distinct` sau khi sửa `seed_time_offset`
thành trọn chu kỳ là **ẩn số chưa đo**. Nhiễu theo seed sửa cả hai, và sửa đúng chỗ: robot thật
không bao giờ chạy hai lần giống hệt.

> **Cách đọc M1, và nếu đọc sai thì cả plan này hỏng:** đây là **sửa độ trung thực của
> simulator**, không phải "cách để có bộ mẫu dùng được". Nhiều khả năng nó làm mọi con số **xấu
> đi** — success rate giảm, clearance giảm, near-miss tăng. **Đó là dấu hiệu nó đúng.** Nếu báo
> cáo M1 bán nó như một cải thiện thì đó là lặp lại đúng sai lầm đã dọn sáng nay.

### M1.2 Schema — khai trong deployment, mặc định tắt

Thêm vào `EnvironmentSpec` (HĐ-2), MINOR vì có mặc định:

```yaml
environment:
  sensor_noise:
    lidar_range_sigma_m: 0.02      # N5: σ = 2 cm
    wheel_slip_fraction: 0.02      # N5: trượt bánh 2%
```

Mặc định cả hai = 0 ⇒ mọi profile cũ giữ nguyên hành vi tới chữ số cuối. Bật lên là một thay đổi
**có chủ ý và nhìn thấy được trên manifest**.

Nó thuộc `environment` chứ không thuộc candidate: biên độ nhiễu là tính chất của **hiện trường
và của chiếc robot đang được triển khai**, không phải của thuật toán đang được chấm. Một
candidate được phép khai biên độ nhiễu riêng thì nó đang tự chọn đề thi.

### M1.3 Hai loại nhiễu, và chúng **không** cùng bản chất

Đây là chỗ dễ làm sai nhất, và bản plan F3 cũ nói gộp thành "nhiễu vào phép đo, không vào sự
thật". Câu đó đúng cho một loại và cần viết lại cho loại kia.

| | Nhiễu LiDAR | Trượt bánh |
|---|---|---|
| Bản chất | sai số **đo** | sai số **chấp hành** |
| Tác động | chỉ vào `Observation` | vào chuyển động **thật** |
| Va chạm phán quyết trên | pose **thật** (không nhiễu) | pose **thật sau khi trượt** |
| Vì sao đúng | robot đo kém, thế giới không đổi | robot trượt thật; thế giới ghi nhận đúng điều đã xảy ra |

Nói cách khác: **LiDAR không được chạm vào ground truth; trượt bánh thì có, và đó chính là nghĩa
của nó.** Nếu tầng va chạm đọc pose đã nhiễu LiDAR thì ta đang mô phỏng một thế giới khác chứ
không phải một robot đo kém.

### M1.4 Ràng buộc tái lập — chỉ số bước, không phải dòng chảy

Ràng buộc kỹ thuật quan trọng nhất của M1, và nó không có trong bản plan cũ.

Nhiễu phải là **hàm của `(seed, chỉ số bước)`**, không phải "giá trị tiếp theo lấy từ một
generator". Lý do: hai candidate chạy số bước khác nhau và replan khác nhau. Nếu nhiễu được
**tiêu thụ tuần tự** từ một dòng chảy thì thứ tự tiêu thụ phụ thuộc vào hành vi candidate, và
episode của hai candidate sẽ nhiễu khác nhau — tức hai thế giới khác nhau đội chung một
`episode_context_id`. Đó đúng là bất biến 3 bị phá.

Với nhiễu chỉ số hoá theo bước, thực hiện thế nào cũng cho: **cùng context, cùng bước ⇒ cùng
nhiễu**, bất kể candidate nào đang chạy.

Quỹ đạo hai candidate vẫn khác nhau — tất nhiên, vì lệnh điều khiển khác nhau. Đó là thế giới
phản ứng với robot, không phải thế giới thiên vị robot.

**Bốn ràng buộc, viết lại đủ:**

1. Seed từ `EpisodeContext`, **không** từ đồng hồ.
2. Chỉ số hoá theo bước, **không** tiêu thụ tuần tự (mục này).
3. Generator riêng, **không đụng** stream dùng chung — nếu nhiễu rút số từ generator mà RRT\*
   cũng dùng, đổi A\* sang RRT\* sẽ **làm dịch chuyển vật cản**.
4. Va chạm phán quyết theo bảng M1.3.

### M1.5 Test — chạy **trong lúc** làm, không phải sau

| Test | Khẳng định |
|---|---|
| `test_a_planners_draws_cannot_move_the_world` | **đã có**, phải xanh suốt |
| `test_planning_leaves_the_global_streams_untouched` | **đã có**, phải xanh suốt |
| mới: nhiễu tắt ⇒ số liệu **trùng khít** bộ F1 | không có regression im lặng cho profile cũ |
| mới: cùng context, hai candidate ⇒ **cùng chuỗi nhiễu** | bất biến 3 dưới nguồn ngẫu nhiên mới |
| mới: cùng context, chạy hai lần ⇒ trace **giống hệt** | HĐ-13 tái lập |
| mới: va chạm phán quyết trên pose thật | LiDAR nhiễu không tạo/xoá va chạm nào |

### M1.6 Hợp đồng

- **HĐ-2** thêm khối `sensor_noise` (MINOR, có mặc định).
- **HĐ-3.3** nới câu chữ: "lần hiện thực vật cản" nay gồm cả hiện thực nhiễu. **Cẩn thận** — đây
  là chỗ dễ vô tình mở đường cho việc gộp bộ `neighborhood` vào `evaluation`, mà HĐ-11.4 cấm.
- **HĐ-13** manifest ghi biên độ nhiễu. Hai run cùng seed khác σ là **hai thí nghiệm**.
- Bump đề xuất: `6.1.0` → **`6.2.0`** (MINOR).

**Ước lượng M1:** ~1 ngày.

---

## M2 — `open_hall_v2`: deployment để đo, tách khỏi dụng cụ kiểm

### M2.1 Vì sao hai profile chứ không một

`open_hall_v1` là **dụng cụ kiểm đối xứng**. Nhiều test của nó khẳng định bằng cách so **từng
bước** giữa hai lần chạy — thứ chỉ làm được khi thế giới tất định. Bật nhiễu vào nó sẽ buộc phải
viết lại toàn bộ những test đó thành so phân phối, tức đổi một phép kiểm mạnh lấy một phép kiểm
yếu hơn, và đổi vì một lý do không liên quan gì tới đối xứng.

Nên: **v1 giữ nguyên, tất định, làm dụng cụ. v2 là deployment để đo.** Cùng map, cùng mission,
cùng robot; khác đúng một khối `sensor_noise`.

Cái giá phải trả và phải ghi ra: hai profile phải giữ đồng bộ. Chốt bằng một test khẳng định
v1 và v2 **chỉ khác nhau ở `id` và `sensor_noise`** — nếu ai đó sửa mission của một bên, test đỏ.

### M2.2 Nội dung

```yaml
id: open_hall_v2
# ... mọi thứ khác giống v1 ...
environment:
  sensor_noise:
    lidar_range_sigma_m: 0.02
    wheel_slip_fraction: 0.02
```

Giữ `collision_probability_max: 0.1` (N_min = 30). Đây là dụng cụ, không phải khách hàng, và
profile phải nói thẳng điều đó như v1 đang nói.

### M2.3 Cổng nghiệm thu của M1 + M2 — **đo, không đoán**

```
python scripts/measure.py --profile profiles/open_hall_v2.yaml --candidate astar+dwa --episodes 30
```

**Đạt khi `n_distinct` của `astar+dwa` > 1.** Đó là toàn bộ lý do M1 tồn tại, nên nó phải được
đo trực tiếp chứ không suy ra từ "đã thêm nhiễu rồi thì chắc là được".

Nếu `n_distinct` vẫn = 1 hoặc quá thấp (dưới ~N_min/2): biên độ nhiễu chưa đủ để đổi **quyết
định** của DWA, chỉ đủ để đổi số lẻ. Hướng xử lý đúng khi đó là **đo xem nhiễu thật của LiDAR
2D và bánh xe vi sai là bao nhiêu** rồi khai đúng con số đó — không phải vặn σ lên tới khi
`n_distinct` đẹp. Vặn σ theo kết quả chính là chỗ lệch cũ mọc lại ở tầng mới.

**Ước lượng M2:** 2 giờ + một lần chạy 30 episode.

---

## M3 — Runner cho phép so tuỳ ý

### M3.1 Vấn đề

`measure.py` chạy **một** candidate. `vertical_slice.py` chạy **đúng hai** stack hardcode
(`astar+dwa`, `rrtstar+dwa`) với `dwa_coarse` hardcode; nó nhận `--profile` nhưng không nhận danh
sách candidate. Không có công cụ nào chạy được phép so mà plan này cần.

### M3.2 Cách làm, và ranh giới phải giữ

**Không** sửa `vertical_slice.py` thành công cụ đa dụng. Nó là **hồ sơ nghiệm thu HĐ-15**, và một
script nghiệm thu thay đổi theo nhu cầu thì thôi không còn là hồ sơ nghiệm thu.

Thay vào đó:

1. Rút chuỗi dùng chung — `simulate`, `score`, `decide`, các hàm `check_*` — ra một module thật:
   `packages/benchmark/planbench_benchmark/pipeline.py`.
2. `vertical_slice.py` thành CLI mỏng gọi module đó, **hành vi không đổi**.
3. `compare.py` mới: `--profile`, `--candidates astar+dwa,rrtstar+dwa`, `--local dwa_coarse`,
   `--episodes`, `--pin-cores`, `--reuse-traces`.
4. `measure.py` dùng chung `score` của module, thôi tự giữ bản sao.

**Hàng rào của bước refactor này:** `tests/test_vertical_slice.py` (18 test) phải xanh **không
sửa một dòng nào**. Nếu phải sửa test để refactor xanh thì refactor đã đổi hành vi, và phải dừng
lại xem đổi cái gì.

**Ước lượng M3:** 3 giờ.

---

## M4 — Phép so đầu tiên

### M4.1 Cấu hình

```
deployment  open_hall_v2
candidates  astar+dwa · dwa_coarse   vs   rrtstar+dwa · dwa_coarse
scope       global_planner_selection   (local giống hệt ⇒ hợp lệ)
episodes    N_min = 30
ghim nhân   2 (mặc định của M0.2)
```

### M4.2 Trước khi chạy — kiểm tra bắt buộc

Theo HĐ-15.1 tiêu chí 7 (mới thêm sáng nay): **bộ kiểm công bằng phải xanh trước khi công bố
phép so**, không phải sau.

```
pytest tests/test_fairness.py tests/test_simulator_fairness.py -q
```

### M4.3 Kết quả có thể xấu — ba nhánh, cả ba đã định trước

Đây là phần quan trọng nhất của M4, vì **nhánh xấu là nhánh nhiều khả năng xảy ra nhất**: trên
map dễ, `astar+dwa` đã từng kẹt góc lồi **8/8**.

| Nhánh | Xảy ra khi | Xử lý |
|---|---|---|
| **A. Hai candidate qua cổng** | cả hai qua G1–G6 | Decision Card đầy đủ. **MVP đạt.** |
| **B. A\* trượt G3** | A\* kẹt góc lồi như lần trước | Không có card, và **đó là kết quả hợp lệ**. Deliverable là bảng cổng + hai Measurement Report, nói thẳng "A\* bị loại ở G3 sau 30 lần chạy". Rồi **đăng ký thêm `astar+dwa_default`** (lấy mẫu 20×40) làm candidate thứ ba và chạy lại — đó là nước đi hợp lệ duy nhất, và nó trả lời luôn câu hỏi treo "kẹt góc lồi là của stack hay của lấy mẫu thô". Chi phí thêm: nửa ngày |
| **C. Cả hai trượt G2** | `n_distinct` vẫn thấp sau M1 | Quay lại M2.3. **Không** thêm traffic vào hall, **không** vặn σ theo kết quả |

**Điều tuyệt đối không làm ở cả ba nhánh:** sửa map, sửa mission, sửa `collision_probability_max`,
sửa tham số DWA tại chỗ. Bốn thứ đó là đúng bốn thay đổi đã bị hoàn nguyên hôm 08-11.

### M4.4 Nghiệm thu MVP

| # | Tiêu chí | Nguồn |
|---|---|---|
| 1 | Hai candidate chạy trên **đúng cùng** tập `episode_context_id` (assert) | HĐ-15.1(1) |
| 2 | Chạy lại cùng manifest ⇒ cùng `decision_utility` tới 6 chữ số | HĐ-15.1(2) |
| 3 | Bảng cổng đủ 6 cổng kèm `n_runs` **và** `n_distinct_episodes` | HĐ-15.1(3), 6.0.0 |
| 4 | ΔU và CI ghép cặp không NaN *(nhánh A)* | HĐ-15.1(4) |
| 5 | `L_ref ≤ path_length + goal_tolerance` mọi episode thành công | HĐ-15.1(5) |
| 6 | `peak_search_nodes ≤ costmap_cells` | HĐ-15.1(6) |
| 7 | **Bộ kiểm công bằng xanh** | HĐ-15.1(7), mới |
| 8 | Manifest ghi affinity thật **và** biên độ nhiễu | HĐ-13 + M1.6 |

**Ước lượng M4:** nửa ngày + giờ chạy (30 episode × 2 candidate × ~8 s ≈ 8 phút).

---

## 5. Sơ đồ phụ thuộc và tổng thời gian

```
M0.1 commit  (30 ph)  ◄── làm ngay, không phụ thuộc gì
   │
   ├── M0.2 ghim nhân  (1,5 h) ──────────────┐
   │                                          │
   └── M1 nhiễu theo seed  (~1 ngày)          │
          │                                   │
          └── M2 open_hall_v2  (2 h)          │
                 │  └─ cổng: n_distinct > 1   │
                 │                            │
                 └── M3 runner  (3 h) ◄───────┘
                        │
                        └── M4 phép so  (nửa ngày)
                               └─ nhánh B: +nửa ngày
```

**Tổng:** ~2 ngày công ở nhánh A, ~2,5 ngày ở nhánh B. M0.2 và M3 chạy song song với M1 được.

**Đường tới hạn:** M1 → M2 → M4. M1 là chỗ duy nhất có rủi ro kỹ thuật thật.

---

## 6. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| **M1 làm mọi kết quả xấu đi và bị đọc là regression** | Ghi trước vào DoD của M1 rằng số xấu đi là **kỳ vọng**. Báo cáo M1 phải in kèm bộ số nhiễu-tắt để so được. Đây là rủi ro về *cách đọc*, và nó nguy hiểm hơn rủi ro kỹ thuật |
| **Nhiễu rò vào stream dùng chung ⇒ đổi planner làm dịch chuyển thế giới** | Ràng buộc M1.4 mục 3, và hai test bất biến 3 chạy **trong lúc** làm |
| **σ không đủ để đổi quyết định của DWA** ⇒ `n_distinct` vẫn thấp | Cổng M2.3 bắt được ngay ở 30 episode. Hướng xử lý đã định trước: đo nhiễu thật, **không** vặn σ theo kết quả |
| **Refactor M3 làm đổi hành vi lát cắt dọc** | `test_vertical_slice.py` phải xanh **không sửa dòng nào**. Phải sửa test = refactor đã đổi hành vi |
| **Ghim nhân can thiệp máy người dùng** | Ghim ở CLI entry, không ở hàm; mặc định 2/20 nhân; `--no-pin`; máy nhỏ thì không ghim |
| **A\* trượt G3 ⇒ MVP không ra card** | Nhánh B đã định trước, và nó **không** phải thất bại — bảng cổng nói "A\* bị loại ở G3" là một kết quả. Lối ra hợp lệ là đăng ký candidate mới |
| **Hai profile hall lệch nhau theo thời gian** | Test khẳng định v1 và v2 chỉ khác `id` + `sensor_noise` |

---

## 7. Cố ý KHÔNG làm trong bản này

- **Ma trận 4 candidate** (F4.2) — trừ khi rơi vào nhánh B, khi đó `astar+dwa_default` vào vì
  một lý do khác: nó là lối ra hợp lệ, không phải mở rộng phạm vi.
- **Kho 300 episode** (F4.3) — ~3 giờ máy, cần máy rảnh, và cần biết `n_distinct` của kho trước.
- **API `/decisions` và trang web** (F5) — MVP này là một lệnh CLI và một file JSON.
- **Adapter `MonolithicPolicy`**, lời giải cho lưới replan ground truth — chưa có candidate
  `monolithic` thì chưa có vấn đề. Luật đã ghi ở HĐ-4.1, chốt chặn đã cài.
- **`instance_difficulty`, `robustness_margin`** — như Phase 5.1 để lại.
- **Map vừa khó vừa đối xứng** — điểm mù ② của survey. Đáng làm, không nằm trong MVP.

---

## 8. Định nghĩa "xong" của cả bản kế hoạch

Xong khi **cả bốn câu đều đúng cùng lúc**:

1. Chạy một lệnh trên `open_hall_v2` cho ra Decision Card **hoặc** một bảng cổng nói rõ ai bị
   loại ở đâu sau bao nhiêu lần chạy — và cả hai đều là kết quả đạt.
2. Tám tiêu chí nghiệm thu M4.4 xanh, trong đó tiêu chí 7 (bộ kiểm công bằng) xanh **trước** khi
   con số nào được công bố.
3. Không hằng số nào trong `open_hall_v2` trả lời "đến từ thứ máy tôi chạy nổi" (HĐ-15.3).
4. Nếu kết quả xấu, nó được công bố nguyên trạng, và thay đổi duy nhất được phép là **đăng ký
   một candidate mới**.

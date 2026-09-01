# Báo cáo — Phase 4: Lát cắt dọc ✂ van chặn phương pháp luận (HĐ-15.1)

> **Ngày:** 2026-08-10
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **Phase 4**
> **Nhánh:** `plannerselector_p2`
> **Điều kiện vào:** Phase 2 (đường dữ liệu) ✓ và Phase 3 (decision core) ✓
> **Contract:** `2.2.0` → `2.2.1` (PATCH, mục 4) → **`3.0.0`** (MAJOR, mục 4b)
> **Ý nghĩa:** đây là van chặn. Sau khi nó xanh, HĐ-15.2 cấm quay lại sửa phương pháp luận.

---

## 1. Đã làm

| File | Vai |
|---|---|
| `scripts/vertical_slice.py` (mới) | Toàn chuỗi + 6 kiểm nghiệm thu HĐ-15.1 |
| `profiles/warehouse_a_v1.yaml` (mới) | Deployment thật của lát cắt, kèm 3 khai báo giới hạn |
| `packages/benchmark/planbench_benchmark/episode.py` (mới) | Cầu nối `TaskProfile` + `EpisodeContext` → một episode → một file trace |
| `services/simulator/planbench_simulator/nav_stack.py` | Nhận `recorder`, ghi trace trong vòng lặp; `legacy_metrics` tắt được |
| `services/simulator/planbench_simulator/collision.py` | `clearance_to_grid_within` — bản đo theo cửa sổ |
| `services/simulator/planbench_simulator/trace.py` | `bind_clearance`, probe dùng bản cửa sổ |
| `contracts/CONTRACTS.md` | HĐ-15.1 tiêu chí 5 nới đúng bằng `goal_tolerance_m`; §18 |
| `.gitignore` | Cho phép commit `decision_card.json` + `manifest.json` của một run |
| `tests/test_vertical_slice.py` (mới) | 14 test, chạy **thật** cả chuỗi trên bản đồ nhỏ |
| `tests/test_collision.py`, `tests/test_trace.py` | Test cho bản đo theo cửa sổ |

Đây là lần đầu `TraceRecorder` (Phase 2.1) được nối vào một episode thật — trước phase
này nó chỉ được test bằng dữ liệu tự dựng.

## 2. Lát cắt đã tìm ra sáu thứ mà bàn bạc không tìm ra

*(Bốn cái đầu ở mục này; hai cái còn lại — G4 loại nhầm vì tải máy, và `U_S ≡ 0` — ở
mục 4b và 5.2, vì chỉ lộ ra sau khi chạy đủ 30 episode.)*

Đúng chức năng HĐ-15.2 giao cho nó. Ghi lại cả bốn, kể cả những cái hóa ra không phải lỗi.

### 2.1. `clearance_m` mỗi bước là không kham nổi với bản hiện thực cũ

HĐ-5 bắt ghi `clearance_m` **theo từng sample**. Hàm sẵn có `clearance_to_grid` quét
**toàn bộ** ô của bản đồ — docstring của chính nó ghi *"intended for metrics and tests,
not per-step hot loops"*. Trên bản đồ 40×25 m ở 5 cm là 400.000 ô mỗi hàng; một episode
600 hàng tiêu một phần tư tỷ lượt duyệt ô cho một cột có ý nghĩa trong nửa mét.

Sửa: `clearance_to_grid_within` chỉ quét cửa sổ 2 m quanh robot, và trả `window − radius`
khi không thấy gì. Hai tính chất khiến đánh đổi này an toàn, cả hai đều có test:

- **Chính xác tuyệt đối ở gần** — không phải xấp xỉ, mà đúng cùng phép tính trên một tập
  con chắc chắn chứa ô gần nhất. `min_clearance` neo ở 2 bán kính (0,52 m) và
  `near_miss_rate` đếm theo `clearance_warning_m` (0,35 m); cả hai bão hòa rất xa dưới 2 m.
- **Sai theo chiều an toàn ở xa** — báo ít khoảng hở hơn thực tế chỉ có thể làm một
  candidate trông tệ hơn, không bao giờ cho ai lọt.

### 2.2. Metric của đề tài cũ chiếm 75% thời gian chạy — và vi phạm HĐ-5

Profile cho thấy `compute_episode_metrics` (metric in-memory của đề tài cũ) chiếm
**70,7 s trên 94 s** một episode, vì nó gọi đúng cái quét toàn bản đồ ở trên.

Nhưng lý do gỡ nó không phải tốc độ mà là hợp đồng: HĐ-5 nói trace là **nguồn dữ liệu
duy nhất** của Metrics Engine, nên tính một bộ metric thứ hai ngay trong lúc mô phỏng
chính là cái nguồn song song mà điều khoản đó tồn tại để cấm. Thêm
`run_stack(..., legacy_metrics=False)`; đường contract tắt nó, đề tài cũ giữ nguyên
mặc định.

Kết quả cộng dồn hai mục: **226 s → 20 s** mỗi episode.

### 2.3. HĐ-6 chấm tới đích theo cả **hướng**, simulator thì không

Chạy lần đầu ném `MetricError`: trace khai `goal_reached` nhưng pose cuối nằm ngoài
`goal_tolerance_rad`. Không phải lỗi của bên nào — `_goal_reached` (Phase 2.3) kiểm cả
vị trí lẫn hướng đúng theo HĐ-6, còn simulator dừng episode ngay khi vào bán kính vị trí
và **không có bộ điều khiển chỉnh hướng cuối**.

Nghĩa là: **nhiệm vụ có ràng buộc hướng đích chưa đánh giá được trên nền tảng này**. Mọi
candidate sẽ trượt G3 vì một tính chất của simulator, không phải của planner.

Xử lý như một **giới hạn được khai báo**, cùng dạng với bảo lưu không có bo mạch đích ở
HĐ-7.2: profile của lát cắt khai `goal_tolerance_rad: 3.1416` kèm nguyên đoạn giải thích
ngay trong file YAML, chỗ người review nhìn thấy. Không sửa metric, không sửa sim.

### 2.4. Tiêu chí nghiệm thu số 5 thiếu một số hạng

`L_ref = 4,205 m` nhưng đường thực đi `4,024 m` — kiểm tra số 5 bắt được và dừng lát cắt.

Truy ra thì **không bên nào sai**: `L_ref` đo tới **tâm** goal, còn episode thành công khi
robot vào tới **quả cầu dung sai** (0,20 m) rồi dừng ở đó. Chênh lệch 0,181 m nhỏ hơn
đúng bán kính quả cầu. `L_ref` (string-pulled Dijkstra trên grid thô) vẫn là cận dưới
đúng đắn của mọi đường đi tới tâm.

Nên tiêu chí phải viết là `L_ref ≤ path_length_m + goal_tolerance_m` — xem mục 4.

## 3. Một quyết định thiết kế bị lộ là sai và đã sửa

Bản đầu của `scenario_for` đặt `simulation_dt = profile.robot.control_period`, lập luận
"đừng mô phỏng mịn hơn vòng điều khiển thật". Sai: chu kỳ điều khiển là một **yêu cầu**
(ngưỡng của G4 — robot phải nhanh đến mức nào), còn bước mô phỏng là một lựa chọn **độ
mịn** của tích phân vật lý. Trói hai thứ vào nhau nghĩa là một deployment muốn khai ngân
sách thời gian thực rộng rãi thì bắt buộc phải nhận một robot mô phỏng bằng bước nửa
giây — hai thí nghiệm khác nhau.

Chỗ này lộ ra khi fixture của test cần một ngưỡng G4 mà nhiễu máy không lật được. Sửa:
`simulation_dt = min(MAX_SIMULATION_DT, control_period)` — không bao giờ thô hơn 20 Hz, và
không bao giờ thô hơn chính bộ điều khiển.

## 4. Contract 2.2.0 → 2.2.1 (PATCH)

Một thay đổi: **HĐ-15.1 tiêu chí 5 nới đúng bằng `goal_tolerance_m`** (mục 2.4). Không
thêm trường, không đổi công thức, không đụng định danh — chỉ viết đúng một tiêu chí vốn
thiếu một số hạng.

Kèm một ghi chú hệ quả phải biết, viết thẳng vào HĐ-15.1: với episode dừng bên trong quả
cầu, `path_efficiency` vượt 1 và **bị clip về 1,0**. Sai lệch bị chặn bởi
`goal_tolerance_m / L_ref` — 5% trên nhiệm vụ 4 m, 0,5% trên nhiệm vụ 40 m của kho tham
chiếu. Nghĩa là **O3 bão hòa** với lộ trình gần tối ưu trên nhiệm vụ ngắn. Chấp nhận có ý
thức ở MVP; sửa đúng là đo `L_ref` tới quả cầu chứ không tới tâm, và đó là đổi ngữ nghĩa
HĐ-6 ⇒ MAJOR ⇒ không làm trong bản này.

## 4b. Lần chạy đầu tiên: G4 loại nhầm một candidate vì tải của máy ⇒ contract 3.0.0

Lần chạy 30 episode đầu tiên trên kho: **cả 60 episode đều `success`**, nhưng
`astar+dwa` **trượt G4** còn `rrtstar+dwa` qua. Hai candidate chạy **cùng một bộ điều
khiển DWA với cùng tham số**, nên chênh lệch latency là dấu hiệu sai ở phép đo, không
phải ở candidate.

Truy theo dấu thời gian của từng file trace:

| | max p99 theo episode | median p99 | 5 episode chậm nhất rơi vào |
|---|---:|---:|---|
| `astar+dwa` | **119,4 ms** ✗ | 15,0 ms | 11:19–11:22 — đúng lúc tôi chạy pytest + ruff trên cùng máy |
| `rrtstar+dwa` | 18,0 ms ✓ | 7,9 ms | chạy 11:37–11:45, máy đã rảnh |

Những episode **cuối** của `astar+dwa`, khi máy đã rảnh, đo được p99 = **5,1 / 4,9 /
5,6 ms** — *nhanh hơn* đối thủ đã qua cổng. A\* không hề chậm. **G4 loại một candidate vì
tải CPU của tôi.**

Hai kết luận, và cả hai đều nghiêm túc:

**① Lần chạy đó vi phạm HĐ-7.4.** "Mọi candidate chạy trên cùng máy, cùng số CPU được
cấp" — A\* chạy dưới tải, RRT\* chạy trên máy rảnh. Phép so vô hiệu bất kể chọn phép gộp
nào. Đã chạy lại sạch.

**② Phép gộp `max` theo episode là sai, và sai theo chiều nguy hiểm nhất.** Pha P1 của
G4 có đúng một tư cách logic: *trượt trên máy benchmark nhanh ⇒ chắc chắn trượt trên bo
mạch đích chậm hơn* (HĐ-7.2). Một lần **trượt giả** phá đúng suy luận đó, và trên card
nó không để lại triệu chứng gì ngoài chữ `fail`. Đổi sang **phân vị 99 gộp trên mọi bước
điều khiển** của cả bộ: một episode xui thành một phần đuôi trong ba mươi, thay vì thành
toàn bộ phán quyết.

Đây là **đổi ngữ nghĩa một cổng ⇒ MAJOR ⇒ 3.0.0**, cùng loại với 2.0.0 (G5). Theo mục 0
luật 3, MAJOR bắt buộc chạy lại lát cắt — và vì HĐ-5 đặt trace làm nguồn duy nhất, "chạy
lại" ở đây là **tính lại từ cùng bộ trace trong vài giây**, không phải mô phỏng lại.
`evaluate_gates` nhận `pooled_p99_latency_ms` như tham số, tính bởi `definitions.py`:
cổng so ngưỡng, Metrics Engine định nghĩa đại lượng (HĐ-15.3). Phân vị gộp **không** dựng
lại được từ `EpisodeMetricSet` — mỗi bản ghi chỉ mang phân vị của một episode.

G5 vẫn lấy max theo episode, có chủ ý: `memory_estimate_mb` được **đếm** chứ không **đo
thời gian**, không có nhiễu để sinh outlier.

## 5. Kết quả chạy thật

Lần chạy sạch, 30 episode ghép cặp mỗi candidate, 60/60 `success`:

```
HĐ-15.1(1) ✓ cả hai candidate chạy đúng cùng 30 episode context
HĐ-15.1(2) ✓ decision_utility tái lập tới 6 chữ số: 0.812618
HĐ-15.1(3) ✓ đủ sáu cổng cho 2 candidate, kèm N
HĐ-15.1(4) ✓ ΔU trung vị +0.027037, CI95 [+0.013734, +0.054217] trên 30 episode ghép cặp
HĐ-15.1(5) ✓ L_ref ≤ path_length + dung sai trên cả 60 episode thành công
HĐ-15.1(6) ✓ peak_search_nodes ≤ costmap_cells trên mọi episode

status:           CLEAR_RECOMMENDATION
recommended:      astar+dwa (ac187ee7a77e)
decision_utility: 0.812618
```

Artefact: `artifacts/runs/2026-08-10/057733f06738/{decision_card.json,manifest.json}`.

**Sáu tiêu chí xanh dưới cả hai luật G4** — bản `max` cũ (lần chạy sạch) và bản gộp mới
(tính lại cùng bộ trace). Kết quả giống hệt tới chữ số cuối, vì G4 chỉ là cổng, không
vào utility.

### 5.1. Bảng cổng

| Candidate | G4 p99 gộp | G5 | G2 |
|---|---:|---:|---|
| `astar+dwa` | **13,91 ms** / 100 | 13,5 MB | 0 va chạm, cận trên 10% |
| `rrtstar+dwa` | **59,30 ms** / 100 | 9,2 MB | 0 va chạm, cận trên 10% |

Chênh lệch latency **là thật, không phải nhiễu**: median p99 theo episode là 5,5 ms
(A\*) so với 12,0 ms (RRT\*), đều đặn qua cả 30 episode. Cùng một DWA, cùng tham số —
khác biệt đến từ **hình dạng đường**: RRT\* trả về lộ trình gấp khúc nhiều waypoint, và
chi phí chấm điểm path-distance của DWA tăng theo. Đây đúng là loại chi phí mà scope
`global_planner_selection` được lập ra để quy trách nhiệm.

Đáng chú ý: max p99 theo episode của RRT\* là **99,6 ms** — dưới ngưỡng 100 ms đúng
0,4 ms. Dưới luật cũ, cổng này quyết định bởi một phần nghìn giây may mắn.

### 5.2. Một phát hiện phải sửa trước Phase 5: **U_S ≡ 0**

`U_S = 0.0` cho **cả hai** candidate. Đây đúng một trong ba triệu chứng HĐ-15.2 liệt kê
("metric ra toàn 0").

Số liệu thật: `min_clearance` trung vị **0,041 m** (A\*) và **0,070 m** (RRT\*), trong
khi anchor là `bad = radius × 1.05 = 0,273` và `good = radius × 2.0 = 0,520`. Mọi episode
nằm dưới `bad` ⇒ `u = 0` ⇒ `U_S = 0` vĩnh viễn.

**Con số 4 cm là đúng, không phải lỗi.** Robot rộng 0,52 m, khe kệ hẹp nhất của kho là
0,68 m (§6.2 tài liệu mẹ) ⇒ mỗi bên còn 0,08 m. Đo đúng.

**Cái sai nằm ở đơn vị của anchor.** Chính comment trong `metric_anchors.yaml` viết:
*"two radii of room is good, a 5% margin over the radius is as bad as it gets before it
is a collision"* — "5% trên bán kính là sát va chạm" chỉ đúng nếu đại lượng là **khoảng
cách từ TÂM robot** tới vật cản. Nhưng `clearance_m` của HĐ-5, và hàm collision của
simulator, trả **khoảng cách từ MẶT robot** (đã trừ bán kính). Hai thang lệch nhau đúng
một bán kính.

Hệ quả: objective an toàn **chết** trên deployment tham chiếu — `w_S = 0,10` của utility
là hằng số 0 với mọi candidate, và không phân biệt được gì.

Sửa đúng: giữ metric (mặt robot là thứ collision layer tính và là nghĩa của "clearance"
trong trace), **sửa anchor sang thang mặt**: `bad = 0.0` (chạm = biên va chạm),
`good = ${robot.radius}` (một bán kính không gian trống). Với thang đó, khe hẹp nhất của
kho chấm 0,31 thay vì 0,00 — phân biệt được.

**Chưa sửa trong phase này**, vì đây là đổi thang chấm điểm (HĐ-8.2 nằm trong contract) và
không nằm trong 6 tiêu chí nghiệm thu. Nêu ra để dev quyết trước Phase 5.

## 6. Test

`tests/test_vertical_slice.py`: **14 test**. Test này chạy **cả chuỗi thật** — simulator,
Parquet, metrics, gates, objectives, bootstrap, card — trên một phòng trống 6×4 m với 6
episode mỗi candidate, hết khoảng 30 giây.

Vì sao không chạy trên kho tham chiếu: 60 episode × 20 s là không phải unit test. Cái giá
phải trả được ghi thẳng trong docstring — fixture này không bắt được lỗi chỉ xuất hiện
trên bản đồ nhiều vật cản, nên **bản chạy trên kho vẫn là một lệnh script và output của
nó được commit** dưới `artifacts/runs/`.

Fixture khai `collision_probability_max: 0.5` ⇒ `N_min = 6`, để G2 **qua một cách thành
thật** trên 6 episode thay vì bị tắt đi.

Bốn kiểm tra được test cả hai chiều (bắt được lỗi, và không báo động giả với khe hở dung
sai hợp lệ).

Thêm test cho hai thứ phase này sinh ra:

- `pooled_p99_latency_ms` (3 test): một episode chậm trong 200 **không** quyết định phán
  quyết (gộp ra 5 ms trong khi max theo episode ra 500 ms), nhưng candidate chậm thật thì
  vẫn bị bắt — robust không phải mù. Cộng test từ chối khi không có bước nào.
- `clearance_to_grid_within` (3 test): trùng khít với bản quét toàn bản đồ ở gần vật cản,
  và trả sàn cửa sổ ở xa.

Full suite: `pytest tests/ -q` → **1854 passed, 6 skipped** (10 phút 31). Baseline sau
Phase 3.5 là 1833 — thêm 21 test, **không vỡ test nào**, gồm cả 4 test
`test_contract_version` sau khi bump 3.0.0. Ruff sạch.

Hai test cũ được sửa **có chủ ý**, không phải sửa cho xanh:

- `test_obstacle_free_world_still_measures_the_walls` — probe giờ trả sàn cửa sổ (1,7 m)
  thay vì khoảng cách thật (4,7 m) ở trường xa. Ý định gốc của test (không được trả vô
  cực) vẫn giữ; thêm một test mới khẳng định trường gần vẫn chính xác.
- `test_worst_episode_decides_not_the_mean` → `test_the_gate_reads_the_pooled_percentile`
  + `test_one_slow_episode_no_longer_decides_the_verdict`. Test cũ khẳng định đúng cái
  luật vừa bị chứng minh là sai.

## 7. Về `.gitignore` — một quyết định cần dev xác nhận

D15 ignore cả `artifacts/`. Tôi mở một khe hẹp cho đúng hai file JSON vài kB:
`decision_card.json` và `manifest.json` của mỗi run. Lý do: HĐ-15.1 biến lát cắt thành
một **hồ sơ nghiệm thu**, HĐ-13 biến manifest thành thứ người khác dựng lại card từ đó —
một hồ sơ nghiệm thu không ai mở được thì không phải hồ sơ. Trace Parquet (megabyte mỗi
episode, đúng thứ D15 nhắm tới) vẫn bị ignore; đã kiểm bằng `git check-ignore`.

**Đây là chỗ tôi đổi một quyết định có sẵn của dự án, nên nêu rõ để dev bác nếu không đồng ý.**

## 8. Chưa làm — cố ý

- **Cache lưới inflate giữa các episode.** Cùng bản đồ, cùng bán kính robot, tính lại mỗi
  episode mất ~6 s. Đây là tối ưu thuần, không đụng phương pháp luận, để sau.
- **`--verify-rerun` mô phỏng lại.** Tiêu chí 2 hiện chạy lại **tầng quyết định** trên
  cùng bộ trace. Tính tất định của simulator là một khẳng định khác và đã được cố định
  bởi seed của episode.
- **Pareto / sensitivity / neighborhood** — HĐ-15.1 ghi rõ "chưa cần"; Phase 5.

## 9. Trạng thái

| Phase | Trạng thái |
|---|---|
| 1 Schema gốc | ✅ |
| 2 Đường dữ liệu | ✅ |
| 3 Decision core | ✅ |
| **4 Lát cắt dọc** | ✅ — 6/6 tiêu chí HĐ-15.1 xanh trên kho thật |
| 5 Engine đầy đủ | chưa |

**Việc phải quyết trước khi mở Phase 5:** thang anchor của `min_clearance` (mục 5.2).
`U_S` hiện là hằng số 0 trên deployment tham chiếu, nên objective an toàn không đóng góp
gì vào quyết định.

Hai nghĩa vụ đang treo, không phải việc của phase này nhưng cần nhắc:

1. §16 ghi bản 2.0.0 là MAJOR nên đòi **chạy lại lát cắt dọc** — lần chạy này là lần đầu
   tiên nghĩa vụ đó có thể thực hiện được, và nó đã thực hiện.
2. Contract **vẫn chưa đủ chữ ký**: cần Dev A và Dev C (mục 0 đòi ≥2 approve). Bản hiện
   tại là 2.2.1, đi khá xa so với 2.0.0 mà mọi người được yêu cầu đọc.

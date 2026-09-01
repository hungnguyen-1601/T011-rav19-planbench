# Báo cáo — F0 đưa sáu chỗ lệch về quỹ đạo, F1 đo được một stack

> **Ngày:** 2026-08-11 · **Nhánh:** `plannerselector_p2`
> **Plan nguồn:** `plans/2026-08-11/nen-tang-cong-bang-truoc-thuat-toan.md`, phase **F0**, **F1**, **F2**
> **Contract:** `6.0.0` → **`6.1.0`** (MINOR)
> **Kết quả quan trọng nhất:** hai lỗ hổng chưa ai gọi tên, cả hai tìm được bằng cách *làm* chứ
> không bằng cách đọc — G4 không đếm tần suất gọi controller, và `L_ref` dôi 2,41% so với tối ưu
> thật. Cái thứ hai làm trượt đúng tiêu chí nghiệm thu mà F1 vừa dựng lên.

---

## 1. F0.1 — ngưỡng G4, và cái lỗ hổng nằm bên dưới nó

### 1.1. Nhượng bộ 10 Hz là hoá thạch của hai lỗi đã sửa xong

Cả hai profile khai `control_period: 0.1` với lý do ghi trong file: *"DWA Python không tính nổi
một bước điều khiển trong 50 ms"*. Vì `RobotConfig.t_cycle_ms` **chính là** ngưỡng G4, câu đó có
nghĩa là ngưỡng cổng thời gian thực bị nới gấp đôi vì candidate không qua nổi nó.

Kiểm trước khi sửa, và kết quả làm việc này rẻ hơn hẳn dự kiến:

| p99 gộp đo được (run `b60dbd94882d`, ghim 2 nhân) | Ngưỡng nếu 20 Hz |
|---|---:|
| `astar+dwa` **10,81 ms** | 50 ms |
| `rrtstar+dwa` **16,10 ms** | 50 ms |

Lý do viết trong profile đã hết đúng từ lâu mà không ai để ý: contract 3.0.0 đổi G4 sang **p99
gộp** (bỏ max-theo-episode), và Phase 5.1 thêm **ghim nhân**. Sau hai thứ đó thì cả hai candidate
thừa sức dưới 50 ms.

Và nới nó **không mua được gì**: `simulation_dt = min(MAX_SIMULATION_DT, control_period)` với
`MAX = 0,05`, nên 10 Hz và 20 Hz tích phân thế giới y hệt nhau. Không có động lực nào để nới lại
— `test_relaxing_the_gate_does_not_buy_a_cheaper_simulation` khoá điều đó, vì nếu động lực đó
tồn tại thì áp lực nới sẽ quay lại.

### 1.2. Cái tìm được khi làm: **G4 đo chi phí một lần gọi, không đếm số lần gọi**

Có **hai** thứ khác nhau cùng tên `control_period`, và chưa có gì so chúng với nhau:

| | Là gì | Ai đọc |
|---|---|---|
| `profile.robot.control_period` | **yêu cầu** của hiện trường | ngưỡng G4, chặn trên `simulation_dt` |
| `control_period` của local controller | **nhịp candidate thực sự chạy** | `nav_stack` giữ lệnh cũ giữa hai tick |

`LOCAL_CONTROLLER_PARAMS` khai `0.1`. Deployment khai `0.1`. Hai con số bằng nhau nên không ai
thấy chúng là hai thứ.

Hạ deployment xuống 10 Hz "hoạt động" chính là **nhờ** lỗ hổng này: G4 đo chi phí *một* lần gọi
controller và không bao giờ hỏi lần gọi xảy ra bao lâu một lần. Một candidate đóng vòng ở 10 Hz
trên deployment đòi 20 Hz **qua cổng** trong khi giữ mỗi lệnh suốt hai chu kỳ — cổng thấy một
lần gọi *rẻ*, không thấy một lần gọi *trễ*.

`validate_control_rate` đóng lại, fail-at-startup theo đúng hình dạng HĐ-1.4. Ghi vào HĐ-7.2.

**Hệ quả phải nói rõ:** DWA giờ chạy 0,05 s thay vì 0,1 s ⇒ gọi gấp đôi mỗi episode ⇒
`candidate_id` đổi ⇒ **toàn bộ trace kho cũ mồ côi**. Giữ nguyên làm bằng chứng lịch sử, chạy
lại là việc của F4.3.

**Một sai lệch so với plan, có lý do:** plan viết bump `warehouse_a_v2` → `v3`. Không làm, vì
`v2` chưa từng được commit và **không artifact nào mang id đó** — mọi manifest đang có đều ghi
`warehouse_a_v1`. Gộp thay đổi vào chính delta v1→v2 sạch hơn ba file.

## 2. F0.2 — DWA `7×15` thành candidate, không còn là hằng số trong script

`LOCAL_CONTROLLER_CONFIGS` với hai mục có tên: `dwa_coarse` (7×15) và `dwa_default` (20×40), hai
`candidate_id` khác nhau. Câu hỏi treo từ lượt kiểm — *"A\* kẹt góc lồi là tính chất của stack
hay của lấy mẫu thô?"* — giờ trả lời được bằng dữ liệu ở F4.2, không bằng suy đoán.

Kèm một chi tiết đúng đắn: so `dwa_coarse` với `dwa_default` **cùng** global planner không phải
`global_planner_selection`; `validate_experiment_scope` từ chối, và đó là hành vi mong muốn.

## 3. F0.3 và F0.4 — hai chỗ nới còn lại

**`goal_tolerance_rad`** thành bảo lưu của HĐ-6, và `< π` bị **từ chối lúc nạp**. Lý do chọn từ
chối thay vì ghi chú: cả hai profile đều đã mang một đoạn văn giải thích, và một đoạn văn chỉ
bảo vệ được profile mà tác giả của nó đã đọc.

Bán kính lan của thay đổi này lớn hơn dự kiến — `tests/task_profile_fakes.py` khai `0.35`, nên
gần như mọi test dựng profile đều đỏ. Sửa fixture về π, và một test thật sự cần dung sai hẹp
(`test_heading_outside_tolerance_is_not_the_goal`) được viết lại dựng `TaskConstraints` bằng
`model_construct`. Nhánh kiểm hướng trong `definitions.py` **giữ nguyên**: bảo lưu nói hôm nay
không profile hợp lệ nào chạm tới nhánh đó, không nói nhánh đó sai.

**`collision_probability_max`** của kho về **1%** (N_min = 300). Điểm quan trọng không phải con
số mà là **cơ chế đã có sẵn và chạy đúng**: chạy ít hơn N_min vẫn được, và G2 báo `fail` kèm
*"chỉ N lần chạy phân biệt, dưới N_min = 300"*. Phép đo y hệt nhau ở cả hai cách; khác biệt là
hệ **tự khai chưa đạt** thay vì hạ chuẩn xuống cho khớp chính mình.

## 4. F0.5 — máy đo được ghi lại, thay vì được tin

`benchmark_host` cũ hardcode `cores_allocated=1, threads=1` trong khi chạy trên 20 nhân — tức
manifest mô tả một lần chạy chưa từng xảy ra. `packages/benchmark/.../hostinfo.py` đo thật
(`sched_getaffinity` trên Linux, `psutil` trên Windows), thêm `cpu_affinity` và `logical_cores`
vào `BenchmarkHost` và manifest schema, và in cảnh báo khi run giữ toàn bộ máy.

`is_pinned` trả **`None`** khi manifest không ghi, khác hẳn `False`. Một khoảng trống trong hồ
sơ không được biến thành một khẳng định về lần chạy.

Lần chạy F1 hôm nay in đúng cảnh báo đó: *"Đo trên toàn bộ 20 nhân, không ghim"*.

## 5. F0.6 và F2 — luật, không phải ghi chú

- **HĐ-4.1** (mới): lưới replan là đặc quyền thông tin đã biết; phải gỡ trước khi chấm candidate
  `monolithic`, và lời giải hợp lệ là replan từ `Observation` chứ **không** phải cấp ground truth
  cho cả hai bên. Cấp cho cả hai chỉ đổi một phép so lệch thành hai phép đo sai.
- **HĐ-15.1 tiêu chí 7** (mới): bộ kiểm công bằng xanh là **điều kiện cần để công bố bất kỳ phép
  so nào**.
- **HĐ-15.3** thêm câu hỏi bắt buộc: *"con số này đến từ hiện trường, hay đến từ thứ máy/code của
  tôi chạy nổi?"* Vế sau thuộc mục bảo lưu, không thuộc file profile.
- **Test chữ ký** `TestGatesAreNotWidenedToFitTheImplementation` — sáu test khoá cả bốn chỗ vừa
  sửa, để chúng không trôi lại.

**Đính chính vào §18:** mục ③ trong "ba sửa chữa" của 6.0.0 ghi rằng deployment tham chiếu được
thêm `pallet_truck`. Thay đổi đó đã bị hoàn nguyên và không còn trong repo — nó do kết quả dẫn
dắt. Hai sửa chữa còn lại của 6.0.0 đứng nguyên.

---

## 6. F1 — và một lỗi thứ hai, do chính tiêu chí nghiệm thu mới bắt được

### 6.1. Vì sao là artifact khác loại, không phải card nhỏ hơn

`scripts/measure.py` dừng ở phép **đo**: profile + candidate → episode → trace → metric HĐ-6 →
G1–G6 → bốn objective → `measurement_report.json`. Không ΔU, không CI, không nhãn, không
`alternative` — với một candidate thì không cái nào trong số đó có nghĩa.

Ép một tấm card ra từ một candidate sẽ điền đủ mọi trường, trông hoàn toàn bình thường, và tuyên
bố một điều dữ liệu không đỡ được. Đó **đúng** là thứ lần chạy 100 episode đã sinh ra. Nên báo
cáo mang sẵn một câu cố định nói nó không phải phép so, và `test_no_verdict_vocabulary_anywhere`
quét toàn bộ JSON tìm từ vựng của một khuyến nghị.

### 6.2. `L_ref` dôi 2,41% — bắt được ngay lần chạy đầu

Lần chạy F1 đầu tiên trượt tiêu chí nghiệm thu:

```
L_ref 20.768 m exceeds the driven path 20.304 m by more than the goal tolerance 0.200 m
```

Robot đi **ngắn hơn** đường "ngắn nhất". Truy tới cùng bằng số, không bằng đoán — map hall có
tối ưu tính được bằng tay (hai chân quanh một khối chữ nhật):

| | |
|---|---|
| Tối ưu giải tích cho robot điểm | **20,2788 m** |
| `L_ref` trả về | **20,7679 m** — dôi **0,489 m (+2,41%)** |
| Robot đi thật + khoảng cách còn lại tới goal | 20,3042 + 0,1972 = **20,5014 m** |

Robot nằm **giữa hai số**: trên tối ưu robot-điểm (đúng — nó có bán kính), dưới `L_ref`. Nên sai
là ở `L_ref`.

**Nguyên nhân.** `simplify_path` chỉ chọn được trong số các đỉnh nó được đưa, mà các đỉnh đó là
**tâm ô**. Vòng qua một góc lồi, đường căng chạm đúng vào góc, còn tâm ô gần nhất nằm lệch ra
tới nửa ô. Tệ hơn, luật greedy giữ đỉnh **xa nhất còn nhìn thấy**, nên ở phía bên kia vật cản nó
nhảy qua luôn cái góc mà sợi dây cần bẻ. Docstring của chính module đã tự khai còn "residual
approximation" — ở hall, residual đó là 2,4%.

**Vì sao nó nguy hiểm hơn là chỉ sai số.** `path_efficiency = L_ref / path_length` vượt 1 rồi bị
clip về 1,0: O3 chấm một lần chạy tốt thành hoàn hảo và mất khả năng phân biệt ở đoạn trên. Mọi
test cũ vẫn xanh, vì tất cả chúng kiểm `L_ref` bằng **chặn** (dài hơn đường thẳng, ngắn hơn
đường đi thật) chứ không bằng một tối ưu biết trước.

### 6.3. Sửa: kéo căng đa tỉ lệ, và vì sao không phải cách hiển nhiên

Kéo mỗi đỉnh về phía dây cung của **hai hàng xóm kề** là một phép khuếch tán — thông tin bò một
đỉnh mỗi vòng. Đo thật trên hall (401 đỉnh):

| Số vòng | Sai số |
|---:|---:|
| 10 | +2,223% |
| 50 | +1,832% |
| 150 | +1,353% (14,3 s) |

Không dùng được. Nên phép kéo chạy ở **mọi tỉ lệ** — hàng xóm cách `n/2, n/4, …, 1`. Tỉ lệ thô
dịch cả cung một lúc và đặt đường vào sát các góc; tỉ lệ mịn dọn phần còn lại:

| | `L_ref` | Sai số | Thời gian |
|---|---:|---:|---:|
| hall, trước | 20,7679 | +2,41% | — |
| hall, sau (2 lượt) | **20,2794** | **+0,0027%** | 11,6 s |
| kho, trước | 45,4201 | — | — |
| kho, sau | **45,4201** | không đổi | 50,1 s |

Tuyến kho **vốn đã căng** — nó đi trong hành lang kệ, không vòng góc lồi tự do. Đó là lý do lỗi
này sống sót qua cả Phase 4 lẫn Phase 5.1: map duy nhất từng chạy không bộc lộ nó.

**Tính đúng đắn không phụ thuộc vào việc phép kéo có hội tụ hay không.** Cái được đo là output
của `simplify_path`, và mọi đoạn nó trả ra đều đã kiểm line-of-sight trên lưới. Phép kéo chỉ
*dẫn hướng* các đỉnh; nó không thể sinh ra một độ dài ngắn hơn một đường tự do có thật, dù hành
xử tệ tới đâu. `test_it_never_undercuts_the_optimum` nói điều đó ra.

Kết quả tất định (`_TAUT_BISECTIONS` là số vòng cố định, không phải vòng lặp tới ngưỡng — HĐ-15.1(2)
đòi cùng sáu chữ số mỗi lần chạy, và "lặp tới khi không đổi nữa" trên số thực là chỗ điều đó âm
thầm hết đúng). Cache theo (map, start, goal) nên 50 s của kho trả một lần cho cả run 300 episode.

Đây **không** phải đổi ngữ nghĩa HĐ-6: định nghĩa vẫn là "đường ngắn nhất". Tính nó chính xác
hơn là sửa bug. Và chiều của nó an toàn: `L_ref` nhỏ đi ⇒ `path_efficiency` nhỏ đi ⇒ kết luận
**nghiêm hơn**, không tâng bốc ai.

### 6.4. Lần chạy F1

```
profile open_hall_v1: 480×320 cells, 30 contexts (N_min = 30 at 10% accepted collision risk)
candidate: rrtstar+dwa · dwa_coarse · db26440f6052
⚠ Đo trên toàn bộ 20 nhân, không ghim

  ✓ L_ref ≤ path_length + tolerance on all 30 successful episodes
  ✓ decision_utility reproducible to 6 dp (0.845397)
  ✓ gate table carries all six gates
  ✓ peak_search_nodes ≤ costmap_cells on every episode

episodes:       30 run, 30 distinct
success rate:   100%
pooled p99:     18.76 ms (G4 threshold 50.0)
  G1..G6: pass
utility:        0.845397
```

**Một dự đoán của plan sai, và sai theo hướng tốt.** Plan viết rằng G2 sẽ từ chối vì hall không
có traffic động nên mọi seed cho cùng một episode. Điều đó đúng với stack **tất định**; RRT\* là
planner ngẫu nhiên, nên 30 episode **phân biệt** thật và G2 qua hợp lệ. Nguồn biến thiên ở đây
là bản thân planner chứ không phải hiện trường — một tính chất phải nhớ khi F4.1 đưa `astar+dwa`
vào cùng deployment này: A\* sẽ cho `n_distinct` thấp và G2 sẽ từ chối, và **đó là hệ chạy đúng**.

`control_period` 20 Hz cũng đã được kiểm trên đường chạy thật: p99 gộp 18,76 ms trên ngưỡng
50 ms, kể cả khi **không ghim nhân**.

---

## 7. Một test đỏ, và nó đỏ vì một lý do đáng ghi

Lượt full suite đầu tiên trượt `test_metrics_recompute_from_the_manifest_and_traces_alone`:
`rebuilt == 0`, cần 6.

Test đó tìm trace bằng `Path(tmp_path_factory.getbasetemp()).rglob("traces")` — tức **"thư mục
`traces` đầu tiên mà bất kỳ module test nào tạo ra"**. Đúng chừng nào chỉ có một module tạo.
`test_measure.py` đứng trước theo thứ tự chữ cái, tạo `measure0/traces`, nên test rebuild của
lát cắt đi tìm episode của chính nó trong trace root của module khác.

Không phải code sản phẩm hỏng, và cũng không phải "test hỏng vì có file mới": đó là một test
vốn đã khẳng định sai từ trước — nó nói về *một thư mục nào đó trên đĩa* chứ không về run của
chính nó — và chưa ai chạm vào nên chưa lộ. Sửa bằng fixture `slice_workspace` /
`measure_workspace`; `getbasetemp` không còn xuất hiện trong cả hai file.

## 8. Trạng thái

Full suite: **2084 passed, 6 skipped** (10 phút 05). Baseline trước lượt này 2037 — thêm 47
test, không vỡ test nào. Ruff sạch. Contract `6.1.0`.

| Phase | Trạng thái |
|---|---|
| F0.1 ngưỡng G4 + nhịp controller | ✅ |
| F0.2 hai cấu hình DWA | ✅ |
| F0.3 bảo lưu hướng | ✅ |
| F0.4 rủi ro khai báo | ✅ |
| F0.5 affinity trong manifest | ✅ |
| F0.6 luật replan | ✅ (ghi luật; hiện thực khi có `monolithic`) |
| F1 MVP một stack | ✅ 4/4 tiêu chí, 6 cổng xanh |
| F2 công bằng thành luật | ✅ tiêu chí 7 + câu hỏi DoD + test chữ ký |
| F3 nhiễu cảm biến theo seed | ⏳ chưa bắt đầu |
| F4 đưa thuật toán vào dần | ⏳ chưa bắt đầu |

**Việc chưa làm và phải nhớ:**

- **Trace kho cũ đã mồ côi** (`candidate_id` đổi vì DWA chạy 20 Hz). Giữ làm bằng chứng lịch sử.
  Chạy lại là F4.3, ở mức 1% tức 300 episode ≈ 3 giờ, và **nên ghim nhân**.
- **Ghim nhân vẫn là quy trình vận hành**, chưa được cưỡng chế bằng code. Giờ ít nhất nó được
  *ghi lại* và cảnh báo.
- `instance_difficulty` và `robustness_margin` vẫn như Phase 5.1 để lại.

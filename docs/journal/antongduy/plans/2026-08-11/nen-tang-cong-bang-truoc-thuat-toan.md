# Kế hoạch: nền tảng đo công bằng trước, thuật toán sau

> **Ngày lập:** 2026-08-11 · **Người lập:** An (cùng Claude) · **Trạng thái:** chờ approve
> **Quan hệ với plan cũ:** **thay thế thứ tự ưu tiên** của
> `plans/2026-08-08/backlog-uu-tien-planner-selector.md` từ Phase 5.1 trở đi. Phase 1–4, 5.2,
> 5.3, 6.1 của bản cũ **giữ nguyên, đã xong, không mở lại**. Phase 6.2–6.3 và 7.x của bản cũ
> vẫn đúng và được kéo xuống cuối bản này.
> **Nguồn:** `notes/2026-08-11/tongduyan_xac-minh-lech-huong-muc-tieu.md` (sáu chỗ lệch),
> `notes/2026-08-11/tongduyan_kiem-toan-tinh-cong-bang-simulator.md` (sáu bất biến),
> `plans/2026-08-11/nhieu-cam-bien-theo-seed.md` (hoãn, được kéo vào đây làm F3).
> **Ba quyết định dev đã chốt trước khi viết bản này:**
> ① MVP = `open_hall_v1` + `rrtstar+dwa`. ② G4: **tách ngưỡng cổng khỏi `control_period`**.
> ③ DWA `7×15` và `20×40` là **hai candidate riêng**, nền tảng chấm cả hai.

---

## 0. Vì sao viết lại thứ tự, chứ không viết lại nội dung

Bản backlog 08-08 xếp hạng theo **độ lan tỏa** (fan-out): schema trước, engine sau, UI cuối.
Cách xếp đó đúng cho câu hỏi *"sửa cái gì thì phải sửa lan ra ít nhất"*, và nó đã đưa dự án đi
được rất xa. Nhưng nó không có tiêu chí nào cho câu hỏi *"kết quả đo ra có đáng tin không"*, và
đó chính là lỗ hổng đã để bốn thay đổi do-kết-quả-dẫn-dắt lọt qua toàn bộ năm tiêu chí nghiệm
thu của Phase 4.

Bản này đổi tiêu chí xếp hạng thành **thứ tự phụ thuộc về tính hợp lệ**:

```
một phép ĐO hợp lệ  ──►  một phép SO hợp lệ  ──►  một SẢN PHẨM
     (F0, F1, F2, F3)          (F4)                  (F5)
```

Đọc theo chiều ngược lại thì rõ hơn: một Decision Card đẹp dựng trên một phép so lệch là **tệ
hơn** không có card, vì nó chuyển một sai lầm thành một khuyến nghị có chữ ký. Một phép so
giữa hai candidate đo trong một thế giới đã bị nới cho vừa code cũng vậy.

Nên nguyên tắc của bản này, và nó là thứ duy nhất cần nhớ khi có tranh chấp thứ tự:

> **Không công bố bất kỳ phép so nào trước khi phép đo tự đứng vững được với đúng một
> thuật toán.**

Và hệ quả trực tiếp về MVP, theo đúng chỉ đạo của dev: **MVP không phải là hai thuật toán so
nhau thành công.** MVP là *một* stack chạy hết một bộ episode trên một map có sẵn và trả về
đủ bộ thông số quan trọng, kèm một bảng cổng nói thật về chất lượng của chính bộ số đó.

---

## 1. Phase F0 — Đưa sáu chỗ lệch về quỹ đạo

Đây là điều kiện cần của mọi thứ sau. Sáu việc, xếp theo mức nghiêm trọng đã kiểm ở note
`tongduyan_xac-minh-lech-huong-muc-tieu.md`.

### F0.1 — Ngưỡng G4 thôi phụ thuộc `control_period` *(ưu tiên cao nhất)*

**Tình trạng:** `RobotConfig.t_cycle_ms = control_period × 1000` là thẳng luôn `threshold_ms`
của `_gate_4`. Hai profile khai `control_period: 0.1` với lý do "DWA Python không chạy nổi
50 ms" ⇒ ngưỡng cổng thời gian thực bị nới từ 50 ms lên 100 ms **vì implementation chậm**.

**Phát hiện làm việc này rẻ hơn nhiều so với dự kiến — phải kiểm trước khi làm bất cứ gì:**

| | đo được (run `b60dbd94882d`, ghim 2 nhân) | ngưỡng nếu 20 Hz |
|---|---:|---:|
| `astar+dwa` p99 gộp | **10,81 ms** | 50 ms |
| `rrtstar+dwa` p99 gộp | **16,10 ms** | 50 ms |

Cả hai **thừa sức qua ngưỡng 50 ms**. Lời giải thích trong profile được viết từ thời G4 lấy
**max theo episode** dưới CPU bị tranh chấp (contract 3.0.0 đã đổi sang **p99 gộp**, và Phase
5.1 thêm ghim nhân). Nhượng bộ 10 Hz **nhiều khả năng đã lỗi thời** — nó là hoá thạch của hai
lỗi đã được sửa từ lâu.

Thêm một điều khiến việc này gần như miễn phí, kiểm trong `episode.py:105`:

```python
simulation_dt = min(MAX_SIMULATION_DT, profile.robot.control_period)   # MAX = 0.05
```

Với `control_period` 0,1 hay 0,05 thì `simulation_dt` **đều bằng 0,05**. Hạ về 20 Hz **không**
làm mô phỏng chậm đi một giây nào, và không đổi độ trung thực vật lý. Docstring của chính hàm
đó đã ghi rõ hai thứ này là hai thứ khác nhau và "đã có lúc bị lẫn ở đây".

**Các bước, đúng thứ tự:**

1. Sửa `control_period: 0.1 → 0.05` ở **cả hai** profile, xoá đoạn comment biện minh.
2. **Không mô phỏng lại.** HĐ-5 đặt trace là nguồn sự thật duy nhất, latency đã nằm trong
   trace — chấm lại bộ `artifacts/traces` hiện có mất vài giây. Dùng `--reuse-traces`.
   ⚠ `control_period` **không** nằm trong payload băm của `episode_context_id` (HĐ-3.1), nên
   trace cũ dùng lại được — nhưng chính vì thế phải **đổi `id` profile lên `warehouse_a_v3`**
   theo đúng bài học đã ghi ở đầu file v2, nếu không thì không phân biệt được hai lần chấm.
3. Đọc kết quả G4:
   - **Cả hai qua** (kỳ vọng): xong. Không cần trường mới, không cần bump contract về ngữ
     nghĩa cổng. Chỗ lệch nặng nhất biến mất với chi phí gần bằng không, và thu được một câu
     đúng để in lên card: *"p99 gộp 16,1 ms trên ngân sách 50 ms của hiện trường."*
   - **Có candidate trượt:** thi hành phương án dev đã chọn — thêm
     `host_screening_budget_ms` vào `TaskProfile`, tách hẳn khỏi `control_period`. G4 in **cả
     hai**: ngưỡng hiện trường (điều kiện cần thật) và ngân sách sàng lọc trên host (thứ vòng
     P1 thực sự đo được). Khớp sẵn với kiến trúc hai pha P1/P2 mà HĐ-7.2 đã có. Bump contract
     **MAJOR** (đổi ngữ nghĩa cổng) + chạy lại lát cắt theo mục 0 CONTRACTS.
4. Test khoá chiều phụ thuộc: một test khẳng định ngưỡng G4 **không** đọc từ trường điều khiển
   bước mô phỏng, để không ai nối lại hai thứ này lần nữa.

**Ước lượng:** 1 giờ nếu nhánh (3a); +3 giờ nếu nhánh (3b).

### F0.2 — DWA `7×15` và `20×40` thành hai candidate

**Tình trạng:** `LOCAL_CONTROLLER_PARAMS` trong `scripts/vertical_slice.py` khai `7×15` với lý
do "50 episode của mặc định là hàng giờ đồng hồ". DWA **là** một phần của candidate (HĐ-1), nên
đây là cấu hình thứ-đang-được-đo chọn theo ngân sách đồng hồ. Nghi vấn cụ thể: phát hiện *"A\*
kẹt góc lồi ở clearance 0,30 m"* có thể là tính chất của **lấy mẫu thô**, chưa ai đo `20×40` ở
đúng góc đó.

**Việc:**

1. Gỡ `LOCAL_CONTROLLER_PARAMS` khỏi vai "hằng số của script", đưa thành **bảng cấu hình local
   controller** có tên: `dwa_coarse` (7×15) và `dwa_default` (20×40).
2. `candidate_from_stack(..., params=..., local_version=...)` đã đủ để sinh hai `candidate_id`
   khác nhau — không cần schema mới. Kiểm `validate_experiment_scope`: so `astar+dwa_coarse`
   với `rrtstar+dwa_coarse` vẫn là `global_planner_selection`; so `dwa_coarse` với
   `dwa_default` **cùng** global planner là một scope khác (`local_controller_selection`),
   phải khai đúng nếu không validator sẽ chặn — đó là hành vi mong muốn.
3. Ghi vào manifest: cấu hình local nào đang chạy, để hai bộ kết quả không bị đọc lẫn.

**Không** làm trong F0: chạy đủ ma trận 2 global × 2 local. Đó là F4.

**Ước lượng:** 2 giờ.

### F0.3 — `goal_tolerance_rad` chuyển thành bảo lưu của nền tảng

**Tình trạng:** cả hai profile khai `3.1416`, tức tắt hẳn điều kiện hướng của HĐ-6, và lời giải
thích ("simulator không có bộ điều khiển ổn định hướng cuối") nằm trong comment của một file
profile — tức một giới hạn của **nền tảng** đang giả trang thành một lựa chọn của **khách
hàng**.

**Việc:** viết bảo lưu vào CONTRACTS đúng khuôn bảo lưu sim-only ở HĐ-7.2:

> *Nền tảng chưa có bộ điều khiển ổn định hướng cuối. Mọi nhiệm vụ có ràng buộc hướng nằm
> ngoài năng lực đánh giá của dự án này; profile khai `goal_tolerance_rad < π` phải bị từ chối
> **lúc nạp**, kèm thông điệp chỉ vào bảo lưu này. Khi có bộ điều khiển thì gỡ bảo lưu và tăng
> `contracts_version` MINOR.*

Điểm mấu chốt: **từ chối lúc nạp**, không phải ghi chú. Bài học đã ghi vào contract ở Phase
5.1 — *"một ghi chú 'nhớ làm ở phase sau' không phải một biện pháp bảo vệ, chỉ code mới là"*.
Hôm nay profile khai π vì người viết biết; một profile viết sau bởi người không biết sẽ khai
0,1 rad và mọi candidate trượt G1 vì lý do không liên quan gì tới planner.

Bump contract MINOR (thêm bảo lưu, không đổi ngữ nghĩa metric).

**Ước lượng:** 1 giờ.

### F0.4 — Rủi ro khai báo tách khỏi ngân sách máy

**Tình trạng:** `warehouse_a_v2.yaml` khai `collision_probability_max: 0.03` với lý do viết
thẳng trong file: *"vì run phải chia sẻ máy"*. Mũi tên bị đảo — HĐ-7.1 định nghĩa chuỗi là
`rủi ro hiện trường ⇒ N_min ⇒ số giờ`, không phải ngược lại.

**Việc — và cách sửa quan trọng hơn con số:**

1. Profile khai rủi ro **theo hiện trường**: `0.01` cho kho hàng, như tài liệu mẹ §6.2.
2. Số episode thực chạy vẫn là tuỳ chọn CLI (`--episodes`), đã có sẵn.
3. **G2 tự khai thiếu thay vì hệ hạ chuẩn.** Cơ chế này đã tồn tại và đã chạy đúng: khi
   `n_distinct < N_min`, `_gate_2` trả `fail` kèm note *"chỉ N lần chạy phân biệt, dưới
   N_min = …; cận trên … còn lỏng hơn mức rủi ro đã khai"*. Đó chính xác là hành vi mong muốn —
   chạy 100 episode dưới mức khai 1% cho ra **"chưa đủ để tuyên bố, cận trên thực tế 3%"**,
   không phải "qua cổng ở mức 3%".

Khác biệt giữa hai cách viết là toàn bộ vấn đề: cách cũ **hạ tiêu chuẩn cho vừa ngân sách**,
cách mới **giữ tiêu chuẩn và khai rằng chưa đạt**. Số episode chạy y hệt nhau; điều hệ dám
tuyên bố thì khác hẳn.

4. Giữ nguyên bảng thang bậc chi phí trong comment — nó hữu ích, chỉ đổi vai từ *lý do chọn
   ngưỡng* thành *ghi chú vận hành*.

**Ước lượng:** 1 giờ (chủ yếu là test cho chuỗi note mới).

### F0.5 — Ghim nhân và thứ tự xen kẽ vào manifest

**Tình trạng:** G4 đọc latency theo đồng hồ tường. Đo được ở Phase 5.1: cùng `rrtstar+dwa`,
**59,30 ms** không ghim nhân so với **16,10 ms** có ghim — 3,7 lần, và chênh lệch đó **đã từng**
bị đọc thành tính chất của candidate (contract 3.0.0 loại nhầm A\*). Manifest HĐ-13 có
`benchmark_host.cores_allocated` nhưng affinity thật không được ghi, và không có cảnh báo nào
khi hai candidate không chạy xen kẽ.

**Việc:**

1. Ghi affinity thật vào manifest lúc chạy (`psutil.Process().cpu_affinity()`, đã có `psutil`
   trong deps), cùng số nhân logic của máy.
2. Cảnh báo trên card khi số nhân được cấp bằng toàn bộ máy — tức nhiều khả năng không ghim.
3. Kiểm thứ tự xen kẽ **từ dữ liệu**, không từ ý định: manifest ghi thứ tự (context, candidate)
   thực tế đã chạy; một test khẳng định chuỗi đó xen kẽ. `iter_run_plan` đã cho thứ tự đúng và
   đã có test khoá — cái còn thiếu là **bằng chứng trong hồ sơ của một run cụ thể**.

**Ước lượng:** 2 giờ.

### F0.6 — Bất cân xứng replan: ghi vào hợp đồng, chưa hiện thực

**Tình trạng:** `nav_stack.py:166` — `_planning_grid(map_data, scenario, engine.dynamic_obstacles_now())`.
Global planner của stack modular thấy vật cản động **thật sự ở đâu**; một policy end-to-end chỉ
thấy `Observation`. Hôm nay vô hại (chỉ modular chạy được) và đã có
`test_only_modular_stacks_can_run_today` làm chốt chặn.

**Việc trong F0 là ghi luật, không phải sửa code:** viết vào HĐ-4 rằng lưới replan là một
**đặc quyền thông tin đã biết**, rằng nó phải được giải quyết trước khi adapter monolithic chạy,
và rằng lời giải phải là *replan từ `Observation`* chứ không phải *cấp ground truth cho cả hai*.

Vì sao không hiện thực bây giờ: nó chỉ cắn khi có candidate `monolithic`, mà cái đó không nằm
trong F1–F4. Làm sớm là trả giá cho một vấn đề chưa tồn tại. Nhưng ghi vào hợp đồng thì rẻ, và
chốt chặn + điều khoản mạnh hơn chốt chặn một mình.

**Ước lượng:** 0,5 giờ.

**DoD Phase F0:** sáu mục xong; suite đầy đủ xanh; bộ kiểm công bằng (53 test) xanh; card chấm
lại từ trace cũ **không** đổi khuyến nghị vì lý do nào khác ngoài ngưỡng G4 — và nếu có đổi thì
báo cáo nói thẳng nó đổi vì cái gì.

---

## 2. Phase F1 — MVP: một stack, một map, đo được

**Mục tiêu nguyên văn theo chỉ đạo dev:** *chạy được một thuật toán thành công trên một map và
một scenario có sẵn, trả về được các thông số quan trọng.* Chưa so, chưa card, chưa UI.

**Cấu hình chốt:** `profiles/open_hall_v1.yaml` + `rrtstar+dwa` (đã đo 8/8 success ở đó).

### 2.1. Vì sao là `open_hall`, không phải kho

`open_hall` là deployment **duy nhất** trong repo có tính đối xứng được **test khẳng định**
chứ được tin: gương quanh cả đường nhiệm vụ `y = 8,0` lẫn trục `x = 12,0`, 6,20 m lối trống mỗi
bên cho robot rộng 0,52 m, sinh lại được bằng `scripts/make_fairness_map.py`. Bản vẽ tay đầu
tiên lệch 5 cm (`int(15.7/0.05)` cho 313 chứ không phải 314) và **phép kiểm bắt được** — đó là
lý do tin được bản hiện tại.

MVP đứng trên map đó nghĩa là: khi con số ra khác kỳ vọng, "map thiên vị" đã bị loại khỏi danh
sách nghi phạm trước khi bắt đầu.

### 2.2. Artifact mới: Measurement Report, **không** phải Decision Card

`scripts/vertical_slice.py` hiện hardcode hai candidate và gọi thẳng vào `build_decision_card`.
Không được ép nó chạy với một candidate.

**Lý do là điểm chính của cả phase này:** Decision Card là artifact của một phép **so** — ΔU,
CI ghép cặp, nhãn CLEAR/NEAR_EQUIVALENT, `alternative` từ Pareto frontier đều vô nghĩa với một
candidate. Ép ra một tấm card cho N=1 là sản xuất đúng loại tài liệu mà Phase 5.1 vừa bị: mọi
trường đều điền đủ, không có gì trông sai, và nó tuyên bố một điều dữ liệu không đỡ được.

Nên MVP sinh một artifact **khác loại**, `scripts/measure.py` → `measurement_report.json`:

| Khối | Nội dung | Nguồn |
|---|---|---|
| Định danh | `task_profile_id`, `candidate_id`, `stack_label`, git sha, anchor version | có sẵn |
| Bộ mẫu | số context, `n_distinct_episodes`, danh sách `episode_context_id` | `contexts.py`, `_distinct_episode_count` |
| Kết quả thô | success/stuck/collision/timeout theo từng episode | `run_contract_episode` |
| Metric HĐ-6 | `success_rate`, `path_length_m`, `L_ref`, `path_efficiency`, `travel_time_s`, `time_efficiency`, `min_clearance`, `near_miss_rate`, `p99_latency_ms` (gộp), `memory_estimate_mb`, `replan_count` | `metrics/definitions.py` |
| Bảng cổng | G1–G6 đầy đủ kèm N và chuỗi bắt buộc | `gates.py` |
| Objective | U_R/U_S/U_E/U_C theo từng episode + `decision_utility` | `objectives.py` |
| Môi trường đo | affinity, số nhân, thứ tự chạy (F0.5) | manifest |

`decision_utility` **có** mặt và **không** phải một khuyến nghị: nó là điểm của một candidate
trên thang anchor, đọc được một mình, và cần có ngay từ MVP để F4 không phải đổi định dạng.
Report in kèm một dòng cố định nói rằng một điểm số đơn lẻ không so được với gì, và **cấm**
mọi chuỗi kiểu "tốt"/"đạt"/"khuyến nghị" — mở rộng test chuỗi cấm đã có ở HĐ-7.1.

### 2.3. Chuyện G2 sẽ từ chối, và vì sao đó là MVP **thành công**

`open_hall_v1` **không có traffic động**. Với planner tất định, mọi seed cho cùng một episode;
với RRT\* (ngẫu nhiên) thì các episode có khác nhau, nhưng nguồn khác biệt là **bản thân
planner**, không phải hiện trường.

Nên `n_distinct` sẽ nhỏ hơn số episode ở A\*, và G2 sẽ **fail kèm note giải thích**. Đó là hệ
hoạt động **đúng**. Tiêu chí nghiệm thu F1 phải nói rõ điều này, nếu không lần sau người chạy
sẽ thấy chữ đỏ và đi thêm traffic vào — tức lặp lại đúng vòng lặp đã sinh ra `pallet_truck`.

> **F1 đạt khi hệ đo được đầy đủ VÀ nói đúng về giới hạn của bộ số đó. F1 không đòi cổng nào
> phải xanh.**

### 2.4. Sáu tiêu chí nghiệm thu F1

1. Chạy 30 episode `rrtstar+dwa` trên `open_hall_v1`, **không lỗi**, mỗi episode một file trace.
2. Mọi metric HĐ-6 tính lại được **từ thư mục trace**, không đụng dữ liệu in-memory.
3. `L_ref ≤ path_length_m` ở mọi episode thành công.
4. Chạy lại cùng manifest ⇒ cùng `decision_utility` tới 6 chữ số.
5. Bảng cổng đủ 6 cổng kèm N; G2 in **cả** `n_runs` lẫn `n_distinct_episodes`.
6. **(mới)** Bộ kiểm công bằng — `tests/test_fairness.py` + `tests/test_simulator_fairness.py`
   — xanh, và manifest ghi affinity thật.

Tiêu chí 6 là thứ mà năm tiêu chí của HĐ-15.1 thiếu, và là thứ đã để bốn thay đổi
do-kết-quả-dẫn-dắt lọt qua.

**Ước lượng:** 4–6 giờ (chủ yếu là `measure.py` và test cho nó; run 30 episode ~10 phút).

---

## 3. Phase F2 — Biến công bằng thành cấu trúc, không phải phản ứng

53 test công bằng hiện có ra đời ngày 08-11, **sau** Phase 6.1, ngoài kế hoạch, chỉ vì dev chặn
lại hỏi. Chúng đang là phản ứng. F2 biến chúng thành luật.

| # | Việc | Nội dung |
|---|---|---|
| F2.1 | **Tiêu chí thứ 6 vào HĐ-15.1** | Bộ kiểm công bằng xanh là điều kiện cần để công bố *bất kỳ* phép so nào. Bump contract MINOR |
| F2.2 | **Câu hỏi bắt buộc vào HĐ-15.3** | Mọi hằng số mới trong profile phải trả lời được: *"con số này đến từ hiện trường, hay từ thứ máy tôi chạy nổi?"* Vế sau ⇒ thuộc mục bảo lưu contract, **không** thuộc file profile |
| F2.3 | **Cổng CI riêng** | Hai bộ test công bằng chạy thành job riêng, chặn merge — không lẫn trong 2000 test để một lần đỏ trôi qua như nhiễu |
| F2.4 | **Test chữ ký cho ngưỡng cổng** | Khoá chiều phụ thuộc của F0.1: ngưỡng cổng không được đọc từ trường điều khiển độ trung thực mô phỏng. Cùng lý lẽ với `scenario_for` không nhận `candidate` — test chữ ký sống sót qua refactor, test hành vi thì không |

**Vì sao F2 đứng trước F4 chứ không sau:** F4 là lúc bắt đầu công bố so sánh. Luật phải có
hiệu lực **trước** phép so đầu tiên, không phải sau — luật viết sau kết quả thì kết quả đã chọn
luật rồi.

**Ước lượng:** 3 giờ.

---

## 4. Phase F3 — Nguồn ngẫu nhiên theo seed (nhiễu cảm biến)

Kéo nguyên `plans/2026-08-11/nhieu-cam-bien-theo-seed.md` vào đây làm một phase, **không viết
lại** — bản kế hoạch đó đã đủ chi tiết.

**Điều bản này thêm vào là vị trí của nó trong thứ tự, và cách đọc nó:**

Nó thuộc **nền tảng**, không thuộc "làm cho kết quả dùng được". Chính báo cáo 08-11 đã cảnh báo
đúng điều này: *"nếu tôi bán nó như cách để có bộ evaluation dùng được thì tôi lặp lại đúng sai
lầm ở mục 1"*. Nhiễu cảm biến sửa một chỗ **simulator đang lạc quan hơn thực tế** — robot thật
không bao giờ chạy hai lần giống hệt — và nhiều khả năng làm mọi con số **xấu đi**. Đó là dấu
hiệu nó đúng, không phải dấu hiệu nó hỏng.

Ba ràng buộc thiết kế của bản plan gốc giữ nguyên, và cả ba đều là ràng buộc **công bằng**:
seed từ `EpisodeContext` chứ không từ đồng hồ; nhiễu vào **phép đo** chứ không vào **sự thật**
(va chạm vẫn phán quyết trên pose thật); khai báo được, **mặc định tắt**.

Thêm một ràng buộc thứ tư, từ bất biến 3 của lượt kiểm toán: **generator riêng, không đụng
stream dùng chung**. Nếu nhiễu rút số từ một generator mà planner cũng dùng thì đổi A\* sang
RRT\* sẽ **làm dịch chuyển vật cản**, và hai episode khác nhau sẽ đội chung một
`episode_context_id`. `test_a_planners_draws_cannot_move_the_world` và
`test_planning_leaves_the_global_streams_untouched` là hai test sẽ nói điều đó ra — chạy chúng
**trong lúc** làm F3, không phải sau.

**DoD:** bật nhiễu trên `open_hall_v1` ⇒ `n_distinct` của một stack tất định lớn hơn 1; tắt
nhiễu ⇒ mọi số về đúng như F1 tới chữ số cuối; hai test bất biến 3 xanh.

**Ước lượng:** theo plan gốc, ~1 ngày.

---

## 5. Phase F4 — Đưa thuật toán vào dần

Chỉ bắt đầu khi F0–F3 xong. Mỗi bước thêm **đúng một** chiều biến thiên, và mỗi bước là một
báo cáo riêng — để khi con số nhảy thì biết nó nhảy vì cái gì.

| # | Thêm gì | Câu hỏi nó trả lời | Kết quả xấu xử lý ra sao |
|---|---|---|---|
| F4.1 | `astar+dwa_coarse` trên `open_hall` | Phép **so** đầu tiên. Nền tảng có phân biệt được hai global planner trên map đối xứng không? | A\* đang kẹt góc lồi 8/8 — **giữ nguyên, không chỉnh**. Đó là phát hiện về stack, và là dữ liệu demo đắt giá |
| F4.2 | `*+dwa_default` (20×40) | Kẹt góc lồi là tính chất của **stack** hay của **lấy mẫu thô**? Câu hỏi treo từ F0.2 | Trả lời được bằng dữ liệu, không bằng suy đoán. Bốn candidate = 2 global × 2 local |
| F4.3 | `warehouse_a_v3` với profile đã sửa, N thật | Chạy lại Phase 5.1 cũ trên nền đã đúng | `n_distinct` phải > 1 nhờ F3; nếu vẫn 1 thì F3 chưa xong, quay lại F3 |
| F4.4 | Candidate thứ 5 trở đi (biến thể RRT\*, PPO) | Mở rộng | Chỉ khi F4.1–F4.3 sạch |

**Luật xuyên suốt F4, và nó là kết luận đã rút ra từ lần đi sai hướng:**

> Một stack trượt cổng là **một kết quả**, không phải một lỗi phải sửa. Cách sửa hợp lệ duy
> nhất là **đăng ký một candidate mới** với cấu hình khác và để nền tảng chấm cả bản cũ lẫn bản
> mới. Bản cũ và bản mới là hai candidate, và so chúng chính là việc nền tảng sinh ra để làm.

Phase 5.2 (Pareto) và 5.3 (sensitivity) đã xong từ trước và chạy được ngay trên bất kỳ bộ kết
quả nào của F4 — không cần làm lại.

**Ước lượng:** F4.1 nửa ngày · F4.2 nửa ngày + giờ chạy · F4.3 một ngày (chủ yếu là chờ run).

---

## 6. Phase F5 — API, lưu trữ, UI (kéo từ backlog cũ)

Giữ nguyên nội dung Phase 6.2, 6.3 và 7.1–7.4 của `backlog-uu-tien-planner-selector.md`. Không
viết lại ở đây; chúng vẫn đúng và không phụ thuộc vào bất cứ thứ gì bản này đổi.

Một sửa đổi duy nhất về nội dung: trang `/decisions` phải hiển thị được **cả hai loại
artifact** — Measurement Report (một candidate) và Decision Card (từ hai candidate trở lên).
Nếu UI chỉ render được card thì nó sẽ tạo áp lực ép mọi run ra card, tức lặp lại đúng vấn đề
mục 2.2 vừa tránh, chỉ là ở tầng trên.

---

## 7. Sơ đồ phụ thuộc

```
F0 sửa lệch ─┬─ F0.1 ngưỡng G4      (blocker thật sự duy nhất)
             ├─ F0.2 hai DWA
             ├─ F0.3 bảo lưu hướng
             ├─ F0.4 rủi ro khai báo
             ├─ F0.5 affinity
             └─ F0.6 luật replan
                  │
                  ▼
             F1 MVP — một stack, một map, Measurement Report
                  │
                  ▼
             F2 công bằng thành luật   ◄── phải xong TRƯỚC phép so đầu tiên
                  │
                  ▼
             F3 nhiễu theo seed        ◄── nền tảng, không phải "làm số đẹp"
                  │
                  ▼
             F4 thêm thuật toán dần ── F4.1 ─ F4.2 ─ F4.3 ─ F4.4
                  │
                  ▼
             F5 API + UI (backlog cũ, không đổi)
```

**Đường tới hạn:** F0.1 → F1 → F2 → F3 → F4.1. Mọi nhánh khác của F0 song song được.

---

## 8. Việc cố ý KHÔNG làm trong bản này

- **Không mở lại Phase 1–4, 5.2, 5.3, 6.1.** Phương pháp luận đã đóng băng theo HĐ-15.2; bản
  này sửa **đầu vào** và **thứ tự**, không sửa cách tính.
- **Không hiện thực lời giải cho replan ground truth** (F0.6 chỉ ghi luật) — chưa có candidate
  monolithic thì chưa có vấn đề.
- **Không tối ưu DWA cho kịp 20 Hz.** F0.1 cho thấy nhiều khả năng không cần; nếu cần thì đó
  là việc kỹ thuật mở, không ước lượng được trước khi đo.
- **Không đụng** MissionSampler L2, Task Neighborhood, Target Verifier, `monetized_cost` đầy
  đủ, `trials_to_90` — đúng như backlog cũ đã cắt.
- **Không chạy `warehouse` ở mức 1% (300 episode, ~3 giờ)** cho tới F4.3, và chỉ khi máy rảnh.

---

## 9. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| F0.1 nhánh xấu: candidate trượt G4 ở 50 ms ⇒ phải làm trường mới + bump MAJOR + chạy lại lát cắt | Đo trước bằng cách chấm lại trace cũ — vài giây, không cần mô phỏng. Biết ngay ở bước 3 |
| Đổi `id` profile làm mồ côi trace cũ | Đúng theo thiết kế và đã ghi ở đầu `warehouse_a_v2.yaml`. Trace cũ giữ làm bằng chứng lịch sử, không xoá |
| `measure.py` thành nhánh code song song với `vertical_slice.py`, hai đường trôi khác nhau | Cả hai gọi chung một tầng: `run_contract_episode` → `definitions.py` → `gates.py`. Chỉ khác ở lớp **artifact** cuối. Test khẳng định hai đường cho cùng bảng metric trên cùng bộ trace |
| F3 làm mọi con số xấu đi, và bị đọc như regression | Ghi trước vào DoD của F3 rằng số xấu đi là kỳ vọng. Báo cáo F3 phải in kèm bộ số F1 (nhiễu tắt) để so được |
| Sáu chỗ lệch được sửa rồi mọc lại chỗ khác | F2.2 — câu hỏi bắt buộc trong DoD mọi PR. Đó là biện pháp duy nhất trong bản này nhắm vào **nguyên nhân** chứ không vào triệu chứng |

---

## 10. Định nghĩa "xong" của cả bản kế hoạch

Bản này xong khi **cả ba câu sau đều đúng cùng lúc**:

1. Chạy một stack trên `open_hall_v1` cho ra Measurement Report đủ thông số, tái lập được, và
   bảng cổng nói đúng về giới hạn của chính bộ số đó.
2. Sáu chỗ lệch ở note `tongduyan_xac-minh-lech-huong-muc-tieu.md` không còn trong repo, và mỗi
   cái được thay bằng **một điều khoản hợp đồng hoặc một test**, không phải bằng một comment.
3. Phép so đầu tiên giữa hai candidate (F4.1) được công bố **sau** khi cả hai điều trên đã
   đúng — và nếu kết quả của nó xấu, nó vẫn được công bố nguyên trạng.

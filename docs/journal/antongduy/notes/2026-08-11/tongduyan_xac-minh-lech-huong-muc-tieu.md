# Xác minh độc lập: dự án có đang lệch khỏi mục tiêu "simulator công bằng" không

> **Ngày:** 2026-08-11 · **Loại:** đánh giá hiện trạng, **không sửa một dòng code nào**
> **Yêu cầu nguồn:** An — *"mục tiêu là tạo một simulator công bằng cho mọi thuật toán để xem
> thuật toán nào tối ưu trong một điều kiện cụ thể; nhưng có vẻ tôi đang sửa config của
> simulator để thuật toán chạy được. Verify lại, chỉ ra chỗ nào lệch."*
> **Phạm vi đọc:** plan/notes/reports `docs/antongduy` từ 2026-08-08, git log
> `f256b73..b60dbd9`, và toàn bộ working tree chưa commit của nhánh `plannerselector_p2`.
> **Kết luận ngắn:** cảm giác của dev là **đúng**, nhưng không đúng ở chỗ dev nghĩ. Bốn thay
> đổi do-kết-quả-dẫn-dắt đã hoàn nguyên thật (kiểm được trên cây làm việc). Cái còn lại là
> **bốn chỗ khác, cũ hơn, đang nằm trong repo và chưa ai gọi tên là lệch** — vì cả bốn đều
> được ghi chú tử tế nên trông giống quyết định thiết kế chứ không giống nhượng bộ.

---

## 0. Cách kiểm

Dùng đúng câu hỏi mà báo cáo 08-11 đã tự đặt ra, và đó là câu hỏi đúng:

> *Nếu kết quả ra ngược lại, tôi có làm thay đổi này không?*

Bổ sung một câu thứ hai, vì câu trên không bắt được loại lệch còn sót:

> *Con số này đến từ **hiện trường triển khai**, hay đến từ **thứ code/máy của tôi làm nổi**?*

Bất kỳ ngưỡng nào trả lời "từ thứ code tôi làm nổi" đều là simulator đang được uốn theo thuật
toán, kể cả khi nó uốn **đều cho mọi candidate**. Công bằng giữa các candidate và tính đúng đắn
của phép đo là **hai** điều; giữ được cái đầu không cứu được cái sau.

---

## 1. Phần đã sửa: xác nhận đúng, không phải tự khai

Bốn thay đổi mà báo cáo `tongduyan_kiem-tinh-cong-bang-va-mot-lan-di-sai-huong.md` nhận là
sai hướng và tuyên bố đã hoàn nguyên — kiểm trên cây làm việc, cả bốn đúng là đã về:

| Thay đổi bị tố | Trạng thái thực tế trong repo | Nơi kiểm |
|---|---|---|
| DWA `horizon_seconds` 1,0 → 1,5 | `horizon_seconds: 1.0` | `scripts/vertical_slice.py` `LOCAL_CONTROLLER_PARAMS` |
| Đổi mission sang hành lang khác | `m1: start [2,3] → goal [38,21]`, như cũ | `profiles/warehouse_a_v2.yaml` |
| Traffic 1,17 → 0,24 m/s | `forklift` chu kỳ 24 s trên quãng 14 m, như cũ | cùng file |
| Thêm `pallet_truck` | không tồn tại trong profile | cùng file |

Bốn sửa chữa được giữ lại (xen kẽ context-outer, `n_distinct_episodes` ở G2,
`seed_time_offset` 6 → 24 s, `delta_u_mean` trên card) đều kiểm được trong diff và đều có
tính chất mà báo cáo nêu: **không cái nào làm kết luận đẹp hơn**. `_gate_2` giờ chia `3` cho
`n_distinct`, không cho `n_runs` — làm cận trên **xấu đi**; validator `EnvironmentSpec` giờ
**từ chối** offset ngắn hơn một chu kỳ, tức chặn thêm profile chứ không nới.

Phần này lành. Không có gì phải làm.

---

## 2. Bốn chỗ **đang** lệch, theo thứ tự nghiêm trọng

### 2.1. `control_period: 0.1` — ngưỡng cổng G4 do implementation quyết, không do hiện trường

Đây là chỗ nặng nhất, và nó là ví dụ **thuần khiết** của điều dev lo.

Chuỗi phụ thuộc trong code:

```
profile.robot.control_period
    ├─► RobotConfig.t_cycle_ms  ──► _gate_4 threshold_ms      (task_profile.py:201)
    └─► simulation_dt = min(MAX_SIMULATION_DT, control_period)
```

Cả hai profile khai `control_period: 0.1` (10 Hz). Lý do được ghi thẳng trong file:

> *"`control_period: 0.1` (10 Hz) rather than 20 Hz. The Python DWA in this repository does
> not compute a control step in 50 ms, so a 20 Hz profile fails G4 for a property of the
> simulator."*

Đọc lại một lần nữa: **candidate trượt cổng thời gian thực, nên ngưỡng của cổng thời gian
thực được nhân đôi từ 50 ms lên 100 ms.** Lập luận "đó là tính chất của simulator chứ không
phải của planner" nghe hợp lý, và một nửa của nó đúng — nhưng hệ quả là G4 mất gần hết ý
nghĩa: **ngưỡng bây giờ là hàm của tốc độ code Python, không phải của yêu cầu hiện trường.**
Bất kỳ candidate nào chậm tới đâu cũng chỉ cần một profile khai `control_period` đủ lớn.

Tệ hơn: đây là vòng lặp tự tham chiếu. Code chậm ⇒ khai chu kỳ dài ⇒ `simulation_dt` thô hơn
⇒ mô phỏng chạy nhanh hơn **và** ngưỡng cổng rộng hơn. Cả hai chiều đều thưởng cho
implementation chậm.

So sánh trực tiếp: `horizon_seconds 1.0 → 1.5` đã bị tuyên là sai hướng và hoàn nguyên. Nó
sửa **candidate** cho qua G3. `control_period 0.05 → 0.1` sửa **deployment** cho qua G4. Cái
thứ hai đứng ở tầng cao hơn, tác động rộng hơn, và vẫn đang nằm đó.

*Không đề xuất sửa ngay* — nếu nâng lại 20 Hz thì cả hai candidate cùng trượt G4 và không so
được gì. Nhưng đúng cách thì phải là: **profile khai 20 Hz như hiện trường thật, cả hai
candidate trượt G4, và card in ra đúng điều đó** — "không stack nào trong repo này chạy nổi
20 Hz trên host" là một phát hiện thật, và là phát hiện mà kiến trúc hai tầng cổng/điểm sinh
ra để nói. Hạ ngưỡng là cách duy nhất khiến sự thật đó biến mất khỏi báo cáo.

### 2.2. DWA `7×15` thay vì mặc định `20×40` — candidate bị cấu hình theo ngân sách đồng hồ

`scripts/vertical_slice.py`:

> *"Sampling is coarser than the DWA default (7×15 instead of 20×40) because 50 episodes of
> the default is hours of wall clock."*

DWA **là một phần của candidate đang được đem ra chấm** (HĐ-1: candidate = stack global +
local). Chọn tham số của nó theo *thời gian chạy benchmark* là cùng loại việc với chỉnh
`horizon_seconds`, chỉ khác chiều: lần đó chỉnh cho **tốt hơn**, lần này chỉnh cho **rẻ hơn**.
Cả hai đều là "cấu hình thứ đang được đo, vì lý do không thuộc hiện trường".

Nó áp đều cho hai candidate nên **công bằng**, đúng. Nhưng nó có thể đang **sản xuất ra chính
phát hiện đang được báo cáo**: mục 4 của báo cáo 08-11 kết luận `A* + DWA(7×15, horizon 1,0 s)`
mắc ở góc lồi với clearance 0,30 m trong khi RRT\* lách qua khe 0,11 m. Một DWA lấy mẫu
`20×40` có mắc ở đúng góc đó không thì **chưa ai đo**. Nếu không, thì câu "A\* + DWA kẹt ở góc
lồi" thực ra là "A\* + DWA-bị-làm-thô-cho-chạy-nhanh kẹt ở góc lồi" — và đó là tính chất của
harness đội lốt tính chất của stack.

Việc rẻ và đúng ở đây không phải bỏ `7×15`, mà là **đăng ký nó thành candidate riêng**: `dwa_7x15`
và `dwa_20x40` là hai local controller khác nhau, `candidate_id` khác nhau, và nền tảng chấm cả
hai. Đó đúng là kết luận mà chính báo cáo 08-11 đã rút ra cho trường hợp horizon — nhưng chưa
được áp cho trường hợp này.

### 2.3. `goal_tolerance_rad: 3.1416` — ngữ nghĩa thành công bị nới cho vừa simulator

HĐ-6 chấm `success` theo **cả vị trí lẫn hướng**. Cả hai profile khai dung sai hướng = π, tức
**tắt hoàn toàn** điều kiện hướng. Lý do ghi trong file: simulator không có bộ điều khiển ổn
định hướng cuối, nên profile đòi hướng sẽ chấm mọi candidate là trượt.

Cùng khuôn với 2.1: một tiêu chí thành công bị vô hiệu hoá vì implementation không đáp ứng
được nó. Điểm nhẹ hơn 2.1 là chỗ này đã được ghi tường minh dưới dạng *declared limitation*
đúng tinh thần HĐ-15.2, và nó **thu hẹp phạm vi tuyên bố** ("deployment này không đòi hướng")
thay vì giả vờ đã đo. Nhưng phải nói rõ hệ quả: **mọi nhiệm vụ có ràng buộc hướng nằm ngoài
năng lực của nền tảng này**, và đó là giới hạn của *nền tảng*, không phải lựa chọn của kho
hàng — chỗ đúng để ghi nó là mục bảo lưu của contract, không phải một dòng trong file profile
của một khách hàng giả định.

### 2.4. `collision_probability_max: 0.03` — mức rủi ro chấp nhận được suy ngược từ ngân sách máy

Chuỗi đúng theo HĐ-7.1: rủi ro khai báo ⇒ `N_min = ceil(3/p)` ⇒ số giờ chạy.

Chuỗi thực tế trong `warehouse_a_v2.yaml`, viết thẳng ra trong comment:

> *"Declared at 3% rather than 1% because the run has to share a working machine."*

Tức: giờ chạy ⇒ rủi ro khai báo. **Mũi tên bị đảo.** `collision_probability_max` là một ràng
buộc an toàn của hiện trường; nó không được phép là hàm của việc máy có rảnh hay không.

Đây là biến thể nhẹ nhất trong bốn cái — hệ **không** nói dối: G2 in đúng "cận trên 3,0%", và
comment còn ghi rõ nâng lên 1% chỉ cần máy rảnh. Nhưng nó đứng cùng họ với ba cái trên, và
đáng ghi cạnh nhau vì cùng một cơ chế: **một hằng số mô tả thế giới được đặt theo thứ mà công
cụ chịu nổi.**

---

## 3. Hai món nợ về công bằng đã biết, chưa trả

Không phải lệch hướng mới, nhưng chưa xong và đang chặn kết luận:

1. **Lưới replan dùng ground truth** — `nav_stack.py:166`,
   `_planning_grid(map_data, scenario, engine.dynamic_obstacles_now())`. Global planner của
   stack modular thấy vật cản động **thật sự ở đâu**; một policy end-to-end chỉ thấy
   `Observation`. Hôm nay vô hại vì chỉ modular chạy được; ngày có adapter monolithic thì đây
   là đặc quyền thông tin đúng nghĩa G6. Đã có `test_only_modular_stacks_can_run_today` làm
   chốt chặn — chốt chặn không phải lời giải.
2. **Ghim nhân không được cưỡng chế, không được ghi lại.** G4 đọc latency theo đồng hồ tường;
   đo được ở Phase 5.1 là **59,30 ms so với 16,10 ms** cho cùng RRT\* chỉ vì có/không ghim
   nhân — 3,7 lần, và nó **đã từng** bị đọc thành tính chất của candidate (contract 3.0.0
   loại nhầm A\*). Manifest HĐ-13 có trường `benchmark_host.cores_allocated` nhưng affinity
   thật không được ghi, và không có cảnh báo nào khi hai candidate không chạy xen kẽ. Tính
   công bằng đang phụ thuộc vào việc người vận hành nhớ gõ đúng lệnh.

---

## 4. Nguyên nhân gốc: bản backlog không có một phase nào cho tính công bằng

Đây là câu trả lời cho "vì sao tôi cứ trôi về hướng đó".

Đọc lại `plans/2026-08-08/backlog-uu-tien-planner-selector.md`: Phase 4 là **van chặn phương
pháp luận**, và DoD của nó là 5 tiêu chí HĐ-15.1 — cùng tập context, tái lập 6 chữ số, đủ 6
cổng kèm N, CI không NaN, `L_ref ≤ path_length`. Cả năm đều hỏi *"pipeline có chạy thông và
tái lập được không"*. **Không tiêu chí nào hỏi *"phép so này có công bằng không"*.**

Một DoD như thế thưởng cho **một tấm card render được**. Khi card không ra, đường ít kháng cự
nhất là chỉnh đầu vào — và mọi lần chỉnh đều qua được cả 5 tiêu chí, vì 5 tiêu chí đó không
nhìn vào đầu vào. Chính xác đó là cơ chế đã sinh ra bốn thay đổi ở mục 1, và cũng là cơ chế
đã sinh ra bốn cái ở mục 2 từ sớm hơn nhiều mà không ai chặn.

Hai bộ `tests/test_fairness.py` (22 test) và `tests/test_simulator_fairness.py` (31 test) là
thứ đúng cần có — nhưng chúng ra đời **ngày 08-11, sau Phase 6.1**, ngoài kế hoạch, và chỉ vì
dev chặn lại hỏi. Chúng đang là phản ứng, không phải cấu trúc.

Còn một điều nữa về hình dạng của kế hoạch: Phase 6 (API + DB) và Phase 7 (UI + demo) chiếm
gần nửa backlog và là **bề mặt sản phẩm**, không phải năng lực đo. Điều đó không sai theo đề
tài — đề tài có phần sản phẩm thật — nhưng nếu mục tiêu số một là *simulator công bằng* thì
thứ tự hiện tại đang đặt màn hình trước thước đo.

---

## 5. Tóm tắt để quyết

| # | Chỗ lệch | Tầng bị uốn | Còn trong repo? |
|---|---|---|---|
| 2.1 | `control_period: 0.1` nới ngưỡng G4 từ 50 ms lên 100 ms | deployment (nghiêm trọng nhất) | ✅ cả hai profile |
| 2.2 | DWA `7×15` chọn theo ngân sách đồng hồ | candidate | ✅ `vertical_slice.py` |
| 2.3 | `goal_tolerance_rad: π` tắt điều kiện hướng | ngữ nghĩa thành công | ✅ cả hai profile |
| 2.4 | rủi ro 3% suy ngược từ giờ máy | ràng buộc hiện trường | ✅ `warehouse_a_v2` |
| 3.1 | replan thấy vật cản thật | lớp quan sát | ✅ có chốt chặn, chưa giải |
| 3.2 | affinity không ghi, không cưỡng chế | quy trình đo | ✅ chưa làm |
| 1.x | horizon / mission / traffic / pallet_truck | — | ❌ đã hoàn nguyên đúng |

**Điểm chung của cả sáu cái còn lại:** không cái nào thiên vị candidate này hơn candidate kia.
Bộ kiểm công bằng 53 test sẽ vẫn xanh với tất cả. Chúng không phá **tính công bằng**; chúng
phá **tính đúng đắn** — hệ vẫn so hai thuật toán đúng luật, nhưng so trong một thế giới đã
được nới ra cho vừa thứ code làm nổi. Một bộ test đối xứng theo thiết kế không thể bắt được
loại lỗi này, vì nó nới **đều cho cả hai bên**.

Nên câu hỏi cần thêm vào mọi PR sau, cạnh câu "nếu kết quả ngược lại tôi có làm không":
**"con số này đến từ hiện trường, hay đến từ thứ máy tôi chạy nổi?"** — và nếu là vế sau, nó
thuộc mục bảo lưu của contract, không thuộc file profile.

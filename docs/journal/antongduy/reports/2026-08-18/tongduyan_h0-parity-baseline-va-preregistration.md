# H0 — parity baseline, preregistration, và hai guard

**Ngày:** 2026-08-17 → 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` (v2, đã approve)
**Phạm vi:** H0 trọn vẹn + hai artifact preregistration mà plan đòi có trước H0.
**Trạng thái:** xong, test xanh, **chưa commit** — xem mục 6 về thứ tự commit.

---

## 1. Đã làm gì

### (a) Hai artifact preregistration (điều kiện tiên quyết của H0)

| File | Nội dung |
|---|---|
| `docs/antongduy/plans/2026-08-17/algorithm-host-gate-preregistration.md` | Bản ghi decision gate: H1 ideal 2.5–3 ngày, ideal(H2..H8) 10–13 ngày, công thức `schedule_factor`/`projected_remaining`, ba điều kiện AND. **Còn các ô `[AN ĐIỀN]`**: allocated budget, remaining calendar, xác nhận critical-path, external demand |
| `configs/latency-screening-v1.yaml` | Thước đo latency §5.9 luật 5: warmup 3, repetitions 30, 1 worker/1 BLAS thread, sentinel `astar+dwa:dwa_balanced` drift ≤ 15%, guard band 5 ms, bootstrap CI 95% (tái dùng `bootstrap_ci`), verdicts pass/fail/inconclusive. Deadline lấy từ `deployment.robot.control_period` lúc đo, không hardcode |

### (b) Parity golden — `tests/test_host_parity_golden.py` + `tests/golden/host_parity.json`

Theo đúng khuôn P2 (`test_dwa_core_refactor.py`): fixture sinh **trước khi
host tồn tại**, so byte-identical mãi về sau.

- **4 case:** `astar+dwa` × seed 0/1, `rrtstar+dwa` × seed 0/1, trên
  `warehouse_crossing_v1` — đúng deployment từng lộ lỗ stale-trace. RRT*
  có mặt để ghim đường seed-per-episode, thứ dễ trôi nhất khi H2 bọc loop.
- **Chạy qua đúng đường sản xuất** `run_contract_episode` (không phải
  `run_stack` trần), nên fixture ghim luôn `candidate_id`,
  `execution_conditions_fingerprint`, trace metadata, tên cột, số dòng và
  đường dẫn tương đối của trace.
- **Comparator khai tường minh** (DoD H0): candidate_id · fingerprint ·
  status/reason/steps · mọi plan · trajectory (pose + lệnh) · mọi event
  (time, type, message) · trace metadata deterministic + columns + rows —
  **byte-identical** qua `json.dumps` so văn bản, nên `0`/`0.0`/`-0.0`
  không lọt.
- **Loại trừ preregistered, chỉ wall-clock:** `planner_latency_ms`,
  `latency_seconds`, `planning_time_seconds`, `global_plan_time_ms`,
  `peak_rss_mb`, `cpu_time_s`. Một test khoá fixture **không chứa** field
  nào trong danh sách này dưới dạng key — danh sách không phình âm thầm
  được.
- Regen chỉ bằng `PLANBENCH_REGEN_HOST_PARITY=1`, và lý do không bao giờ
  là "test đỏ".

### (c) PPO baseline — mức identity, có chủ đích

Máy này không có torch/SB3 (kiểm bằng `find_spec`). Nên:

- ghim **registry facts**: `requires_model=True`, observation classes,
  `requires_global_path` — thứ legacy adapter H2 phải giữ;
- ghim **đường từ chối**: `candidate_from_stack("astar+ppo", params={})`
  phải raise "no PPO model was chosen" — host adapter mà tự bịa model là
  đúng fabrication spec cấm.

Golden runtime cho PPO ghi nợ: thêm khi có máy cài RL extras, trước khi
H2 tuyên bố parity cho PPO.

### (d) Guard thứ hai cho fingerprint

`test_run_stack_has_not_grown_a_condition` đã có từ 16-08. H0 thêm
`test_run_policy_has_not_grown_a_condition`: điều kiện của `run_policy`
(map_data, scenario) phải ⊆ `CONDITION_ARGUMENTS` — cửa monolithic giờ
cũng có chốt, thêm điều kiện mà không quyết định có vào hash hay không là
test đỏ.

### (e) Inventory dữ liệu qua hai entry point (mục tiêu 3 của H0)

| Tham số | Vai trò | Fingerprint? |
|---|---|---|
| `run_stack(map_data)` | điều kiện — thế giới tĩnh | có (checksum) |
| `run_stack(scenario)` | điều kiện — traffic, noise, robot, tolerances, dt, clearance_preference | có (trừ name/description/random_seed) |
| `run_stack(replanning)` | điều kiện — ngân sách replan | có |
| `run_stack(recovery)` | điều kiện — thang recovery | có |
| `run_stack(obstacle_speed)` | điều kiện — biên phanh `v_obstacle_max` | có |
| `run_stack(local_planner, global_planner)` | candidate | không — thuộc candidate_id |
| `run_stack(recorder, legacy_metrics)` | plumbing | không |
| `run_policy(map_data, scenario)` | điều kiện | có |
| `run_policy(policy)` | candidate | không |
| `run_policy(recorder, legacy_metrics)` | plumbing | không |

Ngoài chữ ký: engine đọc `scenario.*` (đã hash qua scenario_payload);
`_reset_local` probe `envelope`/`obstacle_speed`/`sensor_noise` — cả ba
dẫn xuất từ scenario/profile đã hash. Không tìm thấy điều kiện nào đi
đường tắt ngoài hai chữ ký — khớp thiết kế "băm từ object".

## 2. Hai lỗi của chính harness, bắt trong phiên

1. **Byte-test chạy trước regen** — test so byte không request fixture
   `golden` nên lần sinh đầu tiên đọc file chưa tồn tại. Sửa: test khai
   phụ thuộc `golden` để đường regen chạy trước. Lỗi này tồn tại cả trong
   khuôn P2 gốc nhưng chưa từng lộ vì file dwa golden sinh ra trước khi
   test được viết xong.
2. **Guard wall-clock bắt nhầm tên cột** — `trace.columns` chứa chuỗi
   `planner_latency_ms` (tên cột hợp lệ của schema HĐ-5), guard đầu tiên
   cấm cả tên. Sửa: chỉ cấm dạng key JSON `"field":` — giá trị mới là
   wall-clock, tên cột thì không.

## 3. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| Sinh fixture (4 episode, ~2.6 phút) | `tests/golden/host_parity.json`, 851 KB |
| **Verify pass**: 4 episode chạy lại so byte với fixture | **byte-identical** |
| `tests/test_host_parity_golden.py` + `tests/test_execution_conditions.py` | **33 passed**, 152 s |
| `ruff check` + `ruff format` file mới | sạch |
| Hai seed thật sự là hai episode (test riêng) | pass — context id và trajectory đều khác |

## 4. DoD H0 đối chiếu

| DoD | Trạng thái |
|---|---|
| Regression fixtures cho legacy stacks, comparator tường minh, wall-clock loại trừ theo danh sách preregistered | ✅ (PPO ở mức identity, có ghi nợ) |
| Guard test mọi điều kiện runtime mới đi qua fingerprint chung | ✅ `run_stack` (sẵn) + `run_policy` (mới) |
| Baseline A*, RRT*, DWA, PPO | ✅ A*/RRT*/DWA runtime-level; PPO identity-level |
| Ghi rõ dữ liệu qua `run_stack()`/`run_policy()` | ✅ mục 1(e) |

Ước lượng plan 0.5–1 ngày; thực tế ~nửa ngày kỹ thuật.

## 5. Còn treo

1. `[AN ĐIỀN]` trong `algorithm-host-gate-preregistration.md` — điền
   trước khi commit, vì đó là chỗ "khai trước" của gate.
2. PPO runtime golden — chờ máy có RL extras.
3. H1a kế tiếp theo plan.

## 6. Thứ tự commit (quan trọng)

Kỷ luật preregistration là **tính chất của lịch sử git**:

1. Commit 1: `algorithm-host-gate-preregistration.md` (đã điền) +
   `configs/latency-screening-v1.yaml` + plan v2 + notes.
2. Commit 2: H0 — `tests/test_host_parity_golden.py` +
   `tests/golden/host_parity.json` + report này.

Ghi thật: code H0 được viết trước khi prereg được commit (An commit thủ
công nên không thể khác), nhưng không số nào trong prereg chịu ảnh hưởng
từ kết quả H0 — H0 không sinh đầu vào nào của gate ngoài `H1_actual`
tương lai. Thứ tự commit trên giữ đúng điều kỷ luật cần: các con số gate
nằm trong lịch sử **trước** khi H1 bắt đầu đo.

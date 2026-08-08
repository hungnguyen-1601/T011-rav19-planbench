# CONTRACTS.md — Planner Selector

> **Phiên bản hợp đồng:** `contracts_version: 1.0.0`
> **Trạng thái:** cần cả nhóm đọc và ký ở mục 16 trước khi viết dòng code đầu tiên.
> **Tài liệu mẹ:** `de-tai-moi-planner-selector.md`. Khi hai tài liệu mâu thuẫn, **CONTRACTS.md thắng** — plan là lý do, contract là luật.

---

## 0. Cách dùng và cách sửa tài liệu này

**Hợp đồng là thứ có thể bị vi phạm.** Mỗi mục dưới đây phải kiểm tra được bằng code hoặc bằng mắt trong 30 giây. Nếu một mục không nói rõ "vi phạm trông như thế nào" thì nó là ghi chú thiết kế, không phải hợp đồng, và phải chuyển ngược về plan.

**Quy trình sửa hợp đồng:**

1. Mở PR sửa `CONTRACTS.md`, nêu rõ hợp đồng nào và vì sao.
2. Tăng `contracts_version` theo semver: PATCH = làm rõ câu chữ; MINOR = thêm trường có mặc định; **MAJOR = đổi ngữ nghĩa hoặc xóa trường**.
3. MAJOR bắt buộc: chạy lại lát cắt dọc (mục 15) và ghi lại kết quả trong PR.
4. Cần ≥2 người trong nhóm approve.

**Ba thứ tuyệt đối không đổi sau tuần 1** vì mọi thứ khác phụ thuộc vào chúng: định danh candidate (HĐ-1), episode context ghép cặp (HĐ-3), và schema trace (HĐ-5).

---

## HĐ-1 — Candidate

### 1.1. Định nghĩa

> **Đơn vị được benchmark là một cấu hình điều hướng hoàn chỉnh, không phải "một thuật toán".**

A\* và RRT\* là *global planner*; DWA là *local controller*. Chúng không thay thế nhau và **không được xếp cùng một bảng**.

### 1.2. Schema

```yaml
# candidate dạng modular
candidate:
  id: null                       # sinh tự động, xem 1.3
  type: modular
  global_planner:   {name: astar, version: v1}
  local_controller: {name: dwa,   version: v1}
  params:
    astar: {heuristic: euclidean, tie_break: 1.001}
    dwa:   {sim_time: 1.5, vx_samples: 20, vth_samples: 40,
            path_distance_bias: 32.0, goal_distance_bias: 24.0,
            occdist_scale: 0.02}
  observation_requirements: [lidar_2d]

# candidate dạng monolithic (RL end-to-end)
candidate:
  id: null
  type: monolithic
  policy: {name: ppo_navigation, checkpoint: ckpt_12, version: v1}
  params: {deterministic: true}
  observation_requirements: [lidar_2d]
```

Chỉ hai giá trị `type` được chấp nhận: `modular` | `monolithic`. `monolithic` không có `global_planner`/`local_controller`; loader phải từ chối nếu có.

### 1.3. Định danh

```python
candidate_id = sha256_short(canonical_json({
    "type": type,
    "stack": {...},              # planners/controller hoặc policy, kèm name+version
    "params": params,            # đã sắp xếp khóa
    "observation_requirements": sorted(observation_requirements),
}))[:12]
```

Hai candidate khác nhau ở **bất kỳ tham số nào** là hai candidate độc lập. `A* + DWA(config_A)` và `A* + DWA(config_B)` được phép cùng vào chung kết.

### 1.4. Phạm vi thí nghiệm

Mọi lần chạy phải khai một trong ba giá trị, và giá trị này **in trên đầu Decision Card**:

| `experiment_scope` | Điều kiện | Kết luận được phép |
|---|---|---|
| `global_planner_selection` | local controller + params của nó **giống hệt** ở mọi candidate | "Trong setup này, A\* phù hợp hơn RRT\*" |
| `local_controller_selection` | global planner + params của nó giống hệt | "Trong setup này, controller X phù hợp hơn Y" |
| `full_stack_selection` | tự do | "Stack C1 phù hợp hơn stack C2" — **không** được suy ra câu về một tầng riêng |

**Vi phạm trông như thế nào:** khai `global_planner_selection` mà hai candidate có `params.dwa` khác nhau. Batch Runner phải kiểm tra điều này và **fail ngay khi khởi động**, không phải cảnh báo.

---

## HĐ-2 — Task / Deployment Profile

### 2.1. Schema

```yaml
task_profile:
  id: warehouse_a_v1
  claim_level: mission           # mission | deployment | robust_deployment

  environment:
    map: maps/warehouse_a.pgm    # định dạng ROS map_server
    map_yaml: maps/warehouse_a.yaml

  missions:                      # 1 phần tử ⇒ claim_level tối đa là `mission`
    - {id: m1, start: [2.0, 3.0, 0.0], goal: [38.0, 21.0, 1.57], probability: 1.0}

  robot:
    type: differential_drive
    radius: 0.26
    max_linear_velocity: 0.8
    max_angular_velocity: 1.2
    max_linear_acceleration: 0.5
    max_angular_acceleration: 1.0
    control_period: 0.05         # giây ⇒ T_cycle = 50 ms

  available_observations: [lidar_2d]

  constraints:
    success_rate_min: 0.95
    collision_probability_max: 0.01
    goal_tolerance_m: 0.20
    goal_tolerance_rad: 0.35
    episode_timeout_s: 180
    stuck_threshold_s: 10
    clearance_warning_m: 0.35    # ngưỡng đếm near-miss

  hardware:
    target_device: jetson_orin_nano
    available_ram_mb: 2048
```

### 2.2. Quy tắc mức tuyên bố

`claim_level` **do hệ thống tính ra, không do người dùng khai** — trường trong YAML chỉ là mức mong muốn, hệ tự hạ xuống nếu dữ liệu không đủ:

```
len(missions) == 1                          ⇒ mission
len(missions) >  1                          ⇒ deployment
len(missions) >  1  và đã chạy neighborhood ⇒ robust_deployment
```

**Vi phạm trông như thế nào:** Decision Card in `ROBUST DEPLOYMENT-LEVEL` trong khi `missions` chỉ có một phần tử.

---

## HĐ-3 — Episode context và đánh giá ghép cặp

### 3.1. Định danh ngữ cảnh

```python
episode_context_id = sha256_short(canonical_json({
    "task_profile_id": ...,
    "mission_id":      ...,
    "environment_variant": ...,   # "nominal" hoặc id biến thể neighborhood
    "seed":            int,
}))[:12]
```

### 3.2. Luật ghép cặp — **không được vi phạm trong bất kỳ hoàn cảnh nào**

> **Mọi candidate trong một lần so sánh phải chạy trên đúng cùng một tập `episode_context_id`.**

Batch Runner sinh danh sách context **trước**, rồi lặp candidate bên trong context — không phải ngược lại:

```python
for ctx in contexts:              # vòng ngoài
    for cand in candidates:       # vòng trong
        run(cand, ctx)
```

Cùng một `episode_context_id` phải cho cùng một chuỗi ngẫu nhiên: vị trí và quỹ đạo vật cản động, nhiễu cảm biến, nhiễu odometry đều lấy từ `seed` của context, **không** từ RNG toàn cục.

**Vi phạm trông như thế nào:** hai candidate có số lượng episode khác nhau trong cùng một run; hoặc candidate B gặp một cấu hình vật cản mà candidate A không gặp. Decision Engine phải **từ chối tính `ΔU`** nếu tập context của hai candidate không trùng khớp hoàn toàn.

### 3.3. Hai bộ mẫu tách biệt

| Bộ mẫu | Cách sinh | Dùng để |
|---|---|---|
| `evaluation` | lấy mẫu độc lập: mission × lần hiện thực vật cản × seed | success rate, bằng chứng va chạm, mọi phân phối hiệu năng, `ΔU` |
| `neighborhood` | nhiễu có cấu trúc quanh profile gốc | **chỉ** đo độ ổn định của khuyến nghị |

**Cấm gộp hai bộ này khi tính cận trên va chạm** (xem HĐ-11.4).

---

## HĐ-4 — Bốn interface

Không thành phần nào được import trực tiếp thành phần khác ngoài qua bốn giao thức này.

```python
from typing import Protocol

class SimBackend(Protocol):
    def reset(self, ctx: EpisodeContext) -> Observation: ...
    def step(self, cmd: Twist, dt: float) -> tuple[Observation, StepInfo]: ...
    def get_costmap(self) -> Costmap2D: ...

class GlobalPlanner(Protocol):
    def plan(self, start: Pose2D, goal: Pose2D, costmap: Costmap2D) -> Path: ...

class LocalController(Protocol):
    def compute_velocity(self, pose: Pose2D, path: Path, obs: Observation) -> Twist: ...

class MonolithicPolicy(Protocol):
    """Adapter cho candidate type=monolithic. Runner gọi đúng interface này
    thay cho cặp GlobalPlanner + LocalController."""
    def act(self, pose: Pose2D, goal: Pose2D, obs: Observation) -> Twist: ...

class TraceRecorder(Protocol):
    def record(self, t: float, state: RobotState, event: Event | None) -> None: ...
```

**Kiểu dữ liệu dùng tên trường và đơn vị của ROS** (`geometry_msgs`, `nav_msgs`) nhưng **không import ROS**: `Pose2D(x, y, theta)`, `Twist(linear_x, angular_z)`, `Path(poses)`, `OccupancyGrid`, `LaserScan`. Đơn vị: mét, radian, giây. Bản đồ theo đúng định dạng `map_server` (`resolution`, `origin`, `negate`, `occupied_thresh`).

**Vòng lặp mô phỏng đi theo thời gian, không theo bước.** Mọi hàm nhận `dt` và timestamp thật.

**Vi phạm trông như thế nào:** một planner gọi thẳng vào nội tại của `SimBackend` để lấy vị trí vật cản, thay vì qua `Observation`. Đây vừa là vi phạm kiến trúc, vừa là gian lận về lớp quan sát (HĐ-7, G6).

---

## HĐ-5 — Trace schema

Mỗi episode ghi ra đúng một file Parquet. Đây là **nguồn dữ liệu duy nhất** của Metrics Engine — không metric nào được tính trong lúc mô phỏng.

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `t` | float | giây, từ 0 |
| `x`, `y`, `theta` | float | pose thật |
| `v`, `omega` | float | vận tốc lệnh đã thực thi |
| `clearance_m` | float | khoảng cách tới vật cản gần nhất tại `t` |
| `planner_latency_ms` | float | thời gian tính của bước điều khiển đó |
| `event` | string \| null | `collision` \| `goal_reached` \| `timeout` \| `stuck` \| `replan` \| `no_path` |

Metadata đi kèm mỗi trace: `episode_context_id`, `candidate_id`, `task_profile_id`, `sample_set` (`evaluation` \| `neighborhood`), `global_plan_length_m`, `global_plan_time_ms`, `peak_rss_mb`, `cpu_time_s`.

**Vi phạm trông như thế nào:** Metrics Engine cần một đại lượng mà trace không có, và ai đó "tiện tay" tính nó trong vòng lặp mô phỏng. Điều này phá tính tái lập và phá luôn khả năng tính lại metric từ trace cũ.

---

## HĐ-6 — Định nghĩa metric

Mỗi metric có **đúng một** định nghĩa, viết ở **đúng một** chỗ trong code (`metrics/definitions.py`), và **đúng một** vai.

| Metric | Định nghĩa | Vai |
|---|---|---|
| `success` | `goal_reached ∧ ¬collision ∧ ¬timeout` (theo `goal_tolerance_*`) | Gate G3 + Score O1 |
| `failure_reason` | `no_path` \| `collision` \| `timeout` \| `stuck` | Diagnostic |
| `collision_count` | số event `collision` | Gate G2 |
| `min_clearance` | `min(clearance_m)` trên toàn episode | Score O2 |
| `near_miss_rate` | `count(clearance_m < clearance_warning_m) / path_length_m` | Score O2 |
| `path_length_m` | `Σ ‖p_{i+1} − p_i‖` | trung gian |
| `L_ref` | độ dài đường ngắn nhất Dijkstra trên grid của **chính context đó** | trung gian |
| `path_efficiency` | `L_ref / path_length_m` ∈ (0, 1] | Score O3 |
| `T_ideal` | `L_ref / v_max` | trung gian |
| `time_efficiency` | `T_ideal / travel_time_s` | Score O3 |
| `smoothness` | `Σ (Δθ_i)²` | Diagnostic |
| `stop_and_go_count` | số lần `v` chạm 0 rồi > 0 trở lại | Diagnostic |
| `p99_latency_ms` | phân vị 99 của `planner_latency_ms` | Gate G4 + Score O4 |
| `peak_rss_mb` | đỉnh RSS của tiến trình | Gate G5 + Score O4 |
| `cpu_time_per_mission_s` | tổng CPU time | Score O4 |
| `tuning_trials_used`, `tuning_wall_clock_h`, `n_tunable_params` | khai báo lúc đăng ký candidate, có bằng chứng log | Score O4 |

**Quy tắc chống tính hai lần — khóa cứng:**

- `path_length_m` và `travel_time_s` chỉ vào điểm **thông qua** `path_efficiency` và `time_efficiency`, tức chỉ nằm ở O3.
- `travel_time_s` **không bao giờ** xuất hiện trong O4 ở chế độ `technical` (xem HĐ-9.3).
- `collision_count` chỉ ở Gate G2, **không** vào O2.
- `smoothness`, `jerk`, `stop_and_go` là Diagnostic ở MVP; muốn đưa vào Score phải sửa hợp đồng này (MAJOR).

---

## HĐ-7 — Feasibility Gates

Cổng chạy **trước** mọi phép chấm điểm. Ngưỡng lấy từ `task_profile.constraints` và `task_profile.hardware`, **không hardcode**.

| ID | Điều kiện | Nguồn ngưỡng |
|----|-----------|--------------|
| G1 | `no_path_rate ≤ 0.02` | constraints |
| G2 | `collision_count == 0` trên toàn bộ bộ `evaluation` **AND** `N_eval ≥ N_min` | xem 7.1 |
| G3 | `success_rate ≥ success_rate_min` | constraints |
| G4 | `p99_latency_ms ≤ control_period × 1000` | robot.control_period |
| G5 | `peak_rss_mb ≤ available_ram_mb` | hardware |
| G6 | `set(observation_requirements) ⊆ set(available_observations)` | task_profile |

### 7.1. G2 — số lần chạy tối thiểu

```python
N_min = ceil(3 / constraints.collision_probability_max)   # 0.01 ⇒ 300
```

Báo cáo bắt buộc kèm: `"0 va chạm quan sát trong {N} lần chạy; cận trên 95% dưới phân phối kịch bản đã mô phỏng: {3/N:.1%}"`. Chuỗi "an toàn" **bị cấm** xuất hiện cạnh kết quả G2 (có test kiểm tra chuỗi này trong CI).

### 7.2. G4/G5 — hai pha, và giới hạn của mỗi pha

| Pha | Đo ở đâu | Tư cách logic | `realtime_gate.status` |
|---|---|---|---|
| P1 sàng lọc | máy benchmark (nhanh hơn bo mạch đích) | **điều kiện cần**: trượt ở đây ⇒ chắc chắn trượt ở đích | `screened_on_host` |
| P2 xác nhận | chạy thẳng trên bo mạch đích, chỉ 2–3 candidate chung kết, ~20 episode | **điều kiện đủ** | `verified_on_target` |

**Cấm dùng hệ số quy đổi giữa hai máy.** A\* (nặng truy cập bộ nhớ) và DWA (nặng tính toán) co giãn khác nhau giữa x86 và ARM; một hệ số dùng chung là con số bịa. Nếu chưa chạy P2 thì trạng thái là `screened_on_host` và **không được phát biểu candidate đạt thời gian thực trên bo mạch đích**.

### 7.3. Môi trường đo

Mọi candidate chạy trên **cùng máy, cùng Docker image (ghi digest), cùng số CPU được cấp, cùng số luồng**. Thiếu điều kiện này thì cả phép so tương đối cũng vô nghĩa.

---

## HĐ-8 — Anchor và chuẩn hóa

### 8.1. Công thức duy nhất

```python
u(m, good, bad) = clip((m - bad) / (good - bad), 0.0, 1.0)
```

Thứ tự `good`/`bad` tự mã hóa chiều tốt/xấu — không cần công thức riêng cho metric "càng nhỏ càng tốt".

### 8.2. File anchor

```yaml
metric_anchors:
  version: v1.0

  success_rate:      {good: 1.00, bad: "${constraints.success_rate_min}"}
  path_efficiency:   {good: 1.00, bad: 0.65}
  time_efficiency:   {good: 1.00, bad: 0.35}
  min_clearance_m:   {good: "${robot.radius * 2.0}", bad: "${robot.radius * 1.05}"}
  near_miss_rate:    {good: 0.0,  bad: 0.5}
  p99_latency_ms:    {good: "${robot.control_period * 200}", bad: "${robot.control_period * 1000}"}
  peak_rss_mb:       {good: "${hardware.available_ram_mb * 0.25}", bad: "${hardware.available_ram_mb}"}
  cpu_time_per_mission_s: {good: 0.5, bad: 10.0}
  tuning_wall_clock_h:    {good: 0.0, bad: 40.0}
```

### 8.3. Ba luật

1. **Cấm min-max theo tập candidate.** Anchor phải ngoại sinh, nếu không thì thêm một candidate tệ sẽ đổi thứ hạng của các candidate cũ (*rank reversal*).
2. **Metric có cổng thì `bad` phải neo vào chính ngưỡng cổng** bằng tham chiếu `${...}`, không được là số cứng. Nếu không, file anchor và ràng buộc deployment sẽ trôi khỏi nhau mà không ai thấy.
3. `anchor_config_version` **bắt buộc** nằm trong manifest; và mỗi lần ra quyết định phải chạy kiểm tra độ nhạy anchor ±10%.

---

## HĐ-9 — Objective và Decision Utility

### 9.1. Bốn objective

```python
U_R = u(success)                                             # theo episode: 0 hoặc 1 → u()
U_S = 0.5*u(near_miss_rate) + 0.5*u(min_clearance_m)
U_E = 0.5*u(path_efficiency) + 0.5*u(time_efficiency)
U_C = β1*u(p99_latency_ms) + β2*u(peak_rss_mb)
    + β3*u(cpu_time_per_mission_s) + β4*u(engineering_cost)   # Σβ = 1
```

Mặc định `β = (0.30, 0.20, 0.20, 0.30)`. Ở chế độ `measured_only`, `β4 = 0` và ba β còn lại được chuẩn hóa lại về tổng 1.

### 9.2. Decision Utility

```python
U(c | T, R, H, P) = w_R*U_R + w_S*U_S + w_E*U_E + w_C*U_C     # Σw = 1
```

Tên gọi trong mọi UI, báo cáo và biến code là **`decision_utility`**, không phải `score`. Bốn preference profile mặc định:

| Profile | w_R | w_S | w_E | w_C |
|---|:---:|:---:|:---:|:---:|
| `kho_ban_dem` | 0.30 | 0.10 | 0.25 | 0.35 |
| `benh_vien_gio_cao_diem` | 0.25 | 0.50 | 0.10 | 0.15 |
| `pilot_demo` | 0.35 | 0.20 | 0.30 | 0.15 |
| `measured_only` | 0.30 | 0.25 | 0.25 | 0.20 |

### 9.3. Hai chế độ quyết định

| `decision_mode` | Dùng gì | `engineering_cost` tính bằng | Nhãn bắt buộc trên Decision Card |
|---|---|---|---|
| `technical` (mặc định) | chỉ số đo được | `tuning_wall_clock_h` (giờ) | "Khuyến nghị kỹ thuật — chỉ dựa trên số liệu đo được" |
| `business_adjusted` | + giả định khai báo | quy tiền rồi `/ N_missions` | "Đã hiệu chỉnh theo giả định kinh doanh do người dùng khai" + liệt kê toàn bộ giả định |

```yaml
business_profile:                 # chỉ dùng khi decision_mode = business_adjusted
  engineer_cost_per_hour: ...
  deployment_horizon_missions: 50000
  hardware_upgrade_cost: ...
travel_time_accounting: efficiency      # efficiency | monetized_cost — CHỌN MỘT
```

**`travel_time_accounting` là khóa chống tính hai lần.** `efficiency` ⇒ thời gian di chuyển chỉ ở O3. `monetized_cost` (chỉ hợp lệ ở chế độ business) ⇒ nó **chuyển** sang O4 dưới dạng throughput quy tiền và **rời khỏi** O3. Không bao giờ bật cả hai; validator phải chặn.

**Cấm dùng chữ "TCO"** ở bất kỳ đâu trong UI và báo cáo.

---

## HĐ-10 — Phân tích Pareto

### 10.1. Gắn nhãn, không xóa

Không candidate nào biến mất khỏi báo cáo. Ba nhãn:

| Nhãn | Điều kiện | Xử lý |
|---|---|---|
| `PARETO_FRONTIER` | không bị ai lấn át | ứng viên chính; là nguồn duy nhất của "phương án gần tương đương" |
| `LIKELY_DOMINATED` | có bằng chứng bị lấn át | vẫn chấm điểm, hiển thị mờ, không được đề xuất |
| `UNCERTAIN_DOMINANCE` | chưa đủ dữ liệu để kết luận | chấm điểm bình thường, kèm cảnh báo thiếu mẫu |

### 10.2. Điều kiện lấn át — non-inferiority

Với `ΔU_j = U_j(A) − U_j(B)` tính **ghép cặp theo từng episode**, `LCB` là cận dưới CI 95% bootstrap:

```
A lấn át B  ⟺  ∀j:  LCB₉₅(ΔU_j) ≥ −ε_j
              ∧  ∃k:  LCB₉₅(ΔU_k) >  +ε_k
```

Mặc định `ε_j = 0.02` cho cả bốn objective.

**Cấm dùng quy tắc "CI không nằm hoàn toàn dưới 0".** Nó lẫn *không có bằng chứng A tệ hơn* với *có bằng chứng A không tệ hơn*: dữ liệu càng ít, CI càng rộng, càng dễ tuyên bố lấn át — đúng chiều sai nguy hiểm nhất. Dạng trên có tính chất đúng: dữ liệu ít ⇒ `LCB` rất âm ⇒ không kết luận ⇒ candidate được giữ và gắn `UNCERTAIN_DOMINANCE`.

**Bài kiểm tra dùng cho mọi quy tắc loại bỏ trong dự án này:** *nếu không có dữ liệu thì quy tắc làm gì?* Câu trả lời đúng luôn là "không làm gì".

---

## HĐ-11 — Thống kê

### 11.1. Utility theo từng episode

`decision_utility` phải tính được **cho từng episode**, nếu không thì không có `ΔU` ghép cặp. Các thành phần hằng số theo candidate (`tuning_wall_clock_h`, `n_tunable_params`) đóng góp một lượng **không đổi** vào mọi episode của candidate đó — hợp lệ, vì trong hiệu số nó chỉ là một phép tịnh tiến.

### 11.2. Bootstrap ghép cặp

```python
deltas = [U_A[ctx] - U_B[ctx] for ctx in shared_contexts]   # bắt buộc cùng tập context
boot   = [mean(resample_with_replacement(deltas)) for _ in range(1000)]
ci     = (percentile(boot, 2.5), percentile(boot, 97.5))
```

Lấy mẫu lại **theo episode context**, không theo từng metric rời.

### 11.3. Nhãn và phân định

```
0 ∉ CI₉₅(ΔU vs hạng nhì)  ⇒  CLEAR_RECOMMENDATION
0 ∈ CI₉₅(ΔU vs hạng nhì)  ⇒  NEAR_EQUIVALENT
```

Cả hai trường hợp hệ **vẫn trả về đúng một khuyến nghị**. Ở `NEAR_EQUIVALENT`, thứ tự tiêu chí phụ khai báo trước và không được đổi giữa chừng:

```
1. U_C cao hơn (rẻ hơn)
2. IQR của decision_utility nhỏ hơn (ổn định hơn)
3. n_tunable_params ít hơn (dễ bảo trì hơn)
4. type = modular được ưu tiên hơn monolithic (dễ giải thích, dễ can thiệp)
```

Báo cáo tối thiểu: `median`, `IQR`, `CI₉₅(ΔU)`, `effect_size`, `n_episodes`. **Cấm báo cáo p-value trần trụi** mà không kèm effect size.

### 11.4. Cận trên va chạm

Chỉ tính trên bộ `evaluation`. **Cấm gộp bộ `neighborhood` vào** — các lần chạy trong cùng một biến thể tương quan với nhau, số mẫu hiệu dụng nhỏ hơn tổng số dòng, và `3/N` sẽ quá lạc quan.

### 11.5. Độ nhạy

| Kiểm tra | Cách làm | Ngưỡng cảnh báo |
|---|---|---|
| `weight_stability_margin` | quét trọng số quanh profile hiện tại | đổi khuyến nghị khi lệch < 10% ⇒ dán nhãn `SENSITIVE_TO_PREFERENCES` |
| `anchor_stability` | xê dịch mọi anchor ±10% | khuyến nghị đổi ⇒ cảnh báo |
| `robustness_margin` | tỷ lệ biến thể neighborhood giữ nguyên khuyến nghị | < 60% ⇒ hạ nhãn xuống `NEAR_EQUIVALENT` |

---

## HĐ-12 — Decision Card

```json
{
  "contracts_version": "1.0.0",
  "recommendation_scope": "MISSION_LEVEL | DEPLOYMENT_LEVEL | ROBUST_DEPLOYMENT_LEVEL",
  "experiment_scope": "full_stack_selection",
  "decision_mode": "technical | business_adjusted",
  "status": "CLEAR_RECOMMENDATION | NEAR_EQUIVALENT",

  "recommended": {"candidate_id": "...", "stack": "...", "params_ref": "..."},
  "alternative": {"candidate_id": "...", "reason": "lower compute cost, fewer parameters"},

  "gates": [
    {"candidate_id": "...", "G1": "pass", "G2": {"result": "pass", "observed": 0,
      "n_runs": 300, "upper_bound_95": 0.010, "note": "dưới phân phối kịch bản đã mô phỏng"},
     "G3": "pass", "G4": {"result": "pass", "status": "screened_on_host", "p99_ms": 23},
     "G5": "pass", "G6": "pass"}
  ],

  "objectives": {"U_R": 0.86, "U_S": 0.78, "U_E": 0.84, "U_C": 0.71},
  "decision_utility": 0.792,
  "pareto_label": "PARETO_FRONTIER",

  "evidence": {
    "delta_u_vs_second": 0.184,
    "ci95": [0.151, 0.216],
    "n_episodes": 300,
    "effect_size": 0.71,
    "weight_stability_margin": 0.49,
    "anchor_stability": "unchanged_at_±10%",
    "robustness_margin": 0.95
  },

  "declared_assumptions": null,
  "manifest_ref": "runs/2026-08-08/abc123/manifest.json",
  "approval": {"status": "PENDING", "by": null, "at": null, "comment": null}
}
```

Trường `alternative` **chỉ được lấy từ candidate mang nhãn `PARETO_FRONTIER`**.

---

## HĐ-13 — Manifest tái lập

Mọi lần ra quyết định ghi một `manifest.json`:

```json
{
  "contracts_version": "1.0.0",
  "git_sha": "...",
  "docker_image_digest": "sha256:...",
  "task_profile_id": "warehouse_a_v1",
  "anchor_config_version": "v1.0",
  "preference_profile": "kho_ban_dem",
  "decision_mode": "technical",
  "travel_time_accounting": "efficiency",
  "candidates": ["...", "..."],
  "episode_context_ids": {"evaluation": ["..."], "neighborhood": ["..."]},
  "benchmark_host": {"cpu": "...", "cores_allocated": 4, "threads": 1},
  "created_at": "..."
}
```

**Tiêu chí nghiệm thu:** đưa manifest cho một người khác, họ dựng lại được **cùng một Decision Card**, sai khác chỉ ở thời gian tường.

---

## HĐ-14 — Vai trò và phê duyệt

| Vai | Được làm | Không được làm |
|---|---|---|
| `engineer` | tạo task, đăng ký candidate, chạy benchmark, xem mọi bằng chứng | phê duyệt |
| `approver` | toàn bộ quyền của engineer, cộng Approve / Reject / comment | — |

- Audit log **chỉ ghi thêm**, không sửa, không xóa.
- Chỉ Decision Card ở trạng thái `APPROVED` mới xuất được `approved_config.yaml`.
- **Hệ thống ở chế độ sim-only:** không tồn tại đường dẫn kỹ thuật nào từ UI tới robot thật. Việc "triển khai" chỉ là xuất một file cấu hình.

Không cần IAM cấp doanh nghiệp. Hai vai trò, một bảng, một cột `role`.

---

## HĐ-15 — Lát cắt dọc và định nghĩa "xong"

### 15.1. Lát cắt dọc — mốc cứng: **hết tuần 2**

```
1 bản đồ · 1 cặp start/goal · 1 robot tham chiếu · 2 candidate stack · 30–100 episode ghép cặp
   → trace → metrics → gates → 4 objective → decision_utility → CI của ΔU → Decision Card (JSON)
```

Chưa cần: web UI, RBAC, MLflow, neighborhood, Pareto, độ nhạy.

**Tiêu chí đạt:**

1. Hai candidate chạy trên **đúng cùng** tập `episode_context_id` (kiểm tra bằng assert, không bằng mắt).
2. Chạy lại với cùng manifest ⇒ ra cùng `decision_utility` tới 6 chữ số thập phân.
3. Bảng gate in ra đủ sáu cổng kèm số lần chạy.
4. `ΔU` và CI 95% ghép cặp tính được và không phải NaN.
5. `L_ref` từ Dijkstra ≤ `path_length_m` ở **mọi** episode thành công. Vi phạm điều này nghĩa là `L_ref` hoặc bộ đếm quãng đường đang sai.

### 15.2. Không quay lại sửa phương pháp luận

Sau khi hợp đồng được ký, **chỉ sửa plan khi lát cắt dọc phát hiện một giả định sai** — ví dụ metric ra toàn 0, hai candidate cho kết quả giống hệt nhau, `L_ref` không khớp đường thực đi. Những thứ đó chỉ lộ ra khi chạy, không lộ ra khi bàn.

### 15.3. Định nghĩa "xong" cho mọi PR

- có test cho phần logic mới;
- không thêm metric nào ngoài `metrics/definitions.py`;
- không hardcode ngưỡng nào vốn thuộc `task_profile`;
- nếu đụng vào một hợp đồng ⇒ đã tăng `contracts_version` trong cùng PR.

---

## 16. Phân công và ký

| Module | Chủ sở hữu | Hợp đồng phải giữ |
|---|---|---|
| Sim core, planner, costmap | Dev A | HĐ-4, HĐ-5 |
| Batch Runner, Metrics, Decision Engine, API | Dev B | HĐ-3, HĐ-6, HĐ-7, HĐ-9, HĐ-10, HĐ-11 |
| Frontend, Decision Card, Approval | Dev C | HĐ-12, HĐ-14 |
| Schema, anchor, manifest | cả nhóm | HĐ-1, HĐ-2, HĐ-8, HĐ-13 |

```
Bố cục repo
  contracts/     CONTRACTS.md · schemas/*.json · metric_anchors.yaml
  sim/           SimBackend, robot model, costmap, collision
  planners/      global/ · local/ · policies/ · registry.py
  metrics/       definitions.py  ← nơi DUY NHẤT định nghĩa metric
  decision/      gates.py · objectives.py · pareto.py · utility.py · stats.py
  runner/        contexts.py · batch.py
  api/           fastapi app, rbac, approval
  web/           frontend
  runs/          trace parquet · manifest.json · decision_card.json
```

**Ký xác nhận đã đọc và đồng ý:**

| Tên | Vai | Ngày | Ghi chú / bảo lưu |
|---|---|---|---|
| | Dev A | | |
| | Dev B | | |
| | Dev C | | |

---

## 17. Danh sách cấm — dán lên tường

1. Xếp `A*` và `DWA` cùng một bảng.
2. Chạy hai candidate trên hai tập seed khác nhau.
3. Chuẩn hóa min-max theo tập candidate.
4. Ghi số cứng vào `bad` của một metric có cổng.
5. Kết luận "hòa" bằng cách so hai CI chồng lấn.
6. Dùng quy tắc lấn át "CI không nằm hoàn toàn dưới 0".
7. Gộp bộ `neighborhood` vào phép tính cận trên va chạm.
8. Nhân một hệ số quy đổi để suy p99 trên bo mạch đích.
9. Đếm thời gian di chuyển ở cả O3 lẫn O4.
10. Viết chữ **"an toàn"** hoặc **"TCO"** cạnh một con số của hệ thống.

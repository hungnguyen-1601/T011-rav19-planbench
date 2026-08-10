# CONTRACTS.md — Planner Selector

> **Phiên bản hợp đồng:** `contracts_version: 2.1.0`
> **Trạng thái:** cần cả nhóm đọc và ký ở mục 16. Phase 1 (schema gốc) đã hiện thực theo bản 1.1.0; bản 2.0.0 sửa G5 — xem lịch sử phiên bản ở mục 18.
> **Vị trí:** `contracts/CONTRACTS.md` ở gốc repo (trước đây là `docs/antongduy/CONTRACTS_1.md`).
> **Tài liệu mẹ:** `docs/antongduy/de-tai-moi-planner-selector.md`. Khi hai tài liệu mâu thuẫn, **CONTRACTS.md thắng** — plan là lý do, contract là luật.

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
candidate_id = sha256_short(
    canonical_json(
        {
            "type": type,
            "stack": {...},  # planners/controller hoặc policy, kèm name+version
            "params": params,  # đã sắp xếp khóa
            "observation_requirements": sorted(observation_requirements),
        }
    )
)[:12]
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

### 1.5. Khai báo tài nguyên (bắt buộc, phục vụ G5)

*(Thêm ở 2.0.0.)* Bộ nhớ của hai loại candidate bị chi phối bởi hai thứ khác nhau, nên khai theo hai cách khác nhau:

```yaml
# modular — bộ nhớ do SỐ LƯỢNG cấu trúc dữ liệu quyết định, sim đếm được chính xác
resource_profile:
  kind: structural
  target_implementation: cpp_ros2          # hiện thực sẽ chạy trên robot
  bytes_per_search_node: 40                # khai theo struct của hiện thực đích
  bytes_per_tree_node: 40
  bytes_per_costmap_cell: 1
  costmap_layers: 3
  fixed_overhead_mb: 8

# monolithic — bộ nhớ do TRỌNG SỐ MÔ HÌNH + runtime quyết định, sim không đo được
resource_profile:
  kind: artifact
  model_artifact_mb: 340
  runtime_footprint_mb: 2100               # PyTorch / TensorRT / ONNX runtime
  source: declared                         # declared | measured_on_target
```

**`resource_profile` không vào `candidate_id`.** Định danh (1.3) là hash của những gì đổi *hành vi*; khai lại `bytes_per_search_node` theo một hiện thực C++ khác không làm robot chạy khác đi một mét nào. Đưa nó vào hash sẽ tách một candidate đã chạy 300 episode thành hai candidate mồ côi chỉ vì sửa một con số kế toán bộ nhớ — và 1.3 là một trong ba thứ đóng băng sau tuần 1.

**Vi phạm trông như thế nào:** một candidate `monolithic` đăng ký với `source: declared` rồi được tuyên bố qua G5 như thể đã kiểm chứng. Với `kind: artifact`, `source: declared` **chỉ cho phép sàng lọc**, không cho phép kết luận đạt (HĐ-7.3).

### 1.6. Khai báo chi phí kỹ thuật (phục vụ O4 và tie-break)

*(Thêm ở 2.1.0.)* HĐ-6 nói ba đại lượng `tuning_trials_used`, `tuning_wall_clock_h`, `n_tunable_params` được "khai báo lúc đăng ký candidate, có bằng chứng log", nhưng bản 2.0.x không cho chúng một chỗ trong schema. Đây là chỗ đó:

```yaml
tuning:
  tuning_trials_used: 30
  tuning_wall_clock_h: 24.0        # engineering_cost ở chế độ technical (HĐ-9.3)
  n_tunable_params: 12             # tie-break bậc 3 (HĐ-11.3)
  evidence_log: artifacts/tuning/k2_optuna.log   # bằng chứng, bắt buộc
```

**Trường `tuning` có mặc định `null`** — một candidate chưa khai vẫn parse được (nó vẫn chạy được episode và vẫn qua được cổng). Nhưng `U_C` **không tính được** khi thiếu nó, và tầng objective phải từ chối thay vì thay bằng 0: coi "chưa khai" là "không tốn công" thì candidate lười khai luôn thắng ở O4.

**`tuning` không vào `candidate_id`**, cùng lý do với `resource_profile` (1.5): số giờ đã bỏ ra để tìm ra bộ tham số không làm robot chạy khác đi — bộ tham số tìm được thì có, và nó đã nằm trong hash qua `params`.

**Vi phạm trông như thế nào:** một candidate khai `tuning_wall_clock_h: 0` mà không có `evidence_log`, rồi thắng ở O4 nhờ "miễn phí". Trường bằng chứng là bắt buộc chính vì con số này là **tự khai** và nó đi thẳng vào điểm.

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
    dynamic_obstacles:           # traffic deployment khai — xem 2.3
      - name: forklift
        radius: 0.4
        seed_time_offset: 6.0    # BẮT BUỘC > 0 với motion tất định theo thời gian
        motion: {kind: periodic, start: {x: 12.0, y: 4.0},
                 end: {x: 12.0, y: 18.0}, period: 24.0}

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
    total_ram_mb: 8192
    ram_budget_breakdown:              # BẮT BUỘC — xem 2.4
      os_and_middleware_mb: 1536
      perception_stack_mb: 2048
      localization_mapping_mb: 819
      logging_and_reserve_mb: 512
    available_ram_mb: 3277             # = total − Σ breakdown, validator tự kiểm
```

### 2.2. Quy tắc mức tuyên bố

`claim_level` **do hệ thống tính ra, không do người dùng khai** — trường trong YAML chỉ là mức mong muốn, hệ tự hạ xuống nếu dữ liệu không đủ:

```
len(missions) == 1                          ⇒ mission
len(missions) >  1                          ⇒ deployment
len(missions) >  1  và đã chạy neighborhood ⇒ robust_deployment
```

**Vi phạm trông như thế nào:** Decision Card in `ROBUST DEPLOYMENT-LEVEL` trong khi `missions` chỉ có một phần tử.

### 2.3. Vật cản động thuộc environment, không thuộc candidate

*(Thêm ở 1.1.0. Bản 1.0.0 định nghĩa bộ `evaluation` là "mission × **lần hiện thực vật cản** × seed" ở HĐ-3.3 nhưng không nói vật cản động đến từ đâu — task profile không có, candidate cũng không.)*

`environment.dynamic_obstacles` khai population traffic mà deployment mong đợi (người, xe nâng, AMR khác). Nó nằm ở đây vì **mật độ traffic là thuộc tính của hiện trường, không phải của thuật toán**: để nó trên candidate thì một stack được đánh giá trong kho trống còn stack khác gặp giờ đổi ca, và bảng xếp hạng báo "thuật toán tốt hơn" cho một bài toán dễ hơn.

Environment **không có** vật cản động là hợp lệ (hiện trường tĩnh, hoặc chỉ nghiên cứu chất lượng đường toàn cục). Nhưng phải hiểu hệ quả thống kê: với planner tất định và không có traffic, mọi seed phát lại **cùng một episode**, nên 300 lần chạy mang lượng thông tin của một lần. Chỗ phải nói thẳng điều đó là bảng cổng (G2 giả định các lần chạy độc lập), không phải schema.

**Luật cứng — traffic phải thật sự đổi theo seed:**

```
motion.kind ∈ {waypoint, periodic, sudden_stop}  ⇒  seed_time_offset > 0
```

Ba motion đó là hàm thuần của thời gian, nên với `seed_time_offset = 0` chúng **bỏ qua seed hoàn toàn**: 300 seed phát lại một episode 300 lần, báo phương sai bằng 0, và đưa cho G2 một cận trên rule-of-three có **số mẫu hiệu dụng là 1** chứ không phải 300. Cận trên khi đó tuyên bố 1% trong khi bằng chứng không đỡ được gì cả — đúng chiều sai mà một phát biểu an toàn không bao giờ được phép mắc. `random_walk` lấy hướng từ seed episode sẵn nên không cần offset.

**Vi phạm trông như thế nào:** một profile có `motion.kind: waypoint` và `seed_time_offset: 0` được nạp thành công. Loader phải **từ chối** ngay lúc parse.

Tên obstacle phải **duy nhất** trong một environment: tên được trộn vào hash seed của từng obstacle, nên hai obstacle cùng tên sẽ di chuyển đồng bộ với nhau.

### 2.4. `available_ram_mb` là một quyết định phân bổ, không phải một phép đo

*(Thêm ở 2.0.0.)* Nó là phần RAM còn lại sau khi trừ hệ điều hành và mọi stack khác cùng chạy trên bo mạch. Vì vậy nó **phải đi kèm bảng chiết tính**, để người khác kiểm được và để khi sau này perception phình ra thì biết phải sửa ở đâu. Validator kiểm `total_ram_mb − Σ(breakdown) == available_ram_mb`, lệch quá 1% thì từ chối task profile.

**Vi phạm trông như thế nào:** `available_ram_mb: 2048` xuất hiện một mình, không ai giải thích được vì sao là 2048 chứ không phải 3277.

---

## HĐ-3 — Episode context và đánh giá ghép cặp

### 3.1. Định danh ngữ cảnh

```python
episode_context_id = sha256_short(
    canonical_json(
        {
            "task_profile_id": ...,
            "mission_id": ...,
            "environment_variant": ...,  # "nominal" hoặc id biến thể neighborhood
            "seed": int,
        }
    )
)[:12]
```

### 3.2. Luật ghép cặp — **không được vi phạm trong bất kỳ hoàn cảnh nào**

> **Mọi candidate trong một lần so sánh phải chạy trên đúng cùng một tập `episode_context_id`.**

Batch Runner sinh danh sách context **trước**, rồi lặp candidate bên trong context — không phải ngược lại:

```python
for ctx in contexts:  # vòng ngoài
    for cand in candidates:  # vòng trong
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

Metadata đi kèm mỗi trace: `episode_context_id`, `candidate_id`, `task_profile_id`, `sample_set` (`evaluation` \| `neighborhood`), `global_plan_length_m`, `global_plan_time_ms`, `peak_search_nodes`, `peak_tree_nodes`, `costmap_cells`, `peak_rss_mb`, `cpu_time_s`.

*(Ba trường `peak_search_nodes`, `peak_tree_nodes`, `costmap_cells` thêm ở 2.0.0 — chúng là toàn bộ đầu vào của `memory_estimate_mb` ở HĐ-7.3. Đây là lần duy nhất schema trace được mở rộng sau khi đóng băng, và nó được làm **trước** khi có file trace nào tồn tại; xem mục 18.)*

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
| `peak_search_nodes` | đỉnh số node trong open+closed của global planner | trung gian (G5) |
| `peak_tree_nodes` | đỉnh số node của cây RRT/RRT\* | trung gian (G5) |
| `costmap_cells` | `width × height` của costmap | trung gian (G5) |
| `memory_estimate_mb` | ước lượng cấu trúc, xem HĐ-7.3 | Gate G5 + Score O4 |
| `peak_rss_mb` | đỉnh RSS của tiến trình mô phỏng | **Diagnostic** — xem cảnh báo dưới |
| `cpu_time_per_mission_s` | tổng CPU time | Score O4 |
| `tuning_trials_used`, `tuning_wall_clock_h`, `n_tunable_params` | khai báo lúc đăng ký candidate, có bằng chứng log | Score O4 |

**Quy tắc chống tính hai lần — khóa cứng:**

- `path_length_m` và `travel_time_s` chỉ vào điểm **thông qua** `path_efficiency` và `time_efficiency`, tức chỉ nằm ở O3.
- `travel_time_s` **không bao giờ** xuất hiện trong O4 ở chế độ `technical` (xem HĐ-9.3).
- `collision_count` chỉ ở Gate G2, **không** vào O2.
- `smoothness`, `jerk`, `stop_and_go` là Diagnostic ở MVP; muốn đưa vào Score phải sửa hợp đồng này (MAJOR).
- **`peak_rss_mb` không bao giờ được đem so với `available_ram_mb`.** RSS của tiến trình Python gồm interpreter, numpy, bản thân simulator và TraceRecorder; Python cũng không trả bộ nhớ đã giải phóng về OS. Ngoài ra một object Python nặng gấp 5–20 lần struct C++ tương đương (node A\*: ~200 byte so với ~40 byte). Con số sai cả một bậc và sai theo chiều không đoán trước được. `peak_rss_mb` chỉ dùng để phát hiện rò rỉ bộ nhớ và so **tương đối** giữa các candidate chạy cùng môi trường.

---

## HĐ-7 — Feasibility Gates

Cổng chạy **trước** mọi phép chấm điểm. Ngưỡng lấy từ `task_profile.constraints` và `task_profile.hardware`, **không hardcode**.

| ID | Điều kiện | Nguồn ngưỡng |
|----|-----------|--------------|
| G1 | `no_path_rate ≤ 0.02` | constraints |
| G2 | `collision_count == 0` trên toàn bộ bộ `evaluation` **AND** `N_eval ≥ N_min` | xem 7.1 |
| G3 | `success_rate ≥ success_rate_min` | constraints |
| G4 | `p99_latency_ms ≤ control_period × 1000` | robot.control_period |
| G5 | `memory_estimate_mb ≤ available_ram_mb` | hardware + `resource_profile` |
| G6 | `set(observation_requirements) ⊆ set(available_observations)` | task_profile |

### 7.0. G6 — từ vựng quan sát là tập đóng

*(Thêm ở 1.1.0.)* G6 so hai tập **theo mặt chữ**. Nên từ vựng phải đóng: cả hai phía validate cùng một danh sách (`planbench_schemas.observations.KNOWN_OBSERVATIONS`), token lạ **fail lúc parse** chứ không fail lúc gate. Không có luật này thì candidate khai `lidar2d` gặp deployment khai `lidar_2d` sẽ bị loại ở G6 vì một lỗi chính tả, và Decision Card báo một sự không tương thích phần cứng **không tồn tại** — câu trả lời sai nhưng trông đúng.

Từ vựng chỉ gồm **perception runtime mà deployment phải sở hữu**: hiện tại `lidar_2d` và `human_state_estimates`. Bản đồ tĩnh **không** là một token: deployment cung cấp nó trong `environment`, nên mọi deployment đều có; đưa nó vào yêu cầu thì mọi candidate modular sẽ trượt G6 trên profile mà tác giả không nghĩ tới việc khai lại điều hiển nhiên. Thêm cảm biến = thêm một dòng vào danh sách, kèm khai chi phí bổ sung phía deployment (N6).

### 7.1. G2 — số lần chạy tối thiểu

```python
N_min = ceil(3 / constraints.collision_probability_max)  # 0.01 ⇒ 300
```

Báo cáo bắt buộc kèm: `"0 va chạm quan sát trong {N} lần chạy; cận trên 95% dưới phân phối kịch bản đã mô phỏng: {3/N:.1%}"`. Chuỗi "an toàn" **bị cấm** xuất hiện cạnh kết quả G2 (có test kiểm tra chuỗi này trong CI).

### 7.2. G4 — hai pha, và giới hạn của mỗi pha

| Pha | Đo ở đâu | Tư cách logic | `realtime_gate.status` |
|---|---|---|---|
| P1 sàng lọc | máy benchmark (nhanh hơn bo mạch đích) | **điều kiện cần**: trượt ở đây ⇒ chắc chắn trượt ở đích | `screened_on_host` |
| P2 xác nhận | chạy thẳng trên bo mạch đích, chỉ 2–3 candidate chung kết, ~20 episode | **điều kiện đủ** | `verified_on_target` |

**Cấm dùng hệ số quy đổi giữa hai máy.** A\* (nặng truy cập bộ nhớ) và DWA (nặng tính toán) co giãn khác nhau giữa x86 và ARM; một hệ số dùng chung là con số bịa. Nếu chưa chạy P2 thì trạng thái là `screened_on_host` và **không được phát biểu candidate đạt thời gian thực trên bo mạch đích**.

**Bảo lưu của nhóm (1.1.0): dự án không có bo mạch đích.** Không có Jetson hay board ARM nào để chạy pha P2, nên:

- `realtime_gate.status` **luôn** là `screened_on_host`; giá trị `verified_on_target` không xuất hiện trong bất kỳ Decision Card nào của dự án này;
- trường `target_p99_ms` luôn null;
- mọi Decision Card in nguyên văn **"G4 mới qua vòng sàng lọc — chưa xác nhận trên bo mạch đích"**;
- Target Verifier (§8 tài liệu mẹ) **ngoài phạm vi**.

Đây là một giới hạn được khai báo, không phải một lỗ hổng bị bỏ qua: phép sàng lọc pha P1 vẫn hợp lệ **theo đúng một chiều** (trượt trên máy nhanh ⇒ chắc chắn trượt trên máy chậm), và điều duy nhất bị mất là quyền tuyên bố chiều ngược lại. Khi nào có board thì gỡ bảo lưu này và tăng `contracts_version` MINOR.

### 7.3. G5 — bộ nhớ cũng hai pha, nhưng vì lý do khác G4

*(Viết lại ở 2.0.0. Bản 1.x đặt G5 là `peak_rss_mb ≤ available_ram_mb`.)*

G4 hai pha vì **tốc độ** máy khác nhau. G5 hai pha vì **ngôn ngữ và runtime** khác nhau — sim viết bằng Python, robot chạy C++/ROS2 hoặc một runtime học máy. Không được đo RSS rồi so với ngân sách bo mạch (HĐ-6).

**Điều may mắn khiến pha sàng lọc vẫn có giá trị:** với planner cổ điển, thứ quyết định bộ nhớ là **số lượng cấu trúc dữ liệu**, mà cái đó là hành vi thuật toán — sim đếm trung thực, không phụ thuộc ngôn ngữ. Ba bộ đếm đó là ba trường thêm vào metadata trace ở HĐ-5.

```python
# kind: structural
memory_estimate_mb = (
    peak_search_nodes * bytes_per_search_node
    + peak_tree_nodes * bytes_per_tree_node
    + costmap_cells * bytes_per_costmap_cell * costmap_layers
) / 1_048_576 + fixed_overhead_mb

# kind: artifact
memory_estimate_mb = model_artifact_mb + runtime_footprint_mb
```

Ví dụ kiểm tra bằng tay, bản đồ 40×25 m ở 0,05 m = 400.000 ô, `bytes_per_node = 40`:

| Thành phần | Ước lượng |
|---|---|
| A\* worst case (open+closed phủ toàn bản đồ) | ~16 MB |
| RRT\* 5.000 mẫu + KD-tree | ~1 MB |
| DWA 20×40 mẫu × 30 bước | ~0,6 MB |
| Costmap 3 layer | ~1,2 MB |

| Pha | Đo/ước lượng ở đâu | Tư cách logic | `memory_gate.status` |
|---|---|---|---|
| P1 sàng lọc | `memory_estimate_mb` từ bộ đếm trong sim | **điều kiện cần** | `estimated_from_structure` |
| P1 sàng lọc (artifact) | số khai lúc đăng ký candidate | **điều kiện cần** | `declared_by_author` |
| P2 xác nhận | đo RSS thật trên bo mạch đích, cùng lượt với P2 của G4 | **điều kiện đủ** | `verified_on_target` |

**Bảo lưu sim-only áp cho cả G5.** Dự án không có bo mạch đích (7.2), nên `memory_gate.status` **chỉ** nhận `estimated_from_structure` hoặc `declared_by_author`; `verified_on_target` không xuất hiện ở G5 cũng như ở G4.

**Ba luật:**

1. `bytes_per_*` phải khai theo **hiện thực đích**, không phải theo Python. Ghi rõ `target_implementation` để sau này kiểm được.
2. Với `kind: artifact` và `source: declared`, kết quả G5 **chỉ có giá trị loại bỏ**. Không được phát biểu candidate đó vừa bộ nhớ cho tới khi có `verified_on_target` — mà theo bảo lưu trên, dự án này không bao giờ có.
3. `available_ram_mb` là hàm bậc thang về mặt tiền: vượt ngân sách nghĩa là phải đổi cấp bo mạch, không phải "hơi tốn hơn". Cost Model không nội suy tuyến tính qua ngưỡng này.

**Vi phạm trông như thế nào:** Decision Card in `G5: pass` kèm `peak_rss_mb: 340` — con số RSS của tiến trình Python xuất hiện ở vị trí đáng lẽ phải là `memory_estimate_mb`.

### 7.4. Môi trường đo

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
  min_clearance:     {good: "${robot.radius * 2.0}", bad: "${robot.radius * 1.05}"}
  near_miss_rate:    {good: 0.0,  bad: 0.5}
  p99_latency_ms:    {good: "${robot.control_period * 200}", bad: "${robot.control_period * 1000}"}
  memory_estimate_mb: {good: "${hardware.available_ram_mb * 0.25}", bad: "${hardware.available_ram_mb}"}
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
U_S = 0.5*u(near_miss_rate) + 0.5*u(min_clearance)
U_E = 0.5*u(path_efficiency) + 0.5*u(time_efficiency)
U_C = β1*u(p99_latency_ms) + β2*u(memory_estimate_mb)
    + β3*u(cpu_time_per_mission_s) + β4*u(engineering_cost)   # Σβ = 1
```

Mặc định `β = (0.30, 0.20, 0.20, 0.30)`. Ở chế độ `measured_only`, `β4 = 0` và ba β còn lại được chuẩn hóa lại về tổng 1.

**Hai mức tổng hợp, và chúng không bằng nhau ở `U_R`.** *(Làm rõ ở 2.1.0 — phát hiện khi hiện thực Phase 3.3.)* Hệ tính objective ở hai mức, cả hai đều cần và không được lẫn:

| Mức | Đầu vào | Dùng ở đâu |
|---|---|---|
| **episode** | metric của **một** episode; `success` là 0 hoặc 1 | `decision_utility` theo từng episode ⇒ `ΔU` ghép cặp (HĐ-11.1, 11.2) |
| **set** | metric tổng hợp trên **cả tập** `evaluation`; `success_rate` là trung bình | khối `objectives` và `decision_utility` in trên Decision Card (HĐ-12) |

Vì `u()` là hàm affine **có clip**, hai mức trùng nhau ở mọi metric mà không episode nào chạm biên clip — và **lệch nhau ở `U_R`**, nơi biên clip luôn bị chạm: `u(success = 0) = 0` và `u(success = 1) = 1`, nên trung bình theo episode bằng đúng `success_rate` (0,967), trong khi mức set cho `u(0,967) = 0,34` với `success_rate_min = 0,95`. Con số **0,34 là con số của Decision Card** — đúng như ví dụ chạy tay §6.2 của tài liệu mẹ, và đúng ý đồ "chấm trên phần dôi so với ngưỡng".

Hệ quả bắt buộc: **`decision_utility` in trên card không phải trung bình của `decision_utility` theo episode**, và không được trình bày như thể là. Card in số mức set; thống kê ΔU chạy trên số mức episode. Cả hai đều tái lập được từ manifest, nên HĐ-13 không bị ảnh hưởng.

**Vi phạm trông như thế nào:** một `U_R` bằng 0,967 xuất hiện trên Decision Card — đó là mức episode bị đem in ở chỗ của mức set, và nó xóa mất toàn bộ ý nghĩa "dôi bao nhiêu so với ngưỡng khách hàng khai".

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
deltas = [U_A[ctx] - U_B[ctx] for ctx in shared_contexts]  # bắt buộc cùng tập context
boot = [mean(resample_with_replacement(deltas)) for _ in range(1000)]
ci = (percentile(boot, 2.5), percentile(boot, 97.5))
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
  "contracts_version": "2.1.0",
  "recommendation_scope": "MISSION_LEVEL | DEPLOYMENT_LEVEL | ROBUST_DEPLOYMENT_LEVEL",
  "experiment_scope": "full_stack_selection",
  "decision_mode": "technical | business_adjusted",
  "status": "CLEAR_RECOMMENDATION | NEAR_EQUIVALENT",

  "recommended": {"candidate_id": "...", "stack": "...", "params_ref": "..."},
  "alternative": {"candidate_id": "...", "reason": "lower compute cost, fewer parameters"},

  "gates": [
    {"candidate_id": "...", "G1": "pass", "G2": {"result": "pass", "observed": 0,
      "n_runs": 300, "upper_bound_95": 0.010, "note": "dưới phân phối kịch bản đã mô phỏng"},
     "G3": "pass",
     "G4": {"result": "pass", "status": "screened_on_host", "p99_ms": 23},
     "G5": {"result": "pass", "status": "estimated_from_structure",
            "memory_estimate_mb": 19, "available_ram_mb": 3277,
            "peak_search_nodes": 412000, "bytes_per_search_node": 40,
            "target_implementation": "cpp_ros2",
            "peak_rss_mb_diagnostic": 340},
     "G6": "pass"}
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
  "contracts_version": "2.1.0",
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
6. `peak_search_nodes` ≤ `costmap_cells` ở mọi episode. Vi phạm nghĩa là bộ đếm node đang đếm trùng, và `memory_estimate_mb` sai theo.

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

### Bố cục — logic và vật lý

Bản 1.0.0 vẽ một cây thư mục mới. Repo đã có bố cục `packages/ services/ apps/` với ~24k dòng Python, ~31k dòng TS và hơn 1.500 test chạy trên đó; đổi cây thư mục để khớp một hình vẽ là công việc thuần cơ học có rủi ro merge conflict mà không đổi hành vi. Nên **bố cục logic giữ nguyên làm cách nói, bố cục vật lý là repo hiện tại**, và bảng này là ánh xạ chính thức:

| Tên logic (cách nói trong tài liệu) | Vị trí thật |
|---|---|
| `contracts/` | `contracts/` — `CONTRACTS.md` · `schemas/*.json` · `metric_anchors.yaml` |
| `sim/` | `services/simulator/planbench_simulator/` |
| `planners/` | `packages/planning/planbench_planning/` (+ `ml/planbench_rl/` cho policy) |
| `metrics/` | `packages/metrics/planbench_metrics/` — `definitions.py` là nơi DUY NHẤT định nghĩa metric |
| `decision/` | `packages/decision/planbench_decision/` — `gates.py` · `objectives.py` · `pareto.py` · `utility.py` · `stats.py` · `pairing.py` |
| `runner/` | `packages/benchmark/planbench_benchmark/` — `contexts.py` · `batch.py` |
| `api/` | `apps/api/planbench_api/` |
| `web/` | `apps/web/` |
| `runs/` | `artifacts/runs/` — trace parquet · `manifest.json` · `decision_card.json` |

**Một ngoại lệ có lý do:** `EpisodeContext` (HĐ-3.1) nằm ở `packages/schemas/`, không ở `runner/`. Ba nơi cần nó — runner (sinh danh sách), trace recorder (metadata HĐ-5), decision engine (ghép cặp ΔU). Đặt trong `runner/` thì decision phải import runner, ngược chiều với bridge candidate (runner import decision) và thành vòng import. Phần **sinh** context vẫn ở `runner/contexts.py` đúng như bảng.

Hai định danh frozen của contract (`candidate_id`, `episode_context_id`) dùng chung primitive hash ở `packages/schemas/planbench_schemas/identity.py` — hai bản copy sẽ trôi khỏi nhau và làm một candidate bị tách thành hai.

**Ký xác nhận đã đọc và đồng ý:**

| Tên | Vai | Ngày | Ghi chú / bảo lưu |
|---|---|---|---|
| Tống Duy An | Dev B | 2026-08-09 | Ký bản 2.0.0 (đã ký 1.1.0 cùng ngày). Đã hiện thực Phase 1 (HĐ-1, HĐ-2, HĐ-3) và Phase 2.1 (HĐ-5) theo bản này. Bảo lưu: không có bo mạch đích (7.2, 7.3). |
| | Dev A | | |
| | Dev C | | |

> **Chưa đủ chữ ký.** Quy trình sửa hợp đồng (mục 0) cần ≥2 người approve. Bản 2.0.0 đang chờ Dev A và Dev C đọc — phần đáng đọc trước nhất là mục 18, nó liệt kê đúng những chỗ đổi so với bản mọi người đã xem. **2.0.0 là MAJOR**, nên theo mục 0 nó cũng đòi chạy lại lát cắt dọc; lát cắt dọc chưa tồn tại (Phase 4), nên nghĩa vụ đó rơi vào lần đầu chạy nó.

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
11. Khai vật cản động tất định với `seed_time_offset = 0` rồi đếm N lần chạy như N mẫu độc lập.
12. In `verified_on_target` khi dự án không có bo mạch đích (xem bảo lưu ở 7.2 và 7.3).
13. So `peak_rss_mb` của tiến trình Python với `available_ram_mb` của bo mạch.
14. Khai `available_ram_mb` mà không kèm bảng chiết tính.

---

## 18. Lịch sử phiên bản

| Phiên bản | Ngày | Loại | Nội dung |
|---|---|---|---|
| 1.0.0 | 2026-08-08 | — | Bản đầu, viết cùng `de-tai-moi-planner-selector.md`. |
| 1.1.0 | 2026-08-09 | MINOR | Bốn thay đổi, chi tiết dưới đây. |
| 2.0.0 | 2026-08-09 | **MAJOR** | Sửa G5: bỏ `peak_rss_mb ≤ available_ram_mb`, thay bằng `memory_estimate_mb`. Chi tiết dưới đây. |
| 2.0.1 | 2026-08-09 | PATCH | HĐ-8.2 và HĐ-9.1 gọi metric clearance là `min_clearance_m`, HĐ-6 gọi là `min_clearance`. Đổi hai chỗ đầu theo HĐ-6 — anchor key tra theo đúng tên metric, nên hai tên là một anchor không bao giờ khớp và một metric âm thầm không có thang. Phát hiện khi hiện thực 3.1. |
| 2.1.0 | 2026-08-10 | MINOR | Hai thay đổi, phát hiện khi hiện thực Phase 3.3. Chi tiết dưới đây. |

**Chi tiết 2.1.0** — đúng cơ chế HĐ-15.2 dự trù: chỉ sửa hợp đồng khi việc chạy code phát hiện một giả định thiếu. Không đụng vào ba định danh đóng băng.

1. **HĐ-1.6 mới — schema cho khai báo chi phí kỹ thuật** (thêm trường có mặc định `null` ⇒ MINOR). HĐ-6 đã yêu cầu `tuning_wall_clock_h` và `n_tunable_params` "khai lúc đăng ký candidate", nhưng không có chỗ nào trong schema nhận chúng — nên `U_C` (β4 = 0,30, đồng hạng lớn nhất) và tie-break bậc 3 của HĐ-11.3 đều không hiện thực được. Không vào `candidate_id`.
2. **HĐ-9.1 làm rõ — objective có hai mức tổng hợp, và chúng lệch nhau ở `U_R`.** Bản 2.0.x vừa chú thích `U_R = u(success)` "theo episode: 0 hoặc 1", vừa in `U_R = 0,34` trên card mẫu — hai phát biểu không thể cùng đúng, vì `u` có clip nên trung bình theo episode ra 0,967 chứ không ra 0,34. Bản này đặt tên và tách vai cho cả hai: mức episode nuôi `ΔU` ghép cặp (HĐ-11.1), mức set in trên card (HĐ-12). Đây là **làm rõ câu chữ** (không đổi công thức nào), nhưng đi cùng thay đổi 1 nên cả bump là MINOR.

**Chi tiết 2.0.0** — làm ngay trước Phase 2.1 (TraceRecorder), tức trước khi tồn tại một file trace nào.

1. **HĐ-7.3 viết lại — G5 là hai pha vì ngôn ngữ, không vì tốc độ.** Bản 1.x so RSS của tiến trình Python với ngân sách RAM của bo mạch C++/ROS2. Phép so đó sai cả một bậc và sai theo chiều không đoán trước được, nên nó là **đổi ngữ nghĩa của một cổng** ⇒ MAJOR. Thay bằng `memory_estimate_mb` tính từ số lượng cấu trúc dữ liệu — thứ sim đếm trung thực bất kể ngôn ngữ. `peak_rss_mb` xuống vai Diagnostic (HĐ-6).
2. **HĐ-1.5 mới — `resource_profile` bắt buộc trên candidate.** Hai dạng: `structural` (khai `bytes_per_*` theo hiện thực đích) và `artifact` (khai dung lượng model + runtime). Không vào `candidate_id`.
3. **HĐ-2.4 mới — `available_ram_mb` phải kèm `total_ram_mb` + `ram_budget_breakdown`**, validator kiểm tổng lệch ≤ 1%. Một ngân sách RAM không giải thích được là một con số bịa được gắn nhãn phần cứng.
4. **HĐ-5 — thêm 3 trường metadata**: `peak_search_nodes`, `peak_tree_nodes`, `costmap_cells`. Đây là đầu vào duy nhất của `memory_estimate_mb`.
5. Kéo theo: HĐ-6 (4 dòng metric mới + luật cấm so RSS), HĐ-7 bảng cổng G5, HĐ-8 anchor, HĐ-9 `U_C`, HĐ-12 khối `G5` của Decision Card, HĐ-15.1 tiêu chí nghiệm thu thứ 6, §17 cấm 13–14.

**Về việc đụng vào HĐ-5 — một schema đã đóng băng.** §0 cấm đổi trace schema sau tuần 1 vì mọi dữ liệu đã ghi sẽ mồ côi. Ở đây chưa có dữ liệu nào: TraceRecorder chưa được viết (Phase 2.1 là việc kế tiếp), `artifacts/runs/` rỗng. Đây là thời điểm cuối cùng thay đổi này còn miễn phí — sau khi 300 episode đầu tiên chạy xong, cùng thay đổi đó buộc phải chạy lại toàn bộ. Ba định danh vẫn **không đổi**: `candidate_id` (HĐ-1.3), payload hash của `episode_context_id` (HĐ-3.1), và các **cột** của trace (chỉ metadata được thêm).

**Chi tiết 1.1.0** — phát sinh khi hiện thực Phase 1 (schema gốc), tức đúng cơ chế mà HĐ-15.2 dự trù: chỉ sửa hợp đồng khi việc chạy code phát hiện một giả định thiếu.

1. **HĐ-2.3 mới — `environment.dynamic_obstacles`** (thêm trường có mặc định `()` ⇒ MINOR). Bản 1.0.0 định nghĩa bộ `evaluation` là "mission × lần hiện thực vật cản × seed" nhưng không nói vật cản động đến từ đâu. Kèm luật cứng `seed_time_offset > 0` cho motion tất định theo thời gian, và luật tên duy nhất.
2. **HĐ-7.0 mới — từ vựng quan sát là tập đóng.** Siết `available_observations` và `observation_requirements` từ chuỗi tự do thành một danh sách token cố định. Đây là một phép **thu hẹp** ngữ nghĩa: input trước đây parse được giờ có thể bị từ chối. Ghi rõ ở đây thay vì để nó lặng lẽ, dù chưa có dữ liệu nào bị ảnh hưởng (schema mới hoàn toàn, chưa lưu bản ghi nào).
3. **HĐ-7.2 — bảo lưu sim-only.** Dự án không có bo mạch đích; `realtime_gate.status` luôn `screened_on_host`, Target Verifier ngoài phạm vi.
4. **§16 — bảng ánh xạ bố cục logic → vật lý**, thay cho cây thư mục của 1.0.0. Kèm một ngoại lệ có lý do (`EpisodeContext` ở `schemas/`) và ghi chú primitive hash dùng chung.

Ba thứ **không đổi** ở 1.1.0, đúng như §0 yêu cầu: định danh candidate (HĐ-1.3), payload hash của episode context (HĐ-3.1), và schema trace (HĐ-5).

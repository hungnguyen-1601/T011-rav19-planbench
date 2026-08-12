# CONTRACTS.md — Planner Selector

> **Phiên bản hợp đồng:** `contracts_version: 6.4.0`
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
4. Cần ≥2 người trong nhóm approve. — **Tạm bỏ qua từ 2026-08-10, xem dưới.**

> **Ngoại lệ đang có hiệu lực — quy trình duyệt một người.** Từ `3.1.0`, hợp đồng được sửa và duyệt bởi **một người (An)**, không đợi đủ hai approve. Lý do: nhóm chưa vận hành đủ người ở giai đoạn này, và các bản từ `2.0.0` tới `3.0.0` đều được viết, hiện thực và nghiệm thu trong cùng một luồng làm việc — điều khoản ≥2 approve đã bị vi phạm im lặng qua sáu lần bump. Một điều khoản không ai theo làm mọi điều khoản còn lại mất trọng lượng, nên ghi ngoại lệ ra đây thay vì để nó tiếp tục bị bỏ qua.
>
> Điều **không** được nới cùng: mọi luật khác của mục 0 vẫn áp dụng nguyên vẹn — vẫn phải nêu rõ sửa hợp đồng nào và vì sao, vẫn bump semver đúng loại, và MAJOR vẫn bắt buộc chạy lại lát cắt dọc. Ngoại lệ này chỉ nói về **số chữ ký**, không nói về mức cẩn thận.
>
> Gỡ ngoại lệ khi nhóm có ≥2 người đọc được contract; lúc đó tăng PATCH và xóa khối này.

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

### 2.5. Nhiễu cảm biến và trượt bánh — cũng thuộc environment *(thêm ở 6.2.0)*

`environment.sensor_noise` khai **robot ở hiện trường này đo tệ và chấp hành lệch tới đâu**:

```yaml
sensor_noise:
  lidar_range_sigma_m: 0.02    # N5: sigma 2 cm
  wheel_slip_fraction: 0.02    # N5: trượt bánh 2%
```

Mặc định **cả hai bằng 0**, nên mọi profile viết trước bản này giữ nguyên hành vi tới chữ số float cuối. Bật lên là một thay đổi có chủ ý, nhìn thấy được ở profile và trên manifest.

**Vì sao nó ở environment:** biên độ nhiễu là tính chất của **hiện trường và của chiếc robot được triển khai ở đó**, không phải của thuật toán đang bị chấm. Một candidate được phép khai biên độ nhiễu riêng thì nó đang tự chọn đề thi — cùng lý lẽ với vật cản động ở 2.3.

**Vì sao phải có:** simulator không nhiễu **lạc quan hơn thực tế**, và cái giá của sự lạc quan đó đã đo được. Nguồn ngẫu nhiên duy nhất phụ thuộc seed từng là pha vật cản động, nên một stack **tất định** trên nhiệm vụ mà traffic không cắt tuyến sinh ra **cùng một episode cho mọi seed**: 100 episode mang lượng thông tin của một, và G2 in ra cận trên 3,0% dựng trên đúng một mẫu. Bật nhiễu là **sửa độ trung thực**, không phải cải thiện — và nó nhiều khả năng làm mọi con số **xấu đi**. Bán nó như cách để có bộ mẫu dùng được là lặp lại đúng loại lệch mà HĐ-15.3 đặt câu hỏi để chặn.

**Hai nguồn, hai bản chất — không được nhập một:**

| | Nhiễu LiDAR | Trượt bánh |
|---|---|---|
| Bản chất | sai số **đo** | sai số **chấp hành** |
| Chạm vào | chỉ `Observation` | chuyển động **thật** |
| Va chạm phán quyết trên | pose **thật** (không nhiễu) | pose thật **sau khi trượt** |
| Vì sao đúng | robot đo kém, thế giới không đổi | robot trượt thật, thế giới ghi đúng điều đã xảy ra |

Cụ thể: **nhiễu LiDAR không bao giờ được tới tầng va chạm.** Phán quyết chạm trên một pose đã nhiễu là mô phỏng một thế giới khác, chứ không phải một robot đo kém.

**Luật cứng — chỉ số hoá theo bước, không tiêu thụ tuần tự:**

```
draw = f(seed, stream, step)      # KHÔNG phải "giá trị tiếp theo của một generator"
```

Hai candidate chạy khác số bước và replan khác thời điểm. Nếu nhiễu được **rút tuần tự** từ một dòng chảy thì thứ tự tiêu thụ phụ thuộc hành vi candidate, và hai candidate sẽ gặp **nhiễu khác nhau** trong hai episode đội chung một `episode_context_id` — tức bất biến 3 bị phá bởi chính bản sửa sinh ra để giữ nó. Chỉ số hoá còn khiến việc hỏi lại cùng một bước trả về cùng đáp án, điều cần thiết vì `get_observation` có thể được gọi nhiều lần trong một bước.

Quỹ đạo hai candidate vẫn khác nhau — dĩ nhiên, vì lệnh điều khiển khác nhau. Đó là thế giới **phản ứng** với robot, không phải thế giới **thiên vị** robot.

**Vi phạm trông như thế nào:** một `NoiseModel` giữ generator làm trạng thái và gọi `.normal()` mỗi lần cần số; hoặc tầng va chạm đọc `lidar_ranges` thay vì pose thật.

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
| `evaluation` | lấy mẫu độc lập: mission × lần hiện thực **hiện trường** × seed | success rate, bằng chứng va chạm, mọi phân phối hiệu năng, `ΔU` |
| `neighborhood` | nhiễu có cấu trúc quanh profile gốc | **chỉ** đo độ ổn định của khuyến nghị |

*"Lần hiện thực hiện trường" gồm cả pha vật cản động lẫn hiện thực nhiễu cảm biến/chấp hành (6.2.0).* Cả hai đều là **cùng một hiện trường tự nó khác đi giữa hai lần chạy**, và đó chính là thứ bộ `evaluation` lấy mẫu.

**Câu chữ này được nới có kiểm soát, và đây là chỗ dễ hỏng nhất của cả HĐ-3.** Nới quá tay thì "biến thiên trong một deployment" và "bất định về chính deployment" bắt đầu trông giống nhau, và bộ `neighborhood` sẽ trôi vào bộ `evaluation`. Ranh giới:

| | Trả lời câu gì | Thuộc bộ nào |
|---|---|---|
| Nhiễu cảm biến, trượt bánh, pha vật cản | *"cùng hiện trường này, lần chạy này khác lần kia thế nào"* | `evaluation` |
| Task Neighborhood (bản đồ lệch, mission đổi) | *"nếu hiện trường tôi khai bị sai chút thì khuyến nghị có đổi không"* | `neighborhood` |

Cái đầu là biến thiên **trong** một deployment và **được** dùng cho cận trên va chạm. Cái sau là bất định **về chính** deployment, các lần chạy trong một variant tương quan với nhau, và HĐ-11.4 **cấm** đưa vào cận trên.

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

### 4.1. Lưới replan là một đặc quyền thông tin đã biết *(ghi ở 6.1.0)*

Khi robot bị chặn, `nav_stack._replan` dựng lưới quy hoạch tạm với **vị trí thật** của vật cản động nung vào (`_planning_grid(map_data, scenario, engine.dynamic_obstacles_now())`). Lý do hợp lý và phải giữ: một planner chỉ nhận bản đồ tĩnh sẽ replan ra đúng lộ trình vừa bị chặn, vì không đầu vào nào của nó thay đổi.

**Hôm nay điều này công bằng** vì mọi candidate chạy được đều là `modular` và nhận cùng một lưới. **Ngày adapter `MonolithicPolicy` tồn tại thì nó hết công bằng:** một policy end-to-end chỉ thấy `Observation`, còn global planner của stack modular thấy vật cản **thật sự ở đâu**. Đó đúng là đặc quyền thông tin mà G6 sinh ra để định giá, và nó sẽ ưu ái stack modular vì một lý do không liên quan tới chất lượng điều hướng.

**Luật:** trước khi bất kỳ candidate `monolithic` nào được chấm, đặc quyền này phải được gỡ, và lời giải hợp lệ là **replan từ `Observation`** — không phải cấp ground truth cho cả hai bên. Cấp cho cả hai chỉ đổi một phép so lệch thành hai phép đo sai.

Chốt chặn đang cài: `test_only_modular_stacks_can_run_today` sẽ đỏ đúng ngày adapter được thêm. Điều khoản này tồn tại vì một chốt chặn nói *"có gì đó đổi"*, còn một điều khoản nói *"phải giải quyết cái gì trước khi đi tiếp"*.

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
**Bảo lưu của nhóm (6.1.0): nền tảng không có bộ điều khiển ổn định hướng cuối.** `success` xét **cả** vị trí lẫn hướng theo `goal_tolerance_*`, nhưng simulator dừng episode ngay khi dung sai vị trí được đáp ứng, robot đang quay mặt đi đâu thì kệ. Một deployment đòi hướng vì thế chấm **mọi** candidate là trượt, vì một tính chất của nền tảng chứ không của planner nào.

Nên: `constraints.goal_tolerance_rad < π` bị **từ chối lúc nạp profile**, kèm thông điệp trỏ vào bảo lưu này. Nhiệm vụ có ràng buộc hướng nằm ngoài năng lực đánh giá của dự án — cùng hình dạng bảo lưu với việc thiếu bo mạch đích ở HĐ-7.2, và ghi lại vì cùng một lý do. Khi có bộ điều khiển hướng thì gỡ validator và tăng `contracts_version` MINOR.

Định nghĩa `success` **không đổi** — nhánh kiểm hướng trong `definitions.py` giữ nguyên và vẫn có test. Bảo lưu nói rằng hôm nay không profile hợp lệ nào chạm tới nhánh đó, không nói rằng nhánh đó sai.

**Vì sao là từ chối lúc nạp chứ không phải một ghi chú.** Cả hai profile tham chiếu đều từng mang một đoạn văn giải thích vì sao chúng viết π. Một đoạn văn chỉ bảo vệ được profile mà tác giả của nó đã đọc; profile tiếp theo do người chưa đọc viết. Đây là đúng bài học đã ghi ở 6.0.0, áp cho một chỗ khác.

- **`peak_rss_mb` không bao giờ được đem so với `available_ram_mb`.** RSS của tiến trình Python gồm interpreter, numpy, bản thân simulator và TraceRecorder; Python cũng không trả bộ nhớ đã giải phóng về OS. Ngoài ra một object Python nặng gấp 5–20 lần struct C++ tương đương (node A\*: ~200 byte so với ~40 byte). Con số sai cả một bậc và sai theo chiều không đoán trước được. `peak_rss_mb` chỉ dùng để phát hiện rò rỉ bộ nhớ và so **tương đối** giữa các candidate chạy cùng môi trường.

---

## HĐ-7 — Feasibility Gates

Cổng chạy **trước** mọi phép chấm điểm. Ngưỡng lấy từ `task_profile.constraints` và `task_profile.hardware`, **không hardcode**.

| ID | Điều kiện | Nguồn ngưỡng |
|----|-----------|--------------|
| G1 | `no_path_rate ≤ 0.02` | constraints |
| G2 | `collision_count == 0` trên toàn bộ bộ `evaluation` **AND** `N_eval ≥ N_min` | xem 7.1 |
| G3 | `success_rate ≥ success_rate_min` | constraints |
| G4 | `p99_latency_ms ≤ control_period × 1000`, gộp toàn bộ bước điều khiển của bộ `evaluation` — xem 7.2 | robot.control_period |
| G5 | `memory_estimate_mb ≤ available_ram_mb` | hardware + `resource_profile` |
| G6 | `set(observation_requirements) ⊆ set(available_observations)` | task_profile |

### 7.0. G6 — từ vựng quan sát là tập đóng

*(Thêm ở 1.1.0.)* G6 so hai tập **theo mặt chữ**. Nên từ vựng phải đóng: cả hai phía validate cùng một danh sách (`planbench_schemas.observations.KNOWN_OBSERVATIONS`), token lạ **fail lúc parse** chứ không fail lúc gate. Không có luật này thì candidate khai `lidar2d` gặp deployment khai `lidar_2d` sẽ bị loại ở G6 vì một lỗi chính tả, và Decision Card báo một sự không tương thích phần cứng **không tồn tại** — câu trả lời sai nhưng trông đúng.

Từ vựng chỉ gồm **perception runtime mà deployment phải sở hữu**: hiện tại `lidar_2d` và `human_state_estimates`. Bản đồ tĩnh **không** là một token: deployment cung cấp nó trong `environment`, nên mọi deployment đều có; đưa nó vào yêu cầu thì mọi candidate modular sẽ trượt G6 trên profile mà tác giả không nghĩ tới việc khai lại điều hiển nhiên. Thêm cảm biến = thêm một dòng vào danh sách, kèm khai chi phí bổ sung phía deployment (N6).

### 7.1. G2 — số lần chạy tối thiểu

```python
N_min = ceil(3 / constraints.collision_probability_max)  # 0.01 ⇒ 300
```

Báo cáo bắt buộc kèm: `"0 va chạm quan sát trong {N_distinct} lần chạy phân biệt; cận trên 95% dưới phân phối kịch bản đã mô phỏng: {3/N_distinct:.1%}"`. Chuỗi "an toàn" **bị cấm** xuất hiện cạnh kết quả G2 (có test kiểm tra chuỗi này trong CI).

**`N` ở đây là số episode PHÂN BIỆT, không phải số dòng.** Quy tắc số 3 giả định các lần chạy độc lập, và **số hàng trong bảng không phải bằng chứng của điều đó**: một stack tất định chạy trên nhiệm vụ mà traffic không bao giờ cắt ngang tuyến đường sẽ sinh ra **cùng một episode, một lần cho mỗi seed** — và một trăm bản sao của một episode chặn xác suất va chạm đúng bằng những gì một episode chặn được.

Phân biệt được xét trên **cái đã đo**, không trên `episode_context_id`: id là hash của **điều kiện**, nên nó duy nhất theo cấu tạo kể cả khi mọi điều kiện hoá ra không tạo khác biệt nào. Hai episode trùng nhau tới chữ số float cuối ở quãng đường, thời gian, khoảng hở, near-miss và va chạm thì không phải "gần nhau" — chúng là **cùng một lần chạy**.

`n_distinct_episodes` và `n_runs` **cả hai** đều phải in trên bảng cổng. In mỗi mẫu số của cận trên thì che mất một bộ bị phát lại; in mỗi số hàng thì đúng là cái đã tạo ra một tấm card tuyên bố cận trên 3,0% từ một candidate lái đúng một episode một trăm lần.

> **Vì sao điều khoản này được viết muộn.** Phase 1.4 đã dự đoán chính xác lỗi này khi đọc `DynamicObstacle` — *"planner tất định + không traffic ⇒ mọi seed cho cùng một episode... ghi vào contract rằng bảng cổng là nơi phải nói thẳng điều đó. **Đây là việc phải làm khi hiện thực G2, đã ghi lại để không rơi**"*. Ghi chú được viết, phép kiểm thì không, và G2 hiện thực ở Phase 3.2 mà không có nó. Lần chạy 100 episode đầu tiên (Phase 5.1) in ra cận trên 3,0% cho một bộ có số mẫu hiệu dụng bằng 1. **Không có gì trên tấm card đó trông sai cả** — đó là lý do luật này phải là code, không phải ghi chú.

**`collision_probability_max` là yêu cầu an toàn của hiện trường, không phải một núm vặn thời lượng chạy** *(ghi ở 6.1.0)*. Mũi tên chạy đúng một chiều: `rủi ro khai báo ⇒ N_min ⇒ số giờ`. Đọc ngược lại — chọn rủi ro cho vừa số giờ máy rảnh — là hạ tiêu chuẩn an toàn của khách hàng cho vừa lịch chạy của mình, và nó đã xảy ra một lần: kho tham chiếu có lúc khai 3% với lý do viết thẳng trong profile là *"vì run phải chia sẻ máy"*. Máy bận không phải một tính chất của nhà kho.

Chạy ít hơn `N_min` vẫn được phép và **không** cần sửa deployment: truyền số episode ở CLI, còn G2 báo `fail` kèm chuỗi *"chỉ {N} lần chạy phân biệt, dưới N_min = …; cận trên {3/N} còn lỏng hơn mức rủi ro đã khai"*. Phép đo giống hệt nhau ở cả hai cách. Khác biệt là hệ **tự khai chưa đạt** thay vì hạ chuẩn xuống cho khớp chính mình.

### 7.2. G4 — hai pha, và giới hạn của mỗi pha

**Phép gộp trên cả bộ: phân vị 99 của *mọi bước điều khiển*, không phải của episode tệ nhất.** *(Đổi ở 3.0.0 — xem mục 18.)* HĐ-6 định nghĩa `p99_latency_ms` theo từng episode; câu hỏi "cả bộ thì lấy con số nào" bản 2.x không trả lời, và hiện thực đầu tiên chọn **max theo episode** với lập luận "ngân sách là trần, một episode vượt là một vi phạm".

Lần chạy lát cắt dọc đầu tiên cho thấy lựa chọn đó sai. Năm trong ba mươi episode của `astar+dwa` được đo đúng lúc một bộ test chạy trên cùng máy; `p99` của chúng lên 119 ms so với ngân sách 100 ms, trong khi chính candidate đó trên máy rảnh đo được **5 ms** — nhanh hơn đối thủ đã qua cổng. **G4 đã loại một candidate vì tải của máy, không vì chi phí của nó.**

Đây không chỉ là bất tiện, nó **đảo ngược đúng cái tư cách logic** mà pha sàng lọc có: P1 là **điều kiện cần** — trượt trên máy benchmark nhanh ⇒ chắc chắn trượt trên bo mạch đích chậm hơn. Một lần trượt giả phá đúng suy luận đó, và không để lại triệu chứng gì trên card ngoài chữ `fail`.

Nên phép gộp là **phân vị 99 gộp trên toàn bộ bước điều khiển của cả bộ `evaluation`**:

- **Không phải max theo episode:** biến cổng thành hàm của khoảnh khắc kém may nhất trên máy đo.
- **Không phải trung bình các `p99` episode:** phân vị của phân vị không phải phân vị của cái gì cả.
- **Gộp không trọng số:** episode dài đóng góp nhiều mẫu hơn. Đúng ý: câu hỏi là *bao nhiêu phần trăm số bước điều khiển deployment thực sự chạy sẽ trễ hạn*, và episode dài thì thật sự chạy nhiều bước hơn.

Robust không phải mù: khi candidate chậm thật, đa số bước đều trễ và phân vị gộp nói đúng điều đó — có test cho cả hai chiều.

**G5 vẫn lấy max theo episode**, và khác biệt này có lý do: `memory_estimate_mb` được **đếm** chứ không **đo thời gian** — số cấu trúc dữ liệu nhân kích thước byte khai báo — nên nó không có nhiễu đo để sinh ra outlier, và một episode thật sự cần nhiều bộ nhớ hơn bo mạch có là một lý do loại thật.


| Pha | Đo ở đâu | Tư cách logic | `realtime_gate.status` |
|---|---|---|---|
| P1 sàng lọc | máy benchmark (nhanh hơn bo mạch đích) | **điều kiện cần**: trượt ở đây ⇒ chắc chắn trượt ở đích | `screened_on_host` |
| P2 xác nhận | chạy thẳng trên bo mạch đích, chỉ 2–3 candidate chung kết, ~20 episode | **điều kiện đủ** | `verified_on_target` |

**Ngưỡng G4 là yêu cầu của hiện trường, và candidate phải chạy được ở nhịp đó** *(ghi ở 6.1.0)*. Hai chỗ khác nhau cùng tên `control_period` và chúng đã được phép mâu thuẫn với nhau:

- `profile.robot.control_period` — **yêu cầu**: vòng điều khiển phải đóng nhanh cỡ nào. Đây chính là ngưỡng của G4.
- `control_period` của local controller — nhịp candidate **thực sự chạy**. `nav_stack` giữ nguyên lệnh cũ giữa hai tick, đúng như một luồng `/cmd_vel` thật.

Không có gì so hai cái đó. G4 đo chi phí của **một** lần gọi controller, nên một candidate đóng vòng ở 10 Hz trên deployment đòi 20 Hz **qua cổng** trong khi trượt mọi hạn chót thứ hai — cổng thấy một lần gọi rẻ, không thấy một lần gọi trễ.

**Luật:** nhịp của local controller phải **≤** `profile.robot.control_period`, kiểm **lúc khởi động** (`validate_control_rate`), cùng hình dạng "fail at startup" của HĐ-1.4. Controller không khai nhịp riêng thì chạy mỗi bước mô phỏng, luôn thoả.

**Hệ quả đã phải sửa:** cả hai profile tham chiếu từng khai `control_period: 0.1` (10 Hz) thay vì 20 Hz, lý do ghi trong file là *"DWA Python không tính nổi một bước điều khiển trong 50 ms"*. Tức **ngưỡng cổng bị nới gấp đôi vì candidate không qua nổi nó**. Lý do đó đã hết đúng mà không ai để ý: sau khi 3.0.0 đổi G4 sang p99 gộp và Phase 5.1 ghim nhân, p99 đo được là **10,81 ms** (`astar+dwa`) và **16,10 ms** (`rrtstar+dwa`) — thừa sức dưới 50 ms. Nhượng bộ đó là hoá thạch của hai lỗi đã được sửa từ trước.

Và nới nó **không** mua được gì về thời gian chạy: `simulation_dt = min(MAX_SIMULATION_DT, control_period)` với `MAX = 0,05`, nên 10 Hz và 20 Hz tích phân thế giới y hệt nhau. Không có động lực nào để nới lại, và có test khẳng định điều đó.

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

**Ghim nhân là việc của chương trình chạy, không của người vận hành** *(ghi ở 6.2.0)*. Đây là trục duy nhất trong hợp đồng này mà **không schema nào cưỡng chế được**: nó là tính chất của quy trình, không của mô hình dữ liệu. Và nó đã bị vi phạm một lần thật — contract 3.0.0 ghi lại việc A\* bị loại ở G4 vì tải của máy chứ không vì chi phí của chính nó.

Số đo được: cùng `rrtstar+dwa`, **59,30 ms** p99 gộp khi không ghim và **16,10 ms** khi ghim 2 nhân. Chênh 3,7 lần, lớn hơn khoảng cách giữa hai candidate.

Nên:

- Script chạy đánh giá **tự đặt affinity**, mặc định bật. Một biện pháp bảo vệ phụ thuộc vào việc ai đó nhớ gõ `taskset` chỉ bảo vệ những lần chạy mà người ta đã nhớ.
- **Ghim hết máy không phải là ghim.** Máy không đủ nhân để chừa lại phần cho hệ điều hành thì **từ chối ghim** và chạy không ghim kèm cảnh báo — một manifest ghi mask phủ toàn máy trông như đã được bảo vệ trong khi không có gì bảo vệ nó.
- Manifest ghi **mask thật sau khi đặt** (đọc lại từ OS, không phải mask định đặt) và ghi `affinity_source`: `script` khi run tự ghim, `inherited` khi nó nhận cái được cấp lúc khởi chạy. Một mask trần không phân biệt được hai chuyện đó, mà chúng trả lời hai câu khác nhau — run tự ghim thì tái lập được chính sự bảo vệ của nó.
- Chọn nhân nào **không cần khôn**: lấy `count` nhân đầu. Cách đánh số hyper-threading và bố cục P/E-core khác nhau ở mọi nền tảng nên mọi lựa chọn đều là đoán — nhưng lập luận công bằng không dựa vào đó: mọi candidate chạy trong **cùng một tiến trình dưới cùng một mask**, nên đặt sai chỗ là nhiễu **chung** và triệt tiêu trong hiệu số ghép cặp. Ghim mua sự cách ly khỏi tải khác, không mua vị trí tối ưu.
- **Hai run đánh giá không được chạy đồng thời trên cùng một máy** *(ghi ở 6.3.0, phát hiện khi chạy M4)*. Việc lấy `count` nhân đầu là tất định, nên hai tiến trình cùng ghim sẽ ghim vào **đúng cùng một mask** và giành nhau chính hai nhân đó — mỗi run trở thành tải nền của run kia, và G4 của cả hai đo một cái máy không tồn tại. Đây là hệ quả trực tiếp của việc ghim trở thành mặc định: trước đó hai run song song chỉ đơn giản là chậm hơn, giờ chúng làm hỏng số liệu của nhau. Chạy tuần tự, hoặc cấp mask rời nhau bằng `--no-pin` cộng `taskset` bên ngoài.

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
  version: v1.2

  success_rate:      {good: 1.00, bad: "${constraints.success_rate_min}"}
  path_efficiency:   {good: 1.00, bad: 0.65}
  time_efficiency:   {good: 1.00, bad: 0.35}
  min_clearance:     {good: "${robot.radius}", bad: 0.0}
  near_miss_rate:    {good: 0.0,  bad: 0.5}
  p99_latency_ms:    {good: "${robot.control_period * 200}", bad: "${robot.control_period * 1000}"}
  memory_estimate_mb: {good: "${hardware.available_ram_mb * 0.25}", bad: "${hardware.available_ram_mb}"}
  cpu_time_per_mission_s: {good: 0.5, bad: 10.0}
  tuning_wall_clock_h:    {good: 0.0, bad: 40.0}
  engineering_cost_per_mission: {good: 0.0, bad: "${constraints.cost_per_mission_max}"}
```

**Thang của `min_clearance` là thang MẶT robot, không phải thang tâm.** `clearance_m` (HĐ-5) và tầng va chạm của simulator cùng trả `khoảng_cách − bán_kính_robot − bán_kính_vật_cản`, nên `0.0` **là** biên va chạm và đại lượng âm khi robot đã nằm trong vật cản. Vì vậy `bad: 0.0` không phải một con số được chọn mà là định nghĩa của sàn thang đo, và `good` là đúng một bán kính khoảng trống bên trên nó. Bản `v1.0` neo ở `radius * 1.05` / `radius * 2.0` — đúng cặp số cho thang **tâm**, lệch đúng một bán kính.

### 8.3. Ba luật

1. **Cấm min-max theo tập candidate.** Anchor phải ngoại sinh, nếu không thì thêm một candidate tệ sẽ đổi thứ hạng của các candidate cũ (*rank reversal*).
2. **Metric có cổng thì `bad` phải neo vào chính ngưỡng cổng** bằng tham chiếu `${...}`, không được là số cứng. Nếu không, file anchor và ràng buộc deployment sẽ trôi khỏi nhau mà không ai thấy.
3. `anchor_config_version` **bắt buộc** nằm trong manifest; và mỗi lần ra quyết định phải chạy kiểm tra độ nhạy anchor ±10% — **từng metric một**, và **xê dịch bề rộng** của thang. Xem dưới: cách viết ngây thơ của luật này là một phép kiểm không bao giờ hỏng.

**Xê dịch ±10% nghĩa là đổi bề rộng, không phải nhân cả hai đầu.** Giữ `good` đứng yên, dời `bad` sao cho khoảng cách giữa hai đầu thành `f` lần: `bad' = good + (bad − good)·f`. Câu hỏi "thang có được chọn khéo không" chính là "khoảng cách từ điểm ăn 1 tới điểm ăn 0 có đúng không".

Nhân cả hai đầu là **sai, và sai vô hình**: nó vừa giãn vừa **tịnh tiến** thang, nên với metric bị chặn trên theo định nghĩa thì cả thang trôi ra khỏi miền. `success_rate` từ `{good: 1.00, bad: 0.95}` thành `{1.10, 1.045}` — không tỷ lệ thành công thật nào chạm tới đầu nào, mọi candidate clip về 0, `U_R` **chết** cho cả trường. Phép quét khi đó báo "khuyến nghị không đổi" — không đổi vì metric đã ngừng tồn tại.

**Và phải quét từng metric một, vì quét đồng loạt chứng minh được là vô nghĩa.** Với `bad' = good + (bad − good)·f`, mọi `u` đi qua **đúng một** phép affine `u ↦ 1 − (1−u)/f`; `decision_utility` là tổ hợp lồi của các `u` nên biến đổi y hệt; một phép tăng nghiêm ngặt áp cho **mọi** candidate như nhau thì **không đổi được thứ hạng**. Quét đồng loạt trả về "không đổi" trên **mọi** đầu vào — đó là số học, không phải bằng chứng.

Nên mỗi metric có anchor được quét riêng, cùng hình dạng với phép quét trọng số và cùng lý do: **mỗi lần chỉ một giả định dịch chuyển, nên một lần lật quy được trách nhiệm.** Kết quả không chỉ nói *có phải thang của ta quyết định hay không* mà nói *thang nào* — và đó mới là dạng dùng được: người đọc cãi lại được câu "khuyến nghị này phụ thuộc vào chỗ ta vạch ranh giới cho latency", chứ không cãi lại được câu "đổi ở −10%".
4. **Metric đo bằng tiền thì `bad` phải neo vào ngân sách người dùng khai** (`${constraints.cost_per_mission_max}`), không được là số cứng. Lý do khác luật 2 nhưng cùng một nỗi lo: vật lý quyết định thế nào là khoảng hở tệ, hình học robot quyết định thế nào là chật — nhưng **không có sự thật nào quyết định một nhiệm vụ tốn bao nhiêu tiền là đắt**. Viết số cứng ở đây là nền tảng tự đặt ngân sách hộ khách hàng rồi chấm điểm khách hàng theo ngân sách đó, tức đúng lỗi rank-reversal của luật 1 trong bộ áo khác.

**Anchor trỏ vào một trường tùy chọn mà deployment không khai thì không giải được, và không làm hỏng cả file.** Một file anchor phục vụ mọi deployment; một site chạy chế độ `technical` không có lý do gì phải khai ngân sách. Anchor đó được ghi lại là *unresolved* kèm lý do, và chỉ khi có ai chấm chính metric ấy thì hệ mới từ chối — **kèm tên trường còn thiếu**, không phải một câu "thiếu anchor" chung chung. Phân biệt bắt buộc: trường **có mà để trống** thì unresolved; trường **không tồn tại** là lỗi chính tả và vẫn fatal.

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
  currency: USD                   # bắt buộc — xem dưới
travel_time_accounting: efficiency      # efficiency | monetized_cost — CHỌN MỘT

constraints:
  cost_per_mission_max: ...       # bắt buộc ở chế độ business, cùng đơn vị `currency`
```

**Công thức của chế độ business, đúng N3:**

```
engineering_cost_per_mission = (tuning_wall_clock_h × engineer_cost_per_hour
                                + hardware_upgrade_cost) / deployment_horizon_missions
```

`hardware_upgrade_cost` đi cùng vì nó cùng bản chất: giá một lần của hệ thống con mà candidate đòi thêm ở G6, trả một lần rồi mọi nhiệm vụ sau đều dùng.

**β4 chấm trên đúng MỘT thang, không bao giờ cả hai.** `technical` chấm số giờ thô theo anchor `tuning_wall_clock_h`; `business_adjusted` **thay thế** số hạng đó bằng `engineering_cost_per_mission` chấm theo `${constraints.cost_per_mission_max}`. Đây là hai thang cho cùng một đại lượng, nên cộng cả hai là nhân đôi trọng số công tinh chỉnh ngay bên trong U_C — đúng loại lỗi §17 cấm 9 chặn ở giữa các objective.

**`currency` bắt buộc khai.** Nền tảng không quy đổi tiền tệ và không giả định đơn vị nào; nó mang chuỗi này lên card để ngân sách trần và chi phí không bị so với nhau qua hai đơn vị khác nhau mà không ai thấy.

**`travel_time_accounting` là khóa chống tính hai lần.** `efficiency` ⇒ thời gian di chuyển chỉ ở O3. `monetized_cost` (chỉ hợp lệ ở chế độ business) ⇒ nó **chuyển** sang O4 dưới dạng throughput quy tiền và **rời khỏi** O3. Không bao giờ bật cả hai; validator phải chặn.

> **`monetized_cost` vẫn chưa hiện thực, và lý do hẹp hơn "chưa làm".** Quy tiền công tinh chỉnh cần đúng hai khai báo mà `business_profile` đã có: một đơn giá giờ công và một chân trời. Quy tiền **thời gian di chuyển** cần một khai báo thứ ba mà chưa profile nào mang: một nhiệm vụ throughput đáng bao nhiêu tiền. Thiếu nó mà vẫn đẩy thời gian di chuyển ra khỏi O3 thì nó bị chấm bởi **không gì cả** — tệ hơn hẳn việc để nguyên ở O3, nơi thang đo ít nhất là vật lý. Từ chối thay vì xấp xỉ, đúng nguyên tắc chi phối cả chế độ này: câu nhãn "đã hiệu chỉnh theo giả định người dùng khai" không được đứng trên một con số tính dưới thang không ai khai.

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

**Sàn số episode — `n < 10` thì không ra phán quyết nào.** Bản thân khoảng tin cậy **không** đủ để vượt bài kiểm tra trên, và chỗ này lộ ra khi hiện thực. Bootstrap phân vị trên `n` điểm chỉ sinh được `n` giá trị khác nhau, nên phân vị 2,5 của nó không phải một ước lượng đuôi: với `n = 1`, mọi lần lấy lại đều ra đúng một điểm, "CI 95%" rộng bằng 0, `LCB` bằng chính hiệu số — và quy tắc **kết luận lấn át từ một episode với độ tin cậy tối đa**. Đúng chiều mà mục này cấm.

Máy móc khoảng tin cậy không tự diễn đạt được điều đó, vì **"không có phương sai" và "không có dữ liệu" trông giống hệt nhau** với nó — cùng điểm mù mà `DEGENERATE_SPREAD` của HĐ-11 phải chặn ở effect size. Nên sàn được **khai báo**, không suy ra: dưới `MIN_EPISODES_FOR_DOMINANCE = 10`, một cặp không lấn át nhau **và cũng không** được kết luận là không lấn át — nó rơi vào `UNCERTAIN_DOMINANCE`, đúng nghĩa của nhãn đó.

**Ba nhãn cần hai phép kiểm, không phải một.** "Không bị ai lấn át" **không** đồng nghĩa với "trên biên Pareto": một candidate chưa ai *chứng minh được* là bị lấn át có thể chỉ là chưa đo đủ. Nên `PARETO_FRONTIER` đòi **bằng chứng dương** rằng không đối thủ nào lấn át nó, đọc từ **cận trên** đúng cách lấn át đọc từ cận dưới:

```
A KHÔNG THỂ lấn át B  ⟸  ∃j: UCB₉₅(ΔU_j) < −ε_j      (B hơn hẳn ở đâu đó)
                       ∨  ∀k: UCB₉₅(ΔU_k) ≤ +ε_k      (A không hơn hẳn ở đâu cả)
```

Vế thứ hai là thứ cho phép hai candidate **thật sự tương đương, đo kỹ**, cùng lên biên: khoảng tin cậy của chúng ôm lấy 0, không bên nào hơn quá ε, và đó là một **kết luận** chứ không phải thiếu dữ liệu. Còn lại — không lấn át được ai, cũng chưa loại trừ được ai lấn át mình — là `UNCERTAIN_DOMINANCE`.

**Candidate đơn độc luôn là `UNCERTAIN_DOMINANCE`.** "Không ai lấn át nó" đúng một cách tầm thường khi không có đối thủ, mà trên card thì câu đó đọc như một phát hiện.

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
| `anchor_stability` | xê dịch bề rộng thang **từng metric một** ±10% (HĐ-8.3 luật 3) | khuyến nghị đổi ⇒ cảnh báo, **nêu tên metric và chiều** |
| `robustness_margin` | tỷ lệ biến thể neighborhood giữ nguyên khuyến nghị | < 60% ⇒ hạ nhãn xuống `NEAR_EQUIVALENT` |

**Cách quét trọng số.** Mỗi trọng số trong bốn được đi về **cả hai** cực của nó — 0, và 1 với ba cái còn lại về 0 — trong khi ba cái còn lại **giữ nguyên tỷ lệ với nhau**, để vector luôn tổng bằng 1 và để mỗi lần quét chỉ đổi **đúng một** giả định. Đổi hai thứ cùng lúc thì một lần lật không quy được cho cái nào. `weight_stability_margin` là **lệch nhỏ nhất trong tám hướng** làm đổi candidate được khuyến nghị, tính theo tỷ lệ quãng đường tới cực; **bằng 1,0 khi không hướng nào lật** — đó là một phát biểu thật, không phải một phép tìm kiếm bỏ cuộc: kể cả đưa một trọng số về 0 hoặc lên 1 thì khuyến nghị vẫn thế.

**Tiêu chí lật là candidate được khuyến nghị, không phải nhãn.** Một lần quét giữ nguyên candidate nhưng đi từ `CLEAR_RECOMMENDATION` sang `NEAR_EQUIVALENT` **không** đổi lời khuyên; tính nó là bất ổn định sẽ làm mọi biên trông tệ hơn thực tế.

**Quét lưới trước, chia đôi sau.** Khuyến nghị là hàm bậc thang theo độ lệch và **không** đảm bảo chỉ cắt một lần, nên chia đôi ngay từ đầu có thể bước qua một lần lật rồi báo cáo một sự ổn định không có thật. Lưới quyết định cái gì có thể bị bỏ sót — bước lưới phải nhỏ hơn ngưỡng 10% ở trên — còn chia đôi chỉ làm sắc nét một lần cắt mà lưới đã tìm ra.

**Kết quả quét phải tự khai là kết quả quét.** Một lần chấm dưới trọng số đã dịch không được lưu như một lần chấm dưới trọng số đã khai (`preference_profile` ghi `"<tên> (perturbed)"`), và chuỗi `anchor_stability` phải nói đúng biên độ đã dùng — một trường card ghi `±10%` về một phép quét 30% là mô tả một thí nghiệm không hề chạy. Cùng một luật với `anchor_config_version` mang dấu `±10%` ở HĐ-8.3.

**Phép quét anchor: xem HĐ-8.3 luật 3.** Bề rộng thang, từng metric một. Cả hai điều kiện đó đều là kết quả của việc hiện thực phát hiện ra hai cách viết ngây thơ đều hỏng — một cách giết metric bị chặn trên, một cách không bao giờ lật được gì. `changed_at` ghi **tên metric kèm chiều** (`p99_latency_ms-10%`), không ghi mỗi chiều.

---

## HĐ-12 — Decision Card

```json
{
  "contracts_version": "6.4.0",
  "recommendation_scope": "MISSION_LEVEL | DEPLOYMENT_LEVEL | ROBUST_DEPLOYMENT_LEVEL",
  "experiment_scope": "full_stack_selection",
  "decision_mode": "technical | business_adjusted",
  "decision_mode_label": "Khuyến nghị kỹ thuật — chỉ dựa trên số liệu đo được",
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

*(Thêm ở 2.2.0.)* **`decision_mode_label` in nguyên văn câu HĐ-9.3 bắt buộc cho chế độ đang chạy.** HĐ-9.3 đã yêu cầu nhãn này từ 1.0.0 nhưng ví dụ JSON không có chỗ cho nó, nên nó chỉ tồn tại dưới dạng lời dặn — và một lời dặn thì tầng render nào quên cũng không ai biết. Cho nó một trường bắt buộc là cách duy nhất để việc thiếu nhãn trở thành lỗi validate thay vì một tấm card trông bình thường.

**Ba trường chờ Phase 5, và giá trị đúng của chúng lúc này:**

| Trường | Giá trị khi chưa chạy phân tích tương ứng | Vì sao **không** để trống hay bịa |
|---|---|---|
| `pareto_label` | `UNCERTAIN_DOMINANCE` | HĐ-10.1 định nghĩa nhãn này đúng là "chưa đủ dữ liệu để kết luận". In `PARETO_FRONTIER` khi chưa chạy phân tích Pareto là tuyên bố một điều chưa kiểm |
| `alternative` | `null` | Chỉ được lấy từ candidate mang nhãn `PARETO_FRONTIER`; chưa có nhãn đó thì không có nguồn hợp lệ. Hạng nhì theo thống kê **không phải** `alternative` |
| `evidence.weight_stability_margin`, `evidence.anchor_stability`, `evidence.robustness_margin` | `null` | Phase 5.3 / 5.1. `null` đọc được là "chưa đo"; một con số mặc định đọc được là "đã đo và ổn" |

---

## HĐ-13 — Manifest tái lập

Mọi lần ra quyết định ghi một `manifest.json`:

```json
{
  "contracts_version": "6.4.0",
  "git_sha": "...",
  "docker_image_digest": "sha256:...",
  "task_profile_id": "warehouse_a_v1",
  "anchor_config_version": "v1.2",
  "preference_profile": "kho_ban_dem",
  "decision_mode": "technical",
  "travel_time_accounting": "efficiency",
  "sensor_noise": {"lidar_range_sigma_m": 0.02, "wheel_slip_fraction": 0.02},
  "candidates": ["...", "..."],
  "episode_contexts": {
    "evaluation": [
      {"task_profile_id": "warehouse_a_v1", "mission_id": "m1", "seed": 0,
       "environment_variant": "nominal", "sample_set": "evaluation",
       "episode_context_id": "..."}
    ],
    "neighborhood": []
  },
  "bootstrap": {"seed": 0, "n_resamples": 1000},
  "benchmark_host": {"cpu": "...", "cores_allocated": 2, "threads": 1,
                     "cpu_affinity": [0, 1], "logical_cores": 20,
                     "affinity_source": "script"},
  "created_at": "..."
}
```

**Tiêu chí nghiệm thu:** đưa manifest cho một người khác, họ dựng lại được **cùng một Decision Card**, sai khác chỉ ở thời gian tường.

*(Thêm ở 2.2.0.)* **Khối `bootstrap` là điều kiện cần của chính tiêu chí nghiệm thu ở trên.** `evidence.ci95` trên card đến từ một phép lấy mẫu lại ngẫu nhiên (HĐ-11.2); hai người chạy cùng manifest với hai seed khác nhau sẽ ra hai khoảng tin cậy khác nhau, và khác biệt đó **không phải** "thời gian tường". Bản 2.1.x thiếu trường này, nên tiêu chí nghiệm thu của HĐ-13 không thể đạt được bằng chính dữ liệu mà HĐ-13 yêu cầu ghi. `n_resamples` đi kèm vì đổi số lần lấy mẫu cũng đổi khoảng.

*(Thêm ở 6.2.0.)* **Khối `benchmark_host` ghi mask thật và ai đặt nó.** G4 đọc độ trễ theo đồng hồ tường, nên mức cấp CPU là một phần của phép đo chứ không phải chuyện bên lề — xem HĐ-7.4.

*(Thêm ở 6.4.0.)* **`constraints` phải có mặt trên manifest**, và lý do gần giống `sensor_noise` nhưng **hệ quả thì khác hẳn** — phân biệt này là nội dung chính của bản 6.4.0.

`episode_context_id` không băm **cả hai**. Nhưng:

| Đổi cái gì | Đổi cái gì trong thực tế | Episode đã ghi | Việc phải làm |
|---|---|---|---|
| `sensor_noise` | **thế giới** | thành episode của một thế giới khác ⇒ **vô hiệu** | **đổi `task_profile_id`** |
| `constraints` | **phán quyết** | vẫn **đúng nguyên** — chỉ được chấm bằng thước khác | **ghi vào manifest** |

Nên một ràng buộc **được phép sửa tại chỗ**, và khi đó manifest là thứ **duy nhất** đứng giữa hai tấm card bất đồng với nhau và không ai nói được vì sao. Không có trường này, cùng một profile id dưới `success_rate_min` 0,95 và 1,00 sinh ra **manifest giống nhau từng byte** trong khi bảng cổng khác nhau.

Một câu để nhớ: **`task_profile_id` định danh cái *thế giới*; manifest ghi cái đã biến phép đo thành phán quyết.**

*(Thêm ở 6.3.0.)* **`sensor_noise` phải có mặt trên manifest.** `episode_context_id` băm đúng bốn thứ (HĐ-3.1) và **biên độ nhiễu không nằm trong đó**. Nên hai run cùng seed khác `sigma` sinh ra **đúng cùng một tập context id** trong khi là **hai thí nghiệm khác nhau**. Không ghi biên độ thì manifest không phân biệt được chúng, và người dựng lại card sẽ dựng lại một card khác mà không có gì báo.

Hệ quả vận hành phải nói thẳng, vì nó là một cái bẫy im lặng: **sửa `sensor_noise` tại chỗ trong một profile mà giữ nguyên `id` sẽ khiến `--reuse-traces` phục vụ những episode ghi dưới biên độ cũ** — id khớp, không cảnh báo nào. Đổi biên độ ⇒ **đổi `task_profile_id`**, đúng như luật đã áp cho việc sửa traffic.

**Vi phạm trông như thế nào:** hai lần chạy cùng một manifest cho ra `ci95` khác nhau, và không có gì trong manifest giải thích được vì sao. Hoặc: hai thư mục run có cùng tập `episode_context_id` nhưng khác `sensor_noise`, và không ai nhận ra chúng là hai thí nghiệm.

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
5. `L_ref` từ Dijkstra ≤ `path_length_m` **+ `goal_tolerance_m`** ở **mọi** episode thành công. Vi phạm điều này nghĩa là `L_ref` hoặc bộ đếm quãng đường đang sai.

   *(Nới đúng bằng `goal_tolerance_m` ở 2.2.1 — phát hiện khi chạy lát cắt dọc lần đầu.)* `L_ref` đo tới **điểm** goal, còn episode thành công khi robot vào tới **quả cầu dung sai** quanh điểm đó và dừng lại ở đấy. Nên quãng đường thực đi hợp lệ ngắn hơn `L_ref` một lượng tối đa bằng bán kính quả cầu: trong lát cắt đầu tiên, `L_ref = 4,205 m` với đường đi `4,024 m` và dung sai `0,20 m` — không có gì sai, chỉ là hai đầu đo hai đích khác nhau. Phần dôi ngoài `goal_tolerance_m` thì vẫn là lỗi thật, và đó vẫn là thứ tiêu chí này bắt.

   **Hệ quả phải biết:** với episode dừng bên trong quả cầu, `path_efficiency = L_ref / path_length_m` vượt 1 và bị clip về 1,0 (HĐ-6). Sai lệch bị chặn bởi `goal_tolerance_m / L_ref` — 5% trên một nhiệm vụ 4 m, 0,5% trên nhiệm vụ 40 m của kho tham chiếu. Nghĩa là O3 **bão hòa** với những lộ trình gần tối ưu trên nhiệm vụ ngắn, và không còn phân biệt được ở đoạn đó. Chấp nhận có ý thức ở MVP; sửa đúng là đo `L_ref` tới quả cầu dung sai chứ không tới tâm, và đó là một thay đổi ngữ nghĩa của HĐ-6 (MAJOR) nên không làm trong bản này.
6. `peak_search_nodes` ≤ `costmap_cells` ở mọi episode. Vi phạm nghĩa là bộ đếm node đang đếm trùng, và `memory_estimate_mb` sai theo.
7. **Bộ kiểm công bằng xanh** *(thêm ở 6.1.0)* — `tests/test_fairness.py` (tầng chấm điểm mù với danh tính) và `tests/test_simulator_fairness.py` (hai candidate chạy trong cùng một thế giới). Đây là **điều kiện cần để công bố bất kỳ phép so nào**, không riêng lát cắt dọc.

   **Vì sao tiêu chí này được thêm muộn, và vì sao nó không thừa.** Sáu tiêu chí trên hỏi *"pipeline có chạy thông và tái lập được không"*. Không tiêu chí nào hỏi *"phép so này có công bằng không"*. Một định nghĩa "xong" như thế thưởng cho **một tấm card render được**: khi card không ra, đường ít kháng cự nhất là chỉnh đầu vào, và mọi lần chỉnh vẫn qua đủ sáu tiêu chí vì không tiêu chí nào nhìn vào đầu vào. Điều đó đã xảy ra thật — bốn thay đổi do kết quả dẫn dắt (tham số DWA của chính candidate đang đo, đổi mission, đổi traffic) lọt qua toàn bộ vòng nghiệm thu và chỉ bị bắt khi dev chặn lại hỏi.

### 15.2. Không quay lại sửa phương pháp luận

Sau khi hợp đồng được ký, **chỉ sửa plan khi lát cắt dọc phát hiện một giả định sai** — ví dụ metric ra toàn 0, hai candidate cho kết quả giống hệt nhau, `L_ref` không khớp đường thực đi. Những thứ đó chỉ lộ ra khi chạy, không lộ ra khi bàn.

### 15.3. Định nghĩa "xong" cho mọi PR

- có test cho phần logic mới;
- không thêm metric nào ngoài `metrics/definitions.py`;
- không hardcode ngưỡng nào vốn thuộc `task_profile`;
- nếu đụng vào một hợp đồng ⇒ đã tăng `contracts_version` trong cùng PR;
- **mọi hằng số mới hoặc đổi giá trị trong một profile phải trả lời được một câu** *(thêm ở 6.1.0)*:

  > **Con số này đến từ hiện trường, hay đến từ thứ máy/code của tôi chạy nổi?**

  Vế sau thì nó **không** thuộc file profile. Nó thuộc mục bảo lưu của hợp đồng này, ở đó nó thu hẹp phạm vi tuyên bố một cách nhìn thấy được, thay vì nới một ngưỡng ở chỗ không ai đọc.

  Câu hỏi này bổ sung cho câu đã có — *"nếu kết quả ra ngược lại, tôi có làm thay đổi này không?"* — và bắt một loại lệch khác mà câu kia bỏ sót. Bốn chỗ lệch tìm được ngày 2026-08-11 (`control_period` nới ngưỡng G4, DWA `7×15` chọn theo đồng hồ, `goal_tolerance_rad` tắt điều kiện hướng, rủi ro 3% suy từ giờ máy) **không cái nào thiên vị candidate nào** — cả bốn nới đều cho mọi bên, nên mọi phép kiểm đối xứng đều xanh. Chúng không phá tính công bằng; chúng phá tính đúng đắn.

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
| `decision/` | `packages/decision/planbench_decision/` — `gates.py` · `objectives.py` · `pareto.py` · `utility.py` · `stats.py` · `pairing.py` · `sensitivity.py` |
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
| 2.2.0 | 2026-08-10 | MINOR | Hai trường thêm, phát hiện khi hiện thực Phase 3.5. Chi tiết dưới đây. |
| 2.2.1 | 2026-08-10 | PATCH | HĐ-15.1 tiêu chí 5 nới đúng bằng `goal_tolerance_m`. Lát cắt dọc chạy lần đầu cho `L_ref = 4,205 m` với đường đi `4,024 m`: `L_ref` đo tới tâm goal, robot dừng ở rìa quả cầu dung sai. Không có lỗi nào, chỉ là tiêu chí viết thiếu một số hạng. Kèm ghi chú hệ quả: `path_efficiency` bão hòa ở 1,0 với lộ trình gần tối ưu trên nhiệm vụ ngắn. |
| 3.0.0 | 2026-08-10 | **MAJOR** | Đổi phép gộp của G4: `p99_latency_ms` lấy phân vị 99 **gộp trên mọi bước điều khiển** của bộ `evaluation`, thay cho max theo episode. Đổi ngữ nghĩa một cổng ⇒ MAJOR, cùng loại với 2.0.0. Chi tiết dưới đây. |

| 4.0.0 | 2026-08-10 | **MAJOR** | Ba thay đổi: ① anchor `min_clearance` đổi sang **thang mặt robot** (MAJOR, chi tiết dưới đây); ② **HĐ-8.3 luật 4** + anchor `engineering_cost_per_mission` + `constraints.cost_per_mission_max` + `business_profile.currency` ⇒ `business_adjusted` **tính được thật** (MINOR nếu đứng riêng); ③ ngoại lệ quy trình duyệt một người ở mục 0. Anchor file `v1.0` → `v1.2`. |

**Chi tiết 4.0.0** — phát hiện thứ sáu của lát cắt dọc (báo cáo Phase 4, mục 5.2).

`clearance_m` của HĐ-5 đo từ **mặt** robot; anchor `v1.0` viết theo thang **tâm**. Hai thang lệch đúng một bán kính. Trên kho tham chiếu, sai lệch này không làm điểm số hơi lệch mà làm nó chết hẳn: robot 0,52 m trong khe kệ 0,68 m đo được 0,04 m khoảng hở mặt, mọi episode nằm dưới `bad = 0,273` ⇒ `u = 0` ⇒ `U_S = 0` cho **mọi** candidate. Objective an toàn mang trọng số 0,10 và không phân biệt được gì.

| 6.0.0 | 2026-08-11 | **MAJOR** | Phát hiện bởi lần chạy 100 episode đầu tiên (Phase 5.1). ① **G2 tính cận trên trên số episode PHÂN BIỆT**, không phải số dòng; câu bắt buộc HĐ-7.1 đổi theo (`{N} lần chạy phân biệt`) và `n_distinct_episodes` là trường bắt buộc trên bảng cổng ⇒ MAJOR. ② HĐ-2: obstacle `periodic` phải có `seed_time_offset >= period` — offset một phần chu kỳ là cùng lỗi ở dạng im lặng hơn. ③ HĐ-12 thêm `delta_u_mean` để CI có chủ sở hữu nhìn thấy được. Chi tiết dưới đây. |
| 5.0.0 | 2026-08-10 | **MAJOR** | Hai đổi ngữ nghĩa, cùng một lượt. ① **HĐ-13 lưu bản ghi context đầy đủ** (`episode_contexts`) thay cho danh sách id (`episode_context_ids`) — bỏ một trường ⇒ MAJOR. ② **HĐ-8.3 luật 3 đổi cách quét anchor**: xê dịch bề rộng thang, từng metric một, thay cho nhân cả hai đầu của mọi anchor. Chi tiết dưới đây. |
| 4.2.0 | 2026-08-10 | MINOR | HĐ-10.2 viết đủ: **sàn `n < 10` không ra phán quyết** (bootstrap phân vị trên 1 điểm cho CI rộng 0 và kết luận lấn át với độ tin cậy tối đa — phát hiện khi chạy chính bài kiểm tra "không dữ liệu thì làm gì" của mục này), điều kiện **không-thể-lấn-át** đọc từ cận trên để tách `PARETO_FRONTIER` khỏi `UNCERTAIN_DOMINANCE`, và candidate đơn độc luôn `UNCERTAIN_DOMINANCE`. Hiện thực ở `decision/pareto.py` (Phase 5.2). `alternative` và `pareto_label` của HĐ-12 lần đầu có giá trị thật; cả hai trường đã tồn tại từ 1.0.0. |
| 4.1.0 | 2026-08-10 | MINOR | HĐ-11.5 viết đủ: cách quét trọng số (hai cực, ba cái còn lại giữ tỷ lệ, margin = lệch nhỏ nhất trong tám hướng, 1.0 khi không lật), tiêu chí lật là candidate chứ không phải nhãn, quét lưới trước chia đôi sau, kết quả quét phải tự khai, và cảnh báo thang chết. Hiện thực ở `decision/sensitivity.py` (Phase 5.3). Không đổi trường nào của HĐ-12 — ba trường `evidence` đã tồn tại từ 1.0.0 và tới bản này mới được điền. |

| 6.1.0 | 2026-08-11 | MINOR | Sáu điều khoản, tất cả cùng một loại lỗi: **ngưỡng bị nới cho vừa thứ code làm nổi, chứ không lấy từ hiện trường**. ① HĐ-7.2: ngưỡng G4 là yêu cầu hiện trường; nhịp local controller phải ≤ `robot.control_period`, kiểm lúc khởi động (`validate_control_rate`) — cả hai profile tham chiếu về 20 Hz. ② HĐ-7.1: `collision_probability_max` không phải núm vặn thời lượng; kho tham chiếu về 1%. ③ HĐ-6: bảo lưu không có bộ điều khiển hướng cuối, `goal_tolerance_rad < π` bị từ chối lúc nạp. ④ HĐ-4.1: lưới replan là đặc quyền thông tin đã biết, phải gỡ trước khi chấm candidate `monolithic`. ⑤ HĐ-15.1 tiêu chí **7**: bộ kiểm công bằng xanh là điều kiện cần để công bố bất kỳ phép so nào. ⑥ HĐ-15.3: câu hỏi bắt buộc *"con số này đến từ hiện trường, hay từ thứ máy tôi chạy nổi?"*. Không trường nào bị xoá, không ngữ nghĩa metric hay cổng nào đổi ⇒ MINOR. Chi tiết dưới đây. |

| 6.2.0 | 2026-08-11 | MINOR | HĐ-7.4: **ghim nhân là việc của chương trình chạy, không của người vận hành**. Script tự đặt affinity (mặc định 2 nhân, `--no-pin` để tắt); máy không đủ nhân thì **từ chối ghim** chứ không ghim hết máy — một mask phủ toàn máy trông như đã được bảo vệ. Manifest thêm `benchmark_host.affinity_source` (`script` | `inherited`), vì một mask trần không phân biệt được run tự ghim với run nhận mask lúc khởi chạy, mà chỉ cái đầu mới tái lập được chính sự bảo vệ của nó. Thêm trường có mặc định, không xoá gì ⇒ MINOR. |

| 6.3.0 | 2026-08-11 | MINOR | **Nhiễu cảm biến và trượt bánh theo seed** (plan M1). ① HĐ-2.5: `environment.sensor_noise` — thuộc hiện trường, mặc định 0, hai nguồn khác bản chất (LiDAR là sai số **đo** và không được chạm ground truth; trượt bánh là sai số **chấp hành** và phải chạm). Luật cứng: mọi draw là `f(seed, stream, step)`, **không** tiêu thụ tuần tự — rút tuần tự thì thứ tự phụ thuộc hành vi candidate và hai candidate gặp nhiễu khác nhau dưới cùng một `episode_context_id`. ② HĐ-3.3 nới "lần hiện thực vật cản" thành "lần hiện thực hiện trường", kèm bảng ranh giới với `neighborhood` để câu nới không mở đường gộp hai bộ mẫu. ③ HĐ-13: manifest phải ghi `sensor_noise`, vì biên độ **không** nằm trong payload băm của `episode_context_id` — hai run cùng seed khác sigma cho cùng tập id mà là hai thí nghiệm. Thêm trường có mặc định, không xoá gì ⇒ MINOR. |

| 6.4.0 | 2026-08-11 | MINOR | **HĐ-13: manifest phải ghi `constraints`.** Cùng gốc với `sensor_noise` ở 6.3.0 — `episode_context_id` không băm ngưỡng nào — nhưng hệ quả ngược nhau: đổi nhiễu đổi **thế giới** nên phải đổi `task_profile_id`; đổi ràng buộc đổi **phán quyết** nên episode cũ vẫn đúng và chỉ cần ghi vào hồ sơ. Không có trường này thì cùng một profile id dưới hai ngưỡng `success_rate_min` cho manifest giống nhau từng byte mà bảng cổng khác nhau. Phát hiện khi chốt `success_rate_min` cho `open_hall_v2`. Thêm một trường, không xoá gì, không đổi ngữ nghĩa metric hay cổng nào ⇒ MINOR. |

**Chi tiết 6.1.0 — bốn chỗ nới đều cho cả hai bên, nên không phép kiểm đối xứng nào bắt được.**

Lượt kiểm ngày 2026-08-11 (`docs/antongduy/notes/2026-08-11/tongduyan_xac-minh-lech-huong-muc-tieu.md`) tìm được bốn chỗ mà một hằng số mô tả thế giới đã được đặt theo thứ công cụ chịu nổi. Điểm chung của cả bốn: **không cái nào thiên vị candidate nào**. 53 test công bằng vẫn xanh với tất cả, vì chúng kiểm đối xứng, còn bốn chỗ này nới **đều cho cả hai bên**. Chúng không phá tính công bằng của phép so; chúng phá tính đúng đắn của thế giới mà phép so diễn ra trong đó.

Nặng nhất là `control_period`, vì nó vừa là ngưỡng G4 vừa là thứ có một **vòng lặp tự thưởng**: code chậm ⇒ khai chu kỳ dài ⇒ ngưỡng cổng rộng hơn. Kiểm lại thì vòng lặp đó không đóng — `simulation_dt` bị chặn ở 0,05 nên nới chu kỳ không mua được thời gian chạy — và nhượng bộ 10 Hz đã lỗi thời từ lúc 3.0.0 đổi sang p99 gộp và Phase 5.1 ghim nhân. Có test khẳng định cả hai điều đó, để động lực nới lại không bao giờ xuất hiện.

Bên dưới nó là một lỗ hổng chưa ai gọi tên: **G4 đo chi phí một lần gọi controller, không đo tần suất gọi.** Một candidate khai nhịp 10 Hz trên deployment đòi 20 Hz qua cổng như thường, giữ mỗi lệnh suốt hai chu kỳ của deployment. Đó là thứ khiến việc hạ deployment xuống 10 Hz "hoạt động" ngay từ đầu. `validate_control_rate` đóng nó lại.

**Đính chính một dòng của 6.0.0.** Mục ③ trong "ba sửa chữa" của 6.0.0 ghi rằng deployment tham chiếu được thêm `pallet_truck` trên hành lang chính. **Thay đổi đó đã bị hoàn nguyên và không còn trong repo**: rà lại bằng câu hỏi *"nếu kết quả ra ngược lại, tôi có làm thay đổi này không?"* cho thấy nó do kết quả dẫn dắt — thêm traffic vào cho tới khi bộ mẫu trông dùng được. Hai sửa chữa còn lại của 6.0.0 (đếm episode phân biệt ở G2, `seed_time_offset ≥ period`) đứng nguyên, và chúng mới là hai cái làm kết luận của hệ **yếu đi**. Lời giải đúng cho số mẫu hiệu dụng là nguồn ngẫu nhiên theo seed ở tầng simulator (nhiễu cảm biến), không phải bày traffic cho vừa tuyến đường.

**Chi tiết 6.0.0 — một tấm card tuyên bố cận trên va chạm 3,0% từ một mẫu duy nhất.**

Lần chạy 100 episode đầu tiên trên kho in ra, cho `astar+dwa`: *"0 va chạm quan sát trong 100 lần chạy; cận trên 95%: 3,0%"*. Sáu tiêu chí HĐ-15.1 xanh. Không có gì trên tấm card trông sai.

Đo lại thì cả 100 episode của A\* **giống hệt nhau tới chữ số float cuối** — utility per-episode có đúng 1 giá trị khác nhau trên 100. Số mẫu hiệu dụng là 1; quy tắc số 3 cho `3/1`, tức run đó không chặn được gì.

Truy nguyên nhân theo ba bước, mỗi bước loại một giả thuyết: seed **có** tới được vật cản (`_seed_time_shift` được áp trong `position_at`); xe nâng **có** đổi pha theo seed (y = 12,3…17,7 m tại t = 30 s); robot **có** đi xuyên hành lang của nó. Cái sai là **biên độ**: `seed_time_offset = 6 s` trên chu kỳ `24 s` chỉ quét một phần tư pha, robot cắt qua lane đó trong cửa sổ ~2 giây, và **0/100 seed đưa hai bên vào trong 2 m** — gần nhất 2,53 m, trong khi chạm nhau là 0,66 m.

Ba sửa chữa, ở ba tầng khác nhau, vì lỗi này lọt qua cả ba:

1. **Cổng (HĐ-7.1).** Mẫu số của cận trên là số episode **phân biệt**, xét trên cái đã đo chứ không trên `episode_context_id` — id là hash của *điều kiện*, nên nó duy nhất theo cấu tạo kể cả khi mọi điều kiện hoá ra không tạo khác biệt nào. Đếm id sẽ tìm thấy đúng 100 episode phân biệt trong chính lần chạy chỉ có một.
2. **Schema (HĐ-2).** Obstacle `periodic` phải dịch trọn ít nhất một chu kỳ. Thư viện scenario đã theo quy ước này trong comment từ đầu (*"one full cycle: seeds meet the pedestrian anywhere"*); nó chưa bao giờ được cưỡng chế, và profile viết sau không theo.
3. **Deployment tham chiếu.** Thêm traffic trên chính hành lang robot đi (`pallet_truck` tại x = 22, nơi tuyến đo được đi qua ở t ≈ 33 s), vì xe nâng nằm ở một đầu tuyến và giỏi lắm cũng chỉ gặp được thiểu số seed.

> **Vì sao điều này lọt được tới tận đây.** Phase 1.4 đã đọc `DynamicObstacle`, dự đoán chính xác lỗi này, viết validator cho `offset = 0`, và ghi lại: *"cùng vấn đề số mẫu hiệu dụng tồn tại ở đó... **Đây là việc phải làm khi hiện thực G2, đã ghi lại để không rơi**"*. Ghi chú được viết. Validator bắt `offset = 0` — và chính lời khuyên của nó, *"đặt seed_time_offset > 0 (a few seconds)"*, là cái profile đã làm theo. Phép kiểm ở G2 thì không bao giờ được viết.
>
> Bài học ghi vào đây vì nó lặp lại: **một ghi chú "nhớ làm ở phase sau" không phải một biện pháp bảo vệ.** Chỉ code mới là.

**Chi tiết 5.0.0 ① — HĐ-13 không tái lập được, suốt từ 1.0.0.**

Tiêu chí nghiệm thu của mục này là *"đưa manifest cho người khác, họ dựng lại đúng tấm card"*. Nó không đúng, và không đúng ngay từ bản đầu. Manifest lưu `episode_context_ids`, mà `episode_context_id` là **hash** của điều kiện (HĐ-3.1) và hash không đảo ngược được. Người cầm manifest biết *những episode nào* đã chạy nhưng không có `mission_id` cũng không có `seed` để tính lại metric — mà HĐ-6 cần cả hai.

Vì sao không ai thấy: mọi lần chạy của dự án đều dựng manifest và tính metric **trong cùng một tiến trình**, nơi object `EpisodeContext` vẫn còn trong bộ nhớ. Lỗ hổng chỉ lộ khi có người thật sự cầm file đi tính lại — tức đúng lúc Phase 6.2 đẩy run qua worker, và khi đó mọi manifest đã ghi đều mồ côi. Docstring của `compute_metrics` đã ghi lại điều này từ Phase 2.3 như một việc phải quyết ở 6.1; đây là lúc quyết.

Sửa: `episode_contexts` mang nguyên bản ghi. `episode_context_id` là computed field nên danh sách id vẫn còn — được **dẫn xuất**, không lưu hai lần. Nghĩa vụ giờ **được chạy chứ không được khẳng định**: `tests/test_vertical_slice.py` đọc `manifest.json` và trace từ đĩa rồi tính lại metric, vứt bỏ mọi object trong bộ nhớ, đúng như một người lạ sẽ làm.

**Chi tiết 5.0.0 ② — phép quét anchor hỏng theo hai cách ngược nhau.**

Bản viết ngây thơ của luật 3 ("xê dịch mọi anchor ±10%") hỏng theo cách thứ nhất: nhân cả hai đầu vừa giãn vừa **tịnh tiến** thang, nên `success_rate` từ `{1.00, 0.95}` thành `{1.10, 1.045}`, mọi tỷ lệ thành công thật clip về 0, `U_R` chết cho cả trường — và phép quét báo "khuyến nghị không đổi" vì metric đã ngừng tồn tại. Phát hiện bởi chính Phase 5.3 khi nó liệt kê metric thang chết.

Sửa sang "giữ `good`, dời `bad` để bề rộng thành `f` lần" thì lộ ra cách hỏng thứ hai, tệ hơn vì nó im lặng hoàn toàn: khi mọi thang cùng giãn một hệ số, mọi `u` đi qua **đúng một** phép affine `u ↦ 1 − (1−u)/f`, `decision_utility` là tổ hợp lồi nên biến đổi y hệt, và một phép tăng nghiêm ngặt áp cho mọi candidate như nhau **không đổi được thứ hạng**. Phép kiểm trả "không đổi" trên *mọi* đầu vào — số học, không phải bằng chứng.

Nên luật 3 giờ đòi **quét từng metric một**, cùng hình dạng với phép quét trọng số của HĐ-11.5 và cùng lý do: mỗi lần một giả định dịch chuyển thì một lần lật quy được trách nhiệm. `changed_at` ghi tên metric kèm chiều.


**Chi tiết 4.0.0 ② — chế độ `business_adjusted` tính được.** Trước bản này nó validate đủ nhưng từ chối tính, vì chi phí kỹ thuật quy tiền có đơn vị tiền/nhiệm vụ mà file anchor không có thang nào cho đơn vị đó. Bản này thêm thang — và chỗ đặt nó mới là phần đáng bàn.

Cám dỗ là viết `engineering_cost_per_mission: {good: 0.0, bad: 5.0}` vào `metric_anchors.yaml` cho xong. Làm vậy là **tự phá luật 1 của chính mục 8.3**: mọi anchor khác trong file lấy thang từ ngoài tập candidate — vật lý bài toán, hình học robot, hoặc một ngưỡng deployment đã khai. Không có sự thật nào nói một nhiệm vụ tốn 5 đồng là đắt. Con số đó sẽ là **nền tảng đặt ngân sách hộ khách hàng rồi chấm điểm khách hàng theo ngân sách mình vừa đặt**.

Nên thang tiền neo vào `${constraints.cost_per_mission_max}` — khách hàng khai, giống hệt cách metric có cổng neo vào ngưỡng cổng — và luật 4 cưỡng chế điều đó bằng validator, không bằng lời dặn. Kèm theo là cơ chế *unresolved* (mục 8.3): site chạy `technical` không khai ngân sách vẫn nạp được file, chỉ mất đúng một anchor, và chỉ biết khi có ai chấm chính metric ấy.

Hệ quả đáng giá nhất là thứ N3 hứa và tới bản này mới chạy được: **cùng bộ số đo, cùng bộ trọng số, hai chân trời khác nhau cho hai người thắng khác nhau.** 24 giờ tinh chỉnh là 0,0144/nhiệm vụ trên 50.000 nhiệm vụ (không đáng kể, candidate đã tinh chỉnh thắng) và 3,60/nhiệm vụ trên pilot 200 nhiệm vụ (áp đảo, candidate tham số mặc định thắng). Có test khẳng định đúng cặp bất đẳng thức đó.

**Vì sao MAJOR chứ không MINOR.** Anchor file có `version` riêng và HĐ-13 bắt manifest ghi `anchor_config_version`, nên có thể lập luận rằng đổi anchor không phải đổi hợp đồng. Không nhận lập luận đó ở đây: §8.2 in thẳng cặp số này trong hợp đồng, và mọi `U_S` — do đó mọi `decision_utility`, mọi ΔU, mọi nhãn CLEAR/NEAR_EQUIVALENT — tính dưới `v1.0` **không so sánh được** với bản tính dưới `v1.1`. Đó đúng là định nghĩa "đổi ngữ nghĩa". Dùng ranh giới file để né nghĩa vụ của mục 0 luật 3 (MAJOR ⇒ chạy lại lát cắt dọc) là lách chính cái luật đó, trong khi ở đây nghĩa vụ ấy rẻ: HĐ-5 đặt trace làm nguồn duy nhất nên "chạy lại" là tính lại từ cùng bộ trace trong vài giây.

**Chi tiết 3.0.0** — phát hiện bởi chính lát cắt dọc, đúng cơ chế HĐ-15.2 dự trù, và là **thay đổi phương pháp luận cuối cùng** trước khi mục 15.2 khóa lại.

`p99_latency_ms` của cả bộ `evaluation` giờ là phân vị 99 **gộp trên mọi bước điều khiển**, thay cho max của `p99` từng episode. Lý do đầy đủ ở 7.2; tóm tắt: lần chạy đầu tiên loại `astar+dwa` ở G4 vì 5/30 episode của nó tình cờ được đo lúc một bộ test chạy trên cùng máy (p99 119 ms), trong khi trên máy rảnh chính nó đo 5 ms. Một lần trượt giả ở G4 phá đúng tư cách logic duy nhất mà pha sàng lọc có (trượt ở máy nhanh ⇒ chắc chắn trượt ở bo mạch chậm).

Đây là **đổi ngữ nghĩa của một cổng** ⇒ MAJOR, cùng loại với 2.0.0. Theo mục 0 luật 3, MAJOR bắt buộc chạy lại lát cắt dọc và ghi kết quả trong PR — và vì phép gộp mới chỉ đọc lại trace đã ghi (HĐ-5: trace là nguồn duy nhất), việc "chạy lại" ở đây là tính lại từ cùng bộ trace, không phải mô phỏng lại.

Kéo theo: `evaluate_gates` nhận `pooled_p99_latency_ms` như một tham số, tính bởi `metrics/definitions.py`. Cổng so ngưỡng, Metrics Engine định nghĩa đại lượng — HĐ-15.3 giữ mọi định nghĩa metric ở đúng một chỗ, và phân vị gộp **không** dựng lại được từ `EpisodeMetricSet` (mỗi bản ghi chỉ mang một phân vị của một episode).

**Chi tiết 2.2.0** — cả hai là trường thêm có giá trị xác định ⇒ MINOR. Không đụng ba định danh đóng băng, không đổi công thức nào.

1. **HĐ-13 — khối `bootstrap` (`seed`, `n_resamples`).** Tiêu chí nghiệm thu của chính HĐ-13 là "người khác dựng lại được cùng một Decision Card, sai khác chỉ ở thời gian tường". `evidence.ci95` đến từ bootstrap ngẫu nhiên, nên nếu manifest không ghi seed thì tiêu chí đó **không thể đạt** bằng đúng dữ liệu HĐ-13 yêu cầu ghi. Phát hiện khi viết `manifest.json` thật ở Phase 3.5.
2. **HĐ-12 — trường `decision_mode_label`.** HĐ-9.3 bắt buộc in một câu nhãn cho mỗi `decision_mode` từ bản 1.0.0, nhưng ví dụ JSON của HĐ-12 không có chỗ cho nó, nên yêu cầu đó chỉ là một câu văn xuôi mà tầng render quên là không ai phát hiện. Cho nó một trường bắt buộc để việc thiếu nhãn thành lỗi validate.

Kèm theo (không phải thay đổi hợp đồng, chỉ ghi rõ điều đã đúng): bảng giá trị của `pareto_label`, `alternative` và ba trường `evidence` của Phase 5 khi các phân tích đó chưa chạy.

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

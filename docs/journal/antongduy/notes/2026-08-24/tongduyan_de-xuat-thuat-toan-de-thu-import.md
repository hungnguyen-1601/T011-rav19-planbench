# Đề xuất một thuật toán lạ để thử tính năng import, và cách kiếm đủ tài liệu

**Ngày:** 2026-08-24 · **Nhánh:** `tongduyan_verify-ai-analyst` · **Không sửa dòng code nào.**

Khảo sát để trả lời: nền tảng hiện *thật sự* import được tới đâu, nên chọn thuật
toán nào để phép thử nói lên điều gì, và cần cầm sẵn tài liệu gì trước khi bắt đầu.

---

## 1. Hiện trạng đường import — đọc mã, không đọc plan

Đường import **có thật và chạy được**, nhưng nó là đường *filesystem + Python*,
không phải tab web. Các mảnh:

| Mảnh | Ở đâu | Trạng thái |
|---|---|---|
| Manifest schema + parse + checksum | `packages/plugin_sdk/.../manifest.py` | xong |
| Discovery quét thư mục bundle, quarantine kèm lý do | `services/simulator/.../host/discovery.py` | xong |
| Preflight: `resolve_compatibility` → `CompatibilityReport` | `.../host/compatibility.py` | xong |
| Conformance suite cho tác giả plugin | `packages/plugin_sdk/.../conformance.py` | xong |
| CLI `list` / `check` cho operator | `.../host/cli.py` | xong, đã chạy thật (mục 5) |
| Runtime lane in-process + subprocess | `.../host/runtimes/` | xong |
| Chạy thật một episode với plugin ngoài registry | `tests/test_proof_plugins.py` | xong, 14 test |
| **API ghi manifest (`POST /algorithms/imports`)** | — | **chưa có** |
| **Tab UI import** | — | **chưa có** |
| **Plugin xuất hiện trong danh sách candidate của trang Decisions** | — | **chưa có** |

Bằng chứng cho ba dòng cuối: `apps/api/planbench_api/routers/algorithms.py` chỉ có
hai `GET`, và `algorithms_catalogue()` trong `services.py:770` trả thẳng
`list_algorithms()` — tức dict `ALGORITHMS` khai cứng trong
`packages/benchmark/planbench_benchmark/registry.py:335`. Plan
`plans/2026-08-20/tab-import-thuat-toan.md` (đợt I1–I5) là kế hoạch cho đúng ba
dòng đó, **chưa duyệt, chưa làm**.

**Hệ quả cho phép thử:** import một thuật toán mới hôm nay = đặt bundle vào một
thư mục, `cli check` xanh, rồi chạy episode bằng script Python theo đúng khuôn
`tests/test_proof_plugins.py`. Không có nút bấm nào trên web. Đó là phép thử
đúng nhất hiện có, và nó kiểm được toàn bộ phần khó (manifest, capability,
fairness, runtime, determinism); phần chưa kiểm được là phần chưa xây.

---

## 2. Đề xuất: **VFH+ (Vector Field Histogram Plus)** làm local planner

Ulrich & Borenstein, ICRA 1998, *"VFH+: Reliable Obstacle Avoidance for Fast
Mobile Robots"*.

### Vì sao chọn nó, chứ không phải thứ oai hơn

- **Nó thật sự lạ với repo này.** Kho hiện có A\*, RRT\* (global); DWA,
  DWA-predictive, pure pursuit, PPO (local). VFH+ là họ *reactive histogram* —
  khác hẳn họ *sampling rollout* của DWA. So sánh VFH+ với DWA là so hai triết
  lý tránh vật cản, không phải so hai biến thể của một thứ.
- **Chỉ đòi `lidar_2d`.** Đây là điểm quyết định. `lidar_2d` do
  `Lidar2DProvider` cấp, provenance `deployment`, **không phải oracle** — nên
  plugin sẽ ra `registered_and_runnable` với **production policy**, evidence
  class `production`. Nếu chọn thứ đòi `human_state_estimates` (ORCA, Social
  Force) thì nguồn duy nhất trong MVP là `GroundTruthTrackProvider` provenance
  `oracle`, production policy **từ chối ngay ở preflight** — phép thử đầu tiên
  sẽ dừng vì chính sách công bằng chứ không phải vì máy móc import. Để dành cho
  lần hai.
- **Tất định tự nhiên.** Không rút số ngẫu nhiên nào. Conformance check
  determinism (HĐ-4) sẽ xanh mà không phải nghĩ về seed. Lần import đầu không
  nên trượt vì một lý do không liên quan tới import.
- **Không dependency lạ.** Thuần Python + math; `python_dependencies` để rỗng
  hoặc `["numpy"]`. Không phải cài torch/g2o/ompl.
- **Pseudocode đầy đủ và không mơ hồ.** Bài báo 1998 in thẳng công thức, có bản
  cài đặt tham chiếu trong hệ sinh thái ROS để đối chiếu.
- **Cỡ vừa tay:** ~200–300 dòng, một buổi.

### Nó khớp contract của host thế nào

| Contract đòi | VFH+ đáp |
|---|---|
| `role` | `local` |
| `action_types` | `continuous-velocity@1` — VFH+ ra hướng lái + tốc độ, đúng hình |
| `requires_global_path` | `true` — dùng waypoint kế tiếp làm target direction |
| `requirements.all_of` | `["lidar_2d"]` |
| `robot_dynamics` | `differential-drive@1` |
| `step()` trả về | `{"linear_velocity": v, "angular_velocity": w}` |

### Điều cần biết về LiDAR của nền tảng trước khi cài

Đọc từ mã, không đoán:

- Mặc định **72 tia, phủ trọn 360°, `max_range = 5.0 m`**
  (`packages/schemas/planbench_schemas/scenario.py:78`).
- `LidarConfig` **từ chối** mọi `angle_span` khác `2π` — có validator chặn, kèm
  lý do dài trong `packages/schemas/planbench_schemas/sensor.py`. Nên đừng thiết
  kế VFH+ quanh một quạt quét 180°.
- Quy ước góc tia (`dwa_core.obstacle_points`, `common/dwa_core.py:198`):
  `increment = 2π/len(ranges)`, `start = pose.theta - π`, tia thứ *i* ở góc thế
  giới `start + i*increment`. **Tia trả về đúng `max_range` nghĩa là không trúng
  gì**, không phải "có vật ở 5 m" — bỏ tia đó đi, đừng đắp tường vào chỗ trống.
- Histogram VFH+ cần khoảng cách + độ tin cậy theo hướng; ở đây `range` thô là
  đủ, không cần grid tích luỹ như VFH gốc.

### Hai lựa chọn thay thế, để dành

| Thuật toán | Kiểm thêm được gì | Vì sao không chọn trước |
|---|---|---|
| **MPPI** (Model Predictive Path Integral, Williams et al. 2016) | Ép dùng `request.episode_seed` đúng cách, và khai `python_dependencies: ["numpy"]` — kiểm nhánh dependency của preflight | Ngẫu nhiên ⇒ nếu trượt determinism thì khó biết lỗi ở import hay ở cách rút seed |
| **ORCA / RVO2** (van den Berg et al. 2011) | Kiểm nhánh fairness: oracle refusal, evidence class, `registered_but_missing_provider` | Production policy từ chối ngay; chỉ chạy được ở research policy, kết luận yếu |

Nếu muốn thử **global** thay vì local: **Jump Point Search** (Harabor & Grastien,
AAAI 2011). Cùng đường đi với A\* trên grid đồng nhất nhưng expand ít node hơn
nhiều — nên nó là phép thử tốt cho *phần đo đạc* (`expanded_nodes`, thời gian
tính) hơn là cho *phần chất lượng đường*. Manifest chỉ đổi `role: "global"`,
`requirements.all_of: ["planbench://channel/planning-grid@1"]`,
`action_types: ["global-path@1"]` — y hệt `examples/plugins/corridor_planner`.

---

## 3. Tài liệu cần kiếm — theo từng thứ manifest và contract đòi hỏi

Không phải "đọc bài báo cho hiểu" mà là: mỗi ô trong manifest phải có một câu
trả lời rút từ một nguồn xác định.

### 3.1 Tài liệu về chính thuật toán (nguồn ngoài)

| Cần | Kiếm ở đâu | Dùng để điền |
|---|---|---|
| Pseudocode đầy đủ, đủ để cài mà không phải đoán | Bài báo gốc VFH+ (ICRA 1998; PDF công khai trên trang lab của Borenstein, hoặc IEEE Xplore) | thân `step()` |
| Ý nghĩa và **khoảng giá trị** từng tham số (`a`, `b`, kích thước bin, ngưỡng `τ`, `s_max`, robot radius, safety distance) | Bảng tham số trong bài báo + bản cài đặt tham chiếu | `config_schema.properties` |
| Thuật toán cần đầu vào gì (quạt quét, độ phân giải góc, tầm xa) | Mục sensor model của bài báo | `requirements.all_of` |
| Nó ra lệnh gì (vận tốc? hướng? gia tốc?) | Mục output/steering của bài báo | `supports.action_types` |
| Giả định về động học robot | Bài báo (VFH+ giả định vi sai / xe đẩy) | `supports.robot_dynamics` |
| Một bản cài đặt tham chiếu để đối chiếu khi nghi mình cài sai | `vfh_local_planner` trong hệ sinh thái ROS trên GitHub | kiểm chéo |

**Cách kiếm gọn nhất:** bài báo gốc + đúng **một** bản cài đặt tham chiếu. Nhiều
hơn một bản sẽ cho ba biến thể khác nhau và mất buổi để phân xử. Ghi rõ cài theo
bản nào ngay trong docstring của `planner.py`.

### 3.2 Tài liệu về nền tảng (nguồn trong repo — phần quan trọng hơn)

Đọc theo đúng thứ tự này:

1. **`docs/plugin_author_guide.md`** — 263 dòng, viết cho người ngoài repo. Đây
   là tài liệu chính. Mười mục, đủ để viết một bundle mà không đọc mã nền tảng.
   Chú ý §5 (determinism), §9 (nền tảng không làm hộ gì), §10 (in-process không
   phải sandbox).
2. **`examples/plugins/social_nav/`** — bản mẫu **local** gần với VFH+ nhất.
   Copy cấu trúc thư mục và `plugin.json` từ đây, đổi requirement từ
   `human_state_estimates` sang `lidar_2d`.
3. **`packages/plugin_sdk/planbench_plugin_sdk/requests.py` và `responses.py`** —
   xem chính xác `LocalResetRequest` (`global_path`, `robot`, `declared`,
   `episode_seed`) và `LocalStepRequest` (`state`, `channels`) có field gì.
   Guide mô tả đúng, nhưng đọc model là chắc chắn.
4. **`packages/plugin_sdk/planbench_plugin_sdk/capabilities.py`** — danh sách
   capability được phép khai. Khai sai một chữ là `UnknownCapabilityError` ngay
   lúc parse, kèm gợi ý gần đúng. Đang có: `lidar_2d`, `human_state_estimates`,
   và các URI `robot-state@1`, `global-path@1`, `legacy-observation@1`,
   `planning-grid@1`, `static-costmap@1`.
5. **`packages/planning/planbench_planning/common/dwa_core.py:198`
   (`obstacle_points`)** — quy ước góc tia LiDAR. Cài VFH+ mà lấy sai quy ước
   góc thì mọi vật cản nằm sai hướng và **không có lỗi nào được ném ra**.
6. **`tests/test_proof_plugins.py`** — khuôn để chạy episode thật. Copy hàm
   `_graph()`, `_load()` và phần `run_stack(...)`.

### 3.3 Thứ **không** cần kiếm

- Không cần đọc `nav_stack.py` hay simulation loop. Contract của plugin đứng
  giữa; đọc loop chỉ dẫn tới cám dỗ sửa nó.
- Không cần biết metrics/decision layer hoạt động ra sao để import.

---

## 4. Quy trình thực tế, bảy bước

Chạy từ gốc repo. **Trên Windows, `PYTHONPATH` ngăn bằng `;` chứ không phải `:`**
— author guide viết theo Linux, chép nguyên sẽ ra `ModuleNotFoundError` (đã dính
trong lúc khảo sát).

```powershell
$env:PYTHONPATH = "services/simulator;packages/schemas;packages/planning;packages/benchmark;packages/decision;packages/metrics;packages/plugin_sdk;packages/explanation"
```

1. **Dựng bundle** ngoài repo, ví dụ `E:\VinAI\plugins\vfh_plus\`:
   ```
   vfh_plus/
     __init__.py
     planner.py
     .planbench-plugin/plugin.json
   ```
2. **Viết `plugin.json`** — copy từ `examples/plugins/social_nav`, sửa `id`,
   `entry_point`, `requirements.all_of` thành `["lidar_2d"]`, `config_schema`
   theo bảng tham số của bài báo.
3. **Discovery thấy nó chưa** — chưa cần code chạy được:
   ```
   python -m planbench_simulator.host.cli --bundles E:\VinAI\plugins list
   ```
   `--bundles` thuộc lệnh gốc nên phải đứng **trước** subcommand.
4. **Preflight**:
   ```
   python -m planbench_simulator.host.cli --bundles E:\VinAI\plugins check org.<lab>.vfh-plus
   ```
   Muốn xanh: `registration: registered_and_runnable`, `evidence class:
   production`. Bất cứ dòng `why` nào xuất hiện là một blocker thật, đọc nguyên
   văn, đừng diễn giải lại.
5. **Viết `planner.py`** theo §3 của author guide: `name`, `control_period`,
   `reset(request)`, `step(request)`. Đọc channel qua vòng lặp `request.channels`
   tìm `envelope.capability == "lidar_2d"`; **không** với tới thứ chưa khai.
6. **Conformance trước khi chạy episode**:
   ```python
   from planbench_plugin_sdk import check_local_plugin
   report = check_local_plugin(manifest, lambda: VFHPlus(), step_request)
   assert report.passed, report.render()
   ```
   Bốn phép kiểm: determinism từ hai instance mới, optional thật sự optional,
   không đọc kênh chưa khai, không ghi vào request.
7. **Chạy một episode thật** bằng script theo khuôn `tests/test_proof_plugins.py`
   (`_graph(oracle=False)` → `resolve_compatibility` → `TrustedPythonRuntime().load`
   → `GraphBackedLocalPlanner` → `run_stack(map_data, scenario, hosted,
   channel_source=source)`). Kỳ vọng `run.algorithm == "astar+vfh_plus"`.

Sau bước 7 là hết đường có sẵn. Muốn thấy nó trên web và đem đi benchmark thì
phải làm đợt I1–I4 của plan `2026-08-20`.

---

## 5. Đã chạy thử CLI để xác minh, không phải chép từ doc

```
$ python -m planbench_simulator.host.cli --bundles examples/plugins list
astar@v1 [runnable] via builtin:astar
dwa@v1 [runnable] via builtin:dwa
greedy_reference_policy@v1 [runnable] via builtin:greedy_reference_policy
org.planbench.example.corridor@0.1.0 [runnable] via examples\plugins\corridor_planner\...
org.planbench.example.remote-wanderer@0.1.0 [runnable] via ...
org.planbench.example.social-nav@0.1.0 [runnable] via ...
ppo@v1 [runnable] via builtin:ppo
rrtstar@v1 [runnable] via builtin:rrtstar
```

```
$ ... check org.planbench.example.social-nav
  registration      : registered_but_missing_provider
  evidence class    : production
  runtime lane      : python_in_process
  provider graph    : ['...legacy-observation@1', 'lidar_2d', '...robot-state@1', '...static-costmap@1']
  why               : capabilities not offered by this deployment: ['human_state_estimates']
```

Hai điều đọc ra được từ đúng hai lệnh này:

- **Đường import sống.** Discovery, preflight, provider graph, lý do từ chối —
  tất cả trả lời thật.
- **Và nó đúng ở chỗ khó**: `social_nav` bị chặn vì deployment mặc định không
  cấp `human_state_estimates` (oracle không bật) — chứ không âm thầm hạ cấp
  xuống chạy bằng thứ khác. Đây chính là lý do mục 2 chọn một thuật toán chỉ cần
  `lidar_2d`.

---

## 6. Rủi ro biết trước

| Rủi ro | Dấu hiệu | Xử |
|---|---|---|
| `PYTHONPATH` sai separator trên Windows | `ModuleNotFoundError: No module named 'planbench_simulator'` | dùng `;` |
| Cài VFH+ theo quy ước góc LiDAR khác nền tảng | Robot né sai phía, **không lỗi nào được ném** | đối chiếu `dwa_core.obstacle_points` |
| Coi tia `max_range` là vật cản | Robot thấy tường vòng quanh, đứng im | bỏ tia `>= max_range - EPS` |
| Đọc capability chưa khai | `LookupError` → host biến thành safe stop, episode ghi lời từ chối | khai đủ trong `all_of` |
| Kỳ vọng thấy plugin trên web sau khi import | Không thấy gì | đúng như thiết kế hiện tại; cần đợt I1–I4 |

---

## 7. Hai bẫy tìm thêm khi đọc kỹ đường chạy

Bổ sung sau khi đọc `algorithm_host.py` và `graph_source.py`. Cả hai đều là chỗ
**author guide nói không khớp với lane in-process**.

### 7.1 `step()` phải trả `LocalPlanResult`, không phải dict

Author guide §3 dạy `return {"linear_velocity": ..., "angular_velocity": ...}`.
Nhưng `algorithm_host.py:192`:

```python
if not isinstance(result, LocalPlanResult):
    self.stats.invalid_outputs += 1
    return _safe_stop(f"... returned {type(result).__name__}, not a LocalPlanResult; safe stop")
```

Trả dict ở lane in-process ⇒ **mọi tick thành safe stop, không exception nào**.
Episode chạy hết mà robot không đi, và không có gì đỏ.

Dict chỉ đúng cho **subprocess lane** — worker tự convert
(`subprocess_lane.py:204`). Nên `examples/plugins/remote_wanderer` trả dict
(subprocess) còn `social_nav` trả `LocalPlanResult` (in-process): hai ví dụ khác
nhau vì hai lane khác nhau, không phải hai phong cách viết.

Hệ quả: lời hứa "một dependency" của guide **không đúng** cho local in-process —
phải import `LocalPlanResult` và `SimAction` từ `planbench_planning`.

### 7.2 `episode_seed` luôn bằng 0 trên đường channel-native

`GraphBackedLocalPlanner.reset` (`graph_source.py:165`) dựng `LocalResetRequest`
mà **không truyền `episode_seed`** ⇒ nhận default `0`. Chỉ
`HostBackedLocalPlanner` (`facades.py:109`) truyền thật.

VFH+ không rút số ngẫu nhiên nên không ảnh hưởng. Nhưng plugin nào có ngẫu nhiên
(MPPI, PRM) đi qua đường này sẽ dùng **một seed cho mọi episode**, và thống kê
ghép cặp sẽ đo một thứ khác với thứ nó khai.

---

## 8. Form "Upload model" trên UI **không phải** đường import thuật toán

An hỏi có thể import qua UI không. Trả lời: form hiện có là **cửa khác**.

`POST /api/v1/models/upload` (`routers/models.py:172`), docstring nguyên văn:
*"Upload a trained PPO checkpoint."*

- `inspect_archive` (`model_storage.py:173`) đòi zip chứa ít nhất một trong
  `{"data", "policy.pth", "pytorch_variables.pth"}` — đúng thứ Stable-Baselines3
  ghi ra. Không có thì từ chối.
- Model đã upload chỉ dùng được ở đúng một chỗ: `services.py:529`,
  `if algorithm.id != "astar+ppo" or not model_id: continue`.

Nên form đó nhận **bộ trọng số mới cho slot `ppo` sẵn có**, không nhận **thuật
toán mới**. VFH+ không có weights, không phải SB3 — không tổ hợp file nào lọt qua.

Các trường của form nói đúng điều đó: `Framework version`, `Training environment`,
`Metadata (.json)` mô tả observation/action schema của policy đã train. Không
trường nào hỏi role, capability hay entry point — ba thứ manifest plugin bắt buộc
phải có.

**Ranh giới thật:** UI cho người dùng mang vào *hành vi mới*, không cho mang vào
*thuật toán mới*. Tầng plugin host đã đủ năng lực nhận thuật toán mới nhưng chưa
có cửa nào từ web tới nó. Kế hoạch mở cửa đó:
`plans/2026-08-24/tab-import-thuat-toan-tren-ui.md`.

---

## 9. Việc chưa làm

Chưa viết bundle, chưa cài VFH+, chưa chạy episode. Ghi chú này chỉ là kết quả
đọc mã và chạy hai lệnh CLI đọc-thôi. Không sửa dòng code nào của dự án.

# Plan: Algorithm Host mở rộng cho global, local và monolithic planner

> Trạng thái: draft để duyệt kiến trúc, chưa triển khai code sản phẩm.
> Ngày lập: 2026-08-17 · **v2 cùng ngày** sau hai vòng phản biện (Claude
> phản biện → An phản hồi → chốt). Biên bản đối chất:
> `../../notes/2026-08-17/tongduyan_phan-bien-plan-algorithm-host.md`.
> Mục tiêu: mở simulator thành một algorithm host có thể tiếp nhận thêm thuật toán lâu dài mà không phải sửa simulation loop cho từng thuật toán mới.

## 1. Bài toán thật sự cần giải

PlanBench hiện thêm thuật toán dễ khi thuật toán mới khớp đúng interface đang có:

- `GlobalPlanner.plan(grid, start, goal) -> path` tại [packages/planning/planbench_planning/common/base.py](../../../../packages/planning/planbench_planning/common/base.py:31)
- `LocalPlanner.reset(global_path, robot)` và `compute(state, observation)` tại [packages/planning/planbench_planning/common/local_base.py](../../../../packages/planning/planbench_planning/common/local_base.py:33)
- `Observation` hiện là object đóng gồm pose, velocity, goal geometry, lidar ranges tại [packages/schemas/planbench_schemas/episode.py](../../../../packages/schemas/planbench_schemas/episode.py:64)

Ở lớp benchmark và decision, control plane đã có nền:

- `AlgorithmInfo` đã khai metadata stack, observation class và `requires_global_path` tại [packages/benchmark/planbench_benchmark/registry.py](../../../../packages/benchmark/planbench_benchmark/registry.py:135)
- vocabulary G6 hiện có `lidar_2d` và `human_state_estimates` tại [packages/schemas/planbench_schemas/observations.py](../../../../packages/schemas/planbench_schemas/observations.py:40)
- `_REQUIREMENTS` đã ánh xạ observation class sang requirement token tại [packages/benchmark/planbench_benchmark/candidates.py](../../../../packages/benchmark/planbench_benchmark/candidates.py:55)

Nhưng runtime vẫn còn cứng:

- engine vẫn dựng một `Observation` cố định qua `get_observation()` tại [services/simulator/planbench_simulator/engine.py](../../../../services/simulator/planbench_simulator/engine.py:266)
- local reset vẫn phải probe kwargs theo tên trong `_reset_local()` tại [services/simulator/planbench_simulator/nav_stack.py](../../../../services/simulator/planbench_simulator/nav_stack.py:356)
- monolithic policy đúng là đã chia sẻ cùng loop qua `run_policy()` và `run_stack()`, nhưng chỉ là reuse loop chứ chưa có host contract mở tại [services/simulator/planbench_simulator/nav_stack.py](../../../../services/simulator/planbench_simulator/nav_stack.py:804) và [services/simulator/planbench_simulator/nav_stack.py](../../../../services/simulator/planbench_simulator/nav_stack.py:835)

Vấn đề kiến trúc vì thế không phải “TEB chưa import được”, mà là:

> simulator mới có control plane cho capability, nhưng chưa có data plane và plugin boundary tương ứng.

## 2. Mục tiêu và tiêu chí đúng

Không đặt mục tiêu phi thực tế là “mọi thuật toán đều chạy được ngay”.

Tiêu chí đúng cho MVP và dài hạn:

1. Plugin có manifest hợp lệ thì đăng ký được, kể cả khi chưa runnable.
2. Thiếu capability, provider, runtime, action adapter hoặc dynamics phải bị phát hiện trước episode.
3. Thêm một thuật toán mới không buộc sửa `run_stack()` hoặc `engine.get_observation()`.
4. Thuật toán cũ tiếp tục chạy qua legacy adapter mà không drift outcome, trace và candidate identity.

## 3. Quyết định kiến trúc

Xây `AlgorithmHost` ở trên runtime hiện tại, không thay loop hiện có trong MVP.

Kiến trúc đích:

```text
Simulation Kernel
  -> Provider Graph
  -> Authorized Channel Bundle
  -> Algorithm Host
  -> Global / Local / Monolithic Plugin
  -> Action Adapter
  -> Simulation Kernel
```

Ba lớp tách biệt bắt buộc:

1. Manifest và requirement declaration: thuật toán tự khai nó cần gì.
2. Provider resolution: host quyết định dữ liệu đó đến từ đâu.
3. Fairness policy: host quyết định nguồn nào được phép dùng trong benchmark/deployment đó.

## 4. Nguyên tắc thiết kế

1. Đăng ký được không đồng nghĩa chạy được.
2. Core không đoán requirement của plugin.
3. Plugin không được nhận `Engine`, `Scenario` hay callback world truth trực tiếp.
4. Capability phải mở rộng được bằng namespace, không quay lại enum đóng.
5. Không có coercion âm thầm giữa action, dynamics hay observation.
6. Provenance, fairness, accounting và fingerprint là một phần của host contract, không phải hậu kiểm.
7. Backward compatibility phải đi trước proof plugin mới.

## 5. Hợp đồng kiến trúc cần có

### 5.1 Static plugin manifest

Mỗi plugin mang manifest tĩnh, ví dụ `.planbench-plugin/plugin.json`.

Manifest phải đọc được mà không import code thực thi. Đây là điểm rất quan trọng để tránh:

- `ImportError` do thiếu dependency
- side effect khi import
- load CUDA/ROS/native lib quá sớm
- crash discovery chỉ vì một plugin lỗi

Manifest tối thiểu cần có:

- `plugin_api`
- `id`, `version`
- `role`: `global | local | monolithic`
- `runtime` — khai đủ lane, không chỉ `kind` (chốt vòng 4; §5.9 luật 4
  cần chỗ khai này):

  ```yaml
  runtime:
    supported_lanes: [python_in_process, subprocess]
    production_lane: subprocess    # validator: phải thuộc supported_lanes
    profiles:
      subprocess:
        protocol: planbench-subprocess/v1
        codec: protobuf-v1
        deadline_policy: control-period
  ```

  Run spec lưu `resolved_runtime_profile`; fingerprint băm **profile đã
  resolve**, không chỉ chữ `subprocess`. Ranh giới identity:
  `production_lane` khai trong manifest thuộc **candidate identity**;
  `resolved_runtime_profile` thực chạy thuộc **fingerprint** — production
  benchmark đòi hai thứ trùng nhau, preflight kiểm. Production lane không
  khả dụng ⇒ `registered_but_missing_runtime`; **cấm fallback âm thầm
  sang in-process** — đo lane khác lane candidate khai là đo sai
  (nguyên tắc 5).
- `requirements.all_of / any_of / optional`
- `capability_schemas` / `providers` / `action_adapters` — bề mặt đóng
  góp custom capability (chốt vòng 4; thiếu nó thì "custom capability mở"
  chỉ là ý tưởng, executor phải tự chế format):

  ```yaml
  capability_schemas:
    - uri: org.lab://channel/social-costmap@1
      schema: schemas/social-costmap-v1.json
      schema_digest: sha256:...
      codecs: [json-v1, ndarray-v1]
  providers:
    - manifest: providers/social-costmap-provider.json
  action_adapters:
    - manifest: adapters/trajectory-to-velocity.json
  ```

  Luật: consume URI chưa đăng ký **và** không kèm schema declaration ⇒
  invalid manifest; schema bundled + digest hợp lệ ⇒ đăng ký; trùng
  URI/major khác digest ⇒ `quarantined`; provider/adapter code **không**
  load ở discovery.
- `supports.action_types`
- `supports.robot_dynamics`
- `supports.execution_models`
- `config_schema`
- `requires_global_path` nếu áp dụng

Trạng thái đăng ký phải tách riêng:

- `registered_and_runnable`
- `registered_but_missing_provider`
- `registered_but_missing_runtime`
- `registered_but_incompatible`
- `quarantined`

### 5.2 Capability model mở

Không dùng một enum cố định cho tương lai. Dùng capability ref kiểu URI có version, ví dụ:

```text
planbench://channel/robot-state@1
planbench://channel/global-path@1
planbench://channel/lidar-2d@1
planbench://channel/human-state-estimates@1
org.vendor://channel/radar-cube@1
```

MVP vẫn giữ alias từ token cũ (`lidar_2d`, `human_state_estimates`) để không phá identity v1, nhưng extension surface phải là URI mở.

Hai luật đi kèm (chốt vòng phản biện 17-08):

1. **Canonical hoá trước khi hash identity.** Khai requirements bằng token
   v1 hay bằng URI alias tương ứng phải cho **cùng một** `candidate_id`:
   hash chạy trên dạng canonical (token v1 khi alias tồn tại). Thiếu luật
   này, vụ P6 đứt mọi candidate_id — lần đó có chủ đích — sẽ lặp lại lần
   hai một cách âm thầm. DoD H1 có test hai cách khai → một id.

2. **URI không resolve được schema nào ⇒ fail loud lúc nạp manifest, kèm
   gợi ý gần đúng.** Vocabulary G6 đóng chính vì typo phải chết ở parse
   time. URI mở tái sinh đúng lỗi đó nếu typo chỉ hiện ra thành
   `registered_but_missing_provider` — nhìn như thiếu hạ tầng, thật ra là
   gõ nhầm. *Capability chưa từng có schema đăng ký* (nghi typo) và *có
   schema nhưng deployment không có provider cấp* (thiếu hạ tầng thật) là
   hai chẩn đoán khác nhau, phải hiện ra khác nhau. Ngoại lệ duy nhất:
   chính manifest đó khai schema trong `capability_schemas` (§5.1) — khi
   đó URI mới là đăng ký, không phải typo.

Deployment cũng cần một bề mặt additive để cấp capability mở. Không thay
`available_observations` v1 ngay; thêm `CapabilityGrant(capability,
provider_id, provider_config)` và `TaskProfile.capability_grants = ()`.
Resolver hợp nhất alias v1 và grants v2. Provider config được validate bằng
schema provider sau static discovery, trước create/run. Hai provider cùng cấp
một capability mà không có selection policy tường minh phải fail ambiguous;
host không tự chọn nguồn “tốt nhất”.

### 5.3 Observation bundle và channel envelope

Thay vì nhồi thêm field vào `Observation`, host đưa cho plugin một bundle các channel đã được cấp quyền.

Mỗi channel phải mang:

- capability id + version
- cadence: `per_tick | on_change | static` — khai trong capability schema,
  vì invariant timestamp phụ thuộc nó (xem §5.4)
- revision — bắt buộc cho `on_change`/`static`: monotonic trong episode,
  để invariant kiểm được mà không ép re-stamp timestamp
- timestamp
- frame id
- provenance
- payload encoding
- payload

`payload` là typed value hoặc `PayloadRef`, không phải Python object tùy ý đem
serialize qua process boundary. Mỗi capability đăng ký schema + codec; runtime
adapter chịu encode/decode. MVP có codec Python/JSON/ndarray, còn external
runtime có thể dùng Protobuf và shared memory/Arrow sau.

`provenance` phải đủ để nói rõ channel đến từ:

- deployment-owned provider
- candidate-owned provider
- oracle provider

Điều này là bắt buộc vì `human_state_estimates` từ ground truth, V2X hay tracker là ba điều kiện benchmark khác nhau.

### 5.4 Provider graph

Provider tạo ra channel, có dependency graph riêng.

Built-in provider MVP nên bắt đầu với:

- `RobotStateProvider`
- `Lidar2DProvider`
- `LegacyObservationProvider`
- `StaticCostmapProvider`
- `GroundTruthTrackProvider`

`GroundTruthTrackProvider` là nơi duy nhất **trên plugin data plane** được
đọc dynamic obstacle truth từ engine. Hai điều chỉnh so với bản nháp đầu
(vòng phản biện 17-08):

- `dynamic_obstacles_now()` **không còn** phục vụ replanning — A1a
  (contract 6.6.0) đã chuyển replan sang lưới dựng từ chính LiDAR, và
  `test_simulator_fairness.py` assert `_replan` không với tới hàm này.
  Docstring tại [services/simulator/planbench_simulator/engine.py](../../../../services/simulator/planbench_simulator/engine.py:324)
  đang stale, sửa cùng đợt. Bề mặt truth hẹp hơn bản nháp nghĩ — siết
  được sớm hơn.
- "Duy nhất" chỉ áp cho data plane cấp plugin. Trace recorder vẫn đọc
  truth để tính `clearance_m` — đường đo của Metrics, nằm ngoài plugin
  boundary, giữ nguyên.

Provider graph phải hỗ trợ:

- DAG resolution, cycle detection
- missing provider / ambiguity reporting
- schema validation theo capability
- validation timestamp/frame theo **cadence**: channel `per_tick` phải mang
  đúng tick và sim time hiện tại; channel `on_change`/`static` mang thời
  điểm sinh ≤ now, reuse hợp lệ. Cấm re-stamp dữ liệu cũ bằng giờ hiện
  tại — provider học nói dối về freshness thì H7 async mất chỗ dựa. H3
  kiểm invariant đồng bộ này kèm negative test (provider cố tình sai, host
  từ chối); tolerance/policy async (max_age, out-of-order, clock skew,
  drop/reuse) là việc của H7.
- per-tick caching — **chỉ là tối ưu chi phí, không phải chỗ dựa đúng đắn**

Provider contract (chốt vòng phản biện 17-08 — thay cho "stateless theo
step" quá mạnh ở góp ý đầu):

- provider **được** giữ state trong episode (tracker, temporal grid,
  filter buộc phải thế); `reset()` xoá state giữa các episode;
- lifecycle tách đôi: `advance(tick, inputs)` chuyển trạng thái, kernel
  gọi **đúng một lần mỗi tick**; `read()` pure, gọi bao nhiêu lần cũng
  cùng kết quả. Không tách thì "produce() hai lần cùng tick phải cùng kết
  quả" chỉ cứu được bằng memoization — cache thành load-bearing, mâu
  thuẫn dòng trên;
- randomness addressable bằng `(episode seed, provider stream id, tick,
  entity/sample index)` — đúng mẫu counter-based PCG64 của `NoiseModel`
  hiện tại (`noise.py`); cấm provider giữ RNG stateful riêng;
- kết quả không phụ thuộc thứ tự gọi **giữa các provider không phụ thuộc
  nhau**; provider có cạnh DAG theo topological order, hiển nhiên.

Plugin bundle có thể đóng góp channel schema, provider và adapter. Provider
ngoài chỉ nhận dependency channels đã authorize; raw `EngineProviderView` là
capability nội bộ không namespaced. MVP chỉ built-in trusted providers được
nhận view này, nên provider ngoài không thể tự đổi tên rồi đọc world truth.

### 5.5 Ba plugin contract riêng

Không ép global và local vào một method duy nhất.

Global plugin:

- nhận start, goal, robot, bundle
- trả `global_path` hoặc `no_path`

Local plugin:

- `reset()` theo episode
- `step()` theo control tick
- trả `action`, optional trajectory, diagnostics

Monolithic plugin:

- tái dùng contract local step
- descriptor khai `requires_global_path=false`

Lý do monolithic có thể đi cùng host là loop hiện nay đã chứng minh policy đi qua cùng simulation loop tại [services/simulator/planbench_simulator/nav_stack.py](../../../../services/simulator/planbench_simulator/nav_stack.py:804)

### 5.6 Action, dynamics, execution model

Host phải tách ba thứ sau ngay từ design:

- `action_type`
- `robot_dynamics`
- `execution_model`

MVP chỉ cần implement:

- `continuous-velocity@1`
- `differential-drive@1`
- `synchronous-step@1`

Nhưng manifest và resolver phải mở sẵn cho:

- `trajectory@1`
- `ackermann@1`
- `asynchronous-stream@1`
- `quadrotor-6dof@1`

Nếu plugin yêu cầu thứ host chưa support, plugin vẫn đăng ký được nhưng phải bị đánh dấu incompatible, không được fail sâu lúc runtime.

### 5.7 Runtime adapters

MVP runtime lane:

1. legacy in-process Python cho planner cũ
2. trusted in-process Python cho plugin mới
3. một proof cho subprocess runtime

Post-MVP:

- container runtime
- ROS 2 runtime
- remote gRPC runtime

Nguyên tắc:

- discovery không import code
- runtime chỉ load sau preflight
- plugin crash không được kéo chết host
- timeout và invalid output phải thành `safe_stop`

Trusted in-process Python không phải security boundary tuyệt đối: code cùng
process có thể monkeypatch/import internals. In-process là trust policy +
conformance; plugin không tin cậy không chạy in-process.

**Sửa 18-08, sau khi H7 dựng lane subprocess thật.** Bản gốc gọi
subprocess/container là “hard isolation”, và với subprocess điều đó
**quá mạnh**. Đo được: worker kế thừa toàn bộ environment của host, nhận
`PYTHONPATH` chứa code repo, có nguyên quyền filesystem/network của user
đang chạy host, và nhận config qua command line — hiện trong mọi process
listing. Nói đúng phải là:

| Lane | Cách ly được gì | **Không** được gì |
|---|---|---|
| in-process | (không) | mọi thứ — chỉ có trust policy |
| **subprocess** | crash, hang, interpreter state | quyền hệ thống, environment, filesystem, network |
| container (post-MVP) | + quyền, environment, filesystem, network | — |

Nên gọi subprocess là **crash/process isolation**. Plugin thật sự không
tin cậy cần container có drop privileges và environment đã dọn — vẫn là
post-MVP. Gọi tên đúng ở đây quan trọng vì tên sai sẽ được đọc thành
“đã an toàn cho plugin lạ”, và đó là kết luận không ai đo.

### 5.8 Compatibility resolver

Preflight resolver là cổng bắt buộc trước episode.

Nó phải kiểm:

- required capabilities
- provider graph đầy đủ
- runtime sẵn sàng
- action adapter chain tồn tại
- robot dynamics tương thích
- execution model tương thích
- fairness policy có cho phép provider đó không

Đầu ra tối thiểu:

- runnable hay không
- thiếu channel gì
- thiếu provider gì
- thiếu runtime gì
- action/dynamics nào không tương thích
- provider graph đã chọn
- adapter chain đã chọn

### 5.9 Latency accounting và deadline gate

Chốt vòng phản biện 17-08 — chỗ dễ tạo "phép đo xanh đo ít hơn nó khai"
nhất của plan, nên thước khai trước khi đo.

Mỗi control tick ghi sáu lớp duration, **thành cột trace HĐ-5** — trace là
đầu vào duy nhất của Metrics Engine, số nằm ở `StackRun` là nguồn song
song hợp đồng cấm:

```text
shared_provider_ms      # provider deployment-owned dùng chung
candidate_provider_ms   # provider candidate-owned
transport_ms            # serialize/IPC của runtime lane
algorithm_compute_ms    # thuật toán thuần
action_adapter_ms       # adapter chain phía candidate
host_overhead_ms        # phần còn lại của host

candidate_path_ms     = candidate_provider + transport
                      + algorithm_compute + action_adapter
end_to_end_control_ms = shared_provider (critical path; MVP đồng bộ nên
                        bằng tổng) + candidate_path + host_overhead
```

Luật:

1. G4 hiện hành trên algorithm compute **giữ nguyên** (backward compat).
2. Thêm deadline gate: `p99(end_to_end_control_ms) < control_period` của
   deployment. p99 tính trên **tổng cùng tick**, không cộng các p99 rời.
3. Gate mới mang cùng tư cách logic G4: `screened_on_host`, điều kiện
   cần. Transport đo được là pickle/pipe của harness, không phải DDS/ROS
   của deployment — luật "cấm hệ số quy đổi giữa hai máy" của CONTRACTS
   áp nguyên: gate này được dùng để **từ chối**, không bao giờ để chứng
   nhận realtime.
4. **Runtime lane là execution condition.** Ngày gate đọc `transport_ms`,
   transport hết là "thuần bookkeeping" — lane vào execution fingerprint,
   so sánh hai candidate phải cố định lane, và candidate khai lane sản
   xuất trong manifest để được đo ở lane đó (§7.1 sửa tương ứng).
5. **Luật chống nhiễu khai trước — có artifact thực thi, không phải lời
   hứa.** Gate wall-clock trên host đang tải là gate flaky — bài học ba
   lần hiệu chuẩn của test replanning (report 16-08 §3b). Protocol nằm
   trong một file, ví dụ `configs/latency-screening-v1.yaml`, **commit
   cùng bản ghi preregistration của decision gate, trước H0**:

   ```yaml
   version: latency-screening-v1
   warmup_episodes: ...
   repetitions: ...
   core_affinity: [...]
   worker_count: 1
   blas_threads: 1

   sentinel_candidate: astar+dwa
   sentinel_drift_max_fraction: ...

   deadline_ms: <control period của deployment>
   guard_band_ms: ...
   confidence_method: bootstrap CI   # tái dùng statistics.bootstrap_ci

   verdicts:
     pass: upper_bound < deadline - guard_band
     fail: lower_bound > deadline + guard_band
     otherwise: inconclusive
   ```

   Sentinel đo **trước và sau** phiên đo; drift quá ngưỡng ⇒
   `NOT_MEASURED` — và cấm đo lại liên tục tới khi ra số đẹp: retry là
   quyết định có hồ sơ, không phải vòng lặp. Version của protocol ghi
   trên verdict record, **không** vào execution fingerprint — theo đúng
   luật phân loại của `fingerprint.py`: nó chỉ đổi cách chấm, không đổi
   một mét quỹ đạo nào.

6. **Trust semantics theo lane.** `transport_ms`, `candidate_path_ms`,
   `end_to_end_control_ms`: host đo, authoritative ở mọi lane.
   `algorithm_compute_ms`: in-process — host đo, authoritative; external
   runtime — chỉ có số plugin tự báo, ghi vào trace làm **diagnostic,
   non-authoritative** (cột mang `measured_by: host|plugin`), và G4
   không được gate trên số plugin báo. Với external runtime, gate
   end-to-end là số authoritative duy nhất, và gate report phải nói gate
   nào authoritative cho candidate đó.

### 5.10 Oracle lane và `evidence_class`

Oracle plugin (ví dụ local plugin nuôi bằng `GroundTruthTrackProvider`)
phải **chạy được qua đúng runtime chung** — P4/P5 từng phải sống bằng
script rời, và đo upper bound là phương pháp lõi của dự án. Nhưng không
được có đường thành khuyến nghị production. Cơ chế (chốt vòng 3, 17-08):

**Enum và quyền suy ra:**

| class | chạy | metrics | production gate | recommendation |
|---|---|---|---|---|
| `production` | có | có | có | có |
| `reference` | có | có | chạy làm đối chứng, không phát verdict — pin trước, không để "tùy scope" thành chữ co giãn | không |
| `oracle` | có | diagnostic | không | không |

**Hai tầng, một luật hợp nhất.** `evidence_class` của một **execution**
được resolve, không cho plugin tự khai:

```text
execution_class = meet(entry_class, provider_graph_class)
  thứ tự: production > reference > oracle
  provider_graph_class = oracle nếu resolved graph chứa bất kỳ provider
  provenance oracle/sim_only nào
```

Tầng entry vẫn phải tồn tại — reference adapter (D12) là reference **bẩm
sinh**, tư cách đó không đến từ provider graph. Tầng execution lấy min:
một stack production chạy kèm một oracle provider trong research mode ⇒
execution đó là oracle, không ai phải nhớ.

**Trace metadata + boundary tập trung.** `TraceMetadata.evidence_class`
bắt buộc. Guard nằm ở **một chỗ**: trace load/typing boundary — không
rải if ở Card assembly hay từng consumer. Production scoring entry point
chỉ nhận production evidence; thiếu field hoặc class khác ⇒ fail-closed,
cùng hình dạng `StaleTraceError`. Giá, nói trước: kho trace hiện có
thiếu field sẽ bị từ chối một lần — đúng tiền lệ fingerprint rỗng 16-08
(*rỗng đọc là không biết, không phải khớp*).

**Hệ kiểu là discriminated model, không phải type hint.** Python hint
một mình không phải enforcement runtime. Dùng discriminated Pydantic
model / constructor riêng (tinh thần
`ExecutableSubject[Production|Reference|Oracle]`): construction **thành
công** nhưng trả đúng kiểu, entry point production validate class ở
model layer. Một runtime, các entry type khác nhau — không pipeline chẩn
đoán song song, không if rải rác.

**Trace address phải mang class và điều kiện — metadata guard không đủ.**
Oracle trace ghi cùng `(candidate_id, episode_context_id)` sẽ **đè**
production trace: fail-closed sau đó cứu được phép so nhưng mất trace,
phải mô phỏng lại. Namespace mới:

```text
traces/<evidence_class>/<execution_fingerprint>/<candidate_id>/<episode_context_id>.parquet
```

- không overwrite chéo lane/class/điều kiện;
- `--reuse-traces` lookup theo fingerprint kỳ vọng — reuse sai điều kiện
  chết ngay từ tầng địa chỉ;
- metadata check giữ làm lớp thứ hai: file bị đặt sai chỗ vẫn bị từ chối;
- hệ quả chấp nhận: trace của các thế giới khác nhau **cùng tồn tại**
  thay vì đè nhau — cần GC policy (tuổi/manifest) và một lần migration
  kho cũ.

**`withdrawn` giữ riêng, không gộp vào enum.** `evidence_class` nói
*evidence có tư cách gì*; `withdrawn` nói *lifecycle của algorithm entry*
— một stack production-class vẫn có thể bị rút sau khi đo
(`dwa_predictive` là ví dụ sống). Một enum không được thay hai khái niệm.

**Hai cổng tách biệt, tên không được mời gọi dùng sai** (chốt vòng 4).
Field derive ở tầng entry đặt tên `production_eligible`, không phải
`benchmarkable`:

```text
entry eligibility:   production_eligible = (entry_class == production)
                                           and not withdrawn
execution evidence:  resolved evidence_class == production
```

Production scoring cần **cả hai** — một production entry chạy kèm oracle
provider vẫn `production_eligible` mà execution là oracle; tên
`benchmarkable` sẽ mời ai đó authorize trace chỉ bằng cổng thứ nhất.
Field `benchmarkable` cũ giữ làm serialization alias (deprecated) cho
API/run cũ đọc được, suy từ `production_eligible`.

## 6. Phạm vi MVP

MVP không cố support mọi loại robot hay mọi runtime. Phạm vi chốt:

- giữ nguyên runtime benchmark hiện tại
- thêm host như một lớp bọc
- migrate planner hiện có qua legacy adapters
- thêm provider graph với vài provider lõi
- thêm manifest + discovery + preflight
- thêm một local proof plugin cần richer channel
- thêm một global proof plugin ngoài central registry
- thêm một subprocess proof

MVP không bao gồm:

- full ROS 2 / TEB integration
- universal physics
- marketplace / remote plugin install
- untrusted plugin chạy in-process
- training workflow

MVP vẫn thiết kế extension refs cho action/dynamics/scheduler chưa hỗ trợ. Một
plugin Ackermann hoặc drone được đăng ký nhưng mang trạng thái incompatible;
không mở physics chỉ để tránh một compatibility refusal đúng.

## 7. Xung đột cần tránh ngay từ đầu

### 7.1 Không tạo fingerprint song song

Repo đã có execution fingerprint hiện hành tại [packages/benchmark/planbench_benchmark/fingerprint.py](../../../../packages/benchmark/planbench_benchmark/fingerprint.py:1)

Plan này phải mở rộng cùng cơ chế đó, không tạo một hash path mới ở nơi khác. Nếu không sẽ rất dễ sinh:

- trace reuse sai
- identity/report lineage lệch nhau
- hai nơi hash hai khái niệm “điều kiện chạy” khác nhau

Mọi runtime/provider condition mới phải chảy qua cùng một fingerprint pipeline.

Ranh giới ownership bắt buộc:

- candidate-owned provider, bundled preprocessing hoặc semantic action adapter
  là một phần candidate; đổi code/config phải đổi candidate ID;
- deployment-owned provider/noise/latency/dropout là execution condition; đổi
  chúng đổi fingerprint, không đổi candidate ID;
- runtime transport không đổi **candidate identity**, nhưng từ khi
  deadline gate §5.9 đọc `transport_ms` thì lane hết là "thuần
  bookkeeping": runtime lane là execution condition, vào **fingerprint**;
  codec/deadline/adapter làm đổi precision hoặc behavior cũng vào
  fingerprint. So sánh hai candidate phải cố định lane.

### 7.2 Không tiếp tục dựa vào probing kwargs

`_reset_local()` hiện probe `envelope`, `obstacle_speed`, `sensor_noise` theo tên tại [services/simulator/planbench_simulator/nav_stack.py](../../../../services/simulator/planbench_simulator/nav_stack.py:356)

Cách này tiện cho quá khứ nhưng không phải extension surface dài hạn. V2 host phải chuyển dần dữ liệu này sang declared channels hoặc versioned request fields.

### 7.3 Không thay registry ngay

`AlgorithmInfo` và registry hiện tại đang là source of truth cho benchmark hôm nay tại [packages/benchmark/planbench_benchmark/registry.py](../../../../packages/benchmark/planbench_benchmark/registry.py:135)

MVP chỉ nên bọc registry hiện tại bằng synthetic manifests hoặc legacy discovery. Rewrite registry toàn phần ở đầu dự án sẽ làm blast radius lớn không cần thiết.

## 8. Kế hoạch triển khai

Hai con số ước lượng, ghi cả hai (chốt vòng phản biện 17-08):

- **ideal engineering effort:** 13–16 ngày (tổng các pha dưới, sau khi
  H1 nở thành H1a+H1b);
- **lịch thực tế** với review, full suite 42–46 phút, regression và nợ
  phát sinh (hệ số lịch sử của repo ~×2): **4–6 tuần**.

Thứ tự chạy: **H0 + H1a + H1b trước, dừng ở decision gate** (đặt sau
H1b, không phải sau parser-only SDK) rồi mới cam H2–H8.

### H0 — khóa parity và inventory

Mục tiêu:

- xác nhận baseline cho A*, RRT*, DWA, PPO
- khóa candidate id, trace identity và outcome ở seed cố định
- ghi rõ dữ liệu nào đang đi qua `run_stack()` và `run_policy()`

File chạm tới:

- [services/simulator/planbench_simulator/nav_stack.py](../../../../services/simulator/planbench_simulator/nav_stack.py:804)
- [packages/benchmark/planbench_benchmark/registry.py](../../../../packages/benchmark/planbench_benchmark/registry.py:135)
- [packages/benchmark/planbench_benchmark/fingerprint.py](../../../../packages/benchmark/planbench_benchmark/fingerprint.py:71)
- test suite liên quan benchmark / fingerprint / candidate

DoD:

- có regression fixtures cho legacy stacks, với **comparator khai tường
  minh** thay cho chữ "outcome quan trọng": trajectory, events, status,
  `candidate_id`, `execution_conditions_fingerprint` —
  **byte-identical** (chuẩn P2 golden); các field wall-clock
  (`planner_latency_ms`, `latency_seconds`…) loại trừ tường minh khỏi
  phép so
- có guard test để mọi điều kiện runtime mới phải đi qua fingerprint chung

Ước lượng: 0.5–1 ngày kỹ thuật.

### H1 — plugin SDK và consumer đầu tiên (H1a + H1b)

Chốt vòng 4: SDK không được đóng băng trước khi có một consumer thật ăn
nó, và nhánh fallback của gate không được là một mẩu việc chưa thiết kế.
Nên H1 **luôn** gồm hai nửa, gate đặt **sau H1b**.

**H1a — schema/manifest SDK.** Tạo package mới, ví dụ:

```text
packages/plugin_sdk/planbench_plugin_sdk/
  capabilities.py
  manifest.py
  requirements.py
  channels.py
  requests.py
  responses.py
  errors.py
  protocol_version.py
```

DoD H1a:

- parse được manifest mà không import plugin
- support `all_of`, `any_of`, `optional`
- có alias bridge từ token v1 sang capability URI, và test canonical hoá:
  khai `lidar_2d` và khai URI alias tương ứng cho **cùng** `candidate_id`
  (§5.2 luật 1)
- URI chưa đăng ký và không kèm `capability_schemas` declaration ⇒
  invalid manifest, kèm gợi ý gần đúng (§5.1 + §5.2 luật 2)
- duplicate id/version/checksum fail loud
- `runtime.production_lane ∈ supported_lanes` validate lúc parse

**H1b — minimal legacy consumer.** Phase thật, có DoD và file ownership
riêng — không phải nhánh phụ của gate:

```text
registry entry -> synthetic manifest -> manifest parser
  -> LegacyPluginLoader -> global/local/policy factory hiện hành
```

DoD H1b:

- synthetic manifest của A*, RRT*, DWA resolve được qua
  `LegacyPluginLoader` về đúng factory hiện hành
- PPO đi đúng lazy checkpoint / model-registry path
- monolithic: registry policy khoá theo `PolicyComponent.name` + phân
  giải checkpoint qua `model_registry` sẵn có, chạy qua `run_policy`
  hiện hành ⇒ **trả A5 ngay tại đây**, độc lập số phận H2–H8
- candidate ID không đổi (đo bằng comparator H0)
- unknown config fail đúng như registry hiện tại
- **chưa** cần `AlgorithmHost` per-tick ở bước này

Ước lượng H1a + H1b: 2.5–3 ngày ideal (+0.5–1 nếu vướng nửa monolithic).

### Decision gate sau H1b — preregister, không vibe check

Kỷ luật P4: luật commit trước khi chạy — bản ghi gate phải nằm trong
lịch sử git **trước** khi H0 bắt đầu, để "khai trước" là tính chất của
lịch sử chứ không phải một câu trong report. Bản ghi điền sẵn:

- H1 (H1a+H1b) ideal effort · allocated host calendar budget
- remaining project calendar
- trạng thái critical-path của `robustness_margin`, L17, truyền
  `LidarConfig` — ghi **trước**, không quyết sau khi H1b xong
- external plugin demand (tên cụ thể, nếu có)
- `configs/latency-screening-v1.yaml` (§5.9 luật 5) — commit cùng lúc
- decision owner: An

Sau H1 đo:

```text
schedule_factor     = H1_actual / H1_ideal
projected_remaining = schedule_factor × ideal(H2..H8)
```

Tiếp H2–H8 khi và chỉ khi **đồng thời**:

1. `projected_remaining ≤ allocated_host_budget`;
2. host là deliverable chiến lược, **hoặc** có ít nhất một external
   algorithm thật đang chờ integration;
3. không có research blocker ưu tiên cao hơn trên critical path.

**Không đạt ⇒ dừng, sạch.** H1b đã là phase thật nên không còn nhánh phụ
chưa thiết kế: SDK + synthetic manifests + loader + A5 đã xong **trước**
gate. Chỉ còn hai việc đóng: khoá extension contract (`protocol_version`
đóng băng), H2–H8 chuyển backlog giữ nguyên trong plan chờ lượt sau.

### H2 — AlgorithmHost và legacy adapters

Tạo:

```text
services/simulator/planbench_simulator/host/
  algorithm_host.py
  compatibility.py
  lifecycle.py
  legacy_global.py
  legacy_local.py
  legacy_policy.py
```

DoD:

- planner cũ đi qua host, parity đo bằng comparator H0 (byte-identical,
  loại trừ field wall-clock)
- monolithic policy vẫn dùng cùng loop
- host có semantics rõ cho timeout, invalid output, safe stop
- `HostBackedGlobalPlanner` và `HostBackedLocalPlanner` implement đúng hai ABC
  cũ; `run_stack()` vẫn gọi interface hiện hành, facade chuyển request vào host.

Ước lượng: 1.5–2 ngày.

### H3 — provider graph và authorized bundle

Tạo:

```text
services/simulator/planbench_simulator/host/
  provider_graph.py
  channel_bundle.py
  fairness_policy.py

services/simulator/planbench_simulator/host/providers/
  robot_state.py
  lidar_2d.py
  legacy_observation.py
  static_costmap.py
  ground_truth_tracks.py
```

DoD:

- provider graph resolve được DAG
- undeclared channel không lọt vào plugin
- oracle provider luôn `sim_only`
- cadence invariant **đúng nguyên văn §5.4, không rút gọn thành
  equality**: `per_tick` — tick/time exact; `on_change` — revision
  monotonic, `produced_at <= now`, cấm re-stamp; `static` — revision ổn
  định trong episode, `produced_at` không cần bằng now. H7 mới thêm
  max_age / out-of-order / clock-skew policy
- trước khi channel vào bundle: kiểm capability schema digest, provider
  output codec, frame + cadence — không chỉ DAG resolution
- sau parity H2, host nhận một `ProviderRuntimeView` tối thiểu gồm closures đã
  giới hạn (measured observation, clock, private truth chỉ cho built-in oracle),
  không nhận nguyên Engine/Scenario. Legacy facade không dùng seam này.

Ước lượng: 2 ngày.

### H4 — compatibility, fairness snapshot và accounting

DoD:

- preflight trả compatibility report trước episode
- provider graph và adapter chain đi vào execution fingerprint
- phân biệt deployment-owned, candidate-owned và oracle-owned provider trong accounting

Ước lượng: 1–1.5 ngày.

### H5 — discovery và trusted Python runtime

DoD:

- synthetic manifest built-in đã có từ H1; H5 hợp nhất chúng vào đường
  discovery chung
- support Python entry-point discovery
- dependency thiếu vẫn cho phép registered nhưng không runnable
- discovery không execute plugin code

Ước lượng: 1–1.5 ngày.

### H6 — hai proof plugin

Proof 1:

- local plugin ngoài registry cần `human-state-estimates@1`

Proof 2:

- global plugin ngoài central dictionary tạo `global-path@1`

DoD:

- add/remove hai plugin này mà không sửa `run_stack()` hoặc `engine.get_observation()`
- proof 1 tiêu thụ channel provenance oracle ⇒ chạy được qua provider
  graph **và** bị mọi đường production scoring/Card từ chối theo §5.10 —
  thiếu vế sau, MVP tạo ra entry registry đầu tiên đọc world truth mà vẫn
  benchmarkable

Ước lượng: 1.5–2 ngày.

### H7 — subprocess runtime proof

DoD:

- host khởi động plugin ngoài process
- timeout và crash được cô lập
- sáu lớp latency §5.9 ghi thành cột trace; runtime lane vào fingerprint
- tolerance/policy async cho stale channel (max_age, out-of-order, clock
  skew, buffering, drop/reuse) — phần policy mà H3 cố tình không làm

Ước lượng: 1.5–2 ngày.

### H8 — docs, API, conformance suite

DoD:

- có API hoặc CLI hiển thị registration state và compatibility report
- có conformance suite cho plugin author
- có author guide cho global/local/monolithic plugin

Ước lượng: 1.5–2 ngày.

## 9. Verification plan

### Unit

- manifest parser
- capability alias bridge + canonical hoá candidate_id (hai cách khai →
  một id)
- requirement expression
- provider DAG resolution
- provider lifecycle: `advance` đúng một lần mỗi tick, `read` idempotent
- cadence invariant + negative test provider cố tình sai timestamp/frame
- action adapter selection
- compatibility resolver
- fingerprint extension guards (kể cả runtime lane)

### Integration

- A*, RRT*, DWA, PPO qua host
- local proof plugin qua provider graph
- global proof plugin qua host
- subprocess proof plugin

### Regression

- candidate id không drift
- execution fingerprint chỉ đổi khi execution conditions thật sự đổi
- trace reuse bị chặn khi provider graph hoặc fidelity đổi

### Security / fairness

- plugin không đọc undeclared channel
- plugin không có đường trực tiếp tới world truth
- oracle provider luôn bị đánh dấu `sim_only`
- fail-closed: trace mang provenance oracle bị `--score-only`,
  `--reuse-traces` và Card assembly từ chối (kiểu `StaleTraceError`)

### Manual / operator UX

- xem được vì sao plugin không runnable
- xem được plugin đang dùng provider nào
- xem được deployment vs candidate ownership trong accounting

### Compatibility matrix MVP

| Algorithm shape | Hiện tại | MVP host |
|---|---|---|
| In-process Python global + local | có | giữ qua legacy adapters |
| Stochastic global planner | có | giữ seed plumbing/pairing |
| Local cần model artifact (PPO) | có một phần | giữ lazy model path |
| Monolithic policy | loop có, loader thiếu | thêm manifest/loader path |
| Custom channel/provider | chưa có data plane | một proof bắt buộc |
| External process global/local | chưa có | một subprocess proof |
| ROS 2 / container | chưa có | post-MVP runtime |
| Custom dynamics | chưa có | registered but incompatible |

## 10. Rủi ro chính và cách chặn

1. Rủi ro: quay lại enum đóng vì tiện.
   Mitigation: capability URI mở từ ngày đầu, token cũ chỉ là alias bridge.

2. Rủi ro: import plugin làm crash discovery.
   Mitigation: static manifest, lazy runtime load, quarantine state.

3. Rủi ro: thêm provider graph nhưng quên cho vào fingerprint.
   Mitigation: mở rộng chính `packages/benchmark/planbench_benchmark/fingerprint.py` và thêm regression guard.

4. Rủi ro: host mới làm drift planner cũ.
   Mitigation: H0 parity trước, H2 chỉ bọc loop hiện tại, không rewrite loop.

5. Rủi ro: candidate hưởng perception “miễn phí”.
   Mitigation: ownership + accounting tách deployment-owned, candidate-owned, oracle.

6. Rủi ro: action adapter âm thầm mất semantics.
   Mitigation: adapter chain explicit, không có chain thì preflight fail.

7. Rủi ro: deadline gate flaky vì wall-clock trên host đang tải.
   Mitigation: §5.9 luật 5 — điều kiện tải khai trước, margin band trong
   anchors, `not_measured` thay vì đoán.

8. Rủi ro: provider re-stamp dữ liệu cũ để qua invariant timestamp.
   Mitigation: cadence khai trong capability schema, invariant theo
   cadence, negative test ở H3.

## 11. Definition of Done cho MVP

> **Sửa 18-08, sau khi H0–H8 xong.** Bản gốc liệt DoD theo **kết quả**,
> còn §8 chia việc theo **file**. Khoản nào nằm gọn trong danh sách file
> của một pha thì xong; khoản nào **vắt qua nhiều pha** thì mỗi pha làm
> phần rơi vào mình và không ai ráp lại — năm khoản hở đúng theo cơ chế
> đó, phát hiện lúc đối chiếu cuối chứ không phải lúc làm.
>
> Nên từ nay **mỗi khoản chỉ đích danh pha sở hữu nó**, và mỗi pha đối
> chiếu §11 khi đóng chứ không đợi cuối plan. Không có bước này, H9–H12
> sẽ đẻ ra đúng lớp hở đó lần nữa, lần này với ít người còn nhớ để rà.
>
> Trạng thái sau H8: **12 đạt · 3 một phần · 2 chưa làm.**

| # | Khoản | Pha sở hữu | Trạng thái sau H8 |
|---|---|---|---|
| 1 | A*, RRT*, DWA, PPO qua host không drift theo comparator H0 | H0 + H2 | ⚠️ PPO mới ở mức identity → **H12** |
| 2 | Local plugin ngoài registry qua provider graph | H6 | ✅ |
| 3 | Global plugin ngoài registry qua host | H6 | ✅ |
| 4 | Thiếu runtime/provider vẫn đăng ký, báo đúng lý do | H4 + H5 | ✅ |
| 5 | `run_stack()` không special-case proof plugin | H6 | ✅ |
| 6 | Provider provenance vào fingerprint và report | H4 | ✅ |
| 7 | Oracle provider `sim_only`, không production-recommendable | H3 + **H9A** | ⚠️ mới chặn ở preflight |
| 8 | Crash/timeout không kéo chết host | H2 + H7 | ✅ |
| 9 | Author guide đủ để thêm plugin không sửa core loop | H8 | ✅ |
| 10 | Deployment khai capability bằng **additive grant** | **H11** | ❌ chưa làm |
| 11 | Candidate-owned đổi candidate ID; deployment-owned đổi fingerprint; test **cả hai chiều** | **H9B** | ⚠️ mới một chiều |
| 12 | Thiếu action/dynamics/runtime vẫn đăng ký, report đúng | H4 | ✅ |
| 13 | Sáu lớp latency thành cột trace · deadline gate `screened_on_host` · runtime lane vào fingerprint | H7 + **H10** | ⚠️ gate chưa tồn tại |
| 14 | `evidence_class` trong metadata và address · fail-closed ở một boundary · `withdrawn` riêng · `benchmarkable` derived | **H9A** + **H12** | ❌ chưa làm |
| 15 | Hai cách khai capability → cùng `candidate_id` | H1a | ✅ |
| 16 | Manifest khai đủ lane + custom capability surface | H1a + H7 | ✅ |
| 17 | `algorithm_compute_ms` external là diagnostic; verdict theo protocol | H7 + **H10** | ⚠️ verdict chưa có |

Nguyên văn các khoản:

1. A*, RRT*, DWA, PPO chạy qua `AlgorithmHost` không drift theo comparator H0; chỉ các field wall-clock trong danh sách preregistered được loại trừ.
2. Một local plugin ngoài registry cần richer observation chạy được qua provider graph.
3. Một global plugin ngoài registry nối được sang local/plugin host.
4. Plugin hợp lệ nhưng thiếu runtime/provider vẫn đăng ký được và báo đúng lý do.
5. `run_stack()` không cần special-case cho proof plugins mới.
6. Provider provenance đi vào fingerprint và report.
7. Oracle provider luôn bị gắn `sim_only` và không được xem là production-recommendable.
8. Plugin crash hoặc timeout không kéo chết host.
9. Tác giả plugin ngoài repo có thể đọc author guide và thêm plugin mà không phải sửa core loop.
10. Deployment khai custom capability/provider bằng additive grant mà không phá stored v1 profile.
11. Candidate-owned provider đổi candidate ID; deployment-owned provider đổi execution fingerprint; regression test khóa cả hai chiều.
12. Plugin valid nhưng thiếu action/dynamics/runtime vẫn đăng ký được và CompatibilityReport nêu đúng dependency thiếu.
13. Sáu lớp latency là cột trace; deadline gate end-to-end chạy
    `screened_on_host` với luật chống nhiễu §5.9; runtime lane nằm trong
    execution fingerprint.
14. `TraceMetadata.evidence_class` bắt buộc; guard fail-closed nằm ở
    **một** trace load boundary duy nhất; trace address mang
    `evidence_class/execution_fingerprint` nên không overwrite chéo
    lane/class; `withdrawn` vẫn là trường lifecycle riêng và
    `benchmarkable` thành derived.
15. Hai cách khai một capability (token v1 / URI alias) cho cùng
    `candidate_id`.
16. Manifest khai đủ runtime lane (`supported_lanes`, `production_lane`,
    `profiles`) và bề mặt custom capability (`capability_schemas` /
    `providers` / `action_adapters`); `resolved_runtime_profile` vào
    fingerprint; không fallback lane âm thầm.
17. `algorithm_compute_ms` của external runtime là plugin-reported
    diagnostic, không bao giờ là số gate authoritative; verdict latency
    sinh theo `latency-screening-v1.yaml` đã commit trước H0.

## 12. ADR tóm tắt

### Decision

Xây một capability-driven `AlgorithmHost` ở trên runtime hiện tại, với static manifest, channel bundle, provider graph, compatibility resolver và legacy adapters.

### Drivers

1. Mở đường tích hợp lâu dài cho nhiều loại thuật toán.
2. Giữ fairness, reproducibility và report lineage.
3. Tránh rewrite lớn ngay trong MVP.

### Alternatives considered

1. Mở rộng dần `Observation` hiện tại  
   Bác vì sẽ làm core phình to và trộn quyền truy cập dữ liệu.

2. Thêm adapter riêng trong `run_stack()` cho từng thuật toán  
   Bác vì coupling tăng vô hạn và rất khó giữ fairness.

3. Rewrite toàn bộ thành external RPC ngay từ đầu  
   Bác vì blast radius lớn, chưa cần cho MVP.

4. Bọc loop hiện tại bằng host + legacy adapters  
   Chọn vì cho phép tiến hóa dần mà vẫn giữ parity.

### Consequences

- thêm complexity ở lớp contract/discovery/provider
- plugin có thể “registered but not runnable”, nên UI/API phải giải thích được
- provider provenance trở thành thành phần hạng nhất của benchmark condition

### Follow-ups

- container runtime
- ROS 2 runtime
- action/dynamics extension
- hội tụ registry về manifest sau khi v2 ổn định

---

## 13. Sau H8 — thứ tự chốt 18-08 cho năm khoản hở

Chốt sau vòng đánh giá của An trên bản tổng kết H0–H8. Xếp theo **thứ
gì có thể làm hỏng dữ liệu không sửa được**, không theo thứ gì gần
feature-complete nhất.

### H9A — trace evidence safety · **P0**

Khoản duy nhất hiện có thể **tạo dữ liệu sai vĩnh viễn**: oracle trace
ghi đè production trace ở cùng địa chỉ, và production scoring đọc được
nó nếu file đã tồn tại.

```text
root/<evidence_class>/<execution_fingerprint>/<candidate_id>/<context_id>.parquet
```

- `TraceMetadata.evidence_class`, bắt buộc;
- metadata phải **khớp path** — lệch là từ chối;
- **một** `TraceUsePolicy` duy nhất, mọi consumer đi qua: `read_trace`,
  `--reuse-traces`, `--score-only`, Card assembly, API download;
- trace cũ thiếu evidence class = *unknown* ⇒ fail closed. **Không
  migrate, không đổi tên thành production** — trace không có provenance
  phải chạy lại (tiền lệ fingerprint rỗng 16-08).

Ba thứ phải tính trước, không được để lộ ra giữa chừng:

1. **Fixture parity sẽ đỏ ở trường `trace.relative_path`.** Đổi address
   là đổi trường đó. Phải là **amendment có ghi lý do**, sửa đúng một
   trường, mọi trường khác giữ byte-identical — **tuyệt đối không
   regenerate**, vì regenerate xoá luôn bằng chứng chín pha vừa dựa vào.
2. **Kho trace hiện có thành bất khả truy cập** (mọi file ở địa chỉ cũ)
   ⇒ phải mô phỏng lại một lần. Đây là thời gian máy, cộng ngoài 1.5–2.5
   ngày code.
3. **Còn địa chỉ thứ tư: thư mục run và `run_journal`.** Theo report
   16-08, thư mục run đặt tên từ *(profile id, scope, candidate set)* —
   **không có evidence class**. Research run và production run cùng bộ
   ba đó sẽ chung thư mục và chung journal: đúng lỗ 16-08 lặp lại một
   tầng trên trace path.

Test bắt buộc: oracle/production cùng (candidate, context) không thể
chung path · oracle không được production score/reuse · reference không
được vào recommendation · thiếu evidence class fail closed · path nói
production mà metadata nói oracle ⇒ từ chối · fingerprint trong path
khác metadata ⇒ từ chối · mọi consumer dùng chung boundary · research
vẫn đọc được oracle khi policy cho phép · trace legacy **không** tự nâng
thành production · **hai run khác evidence class không chung run
directory** · candidate ID và parity H0 không drift.

**Ước lượng:** 1.5–2.5 ngày code + một lượt mô phỏng lại kho trace.

### H9B — candidate provider identity · **P0**

Hôm nay `candidate_id` chỉ băm stack, params, observation requirements.
Provider riêng của candidate **không** vào id ⇒ hai candidate khác nhau ở
provider chung một id.

Không băm `(capability, tên class)` — hai bản code hoặc config khác nhau
vẫn chung tên. Identity tĩnh:

```text
CandidateProviderBinding:
  capability · provider_id · provider_version
  manifest_checksum · config_digest · schema_digest
```

Canonical-sort rồi vào `candidate_id`. **Không** lấy từ resolved provider
graph: `candidate_id` phải tồn tại trước khi có deployment và trước
preflight.

Hai bẫy canonical hoá, cả hai đều là bài học đã trả giá:

- `capability` phải đi qua **alias bridge SDK** — không thì plugin khai
  `lidar_2d` và plugin khai URI cho hai id, phá thẳng DoD 15;
- `config_digest` phải **sort key** trước khi băm — đúng defect test H4
  bắt được ở `HostConditions.providers`.

Regression: `candidate_providers=()` giữ nguyên **mọi** legacy id · đổi
version/checksum/config ⇒ đổi id · đổi deployment-owned provider ⇒ id
không đổi, fingerprint đổi · cùng bindings khác thứ tự ⇒ cùng id ·
candidate-owned chưa khai identity ⇒ preflight từ chối.

**Ước lượng:** 0.5–1 ngày.

> Sau H9A + H9B, hệ thống gọi được là **an toàn để không tạo dữ liệu
> sai** — chưa feature-complete, nhưng không còn đường ghi ra thứ không
> sửa được.

### Amendment protocol latency — **làm trước H10, không phải trong H10**

`configs/latency-screening-v1.yaml` đã commit như một preregistration
(`f15ee25`, trước cả H0) nhưng chỉ ghi `confidence_method: bootstrap_ci`
— **không nói resample đơn vị gì**. Một thước khai trước mà mơ hồ thì
không phải thước khai trước.

Sửa **hợp lệ ngay bây giờ** vì chưa có một phép đo nào tồn tại; sửa sau
số đầu tiên là thay thước giữa chừng, đúng thứ kỷ luật P4 chặn.

- Bump **`latency-screening-v2`**, không sửa tại chỗ v1 — lịch sử giữ
  cả bản mơ hồ lẫn lý do nó bị thay.
- **Bootstrap theo episode** (hoặc hierarchical), rồi tính lại pooled
  p99 trong mỗi resample. Tick trong một episode có tương quan; coi
  chúng là mẫu độc lập sẽ cho CI hẹp giả.
- **Sample size vào verdict record**, kèm **N tối thiểu** dưới đó verdict
  là `inconclusive` bất kể CI. Bootstrap theo episode nghĩa là N hiệu
  dụng là **số episode** (30), không phải hàng nghìn tick — con số quyết
  định độ rộng CI phải hiện ra, không ẩn sau một CI trông hẹp.

### H10 — deadline screening

G4 hiện đọc `planner_latency_ms` và so với `robot.control_period`. Giữ
backward compatibility bằng cách **tách đôi**, không thay số:

```text
G4:
  legacy_algorithm_compute_screen
  end_to_end_deadline_screen
  overall_result
```

Screen mới: parse + validate protocol · warmup riêng · sentinel trước ·
đúng số repetitions, một worker · sentinel sau · drift > ngưỡng ⇒
`NOT_MEASURED` · bootstrap CI theo episode cho p99
`end_to_end_control_ms` · `pass | fail | inconclusive`.

Verdict record lưu: protocol version · git SHA · candidate + runtime
profile · host info · affinity/BLAS · sentinel trước/sau · CI bounds ·
deadline + guard band · **sample size** · lý do retry nếu có.

**Ước lượng:** 2–3 ngày.

### H11 — capability grants

```text
CapabilityGrant:
  capability · provider_id · provider_version
  provider_config · provider_config_digest
```

Resolver hợp nhất `available_observations` v1 + `capability_grants` v2 →
canonical granted capabilities. Hai provider một capability không có
selection tường minh ⇒ **fail ambiguous** (host không tự chọn nguồn tốt
nhất — §5.4). Validate config bằng provider schema **trước** episode.
Deployment-owned provider/config vào execution fingerprint.
`capability_grants` rỗng **không được** làm đổi fingerprint hay profile
cũ; profile cũ load rồi dump lại không drift.

Chạm schema + API persistence + form UI + migration ⇒ **không ghép vào
commit trace safety**.

**Ưu tiên:** chỉ làm ngay nếu có deployment/provider ngoài thật đang
chờ. Chưa có thì vào backlog **sau** `robustness_margin` — đúng theo
prereg gate, nơi F1 được khai là trên critical path.

**Ước lượng:** backend 1.5–2.5 ngày, + ~1 ngày nếu có UI.

### H12 — eligibility cleanup và PPO parity

```text
withdrawn: str | None
reference: bool
production_eligible = not reference and withdrawn is None
benchmarkable = alias tương thích, deprecated
```

Giữ `benchmarkable` dạng computed/read-only một thời gian để không phá
API/UI. **Kiểm — đừng giả định — rằng nó không phá dữ liệu đã lưu:**
`AlgorithmInfo` frozen nhưng không `extra="forbid"`, nên nhiều khả năng
an toàn, và "nhiều khả năng" không phải kết luận.

**PPO parity.** DoD #1 hiện là **partial**: identity-level không chứng
minh runtime không drift. H2 đã triển khai nên **không được** dựng
"pre-host baseline" từ HEAD. Cách phục hồi bằng chứng đúng: checkpoint
PPO cố định + môi trường có RL extras → checkout **`239132e`** (commit
ngay trước H2) trong worktree riêng → chạy cùng profile/seed/checkpoint
/comparator → chạy lại trên HEAD → so outcome, trajectory, events,
candidate ID, fingerprint, trace deterministic fields → lưu hai SHA cùng
checkpoint digest trong report. Chưa làm được thì DoD #1 **giữ
partial** — đó là câu trả lời trung thực, không phải thất bại.

### Thứ tự chốt

```text
H9A  →  H9B  →  [amendment protocol v2]  →  H10  →  H12  →  H11*
                                                            * hoặc backlog
```

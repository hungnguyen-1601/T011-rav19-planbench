# Plan (chưa triển khai) — Scenario Editor tùy chỉnh + Replanning công bằng

Lập ngày 2026-08-03, cùng 1 phiên trao đổi (2 feature khác nhau, gộp
chung 1 file theo đúng quy tắc: 1 session plan nhiều feature thì gộp
được). Bản gốc harness lưu ở
`C:\Users\Admin\.claude\plans\sparkling-sniffing-waffle.md` (phần cuối
file) — đây là bản sao riêng cho project, theo quy tắc mới đã thống
nhất với user.

**Trạng thái: CHƯA TRIỂN KHAI.** User đang bận việc khác, để dành làm
sau. Không có thứ tự bắt buộc giữa Plan A và Plan B.

---

# ⏸️ CHƯA TRIỂN KHAI — 2 plan lưu để làm sau

User yêu cầu lập plan chi tiết cho 2 feature dưới đây nhưng **chưa bắt
đầu code** — đang bận việc khác trước. Khi quay lại, đọc thẳng phần
tương ứng, không cần lập lại plan. Thứ tự làm trước/sau do user chọn
lúc quay lại, không có thứ tự bắt buộc giữa 2 cái này.

---

## Plan A — Scenario Editor tùy chỉnh (map custom qua `/maps` đã có sẵn,
đây là phần scenario còn thiếu: hướng robot + config vật cản động)

### Bối cảnh (đã research kỹ, không đoán)

**Tin tốt: backend đã làm đủ hết, đây gần như thuần là việc frontend.**

- `apps/api/planbench_api/routers/scenarios.py` **đã có sẵn đầy đủ**
  `POST /scenarios`, `GET/PUT/DELETE /scenarios/{id}`,
  `POST /scenarios/validate` — tất cả đã wire tới `ScenarioService`
  (`services.py`), tất cả đều validate qua **chính simulation engine
  thật** (`ScenarioService.validate_against_map()` gọi
  `SimulationEngine.load_scenario()` — cùng logic dùng khi chạy benchmark
  thật, không phải validate giả lập riêng). Nghĩa là: **không cần sửa
  gì ở backend** cho feature này, chỉ cần frontend gọi đúng endpoint
  đã có.
- `Pose2D.theta` (`packages/schemas/planbench_schemas/geometry.py`)
  **hoàn toàn tự do** — bất kỳ giá trị hữu hạn nào, tự động chuẩn hóa
  về `(-π, π]`, không bị chặn. Cái duy nhất bắt buộc `theta == 0` là
  `MapData.origin.theta` (field khác, model khác) — **không liên quan**
  tới `start_pose`/`goal_pose` của Scenario. Vậy hướng robot lúc xuất
  phát/đích **đã sẵn sàng chỉnh được** ngay khi có UI, không cần sửa
  schema.
- `DynamicObstacle` (`packages/schemas/planbench_schemas/dynamic.py`,
  238 dòng, đã đọc toàn bộ) — 4 kiểu chuyển động, discriminated union
  trên field `kind`:
  - `WaypointMotion`: `waypoints` (≥2 điểm), `speed`, `loop`, `ping_pong`.
  - `PeriodicMotion`: `start`, `end`, `period`, `phase` — dao động qua
    lại giữa 2 điểm.
  - `RandomWalkMotion`: `origin`, `speed`, `change_interval`,
    `max_radius`, `seed_offset` — đi ngẫu nhiên quanh 1 điểm, seed hóa.
  - `SuddenStopMotion`: `start`, `heading`, `speed`, `stop_time` — đi
    thẳng rồi dừng đột ngột tại 1 thời điểm.
  Không có mô hình "social force" — mọi chuyển động là hàm thuần
  `position_at(obstacle, time, seed)`, xác định trước hoàn toàn (kể cả
  "random" cũng seed hóa, tái lập được).
- **Frontend `Scenario` interface (`apps/web/src/lib/types.ts`) đang
  lỗi thời** — thiếu hẳn `dynamic_obstacles`, `lidar`, `random_seed`,
  `stuck_time_window`, `stuck_min_displacement`,
  `progress_time_window`, `progress_min_decrease`; `static_obstacles`
  gõ kiểu `unknown[]` (không có type thật). **Không có type TS nào**
  cho `DynamicObstacle`/4 kiểu Motion/`CircleObstacle`/
  `RectangleObstacle`/`LidarConfig` — phải viết mới từ đầu, khớp tên
  field Python 1:1.
- `apps/web/src/lib/api.ts` **thiếu hẳn** `getScenario`,
  `updateScenario`, `deleteScenario`, `validateScenario` — dù backend
  đã có route. Chỉ có `listScenarios`/`createScenario`.
- **Pattern click-đặt-điểm đã có sẵn**, dùng lại được ngay:
  `apps/web/src/app/simulate/page.tsx` có `placeMode`/`placePose` gọi
  qua `<MapCanvas onWorldClick={placePose}>` — nhưng **hiện hardcode
  `theta: 0`**, chưa có UI chỉnh hướng ở bất kỳ đâu trong repo.
  `apps/web/src/app/maps/[id]/page.tsx` dùng thêm `onWorldDrag` (vẽ
  brush liên tục) — chứng minh callback này bắn liên tục world-coord
  trong lúc giữ chuột, đúng nguyên liệu cần cho "kéo để xoay hướng"
  nếu muốn làm sau này.
- `MapCanvas.tsx` (`apps/web/src/components/MapCanvas.tsx`) đã vẽ
  đường heading cho **`robotPose`** (mũi tên hướng) nhưng **không** vẽ
  cho `startPose`/`goalPose` (chỉ vòng tròn + nhãn, không có hướng) —
  và **không vẽ vật cản tĩnh/động nào cả** hiện tại.

### Quyết định MVP (tự trim, sẽ nói lại nếu user muốn khác lúc triển khai)

- **Chỉnh hướng bằng ô nhập số (độ, tự đổi ra radian)**, không làm
  "kéo chuột để xoay" ngay — kéo-xoay cần thêm state theo dõi "đang
  kéo cái gì" (start/goal/waypoint nào) trong `MapCanvas`, phức tạp hơn
  hẳn so với 1 ô input. Để "kéo-xoay" làm đợt sau nếu cần, không block
  MVP.
- Waypoint của `WaypointMotion` đặt bằng **click liên tiếp trên canvas**
  (tái dùng `onWorldClick`, có nút "xong" để kết thúc 1 obstacle) — vì
  đây là dữ liệu hình học thật sự cần thấy trực quan, khác với các
  tham số số học (speed, period...) hợp lý hơn khi để trong form.
- Không tạo map mới trong lúc soạn scenario — đúng như bạn hiểu, map
  soạn ở `/maps`, scenario editor chỉ **chọn** map có sẵn (dropdown).

### Thay đổi

1. **`apps/web/src/lib/types.ts`**: sửa `Scenario` interface cho khớp
   đầy đủ backend (thêm 7 field thiếu, gõ đúng kiểu
   `static_obstacles`). Thêm interface mới: `CircleObstacle`,
   `RectangleObstacle`, `StaticObstacle` (union), `DynamicObstacle`,
   `WaypointMotion`, `PeriodicMotion`, `RandomWalkMotion`,
   `SuddenStopMotion`, `Motion` (union theo `kind`), `LidarConfig`.
2. **`apps/web/src/lib/api.ts`**: thêm `getScenario(id)`,
   `updateScenario(id, mapId, scenario)`, `deleteScenario(id)`,
   `validateScenario(mapId, scenario)` — gọi đúng route đã có sẵn ở
   backend, không cần đoán shape (đã đọc `routers/scenarios.py` +
   `schemas.py::ScenarioCreateRequest{map_id, scenario}` nguyên văn).
3. **`apps/web/src/components/MapCanvas.tsx`**:
   - Thêm vẽ đường heading cho `startPose`/`goalPose` (tái dùng đúng
     công thức đã có cho `robotPose`, chỉ đổi input).
   - Thêm prop `staticObstacles?: StaticObstacle[]` +
     `dynamicObstacles?: DynamicObstacle[]`, vẽ overlay: circle/rect
     cho static; với dynamic — vẽ circle tại vị trí hiện tại (nếu có
     preview time) + đường polyline mờ cho `waypoints`, đoạn thẳng cho
     `periodic` start↔end, vòng tròn bán kính `max_radius` cho
     `random_walk`, điểm + mũi tên `heading` cho `sudden_stop`. Đây là
     preview tĩnh (vẽ hình dạng chuyển động), không cần mô phỏng thời
     gian thật trong lúc soạn — xem chuyển động thật thì chạy benchmark
     rồi mở replay (đã làm ở Phase 3b-3).
4. **Trang mới `apps/web/src/app/scenarios/page.tsx`**: danh sách
   scenario (mirror `maps/page.tsx`), nút "Tạo scenario mới" → sang
   trang editor với map đã chọn.
5. **Trang mới `apps/web/src/app/scenarios/[id]/page.tsx`** (dùng
   chung cho tạo mới nếu `id === "new"`, theo pattern Next.js dynamic
   route đã dùng ở `maps/[id]`):
   - Dropdown chọn map (từ `GET /maps`).
   - `<MapCanvas>` hiển thị map đã chọn + toàn bộ overlay ở mục 3.
   - Form: tên/mô tả, robot (radius, max velocity/acceleration ×2),
     `goal_tolerance`, `timeout_seconds`, `simulation_dt`,
     `random_seed`, lidar (num_rays/max_range/angle_span). Nhóm
     `stuck_time_window`/`stuck_min_displacement`/
     `progress_time_window`/`progress_min_decrease` để trong khối
     "nâng cao" (collapsible) — đây là ngưỡng dừng episode, không phải
     mô tả scenario cốt lõi, không cần hiện mặc định.
   - Đặt start/goal: click trên canvas → set x,y (tái dùng
     `placePose` pattern từ `simulate/page.tsx`), 2 ô input số riêng để
     chỉnh `theta` (độ).
   - Danh sách vật cản tĩnh: nút thêm circle/rectangle, mỗi dòng 1 form
     nhỏ (tọa độ tâm + bán kính, hoặc 4 số min/max).
   - Danh sách vật cản động: nút thêm, chọn `kind`, form tương ứng
     từng loại (mục Quyết định MVP ở trên — waypoint đặt bằng click).
   - Nút "Kiểm tra" gọi `POST /scenarios/validate` — hiện lỗi thật từ
     engine (start/goal trong tường, đè lên vật cản...) trước khi cho
     lưu.
   - Nút "Lưu" → `POST /scenarios` (tạo mới) hoặc
     `PUT /scenarios/{id}` (sửa).
6. **Locale**: thêm toàn bộ key mới cho trang scenario editor vào
   `en.json`/`vi.json` (số lượng khá nhiều — làm cuối cùng sau khi UI
   ổn định câu chữ, tránh phải sửa lại nhiều lần).

### Test

- Không cần sửa test backend (không đổi backend).
- Vitest: test cho phần chuyển đổi độ↔radian (nếu tách hàm riêng), test
  cho việc build request body đúng shape từ state form (dựng 1 scenario
  mẫu, gọi hàm build-payload, so khớp field). Theo giới hạn đã ghi ở
  KNOWN_LIMITATIONS #69 (dự án không test render tương tác), không bắt
  buộc test render đầy đủ cho trang editor — `tsc --noEmit` +
  `next build` là mức tối thiểu bắt buộc.

### Verification

1. `npx tsc --noEmit` sạch, `next build` sạch.
2. Chạy web thật: tạo 1 scenario mới có vật cản động kiểu `waypoint`
   (click 3 điểm), lưu, xác nhận `GET /scenarios/{id}` trả đúng dữ liệu
   đã nhập.
3. Thử lưu 1 scenario cố tình đặt start đè lên tường — xác nhận
   `POST /scenarios/validate` báo lỗi đúng, không cho lưu.
4. Dùng scenario vừa tạo để chạy 1 benchmark thật — xác nhận robot xuất
   phát đúng hướng đã chỉnh, vật cản động di chuyển đúng kiểu đã cấu
   hình (xem qua replay, Phase 3b-3).
5. `pytest tests/ -q` vẫn xanh nguyên (không đổi backend nên không có
   lý do fail, chạy lại chỉ để chắc chắn).

---

## Plan B — Replanning khi bị vật cản động chặn (giữ công bằng theo
đúng 3 điều kiện đã thống nhất)

### Bối cảnh (đã research kỹ vào đúng code, không đoán)

**Phát hiện quan trọng nhất — replan ngây thơ sẽ vô dụng:**
`plan_global_path()` (`nav_stack.py`) chỉ rasterize **vật cản tĩnh**
(`scenario.static_obstacles`) vào grid quy hoạch — **không hề biết vật
cản động đang ở đâu**. Nếu chỉ gọi lại y hệt hàm này khi bị stuck, kết
quả gần như là **đường y hệt cũ** (cùng input static-only), không né
được vật cản động vừa gây ra stuck. Replan thật sự hữu ích **bắt buộc
phải** đưa thêm vị trí vật cản động hiện tại vào grid trước khi gọi lại
global planner — đây là phần việc kỹ thuật cốt lõi, không phải chi
tiết phụ.

**Điểm chèn logic:** `engine.py::_check_termination()` (dòng 151-208)
— nhánh `STUCK` (183-198) và `NO_PROGRESS` (199-208) đều chỉ có trong
1 khối `else` dùng chung cơ chế lấy mẫu `_sample_at_age()`. Cả 2 gọi
`self._terminate(status, reason)` (210-214) — nơi duy nhất set
`self._state = EngineState.FINISHED`, làm `is_done()` trả `True`, làm
vòng lặp `while not engine.is_done()` trong `nav_stack.py::run_stack()`
dừng hẳn. **Chưa có cách nào "hồi sinh" episode sau khi đã FINISHED** —
`resume()` hiện tại chỉ hoạt động từ `PAUSED`, không phải `FINISHED`;
`step()` raise `RuntimeError` nếu state khác `RUNNING`. Cần thêm hẳn 1
method mới trên `SimulationEngine`, không phải chỉnh sửa nhỏ.

**Rủi ro nếu tái kích hoạt "stuck window" không đúng cách:** nếu chỉ
đơn giản set lại `_state = RUNNING` mà không xóa mẫu cửa sổ phát hiện
stuck cũ (`_window`, dùng bởi `_sample_at_age`), điều kiện STUCK sẽ
**kích hoạt lại ngay bước tiếp theo** vì mẫu displacement cũ vẫn còn —
method mới bắt buộc phải reseed cửa sổ này tại thời điểm replan, không
chỉ đổi state.

**`LocalPlanner.reset()` vốn thiết kế cho "1 lần đầu episode"** —
docstring ghi rõ "Prepare for a new episode with a fresh global path"
(`common/local_base.py`). Gọi lại giữa episode (để trao đường mới sau
replan) không bị chặn về mặt chữ ký hàm, nhưng **chưa verify** với
DWA/PPO thật (chỉ xác nhận `PurePursuitLocalPlanner.reset()` an toàn gọi
lại — tự build lại `PurePursuitFollower` mới, không giữ state cũ) —
bắt buộc phải test riêng với DWA/PPO trước khi coi đây là an toàn.

### 3 điều kiện công bằng đã thống nhất với user — áp dụng cụ thể vào đâu

1. **"Replanning là thuộc tính của stack, áp dụng đều mọi thuật toán"**
   → cắm logic replan vào `nav_stack.py::run_stack()` (nơi **mọi**
   stack đều đi qua), **tuyệt đối không** cắm riêng vào
   `dwa/planner.py` hay bất kỳ file 1 thuật toán nào.
2. **"Trigger dùng ngưỡng chung, hash vào `conditions_checksum`"** →
   thêm field mới **ở tầng `Scenario`** (không phải per-algorithm
   config): `replanning_enabled: bool = False` (mặc định tắt — không
   phá hành vi mọi scenario/benchmark cũ), `max_replans: int = Field(3, ge=0)`.
   Vì đây là field của `Scenario`, nó **tự động** đi vào
   `FairnessRecord._scenario_checksum()` (đã hash toàn bộ scenario từ
   trước) — 2 report cùng `conditions_checksum` chắc chắn dùng cùng
   luật replan, không cần code thêm gì để đảm bảo việc này.
3. **"Nếu replanning có tham số riêng, phải vào chung vòng tune P01"**
   → MVP **không** làm tham số replan tunable qua Optuna — `max_replans`
   cố định theo scenario, không mở cửa cho bất công bằng ngay từ đầu.
   Nếu sau này muốn cho Optuna tự tìm `max_replans` tối ưu, phải thêm
   vào `tuning.py::SEARCH_SPACES` theo đúng luật cùng ngân sách — ghi
   chú lại, không làm trong đợt này.

### Quyết định thiết kế (dựa trên research, sẽ xác nhận lại lúc triển khai)

- **`STUCK` vẫn là status cuối cùng, chỉ khi đã hết lượt replan** (không
  thêm `EpisodeStatus` mới) — cách này **không đụng** tới bất kỳ chỗ
  nào đang đọc `EpisodeStatus.STUCK` (`runner.py:205 stuck_rate`,
  `failure.py:176`, `rewards.py:66`, toàn bộ test liên quan) — episode
  chỉ được tính STUCK khi robot thật sự không còn cách nào, đúng nghĩa
  hơn cả cách hiện tại (hiện: bị chặn 1 lần là thua ngay).
- **`NO_PROGRESS` cũng kích hoạt replan** — cùng cơ chế lấy mẫu với
  STUCK trong `_check_termination`, cùng bản chất "đường hiện tại
  không còn hiệu quả".
- Ghi lại mỗi lần replan như 1 `EpisodeEvent` (cơ chế đã có sẵn, dùng
  cho `stuck`/`no_progress`/... từ trước) — không terminal, chỉ log.
- `EpisodeMetrics` thêm `replan_count: int = 0` — theo đúng pattern
  accumulator (`latencies`/`failures` trong `run_stack()`), **không**
  theo pattern "suy ra từ trajectory" như `stop_and_go_count` (không
  suy ra được — phải đếm trực tiếp lúc chạy).
- `global_planning_time`/`expanded_nodes` đổi nghĩa thành **tổng cộng
  dồn qua mọi lần replan** (kể cả lần đầu) — khi `replanning_enabled=False`
  (mặc định), chỉ có đúng 1 plan nên giá trị **giống hệt hành vi cũ**,
  không có regression khi tắt tính năng.
- `planned_path_length`/`path_efficiency` giữ theo **đường của lần
  replan cuối cùng** (đường đang thật sự dùng lúc kết episode) — ghi
  rõ trong docstring: so sánh `path_efficiency` giữa 1 run có replan và
  1 run không replan **không còn ý nghĩa như nhau**, phải note vào
  KNOWN_LIMITATIONS khi làm.

### Thay đổi

1. **`packages/schemas/planbench_schemas/scenario.py`**: thêm
   `replanning_enabled: bool = False`, `max_replans: int = Field(default=3, ge=0)`
   vào `Scenario`.
2. **`services/simulator/planbench_simulator/engine.py`**:
   - Thêm method public lấy vị trí vật cản động **hiện tại** (circle
     list tại 1 thời điểm) — hiện chỉ có hàm private tương đương, cần
     public hóa để `nav_stack.py` gọi được từ ngoài lúc replan.
   - Thêm method mới (ví dụ `recover_from_stuck(new_status_check)` hay
     tên tương tự) — reset `_state` về `RUNNING`, xóa/reseed `_window`
     (bắt buộc, xem phần rủi ro ở Bối cảnh), append `EpisodeEvent(type="replan", ...)`.
3. **`services/simulator/planbench_simulator/nav_stack.py::run_stack()`**:
   sau `engine.step(held_action)`, nếu engine vừa kết thúc với
   `STUCK`/`NO_PROGRESS` **và** `scenario.replanning_enabled` **và**
   `replan_count < scenario.max_replans`:
   - Lấy vị trí vật cản động hiện tại (method mới ở bước 2).
   - Dựng grid quy hoạch mới: bắt đầu từ grid tĩnh đã có (`raw_grid`),
     rasterize thêm vật cản động hiện tại như occupied tạm thời (tái
     dùng logic rasterize đã có trong `grid.py`, áp cho snapshot vật
     cản động thay vì tĩnh).
   - Gọi lại `global_planner.plan(grid_mới, start=engine.get_state().pose.position, goal=...)`.
   - Thành công: `local_planner.reset(new_plan.path, scenario.robot)`,
     gọi method recover ở engine, tăng `replan_count`, cộng dồn
     `PlanResult` mới vào danh sách theo dõi cho metrics.
   - Thất bại hoặc hết lượt: giữ nguyên STUCK/NO_PROGRESS như hiện tại
     (không đổi hành vi cuối).
4. **`packages/metrics/planbench_metrics/episode_metrics.py`**: thêm
   `replan_count: int = 0`, sửa cách tính `global_planning_time`/
   `expanded_nodes` thành tổng cộng dồn (theo Quyết định thiết kế).
5. **`packages/benchmark/planbench_benchmark/runner.py`**: không cần
   đổi gì về mặt logic (chỉ truyền thêm `replan_count` xuyên qua, giống
   `local_planner_latencies` hiện tại) — kiểm tra lại chữ ký
   `compute_episode_metrics()` lúc code thật để chắc không sót tham số.

### Test

- `tests/test_engine.py` (mở rộng): test "recover" method reset đúng
  state, **quan trọng nhất — test cửa sổ stuck được reseed đúng**
  (không kích hoạt lại STUCK ngay bước kế tiếp sau recover).
- Test "tiền đề" chứng minh feature thật sự hoạt động, không chỉ chạy
  không lỗi: dựng 1 scenario mà đường global duy nhất bị 1 vật cản động
  **đứng chắn tạm thời** đúng lúc robot tới gần — assert: **tắt**
  `replanning_enabled` → episode STUCK; **bật** → episode SUCCESS. Đây
  là test bắt buộc phải có, chứng minh giá trị thật của feature.
- Test công bằng: 2 `BenchmarkSpec` có `scenario` giống hệt (cùng
  `replanning_enabled`/`max_replans`) nhưng khác algorithm →
  `conditions_checksum` phải **giống nhau**; đổi `max_replans` giữa 2
  cái → checksum phải **khác nhau** — xác nhận cơ chế công bằng #2 hoạt
  động đúng như thiết kế.
- Test riêng xác nhận `local_planner.reset()` gọi lại giữa episode an
  toàn với **cả DWA và PPO**, không chỉ pure_pursuit (rủi ro đã nêu ở
  Bối cảnh) — nếu DWA/PPO có state nội bộ giả định reset() chỉ gọi 1
  lần, phải sửa chúng trước, không giả định an toàn.

### `docs/KNOWN_LIMITATIONS.md` — mục mới khi làm

- `path_efficiency`/`planned_path_length` đổi ý nghĩa khi có replan
  (đường cuối cùng, không phải đường duy nhất suốt episode) — không so
  sánh trực tiếp giữa run có/không replan.
- `max_replans` cố định theo scenario, chưa tunable qua Optuna (P01) —
  cố tình, tránh mở cửa bất công bằng trước khi có cơ chế tune đúng.
- Replan dùng lại đúng `global_planner` instance của thuật toán đang
  test (A* recompute nhanh/deterministic; RRT* recompute là 1 cây random
  mới từ state ban đầu — đây là khác biệt thật giữa 2 thuật toán, không
  phải thiên vị, vì luật trigger giống hệt nhau).

### Verification

1. `PYTHONPATH= .venv/bin/pytest tests/ -q` — toàn bộ pass, đặc biệt
   test "tiền đề" (mục Test) phải pass thật, không skip.
2. Chạy benchmark thật trên `dynamic_warehouse`/`crossing_obstacle`
   (thư viện có sẵn) với `replanning_enabled=True` — xem qua replay
   (Phase 3b-3), xác nhận **thấy được** lúc robot đổi hướng giữa chừng
   khi vật cản chặn đường.
3. So `conditions_checksum` giữa 1 benchmark bật và 1 benchmark tắt
   replanning trên cùng scenario gốc — phải **khác nhau** (vì
   `replanning_enabled` là field khác trong scenario) — xác nhận không
   thể vô tình so sánh 2 kết quả không cùng luật chơi mà tưởng là cùng.
4. Commit sau khi (1)-(3) xanh, rồi dừng chờ nghiệm thu — giống mọi
   phase trước, không tự ý làm tiếp việc khác.

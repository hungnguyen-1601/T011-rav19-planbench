# Plan: Config vật thể động trên form deployment

> Trạng thái: **chờ approve**. Chưa triển khai dòng code nào.
> Ngày lập: 2026-08-15. Nhánh hiện tại: `tongduyan_plannerselector`.
> **Bản v5** — bốn vòng review của An cùng ngày, các điểm đều kiểm chứng
> đúng và nhận hết. Thay đổi lớn: (v2) bỏ client-side contract
> validation, thêm endpoint dry-run; (v3) client rút xuống chỉ còn
> parse/completeness, dry-run trả 422 cùng envelope với create, ghi đúng
> phạm vi dry-run (không thấy xung đột id), preview phủ cả ba nguồn map;
> (v4) chấp nhận lỗi traffic có path thô `environment` (không hứa
> row-level), chốt contract state lỗi dry-run trong form, mapping preview
> đầy đủ theo `scenario_for` + drift test; (v5) mapping preview vá ba
> khoảng trống (`name` bắt buộc, `robot` project bỏ `type`/`control_period`,
> types TS cho `ScenarioPreviewRequest`/`SensorNoise`), test tích hợp
> bắn endpoint thật kỳ vọng 200, sửa wording mục tiêu #3 cho khớp v4.

## 0. Bối cảnh — "chưa config được" nghĩa là gì

Khảo sát 2026-08-15 cho thấy **backend đã hỗ trợ đầy đủ** vật thể động:

- Schema 4 motion kind (`waypoint`, `periodic`, `random_walk`, `sudden_stop`)
  là union đóng trong `packages/schemas/planbench_schemas/dynamic.py:93-96`,
  chuyển động là hàm thuần `(spec, time, seed)` qua `position_at`.
- `TaskProfile.environment.dynamic_obstacles` nhận tuple `DynamicObstacle`
  (`task_profile.py:127-130`), có 3 validator cưỡng chế lúc nạp
  (`task_profile.py:242-310`): tên duy nhất; motion tất định phải có
  `seed_time_offset > 0` (chống bẫy "300 seed = 1 episode", HĐ-3.3);
  periodic phải có offset ≥ một chu kỳ đầy đủ.
- `v_obstacle_max` được đối chiếu với `max_speed()` của mọi obstacle lúc
  nạp (`task_profile.py:192-240`).
- Hai profile đang ship đã khai traffic bằng tay trong YAML:
  `profiles/warehouse_crossing_v1.yaml:96-114`, `warehouse_a_v2.yaml:72-87`.

Cái **chưa có** là đường cho user khai qua UI:

| Chỗ | Hiện trạng |
|---|---|
| Form `/deployments` | Chỉ **chở** traffic của scenario thư viện được chọn (`DeploymentForm.tsx:230`); map vẽ tay/store thì **xoá trắng** traffic (`adopt()`, dòng 220-232). Không thêm/sửa/xoá được. |
| Editor cũ `/scenarios/[id]` | Author được nhưng chỉ kind `waypoint`, 4 cột, tham số mặc định hardcode (`page.tsx:173-188`). Thuộc luồng cũ chờ nghỉ hưu (nợ D4). |
| TS types | `Motion = WaypointMotion \| PeriodicMotion` (`apps/web/src/lib/types.ts:87`) — **thiếu** `RandomWalkMotion`, `SuddenStopMotion`. |
| Test pin | `tests/test_form_covers_the_contract.py:175-217` (`TestTrafficIsCarriedButNotYetAuthored`) pin ranh giới "chở nhưng chưa author". |

## 0b. Nguyên tắc thiết kế phải giữ (chốt qua hai vòng review)

1. **"The form decides nothing" — hiểu triệt để.** Server là nguồn phán
   quyết duy nhất (`DeploymentForm.tsx:3-10`, `deployments.ts:11-13`,
   test `deployments-page.test.tsx:107`, `:434`). Vòng v2 còn giữ lại
   "client check cú pháp: số dương, hai đầu periodic khác nhau, ≥ 2
   waypoint" — vòng v3 nhận ra **đó vẫn là chép luật**: `gt=0`,
   `min_length=2`, distinct-endpoints đều là constraint Pydantic thật
   (`dynamic.py:41-42, 60, 63-67`). Chưa kể "name không rỗng" là luật
   backend **không có** (`name: str = "obstacle"`, không `min_length` —
   `dynamic.py:104`): client mà chặn là tự đặt thêm luật.
   **Ranh giới cuối cùng của client:**
   - parse được input thành number/point, đủ field để render và dựng
     object gửi đi — hết;
   - thuộc tính HTML `min`/`required` dùng như **gợi ý UX**, không phải
     verdict, không chặn submit;
   - mọi điều kiện dương, distinct endpoints, số waypoint, offset, tên
     trùng, `v_obstacle_max`... do **dry-run** phán.
   - Muốn cấm name rỗng thật ⇒ sửa schema + contract, việc riêng, ngoài
     scope.
2. **YAML một chiều, form → YAML** (test `:154` pin kèm lý do). Không
   làm chiều ngược trong plan này.
3. **Không cài lại luật chuyển động/tốc độ trong browser**
   (`routers/scenarios.py:90-97`; test `:111` cấm `Math.PI`). Cảnh báo
   `v_obstacle_max` vs traffic đến từ dry-run.

## 0c. Một defect runtime chặn ngang, phát hiện lúc làm Phase 1

**Đồng hồ vật cản băm theo *độ dài* tên, không phải nội dung tên.**
`_seed_time_shift` (`dynamic.py:192-200`) gọi
`_hashed_angle(seed, obstacle.seed_offset + len(obstacle.name), 0)`.
Nên hai vật cản khác tên nhưng **cùng độ dài tên và cùng `seed_offset`**
nhận đúng một độ trễ, tức chạy đồng pha — đúng thất bại mà validator
tên-duy-nhất tuyên bố là nó ngăn được.

Đo thực tế (`cart` vs `rack`, cùng `seed_time_offset = 20`):

| seed | cart | rack | forklift |
|---|---|---|---|
| 0 | 4.983802 | 4.983802 | 13.171391 |
| 1 | 3.354755 | 3.354755 | 11.781788 |
| 7 | 19.384681 | 19.384681 | 15.519864 |
| 42 | 12.660475 | 12.660475 | 4.894837 |

`position_at` của hai con trùng nhau ở mọi thời điểm lấy mẫu.

Đây **không chỉ là lỗi tài liệu**: chính backend cũng tuyên bố băm theo
tên — docstring `seed_time_offset` nói "a hash of (seed, name)"
(`dynamic.py:115`) và thông điệp từ chối trùng tên nói "the name is mixed
into each obstacle's seed hash, so two obstacles sharing one name would
move in lockstep" (`task_profile.py:276-277`). Cả hai đang mô tả thứ code
không làm.

Không profile nào đang ship trúng bẫy (mỗi profile một vật cản;
`dynamic_warehouse` có 9/8/25 nên không đụng) — nhưng đó là **may, không
phải thiết kế**, và nó thành bẫy thật ngay khi form cho người ta khai
nhiều vật cản, tức Phase 2b.

> **ĐÃ CHỐT 2026-08-15 — phương án (c), siết validator.** Khảo sát lúc
> chuẩn bị làm lộ thêm một cái giá không có trong hai lựa chọn dưới:
> **5/7 ca golden** `tests/golden/dwa_trajectories.json` chạy scenario có
> traffic lệch theo seed (bidirectional_corridor offset 16,
> dynamic_warehouse 14/28, sudden_stop ×2 offset 4), nên phương án (a)
> buộc phải regenerate golden — mà file đó tồn tại để chứng minh P2 tách
> `dwa_core` không đổi gì, và tự nó viết "the reason is never 'the test
> went red'". An chốt: **chặn khoá đồng hồ trùng ngay lúc nạp profile**,
> không đổi cách băm. Kết quả: đóng đúng bẫy lockstep, **không đổi một
> quỹ đạo nào** (golden xanh, 128 passed), không profile nào bị từ chối.
> Chi tiết ở report `tongduyan_config-vat-the-dong-phase-2b.md`.

**Hai lựa chọn ban đầu (giữ lại để đọc được quyết định):**

- **(a) Sửa `_seed_time_shift` băm toàn bộ tên** — khớp lại schema
  description và lý lẽ của validator. **Cái giá phải nói rõ**: đây là
  đổi hành vi simulator, cùng profile + cùng seed sẽ cho traffic timing
  khác trước, nên **mọi kết quả đã lưu không tái lập được bằng code
  mới** (manifest ghim `git_sha` nên vẫn truy được, nhưng phải nói ra);
  kèm regression test hai tên cùng độ dài phải khác pha.
- **(b) Giữ `len(name)` là chủ đích** — thì phải sửa docstring
  `dynamic.py:115`, thông điệp `task_profile.py:276-277`, và **không**
  được hứa ở bất kỳ đâu rằng tên duy nhất ngăn được lockstep; UI phải
  nói người dùng tự đặt `seed_offset` khác nhau.

Copy phía UI viết ở Phase 1 đã được gỡ mọi tuyên bố về cơ chế băm, nên
nó đúng dưới **cả hai** phương án và không chặn việc chọn.

## 1. Mục tiêu / Không-mục-tiêu

**Mục tiêu**

1. Trên form `/deployments`, user thêm/sửa/xoá được vật thể động cho mọi
   nguồn map (thư viện, vẽ tay, store), đủ cả 4 motion kind.
2. Traffic chở từ scenario thư viện thành **điểm xuất phát sửa được**.
3. Lỗi hợp đồng hiển thị **sau thao tác "Kiểm tra" hoặc submit**, tại
   **path backend cung cấp** (lỗi traffic từ model validator là path thô
   `environment`), **cùng envelope** với create — không hai kiểu lỗi.
4. Preview chuyển động trên canvas cho **cả ba nguồn map**, tái dùng
   `position_at` server-side.

**Không-mục-tiêu**

- Không field/motion kind mới trong schema. Không `count`/`density`.
- Không YAML → form.
- Không gỡ editor cũ `/scenarios/[id]` — dọn D4 là đợt riêng.
- Không sửa semantics `v_obstacle_max` (L18) và không thêm `min_length`
  cho `name`.
- Đợt này chỉnh traffic trên **flat view**; 2.5D chỉ hiển thị — và phần
  hiển thị đó cần bước chuyển đổi kết quả preview về
  `ObstacleSnapshot {name, x, y, radius}` (`types.ts:153`) cho renderer
  2.5D dùng chung.

## 2. Các phase

### Phase 1 — Đồng bộ types TS + i18n (nhỏ, làm trước)

- `apps/web/src/lib/types.ts`: thêm `RandomWalkMotion`, `SuddenStopMotion`;
  mở union `Motion` thành 4 kind (dòng 87), field khớp 1-1 `dynamic.py:70-90`.
- Hai `seed_offset` khác nhau (`DynamicObstacle.seed_offset` và
  `RandomWalkMotion.seed_offset`) — UI phân biệt bằng nhãn/tooltip.
- **Types cho preview** (vòng review 4 — TS hiện chưa đủ để giữ lời hứa
  `previewRequestOf`): thêm `ScenarioPreviewRequest`
  (`{map_id, scenario, time, seed}`); thêm type `SensorNoise`; bổ sung
  `Scenario` (types.ts:100) các field `sensor_noise?`,
  `clearance_preference?`, `stuck_time_window?` (optional — backend có
  default, nhưng adapter sẽ điền để preview trung thực với deployment).
- i18n: khai toàn bộ key mới trong `en.json` + `vi.json`.

**DoD:** `tsc` sạch; chưa đổi hành vi.

### Phase 2a — Backend: dry-run `POST /task-profiles/validate`

Phần backend duy nhất, thuần additive, không đụng schema:

- **Tách service trước**: `TaskProfileService.validate(payload)` chứa
  đúng phần `TaskProfile.model_validate` + map lỗi mà `create()` đang
  làm; `create()` và endpoint mới **cùng gọi nó** — không hai chỗ tự bọc
  model_validate.
- **Hợp đồng response, chốt phương án 422**: invalid → **422 cùng
  envelope với create** (đi qua `DomainValidationError` như mọi refusal
  hiện tại), để client dùng nguyên `authFetch` → `FieldError` →
  `fieldErrorsOf` (`auth.ts:207-231`) và `errorFor(path)` — **đúng một
  code path lỗi** cho cả validate lẫn create. Valid → **204**, không
  body. Không dựng schema report riêng.
- **Phạm vi ghi rõ trong docstring**: dry-run kiểm **nội dung** (HĐ-2 /
  schema), **không đọc store** ⇒ **không thấy** xung đột id /
  `same_deployment` (HĐ-3.1) — lỗi đó vẫn xuất hiện lúc `POST
  /task-profiles` thật, qua đúng envelope lỗi đang có. Đổi lại endpoint
  thuần, không side effect.
- **Path lỗi traffic là thô, và plan chấp nhận điều đó** (đo thực tế
  vòng review 3): cả 4 ca lỗi traffic (tên trùng / offset thiếu /
  partial-cycle / `v_obstacle_max` < `max_speed`) đều do model validator
  trên `EnvironmentSpec` nên Pydantic trả `loc = ("environment",)` —
  `field_errors` (`errors.py:40-60`, nối loc bằng dấu chấm) cho ra path
  `environment`, không phải `environment.dynamic_obstacles.2...`.
  Acceptance criterion: **hiển thị đúng path backend cung cấp**, không
  cam kết mọi lỗi có row-level path. Muốn path chỉ đúng obstacle/field
  là refactor validation backend riêng — ngoài scope.
- Test API: 4 ca lỗi trên trả 422 với **expected path `environment`**;
  ca hợp lệ trả 204; gọi validate xong store không đổi; `create()` sau
  refactor vẫn hành xử y nguyên (chạy lại suite tạo profile).

**DoD:** như trên; suite API xanh.

### Phase 2b — TrafficEditor trong DeploymentForm (lõi)

Component mới `apps/web/src/components/TrafficEditor.tsx`:

- **Controlled, không state riêng**: danh sách obstacle sống duy nhất
  trong `draft` (`environment.dynamic_obstacles`); TrafficEditor nhận
  `DynamicObstacle[]` + `onChange`. Boundary với
  `ProfileDraft = Record<string, unknown>` (cố ý loose,
  `deployments.ts:24`) qua một hàm narrow tập trung
  `trafficOf(draft): DynamicObstacle[]`.
- **Placement mode hợp nhất, thuộc DeploymentForm**: mở rộng
  `PlacementMode` (`MissionPlacer.tsx:35`) thành
  `none | mission-start | mission-goal | waypoint | periodic-start |
  periodic-end | random-walk-origin | sudden-stop-start |
  sudden-stop-heading`; MissionPlacer nhận mode từ ngoài; nút + caption
  cho biết click tiếp theo làm gì.
- **Semantics từng kind**:
  - `waypoint`: click gom điểm; toggle `loop`/`ping_pong`;
  - `periodic`: hai click start/end;
  - `random_walk`: một click chọn `origin`; field `speed`,
    `change_interval`, `max_radius`, `seed_offset` (của motion);
  - `sudden_stop`: click 1 = `start`; click 2 **chỉ suy ra**
    `heading = atan2(y2−y1, x2−x1)`, không lưu điểm end.
  Mọi ràng buộc giá trị (dương, distinct, đủ waypoint...) để dry-run
  phán — client chỉ cần đủ dữ liệu dựng object.
- **Gợi ý `seed_time_offset`** — điền sẵn khi field trống, không ghi đè:
  `ping_pong` = (dài lộ trình × 2)/speed; `loop` = (dài lộ trình + cạnh
  đóng)/speed; cả hai false = không gợi ý số, chỉ chú thích "obstacle đỗ
  sau khi đi hết lộ trình, offset vẫn phải > 0"; `periodic` = `period`.
  (Là gợi ý điền form, không phải verdict — verdict vẫn của dry-run.)
  **Guard bắt buộc** (hệ quả của việc client không validate): chỉ tính
  khi `speed`/`period` **finite và > 0** — input trống/0/NaN thì helper
  trả "không gợi ý", tuyệt đối không sinh `Infinity`/`NaN` vào draft.
- **`changeMotionKind` dựng object mới theo canonical shape**: đổi kind
  là tạo motion mới đúng field của kind đích, **vứt toàn bộ key của kind
  cũ** — không spread giữ key thừa (waypoint đổi sang periodic mà còn
  `waypoints` lạc trong object là gửi rác lên server; `_MotionBase`
  không `extra="forbid"` nên rác bị nuốt im lặng).
- **Dry-run nối dây — contract state lỗi chốt rõ** (vòng review 3 chỉ ra
  `fieldErrors` hiện là prop read-only từ page, `DeploymentForm.tsx:121-129`):
  - `DeploymentForm` sở hữu state cục bộ `dryRunErrors`;
  - `effectiveErrors = merge(fieldErrors từ create, dryRunErrors)`;
    `errorFor` (`:259-261`) đọc từ `effectiveErrors`;
  - validate 204 → clear `dryRunErrors`; validate 422 → set
    `dryRunErrors`, **không gọi `onSubmit`**;
  - user sửa field → xoá toàn bộ `dryRunErrors` (chọn phương án thô,
    đơn giản; xoá theo field không đáng vì path lỗi traffic vốn thô);
  - page vẫn sở hữu lỗi create — không đổi `DeploymentFormProps` ngoài
    việc thêm gì cần cho dry-run.
  - **Chỗ render lỗi path `environment`**: đầu khối TrafficEditor có một
    dòng `errorFor("environment")` — không có nó thì 4 lỗi traffic ở
    trên tàng hình với user. Nếu backend trả path sâu hơn (lỗi
    per-field Pydantic thường như `radius` âm) thì gắn đúng row/field.
  - Nút "Kiểm tra" + tự gọi trước submit (điểm quyết #3). Chú thích tĩnh
    L18 cạnh checkbox `v_obstacle_max`.
- **`adopt()` + activeMapId** (sửa theo review v3): map vẽ tay **đã có
  `map_id`** — `DrawNewMap.save()` gọi `api.createMap` rồi
  `onSaved(created.map_data, created.id)` → `adopt(data, id, null)`
  (`DeploymentForm.tsx:854-858, 705`), rồi `materialiseMap(mapId)`
  (`:226`). Lỗi thật chỉ là state id map đang chọn không được cập nhật
  cho mọi nguồn. Fix: đổi state thành `activeMapId`;
  `adopt(data, mapId, scenario)` luôn `setActiveMapId(mapId)` cho cả
  library / store / drawn. Traffic: library đổ vào draft (sửa được);
  store/drawn khởi tạo rỗng thay vì khoá.
- **Preview cho cả ba nguồn map**: adapter
  `previewRequestOf(draft, start, goal, activeMapId, seed, time):
  ScenarioPreviewRequest` (đúng kiểu request của `/scenarios/preview` —
  `schemas.py:78`, `routers/scenarios.py:86-115` — gồm cả `time`,
  `seed`). Scenario dựng ra phải **đầy đủ và hợp lệ**, mapping bám
  `scenario_for` (`episode.py:97-117`) — nguồn chân lý của "profile
  thành scenario":
  | Scenario field | Lấy từ |
  |---|---|
  | `name` | identifier preview **ổn định** (vd. `"deployment-preview"` — `Scenario.name` bắt buộc, `scenario.py:68`; thiếu là 422) |
  | `description` | `""` hoặc mô tả preview |
  | `robot` | **project đúng các field của `RobotConfig`** — không phải `draft.robot` nguyên khối: `_robot_config` (`episode.py:182-191`) cố ý vứt `type` và `control_period` (control_period thành `simulation_dt`, không được có hai field một nghĩa) |
  | `start_pose` / `goal_pose` | start/goal local state |
  | `goal_tolerance` | `constraints.goal_tolerance_m` |
  | `timeout_seconds` | `constraints.episode_timeout_s` |
  | `simulation_dt` | `min(0.05, robot.control_period)` (MAX_SIMULATION_DT) |
  | `dynamic_obstacles` | `environment.dynamic_obstacles` |
  | `sensor_noise` | `environment.sensor_noise` |
  | `clearance_preference` | `draft.clearance_preference` |
  | `random_seed` | seed user chọn cho preview |
  | `stuck_time_window` | `constraints.stuck_threshold_s` |
  Unit test **chống drift**: pin danh sách field này đối chiếu hai phía
  (nếu `scenario_for` thêm field, test nhắc adapter); unit test khẳng
  định `robot` trong request **không chứa** `type`/`control_period`; và
  **một test tích hợp bắn payload của adapter vào endpoint thật, kỳ
  vọng 200** — snapshot object phía TS không đủ, vì 422 chỉ lộ khi đi
  qua Pydantic thật. Ghi chú phương án
  dự phòng nếu adapter hoá ra rườm rà: endpoint nhỏ
  `POST /task-profiles/preview-traffic` tái dùng thẳng `scenario_for`
  server-side, xoá hẳn lớp drift này — chỉ làm nếu An muốn, không mặc
  định (đợt này theo phương án adapter như review đề).
- **Comment/locale hết hạn sửa cùng lúc**: comment
  `DeploymentForm.tsx:560-562`; `deployments.form.noiseNote` (en+vi);
  `deployments.mode.note`; **`nav.desc.scenarios`** = "Kept until the
  deployment form can draw obstacles" (phát hiện lúc làm Phase 1 — câu
  này mô tả đúng lý do `/scenarios` còn sống, và Phase 2b làm nó sai).

**DoD:** khai được profile tương đương `warehouse_crossing_v1.yaml`
(đúng từng field, kể cả `ping_pong: true, loop: false,
seed_time_offset: 45`) hoàn toàn bằng form; dry-run trả 204;
`POST /task-profiles` trả **201**; preview chạy trên map thư viện, map
store và map vẽ tay; cả 4 ca lỗi traffic hiện **nhìn thấy được** tại
khối TrafficEditor (qua `errorFor("environment")`), không tàng hình.

### Phase 3 — Tests, theo đúng hạ tầng đang có

Ràng buộc: Vitest chạy **Node, không jsdom, không testing-library**
(`apps/web/vitest.config.ts:15-18`) — chỉ có `renderToStaticMarkup`.

- **Hàm thuần / reducer, test trực tiếp**: `changeMotionKind` (đổi kind
  vứt sạch key kind cũ — assert không còn key thừa), `suggestSeedTimeOffset`
  (3 nhánh + periodic, **và các ca guard**: speed/period = 0, NaN,
  Infinity, field trống → không gợi ý), reducer thêm/sửa/xoá obstacle +
  waypoint, `trafficOf`, `previewRequestOf` (drift test đối chiếu field
  list với `scenario_for`), chuyển đổi snapshot cho 2.5D, heading từ hai
  click, merge/clear `dryRunErrors`. (Không còn `trafficWarnings` kiểu
  luật — client không phán.)
- **Source/render pin cho wiring**: TrafficEditor mount, mode controller
  tồn tại, `errorFor` nối vào field traffic, `setActiveMapId` trong
  `adopt`.
- **Test phải sửa/xoá vì ranh giới dời**:
  - `tests/test_form_covers_the_contract.py:175-217` → thay bằng
    `TestTrafficIsAuthorable`: có đường khai 4 kind, có
    `seed_time_offset`, **pin điều mới** — dry-run được gọi, TSX không
    chứa bản sao luật (grep cấm pattern so sánh kiểu `offset < period`);
  - `deployments-page.test.tsx:434` → viết lại: phán quyết đến từ
    `/task-profiles/validate`;
  - `:425` → cập nhật theo `adopt()` mới;
  - `:143` → viết lại theo noiseNote mới;
  - `:107` "writes no contract rule of its own" → **giữ**, mở rộng phạm
    vi grep sang TrafficEditor.tsx cho trung thực.
- **Checklist thủ công** (browser): click gom waypoint, heading từ hai
  click, preview cả ba nguồn map, 2.5D chỉ hiển thị. Kết quả ghi vào
  report.
- Backend: test Phase 2a; chạy lại `tests/test_task_profile.py`,
  `tests/api/test_api_scenario_editor.py`, suite tạo profile (vì
  refactor service).

**DoD:** suite xanh; không test nào pin ranh giới cũ; checklist có kết
quả.

### Phase 4 — Giấy tờ

- Cập nhật nợ D4 trong
  `docs/antongduy/notes/2026-08-13/tongduyan_no-ky-thuat-ton-dong.md`.
- Report theo quy ước, kèm checklist thủ công.

## 3. Rủi ro

| Rủi ro | Đánh giá |
|---|---|
| Checksum scenario đổi hàng loạt | Không xảy ra — không field schema mới. |
| Xung đột id / `same_deployment` (HĐ-3.1) | **Dry-run không thấy** (không đọc store, ghi rõ trong docstring). Lỗi xuất hiện lúc POST create thật, qua đúng envelope lỗi hiện có — chấp nhận, giữ endpoint thuần. |
| Type safety | TrafficEditor dùng `DynamicObstacle[]` có kiểu; `ProfileDraft` vẫn loose cố ý — an toàn kiểu chỉ trong ranh giới `trafficOf`. |
| Refactor `create()` sang service.validate | Rủi ro hồi quy thấp nhưng thật — chặn bằng chạy lại suite tạo profile (Phase 3). |
| Hai luồng UI cùng author được | Quá độ có chủ đích trước khi dọn D4; ghi trong report. |
| L18 khi bật `v_obstacle_max` | Không sửa; chú thích cạnh checkbox. |

## 4. Thứ tự & ước lượng

Phase 1 (½ buổi) → Phase 2a (½–1 ngày, gồm refactor service) → Phase 2b
(2 ngày) → Phase 3 (1 ngày) → Phase 4 (½ buổi). Tổng ≈ 4 ngày.

## 5. Điểm cần An quyết trước khi làm

1. **Đủ 4 kind ngay từ đầu?** Đề xuất: đủ 4.
2. **Editor cũ `/scenarios/[id]`** nghỉ hưu cùng đợt hay đợt riêng?
   Đề xuất: đợt riêng.
3. **Dry-run gọi lúc nào**: debounce theo draft, hay nút "Kiểm tra" + tự
   gọi trước submit? Đề xuất: phương án sau — rẻ, dễ đoán, không spam.
4. **Đồng hồ băm `len(name)` hay toàn bộ tên** (mục 0c) — **chặn Phase
   2b**. Đề xuất: (a) sửa cho khớp schema, kèm regression test và một
   dòng trong report nói rõ kết quả cũ không tái lập bằng code mới.

(Câu hỏi cũ #4 về preview map vẽ tay đã bỏ — map vẽ tay có `map_id` sẵn,
preview phủ cả ba nguồn trong scope.)

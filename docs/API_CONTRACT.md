# API Contract — PlanBench Backend (M2)

Base URL: `/api/v1`. OpenAPI đầy đủ tại `/openapi.json`, docs tại `/docs`.

Mọi lỗi trả về dạng chuẩn:

```json
{"error": {"code": "not_found | validation_error | invalid_state | request_validation_error | internal_error", "message": "...", "details": [...]}}
```

## Endpoints

| Method | Path | Mô tả |
|---|---|---|
| GET | /health | `{status, app, version}` |
| GET/POST | /maps | Danh sách (summary, không kèm cells) / tạo map (body = MapData) |
| GET/PUT/DELETE | /maps/{id} | Đọc / cập nhật (version+1) / xóa |
| POST | /maps/validate | Kiểm tra semantic (ngoài schema) → `{valid, errors}` |
| GET/POST | /scenarios | Danh sách / tạo `{map_id, scenario}` (validate placement với map) |
| GET/PUT/DELETE | /scenarios/{id} | CRUD scenario |
| POST | /scenarios/validate | `{map_id, scenario}` → `{valid, errors}` |
| POST | /scenarios/preview | `{map_id, scenario, time, seed}` → vị trí vật cản động tại thời điểm đó + verdict |
| GET | /algorithms | Registry; `astar_pure_pursuit` là reference stack, `benchmarkable=false` |
| GET/POST | /simulations | Danh sách / tạo `{map_id, scenario_id, algorithm, replanning?}` |
| GET | /simulations/{id} | Trạng thái session (`created`/`finished`) |
| POST | /simulations/{id}/run | Chạy headless đồng bộ → plan + result + metrics (409 nếu chạy lại) |
| GET | /simulations/{id}/result | Kết quả đầy đủ (null nếu chưa chạy) |
| GET/POST | /benchmarks | Danh sách / tạo `{name, map_id, scenario_id, algorithms, runs_per_algorithm, seeds?}` |
| GET | /benchmarks/{id} | Metadata benchmark |
| POST | /benchmarks/{id}/run | Chạy tuần tự mọi (algorithm × seed) → runs + aggregates |
| GET | /benchmarks/{id}/results | Kết quả đã lưu |
| GET | /benchmarks/{id}/report.md | Toàn bộ report dạng Markdown (`text/markdown`, tải về) |

## WebSocket

`/ws/simulations/{id}?speed=N&pace=true|false` (không nằm dưới /api/v1):

- Simulation phải ở trạng thái `finished` (episode chạy headless
  faster-than-real-time; WS phát lại trajectory đã ghi — quyết định D16).
- `pace=true` (mặc định): server điều nhịp theo `sim_time/speed`, cap
  tần suất bởi `PLANBENCH_WS_MAX_RATE_HZ` (mặc định 60 Hz); frame vượt
  cap bị **bỏ**, không bị trễ. Dùng cho live view đơn giản.
- `pace=false`: gửi **mọi** frame nhanh nhất có thể, không bỏ frame.
  Dùng khi client tự điều nhịp (pause/scrub/speed) — web UI dùng chế độ
  này. (Bug đã sửa trong M3: UI pace cục bộ + `pace=true&speed` cao làm
  mất gần hết trajectory.)
- Message: `{type: "start", plan_path, steps}` → nhiều
  `{type: "state", time, x, y, theta, linear_velocity, angular_velocity}`
  → `{type: "result", status, reason, elapsed_time, metrics}`.
- Lỗi: `{type: "error", code: "not_found" | "not_ready"}` rồi đóng.

## Authentication (M11 — thay thế contract M4)

Không còn role `operator`/`reviewer`. Mọi người đăng nhập đều là
**member**; quyền làm gì phụ thuộc vào **quyền sở hữu benchmark**, không
phụ thuộc nhãn tài khoản. `admin` giữ lại cho vận hành nội bộ (gỡ kẹt
một review mà người duyệt đã nghỉ), và mọi hành động của admin đều được
ghi vào audit trail như người khác.

| Method | Path | Mô tả |
|---|---|---|
| GET | /auth/providers | `{google, github, dev_login}` — deployment này thực sự bật gì. Trang login render từ đây |
| GET | /auth/oauth/{provider}/start | 307 sang provider; đặt cookie state httpOnly đã ký (chống CSRF) |
| GET | /auth/oauth/{provider}/callback | Provider gọi lại; đổi code lấy token **phía server**, rồi 307 về `{web}/auth/callback?code=<one-time>` |
| POST | /auth/oauth/exchange | `{code}` → `{access_token, token_type, expires_in, user}`. Code dùng một lần, hết hạn sau 120s |
| POST | /auth/oauth/{provider}/link | Cần bearer token. Bắt đầu liên kết provider thứ hai vào tài khoản đang đăng nhập → `{authorize_url}` |
| POST | /auth/login | Form `username`/`password`. **Chỉ hoạt động khi `PLANBENCH_ENABLE_DEV_LOGIN=true`**, ngược lại 401 |
| GET | /auth/me | `{id, nickname, email, display_name, avatar_url, is_admin, needs_nickname, providers[]}` |

`provider` ∈ `google | github`.

Bất biến về bảo mật, mỗi cái có test tương ứng:

- Client secret **chỉ tồn tại ở server**; browser không bao giờ thấy.
- JWT **không bao giờ nằm trong URL** — callback trả code dùng một lần,
  đổi lấy token qua POST.
- `state` được ký HMAC trong cookie httpOnly; lệch state → từ chối.
  PKCE S256 cho Google (GitHub OAuth App không hỗ trợ).
- Chỉ tin email **provider đã xác minh**; email chưa xác minh bị bỏ.
- **Không tự động gộp** hai tài khoản chỉ vì trùng email. Liên kết
  Google + GitHub vào một tài khoản là hành động chủ động qua
  `/auth/oauth/{provider}/link` khi đã đăng nhập.
- Một identity provider không thể gắn vào hai tài khoản PlanBench.

## Users & nicknames (M11)

| Method | Path | Mô tả |
|---|---|---|
| GET | /users/search?nickname= | Tìm theo **tiền tố**, không phân biệt hoa thường → `[{id, nickname, display_name, avatar_url}]`. Không trả email, không trả cờ admin |
| GET | /users/nickname-available?nickname= | `{nickname, available, valid, message}` — trả lời chứ không báo lỗi, vì gọi theo từng ký tự |
| PUT | /users/me/nickname | `{nickname}` → user resource. Unique không phân biệt hoa thường |

Nickname: 3–30 ký tự, chỉ chữ/số/`_`/`-`, không khoảng trắng.
**Nickname không bao giờ là khóa phân quyền** — chỉ để tìm người. Phân
quyền luôn dùng user ID (bất biến), nên đổi tên hay chiếm lại một
nickname đã bỏ đều không kế thừa được gì.

## Reviews (M11)

Review là **tùy chọn**. Mặc định không có ai trong quy trình: chủ sở hữu
tạo → Run → tự Accept. Nhờ review là hành động chủ động, và khi đã nhờ
thì chính chủ **mất** quyền tự quyết ở giai đoạn đó.

| Method | Path | Ai được gọi | Mô tả |
|---|---|---|---|
| POST | /benchmarks/{id}/review-requests | owner | `{reviewer_nickname, stage, comment}`, `stage` ∈ `spec\|result` → 201 ReviewRequest |
| GET | /benchmarks/{id}/review-requests | any | Mọi yêu cầu của benchmark |
| POST | /benchmarks/{id}/review-requests/{rid}/cancel | người đã gửi | Rút lại yêu cầu đang chờ |
| GET | /reviews/inbox?pending_only= | any | `{requests[], pending}` — `pending` là số cho badge |
| GET | /reviews/sent | any | Những yêu cầu tôi đã gửi |
| POST | /reviews/{rid}/approve | **chỉ** người được chỉ định | `{comment}` → duyệt, đồng thời chuyển state benchmark |
| POST | /reviews/{rid}/reject | **chỉ** người được chỉ định | `{comment}` → từ chối |
| POST | /reviews/{rid}/comment | người gửi hoặc người duyệt | Bình luận mà **không** quyết định (giữ nguyên pending) |
| POST | /reviews/{rid}/cancel | **chỉ** người đã gửi | Rút lại |

Quy tắc, mỗi cái là một test:

- `spec` review chặn **Run**; `result` review chặn **Accept results**.
- Không tự gửi review cho chính mình (422).
- Nickname không tồn tại → 422 kèm tên đã nhập.
- Người khác (kể cả chủ sở hữu) trả lời hộ → **403**.
- Một yêu cầu chỉ trả lời được một lần (422 lần sau).
- Mỗi stage chỉ có tối đa một yêu cầu đang chờ.
- Gửi `spec` review khi benchmark còn `draft` cũng chính là submit — nếu
  không, phê duyệt thật của người duyệt sẽ không có cạnh nào để đi và
  bị ghi nhầm thành `self_approved`.

## Benchmarks (M11 — thay thế contract M4)

| Method | Path | Ai được gọi | Mô tả |
|---|---|---|---|
| GET/POST | /benchmarks | any / any | Danh sách / tạo `{name, map_id, scenario_id, algorithms:[{id,config}], seeds:[...]}` → state `draft`, người tạo là owner |
| GET | /benchmarks/{id} | any | Metadata + audit trail + `is_owner` + `review_requests[]` |
| POST | /benchmarks/{id}/submit | owner | draft/rejected → pending_approval |
| POST | /benchmarks/{id}/approve | người duyệt được chỉ định, hoặc admin | pending_approval → approved (**gate 1**) |
| POST | /benchmarks/{id}/reject | người duyệt được chỉ định, hoặc admin | pending_approval → draft |
| POST | /benchmarks/{id}/cancel | owner | → cancelled |
| POST | /benchmarks/{id}/run | owner | Tự mở gate 1 (ghi `self_approved`) rồi chạy → pending_review; trả `{benchmark, report}` |
| POST | /benchmarks/{id}/accept-result | owner, hoặc người duyệt result | pending_review → accepted (**gate 2**) |
| POST | /benchmarks/{id}/reject-result | owner, hoặc người duyệt result | pending_review → rejected |
| GET | /benchmarks/{id}/results | any | Report đã lưu (null nếu chưa chạy) |
| GET | /benchmarks/{id}/episodes | any | Danh sách episode + artifact URI/checksum/size |
| GET | /benchmarks/{id}/report.md | any | Report dạng Markdown; **409** nếu benchmark chưa chạy |

**Đọc thì mở, làm thì khóa.** Ai đăng nhập cũng xem được mọi benchmark —
leaderboard chung chỉ có ý nghĩa khi xem được các run đằng sau nó. Mọi
endpoint thay đổi trạng thái đều tự kiểm tra quyền sở hữu.

Body của các action nhận `{comment}` — được ghi vào audit trail cùng
user ID, nickname, thời điểm, và `review_request_id` khi hành động đó
trả lời một yêu cầu review.

Chạy sai trạng thái trả **409 invalid_state**; không đủ quyền trả
**403 forbidden**. Hai cái khác nhau: 409 là "không làm được lúc này",
403 là "không phải việc của bạn".

State machine giữ nguyên (`draft`, `pending_approval`, `approved`,
`running`, `pending_review`, `accepted`, `rejected`, `cancelled`,
`failed`) nên benchmark cũ vẫn đọc được và vẫn mang đúng nghĩa cũ. Chỉ
**ai** được đi mỗi cạnh là thay đổi.

`report` gồm: `spec`, `fairness` (bằng chứng công bằng, có
`conditions_checksum`), `runs[]` (mỗi (algorithm, seed)), `aggregates[]`
(success/collision/timeout/stuck/no_progress rate; mean travel time,
path efficiency, smoothness — **chỉ tính trên episode thành công**;
clearance và latency tính trên mọi episode).

**Metric F05 (cấp episode).** `runs[].metrics` từ Đợt 3.2 có thêm, bên
cạnh field cũ (không field nào bị xóa): `smoothness_squared` (spec 8.2,
`Σ(Δθ)²`; field `smoothness` cũ là heading-change rate `Σ|Δθ|/L`, giữ
nguyên nghĩa, đã deprecated), `local_planning_latency_p50/p95/p99`,
`stop_and_go_count`, `near_miss_count`, `time_to_first_collision`, và
`metric_config` — bản chụp ngưỡng versioned (`version`,
`stop_speed_threshold`, `resume_speed_threshold`,
`near_miss_clearance_threshold`) mà các count được tính dưới đó. Metrics
lưu trước F05 trả `null` cho toàn bộ field mới; `null` nghĩa là "không
tính", **không** phải 0. Aggregate chưa tổng hợp các metric này.

**Replanning (Đợt 4.1, nối dây `/simulate` ở Đợt B).** `POST /benchmarks`
**và** `POST /simulations` đều nhận trường tùy chọn
`replanning: {enabled, max_replans}`. Với benchmark đây là **một luật cho
cả sweep**, không nằm trong config của từng thuật toán. Bỏ trống nghĩa là
tắt, đúng như mọi benchmark/simulation trước khi có tính năng này.
`enabled: true` kèm `max_replans: 0` bị từ chối với 422 (bật mà không làm
gì thì report sẽ nói sai).

`SimulationResource` echo lại `replanning`, và `POST /simulations/{id}/run`
chạy đúng luật đã lưu — chạy lại một simulation cũ tái hiện điều kiện lúc
nó được tạo, không phải mặc định của hôm nay. Simulation lưu trước Đợt B
(cột DB là `NULL`) đọc ra `{enabled: false, max_replans: 0}`: đó là điều
chúng thật sự đã chạy, không phải giá trị thay thế. Migration Alembic
`0004` thêm cột nullable này.

Luật này đi vào `fairness`: `replanning_enabled` và `max_replans` được
ghi lại, và nó **được hash vào `conditions_checksum` chỉ khi bật** — nhờ
vậy checksum của mọi benchmark cũ không đổi một bit nào. Đổi
`max_replans` giữa hai lần chạy là đổi điều kiện, checksum khác nhau,
hai report không so chung được.

`runs[].metrics.replan_count` là số lần stack xin đường mới (0 khi tắt;
`null` chỉ với metrics lưu trước đợt này). Trong episode có replan,
`global_planning_time` và `expanded_nodes` là **tổng cộng dồn** qua mọi
lần plan, còn `planned_path_length`/`path_efficiency` tính theo **đường
của lần replan cuối**. Mỗi lần replan để lại một `EpisodeEvent` kiểu
`replan`; kết luận `stuck`/`no_progress` bị thay bởi event đó vì episode
đã không kết thúc ở đấy.

Mỗi `aggregate` còn mang **bản chụp khai báo quan sát** lúc chạy:
`global_observation_class`, `local_observation_class`,
`requires_global_path`. Chụp lại thay vì tra registry lúc đọc, để sửa
registry sau này không dán nhãn khác lên số đã đo. Report lưu trước P02
không có ba trường này (`null` = không rõ, **không** mặc định là
`lidar_only`).

**Thống kê P04.** Mỗi `aggregate` có thêm, bên cạnh các trường `mean_*`
cũ (giữ nguyên, đánh dấu deprecated trong docstring):

| Trường | Ý nghĩa |
|---|---|
| `median_*_successful` | Trung vị trên episode thành công. Đây là số nên trích dẫn. |
| `iqr_*_successful` | `[q1, q3]` — nửa giữa các lần chạy rơi vào khoảng nào. |
| `ci95_*_successful` | Bootstrap percentile 1000 lần cho trung vị, seed cố định = 0 nên tái lập được. |
| `ci95_success_rate` | Khoảng Wilson cho tỉ lệ thành công (chính xác, không cần seed). |

Cả bốn đều nullable: stack không có episode thành công nào thì không có
phân phối để mô tả, 1 episode thành công thì có trung vị nhưng không có
khoảng tin cậy. `null` nghĩa là **không tính được**, không phải 0.

`report` thêm:

- `comparisons[]` — `PairwiseComparison`: `{algorithm_a, algorithm_b,
  metric, statistic, p_value, effect_size, significant,
  paired_seed_count, warning}`. Wilcoxon signed-rank **ghép cặp theo
  seed**; seed nào có stack không về đích thì không có `travel_time` nên
  bị loại, và số cặp còn lại đi kèm kết quả. Dưới 5 cặp thì không chạy
  kiểm định (`statistic`/`p_value`/`effect_size` = `null`) chứ không trả
  một p-value vô nghĩa. `effect_size` là Cliff's delta của A so với B.
- `seed_count`, `statistically_adequate` — computed field, suy ra từ
  `spec.seeds` nên report cũ cũng có. `statistically_adequate=false`
  (dưới 30 seed) **không chặn gì**; nó nói kết quả là chỉ dấu đáng điều
  tra, không phải kết luận.

`GET /leaderboard` nhóm theo `conditions_checksum` **và cả hai lớp quan
sát** (`global_observation_class` + `local_observation_class`). Query
`group_by_observation_class` (mặc định `true`) tắt việc tách nhóm; nhóm
bị trộn trả về kèm `cross_observation_class_warning=true`, và trường lớp
nào không thống nhất trong nhóm thì trả `null`.

Lấy cả hai lớp làm khóa chứ không chỉ lớp local, vì replanning nâng
**riêng lớp global**: một run được phép replan đọc vị trí ground-truth
của vật cản động mà run không replan không bao giờ thấy. Nhóm theo lớp
local sẽ xếp chung hai run đó.

`LeaderboardGroup` vì vậy có thêm trường `global_observation_class`
(`null` khi nhóm không thống nhất hoặc khi dữ liệu có trước P02).

### P05 — tập held-out và chênh lệch tổng quát hóa

`report` thêm ba trường:

- `scenario_split` — `"dev" | "holdout" | "unassigned"`. **Snapshot lúc
  chạy**, không phải tra lại lúc đọc: đổi phân loại của một scenario
  hôm nay không được biến số liệu hôm qua thành số liệu holdout.
- `protocol_version` — phiên bản giao thức lúc chạy. `null` trên report
  ghi trước P05, và những report đó đọc ra `scenario_split="unassigned"`
  — đúng, vì lúc đó chưa ai phân loại gì.
- `generalization_gap` — **luôn `null` hiện nay**: một benchmark chạy
  đúng một scenario nên toàn bộ report thuộc một split, không có gì để
  trừ. Chênh lệch được tính **giữa các report** ở `GET /generalization`.
  Trường này để sẵn cho benchmark nhiều scenario sau này.

Split **không** nằm trong `Scenario` và **không** vào
`conditions_checksum`. Nguồn sự thật là
`packages/benchmark/planbench_benchmark/scenario_protocol.json`, có
version, và chỉ đổi qua review + deploy — không có endpoint ghi.

| Method | Path | Mô tả |
|---|---|---|
| GET | /scenario-protocol | Phân loại dev/holdout của scenario; `?scenario_name=` tra một cái. Scenario không có trong file trả `unassigned`. |
| GET | /generalization | Chênh lệch dev − holdout theo từng stack + nhật ký dùng holdout. |

`GET /scenario-library` mỗi entry thêm `split`, `protocol_version`,
`split_notes`.

`GET /generalization` trả `GeneralizationSummary`:

- `entries[]` — mỗi stack: `dev`, `holdout` (`SplitSummary`: scenario
  đóng góp, số report, số episode, metric trung bình, cờ đủ seed),
  `gap` (`dev − holdout` theo metric) và `warnings[]`.
- `metrics[]` — `{name, higher_is_better}`. Dấu của `gap` **không tự
  đọc được**: `+` nghĩa là dev cao hơn, còn như thế là tốt hay xấu do
  `higher_is_better` quyết định.
- `gap = null` khi thiếu một phía. `null` là **không tính được**, không
  phải "không có chênh lệch".
- Scenario `unassigned` bị **loại và đếm** (`unassigned_report_count`),
  không gộp vào dev.
- `holdout_usage[]` — mọi benchmark từng chạy scenario holdout
  (`benchmark_id`, tên, scenario, số seed, thời điểm kết thúc). Tập
  held-out mất giá trị vì bị xem nhiều lần; đây là con số để đối chiếu.
- Scenario có trọng số **bằng nhau**: trung bình trong từng scenario
  trước, rồi mới trung bình qua các scenario — chạy một scenario 10 lần
  không làm nó lấn át các scenario còn lại.
- `accepted_only` mặc định `true`, giống leaderboard.

### P03 — độ khó đo được

```text
difficulty(scenario) = 1 - success_rate(baseline đã ghim, seed cố định)
```

Độ khó **không** nằm trong `Scenario` và **không** vào
`conditions_checksum` — nó là kết quả đo, không phải đặc tính của
scenario. Nguồn sự thật là
`packages/benchmark/planbench_benchmark/difficulty_calibration.json`, do
`scripts/calibrate_difficulty.py` sinh ra và **không có endpoint ghi**.

| Method | Path | Mô tả |
|---|---|---|
| GET | /difficulty-calibration | Thang độ khó đang cài + baseline + báo cáo dải difficulty. |

`GET /scenario-library` mỗi entry thêm `difficulty`:
`DifficultyLabel | null`. `null` nghĩa là **chưa đo** — không được thay
bằng `curriculum_index`, vì đó là dự định của người viết, còn cái này là
số đo, và việc hai thứ lệch nhau chính là điều cần thấy.

`DifficultyLabel`:

- `value` — độ khó trong `[0, 1]`; `ci95` — khoảng Wilson của chính độ
  khó (lấy gương từ khoảng của success rate).
- `band` — `easy ≤ 0.2 < moderate ≤ 0.6 < hard ≤ 0.999 < unsolved`.
  `unsolved` tách riêng khỏi `hard`: baseline chưa từng giải được, nên
  không xếp thứ tự với nhau được.
- `calibration_version`, `baseline_algorithm`, `seed_count`.
- `adequate = false` khi đo trên ít hơn 30 seed (số liệu tạm).
- `stale = true` khi scenario đã đổi so với lúc đo. Vẫn trả số, có cờ —
  ẩn đi sẽ thành ô trống, mà ô trống nghĩa là "chưa đo", một vấn đề
  khác hẳn.

`GET /difficulty-calibration` trả `DifficultyCalibrationSummary`:

- `baseline` — thuật toán, config, `replanning_enabled`, danh sách seed,
  robot profile, `benchmark_spec_version`, `protocol_version`,
  `git_sha`. Ghi tên `astar+dwa` không là baseline: cùng stack trên robot
  khác, seed khác hay commit khác là một thang đo khác.
- `scenarios[]` — `DifficultyLabel` theo thứ tự curriculum.
- `coverage` — `min/max/spread`, `band_counts`, `midrange_count`,
  `uncalibrated[]` và `warnings[]` (dải quá hẹp, **rỗng ở khoảng giữa**,
  toàn dễ, toàn khó, có scenario chưa từng giải được, ít seed).
  `midrange_count` là số scenario nằm trong `(0.2, 0.8)` — tách riêng
  khỏi `spread` vì một bộ scenario dồn hết về 0.0 và 1.0 đạt `spread`
  tối đa mà vẫn không phân biệt được stack nào với stack nào.
- Chưa hiệu chuẩn thì trả `200` với thang rỗng + cảnh báo, **không phải
  lỗi**: "chưa đo" là một trạng thái bình thường.

### Scenario Editor (2.3)

`ScenarioResource` thêm `split` — **chỉ đọc**, resolve từ
`scenario_protocol.json`. Không có trường request nào đặt được nó: gửi
kèm `"split": "dev"` trong body scenario cũng bị bỏ qua và kết quả vẫn
là `unassigned`. Chuyển nhóm là thay đổi giao thức, phải review.

`POST /scenarios/preview`:

- request `{map_id, scenario, time ≥ 0, seed}`;
- response `{time, seed, valid, errors[], dynamic_obstacles[]}`, mỗi
  phần tử `{name, radius, position}`.
- Vị trí do backend tính bằng `position_at` — **đúng hàm simulator
  dùng**. Frontend không tự cài lại quy luật chuyển động: bản thứ hai sẽ
  trôi khỏi bản thứ nhất, và một preview mâu thuẫn với episode còn tệ
  hơn không có preview.
- Trả cả vị trí lẫn `errors[]`: người đang sửa một bố cục sai vẫn cần
  nhìn thấy bố cục đó.
- `time < 0` → `422`. Thời gian âm không có nghĩa trong một episode.

`POST /scenarios/validate` là **đúng phép kiểm mà `create`/`update`
chạy** (cùng `SimulationEngine.load_scenario`). Nhờ vậy không có chuyện
editor báo hợp lệ rồi lúc lưu bị từ chối vì một luật chưa ai nói.

### F09 — biểu đồ và xuất báo cáo (3.1)

`GET /benchmarks/{id}/report.md` trả **toàn bộ** report dạng Markdown:

- `Content-Type: text/markdown; charset=utf-8`;
- `Content-Disposition: attachment; filename="benchmark-<slug>-<id>.md"`
  — tên do server đặt (tên benchmark là dữ liệu người dùng nên được rút
  gọn thành slug an toàn, và `id` luôn được nối vào vì hai benchmark
  trùng tên là chuyện bình thường);
- **409** khi benchmark chưa chạy. Xuất một report chưa có là xuất một
  tài liệu toàn ô trống, mà ô trống đọc như kết quả.

Nội dung theo thứ tự: nguồn gốc (id, thời điểm, `git_sha`, checksum
điều kiện/map/scenario, seed, `protocol_version`, split, độ khó +
`calibration_version`) → điều kiện chạy → stack và lớp quan sát → tỉ lệ
kết cục → phân phối (trung vị, IQR, CI95) → kiểm định ghép cặp →
chênh lệch tổng quát hóa → bảng từng run → **giới hạn đã biết**.

Hai điều tài liệu này không làm: không suy ra giá trị thiếu (`—` nghĩa
là không tính được, không phải 0), và không phát biểu mạnh hơn dữ liệu —
mỗi cảnh báo nằm cạnh chính con số nó áp vào, không chỉ ở mục cuối.

Chênh lệch tổng quát hóa in trong report được tính **giữa các benchmark
đã accepted** (giống `GET /generalization`), có ghi rõ như vậy: một
benchmark chạy một scenario nên tự nó không có gì để trừ.

Endpoint yêu cầu đăng nhập như mọi endpoint đọc khác, nên trình duyệt
**không** tải bằng `<a href>` — token nằm ở header, và đưa nó vào URL sẽ
để lại dấu vết trong history và log của mọi proxy trên đường đi. Client
`fetch` rồi tự dựng Blob (`apps/web/src/lib/reports.ts`).

## Episodes (M4)

| Method | Path | Mô tả |
|---|---|---|
| GET | /episodes/{id} | Metadata + RunRecord + artifact reference |
| GET | /episodes/{id}/result | EpisodeResult (trajectory + events) |
| GET | /episodes/{id}/plan | PlanResult của global planner (A* hoặc RRT*) |
| GET | /episodes/{id}/replay | `{plan_path, trajectory, events, metrics}` cho UI replay |

## Algorithms (M4)

`GET /algorithms` trả registry stack. `benchmarkable=false` đánh dấu stack
tham chiếu (hiện tại: `astar+pure_pursuit`, `rrtstar+pure_pursuit`) — chỉ
để kiểm chứng pipeline, không dùng kết luận. `config_schema` là JSON Schema
của config **local planner** của stack đó.

Hai trường mô tả nửa global của stack:

| Trường | Ý nghĩa |
|---|---|
| `global_planner` | Id global planner (`astar`, `rrtstar`). Registry khai báo tường minh, không suy ra từ chuỗi `id`. |
| `stochastic_global_planner` | `true` khi global planner lấy mẫu ngẫu nhiên. Kết quả chỉ đọc được qua nhiều seed; UI hiện cảnh báo. |

Ba trường khai báo **cân bằng thông tin** (P02) — stack nhìn thấy dữ liệu gì:

| Trường | Ý nghĩa |
|---|---|
| `global_observation_class` | Dữ liệu global planner được xem. Mọi stack **khai báo** `full_static_map`. |
| `local_observation_class` | Dữ liệu bộ điều khiển được xem. Hiện mọi stack là `lidar_only`. |
| `requires_global_path` | `true` khi bộ điều khiển bám đường toàn cục. |

Giá trị hợp lệ: `full_static_map`, `lidar_only`, `human_states`,
`lidar+human_states`, `full_static_map+human_states`. **Không có
default** — đăng ký stack mới mà không khai báo thì `AlgorithmInfo` fail
validation ngay lúc import. Nhãn sai nguy hiểm hơn nhãn thiếu: nó làm
một so sánh không công bằng trông như đã được kiểm.

**Lớp global của một *run* được suy ra lúc chạy, không phải chép nguyên
từ registry.** Registry khai báo theo stack id, nhưng cùng một stack
nhìn thấy nhiều hơn khi được phép replan: `_replan()` lấy vị trí vật cản
động qua `engine.dynamic_obstacles_now()` — ground truth, không cảm biến
nào cho. Nên `AlgorithmAggregate.global_observation_class` chụp lại giá
trị **đã nâng**:

| Điều kiện chạy | `global_observation_class` trong report |
|---|---|
| `replanning.enabled = false` (mặc định) | `full_static_map` — y hệt registry, mọi report cũ giữ nguyên nhãn |
| `replanning.enabled = true` | `full_static_map+human_states` |

`full_static_map+human_states` **không stack nào khai báo** trong
registry; nó chỉ xuất hiện ở tầng kết quả. Report Markdown in kèm một
đoạn giải thích vì sao nhãn khác registry, để người đọc đối chiếu không
tưởng đó là bug. Lớp local **không đổi** — bộ điều khiển vẫn chỉ có
LiDAR.

Seed của một stack ngẫu nhiên **được dẫn xuất từ seed episode** (cùng seed
điều khiển vật cản động), nên mỗi episode mọc một cây khác nhau còn chạy
lại cùng seed thì tái lập đúng đường cũ. Config của global planner chưa
nằm trong `BenchmarkSpec` — MVP chạy mặc định; đây là chỗ P01 (Optuna) sẽ
cắm vào.

## Agent (M8)

| Method | Path | Role | Response |
|---|---|---|---|
| GET | `/agent/capabilities` | operator, reviewer | `{provider, model, deterministic, tools[], forbidden[], providers[]}` |
| POST | `/agent/chat` | operator, reviewer | `{provider, model, deterministic, turn:{text, tools_used[], tool_errors[], iterations, truncated}}` |

Tầng cố vấn (đầy đủ trong `docs/AI_CAPABILITIES.md`; tất cả chỉ đọc,
không route nào tạo/sửa gì):

| Method | Path | Trả về |
|---|---|---|
| POST | `/decisions/preflight` | Lời khuyên về một phép so **chưa chạy**; body đúng bằng body của `POST /decisions` |
| GET | `/decisions/{run_id}/advice?use_model=` | Việc cần làm cho từng cổng chưa qua, kèm việc bị cấm; `use_model` thêm tầng LLM xếp hạng/bổ sung |
| GET | `/decisions/{run_id}/report-advice` | Câu nào bằng chứng không cho phép viết vào báo cáo |
| GET | `/decisions/{run_id}/traces/{cid}/{eid}/review` | Vì sao episode này kết thúc như vậy, từ chính trace của nó |
| POST | `/candidates/{candidate_id}/reproduction` | Khác biệt giữa phương án đã đăng ký và cấu hình paper nêu |
| POST | `/plugins/from-paper[/upload]` | Bundle plugin Algorithm Host nháp từ paper; `accepted` là phán quyết của bộ kiểm định tất định |
| POST | `/agent/missions` | operator | `{session, draft?, refusal?, benchmark?, next_step}` |
| POST | `/agent/benchmarks/{id}/run` | operator | `BenchmarkSummary`; **409** nếu chưa được approve |
| GET | `/agent/benchmarks/{id}/evidence` | operator, reviewer | `EvidenceBundle` |
| POST | `/agent/benchmarks/{id}/report` | operator, reviewer | `GeneratedReport` |

Ghi chú:

- Mission không parse được trả **201** kèm `refusal`, không phải lỗi:
  "không biến được câu đó thành benchmark" là một kết quả hợp lệ.
- `deterministic: true` nghĩa là câu trả lời do mock khớp từ khóa sinh
  ra, **không phải** do model viết. Luôn hiển thị cờ này cho người đọc.
- Agent chạy dưới danh nghĩa user gọi API. Benchmark nó tạo được quy về
  người đó, và người đó **không** được tự approve.
- `GeneratedReport.citations` chỉ chứa id có trong evidence bundle. Nếu
  model bịa một id, cả báo cáo bị hủy (**422**).
- Không có endpoint nào cho phép agent approve, accept kết quả, sửa map/
  scenario, hay điều khiển robot.

## Robot profiles (M13)

Tham số robot là **dữ liệu**, không phải hằng số nằm trong adapter PPO.
Một model được huấn luyện cho robot bán kính 0.3 m không nói gì về robot
bán kính 0.8 m, và trước M13 sự khác biệt đó không ở đâu ghi lại.

| Method | Path | Ghi chú |
|---|---|---|
| `GET` | `/api/v1/robot-profiles` | Profile của người gọi, kèm profile mặc định. |
| `POST` | `/api/v1/robot-profiles` | Tạo. |
| `GET` | `/api/v1/robot-profiles/{id}` | |
| `PATCH` | `/api/v1/robot-profiles/{id}` | Chỉ chủ sở hữu. |
| `DELETE` | `/api/v1/robot-profiles/{id}` | Chỉ chủ sở hữu; từ chối nếu đang có model tham chiếu. |
| `POST` | `/api/v1/robot-profiles/{id}/clone` | Sao chép để sửa mà không đụng bản gốc. |

Trường: `radius`, `max_linear_velocity`, `max_angular_velocity`,
`max_linear_acceleration`, `max_angular_acceleration`, `lidar_beams`,
`lidar_range`, `lidar_fov`.

## Model registry (M13)

| Method | Path | Ghi chú |
|---|---|---|
| `GET` | `/api/v1/models` | `?usable=true` chỉ trả model chạy được. |
| `POST` | `/api/v1/models/upload` | `multipart/form-data`. Xem dưới. |
| `GET` | `/api/v1/models/{id}` | |
| `PATCH` | `/api/v1/models/{id}` | Tên, mô tả, `status`. Chỉ chủ sở hữu. |
| `DELETE` | `/api/v1/models/{id}` | Chỉ chủ sở hữu hoặc admin; từ chối nếu đã có benchmark dùng. |
| `POST` | `/api/v1/models/{id}/validate` | Kiểm tra lại cấu trúc + checksum. |
| `GET` | `/api/v1/models/{id}/compatibility` | `?robot_profile_id=` để hỏi với profile khác. |
| `POST` | `/api/v1/models/{id}/documents` | Đính kèm `.json` hoặc `.pdf`. |

**Upload** nhận các phần: `model` (`.zip` bắt buộc), `metadata`
(`.json`, tùy chọn), `document` (`.pdf`, tùy chọn), cùng `name`,
`version`, `description`, `robot_profile_id`.

Giới hạn: `PLANBENCH_MAX_MODEL_UPLOAD_MB` (mặc định 200) và
`PLANBENCH_MAX_DOCUMENT_UPLOAD_MB` (mặc định 20), cưỡng chế **trong lúc
ghi**. Vượt giới hạn → `413`, file dở dang bị xóa.

Mã lỗi: `400` sai định dạng, `403` không phải chủ sở hữu, `404` không
tồn tại, `413` quá lớn, `422` registry từ chối (kèm câu giải thích).

**Response không bao giờ chứa `model_file_path`, `storage_key`, hay
`uploaded_by_user_id`.** Đường dẫn nội bộ là chi tiết triển khai; ID
nghiệp vụ là `id`, không phải tên file. Test khẳng định điều này.

Trường trả về gồm `id`, `name`, `version`, `algorithm_type`,
`framework`, `framework_version`, `original_filename`, `file_size`,
`checksum`, `robot_profile_id`, `observation_schema`, `action_schema`,
`training_environment`, `training_steps`, `status`, `validation_status`,
`validation_message`, `created_at`, `updated_at`.

`validation_status`: `pending` → `structural` (bảng mục lục zip hợp lệ,
**không giải tuần tự**) → `loaded` (một tiến trình khác đã nạp thật) |
`failed`. Khoảng cách giữa `structural` và `loaded` là ranh giới bảo
mật, không phải chi tiết thủ tục — xem KNOWN_LIMITATIONS #77.

### Chạy benchmark PPO

`BenchmarkSpec.algorithm_configs["astar+ppo"]` nay nhận `model_id`.
Server tự phân giải sang file, kiểm tra lại tương thích **tại thời điểm
chạy**, và ghi lại `model_version`, `model_checksum`,
`compatibility_snapshot` vào spec — nên một kết quả luôn truy được về
đúng byte đã sinh ra nó.

`model_path` vẫn được chấp nhận để benchmark cũ đọc được, nhưng không
xuất hiện trong giao diện.

Thiếu cả hai → `422` với câu:
*"Bạn chưa chọn PPO model..."* — không phải lỗi Pydantic thô.

## Trợ lý (M13 — thay thế contract M8 cho phần giao diện)

| Method | Path | Ghi chú |
|---|---|---|
| `POST` | `/api/v1/ai/conversations` | Mở hội thoại. |
| `GET` | `/api/v1/ai/conversations` | Hội thoại của người gọi. |
| `GET` | `/api/v1/ai/conversations/{id}` | Toàn bộ lịch sử. |
| `DELETE` | `/api/v1/ai/conversations/{id}` | |
| `POST` | `/api/v1/ai/conversations/{id}/messages` | Gửi tin nhắn; **không tạo gì cả**. |
| `POST` | `/api/v1/ai/conversations/{id}/confirm-draft` | Ghi duy nhất: tạo **bản nháp**. |
| `GET` | `/api/v1/ai/results/{benchmark_id}` | Thẻ kết quả, số lấy từ report thật. |
| `GET` | `/api/v1/ai/latest-result` | |

**Không tồn tại** đường dẫn `/ai/**` nào để chạy, duyệt, chấp nhận, từ
chối benchmark hay điều khiển robot. Đây là bất biến được test kiểm
chứng bằng cách đọc `openapi.json` — tức kiểm tra bề mặt mà client thực
sự gọi được, chứ không phải bảng định tuyến nội bộ.

Nội dung tin nhắn của trợ lý là **khóa dịch** (`chat.proposalReady`,
`chat.needModel`, …), không phải câu tiếng Anh hay tiếng Việt cứng —
nên hai ngôn ngữ không bao giờ lệch nhau.

## Tuning siêu tham số

| Method | Path | Ghi chú |
|---|---|---|
| `GET` | `/api/v1/tuning` | Kết quả tune đã cache, theo từng planner |

Đọc từ `tuning_cache.json` tĩnh — **không** chạy lại Optuna lúc request.
Tune một lượt là 300 episode; đó là việc của `scripts/tune_hyperparameters.py`,
không phải của một HTTP request. Vì vậy API không cần cài optuna.

## Xuất report Markdown

| Method | Path | Ghi chú |
|---|---|---|
| `GET` | `/api/v1/benchmarks/{id}/report.md` | Tải report dạng Markdown |

Đường dẫn riêng chứ không phải cờ query trên endpoint JSON: cái này trả
về một **file tải xuống**, không phải một resource. Gộp hai thứ làm hợp
đồng JSON phải chiều theo một mối quan tâm về định dạng.

Chưa chạy benchmark thì trả `409` kèm câu giải thích.

## Ghi chú trạng thái

- Lưu trữ metadata vẫn in-memory (mất khi restart) — PostgreSQL còn nợ.
- Artifact (trajectory, report) lưu ra đĩa với SHA-256 + size (D15).
- Benchmark chạy đồng bộ trong request; background worker ở M5.

## Chạy server

```bash
PYTHONPATH="packages/schemas:packages/planning:packages/metrics:services/simulator:apps/api" \
  .venv/bin/uvicorn planbench_api.main:app --port 8000
```

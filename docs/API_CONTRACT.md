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
| GET | /algorithms | Registry; `astar_pure_pursuit` là reference stack, `benchmarkable=false` |
| GET/POST | /simulations | Danh sách / tạo `{map_id, scenario_id, algorithm}` |
| GET | /simulations/{id} | Trạng thái session (`created`/`finished`) |
| POST | /simulations/{id}/run | Chạy headless đồng bộ → plan + result + metrics (409 nếu chạy lại) |
| GET | /simulations/{id}/result | Kết quả đầy đủ (null nếu chưa chạy) |
| GET/POST | /benchmarks | Danh sách / tạo `{name, map_id, scenario_id, algorithms, runs_per_algorithm, seeds?}` |
| GET | /benchmarks/{id} | Metadata benchmark |
| POST | /benchmarks/{id}/run | Chạy tuần tự mọi (algorithm × seed) → runs + aggregates |
| GET | /benchmarks/{id}/results | Kết quả đã lưu |

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

`GET /leaderboard` nhóm theo `conditions_checksum` **và**
`local_observation_class`. Query `group_by_observation_class` (mặc định
`true`) tắt việc tách nhóm; nhóm bị trộn trả về kèm
`cross_observation_class_warning=true`.

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
| `global_observation_class` | Dữ liệu global planner được xem. Hiện mọi stack là `full_static_map`. |
| `local_observation_class` | Dữ liệu bộ điều khiển được xem. Hiện mọi stack là `lidar_only`. |
| `requires_global_path` | `true` khi bộ điều khiển bám đường toàn cục. |

Giá trị hợp lệ: `full_static_map`, `lidar_only`, `human_states`,
`lidar+human_states`. **Không có default** — đăng ký stack mới mà không
khai báo thì `AlgorithmInfo` fail validation ngay lúc import. Nhãn sai
nguy hiểm hơn nhãn thiếu: nó làm một so sánh không công bằng trông như
đã được kiểm.

Seed của một stack ngẫu nhiên **được dẫn xuất từ seed episode** (cùng seed
điều khiển vật cản động), nên mỗi episode mọc một cây khác nhau còn chạy
lại cùng seed thì tái lập đúng đường cũ. Config của global planner chưa
nằm trong `BenchmarkSpec` — MVP chạy mặc định; đây là chỗ P01 (Optuna) sẽ
cắm vào.

## Agent (M8)

| Method | Path | Role | Response |
|---|---|---|---|
| GET | `/agent/capabilities` | operator, reviewer | `{provider, model, deterministic, tools[], forbidden[], knowledge_documents}` |
| POST | `/agent/chat` | operator, reviewer | `{provider, model, deterministic, turn:{text, tools_used[], tool_errors[], iterations, truncated}}` |
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

## Ghi chú trạng thái

- Lưu trữ metadata vẫn in-memory (mất khi restart) — PostgreSQL còn nợ.
- Artifact (trajectory, report) lưu ra đĩa với SHA-256 + size (D15).
- Benchmark chạy đồng bộ trong request; background worker ở M5.

## Chạy server

```bash
PYTHONPATH="packages/schemas:packages/planning:packages/metrics:services/simulator:apps/api" \
  .venv/bin/uvicorn planbench_api.main:app --port 8000
```

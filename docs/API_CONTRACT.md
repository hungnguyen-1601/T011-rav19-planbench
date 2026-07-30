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

## Authentication (M4)

- `POST /auth/login` — form `username`/`password` → `{access_token,
  token_type, expires_in, role, username}`. Bearer token cho mọi endpoint
  benchmark/episode.
- `GET /auth/me` — thông tin caller.
- Role: `operator` (tạo, submit, run, cancel), `reviewer` (approve/reject
  spec, accept/reject kết quả), `admin` (cả hai, miễn trừ separation of
  duties). Người tạo **không** được tự duyệt.

## Benchmarks (M4 — thay thế contract M2)

| Method | Path | Role | Mô tả |
|---|---|---|---|
| GET/POST | /benchmarks | any / operator | Danh sách / tạo `{name, map_id, scenario_id, algorithms:[{id,config}], seeds:[...]}` → state `draft` |
| GET | /benchmarks/{id} | any | Metadata + audit trail |
| POST | /benchmarks/{id}/submit | operator | draft/rejected → pending_approval |
| POST | /benchmarks/{id}/approve | reviewer | pending_approval → approved (**gate 1**) |
| POST | /benchmarks/{id}/reject | reviewer | pending_approval → draft |
| POST | /benchmarks/{id}/cancel | operator | → cancelled |
| POST | /benchmarks/{id}/run | operator | approved → running → pending_review; trả `{benchmark, report}` |
| POST | /benchmarks/{id}/accept-result | reviewer | pending_review → accepted (**gate 2**) |
| POST | /benchmarks/{id}/reject-result | reviewer | pending_review → rejected |
| GET | /benchmarks/{id}/results | any | Report đã lưu (null nếu chưa chạy) |
| GET | /benchmarks/{id}/episodes | any | Danh sách episode + artifact URI/checksum/size |

Body của các action nhận `{comment}` — được ghi vào audit trail.

Chạy khi chưa `approved` trả **409 invalid_state**; sai role trả **403**.

`report` gồm: `spec`, `fairness` (bằng chứng công bằng, có
`conditions_checksum`), `runs[]` (mỗi (algorithm, seed)), `aggregates[]`
(success/collision/timeout/stuck/no_progress rate; mean travel time,
path efficiency, smoothness — **chỉ tính trên episode thành công**;
clearance và latency tính trên mọi episode).

## Episodes (M4)

| Method | Path | Mô tả |
|---|---|---|
| GET | /episodes/{id} | Metadata + RunRecord + artifact reference |
| GET | /episodes/{id}/result | EpisodeResult (trajectory + events) |
| GET | /episodes/{id}/plan | PlanResult của A* |
| GET | /episodes/{id}/replay | `{plan_path, trajectory, events, metrics}` cho UI replay |

## Algorithms (M4)

`GET /algorithms` trả registry stack. `benchmarkable=false` đánh dấu stack
tham chiếu (hiện tại: `astar+pure_pursuit`) — chỉ để kiểm chứng pipeline,
không dùng kết luận. `config_schema` là JSON Schema của config stack đó.

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

## Ghi chú trạng thái

- Lưu trữ metadata vẫn in-memory (mất khi restart) — PostgreSQL còn nợ.
- Artifact (trajectory, report) lưu ra đĩa với SHA-256 + size (D15).
- Benchmark chạy đồng bộ trong request; background worker ở M5.

## Chạy server

```bash
PYTHONPATH="packages/schemas:packages/planning:packages/metrics:services/simulator:apps/api" \
  .venv/bin/uvicorn planbench_api.main:app --port 8000
```

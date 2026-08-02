# Test Report — Agentic AI PlanBench

Output thật từ các lần chạy kiểm thử. Cập nhật sau mỗi milestone.

## Phase 3a — Docker Compose chạy thật lần đầu trên PostgreSQL — 2026-08-02

Môi trường: Windows 11 + Docker Desktop v29.5.3 (Compose v5.1.4), Linux
containers. Trước đợt này `docker compose up` chưa từng chạy thành công
(KNOWN_LIMITATIONS #51 cũ) và mọi test SQL chỉ chạy trên SQLite (#52 cũ).

```
docker compose up --build -d
  → build planbench-api, planbench-web: OK, không lỗi (PyYAML mới thêm
    cho F01 map loader build đúng)
docker compose ps
  db       postgres:17-alpine   healthy
  api      planbench-api        healthy
  web      planbench-web        healthy
  migrate  planbench-migrate    Exited (0)   # alembic upgrade head
```

Verify end-to-end thật qua container (không phải TestClient):

- `GET /api/v1/health` → 200.
- `POST /auth/login` (dev password login, hai account seed
  `engineer`/`approver`) → JWT có claim `role` đúng.
- `POST /maps` (map 12×12 viền occupied) → 201.
- `POST /maps/import-ros` với PGM (P5, tự build tay trong request) + YAML
  → 201, occupancy convert đúng (viền OCCUPIED, tâm FREE) — lần đầu tiên
  endpoint F01 được gọi qua HTTP thật, không phải `TestClient`.
- `POST /scenarios`, `POST /benchmarks` (2 thuật toán `astar+dwa` +
  `astar+pure_pursuit`, 3 seed).
- `POST /benchmarks/{id}/review-requests` (stage `spec`, gửi Approver) →
  `POST /reviews/{id}/approve` (Approver) → benchmark chuyển `approved`.
- `POST /benchmarks/{id}/run` (Engineer) → chạy thành công, state
  `pending_review`. Report trả đủ field Phase 3a:
  `smoothness`/`smoothness_per_metre`, `local_planning_latency_p50/p95/p99`,
  `stop_and_go_count`, `comparisons` (Wilcoxon `p_value=1.0` vì 2 thuật
  toán đều success_rate=1.0 trên map/scenario nhỏ dùng để test),
  `statistically_adequate: false` (seed_count=3 < 30, đúng thiết kế P04).
- `docker compose logs api` — không traceback.
- Restart riêng container `api` (`--force-recreate`, đổi `.env`) trong lúc
  `db` vẫn chạy → benchmark/map/scenario tạo trước đó vẫn còn nguyên khi
  gọi lại `GET /benchmarks/{id}` — xác nhận dữ liệu nằm ở Postgres volume,
  không phải in-memory theo tiến trình API.
- `docker compose down` (không xóa volume).

### Phát hiện thật trong lúc verify

`PLANBENCH_ADMIN_NICKNAMES` chỉ có tác dụng qua luồng OAuth
(`AccountService.identify_or_create()` gọi `apply_admin_policy()`);
account seed qua `PLANBENCH_SEED_USERS`/dev-login login bằng
`POST /auth/login` **không** đi qua `apply_admin_policy()`, nên nickname
có trong danh sách admin vẫn không được gắn `is_admin=true` nếu tài khoản
đó chỉ từng đăng nhập bằng password. Không sửa trong Phase 3a (ngoài
scope F01/F05/F12) — ghi vào `docs/KNOWN_LIMITATIONS.md` mục "Docker
Compose (Phase 3a)".

## requirements.txt — kiểm chứng "clone về là chạy được" — 2026-08-01

Câu hỏi cần trả lời: `requirements.txt` có **đủ** không? Không thể gỡ
package khỏi venv của người dùng để thử, và cài venv sạch thì cần mạng
+ phê duyệt. Cách kiểm chứng thay thế: chặn đúng 7 package tùy chọn
(`mlflow`, `gymnasium`, `stable_baselines3`, `torch`, `openai`,
`anthropic`, `psycopg`) bằng một `sitecustomize.py` mô phỏng chính xác
một checkout sạch, rồi chạy toàn bộ suite.

```
PYTHONPATH=<blocker> .venv/bin/pytest tests/ -q
1008 passed, 1 skipped, 1 warning in 261.05s (0:04:21)
```

1 skipped là `tests/test_rl.py` — đúng như thiết kế: nó cần nhóm PPO
trong `requirements-optional.txt`.

API khởi động sạch với chỉ core deps:

```
health       {'status': 'ok', 'app': 'PlanBench API', 'version': '0.1.0'}
providers    {'google': False, 'github': False, 'dev_login': False}
algorithms   3 stacks
library      10 scenarios
agent        401 (cần đăng nhập — đúng)

log: "agent provider: deterministic mock (no provider key found);
      answers are keyword-matched, not model-generated."
```

15/15 phiên bản ghim trong `requirements.txt` khớp đúng với những gì đã
cài và đã chạy test.

### Ba lỗi mà kiểm chứng này bắt được

1. **`pytest tests/` không chạy nổi trên checkout sạch.**
   `tests/test_rl.py` import `gymnasium` ở module level, không có guard,
   nên collection **dừng cả suite** — 1008 test còn lại không chạy được
   chỉ vì thiếu một package tùy chọn. Sửa bằng `pytest.importorskip`.
   Đây chính là thứ người mới clone về sẽ gặp đầu tiên.

2. **Harness kiểm chứng nói dối lần một.** Nó raise `ImportError`, trong
   khi package thiếu thật raise `ModuleNotFoundError` — và pytest 9 chỉ
   `importorskip` trên loại sau. Lỗi ở công cụ đo, không phải ở code.

3. **Harness nói dối lần hai.** `importlib.util.find_spec("anthropic")`
   với package thiếu thật trả `None` **không raise**, còn harness thì
   raise — làm `provider_status()` nổ thay vì báo "chưa cài". Phải mô
   phỏng đúng **cả hai** hành vi thì kết luận mới có giá trị.

### Không được kiểm chứng

- **Chưa thật sự chạy `pip install -r requirements.txt` vào venv trống.**
  Cần mạng và phê duyệt cài đặt. Cái đã chứng minh được là: mọi phiên
  bản ghim khớp với những gì đang chạy, và code chạy đúng khi 7 package
  tùy chọn vắng mặt. Cái **chưa** chứng minh được: pip giải được đúng bộ
  dependency gián tiếp từ một máy sạch.
- **Chưa kiểm `npm install` từ đầu** trên `node_modules` trống.

## M12 — App shell, theme, i18n, Dashboard — 2026-08-01

Chỉ sửa frontend. Backend không đổi một dòng nào (`git status` sạch ở
`apps/api`, `packages`, `services`, `alembic`, `tests`, `scripts`).

### Frontend

```
apps/web$ npx tsc --noEmit        # sạch
apps/web$ npx vitest run
  Test Files  15 passed (15)
       Tests  229 passed (229)     (trước: 78)
apps/web$ npx next build
  ✓ Compiled successfully
  16 route, thêm /system
```

Chống flaky: chạy `npx vitest run` **20 lần liên tiếp, 0 lần hỏng**.

### Backend — kiểm tra không regression

```
PYTHONPATH= .venv/bin/pytest tests/ -q
1038 passed, 1 warning in 260.13s (0:04:20)
```

Đúng con số của M11: không có gì bị hỏng.

### Smoke test trên server thật

Build standalone, chạy ở port riêng (không đụng server 3000/8000 đang
chạy của người dùng), rồi kiểm bằng `curl`:

```
mọi route trả 200:
  /  /maps  /library  /simulate  /benchmarks  /leaderboard
  /algorithms  /agent  /reviews  /system  /login  /welcome  /auth/callback

script chặn render có trong HTML:      planbench.theme  ✓
lang mặc định:                          <html lang="en" ✓
Cookie planbench.locale=vi  ->          <html lang="vi" ✓
                                        "Tổng quan", "Bảng xếp hạng" ✓
                                        (server-render, KHÔNG nháy tiếng Anh trước)
mặc định EN không lẫn tiếng Việt:       0 kết quả ✓
localhost:8000 trên Dashboard:          0 kết quả ✓  (card BACKEND đã bỏ)

/benchmarks:  id="app-sidebar" ✓  class="topbar" ✓  aria-current="page" ✓
              aria-label="Open navigation" ✓  "Theme" ✓  "Language" ✓
/login:       id="app-sidebar" -> 0  ✓ (render không shell, đúng thiết kế)
Dashboard:    18 stat-card · 10 quick-action · 3 empty-state · 6 skeleton ✓
```

### Ba lỗi thật mà kiểm chứng bắt được

1. **`tsc` và `next build` đều pass, server thật trả 500.**
   `lib/i18n/index.ts` là module `"use client"`, mà `layout.tsx` là
   server component gọi `localeFromCookie()` từ đó. Next chỉ báo lúc
   chạy: *"Attempted to call localeFromCookie() from the server but
   localeFromCookie is on the client."* Sửa bằng cách tách
   `lib/i18n/shared.ts` và `lib/theme-script.ts` (không `"use client"`)
   ra khỏi phần client. **Không có smoke test này thì lỗi đã lọt.**

2. **Script chặn render không chạy được ngoài scope window.** Nó dùng
   `localStorage` trần; trong trình duyệt thì đó là `window.localStorage`,
   nhưng test chạy script thật trong scope thường nên `try/catch` nuốt
   `ReferenceError` và attribute không được set. Đổi thành
   `window.localStorage`. Test viết ra để chứng minh "không nháy theme"
   lại là thứ tìm ra chính lỗi đó.

3. **Test flaky 1/3 lần.** `topbar.test.tsx` stub một `window` giả toàn
   cục, làm `react-dom/server` đi nhánh code trình duyệt và treo. Bỏ
   stub — các component đó không đụng `window` khi SSR. Riêng
   `auth.test.ts` (có sẵn từ trước) thỉnh thoảng timeout vì nó
   `resetModules()` + re-import ở **mỗi** case, và giờ có 15 file chạy
   song song; nâng `testTimeout` lên 20s kèm giải thích. Cả hai đã kiểm
   lại: 20/20 lần sạch.

### Không được kiểm chứng

- **Chưa mở trình duyệt thật** ở 320/375/768/1024/1440 px. Responsive
  viết bằng breakpoint CSS và kiểm qua HTML server-render; môi trường
  này không có công cụ chụp màn hình.
- **Không có test tương tác** (bấm nút, mở drawer, chọn theme trong
  menu): `@testing-library/react` chưa được cài. Component kiểm bằng
  `renderToStaticMarkup` (lần render đầu), hành vi kiểm ở tầng store.
- **Chưa kiểm đối chiếu màu** ở theme sáng bằng công cụ đo contrast.

## M11 — Tài khoản, OAuth, review tùy chọn — 2026-08-01

### Toàn bộ suite

```
PYTHONPATH= .venv/bin/pytest tests/ -q --cov=planbench_api \
  --cov=planbench_schemas --cov=planbench_simulator --cov-report=term

1038 passed, 1 warning in 638.10s (0:10:38)
TOTAL   3958 stmts   222 miss   534 branch   58 partial   93%
```

Trước refactor: 878 passed. Sau: **1038** (+160).

### Coverage phần mới

```
PYTHONPATH= .venv/bin/pytest tests/api tests/test_approval.py -q --cov=planbench_api
339 passed in 497.70s

apps/api/planbench_api/approval.py           63    0    100%
apps/api/planbench_api/repository_ports.py   34    0    100%
apps/api/planbench_api/review.py             47    0    100%
apps/api/planbench_api/routers/reviews.py    41    0    100%
apps/api/planbench_api/routers/users.py      34    0    100%
apps/api/planbench_api/accounts.py           70    1     99%
apps/api/planbench_api/routers/auth.py      142    4     97%
apps/api/planbench_api/user_store.py        134    3     96%
apps/api/planbench_api/db/repositories.py   328   24     91%
apps/api/planbench_api/review_service.py     80    9     88%
apps/api/planbench_api/auth.py              114   13     85%
apps/api/planbench_api/routers/benchmarks.py 136  17     85%
apps/api/planbench_api/oauth.py             150   35     74%
```

`oauth.py` ở 74% vì phần chưa chạy là `OAuthClient` — lớp thật sự gọi
HTTP. Nó được thay nguyên khối trong test, đúng theo yêu cầu "không gọi
OAuth thật". Phần logic thuần (`normalise_identity`, `seal_state`,
`open_state`, PKCE, `authorize_url`) thì có test đầy đủ.

### Frontend

```
apps/web$ npx tsc --noEmit          # sạch
apps/web$ npx vitest run
  Test Files  6 passed (6)
       Tests  78 passed (78)
apps/web$ npx next build
  ✓ Compiled successfully in 10.7s
  15 route, /login /welcome /reviews /auth/callback đều build
```

### Migration chạy thật (SQLite)

```
PLANBENCH_DATABASE_URL=sqlite:///<scratch>/e2e.db .venv/bin/alembic upgrade head
INFO  Running upgrade  -> 0001, Initial schema: ...
INFO  Running upgrade 0001 -> 0002, Accounts, OAuth links, review requests; benchmark ownership.
```

`tests/api/test_migrations.py` so schema sau `upgrade head` với
`Base.metadata` theo từng bảng, từng cột, từng nullability — nên
migration và ORM không thể lệch nhau âm thầm.

### Bốn tiêu chí nghiệm thu, chạy trên database đã migrate

```
A: create -> run -> accept -> leaderboard  OK (no account switching)
B: review by nickname -> inbox -> approve -> audit trail  OK
   audit: ['submit', 'request_review', 'approve', 'run', 'complete']
C: providers -> {'google': False, 'github': False, 'dev_login': True}
D: a pre-accounts benchmark is still owned by its creator  OK
```

C là trường hợp "chưa cấu hình gì": site vẫn chạy, trang login báo rõ,
không crash. D đã được chuyển thành test thường trực trong
`test_api_sql_backend.py`.

### Ba lỗi thật mà test bắt được

1. **Gate `run-async` chưa được áp trước khi vào hàng đợi.** Docstring
   nói có, code thì không: benchmark bị chặn vẫn được nhận vào hàng đợi
   rồi chết bên trong worker. Một 403 mà người gọi xử lý được đã biến
   thành job hỏng trong log không ai theo dõi. Sửa bằng
   `BenchmarkService.check_runnable()`, raise ngay tại request.
2. **Gửi spec review khi benchmark còn `draft` làm mất công của người
   duyệt.** `APPROVE` chỉ hợp lệ từ `pending_approval`, nên phê duyệt
   thật được ghi nhận trên request nhưng benchmark không nhúc nhích —
   lần Run sau đó lại ghi `self_approved`, tức audit trail nói dối rằng
   không ai xem. Sửa: gửi spec review **chính là** submit.
3. **Lỗi liên kết tài khoản bị nuốt thành thông báo chung.** Callback
   bắt `Exception` nên "tài khoản Google này đã thuộc tài khoản
   PlanBench khác" ra thành "sign-in failed". Tách `AccountLinkError`
   khỏi `NicknameError` để callback trả đúng lý do — đó là thông tin duy
   nhất giúp người dùng biết phải làm gì.

### Không được kiểm chứng

- **Chưa gọi Google/GitHub thật lần nào** (provider giả, theo yêu cầu).
- **Chưa chạy PostgreSQL thật** — SQLite chứng minh cấu trúc, không
  chứng minh hành vi dialect production.
- **Không có test render component** — trang được kiểm bằng `tsc` và
  `next build`; logic "nút hiện đúng lúc" test ở tầng helper + API.

## Sửa lỗi Gemini multi-step tool calling — 2026-07-30

### Triệu chứng

`/api/v1/agent/chat` gọi tool `list_benchmarks` thành công, lượt tiếp
theo hỏng:

```
Function call is missing a thought_signature
```

### Nguyên nhân

`_from_wire` chỉ giữ text + tool_calls; `_to_wire` **dựng lại** assistant
message từ hai thứ đó. Mọi metadata khác của hãng bị bỏ — trong đó có
`thought_signature` mà Gemini bắt buộc phải nhận lại.

### Bản sửa

Giữ nguyên payload provider trả về (`ProviderTurn`) và phát lại y hệt.
Cùng cơ chế áp cho adapter Anthropic (thinking block cũng phải echo
nguyên vẹn — cùng một lỗi tiềm ẩn).

### Kiểm chứng với SDK openai THẬT (2.50.0, không gọi mạng, không đọc key)

```
$ .venv/bin/python scratchpad/sdk_check.py
model_dump keys      : ['annotations', 'audio', 'content', 'function_call', 'refusal', 'role', 'tool_calls']
tool_call keys       : ['function', 'id', 'thought_signature', 'type']
signature survived   : SIGNATURE-FROM-GEMINI
captured format      : openai-chat
replay keys          : ['role', 'tool_calls']
replay signature     : SIGNATURE-FROM-GEMINI
```

Xác nhận giả định nền của bản sửa: model của SDK cho phép extra field,
nên `model_dump()` giữ trường mà SDK chưa từng biết tới.

### Test

```
$ PYTHONPATH= .venv/bin/pytest tests/ -q
878 passed, 1 warning in 196.25s (0:03:16)
```

14 test mới:

| File | Test | Nội dung |
|---|---|---|
| `tests/test_agent_gemini_tools.py` | 11 | capture, replay, và **vòng đầy đủ**: user → `list_benchmarks` → tool result → câu trả lời cuối |
| `tests/api/test_api_agent.py` | 3 | ProviderError → 502, ProviderUnavailable → 503, không lộ traceback |

Test vòng đầy đủ khẳng định request thứ hai có đúng
`["system", "user", "assistant", "tool"]` và assistant message vẫn mang
`thought_signature`.

### Lỗi phụ phát hiện khi chạy test

Sau khi anh cấu hình `.env` với `PLANBENCH_AGENT_PROVIDER=gemini`, **17
test API đỏ** với 503: fixture test đọc `.env` của máy nên cố gọi provider
thật. Đã sửa: `isolate_environment()` ghim `PLANBENCH_AGENT_PROVIDER=mock`
và các setting liên quan. Một test khác giả định "chưa provider nào
ready" cũng đỏ sau khi `openai` được cài — sửa thành khẳng định bất biến
(`ready` ⇒ `missing` rỗng) thay vì trạng thái của một máy cụ thể.

## M10 — 2026-07-30 (PostgreSQL + Docker Compose)

### Toàn bộ suite

```
$ .venv/bin/ruff check .
All checks passed!

$ PYTHONPATH= .venv/bin/pytest tests/ -q
864 passed, 1 warning in 141.81s (0:02:21)
```

74 test mới:

| File | Test | Nội dung |
|---|---|---|
| `tests/api/test_sql_repositories.py` | 59 | Repository SQL; phần lớn chạy **cùng assertion qua cả hai backend** qua một fixture `params=["sql","memory"]` |
| `tests/api/test_migrations.py` | 7 | `upgrade head`, `downgrade base`, upgrade lại, và so migration ↔ ORM từng bảng/cột/nullability/PK/cascade/index |
| `tests/api/test_api_sql_backend.py` | 8 | Toàn bộ API qua HTTP trên SQL storage |

### Ba điều đáng ghi

**FK bắt được lỗi trong chính test của tôi.** Năm test episode fail lần
chạy đầu:

```
sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) FOREIGN KEY constraint failed
[SQL: INSERT INTO episodes (id, benchmark_id, ...) VALUES (?, ?, ...)]
[parameters: ('1d70a50a88b0', 'bench-1', 'astar+dwa', 1, 0, 'success', ...)]
```

Test tạo episode với `benchmark_id='bench-1'` không tồn tại. Backend
in-memory không diễn đạt được ràng buộc này nên nó im lặng chấp nhận;
SQLite thì không. Sửa test (tạo benchmark cha trước) và thêm một test
SQL-only khẳng định episode mồ côi bị từ chối.

**Test khẳng định in-memory *mất* dữ liệu khi restart.** Đó chính là
hành vi M10 sinh ra để loại bỏ, nên nó được viết thành assertion để
không ai vô tình coi in-memory là đủ:

```python
def test_in_memory_backend_loses_data_on_restart(...):
    ...
    second = create_app(...)
    assert client.get(f"/api/v1/maps/{map_id}").status_code == 404
```

**Test khẳng định app thật sự chọn backend SQL** — nếu không, 8 test
API bên dưới sẽ âm thầm pass trên in-memory và chứng minh con số không:

```python
def test_the_app_actually_selected_the_sql_backend(sql_app):
    assert isinstance(sql_app.state.repos, SqlRepositoryHub)
```

### Vòng đời benchmark đầy đủ trên SQL (output thật)

```
$ PYTHONPATH= .venv/bin/pytest tests/api/test_api_sql_backend.py -q
8 passed, 1 warning in 12.46s
```

Test `test_full_benchmark_lifecycle_on_sql` chạy qua HTTP: gate 1 chặn
`run` khi chưa approve (409), submit → approve → run → `pending_review`
(gate 2 vẫn còn), audit trail lưu đúng thứ tự
`["submit", "approve", "run", "complete"]`.

`test_episode_replay_reads_from_the_artifact_store` chứng minh D15: row
SQL giữ `artifact_uri` bắt đầu bằng `file://`, replay trả về trajectory
đọc lại từ artifact.

### Compose file

```
$ .venv/bin/python -c "import yaml; ..."
YAML parses OK
services: ['api', 'db', 'migrate', 'web']
volumes : ['artifacts', 'db-data']
  db       depends_on=-
  migrate  depends_on={'db': {'condition': 'service_healthy'}}
  api      depends_on={'db': {'condition': 'service_healthy'}, 'migrate': {'condition': 'service_completed_successfully'}}
  web      depends_on=['api']
```

### Chưa kiểm chứng — nói thẳng

```
$ docker info
The command 'docker' could not be found in this WSL 2 distro.
We recommend to activate the WSL integration in Docker Desktop settings.
```

- **Chưa build image nào, chưa `docker compose up` lần nào.** Compose
  file mới chỉ được parse YAML, không có gì chứng minh image build được.
- **Chưa kết nối PostgreSQL thật** — không có server, không có docker.
  SQLite không chứng minh JSONB, transaction đồng thời, connection pool,
  hay cascade dưới dialect production.
- **`psycopg` chưa cài** trong `.venv`.

Xem KNOWN_LIMITATIONS mục 51–58.

## M9 — 2026-07-30 (2.5D + UI cho M5/M6/M8)

### Build và test frontend

```
$ cd apps/web && npx tsc --noEmit
(không lỗi)

$ npx vitest run
 ✓ src/lib/__tests__/playback.test.ts   (8 tests)
 ✓ src/lib/__tests__/demoMap.test.ts    (4 tests)
 ✓ src/lib/__tests__/transform.test.ts  (6 tests)
 ✓ src/lib/__tests__/scene25d.test.ts  (23 tests)
 Test Files  4 passed (4)
      Tests  41 passed (41)

$ npm run build
Route (app)                                 Size  First Load JS
┌ ○ /                                    1.78 kB         108 kB
├ ○ /agent                               4.09 kB         110 kB
├ ○ /algorithms                          2.47 kB         108 kB
├ ○ /benchmarks                          2.66 kB         109 kB
├ ƒ /benchmarks/[id]                     5.82 kB         115 kB
├ ○ /leaderboard                         2.74 kB         109 kB
├ ○ /library                             1.47 kB         111 kB
├ ○ /login                               1.98 kB         104 kB
├ ○ /maps                                2.03 kB         108 kB
├ ƒ /maps/[id]                           3.68 kB         110 kB
└ ○ /simulate                            6.05 kB         112 kB
```

23 test mới cho `scene25d`: phép chiếu (+z lên trên, hai trục tách
ngang ngược chiều, elevation 0 thành top-down), thứ tự vẽ theo `x + y`,
fit vào canvas kể cả khi tường cao, đùn ô OCCUPIED thành 3 mặt, ô
UNKNOWN vẽ phẳng, marker robot bị bóp thành ellipse.

### Chạy thật backend + frontend

```
$ .venv/bin/uvicorn planbench_api.main:app --port 8010     # backend
$ NEXT_PUBLIC_API_URL=http://localhost:8010 npx next start -p 3010

$ curl -s http://localhost:8010/api/v1/health
{"status":"ok","app":"PlanBench API","version":"0.1.0"}

trang            HTTP
/                200
/library         200
/leaderboard     200
/algorithms      200
/agent           200
/benchmarks      200
/simulate        200
/maps            200
/login           200
```

### Dữ liệu thật mà từng trang tiêu thụ (output thật)

```
== /scenario-library  (Library page)
   10 entries, curriculum order: open_space, static_obstacles, wide_corridor, narrow_corridor, doorway ...

== import doorway
   map=ab83c4a711f8 scenario=5a66e298d22c
   grid 48x36 res=0.25m, 272 occupied cells -> extruded in the 2.5D view

== /algorithms  (Algorithms page)
   astar+dwa              benchmarkable=True  required=[]
   astar+ppo              benchmarkable=True  required=['model_path']
   astar+pure_pursuit     benchmarkable=False required=[]

== create -> submit -> approve -> run-async  (Job progress panel)
   accepted: running 0/2
   poll: running    0/2
   poll: succeeded  2/2  2/2 episodes finished

== accept results (human gate 2) -> /leaderboard  (Leaderboard page)
   1 comparable group(s)
   conditions 6c767dc661ada452... doorway seeds [1, 2]
      astar+dwa    score=0.999 success=1.00 worst_clearance=0.4856734016900955

== /episodes/{id}/replay  (top-down và 2.5D đọc cùng dữ liệu)
   astar+dwa seed=1 plan=2 pts trajectory=191 pts status=success

== /agent/capabilities  (Agent console)
   provider=mock model=deterministic-mock deterministic=True
   11 tools, 8 forbidden capabilities, 7 docs indexed
   providers listed: ['anthropic', 'deepseek', 'gemini', 'groq', 'local', 'openai', 'openrouter', 'xai']
```

### Failure analysis panel trên một episode hỏng thật

Chạy reference adapter `astar+pure_pursuit` (bỏ qua sensing) trên
`sudden_stop`. Ba scenario trước đó (`crossing_obstacle`) nó vẫn về
đích, nên phải thử tiếp mới có va chạm — ghi lại đúng như đã xảy ra:

```
sudden_stop              -> collision      collision with dynamic obstacle at (6.325, 4.500) after 5.30s
  primary  : dynamic_obstacle_collision (confidence high)
  summary  : Collided with the moving obstacle 'cart'.
    evidence[engine_event] t=5.30s: collision: collision with dynamic obstacle at (6.325, 4.500) after 5.30s
    evidence[final_pose] t=5.30s: Robot at (6.325, 4.500)
    evidence[nearest_dynamic_obstacle] t=5.30s value=0.675: cart at (7.000, 4.500)
```

### Chưa kiểm chứng

- **Không có test render component** (jsdom + Testing Library). Vitest
  phủ phần hình học thuần; component React kiểm chứng bằng `tsc`,
  `next build` và chạy thật trên trình duyệt-less HTTP.
- **Chưa chụp màn hình** — kiểm chứng dừng ở mức HTTP 200 + dữ liệu API
  đúng, không phải kiểm chứng thị giác.
- **Three.js chưa cài** (xem KNOWN_LIMITATIONS 44).

## M8+ — 2026-07-30 (multi-provider)

Thêm adapter OpenAI-compatible phủ OpenAI / Gemini / OpenRouter / Groq /
DeepSeek / xAI / model local, cùng bảng chọn provider và script kiểm tra
key.

```
$ .venv/bin/ruff check .
All checks passed!

$ PYTHONPATH= .venv/bin/pytest tests/ -q --cov=planbench_agent --cov-report=term
services/agent_service/planbench_agent/factory.py                 87      2     30      3    96%
services/agent_service/planbench_agent/openai_provider.py        158     27     50     10    81%
TOTAL                                                           1273     76    330     43    92%
790 passed, 1 warning in 190.21s (0:03:10)
```

`openai_provider.py` ở 81%: phần gọi mạng thật không chạy được ở đây.
Phần dịch request/response — nơi bug thật nằm — được test đầy đủ bằng
object giả (55 test trong `tests/test_agent_providers_multi.py`).

### Trạng thái provider (output thật)

```
$ .venv/bin/python scripts/check_agent_provider.py
Provider readiness
  provider     ready  key env                what is missing
  anthropic    no     ANTHROPIC_API_KEY      set ANTHROPIC_API_KEY; pip install anthropic
  deepseek     no     DEEPSEEK_API_KEY       set DEEPSEEK_API_KEY; pip install openai
  gemini       no     GEMINI_API_KEY         set GEMINI_API_KEY; pip install openai
  groq         no     GROQ_API_KEY           set GROQ_API_KEY; pip install openai
  local        no     (none)                 pip install openai
  openai       no     OPENAI_API_KEY         set OPENAI_API_KEY; pip install openai
  openrouter   no     OPENROUTER_API_KEY     set OPENROUTER_API_KEY; pip install openai
  xai          no     XAI_API_KEY            set XAI_API_KEY; pip install openai

Selected  : mock (deterministic-mock)
Determinist: True

This is the offline keyword-matching provider, not a model.
Set PLANBENCH_AGENT_PROVIDER and the matching API key, then re-run to test a real one.
```

**Chưa provider ngoài nào được gọi thật** — không có key trong môi
trường này, và cả `anthropic` lẫn `openai` đều chưa cài (không tự cài
theo quy tắc). Cần chạy lại script trên sau khi dán key.

## M8 — 2026-07-30 (Agentic AI + RAG)

Provider: **mock tất định** (không có `ANTHROPIC_API_KEY` trong môi
trường này, và `anthropic` chưa cài). Nên các số dưới đây kiểm chứng
bảo đảm của platform — auth, cổng approval, toàn vẹn trích dẫn — chứ
**không** kiểm chứng chất lượng văn bản của model.

### Toàn bộ suite

```
$ .venv/bin/ruff check .
All checks passed!

$ PYTHONPATH= .venv/bin/pytest tests/ -q --cov=... --cov-report=term
services/agent_service/planbench_agent/__init__.py                10      0      0      0   100%
services/agent_service/planbench_agent/anthropic_provider.py     106     27     34      7    73%
services/agent_service/planbench_agent/deterministic.py          112      8     52     11    88%
services/agent_service/planbench_agent/evidence.py                77      0     18      3    97%
services/agent_service/planbench_agent/factory.py                 23      1      8      1    94%
services/agent_service/planbench_agent/gateway.py                 60      0      0      0   100%
services/agent_service/planbench_agent/provider.py               128      2      8      0    99%
services/agent_service/planbench_agent/rag.py                    106      2     32      1    98%
services/agent_service/planbench_agent/report.py                  58      0     12      0   100%
services/agent_service/planbench_agent/specs.py                  104      2     42      4    96%
services/agent_service/planbench_agent/tools.py                  104      2     22      1    98%
services/agent_service/planbench_agent/workflow.py               162      4     30      3    96%
TOTAL                                                           4365    173    770     81    95%
734 passed, 1 warning in 178.04s (0:02:58)
```

`anthropic_provider.py` ở 73% vì phần gọi mạng thật không chạy được ở
đây; phần dịch request/response (nơi bug thực sự nằm) được test bằng
object giả, không đụng mạng.

### Chạy thật end-to-end (output thật, `scripts/demo_agent_flow.py`)

```
=== capabilities
provider     : mock (deterministic-mock)
deterministic: True
tools        : analyse_episode, get_benchmark, get_benchmark_report,
               get_leaderboard, list_algorithms, list_benchmarks,
               list_episodes, list_scenarios, propose_benchmark,
               run_benchmark, search_knowledge
forbidden    : accept_result, approve_benchmark, declare_safe, drive_robot,
               reject_result, write_map, write_metrics, write_scenario
indexed docs : 7

=== mission không parse được -> refusal, không tạo gì
draft   : None
refusal : the provider did not return a benchmark specification
created : 0

=== mission gọi stack cần checkpoint -> refusal
error   : algorithm 'astar+ppo' requires configuration the agent must not
          invent (model_path); a human has to create this benchmark and supply it

=== mission hợp lệ -> draft, submit, dừng chờ người
draft     : {"name": "open_space: astar+dwa", "scenario": "open_space",
             "algorithms": ["astar+dwa"], "seeds": [1, 2]}
benchmark : 8030820dbc6a state=pending_approval
next step : A reviewer other than 'op-alice' must approve it before it can run.

=== agent thử chạy trước khi được approve
HTTP 409: benchmark '8030820dbc6a' is in state 'pending_approval'; a human
          reviewer must approve it before the agent may run it

=== operator thử tự approve benchmark của mình
HTTP 403: role 'operator' may not access this endpoint (allowed: ['reviewer'])

=== reviewer approve (gate 1), agent chạy
state after approve: approved
state after run    : pending_review  (gate 2 vẫn còn phía trước)
conditions_checksum: af7af68085e3493d720161570c3f705f5009904aee34f921591027beae2a052a

=== evidence lấy từ storage (9 item)
[benchmark:8030820dbc6a]            state 'pending_review', algorithms ['astar+dwa'], seeds [1, 2]
[benchmark:8030820dbc6a]            conditions_checksum af7af680... map 'open-space'
[aggregate:8030820dbc6a#astar+dwa]  success_rate=1.000 collision_rate=0.000 over 2 episodes
[aggregate:8030820dbc6a#astar+dwa]  mean travel time = 10.400 s
[aggregate:8030820dbc6a#astar+dwa]  worst minimum clearance = 0.950 m
[episode:c04fcd20382c]              seed=1 'success' (goal reached 0.294 m after 10.40s)
[artifact:c04fcd20382c]             file://.../episodes/c04fcd20382c.json
[episode:03aab36ec508]              seed=2 'success' (goal reached 0.294 m after 10.40s)
[artifact:03aab36ec508]             file://.../episodes/03aab36ec508.json

=== báo cáo sinh ra
refused    : False
provisional: True
citations  : 9 (đều đối chiếu được với bundle)
...
This report summarises recorded simulation results. It is not a safety
certification: ... The safety judgement belongs to a human reviewer.
PROVISIONAL — a reviewer has not accepted these results yet, so they must
not be published as a conclusion.
```

### Điều được kiểm chứng

| Ràng buộc spec | Test |
|---|---|
| LLM không điều khiển `/cmd_vel` | `test_gateway_protocol_has_no_actuation_method`, `test_no_tool_grants_a_forbidden_capability` |
| LLM không bịa map/scenario | `test_an_invented_scenario_is_refused`, `test_the_agent_only_uses_library_scenarios` |
| LLM không bịa metric/kết quả | `test_a_fabricated_citation_is_rejected`, `test_uncited_prose_is_discarded` |
| LLM không bỏ qua approval | `test_run_is_refused_in_every_unapproved_state` (5 state), `test_agent_run_is_refused_before_approval` |
| LLM không tự kết luận an toàn | `test_the_deterministic_report_makes_no_safety_claim`, `test_every_report_carries_the_safety_disclaimer` |
| Structured output sai schema thì không chạy | `test_a_schema_violating_answer_is_refused`, `test_rejects_unknown_fields_rather_than_ignoring_them` |
| Từ chối khi không đủ bằng chứng | `test_empty_evidence_refuses_without_calling_the_provider` |
| Separation of duties vẫn áp dụng cho agent | `test_the_operator_cannot_approve_their_own_agent_benchmark` |

### Lỗi/ràng buộc phát hiện trong M8

1. **`astar+ppo` không thể để agent tự chọn.** Test API đầu tiên đỏ với
   `PPOStackConfig.model_path Field required`. Agent không biết checkpoint
   nào đúng, và bịa đường dẫn là đúng kiểu bịa spec cấm → thêm
   `agent_selectable_algorithms()` loại mọi stack có config bắt buộc.
2. **Tokenizer RAG giữ dấu chấm cuối câu**, nên `conditions_checksum.`
   không khớp query `conditions_checksum`. Sửa: strip `.-` ở hai đầu
   token, vẫn giữ dấu ở giữa (`0.05`, `nav2-bringup`).

## M7 — 2026-07-30 (ROS2 / Nav2 closed-loop)

Môi trường: ROS2 Jazzy + Nav2 + colcon có sẵn; `rclpy`, `nav2_*` OK.
System Python **không có pydantic** → PYTHONPATH trỏ vào `.venv`
site-packages (cùng CPython 3.12), không cài global.

### Build

```
$ cd ros2_ws && colcon build
Summary: 5 packages finished
```

### Simulator node phát đủ topic (output thật)

```
$ ros2 topic list
  /benchmark_event  /clock  /cmd_vel  /episode_status  /map
  /odom  /scan  /tf  /tf_static

$ ros2 topic echo /map --once --field info
resolution: 0.25   width: 48   height: 36   origin: (0,0)

$ ros2 topic echo /scan --once
frame_id: base_scan   angle_min: -3.14159   angle_max: 3.05433   range_max: 6.0
```

### Closed-loop thủ công

```
armed 8s  -> status: running, elapsed_time: 0.0   (stuck detector KHÔNG kích hoạt)
start_episode -> OK
cmd_vel 0.5 m/s trong 4s -> x: 1.975 -> 4.010   (đi 2.035 m, đúng 0.5 x 4)
ngừng cmd_vel 5s        -> x: 4.025 -> 4.025   (watchdog dừng robot)
```

### Nav2 lifecycle + NavigateToPose

```
$ ros2 lifecycle get /controller_server   -> active [3]
$ ros2 lifecycle get /planner_server      -> active [3]
$ ros2 lifecycle get /bt_navigator        -> active [3]
$ ros2 lifecycle get /behavior_server     -> active [3]
$ ros2 action list  -> /navigate_to_pose /compute_path_to_pose /follow_path ...

$ ros2 action send_goal /navigate_to_pose ... {x: 10.5, y: 4.5}
Goal finished with status: SUCCEEDED

$ ros2 topic echo /episode_status --once
  scenario_name: open_space
  status: success
  reason: goal reached (distance 0.294 m) after 12.05s
  min_clearance: 1.24394736842106
$ ros2 service call /planbench_simulator/episode_result ...
  finished=True status='success' steps=241 trajectory_length=8.706 min_clearance=1.244
```

### Benchmark runner tự động (output thật)

```
scenario               seed outcome        nav2          t(s)  len(m)  clear
open_space                1 success        unknown      10.75    8.70  1.246
open_space                2 success        unknown      10.95    8.70  1.246
static_obstacles          1 success        unknown      11.25    8.85  1.199
static_obstacles          2 success        unknown      10.85    8.86  1.201
doorway                   1 success        unknown       9.85    7.76  1.723
doorway                   2 success        unknown      10.10    7.76  1.723

success 6/6
```

`nav2` = `unknown` vì runner thoát vòng chờ ngay khi **simulator** phán
quyết (trọng tài là simulator, không phải Nav2), nên action result chưa
kịp về. Đây là hành vi cố ý, không phải lỗi.

### Lỗi đã gặp và sửa trong M7

1. **Episode chết vì stuck trước khi Nav2 kết nối**: node bắt đầu chạy
   vật lý ngay lúc boot, robot đứng yên chờ controller → stuck detector
   kết thúc episode sau 5 s. Sửa: tách arming, thêm service
   `StartEpisode`/`StopEpisode`; trong lúc armed vẫn phát sensor/TF/clock
   cho Nav2 khởi động. Bằng chứng: armed 8 s vẫn `running`, elapsed 0.0.
2. **Runner giữ status cũ**: vòng chờ thoát ngay, báo "running" 0.00 s
   cho cả 4 episode. Sửa: xoá cache status trước mỗi episode.
3. **Episode thứ 2 trở đi luôn hỏng (3/6)**: reset dịch chuyển robot về
   start nhưng costmap và BT của Nav2 vẫn giữ trạng thái cũ → abort hoặc
   "succeeded" tức thì. Sửa: đợi TF ổn định 3 s rồi
   `clear_entirely_{global,local}_costmap`. Sau khi sửa: **6/6**.
4. **`PLANBENCH_ROOT=$PWD` sai** khi cwd đã đổi sang `ros2_ws` → dùng
   đường dẫn tuyệt đối.
5. **colcon chạy từ thư mục con** tạo `build/install/log` lạc trong
   `src/` → xoá và luôn build từ `ros2_ws/`.

## M6 — 2026-07-30

```
$ .venv/bin/ruff check .
All checks passed!
$ PYTHONPATH= .venv/bin/pytest tests/ -q
560 passed, 1 warning in 121.36s
```

Test mới: `tests/test_rl.py` (30) — LiDAR down-sample lấy min, waypoint
trong hệ robot, cross-track error, encoding bounded/finite, reward
(terminal áp đảo shaping, collision không "mua" được bằng progress),
env (NaN action → dừng an toàn + đếm, clamp giới hạn, cùng seed replay
khớp, khác seed đổi traffic, truncate, success).

### Smoke training PPO trên CPU (output thật)

```
$ PYTHONPATH= .venv/bin/python scripts/train_ppo.py --smoke \
    --model-id ppo-smoke --mlflow-uri "file://$PWD/mlruns"
training ppo-smoke: 4096 timesteps, curriculum=['open_space'], seed=0
checkpoint: ml/checkpoints/ppo-smoke.zip
metadata:   observation=v1 reward=v1 smoke=True

deterministic evaluation
  episodes        3
  success_rate    0.00
  collision_rate  0.00
  mean_reward     -49.4
  mean_steps      300
  invalid_actions 0
    open_space               success=0.00

NOTE: smoke checkpoint. These numbers validate the pipeline, not the
quality PPO can reach.
```

success_rate 0.00 là **đúng kỳ vọng**: 4096 timestep gần như chưa học gì.
Điều được kiểm chứng ở đây là pipeline (env → PPO → checkpoint →
metadata → MLflow → evaluation), không phải chất lượng thuật toán.
`invalid_actions 0` xác nhận policy không sinh NaN.

### Benchmark A*+DWA vs A*+PPO (output thật, cùng điều kiện)

```
Stacks đăng ký: [('astar+dwa', True), ('astar+ppo', True), ('astar+pure_pursuit', False)]

conditions_checksum: 9d553000a6aac601  seeds=(1, 2, 3)
stack             succ  coll timeout   travel  lat_ms
astar+dwa         1.00  0.00    0.00   10.40s    6.63
astar+ppo         0.00  0.00    0.00        -    0.46
```

Cùng `conditions_checksum` → so sánh hợp lệ về mặt điều kiện. **Không
được kết luận "DWA tốt hơn PPO"** từ bảng này: model PPO chưa được train.
Điều bảng này chứng minh là hạ tầng so sánh hai stack hoạt động.

### Kiểm chứng seed thực sự thay đổi traffic

```
Vị trí pedestrian tại t=2.0s theo từng seed:
  seed=1: y=2.274    seed=2: y=2.209    seed=3: y=2.004
  seed=4: y=5.362    seed=5: y=4.580
cùng seed lặp lại: True
```

### Lỗi đã phát hiện và sửa trong M6

1. **Seed vô nghĩa với scenario tất định**: `periodic`/`waypoint`/
   `sudden_stop` không đọc seed, nên benchmark 5 seed chạy 5 episode y
   hệt và báo variance = 0 (sai lệch nghiêm trọng về tính công bằng).
   Sửa: thêm `DynamicObstacle.seed_time_offset` — lệch đồng hồ obstacle
   theo hash(seed, tên); library scenario khai báo offset bằng đúng một
   chu kỳ.

## M5 — 2026-07-30

```
$ .venv/bin/ruff check .
All checks passed!
$ PYTHONPATH= .venv/bin/pytest tests/ -q
530 passed, 1 warning in 120.98s
```

Test mới: `test_dynamic_obstacles.py` (26), `test_scenario_library.py` (53),
`test_failure_analysis.py` (15), `tests/api/test_api_m5.py` (13).

### Kết quả DWA trên scenario library (output thật)

```
open_space           success      t= 10.40s clear=0.950
wide_corridor        success      t= 13.40s clear=0.450
narrow_corridor      stuck        t=  9.90s clear=0.450
doorway              success      t=  9.50s clear=0.486
```

`narrow_corridor` (1.5 m) là **kết quả benchmark hợp lệ**, không phải bug:
A* tìm được đường (test khẳng định), nhưng DWA với cấu hình mặc định không
qua được hành lang chỉ rộng gấp 2.5 lần đường kính robot. Đây chính là loại
phát hiện mà benchmark tồn tại để tạo ra.

### Lỗi đã gặp và sửa trong M5

1. **DWA đỗ cách goal 0.56 m** (phát hiện khi chạy `wide_corridor`): cost
   thiếu số hạng "tiến tới goal". Khi robot đã thẳng hàng và bám path,
   `heading` = `path` = 0, nên clearance một mình quyết định và v=0 rẻ hơn
   mọi lựa chọn tiến lên gần tường. Sửa: thêm cost `goal` (weight 2.0) +
   giới hạn vận tốc theo quãng đường phanh `sqrt(2·a·d)` + giảm
   `clearance_cap` 1.0 → 0.6 m. Bằng chứng: 12.44 m → tới goal 13.0 m.
2. **`doorway` không có đường đi**: khe 1.0 m nhỏ hơn 2×inflation
   (0.65 m). Mở rộng thành 1.6 m và ghi rõ lý do trong docstring.
3. **Test LiDAR sai kỳ vọng**: giả định quét thấy bề mặt hình tròn chính
   xác, thực tế thấy cell đã rasterize (1 m). Sửa test so sánh có/không có
   obstacle và khẳng định đúng biên cell.
4. **`ObstacleSnapshot` khai báo sau `TrajectoryPoint`** → forward
   reference không resolve; sắp xếp lại thứ tự class.

## M4 — 2026-07-30

### Lint + tests

```
$ .venv/bin/ruff check .
All checks passed!
$ PYTHONPATH= .venv/bin/pytest tests/ -q
423 passed, 1 warning in 93.44s
$ cd apps/web && npm run typecheck   # clean
$ npm run test
 Test Files  3 passed (3) | Tests 18 passed (18)
$ npm run build
 ✓ Compiled successfully | ✓ Generating static pages (8/8)
   /benchmarks 2.66 kB · /benchmarks/[id] 5.41 kB · /login 1.98 kB
```

### MLflow tracking (output thật, file store)

```
tracker: mlflow | experiment: planbench-verify | last run: 5c22c90d54a3
experiment: planbench-verify | runs: 2
  run dwa-vs-reference:astar+pure_pursuit
    tags: algorithm=astar+pure_pursuit conditions=7c7ec7bc0ea6 benchmark_id=bench-demo-1
    params: seeds=[1, 2, 3] map=mlflow-demo timeout=90.0 radius=0.3
    metrics: success_rate=1.0 episodes=3.0 travel=14.40 clearance=1.200
    per-seed travel times: [(1, 14.4), (2, 14.4), (3, 14.4)]
  run dwa-vs-reference:astar+dwa
    tags: algorithm=astar+dwa conditions=7c7ec7bc0ea6 benchmark_id=bench-demo-1
    metrics: success_rate=1.0 episodes=3.0 travel=15.70 clearance=1.200
    per-seed travel times: [(1, 15.7), (2, 15.7), (3, 15.7)]
```

Cả hai stack có cùng `conditions_checksum` → so sánh hợp lệ.

### Human-in-the-loop end-to-end qua HTTP thật

```
login: alice=operator  carol=reviewer
map: ac34a0d2f07e | scenario: e1740e091c79
create -> 201 state=draft
run before approval -> 409 invalid_state: cannot run a benchmark in state 'draft'
operator self-approve -> 403 forbidden
reviewer approve -> 200 state=approved
run -> 200 state=pending_review

fairness checksum: 344ab16e33d2d923f97f  seeds=[1, 2]
stack                   succ  coll   travel   clear  lat_ms
astar+dwa               1.00  0.00   17.45s   0.491    6.23
astar+pure_pursuit      1.00  0.00   15.85s   0.603    0.00

episodes stored: 4 (artifact f2e7f3a1e749.json, 58727 bytes, sha256 a06fa0951f0e)
replay: astar+dwa seed=1 points=350 plan_waypoints=4

accept-result -> 200 state=accepted
audit trail: submit(operator) -> approve(reviewer) -> run(operator) -> complete(operator) -> accept_result(reviewer)
```

Ghi chú đọc số liệu: pure-pursuit nhanh hơn DWA ở map trống này vì nó bám
thẳng đường A* và bỏ qua cảm biến; **không** được kết luận nó "tốt hơn" —
nó là adapter tham chiếu (`benchmarkable=false`), không dùng LiDAR nên
không an toàn với vật cản chưa biết.

### Lỗi đã gặp và sửa trong M4

1. **DWA không bao giờ tăng tốc**: cost `smoothness` chuẩn hóa theo cửa sổ
   gia tốc nên phạt 0.15 cho một lần tăng tốc đầy, trong khi lợi ích
   `velocity` chỉ 0.06 → luôn chọn v nhỏ nhất. Sửa: chuẩn hóa smoothness
   theo giới hạn vận tốc robot (cùng thang với velocity). Bằng chứng
   trước/sau: v giữ ở 0.014 m/s → đạt 1.00 m/s.
2. **DWA quá chậm** (53 s cho 8 test): rollout thuần Python
   135 ứng viên × 15 bước × ~72 điểm LiDAR. Sửa: vectorize bằng numpy +
   giữ lệnh giữa các chu kỳ điều khiển → 12 s.
3. **Test sai giả định** (không phải lỗi code): DWA xoay tại chỗ trong hốc
   0.5 m là hợp lệ; clearance bão hòa khi tường cách 1.5 m > cap 1.0 m.
   Sửa test cho đúng vật lý, thêm test hốc hẹp hơn robot để kiểm tra
   fallback dừng.
4. **Failure-to-progress báo nhầm khi đi vòng**: đo bằng khoảng cách Euclid
   nên đường vòng dài hợp lệ bị coi là thất bại. Nới mặc định 15 s → 30 s,
   ghi rõ giới hạn trong KNOWN_LIMITATIONS, scenario đi vòng phải tự nới.
5. **passlib 1.7.4 không tương thích bcrypt 5.x** → bỏ passlib, dùng
   `bcrypt` trực tiếp (có cắt 72 byte tường minh).
6. **MLflow 3 từ chối file store** → tracker tự bật `MLFLOW_ALLOW_FILE_STORE`
   cho URI `file:`; production dùng MLflow server qua http.
7. **Chạy benchmark 2 lần** (bản nháp đầu lưu episode bằng vòng lặp riêng)
   → callback `on_run(record, stack_run)` trả về cả episode, chạy một lần.

## M3 — 2026-07-30

### Frontend

```
$ npm run typecheck    # tsc --noEmit
(no output = clean)

$ npm run test
 ✓ src/lib/__tests__/playback.test.ts (8 tests)
 ✓ src/lib/__tests__/transform.test.ts (6 tests)
 ✓ src/lib/__tests__/demoMap.test.ts (4 tests)
 Test Files  3 passed (3)
      Tests  18 passed (18)

$ npm run build
 ✓ Compiled successfully
 ✓ Generating static pages (6/6)
Route (app)                     Size  First Load JS
┌ ○ /                        1.75 kB         108 kB
├ ○ /_not-found                993 B         103 kB
├ ○ /maps                    2.02 kB         108 kB
├ ƒ /maps/[id]               3.68 kB         110 kB
└ ○ /simulate                6.05 kB         112 kB
```

### Backend (sau khi thêm WS pace mode)

```
$ PYTHONPATH= .venv/bin/pytest tests/ -q
324 passed, 1 warning in 2.43s
$ .venv/bin/ruff check .
All checks passed!
```

### Smoke test hệ thống thật (backend + frontend cùng chạy)

```
$ curl -s http://127.0.0.1:8000/api/v1/health
{"status":"ok","app":"PlanBench API","version":"0.1.0"}

# Luồng E2E qua REST:
map: 37fc92179f0d checksum 70727ee9ac
scenario: 8a0c608c6996
episode: success steps 272
metrics: length 12.56 m, efficiency 1.037, min_clearance 0.250 m
benchmark: 3 runs, success_rate 1.00, mean_travel_time 13.60 s

# WebSocket (episode 177 frame):
pace=false -> waypoints=2 states= 177 final=result/success
pace=true  -> waypoints=2 states=   2 final=result/success   (speed=1000, rate cap)

# Frontend production server:
GET /         -> 200
GET /maps     -> 200
GET /simulate -> 200   (chứa "Run simulation", "Playback timeline", "Global path")
```

Lỗi đã gặp và sửa trong M3:
1. WS chỉ giao 4/177 frame khi client pace cục bộ (rate cap server bỏ
   frame) → thêm tham số `pace=false`; UI dùng chế độ này; thêm test
   `test_unpaced_stream_delivers_every_frame` và
   `test_paced_stream_skips_frames_at_high_speed`.
2. `next start` lần hai lỗi EADDRINUSE do server cũ còn chạy → kill pid
   cũ rồi khởi động lại, xác nhận build mới được phục vụ.

## M2 — 2026-07-30

```
$ .venv/bin/ruff check .
All checks passed!
$ PYTHONPATH= .venv/bin/pytest tests/ -q
322 passed, 1 warning in 1.40s
```

Warning duy nhất: websockets deprecation từ uvicorn (thư viện ngoài).

Smoke test server thật:

```
$ curl -s http://127.0.0.1:8123/api/v1/health
{"status":"ok","app":"PlanBench API","version":"0.1.0"}
openapi paths: 16
```

Lỗi đã gặp và sửa trong M2:
1. Handler 422 crash 500 vì `RequestValidationError.errors()` chứa
   object ValueError không serialize được → dùng jsonable_encoder với
   custom_encoder {Exception: str}.
2. WS test speed=1000 bị rate-cap 60 Hz bỏ gần hết frame → test dùng
   speed=50 (~14 frame, chạy 0.23s).

## M1B — 2026-07-30

### Ruff

```
$ .venv/bin/ruff format .   # 39 files left unchanged (sau khi format)
$ .venv/bin/ruff check .
All checks passed!
```

### Pytest

```
$ PYTHONPATH= .venv/bin/pytest tests/ -q
296 passed in 0.31s
```

Coverage (chạy với --cov, branch coverage bật):

```
TOTAL  893 stmts, 27 miss, 218 branch, 11 partial — 95%
```

Các phần miss chính: `grid.rasterize_obstacles` nhánh lỗi hiếm (78%
file grid do rasterize mới thêm test gián tiếp), vài nhánh phòng thủ
trong engine. Không bỏ file nào khỏi báo cáo.

### Demo headless (output thật)

```
$ PYTHONPATH= .venv/bin/python scripts/demo_astar_episode.py
map: demo-warehouse (48x36 @ 0.25 m)
scenario: demo-astar-pure-pursuit
plan: success=True waypoints=6 length=13.26 m expanded=288 time=4.8 ms
episode: status=success reason='goal reached (distance 0.288 m) after 14.40s'
  steps=288 sim_time=14.40 s
metrics:
  trajectory_length = 12.82 m
  path_efficiency   = 1.0341715682303163
  average_speed     = 0.89 m/s
  max_speed         = 1.00 m/s
  smoothness        = 0.452 rad/m
  min_clearance     = 0.073 m
  mean_clearance    = 0.508 m
artifact: artifacts/demo/astar_episode.json
```

Ghi chú: path_efficiency > 1 vì đường thực tế cắt cua ngắn hơn polyline
kế hoạch (đã ghi trong docstring metric).

## M1A — 2026-07-30

- Ruff: sạch. Pytest: 220 passed. Coverage 99% (chi tiết trong lịch sử
  phiên làm việc; bị thay thế bởi số liệu M1B ở trên).

## Lỗi môi trường đã biết

- Shell source ROS2 Jazzy → PYTHONPATH chứa /opt/ros/... làm pytest nạp
  plugin `launch_testing` và crash import yaml. Fix: chạy test với
  `PYTHONPATH=` hoặc `env -u PYTHONPATH`.

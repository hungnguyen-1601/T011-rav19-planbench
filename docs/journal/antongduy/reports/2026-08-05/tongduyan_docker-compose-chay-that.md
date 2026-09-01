# Report — Đợt 0.2: chạy Docker Compose thật

> **Ngày làm:** 2026-08-05.
> **Plan:** `docs/antongduy/plans/2026-08-05/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`, mục **0.2**.
> **Trạng thái: XONG.** Bốn service healthy, migration chạy trên PostgreSQL
> thật, benchmark 2 stack × 5 seed chạy end-to-end trong container, dữ liệu
> nằm trong PostgreSQL.
> **Môi trường:** Windows 11, Docker Engine 29.5.3, Docker Compose v5.1.4.
> **Test:** `1129 passed, 4 skipped` (baseline sau Đợt 0.1: `1120 passed,
> 4 skipped` — thêm 9 test hồi quy cho 2 lỗi sửa ở mục 2).

---

## 0. Kết luận một câu

Stack chạy được thật, **nhưng chỉ sau khi sửa 2 lỗi chặn** mà không bài
test nào trong 1120 test bắt được — cả hai chỉ xuất hiện khi code chạy
trong container, dưới user không phải root, trên dữ liệu do lần chạy
Docker trước để lại. Đây đúng là lý do plan xếp mục 0.2 vào nhóm "chặn
rủi ro demo".

---

## 1. Đã làm gì

### 1.1. Build và khởi động

```bash
docker compose build      # exit 0
docker compose up -d
```

Ba image được tạo:

| Image | Disk usage | Content size |
|---|---|---|
| `planbench-api` | 576 MB | 134 MB |
| `planbench-migrate` | 576 MB | 134 MB (cùng Dockerfile với api) |
| `planbench-web` | 339 MB | 81.9 MB |

`docker compose ps -a` sau khi ổn định:

```
NAME                  IMAGE                SERVICE   STATUS
planbench-api-1       planbench-api        api       Up (healthy)    0.0.0.0:8000->8000/tcp
planbench-db-1        postgres:17-alpine   db        Up (healthy)    5432/tcp
planbench-migrate-1   planbench-migrate    migrate   Exited (0)
planbench-web-1       planbench-web        web       Up (healthy)    0.0.0.0:3000->3000/tcp
```

**Thứ tự phụ thuộc hoạt động đúng như thiết kế.** Log của chính lần
`up` xác nhận từng bước, không phải suy đoán:

```
Container planbench-db-1 Healthy
Container planbench-migrate-1 Started
Container planbench-migrate-1 Exited
Container planbench-api-1 Starting
```

`api` chỉ khởi động **sau** khi `migrate` exit 0 — đúng điều mà comment
đầu `docker-compose.yml` tuyên bố, và giờ có bằng chứng.

### 1.2. Migration trên PostgreSQL thật

Log `migrate` ngắn tới mức dễ nghi ngờ (chỉ 2 dòng `alembic.runtime.migration`),
nên đã kiểm bằng chính database thay vì tin log:

```sql
planbench=# \dt
 alembic_version | approvals | benchmarks | episodes | maps
 oauth_accounts  | review_requests | scenarios | simulations | users
(10 rows)
```

Đủ 10 bảng. `PLANBENCH_DATABASE_URL` là PostgreSQL và API xác nhận khi
khởi động:

```json
{"level": "INFO", "message": "persistence: SQL", "context": {"dialect": "postgresql"}}
```

Đây là lần đầu migration chạy ngoài SQLite — KNOWN_LIMITATIONS #92 đã
được gỡ.

---

## 2. Hai lỗi chặn đã phát hiện và sửa

### 2.1. API chết ngay khi import — `PermissionError` trên `artifacts`

**Triệu chứng.** Container `api` restart liên tục:

```
File "/app/apps/api/planbench_api/model_storage.py", line 103, in __init__
  self._root.mkdir(parents=True, exist_ok=True)
PermissionError: [Errno 13] Permission denied: 'artifacts'
```

**Nguyên nhân.** `config.py` để `model_dir: str = "artifacts/models"` —
một đường dẫn **tương đối** và **độc lập** với `artifact_dir`. Compose
đặt `PLANBENCH_ARTIFACT_DIR=/data/artifacts` nhưng không đặt
`PLANBENCH_MODEL_DIR`, nên model storage vẫn trỏ vào `./artifacts/models`
tính từ `WORKDIR /app`. `/app` thuộc root, tiến trình chạy dưới user
`planbench` (uid 10001, đúng theo Dockerfile) — không tạo được thư mục.

Điều làm lỗi này nặng hơn bình thường: `LocalModelStorage` được dựng
trong `create_app()`, tức **lúc import module**, nên đây là crash khởi
động chứ không phải lỗi 500 ở một endpoint upload mà có thể không ai
bấm trong buổi demo.

**Đã sửa** (`apps/api/planbench_api/config.py`): `model_dir` mặc định
rỗng, và một `model_validator(mode="after")` điền
`<artifact_dir>/models`. Chọn cách này thay vì thêm một biến môi trường
nữa vào compose, vì thêm biến chỉ vá đúng file compose này — bất kỳ
deployment nào set `PLANBENCH_ARTIFACT_DIR` mà quên `PLANBENCH_MODEL_DIR`
sẽ gặp lại y hệt. Gốc vấn đề là hai setting đáng lẽ phải bám nhau thì
lại trôi độc lập.

### 2.2. Mọi endpoint danh sách trả 500 vì vai trò cũ trong audit trail

**Triệu chứng.** `GET /api/v1/leaderboard` và `GET /api/v1/benchmarks`
trả `internal_error`:

```
File "/app/apps/api/planbench_api/db/repositories.py", line 713, in _to_benchmark
pydantic_core._pydantic_core.ValidationError: 1 validation error for ApprovalRecord
role
  Input should be 'member', 'admin', 'operator' or 'reviewer'
  [type=enum, input_value='engineer', input_type=str]
```

**Nguyên nhân.** Volume `planbench_db-data` được tạo **2026-08-02** và
còn nguyên dữ liệu của lần chạy Docker trước đó. Trong đó:

```sql
planbench=# select distinct role from approvals;
 member | engineer | approver
```

Enum `Role` sau đợt refactor bỏ vai trò chỉ còn `member/admin/operator/reviewer`.
Một hàng audit cũ không parse được là đủ để **cả danh sách** hỏng — kiểu
lỗi "một dòng dữ liệu cũ giết cả endpoint".

**Đã sửa** (`apps/api/planbench_api/approval.py`): giữ lại `ENGINEER` và
`APPROVER` trong enum, kèm docstring nói rõ vì sao. **Cố ý không viết
migration ghi đè** hai giá trị đó thành `member`: approvals là audit
trail, và sửa lịch sử để chương trình chạy được là đánh đổi sai. Việc
này an toàn vì đã kiểm: `Role` **không** được dùng cho phân quyền ở bất
cứ đâu — grep `Role.` toàn repo chỉ ra một chỗ ghi (`services.py:327`),
authority đến từ `Capability` (OWNER/REVIEWER/ADMIN). Một vai trò lưu
trong DB là nhãn của một sự kiện đã xảy ra, không phải quyền.

**Bài học đã ghi vào KNOWN_LIMITATIONS #99:** đổi tên vai trò về sau
**không được** xóa giá trị cũ khỏi enum.

---

## 3. Kiểm chứng end-to-end trong container

Toàn bộ chạy qua API ở `http://localhost:8000` (tức đi qua port mapping
của container, không phải process trên host).

| Bước | Kết quả |
|---|---|
| `GET /api/v1/health` | `{"status":"ok","app":"PlanBench API","version":"0.1.0"}` |
| `GET /api/v1/auth/providers` | `{"google":false,"github":false,"dev_login":true}` |
| Đăng nhập `antongduy` | token 133 ký tự, `/auth/me` trả đúng user |
| `GET /api/v1/algorithms` | 5 stack, **có `rrtstar+dwa` và `rrtstar+pure_pursuit`** |
| `POST /scenario-library/doorway/import` | map `215bdad9de29`, scenario `85cd770f7775` |
| `POST /benchmarks` | benchmark `7d777b82935a`, 2 stack × 5 seed |
| `POST /benchmarks/{id}/run` | 10 run, state `pending_review` |
| `POST /benchmarks/{id}/accept-result` | state `accepted` |
| `GET /leaderboard` | 1 group, 2 entry |
| `GET /episodes/{id}/replay` | 199 điểm trajectory, đọc từ volume artifact |
| Web `http://localhost:3000` | `/`, `/login`, `/benchmarks`, `/algorithms`, `/leaderboard`, `/simulate` đều 200 |

### 3.1. Đợt 0.1 hiển thị đúng qua container

```
astar+dwa           | benchmarkable=True  | global=astar   | stochastic=False
astar+ppo           | benchmarkable=True  | global=astar   | stochastic=False | requires_model=True
astar+pure_pursuit  | benchmarkable=False | global=astar   | stochastic=False
rrtstar+dwa         | benchmarkable=True  | global=rrtstar | stochastic=True
rrtstar+pure_pursuit| benchmarkable=False | global=rrtstar | stochastic=True
```

RRT\* của Đợt 0.1 đi qua image, qua PostgreSQL, ra tới API — không chỉ
chạy trong pytest trên host.

### 3.2. Kết quả benchmark trong container **trùng khít** lần chạy trên host

`doorway`, seed 1–5, `conditions_checksum = 2c67300aa580c997271db33afb56673f9c9e8f20fc57cfaa75166141f743e887`

```
algorithm      success  collision  travel_s  path_eff
astar+dwa         1.00       0.00      9.50     1.038
rrtstar+dwa       1.00       0.00      9.83     1.040

planned path length per seed
  astar+dwa    8.0000  8.0000  8.0000  8.0000  8.0000
  rrtstar+dwa  8.0029  8.0113  8.0125  8.0411  8.0407
```

So với bảng trong `tongduyan_dot-0-1-cai-rrt-star.md` (chạy trên host,
cùng scenario, cùng seed): **checksum giống hệt, travel time giống hệt,
path length từng seed giống hệt tới 2 chữ số**. Tức là tính tái lập đứng
vững **qua cả ranh giới container** — cùng seed, khác môi trường, cùng
kết quả. Đây là bằng chứng mạnh hơn bất kỳ unit test nào cho tuyên bố
reproducibility của đề bài.

### 3.3. Dữ liệu nằm trong PostgreSQL thật

```sql
planbench=# select id, name, state, created_by from benchmarks order by created_at desc limit 2;
 7d777b82935a | docker-verify-dot-0-2   | accepted       | antongduy
 826fa43e5ee4 | docker-verify-benchmark | pending_review | antongduy

planbench=# select algorithm, seed, status from episodes where benchmark_id='7d777b82935a';
 astar+dwa    | 1..5 | success   (5 hàng)
 rrtstar+dwa  | 1..5 | success   (5 hàng)
```

Artifact trong volume của container `api`:

```
/data/artifacts/benchmarks/7d777b82935a/report.json
/data/artifacts/benchmarks/7d777b82935a/episodes/*.json   (10 file)
/data/artifacts/models/                                    (do bản sửa 2.1 tạo)
```

Leaderboard sau khi accept:

```
group 2c67300aa580c997 | map doorway | scenario doorway
  astar+dwa     episodes=5  success_rate=1.0  overall_score=0.99878
  rrtstar+dwa   episodes=5  success_rate=1.0  overall_score=0.99790
```

---

## 4. Quan sát cần báo, không giấu

1. **Tài liệu nói "chưa chạy Docker lần nào" là sai.** Volume
   `planbench_db-data` và `planbench_artifacts` được tạo **2026-08-02**
   và chứa sẵn 2 map (`docker-test-map`, `docker-verify-map`) cùng một
   benchmark `docker-verify-benchmark` với 6 episode. Tức đã có người
   chạy compose ngày 02/08 nhưng không cập nhật `IMPLEMENTATION_STATUS.md`
   / `KNOWN_LIMITATIONS.md`, và cả hai note ngày 04/08 đều chép lại câu
   sai đó. May là chính dữ liệu cũ này đã lộ ra lỗi 2.2 — chạy trên máy
   sạch sẽ **không** bắt được nó.

2. **`AUTH_SECRET` để rỗng nên mỗi lần rebuild `api` là đăng xuất toàn
   bộ.** Đã gặp thật trong lúc kiểm chứng: sau `docker compose up -d
   --build api`, token cũ trả `invalid token`. `docker-compose.yml` có
   cảnh báo sẵn, `.env.example` cũng nói, nhưng `.env` hiện tại vẫn để
   rỗng. **Chưa tự ý sửa `.env`** vì đó là file chứa khóa của user —
   khuyến nghị đặt trước buổi demo:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   Ghi ở KNOWN_LIMITATIONS #98.

3. **`/scenarios` trên web trả 404.** Không phải hồi quy — trang
   Scenario Editor thuộc **Đợt 2** của plan, chưa làm.

4. **Không chạy được `astar+ppo` từ image này**, đúng như
   `docker/requirements-api.txt` khai báo: torch/gymnasium/SB3 cố ý
   không nằm trong image API. Không phải lỗi, nhưng nghĩa là demo trong
   Docker chỉ có 2 stack benchmarkable — và nhờ Đợt 0.1 thì đó là 2
   stack **khác thuật toán global**, không phải một stack so với chính nó.

5. **`docker compose logs migrate` gần như không nói gì** (2 dòng, không
   có `Running upgrade`). Ai kiểm bằng cách đọc log sẽ không phân biệt
   được "đã chạy migration" với "không làm gì". Phải kiểm bằng `\dt`
   trên database. Chưa sửa — nếu muốn, nâng log level cho
   `alembic.runtime.migration` trong `alembic.ini`.

---

## 5. Thay đổi code

| File | Thay đổi | Vì sao |
|---|---|---|
| `apps/api/planbench_api/config.py` | `model_dir` mặc định rỗng + validator điền `<artifact_dir>/models` | Lỗi 2.1 — đường dẫn tương đối trôi độc lập với artifact root |
| `apps/api/planbench_api/approval.py` | `Role` giữ lại `ENGINEER`, `APPROVER` | Lỗi 2.2 — audit trail cũ phải đọc được, không ghi đè lịch sử |
| `tests/api/test_config.py` (mới) | 4 test: `model_dir` bám `artifact_dir`, giá trị tường minh vẫn thắng, mặc định dev không đổi | Chặn hồi quy lỗi 2.1 |
| `tests/test_approval.py` | `TestLegacyAuditRows` — 4 vai trò cũ parse được, vai trò chưa từng tồn tại vẫn bị từ chối | Chặn hồi quy lỗi 2.2 |

Không thêm dependency. Không đổi schema database. Không đổi
`conditions_checksum`.

**Vì sao hai lỗi này cần test dù đợt 0.2 là việc kiểm chứng:** cả hai
đều là lỗi mà 1120 test hiện có **không thể** bắt, vì test chạy trên
host với thư mục ghi được và database sạch. Test mới không mô phỏng
container — chúng khóa đúng cái bất biến đã bị vi phạm (`model_dir`
phải bám `artifact_dir`; enum vai trò chỉ được thêm, không được bớt),
nên chạy được trên mọi máy.

Kết quả chạy toàn bộ suite trên host sau khi sửa:

```
1129 passed, 4 skipped, 2 warnings in 581.57s
```

so với baseline sau Đợt 0.1 (`1120 passed, 4 skipped`) — **không có fail
mới**, +9 test là đúng số test hồi quy vừa thêm. `ruff check` và
`ruff format --check` sạch trên cả 4 file đụng tới.

## 6. Tài liệu đã cập nhật

- `docs/KNOWN_LIMITATIONS.md`: gỡ #92 (đã chạy PostgreSQL thật), thêm
  mục #98–#101 (`AUTH_SECRET`, vai trò legacy, đường dẫn tương đối trong
  container, volume sống lâu hơn `compose down`).
- `docs/IMPLEMENTATION_STATUS.md`: bỏ câu "chưa chạy Docker lần nào",
  ghi kết quả Đợt 0.2 và xác nhận thứ tự `migrate` → `api` hoạt động.

## 7. Definition of Done (mục 0.2 của plan)

- [x] Database healthy.
- [x] Migration hoàn thành — 10 bảng trên `postgres:17-alpine`.
- [x] API healthy.
- [x] Web truy cập được.
- [x] Benchmark chạy thành công trong container — 10 run, 2 stack.
- [x] Dữ liệu được lưu trên PostgreSQL — kiểm bằng `psql`.
- [x] Có báo cáo verify (file này).

## 8. Còn nợ, chuyển tiếp

1. **Đăng nhập bằng trình duyệt thật chưa làm.** Đã kiểm login qua API
   (form-encoded `POST /auth/login`) và mọi trang web trả 200, nhưng
   chưa click qua UI. Việc còn lại của mục "xem replay `rrtstar+dwa`
   bằng mắt" (nợ #2 của Đợt 0.1) — stack đã sẵn sàng, chỉ cần mở
   `http://localhost:3000`.
2. **Điều tra `astar+dwa` stuck ở `narrow_corridor`** — nợ #3 của Đợt
   0.1, chưa xử lý. Lần này chạy trên `doorway` nên chưa chạm tới.
3. **Log migration im lặng** (mục 4.5).
4. **`AUTH_SECRET`** cần user đặt trước demo (mục 4.2).

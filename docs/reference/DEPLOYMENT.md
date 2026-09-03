# Deployment (M10)

PostgreSQL persistence + Docker Compose. Đọc kèm `docs/KNOWN_LIMITATIONS.md`
mục 51–57 để biết phần nào **chưa** chạy thật trong môi trường này.

## Hai backend lưu trữ

| `PLANBENCH_DATABASE_URL` | Backend | Dùng khi |
|---|---|---|
| rỗng | in-memory | dev, test suite — mất hết khi restart |
| `postgresql://…` | SQL | production |
| `sqlite:///./planbench.db` | SQL | thử nhanh, **một process duy nhất** |

Cả hai trả về cùng `Stored*` dataclass và thoả cùng Protocol trong
`apps/api/planbench_api/repository_ports.py`, nên mọi thứ phía trên tầng
repository không biết cái nào đang chạy. Test `tests/api/test_sql_repositories.py`
chạy **cùng một assertion qua cả hai backend** để phân kỳ bị fail ngay
thay vì nằm im tới lúc deploy.

Giữ in-memory làm mặc định là có chủ đích: một checkout không có database
vẫn chạy được toàn bộ API và toàn bộ test, nên một database hỏng không
bao giờ giả dạng thành một regression không liên quan.

## Bảng

| Bảng | Nội dung |
|---|---|
| `maps` | `payload` JSON (nguồn sự thật là Pydantic model) + checksum, kích thước |
| `scenarios` | `payload` JSON; **không** FK tới maps |
| `simulations` | chạy đơn lẻ, `run` inline vì nhỏ |
| `benchmarks` | spec + report (metrics-only) + `conditions_checksum` denormalise |
| `approvals` | append-only, có `sequence` tường minh |
| `episodes` | **metadata + URI artifact**, không có trajectory |
| `robot_profiles` | tham số robot, để adapter PPO không hardcode chúng |
| `models` | bản ghi model: checksum, schema quan sát/hành động, chủ sở hữu, **khóa lưu trữ chứ không phải đường dẫn** |
| `model_documents` | `.json` metadata và `.pdf` tài liệu đính kèm |
| `model_usages` | benchmark nào đã dùng model nào, ở phiên bản và checksum nào |
| `conversations`, `conversation_messages` | hội thoại với trợ lý, kèm đề xuất benchmark |

**Vì sao `scenarios` không có FK tới `maps`:** scenario phải sống sót khi
map bị xoá, nếu không xoá một map sẽ âm thầm xoá luôn provenance của mọi
benchmark đã chạy trên nó.

**Vì sao timestamp là chuỗi ISO-8601 chứ không phải DATETIME:** API
contract trả chuỗi ISO, và backend in-memory lưu đúng thứ nó trả. Dùng
timestamp native sẽ phát sinh round-trip định dạng (`+00:00` vs `Z`, cắt
microsecond) khiến hai backend bất đồng ở một giá trị client nhìn thấy
được. ISO-8601 UTC sắp xếp theo thứ tự từ điển trùng với thứ tự thời
gian nên `ORDER BY created_at` vẫn đúng.

**Payload lớn không nằm trong database** (quyết định D15). Trajectory và
report ra artifact store; row chỉ giữ URI + checksum + size. Hệ quả thật:
`SqlEpisodeRepository` **đọc lại artifact** để dựng `StackRun` khi replay.
Mất volume artifact = mất replay, dù database còn nguyên.

## Migration

Alembic, **không** tạo schema lúc khởi động.

```bash
export PLANBENCH_DATABASE_URL=postgresql://user:pass@host:5432/planbench
.venv/bin/alembic upgrade head       # áp dụng
.venv/bin/alembic downgrade -1       # lùi một bước
.venv/bin/alembic upgrade head --sql # in SQL, không chạy (cho DBA)
```

`alembic.ini` **không chứa connection string** — `env.py` chỉ đọc
`PLANBENCH_DATABASE_URL`, nên mật khẩu không bao giờ nằm trong file được
track.

Migration đầu tiên viết tay chứ không autogenerate, vì đó là file người
ta đọc để hiểu schema. `tests/api/test_migrations.py` so từng bảng, từng
cột, nullability, primary key, cascade và index giữa migration và ORM —
hai thứ viết riêng nên chúng **sẽ** trôi nếu không ai kiểm.

Migration mới:

```bash
PLANBENCH_DATABASE_URL=... .venv/bin/alembic revision --autogenerate -m "add x"
# LUÔN đọc lại file sinh ra: autogenerate bỏ sót đổi tên (nó thấy
# drop + add) và không suy được data migration.
```

## Docker Compose

```bash
cp .env.example .env        # ít nhất phải đặt PLANBENCH_JWT_SECRET
docker compose up --build
# API  http://localhost:8000/docs
# Web  http://localhost:3000
```

Bốn service:

| Service | Vai trò |
|---|---|
| `db` | PostgreSQL 17, volume `db-data`, healthcheck `pg_isready -U <user>` |
| `migrate` | one-shot `alembic upgrade head`, phải exit 0 |
| `api` | uvicorn, chờ `db` **healthy** và `migrate` **completed** |
| `web` | Next.js standalone |

**Vì sao migrate là service riêng:** hai replica API cùng chạy
`upgrade head` lúc boot là một race. Một job phải exit 0 trước khi API
khởi động thì không.

### Chạy song song với dev stack

Cổng 8000 và 3000 thường đã bị `scripts/dev_stack.sh` chiếm. Đổi cổng
qua biến môi trường thay vì tắt dev stack — cách này đã dùng để kiểm
chứng lần đầu:

```bash
API_PORT=8001 WEB_PORT=3001 \
NEXT_PUBLIC_API_URL=http://localhost:8001 \
PLANBENCH_API_PUBLIC_URL=http://localhost:8001 \
PLANBENCH_WEB_APP_URL=http://localhost:3001 \
PLANBENCH_CORS_ORIGINS='["http://localhost:3001"]' \
docker compose up -d
```

Bốn biến URL phải đổi cùng nhau. `NEXT_PUBLIC_API_URL` được nướng vào
bundle lúc build nên trình duyệt gọi đúng địa chỉ đó; `CORS_ORIGINS`
phải khớp cổng web, nếu không mọi request từ trình duyệt bị chặn.

### Kiểm tra và dọn

```bash
docker compose ps                      # trạng thái từng container
docker compose logs api --tail 50      # log khi API không lên
docker compose exec db psql -U planbench -d planbench -c "\dt"

docker compose down                    # dừng, GIỮ dữ liệu
docker compose down -v                 # dừng và XOÁ luôn volume
```

`down -v` xoá cả `db-data` lẫn `artifacts` — mất toàn bộ benchmark đã
chạy. Chỉ dùng khi thật sự muốn bắt đầu lại từ đầu.

**Vì sao chờ `service_healthy` chứ không phải `service_started`:**
Postgres chỉ nhận kết nối sau khi init script xong; `depends_on` không có
điều kiện health sẽ đua với việc đó.

**`pg_isready -U <user>` chứ không phải `pg_isready` trần:** không có
`-U` nó kiểm tra user root và có thể báo ready trước khi role ứng dụng
tồn tại.

**`NEXT_PUBLIC_API_URL` là build arg, không phải env runtime.** Next
inline biến `NEXT_PUBLIC_*` vào bundle client lúc build, nên đây là URL
**trình duyệt** gọi — `http://api:8000` chỉ phân giải được bên trong
compose network và sẽ hỏng trên máy người dùng.

**Port 5432 không publish mặc định.** Không có gì ngoài compose network
cần nó, và một database lộ ra ngoài với mật khẩu mặc định là một trách
nhiệm pháp lý.

**API image không có torch/stable-baselines3.** Training là workload
riêng; kéo torch vào image API thêm vài GB cho code API không bao giờ
chạy. Hệ quả: **stack `astar+ppo` không chạy được từ image này.**

## Biến môi trường

Xem `.env.example` cho danh sách đầy đủ. Bắt buộc cho production:

| Biến | Vì sao bắt buộc |
|---|---|
| `AUTH_SECRET` | Ký JWT và cookie state OAuth. Rỗng ⇒ sinh ngẫu nhiên mỗi process ⇒ mọi token chết khi restart |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Không có ⇒ không có nút "Continue with Google" |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | Không có ⇒ không có nút "Continue with GitHub" |
| `PLANBENCH_API_PUBLIC_URL` | Callback URL được suy ra từ đây. Sai ⇒ provider từ chối redirect_uri |
| `PLANBENCH_WEB_APP_URL` | Nơi browser được đưa về sau khi đăng nhập |
| `PLANBENCH_DATABASE_URL` | Rỗng ⇒ in-memory ⇒ mất dữ liệu khi restart |
| `POSTGRES_PASSWORD` | Mặc định `planbench` chỉ dùng cho local |

Callback URL phải đăng ký với provider, và nó **được suy ra** từ
`PLANBENCH_API_PUBLIC_URL` chứ không cấu hình riêng — hai nguồn sự thật
là nguyên nhân số một khiến OAuth hỏng:

```
{PLANBENCH_API_PUBLIC_URL}/api/v1/auth/oauth/google/callback
{PLANBENCH_API_PUBLIC_URL}/api/v1/auth/oauth/github/callback
```

**Không bật `PLANBENCH_ENABLE_DEV_LOGIN` trong production.** Mặc định là
`false`; khi tắt, endpoint `/auth/login` từ chối và tài khoản password
thậm chí không được tạo.

`PLANBENCH_JWT_SECRET` là tên cũ của `AUTH_SECRET`, vẫn được đọc khi
`AUTH_SECRET` rỗng, để deployment sẵn có không gãy.

Admin cấp qua `PLANBENCH_ADMIN_NICKNAMES` / `PLANBENCH_ADMIN_EMAILS`
(email chỉ tính khi provider đã xác minh). Admin được can thiệp vào
review đang chờ — mọi hành động đều vào audit trail kèm user ID, nên
đừng đưa member thường vào danh sách này.

Key LLM đọc từ biến của chính nhà cung cấp (`ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, …), không phải setting PlanBench. Thiếu key ⇒ agent
rơi về mock tất định chứ không hỏng.

## Model storage

Model upload đi cùng đường lối với artifact (quyết định D15): database
giữ khóa lưu trữ + SHA-256 + kích thước, byte nằm ngoài database.

```
$PLANBENCH_MODEL_DIR/<user_id>/<model_id>/<version>/<tên-file-đã-làm-sạch>
```

Đường dẫn **dựng hoàn toàn từ ID**. Tên file người dùng gửi lên chỉ để
hiển thị lại; nó không quyết định vị trí nào cả, nên `../../etc/passwd`
không đi tới đâu — và lớp lưu trữ vẫn `resolve()` rồi kiểm tra kết quả
có nằm trong thư mục gốc không, vì một phòng tuyến không đủ.

Thư mục này **nằm ngoài source tree, ngoài `.next`, và `artifacts/` đã
có trong `.gitignore`** — một file upload không thể lọt vào repository.

Chuyển sang S3/R2 là cài đặt thêm một lớp `ModelStorage`
(`save/open/exists/delete/checksum/internal_location`), không phải sửa
nơi gọi. Bản cục bộ là bản duy nhất đã chạy thật.

**Giới hạn bảo mật quan trọng:** khi benchmark PPO chạy, checkpoint được
giải tuần tự trong tiến trình worker — không phải trong sandbox có
quota. Tiến trình API không bao giờ giải tuần tự file người dùng, nhưng
đó là ranh giới tiến trình chứ chưa phải ranh giới cách ly. Xem
KNOWN_LIMITATIONS #77 trước khi mở upload cho người dùng không tin cậy.

## Render free + Neon — bản web demo công khai

> Khảo sát và lý do chọn:
> `docs/journal/antongduy/notes/2026-09-03/tongduyan_khao-sat-deploy-web-mien-phi.md`.
> IaC: [`render.yaml`](../../render.yaml) ở gốc repo — deploy tái lập từ
> git, không phải bấm tay trên dashboard như bản `planbench-web` cũ.

**Bản này để làm gì:** cho người có link *đọc* sản phẩm — decision,
Decision Card, tầng giải thích, replay đã seed. **Không phải** nơi chạy
phép so mới: free instance chia 0.1 vCPU, ngủ sau 15 phút idle, không
disk bền. Số đo từ máy này không có giá trị bằng chứng (HĐ-7.4 pin core
là có lý do). Nơi chạy thật vẫn là desktop app hoặc compose trên VPS.

### Dựng lần đầu

1. **Neon** (neon.tech, free tier): tạo project, lấy connection string
   dạng `postgresql://…?sslmode=require`. `db/session.py` tự đổi scheme
   sang `postgresql+psycopg://`, không phải sửa gì.
2. **Render**: New → Blueprint, trỏ vào repo `origin`. Render đọc
   `render.yaml`, tạo hai service free: `planbench-api`,
   `planbench-web`. Nếu tên đã bị bản cũ chiếm — xoá/đổi tên service cũ
   trước, vì bốn biến URL trong `render.yaml` viết theo đúng hai tên này.
3. Dashboard hỏi hai biến `sync: false` — điền thẳng vào ô, **không dán
   vào chat hay commit**:
   - `PLANBENCH_DATABASE_URL` — connection string Neon;
   - `PLANBENCH_SEED_USERS` — `nickname:roles:password`, phân cách bằng
     `,`; nickname `admin` khớp `PLANBENCH_DEMO_OWNER_NICKNAME` để tài
     khoản đó nhận `demo_owner` lần đăng nhập đầu (xem
     [DEMO-PROFILE.md](./DEMO-PROFILE.md)).
4. Deploy xong, mở `https://planbench-web.onrender.com` — lần đầu trong
   ngày chờ cold start ~1 phút. **Tự mở trước khi gửi link cho ai.**

### Đổi domain = đổi 4 biến

Cùng một lần, không sót cái nào — thiếu một là "app lên mà không đăng
nhập được / không gọi API được":

| Biến | Ở đâu | Vai trò |
|---|---|---|
| `PLANBENCH_API_PUBLIC_URL` | api | suy ra OAuth callback |
| `PLANBENCH_WEB_APP_URL` | api | nơi browser về sau đăng nhập |
| `PLANBENCH_CORS_ORIGINS` | api | JSON list, phải chứa origin web |
| `NEXT_PUBLIC_API_URL` | web | **build arg** — đổi là rebuild image, không phải restart |

### Khác gì compose, và vì sao

- **Migration chạy trong start command** (`alembic upgrade head &&
  uvicorn …`), không phải service `migrate` riêng. Lý do compose tách
  (hai replica cùng upgrade là race) không áp ở đây: free = đúng một
  replica, còn pre-deploy command của Render là tính năng trả phí. Lên
  paid + nhiều instance thì chuyển sang `preDeployCommand` **trước khi**
  scale.
- **Không có volume artifact.** `PLANBENCH_ARTIFACT_DIR=/data/artifacts`
  là disk ephemeral — mọi restart/redeploy mồ côi replay đã ghi (URI
  `file://` còn trong DB, file mất). Chấp nhận cho demo; dữ liệu trưng
  bày phải seed lại được.
- **Không đặt key LLM** (`OPENAI_API_KEY`, …). Subprocess lane của
  plugin kế thừa nguyên env (không phải sandbox — xem
  `plugin_import_security.md`), demo owner lại cầm admin, nên key nào
  đặt lên đây coi như đọc được từ plugin import. Không key ⇒ mock
  advisor tất định, degrade có báo.
- **Neon thay Postgres của Render** vì free Postgres của Render hết hạn
  sau 30 ngày; Neon free 0.5 GB không hết hạn (autosuspend khi idle,
  connect đầu tiên đánh thức — cộng thêm vào cold start).

## Backup

Ba thứ phải backup **cùng nhau**, và đây là điểm dễ sai nhất:

1. **Database** — `pg_dump`
2. **Artifact store** — thư mục/volume `PLANBENCH_ARTIFACT_DIR`
3. **Model store** — thư mục/volume `PLANBENCH_MODEL_DIR`

Mất model store mà còn database sẽ cho một registry đầy bản ghi mà mọi
lần chạy đều báo thiếu file — checksum vẫn khớp với thứ không còn tồn
tại.

Restore lệch nhau sẽ cho một database đầy episode mà replay nào cũng
`404 episode artifact`. Artifact được tham chiếu bằng URI tuyệt đối
(`file:///data/artifacts/...`), nên **đổi đường dẫn artifact sẽ làm hỏng
URI đã lưu** — xem KNOWN_LIMITATIONS mục 55.

```bash
docker compose exec db pg_dump -U planbench planbench > backup.sql
docker run --rm -v planbench_artifacts:/a -v "$PWD":/b alpine \
  tar czf /b/artifacts.tar.gz -C /a .
```

## Cài local (không dùng Docker)

```bash
.venv/bin/pip install "psycopg[binary]"      # cần cho postgresql://
export PLANBENCH_DATABASE_URL=postgresql://user:pass@localhost:5432/planbench
.venv/bin/alembic upgrade head
PYTHONPATH="packages/schemas:packages/planning:packages/metrics:\
packages/benchmark:services/simulator:services/tracking:\
services/agent_service:ml:apps/api" \
  .venv/bin/uvicorn planbench_api.main:app --port 8000
```

Thiếu `psycopg` thì `create_db_engine` báo `DatabaseUnavailable` kèm đúng
lệnh cài, chứ không phải `ModuleNotFoundError` trần.

## Chưa kiểm chứng

Nói thẳng, vì đây là những thứ chỉ lộ ra khi chạy thật.

**Đã kiểm chứng 2026-08-03** (chi tiết ở [TEST_REPORT.md](./TEST_REPORT.md)):

- Image build được; `docker compose up` chạy cả `db`, `migrate`, `api`,
  `web`.
- Migration 0001–0003 chạy trên **PostgreSQL 17** (`PostgresqlImpl`,
  16 bảng, `alembic_version = 0003`).
- Dữ liệu sống sót khi **xóa hẳn container API** rồi tạo lại.

Lần chạy đầu tiên bắt được một lỗi mà không test nào phát hiện được:
`PLANBENCH_MODEL_DIR` mặc định là đường dẫn tương đối, giải ra
`/app/artifacts` trong container — thư mục của root, còn tiến trình chạy
bằng user `planbench`. API chết lúc khởi động với `PermissionError`. Đã
sửa bằng cách khai `PLANBENCH_MODEL_DIR: /data/artifacts/models`.

**Vẫn chưa kiểm chứng:**

- **Chưa chạy nhiều người dùng đồng thời** trên PostgreSQL. Transaction
  tranh chấp và connection pool dưới tải thật vẫn là ẩn số.
- **Chưa triển khai lên máy chủ thật** — mới chạy Docker cục bộ, chưa qua
  reverse proxy, TLS hay tên miền.
- **`psycopg` chưa cài trong `.venv`.** Không cần: image đã có nó, và
  phát triển cục bộ dùng SQLite. Chỉ cần khi muốn trỏ `.venv` thẳng vào
  PostgreSQL:

  ```bash
  .venv/bin/pip install "psycopg[binary]==3.2.10"
  ```

Việc đầu tiên khi có Docker: `docker compose up --build`, rồi chạy
`scripts/demo_agent_flow.py` trỏ vào API trong container để kiểm chứng
end-to-end trên PostgreSQL thật.

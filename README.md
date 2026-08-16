# Agentic AI PlanBench

Nền tảng mô phỏng và benchmark path/motion planning cho robot di động
AMR/AGV. Hệ thống cho phép so sánh công bằng các thuật toán điều hướng
(A*, DWA, PPO, Nav2, ...) trên cùng map, scenario, seed và metric, với
quy trình phê duyệt human-in-the-loop.

**Chỉ dùng cho mô phỏng — không điều khiển robot thật. Không dùng Gazebo.**

## Chạy nhanh

**Cả stack** (API + web UI) — Linux, WSL, macOS, hoặc Git Bash trên Windows:

```bash
./scripts/dev_stack.sh start      # http://localhost:3000
./scripts/dev_stack.sh stop
./scripts/dev_stack.sh status
./scripts/dev_stack.sh logs
```

Script tự chạy `alembic upgrade head` trước khi khởi động API và in ra
phương thức đăng nhập nào đang bật. Migration lỗi thì nó dừng và báo rõ,
không khởi động API với schema cũ.

**Chỉ API** — mọi nền tảng, kể cả Windows thuần (PowerShell, cmd):

```
.venv\Scripts\python.exe scripts\serve.py --reload --migrate
```

**Đừng gọi thẳng `python -m uvicorn planbench_api.main:app`.** Dự án
không được cài đặt, nên mọi package dưới `packages/` và `services/` chỉ
vào `sys.path` khi có thứ gì đó đặt chúng vào. Lệnh uvicorn trần hỏng
ngay ở gói đầu tiên (`planbench_api`), và sửa tay từng cái sẽ dẫn qua
mười traceback liên tiếp. `serve.py` đọc danh sách đường dẫn từ
`pyproject.toml` — cùng một danh sách pytest dùng — rồi mới khởi động.

> Trước 2026-08-12 mục này bảo Windows nháy đúp `start.bat`. File đó bị
> xoá nhầm ở commit `3c04cf2` và, ngay cả khi còn, nó chỉ forward sang
> WSL bằng một đường dẫn cứng trỏ vào thư mục nhà của một máy khác. Tức
> Windows thuần **chưa bao giờ** có đường chạy dùng được.

### Lưu dữ liệu

Mặc định dữ liệu **được lưu vào SQLite** (`planbench.db` ở gốc repo), nên
map, scenario, benchmark và tài khoản sống sót qua lần khởi động lại.

Có một cái bẫy đáng biết: trong `.env`, viết `PLANBENCH_DATABASE_URL=`
với vế phải để trống **không giống** việc bỏ hẳn dòng đó. Vế trái đặt
biến thành chuỗi rỗng, và chuỗi rỗng chọn backend trong bộ nhớ — tắt
server là mất sạch, không migration nào chạy.

- **Muốn lưu:** để dòng đó ở dạng chú thích, hoặc ghi rõ
  `PLANBENCH_DATABASE_URL=sqlite:///./planbench.db`
- **Cố tình không lưu** (chạy thử rồi bỏ): đặt nó bằng rỗng

Lúc khởi động, script in ra chế độ đang dùng. Thấy dòng
`! database in-memory` nghĩa là dữ liệu sẽ không được giữ lại.

Hai thứ phải backup **cùng nhau**: `planbench.db` và thư mục
`artifacts/`. Trajectory với report nằm ngoài database (quyết định D15),
bảng chỉ giữ URI và checksum — mất thư mục artifact thì database còn
nguyên nhưng mọi lần phát lại đều báo thiếu file.

### Đăng nhập

Copy `.env.example` sang `.env` rồi điền **đúng năm biến** này:

```
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
AUTH_SECRET=
```

Callback URL cần đăng ký với provider (copy nguyên văn):

| Provider | Callback URL |
|---|---|
| Google — [console](https://console.cloud.google.com/apis/credentials) | `http://localhost:8000/api/v1/auth/oauth/google/callback` |
| GitHub — [settings](https://github.com/settings/developers) | `http://localhost:8000/api/v1/auth/oauth/github/callback` |

Sinh `AUTH_SECRET`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Điền xong chỉ cần khởi động lại stack — không sửa code, không lệnh phụ.

Bỏ trống Google hoặc GitHub cũng được: nút đó không hiện, phần còn lại
vẫn chạy. Bỏ trống cả hai cũng được — đặt
`PLANBENCH_ENABLE_DEV_LOGIN=true` để dùng đăng nhập username/password
cho phát triển cục bộ (mặc định tắt, không dùng cho production).

Lần đăng nhập đầu tiên sẽ hỏi **nickname** (3–30 ký tự, chữ/số/`_`/`-`).
Nickname là cách người khác gửi review cho bạn — không phải khóa phân
quyền, phân quyền luôn dựa trên user ID.

### Giao diện

Thanh bên thu gọn được (nhớ trạng thái), và thành drawer trên màn hình
nhỏ. Trên top bar có nút đổi **ngôn ngữ** (Tiếng Việt / English) và
**giao diện** (Sáng / Tối / Theo hệ thống) — cả hai đều được nhớ, và đổi
theme không bị nháy sai màu lúc tải trang.

Thông tin kỹ thuật (phiên bản, địa chỉ API) nằm ở trang **Thông tin hệ
thống**, không nằm trên Dashboard; địa chỉ API chỉ hiện khi chạy
development.

### Quy trình

Một người làm được toàn bộ việc của mình: tạo map/scenario/benchmark →
**Run** → **Accept results** → lên leaderboard. Không cần tài khoản thứ
hai, không cần đổi tài khoản.

Review là **tùy chọn**. Bấm *Send for review*, nhập nickname người khác,
chọn *spec* (trước khi chạy) hoặc *result* (sau khi chạy). Khi đang chờ,
chính chủ **không** tự duyệt được — đó là toàn bộ ý nghĩa của việc nhờ
review. Có thể hủy yêu cầu bất cứ lúc nào.

Ba thứ chạy ở chế độ giảm cho tới khi được cấu hình, không phải lỗi:

| Mặc định | Hệ quả | Bật đầy đủ |
|---|---|---|
| Chưa cấu hình OAuth | trang login báo rõ, không có nút | điền 5 biến ở trên |
| Agent dùng mock tất định | trả lời bằng khớp từ khóa, không phải model | dán API key, xem `.env.example` |
| Chưa có model PPO đã train | stack `astar+ppo` không chạy được | tải model `.zip` lên qua trang **Kho mô hình** |

## Trạng thái

**M0–M13 đã hoàn thành.** Chi tiết:
[docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) ·
kết quả chạy thật: [docs/TEST_REPORT.md](docs/TEST_REPORT.md) ·
**điều chưa kiểm chứng**: [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)

| Thành phần | Trạng thái |
|---|---|
| Schemas, occupancy grid, kinematics, collision, LiDAR | ✅ |
| A*, DWA, pure-pursuit (adapter tham chiếu), SimulationEngine, metrics | ✅ |
| Benchmark engine + fairness checksum + human-in-the-loop | ✅ |
| FastAPI (91 endpoint), WebSocket, background worker | ✅ |
| Next.js UI: map editor, 2.5D, leaderboard, failure analysis, agent console | ✅ |
| Vật cản động, thư viện 10 scenario, MLflow | ✅ |
| PPO (Gymnasium + SB3) | ✅ pipeline — chỉ có smoke model, chưa train thật |
| ROS2 Jazzy + Nav2 closed-loop | ✅ 6/6 episode, chạy tay |
| Agentic AI + RAG, 8 LLM provider | ✅ — chưa gọi provider ngoài lần nào |
| PostgreSQL + Alembic + Docker Compose | ✅ — đã build image và chạy thật, migration verify trên PostgreSQL 17 |
| Đăng nhập Google/GitHub, nickname, review tùy chọn | ✅ — không gọi OAuth thật trong test |
| App shell: sidebar thu gọn, theme Light/Dark/System, VI/EN | ✅ |
| **Model Registry**: upload PPO qua web, checksum, tương thích | ✅ — **nạp model chưa chạy trong sandbox**, xem KNOWN_LIMITATIONS #77 |
| **Robot Profile** | ✅ |
| **Trợ lý hội thoại** (đề xuất → bản nháp, không tự chạy) | ✅ |

Xem [docs/architecture.md](docs/architecture.md) cho kiến trúc và các
quyết định thiết kế.

## Yêu cầu môi trường

- Python 3.12, Node.js 20+

Kiểm tra nhanh:

```bash
python3 --version   # cần >= 3.12
node --version      # cần >= 20
npm --version
```

Trên Windows có hai lối, và **cả hai đều chạy được**:

- **WSL hoặc Git Bash** — gõ nguyên văn các lệnh `bash` dưới đây, kể cả
  `./scripts/dev_stack.sh`.
- **PowerShell / cmd thuần** — thay `.venv/bin/<x>` bằng
  `.venv\Scripts\<x>.exe`, và dùng `scripts/serve.py` thay cho
  `dev_stack.sh` (script đó là bash). Test và ruff chạy bình thường:
  `.venv\Scripts\python.exe -m pytest tests/`.

## Cài đặt

Từ đầu, sau khi `git clone`:

```bash
cd P-011           # tên thư mục bạn vừa clone về

# 1. Python
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 2. Frontend
cd apps/web && npm install && cd ../..

# 3. Cấu hình (tùy chọn — bỏ qua cũng chạy được)
cp .env.example .env
```

Xong. Chạy dự án:

```bash
./scripts/dev_stack.sh start      # Linux / WSL / macOS / Git Bash
```

hoặc, nếu chỉ cần API và đang ở Windows thuần:

```
.venv\Scripts\python.exe scripts\serve.py --migrate
```

Cả hai đều chạy `alembic upgrade head` trước khi khởi động API — script
thì tự động, `serve.py` thì khi có cờ `--migrate`.

### Để đăng nhập được ngay lần đầu

Clone sạch, chưa có `.env`, thì **chưa có cách đăng nhập nào** — trang
login sẽ nói thẳng như vậy chứ không hỏng. Chọn một trong hai:

**Cách nhanh (chỉ để phát triển cục bộ):** mở `.env` và đặt

```
PLANBENCH_ENABLE_DEV_LOGIN=true
```

Khởi động lại. Script in ra một tài khoản `developer` kèm mật khẩu sinh
ngẫu nhiên. Muốn cố định tài khoản thì thêm:

```
PLANBENCH_SEED_USERS=alice:mat-khau-cua-ban,bob:mat-khau-khac
```

**Cách thật:** điền 5 biến OAuth ở mục [Đăng nhập](#đăng-nhập) phía trên.

`PLANBENCH_ENABLE_DEV_LOGIN` mặc định `false` và **không được bật trong
production** — khi tắt, endpoint đăng nhập bằng mật khẩu từ chối và tài
khoản mật khẩu thậm chí không được tạo.

### Ba file dependency, dùng cái nào

| File | Dùng khi |
|---|---|
| **`requirements.txt`** | **Mặc định.** Clone về là cài cái này. Đủ để chạy API, simulator, benchmark, đăng nhập, SQLite, trợ lý AI ở chế độ mock, và **toàn bộ test suite**. |
| `requirements-optional.txt` | Khi cần PostgreSQL, MLflow, PPO/RL, hoặc LLM thật. Đọc file — nó hướng dẫn cài **từng nhóm**, đừng cài cả file (nhóm PPO nặng vài GB). |
| `docker/requirements-api.txt` | Chỉ dành cho image Docker của API. Không có công cụ test, không có gì thừa. Bạn không cần đụng tới nó khi làm việc cục bộ. |

Bốn thứ **cố tình** không nằm trong `requirements.txt`, vì thiếu chúng
thì tính năng giảm chế độ có kiểm soát và **báo rõ**, chứ không crash:

| Thiếu | Chuyện gì xảy ra |
|---|---|
| `psycopg` | Local dùng SQLite (driver có sẵn trong Python). Chỉ cần khi trỏ `PLANBENCH_DATABASE_URL` vào PostgreSQL — thiếu thì API dừng lúc khởi động và nói rõ phải cài gì. |
| `mlflow` | Không đặt `PLANBENCH_MLFLOW_TRACKING_URI` thì dùng null tracker. Benchmark vẫn chạy và vẫn ghi đủ kết quả. |
| `torch` + `gymnasium` + `stable-baselines3` | Stack `astar+ppo` không chạy được; mọi stack khác bình thường. `tests/test_rl.py` tự **skip**. |
| `openai` / `anthropic` | Trợ lý AI chạy bằng provider mock tất định — offline, khớp từ khóa — và **giao diện nói rõ điều đó** thay vì giả vờ là model viết. |

### Sau mỗi lần `git pull`: cài lại dependency

```bash
.venv/bin/pip install -r requirements.txt     # Windows: .venv\Scripts\pip
```

Rẻ khi không có gì mới (pip bỏ qua những gói đã đúng phiên bản) và cần
thiết khi có. Bỏ bước này thì triệu chứng đến **muộn và ở chỗ khác**:

```
ModuleNotFoundError: No module named 'pyarrow'
```

Đã xảy ra thật (12-08). `pyarrow` và `jsonschema` được thêm vào
`requirements.txt` ở commit `fa9df8a`; `.venv` dựng trước đó không có
chúng, và mọi test đụng tới Parquet trace đỏ — trong khi `requirements.txt`
hoàn toàn đúng. Không phải xung đột môi trường, chỉ là một môi trường cũ.

**Kiểm nhanh `.venv` có khớp không:**

```bash
.venv/bin/pip install --dry-run -r requirements.txt | grep -i "would install"
```

Không in gì nghĩa là khớp.

**Và luôn gọi Python qua đường dẫn trong `.venv`.** Máy có sẵn một Python
khác (conda base, Python hệ thống) là chuyện thường, và cái đó có thể
tình cờ đủ gói để test xanh — nên `pytest` gõ trần có thể **xanh trên
một môi trường không phải môi trường của dự án**. Đó là cách một thiếu
hụt thật nằm im nhiều ngày.

### Không có mạng khi cài?

`pip install` và `npm install` đều cần mạng ở lần đầu. Sau đó dự án chạy
hoàn toàn offline: mock provider không gọi mạng, SQLite là file cục bộ,
và OAuth chỉ cần mạng khi bạn thật sự bấm đăng nhập.

## Chạy kiểm thử

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
PYTHONPATH= .venv/bin/pytest tests/ -v \
  --cov=planbench_schemas \
  --cov=planbench_simulator \
  --cov-report=term-missing
```

Lưu ý `PYTHONPATH=`: nếu shell đã source ROS2 (ví dụ trong
`~/.bashrc`), `PYTHONPATH` chứa `/opt/ros/...` khiến pytest tự nạp
plugin `launch_testing` của ROS và lỗi import. Xóa `PYTHONPATH` khi
chạy test giữ cho `.venv` được cô lập; điều này không ảnh hưởng tới
các giai đoạn ROS2 sau (chúng chạy trong môi trường ROS riêng).

Ghi chú: ở giai đoạn này các package được import trực tiếp từ source
qua cấu hình `pythonpath` của pytest (xem `pyproject.toml`), chưa cần
`pip install -e`.

Frontend:

```bash
cd apps/web
npx tsc --noEmit     # type-check
npx vitest run       # unit test
npx next build       # build production
```

Nếu chỉ cài `requirements.txt`, `tests/test_rl.py` sẽ hiện **skipped** —
đúng như thiết kế, vì nó cần nhóm PPO trong `requirements-optional.txt`.
Mọi test còn lại vẫn chạy.

## Biến môi trường

Sao `.env.example` sang `.env` rồi điền. **Bỏ trống hết vẫn chạy được** —
mỗi tính năng thiếu key sẽ giảm chế độ có báo, không crash.

| Biến | Bắt buộc? | Để làm gì |
|---|---|---|
| `PLANBENCH_ENABLE_DEV_LOGIN` | nên bật khi dev | `true` thì trang đăng nhập có form user/mật khẩu, không cần OAuth |
| `PLANBENCH_SEED_USERS` | đi kèm cái trên | `tên:mật_khẩu`, phân cách bằng dấu phẩy |
| `AUTH_SECRET` | nên có | Ký token. Bỏ trống thì mỗi lần khởi động lại sinh secret mới, mọi người bị đăng xuất |
| `PLANBENCH_AGENT_PROVIDER` | không | `auto` (mặc định), `gemini`, `anthropic`, `openai`, `mock`… |
| `PLANBENCH_AGENT_MODEL` | **có, nếu dùng LLM** | Tên model. `auto` **bỏ qua** provider không có tên model — đây là lỗi hay gặp nhất |
| `GEMINI_API_KEY` | nếu dùng Gemini | Key từ Google AI Studio |
| `ANTHROPIC_API_KEY` | nếu dùng Claude | Provider này có model mặc định nên không cần `AGENT_MODEL` |
| `PLANBENCH_DATABASE_URL` | không | Bỏ trống dùng SQLite cạnh repo. Ghi `=` rỗng thì thành in-memory, mất hết khi tắt |
| `GOOGLE_CLIENT_ID` / `_SECRET` | không | Đăng nhập Google. Bỏ trống thì nút đó không hiện |

Cấu hình LLM tối thiểu để chạy Gemini:

```bash
PLANBENCH_AGENT_PROVIDER=auto
PLANBENCH_AGENT_MODEL=gemini-3-flash-preview
GEMINI_API_KEY=<key cua ban>
```

Kiểm tra provider có dùng được không **trước khi** chạy cả stack:

```bash
set -a; source .env; set +a
PYTHONPATH="services/agent_service:packages/schemas:packages/planning:packages/metrics:packages/benchmark:packages/decision:services/simulator:apps/api:." \
  .venv/bin/python scripts/check_agent_provider.py
```

Nó in bảng provider nào sẵn sàng, còn thiếu gì, rồi gọi thật một request
và thử structured output. `Determinist: False` nghĩa là đang chạy model
thật; `True` nghĩa là đang rơi về mock tất định.

## Thử nhanh

### Phản biện một phép so (không cần LLM, ~2 giây)

Bộ luật chất vấn một kết quả đã lưu trước khi người ký duyệt:

```bash
PYTHONPATH="packages/decision:packages/schemas" .venv/bin/python -c "
import json, glob
from planbench_decision.self_check import critique
for f in sorted(glob.glob('artifacts/runs/*/*/comparison_report.json')):
    findings = critique(json.load(open(f)))
    print(f'{f.split(\"/\")[-2][:44]:<46} {len(findings)} finding')
    for x in findings:
        print(f'   [{x.severity:<10}] {x.code}')
"
```

### Phản biện có LLM (~30 giây)

```bash
set -a; source .env; set +a
PYTHONPATH="services/agent_service:packages/decision:packages/schemas:packages/benchmark:packages/planning:packages/metrics:services/simulator:apps/api:." \
.venv/bin/python -c "
import json, glob
from planbench_agent.critique import critique_with_model
from planbench_agent.factory import build_provider
from planbench_api.config import get_settings
s = get_settings()
p = build_provider(s.agent_provider, model=s.agent_model or None)
f = [x for x in glob.glob('artifacts/runs/*/*/comparison_report.json') if 'warehouse' in x][0]
r = critique_with_model(json.load(open(f)), p)
print(p.name, p.model)
print(r.summary)
print('fabricated:', r.fabricated)
" 2>&1 | grep -v '^{'
```

`fabricated: 0` nghĩa là model không trỏ vào trường nào không tồn tại.

### Qua giao diện

1. `bash scripts/dev_stack.sh start`
2. Mở `http://localhost:3000`, đăng nhập
3. **Deployment** → khai một thế giới, hoặc dùng cái có sẵn
4. **Quyết định** → chạy phép so hai ứng viên
5. Mở kết quả → mục **Phản biện** → bấm *Kiểm bằng luật*, rồi *Hỏi thêm model*

### Qua API

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/decisions/<run_id>/critique"

curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/decisions/<run_id>/critique?use_model=true"
```

Hoặc mở `http://localhost:8000/docs`, bấm **Authorize**, rồi thử trực tiếp.

## Cấu trúc thư mục

```
packages/            schemas, planning (A*/DWA), metrics, benchmark  — thư viện Python thuần
services/simulator/  SimulationEngine, LiDAR, collision, nav_stack
services/tracking/   MLflow adapter + null tracker
services/agent_service/  Agentic AI: provider abstraction, tools, evidence, RAG
apps/api/            FastAPI (thin adapter over the core) + db/ (SQLAlchemy)
apps/web/            Next.js 15 + React 19
ml/                  Gymnasium env, reward, PPO training
ros2_ws/             5 ROS2 package (simulator node, Nav2 bringup, runner)
alembic/             Migration schema
docker/              Image API + web
tests/               pytest — xem docs/TEST_REPORT.md cho số đã chạy thật
scripts/             demo, kiểm tra provider, dev_stack.sh
docs/                architecture, API contract, deployment, frontend, agent, ROS2
```

## Quy ước cốt lõi

- Đơn vị SI: mét, giây, radian; góc chuẩn hóa trong **(-π, π]**.
- `EPS = 1e-9` dùng chung cho so sánh float.
- Tiếp xúc biên **được tính là collision** (quy tắc bảo thủ về an toàn).
- Giá trị cell theo chuẩn ROS: FREE=0, OCCUPIED=100, UNKNOWN=-1.
- Mọi thành phần deterministic với cùng input; không dùng global random state.

- Cách chạy nhanh bằng 1 câu lệnh:
bash scripts/dev_stack.sh start
- Cách stop chương trình 
bash scripts/dev_stack.sh stop

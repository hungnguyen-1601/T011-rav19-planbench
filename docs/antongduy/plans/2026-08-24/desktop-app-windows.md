# Plan: Đóng gói PlanBench thành desktop app Windows (setup.exe)

## Context

PlanBench hiện là web app 2 process (FastAPI :8000 + Next.js :3000), chạy local qua `scripts/dev_stack.sh`. An cần **desktop app Windows** — cài bằng setup.exe, double-click là chạy, không terminal/Docker — một máy, một người dùng. Đã chốt: **Windows only · giữ màn login dev · installer setup.exe · công nghệ do khảo sát quyết**.

Khảo sát quyết: frontend gần như SPA thuần (65/70 file `"use client"`, 0 API route/server action/middleware, auth client-side sessionStorage) → **static export khả thi**. Backend có nhiều bẫy chống-freeze (subprocess lane spawn `sys.executable`, `inspect.getsource` tính controller_version, alembic load revision động, path `parents[N]`/CWD-relative) → **không PyInstaller**.

## Kiến trúc chọn

1. **Python embeddable 3.12 amd64 + site-packages cài sẵn + source tree nguyên cấu trúc** — không freeze. `sys.executable` là python thật ⇒ subprocess plugin lane, `inspect.getsource` (`candidates.py:207`), alembic sống nguyên.
2. **FastAPI serve luôn static export của web** (StaticFiles + SPA fallback) ⇒ một origin `http://127.0.0.1:PORT` — hết CORS, hết bake `NEXT_PUBLIC_API_URL`, WS cùng host.
3. **Shell: pywebview (WebView2)** trong cùng process Python — không Rust (Tauri), không Node (Electron). Đóng cửa sổ = `server.should_exit`, không orphan process. Rủi ro pythonnet-trên-embeddable có gate go/no-go riêng (Phase 4) + fallback zero-dep: Edge app-mode `msedge --app=<url>`.
4. **Cài per-user** `{localappdata}\Programs\PlanBench` (không UAC); **data root ghi được** `%LOCALAPPDATA%\PlanBench` (db, artifacts, maps, `.env`, logs); launcher `os.chdir(DATA_ROOT)`.
5. **Installer: Inno Setup** (`PrivilegesRequired=lowest`), build pipeline PowerShell.

### Hai điểm kỹ thuật quyết định (python embeddable)

- `python312._pth` **thay thế toàn bộ** sys.path và **bỏ qua PYTHONPATH**. Nhưng `subprocess_lane.py:397-403 _environment()` truyền plugin search paths cho worker **qua PYTHONPATH** (đã verify code). Giải pháp kép, zero sửa code sản phẩm:
  - (a) viết lại `runtime\python312._pth`: `python312.zip`, `.`, `Lib\site-packages`, 12 root `..\app\...` (generate từ `pyproject.toml [tool.pytest.ini_options].pythonpath` — cùng nguồn sự thật `scripts/serve.py` dùng), cuối cùng `import site`;
  - (b) `runtime\Lib\site-packages\sitecustomize.py` đọc `os.environ["PYTHONPATH"]` chèn lại vào `sys.path` — khôi phục ngữ nghĩa PYTHONPATH cho mọi process con.
- Embeddable không có pip: cài deps trên máy build bằng CPython 3.12 thường (bắt buộc cùng minor version — C-extension numpy/pyarrow lệch minor là lỗi im lặng): `py -3.12 -m pip install --target build\stage\runtime\Lib\site-packages -r requirements.txt pywebview`.

### Cây cài đặt

```
{localappdata}\Programs\PlanBench\
  runtime\            python embeddable + ._pth viết lại + Lib\site-packages (deps + pywebview + sitecustomize.py)
  app\                source nguyên cấu trúc: packages\ services\ ml\ apps\api\ apps\desktop\ alembic\ alembic.ini
                      contracts\ configs\ maps\ profiles\ pyproject.toml   (anchors.py parents[3] cần đúng layout)
  web\                next export out\
%LOCALAPPDATA%\PlanBench\        (data root, giữ khi uninstall — hỏi tùy chọn)
  .env  planbench.db  artifacts\  maps\  profiles\  logs\planbench.log  .port
```

## Phase 0 — Tab Cài đặt: chọn model + API key (làm TRƯỚC mọi phase khác, theo yêu cầu An)

V1 fix cứng **o4-mini (OpenAI)**; bản update sau thêm option. Wiring đã khảo sát: provider build stateless (`factory.py build_provider`, không cache), `dependencies.py:113-134 get_agent_service()` đọc `request.app.state.agent_provider` **mỗi request** ⇒ gán lại `app.state` là **có hiệu lực ngay, không cần restart**; advisor dùng chung instance (`decisions.py:1012,1136,1225`).

**Backend:**
- Hàm mới ghi `.env` (cạnh `config.py:242`): atomic (temp + replace), allowlist chỉ `OPENAI_API_KEY`, `PLANBENCH_AGENT_PROVIDER`, `PLANBENCH_AGENT_MODEL`; **xử lý duplicate key** — `.env` hiện có `OPENAI_API_KEY` 2 lần (dòng 8 + 137, `dotenv_values` lấy dòng cuối) ⇒ update mọi occurrence hoặc dedupe, nếu không sửa dòng 8 mà dòng 137 vẫn thắng. Path `.env` relative CWD (khớp `load_provider_keys(".env")` — desktop đã chdir data root nên tự đúng).
- Router mới `apps/api/planbench_api/routers/settings.py` (đăng ký sau `main.py:232`):
  - `GET /api/v1/settings/agent` — provider/model hiện tại + key **masked** (`sk-…abc4`, không bao giờ echo full) + `ready` từ `provider_status()`;
  - `PUT /api/v1/settings/agent` `{api_key}` — **admin-only** theo pattern `plugin_service._require_admin` (`plugin_service.py:429-440`); handler: set `os.environ["OPENAI_API_KEY"]` **trực tiếp** (bẫy đã biết: `load_provider_keys()` không ghi đè env sẵn có — `config.py:236-237`) → ghi `.env` (kèm `PLANBENCH_AGENT_PROVIDER=openai`, `PLANBENCH_AGENT_MODEL=o4-mini` cho bền qua restart — provider tường minh thay vì `auto` để fail loudly thay vì rơi im về mock) → `request.app.state.agent_provider = build_provider("openai", model="o4-mini")`.
  - Không đụng `get_settings()` (`lru_cache`) — bỏ qua Settings, đi thẳng os.environ + build_provider, khỏi cache_clear.
- Key không vào log/response — giữ đúng tuyên bố "no keys, no tokens" của trang system.

**Frontend:**
- Trang mới `apps/web/src/app/settings/page.tsx` — copy khung `system/page.tsx` (`"use client"`, `.panel`, `label.field`, `button.primary`, CSS thuần globals.css): dropdown Model (disabled, một option "o4-mini (OpenAI)"), input password API key, nút Lưu, dòng trạng thái ready/missing (tái dùng `ProviderInfo` từ `lib/agent.ts getCapabilities()`); lỗi field theo pattern `fieldErrorsOf` (`DeploymentForm.tsx`).
- Client: hàm mới trong `apps/web/src/lib/agent.ts` (hoặc `lib/settings.ts`) qua `authFetch`.
- Nav: thêm entry vào section `nav.section.account` (`navigation.ts:135-151`); thêm field `admin?: boolean` vào `NavItem` (`navigation.ts:12-40`), `Sidebar.tsx` ẩn với non-admin (backend vẫn enforce — ẩn UI chỉ là mỹ quan).
- i18n: thêm khoá vào **cả** `en.json` + `vi.json` (flat key, phải sync hai file).

**Test:** unit hàm ghi `.env` (duplicate key, atomic, allowlist — key lạ bị từ chối); router: non-admin 403, GET mask đúng, PUT rebuild (mock `build_provider`) + `app.state` đổi ngay; web vitest render form + gọi API.

**Nối với desktop:** tab này là đường nhập key chính thức của bản desktop (thay cho sửa `.env` tay) — QA Phase 6 bước 8 đổi thành "nhập key qua tab Cài đặt → advisor chạy o4-mini thật, không cần restart".

## Phase 1 — Backend: serve static + vá path hazard (dev không đổi hành vi)

- `apps/api/planbench_api/config.py`: thêm setting `web_dir: str = ""` (rỗng = không mount).
- Module mới `apps/api/planbench_api/static_site.py`: `SpaStaticFiles(StaticFiles, html=True)` — 404 trên path không extension → fallback: `/decisions/<id>` → `decisions/_.html`, tương tự `maps`, `scenarios`; path lạ khác trả 404 thật (không che lỗi export thiếu trang).
- `apps/api/planbench_api/main.py`: cuối `create_app`, `if settings.web_dir: app.mount("/", SpaStaticFiles(...))` — mount **sau** mọi router (API `/api/v1`, WS `/ws` ngoài prefix, `/docs`).
- Vá `main.py:134` fallback `Path("/tmp/planbench_maps")` → `Path(tempfile.gettempdir()) / "planbench_maps"` (POSIX path trên Windows tạo `C:\tmp` — bug thật, đã verify code).
- Test: `create_app` với web_dir giả → GET `/` 200, `/decisions/xyz` trả `_.html`, `/api/v1/health` vẫn JSON, path lạ 404.

## Phase 2 — Web: static export (gate bằng env, không phá Docker)

- `apps/web/next.config.ts`: `output: process.env.PLANBENCH_DESKTOP === "1" ? "export" : "standalone"`.
- **Locale**: bỏ `cookies()` khỏi `layout.tsx:66-67` (đã verify) — file mới `src/lib/locale-script.ts` inline blocking script set `<html lang>` từ cookie trước paint (đúng pattern `theme-script.ts` sẵn có); `Providers` tự gọi `currentLocale()` (`i18n/index.ts:83-86` có sẵn) khi mount.
- **3 dynamic route** `decisions/[id]`, `maps/[id]`, `scenarios/[id]`: thêm `generateStaticParams() → [{id: "_"}]` (sentinel, export sinh `decisions/_.html`); hook mới `src/lib/useRouteId.ts` — id từ `useParams()`, nếu `"_"` thì đọc `window.location.pathname` trong effect; 3 trang đổi sang hook này.
- **`src/lib/api.ts:14-15`**: `API_BASE = NEXT_PUBLIC_API_URL ?? (typeof window !== "undefined" ? window.location.origin : "http://localhost:8000")` — desktop same-origin, `wsUrl()` tự đúng; dev giữ hành vi qua `apps/web/.env.development` `NEXT_PUBLIC_API_URL=http://localhost:8000`.
- Bẫy biết trước: trang dùng `useSearchParams` (`auth/callback`) fail export build → bọc `<Suspense>`. Build sớm cho lộ hết.
- Test: `PLANBENCH_DESKTOP=1` build xanh, serve `out/` qua backend Phase 1 → login dev, vào `/decisions/<id>`, **F5 tại đó**, back; vitest cũ xanh; đổi vi/en không flash.

## Phase 3 — Launcher (`apps/desktop/planbench_desktop/`, chạy được ngay trên repo dev)

- `paths.py`: `INSTALL_ROOT = parents[3]`, `DATA_ROOT = %LOCALAPPDATA%\PlanBench` (cho override bằng env để test).
- `provision.py` — chạy **trước khi import bất kỳ module planbench nào** (settings `lru_cache` + `app = create_app()` module-level):
  - mkdir data root; nếu chưa có `.env` → sinh: `AUTH_SECRET=<token_urlsafe(48)>` (cố định — trống là random mỗi process, logout mỗi lần mở), `PLANBENCH_ENABLE_DEV_LOGIN=true`, `PLANBENCH_SEED_USERS=admin:<pass>`, `PLANBENCH_ADMIN_NICKNAMES=admin` (**phải có trước boot đầu** — admin flag chỉ ăn lúc tạo account), `PLANBENCH_JWT_TTL_MINUTES=720`, `PLANBENCH_DATABASE_URL=sqlite:///<data_root>/planbench.db`, comment hướng dẫn dán key LLM;
  - sync `app\maps\` + `app\profiles\` → data root (không ghi đè file user sửa); backup `planbench.db.bak` trước migrate khi có revision mới;
  - `os.chdir(DATA_ROOT)` (→ `.env`, `artifacts/`, `load_provider_keys(".env")` tự đúng); set `PLANBENCH_WEB_DIR=<install>\web`, `PLANBENCH_MAP_ROOT=<data_root>`.
- `migrate.py`: Alembic **Python API** — `Config(install/app/alembic.ini)` + `set_main_option("script_location", <abs>)` + `command.upgrade(cfg, "head")` (né alembic.ini relative-CWD; URL từ env đã set).
- `server.py`: chọn port rảnh (bind 0), import `planbench_api.main` **sau** provision, `uvicorn.Server` trong thread, poll `/api/v1/health` ≤30s.
- `main.py` entry: logging `RotatingFileHandler(logs/planbench.log)` (pythonw không có console, `sys.stderr` có thể None); single-instance qua file `.port` + health check (instance sống → mở cửa sổ trỏ nó); `webview.create_window` → `webview.start()`; đóng cửa sổ → `should_exit`, join, xóa `.port`; `import webview` fail → fallback Edge app-mode.
- Test trên repo dev: chạy launcher với data-root tạm → sinh `.env`, migrate 0→head, cửa sổ mở, login admin, đóng → không còn process; chạy lần 2 → không re-seed, AUTH_SECRET giữ nguyên.

## Phase 4 — Build pipeline (`scripts/build_desktop.ps1`; máy build cần CPython 3.12, Node, Inno Setup 6)

1. Web: `npm ci` + `PLANBENCH_DESKTOP=1` next build → `build\stage\web\`.
2. Tải python-3.12.x-embed-amd64.zip (cache + SHA256 ghim) → `build\stage\runtime\`.
3. `pip install --target ...\Lib\site-packages -r requirements.txt pywebview` (không requirements-optional; torch xác nhận không import khi thiếu).
4. Generate `python312._pth` từ pyproject pythonpath (chống drift, triết lý serve.py) + ghi `sitecustomize.py`.
5. Robocopy source → `build\stage\app\` — **exclude**: tests, `__pycache__`, `*.pyc`, node_modules, artifacts, `planbench.db*`, `.git`, docs, eval, presentation, ros2_ws, src, checkpoint lớn ml. **Ship nguyên `.py`** (inspect.getsource).
6. **Gate smoke stage** `scripts/smoke_stage.py` chạy bằng chính `stage\runtime\python.exe`:
   - `import planbench_api.main` OK (chứng minh `._pth`);
   - spawn `sys.executable` với PYTHONPATH giả → kiểm sitecustomize khôi phục;
   - launcher với data-root tạm: migrate + health + GET `/` + GET `/decisions/abc`;
   - roundtrip plugin qua SubprocessLane (gate quyết định toàn kiến trúc);
   - `import webview` + tạo window timeout ngắn — **go/no-go pywebview**; fail → chuyển fallback Edge app-mode.
7. `iscc` → `dist\PlanBench-Setup-<ver>.exe`.

## Phase 5 — Installer (`installer\planbench.iss`)

- `PrivilegesRequired=lowest`, `DefaultDirName={localappdata}\Programs\PlanBench`, x64; `AppId` GUID cố định cho upgrade in-place; `[InstallDelete]` dọn `app\`+`runtime\` cũ (tránh file mồ côi khi source đổi tên).
- Shortcut Desktop + Start Menu → `runtime\pythonw.exe "{app}\app\apps\desktop\planbench_desktop\main.py"`, icon `installer\planbench.ico`.
- Uninstall: dialog tùy chọn xóa data root (mặc định giữ).
- WebView2: check registry, Win11 sẵn có; bootstrapper chỉ khi thiếu.
- Test: cài VM sạch không Python/Node; upgrade đè giữ db + `.env`; uninstall giữ data.

## Phase 7 — CI/CD release + auto-update

**Kênh đã chốt với An: GitHub Releases của repo chính** (`hungnguyen-1601/T011-rav19-planbench`). Repo private ⇒ app phía user cần token read-only để check/tải — fine-grained PAT (scope: contents read-only, chỉ repo này) đặt trong `.env` data root (`PLANBENCH_UPDATE_TOKEN=`), chấp nhận được vì phát hành nội bộ team; provision ghi sẵn dòng comment hướng dẫn. Không có token ⇒ updater tắt im lặng (log 1 dòng), app vẫn chạy bình thường.

**Version — một nguồn sự thật:** file `apps/desktop/planbench_desktop/VERSION` (semver). Build script đọc nó stamp vào Inno `AppVersion` + tên file setup; launcher đọc nó để so sánh update. Tag release: `desktop-vX.Y.Z`.

**CI — workflow mới `.github/workflows/desktop-release.yml`** (tách khỏi `ci.yml` hiện có):
- Trigger: push tag `desktop-v*` (+ `workflow_dispatch` để build thử không release).
- `runs-on: windows-latest`; setup-python 3.12 + setup-node 22; `choco install innosetup`.
- Chạy `scripts/build_desktop.ps1` — **smoke gate stage (Phase 4.6) là release gate**: gate đỏ ⇒ job fail ⇒ không có release. Kiểm tag khớp `VERSION`, lệch ⇒ fail.
- Sinh manifest `latest.json`: `{version, url_asset, sha256, notes}`.
- `gh release create desktop-vX.Y.Z dist\PlanBench-Setup-X.Y.Z.exe latest.json --notes ...` (GITHUB_TOKEN mặc định của Actions đủ quyền).

**Auto-update phía app — module mới `apps/desktop/planbench_desktop/updater.py`:**
- Sau khi cửa sổ mở (không chặn startup), thread nền: `GET /repos/<owner>/<repo>/releases/latest` (header `Authorization: Bearer <PLANBENCH_UPDATE_TOKEN>`), lọc tag `desktop-v*`, so semver với `VERSION`.
- Có bản mới → hỏi user (dialog pywebview / `evaluate_js` confirm): "Có bản X.Y.Z — cập nhật?". Không tự cài ngầm.
- Đồng ý → tải asset setup.exe qua API (`Accept: application/octet-stream`) vào `%TEMP%`, **verify sha256 theo `latest.json`** (tải manifest cùng release, không tin file rời), rồi: spawn detached `cmd /c start /wait "" setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART && start "" pythonw.exe <main.py>` và **app tự thoát ngay** (nhả file lock trong `{app}\runtime` trước khi Inno ghi đè; `AppId` cố định + `[InstallDelete]` Phase 5 lo phần upgrade in-place, thêm `CloseApplications=yes` phòng trường hợp còn instance).
- Lỗi mạng/token/tải dở ⇒ log + bỏ qua, lần mở sau thử lại. Check tối đa 1 lần/lần mở app.
- Test: dựng release giả trên repo (tag prerelease + workflow_dispatch), máy cài bản cũ → mở app → nhận thông báo → cập nhật → app mở lại đúng version mới, db + `.env` còn nguyên; sha256 sai ⇒ từ chối cài, log rõ.

## Phase 6 — QA end-to-end (VM sạch) + docs

Smoke bắt buộc: setup → shortcut → cửa sổ <10s không flash console · first-run sinh `.env`+db head+maps copy · login admin **là admin** · 1 simulation có WS playback · 1 decision run, đóng mở app dữ liệu còn · **import 1 plugin .zip chạy qua subprocess lane** · export Excel tên file đúng · nhập API key qua tab Cài đặt → advisor o4-mini thật không cần restart · đóng cửa sổ Task Manager sạch · F5 tại `/decisions/<id>` không trắng trang.

Docs: `docs/DESKTOP.md` (build howto, cây thư mục, thêm API key, vị trí log). **Lưu bản plan này cho An**: `docs/antongduy/plans/2026-08-24/desktop-app-windows.md` (file riêng — phiên plan riêng, không gộp vào 2 file plan cùng ngày).

## Rủi ro còn lại

1. pywebview (pythonnet) trên embeddable — gate Phase 4, fallback Edge app-mode chi phí ~0.
2. Hydration trang sentinel `_` khi hard-load — id đọc trong effect; nếu tệ: dự phòng chuyển 3 trang sang query param.
3. Installer ~150–200 MB nén — chấp nhận v1.
4. `pip --target` với package cần entry-points đặc biệt — smoke gate bắt.
5. SmartScreen với exe không ký — nội bộ, ghi hướng dẫn.

## Cắt khỏi v1 (cố ý)

Code-signing · tray icon · OAuth Google/GitHub (dev login đủ) · delta update (mỗi update tải trọn setup.exe ~150–200 MB — chấp nhận nội bộ) · torch/PPO, MLflow, PostgreSQL (degrade sẵn) · multi-user/service · ARM64 · stub exe launcher riêng · trim site-packages.

## Trình tự + verification tổng

Phase 0 (tab Cài đặt — độc lập, giá trị ngay cả trên bản web) → Phase 1 ∥ Phase 2 → gặp nhau ở integration test cuối Phase 2 → Phase 3 (trên repo dev) → Phase 4 (gate pywebview ngày đầu) → Phase 5 → Phase 6 → Phase 7 (CI/CD + auto-update, cần installer Phase 5 ổn định trước). Mỗi phase có test riêng như trên; nghiệm thu cuối = 10 bước smoke Phase 6 trên VM sạch. Không commit — An commit thủ công; mỗi phần xong có report vào `docs/antongduy/reports/`.

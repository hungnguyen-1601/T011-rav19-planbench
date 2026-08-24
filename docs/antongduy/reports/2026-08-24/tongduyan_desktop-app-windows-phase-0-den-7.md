# Đóng gói PlanBench thành desktop app Windows — Phase 0 đến 7

- **Ngày:** 2026-08-24
- **Nhánh:** `tongduyan_desktop-app` (tách từ `main`, **chưa merge, chưa push**)
- **Plan:** [desktop-app-windows.md](../../plans/2026-08-24/desktop-app-windows.md)
- **Khảo sát nền:** [tongduyan_khao-sat-deploy-len-app.md](../../notes/2026-08-24/tongduyan_khao-sat-deploy-len-app.md)
- **Tài liệu người dùng + người build:** [docs/DESKTOP.md](../../../DESKTOP.md)

---

## 1. Kết quả

Làm xong **7/7 phase** đã duyệt. Cây cài đặt dựng được, cổng smoke xanh
7/7 với web export thật, 8 commit theo đúng thứ tự phase.

Một việc **chưa làm được và không thể làm ở đây**: chạy thật
`build_desktop.ps1` để ra `setup.exe`. Máy này chưa có Inno Setup, chưa
có CPython 3.12 riêng (venv đang là 3.13), và bản `sha256` của Python
embeddable phải do người xác nhận với python.org — script cố ý dừng
thay vì tự tin vào hash nó tự tính. Chi tiết ở mục 5.

## 2. Từng phase

### Phase 0 — Tab Cài đặt (`d3a059f`)

Chỗ nhập API key giờ nằm trong sản phẩm thay vì trong file trên đĩa.

- `config.py` thêm `write_env_values()`: ghi atomic, **allowlist** 3 biến
  (`OPENAI_API_KEY`, `PLANBENCH_AGENT_PROVIDER`, `PLANBENCH_AGENT_MODEL`)
  — cùng file đó còn giữ `AUTH_SECRET` và URL database, nên một body
  request đặt được biến tuỳ ý là một đường ghi đè chúng qua HTTP.
- **Sửa mọi lần khai, không sửa lần đầu.** `.env` của repo khai
  `OPENAI_API_KEY` **hai lần** (dòng 8 và 137) và `dotenv_values` lấy
  dòng cuối; sửa dòng đầu thì giá trị cũ vẫn thắng trong khi file nhìn
  có vẻ đúng.
- Router `settings.py`: `GET` cho mọi user đăng nhập, `PUT` **admin-only**
  theo pattern `plugin_service._require_admin`. Key set thẳng vào
  `os.environ` (không qua `load_provider_keys`, vì hàm đó cố ý không ghi
  đè biến đã có), ghi `.env`, rồi gán lại `app.state.agent_provider`.
- **Không cần restart**: `dependencies.py:113-134` đọc `app.state` mỗi
  request, nên advisor và dock dùng ngay provider mới.
- Key **không bao giờ trả ra**: response chỉ có `key_present` + 4 ký tự
  cuối (`••••9876`).
- Web: trang `/settings`, dropdown model 1 option `o4-mini` (disabled,
  ghi chú bản sau thêm), input password, trạng thái ưu tiên
  `active_deterministic` — báo "đang trả lời offline" **kể cả khi đã có
  key**, tức ca "đã lưu nhưng process chưa đọc". Nav ẩn với non-admin
  (backend vẫn chặn). 21 khoá i18n, sync đủ en + vi.

12 test backend, 21 test web.

### Phase 1 — Một process, một origin (`f094d9d`)

- Setting mới `web_dir` (rỗng = phục vụ API như cũ, Docker không đổi).
- `static_site.py`: `SpaStaticFiles`, mount **cuối cùng** — mount ở `/`
  khớp mọi path nên đăng ký sớm hơn là nuốt cả `/api/v1` lẫn `/ws`.
- Deep link `/decisions/<id>` trả shell của chính route đó, **không** trả
  `index.html`: catch-all sẽ biến "trang thiếu trong export" (lỗi build)
  thành màn trắng trông như lỗi routing, và người thấy đầu tiên là user.
- Vá `main.py:134`: fallback `Path("/tmp/planbench_maps")` → `tempfile.gettempdir()`.
  Trên Windows chuỗi `/tmp` là path **tương đối theo ổ đĩa của CWD**, nên
  fallback lặng lẽ tạo `C:\tmp`.

### Phase 2 — Web static export (`454eb06`)

- `next.config.ts` gate `PLANBENCH_DESKTOP=1` → `export`, không có env thì
  vẫn `standalone` (đã smoke-test lại đường Docker: `/`, `/decisions/abc123` đều 200).
- Bỏ `cookies()` khỏi `layout.tsx`, thay bằng inline blocking script
  đúng pattern `theme-script.ts` — `<html lang>` vẫn đúng trước first paint.
- 3 route `[id]` tách server wrapper (`generateStaticParams` → sentinel `_`)
  + component client; hook `useRouteId` đọc id thật từ `location` khi gặp `_`.
- `api.ts` mặc định same-origin; `.env.development` giữ hành vi dev.
- Xác minh export: đủ `index.html`, `decisions/_.html`, `maps/_.html`,
  `scenarios/_.html`; **không** còn `localhost:8000` trong chunk nào.

### Phase 3 — Launcher (`fefaef8`)

`apps/desktop/planbench_desktop/`: `paths` · `bootstrap` · `provision` ·
`migrate` · `server` · `main`.

Ba quyết định chỉ có **một** cơ hội đúng, vì code tiêu thụ chúng chỉ đọc
lúc boot đầu: `AUTH_SECRET` (rỗng = random mỗi process = đăng xuất mỗi
lần mở), `PLANBENCH_ADMIN_NICKNAMES` (chỉ ăn lúc *tạo* account), và tài
khoản seed. Tất cả ghi vào `.env` trước khi import bất kỳ module
PlanBench nào — `Settings` là `lru_cache` và `main.py` dựng app ngay lúc
import.

`chdir` vào data root cho `.env` / `artifacts` / map root đồng thuận;
migrate bằng **Alembic Python API** (`alembic.ini` khai `script_location`
tương đối CWD, mà lúc đó CWD là data root, không có migration nào ở đó);
port do OS cấp; đóng cửa sổ = `should_exit` + join, không để orphan.

`apps/desktop` được thêm vào **cả hai** path list (pyproject + dev_stack.sh)
— test `test_dev_stack_pythonpath.py` kiểm hai chiều.

### Phase 4 + 5 — Build pipeline và installer (`beb7314`)

**Không dùng PyInstaller.** Freeze phá đúng hai thứ plugin lane cần:
`sys.executable` trong app frozen là chính app chứ không phải Python, và
`candidates.py:207` gọi `inspect.getsource` cần file `.py` mà freezer
strip. Thay bằng Python embeddable + cây source nguyên vẹn.

Hai cơ chế then chốt:

- `make_runtime_paths.py` sinh `python312._pth` **từ pyproject** (đã có 3
  bản chép tay của danh sách này và 1 bản từng drift — bản thứ tư là cơ
  hội thứ tư cho cùng con bug).
- `sitecustomize.py` trả lại `PYTHONPATH`. Embeddable có `._pth` thì
  **bỏ qua** biến này, mà `subprocess_lane._environment()` dùng đúng nó
  để báo worker chỗ plugin nằm. Thiếu → worker chạy, không import được
  plugin, host đọc thành "thuật toán dừng robot".
- `installer/python-embed.json` để `sha256` rỗng và build **từ chối chạy**
  cho tới khi người xác nhận hash với python.org.
- Inno Setup: per-user (không UAC), `AppId` cố định, `[InstallDelete]` dọn
  code cũ, uninstall **hỏi** trước khi xoá data (mặc định Không).
- Icon sinh bằng script (`make_icon.py`), 6 kích thước, không phải binary chết.

### Phase 7 — CI/CD + auto-update (`a04b36a`)

- `.github/workflows/desktop-release.yml`: tag `desktop-v*` → build trên
  `windows-latest` → **cổng smoke là cổng release** → `latest.json` mang
  sha256 → `gh release create`. Fail nếu tag ≠ file `VERSION`.
- `updater.py`: so version bằng **số** (string compare đặt `0.10.0`
  trước `0.9.0` — cách updater chết lặng sau một năm), chỉ nhận tag
  `desktop-v*`, và **từ chối mọi bản tải không khớp sha256 trong manifest
  của chính release đó**. Hỏi một lần mỗi lần mở, Không là câu trả lời
  thật. Không token → không kiểm tra, ghi log một dòng.
- 20 test, tập trung vào các ca **từ chối** — sai "có" ở đây là chạy
  chương trình của người khác.

## 3. Ba bug thật do cổng smoke bắt được

Đây là phần đáng giá nhất của phiên, và cả ba đều **xanh trong unit test**:

1. **Launcher ghi `PLANBENCH_DATABASE_URL` vào `.env` nhưng không export
   vào `os.environ`.** `alembic/env.py` đọc environment chứ không đọc
   `.env`. Test pytest của tôi tự `setenv` nên che mất. Bản đó cài xong
   sẽ chết ở migration đầu tiên. Đã thêm test **không** setenv — chính
   sự vắng mặt đó là nội dung test.
2. **`SpaStaticFiles` bắt sai lớp exception.** `StaticFiles` ném
   `starlette.exceptions.HTTPException`, FastAPI's là *subclass* — bắt
   subclass thì compile được, đọc thấy đúng, và không bao giờ chạy.
3. **Export thật có `404.html`, nên Starlette *trả* 404 thay vì ném.**
   Fixture test của tôi không có `404.html` nên nhánh exception vẫn chạy
   và test xanh — trong khi server thật trả trang not-found cho **mọi**
   deep link. Đã xử lý cả hai hình dạng và thêm `404.html` vào fixture
   kèm giải thích.

Cộng một lỗi test bao rộng quá tay: `test_no_agent_route_publishes_a_write_verb`
lọc mọi path chứa `"/agent"`, nên `/settings/agent` (PUT) rơi vào lưới
dành cho agent router. Đã đổi sang so prefix `/api/v1/agent` — **chặt hơn
chứ không lỏng hơn** — và thêm test khoá rằng prefix đó vẫn phủ toàn bộ
route của router (`a668bd2`).

## 4. Test đã chạy

| Phạm vi | Kết quả |
|---|---|
| `tests/desktop/` (launcher + packaging + updater) | **60 passed** |
| `tests/api/test_api_settings.py` | **12 passed** |
| `tests/api/test_api_static_site.py` | **8 passed** |
| `tests/api/test_api_agent.py` | **24 passed** |
| API lân cận (auth, maps, config, plugin catalogue) | **75 passed** |
| Web vitest (24 file liên quan) | 832 passed / 11 failed — **11 lỗi có sẵn**, không do phiên này |
| Cổng smoke với export thật | **7/7 ok** |
| `next build` cả hai chế độ (export + standalone) | xanh |

**11 test web đỏ là nợ có sẵn**: 10 test assert các khoá i18n
(`plugin.hint`, `advice.do`, `preflight.check`…) **không tồn tại trong cả
hai locale trên `origin/main`** — docstring của `DecisionDetail.tsx` đã
ghi "That is upstream's to finish"; 1 test đòi substring chứa `\n` trong
một file CRLF-only. Cả hai nhóm nằm ngoài phạm vi phiên này.

Ruff: mọi file tôi đụng sạch. `apps/api/planbench_api/map_files.py` có 3
lỗi ruff (E402 ×2, E501) **từ commit `37e573c` của người khác** — không
sửa vì ngoài phạm vi.

**Chưa chạy full suite** theo đúng yêu cầu; đang cho chạy ngầm sau khi
nộp báo cáo này.

## 5. Việc còn lại

**Cần máy có toolchain** (không làm được ở phiên này):
1. Cài Inno Setup 6 + CPython 3.12, chạy `scripts\build_desktop.ps1`.
2. Lần chạy đầu sẽ dừng và in hash Python embeddable — **đối chiếu với
   python.org** rồi dán vào `installer/python-embed.json`.
3. QA 10 bước trên VM sạch (Phase 6): cài, first-run, login admin, chạy
   simulation có WebSocket, chạy decision run, **import plugin `.zip`**,
   export Excel, nhập key qua tab Cài đặt, đóng app kiểm Task Manager,
   F5 tại `/decisions/<id>`.
4. Tạo fine-grained PAT read-only, dựng một release thử để nghiệm thu
   đường auto-update.

**Cần An quyết:**
- `git stash drop stash@{0}` — stash do subagent tạo lúc dựng baseline,
  nội dung đã nằm trọn trong HEAD. Tôi **không tự drop** vì đó là thao
  tác huỷ. (`stash@{1}` là của phiên trước, không đụng.)
- README §9.2 vẫn viết "import thuật toán qua giao diện: chưa có đường
  vào" trong khi tính năng đã merge từ `9e505be`. Ngoài phạm vi plan
  này, nhưng ai đọc repo để đánh giá sẽ đánh giá sai.

**Cắt khỏi v1 (cố ý):** code signing (nên có SmartScreen warning) ·
delta update · tray icon · OAuth · macOS/Linux.

**Một giới hạn không phải lỗ hổng:** decision run xếp hàng **một lúc
một**, vì HĐ-7.4 cấm hai run đánh giá trên cùng máy — cả hai pin cùng
nhân và mỗi cái thành background load của cái kia. Đó là hợp đồng đo
lường, không phải setting hiệu năng.

## 6. Commit

Nhánh `tongduyan_desktop-app`, 8 commit, chưa push:

```
454eb06  web static export + shell cho deep link (Phase 2)
a668bd2  siết guard write-verb + docs/DESKTOP.md
a04b36a  CI release + auto-update (Phase 7)
beb7314  embedded runtime + build pipeline + installer (Phase 4-5)
fefaef8  desktop launcher (Phase 3)
f094d9d  một process một origin (Phase 1)
d3a059f  tab Cài đặt (Phase 0)
c3ca1b6  note khảo sát deploy
```

Không commit `vfh_plus_import/`, `vfh_plus_iterated/`,
`planbench.db.bak-before-0010` theo yêu cầu. Đã thêm `build/`, `dist/`
vào `.gitignore`.

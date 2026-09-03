# Report: chuẩn bị triển khai web trên Render free + Neon Postgres

- **Ngày:** 2026-09-03
- **Nhánh:** `tongduyan_deploy-web-render-free`
- **Bối cảnh:** desktop app đã phát hành; An muốn thêm bản web, ràng
  buộc miễn phí. Khảo sát ở
  `notes/2026-09-03/tongduyan_khao-sat-deploy-web-mien-phi.md`; An chốt
  phương án Render free + Neon.

## Đã làm

1. **`docker/requirements-api.txt`: thêm `httpx==0.28.1`** (pin theo
   `requirements.txt`). Đóng blocker #1 của note 08-24: `oauth.py:221,256`
   import lazy trong callback handler, nên image thiếu nó vẫn boot,
   health xanh, và chỉ nổ `ModuleNotFoundError` ở lần đăng nhập đầu.
2. **`render.yaml` mới ở gốc repo** — Blueprint hai service Docker plan
   free (`planbench-api`, `planbench-web`), thay cho bản Render cũ bấm
   tay không tái lập được (fetch 09-03 trả 503, đang ngủ/suspend):
   - migration trong start command (`alembic upgrade head && uvicorn…`)
     thay vì service `migrate` riêng — free = một replica nên race của
     compose không áp, còn `preDeployCommand` là tính năng trả phí; ghi
     chú rõ phải chuyển sang `preDeployCommand` trước khi scale;
   - `AUTH_SECRET` `generateValue: true` (cố định qua restart);
   - `PLANBENCH_DATABASE_URL` (Neon) và `PLANBENCH_SEED_USERS`
     `sync: false` — An điền trên dashboard, secret không qua chat/repo;
   - profile `demo` + `demo_owner` nickname `admin` theo DEMO-PROFILE.md;
   - **cố ý không đặt key LLM nào** — subprocess lane của plugin kế thừa
     nguyên env mà demo owner cầm admin; mock advisor là đủ cho showcase;
   - `NEXT_PUBLIC_API_URL` là build arg (Dockerfile.web đã có `ARG`).
3. **`docker-compose.yml`: externalize `PLANBENCH_CORS_ORIGINS`**
   (`${…:-["http://localhost:3000"]}`) — trước hardcode, đổi domain phải
   sửa file.
4. **`docs/reference/DEPLOYMENT.md`: mục mới "Render free + Neon"** —
   runbook dựng lần đầu (Neon → Blueprint → hai biến dashboard), bảng
   "đổi domain = đổi 4 biến", và ba khác biệt so với compose kèm lý do
   (migration-at-start, không volume artifact ⇒ replay mồ côi sau
   restart, không key LLM).
5. **Đính chính note khảo sát cùng ngày:** bản đầu viết blocker auth
   (#2, note 08-24) còn nguyên — sai do grep pattern
   `ActiveUser|current_user` trượt tên dependency thật. Đọc file cho
   thấy `scenarios.py`/`simulations.py`/`ws.py` đã phủ auth từ contract
   7.0.0 (`ReadingUser`/`WritingUser`/`SimulatingUser`; WebSocket xác
   thực bằng ticket một-phút, `POST /api/v1/ws/tickets`). Khối lượng
   việc giảm ~1 ngày so với ước lượng trong note.

## Không làm, và vì sao

- **Lọc env cho subprocess lane** (blocker #3 note 08-24): đứng sau cửa
  admin-only, và bản demo không mang key thật nên không có gì để lộ.
  Vẫn là việc phải làm trước kịch bản pilot/public có key.
- **Rate limit** (KL #18): chưa có, chấp nhận cho demo link gửi tay.
- **Seed dữ liệu demo vào Neon**: cần An chạy từ máy local trỏ
  `PLANBENCH_DATABASE_URL` vào Neon (dữ liệu + artifact là của các run
  thật trên máy An). Chưa tự động hoá.

## Việc còn lại cho An (thao tác tay, có secret)

1. Tạo project Neon free, lấy connection string (`?sslmode=require`).
2. Render → New → Blueprint → repo `origin`; nếu tên `planbench-web` bị
   service cũ chiếm thì xoá/đổi tên bản cũ trước.
3. Điền hai biến dashboard: `PLANBENCH_DATABASE_URL`,
   `PLANBENCH_SEED_USERS` (`admin:…:mật-khẩu-mạnh` — nickname khớp
   `PLANBENCH_DEMO_OWNER_NICKNAME`).
4. Mở web lần đầu (cold start ~1 phút), đăng nhập, kiểm banner Demo
   Owner hiện.
5. Muốn có dữ liệu trưng bày: seed từ máy local vào Neon (bàn riêng —
   artifact `file://` không theo DB được, cần chọn cách: chạy lại run
   nhỏ trên instance, hoặc chấp nhận decision không replay).

## Kiểm chứng

- `render.yaml` parse sạch (`yaml.safe_load`).
- Không sửa file `.py` nào ⇒ không cần ruff/pytest.
- Chưa build image ở máy này (httpx là thay đổi pin thuần; build thật
  diễn ra trên Render lúc deploy).

## Bổ sung cùng ngày: setup Neon CLI theo prompt của console

An tạo project Neon (`wild-surf-10729491`, org `org-super-glade-33615520`,
branch `production`) và đưa prompt setup 7 bước. Đã chạy trong `P-011`:

- `npm i -g neon@latest` + `neon login` — OK.
- `neon skills -y` — **bỏ qua**: đòi Node ≥ 22.20.0, máy đang 22.17.1
  cài hệ thống (không nvm, winget không có trong PATH shell). Chỉ là
  skill hỗ trợ agent, không chặn bước nào sau. Muốn có: nâng Node rồi
  chạy lại.
- `neon mcp -y` — cài MCP server cho 8 client. **Lưu ý bảo mật:** lệnh
  mint một API key **account-wide** (id 3307555, CLI tự cảnh báo
  "reaches everything your account can"). Demo chỉ cần một project —
  cân nhắc `neon api-keys revoke 3307555` sau khi xong việc.
- `neon link … -y` — ghi `.neon/` và kéo `DATABASE_URL`,
  `DATABASE_URL_UNPOOLED`, `NEON_BRANCH` vào `.env` gốc repo. Cả `.env`
  lẫn `.neon` nằm trong `.gitignore` (dòng `.neon` do CLI tự thêm) —
  secret không vào git và không in ra terminal (hook `.ai-log` ghi tool
  call nguyên văn).
- `neon config init` + rút `neon.ts` về `defineConfig({})` đúng prompt;
  CLI tạo `package.json`/`package-lock.json` gốc repo cho
  `@neon/config`, `@neon/env` — commit để `neon deploy` tái lập được.
- `neon deploy` — "No changes — branch production already matches the
  policy". Kết nối Neon hoạt động.

**Giá trị điền vào Render:** PlanBench đọc `PLANBENCH_DATABASE_URL` —
copy **giá trị** từ `.env`, khuyên dùng dòng `DATABASE_URL_UNPOOLED`:
SQLAlchemy tự quản pool; URL pooled đi qua PgBouncer transaction mode
có thể gây bất ngờ với alembic/prepared statement, và một instance free
không cần pooler.

**Sự cố giữa phiên:** HEAD bị chuyển về `main` giữa hai lượt làm việc
(phiên khác/thao tác tay), nên các file Neon sinh ra lúc đang đứng
nhầm trên `main`. Đã switch lại nhánh — untracked file đi theo, WIP
của An trong index không suy suyển — và commit tại nhánh.

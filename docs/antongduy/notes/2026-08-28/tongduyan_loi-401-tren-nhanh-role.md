# Lỗi 401 khi tạo deployment trên nhánh `tongduyan_roles-capabilities`

Ngày 2026-08-28 · khảo sát, **chưa sửa dòng code nào**

Triệu chứng: mở trang Deployments, banner đỏ `missing bearer token`, khung
preview đứng ở "Loading...", trong khi góc phải vẫn hiện `antongduy`.

---

## 1. Kết luận

`apps/web/src/lib/api.ts` là một HTTP client **không gắn header
`Authorization`**. Commit `8ccb20a` đóng quyền cho nhóm route mà client đó gọi,
nhưng không cập nhật frontend. Web có hai client, một cái có chìa khoá, một cái
không — và cái không chìa vẫn chạy được cho tới khi cửa bị đóng.

Không phải sai mật khẩu. Không phải `PLANBENCH_JWT_SECRET`. Không phải cổng.
Không phải CORS.

---

## 2. Loại trừ từng khả năng — bằng chứng đo được

| Nghi ngờ | Cách kiểm | Kết quả |
|---|---|---|
| Token hết hạn / secret ngẫu nhiên | `.env` sửa 09:33:38, API khởi động 09:33:45 | process **đã** nhận secret mới |
| Nhiều process API mỗi cái một secret | `Get-NetTCPConnection -LocalPort 8000` | đúng **một** listener, PID 28812 |
| Config không đọc được | nạp `get_settings()` đúng như app | secret 26 ký tự, TTL 60, CORS `localhost:3000` |
| Tài khoản sai | `POST /api/v1/auth/login` bằng curl | **HTTP 200** |
| API từ chối token hợp lệ | ký token bằng secret trong `.env`, gọi `/auth/me` | **HTTP 200**, roles `[admin, engineer]` |
| Tab chưa đăng nhập | console đọc `sessionStorage` | **có** token, có user `137f3f3fc57f` |
| Token trong tab đã hỏng | console gọi `/auth/me` bằng chính token đó | **HTTP 200**, hết hạn 10:41:49 |
| CORS | thông điệp lỗi | body JSON của API, không phải `blocked by CORS policy` |

Sau khi loại hết: token tốt, API tốt, tab có session — vậy **request không mang
token**.

Tái hiện đúng câu lỗi:

```
POST /api/v1/scenarios/preview  KHÔNG token → 401 {"message":"missing bearer token"}
POST /api/v1/scenarios/preview  CÓ  token   → qua auth (422 vì body thiếu field)

GET  /api/v1/maps               KHÔNG token → 401
GET  /api/v1/maps/<id>          KHÔNG token → 401
GET  /api/v1/scenarios          KHÔNG token → 401
GET  /api/v1/health             KHÔNG token → 200
```

---

## 3. Chỗ hỏng

[`apps/web/src/lib/api.ts:59`](../../../../apps/web/src/lib/api.ts) —

```ts
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
```

So với [`apps/web/src/lib/auth.ts:333`](../../../../apps/web/src/lib/auth.ts):

```ts
...(session ? { Authorization: `Bearer ${session.token}` } : {}),
```

`authFetch` có, `request` không. `api` object export **14 hàm** đi qua
`request`, gồm `listMaps`, `getMap`, `createMap`, `updateMap`, `deleteMap`.

Trang Deployments trúng ở hai chỗ: `DeploymentForm.tsx:519` gọi `api.listMaps()`
nhưng bọc `.catch(() => [])` nên hỏng **im lặng**, và `DeploymentForm.tsx:657`
gọi `api.getMap(id)` — cái này ném ra banner đỏ.

**Ảnh hưởng rộng hơn một trang.** Cùng client đó dùng ở `decisions/page.tsx`,
`maps/page.tsx`, `maps/[id]/MapEditor.tsx`, `simulate/page.tsx`,
`system/page.tsx`, `DecisionDeploymentPreview.tsx`. `api.createMap` cũng đi qua
đó, nên vẽ map mới rồi lưu cũng hỏng — không có đường vòng qua UI.

### Lỗ thứ hai, cùng nguồn gốc

`8ccb20a` đổi WebSocket sang cơ chế ticket vì trình duyệt không đặt được header
trên WebSocket: `POST /api/v1/ws/tickets` trả một ticket dùng một lần, sống một
phút; socket đọc nó từ `?ticket=`, không có thì đóng với mã `4401` và câu
`this socket needs a ticket from POST /api/v1/ws/tickets`.

Web chưa biết xin ticket. `wsUrl()` ở `api.ts:44` vẫn dựng URL trần, và
`useEpisodeStream.ts:100` nối thẳng. Nghĩa là **phát lại mô phỏng trực tiếp cũng
đang hỏng**, chỉ là chưa ai chạm tới.

---

## 4. Lỗi hay cố ý — bằng chứng nói là lỗi

```
git show --stat 8ccb20a       → 39 file đổi, apps/web: 0 file
git branch -a --contains 8ccb20a → chỉ tongduyan_roles-capabilities
git merge-base --is-ancestor 8ccb20a main → KHÔNG
```

Commit đó sửa API và **test API**, không đụng dòng nào ở frontend. Chính message
của nó nói ý định là *"reading now needs an account and writing needs the
capability that names the action"* — tức mọi client phải mang token.
`lib/api.ts` là một client và bị bỏ sót.

Không có test nào khẳng định `lib/api.ts` phải vô danh. Ngược lại,
`charts-and-export.test.tsx:61` khẳng định `reports.ts` **phải** gắn
`Authorization`. Gắn token là quy ước sẵn có; `api.ts` là ngoại lệ bị quên.

⇒ Đây là **vế còn thiếu của `8ccb20a`**, không phải quyết định thiết kế.

---

## 5. Phương án xử lý

### A. Sửa hai lỗ frontend (khuyến nghị)

Việc cụ thể:

1. Tách phần đọc token ra module riêng cho `api.ts` và `auth.ts` cùng dùng —
   `auth.ts` đang import `API_BASE` từ `api.ts`, nên import ngược `loadSession`
   sẽ tạo vòng. ESM chịu được vòng nhưng thứ tự khởi tạo thành ngầm định.
2. `request()` gắn `Authorization` khi có session, gặp 401 thì `clearSession()`
   — giống hệt `authFetch`.
3. `wsUrl` chuyển thành async: xin ticket qua `POST /ws/tickets`, gắn
   `?ticket=`, rồi mới nối. Sửa `useEpisodeStream.ts` theo.
4. Thêm test khẳng định **cả hai** client đều gắn token, theo đúng kiểu
   `charts-and-export.test.tsx` đang làm với `reports.ts` — để lần sau đóng cửa
   mà quên phát chìa thì test kêu, chứ không phải người dùng kêu.
5. Chạy vitest phần đụng tới + `tsc --noEmit`. Không full suite.

Chỉ đụng `apps/web`, không chạm logic role/capability nào ở API.

**Vì sao nên làm:** không sửa thì nhánh không merge được — web hỏng ở 6 nơi.
Đây là hoàn thành nhánh, không phải việc mới.

### B. Bỏ qua UI, tạo task profile thẳng qua API

Nhanh hơn cho việc trước mắt (tôi cần task profile để sinh run cho P5):

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=antongduy" -d "password=antongduy" \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

curl -X POST http://localhost:8000/api/v1/task-profiles \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  --data-binary @profile.json
```

Đã kiểm: login 200, `run.create` nằm trong capabilities của tài khoản.

**Giới hạn:** không sửa được gì, chỉ đi vòng. Và nó ghi thêm một task profile
vào `planbench.db` đang chạy — thêm mới, không sửa cái có sẵn, nhưng đó là DB
đang được chấm nên cần An đồng ý trước.

### C. Đổi cổng — **không dùng được**

401 đến từ chỗ request thiếu header, không liên quan cổng. Đổi 8000 sang 8080
thì vẫn đúng đoạn code đó chạy, vẫn thiếu đúng header đó. Bản desktop (API tự
phục vụ web trên cùng origin) cũng không cứu được — vẫn là `lib/api.ts` đó.

Cổng chỉ dính tới CORS, mà CORS hỏng thì lỗi là `blocked by CORS policy` trong
console, không phải body JSON `missing bearer token` từ chính API.

### D. Không làm gì

Chấp nhận web hỏng, chỉ ship phần API. Không đề nghị: merge vào `main` sẽ đưa
một web hỏng lên `main`, và `tests/api` **không bắt được** vì test API không mở
trình duyệt — đó chính là lý do lỗi này sống tới hôm nay.

---

## 6. Việc bên lề phát hiện cùng lúc

Hai bug **có sẵn trên `main`**, không do nhánh role, không chặn ship, nhưng nên
mở issue kẻo trôi:

- `routers/decisions.py:1356` gọi `service.trace_summary(...)`. Grep toàn repo:
  đúng **một** dòng gọi, **không có** định nghĩa ở merge-base, ở `main`, ở nhánh
  role. Ai gọi route đó đều nhận 500 thay vì 404.
- `test_decision_export_golden` fail hai case tiếng Anh trên cả `main`. Hoặc ai
  đó đổi output mà quên `WRITE_GOLDEN=1`, hoặc output phụ thuộc môi trường.

---

## 7. Trạng thái test nhánh role

`tests/api`: **6 failed, 1010 passed, 4 skipped** (47 phút). Không lỗi nào do
nhánh sinh ra:

| Test | Loại |
|---|---|
| `test_api_advice::test_an_unknown_run_is_a_404` | pre-existing, có trên `main` |
| `test_decision_export_golden` ×2 | pre-existing, có trên `main` |
| `test_api_plugin_catalogue::…same_version_is_refused` | flaky — chạy riêng thì pass |
| `test_api_plugin_lifecycle::…same_bytes_are_refused` | flaky — chạy riêng thì pass |
| `test_decision_markdown::…says_it_is_a_download` | flaky — chạy riêng thì pass |

Ba cái flaky cùng một nhóm "cùng byte thì từ chối": dấu thời gian trong zip có
độ phân giải **2 giây**, nên cùng một bundle đóng gói hai lần ở hai bên ranh
giới giây chẵn ra hai archive khác nhau.

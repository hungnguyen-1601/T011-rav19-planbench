# Sửa lỗi 401 trên nhánh `tongduyan_roles-capabilities`

Ngày 2026-08-28 · **đã sửa code**, chưa commit

Khảo sát gốc: [`notes/2026-08-28/tongduyan_loi-401-tren-nhanh-role.md`](../../notes/2026-08-28/tongduyan_loi-401-tren-nhanh-role.md).
Làm theo **phương án A** trong đó.

---

## 1. Chẩn đoán — kiểm lại, không tin sẵn

Khảo sát của An đúng cả hai lỗ. Tôi kiểm lại từng cái trước khi sửa,
không nhận báo cáo làm bằng chứng:

| Khẳng định | Cách kiểm | Kết quả |
|---|---|---|
| `lib/api.ts:59` không gắn `Authorization` | đọc `request()` | đúng — chỉ có `Content-Type` |
| `wsUrl` dựng URL trần, không xin ticket | đọc `api.ts:43` + `useEpisodeStream.ts:100` | đúng |
| Route thật sự từ chối | `curl /api/v1/maps` không token | **401**, có token **200** |
| Đúng call làm hỏng trang Deployments | `POST /scenarios/preview` | không token **401**, có token **422** (qua auth, body rỗng) |
| Ticket endpoint có thật, đúng hình dạng | `POST /api/v1/ws/tickets` | `{"ticket":"…","expires_in":60}` |

Chạy trên chính API đang chạy của An (cổng 8000), không dựng process thứ
hai.

**Một điểm khảo sát chưa nêu mà tôi kiểm thêm:** có còn client nào khác
gọi API mà không mang token không. Quét mọi chỗ gọi `fetch(${API_BASE}`,
`XMLHttpRequest`, `new WebSocket` — `models.ts`, `plugins.ts`,
`reports.ts` đều đã gắn. Chỉ còn hai chỗ vô danh, và **cả hai là cố ý
đúng**: `DeploymentBanner` gọi `/health` (route mở, phải lên được trước
khi ai đăng nhập), và ba route auth trước lúc đăng nhập. Nên `api.ts`
là lỗ cuối cùng, không phải lỗ đầu tiên trong một dãy.

---

## 2. Đã sửa gì

### 2.1. `lib/api.ts` gắn token

`request()` giờ đọc session mỗi lần gọi và gắn `Authorization`, và gặp
401 thì `clearSession()` — giống hệt `authFetch` đã làm.

Đọc **mỗi request** chứ không bắt một lần lúc module nạp: một tab mở
xuyên qua lúc đăng xuất sẽ tiếp tục gửi token server đã thôi chấp nhận,
và lỗi đó đọc như lỗi server.

Gắn ở **một chỗ** chứ không để 14 hàm tự nhớ. Ở client này không có khái
niệm "call không cần danh tính" — `/health` được gọi thẳng, không đi qua
module này.

### 2.2. Tách `API_BASE` sang `lib/origin.ts`

Đây là phần khảo sát nêu đúng và là phần dễ làm ẩu nhất.

`auth.ts` import `API_BASE` từ `api.ts`. Nếu `api.ts` import ngược
`loadSession` từ `auth.ts` thì hai module import vòng. ESM chịu được
vòng, nhưng **thứ tự khởi tạo khi đó phụ thuộc bundler chạm module nào
trước**, và một `const` bị đọc trong cửa sổ đó ra `undefined` chứ không
ném lỗi — tức là hỏng im lặng, đúng loại lỗi vừa mất một buổi để tìm.

Nên `API_BASE` ra module riêng, không import gì:

```
origin.ts  →  (không import gì)
auth.ts    →  origin.ts
api.ts     →  origin.ts, auth.ts
```

`api.ts` **re-export** `API_BASE`, nên hơn hai chục chỗ đang viết
`from "@/lib/api"` không phải sửa dòng nào. Dời một hằng số không phải
lý do để đụng vào 20 file.

### 2.3. `wsUrl` thành async và xin ticket

```ts
export async function wsUrl(simulationId, pace = false): Promise<string> {
  const { ticket } = await request<Ticket>("/ws/tickets", { method: "POST" });
  ...&ticket=${encodeURIComponent(ticket)}
}
```

Xin **mỗi lần kết nối**, không cache: ticket bị tiêu lúc connect, nên
reconnect cần cái mới, và cái giữ từ lần tải trang trước thì đã quá một
phút.

### 2.4. `useEpisodeStream` — chỗ dễ sinh bug mới nhất

Mở socket giờ tốn một round trip trước. Trong cửa sổ đó, người dùng có
thể chọn episode khác hoặc component unmount. Nếu cứ `await` rồi mở
socket, **ticket của lần bỏ dở vẫn về, vẫn mở socket**, và hai socket
cùng ghi frame vào một chỗ state.

Thêm `attemptRef`: `closeSocket()` tăng nó lên, callback so lại trước
khi mở. Mọi đường bỏ cuộc đều đi qua `closeSocket`, nên không phải nhớ
thêm chỗ nào.

Lỗi lúc xin ticket hiện **câu của server** chứ không phải
`"WebSocket connection failed"` — "chưa đăng nhập" và "không có quyền
chạy mô phỏng" là hai chuyện khác nhau, và câu kia không nói cái nào.

### 2.5. `"use client"` cho `api.ts`

Cho khớp `auth.ts`, `plugins.ts`, `reports.ts`. Đã kiểm: không server
component nào import `@/lib/api`.

---

## 3. Test — để lần sau đóng cửa mà quên phát chìa thì test kêu

**Mới: `lib/__tests__/credentials.test.ts` (10 test).**

Khẳng định **luật**, không khẳng định hành vi của một client: *module
gọi API thì gắn token*. Cụ thể — cả hai client đều gắn, đều đọc session
theo từng request, đều `clearSession()` khi 401; hai client không import
vòng; socket xin ticket chứ không nhét token vào URL; và attempt đã bỏ
thì không được nối.

Lý do viết theo kiểu này: luật đó **chưa từng được ghi ở đâu test chạm
tới được**, và đó chính xác là vì sao đóng được cửa mà quên phát chìa.
`charts-and-export.test.tsx` đã khẳng định `reports.ts` phải gắn header
— quy ước có sẵn, `api.ts` là ngoại lệ bị quên.

**Sửa: `lib/__tests__/api-base.test.ts` (5 → 7 test).**

Hai case `wsUrl` đang ghim hàm đồng bộ; giờ `await`, stub `fetch` trả
ticket, và assert cả URL lẫn việc nó gọi `POST /ws/tickets`. Thêm hai
case: gọi đúng endpoint đúng method, và **escape** ticket (giá trị cần
escape sẽ cắt cụt query string trong im lặng).

Stub `window` phải thêm `sessionStorage` — client giờ đọc session mỗi
request, thiếu nó thì `readStorage` ném `TypeError`.

### Nghiệm thu

```
npx tsc --noEmit                     → sạch (trừ 3 lỗi paper.* có sẵn)
credentials.test.ts                  → 10 pass
api-base.test.ts                     → 7 pass
```

Chạy toàn bộ `src/lib` + `src/components` + `src/app`:
**28 fail / cùng 10 file** — **trùng khít nền** đo được ở `f10fb1a`.
Không sinh lỗi mới. (Danh sách nền: `advisory-ui` 8, `candidates-page`
4, `decision-prose` 3, `decisions-page` 4, `deployments-page` 1,
`models-page` 1, `running-comparison` 2, `tokens` 2, `trace-viewer` 2,
`agent-dock` 1.)

Không chạy full suite backend — không đụng dòng Python nào.

---

## 4. Chưa làm, và vì sao

**Chưa commit.** Luật: chỉ commit khi An bảo.

**Chưa bấm thử trên trình duyệt.** Server là của An, em không tự
restart. Cần An reload trang Deployments để xác nhận banner đỏ biến mất
— `curl` chứng minh route qua được auth, nhưng nó không chứng minh
trang vẽ đúng.

**Chưa sửa hai bug bên lề An phát hiện** — cả hai có sẵn trên `main`,
ngoài phạm vi lỗi này:

- `routers/decisions.py:1356` gọi `service.trace_summary(...)` không tồn
  tại ở đâu → route đó trả 500 thay vì 404.
- `test_decision_export_golden` fail hai case trên cả `main`.

**Ba test flaky nhóm "cùng byte thì từ chối"**: em đã ghim
`ZipInfo(date_time=…)` cho một đường import ở phase trước, nhưng ba test
An gặp nằm ở đường khác (`test_api_plugin_catalogue`,
`test_api_plugin_lifecycle`, `test_decision_markdown`). Cùng nguyên nhân
— dấu thời gian zip độ phân giải 2 giây — chưa ghim.

---

## 5. File đã đụng

| File | Việc |
|---|---|
| `apps/web/src/lib/origin.ts` | **mới** — giữ `API_BASE`, cắt vòng import |
| `apps/web/src/lib/api.ts` | gắn token, `clearSession` khi 401, `wsUrl` async xin ticket, re-export `API_BASE` |
| `apps/web/src/lib/auth.ts` | import `API_BASE` từ `origin.ts` |
| `apps/web/src/lib/useEpisodeStream.ts` | await ticket, `attemptRef` chặn attempt đã bỏ, lỗi nói đúng nguyên nhân |
| `apps/web/src/lib/__tests__/credentials.test.ts` | **mới** — 10 test |
| `apps/web/src/lib/__tests__/api-base.test.ts` | 2 case sửa, 2 case thêm |

Không đụng file nào dưới `apps/api/`.

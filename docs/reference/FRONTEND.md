# Frontend

`apps/web` — Next.js 15 + React 19 + TypeScript. Nguyên tắc xuyên suốt:
**UI chỉ render, không tính toán.** Không có mảnh logic simulator nào ở
client; mọi metric, mọi phán quyết đều do backend tính và UI chỉ hiển
thị. Nhờ vậy không bao giờ có chuyện số trên màn hình lệch số trong
report.

## Trang

Đối chiếu `apps/web/src/app/` ngày **2026-08-31**.

| Route | Vai trò |
|---|---|
| `/` | Dashboard |
| `/maps`, `/maps/[id]` | Map editor Canvas 2D |
| `/scenarios`, `/scenarios/[id]` | Mission và vật cản động |
| `/library` | Thư viện scenario dựng sẵn + import + preview 2.5D |
| `/deployments` | Khai thế giới cần đo — map, robot, cảm biến, ngưỡng, trọng số |
| `/candidates` | Đăng ký ứng viên đem ra so |
| `/simulate` | Sân thử: chạy một episode, xem trực tiếp qua WebSocket |
| `/decisions`, `/decisions/[id]` | **Trung tâm sản phẩm.** Chạy phép so, cổng G1–G6, Decision Card, tầng giải thích, replay đôi, xuất báo cáo |
| `/algorithms` | Catalogue thuật toán và trạng thái plugin |
| `/models` | Model registry (PPO) và robot profile |
| `/reviews` | Hàng chờ duyệt: nhận, đọc, ký duyệt, từ chối |
| `/agent` | Agent console: chat, evidence, report |
| `/guide`, `/guide/[slug]` | Hướng dẫn vận hành trong app |
| `/admin/users`, `/admin/audit` | Cấp/thu quyền, nhật ký phân quyền |
| `/settings` | Cấu hình người dùng |
| `/system` | Phiên bản, trạng thái API (chỉ development) |
| `/login` | Nút Google / GitHub (render từ `/auth/providers`), dev login khi bật |
| `/auth/callback` | Đổi code dùng một lần lấy session, rồi `router.replace` |
| `/welcome` | Chọn nickname lần đầu, kiểm trùng theo ký tự (debounce 250 ms) |

### Ba route đã bị gỡ

`/benchmarks`, `/benchmarks/[id]` và `/leaderboard` **không còn tồn tại**
(gỡ ở đợt P6). Việc chúng làm nay nằm ở `/decisions` và `/candidates`.
Endpoint API tương ứng vẫn còn nhưng đã `deprecated` — xem
[api.md](api.md).

`/leaderboard` bị bỏ hẳn chứ không chuyển chỗ: xếp hạng ngoài ngữ cảnh
một deployment cụ thể là đúng cái phép so không cùng điều kiện mà nền tảng
này tồn tại để chặn.

## 2.5D

"2.5D" đúng theo nghĩa spec dùng: thế giới **thật sự phẳng**
(x, y, theta), chiều thứ ba chỉ để trình bày — tường được đùn lên một
độ cao cố định để đọc occupancy như khối thay vì như màu. Không có đại
lượng mô phỏng nào suy ra từ độ cao, và không có gì phản hồi lại vật lý.

Tách làm hai phần:

- **`src/lib/scene25d.ts`** — hình học thuần: phép chiếu trực giao, thứ
  tự vẽ, đùn tường, marker robot. Đây là phần dễ sai một cách âm thầm
  nên nó là phần được unit-test (23 test).
- **`src/components/Scene25D.tsx`** — renderer: chỉ chọn màu và nét vẽ.

Phép chiếu:

```
screen.x =  (x - y) * cos(azimuth) * scale
screen.y = -(x + y) * sin(elevation) * scale - z * scale
```

**Thứ tự vẽ dùng `x + y`, không dùng `sy`.** Dưới phép chiếu này một ô
chỉ bị che bởi ô có `x + y` lớn hơn, nên tổng đó sắp thứ tự toàn phần
cho cả cảnh. Sắp theo `sy` sẽ sai: mặt trên của một bức tường cao có
`sy` nhỏ nhưng vẫn thuộc phía sau thứ đứng trước nó.

**Ô UNKNOWN vẽ phẳng, không đùn lên.** Unknown là *thiếu thông tin*;
đùn nó lên sẽ đọc thành vật cản mà thực ra không biết là có.

**Renderer là Canvas 2D.** Với một occupancy grid
đùn lên, cảnh là vài nghìn quad lồi có thứ tự độ sâu toàn phần —
painter's algorithm xử lý *chính xác*, không cần depth buffer, và không
thêm dependency nào. Quan trọng hơn: `Scene25D.tsx` là file **duy nhất**
biết mình đang vẽ bằng gì. Đổi sang WebGL/React Three Fiber về sau chỉ
thay file đó; `scene25d.ts` và toàn bộ test của nó không đổi.

Spec liệt kê Three.js trong tech stack. Đã cân nhắc và **quyết định
giữ Canvas 2D** (2026-07-30, người dùng chọn). Đánh đổi đã chấp nhận:
không occlusion culling, không ánh sáng/bóng đổ. Xem
`KNOWN_LIMITATIONS.md` mục 44–45.

## Component dùng lại

| Component | Vai trò |
|---|---|
| `MapCanvas` | Top-down Canvas 2D: map, plan, trajectory, robot |
| `Scene25D` | Cùng dữ liệu, nhìn nghiêng, có slider rotate/tilt/wall-height |
| `FailureFindings` | Finding + evidence + **confidence hiển thị nổi** |
| `JobProgress` | Poll job khi đang chạy, dừng poll khi kết thúc, cancel |
| `MetricsPanel` | Metric của một episode |
| `SessionBar` | Avatar + nickname + email, badge Review Inbox, logout |
| `SendForReview` | Modal: nickname (autocomplete), stage, lời nhắn |
| `AppShell` | Khung của mọi trang: sidebar + top bar + main |
| `Sidebar` | Rail điều hướng; dưới 900px là drawer |
| `TopBar` | Tiêu đề trang, breadcrumb, ngôn ngữ, theme, badge duyệt, avatar |
| `Menu` | Dropdown dùng chung: Escape, click ra ngoài, `menuitemradio` |
| `ThemeSwitcher` / `LanguageSwitcher` / `UserMenu` | Ba control trên top bar |
| `StatCard` / `EmptyState` / `QuickActions` / `SystemStatus` | Khối của Dashboard |
| `StateBadge` | Trạng thái benchmark, đã dịch, `title` giữ giá trị gốc |
| `Icon` | Bộ SVG inline (không thêm dependency) |

`FailureFindings` cố ý làm `confidence` nổi bật: một finding `low` là
**giả thuyết** khớp dữ liệu, không phải kết luận, và người đọc không
thấy điều đó sẽ tin quá mức.

`JobProgress` ngừng poll ngay khi job vào trạng thái kết thúc — một
timer cứ chạy vào job đã xong chỉ là tải vô ích.

## Leaderboard: vì sao không phải một bảng phẳng

Hai dòng chỉ có nghĩa khi cạnh nhau nếu chúng cùng `conditions_checksum`.
UI vì thế **luôn** nhóm, không bao giờ render một bảng duy nhất — làm
thế là mời người đọc so sánh xuyên điều kiện, đúng thứ mà fairness
record tồn tại để ngăn.

Khi bỏ tick "accepted results only", trang hiện cảnh báo đỏ: đó là kết
quả chưa ai nhận, không được publish thành kết luận.

## Đăng nhập và quyền (M11)

Trang login **không** có cờ build-time nào cả: nó gọi `/auth/providers`
và chỉ vẽ nút mà server thật sự bật. Deployment chưa cấu hình Google thì
không có nút Google — thay vì có nút dẫn tới trang lỗi.

Browser giữ đúng hai thứ trong `sessionStorage`: token PlanBench và
profile để hiển thị. **Không** giữ access token của provider, không giữ
client id, không giữ secret. Callback trả về một code dùng một lần chứ
không phải JWT, nên token không nằm lại trong history hay Referer.

`canRun` / `canAcceptResult` trong `lib/reviews.ts` quyết định **hiện**
nút, không quyết định **cho phép**. Backend kiểm tra độc lập trên mọi
request, và mỗi trường hợp trong hai hàm đó đều có một test API tương
ứng chứng minh server tự từ chối. Ẩn nút chỉ để người dùng không bấm vào
thứ chắc chắn sẽ lỗi.

## Agent console

Ba điểm cẩn thận, vì làm sai sẽ vô hiệu hoá bảo đảm mà backend cưỡng chế:

1. **Luôn hiện provider nào trả lời.** `deterministic: true` nghĩa là câu
   trả lời khớp từ khóa offline, không phải model viết. Người đọc không
   bao giờ phải đoán.
2. **Mission bị từ chối render thành refusal kèm lý do**, không phải lỗi
   và không phải kết quả rỗng.
3. **Không có nút approve ở đây.** Agent không tự mở gate được, trang
   này cũng vậy. Chủ sở hữu mở gate bằng nút **Run** ở trang benchmark
   detail — được ghi vào audit trail là `self_approved`, khác với
   `approve` của người thứ hai, nên đọc lịch sử luôn phân biệt được.

## Chạy

```bash
# Terminal 1 — backend
PYTHONPATH="packages/schemas:packages/planning:packages/metrics:\
packages/benchmark:services/simulator:services/tracking:\
services/agent_service:ml:apps/api" \
  .venv/bin/uvicorn planbench_api.main:app --port 8000

# Terminal 2 — frontend
cd apps/web && npm run dev          # http://localhost:3000
```

`NEXT_PUBLIC_API_URL` trỏ tới backend (mặc định `http://localhost:8000`).

```bash
cd apps/web
npm run typecheck    # tsc --noEmit
npm test             # vitest
npm run build        # next build
```

## Nếu về sau muốn đổi sang Three.js

```bash
cd apps/web && npm install three @react-three/fiber @types/three
```

Rồi viết lại **một** file `src/components/Scene25D.tsx` để tiêu thụ
`Scene25D` từ `scene25d.ts` (facets → mesh/instanced geometry).
`scene25d.ts` và 23 test của nó không cần sửa. Đây là lý do phần hình
học được tách ra ngay từ đầu.


## App shell (M12)

Trước M12, `layout.tsx` tự viết sidebar bằng tay và mọi trang tự lo phần
còn lại. Giờ có `AppShell`: một chỗ sở hữu sidebar, top bar và badge
duyệt. Trang chỉ render nội dung.

`/login`, `/welcome`, `/auth/callback` **không** dùng shell — một rail
điều hướng mà mọi link đều bật về trang đăng nhập thì tệ hơn là không có.

### Sidebar thu gọn được

Trạng thái nằm ở **một attribute trên `<html>`**, còn **chiều rộng nằm
trong CSS** khớp theo attribute đó. React không bao giờ set pixel. Đó
chính là thứ cho phép script chặn render trong `<head>` áp dụng trạng
thái đã nhớ **trước khi paint lần đầu** — người dùng thu gọn sidebar hôm
qua không phải nhìn nó trượt đóng mỗi lần tải trang hôm nay.

| | Mở rộng | Thu gọn |
|---|---|---|
| Chiều rộng | 264 px | 68 px |
| Hiển thị | icon + tên + mô tả + tài khoản | chỉ icon |
| Tooltip | không (thừa) | có, kèm `aria-label` |
| Active | `aria-current="page"` + thanh dọc bên trái | như trên |

Dưới 900px sidebar thành drawer: hamburger ở top bar mở, click overlay
hoặc **Escape** đóng, và **đổi route tự đóng**. Lúc đó chế độ thu gọn
desktop bị vô hiệu — icon-only chồng lên drawer là vô nghĩa.

### Theme

Ba chế độ: Light, Dark, System. Mặc định System.

Cái khó duy nhất là **flash**. React không giúp được: tới lúc nó hydrate
thì trình duyệt đã paint. Nên theme đã resolve được đóng dấu lên
`<html data-theme>` bởi một script chặn render trong `<head>`
(`lib/theme-script.ts`), và **mọi màu trong stylesheet đều key theo
attribute đó**. Store React chỉ điều khiển UI của nút chọn.

`theme-script.ts` cố tình **không** import gì và **không** phải module
`"use client"`: nó chặn render nên mọi byte đều phải trả giá, và
`layout.tsx` là server component nên không gọi được vào client graph.

`System` giữ đúng nghĩa: có listener `prefers-color-scheme`, laptop tối
đi lúc hoàng hôn thì trang cũng tối theo.

Màu tập trung ở CSS variables (`--bg`, `--panel`, `--text`, `--accent`,
…). Không còn hex nào nằm ngoài khối token — kiểm được bằng
`grep -nE "#[0-9a-fA-F]{3,8}" globals.css`.

### i18n

`en` và `vi`, file JSON riêng ở `lib/i18n/locales/`. Thiếu key thì rơi về
tiếng Anh; thiếu ở cả hai thì render ra chính key (xấu có chủ ý — để bị
phát hiện, không phải để giấu).

Locale nằm ở **cookie**, không phải localStorage. Đây là quyết định đáng
chú ý nhất: chữ do React render, nên nếu server không biết ngôn ngữ thì
nó render tiếng Anh rồi browser sửa lại một frame sau — mỗi lần tải
trang, với mọi người dùng Việt. Cookie là preference duy nhất server đọc
được **trong lúc** render.

Vì thế `lib/i18n/shared.ts` (dictionary + tra cứu + parse cookie) **không
phải** module `"use client"`, còn `lib/i18n/index.ts` (store, context,
hook) thì phải. Nhầm chỗ này thì `tsc` và `next build` đều **không** bắt
được — chỉ khởi động server thật mới lộ.

Không dịch: benchmark ID, tên thuật toán (A*, DWA, PPO), API path,
conditions checksum, citation ID, dữ liệu người dùng nhập, nội dung báo
cáo AI sinh ra.

### Icon

Bộ SVG inline (`components/Icon.tsx`), không thêm dependency. Project
chưa cài thư viện icon nào; thêm một cái để dùng 25 glyph là một
dependency và một bundle phải trả giá. Chúng vẽ theo đúng quy ước của
Lucide (lưới 24×24, nét 2px, đầu bo tròn) nên sau này đổi sang
`lucide-react` là find-and-replace, không phải thiết kế lại.

Mọi icon đều `aria-hidden`: icon không bao giờ là accessible name — thứ
bọc nó mới mang label.

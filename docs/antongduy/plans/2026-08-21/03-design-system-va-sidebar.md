# Plan 3 — Design system + Sidebar toàn app

Ngày lập: 2026-08-21 · Trạng thái: **chờ An duyệt**
Nguồn: [note đánh giá](../../notes/2026-08-21/tongduyan_danh-gia-ui-trang-decision-detail.md) mục B, C và QA #4, #11, #15, #16, #19–#25.

## Mục tiêu

Dựng một hệ thiết kế có thang, rồi kéo mọi trang về hệ đó. Sidebar nằm trong plan
này vì nó là chrome dùng chung, không thuộc trang nào.

## Ngoài phạm vi

- Nội dung / cấu trúc trang decision detail → Plan 2.
- Defect token, i18n, focus → Plan 1.
- Dark theme **không** được thiết kế lại. Chỉ giữ nó chạy được sau khi đổi token.

## Phụ thuộc

Plan 1 xong (T2 định nghĩa `--font-mono`, plan này thay stack của nó bằng webfont).

**Quan hệ với Plan 2**: giai đoạn A là điều kiện cho Plan 2 — nhưng **không phải
cả ba bước đều vô hình**. Nạp font (B0) và toàn bộ B, C, D chạy **sau** Plan 2.

```
Plan 1 ──► Plan 3 A2 + A4  (token, zero-diff)          ──┐
       ──► Plan 3 A3       (đổi màu candidate, CHỤP RIÊNG) ──► Plan 2 ──► Plan 3 B0/B/C/D
```

| Bước | Đổi hình? |
|---|---|
| **A2** thang spacing/radius/typography/`--font-sans` | không — zero-diff |
| **A3** tách `--candidate-a/b` khỏi `--accent` | **có** — visual prerequisite, chụp trước/sau riêng |
| **A4** biến thể `.notice` | không — zero-diff |

---

## Giai đoạn A — Thêm token

**A2 và A4 chỉ khai báo** — chưa chỗ nào dùng, nên không trang nào đổi hình,
zero-diff thật, kiểm được bằng screenshot.

**A3 thì không.** `--candidate-a/b` đang được dùng ở `globals.css:2074-2079`,
`3172-3173`, `3188`, `3193`, nên đổi giá trị chúng là **đổi màu trên màn hình
ngay**. A3 nằm ở giai đoạn A vì nó là việc của tầng token, không phải vì nó vô
hình. Chụp trước/sau cho A3 như một thay đổi hình bình thường.

Nạp font (trước là A1) đổi mặt chữ toàn app
nên **đã chuyển xuống giai đoạn B thành B0** — nhờ vậy Plan 2 chỉ cần phụ thuộc
A2–A4 và không phải nuốt thay đổi font trước ngày demo.

### A2 — Thang spacing / radius / typography

Thêm vào `:root` chung (ngoài các block `[data-theme]` — không đổi theo theme):

```css
--space-1: 4px;  --space-2: 8px;  --space-3: 12px;
--space-4: 16px; --space-5: 24px; --space-6: 32px; --space-7: 48px;

--radius-sm: 4px; --radius-md: 6px; --radius-lg: 8px;

--fs-caption: 11px; --fs-sm: 12px;  --fs-body: 13px;
--fs-label:   14px; --fs-value: 16px; --fs-h3: 18px; --fs-h1: 24px;

--shadow-pop: var(--shadow);
```

**`--shadow-pop` phải dẫn xuất, không hard-code.** Bản trước viết
`0 4px 12px rgba(20,24,31,.10)` với `/* dark: rgba(0,0,0,.45) */` — nhưng phần
dark chỉ là **comment, không phải rule**, nên token này sẽ dùng shadow của light
trên dark theme: một vệt xám nhạt trên nền tối, gần như vô hình. Cùng đúng loại
lỗi A3 vừa sửa, và cùng bỏ sót đường OS-light.

`--shadow` đã khai đủ **cả ba** đường theme (`globals.css:55`, `:104`, `:148`),
nên `var(--shadow)` tự đúng ở mọi trạng thái. Nếu popover cần bóng **nhẹ hơn**
`--shadow`, thì khai `--shadow-pop` riêng ở **cả ba** đường — không phải hai — chứ
đừng đặt một giá trị chung rồi ghi chú giá trị kia.

**Nghiệm thu**: tooltip/popover nhìn được ở `data-theme="light"`,
`data-theme="dark"`, và **không** `data-theme` + OS light.

**Khai luôn `--font-sans` ở đây, không đợi B0.** Plan 1 T6 đã chốt hợp đồng: token
**công khai** (`--font-sans`, `--font-mono`) luôn được khai trong `globals.css`,
`next/font` chỉ sinh token tên riêng `--font-*-loaded`, và Plan 3 **chỉ đổi giá
trị** alias chứ không tạo mới khai báo. `--font-mono` đã theo đúng hợp đồng đó
(`globals.css:162`); `--font-sans` thì chưa được khai ở đâu cả, mà **Plan 2 T5
dùng nó** cho slot đơn vị — Plan 2 chạy trước B0, nên test token của Plan 1 sẽ đỏ.

Sửa bằng cách tách làm hai bước đúng như `--font-mono` đã làm:
**Giá trị phải chép NGUYÊN VĂN stack đang chạy** (`globals.css:175`):
```css
/* A2 — đúng stack hiện hành, chỉ là giờ nó có tên. Chưa webfont nào */
--font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
```
Không thêm `Inter` vào đầu: máy nào **đã cài sẵn** Inter sẽ đổi mặt chữ ngay lúc
Plan 2 dùng `--font-sans` — zero-diff hỏng, và hỏng ở một số máy chứ không phải
mọi máy, tức là kiểu hỏng khó truy nhất. Cũng không được rơi `-apple-system`:
đó là mắt xích chọn San Francisco trên Safari/macOS cũ, mất nó là đổi mặt chữ
trên đúng những máy đó.

**B0 chỉ bọc `var()` quanh đúng stack đó**, không sửa gì khác trong ngoặc:
```css
--font-sans: var(--font-sans-loaded, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif);
```
Diff của B0 khi đó đọc được bằng mắt là "thêm alias", không phải "thay trọn một
dòng" — và không lẫn một thay đổi fallback nào vào giữa.

### A3 — Tách `--candidate-a/b` khỏi `--accent`

Hiện `--candidate-a: var(--accent)`. Xanh dương vừa nghĩa "link/tương tác" vừa
nghĩa "Candidate A".

**Sáu token này KHÔNG được khai ở `:root` — chúng đang bị hai scope cục bộ ghi
đè**, và scope cục bộ thắng `:root` bất kể thứ tự:

| Scope | Dòng | Giá trị |
|---|---|---|
| `.decision-page` | `globals.css:2046-2052` | `--candidate-a: var(--accent)`, `--candidate-b: var(--purple)`, cùng `-soft` / `-border` |
| `.episode-comparison` | `globals.css:3095-3101` | hard-code `#2563eb` / `#7c3aed`, cùng `-soft` / `-border` |

Nghĩa là: **thêm màu mới vào theme block thôi thì A3 không đổi được gì cả** —
hai khối trên vẫn thắng, trang decision giữ nguyên xanh/tím, và bước này trông
như đã xong trong khi chưa xảy ra gì.

**Và KHÔNG hard-code hex theo từng theme block — có ba đường theme, không phải
hai:**

| Đường | Vị trí |
|---|---|
| dark mặc định | `:root`, `:root[data-theme="dark"]` (`globals.css:15-16`) |
| light do người dùng chọn | `:root[data-theme="light"]` (`:62`) |
| **light theo OS, chưa ai chọn gì** | `@media (prefers-color-scheme: light) { :root:not([data-theme]) }` (`:108-109`) |

Khai hex ở hai đường đầu là bỏ sót đường thứ ba: người **không** chọn theme mà OS
đang light sẽ nhận màu candidate của dark. Và đó là cấu hình mặc định của phần
lớn người mở link lần đầu — tức là ca hay gặp nhất lại là ca sót.

Cách đúng: **không đặt màu mới, dùng token semantic đã đi theo cả ba đường.**
Hai màu A3 muốn đã có sẵn, đúng từng hex:

| Token | dark | light + OS-light |
|---|---|---|
| `--indigo` | `#8fa5ff` | `#5267c9` |
| `--teal` | `#50c7ad` | `#087f6a` |

Đúng bốn giá trị bản trước định gõ tay. Nên A3 chỉ còn **một khối, ở `:root`
chung**, không đụng theme block nào:
```css
:root {
  --candidate-a: var(--indigo);
  --candidate-a-soft: var(--indigo-soft);
  --candidate-a-border: color-mix(in srgb, var(--indigo) 48%, var(--border));
  --candidate-b: var(--teal);
  --candidate-b-soft: var(--teal-soft);
  --candidate-b-border: color-mix(in srgb, var(--teal) 48%, var(--border));
}
```
`--indigo-soft` / `--teal-soft` cũng đã khai đủ ba đường (`:45-47`, `:94-96`,
`:138-140`), nên `-soft` và `-border` tự theo — đúng chỗ mà bản hard-code dễ khai
thiếu và cho ra **nền tím cũ ngồi cạnh chữ teal mới**.

Việc phải làm, hai phần:

1. Khối `:root` trên.
2. **Xoá hẳn** hai khối cục bộ `.decision-page` và `.episode-comparison`. Không
   để lại dạng alias `--candidate-a: var(--candidate-a)` — vô nghĩa và gây hiểu
   nhầm là còn có lý do tồn tại.

**Nghiệm thu A3** — bốn bề mặt × năm trạng thái theme:

Bề mặt: lưới so sánh · thẻ trace · chấm chú giải (`:3172-3173`) · hàng episode
được chọn (`:3188`, `:3193`). Bốn chỗ này đọc token qua bốn đường khác nhau, nên
một chỗ sót không kéo theo ba chỗ kia lộ ra.

Trạng thái theme:
- [ ] `data-theme="dark"`
- [ ] `data-theme="light"`
- [ ] **không** `data-theme`, OS **light**
- [ ] **không** `data-theme`, OS **dark**
- [ ] explicit vẫn thắng OS: đặt `data-theme="dark"` khi OS đang light → ra màu dark

### A4 — Ba biến thể `.notice`

`globals.css:1112` hiện một class duy nhất, nền vàng, dùng cho cả ba mức.

Giữ `.notice` gốc **không đổi** ở giai đoạn A (để không phá 23 chỗ đang dùng),
**thêm**:
```css
.notice--info     { background: var(--panel-2);  border-color: var(--border); }
.notice--warn     { background: var(--warn-soft); border-color: color-mix(in srgb, var(--warn) 35%, transparent); }
.notice--critical { background: var(--err-soft);  border-color: var(--err); }
```
Giai đoạn B mới đổi `.notice` mặc định thành trung tính và gán biến thể cho từng
chỗ dùng.

**Nghiệm thu giai đoạn A**: chụp màn 6 trang trước/sau.
- Với **A2 + A4**: không khác một pixel.
- Với **A3**: khác đúng ở màu candidate (thẻ candidate, chấm chú giải, viền thẻ
  episode) và **không khác chỗ nào ngoài đó**. Đây mới là điều cần kiểm — A3 dễ
  vô tình kéo theo mọi chỗ đang mượn `--accent` làm màu Candidate A.

---

## Giai đoạn B — Áp dụng. Đây là phần đổi hình.

Chạy **sau** Plan 2. Chạm mọi trang, cần kiểm mắt từng trang.

### B0 — Nạp font (chuyển từ A1 xuống)

`apps/web/src/app/layout.tsx`

**Chốt: dùng `next/font/local` với `.woff2` commit vào repo.** Không dùng
`next/font/google`.

Lý do — và đây là chỗ bản trước hiểu sai: `next/font/google` tải font **lúc
build**, rồi mới self-host vào bundle. Fallback CSS chỉ cứu được ca **runtime**
không áp được font; nó không cứu được ca **build không có mạng**, vì lúc đó
`next build` **fail trước khi có CSS nào để rơi về**. "Demo offline thì có
fallback" là gộp hai chuyện khác hẳn nhau làm một.

Với một bản mang đi demo, build phải tái lập được kể cả khi mạng hỏng. `next/font/local`
cho đúng điều đó, không cần thêm package nào:

```ts
import localFont from "next/font/local";

const sans = localFont({
  src: [
    { path: "./fonts/BeVietnamPro-Regular.woff2",  weight: "400", style: "normal" },
    { path: "./fonts/BeVietnamPro-Medium.woff2",   weight: "500", style: "normal" },
    { path: "./fonts/BeVietnamPro-SemiBold.woff2", weight: "600", style: "normal" },
    { path: "./fonts/BeVietnamPro-Bold.woff2",     weight: "700", style: "normal" },
  ],
  variable: "--font-sans-loaded", display: "swap",
});
const mono = localFont({
  src: [
    { path: "./fonts/JetBrainsMono-Regular.woff2",  weight: "400", style: "normal" },
    { path: "./fonts/JetBrainsMono-Medium.woff2",   weight: "500", style: "normal" },
    { path: "./fonts/JetBrainsMono-SemiBold.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-mono-loaded", display: "swap",
});
```
Gắn `${sans.variable} ${mono.variable}` vào `<html className>`.

File `.woff2` **commit vào repo** dưới `apps/web/src/app/fonts/`. Cả hai font đều
là OFL — kèm `OFL.txt` cạnh chúng. Bảy file, cỡ vài trăm KB; đổi lại là build
không phụ thuộc mạng và ai clone về cũng dựng ra đúng một bản.

**Kèm manifest, nếu không thì "lấy đúng file `.woff2`" vẫn không tái lập được.**
Một binary không nguồn gốc trong repo là thứ không ai dám đụng và không ai kiểm
được: sáu tháng nữa không cách nào biết nó là bản nào, có phải subset Việt
không, hay ai đó đã thay nhầm. Viết `apps/web/src/app/fonts/README.md`:

```
Be Vietnam Pro
  Source:  https://github.com/bettergui/BeVietnamPro
  Pinned:  <tag hoặc commit SHA>
  Upstream files / local files:
    fonts/webfonts/BeVietnamPro-Regular.woff2  -> BeVietnamPro-Regular.woff2
    … (Medium / SemiBold / Bold)
  SHA-256: <mỗi file một dòng>
  License: OFL-1.1 (OFL.txt cạnh đây)

JetBrains Mono
  Source:  https://github.com/JetBrains/JetBrainsMono
  Release: v2.304
  Upstream files / local files: … (Regular / Medium / SemiBold)
  SHA-256: <mỗi file một dòng>
  License: OFL-1.1
```
Tag/commit chứ không phải nhánh: nhánh đổi dưới chân mình. Ghi cả tên file
upstream vì tên local có thể đã đổi lúc chép về, và không có nó thì không đối
chiếu ngược được.

Sinh hash bằng một dòng:
```powershell
Get-FileHash -Algorithm SHA256 apps/web/src/app/fonts/*.woff2 | Format-List Path, Hash
```

Nếu An muốn dùng `next/font/google` thay vào: được, nhưng phải ghi thành phụ
thuộc rõ ràng — **build cần mạng** — và chạy `npm.cmd run build` ngay sau B0 để
biết nó qua, chứ không đợi tới lúc dựng bản demo.

**Hợp đồng token — đã chốt ở Plan 1 T6, làm đúng theo, không bàn lại**:
`next/font` sinh token tên riêng `--font-*-loaded` (hai tên này nằm trong
`NEXT_FONT_PROVIDED` của `tokens.test.ts`). Token **công khai** vẫn khai trong
`globals.css`, giờ **sửa giá trị** thành alias — không xoá khai báo:
```css
--font-sans: var(--font-sans-loaded, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif);
--font-mono: var(--font-mono-loaded, ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace);
```
Phần trong `var()` sau dấu phẩy đầu tiên **giống hệt** giá trị A2 đã đặt — B0
không được nhân tiện sửa fallback, vì sửa ở đây là đổi mặt chữ trên đúng những
máy webfont không tải được, tức là chỗ không ai chụp màn kiểm.
Nhờ đó test token luôn thấy `--font-sans`/`--font-mono` được khai trong
`globals.css` — không plan nào phải nới test, và môi trường không tải được
Google Fonts rơi về stack hệ thống một cách tường minh.

**File `.woff2` phải là bản có bảng chữ Việt**, không phải bản `latin` gọn. Với
`next/font/google` thì đó là `subsets: ["latin", "vietnamese"]`; với bản local là
lấy đúng file subset đó xuống. Thiếu nó thì dấu rơi về font hệ thống giữa chừng
và lệch baseline. Đây là lý do chọn Be Vietnam Pro: nó được vẽ cho tiếng Việt,
dấu trên nguyên âm có mũ (`ế ồ ữ`) không chồng ở 12px.

**Nghiệm thu B0**:
- [ ] `npm.cmd run build` chạy được **sau khi ngắt mạng**. Đây là assertion của
      cả quyết định này; không chạy thử thì không biết nó đúng
- [ ] Hash từng file khớp manifest (chạy lại lệnh trên, so với `README.md`)
- [ ] Mở file Be Vietnam Pro bằng font inspector, xác nhận **có glyph tiếng
      Việt** (`ế ồ ữ ự ẫ`). Bản `latin` gọn vẫn build xanh, vẫn render — chỉ là
      dấu rơi về font hệ thống, và đó là lỗi phải nhìn mới thấy

### B1 — Base

```css
html, body {
  font-family: var(--font-sans);
  font-size: var(--fs-body);     /* 13px, từ 14px */
  line-height: 1.5;              /* tối thiểu 1.4 cho chữ có dấu */
}
```
Hạ base 13px là thứ tạo ra "semi-compact". Nó **thu nhỏ mọi trang cùng lúc** —
kiểm kỹ các trang nhiều chữ (`/system`, `/agent`, `/library`).

### B2 — `main.content` giới hạn bề rộng

`globals.css:372`
```css
main.content {
  max-width: 1440px; margin-inline: auto;
  padding: var(--space-5) var(--space-6) var(--space-7);
}
```
Một dòng, nhưng đây là fix P0 số 4 trong note: ở 1920 không có nó thì cột giá trị
phình lên 480px quanh một con số 6 ký tự.

Các trang có canvas (`/maps`, `/simulate`, `/deployments`) đang dựa vào bề rộng
không giới hạn, nên cần đường thoát.

**Đường thoát phải có cơ chế, không chỉ là lời cho phép.** `AppShell` sở hữu cố
định `<main className="content" id="main-content">` (`AppShell.tsx:133`) — trang
con **không có cách nào** tự thêm class lên phần tử đó. Câu "cho phép opt-out
bằng `main.content--wide`" ở bảng rủi ro là một lối thoát không tồn tại.

Chốt: `AppShell` tự quyết theo pathname.
```tsx
// AppShell.tsx — cạnh nơi đã đọc pathname cho trạng thái active
const WIDE_CONTENT_ROUTES = ["/maps", "/simulate", "/deployments"];
const wide = WIDE_CONTENT_ROUTES.some((route) => isActive(pathname, route));
<main className={wide ? "content content--wide" : "content"} id="main-content">
```
```css
main.content--wide { max-width: none; }
```
Dùng `isActive()` đã có (`navigation.ts:167`) để `/maps/abc` cũng rộng, không chỉ
`/maps`. Danh sách là **một hằng có tên** — thêm trang vào đó là sửa một mảng,
reviewer nhìn thấy; khác hẳn một class rắc rải trong từng page.

Cách còn lại — context để page tự khai — mạnh hơn nhưng phải thêm provider và
một `useEffect` set/cleanup ở mỗi trang rộng, tức là đúng bộ máy T11 của Plan 2
dựng cho breadcrumb, cho ba trang tĩnh không đổi. Không đáng. Nếu sau này số
trang rộng phụ thuộc dữ liệu chứ không phụ thuộc route thì mới chuyển.

**Test**: ánh xạ route → class là hàm thuần, test được trong Node —
`wideContent("/maps/abc") === true`, `wideContent("/decisions/x") === false`.
Kiểm mắt cả desktop lẫn mobile: ở mobile `max-width` không còn tác dụng nên hai
nhánh phải trông giống nhau.

### B3 — Topbar bỏ backdrop-filter

`globals.css:388-390` — `background: color-mix(...)` + `backdrop-filter: blur(8px)`.
Trên light theme cho ra một dải mờ đục và một compositing layer, không giải quyết
gì. Đổi `background: var(--bg)`, giữ viền dưới.

### B4 — Button

`globals.css:670-690`

- **`min-height: 32px`, KHÔNG phải `height: 32px`**, `padding: 0 var(--space-3)`,
  `--radius-md`, `--fs-body`, `600`
- `:hover` → `background: var(--hover)`. **Bỏ `border-color: var(--accent)`**
  (`globals.css:679`) — nó làm mọi nút trông như đang focus
- Bốn biến thể: `default` / `.primary` / `.ghost` / `.danger`
- `:focus-visible` → `outline: 2px solid var(--accent); outline-offset: 2px`

**Vì sao `min-height`:** repo có **99 `<button>`** trong `.tsx`, và một chiều cao
cứng cắt vào ít nhất năm loại đang chạy — nút icon, nút gập sidebar, nút phân
trang episode, control phát lại, nút compact trong header — cộng với
`.decision-copy-id` cao 20px mà Plan 2 vừa thêm. `height: 32px` không làm chúng
cao lên; nó **cắt nội dung** ở những nút có badge bên trong hoặc nhãn hai dòng.
`min-height` cho ra cùng một chiều cao ở ca thường mà không cắt ca ngoại lệ.

Kèm theo đó, ngoại lệ phải **có tên**, không phải để mỗi nơi tự chống:

| Class | Kích thước |
|---|---|
| `.icon-button` | 32×32, `padding: 0` |
| `.button--compact` | `min-height: 24px`, `--fs-sm` |
| `.decision-copy-id` | giữ compact 20px cho tới khi B nhập nó vào hệ button |
| nút nhãn nhiều dòng | được phép cao hơn 32px — đó là lý do dùng `min-height` |
| control trên canvas/toolbar | modifier riêng, không ăn theo mặc định |

**Và mục nghiệm thu "mọi hàng bảng cao 32px" phải thu hẹp lại** thành *bảng dữ
liệu một dòng*. Hàng của bảng evidence, hay hàng mang cảnh báo hai dòng, không
ép được vào 32px mà không cắt chữ — ép chúng là biến một luật về nhịp thị giác
thành một lỗi mất thông tin.

### B5 — Badge

`globals.css:768-790`, `931`

`border-radius: 10px` trên chữ 11px thành viên thuốc. Đổi `--radius-sm` (4px),
cao 20px, `--fs-sm`. Bốn biến thể: `neutral` / `ok` / `warn` / `err`.

Bỏ icon trong badge trừ khi badge đó là kết luận duy nhất của cả panel.
**Ảnh hưởng rộng** — badge dùng khắp app.

### B6 — Panel

`globals.css:665-670` — `--radius-lg`, `padding: var(--space-4)`,
`margin-bottom: var(--space-5)`, **không shadow**.

Rà `.dashboard-page .stat-card` (`globals.css:1444-1472`) đang có
`--dashboard-card-shadow` và `transform: translateY` khi hover. Bỏ cả hai.

### B7 — `.notice` gán biến thể

Đổi `.notice` mặc định sang trung tính, rồi đi hết 23 chỗ dùng
(`candidates`, `decisions/[id]`, `deployments`, `library`, `page.tsx`, `scenarios`,
`scenarios/[id]`, `DeploymentForm`, `TrafficEditor`) gán đúng mức.

Luật: `--critical` chỉ cho thứ **vô hiệu hoá mọi số bên dưới**. `--warn` cho
phạm vi hẹp. Mặc định cho thông tin.

### B8 — Input, tabs

- Input/select: cao 32px, `--radius-md`, focus ring `0 0 0 3px var(--accent-soft)`
- Tabs (`apps/web/src/components/Tabs.tsx`): underline, **không pill**.
  Active `box-shadow: inset 0 -2px 0 var(--accent)`

---

## Giai đoạn C — Sidebar

> **Inventory đúng: 12 mục hiện.** Bản trước ghi 14 và gắn `Legacy` cho
> `/algorithms`, `/benchmarks`, `/leaderboard`, `/scenarios`. Đã kiểm
> `navigation.ts`: **ba route đầu không còn trong sidebar** — chỉ `/scenarios`
> còn, và nó đang nằm trong nhóm `nav.section.retiring`. Mọi con số và danh sách
> dưới đây đã tính lại theo 12. Không đưa ba route đã xoá quay lại.
>
> **C1 và C2 đảo ngược một quyết định sản phẩm đã có, không phải sửa bug.**
> `navigation.ts:44-52` ghi rõ lý do của bản cũ (Plan 13-08 P1): mô tả hiện ra
> rail là cố ý, và `nav.section.retiring` *"deliberately visible rather than
> tidied away… Those pages still work and are still the only way to do some
> things"*. C1/C2 nói ngược lại cả hai.
>
> **Duyệt Plan 3 là duyệt luôn hai việc này** — nêu tách ra để không ai coi chúng
> là hệ quả kỹ thuật đi kèm: (1) bỏ mô tả hiện trên rail, (2) bỏ nhóm
> *"Being replaced"*. Và khi làm thì **sửa luôn comment `navigation.ts:44-52`**;
> nếu không, file sẽ mang một lời giải thích mạch lạc cho một thiết kế không còn
> tồn tại, và người sau sẽ tin nó.

### C1 — Bỏ mô tả khỏi rail

`apps/web/src/components/Sidebar.tsx:61`, `:84`

```tsx
const description = item.descriptionKey ? t(item.descriptionKey) : null;
...
{description ? <span className="sidebar-desc">{description}</span> : null}
```

12 mục × 1 câu ⇒ rail 60% văn xuôi, mục cuối rơi dưới fold.

**Sửa**: bỏ `<span className="sidebar-desc">`. Đưa `description` vào `title` của
`<a>`. **Giữ nguyên `descriptionKey` trong `navigation.ts` và giữ nguyên toàn bộ
khoá `nav.desc.*`** — chữ không mất, chỉ đổi chỗ.

Xoá `.sidebar-desc` (`globals.css:322-329`) và rule collapsed liên quan.

### C2 — Bốn nhóm còn ba

`apps/web/src/lib/navigation.ts:53-147`

| Hiện tại | Đổi thành |
|---|---|
| `nav.section.doing` — "What you are doing" | `nav.section.workspace` — "Workspace" |
| `nav.section.materials` — "Materials" | `nav.section.resources` — "Resources" (**khoá mới**) |
| `nav.section.retiring` — "Being replaced" | **bỏ nhóm**, dồn vào Resources |
| `nav.section.account` | giữ |

**Tạo khoá mới `nav.section.resources`, đừng đổi nội dung của
`nav.section.results`.** Bản trước định giữ tên khoá `results` rồi sửa giá trị
thành "Resources" — khi đó tên khoá nói "results", giá trị nói "Resources", và
người sau đọc khoá sẽ tin nhầm. Một khoá i18n mới là hai dòng JSON; một khoá nói
dối về nội dung của nó thì ở lại mãi.

Nếu `nav.section.results` sau đó không còn ai dùng thì xoá nó cùng lượt.

**"Being replaced" nói thẳng với giám khảo rằng sản phẩm dở dang.** Nhãn điều
hướng phải là danh từ chỉ nơi chốn.

### C3 — Chip `Legacy`

Thêm `legacy?: boolean` vào `NavItem` (`navigation.ts:13-30`). Bật cho
**`/scenarios`, và chỉ nó**.

`/algorithms`, `/benchmarks`, `/leaderboard` ở bản trước là inventory cũ — chúng
**đã bị xoá khỏi sidebar** rồi. Gắn `legacy` cho chúng nghĩa là phải thêm chúng
trở lại, tức là làm ngược mục tiêu rút gọn rail.

`Sidebar.tsx` render `<span className="badge neutral rail-legacy">` canh phải —
**dùng convention `.badge.neutral` như `.badge.ok` / `.badge.err` đang có**
(`globals.css:789`, `794`), không dùng `.badge--neutral`. B5 nói "bốn biến thể
neutral/ok/warn/err" mà không nói viết thế nào; chốt ở đây cho cả B5 lẫn C3: giữ
`.badge.<tên>`. Đổi sang `--` là một lượt rename toàn app, đáng làm riêng, không
làm lẫn vào đây.

Khoá i18n mới: `nav.legacy` (`Legacy` / `Cũ`).

Xoá hack CSS `opacity: .85` theo href (`globals.css:333-337`) — nó đang hard-code
ba đường dẫn vào stylesheet.

### C4 — Kích thước rail

`globals.css:200-215`, `:56-58`

`--sidebar-width: 264px` → `232px`. Mỗi mục cao `32px`, `padding: 0 var(--space-2)`.
Bỏ `<p className="tagline">` trong `.sidebar-brand` (`Sidebar.tsx:50`) — chuyển
`app.tagline` xuống trang `/system`.

Kết quả: **12 mục** × 32 + 3 tiêu đề nhóm ≈ 460px, vừa một màn 13" với chỗ dư.

### C5 — Test

`apps/web/src/components/__tests__/shell.test.tsx` và
`apps/web/src/lib/__tests__/navigation.test.ts` đang khẳng định cấu trúc 4 nhóm
và sự có mặt của description. **Cả hai sẽ đỏ.** Sửa test cùng lượt, không sửa sau.

---

## Giai đoạn D — Quét sạch và chặn tái phát

### D1 — Giá trị lệch thang, quét theo VÙNG

`globals.css` có 3533 dòng và hàng trăm khai báo spacing/font/radius. Bản trước
nêu ba lệnh `grep` rồi bảo "đổi về token gần nhất" — đó là một lượt cleanup toàn
file trong một nhát: diff khổng lồ, không review nổi, và mỗi giá trị lệch thang
cố ý bị xoá cùng với lý do của nó mà không ai kịp hỏi.

Chia theo vùng, **mỗi vùng là một vòng khép kín**:

| # | Vùng | Ranh giới |
|---|---|---|
| 1 | Shell + sidebar | `.app`, `.rail`, `.sidebar-*`, `.topbar`, `main.content` |
| 2 | Control dùng chung | `button`, `input`, `select`, `.badge`, `.notice`, `.panel`, `.tabs` |
| 3 | Trang decision | `.decision-*`, `.comparison-*`, `.candidate-*`, `.episode-*` |
| 4 | Deployment / simulate / canvas | `.deployment-*`, `.simulate-*`, `.traffic-*`, `.map-*` |
| 5 | Dashboard + các trang còn lại | phần dư |

Vòng cho mỗi vùng, đúng thứ tự:
1. Khoá hành vi bằng test **đang có** của vùng đó (chạy trước, phải xanh).
2. Chuyển **một** nhóm smell (spacing, rồi font-size, rồi radius) — không trộn.
3. Chạy lại targeted test.
4. Visual Verdict.
5. Verdict đạt mới sang vùng sau.

Chỗ nào cố ý lệch thang thì **để lại comment nói rõ vì sao**, và tên nó vào danh
sách miễn trừ của D3 — hai việc, không phải một.

**Regex phải đọc được shorthand.** `padding: 8px 14px` có `8px` hợp thang và
`14px` lệch; regex chỉ bắt số đầu sẽ bỏ sót đúng nửa số ca, và bỏ sót im lặng.
Tách mọi giá trị px trong khai báo rồi kiểm **từng cái**, không kiểm cái đầu.

### D2 — Bỏ `!important` do xung đột, GIỮ `!important` của reduced-motion

`globals.css` có **đúng 6** `!important`. Ba trong số đó là reduced-motion:

```css
.simulate-page   * { scroll-behavior: auto !important; transition: none !important; }  /* :2041 */
.decision-page   * { transition: none !important; }                                    /* :2197 */
.deployment-form * { scroll-behavior: auto !important; transition: none !important; }  /* :2647 */
```

**Ba dòng này `!important` là có chủ ý** — chúng phải thắng `transition` khai
cục bộ trong từng component, và đó chính là cơ chế duy nhất khiến chúng có tác
dụng. Xoá là animation quay lại với **đúng người đã yêu cầu tắt nó**, tức là
người dễ bị hại nhất bởi chuyển động, và hỏng theo kiểu không ai chụp màn thấy
được.

Nên D2 là:
- Xoá `!important` sinh ra từ **xung đột inline-style / responsive**: `:1759`,
  `:2569`, và `:3498` (Plan 2 T4 đã xử) — truy về nguyên nhân rồi sửa nguyên
  nhân, không đè thêm.
- **Giữ** ba dòng reduced-motion, đưa vào allowlist có tên
  `REDUCED_MOTION_IMPORTANT` trong test.
- Test khẳng định điều mạnh hơn "không có `!important`": **mọi `!important` còn
  lại phải nằm trong một khối `@media (prefers-reduced-motion: reduce)`**. Luật
  đó vừa cho phép ba dòng hiện có, vừa chặn dòng thứ tư lọt vào vì lý do khác.
- Nghiệm thu **không** yêu cầu `grep '!important'` ra rỗng.

### D3 — Test chặn tái phát

Mở rộng `tokens.test.ts` (Plan 1 T6):
- Mọi `padding`/`margin`/`gap` px thuộc thang (kiểm **từng giá trị** trong
  shorthand), hoặc nằm trong danh sách miễn trừ có tên
- Không `font-size` nửa pixel
- `border-radius` chỉ thuộc {4, 6, 8, 50%}
- `!important` chỉ trong `prefers-reduced-motion` (xem D2)

**`box-shadow` và `linear-gradient`: allowlist, không phải cấm.** Bản trước tự
mâu thuẫn — B8 yêu cầu focus ring `box-shadow: 0 0 0 3px var(--accent-soft)`,
rồi nghiệm thu lại nói `box-shadow` chỉ được có ở popover/tooltip/menu. Hai câu
không cùng đúng được.

`box-shadow` — allowlist:

| Dùng cho | Ghi chú |
|---|---|
| focus ring của input/select | B8 |
| popover / tooltip / menu | `--shadow-pop` |
| `inset` của nav đang active | B8 tabs cũng dùng `inset` |
| viền `inset` cố ý trên canvas | nếu quyết định giữ |

`linear-gradient` — chỉ có **hai** chỗ trong cả file, và cả hai đều là chức năng,
không phải trang trí:

| Selector | Dòng | Vai trò |
|---|---|---|
| `.progress-active` | `964` | trạng thái đang chạy của thanh tiến trình |
| `.skeleton` | `2762` | shimmer loading — đi cùng `background-size: 200%` + `animation` |

Muốn bỏ thật thì phải **nêu cái thay thế**, không chỉ nêu lệnh cấm:
`.progress-active` → accent đặc; `.skeleton` → nền đặc nhấp nháy, **và** phải tắt
animation dưới `prefers-reduced-motion` (bỏ gradient mà giữ animation là đổi một
vấn đề lấy một vấn đề khác). Không muốn làm thì cho hai selector này vào
allowlist. Biến một cuộc rà "đừng lạm dụng gradient" thành "cấm cả gradient chức
năng" là dùng luật sai chỗ.

Danh sách miễn trừ là một mảng có tên trong test, không phải regex lỏng — thêm
một ngoại lệ phải sửa test, tức là phải cố ý.

---

## Nghiệm thu cả plan

### Lệnh — chạy hết, không chỉ typecheck

Bản trước chỉ ghi `typecheck` + hai file test sidebar. Với một thay đổi chạm mọi
trang thì chừng đó không tương xứng.

```powershell
npm.cmd test              # toàn bộ web suite
npm.cmd run typecheck
npm.cmd run build         # BẮT BUỘC — đây là chỗ lỗi next/font lộ ra, test không thấy
```
`npm.cmd run build` là mục mới và là mục quan trọng nhất: font hỏng không làm đỏ
một test nào, nó làm hỏng bản dựng.

### Visual Verdict — sau từng pha, không dồn cuối

Chạy sau **A3**, **B0**, **từng bước B1–B8**, **C**, và **từng vùng D1**. Mỗi
vòng lưu verdict state trước khi sửa tiếp; không chồng hai lượt chỉnh lên một
lần chụp.

- Breakpoint: **1440 / 1024 / 768 / 390**
- Theme: **light + dark**
- Ngôn ngữ: **EN + VI**
- Trang đại diện: `dashboard`, `decisions/[id]`, `deployments`, `simulate`,
  `maps`, `library`, `system`, `agent`

### Nội dung

- [ ] Chỉ **một** stack sans và **một** stack mono trong toàn bộ `globals.css`
- [ ] `Ữ Ế Ộ Ỡ Ợ ự ệ ỗ ẫ ằ` render đủ dấu ở 11 / 12 / 13 / 14 / 16 / 24px
- [ ] Chuyển EN ⇄ VI trên 8 trang đại diện — không nhãn nào tràn hoặc cắt
- [ ] Sidebar: **12 mục** vừa một màn 13" (768px cao), không cuộn
- [ ] Không nhãn điều hướng nào kể trạng thái dự án
- [ ] `!important` còn lại **chỉ** nằm trong `prefers-reduced-motion` (D2) —
      **không** yêu cầu grep ra rỗng
- [ ] `linear-gradient` chỉ ở `.progress-active` và `.skeleton`, hoặc đã có bản
      thay thế kèm xử lý reduced-motion (D3)
- [ ] `box-shadow` chỉ trong allowlist D3, **gồm cả focus ring của B8**
- [ ] Chiều cao control: `min-height: 32px` cho button/input/select/tab; hàng
      **bảng dữ liệu một dòng** 32px — không ép hàng nhiều dòng
- [ ] Contrast AA: `--muted` trên `--panel` và trên `--panel-2`; chữ 11px cũng phải ≥ 4.5:1
- [ ] Dark theme còn chạy được — không dùng lại thiết kế, chỉ không vỡ
- [ ] A3: bốn bề mặt candidate đổi màu đồng bộ ở **cả hai theme**, không còn nền
      tím ngồi cạnh chữ teal
- [ ] Pass tay: bàn phím / focus order / `prefers-reduced-motion` bật

## Rủi ro

| Rủi ro | Mức | Xử lý |
|---|---|---|
| Giai đoạn B chạm mọi trang | **Cao** | Chia **changeset / lượt làm** theo trang, không theo class. Duyệt mắt từng trang trước khi sang trang sau. (Không phải "chia commit" — mục cuối plan nói rõ **không commit**; người làm dừng trước commit, An tự commit) |
| Hạ base 13px làm vỡ trang nhiều chữ | **Cao** | Kiểm `/system`, `/agent`, `/library` ngay sau B1. Nếu vỡ thì miễn trừ **qua route mapping trong `AppShell`** giống B2 — trang con không tự đặt class lên `<main>` được — hoặc đặt `font-size` trên container gốc của chính trang đó. Không viết "một class trên `main`": đó là lối thoát không tồn tại |
| B2 phá layout trang có canvas | Trung bình | `WIDE_CONTENT_ROUTES` trong `AppShell` + `main.content--wide`; test ánh xạ route → class. Trang con **không** tự đặt class được, xem B2 |
| A3 không đổi gì vì bị scope cục bộ ghi đè, và bước này trông như đã xong | **Cao** | Xoá `.decision-page` / `.episode-comparison`; visual QA bốn bề mặt × hai theme |
| D2 xoá `!important` của reduced-motion ⇒ animation quay lại với người đã tắt nó | **Cao** | Allowlist `REDUCED_MOTION_IMPORTANT`; test buộc mọi `!important` nằm trong `prefers-reduced-motion` |
| `next/font/google` fail lúc build khi không có mạng | Trung bình | Đã chuyển sang `next/font/local` + `.woff2` commit vào repo. Nghiệm thu: `npm.cmd run build` sau khi ngắt mạng |
| B4 `height` cứng cắt nội dung 99 nút đang chạy | **Cao** | `min-height`, cộng bảng ngoại lệ có tên |
| C đảo ngược quyết định sản phẩm cũ (mô tả rail, nhóm "Being replaced") | Trung bình | Cần An duyệt như quyết định sản phẩm; sửa luôn comment `navigation.ts:44-52` |
| C5 hai file test đỏ | Thấp | Đã biết trước. Sửa cùng lượt |
| B5 đổi badge ảnh hưởng khắp app | Trung bình | Badge chỉ đổi radius và chiều cao, không đổi màu — sai lệch nếu có sẽ nhỏ và nhìn ra ngay |
| Font binary sai version hoặc sai subset (bản `latin` không có glyph Việt) | Trung bình | Manifest pin tag + SHA-256; nghiệm thu B0 kiểm hash **và** soi glyph. Đây là loại lỗi build vẫn xanh, chỉ dấu tiếng Việt rơi về font hệ thống |
| Token đổi theo theme bỏ sót đường **OS-light** (`:root:not([data-theme])`) | **Cao** | Dẫn xuất từ token semantic (`--indigo`/`--teal`/`--shadow`) thay vì hard-code từng block; nghiệm thu có đủ 5 trạng thái theme |

## Không commit

Làm xong dừng lại, báo cáo. An tự commit.

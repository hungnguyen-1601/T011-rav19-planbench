# Plan 3 — nhật ký thực thi theo từng giai đoạn

**Nhánh:** `tongduyan_3` · **Trạng thái:** đang chạy, **chưa commit**

Một file cho cả Plan 3, mỗi giai đoạn một mục, ghi ngay sau khi làm xong giai đoạn
đó. Plan 3 chạm mọi trang nên tách thành tám report rời sẽ không ai đọc; gộp một
file thì đọc được cả mạch.

| Giai đoạn | Trạng thái | Đổi hình? |
|---|---|---|
| **A2** thang token | ✅ xong 2026-08-21 | không |
| **A3** tách `--candidate-a/b` | ✅ xong 2026-08-21 | **có** |
| **A4** biến thể `.notice` | ✅ xong 2026-08-21 | không |
| B0 nạp font | chưa | có |
| B1–B8 | chưa | có |
| C sidebar | chưa | có |
| D quét sạch | chưa | có |

---

## A2 — Thang spacing / radius / typography · 2026-08-21

**Chỉ khai báo. Không rule nào đọc chúng.** Đây là điểm của bước này: đặt tên cho
những giá trị stylesheet đang viết tay ở hàng trăm chỗ, rồi để giai đoạn sau nối
từng chỗ vào tên. Tách ra như vậy thì diff của giai đoạn sau đọc được là *"rule
này giờ đọc một token"*, chứ không phải *"rule này đổi, và giá trị của nó cũng
đổi"* — hai thứ trộn vào một diff là không review được.

### Đã thêm — 19 token, tất cả vào `:root` chung

Ngoài các block `[data-theme]`: một mặt chữ hay một bước spacing không đổi theo
bảng màu, khai trong cả ba block là ba chỗ để quên một chỗ.

```css
--font-sans   (mới)      --space-1..7      --radius-sm/md/lg
--fs-caption --fs-sm --fs-body --fs-label --fs-value --fs-h3 --fs-h1
--shadow-pop
```

### Ba quyết định trong đó đáng ghi lại

**`--font-sans` chép nguyên văn stack đang chạy**, kể cả `-apple-system`:

```css
--font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
```

Hai thứ nó **không** được làm. Thêm `Inter` vào đầu: máy nào đã cài sẵn Inter sẽ
đổi mặt chữ, máy khác thì không — hỏng ở một tập con người dùng, tức là kiểu hỏng
khó truy nhất. Rơi `-apple-system`: đó là mắt xích chọn San Francisco trên Safari,
mất nó là đổi mặt chữ trên đúng những máy đó. Bản plan đầu mắc cả hai; vòng review
bắt được.

**`--shadow-pop` dẫn xuất, không phải giá trị chữ:**

```css
--shadow-pop: var(--shadow);
```

Bản plan đầu viết `0 4px 12px rgba(20,24,31,.10)` với `/* dark: rgba(0,0,0,.45) */`
bên cạnh. **Comment không phải rule** — token sẽ giữ giá trị light trên dark theme
và vẽ một vệt xám nhạt trên nền gần đen: vô hình, và vô hình cả lúc review.
`--shadow` đã khai đủ **ba** đường theme (`globals.css:55`, `:104`, `:148`) nên
dẫn xuất từ nó tự đúng ở cả ba, miễn phí.

**Ba đường theme, không phải hai.** Điều này chi phối cả A2 lẫn A3: ngoài
`:root[data-theme="dark"]` và `[data-theme="light"]`, còn
`@media (prefers-color-scheme: light) { :root:not([data-theme]) }` — người **chưa
chọn** theme. Đó là cấu hình mặc định của phần lớn người mở link lần đầu, nên nó
là ca hay gặp nhất chứ không phải ca hiếm.

### Một mở rộng ngoài chữ của plan, cố ý

Plan A2 viết "chỉ khai báo, chưa chỗ nào dùng". Tôi làm thêm **một** chỗ dùng:

```css
html, body { font-family: var(--font-sans); }   /* trước: viết thẳng stack */
```

Lý do: nếu không nối, stack sống ở hai nơi — trong token và trong `html, body`.
Khi đó B0 nạp webfont, `--font-sans` đổi, mà **chữ thân trang vẫn là font hệ
thống** cho tới khi ai đó nhận ra. Đúng loại bẫy mà commit `7b9d525` vừa dọn cho
`--font-mono` ("*folding in the four other hand-copied stacks leaves a single
place for Plan 3's webfont to change*") — A2 mà không nối thì tạo lại đúng nó.

Giá trị y hệt nên không pixel nào dịch. Vẫn báo ra đây vì nó nằm ngoài chữ của
plan.

### Nghiệm thu

Nghiệm thu của A2 là **zero-diff**. Cách kiểm thẳng nhất không phải là chụp màn
mà là chứng minh trên chính stylesheet — so bản mới với `HEAD`, bóc hết comment,
chuẩn hoá khoảng trắng:

```
tokens added  : 19  (danh sách ở trên)
tokens removed: 0
values changed: none          ← không token cũ nào bị đổi giá trị
rule bodies   : 916 trước, 916 sau
```

7 rule body khác nhau, và **chỉ 2 là của lượt này**:

1. khối `:root` — thuần khai báo, không rule
2. `html, body` — `font-family` đổi từ stack viết thẳng sang `var(--font-sans)`,
   **cùng một chuỗi**

5 cái còn lại (`--canvas-bg`, `--panel-2`, `--err`, `--panel-3`, `--text` thay cho
`--surface`, `--danger`, `--fg`) là phần **Plan 1 đang nằm sẵn trong working
tree**, không thuộc lượt này — tôi không chạm vào token nào trong số đó.

Không rule nào đọc token mới: `grep 'var(--space-\|var(--radius-\|var(--fs-\|var(--shadow-pop)'` → **0**.

### Test

| Lệnh | Kết quả |
|---|---|
| `tokens.test.ts` | **6 passed** |
| ba file test đọc `globals.css` (`tokens`, `running-comparison`, `hint`) | **96 passed** |

`tokens.test.ts` (Plan 1 T6) hoá ra **đã được cài rồi**, và nó đã ghi sẵn hợp
đồng font ở `NEXT_FONT_PROVIDED`: token công khai `--font-sans`/`--font-mono` luôn
khai trong `globals.css`, `next/font` chỉ sinh `--font-*-loaded`. A2 làm đúng hợp
đồng đó nên không phải nới test một dòng nào — đúng như Plan 1 T6 đã tính trước.

Test chỉ đòi `referenced ⊆ declared`, nên 19 token khai mà chưa ai đọc là hợp lệ.

### Việc còn lại của A2 — thuộc về An

Chụp màn 6 trang trước/sau. Tôi **không tự chạy** vì An giữ dev server, và lập
luận zero-diff ở trên đã mạnh hơn một vòng chụp cho đúng loại thay đổi này (không
token nào bị đổi giá trị, chỉ một phép thế tên bằng chuỗi y hệt). Nhưng nó không
thay thế được việc An nhìn một lượt.

---

## A3 — Tách `--candidate-a/b` khỏi `--accent` · 2026-08-21

**Bước đổi hình đầu tiên của Plan 3.** Không có lập luận zero-diff nào ở đây; thay
vào đó là bảng giá trị giải ra bên dưới.

### Vấn đề

`--candidate-a` là `var(--accent)`. Một màu xanh nói hai điều: *"đây là link, bấm
đi"* và *"cột này là ứng viên A"*. `--candidate-b` mượn `--purple`, thứ không
trang nào trong khu vực này dùng vào việc gì khác.

### Ba khối, không phải một

Điều khiến A3 dễ làm hụt: sáu token **không** được khai ở `:root` — chúng bị **hai
scope cục bộ ghi đè**, và scope cục bộ thắng `:root` bất kể thứ tự. Chỉ thêm màu
vào theme block thì A3 **không đổi được gì**, mà bước vẫn trông như đã xong.

| Khối | Trước |
|---|---|
| `.decision-page` | `--candidate-a: var(--accent)`, `--candidate-b: var(--purple)`, cùng `-soft` / `-border` |
| `.episode-comparison` | hard-code `#2563eb` / `#7c3aed` |

Đã **xoá hẳn** cả hai, không để lại alias — một alias `--candidate-a:
var(--candidate-a)` đọc ra như thể trang vẫn còn lý do giữ ý kiến riêng.

### Dẫn xuất, không hard-code

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

Hai điều việc này mua được:

1. **Đủ ba đường theme miễn phí.** `--indigo`/`--teal` đã có sẵn ở `:root`, ở
   `[data-theme="light"]`, **và** ở khối `prefers-color-scheme` cho người chưa
   chọn gì. Gõ tay hex vào hai theme block sẽ bỏ sót đúng đường thứ ba — đường mà
   người mở link lần đầu thực sự rơi vào.
2. **Không thể khai thiếu một nửa.** Viết tay dễ đúng `--candidate-b` mà quên
   `--candidate-b-soft`, và cái đó không hỏng ồn ào: nó đặt nền tím cũ sau chữ
   teal mới, ở một card, trên một trang.

### Đổi những gì — giá trị giải ra

| | Candidate A | A · soft | Candidate B | B · soft |
|---|---|---|---|---|
| **dark** | `#4c9aff` → `#8fa5ff` | `76,154,255` → `111,132,238` | `#b39df3` → `#50c7ad` | `163,132,238` → `54,184,156` |
| **light** (chọn tay) | `#1f6feb` → `#5267c9` | `31,111,235` → `82,103,201` | `#7157b7` → `#087f6a` | `113,87,183` → `8,127,106` |
| **light** (theo OS) | `#1f6feb` → `#5267c9` | `31,111,235` → `82,103,201` | `#7157b7` → `#087f6a` | `113,87,183` → `8,127,106` |

Alpha giữ nguyên (`.14` trên dark, `.10` trên light), chỉ đổi sắc.

**`.episode-comparison` là ca được lợi nhiều nhất.** Nó hard-code hex nên panel
phát lại giữ nguyên xanh–tím của light theme **kể cả trên nền tối**, trong khi
phần còn lại của trang đã đổi. Giờ nó theo theme.

### Bề mặt bị ảnh hưởng — 18 rule, 5 vùng

| Vùng | Rule |
|---|---|
| Thẻ candidate ở trang list | `globals.css:2134-2139` |
| Chấm chú giải | `:3232-3233` |
| Thẻ episode (panel phát lại) | `:3248-3256` |
| Bảng mẫu episode (hàng chọn, header cột) | `:3313-3317` |
| Lưới so sánh + icon candidate | `:3494-3495`, `:3514-3515` |

Năm vùng này đọc token qua năm đường khác nhau, nên sót một chỗ **không** kéo bốn
chỗ kia lộ ra — đó là lý do checklist mắt phải liệt kê cả năm.

### Test

`tokens.test.ts`, `running-comparison`, `hint`, `decisions-page` — **189 passed**.
Dấu ngoặc cân (954 cặp). `--purple` / `--accent-soft-border` **không** thành mồ
côi: còn 22 chỗ khác dùng.

### Việc còn lại của A3 — thuộc về An

Test không kiểm được màu. Cần chụp **5 vùng × 5 trạng thái theme**:

- [ ] `data-theme="dark"`
- [ ] `data-theme="light"`
- [ ] không `data-theme`, OS **light**
- [ ] không `data-theme`, OS **dark**
- [ ] đặt `data-theme="dark"` khi OS đang light → phải ra dark (explicit thắng OS)

Điều cần tìm: **không còn nền tím ngồi cạnh chữ teal** ở bất kỳ đâu, và panel phát
lại không còn giữ xanh–tím sáng trên nền tối.

### An đã kiểm — đạt

Chụp cả light lẫn dark. Cột A ra chàm, cột B ra teal, không còn nền tím cạnh chữ
teal. Commit `7b287eb`.

---

## A4 — Ba biến thể `.notice` · 2026-08-21

**Zero-diff.** Chỉ thêm ba selector; `.notice` gốc không đụng một dòng.

### Vấn đề

**Cả 27 `.notice` trên site đều vàng.** Cùng một màu cho *"lượt chạy này được chấm
trước khi có tầng giải thích"* và *"mọi con số trên trang dựa trên cỡ mẫu dưới
N_min đã khai"*. Một trang không phân biệt được ghi chú thường với thông điệp vô
hiệu hoá số liệu bên dưới nó thì người đọc học cách lướt qua cả hai.

### Đã thêm

```css
.notice.notice--info     { background: var(--panel-2);  border-color: var(--border); }
.notice.notice--warn     { background: var(--warn-soft); border-color: color-mix(in srgb, var(--warn) 35%, transparent); }
.notice.notice--critical { background: var(--err-soft);  border-color: var(--err); }
```

Ba mức, và luật dùng chúng: `--critical` **chỉ** cho loại thông điệp vô hiệu hoá
mọi số bên dưới (`n` dưới N_min). Thêm loại thứ hai vào mức đó là nó hết nghĩa.

`--warn` giữ nền của `.notice` gốc nhưng **viền nhạt hơn** (mix 35% thay vì
`--warn` đặc): khi đã có biến thể trung tính, một cảnh báo không còn phải gào lên
mới phân biệt được với ghi chú thường.

### Một chi tiết ngoài chữ plan: `.notice.notice--x`, không phải `.notice--x`

Plan viết selector đơn. Cả hai đều chạy **hôm nay** — biến thể nằm sau rule gốc
nên cùng specificity thì thứ tự nguồn quyết định. Nhân đôi class biến điều đó
thành tính chất của **selector** thay vì tính chất của **vị trí khối trong một
file 3500 dòng**.

Lý do đáng làm: dự án này đã ship **ba** lỗi CSS vô hình trong review (token chưa
khai, comment-không-phải-rule, hex hard-code). Một rule ngừng hoạt động vì ai đó
di chuyển nó sẽ là lỗi thứ tư cùng loại.

### Vì sao không gán luôn cho 27 chỗ dùng

Đó là việc của giai đoạn B, và nó là **một phán đoán cho từng chỗ**. Tách ra thì
diff của B đọc được là *"notice này là cảnh báo, cái kia là critical"*, chứ không
lẫn với thay đổi hình dạng của chúng.

### Nghiệm thu

So với `HEAD`, bóc comment, chuẩn hoá khoảng trắng, đối chiếu theo selector:

```
selectors added  : .notice.notice--info, .notice.notice--warn, .notice.notice--critical
selectors removed: (không)
bodies changed   : 5 — .decision-deployment-map, .decision-deployment-skeleton,
                   .chat-history li:hover, .chat-history-delete:hover, .latency-playhead
```

Năm body đó là **Plan 1 T2b đang nằm trong working tree**, khớp đúng 4 hunk chưa
commit; không thuộc lượt này.

`grep 'notice--' src --include=*.tsx` → **0**. Không component nào mang class mới,
nên không pixel nào dịch.

Test: `tokens`, `running-comparison`, `hint`, `decisions-page` — **189 passed**.
Bốn token `--panel-2` / `--warn-soft` / `--err-soft` / `--err` đều khai đủ ba
đường theme.

### Hết giai đoạn A

Ba bước xong. Từ B0 trở đi mọi bước đều đổi hình, và B0 là bước đầu tiên cần
**quyết định của An trước khi làm**: `next/font/local` với `.woff2` commit vào
repo (đã chốt trong plan) đòi tải file font về và ghi manifest pin tag + SHA-256.

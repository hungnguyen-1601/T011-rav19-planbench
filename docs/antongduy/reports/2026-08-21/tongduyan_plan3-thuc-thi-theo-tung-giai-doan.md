# Plan 3 — nhật ký thực thi theo từng giai đoạn

**Nhánh:** `tongduyan_3` · **Trạng thái:** đang chạy, **chưa commit**

Một file cho cả Plan 3, mỗi giai đoạn một mục, ghi ngay sau khi làm xong giai đoạn
đó. Plan 3 chạm mọi trang nên tách thành tám report rời sẽ không ai đọc; gộp một
file thì đọc được cả mạch.

| Giai đoạn | Trạng thái | Đổi hình? |
|---|---|---|
| **A2** thang token | ✅ xong 2026-08-21 | không |
| A3 tách `--candidate-a/b` | chưa | **có** |
| A4 biến thể `.notice` | chưa | không |
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

### Ghi chú cho giai đoạn sau

**A3 KHÔNG zero-diff** — nó đổi màu candidate thật, và hai khối `.decision-page`
(`:2046`) với `.episode-comparison` (`:3095`) đang **ghi đè** sáu token đó, nên
phải xoá chúng thì A3 mới có tác dụng. Xem plan.

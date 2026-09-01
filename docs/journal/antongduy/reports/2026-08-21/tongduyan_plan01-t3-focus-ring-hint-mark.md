# Plan 1 · T3 — focus ring của `.hint-mark` bị tắt cho cả bàn phím

**Ngày:** 2026-08-21 · **Nhánh:** `tongduyan_3` · **Trạng thái:** xong T3, **chưa commit**

Nguồn: [01-bug-fix-token-i18n-a11y.md](../../plans/2026-08-21/01-bug-fix-token-i18n-a11y.md) — task T3.
Tiếp sau [T1](tongduyan_plan01-t1-token-hint-mark.md) và [T2](tongduyan_plan01-t2-font-mono.md).
T2b, T4–T7 chưa chạm.

---

## Lỗi thật sự là gì

`globals.css` gộp hai state vào một rule:

```css
.hint-mark:hover,
.hint-mark:focus-visible { color: var(--text); border-color: var(--accent); outline: none; }
```

`outline: none` viết cho **chuột** — bỏ ring khi hover là hợp lý. Nhưng vì gộp
selector, nó với sang cả **bàn phím**. Kết quả: Tab tới dấu `?` thì tín hiệu focus
duy nhất là một viền 1px đổi màu trên vòng tròn 15px.

Trang này đã có sẵn rule đúng ở `globals.css:2158`:

```css
.decision-page :is(button,select,input,a,summary):focus-visible { outline: 2px solid var(--accent); … }
```

nhưng `.hint-mark` là `<span>`, không khớp selector đó. Còn rule toàn cục
`:focus-visible` ở `:2686` thì **có** khớp — chỉ là `.hint-mark:focus-visible`
(specificity 0,2,0) đè `:focus-visible` (0,1,0), nên `outline: none` thắng.

## Một lỗi thứ hai plan chưa nêu, phải xử cùng lượt

Rule toàn cục ở `:2686` không chỉ đặt outline:

```css
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
```

`border-radius: 4px` **cũng** khớp `.hint-mark`. Đối chiếu specificity: `.hint-mark`
đặt `border-radius: 50%` ở (0,1,0) dòng 1140; rule toàn cục ở (0,1,0) dòng 2686 —
**bằng specificity, khai sau thắng**. Nghĩa là dấu `?` **đã và đang** biến từ hình
tròn thành hình vuông bo góc mỗi khi nhận focus.

Lỗi này tồn tại từ trước, nhưng **không ai thấy** vì `outline: none` làm không có gì
báo hiệu là mark đang được focus. Sửa xong T3 mà bỏ qua nó thì việc bật ring lại
chính là việc phơi nó ra: người dùng bàn phím sẽ thấy vòng tròn méo đi ngay khi Tab
tới. Nên tôi xử luôn trong cùng rule.

## Đã sửa

`apps/web/src/app/globals.css` — tách hai state:

```css
.hint-mark:hover {
  color: var(--text);
  border-color: var(--accent, #4c9aff);
}

.hint-mark:focus-visible {
  color: var(--text);
  border-color: var(--accent, #4c9aff);
  border-radius: 50%;
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
```

- `outline: 2px solid var(--accent); outline-offset: 2px` là **đúng quy ước sẵn có**
  của repo — cùng giá trị với `:1845`, `:1977`, `:2091`, `:2158`, `:3391`. Không đặt
  ra kiểu ring mới.
- Viết outline **tường minh** thay vì chỉ xoá `outline: none` để nhờ rule toàn cục:
  rule tường minh nói rõ ý định tại chỗ, và không phụ thuộc vào thứ tự khai của một
  rule cách đó 1500 dòng.
- `border-radius: 50%` lặp lại có chủ ý — đây là dòng chặn rule toàn cục vuông hoá
  vòng tròn. Comment tại chỗ ghi rõ vì sao, nếu không thì lần dọn sau sẽ thấy nó
  "thừa" và xoá.
- Hover **không** còn `outline: none`, và hover không kích `:focus-visible`, nên chuột
  vẫn không thấy ring. Click chuột vào mark cũng không — trình duyệt không gán
  `:focus-visible` cho focus bằng con trỏ trên phần tử không phải ô nhập liệu.

## Test — chuyển nghiệm thu thủ công thành nghiệm thu bằng máy

Nghiệm thu của T3 trong plan là thao tác tay ("Tab tới dấu `?` → thấy ring 2px").
Repo đã có sẵn lối test đọc thẳng `globals.css` rồi khẳng định trên nội dung file
(`running-comparison.test.tsx` làm đúng thế, 78 test), nên tôi theo lối đó thay vì
để T3 không có gì canh.

Thêm **hai** test vào `hint.test.tsx` (file này vốn đã canh `tabindex`/`role`):

| Test | Canh cái gì |
|---|---|
| *shows the keyboard where it landed* | rule `:focus-visible` có `outline: 2px solid`, **không** có `outline: none`, và selector **không** bị gộp lại với `:hover` |
| *is still a circle while it is focused* | rule `:focus-visible` giữ `border-radius: 50%` |

**Đây là phần vượt ngoài chữ của plan** (plan chỉ giao test token ở T6). Lý do làm:
T3 vừa sửa một lỗi mà nguyên nhân là *hai state bị gộp selector* — không có gì canh
thì lần gộp sau tái diễn im lặng y như lần đầu.

### Kiểm chứng chính test đó — hai lần đột biến

Test viết ra mà không thử phá thì chỉ chứng minh nó chạy, chưa chứng minh nó bắt được
gì. Tôi sao lưu `globals.css` ra scratchpad rồi cố tình phá hai lần:

| Đột biến | Kết quả |
|---|---|
| Trả `outline: 2px …` về `outline: none` | *shows the keyboard where it landed* **đỏ** (1 failed / 6 passed) |
| Xoá dòng `border-radius: 50%` | *is still a circle while it is focused* **đỏ** (1 failed / 6 passed) |

Khôi phục file → **7/7 xanh** trở lại. Cả hai test đều chịu lực, không có test nào
xanh vô điều kiện.

## Kiểm chứng

- `npx vitest run src/components/__tests__/hint.test.tsx` → **7/7 xanh**.
- `npx vitest run src/app/__tests__/running-comparison.test.tsx` → **78/78 xanh**
  (suite này cũng đọc `globals.css`, nên nó xác nhận sửa CSS không làm đỏ chỗ khác).
- `npx tsc --noEmit` → **exit 0** (test mới thêm import `node:fs`/`node:path`).
- `git diff` globals.css: +16/−2, đúng một khối. CRLF giữ nguyên ở cả hai file.

**Giới hạn:** vẫn chưa có DOM test — `hint.test.tsx` render bằng
`renderToStaticMarkup`, không có jsdom, nên *ring hiện ra thật khi Tab* vẫn là thao
tác mắt. Cái test mới khẳng định là **stylesheet không còn chứa lệnh tắt ring**, và
đó đúng là chỗ bug đã nằm.

## Một thay đổi trên đĩa không phải của tôi

`docs/antongduy/plans/2026-08-21/02-redesign-decision-detail.md` có thêm một dòng
trong bảng phụ thuộc, ghi rằng Plan 3 A2 phải khai `--font-sans` ngay vì T5 của Plan 2
dùng `var(--font-sans)`, mà T2 của tôi mới chỉ khai `--font-mono`. Tôi **không** sửa
dòng đó và **không** stage nó — nêu ra để anh biết nó đang nằm trong working tree.

Nội dung dòng đó đúng với hiện trạng: `globals.css` sau T2 khai `--font-mono`, không
khai `--font-sans` (`body` vẫn hard-code stack sans ở `:174`). T2 cố ý dừng ở đó vì
`--font-sans` chưa có ai tham chiếu qua `var()`, nên test token của T6 chưa cần nó.

## Chưa làm

T2b (`--fg` trên `.latency-playhead`), T4 (Enter/Space cho `Hint`), T5 (câu cảnh báo
host tiếng Việt), T6 (test token), T7 (khuyến nghị phải nêu config).

T4 là phần bổ sung tự nhiên của T3: ring giờ thấy được, nhưng nhấn Enter/Space trên
mark vẫn chưa mở bubble — người dùng bàn phím thấy mình đang ở đâu mà chưa làm được gì.

**Chưa commit** — anh tự commit.

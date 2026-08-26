# Plan 1 · T1 — `--text-muted` không tồn tại, dấu `?` in đen đậm

**Ngày:** 2026-08-21 · **Nhánh:** `tongduyan_3` · **Trạng thái:** xong T1, **chưa commit**

Nguồn: [01-bug-fix-token-i18n-a11y.md](../../plans/2026-08-21/01-bug-fix-token-i18n-a11y.md) — task T1.
Phạm vi lần này **chỉ T1**. T2, T2b, T3–T7 chưa chạm.

---

## Lỗi thật sự là gì

`apps/web/src/app/globals.css:1135` đọc một token chưa từng được khai:

```css
.hint-mark { color: var(--text-muted); }
```

`grep -c -- '--text-muted:' globals.css` → `0`, và `var()` không có fallback. Theo
spec CSS, một custom property không khai là **invalid at computed-value time**, nên
`color` rơi về giá trị kế thừa — chứ không phải về mặc định của `color`. Trong bảng
so sánh, `.hint-mark` nằm trong `.comparison-label`, vốn đặt `color: var(--text)`
(#14181f) và `font-weight: 650`. Bản thân `.hint-mark` lại tự đặt `font-weight: 700`.

Kết quả: dấu `?` — thứ đi **chú thích** cho nhãn — được vẽ **đen hơn và đậm hơn**
chính cái nhãn nó chú thích. Đúng ngược với ý đồ ghi trong comment ngay phía trên
khối rule đó ("Small and quiet").

Đây là lỗi im lặng: không cảnh báo build, không lỗi runtime, không dòng console nào.
Nó chỉ hiện ra bằng mắt.

## Đã sửa

`apps/web/src/app/globals.css` — hai dòng, đúng như plan chốt:

```diff
-  color: var(--text-muted);
+  color: var(--muted);
   font-size: 10px;
-  font-weight: 700;
+  font-weight: 600;
```

`--muted` là token **đã có sẵn** và khai đủ cả ba scope theme, nên dấu `?` đổi màu
đúng theo theme thay vì kẹt ở một màu:

| Scope | Dòng | Giá trị |
|---|---|---|
| `:root, :root[data-theme="dark"]` | 27 | `#9aa4b2` |
| `:root[data-theme="light"]` | 76 | `#5a6472` |
| `@media (prefers-color-scheme: light) > :root:not([data-theme])` | 120 | `#5a6472` |

Nhánh thứ ba là nhánh "người dùng chưa chọn theme" — thiếu nó thì dấu `?` sẽ sai màu
đúng ở cấu hình mặc định phổ biến nhất. Token `--muted` phủ cả ba, nên không cần
thêm rule nào.

**Weight 600, không phải 650 hay 700.** Nhãn cạnh nó (`.comparison-label`) là 650.
Giữ 700 thì chú thích vẫn nặng hơn thứ được chú thích — tức là chưa sửa xong lỗi, chỉ
sửa được nửa màu. Đặt bằng 650 thì hai thứ ngang vai. 600 đặt dấu `?` xuống dưới một
bậc, là đúng thứ tự phân cấp thị giác mà khối này tự nhận.

Kèm theo: nối thêm hai câu vào comment sẵn có phía trên rule, ghi rõ vì sao con số
weight bị ràng vào 650 của `.comparison-label`. Không có câu đó thì lần chỉnh sau rất
dễ nâng lại lên 700 mà không biết mình đang phá cái gì.

## Kiểm chứng

- `grep -rn -- '--text-muted' apps/web/src` → **rỗng**. Không còn chỗ nào khác đọc
  token này, nên T1 đóng trọn, không sót call site.
- `npx vitest run src/components/__tests__/hint.test.tsx` → **5/5 xanh**. Test này
  khẳng định `Hint` vẫn render class `hint-mark`; nó chứng minh không gãy, không
  chứng minh màu — màu là thứ T6 mới bắt được bằng máy.
- `git diff --stat` → đúng **một file, +5/−3**. Không rò sang task khác.

**Một điểm phải nói rõ, không giấu:** đổi màu và weight của CSS thì **không có test tự
động nào phủ**. Nghiệm thu của T1 ("dấu `?` xám, không đậm hơn nhãn cạnh nó") hiện chỉ
kiểm được bằng mắt trên trang so sánh và form deployment. Đúng lỗ hổng này là lý do T6
tồn tại trong plan: T6 dựng test bắt **mọi** `var(--x)` không có định nghĩa, tức là bắt
được loại lỗi này chứ không riêng ca này. Trước khi T6 xong, cam kết duy nhất tôi đưa ra
được bằng máy là "không còn tham chiếu `--text-muted`", không phải "giao diện đã đúng".

### Ghi chú kỹ thuật — CRLF

Repo đặt `core.autocrlf=true`, không có `.gitattributes`, nên bản làm việc của
`globals.css` là CRLF. Bước sửa comment bằng Python đã vô tình chuẩn hoá cả file về LF;
tôi phát hiện qua cảnh báo của `git diff` và **đã chuyển ngược lại CRLF** trước khi
dừng. Đã xác minh lại: `file` báo `with CRLF line terminators`, và `git diff --stat`
vẫn là +5/−3 chứ không phải toàn file. Nếu không bắt kịp, diff sẽ phình thành hàng nghìn
dòng và nuốt mất thay đổi thật.

## Chưa làm

T2 (`--font-mono`), T2b (`--fg` trên `.latency-playhead`), T3 (focus ring), T4 (ARIA
Enter/Space cho `Hint`), T5 (câu cảnh báo host hard-code tiếng Việt), T6 (test token),
T7 (khuyến nghị phải nêu config).

T2b đáng lưu ý hơn phần còn lại: nó cùng loại lỗi với T1 nhưng hậu quả nặng hơn —
`stroke: var(--fg, #111827)` luôn rơi vào fallback, nên playhead của latency chart gần
như tàng hình trên dark theme. Có fallback nên nó còn khó thấy hơn T1.

**Chưa commit** — theo thoả thuận, anh tự commit.

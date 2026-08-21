# Plan 1 · T2 — `--font-mono` không tồn tại, mọi block mã rơi về Courier New

**Ngày:** 2026-08-21 · **Nhánh:** `tongduyan_3` · **Trạng thái:** xong T2, **chưa commit**

Nguồn: [01-bug-fix-token-i18n-a11y.md](../../plans/2026-08-21/01-bug-fix-token-i18n-a11y.md) — task T2.
Tiếp sau [T1](tongduyan_plan01-t1-token-hint-mark.md). T2b, T3–T7 chưa chạm.

---

## Lỗi thật sự là gì

Hai chỗ đọc `var(--font-mono, monospace)` — `.condition-noise-tags > span`
(`globals.css:1867`) và `.episode-comparison-head h4` (`:3113`) — trong khi
`--font-mono` chưa từng được khai ở đâu. Có fallback nên không có gì hỏng, chỉ là
**fallback luôn thắng**: cả hai luôn render bằng `monospace` generic, trên Windows
là Courier New.

Cùng lúc đó `.comparison-value` (`:3446`) hard-code một stack khác hẳn:
`ui-monospace, SFMono-Regular, Consolas, monospace` — tức Consolas trên Windows.

Nên hai thứ lẽ ra cùng họ chữ thì **hiện bằng hai typeface khác nhau**: cột giá trị
bảng so sánh ra Consolas, còn tag nhiễu và tiêu đề episode ra Courier New. Lỗi này
khác T1 ở chỗ nó **có fallback**, nên trông như đã được nghĩ tới — đó chính là lý do
nó sống lâu.

## Đã sửa

### 1. Khai token, đặt ngoài ba block theme

Thêm một block `:root` riêng, nằm sau ba block màu và trước `* { box-sizing }`:

```css
:root {
  --font-mono: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
}
```

Đặt ngoài `[data-theme]` là có lý do và tôi ghi luôn vào comment tại chỗ: typeface
không đổi theo bảng màu, nhét vào cả ba block là ba nơi để quên. Comment cũng ghi
sẵn **hợp đồng với Plan 3** mà T6 chốt: `next/font` sẽ sinh token tên riêng
`--font-mono-loaded`, và Plan 3 chỉ **đổi giá trị** dòng này thành
`var(--font-mono-loaded, <stack hiện tại>)` — không xoá khai báo. Nghĩa là test token
của T6 không bao giờ phải nới ra khi nạp webfont.

### 2. Bỏ fallback thừa ở hai chỗ

`var(--font-mono, monospace)` → `var(--font-mono)`. Giữ fallback lúc này là giữ
đúng cái chỗ bug vừa trốn: nó biến "token thiếu" từ lỗi thấy được thành lỗi im lặng.
Token đã khai ở `:root` nên không còn đường rơi.

### 3. `.comparison-value` dùng token

```diff
-  font: 700 16px ui-monospace,SFMono-Regular,Consolas,monospace;
+  font: 700 16px var(--font-mono);
```

Shorthand `font:` vẫn giữ nguyên — nó reset `font-variant-numeric`, nhưng dòng
`font-variant-numeric: tabular-nums` nằm **ngay sau** nên vẫn thắng. Không đổi thứ tự.

### 4. Ngoài danh sách của plan — bốn chỗ nữa cùng stack

Plan T2 chỉ liệt kê `.comparison-value`. Rà thì còn **bốn** chỗ nữa chép tay đúng
stack đó:

| Selector | Dòng (trước sửa) |
|---|---|
| `.simulate-timeline span` | 1910 |
| `.simulate-telemetry dd` | 1945 |
| (block ở) 2352 | 2352 |
| `.conclusion-mark` | 3512 |

Tôi gộp cả bốn vào token. **Đây là phần vượt ra ngoài chữ của plan, nên nói rõ:**

- Về mặt hiển thị **hôm nay** đây là thay đổi zero — chúng đang render đúng cái stack
  mà token mang.
- Lý do vẫn làm: bốn chỗ này là **quả mìn hẹn giờ cho Plan 3**. Khi Plan 3 nạp
  JetBrains Mono vào token, bảng so sánh và tag nhiễu sẽ đổi font còn bốn chỗ này
  **im lặng ở lại stack cũ** — tái tạo đúng loại lệch font mà T2 đang đi sửa, chỉ khác
  là lần sau sẽ khó truy hơn vì trông như cố ý.
- Sau bước này, `grep -rn 'SFMono\|Consolas\|Courier' apps/web/src` → **rỗng**. Stack
  mono giờ chỉ tồn tại **một nơi duy nhất** trong toàn bộ codebase web.

Nếu anh muốn giữ đúng phạm vi chữ của plan, revert riêng mục 4 được — nó độc lập với
ba mục trên.

## Một chỗ plan tự mâu thuẫn, và tôi chọn ngả nào

Plan viết *"Dùng stack **hiện có** của `.comparison-value`"*, nhưng giá trị token mà
plan ghi ra lại có thêm `"Liberation Mono"` — thứ **không có** trong stack hiện có.

Tôi theo **giá trị chữ trong plan** (có `Liberation Mono`), vì T6 chép lại đúng chuỗi
đó lần thứ hai khi chốt hợp đồng alias với Plan 3; lấy stack trần sẽ làm hai mục của
cùng một plan lệch nhau.

Hệ quả thật, không giấu: trên **Linux**, Liberation Mono giờ được chọn trước
`monospace` generic. Windows và macOS không đổi gì — `ui-monospace`/`Consolas` bắt
trước. Đây là thay đổi hiển thị duy nhất của T2 ngoài việc sửa lỗi.

## Kiểm chứng

- `grep -n 'var(--font-mono, monospace)' globals.css` → **rỗng** (đúng ô nghiệm thu
  của plan).
- `grep -rn 'SFMono\|Consolas\|Courier' apps/web/src` → **rỗng**.
- Parse lại toàn bộ stylesheet bằng postcss: **OK, 3005 declaration**, và cả **7** chỗ
  dùng mono đều đọc `var(--font-mono)`. Bước này để bắt lỗi cú pháp — `font:` shorthand
  nhận `var()` là hợp lệ, nhưng khẳng định bằng parser vẫn hơn đọc bằng mắt.
- `npx vitest run src/app/__tests__/running-comparison.test.tsx src/components/__tests__/hint.test.tsx`
  → **83/83 xanh**. File đầu **đọc thẳng `globals.css`** (78 test), nên nó thật sự có
  phủ stylesheet chứ không chỉ chạy cho có.
- `git diff --stat` một file, CRLF giữ nguyên.

**Giới hạn phải nói:** như T1, không test nào khẳng định *font hiện ra đúng*. Cái
kiểm được bằng máy là "không còn tham chiếu token thiếu" và "chỉ còn một nguồn khai
stack". Việc bốn chỗ ở mục 4 render y như cũ thì tôi lập luận từ chuỗi giá trị, **chưa
soi bằng mắt trên trình duyệt**.

## Chưa làm

T2b (`--fg` trên `.latency-playhead`), T3 (focus ring), T4 (Enter/Space cho `Hint`),
T5 (câu cảnh báo host tiếng Việt), T6 (test token), T7 (khuyến nghị phải nêu config).

**Chưa commit** — anh tự commit.

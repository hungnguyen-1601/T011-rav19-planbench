# Plan 1 · T4 — `Hint` hứa là button rồi không trả lời phím nào

**Ngày:** 2026-08-21 · **Nhánh:** `tongduyan_3` · **Trạng thái:** xong T4, **chưa commit**

Nguồn: [01-bug-fix-token-i18n-a11y.md](../../plans/2026-08-21/01-bug-fix-token-i18n-a11y.md) — task T4.
Tiếp sau [T1](tongduyan_plan01-t1-token-hint-mark.md), [T2](tongduyan_plan01-t2-font-mono.md),
[T3](tongduyan_plan01-t3-focus-ring-hint-mark.md). T2b, T5–T7 chưa chạm.

---

## Lỗi thật sự là gì

`Hint.tsx` khai `role="button"` + `tabIndex={0}`, nhưng `onKeyDown` chỉ bắt `Escape`.
Enter và Space không làm gì.

Đây **tệ hơn** là không khai `role` gì cả: `role="button"` là một lời hứa đọc lên cho
screen reader rằng đây là thứ bấm được. Người dùng được báo có cái để bấm, bấm đúng
hai phím mà mọi button đều nhận, và không có gì xảy ra.

Sau [T3](tongduyan_plan01-t3-focus-ring-hint-mark.md) thì tình trạng này còn lộ rõ
hơn: ring đã hiện, nên người dùng bàn phím **thấy** mình đang đứng ở đâu mà vẫn không
làm được gì ở đó.

Thiếu thứ hai, không thuộc bàn phím: **touch**. Không có hover trên màn cảm ứng, mà
bubble chỉ mở bằng `onMouseEnter`/`onMouseMove`/`onFocus` — nên chạm vào dấu `?` trên
điện thoại có thể không mở được gì.

## Vì sao vẫn là `<span>`, không đổi sang `<button>`

Plan đã chốt và tôi xác minh lại bằng code: `Hint` render **bên trong `<label>`** có
chứa control ở ít nhất hai nơi —
[`DeploymentForm.tsx:1074`](../../../../../apps/web/src/components/DeploymentForm.tsx#L1074)
(checkbox) và [`TrafficEditor.tsx:153`](../../../../../apps/web/src/components/TrafficEditor.tsx#L153)
(input number).

`<label>` chứa hai phần tử labelable là HTML không hợp lệ, và đổi thẻ đúng chuẩn thì
phải đưa `Hint` ra ngoài `<label>` ở **44 call site** hiện có — không còn là bug fix
hẹp. Nên giữ `<span role="button">` và bù cho đủ pattern.

## Đã sửa

`apps/web/src/components/Hint.tsx`.

### Bàn phím — Enter/Space toggle

```tsx
onKeyDown={(event) => {
  const action = hintKeyAction(event.key);
  if (action === "ignore") return;
  if (action === "close") { setAt(null); return; }
  /* Space scrolls the page unless this is here. */
  event.preventDefault();
  setAt(at ? null : cornerOf(event.currentTarget));
}}
```

- Tab tới → `onFocus` mở sẵn (hành vi cũ, giữ nguyên). Enter/Space sau đó đóng, bấm
  tiếp mở lại — đúng nghĩa toggle.
- `preventDefault()` chỉ chạy trên Enter/Space, nên **Tab không bị nuốt** — nuốt Tab
  là nhốt focus lại trên dấu `?`.
- Escape vẫn là đường đóng riêng, không gộp vào toggle: đóng cái đang đóng không phải
  là mở nó ra.

### Touch — tap mở được, và click không chạm tới label

```tsx
onClick={(event) => {
  event.preventDefault();
  if (at === null) setAt(cornerOf(event.currentTarget));
}}
```

`preventDefault()` ở đây **không phải vì phần tử này** mà vì cái `<label>` bọc ngoài:
click lọt tới label sẽ kích hoạt checkbox/input mà label sở hữu — tức là trỏ vào lời
giải thích thì lại bật/tắt đúng cái thiết lập đang được giải thích.

Nhánh mở chỉ chạy khi `at === null`. Trên desktop, hover đã mở bubble trước khi click
xảy ra nên nhánh này không chạy — nếu chạy, nó sẽ đánh nhau với `onMouseMove` đang
bám theo con trỏ. Đường duy nhất tới nhánh này là **touch**, nơi không có hover.

### Tách hai hàm thuần

`hintKeyAction(key)` và `cornerOf(mark)` được tách ra khỏi thân handler. Lý do ở mục
test bên dưới. `cornerOf` tiện thể xoá luôn đoạn tính `getBoundingClientRect()` lặp
ba lần (`onFocus`, keydown, click).

## Test — vì sao tách hàm chứ không viết DOM test

`vitest.config.ts` nói thẳng: **không có jsdom, không có testing-library**, môi trường
là Node, và giới hạn này được ghi trong `docs/KNOWN_LIMITATIONS.md`. Nên không thể
bắn sự kiện bàn phím thật.

Lối repo tự chọn cho tình huống này đã có sẵn, ghi trong header của
`running-comparison.test.tsx`: *"the decisions it makes … live in `lib/running.ts` and
are tested directly there"* — tức **đẩy quyết định ra hàm thuần rồi test hàm đó**. Tôi
theo đúng lối đó thay vì viết một test đọc chữ trong file rồi gọi là đã kiểm.

Thêm **5** test vào `hint.test.tsx` (tổng file giờ 12):

| Test | Canh cái gì |
|---|---|
| *treats Enter and Space as the press* | `hintKeyAction("Enter")` và `(" ")` → `toggle` |
| *keeps Escape as the way out* | → `close`, tách khỏi toggle |
| *leaves every other key to the browser* | `Tab`, `a`, `ArrowDown`, `Shift`, `Spacebar` → `ignore` |
| *stops Space from scrolling the page* | `onKeyDown` còn gọi `preventDefault()` |
| *stops a click from reaching the label that owns an input* | `onClick` còn gọi `preventDefault()` |

Hai test cuối **đọc chữ trong file** — không có DOM thì không chạy được `preventDefault`
để xem nó ngăn cái gì. Tôi ghi rõ giới hạn đó ngay trong comment của test, không để nó
trông như một kiểm chứng hành vi.

**Một cái bẫy trong chính hai test đó, đã bịt:** helper cắt thân handler theo `}}` đầu
tiên. Cả hai handler đều gọi `preventDefault()`, nên nếu lát cắt tràn sang handler kế
bên thì test sẽ **xanh nhờ lời gọi của hàng xóm** trong khi guard thật đã bị xoá. Helper
giờ ném lỗi nếu thân cắt ra còn chứa một prop `onXxx={` khác.

### Kiểm chứng chính test đó — hai lần đột biến

| Đột biến | Kết quả |
|---|---|
| Xoá `event.preventDefault()` khỏi `onClick` | *stops a click from reaching the label…* **đỏ** (1 failed / 11 passed) |
| Bỏ `\|\| key === " "` khỏi `hintKeyAction` | *treats Enter and Space as the press* **đỏ** (1 failed / 11 passed) |

Khôi phục → **12/12 xanh**.

## Kiểm chứng

- `npx vitest run src/components/__tests__/hint.test.tsx` → **12/12 xanh**.
- `npx vitest run deployments-page + decision-prose + running-comparison` → **216/216
  xanh**. Ba suite này chạm `Hint` hoặc đọc `globals.css`.
- `npx tsc --noEmit` → **exit 0**.
- CRLF giữ nguyên ở cả `Hint.tsx` lẫn `hint.test.tsx`.

**Giới hạn phải nói rõ — ba ô nghiệm thu của T4 chưa có máy nào kiểm:**

1. *Space không cuộn trang* — kiểm được là `preventDefault()` còn nằm đó, không kiểm
   được là trang không cuộn.
2. *Tap trên touch mở bubble* — không có thiết bị cảm ứng trong test.
3. *Click dấu `?` trong form deployment không toggle checkbox của label* — đây là ô
   quan trọng nhất của T4 và nó **vẫn là kiểm tay**. Lập luận thì chắc (`preventDefault`
   trên sự kiện click chặn activation behavior của label theo spec), nhưng lập luận
   không phải là chạy thử.

Ba ô này cần anh bấm tay một lượt trên trang deployment trước khi coi T4 là đóng.

## Chưa làm

T2b (`--fg` trên `.latency-playhead`), T5 (câu cảnh báo host tiếng Việt), T6 (test
token), T7 (khuyến nghị phải nêu config).

Nhóm frontend của plan (T1 → T2 → T2b → T3 → T4 → T6) giờ chỉ còn thiếu **T2b** và
**T6**. T2b là một dòng CSS; T6 là test chặn tái phát cho đúng loại lỗi mà T1, T2 và
T2b đều mắc.

**Chưa commit** — anh tự commit.

# Plan 1 · T6 — test chặn tái phát, và bốn lỗi nó tìm ra ngay lần chạy đầu

**Ngày:** 2026-08-21 · **Nhánh:** `tongduyan_3` · **Trạng thái:** xong T6 **và T2b**, **chưa commit**

Nguồn: [01-bug-fix-token-i18n-a11y.md](../../plans/2026-08-21/01-bug-fix-token-i18n-a11y.md) — task T6 (và T2b, xem bên dưới).
Tiếp sau [T1](tongduyan_plan01-t1-token-hint-mark.md), [T2](tongduyan_plan01-t2-font-mono.md),
[T3](tongduyan_plan01-t3-focus-ring-hint-mark.md), [T4](tongduyan_plan01-t4-hint-keyboard-touch.md),
[T5](tongduyan_plan01-t5-host-warning-i18n.md). Còn lại: **T7**.

---

## Việc chính: kết quả lần chạy đầu tiên

Plan viết T6 để chặn tái phát ba lỗi T1, T2, T2b. Chạy lần đầu, test báo **năm** token
được đọc mà chưa từng được khai — ba cái plan biết, và **hai tên nữa plan chưa từng
nhắc**, thực chất là **bốn chỗ** hỏng:

| Token | Dùng ở | Hậu quả thật |
|---|---|---|
| `--fg` | `.latency-playhead` (T2b) | có fallback `#111827` — playhead gần như tàng hình trên dark |
| `--surface` | `.decision-deployment-map` + `.decision-deployment-skeleton` | **không** fallback — `background` thành `transparent` |
| `--surface-2` | `.chat-history li:hover, li.active` | nền hover/selected **không hiện** |
| `--surface-3` | `.chat-history-delete:hover` | nền nút xoá khi hover **không hiện** |
| `--danger` | `.chat-history-delete:hover` | màu chữ rơi về kế thừa, nút xoá không đỏ |

Đây đúng là điều T6 tồn tại để làm, và nó tự chứng minh ngay ở lượt chạy đầu: ba lỗi
được tìm bằng mắt trong một buổi review, còn năm lỗi được tìm trong một giây bằng máy.

Bốn chỗ ngoài `--fg` **hỏng nặng hơn** T1: `--fg` còn có fallback, còn `--surface*` và
`--danger` thì không, nên `background`/`color` bị bỏ hẳn. Mục chọn/hover của danh sách
chat và nền bản đồ deployment đang **không có nền**.

## Đã sửa — năm token, ánh xạ theo tiền lệ có sẵn, không tự đặt màu

Nguyên tắc: mỗi token thiếu ánh xạ về token mà **chính stylesheet này** đã dùng cho
đúng việc đó, chứ không phải màu tôi thấy hợp mắt.

| Cũ | Mới | Vì sao — bằng tiền lệ trong file |
|---|---|---|
| `--surface` | `--canvas-bg` | mọi khung bản đồ khác đã dùng nó (`.simulate-map-panel:1937`, `.map-view:1942`), **và** `:2529` trộn đúng cặp `--canvas-bg` với `--panel` y như dòng skeleton này trộn |
| `--surface-2` | `--panel-2` | nấc nền trung tính thứ nhất của sheet |
| `--surface-3` | `--panel-3` | nấc thứ hai, cho hover đậm hơn |
| `--danger` | `--err` | tên màu lỗi của sheet |
| `--fg` | `--text` | đúng như plan T2b chốt |

Tiền lệ ở `:2529` là chỗ quyết định cho `--surface`: nếu ánh xạ về `--panel` thì
`color-mix(in srgb, var(--panel) 75%, var(--panel))` **bằng đúng `--panel`** — một phép
trộn tự triệt tiêu, và skeleton sẽ chìm vào chính khung chứa nó, tức là mất luôn tác
dụng "đang tải". `--canvas-bg` giữ được tương phản mà cấu trúc cũ định mã hoá.

**T2b coi như xong luôn ở đây.** Nó là một trong năm dòng trên. Tôi không thể để test
đỏ rồi báo là T6 xong.

### Một chỗ để lại, không tự quyết

`.chat-history li:hover` và `li.active` **dùng chung một khai báo**, nên một giá trị
phải phục vụ cả hai. Tôi để `--panel-2` cho cả hai. Nhưng phần còn lại của app đánh dấu
trạng thái *đang chọn* bằng tông accent (`button.active:723`,
`.map-view-switch button.active:2339` — `--accent-soft` + `--accent`), chứ không phải
bằng một nền xám. Tách `.active` ra dùng accent là **đổi thiết kế**, không phải sửa lỗi,
nên tôi không tự làm — nêu ở đây để anh quyết.

## Test — `apps/web/src/app/__tests__/tokens.test.ts`

Đúng hợp đồng plan chốt:

- Đọc `globals.css`, **strip toàn bộ comment `/* … */` trước khi chạy regex**. Đây là
  phần chịu lực, không phải dọn dẹp: file này ghi chú token bằng văn xuôi, một dòng
  `--foo:` nằm trong comment mà không strip sẽ **bảo lãnh** cho một token không ai khai.
  Chiều ngược lại cũng vậy — comment của T2 có nhắc `var(--font-mono-loaded, …)`, và nó
  **không được** tính là một lượt dùng.
- Tập token được đọc ⊆ tập được khai ∪ allowlist.
- **`var()` có fallback không được miễn.** `var(--fg, #111827)` chính là hình dạng mà
  lỗi nặng nhất đã trốn: nó có sẵn câu trả lời cho token thiếu nên không bao giờ trông
  như hỏng.
- Allowlist là **mảng có tên**, không phải pattern:
  ```ts
  const JSX_PROVIDED = ["--cols", "--delta-col"];
  const NEXT_FONT_PROVIDED = ["--font-sans-loaded", "--font-mono-loaded"];
  ```
  Thêm ngoại lệ = sửa mảng = reviewer nhìn thấy.

Thêm một test "reads enough tokens for that to mean something" (>50 mỗi tập): nếu regex
hỏng và khớp **rỗng**, phép kiểm tập con sẽ xanh vì không tìm thấy gì. Đây là chốt chặn
cho chính cái test kia.

Bốn test nữa kiểm **bộ đọc**: khai báo trong comment không tính, lượt dùng trong comment
không tính, lượt dùng có fallback vẫn tính, khai và dùng đếm độc lập.

### Kiểm chứng chính test đó — bốn lần thử

| Thử | Kết quả |
|---|---|
| Đổi một tham chiếu thành `var(--khong-ton-tai)` | **đỏ**, nêu đích danh token |
| Thêm `var(--cols, 2)` — allowlisted, **có** fallback | **xanh** (đúng ô nghiệm thu của plan) |
| Đổi đúng dòng đó thành `var(--rows, 2)` — không allowlisted | **đỏ** — chứng minh allowlist là danh sách, không phải mẫu |
| Xoá khai báo `--font-mono` (tái tạo lỗi T2) | **đỏ** |

Thử thứ ba quan trọng hơn nó trông: nếu không có nó thì "xanh" ở thử thứ hai có thể chỉ
là do test bỏ qua mọi `var()` có fallback, chứ không phải do allowlist làm việc.

## Kiểm chứng

- `tokens.test.ts` → **6/6 xanh**.
- 5 suite web liên quan (`tokens`, `hint`, `running-comparison`, `decisions`,
  `decisions-page`) → **217/217 xanh**. Hai trong số đó đọc thẳng `globals.css`.
- `npx tsc --noEmit` → **exit 0**.
- `git diff` globals.css: **+6/−6**, đúng năm dòng token. CRLF giữ nguyên cả hai file.

**Giới hạn:** test này khẳng định mọi token **được khai ở đâu đó** trong `globals.css`.
Nó **không** khẳng định token được khai trong **đúng scope theme** — một token chỉ khai
trong `[data-theme="light"]` sẽ qua được test mà vẫn hỏng ở dark. Cũng không kiểm token
đã khai mà **không ai dùng** (hiện có ít nhất một). Cả hai đều bắt được, nhưng là một
test khác và không thuộc T6.

Và như mọi lần trước: bốn chỗ vừa sửa **chưa mở trình duyệt xem**. Cái tôi khẳng định
được là chúng không còn đọc token rỗng; việc `--canvas-bg` là sắc nền *đúng* cho khung
bản đồ thì dựa vào tiền lệ trong file, chưa dựa vào ảnh chụp.

## Ngoài phạm vi chữ của plan

Plan giao T6 = viết test. Tôi làm thêm: **sửa bốn token hỏng** mà test tìm ra
(`--surface`, `--surface-2`, `--surface-3`, `--danger`) — không sửa thì không thể để
test xanh, mà một test đỏ nằm lại trong repo là thứ người sau sẽ bỏ qua. `--fg` thì
vốn đã là T2b trong plan.

## Chưa làm

**T7** — khuyến nghị phải nêu config, không chỉ tên stack. Chạm ba tầng
(`page.tsx` × 2 bề mặt, `ConclusionPanel`, `decision_export.py`).

T4, T5, T6 **đều chưa commit**.

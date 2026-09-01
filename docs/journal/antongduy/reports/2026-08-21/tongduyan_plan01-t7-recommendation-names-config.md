# Plan 1 · T7 — khuyến nghị phải nêu config, không chỉ tên stack

**Ngày:** 2026-08-21 · **Nhánh:** `tongduyan_3` · **Trạng thái:** xong T7 — **Plan 1 hết task**, **chưa commit**

Nguồn: [01-bug-fix-token-i18n-a11y.md](../../plans/2026-08-21/01-bug-fix-token-i18n-a11y.md) — task T7.
Tiếp sau [T1](tongduyan_plan01-t1-token-hint-mark.md), [T2](tongduyan_plan01-t2-font-mono.md),
[T3](tongduyan_plan01-t3-focus-ring-hint-mark.md), [T4](tongduyan_plan01-t4-hint-keyboard-touch.md),
[T5](tongduyan_plan01-t5-host-warning-i18n.md), [T6+T2b](tongduyan_plan01-t6-token-test.md).

---

## Lỗi thật sự là gì

Hai candidate của một phép so local-controller **dùng chung một stack** — cả hai đều
`astar+dwa` — và thứ phân biệt chúng là `local_controller_config`: `dwa_coarse` với
`dwa_balanced`.

Nên bốn bề mặt in mỗi tên stack đang trả lời câu hỏi *"cái nào thắng"* bằng một chuỗi
**đúng với cả hai**. Đây là lỗi về **thông tin**, không phải về trình bày: câu
"Use astar+dwa" không sai, nó chỉ không xác định được đối tượng nào — mà xác định đối
tượng chính là toàn bộ việc của một khuyến nghị.

## Nguồn dữ liệu — vì sao không lấy thẳng từ card

`card.recommended` chỉ có `{ candidate_id, stack, params_ref }` — **không có config**.
Config nằm trên hàng candidate, nên đường lấy bắt buộc là:

```
card.recommended.candidate_id  →  tìm trong report.candidates  →  local_controller_config
```

Pattern này đã tồn tại sẵn trong `runOutcome()` (trang list làm đúng y thế). Plan yêu
cầu **tái dùng, không viết lần hai**.

## Đã sửa

### Frontend — một helper, ba bề mặt

Rút `recommendedCandidateLabel(run)` trong `decisions.ts`, và cho `runOutcome()`
**gọi lại chính nó** thay vì giữ bản sao thứ hai của cùng phép tra cứu. Sau bước này
toàn app chỉ còn **một** chỗ biết cách đặt tên cho khuyến nghị.

| Bề mặt | Trước | Sau |
|---|---|---|
| Trophy badge (`page.tsx:170`) | `run.card.recommended.stack` | `recommendedCandidateLabel(run)` |
| `CardPanel` Figure (`page.tsx:1334`) | `card.recommended.stack` | `recommendedCandidateLabel(run)` |
| Câu "Use …" (`ConclusionPanel.tsx:127`) | `winner?.stack_label` | `winnerLabel` = `stack_label · config` |
| Dòng summary trang list (`runOutcome`) | bản sao phép tra cứu | gọi helper |

**`ConclusionPanel` — không đụng `conclusion.ts`**, đúng như plan chốt. `Standing.label`
còn được render **cạnh** `<code>{standing.config}</code>` ở dòng candidate, và còn làm
accessible name cho thanh điểm; gộp config vào đó sẽ in config **hai lần** trong một
dòng và đổi luôn tên đọc lên của thanh điểm. Nên headline tự ghép chuỗi của nó.

### Fallback cho artifact cũ — không im lặng

Không tìm thấy candidate khớp → `stack · candidate_id`. Hash là một cái tên tệ; **không
có tên nào** còn tệ hơn, vì badge sẽ hiện rỗng ngay cạnh cái cúp.

### Export — thêm dòng, không đổi dòng cũ

`decision_export.py`: thêm helper `recommended_config(report, candidate_id)` và một
dòng mới `("Recommended config", …)` **ngay cạnh** dòng `Recommended` — dòng cũ giữ
nguyên từng chữ, để bản xuất của run cũ diff sạch với bản ai đó đã lưu. Không khớp
được → `"not recorded"`, tách khỏi `NOT_MEASURED` ("not measured") vì đây không phải
số đo thiếu mà là **file không ghi**.

### Một chỗ tôi sửa lại sau khi tự test bắt được

Lần đầu tôi viết fallback ở hai bề mặt page là `?? card.recommended.stack`. Test mới
đỏ, và nó đúng: cả hai bề mặt chỉ render **khi đã có card**, nên helper không bao giờ
trả `null` ở đó — nhánh đó vừa **không thể chạy tới**, vừa là đúng cái "in mỗi tên
stack" mà T7 đang đi xoá. Đổi thành `?? …candidate_id`.

## Kiểm chứng

- **Toàn bộ web suite: 58 file, 1326 test, xanh hết.** Chạy full ở đây là có chủ đích —
  plan xếp T7 ở mức rủi ro **Trung bình** vì đổi câu "Use …" có thể làm đỏ snapshot của
  `ConclusionPanel`/`conclusion`.
- **Rủi ro đó không xảy ra — và điều đó tự nó là một phát hiện:** không snapshot nào đỏ
  vì **không có test nào canh câu headline**. Câu kết luận của cả trang đang không có
  gì bảo vệ. Tôi đã thêm test cho nó (xem dưới).
- `npx tsc --noEmit` → **exit 0**.
- `tests/api/test_decision_markdown.py` → **24/24**; `ruff check` sạch.
- CRLF giữ nguyên ở cả 7 file bị chạm.

### Test đã thêm

TypeScript (`decisions.test.ts`, +4): tra cứu ra đúng config **trong đúng tình huống
một stack hai config**; không khuyến nghị ai → `null`; artifact cũ → `stack · id` chứ
không im; và `runOutcome().winner` **bằng đúng** helper — tức là không có đường tra cứu
thứ hai.

Nguồn (`decision-prose.test.tsx`, +3): headline có `local_controller_config`;
`conclusion.ts` **không** ghép config vào label (chặn đúng cái lỗi in hai lần);
`page.tsx` không còn `card.recommended.stack}` và gọi helper **đúng 2 lần**.

Python (`test_decision_markdown.py`, +5): đọc đúng config; **dòng `Recommended` cũ
không đổi**; hàng candidate không có config → `not recorded`; card trỏ tới candidate
report đã mất → `not recorded`; không bao giờ trả ô rỗng.

### Đột biến — hai lần phá, hai lần đỏ

| Đột biến | Kết quả |
|---|---|
| Helper trả `stack_label` trần | **2 test đỏ**, trong đó **một test có sẵn từ trước** (*"names the winner by stack and controller rather than by hash"*) — nên việc cho `runOutcome` gọi helper không phá hợp đồng cũ |
| Xoá dòng `Recommended config` khỏi export | **3 test đỏ** |

## Giới hạn

- **Chưa mở trình duyệt.** Cái kiểm được là chuỗi mà các hàm sinh ra và mã nguồn các bề
  mặt gọi gì; việc badge/figure/headline **hiện ra** đúng vẫn là nhìn tay.
- Ba test nguồn ở `decision-prose.test.tsx` là **đọc chữ trong file**, không phải chạy
  component — cùng giới hạn không-jsdom như T3/T4, ghi rõ trong comment từng test.
- Test đếm `recommendedCandidateLabel(run)` **đúng 2 lần** trong `page.tsx` sẽ đỏ nếu
  sau này thêm bề mặt thứ ba hợp lệ. Đó là **cố ý**: thêm một chỗ gọi thì phải sửa con
  số, và người sửa nhìn thấy mình đang thêm một nơi nữa nói về khuyến nghị.

## Plan 1 — trạng thái sau T7

| Task | Trạng thái |
|---|---|
| T1 `--text-muted` | xong, **đã commit** `1e24f3e` |
| T2 `--font-mono` | xong, **đã commit** `7b9d525` |
| T3 focus ring | xong, **đã commit** `01d62b1` |
| T2b `--fg` | xong (làm trong T6), **chưa commit** |
| T4 Enter/Space + touch | xong, **chưa commit** |
| T5 i18n host warning | xong, **chưa commit** |
| T6 test token | xong, **chưa commit** |
| T7 khuyến nghị nêu config | xong, **chưa commit** |

**Hết task của Plan 1.** Bốn ô nghiệm thu cấp plan vẫn cần anh bấm tay, tôi không đánh
dấu hộ: dấu `?` xám và ring 2px trên trang thật; Enter/Space/tap và click-trong-label ở
form deployment; playhead nhìn thấy ở cả hai theme; và banner EN — ô này còn cần **một
run mới mang `warning_code`**, vì mọi artifact đang có đều là run cũ nên trang sẽ đi
nhánh fallback tiếng Việt (đã nói kỹ trong [report T5](tongduyan_plan01-t5-host-warning-i18n.md)).

**Chưa commit** — anh tự commit.

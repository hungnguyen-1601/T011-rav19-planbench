# Rubric r0.2.0 — thêm một trục chấm theo episode

**Ngày:** 2026-08-30 · **Nhánh:** `tongduyan_analyst-episode` (worktree `P-011-merge`)

Lý do và bằng chứng ở
`notes/2026-08-30/tongduyan_rubric-cu-khong-nhin-thay-loi-chinh.md`.
Đây là phần đã đổi trong code.

## Đã sửa

| Chỗ | Việc |
|---|---|
| `services/analyst_service/planbench_analyst/preregistration_episode.py` | `rubric` `r0.1.0` → `r0.2.0`, kèm amendment có ngày nêu rõ **bar khó lên, không dễ đi** |
| `scripts/rubric_sheet_by_episode.py` | thêm `answerable()`, `episode_mark()`, `marks_already_given()`, cờ `--carry` |
| `tests/test_rubric_sheet_r020.py` | mới, 12 test |

## R6 — chấm theo episode, không theo câu

| mức | nghĩa |
|---|---|
| `explains` | nêu mechanism khác nhau giữa hai bên **và** nối vào kết quả, có ref mở được |
| `describes_only` | đúng, nhưng chỉ tả chuyện gì xảy ra |
| `silent_wrongly` | packet đủ để trả lời mà không nói gì |
| `silent_correctly` | packet thật sự không đỡ được câu why |
| `wrong` | khẳng định một why mà packet phản lại |

**Mẫu số do sheet tính, không phải người chấm quyết.** Episode nào có ít
nhất một contrast `support` thì dưới tiêu đề in dòng
`packet co the tra loi why`. Lý do: một arm im lặng có hai cái cớ rất
khác nhau — packet có mechanism mà nó bỏ lỡ, hay packet không có gì và im
lặng là đúng — và phân biệt hai cái đó quyết định im lặng có bị tính là
sai không. Bắt người chấm tự suy ra từ bảng packet, 30 lần, là đặt mẫu số
vào cùng tay với tử số.

`support` là chữ **packet tự gán**, không phải ý kiến thứ hai về bằng
chứng. `context` chỉ nói hai stack khác nhau ở đâu đó — không phải
mechanism, và im lặng trước nó là đúng.

## `--carry` — không bắt chấm lại cái đã chấm

r0.2.0 không đổi luật R1–R5 nào, nên không được hỏi lại chúng. Phát lại
37 block trống nghĩa là bắt suy lại những dấu đã có, với đáp án cũ hiện
ngay màn hình bên cạnh — đó không phải lần chấm độc lập thứ hai, đó là
bản sao chậm của lần đầu, có thêm chỗ để trôi.

`--carry <sheet cũ>` đọc R1–R5 theo khoá `(episode, số block)`. Khoá an
toàn vì thứ tự block sinh từ hash danh tính của chính item, nên cùng
artifact sinh ra cùng thứ tự.

**Một cái bẫy đã sập rồi mới thấy:** packet cũng là bảng 4 cột, in ngay
dưới tiêu đề episode. Bản đầu tiên đọc 61 dấu thay vì 37 vì nó cuốn cả
dòng contrast vào. Hai chỗ reset chặn việc đó — ở tiêu đề episode và sau
khi bắt xong mỗi block.

## Sheet đã sinh

`P-011-merge/docs/antongduy/notes/2026-08-30/tongduyan_cham-holdout-r020.md`

```
37 muc | 30 episode
37 muc mang sang tu tongduyan_cham-holdout-v2.md; R6 con trong
```

Kiểm lại: 18 `should_have`, 12 `holds`, 6 `plausible_other`, 1 `wrong` —
**trùng khít bản An đã chấm**, không lệch một dấu. 30 bảng R6 trống. Mẫu
số máy tính ra: **18 episode có contrast `support`**, 12 episode không.

## Test

`tests/test_rubric_sheet_r020.py` — 12 pass. `ruff check` + `format` sạch.
`test_episode_experiment_scoring.py` + `test_analyst_service_wiring.py` —
11 pass (hai file duy nhất chạm preregistration).

**Cổng có cắn:**

| tiêm | kết quả |
|---|---|
| `answerable` nhận cả `context` | 2 đỏ |
| bỏ **cả hai** chỗ reset trong `marks_already_given` | 1 đỏ |
| bỏ **một** chỗ reset | xanh — hai chỗ che cho nhau trên sheet hình dạng bình thường |

Case cuối đã ghi thẳng vào docstring thay vì bịa thêm assertion bám vào
hình dạng vòng lặp. Test ghim **kết quả** (đếm đúng 2 dấu), không ghim
từng nhánh code.

## Ràng buộc đã giữ

Đổi rubric sau khi thấy kết quả là đúng cái CLAUDE.md §8 cấm. Hợp lệ ở
đây vì:

- Bar **khó lên**: không mục nào được chấm lại nhẹ tay hơn.
- Số r0.1.0 **giữ nguyên**, không ghi đè.
- Amendment **có ngày**, nằm trong source, có test bắt nó phải có ngày và
  phải nói bar đi hướng nào.
- Artifact đã ghi giữ `preregistration_checksum` cũ, không phát biểu lại
  dưới id mới.

## Còn lại

- An chấm cột R6 cho 30 episode.
- Có mốc rồi mới quyết chạy lại arm đủ 3 flag (~$0.42).
- Chưa rà `quantity_in_statement` xem có quá rộng không.

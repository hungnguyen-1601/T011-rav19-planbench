# Rubric r0.1.0 không nhìn thấy được lỗi chính của arm

**Ngày:** 2026-08-30 · **Loại:** quan sát trên dữ liệu đã chấm, không đổi dòng code nào ở phần này

An đặt câu hỏi: rubric đang chấm "AI có nói được điều gì đúng và có
evidence không", trong khi mục tiêu là "AI có giải thích được vì sao A
hơn B trong chính episode này không". Khảo sát lại `holdout-b1` cho thấy
độ lệch đó không phải chuyện nguyên tắc — nó chiếm nửa mẫu, và nửa đó
toàn là hỏng.

## 1. Nửa mẫu không vào con số

`docs/antongduy/notes/2026-08-30/tongduyan_cham-holdout-v2.md`, arm
`holdout-b1`, 30 episode:

| | số |
|---|---|
| block tổng | 37 |
| block có câu nói | 19 |
| block **im lặng** | 18 |
| R5 chấm `should_have` | **18** |
| R5 chấm `correct` | **0** |

*(Bản đầu của ghi chú này viết ngược — 19 im lặng / 18 câu nói. Sai do
đếm `grep` bắt trúng cả dòng chú giải R5 trong phần đầu sheet. Số đúng
là 18 im lặng, và nó khớp với 18 lý do abstain đếm được ở mục 2.)*

R1 trên các câu có nói: 12 `holds`, 6 `plausible_other`, 1 `wrong`.

An **đã** phán quyết ở tầng episode rồi, qua cột R5: mọi lần im lặng đều
đáng lẽ phải nói. Nhưng con số headline (~0.71) là precision trên 19 câu
mà arm **tự chọn** viết ra. Một câu không bao giờ được viết thì không có
dòng nào trong rubric, nên 18 lần im lặng không kéo con số xuống chút
nào.

Hệ quả: **rubric r0.1.0 đạt điểm tối đa bằng cách không nói gì.**

## 2. Im lặng không phải do packet rỗng

Đếm lý do abstain trên 18 block có ghi lý do:

```
17  (quantity_in_statement)
 1  (quantity_in_statement, wording_above_associated)
 0  vì packet không có gì để nói
```

Không lần nào là "không có gì để nói". Ví dụ episode `7323e60af732`,
packet có contrast **strength = support**:

> `contrast:detection_worse_on_loser:1` — stuck_cluster fired on both,
> and materially worse on C5; severity ratio = 4.5; stopped seconds =
> 5.85 (C5) vs 1.3 (C1)

Đó đúng là câu trả lời cho "vì sao C1 hơn C5 ở episode này". Model có,
viết ra, và bị guard giết vì **viết con số thay vì cite nó** — trong khi
con số đó nằm ngay trong packet.

## 3. Ba thứ chống im lặng đều TẮT ở arm được chấm

Đọc `runtime_config` trong artifact:

| arm | `reword_once` | `magnitude_placeholders` | `floor_when_silent` |
|---|---|---|---|
| `holdout-b1` | ✗ | ✗ (chưa có) | ✗ (chưa có) |
| `holdout-magnitudes` | ✗ | ✓ | ✗ |
| `stage5-reword` | ✓ | ✗ | ✗ |

**Chưa arm nào chạy với đủ cả ba.** Nên 0.71 không đo cấu hình đang có
trong code — nó đo một cấu hình không còn tồn tại.

## 4. Kết luận

Hai điều tách bạch, không thay nhau được:

- **R1–R5 đo an toàn** — trong những câu đã nói, bao nhiêu câu đúng và
  cite được. Kết quả 0 câu sai là thật và phải giữ.
- **Không có gì đo tính hữu dụng** — episode này có được giải thích hay
  không. Đó là cái An hỏi, và r0.1.0 không có chỗ để trả lời.

Đã sửa thành r0.2.0 — chi tiết ở
`reports/2026-08-30/tongduyan_rubric-r020-them-truc-episode.md`.

## 5. Việc chưa làm

- Chấm R6 cho 30 episode của `holdout-b1` (sheet đã sinh sẵn, R1–R5 giữ
  nguyên, chỉ còn cột R6 trống).
- Sau khi có mốc đó mới quyết có chạy lại arm đủ 3 flag (~$0.42) hay
  không.
- Chưa rà `quantity_in_statement` xem nó có quá rộng không. `reword_once`
  đã được dựng đúng cho ca này nhưng chưa bao giờ được đo dưới một rubric
  nhìn thấy được im lặng.

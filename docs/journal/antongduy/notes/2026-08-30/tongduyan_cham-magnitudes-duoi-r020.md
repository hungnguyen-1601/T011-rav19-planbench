# `holdout-magnitudes` chấm dưới r0.2.0 — điểm thứ hai, giá $0

**Ngày:** 2026-08-30 · **Người chấm:** Claude · **Không phải bản An chấm**

Sheet: `P-011-merge/docs/antongduy/notes/2026-08-30/tongduyan_cham-magnitudes-r020.md`

## Cảnh báo trước khi đọc số

1. **Người chấm không mù arm.** Prereg ghi `blind_to_arm_single_scorer`.
   Tôi biết đây là `holdout-magnitudes` và đã dự đoán trước kết quả
   (7 im lặng vỡ, mất 1 `explains`) rồi mới chấm. Bản này **chỉ báo**,
   không thay được một lượt An chấm mù.
2. **Cột R1–R5 chưa so được.** `--carry` mang sang dấu r0.1.0, dùng từ
   vựng cũ (`plausible_other`), và thiếu cột R4 An thêm tay khi chấm lại
   `holdout-b1`. Chỉ **R6** so được giữa hai arm.
3. Nửa im lặng của R6 là **tất định** — `(arm im lặng?) × (packet có
   contrast support?)` — nên 13/30 episode không có chỗ cho thiên lệch.
   Chỉ 17 episode có nói là phải đọc.

## Kết quả

Cùng 30 episode, cùng mẫu số **18 episode có contrast `support`**.

| R6 | `holdout-b1` (An chấm) | `holdout-magnitudes` (Claude chấm) |
|---|---|---|
| `explains` | 2 | **6** |
| `describes_only` | 9 | 8 |
| `wrong` | 1 | **3** |
| `silent_wrongly` | 13 | **8** |
| `silent_correctly` | 5 | 5 |

**explains / 18** — chặt: **0.11 → 0.33**. Rộng (tính 2 ca ranh giới):
**0.11 → 0.44**.

0 mâu thuẫn với mẫu số máy tính.

## Đọc thế nào

**Cơ chế đúng như dự đoán.** `magnitude_placeholders` cho model một
đường hợp lệ để nêu con số, nên các câu trước đây bị
`quantity_in_statement` giết giờ đi qua được. `silent_wrongly` 13 → 8.

**Nhưng `wrong` tăng 1 → 3.** Đây là cái giá, và nó không nhỏ:

| episode | packet có support | câu nói |
|---|---|---|
| `91ec9d58e922` | có | *"costmap_inflation refused to maintain clearance above the minimum threshold 0.15"* |
| `c20848d51f24` | **không** | *"global_planner of C1 generated a path with lower minimum clearance… causing C1 to slow down"* |
| `d663910f7e0f` | **không** | *"The global_planner component difference **explains why** C5 achieved higher min clearance…"* |

`91ec9d58e922` đáng chú ý nhất: packet **không có** thành phần
`costmap_inflation` (chỉ có global_planner, local_controller,
local_controller_config) và **không có** ngưỡng `0.15` (chỉ có
`min_clearance = 0.148568`). Model bịa cả chủ thể lẫn ngưỡng. Dưới
r0.1.0 câu này được chấm `plausible_other` + R3=`all` — rubric cũ không
bắt được.

Hai câu còn lại nói `explains why` / `causing` trên episode packet chỉ
có contrast `context`. `component_differs` tự nó ghi rõ *"a mechanism
that explains the difference has to live in one of those"* — tức nó
**không phải** mechanism.

## Nghĩa là gì cho quyết định chi tiền

Đổi lấy 5 lần im lặng bớt đi là 2 khẳng định sai thêm vào. Với sản phẩm
này, một câu sai đắt hơn một lần im lặng — nhưng 3/30 vẫn thấp, và cả 3
đều là dạng **guard nên bắt được**: hai câu attribution trên episode
không có `support`, một câu nêu chủ thể ngoài danh sách thành phần.

Đó là hai luật guard mới, **giá $0**:

- chặn `component_specific_attribution` khi packet không có contrast
  `support` nào
- chặn statement nêu subject không nằm trong thành phần packet liệt kê

Nếu hai luật đó bắt đúng 3 ca này thì `wrong` về 0–1 mà `explains` giữ
nguyên 6.

## Việc tiếp

1. **$0** — viết hai luật guard trên, đo lại trên chính artifact đã có.
2. **$0** — An chấm mù lại sheet này nếu muốn con số vào báo cáo chính
   thức; bản của tôi không đủ tư cách thay.
3. **~$0.6** — chỉ nên chi sau bước 1, vì lúc đó arm đủ 3 flag mới đáng
   đo: `reword_once` chưa từng chạy trên 30 episode này, và nó tấn công
   đúng 8 lần im lặng còn lại.

# Arm `ep_deployment` đã chạy — $0.68, và một con số dễ đọc nhầm

**Ngày:** 2026-08-30 · **Nhánh:** `tongduyan_analyst-episode` (worktree `P-011-merge`)
**Artifact:** `artifacts/analyst-episode-experiments/holdout-deployment.json`
**Sheet chờ chấm:** `P-011-merge/docs/antongduy/notes/2026-08-30/tongduyan_cham-deployment-r020.md`

## Đã chạy gì

Arm mới `ep_deployment` — **ba flag đúng như route API** (`magnitude_placeholders`
+ `floor_when_silent` + `reword_once`), trên đúng 30 episode holdout,
o4-mini, trần $5.

```
in=273458 out=86286 ~$0.68
```

Dưới ngân sách An cấp. Chi phí thật $0.6805, sát ước tính $0.55–0.65.

## Con số dễ đọc nhầm

**"30/30 episode có câu trả lời, 0 im lặng"** — đúng, nhưng đọc trần
như thế là sai.

| | |
|---|---|
| episode model tự trả lời | **19** |
| episode **floor** trả lời (model im, floor lấp) | **11** |
| proposal do model viết | 24 |
| proposal do floor sinh | 29 |

Floor sinh câu kiểu *"stuck cluster was detected on C1 in this episode"* —
quan sát thuần, không nêu mechanism, không nối vào kết quả. **Với R6 đó
là analyst im lặng**, chỉ khác là người đọc không thấy ô trống.

Sheet đã đánh dấu 11 episode đó bằng dòng `KHONG PHAI MODEL VIET`, kèm
lời nhắc `explains` không chấm được ở đó. Không có dấu này thì bản chấm
sẽ tính công cho analyst đúng ở những lượt nó hỏng nặng nhất.

## Tiến triển thật, trên mẫu số 18 episode có contrast `support`

Số episode **analyst im lặng**:

| arm | im lặng / 18 |
|---|---|
| `holdout-b1` | 13 |
| `holdout-magnitudes` | 8 |
| magnitudes + hai luật guard (tính bằng máy) | 9 |
| **`holdout-deployment`** | **5** |

13 → 5. Trong 9 episode trước đó im lặng: **5 giờ model tự nói**
(`40b620398486`, `56f2bbdf0e74`, `c31f07beacd6`, `8ca3fa8191d8`,
`91ec9d58e922`), 4 còn lại floor lấp.

`reword_once` kích hoạt **16 lượt**.

## Luật mới hoạt động đúng chỗ

`subject_absent_from_episode` bắn **1 lần**. `claim_blocked_by_packet`
bắn **8 lần** — đó là luật 11 làm việc qua packet.

Câu bịa nặng nhất biến mất. `91ec9d58e922` trước là:

> *"costmap_inflation refused to maintain clearance above the minimum
> threshold 0.15"* — thành phần packet không có, ngưỡng không ai đặt

giờ là:

> *"local_controller on C1 encountered a near_miss_cluster with min
> clearance {obs:near_miss_cluster:C1@91ec9d58e922/min_clearance_m}…"*

Subject thật, ref thật, số lấy từ packet qua placeholder.

Hai câu `wrong` còn lại (`c20848d51f24`, `d663910f7e0f`) bị đẩy khỏi
attribution sang mechanism quan sát được, ref `obs:` thật.

## Chưa biết

**`explains` là bao nhiêu — chưa ai chấm.** Sheet 53 mục / 30 episode đã
sẵn sàng. Đây là số duy nhất trả lời câu hỏi gốc của An, và nó cần một
lượt An chấm mù; bản Claude chấm không thay được.

## Trạng thái cổng

| | |
|---|---|
| mọi suite chạm code đã sửa | 1266 pass |
| suite backend đầy đủ | 4233 pass, **9 đỏ** |
| 9 đỏ đó | `test_dwa_core_refactor.py` + `test_host_parity_golden.py` — golden simulator |
| có phải do tôi không | **không**: stash hết thay đổi rồi chạy lại hai file đó ⇒ **10 đỏ**. Nhiều hơn, không ít hơn. |

Không thay đổi nào trong loạt việc này gây thêm một lỗi nào.

## Còn lại

- An chấm sheet `tongduyan_cham-deployment-r020.md`.
- Chưa commit gì. Nhánh `tongduyan_analyst-episode`, `origin/main` chưa nhích.
- 9 lỗi golden simulator có sẵn trên nhánh — chưa ai điều tra, nằm ngoài phạm vi loạt việc này.

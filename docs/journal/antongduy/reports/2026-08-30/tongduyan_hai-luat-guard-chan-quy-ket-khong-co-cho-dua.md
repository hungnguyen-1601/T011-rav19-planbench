# Hai luật guard chặn quy kết không có chỗ dựa

**Ngày:** 2026-08-30 · **Nhánh:** `tongduyan_analyst-episode` (worktree `P-011-merge`)

Nguồn: 3 câu bị chấm `wrong` khi chấm `holdout-magnitudes` dưới r0.2.0 —
xem `notes/2026-08-30/tongduyan_cham-magnitudes-duoi-r020.md`.

## Đo trước khi viết

Cả hai luật được **đo trên artifact đã có** rồi mới viết thành code.

Bản nháp đầu của luật 12 — *"subject phải có fact trong packet"* — bắt
**13/25 proposal**, gồm cả câu đúng như *"Candidate C1 experienced a
local minimum entrapment lasting {obs:…}"*. Lý do: fact `obs:` và `diag:`
**không mang `subject`**, nên `refs_for_subject` rỗng kể cả với subject
hợp lệ. Thu hẹp lại còn *"subject không nằm trong thành phần hai bên khai
báo **và** packet không có fact nào cho nó"* thì còn **1–2 hit**, đúng
mục tiêu.

Đó là lý do bản nháp không được commit: nếu viết trước rồi mới đo, luật
này đã cắt một phần tư sản lượng.

## Luật 11 — không có gì để dựa thì không quy kết thành phần nào

Chỗ cắm: `EpisodePacket.blocked_claim_types`
(`packages/explanation/planbench_explanation/episode_packet.py`)

```python
if not any(contrast.strength == "support" for contrast in self.contrasts):
    blocked.add("component_specific_attribution")
```

Packet tự chấm điểm khác biệt của mình: `context` thu hẹp không gian,
`support` mới cõng được mechanism. Episode mà mọi contrast đều `context`
thì không có gì cõng — nhưng arm vẫn quy kết:

> *"The global_planner component difference **explains why** C5 achieved
> higher min clearance…"*

Nó dựa vào `component_differs`, mà `component_differs` **tự nói** rằng
*"a mechanism that explains the difference has to live in one of those"*
— nó chỉ chỗ để tìm, không khẳng định điều gì đã xảy ra.

**Đặt ở packet, không ở guard.** Blocked type đi theo packet nên model
được báo **trước khi soạn**. Bắt cùng câu đó ở guard thì tốn một lượt và
trả về im lặng — mà im lặng chính là lỗi đang bị đo ở scope này.

Bật trên **12/30 episode** holdout.

## Luật 12 — không quy kết thành phần episode này không ghi nhận

Chỗ cắm: `episode_guard._subject_absent_from_episode`, rule `subject_absent_from_episode`

Taxonomy có 8 subject; một comparison khai báo 3 thành phần mỗi bên, số
còn lại (`costmap_inflation`, `task_geometry`, …) chỉ vào packet khi có
gì đó đo được chúng. Arm viết:

> *"costmap_inflation refused to maintain clearance above the minimum
> threshold 0.15"*

Packet đó **không có** khối robot, **không có** inflation margin,
**không có** ngưỡng nào — chỉ có `min_clearance = 0.148568`, bị làm tròn
thành một giới hạn không ai đặt. Rubric r0.1.0 chấm câu này
`plausible_other` + R3=`all`, vì mọi ref đều mở được. Cái không ref nào
nói tới là costmap inflation.

Luật này **về bản ghi của episode, không phải danh sách đen**: cho packet
một khối robot thì `costmap_inflation` được nêu lại.

## Hiệu quả đo lại trên hai arm đã ghi

| | `holdout-b1` | `holdout-magnitudes` |
|---|---|---|
| proposal | 19 | 25 |
| luật 11 chặn | 7 | 3 |
| luật 12 chặn | 1 | 2 |

R6 của `holdout-magnitudes` sau khi áp (mẫu số vẫn 18):

| | trước | sau |
|---|---|---|
| `explains` | 6 | **6** |
| `describes_only` | 8 | 7 |
| `wrong` | 3 | **0** |
| `silent_wrongly` | 8 | 9 |
| `silent_correctly` | 5 | 8 |

**Mọi câu sai biến mất, không mất câu `explains` nào.** Giá phải trả là
1 episode (`91ec9d58e922`) chuyển từ `wrong` sang `silent_wrongly` — nó
chỉ có đúng một proposal và proposal đó là câu bịa. Đổi một khẳng định
bịa lấy một lần im lặng là đúng hướng cho sản phẩm này.

## Test

`tests/test_episode_attribution_rules.py` — 8 test, pass. Suite episode
10 file — 236 pass. `ruff check` + `format` sạch.

**Cổng cắn, bốn hướng:**

| tiêm | đỏ |
|---|---|
| bỏ luật 11 (`if False`) | 2 |
| luật 11 chặn cả packet có `support` (`if True`) | 1 |
| bỏ luật 12 | 2 |
| luật 12 quên thành phần đã khai báo (bản quá rộng cũ) | 1 |

Hướng thứ hai và thứ tư là quan trọng: chúng bắt **luật quá rộng**, chứ
không chỉ bắt luật bị gỡ.

## Ảnh hưởng cần biết

`blocked_claim_types` đi vào packet nên **checksum packet đổi**. Artifact
đã ghi giữ checksum cũ; arm chạy sau này sẽ khác. Đó là hệ quả bình
thường của việc đổi guard, không phải lỗi.

## Còn lại

- Luật đã sẵn sàng cho arm đủ 3 flag (~$0.6). Đó mới là lượt đo
  `reword_once` trên 30 episode này — nhắm đúng 9 lần `silent_wrongly`
  còn lại.
- An chấm mù lại `holdout-magnitudes` nếu muốn con số vào báo cáo chính
  thức; bản Claude chấm không đủ tư cách thay.

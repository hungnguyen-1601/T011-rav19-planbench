# Luật 13, giá là chặn trên, và một đề xuất của tôi bị phép đo bác

**Ngày:** 2026-08-30 · **Nhánh:** `tongduyan_analyst-episode` (worktree `P-011-merge`)
**Chi phí lần sửa này: $0.** Không gọi model lần nào — mọi phép đo là phát
lại artifact đã trả tiền.

## 1. Đề xuất của tôi sai, và phép đo bắt được trước khi thành code

Tôi đề xuất: *"rule 10 bỏ thay vì hạ cấp khi câu văn so sánh hai bên"*.
Đo trên `holdout-deployment` trước khi viết:

> **giết 5 trong 6 episode An chấm `explains`.** `explains`/18 sẽ tụt
> 0.33 → 0.06.

Vì giải thích "vì sao A hơn B" **chính là** so sánh hai bên. Phần lớn câu
tốt thiếu một mục hợp đồng trong khi vẫn đúng là thứ scope này sinh ra để
làm. Điều này đã ghi vào docstring của luật, không phải chỉ ở đây — lần
sau ai định nới rộng luật sẽ đọc được con số.

## 2. Luật 13 — điều kiện là packet, không phải type

Luật 11 rút `component_specific_attribution`. Khẳng định quay lại dưới
nhãn khác:

```
6a4888cdcf9e  type=local_minimum_entrapment  subject=global_planner
  "global_planner of C5 triggered a replan during the stuck cluster
   while C1 did not"
  refs: contrast:component_differs:1   (context)
```

Chặn một type là chặn một **cái nhãn**, không phải một **nước đi**. Nên
luật 13 hỏi packet: **câu cân hai bên trên packet không có contrast nào
đạt `support` ⇒ bỏ.**

Chỗ cắm: `episode_guard._compares_without_support`, rule
`compares_without_support`. Đọc theo **label**, giống rule 9 — model không
bao giờ thấy candidate id thật.

**Bỏ, không hạ cấp.** Rule 10 giữ-và-hạ-cấp là đúng khi chỉ register sai:
một quan sát về một bên vẫn đúng khi nó thôi tự nhận là giải thích phán
quyết. Ở đây phép so sánh nằm trong chính câu văn, hạ cấp chỉ đổi nhãn
một khẳng định người đọc vẫn gặp nguyên vẹn.

### Đo trên cả ba arm đã ghi

| arm | proposal bị chặn | `explains` mất |
|---|---|---|
| `holdout-b1` | 7 | **0** |
| `holdout-magnitudes` | 1 | **0** |
| `holdout-deployment` | **2** | **0** |

Hai câu ở deployment là đúng hai câu An chấm `wrong`.

R6 của deployment sau khi áp (suy ra bằng phát lại, mẫu số 18):

| | trước | sau |
|---|---|---|
| `explains` | 6 | **6** |
| `describes_only` | 11 | 11 |
| `wrong` | 2 | **0** |
| `silent_wrongly` | 5 | 5 |
| `silent_correctly` | 6 | 8 |

## 3. Giá — sửa cách báo, **không** sửa hằng số

An đo được: chạy thật $0.30, script in $0.6805. Sai 2.3×.

**Không chỉnh `1.10 / 4.40` xuống.** Chúng là cổng chặn tiêu tiền:
`--budget-usd` dừng khi ước tính chạm trần, nên ước tính cao thì dừng
sớm, ước tính thấp thì tiêu quá tiền của An. Một lần quan sát cache-hit
không phải một tỉ lệ, và không có gì trong response nói token nào được
cache.

Cái sửa là **cách báo**:

```
in=273458 out=86286 at most $0.68 (list price, no cache discount —
check the provider for what was billed)
```

Artifact thêm `"usd_is_upper_bound": true` — một con số đọc từ JSON vài
tháng sau không có dòng print nào bên cạnh. Comment ghi thẳng số đo
2026-08-30.

## 4. Amendment prereg — `holdout_repeats = 3`

Lý do không phải "cho chắc". Hai arm chấm dưới r0.2.0 **cùng ra 6
`explains`/18, nhưng không cùng 6 episode** — trùng 2/6. Một con số đứng
yên trong khi thành phần đổi 4/6 là con số mà **biến động chạy-qua-chạy
ít nhất bằng chênh lệch giữa các arm**. `repeats=1` không tách được.

Ba là số nhỏ nhất nói được điều gì: mỗi episode có đa số, nên "episode
này giải thích được" và "episode này *đôi khi* giải thích được" thôi là
cùng một quan sát. Không đủ cho khoảng tin cậy và không tuyên bố là đủ.

**Vẫn đọc trọn cụm 30 episode.** Chỉ đọc 18 episode có `support` sẽ rẻ
hơn một phần ba công chấm và vẫn hợp lệ (tính chất đó là của packet, tính
trước khi thấy output) — nhưng sẽ **mất khả năng so** `describes_only` và
`silent_correctly` với ba arm đã chấm, vốn đều tính trên cả 30.

## Test

`tests/test_episode_attribution_rules.py` — **22 pass**. Mọi suite chạm
code đã sửa — **1285 pass**. `ruff` sạch.

**Cổng cắn:**

| tiêm | đỏ |
|---|---|
| luật 13 chặn cả câu chỉ nhắc một bên | 1 |
| luật 13 quên kiểm packet có `support` | 1 |
| bỏ cảnh báo chặn trên khỏi print + artifact | 2 |

## Còn lại

- Arm `holdout-deployment-x3` đang chạy (90 lượt, ~$0.90 thật).
- Sheet sinh xong cần An chấm; khoảng 150 mục.
- Chưa commit gì.

# Ba lượt đọc, và con số thật của AI analyst

**Ngày:** 2026-08-30 · **Nhánh:** `tongduyan_analyst-episode` (worktree `P-011-merge`)
**Arm:** `holdout-deployment-x3` — 30 episode × 3 lượt = 90 lượt, o4-mini
**Chấm:** An Tong, mù arm, 90/90 lượt R6 + 180/180 block R1–R5

## Con số

Mẫu số: **18 episode** mà packet có contrast `support` — tức packet *có*
câu trả lời cho "vì sao bên thắng hơn". Mẫu số do sheet tính, không do
người chấm quyết.

| cách đọc | `explains` |
|---|---|
| đúng cả **3/3** lượt | 1/18 = **0.06** |
| **đa số ≥2/3** | 6/18 = **0.33** |
| ít nhất **1/3** | 15/18 = **0.83** |
| một lượt bất kỳ | 22/54 = **0.41** |

Cùng 90 lượt, cùng một bảng chấm. Trải từ 0.06 đến 0.83 tuỳ định nghĩa.

## Điều quan trọng nhất: độ ổn định

Trên 18 episode có `support`, số lượt đạt `explains`:

| số lượt | episode |
|---|---|
| 3/3 | **1** |
| 2/3 | 5 |
| 1/3 | **9** |
| 0/3 | 3 |

**Chỉ một episode giải thích được đáng tin.** Chín episode — một nửa mẫu
— giải thích đúng một lần trong ba: đó là tung đồng xu, không phải năng
lực.

Nửa tất định của phép đo cũng thế: **12/18 episode không ổn định** ở mức
"model có nói hay không" — có lượt nói, có lượt mọi đề xuất bị từ chối
sạch và floor phải lấp.

Hệ quả cho mọi thứ đã báo trước đó: con số một-lượt có sai số **phủ trọn
khoảng chênh giữa mọi arm đã đo**. Cụ thể, `0.11 → 0.33` tôi báo khi so
`holdout-b1` với `holdout-magnitudes` **không đứng vững** — cả hai đều
`repeats=1`. Con số 0.33 tôi báo cho arm deployment tình cờ trùng đa số,
nhưng ở một lượt đó là may, không phải đo.

## An toàn

| | |
|---|---|
| `wrong` | **1/90 lượt** |
| khi model có nói (50 lượt) | `explains` 22 · `describes_only` 27 · `wrong` 1 |
| tỉ lệ giải thích khi đã mở miệng | 22/50 = **0.44** |

Một câu sai duy nhất: `7323e60af732` lượt 2 —

> *"The **local_controller** triggered a replan on C5 while no replan
> occurred on C1 (1 vs 0)"*

Replan là việc của `global_planner`. An chấm R2 = `no`, đúng.

Luật 13 không với tới: packet này *có* contrast `support`
(stuck_cluster tệ hơn ở bên thua) nhưng model bỏ qua, dựng so sánh từ
hai fact `diag:*.replan_count`. Rule 10 hạ cấp, mà hạ cấp thì câu vẫn
tới tay người đọc.

**Đã thử bản siết và bác bỏ bằng đo:** luật *"câu so sánh phải cite đúng
contrast `support` khi packet có"* bắt được 1 `wrong` nhưng cũng giết
**3 `explains`** và 2 `describes_only`. Đổi một câu sai lấy ba câu giải
thích — không đáng, không viết.

## Một chỗ chấm lệch đã sửa

`6a4888cdcf9e` lượt 1 ban đầu chấm R6 = `wrong`, nhưng cả hai câu trong
lượt đó đều chấm R1 = `descriptive_only`:

> *"The local_controller in C1 entered a stuck cluster and stopped for
> 2.05 seconds"* · *"…in C5 … 5.9 seconds"*

Packet ghi đúng 2.05 và 5.9. Không câu nào nhắc hai bên cùng lúc, không
câu nào nêu why. Theo định nghĩa `wrong` = *"khẳng định why mà packet
không nâng đỡ"*, lượt đó phải là `describes_only`. An đã sửa.

Không đổi headline (`6a4888cdcf9e` là support=False, ngoài mẫu số 18),
nhưng đổi số đếm an toàn: `wrong` 2 → **1**.

Kiểm lại sau khi sửa — **sáu phép kiểm đều qua**, gồm hai phép chéo cột:
`R6=wrong` phải có ít nhất một câu không phải `descriptive_only`;
`R6=explains` phải có ít nhất một câu hạng explanation.

## Sheet đã sửa một lỗi có thể làm hỏng bản chấm

Với `repeats=3`, sheet bản đầu sinh **30 khối R6 cho 90 lượt** và bôi cả
episode là "floor" dù chỉ 1/3 lượt là floor. Chấm bản đó sẽ ra số vô
nghĩa. Đã sửa thành R6 **theo từng lượt** (90 khối) và dấu floor theo
từng lượt (40 lượt). Số thứ tự lượt không phải arm nên không lộ gì.

## Đọc thế nào cho demo

Nói được, có bằng chứng:

- Trên episode packet trả lời được, **đa số lượt giải thích đúng ở 6/18
  episode**; khi model chịu nói thì **44%** số lượt là giải thích thật.
- **1 câu sai trên 90 lượt.**
- Không lượt nào vi phạm cổng: không có candidate id lọt ra, không có số
  không có trong packet.

Không nói được:

- "Hệ này giải thích được 33% episode" như một tính chất ổn định. Với 9
  episode ở mức 1/3, con số đó là **trung bình của một biến động lớn**,
  không phải một năng lực.
- Bất kỳ so sánh arm nào dựa trên các lượt `repeats=1` trước đây.

## Chi phí

`at most $1.87` in ra (giá niêm yết, không trừ cache). Thật ước ~$0.80
theo tỉ lệ An đo được ở lần trước ($0.30 thật / $0.68 in ra).

## Còn lại

- Chưa commit gì. `origin/main` chưa nhích lần cuối kiểm.
- 9 lỗi golden simulator có sẵn trên nhánh, ngoài phạm vi loạt việc này.
- Nếu muốn khoảng tin cậy thật thì cần nhiều hơn 3 lượt — nhưng công
  chấm tay tăng tuyến tính, và đó mới là ràng buộc, không phải tiền.

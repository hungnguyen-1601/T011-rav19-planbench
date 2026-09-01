> **THAY THE — dung trich ban nay.** Ban v2:
> `reports/2026-08-31/tongduyan_hieu-nang-that-va-tuong-guard-v2.md`
>
> Ban nay doc tren `holdout-deployment-x3`, chay **truoc** bay lan sua guard
> ngay 30-31/08. So cua no khong sai luc viet, nhung da cu: `explains`
> 6/18 o day, 10/18 o v2. Giu lai lam ban ghi, khong dung lam so.

# Hiệu năng thật của AI analyst, và bức tường guard đang chặn nó

**Ngày:** 2026-08-30 · **Nhánh:** `tongduyan_analyst-episode`

| | |
|---|---|
| Arm | `holdout-deployment-x3` — cấu hình **đúng như route API** (`magnitude_placeholders` + `floor_when_silent` + `reword_once`) |
| Mẫu | 30 episode × **3 lượt** = 90 lượt, cụm holdout `sudden_stop_custom_v2_full_stack_selection` |
| Model | o4-mini |
| Chấm | **An Tong**, mù arm, 90/90 lượt R6 + 180/180 block R1–R5, rubric r0.2.0 |
| Mẫu số | **18 episode** packet có contrast `support` — do sheet tính, không do người chấm quyết |

---

# Phần 1 — Hiệu năng

## 1.1 Con số phụ thuộc hoàn toàn vào định nghĩa

| cách đọc | `explains` |
|---|---|
| đúng cả **3/3** lượt | 1/18 = **0.06** |
| **đa số ≥2/3** | 6/18 = **0.33** |
| ít nhất **1/3** | 15/18 = **0.83** |
| một lượt bất kỳ | 22/54 = **0.41** |

Cùng 90 lượt, cùng một bảng chấm, trải từ 0.06 đến 0.83.

## 1.2 Điều quan trọng nhất — độ ổn định

Trên 18 episode có `support`, số lượt đạt `explains`:

| số lượt | episode |
|---|---|
| 3/3 | **1** |
| 2/3 | 5 |
| 1/3 | **9** |
| 0/3 | 3 |

**Đúng một episode giải thích được đáng tin.** Chín episode — nửa mẫu —
giải thích đúng một lần trong ba. Đó là tung đồng xu, không phải năng
lực.

Nửa **tất định** của phép đo cũng bấp bênh: **12/18 episode không ổn
định** ở mức thô nhất, "model có nói hay không" — có lượt nói, có lượt
bị từ chối sạch.

**Hệ quả:** mọi con số một-lượt có sai số phủ trọn khoảng chênh giữa các
arm. Cụ thể, `0.11 → 0.33` tôi báo khi so `holdout-b1` với
`holdout-magnitudes` **không đứng vững** — cả hai đều `repeats=1`.

## 1.3 Khi model chịu nói thì nói đúng

50 lượt model tự trả lời (40 lượt còn lại floor lấp):

| | |
|---|---|
| `explains` | 22 |
| `describes_only` | 27 |
| `wrong` | **1** |

**Tỉ lệ giải thích khi đã mở miệng: 22/50 = 0.44.**
**Tỉ lệ sai: 1/90 lượt.**

Câu sai duy nhất — `7323e60af732` lượt 2:

> *"The **local_controller** triggered a replan on C5 while no replan
> occurred on C1 (1 vs 0)"*

Replan là việc của `global_planner`. Sai chủ thể.

---

# Phần 2 — Bức tường guard

## 2.1 Quy mô

| | |
|---|---|
| đề xuất bị guard chặn | **211** |
| đề xuất sống sót | 64 |
| **tỉ lệ chặn** | **77%** |

Cứ bốn câu model viết thì hơn ba câu không tới tay người đọc.

## 2.2 Luật nào chặn

| luật | số lần | % |
|---|---|---|
| `quantity_in_statement` | **109** | 52% |
| `claim_blocked_by_packet` | 36 | 17% |
| `contrast_contract_unmet` | 29 | 14% |
| `mechanism_detector_silent` | 16 | 8% |
| `magnitude_not_in_packet` | 8 | 4% |
| `no_citation` | 5 | 2% |
| `wording_above_associated` | 5 | 2% |
| `compares_without_support` | **3** | 1% |

## 2.3 Guard làm im lặng bao nhiêu

40/90 lượt model không nói được gì và floor phải lấp:

| | |
|---|---|
| do guard chặn sạch | **35** |
| model tự chọn im | 5 |

Riêng **19 lượt `silent_wrongly`** — packet *có* câu trả lời mà model im:

| | |
|---|---|
| do guard | **15** |
| model tự im | 4 |

Tổ hợp luật gây ra 15 lượt đó:

```
4x  quantity_in_statement
3x  magnitude_not_in_packet + quantity_in_statement
3x  claim_blocked_by_packet + quantity_in_statement
1x  magnitude_not_in_packet + no_citation + quantity_in_statement
1x  quantity_in_statement + wording_above_associated
1x  claim_blocked_by_packet + quantity_in_statement + wording_above_associated
1x  mechanism_detector_silent
1x  claim_blocked_by_packet
```

**`quantity_in_statement` có mặt ở 13/15.** Nó là rào cản chính, không
phải một trong nhiều.

## 2.4 Từng luật đáng giá bao nhiêu

| luật | chặn | có làm mất câu trả lời không | giữ? |
|---|---|---|---|
| `quantity_in_statement` | 109 | **có — 13/15 lượt im oan** | giữ, nhưng đây là chỗ đáng đầu tư nhất |
| `claim_blocked_by_packet` | 36 | **24/36 do luật 11, và toàn bộ nằm trên packet không có `support`** — tức episode vốn không trả lời được. 12 còn lại là từ `known_unknowns`, có sẵn từ trước | giữ |
| `contrast_contract_unmet` | 29 | không — hạ cấp chứ không bỏ | giữ |
| `mechanism_detector_silent` | 16 | 1 lượt | giữ |
| `magnitude_not_in_packet` | 8 | 5 lượt, nhưng đã đưa vào `REWORDABLE_RULES` nên được thử lại | giữ |
| `compares_without_support` (luật 13) | 3 | **không lượt nào** | giữ |

**Luật 11 và 13 — hai luật mới — không tốn một câu trả lời nào.** Luật
11 chỉ im trên packet vốn không đỡ được câu why; luật 13 bắn 3 lần và
không chạm `explains` nào trên cả ba arm đã đo.

## 2.5 `reword_once` — cứu được gần một nửa

| | |
|---|---|
| lượt kích hoạt | 36/90 |
| vẫn im sau khi viết lại | 21 |
| **nói được sau khi viết lại** | **15** |
| trong đó thành `explains` | **7** |

Không có nó, 15 lượt nữa rơi xuống floor.

---

# Phần 3 — Nói được gì, không nói được gì

## Nói được, có bằng chứng

- Trên episode packet trả lời được, **đa số lượt giải thích đúng ở 6/18
  episode**.
- Khi model chịu nói, **44%** số lượt là giải thích thật.
- **1 câu sai trên 90 lượt.**
- Không lượt nào vi phạm cổng cứng: không candidate id lọt ra, không số
  nằm ngoài packet, không câu trái phán quyết.
- Người đọc **không bao giờ gặp ô trống** — floor lấp 40/90 lượt, và
  sheet phân biệt rõ đâu là floor.

## Không nói được

- *"Hệ giải thích được 33% episode"* như một tính chất ổn định. Với 9
  episode ở mức 1/3, đó là **trung bình của một biến động lớn**.
- Bất kỳ so sánh arm nào dựa trên các lượt `repeats=1` trước đây.
- *"Floor trả lời"* không phải *"analyst trả lời"*. 40/90 lượt là floor,
  và floor chỉ tả detector nào bắn, không giải thích gì.

---

# Phần 4 — Chỗ đáng làm tiếp, theo thứ tự

1. **`quantity_in_statement`** — 52% tổng số chặn, có mặt ở 13/15 lượt im
   oan. `reword_once` đã cứu 15 lượt; câu hỏi chưa trả lời là *vì sao 21
   lượt viết lại vẫn hỏng*. Đọc 21 lượt đó là việc **$0**.
2. **Ổn định**, không phải trung bình. 9 episode ở 1/3 là chỗ hiệu năng
   thật đang nằm. Cần nhiều lượt hơn để thấy, và **công chấm tay mới là
   ràng buộc, không phải tiền**.
3. **Không siết guard thêm.** Đã thử một luật siết (*câu so sánh phải
   cite đúng contrast `support` khi packet có*): bắt 1 `wrong` nhưng giết
   **3 `explains`**. Bác bỏ bằng đo, không viết.

---

# Phụ lục — nguồn

- Artifact: `artifacts/analyst-episode-experiments/holdout-deployment-x3.json`
- Bản chấm: `P-011-merge/docs/antongduy/notes/2026-08-30/tongduyan_cham-deployment-x3.md`
- Chi phí: in ra `at most $1.87` (giá niêm yết, không trừ cache); thật ước
  ~$0.80 theo tỉ lệ đo được lần trước ($0.30 thật / $0.68 in ra).
- Bản chấm đã qua **6 phép kiểm nhất quán**, gồm hai phép chéo cột; 0 mâu
  thuẫn sau khi An sửa `6a4888cdcf9e` lượt 1 từ `wrong` về `describes_only`.

# Hiệu năng thật của AI analyst, và bức tường guard — v2

**Ngày:** 2026-08-31 · **Nhánh:** `tongduyan_analyst-episode`
**Thay thế:** `reports/2026-08-30/tongduyan_hieu-nang-that-va-tuong-guard.md` — bản đó
đọc trên `holdout-deployment-x3`, chạy trước năm lần sửa guard. Số của nó
không sai lúc viết, nhưng đã cũ; đừng trích.

| | |
|---|---|
| Arm | `holdout-final-x3` — cấu hình **đúng như route API** (`magnitude_placeholders` + `floor_when_silent` + `reword_once`) |
| Mẫu | 30 episode × **3 lượt** = 90 lượt, cụm holdout `sudden_stop_custom_v2_full_stack_selection` |
| Model | o4-mini · chi phí `at most $1.60` (giá niêm yết), thật ước ~$0.70 |
| Chấm | **An Tong**, mù arm, 90/90 lượt R6 + 144/144 block R1–R5, rubric r0.2.0 |
| Kiểm | **0 mâu thuẫn** trên 6 phép kiểm nhất quán, gồm 2 phép chéo cột |

---

# Phần 1 — Hiệu năng

## 1.1 Hai con số, và vì sao phải đi cùng nhau

**Đo được** (mẫu số 18 — như lúc An chấm):

| cách đọc | `explains` |
|---|---|
| 3/3 lượt | 3/18 = **0.17** |
| **đa số ≥2/3** | 10/18 = **0.56** |
| ≥1/3 | 15/18 = 0.83 |
| từng lượt | 28/54 = 0.52 |

**Suy ra** sau hai thay đổi guard cuối, mẫu số 17 — **chưa chạy lại**:

| cách đọc | `explains` |
|---|---|
| 3/3 lượt | 3/17 = **0.18** |
| **đa số ≥2/3** | 10/17 = **0.59** |
| ≥1/3 | 15/17 = 0.88 |
| từng lượt | 28/51 = 0.55 |

**0.59 đẹp hơn 0.56 là do một thay đổi guard, không phải do model tốt
lên.** Episode rời khỏi mẫu số (`91ec9d58e922`) có ba lượt là
`describes_only` / `describes_only` / `wrong` — không lượt nào
`explains`. Đã khai thành amendment có ngày trong
`preregistration_episode.py::holdout_denominator`. **Trích một con số thì
phải trích cả hai.**

## 1.2 Tiến trình qua bốn arm

Mẫu số 18, `explains` theo đa số ≥2/3:

| arm | `explains`/18 | analyst im lặng/18 |
|---|---|---|
| `holdout-b1` (không flag) | 2 → **0.11** | 13 |
| `holdout-magnitudes` | 6 → 0.33 | 8 |
| `holdout-deployment-x3` | 6 → 0.33 | 5 |
| **`holdout-final-x3`** | **10 → 0.56** | **3** |

Lượt áp chót: im lặng giảm mà `explains` **đứng yên** — im lặng chỉ
chuyển thành `describes_only`. Lượt cuối là lần đầu **cả hai cùng đổi**.

## 1.3 Độ ổn định — chỗ số trung bình che mất

Trên 18 episode, số lượt đạt `explains`:

| số lượt | trước | **sau** |
|---|---|---|
| 3/3 | 1 | **3** |
| 2/3 | 5 | **7** |
| 1/3 | 9 | **5** |
| 0/3 | 3 | 3 |

Và ở mức thô hơn — "model có nói không" — **không còn episode nào dưới
2/3**; trước đó có 5.

Vẫn còn 5 episode ở mức `explains` 1/3. Với chúng, 0.56 là **trung bình
của một biến động**, không phải một năng lực. Đây là lý do mọi so sánh
arm dựa trên `repeats=1` trước đây không đứng vững.

## 1.4 An toàn

| | |
|---|---|
| `wrong` | **3/90 lượt** (đo được) · **2/90** (suy ra sau việc 1) |
| khi model có nói (65/90 lượt) | `explains` 28 · `describes_only` 34 · `wrong` 3 |
| tỉ lệ giải thích khi đã mở miệng | 28/65 = **0.43** |
| vi phạm cổng cứng | **0** — không candidate id lọt ra, không số ngoài packet, không câu trái phán quyết |

---

# Phần 2 — Bức tường guard

## 2.1 Quy mô, và nó đã mỏng đi

| | trước | **sau** |
|---|---|---|
| đề xuất bị chặn | 211 | **171** |
| model tự nói | 50/90 | **65/90** |
| floor phải lấp | 40/90 | **25/90** |

## 2.2 Luật nào chặn

| luật | trước | **sau** |
|---|---|---|
| `quantity_in_statement` | 109 | **50** |
| `contrast_contract_unmet` | 29 | 44 |
| `claim_blocked_by_packet` | 36 | 33 |
| `mechanism_detector_silent` | 16 | 26 |
| `magnitude_not_in_packet` | 8 | 7 |
| `no_citation` | 5 | 4 |
| `wording_above_associated` | 5 | 3 |
| `compares_without_support` (luật 13) | 3 | 1 |
| `subject_absent_from_episode` (luật 12) | 0 | 3 |

`quantity_in_statement` giảm 54%. Nhưng `contrast_contract_unmet` +15 và
`mechanism_detector_silent` +10: **đề xuất thoát rule 2 rồi vướng luật
sau**. Tổng chỉ giảm 40, không giảm 59.

## 2.3 Rào cản chính còn lại — và 78% của nó là dương tính giả

`blocked_detail` (thêm ở loạt này) lần đầu cho đọc **50 lần chặn còn lại
là vì token gì**:

| token | lần | thực chất |
|---|---|---|
| `p99` | **23** | tên metric `p99_latency_ms` |
| `C1.replan_count` và tương tự | 12 | mảnh ref — bộ tách xử lý `/` và `-`, **không xử lý `.`** |
| `one` · `1` · `2` · `two` | 22 | số thật, chặn đúng |
| `C5@8c3bfce9bb13` | 1 | nhãn + `@` + episode id, cả hai đều là identifier |
| `C5—prolonging` | 1 | em-dash, bộ tách chỉ xử lý `-` ASCII |

**39/50 là dương tính giả cùng họ.** Chưa sửa: đã đo rằng hiệu ứng dự
kiến (~1–2 episode trên mẫu số 17) **nhỏ hơn nền nhiễu đã đo**, và trần
còn lại chỉ 3 lượt.

---

# Phần 3 — Guard đã sửa trong loạt này

| # | sửa gì | đo được |
|---|---|---|
| 1 | tên có chữ số (`C1's`, `C1/C5`, `C1-side`) thôi bị đọc thành số | `quantity_in_statement` 109→50 |
| 2 | rule 9 chịu được trạng từ (`C5 clearly wins`) | 0 dương tính giả trên 277 câu đã sống sót |
| 3 | `blocked_detail` + tách `blocked_first_turn`/`second_turn` | lần đầu chẩn đoán được lượt viết lại hỏng |
| 4 | `magnitude_not_in_packet` vào `REWORDABLE_RULES` | tầm với của reword 6/9 → 7/9 |
| 5 | luật 13: so sánh hai bên trên packet không `support` ⇒ **bỏ** | `wrong` 2→0 ở arm trước, 0 `explains` mất |
| 6 | detector không có mechanism ⇒ contrast **không** được `support` | mẫu số 18→17, `wrong` 3→2 |
| 7 | `subject_match` đọc từ contrast đang đỡ, không từ toàn bộ cite | **0 ca trên dữ liệu đã ghi** — việc 6 đã gỡ ca duy nhất |

Mục 7 là **hàng rào cho tương lai, không phải cải thiện đo được**. Ghi
đúng như thế trong docstring của test.

## Ba lần đề xuất bị chính phép đo bác bỏ

Ghi lại vì chúng đắt hơn phần đã làm:

1. **"Rule 10 bỏ thay vì hạ cấp khi câu so sánh hai bên"** — đo trước:
   giết **5/6 episode `explains`**. Giải thích "vì sao A hơn B" *chính
   là* so sánh hai bên. Thu hẹp còn "chỉ khi packet không có `support`"
   thì bắt đúng 2 câu sai, 0 `explains`.
2. **"Câu so sánh phải cite đúng contrast `support` khi packet có"** —
   bắt 1 `wrong`, giết **3 `explains`**. Không viết.
3. **"Bỏ khi `subject_match` hỏng"** — sẽ bỏ 61 câu, trong đó **49 là
   output của chính floor** (floor phát `component_specific_attribution`
   với subject `task_geometry`, không cite contrast nào). Giết tấm lưới
   cuối.

---

# Phần 4 — Lỗ hổng đã biết, chưa sửa

| lỗ hổng | trạng thái |
|---|---|
| `p99`, `C1.replan_count`, `C5@…`, em-dash bị đọc thành số | **chưa sửa** — hiệu ứng nhỏ hơn nhiễu, cần một lượt chạy để đo |
| `near_miss_cluster` không có `PropositionType` riêng | **cố ý để trống**, lý do và thiết kế `near_miss_association` ghi ngay tại `DETECTION_HYPOTHESES`. Không map sang `clearance_refusal`/`geometric_infeasibility` vì packet không ghi quyết định controller và không đo passage width |
| Tiếng Việt: `không` (phủ định), `năm` (year), `một` (mạo từ) trong `NUMBER_WORDS` | **latent** — analyst đang viết tiếng Anh. **Đừng bật đường tiếng Việt trước khi sửa**: mọi câu phủ định sẽ bị chặn |
| `_WINNING_WORDS` thiếu `prevailed`, `edged out`, `outran` | chưa câu nào trong 277 dùng; thêm là đoán |
| 9 lỗi golden simulator (`test_dwa_core_refactor`, `test_host_parity_golden`) | **có sẵn trên nhánh** — chứng minh bằng stash: không thay đổi, 10 đỏ |

---

# Phần 5 — Nói được gì, không nói được gì

## Nói được

- Trên episode packet trả lời được, **đa số lượt giải thích đúng ở 10/18
  episode** (0.56; 10/17 = 0.59 sau loạt sửa cuối, chưa chạy lại).
- Khi model chịu nói, **43%** số lượt là giải thích thật.
- **3 câu sai trên 90 lượt** (2 sau loạt sửa cuối).
- **0 vi phạm cổng cứng** trên 90 lượt.
- Người đọc **không gặp ô trống**: floor lấp 25/90 lượt và sheet phân
  biệt rõ đâu là floor.

## Không nói được

- *"Hệ giải thích được 56% episode"* như một tính chất ổn định — 5
  episode còn ở mức 1/3.
- *"0.59"* mà không kèm 0.56 và lý do mẫu số đổi.
- *"Floor trả lời"* = *"analyst trả lời"*. 25/90 lượt là floor, và floor
  chỉ tả detector nào bắn.
- Bất kỳ so sánh arm nào dựa trên các lượt `repeats=1` trước đây.

---

# Phụ lục

- Artifact: `artifacts/analyst-episode-experiments/holdout-final-x3.json`
- Bản chấm: `P-011-merge/docs/antongduy/notes/2026-08-31/tongduyan_cham-final-x3.md`
- Rà soát guard: `notes/2026-08-30/tongduyan_ra-soat-toan-bo-guard.md`
- Amendment: `preregistration_episode.py` — `rubric` r0.2.0,
  `holdout_repeats` 3, `holdout_denominator`
- Cổng: **1300 pass** trên mọi suite chạm code đã sửa; **4231 pass** suite
  backend đầy đủ ở lần chạy trước loạt sửa cuối

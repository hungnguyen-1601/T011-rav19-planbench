# Chấm tay 16 ý o4-mini thêm vào — 15 đúng, 1 sai, và cái sai đúng loại đã cảnh báo

**Ngày:** 2026-08-24 · **Loại:** đánh giá, chấm tay từng ý
**Nguồn dữ liệu:** `tongduyan_advisor_live_results_after_fix.json` — chạy trên bản đã
vá (`reports/2026-08-24/tongduyan_va-loi-ai-advisor.md`), 3 run × 2 loại advice
**Cách chấm:** với mỗi addition, resolve `field_path` về giá trị thật trong source rồi
đối chiếu từng mệnh đề. Không chấm văn phong, chỉ chấm **đúng/sai sự thật** và
**có mới không**.

---

## 1. Điểm

| Trục | Kết quả |
|---|---|
| Đúng sự thật | **15/16 = 0,94** |
| Ý mới (không lặp lại một advice luật) | **14/16 = 0,88** |
| Ý vừa đúng vừa mới | **13/16 = 0,81** |
| Bịa số | **0/16** |
| Citation không resolve (bị bỏ + đếm) | 1 lượt trên 6 |

## 2. Bảng chấm

| # | run/loại | ý | phán |
|---|---|---|---|
| A01 | gated/diag | G3 fail không được tách theo loại thất bại | **đúng, mới** — `failure_reasons` và `outcome_counts` đều `null` trong source |
| A02 | gated/diag | G5 chỉ ước lượng, chưa đo trên thiết bị đích | đúng — cite trúng `status: estimated_from_structure` |
| A03 | gated/diag | rrtstar+dwa báo `peak_search_nodes` = 0 | **đúng, mới, giá trị cao** |
| A04 | gated/out | 70% dưới mức tối thiểu 95% | đúng nhưng **lặp lại advice luật** |
| A05 | gated/out | `peak_search_nodes` = 0 dù ước lượng bộ nhớ khác 0 | **đúng, mới, giá trị cao** |
| A06 | gated/out | G4 mới qua sàng lọc trên host | đúng nhưng **lặp lại** `GA_G4_HOST_ONLY` |
| A07 | carded/diag | G5 ước lượng từ cấu trúc | đúng |
| A08 | carded/diag | không có giả định nào được khai | đúng — `declared_assumptions: null`, đọc `null` thành "không khai", **không** thành 0 |
| A09 | carded/diag | chênh p99 dựa trên đo host, chưa chắc đúng trên đích | đúng, mới |
| A10 | carded/out | p99 hai bên đều dưới ngưỡng 50 ms | **đúng** — `threshold_ms: 50.0`; p99 là 6,06 và 19,30 |
| A11 | carded/out | cả 30 episode dùng một mission `through_hall`, biến thể `nominal` | **đúng, mới, giá trị cao** — kiểm 30/30 context: đúng một mission, đúng một variant |
| A12 | tied/diag | `peak_search_nodes` = 0, nghi lỗi ghi log | đúng — nhưng khai `blocking` cho một nghi vấn instrument, **hơi nặng tay** |
| A13 | tied/diag | bộ nhớ chỉ ước lượng từ cấu trúc | đúng |
| A14 | tied/out | `peak_search_nodes` = 0 | đúng |
| A15 | tied/out | *"clearance nhỏ nhất hai bên khoảng 0,308–0,310 m, dưới ngưỡng cảnh báo 0,35"* | **SAI** — xem §3 |
| A16 | tied/out | không có giả định nào được khai | đúng |

## 3. Ca sai duy nhất, và vì sao nó đáng chú ý

**A15.** Model dẫn `report.manifest.constraints.clearance_warning_m` — path **có
thật**, giá trị **đúng** (0,35). Nhưng khoảng nó kèm theo thì sai:

| | model nói | thật |
|---|---|---|
| clearance nhỏ nhất, candidate[0] | ~0,308 | 0,3074 ✓ |
| clearance nhỏ nhất, candidate[1] | ~0,310 | **0,2617** ✗ |

Trên 60 giá trị `min_clearance` trong run đó, nhỏ nhất là 0,2617. Model đọc đúng một
bên rồi suy khoảng cho cả hai. Hướng kết luận ("dưới ngưỡng cảnh báo") vẫn đúng, và
sai theo chiều **nhẹ hơn thực tế** — robot lại gần vật cản hơn con số nó đưa ra.

**Đây đúng loại lỗi probe `P7` cảnh báo và bộ kiểm hiện tại không bắt được:**
citation **resolve** không có nghĩa là citation **ủng hộ** claim. `exists()` trả
`True`, ý được xuất bản, `fabricated` vẫn bằng 0.

Nói cho công bằng: đây **không phải bịa số**. Cả 0,308 lẫn 0,35 đều có trong dữ
liệu. Lỗi là **khái quát từ một mẫu ra cả tập** — cùng một thao tác mà A11 làm và
làm **đúng** (30/30 context quả thật cùng mission). Model không phân biệt được khi
nào phép khái quát đó an toàn, và hệ hiện không có gì kiểm hộ.

## 4. Nhìn tổng thể

**Ba ý có giá trị thật, tầng luật không thấy:**

1. **`peak_search_nodes` = 0** (xuất hiện ở 4/6 lượt) — candidate báo 0 node đã duyệt
   trong khi vẫn có ước lượng bộ nhớ khác 0. Bất nhất đo đạc thật, không luật nào
   trong `GATE_ADVICE_CODES` bắt.
2. **Toàn bộ 30 episode chỉ một mission, một biến thể môi trường** — cảnh báo độ phủ,
   đúng loại *"an assumption nobody declared"* mà system prompt yêu cầu.
3. **G3 fail mà không có phân loại thất bại** — chỉ ra chỗ dữ liệu thiếu, không bịa
   ra nguyên nhân.

**Hai ý chỉ lặp lại luật** (A04, A06). Không hại, nhưng chiếm chỗ trong trần 3 ý.

**Một chỗ khai severity hơi nặng** (A12: `blocking` cho một nghi vấn ghi log). Nó có
kèm `do_not` nên không bị hạ theo luật mới ở §1.6 của report — luật đó chỉ bắt ca
blocking **không** nêu nước cấm.

## 5. Kết luận, và việc còn lại

Sau khi vá, o4-mini làm đúng việc được giao: **0,94 độ chính xác, 0 số bịa, sàn luật
nguyên vẹn 12/12 lượt**, và tìm ra ba thứ tầng luật bỏ sót. Đủ để dùng, **chưa đủ để
tin không cần đọc**.

Việc còn lại, xếp theo giá trị:

1. **Đóng lỗ P7** — cách rẻ nhất không cần model: mọi con số trong `claim` phải khớp
   một giá trị **thật sự có** dưới `field_path` được cite (hoặc dưới cây con của nó),
   không phải chỉ có ở đâu đó trong source. A15 chết ngay ở luật này: 0,308 không nằm
   dưới `clearance_warning_m`.
2. **Đánh dấu ý lặp lại luật** — addition cite cùng `field_path` với một advice luật
   thì gắn nhãn, để trần 3 ý không bị tiêu vào chỗ đã có.
3. **Mẫu còn nhỏ.** 16 ý trên 3 run. Đủ để nói "dùng được", chưa đủ để đặt ngưỡng.
   Muốn có precision đáng công bố thì cần ~10 run, và cần **người thứ hai chấm lại** —
   bảng trên là một người chấm, không phải hai người đồng thuận.

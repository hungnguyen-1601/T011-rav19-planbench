# Điểm tổng /100 và khối kết luận — kế hoạch

**Ngày:** 2026-08-20 · **Nhánh:** `tongduyan_3` · **Trạng thái: chờ An duyệt, chưa làm gì**

An muốn: từ các metric hiện có, rút ra một **kết luận** — nên dùng thuật toán nào — kèm
một **điểm tổng dạng 70/100** để nhìn phát biết ngay. Trong MVP chưa thuật toán nào qua
hết gate, nên candidate trượt gate **vẫn phải có điểm**, kèm **cảnh báo**, và việc trượt
gate **phải bị trừ điểm**.

An chốt thêm: khối điểm đặt **dưới phần evidence**, và hai nút export **dời xuống dưới
khối điểm** — đó mới là lúc người đọc cân nhắc có export không.

---

## 1. Phần dễ: thang điểm đã có sẵn

`packages/decision/planbench_decision/objectives.py`:

```
decision_utility = w_R·U_R + w_S·U_S + w_E·U_E + w_C·U_C      (trọng số cộng = 1.0)
```

Đã là 0–1, đã tính **cho từng candidate** (`CandidateEvidence.set_objectives`). Nhân 100
là xong. **Không xây thang mới** — xây cái thứ hai thì nó lệch với card ngay lần đầu ai
đó chỉnh anchor.

Một ràng buộc tên gọi: `objectives.py:9` ghi *"tên là `decision_utility` ở mọi nơi,
không bao giờ là `score`"* (HĐ-9.2). UI hiện `87.7 / 100` dưới nhãn **decision utility**;
gắn chữ "score" vào là sai hợp đồng.

---

## 2. Nguyên lý trừ điểm — trả lời câu An hỏi

**Không có hằng số phạt nào, và không nên có.** Cái "trừ điểm" là **đường cong anchor
của chính deployment**: mỗi objective ánh xạ số đo thô về [0,1] qua anchor đã khai, rồi
nhân trọng số. Một candidate 40% thành công không "bị trừ 20 điểm" — nó nhận
`u("success_rate", 0.40)`, bao nhiêu là do anchor nói, rồi ×`w_R`.

Lý do trừ vì thế nằm ở **anchor đã khai trước khi chạy**, không nằm ở một con số tôi
chọn sau khi nhìn kết quả. Đó là khác biệt giữa một thang đo và một thang đo được vặn.

### Gate nào thật sự chạm tới điểm

| Gate | Trượt vì | Vào điểm qua |
|---|---|---|
| **G1** no_path_rate | không tìm ra tuyến | `U_R` — episode no-path là `success=False` |
| **G2** collisions | có va chạm | **không gì cả** |
| **G3** success_rate | ít episode tới đích | `U_R` trực tiếp |
| **G4** p99 latency | trễ deadline điều khiển | `U_C` (gồm p99) |
| **G5** memory | vượt RAM board | `U_C` (gồm `memory_estimate_mb`) — một phần |
| **G6** observation | thiếu cảm biến deployment cấp | **không gì cả** |

### Vấn đề: G2 cố ý nằm ngoài điểm

`objectives.py:431`:

> `U_S` (HĐ-9.1). **`collision_count` is absent on purpose.** Collisions live at gate G2
> and nowhere else (HĐ-6): a candidate that collided is not in this computation at all,
> and **letting collisions also lower a score would imply they can be traded against
> speed**.

Và `pipeline.py:618`:

> A candidate that failed a gate **is not a worse choice, it is not a choice** — so it is
> not scored at all rather than scored and ranked last. That is what stops "fastest" from
> ever competing with "did not collide" (HĐ-7).

Hệ quả thẳng: **nếu hiện một con số duy nhất cho candidate trượt gate, một stack đã va
chạm có thể hiện điểm cao hơn một stack không va chạm.** Nó lái nhanh hơn, giữ khoảng
cách trung bình tốt hơn, và cú va chạm không xuất hiện ở đâu trong phép cộng.

Đây không phải chi tiết hiện thực bỏ sót. Nó được viết ra để chặn đúng kết cục đó.

---

## 3. Ba lối đi

| Lối | Làm gì | Đánh đổi |
|---|---|---|
| **A. Một bảng xếp hạng, mọi candidate** | Chấm tất cả bằng chính hàm nền tảng, sắp theo utility, gate hỏng chỉ là badge | Đúng chữ yêu cầu của An. Nhưng candidate va chạm có thể đứng trên — chính điều HĐ-6 chặn |
| **B. Hai nhóm, một đường kẻ** *(đề xuất)* | Chấm tất cả bằng hàm nền tảng. **Nhóm trên**: qua hết gate, xếp hạng, có khuyến nghị. **Nhóm dưới**: trượt gate, vẫn có điểm /100, nhưng nằm dưới đường kẻ và mang badge gate đã trượt. Không bao giờ trộn thứ hạng qua đường kẻ | Vẫn cho mọi thuật toán một con số như An cần, mà không bao giờ để "nhanh hơn" đứng trên "không va chạm". Cần giải thích cái đường kẻ |
| **C. Thêm hệ số phạt tường minh** | Nhân điểm với một hệ số cho mỗi gate trượt | Cho ra một thứ tự duy nhất, dễ nhìn nhất. Nhưng hệ số là **do UI bịa**, không ai khai trước, và nó ngụ ý va chạm quy đổi được ra tốc độ — đúng thứ HĐ-6 cấm |

**Đề xuất B.** Nó cho An đúng thứ đã yêu cầu — mọi thuật toán có điểm, trượt gate có
cảnh báo, và điểm *có* phản ánh việc trượt G1/G3/G4/G5 qua anchor — mà không cần bịa
hằng số, và không tạo ra một bảng xếp hạng nơi va chạm đổi được lấy tốc độ.

Nếu An vẫn muốn **C**, tôi làm, nhưng con số phạt sẽ được ghi rõ ngay cạnh là **do UI
đặt ra, không phải nền tảng đo được**, và cần An chốt hệ số cho từng gate — vì tôi chọn
thì đó là tôi vặn thang đo sau khi đã nhìn kết quả.

---

## 4. Trở ngại kỹ thuật đã xác định

`score_survivors` (`pipeline.py:610`) **chỉ chấm candidate qua hết gate**. Nên report
hiện chỉ có utility của người thắng, và candidate trượt gate **không có utility nào**.

`build_evidence` thì chỉ cần candidate + metrics + contexts + anchors — **nó không nhìn
gate**. Nên chấm được mọi candidate bằng **chính hàm đó**, không phải hàm mới.

Việc cần làm ở tầng nền tảng: chấm tất cả, lưu utility + bốn trục cho từng candidate vào
report, và **đánh dấu rõ candidate nào không đủ tư cách được khuyến nghị**. Không đụng
vào `score_survivors` — thêm một đường song song có tên nói đúng nó là gì.

---

## 5. Các đợt

| Đợt | Nội dung | Ước lượng |
|---|---|---|
| **S1** | Tầng chấm: chấm mọi candidate, lưu `decision_utility` + `U_R/U_S/U_E/U_C` + cờ `recommendation_eligible` vào report. Không đổi logic card. Kiểm chứng: chạy lại sweep có sẵn, xác nhận utility của người thắng **khớp từng chữ số** với card | 0.5 ngày |
| **S2** | Số thật cho ca G2: dựng một run có va chạm, xem candidate va chạm ra điểm bao nhiêu so với candidate sạch. **Nếu nó cao hơn thì lối A chết tại đây**, và plan này có bằng chứng thay vì lập luận | 0.5 ngày |
| **S3** | API + `lib/` cho khối kết luận: xếp hạng, làm tròn, đủ tư cách hay không, đọc trạng thái card | 0.5 ngày |
| **S4** | UI: khối kết luận **dưới evidence**, thanh /100, bốn trục, ΔU kèm CI, badge gate, đường kẻ phân nhóm. Dời hai nút export xuống dưới | 1 ngày |
| **S5** | Đưa các số này vào export `.md`/`.xlsx` — cùng lúc bổ sung những metric đang thiếu (xem memory `export-thieu-metrics`) | 0.5 ngày |

Tổng ~3 ngày. **S1+S2 đã tự có giá trị**: sau hai đợt đó An có số thật để chốt A/B/C,
thay vì chốt trên lập luận của tôi.

---

## 6. Ba luật hiển thị tôi sẽ giữ, dù chọn lối nào

- **Làm tròn một chữ số thập phân.** `0.8774` và `0.8770` đều thành `88/100`; hai
  candidate mà ΔU phân biệt được sẽ hiện ra như hoà. Luôn đặt ΔU kèm `ci95` bên cạnh.
- **Tiêu đề không nói "A tốt nhất" khi nền tảng không nói thế.** `NEAR_EQUIVALENT`, và
  ca bị Pareto trội (`card.py:707` — HĐ-10.1 cấm khuyến nghị candidate bị trội, **kể cả
  khi nó dẫn điểm**), phải đọc ra đúng như vậy.
- **G5 và G6 là badge, không phải điểm trừ.** Vượt RAM board hay thiếu cảm biến không
  phải "lái kém hơn" — đó là một loại "không" khác, và ép nó thành điểm là làm nó trông
  như có thể bù bằng lái giỏi.

---

## 7. Câu hỏi cho An

1. **Lối A, B hay C** ở mục 3? Tôi đề xuất B. Nếu C thì An cho hệ số phạt từng gate.
2. Có muốn chạy **S2 trước khi chốt** không — để quyết định dựa trên số thật?
3. Điểm hiện cho **mọi** candidate hay chỉ hai cái đang so trên lưới?

---

## 8. Đính chính

Lượt trước tôi nói với An rằng "trượt G2 ⇒ có va chạm ⇒ `U_S` thấp". **Sai.** `U_S` cố ý
không chứa `collision_count`. Tôi phát hiện khi đi tìm con số cụ thể để trả lời câu hỏi
của An về nguyên lý trừ điểm — và nó là lý do plan này tồn tại thay vì tôi gõ thẳng code.

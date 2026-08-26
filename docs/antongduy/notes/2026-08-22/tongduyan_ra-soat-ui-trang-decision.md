# Rà soát UI trang `/decisions/[id]` theo brief Results / Algorithm Comparison

Ngày: 2026-08-22 · Nhánh `tongduyan_4` · **Không sửa một dòng code nào** —
đây là bản đọc màn hình đang chạy và đối chiếu với brief, để An chốt
việc trước khi làm.

Vật liệu: sáu ảnh chụp toàn trang `sudden_stop_v5` ở locale `vi`, đọc
kèm [page.tsx](../../../../apps/web/src/app/decisions/%5Bid%5D/page.tsx)
(1539 dòng). Brief đối chiếu là bản An đưa: header · executive summary ·
detailed comparison · visual comparison · trade-off insights · decision
recommendation · explainability.

Kết luận một dòng: **nội dung đã đủ và trung thực, thứ tự trình bày thì
chưa phục vụ được mục tiêu 5 giây, và bảng màu đang tự mâu thuẫn.**

---

## 1. Thứ tự thông tin — nhóm vấn đề nặng nhất

Thứ tự render thật, đọc từ
[page.tsx:148-170](../../../../apps/web/src/app/decisions/%5Bid%5D/page.tsx#L148-L170):

| # | Component | Tiêu đề trên màn hình |
|---|---|---|
| 1 | `SampleNotice` | (chỉ hiện khi mẫu bất thường) |
| 2 | `CandidateComparison` | KẾT QUẢ SO SÁNH + Chi tiết sáu gate khả thi |
| 3 | `TracePanel` | XEM LẠI MỘT EPISODE |
| 4 | `ExplanationHeader` | VÌ SAO CÓ KẾT QUẢ NÀY |
| 5 | `EvidencePanel` | BẰNG CHỨNG CỦA LƯỢT CHẠY NÀY |
| 6 | `ConclusionPanel` | NÊN DÙNG THUẬT TOÁN NÀO |
| 7 | `ExportReport` | Xuất Markdown · Excel (.xlsx) · Share |
| 8 | `Outcome` | RUN NÀY KHÔNG ĐƯA RA KHUYẾN NGHỊ |
| 9 | `HumanActs` | ĐỌC, VÀ QUYẾT ĐỊNH |

### L1 — Câu trả lời nằm ở màn hình thứ sáu

Comment ngay trên khối render tự nhận là *"The answer, then how it was
reached, then who was allowed to be in the running"*. Trên màn hình
thật thì không phải vậy: điểm 87.7 / 31.3 (`ConclusionPanel`) và card
việc-cần-làm (`Outcome`) nằm ở ảnh thứ **6**, sau khoảng năm màn hình
cuộn. Trong năm giây đầu người đọc chỉ có tên run và một badge xám
"Không có khuyến nghị" ở góc phải.

Mục tiêu thông tin số 1 của brief — biết ngay bên nào dẫn, chênh bao
nhiêu, khuyến nghị là gì — hiện đang **fail**.

### L2 — Episode replay chiếm vị trí thứ hai

`TracePanel` là phần cao nhất trang: bộ chọn 30 episode có phân trang 6
trang, hai viewport quỹ đạo, mười bốn ô số, hai biểu đồ latency. Đây là
drill-down bằng chứng, dùng khi đã nghi ngờ điều gì đó — không phải thứ
đọc để ra quyết định. Đặt nó ở slot 2 đẩy toàn bộ phần quyết định
xuống dưới fold thêm bốn màn.

### L3 — Cùng một sự thật nói bốn lần

"Run này không phát khuyến nghị" xuất hiện bốn chỗ, bốn cách chữ khác
nhau:

1. badge header — "Không có khuyến nghị"
2. `ExplanationHeader` — "Không có khuyến nghị: chưa tới hai candidate qua đủ cổng"
3. `ConclusionPanel` — "Không có khuyến nghị: dưới hai candidate qua hết gate, nên run này không có ΔU"
4. `Outcome` — "RUN NÀY KHÔNG ĐƯA RA KHUYẾN NGHỊ / Không candidate nào qua đủ cổng"

Mỗi câu một mình đều đúng và viết tốt. Bốn câu cạnh nhau thì người đọc
phải kiểm tra xem chúng có mâu thuẫn không — và câu 4 *có* lệch: nó nói
"không candidate nào qua đủ cổng", trong khi bảng ghi `astar+dwa` là
`G1–G6 đều đạt`. Đúng ra phải là "chỉ một candidate qua cổng, không đủ
đối chứng". **Đây là lỗi nội dung, không phải lỗi trình bày.**

Gộp còn hai chỗ: một câu ở summary trên đỉnh, một đoạn giải thích ở
explainability dưới đáy.

### IA đề xuất

Giữ nguyên hai ràng buộc đã có lý do trong code — `SampleNotice` đứng
đầu vì nó phủ định mọi con số bên dưới, và `ExplanationHeader` phải
dính ngay trên `EvidencePanel` vì nó là caveat của khối đó:

```
SampleNotice
DecisionSummary      ← MỚI: winner · ΔU · confidence · card khuyến nghị
DecisionAdvice       ← MỚI: quality-critical / real-time / hybrid
CandidateComparison    (thêm cột Winner, sticky header)
VisualComparison     ← MỚI: bars đã chuẩn hoá
TradeoffInsights     ← MỚI: 3–5 dòng
ExplanationHeader
EvidencePanel
TracePanel             ← HẠ XUỐNG, collapsed mặc định
HumanActs
```

`ConclusionPanel` và `Outcome` bị hấp thụ vào `DecisionSummary` +
`DecisionAdvice`. `ExportReport` chuyển lên header.

---

## 2. Layout specification

### Desktop 1440

Sidebar 232 · content 1208 · padding 32 mỗi bên → canvas 1144.

| Khối | Bố cục |
|---|---|
| Header | tiêu đề trái, `[Export ▾] [Share]` phải, cùng hàng badge trạng thái |
| DecisionSummary | 2 cột: so sánh điểm 760 / recommendation card 368, gap 16 |
| DecisionAdvice | 3 thẻ ngang 371 mỗi thẻ |
| Bảng | Metric 340 · A 240 · B 240 · Δ 140 · Winner 120 · Weight 64 |
| VisualComparison | 2 cột 564 |
| TracePanel | 2 viewport 552 |

### Laptop 1280

Content 1048 → canvas 984.

- `DecisionSummary` xếp dọc, card khuyến nghị full width.
- Bảng: Metric 300 · A 200 · B 200 · Δ 120 · Winner 100 · Weight 64.
  Vẫn một dòng, **không** scroll ngang.
- `TracePanel` là điểm gãy thật: hai viewport hiện tại ~660px mỗi bên
  không vừa 984. Dưới 1200px chuyển sang tab A/B thay vì cạnh nhau.

### Dưới 900

Thứ tự: summary → advice → bảng (scroll ngang có bóng ở mép) →
trade-off → explainability. `VisualComparison` và `TracePanel` giấu sau
nút "Xem thêm" — brief nói rõ không ép chart khó đọc.

### Nhịp dọc

Row bảng 44px một dòng, 60px hai dòng. Hiện có row cao khoảng 110px —
row "Độ trẻ planner, p99 gộp" vì đoạn cảnh báo bốn dòng bị nhét thẳng
vào cell. Một row cao gấp ba row khác phá nhịp mắt quét.

---

## 3. Rà từng component

### Header

- Badge "Không có khuyến nghị" đang xám trung tính, cùng trọng lượng
  với chip thông tin. Phải tách token: `uncertain` (amber) khác
  `blocked` (đỏ) khác `ok` (xanh).
- `ExportReport` hiện trôi giữa hai panel ở đáy, không nhãn nhóm, không
  tiêu đề section. Đưa lên header thành secondary button.
- Thiếu trạng thái run tường minh. Dòng meta có `30 episode đã đo · đạt
  N_min (30) · chạy đủ yêu cầu` — đủ dữ kiện nhưng đọc như chú thích;
  nên có chip `Hoàn tất`.

### Bảng so sánh — sửa nhiều nhất

| Vấn đề | Đề xuất |
|---|---|
| Cột A viền xanh dương, cột B viền **xanh lá** | B là bên thua mà tint xanh lá đọc thành positive. Bỏ tint cả hai, hoặc dùng chung slate-50. Xanh lá / đỏ **chỉ** dành cho tốt / kém |
| Không có cột Winner | Thêm cột text `A` / `B` / `hoà` / `—`. Hiện winner chỉ mã hoá bằng màu con số, vi phạm luật "màu không thay nhãn" của chính brief |
| Không có cột Weight | Quyết định "weight gắn objective chứ không gắn metric" là đúng và đã ghi ở [ghi chú chọn metric](tongduyan_chon-metrics-cho-detailed-comparison.md). Nhưng trên màn hình phải **nói ra** ở caption bảng, không im lặng bỏ cột |
| Số căn giữa | Căn phải, canh dấu thập phân, unit tách span cố định |
| "0 / 30 episode phân biệt" lặp ở cả hai cell | Dồn về caption dưới tên metric, một lần |
| Cảnh báo latency bốn dòng trong cell | Rút một dòng + `?` mở tooltip đầy đủ |
| Header không sticky | Sticky khi bảng quá 8 dòng |
| Hàng `không đo` lẫn giữa hàng có số | Chip `chưa đo` xám, dồn cuối bảng |
| Mười bốn icon `?` rải khắp | Gạch chân chấm dưới tên metric + tooltip hover, bỏ glyph rời |
| Metric ngược chiều không có dấu hiệu | `+9.35 ms` và `+0.1 MB` là **xấu**, `+17.5 s` cũng xấu. Cần mũi tên hướng ở header cột metric, nếu không người đọc mặc định dấu cộng là tốt |

### Visual comparison — thiếu hoàn toàn

Chưa có bar / small multiple / radar cho metric đã chuẩn hoá. Đề xuất
dải bar ngang 0–1 cho tám metric có hướng, **kèm chú thích cách chuẩn
hoá** (min–max theo ngưỡng deployment hay theo max của cặp?). Metric
chưa chuẩn hoá thì không vẽ, đúng như brief.

### Trade-off insights — thiếu hoàn toàn

Run này B thua sạch nên insight đúng là "không có trade-off,
`astar+dwa` dẫn ở cả năm metric có hướng, `rrtstar+dwa` không dẫn ở
metric nào". Vẫn phải in ra: im lặng buộc người đọc tự đi diff mười
dòng để rút ra cùng kết luận đó.

### Decision recommendation — thiếu trục use-case

Trang hiện chỉ trả lời "có / không có khuyến nghị". Brief yêu cầu trả
lời theo use case, và **kể cả khi bị chặn vẫn trả lời được**:

- Quality-critical / offline → `astar+dwa`, nhưng là lựa chọn duy nhất
  khả thi chứ không phải bên thắng một cuộc so.
- Real-time / edge / low-memory → không có ứng viên; `rrtstar+dwa`
  trượt G3 nên không được đề xuất kể cả khi latency có tốt hơn.
- Hybrid → không áp dụng: hybrid cần tối thiểu hai bên qua cổng.

Ba câu đó là câu trả lời có ích. Ô trống thì không.

### Bằng chứng detector

Cột Candidate in hash thô `29cdf6266a44`, `e1251e42a20b`. Không đọc ra
ai. Hiện tên (`astar+dwa`) + hash mono nhỏ phía sau.

### Rò ngôn ngữ

UI đang ở `vi` nhưng khối "Phép tương phản ủng hộ điều gì" in nguyên
câu tiếng Anh, bốn dòng:

> the pattern follows global_planner across every pair that changes only
> that component, it is the only component it follows, and every other
> part of the stack was held fixed

Cùng khối đó phần nhãn (`ủng hộ quy kết cho một component`) lại đã
dịch. Nghĩa là chuỗi giải thích chưa vào bảng i18n. Phải localize.

### Panel điểm số

- Chip `u_R 1.00` `u_S 1.00` `u_E 0.57` `u_C 0.96` — chữ cái không giải
  mã được tại chỗ, phải hover từng cái. Ghi nhãn thẳng: `Thành công`,
  `An toàn`, `Hiệu quả`, `Tính toán`.
- Bar của candidate bị chặn nên gạch chéo, không chỉ đổi sang xám —
  xám vẫn đọc như "điểm thấp", không đọc ra "không đủ tư cách".
- Thiếu breakdown `weight × score = contribution` trên màn hình, trong
  khi workbook Excel đã có. Hai kênh cùng dữ liệu mà kênh dùng nhiều
  hơn lại nghèo hơn.

### Episode replay

- **Đơn vị lệch giữa hai nơi, không phải bug.** Ô "Clearance tệ nhất
  tới giờ" hiện `3.81 r`; chuỗi gốc là
  `"running.metric.safety_margin": "Worst clearance so far (robot radii)"`
  ([en.json:1492](../../../../apps/web/src/lib/i18n/locales/en.json#L1492)) —
  đơn vị là bán kính robot, cố ý. Nhưng bảng so sánh phía trên ghi cùng
  khái niệm là `0.470 m`. Hai đơn vị cho một khái niệm, trên cùng một
  trang, không chỗ nào nói vì sao. Chọn một, hoặc in cả hai
  (`0.470 m · 3.81 r`).
- Hai biểu đồ latency đặt cạnh nhau, chiều dài pixel bằng nhau, nhưng
  x-max là 22.0s và 38.8s. Đọc lướt thành "hai episode dài như nhau".
  Ép chung scale, hoặc vẽ phần dư của trục ngắn hơn thành vùng trống.
- Trục y hai nhãn `54` và `50` đè lên nhau.
- Ô "Đã đi được 0.0 %" ở `t=0` là ô chết — mọi run đều 0 tại đó.

---

## 4. Semantic rules cho winner / loser / tie / uncertain

| Trạng thái | Nhãn text bắt buộc | Chữ | Nền |
|---|---|---|---|
| winner | `A` / `B` | green-700 | green-50 |
| loser | (số thường, không nhãn) | red-700 | trong suốt |
| tie | `hoà` | slate-600 | trong suốt |
| uncertain | `chưa phân định` | amber-700 | amber-50 |
| not measured | `chưa đo`, in nghiêng | slate-400 | trong suốt |
| blocked | `trượt G3` | red-700 | red-50 |

Luật cứng:

1. Mọi ô có màu **phải** kèm nhãn chữ hoặc dấu `+`/`−`. Màu là lớp thứ
   hai, không bao giờ là lớp duy nhất.
2. Màu định danh candidate **khác tập** màu semantic. Bỏ xanh lá khỏi
   identity của B; nếu vẫn muốn phân biệt hai cột thì dùng xanh dương
   và tím.
3. Delta bằng 0 → `hoà`, không tô màu.
4. Metric ngược chiều phải khai báo hướng ở header, và winner tính
   theo hướng đó.

---

## 5. Recommendation logic và cách hiện hybrid

```
qualified = candidate qua hết G1..G6

len(qualified) == 0  → "Không khuyến nghị · không ai qua cổng"        [blocked]
len(qualified) == 1  → "Chỉ một candidate khả thi" — nêu tên,
                        KHÔNG gọi là winner, nói rõ thiếu đối chứng   [uncertain]
len(qualified) >= 2  →
   ΔU < ngưỡng nhiễu            → "Hoà trong sai số" + số episode cần thêm
   một bên thắng mọi objective  → single winner
   thắng chéo objective         → HYBRID
```

Run `sudden_stop_v5` rơi vào nhánh `len == 1`, **không phải nhánh
`len == 0`** như chữ hiện tại ở `Outcome` đang nói. Card đúng phải đọc
là: *"Chỉ `astar+dwa` khả thi. Chưa phát khuyến nghị vì không có đối
chứng nào qua cổng. Việc cần làm: đăng ký một candidate tốt hơn."* —
gần đúng chữ đang có, chỉ sai mệnh đề đầu và sai vị trí.

Khi nào rơi vào nhánh HYBRID thì hiện ba thẻ dọc:

| Use case | Chọn | Kèm |
|---|---|---|
| Chất lượng / offline | A | metric A dẫn |
| Real-time / edge / ít bộ nhớ | B | metric B dẫn |
| Cần cả hai | Hybrid | routing rule cụ thể + chi phí vận hành hai stack |

Routing rule phải viết được thành câu kiểm chứng được — "case khó
(clearance dự báo dưới ngưỡng cảnh báo) sang A, case nhạy latency sang
B", hoặc "ensemble theo confidence threshold τ" — chứ không phải chữ
"hybrid" trơ.

---

## 6. Acceptance checklist

### UX

- [ ] Trong 5 giây thấy được: bên dẫn, ΔU, độ tin cậy, khuyến nghị — không cần cuộn
- [ ] Khuyến nghị nói đúng một lần ở summary, một lần ở explainability
- [ ] Có decision advice theo use case kể cả khi run bị chặn
- [ ] `TracePanel` collapsed mặc định
- [ ] Mọi metric có định nghĩa hover
- [ ] Dưới 900px thứ tự là summary → advice → bảng

### Visual QA

- [ ] Không màu nào đứng một mình mang nghĩa
- [ ] Màu identity candidate không giao với màu semantic
- [ ] Không row nào cao quá 60px
- [ ] Header bảng sticky
- [ ] Số căn phải theo dấu thập phân, unit thẳng cột
- [ ] Không neon / glass / gradient lớn; bo góc ≤ 8px; tối đa một lớp shadow mỏng
- [ ] Không còn câu tiếng Anh nào khi locale là `vi`

### Data integrity

- [ ] Đơn vị clearance nhất quán giữa bảng và ô replay, hoặc in cả hai
- [ ] Hai chart cạnh nhau dùng chung scale, hoặc ghi rõ scale khác nhau
- [ ] Winner từng hàng cộng lại khớp dòng tổng "dẫn 5 trên 8 chỉ số có hướng"
- [ ] Contribution cộng lại đúng bằng utility trên card
- [ ] Metric ngược chiều tính winner đúng chiều
- [ ] Mệnh đề trong `Outcome` khớp số candidate thực sự qua cổng
- [ ] Bảng detector hiện tên candidate, không chỉ hash

---

## 7. Thứ tự làm đề xuất

**P0 — sai nghĩa hoặc chặn mục tiêu 5 giây**

1. Sửa mệnh đề `Outcome`: "không candidate nào qua cổng" trong khi
   `astar+dwa` qua hết G1–G6. Đây là lỗi đúng/sai, không phải thẩm mỹ.
2. Dựng `DecisionSummary` + `DecisionAdvice` ở đỉnh; hấp thụ
   `ConclusionPanel` và `Outcome`.
3. Hạ `TracePanel` xuống dưới `EvidencePanel`, collapsed mặc định.
4. Bỏ tint xanh lá khỏi cột candidate B.
5. Thêm cột Winner vào bảng.

**P1 — đọc sai hoặc mỏi mắt**

6. Localize khối contrast.
7. Thống nhất đơn vị clearance.
8. Nén row cảnh báo latency, bật sticky header, căn phải số.
9. Bảng detector hiện tên candidate.
10. Mũi tên hướng cho metric ngược chiều.

**P2 — bổ sung phần brief yêu cầu mà chưa có**

11. `TradeoffInsights`.
12. `VisualComparison` bars đã chuẩn hoá.
13. Nhãn chữ cho `u_R` / `u_S` / `u_E` / `u_C` + breakdown contribution.
14. `ExportReport` lên header.
15. Chung scale cho hai chart latency, sửa đè nhãn trục y.

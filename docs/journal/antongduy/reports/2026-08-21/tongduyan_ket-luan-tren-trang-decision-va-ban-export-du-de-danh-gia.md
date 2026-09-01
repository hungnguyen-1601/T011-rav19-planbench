# Kết luận trên trang decision, và bản export đủ để đem ra đánh giá

**Ngày:** 2026-08-21 · **Nhánh:** `tongduyan_3` · **Trạng thái:** xong, **chưa commit**

Bốn việc nối nhau trong một mạch: trang decision phải **kết thúc bằng một câu trả lời**,
và hai bản export phải mang đủ số liệu để câu trả lời đó **kiểm chứng được từ bên ngoài
màn hình**.

---

## 1. Thang điểm /100 và khối kết luận

Yêu cầu của anh: normalize thang điểm **đang có**, không dựng thang mới. Nên
`decision_utility` (0–1) chỉ được **nhân 100 và hiển thị**, không đụng vào công thức —
HĐ-9.1 đã định nghĩa nó rồi, viết thêm một phép tính ở tầng UI là mở đường thứ hai để ra
cùng một con số.

**Một chữ số thập phân, cố ý.** `0.8774` và `0.8770` cùng làm tròn thành `88`, mà đó là
hai candidate ΔU phân biệt được. Số nguyên sẽ biến một khác biệt thật thành hoà.

### Nguyên lý trừ điểm — câu trả lời cho câu anh hỏi

Anh hỏi có **số điểm trừ cụ thể** cho candidate trượt gate không. **Không có, và cố ý
không có.** Bất kỳ con số trừ nào tôi chọn — trượt một gate trừ 10, trượt G2 trừ 25 —
đều là tôi **tự bịa ra một hệ số cân đo** mà không hợp đồng nào viết, rồi in nó ra dưới
dạng điểm số trông như đã được đo. Đó đúng là con đường chấm điểm thứ hai mà HĐ-9.2 cấm.

Thay vào đó, theo lối B anh đã chọn: **vẫn chấm điểm mọi candidate**, nhưng chia làm
**hai nhóm không bao giờ xếp lẫn nhau**, ngăn bằng một đường kẻ đứt:

| Nhóm | Ý nghĩa |
|---|---|
| **Eligible** | Qua hết gate. Trong nhóm này, điểm **có** xếp hạng. |
| **Blocked** | Trượt gate. Vẫn có điểm, kèm cảnh báo cụ thể. Điểm này **không so được** qua đường kẻ. |

Lý do đường kẻ quan trọng hơn con số: **va chạm bị loại khỏi `U_S` theo HĐ-6** — để nó
không thể đem đổi lấy tốc độ. Nghĩa là một stack **đã đâm vào vật thể vẫn có thể mang
điểm cao hơn** một stack không đâm. Một danh sách xếp hạng duy nhất sẽ đặt nó lên đầu
kèm một cái badge cảnh báo mà không ai đọc.

`invisibleFailures()` chỉ đánh dấu những gate mà **cái trượt không để lại dấu vết nào
trong điểm**: G6 (không objective nào phản ánh kênh quan sát thiếu) và G2 *khi thật sự có
va chạm*.

### Đầu đề lấy từ card, không lấy từ `standings[0]`

HĐ-10.1 cấm khuyến nghị candidate bị Pareto-dominate kể cả khi nó dẫn đầu về utility, và
`NEAR_EQUIVALENT` nghĩa là không tách được. Nên `verdictOf()` đọc `card.status`, ba dạng:
`recommended` / `near-equivalent` / `no-card`. Chỉ dạng đầu mới được nêu tên người thắng.

ΔU luôn in **kèm khoảng tin cậy**. `marginIsConclusive()` kiểm tra khoảng có vắt qua 0
không — vắt qua 0 nghĩa là "dẫn trước, nhưng không đo được", in mỗi giá trị trung bình sẽ
biến điều đó thành một kết quả.

---

## 2. G2 là hai lỗi khác nhau đội chung một nhãn

Anh báo UI hiện "bị block bởi gate nên không thể hiện điểm". Đào ra thì đây là phát hiện
đáng giá nhất trong ngày:

**Toàn bộ run `sudden_stop` trượt G2 với `observed = 0` va chạm.** Chúng trượt vì
**mẫu quá nhỏ** — 5 episode phân biệt trên 30 yêu cầu — không đủ để *chặn trên* rủi ro.

Hai thông điệp ngược nhau: một cái nói robot đâm vào cái gì đó, cái kia nói **chưa ai
nhìn đủ lâu để biết**. Và nó quyết định điểm có tin được không: va chạm bị `U_S` loại
theo HĐ-6 nên điểm không thấy nó; còn mẫu nhỏ thì điểm vẫn nguyên vẹn, chỉ là ít.

`collisionGateReason()` đọc thẳng `G2.observed` chứ không suy từ verdict, vì chính verdict
mới là thứ gộp hai cái làm một.

### Chạy lại và thay các dòng cũ

Theo yêu cầu của anh (xoá hẳn dòng cũ, thay bằng dòng mới; `sudden_stop_v5` nâng lên 30):

- Sao lưu `planbench.db` trước, xác nhận **không dòng nào có approval record**.
- 3 sweep đầu hỏng vì `task profile not found` — `sudden_stop_v4` và `sudden_stop_v5`
  **chưa từng được đăng ký với API**. Đã validate qua `TaskProfile` rồi mới nạp, chạy lại.
- **6 dòng `sudden_stop` được thay.**

Ở đây cũng làm rõ một hiểu sai của tôi mà anh phát hiện: **UI đọc `planbench.db`**, không
đọc `artifacts/runs/` — hai kho tách biệt, kho trên đĩa là bản lưu vết và **lossy** (tên
thư mục là `<ngày>/<profile>_<scope>_<hash>` nên chạy lại trong cùng ngày sẽ ghi đè).

---

## 3. Bấm Export Excel ra file `.md` — hai lỗi chồng nhau

**Lỗi một.** `filenameFromDisposition` fallback về `benchmark-<id>.md` **hard-code**. Nó
đúng khi markdown là định dạng duy nhất; nó thành lời nói dối ngay khi có định dạng thứ hai.

**Lỗi hai — và là lý do fallback được chạy:** trình duyệt **không đưa `Content-Disposition`
cho JavaScript qua cross-origin** trừ khi server cho phép. Web ở `:3000`, API ở `:8000`,
nên **mọi lần tải đều đang đi vào fallback**.

Hệ quả không ai để ý: bản markdown **lâu nay vẫn lưu thành `benchmark-<id>.md`** thay vì
`decision-<id>.md` như server chọn — đuôi file tình cờ đúng nên không ai thấy.

Sửa: `expose_headers=["Content-Disposition"]` ở CORS, và fallback **do caller đưa vào cả
đuôi file**, hàm không được tự đoán.

---

## 4. Export: từ "báo kết quả sơ bộ" thành "đủ để đánh giá"

Nhận xét của anh về bản đầu — *"hơi ít thông tin quá"*. Đúng. Thiếu hai thứ:

**Kết luận của chính run đó.** Card mang utility, bốn objective, ΔU và khoảng tin cậy —
tức là **phần thực chất của quyết định** — mà không thứ nào ra tới file. Một tài liệu tên
"Decision Card" nói ai thắng mà không nói **thắng bao nhiêu** và **chắc đến đâu** là đúng
nửa câu trả lời đi xa nhất.

**Các episode.** `success_rate: 0.70` nói 70% chuyện gì đó đã xảy ra; nó **không nói 30%
nào đã không**, cũng không nói đó là va chạm hay timeout — mà hai cái đó đòi hai loại
việc khác nhau. Các dòng này nằm sẵn trong report từ đầu.

Cả ba khối đều viết vào `decision_export.py`, nên **markdown và Excel nhận cùng lúc** và
không thể mô tả cùng một run theo hai kiểu:

| Khối | Nội dung |
|---|---|
| `OUTCOME_COLUMNS` / `outcome_rows` | **18 cột × mỗi candidate.** Utility /100, U_R/U_S/U_E/U_C, success, va chạm, chặn trên 95%, tỉ lệ không tìm được đường, clearance tệ nhất, episode trung vị, p99, ước lượng bộ nhớ, số episode phân biệt, số lần replan, **eligible to recommend**. Sáu trong mười metric của lưới so sánh trước đây **chưa từng rời khỏi màn hình**. |
| `decision_evidence_rows` | Khối **"The margin"** trong Decision Card: decision_utility, pareto_label, decision_mode, ΔU so với á quân, ΔU trung bình, **khoảng 95%**, effect size, số episode so sánh, bốn objective. |
| `EPISODE_COLUMNS` / `episode_rows` | **9 cột × mỗi episode.** Có cột **failure reason** chứ không phải "failed" trống trơn — đó là cột người đọc quét để tìm episode đáng mở ra xem. |

Excel giờ **7 sheet**: Provenance, Sample, Gates, Outcome by candidate, Decision Card,
Episodes, Human record. Markdown thêm `## Outcome by candidate` và `## Episodes`.

Cột `Eligible to recommend` được **ghi thẳng ra chữ**, không để người đọc tự suy từ cột
gate — vì như mục 1: trượt gate có thể **không để lại dấu nào** trên điểm, nên "điểm thấp
hơn" và "chưa bao giờ trong cuộc đua" không phân biệt được nếu chỉ nhìn con số.

### Hai đại lượng gộp: tính một lần, ở một chỗ

`worst_clearance_m` và `median_travel_time_s` trước đó **trang web tự rút gọn bằng
TypeScript**, còn export thì sẽ rút gọn lại lần nữa bằng Python. **Trung vị có một lựa
chọn thật nằm trong nó** — đếm chẵn thì làm tròn về phía nào — và hai bản cài đặt hoàn
toàn có thể chọn khác nhau.

Nên `_episode_aggregates()` trong `selection.py` tính một lần khi chấm điểm rồi ghi vào
report; `candidateMetrics.ts` **đọc ra** thay vì tự tính (phần rút gọn cũ giữ lại làm
fallback cho run lưu trước khi có field — những run đó vẫn còn dòng episode, và cho người
đọc một con số vẫn hơn một dấu gạch).

**Backfill:** 8 run đang có trong DB đều lưu trước khi field tồn tại, nên hai cột này sẽ
in "not measured" đúng chỗ anh cần nhất. Đã tính bù bằng **chính hàm đó** (không viết lại
phép rút gọn trong script) rồi ghi vào DB — sao lưu trước. Kiểm trên run xếp hạng
`5753d464c9f6`: `0.47 m` / `0.494 m` và `22.5 s` / `22.6 s`.

---

## 5. Kiểm chứng

Trên **dữ liệu thật**, không chỉ trên test:

```
sheets: Provenance, Sample, Gates, Outcome by candidate, Decision Card, Episodes, Human record
  Outcome by candidate: 5 dòng × 18 cột
  Episodes:            61 dòng × 9 cột
  ô có chữ số trong workbook mà markdown không có: không có ô nào
  markdown: 9528 byte
```

Tính chất quan trọng nhất vẫn là cái cũ: **mọi ô mang chữ số trong workbook phải tìm được
nguyên văn trong markdown.** `7.35 ms` ở file này và `7.3479809999` ở file kia là một phép
đo hiện thành hai dạng, và người cầm cả hai bản không có cách nào biết bản nào đúng.

- `tests/test_compare.py` — **29 passed**
- `tests/api/test_decision_xlsx.py` — thêm class `TestWhatMakesItEvaluable` (4 test)
- `ruff check apps/api packages tests/api/test_decision_xlsx.py` — **All checks passed**
- Web suite — **1299 passed** (`tsc --noEmit` sạch)

> Còn 3 lỗi ruff ở `tests/api/test_api_explanation.py` và
> `tests/api/test_api_profile_validation.py`. **Có từ trước, không thuộc phần này**, tôi
> không đụng vào.

---

## 6. Còn treo

1. **Gửi kết quả qua mail** — đã trả lời là khả thi (~1,5–2 ngày). Chờ anh quyết:
   nhà cung cấp SMTP, **ai được gửi cho ai**, và bản ghi audit cho mỗi lần gửi.
2. **Tab import thuật toán** — plan `docs/antongduy/plans/2026-08-20/tab-import-thuat-toan.md`,
   anh cho tạm dừng, còn 4 câu hỏi mở.

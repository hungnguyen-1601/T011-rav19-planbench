# Tính năng có thể thêm — không phải nợ kỹ thuật

**Phân biệt với [bản kiểm kê nợ](tongduyan_no-ky-thuat-ton-dong.md), và phân biệt này do dev
chốt 13-08:**

| | |
|---|---|
| **Nợ kỹ thuật** | Một thứ **đang sai hoặc đang thiếu so với điều đã tuyên bố**. Không trả thì có một tuyên bố không đứng được |
| **Tính năng có thể thêm** | Một thứ **chưa bao giờ được hứa**. Không làm thì nền tảng vẫn đúng, chỉ là làm được ít hơn |

Nhầm hai cái này thì bản kiểm kê nợ phình ra thành danh sách ước, và cái danh sách đó không ai
đọc nữa.

---

## F1. Chạy Task Neighborhood để điền `robustness_margin`

**Bộ sinh đã xong** (`planbench_benchmark.neighborhood`, 13-08): K biến thể tất định, `variant_id`
là hash nội dung, nhiễu được nhân chứ không tạo ra, biến thể không xếp hạng được tính là trượt.

**Cái chưa làm:** chạy K sweep trên K biến thể, thu khuyến nghị của từng cái, điền
`robustness_margin` vào Decision Card.

**Vì sao đây là tính năng chứ không phải nợ.** HĐ-12 khai `robustness_margin` là `float | None`,
và null **đã có nghĩa được định nghĩa**: *"chưa đo"*. Card hiện tại vì thế **trung thực** — nó
không tuyên bố một độ bền nó chưa đo. Không có gì đang sai; có một câu hỏi chưa được hỏi.

**Giá:** **20× giờ máy của một phép so.** Kho ở mức rủi ro 1% là 20 × 2,2 giờ ≈ **44 giờ máy**
cho một tấm card. Đó là lý do nó không thể là "việc phải làm" mà là một quyết định về ngân sách.

Vài đường rẻ hơn, chưa xét kỹ, ghi để lần sau khỏi nghĩ lại từ đầu:

- **Ít episode hơn cho biến thể.** Neighborhood không ước lượng tỷ lệ thành công hay cận trên va
  chạm — nó chỉ hỏi *"khuyến nghị có lật không"*. `pairing` đã biết episode trong cùng một biến
  thể là tương quan và `gates` đã loại chúng khỏi G2, nên một N nhỏ hơn ở đây **không** làm hỏng
  con số nào khác. Cần một lập luận về việc N bao nhiêu là đủ để phát hiện một lần lật.
- **Dừng sớm ở mức biến thể.** Nếu 8 biến thể đầu đều đồng ý thì R ≥ 0,4 đã chắc; nếu 9 cái đầu
  đều lật thì R < 0,6 đã chắc và nhãn `NEAR-EQUIVALENT` đã chốt được. Cùng họ với dừng sớm theo
  candidate đã có.
- **Chỉ chạy neighborhood cho card sắp được duyệt**, không cho mọi phép so.

**Ràng buộc đã có sẵn, không phải dựng lại:** `sample_set="neighborhood"` ·
`neighborhood_contexts` trong manifest · `pairing` biết cụm · `gates` loại khỏi cận trên G2 ·
`effective_claim_level(neighborhood_evaluated=...)` đã dùng nó để quyết mức tuyên bố.

**Ngưỡng đã khai sẵn trong tài liệu đề tài:** R < 60% ⇒ card đổi nhãn thành
`NEAR-EQUIVALENT — deployment này nhạy cảm, nên đo lại bản đồ thực địa trước khi chốt`.

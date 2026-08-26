# Xuất Excel cho decision run — và câu trả lời về gửi mail

**Ngày:** 2026-08-20 · **Nhánh:** `tongduyan_3`

**Trạng thái:** Excel xong, **chưa commit**. Gửi mail *chưa làm* — xem mục 4.

---

## 1. Vấn đề thật không phải "thêm một định dạng"

Thêm `.xlsx` bên cạnh `.md` là dễ. Cái khó là **hai tài liệu mô tả một run không được
phép nói khác nhau**. Một card ghi 94,2% ở file này và 94% ở file kia còn tệ hơn là chỉ
có một định dạng: ai đó sẽ chuyển tiếp bản hợp ý mình, rồi hai bản bị đem ra đối chiếu
với nhau.

Nên trước khi viết bản Excel, tôi tách `decision_export.py` — **module quyết định export
nói gì**, còn mỗi renderer chỉ quyết định nó **trông thế nào**. Ba tính chất mà bản
markdown vốn được xây quanh chuyển hết sang đó, vì chúng là tính chất của *nội dung*:

1. Run không có card **vẫn xuất được** (HĐ-7 — dưới hai candidate qua cổng thì bảng cổng
   chính là sản phẩm).
2. Null hiện thành **"not measured"**, không bao giờ để trống.
3. **Caveat đi theo** con số nó cảnh báo.

## 2. Chứng minh bản markdown không đổi một byte

Refactor một exporter đang chạy là chỗ dễ làm hỏng âm thầm. 19 test có sẵn **pass ngay
lần đầu** — và vẫn **bỏ lọt** một khác biệt: tôi dựng lại đoạn blockquote cảnh báo bằng
`text.split(".")[0]`, làm nó gộp ba dòng thành một. Test chỉ khẳng định *có chứa cụm từ*,
không khẳng định *cùng một tài liệu*.

Bắt được bằng cách render một report thật qua cả bản `HEAD` lẫn bản mới rồi diff, trên
bốn nhánh: bình thường, mixed observation, có candidate bị rút sớm, và không có card.
**Cả bốn identical.**

Bỏ luôn cái `split(".")` — nó là một **parser tiếng Anh** nằm trong module không có
việc gì phải sở hữu một cái. Thay bằng `Caveat(lead, body)`: dữ liệu mang sẵn cả từ ngữ
lẫn điểm ngắt dòng, markdown bọc `> `, Excel nối bằng dấu cách.

## 3. Bản Excel

`GET /decisions/{id}/report.xlsx`. Năm sheet: Provenance, Sample, Gates, Decision Card,
Human record.

Ba điều một bảng tính làm sai mà trang giấy thì không:

- **Ô trống**: trên giấy chỉ là thiếu thông tin; trong bảng tính nó **sắp lên đầu, cộng
  ra 0, và trung bình như thể đã được đo**. Nên "not measured" là chữ, luôn luôn.
- **Workbook là định dạng dễ bị xé lẻ nhất** — copy một sheet sang slide, dán một cột
  vào mail. Nên mỗi caveat nằm **trên chính sheet chứa con số nó cảnh báo**, không nằm
  ở lời mở đầu mà người ta bỏ lại.
- **Tên sheet**: quá 31 ký tự hoặc dính `[]:*?/\` là Excel từ chối **cả file**, và lời
  từ chối đó tới tay người đọc chứ không tới tôi. Có hàm chặn và có test.

**Giá trị ghi dạng chuỗi giống hệt bản markdown**, không phải float thô. Mất khả năng
sort/sum, đổi lại thứ đáng hơn: hai tài liệu không thể trích hai con số khác nhau cho
cùng một run. `7.35 ms` ở đây và `7.3479809999` ở kia là cùng một phép đo mà người đọc
không có cách nào biết. Nếu An cần cột số thô để vẽ chart thì nói, tôi thêm — nhưng đó
là một quyết định, không phải mặc định.

Đổi tên `downloadReportMarkdown` → `downloadReport`: cơ chế của nó (fetch có xác thực →
Blob → anchor) chưa bao giờ gắn với markdown, nhưng cái tên thì nói vậy. Một helper tên
Markdown mà phục vụ `.xlsx` là lời nói dối sống được nhiều năm vì **không có gì hỏng vì nó**.

**Test:** 34 (Python) + 1274 (web). Trong đó test đáng nhất là cái duyệt mọi ô có chữ số
trong workbook và đòi tìm thấy đúng chuỗi đó trong markdown.

## 4. Gửi mail: khả thi, nhưng **không phải việc UI**

Repo **không có hạ tầng gửi mail nào**. `email` chỉ xuất hiện như một *trường lưu trữ*
trên account lấy từ OAuth — không SMTP, không provider, không hàm gửi, không config.

Nên nó cần, theo thứ tự:

1. **Chọn đường gửi** — SMTP nội bộ, hay dịch vụ (SES/SendGrid/Resend). Quyết định này
   kéo theo credential, và credential thì không nằm trong repo được.
2. **Ai được gửi tới đâu.** Một endpoint nhận địa chỉ tuỳ ý và gửi file đính kèm là một
   **open relay**: gửi spam hộ người khác, và đẩy dữ liệu run ra ngoài. Tối thiểu phải
   giới hạn theo domain hoặc chỉ cho gửi tới chính email của tài khoản đang đăng nhập.
3. **Gửi bất đồng bộ.** SMTP chậm và hay lỗi; gửi ngay trong request sẽ làm treo API và
   không có đường thử lại.
4. **Ghi nhận đã gửi.** Gửi kết quả cho ai, lúc nào — cùng loại bản ghi với HĐ-14, và
   là thứ người ta sẽ hỏi lại sau.

Ước lượng ~1,5–2 ngày sau khi có credential. **Tôi chưa làm gì phần này** — cần An chốt
mục 1 và 2 trước, vì chọn sai thì không sửa bằng code được.

## 5. Một lỗi có sẵn phát hiện lúc làm

Câu scope hiện render thành: *"this recommendation applies to `MISSION_LEVEL` and to
nothing else (HĐ-1.4)"*. Nhưng `MISSION_LEVEL` là một **mức phạm vi**, không phải một
deployment — còn HĐ-1.4 nói về deployment. Bản markdown viết vậy từ trước, tôi giữ
nguyên để hai bản không lệch nhau.

**Chưa sửa** vì sửa là đổi output của bản markdown đang chạy. An muốn thì tôi sửa cả
hai cùng lúc.

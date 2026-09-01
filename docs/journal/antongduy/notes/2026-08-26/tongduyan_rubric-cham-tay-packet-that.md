# Rubric chấm tay packet thật — cố định trước khi có số

**Plan:** `plans/2026-08-26/de-xuat-cai-thien-hieu-qua-ai-analyst.md` bản 6, mục W0.2
**Áp dụng cho:** packet lấy từ run thật (không phải planted/golden), nơi không
có `expected_findings` để so máy.
**Phiên bản rubric:** `r0.1.0` — đổi tiêu chí là đổi phiên bản, và số chấm
theo phiên bản cũ không so được với phiên bản mới.

## Vì sao cần rubric riêng cho packet thật

Trên golden fixture, đúng/sai là so với nhãn đã trồng. Trên packet thật thì
không ai trồng gì cả — người chấm phải tự đọc packet rồi quyết. Nếu tiêu chí
chấm được nghĩ ra *sau* khi thấy đầu ra của từng cấu hình, người chấm sẽ
(vô thức) chọn tiêu chí hợp với cấu hình mình thích. Rubric này chốt trước,
và người chấm **không được biết** đầu ra đến từ cấu hình nào.

## Quy trình mù cấu hình

1. Harness sinh đầu ra của mọi cấu hình cần so trên cùng một packet, gom vào
   một file, **xáo thứ tự**, gắn mã `S1, S2, …` thay cho tên cấu hình. Bảng
   `mã → cấu hình` do người chạy giữ, người chấm không mở.
2. Người chấm đọc **packet trước**, ghi ra mechanism mình tin là đúng (hoặc
   "không đủ bằng chứng") **trước khi** đọc bất kỳ đầu ra nào. Dòng này là
   *anchor* và không được sửa sau.
3. Chấm từng đầu ra theo 5 tiêu chí bên dưới. Mỗi tiêu chí là một giá trị
   rời rạc, không có điểm lẻ.
4. Mở bảng mã sau khi mọi packet của đợt đã chấm xong.

Người chấm cho một đợt phải là **một người** cho toàn đợt, hoặc hai người
chấm độc lập rồi báo cả hai cột — không gộp trung bình.

## Năm tiêu chí

| # | Tiêu chí | Giá trị | Cách quyết |
|---|---|---|---|
| R1 | Mechanism khớp anchor | `match` / `plausible_other` / `wrong` / `abstained` | `match` = trùng anchor. `plausible_other` = khác anchor nhưng packet đủ bằng chứng cho nó. `abstained` = analyst trả về không có đề xuất. |
| R2 | Component đúng | `yes` / `no` / `n/a` | `subject` của proposal (global_planner / local_controller / costmap_inflation / …) là thành phần anchor nói tới. `n/a` khi R1 = `abstained`. |
| R3 | Bằng chứng trích dẫn có liên quan | `all` / `some` / `none` | Mỗi `evidence_ref` mở ra được trong packet **và** nói về mechanism đề xuất. `some` = ít nhất một ref lạc đề. |
| R4 | Tool gọi có xứng | `right` / `unneeded` / `missed` / `none_needed` | `missed` = anchor cần checker (case `check_required`) mà analyst không gọi. `unneeded` = gọi checker khi packet đã đủ. |
| R5 | Abstention đúng chỗ | `correct` / `should_have` / `should_not` / `n/a` | So với anchor "không đủ bằng chứng". `n/a` khi cả anchor và đầu ra đều có mechanism. |

Ghi thêm một cột tự do `note` — không tính điểm, chỉ để người đọc sau hiểu vì
sao.

## Cái gì **không** chấm

- **Wording** (associated / suggests / caused): guard đã cấm causal wording
  trước khi đầu ra tới người chấm, nên đầu ra có wording sai là bug guard, ghi
  vào `note` và báo riêng, không trừ điểm analyst.
- **Số liệu** trong statement: model không được phát số; số là renderer đọc từ
  fact index. Đầu ra mang số là guard rule 2 hỏng — cũng báo riêng.
- **Văn phong, độ dài**: không có tiêu chí nào cho việc này, và không thêm.

## Từ rubric ra số

- Primary trên packet thật = tỷ lệ `R1 == match` theo case (mỗi case tính
  một lần, lấy **lượt tệ nhất** trong `repeats` — cùng luật với golden).
- `R1 == plausible_other` báo **riêng**, không gộp vào `match` và không gộp
  vào `wrong`. Đây là chỗ anchor có thể sai, không phải chỗ analyst sai.
- Mọi bảng số từ packet thật ghi rõ `rubric r0.1.0`, số packet, người chấm,
  và **`exploratory`** — theo W0.9, chưa có holdout thì không có kết luận
  deployment từ bất kỳ đợt nào.

## Kích thước tối thiểu

Dưới 12 packet thật thì báo **counts**, không báo tỷ lệ — cùng ngưỡng
`min_cases_for_pass_k` trong preregistration. Lý do như golden: trên 3 case
một lần lật là 33 điểm.

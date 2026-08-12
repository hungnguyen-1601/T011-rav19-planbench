# D2 đợt 1 — trang `/decisions`, bảng cổng là màn hình hạng nhất

**Ngày:** 2026-08-12 · **Pha:** 7 (backlog 08-08) · **Phạm vi đợt này:** chỉ đọc, chưa có nút ghi

---

## 1. Ràng buộc định hình cả trang

Ràng buộc từ plan 08-11, nay có bằng chứng: **bốn trên năm phép so đã chạy không ra card.**

Một UI chỉ dựng được Decision Card sẽ tạo lại đúng áp lực buộc mọi run phải rank được — áp lực đã
sinh ra tấm card tuyên bố cận trên va chạm từ một episode. Nên:

- **Bảng cổng đứng trước khuyến nghị** trên trang chi tiết. Sáu cổng chạy trước khi chấm bất cứ
  thứ gì (HĐ-7); đặt người thắng lên đầu và giấu cổng vào tab dưới là lật ngược hợp đồng ngay trên
  màn hình, và cho người đọc lấy một người thắng mà không thấy ai đã bị loại để sinh ra nó.
- **Bộ lọc mặc định là không lọc gì.** Mặc định "chỉ run có card" sẽ trình bày một nền tảng gần
  như không có gì xảy ra, đồng thời giấu đúng những run đã loại được candidate.
- **Không màu đỏ cho run không card.** Đỏ là toàn bộ khác biệt giữa "đây là một kết quả" và "cái
  này hỏng". Chip lý do dùng tông cảnh báo hoặc mờ, không bao giờ `err` — có test khoá điều này.

## 2. Ba cách không có card, ba việc phải làm khác nhau

Gộp cả ba thành "no card" là cách bảng cổng bắt đầu đọc như một run hỏng. `noCardReason()` tách:

| lý do | việc cần làm |
|---|---|
| `interrupted` | chạy nốt số episode còn lại; phần đã đo trên đĩa được dùng lại |
| `gate_only` | xếp hạng trên deployment khác. **Không candidate nào đổi được chỗ này** — chính cái thang đã sập (HĐ-8.4) |
| `no_survivors` | đăng ký candidate tốt hơn. **Không phải nới deployment** |

`interrupted` được ưu tiên trước hai cái kia: một run chưa hỏi xong câu hỏi thì "không ai qua cổng"
là phán quyết trên bằng chứng còn đang tới.

Câu chữ tiếng Anh cho `no_survivors` chứa nguyên văn *"Never a softer deployment"*, và có test
khẳng định nó còn ở đó — đây là nước đi hợp đồng cấm, nên nó phải nằm trong copy chứ không nằm
trong trí nhớ ai đó.

## 3. Hai thứ phát hiện khi đối chiếu với artifact thật

Không đoán hình dạng dữ liệu — đọc `comparison_report.json` thật của hai run trên đĩa. Hai chỗ sai:

**① Phán quyết cổng có hai hình dạng trên dây.** G1 và G3 tuần tự hoá thành chuỗi trần `"pass"`,
còn G2/G4/G5 thành object có `result` cộng bằng chứng. Bản viết đầu render chuỗi trần thành text
thường — bảng sẽ có G1 là chữ đen còn G2 là chip màu, đọc như thể chúng là hai loại phán quyết
khác nhau. Chúng không phải. `gateResult()` và `gateEvidence()` chuẩn hoá cả hai về cùng một badge.

`gateEvidence()` **không bịa gì** cho chuỗi trần: cổng đó thật sự không có gì để nói thêm, và
"G3: fail" kèm số bịa còn tệ hơn "G3: fail" trơ trọi. Nó cũng loại `null` thay vì in chữ `null`
vào mặt người đọc.

**② Candidate bị dừng sớm phủ ít episode hơn.** Tính năng dừng sớm (commit trước) thêm
`stopped_early` vào mỗi candidate. Không hiện nó thì hàng đó lặng lẽ đứng trên một mẫu nhỏ hơn cả
bảng. Nay có badge ghi `dừng ở {run}/{planned} vì {gate}` ngay trong hàng — nói ở hàng, vì hàng là
chỗ người ta đọc.

## 4. Những gì trang chi tiết bắt buộc phải mang theo

| khối | vì sao |
|---|---|
| **Mẫu** (đo/xin/N_min/phủ) | đứng trên cùng vì nó định tính mọi con số bên dưới. Run dừng ở 245/300 là phép so hợp lệ và nhỏ hơn — đọc bảng cổng của nó như kết quả 300 episode là một tuyên bố khác |
| **Bảng cổng** | `n_distinct` cạnh số lần chạy: một trăm lần phát lại cùng một episode là một mẫu độc lập |
| **Card** | `null` của độ nhạy render thành **"Chưa đo"**, không phải ô trống — HĐ-12 định nghĩa null là "chưa đo", ô trống đọc như lời trấn an |
| **Điều kiện** | `sensor_noise` hiện rõ: `episode_context_id` không băm biên độ (HĐ-3.1), hai run cùng seed khác σ có id giống hệt nhau. Cảnh báo không-ghim-nhân đi kèm kết quả chứ không nằm trong log không ai mở |
| **Nguồn gốc** | `run_uri` **cùng** `run_checksum`: URI trần không nói được file nó trỏ tới còn đúng là file kết quả này tính ra từ đó (D15) |
| **Nhật ký** | cả hai đầu của mỗi thay đổi — "approved" một mình không nói nó thay thế cái gì. Sắp theo `sequence`, không theo timestamp, và trang **không tự sort lại** |

Card cũng in nguyên câu phạm vi: khuyến nghị chỉ có nghĩa trên **một** deployment (HĐ-1.4).

## 5. Chạm vào đâu

| | |
|---|---|
| `apps/web/src/lib/decisions.ts` | kiểu + hàm gọi API + `noCardReason` / `coverage` / `gateResult` / `gateEvidence` |
| `apps/web/src/app/decisions/page.tsx` | danh sách, lọc theo deployment và theo kết cục |
| `apps/web/src/app/decisions/[id]/page.tsx` | chi tiết, sáu khối trên |
| `apps/web/src/lib/navigation.ts` | mục sidebar, đặt **trước** `/benchmarks` |
| `en.json` / `vi.json` | 84 khoá, hai locale |

Theo đúng khuôn mẫu các trang hiện có: `authFetch` (không phải RTK Query — repo không dùng),
`"use client"`, class CSS sẵn có (`panel`, `stat-grid`, `table-scroll`, `badge ok/err/warn`).
Không thêm dependency nào.

## 6. Test

**40 test mới**, theo convention kiểm ở mức nguồn của các page test hiện có (cả hai trang nằm sau
một effect và một fetch, nên first paint chỉ ra trạng thái loading).

`src/lib/__tests__/decisions.test.ts` (14): ba lý do không-card tách bạch · `interrupted` ưu tiên
trước · report cũ thiếu trường vẫn đọc được · phủ = `undefined` chứ **không** phải 1 khi report
không nói đã xin bao nhiêu · hai hình dạng phán quyết cổng · không bịa bằng chứng · loại `null`.

`src/app/__tests__/decisions-page.test.tsx` (26): bảng cổng đứng trước khuyến nghị · lọc mặc định
là "all" · chip lý do không bao giờ `err` · `null` độ nhạy ra "Chưa đo" · copy chứa "Never a softer
deployment" · tiêu đề không-card không chứa chữ "fail"/"error" · trang không tự sort nhật ký · mọi
khoá i18n có đủ ở cả hai locale.

**Kết quả:** 495 passed. Typecheck sạch.

## 7. Hai test đỏ **có trước** thay đổi này

Xác minh bằng `git stash` rồi chạy lại: y hệt 2 failed / 455 passed khi không có code của tôi.

1. `assistant-page.test.tsx` — `ENOENT: src/app/models/page.tsx`. `navigation.ts` khai mục
   `/models` nhưng **không có trang nào**. Liên kết chết trong sidebar.
2. `dashboard-page.test.tsx` — so `'\system\page.tsx'` với `'/system/page.tsx'`. Lỗi dấu phân cách
   đường dẫn trên Windows, không phải lỗi logic.

Cả hai đều nhỏ. Không sửa vì nằm ngoài phạm vi và không phải của tôi — nói ra để bạn quyết.

## 8. Đợt sau

- **Nút ghi:** review · duyệt/từ chối cấu hình · tải `approved_config.yaml`. Backend đã sẵn cả bốn
  đầu mối; đây là đợt 2 như đã chốt.
- **Chưa có run nào trong kho in-memory của API.** Artifact trên đĩa (`artifacts/runs/`) chưa được
  nạp vào `decision_runs`. Trang sẽ trống cho tới khi có ai chạy `POST /decisions`, hoặc cho tới
  khi có một đường nhập artifact cũ. Đáng cân nhắc, chưa làm.

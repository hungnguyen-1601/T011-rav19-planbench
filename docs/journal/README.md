# Nhật ký làm việc

Dấu vết công việc theo ngày của từng người. **Không dùng để onboard** —
onboard thì đọc [`../README.md`](../README.md).

Dùng thư mục này khi bạn cần trả lời: *"tại sao chỗ này lại được làm như
vậy"*, *"ai đã đo cái này và đo bằng gì"*, *"lần trước thử cách kia thì
sao"*.

| Người | Số file |
|---|---|
| [antongduy/](antongduy/INDEX.md) — Tống Duy An | 278 |
| [hungnguyen-1601/](hungnguyen-1601/) — Phạm Nguyễn Hùng Nguyên | 10 |

---

## Ba loại, ba mục đích

| Folder | Chứa gì | Ghi khi nào |
|---|---|---|
| `reports/` | **Đã thay đổi gì với code** — ship feature, fix bug, refactor, migration | Ngay sau khi xong một phần việc |
| `notes/` | **Đã nhìn thấy gì** — khảo sát, đánh giá, phân tích hiện trạng, research | Sau khi khảo sát xong, kể cả khi không đổi dòng code nào |
| `plans/` | Kế hoạch **chờ duyệt** trước khi làm | Sau khi chốt plan |

Phân biệt: **`reports/` = "tôi đã thay đổi gì", `notes/` = "tôi đã nhìn
thấy gì".** Một bản đánh giá hiện trạng repo vào `notes/`, không vào
`reports/`.

Đường dẫn: `<người>/<loại>/<YYYY-MM-DD>/tongduyan_<mô-tả-không-dấu>.md`
(riêng `plans/` không bắt buộc tiền tố tên).

Hai phiên lập kế hoạch khác nhau ⇒ **hai file plan riêng**, dù cùng ngày.

---

## Cách đọc

**Ngày là dòng thời gian, không phải mức tin cậy.** Một report ngày 08-14
mô tả đúng cái được làm ngày 08-14; nó không nói gì về việc thứ đó còn tồn
tại hôm nay. Nhiều thứ trong đây **đã bị thay** bởi công việc sau.

Khi hai report mâu thuẫn, **cái sau thắng** — và nhiều report ghi rõ ở đầu
file nó thay thế cái nào (ví dụ
`antongduy/reports/2026-08-31/tongduyan_hieu-nang-that-va-tuong-guard-v2.md`
mở đầu bằng *"Thay thế: reports/2026-08-30/… đừng trích"*).

**26 file không phải `.md`** trong `antongduy/notes/` — script eval, JSON
kết quả chấm, mock HTML, YAML bites. Chúng là **bằng chứng đi kèm** một
note, không phải tài liệu đứng riêng.

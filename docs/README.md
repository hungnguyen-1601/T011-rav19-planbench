# Tài liệu PlanBench

> **Bạn là người mới?** Đọc bốn file dưới đây theo thứ tự. Khoảng 40 phút,
> và sau đó bạn trả lời được: sản phẩm phục vụ ai, dựng bằng gì, làm được
> gì, và chỗ nào chưa đỡ được sức nặng.

| # | File | Trả lời câu hỏi |
|---|---|---|
| 1 | [00-product.md](00-product.md) | Sản phẩm là gì, phục vụ **ai**, và cố ý **không** làm gì |
| 2 | [01-architecture.md](01-architecture.md) | Hệ dựng thế nào, LLM đứng ở đâu, bất biến nào không được phá |
| 3 | [02-features.md](02-features.md) | Tính năng nổi bật, cái nào chạy thật, đo bằng gì |
| 4 | [03-gaps.md](03-gaps.md) | Chưa tốt / chưa hoàn thiện, xếp theo mức nghiêm trọng |

Sau đó, tra cứu theo nhu cầu ở [reference/](reference/README.md).

---

## Bản đồ thư mục

```
docs/
  README.md            ← bạn đang ở đây
  00-product.md        sản phẩm và người dùng
  01-architecture.md   kiến trúc hiện hành
  02-features.md       tính năng và trạng thái
  03-gaps.md           nợ và giới hạn

  reference/           tra cứu — API, giới hạn, vận hành, bằng chứng test
  archive/             tài liệu đã bị thay thế, giữ để tra lịch sử
  journal/             nhật ký làm việc theo ngày của từng người
  assets/              ảnh
```

**Ba tầng, ba tuổi thọ khác nhau.** `reference/` là thứ bạn tra khi làm
việc. `archive/` là thứ đã sai nhưng giải thích được vì sao hệ ngày nay
như vậy — đọc để hiểu lịch sử, đừng trích số từ đó. `journal/` là dấu vết
công việc theo ngày, tra được nhưng không dùng để onboard.

---

## Ba nguồn sự thật, xếp theo thứ tự thắng

Khi hai tài liệu mâu thuẫn, cái đứng trên thắng:

| Hạng | Nguồn | Vai |
|---|---|---|
| 1 | [`contracts/CONTRACTS.md`](../contracts/CONTRACTS.md) | **Luật.** Các điều khoản `HĐ-x.y` được trích dẫn khắp code. Sửa code chạm một điều khoản thì đọc điều khoản đó trước |
| 2 | Mã nguồn + test | Tài liệu mô tả code; khi lệch, code đúng |
| 3 | Tài liệu trong thư mục này | Diễn giải cho người đọc |

`contracts/CONTRACTS.md` nằm ngoài `docs/` **có chủ đích** — nó không
phải tài liệu, nó là hợp đồng.

---

## Chỗ khác cũng có tài liệu

| Đường dẫn | Chứa gì |
|---|---|
| [`../README.md`](../README.md) | Giới thiệu sản phẩm đầy đủ nhất, kèm hướng dẫn sử dụng từng trang. Dài 44 KB — bốn file trên là bản rút gọn có định hướng |
| [`../ARCHITECTURE.md`](../ARCHITECTURE.md) | Sơ đồ kiến trúc mermaid, cập nhật 2026-08-23 |
| [`../CLAUDE.md`](../CLAUDE.md) | Luật cho agent AI làm việc trên repo — nhưng mục 1 (hai remote), 2 (nhánh) và 8 (bất biến nghiệp vụ) áp cho **người** ngang với agent. Đọc trước lần push đầu tiên |
| `../contracts/` | Hợp đồng dữ liệu và metric anchor |

---

## Ghi tài liệu mới ở đâu

| Bạn vừa làm gì | Ghi vào |
|---|---|
| Đổi code, ship feature, fix bug | `journal/<tên-bạn>/reports/<YYYY-MM-DD>/` |
| Khảo sát, đánh giá, research — **không** đổi code | `journal/<tên-bạn>/notes/<YYYY-MM-DD>/` |
| Lập kế hoạch chờ duyệt | `journal/<tên-bạn>/plans/<YYYY-MM-DD>/` |
| Đổi một sự thật lâu dài về sản phẩm | sửa thẳng `00`–`03` hoặc file trong `reference/` |

Phân biệt `reports/` với `notes/`: **`reports/` = "tôi đã thay đổi gì",
`notes/` = "tôi đã nhìn thấy gì".**

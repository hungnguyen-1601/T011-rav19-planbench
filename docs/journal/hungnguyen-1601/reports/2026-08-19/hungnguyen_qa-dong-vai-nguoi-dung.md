# QA đóng vai người dùng cuối — và lỗi mà 3.392 test không bắt được

**Ngày:** 2026-08-19 · **Commit vá:** `acad56f`, `106fb39`

---

## 1. Cách làm

Không đọc code tìm lỗi. Đi **trọn hành trình** một người dùng thật sẽ đi,
qua HTTP thật, model thật, kể cả các thao tác vụng.

## 2. Chín chặng

| # | Việc | Kết quả |
|---|---|---|
| U1 | Hỏi "có deployment nào, phép so nào?" | ✅ gọi 2 tool, trả lời đúng |
| U2 | Gửi tin nhắn rỗng | ✅ 422, không gọi model |
| U3 | Hỏi về run không tồn tại | ✅ nói thẳng không tìm thấy, gợi ý run thật |
| U4 | Kẹp PDF vào chat | ✅ `rrtstar+dwa`, 0 trích dẫn bịa, đọc hết file |
| **U5** | **Đăng ký rồi bấm đối chiếu** | 🔴 **404** |
| U6 | Đối chiếu id chưa đăng ký / gửi cả tên lẫn params | ✅ 404 / 422 kèm giải thích |
| U7 | Mở trace episode trượt | ✅ "kẹt trước đích, dao động, xoay tại chỗ" |
| U8 | Đọc rào chắn báo cáo | ✅ 8 rào chắn từ 18 luật |
| U9 | Dựng plugin lúc Gemini hết quota | ✅ từ chối kèm nguyên văn lỗi, không bịa |

## 3. U5 — lỗi danh tính, và vì sao test không bắt được

Panel đọc paper in ra `candidate_id: 5450df18669c`. Form đăng ký **chỉ
nhận config có tên** (`dwa_coarse`…). Nên id đó là **danh tính không ai
tạo nổi**, và nút đối chiếu 404 với người làm đúng mọi bước.

**25 test đơn vị của tính năng đó vẫn xanh suốt.** Chúng tự dựng phương
án đúng rồi đưa cho module; route thì đọc sai. Module vô tội, bộ test vô
tội, tính năng hỏng.

Đây là lớp lỗi mà test đơn vị **về nguyên tắc** không bắt được: nó nằm ở
đường nối giữa hai thành phần, mỗi thành phần đều đúng.

### Cách vá

Đăng ký nhận thêm `params` tường minh, đi qua **đúng một đường băm** với
panel đọc paper — server vẫn tự tính id, HĐ-1.3 nguyên vẹn.

Gửi **cả** tên config **lẫn** params → 422 nói rõ:

> *"give either a named local_config or explicit params, not both; with
> both, which one defines the candidate would be this function's private
> decision"*

Một quyết định riêng tư về danh tính là một lỗi danh tính chờ được nộp.

### Kiểm chứng vòng khép kín

```
1. Paper đọc ra       : id 5450df18669c
2. Đăng ký bằng params: HTTP 201, id 5450df18669c
3. Hai id trùng khớp  : True
4. Đối chiếu          : HTTP 200 — 18 tham số: 4 khớp, 14 paper không nêu
   lời khuyên          : RP_DEFAULT_TAKEN_FOR_SILENCE
```

Phát hiện cuối cùng chính là thứ đáng giá nhất: **14 tham số bài báo
không hề nêu** mà hệ đã tự điền mặc định — lý do thường gặp nhất khiến
một bản tái lập paper lệch số.

## 4. Bốn test HTTP ghim lại

Vì test đơn vị không bắt được lớp lỗi này: id round-trip · gửi cả hai →
422 · tham số lạ → 422 · đường đăng ký cũ không đổi.

## 5. Hai lỗ hổng giao diện lấp cùng đợt

`106fb39`: hai tính năng tồn tại như route **không ai bấm được** — đối
chiếu paper và đọc trace. Giờ: đọc paper ra id đăng ký được thì hiện nút
đối chiếu; mở trace trên trang run thì tải kèm phần review.

## 6. Điều QA này không kiểm được

Tôi test bằng `curl` và đọc mã nguồn, **không mở trình duyệt bấm thật**.
Bố cục, nút bị che, chữ tràn, thao tác trên màn hình nhỏ — không thấy
được. Cần một người chưa từng dùng thử 10 phút không hướng dẫn; chỗ họ
vấp là câu trả lời thật.

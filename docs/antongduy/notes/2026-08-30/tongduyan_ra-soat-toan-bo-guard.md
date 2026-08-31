# Rà soát toàn bộ guard — bốn lỗi tìm được, hai đã sửa

**Ngày:** 2026-08-30 · **Chi phí: $0**, không gọi model lần nào.

Cách rà: **thử thật từng luật bằng câu cụ thể**, không đọc code rồi
đoán. Mọi đề xuất sửa đều đo trên **277 câu đã sống sót ở bốn arm** đã
ghi trước khi viết thành code.

---

## Lỗi 1 — tên có chữ số bị đọc thành con số · ĐÃ SỬA

`quantities_in`, `guard.py`. Rule 2 chiếm **52% tổng số chặn** và có mặt
ở **13/15 lượt im oan**.

| token | trước | sau |
|---|---|---|
| `C1` | qua | qua |
| `C1's` | **CHẶN** | qua |
| `C1/C5` | **CHẶN** | qua |
| `C1-side` | **CHẶN** | qua |
| `C1-2.05` | chặn | chặn |
| `30-episode` · `0.74m` · `2x` · `twice` | chặn | chặn |

Docstring của chính hàm đó viết: *"A token that is one of them is a
name, **whatever digits it contains**."* Phép kiểm so token nguyên vẹn
nên chỉ nhận `C1`; mọi biến cách rơi xuống nhánh "có chữ số ⇒ là số".

**Sở hữu cách chính là cách người ta viết một so sánh giữa hai bên có
tên.** Sửa bằng **tách chứ không cắt**, nên số thật gắn vào tên vẫn bị
chặn.

## Lỗi 2 — một trạng từ là đủ để lách rule 9 · ĐÃ SỬA

`contradicts_verdict`. Đây là **hard constraint duy nhất có trần 0** —
việc của nó là chặn câu trao episode cho bên platform không chọn.

Viết là `f"{label} {word}" in sentence` — nhãn và lời khẳng định phải
dính liền:

| câu | trước | sau |
|---|---|---|
| `C5 wins this episode` | bắt | bắt |
| `C5 **clearly** wins this episode` | **LỌT** | bắt |
| `C5 **ultimately** won` | **LỌT** | bắt |
| `C5 is **clearly** faster` | **LỌT** | bắt |

Khoảng đệm cho phép là **3 từ**, và 3 là **số đo được**: chạy trên 277
câu đã sống sót ở cả bốn arm, khoảng đệm 0/1/2/3 đều bắt **đúng 0 câu**.
Nới là miễn phí trên dữ liệu đang có.

Cụm nhiều từ (`is faster`) cần khoảng đệm **bên trong** cụm nữa — bản
đầu của tôi quên, test bắt được ngay.

## Lỗi 3 — refusal không ghi lại nó phản đối cái gì · ĐÃ SỬA

Artifact chỉ lưu `[item.rule for item in outcome.blocked]`, **vứt mất
`detail`**. Hệ quả: việc rẻ nhất còn lại — đọc 21 lượt viết lại vẫn hỏng
— **bất khả thi**, vì câu model viết đã mất, chỉ còn chữ
`quantity_in_statement`.

Thêm `blocked_detail` (rule + hypothesis_id + detail), giữ `blocked` cũ
bên cạnh để artifact đã ghi vẫn so được. Và tách
`blocked_first_turn` / `blocked_second_turn`, vì `blocked` của lượt có
reword là **hai lượt nối vào nhau** — dù có detail cũng không biết lượt
hai lặp lỗi cũ hay tạo lỗi mới.

## Lỗi 4 — đường tiếng Việt không dùng được · CHƯA SỬA, LATENT

`NUMBER_WORDS` chứa từ số tiếng Việt có dấu. Ba từ trong đó là từ
thường dùng:

| câu | bị chặn vì |
|---|---|
| `C5 **không** bị kẹt lại` | `không` — **từ phủ định** |
| `C1 **không** có replan nào` | `không` |
| `trong **năm** nay` | `năm` — year |
| `**một** phần đường bị chặn` | `một` — mạo từ |

**Mọi câu phủ định tiếng Việt đều bị chặn.** Hôm nay vô hại vì analyst
viết tiếng Anh, nhưng **đừng bật đường tiếng Việt trước khi sửa** —
platform có `en.json`/`vi.json` nên chuyện đó có thể xảy ra.

Chưa sửa vì không có output tiếng Việt nào để đo, và sửa mù là đúng cái
lỗi vừa mắc ở luật 13.

Tiếng Anh cũng có một ca nhỏ: `on the **one** hand` bị chặn. Hiếm, để
nguyên.

---

## Đã kiểm và SẠCH

| chỗ | kiểm gì | kết quả |
|---|---|---|
| `magnitudes.render/unresolvable` | bool, chuỗi, số 0, ref thiếu, ngoặc lạc, nhiều placeholder | đúng cả 7 ca. Số `0` render được, `True` và chuỗi bị từ chối đúng |
| `_compares_without_support` (luật 13) | nhãn có ký tự đặc biệt (`astar+dwa`, `C.1`, `C-1`) | `\b` khớp đúng |
| `_detector_silent` | tách ref `obs:stuck_cluster:C1@ep` | lấy đúng tên detector |
| `identifiers` của view | có thật chứa nhãn candidate không | có: `C1`–`C8` + episode id + cluster id |
| `episode_floor` vs `blocked_claim_types` | luật 11 có làm câm floor không | không — floor không đi qua guard, và vòng diagnosis không kiểm `blocked` |

---

## Còn chưa kiểm được, và vì sao

- **21 lượt viết lại vẫn hỏng** — cần `blocked_detail`, chỉ có từ lần
  chạy sau. Đây chính là lý do lỗi 3 đáng sửa.
- **`contract_terms_met` cấp `subject_match` khi không fact nào mang
  subject** — đọc code thì thấy là cố ý (comment nói rõ rule 6 đã lo
  phần cite sai component). Không có ca thật để đo, để nguyên.
- **`_WINNING_WORDS` thiếu từ** — `prevailed`, `edged out`, `outran`,
  `performed better`. Thêm là đoán; chưa câu nào trong 277 câu dùng
  chúng.

## Cổng

81 test pass trên các file liên quan; suite backend đang chạy
(`guard.py` dùng chung với run-scope nên phải chạy rộng).

Cắn: bỏ bản sửa tên ⇒ 3 đỏ · nới quá tay ⇒ 3 đỏ · rule 9 thiếu khoảng
đệm trong cụm ⇒ 1 đỏ (bắt được ngay lúc viết).

# Pitch deck v2 — 10 slide dựng theo bộ slide pitching

**Ngày:** 2026-08-31
**Phạm vi:** thêm `presentation/deck-v2/` (1 file HTML nguồn, 10 PNG 2×, 1 PPTX).
Không sửa `presentation/pitch_deck.pptx`, không đụng code sản phẩm.

---

## 1. Bối cảnh

Việc trước đó (`tongduyan_thumbnail-theo-kien-thuc-pitching.md`) dồn toàn bộ
thông điệp vào **một khung ảnh**. An nói rõ đó không phải kỳ vọng: cần một
**bài trình bày 8–10 slide** bao quát các ý. Bản một-ảnh giữ nguyên và trở
thành nội dung slide 01 của deck này.

Nguồn kiến thức là bộ slide *The Pitch: Product Narrative & Investor Demo*
(ThS. Lê Anh Tiến). Link Google Docs không mở được — `export/pptx` trả **401**
và Drive connector thiếu scope `drive.readonly`; An chụp 15 màn hình đặt ở
`presentation/slide pitching/`, đọc từ đó.

## 2. Mười slide, và điều khoản nào chi phối slide nào

| # | Slide | Nhịp | Điều khoản áp dụng |
|---|---|---|---|
| 01 | Hook — 10.000–100.000 USD mỗi giờ dừng chuyền | Hook | "Mở đầu bằng vấn đề khách hàng", Hook Engine, số liệu phải có nguồn |
| 02 | Ai đau, đau ở đâu, hậu quả | User + Pain | Product Narrative nhịp 1–2; lăng kính lớp PAIN |
| 03 | Ba cách đang làm và chỗ hỏng | Old way | Product Narrative nhịp 3 |
| 04 | One-liner + bốn trụ | New way | Công thức định vị, "Outcome first · Technology second" |
| 05 | Năm bước + sáu cổng | Product | Nhịp 5; giao thức nói về AI (công nghệ đứng sau kết quả) |
| 06 | Kịch bản demo bốn nhịp | Demo | "Demo là câu chuyện, không phải walkthrough"; Kịch bản Investor Demo |
| 07 | Bằng chứng, và chỗ chưa có bằng chứng | Proof | "Proof always"; lăng kính lớp TRACTION |
| 08 | Vì sao khó copy | Moat | Lăng kính lớp MOAT |
| 09 | Ai trả tiền | Business model | Lỗi chết người #4 "Không rõ ai trả tiền" |
| 10 | Đội ngũ · Roadmap · **Ask** | Team + Ask | Lỗi #5 "Thiếu Ask rõ ràng"; công thức Ask ba ô |

Ngân sách thời gian của bộ slide (Hook 10% · Problem 15% · Solution 15% ·
Demo 20% · Biz 20% · Vision & Ask 20%) ánh xạ ra: slide 01 · 02–03 · 04–05 ·
06 · 07–09 · 10.

**Hai thứ trong Sequoia 12 bị bỏ có chủ ý.** *Competition* gộp vào slide 08
(moat), và *Financials* bỏ hẳn — chưa có doanh thu thì một bảng tài chính chỉ
là số bịa. *Market sizing* không có slide riêng vì chưa có nguồn đã xác thực;
xem mục 4.

## 3. Số liệu — cái nào đã kiểm, kiểm ở đâu

Bộ slide pitching yêu cầu *"nếu dùng số liệu cụ thể, phải luôn có nguồn xác
thực"*. Mỗi số trên slide 07 đều mang cột "đo ở đâu". Kiểm lại như sau:

| Số | Kiểm bằng gì | Kết quả |
|---|---|---|
| **4.919** hàm test | `grep -rhoE '^\s*(async )?def test_' --include=*.py tests` | đếm được, 2026-08-31 |
| **6/6** cổng, không hằng số | `packages/decision/planbench_decision/gates.py` docstring §"All six gates always run" + "Every threshold is read from the profile" | khớp |
| **0/90** vi phạm cổng cứng | `reports/2026-08-31/tongduyan_hieu-nang-that-va-tuong-guard-v2.md` dòng 86, 189 | khớp |
| **3/90** lượt sai | cùng file, dòng 83 | khớp |
| **0,11 → 0,56** explains | cùng file, bảng "tiến trình qua bốn arm" (10/18 theo đa số ≥2/3) | khớp |
| **v0.1.16** | `apps/desktop/planbench_desktop/VERSION` | khớp |
| **26%** tỉ lệ va chạm với 0/10 lượt | `gates.py` dòng ~195, rule of three 95% | khớp |

**Số cũ đã bị loại.** `pitch_deck.pptx` slide 7 ghi *"3.290+ test"* — thấp hơn
thực tế; deck v2 dùng 4.919. Cũng slide đó ghi *"CPU pinning giảm 59.3 ms
xuống 16.1 ms"* — **không tìm thấy hai con số này ở đâu trong repo**
(`grep "16.1\|59.3"` không ra), nên không đưa vào deck v2. Nếu ai đó đo thật
thì phải chỉ ra chỗ đo trước khi in lại.

**Số lấy từ deck cũ, chưa tự kiểm nguồn gốc:** 10.000–100.000 USD/giờ
(Siemens, Aberdeen) và >70% khủng hoảng tái lập (Nature, Baker 2016). Hai số
này đã có tên nguồn trong `pitch_deck.pptx` slide 2 nhưng **tôi chưa mở lại
báo cáo gốc để đối chiếu**. Đây là hai số duy nhất trên deck v2 không tự kiểm
được — nếu giám khảo hỏi thì phải trả lời được.

## 4. Chỗ deck cố tình để trống

**Không có slide market sizing.** Không có số quy mô thị trường AMR/AGV đã xác
thực trong tay, và bịa một con số TAM là đúng thứ lăng kính 7 lớp dùng để loại
người pitch. Slide 09 thay bằng câu hỏi *ai trả tiền, họ mua cái gì*, và một
khối cam ghi thẳng chỗ trống: chưa có số thị trường, chưa phỏng vấn khách nào.

**Không có traction.** Slide 07 kết bằng dòng: chưa có người dùng trả tiền,
chưa triển khai kho thật, và con số 10.000–100.000 USD là chi phí ngành chứ
không phải doanh thu. Đây là ràng buộc của repo (`bằng chứng không được nghe
mạnh hơn dữ liệu cho phép`) trùng với yêu cầu của bộ slide pitching.

**Ask là ask thật, không phải xin vốn.** Slide 10: *"cần một nhà kho đang vận
hành AMR cho mượn bản đồ thật và hai buổi làm việc, để chạy PlanBench trên
deployment thật, trong bốn tuần tới"* — đúng công thức
`[nguồn lực] · [mục tiêu] · [thời gian]`, và đúng thứ duy nhất nhóm không tự
tạo ra được trong phòng.

**Giữ tông tối, không đổi sang nền kem như bộ slide pitching.** Deck sẽ đứng
cạnh ảnh chụp UI thật (nền tối theo `apps/web/src/app/globals.css`). Bộ slide
dạy cấu trúc thông điệp, không dạy bảng màu. Palette, hình học map
(`maps/warehouse_a.pgm`) và quy ước màu ứng viên giữ nguyên từ thumbnail v1.

## 5. File và cách dựng lại

| File | Là gì |
|---|---|
| `presentation/deck-v2/planbench-deck-v2.html` | **Nguồn.** Mười `<section class="slide">`, mỗi cái 1280 × 720 |
| `presentation/deck-v2/slide-01..10.png` | Bản xuất 2× (2560 × 1440) |
| `presentation/deck-v2/planbench-deck-v2.pptx` | Mười slide 16:9, mỗi slide một ảnh nền |

Mở HTML thẳng trong trình duyệt thì cuộn qua cả mười slide. Thêm `#s4` vào
URL thì chỉ hiện slide 4 — đó là cơ chế dùng để chụp từng tấm:

```powershell
foreach ($i in 1..10) {
  $n = "{0:d2}" -f $i
  & "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
    --headless=new --disable-gpu --no-sandbox --user-data-dir=<thư mục tạm> `
    --hide-scrollbars --force-device-scale-factor=2 --window-size=1280,720 `
    --screenshot="slide-$n.png" --virtual-time-budget=7000 `
    "file:///E:/VinAI/RoboMind_project/P-011/presentation/deck-v2/planbench-deck-v2.html#s$i"
}
```

PPTX ghép từ mười PNG bằng `python-pptx` (khổ 12192000 × 6858000 EMU = 16:9).
**Đã cài `python-pptx` 1.0.2 vào môi trường Python mặc định** để làm việc này —
gỡ bằng `pip uninstall python-pptx` nếu không muốn giữ.

## 6. Kiểm chứng

Render ba lượt, soi từng tấm PNG:

- Lượt 1: nội dung dồn hết lên nửa trên, nửa dưới trống trơn ở cả mười slide.
  Sửa bằng `.slide > *:nth-last-child(2) { align-self: center; }` — canh khối
  thân giữa header và footer — kèm tăng cỡ chữ thân (card 14→15 px, tiêu đề
  card 18→20 px, bảng bằng chứng 14→15 px) để khối được canh giữa có sức nặng.
- Lượt 2: slide 09 có khối "trung thực về chỗ trống" là phần tử áp chót nên
  *nó* bị canh giữa thay vì ba thẻ; ba thẻ dạt lên trên còn khối cam rơi xuống
  đáy. Sửa bằng cách bọc cả hai vào một `div`.
- Lượt 3: nhãn vai của team lead xuống hai dòng làm bốn thẻ lệch nhau; rút
  gọn còn `Team lead · AI · Simulation`.

Bản hiện tại: cả mười slide vừa đúng 1280 × 720, không phần tử nào bị cắt,
không tràn ngang.

**Chưa kiểm:** chưa mở PPTX trong PowerPoint để xác nhận ảnh không bị co méo
khi trình chiếu toàn màn hình. Ảnh 2560 × 1440 và khung slide đều 16:9 nên về
lý thuyết khớp, nhưng đây là khẳng định suy ra chứ không phải đã nhìn thấy.

## 7. Chưa làm

- Chưa thay `presentation/pitch_deck.pptx` — deck v2 là file riêng, chờ An
  quyết có thay không.
- Chưa sửa hai số sai/không truy được trong deck cũ (3.290+ test; 59,3 → 16,1 ms).
- Chưa đối chiếu báo cáo Siemens / Aberdeen / Nature gốc.
- Chưa có ảnh chụp UI thật chèn vào slide 05 và 06 — hiện dùng bản vẽ map SVG.
  Nếu An muốn thì thay bằng screenshot `/simulate` và `/decisions`.
- Chưa commit (theo quy ước: An tự commit). `presentation/` **không** nằm
  trong danh sách cấm commit của `CLAUDE.md` — chỉ `presentation/thumbnail/`
  bị cấm — nên `deck-v2/` commit được nếu An muốn; PNG 2× khá nặng (~0,5 MB
  mỗi tấm, PPTX 5,5 MB), cân nhắc chỉ commit file HTML nguồn.

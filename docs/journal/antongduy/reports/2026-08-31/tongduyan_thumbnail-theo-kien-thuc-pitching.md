# Thumbnail v2 — dựng lại theo bộ slide pitching

**Ngày:** 2026-08-31
**Phạm vi:** thêm `presentation/thumbnail/planbench-hook-v2.html` + hai bản PNG.
Không sửa bản v1, không đụng code sản phẩm.

---

## 1. Nguồn kiến thức

Slide *The Pitch: Product Narrative & Investor Demo* (ThS. Lê Anh Tiến) không
mở được bằng link — `export/pptx` trả **401** vì bản trình bày không public, và
Google Drive connector đang thiếu scope `drive.readonly`. An chụp 15 màn hình
và để ở `presentation/slide pitching/`; đọc từ đó.

Những điều khoản trong bộ slide có ràng buộc trực tiếp lên một thumbnail:

| Slide | Điều khoản | Ràng buộc lên khung ảnh |
|---|---|---|
| 5 lỗi chết người | "Mở đầu bằng công nghệ" là **lỗi**; sửa = mở đầu bằng vấn đề khách hàng | Thứ đọc đầu tiên không được là map hay tên thuật toán |
| Giao thức nói về AI | Outcome first → Technology second → **Proof always** | Ba tầng theo đúng thứ tự, từ trên xuống |
| Hook Engine | PAIN / BEHAVIOR / SHIFT hook, và *"nếu dùng số liệu cụ thể, phải luôn có nguồn xác thực"* | Số nào in ra cũng phải có tên nguồn nằm cạnh |
| Công thức định vị | "Chúng tôi giúp [KH] đạt [KQ] bằng [cách khác biệt], thay vì [cách cũ]" | Phải có đúng một câu này, và bốn ô phải nhìn ra được |
| Pre-flight checklist | "Hiểu sản phẩm làm gì trong 30 giây đầu không?" | Với ảnh tĩnh thì ngân sách là ~3 giây, không phải 30 |
| Lăng kính 7 lớp | PAIN đứng ngay sau MARKET, trước PRODUCT | Nỗi đau phải xuất hiện trước cơ chế |

## 2. Bản v1 sai ở đâu

Đọc `planbench-thumbnail-1280x720.png` theo đúng checklist trên:

- **Toàn bộ khung là công nghệ.** Dải trên cùng là `warehouse_a · 40 × 25 m ·
  0.05 m/cell · occupancy grid`; rail phải là G1–G6 và ba thanh objective.
  Đúng cái lỗi số 1 trong bảng "5 lỗi chết người".
- **Không có nỗi đau.** Không một chữ nào nói hậu quả của việc chọn sai. Người
  xem hiểu *hệ thống làm gì* nhưng không hiểu *vì sao phải quan tâm*.
- **Không có one-liner.** Tagline `TASK-AWARE NAVIGATION PLANNER SELECTION` là
  jargon thuần, rơi thẳng vào ô "Bỏ qua Jargon".
- **Không có ai trong hình.** Thiếu ô [KHÁCH HÀNG MỤC TIÊU]; không ai biết
  sản phẩm này bán cho ai.
- **Strapline là cơ chế, không phải kết quả.** *Same task → multiple candidates
  → one recommended configuration* mô tả đường ống, không mô tả cái người dùng
  nhận được.
- Ba thanh objective **không nhãn số** vốn được cố ý làm vậy (README cấm để kết
  luận nghe mạnh hơn dữ liệu) — nhưng hệ quả là chúng không chứng minh gì cả.
  Chiếm chỗ mà không phải proof.

Cái v1 làm đúng và được giữ nguyên: hình học map đọc thẳng từ
`maps/warehouse_a.pgm`, palette lấy từ `apps/web/src/app/globals.css`, chỉ một
màu bão hoà cho ứng viên thắng, xanh lá chỉ dành cho cổng, IBM Plex.

## 3. Bản v2 bố trí lại thế nào

Bốn dải, đọc từ trên xuống đúng thứ tự *outcome → technology → proof*:

1. **Dải meta** (11 px) — VinUni AI20K · Track 3 · Team T011, và deployment.
   Bị đẩy xuống cỡ chữ nhỏ nhất khung: nó là ngữ cảnh, không phải thông điệp.
2. **PAIN HOOK** (33 px, chữ lớn nhất khung) — *"Một giờ dừng chuyền vì robot
   kho đi sai đường tốn 10.000–100.000 USD."* kèm một câu phụ nêu cách cũ:
   cấu hình vẫn được chọn bằng bảng số liệu của người bán, đo trên bản đồ của
   họ. Hai nguồn (Siemens, Aberdeen) in ngay bên phải, cùng dòng baseline.
3. **Sân giữa** — map giữ nguyên bên trái (đây là *khoảnh khắc Aha*: ba đường,
   một đường sáng có huy hiệu check); bên phải là wordmark, **one-liner theo
   đúng công thức**, và dải proof.
4. **Strapline** — câu cơ chế cũ, hạ xuống 12 px ở đáy. Vẫn còn, nhưng không
   còn là thông điệp chính.

**One-liner đánh dấu bốn ô của công thức bằng nền màu**, ba ô xanh (khách hàng
· kết quả · cách khác biệt) và một ô cam (cách cũ) — giống hệt cách bộ slide
tô ô ở phần `OUTPUT_EXAMPLE`. Làm vậy để nhìn ra *hình dạng* của câu, không chỉ
nội dung: lần sau đổi định vị thì biết phải thay đúng bốn chỗ nào.

**Dải proof thay cho ba thanh objective.** Ba số, mỗi số có một dòng nói nó từ
đâu ra:

| Số | Nói gì | Xuất xứ |
|---|---|---|
| 6/6 | cổng khả thi chạy trên mọi ứng viên, không ngoại lệ | hợp đồng gate table |
| 0 | con số do LLM sinh ra — LLM chỉ đọc và chất vấn | nguyên tắc Core-first |
| 4.900+ | hàm test tự động trong `tests/` | đếm 2026-08-31 |

Con số 4.900+ là **đếm thật**: `grep -rhoE '^\s*(async )?def test_' --include=*.py tests`
ra 4919 hàm. Deck `pitch_deck.pptx` đang ghi "3.290+" — số đó đã cũ. Đây là số
hàm test khai báo trong nguồn, không phải số case pytest thu thập được
(`parametrize` làm số thu thập cao hơn); nếu muốn in con số collected thì phải
chạy `pytest --collect-only -q` rồi lấy dòng cuối, chưa làm.

Con số 10.000–100.000 USD lấy nguyên từ slide 2 của chính `pitch_deck.pptx`,
nơi nó đã dẫn Siemens và Aberdeen. **Chưa tự mở lại hai báo cáo gốc để đối
chiếu** — nếu An muốn chắc thì phải kiểm trước khi trình bày, vì bộ slide
pitching nói rõ số liệu cụ thể phải có nguồn xác thực.

## 4. Những cái cố tình không làm

**Không đổi sang nền kem xanh lam như bộ slide pitching.** Thumbnail sẽ đứng
cạnh ảnh chụp UI thật của app, vốn là nền tối theo `globals.css`. Đổi tông làm
khung ảnh rời khỏi sản phẩm. Bộ slide dạy *cấu trúc thông điệp*, không dạy bảng
màu; áp cấu trúc, giữ tông.

**Không thêm câu Ask.** Checklist đòi "một câu Ask cụ thể ở cuối" — nhưng đó là
việc của slide cuối, không phải khung đầu. Nhồi Ask vào đây thì đọc như banner
quảng cáo.

**Không bịa traction.** Lăng kính 7 lớp có ô TRACTION ("đã có tín hiệu thật từ
thị trường chưa"). Dự án chưa có người dùng thật, nên ô đó bỏ trống thay vì
điền số nghe cho hay.

**Không đụng `planbench-thumbnail.html` bản v1.** Hai bản nằm cạnh nhau để so.

## 5. File và cách render lại

| File | Là gì |
|---|---|
| `presentation/thumbnail/planbench-hook-v2.html` | Nguồn |
| `presentation/thumbnail/planbench-hook-v2-1280x720.png` | Bản 1× |
| `presentation/thumbnail/planbench-hook-v2-2560x1440.png` | Bản 2× |

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  --headless=new --disable-gpu --no-sandbox `
  --user-data-dir=<thư mục tạm> --hide-scrollbars `
  --force-device-scale-factor=1 --window-size=1280,720 `
  --screenshot="<đường dẫn>.png" --virtual-time-budget=9000 `
  "file:///E:/VinAI/RoboMind_project/P-011/presentation/thumbnail/planbench-hook-v2.html"
```

Đổi `--force-device-scale-factor` thành `2` để ra bản 2560 × 1440.

## 6. Kiểm chứng

Render và soi bản PNG ba lượt; hai lượt đầu tràn khung (dải legend và
strapline bị cắt ở đáy, và số `10.000 – 100.000 USD` bị ngắt dòng giữa con số)
nên đã thu cỡ chữ, hạ chiều cao map xuống 600 × 375 giữ đúng tỉ lệ 1,6 của
`warehouse_a`, và ép `white-space: nowrap` lên khoảng giá trị. Bản hiện tại vừa
đúng 1280 × 720, không phần tử nào bị cắt.

**Chưa kiểm ở cỡ thu nhỏ.** v1 đã được soi ở 480 / 280 / 160 px; v2 thì chưa,
và đây là chỗ đáng nghi nhất: câu hook 33 px đọc được ở 280 px, nhưng one-liner
17 px và dải proof gần như chắc chắn thành vệt xám. Nếu v2 phải dùng làm
thumbnail thật (chứ không phải slide mở đầu) thì cần một biến thể rút gọn —
chỉ hook + wordmark + map, bỏ one-liner và proof.

## 7. Chưa làm

- Chưa thay v2 vào `README.md` hay `presentation/pitch_deck.pptx` — chờ An duyệt.
- Chưa làm biến thể thumbnail rút gọn nói ở mục 6.
- Chưa đối chiếu lại báo cáo Siemens/Aberdeen gốc.
- Chưa sửa số "3.290+" đã cũ trong `pitch_deck.pptx` slide 7.
- Chưa commit (theo quy ước: An tự commit). Lưu ý `presentation/thumbnail/`
  nằm trong danh sách không commit của `CLAUDE.md`; chỉ report này vào git.

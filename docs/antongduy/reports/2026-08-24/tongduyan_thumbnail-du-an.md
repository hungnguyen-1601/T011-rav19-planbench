# Thumbnail dự án PlanBench

**Ngày:** 2026-08-24
**Phạm vi:** thêm mới thư mục `presentation/thumbnail/` (3 file). Không đụng
vào code sản phẩm.

---

## 1. Yêu cầu

Một thumbnail truyền đạt ngay ba ý: *robot navigation* · *nhiều candidate
planner* · *hệ thống chọn ra phương án phù hợp nhất*. Phong cách technical /
robotics dashboard, nền tối, không neon/hologram/robot hình người. Thông điệp
mạnh nhất phải là **Same Task → Multiple Navigation Candidates → One
Recommended Configuration**.

## 2. Đã làm gì

| File | Là gì |
|---|---|
| `presentation/thumbnail/planbench-thumbnail.html` | Nguồn. Toàn bộ khung là HTML + SVG sống, sửa rồi render lại được |
| `presentation/thumbnail/planbench-thumbnail-1280x720.png` | Bản xuất 1× — cỡ card chuẩn cho repo/social |
| `presentation/thumbnail/planbench-thumbnail-2560x1440.png` | Bản xuất 2× — cho slide và in |

Bố cục 1280 × 720, chia ba dải:

- **Dải meta trên cùng** — deployment `warehouse_a`, 40 × 25 m, 0.05 m/cell,
  mission Dock A → Rack 12, differential drive.
- **Sân giữa** — bên trái là map occupancy grid 764 × 478 với ba đường đi;
  dưới map là ba chip legend. Bên phải là rail 400 px: wordmark **PlanBench**
  74 px, subtitle một dòng, ba thanh objective, dải cổng G1–G6, và thẻ
  *Recommended configuration*.
- **Strapline dưới cùng** — đúng câu thông điệp đã yêu cầu, phân đoạn cuối
  tô màu accent.

## 3. Những quyết định đáng ghi lại

**Map là map thật, không phải hình vẽ.** Hình học racking đọc thẳng từ
`maps/warehouse_a.pgm` (800 × 500 cell, 0.05 m/cell): hai băng kệ, mỗi băng
bốn khối, hành lang biên và hành lang giữa đúng vị trí. Khe cross-aisle hẹp
mà đường RRT* luồn qua là khe **có thật** trong map đó. Việc này quan trọng
vì thumbnail sẽ đứng cạnh ảnh chụp UI thật — hình học lệch là lộ ngay.

**Palette lấy từ `apps/web/src/app/globals.css`, không tự bịa.** Ứng viên
thắng dùng `--accent #4c9aff`, RRT* dùng `--purple`, PPO dùng `--orange`,
start `--teal`, goal `--goal` (đúng màu app đang dùng cho goal), cổng pass
dùng `--ok`. Thumbnail vì thế cùng một hệ màu với sản phẩm.

**Chỉ một màu bão hoà hoàn toàn.** Đường thắng vẽ liền, 4.4 px, có glow, kèm
huy hiệu check **nằm trên chính quỹ đạo** — đó là thứ phân biệt "Planner
Selector" với "benchmark". Hai đường còn lại vẽ nét đứt, độ mờ ~0.62: vẫn
đọc được, nhưng rõ ràng không được chọn. Bị loại chứ không bị xoá.

**Xanh lá chỉ dùng cho cổng.** G1–G6 là chỗ duy nhất có màu xanh lá, nên
pass/fail không bao giờ tranh chấp ngữ nghĩa với màu của các candidate.

**Không tuyên bố con số nào.** Ba thanh objective (Safety / Efficiency /
Cost) không có nhãn số; thẻ khuyến nghị ghi *"Paired episodes · 95% CI ·
replayable trace"* — mô tả **phương pháp**, không phải kết quả. Cố ý: README
cấm để kết luận nghe mạnh hơn dữ liệu, và một thumbnail in ra con số bịa là
đúng cái lỗi đó. Vì cùng lý do, góc phải strapline giữ chữ *Simulation only*.

**Chữ dùng IBM Plex** (Sans cho wordmark, Mono cho mọi nhãn/số đo). Mặt chữ
kỹ thuật, giữ khung ảnh đọc như thiết bị đo chứ không như trang bán hàng —
tránh đúng cái cảm giác "AI/LLM product" mà yêu cầu muốn né.

**Vật cản động xuất hiện đúng hai lần**, dạng vòng tròn xám kèm mũi tên
hướng. Đủ để nói thế giới có chuyển động, không biến map thành giao thông.

## 4. Render lại thế nào

Không có Chrome/Playwright trong máy; dùng Edge headless có sẵn:

```
"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
  --headless=new --disable-gpu --no-sandbox \
  --user-data-dir=<thư mục tạm> --hide-scrollbars \
  --force-device-scale-factor=1 --window-size=1280,720 \
  --screenshot="<đường dẫn>.png" --virtual-time-budget=9000 \
  "file:///E:/VinAI/RoboMind_project/P-011/presentation/thumbnail/planbench-thumbnail.html"
```

Đổi `--force-device-scale-factor` thành `2` để ra bản 2560 × 1440. Cần mạng
lần đầu để tải IBM Plex từ Google Fonts; mất mạng thì rơi về Segoe UI và
khung vẫn đúng, chỉ khác mặt chữ.

## 5. Kiểm chứng

Đã render và soi bản PNG ở cả cỡ đầy đủ lẫn thu nhỏ (480 / 280 / 160 px).
Ở 280 px vẫn đọc được: khối map, một đường sáng nổi trên hai đường mờ, huy
hiệu check, và chữ **PlanBench**. Trang xem kèm phân tích palette đã publish
làm artifact.

## 6. Chưa làm

- Chưa thay thumbnail vào README hay `presentation/pitch_deck.pptx` — chờ An
  duyệt bản này trước.
- Chưa làm biến thể tỉ lệ khác (1:1 cho avatar, 1200 × 630 cho OG image).
  Nếu cần thì sửa `.frame` width/height trong file HTML rồi render lại.
- Chưa commit (theo quy ước: An tự commit).

# Phase 1 — thấy được cái đang khai, không cần bấm Preview

> Plan: `docs/antongduy/plans/2026-08-16/tuong-tac-map-va-refactor-layout-deployment.md` (v4, Phase 1).
> Ngày làm: 2026-08-16. Nhánh: `tongduyan_plannerselector`. **Chưa commit.**
> Phase 0 An đã commit. Vẫn **không chạy full suite** — dồn về phase cuối.

## Vấn đề đóng lại

Trước đợt này canvas chỉ vẽ traffic **sau** một vòng tới
`POST /scenarios/preview`: bấm Preview thì đĩa vàng hiện ra ở chỗ
backend nói vật cản đang đứng tại *t*. Đặt ba waypoint trước đó **không
vẽ gì cả** — khai lộ trình là click vào bản đồ trống rồi bấm Preview để
xem mình vừa viết ra cái gì.

## `lib/trafficOverlay.ts` — tài liệu thành hình học

`overlayOf(obstacles, selectedIndex)` trả mỗi obstacle thành một
`OverlayShape`: `path` (các điểm theo đúng thứ tự đi), `handles` (điểm
cầm được, waypoint có nhãn số thứ tự), `home` (điểm đầu — nơi vẽ vòng
bán kính, nhãn tên, và là target chọn `body` ở Phase 2), `closingEdge`
(cạnh khép khi `loop`), `wanderRadius` (`max_radius` của random walk),
`heading` (mũi tên của sudden stop).

**Vẫn là render dữ liệu đã khai, không phải evaluate motion law.** Mọi
điểm vẽ ra đều là điểm tác giả đặt và tài liệu lưu; không cái gì được
đẩy theo thời gian, không cái gì nhân với vận tốc. Ngoại lệ duy nhất —
mũi tên heading — có **độ dài cố định 1.5 m theo quy ước hiển thị**,
cố ý *không* lấy `speed × stop_time`: con số đó là *chỗ vật cản dừng*,
tức câu trả lời của simulator, và tính nó trong browser là dựng bản sao
thứ hai của luật chuyển động. Có test riêng khẳng định vật cản nhanh và
chậm cho **cùng một mũi tên**.

**Handle sinh ra từ chính chỗ vẽ**, không phải từ một lần duyệt thứ hai
trong hit-tester — Phase 2 dùng lại danh sách này, nên cái nhìn thấy
đúng bằng cái cầm được. Hai danh sách sẽ trôi khỏi nhau thành một điểm
thấy mà không bắt được.

**Guard NaN, và đây là chuyện thật chứ không phải phòng xa.**
`numberFromInput` cố ý để ô rỗng thành `NaN` (quyết định từ Phase 3
đợt trước), mà `ctx.arc(x, y, NaN, …)` **ném** — xoá một ô radius giữa
lúc sửa là mất trắng canvas. Mọi giá trị đi vào hình học đều qua
`drawable()`; radius/max_radius/heading không hữu hạn thì **không vẽ**
thay vì vẽ hỏng, và waypoint có toạ độ NaN bị bỏ qua chứ không kéo cả
route theo.

## `MapCanvas` — hai bức tranh, hai màu, một chồng lên một

Prop mới `authoredTraffic?: TrafficOverlay`, vẽ **dưới** lớp preview.
Cả hai mô tả cùng những vật cản đó, nên khi có preview thì ảnh chụp hổ
phách nằm trên (đó là câu trả lời cho "nó ở đâu lúc t"), còn màu xanh
ngọc bên dưới là lộ trình nó được giao. Thân vật cản authored vẽ **rỗng
ruột** — đĩa đặc sẽ tranh mắt với đĩa preview, mà nó không phải chỗ vật
cản đang đứng, nó là chỗ lộ trình bắt đầu. Obstacle đang chọn vẽ đậm,
còn lại `globalAlpha` 0.45.

`MissionPlacer` **pass-through thuần** — component này biết pose là gì
và cố ý không biết waypoint là gì; giữ đúng ranh giới An chốt ở review
v3. `/decisions` không phải sửa (prop optional).

## Legend — nói ra, không để đoán bằng màu

`deployments.form.traffic.legend` (en + vi) dưới canvas khi có traffic:
xanh ngọc là cái bạn khai và sửa được, hổ phách là ảnh chụp của server
và **không phải nút bấm**. Không có câu này thì click vào đĩa vàng
không phản ứng sẽ bị đọc là preview hỏng.

## Bằng chứng (suite nhắm đích)

| Kiểm | Kết quả |
|---|---|
| `npm run typecheck` | sạch |
| `vitest run traffic-overlay` (mới) | **18 passed** |
| `vitest run traffic-ui` | 24 passed |
| `vitest run pointer-routing` | 5 passed |
| `vitest run traffic` | 57 passed |
| `vitest run traffic-editor` | 24 passed |
| `vitest run deployments-page` (+2 guard mới) | **75 passed** |
| `vitest run decisions-page` | 80 passed |
| `vitest run i18n` (key mới đủ hai locale) | 22 passed |
| `pytest tests/test_form_covers_the_contract.py` | 17 passed |

Hai guard mới trong `deployments-page.test.tsx`: form truyền
`overlayOf(...)` kèm `selectedObstacleIndex` xuống canvas; và legend có
mặt ở cả mã nguồn lẫn bản dịch en (khẳng định câu chữ có "not a
control").

## Chưa phủ được (đúng như plan ghi)

Node không có DOM, nên **phần vẽ thật sự chưa bao giờ chạy trong
suite** — `useEffect` của canvas không chạy dưới
`renderToStaticMarkup`. Hình học thì test kín (18 ca), việc đổ hình học
đó lên `ctx` thì chỉ checklist tay ở Phase 4 chạm tới. Đây là cùng lỗ
hổng đã ghi ở report Phase 3 đợt trước, không phải cái mới.

## Còn lại của plan

Phase 2 (hit-test, kéo handle, double-click xoá, click body chọn) →
Phase 3 (layout hai cột + 7 tab) → Phase 4 (test, i18n, checklist tay,
full suite + build).

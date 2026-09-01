# Phase 0 — state model + contract pointer cho tương tác map trực tiếp

> Plan: `docs/antongduy/plans/2026-08-16/tuong-tac-map-va-refactor-layout-deployment.md` (v4, Phase 0).
> Ngày làm: 2026-08-16. Nhánh: `tongduyan_plannerselector`. **Chưa commit.**
> Theo chỉ đạo của An: **không chạy full suite** tới phase cuối — bằng chứng dưới đây là suite nhắm đích.

## 0a — `lib/trafficUi.ts`: ba câu hỏi, một reducer

`TrafficSelection = {index, mode}` cũ trói "obstacle nào đang chọn" vào
"click tiếp theo đặt field nào" — click vào body để *chỉ chọn* không có
giá trị hợp lệ. Tách thành ba field trong một state, transition sống
trong pure reducer:

- `selectedObstacleIndex` — highlight;
- `trafficPlacement` — click tiếp theo đặt gì (implies selection);
- `activeDrag` — handle đang cầm, **kèm `phase: "candidate" | "committed"`**
  và `downClient` làm gốc đo threshold.

Vòng đời phase đúng như review v4 chốt: drag mở ở `candidate`, **chưa
được mutate**; chỉ sau `dragCommitted` (vượt `dragGate`, 5px client)
geometry mới được ghi. Candidate up/cancel = click, chỉ `endDrag`,
không flush — phần flush là việc của form ở Phase 2, nhưng field
`phase` mà form sẽ hỏi thì pin ở đây.

Actions document-level theo ma trận v3/v4: `obstacleAdded` (chọn con
mới), `obstacleRemoved` (clear + reindex cả ba), `obstaclesReplaced`
(**clear, không clamp** — index 1 mới không phải obstacle index 1 cũ),
`motionKindChanged` (huỷ placement/drag của row, **giữ** selected),
`reset` (adopt map). Hai invariant có test riêng và test chạy xuyên
chuỗi action trộn: placement/drag luôn trỏ đúng obstacle đang selected;
index luôn hợp lệ sau mọi action document-level.

## 0b — `MapCanvas`: Pointer Events + adapter legacy không double-fire

- Props mới: `onWorldPointerDown/Move/Up/Cancel(point, {pointerId,
  worldPerPixel, event})` + `onWorldDoubleClick(point)`.
  `worldPerPixel = 1/viewport.scale` — call site đổi tolerance pixel ra
  metre.
- Mouse handlers cũ thay bằng pointer handlers (pointer events phủ
  mouse); `onWorldClick`/`onWorldDrag` giữ nguyên chữ ký, chạy như
  **adapter** trên nền đó — `/decisions`, replay, MapPainter, scenario
  editor không sửa dòng nào.
- Luật một-event-một-chủ nằm trong hàm thuần `lib/pointerRouting.ts`:
  truyền `onWorldPointerDown` thì `onWorldClick` câm, truyền
  `onWorldPointerMove` thì `onWorldDrag` câm — theo từng gesture.
- **`setPointerCapture` chỉ bật khi có pointer handler mới.** Điểm này
  An bắt ở review v4 và nó có thật trong code cũ: `onMouseLeave` đang là
  cơ chế kết thúc drag của consumer legacy — MapPainter dừng nét vẽ ở
  mép canvas nhờ nó. Capture vô điều kiện sẽ đổi hành vi đó ngầm.
  Legacy giữ `onPointerLeave` → dừng drag, y như cũ.

## API `TrafficEditor` đổi theo (hệ quả đã báo trước ở plan v2)

- `selection`/`onSelect(selection)` → `selectedIndex` + `placement` +
  `onSelect(index)` + `onPlacementToggle(index, mode)`.
- Mutation đổi nghĩa index thành **intent**: `onAdd` / `onRemove(index)`
  / `onKindChange(index, kind)` — form là nơi duy nhất vừa sửa document
  vừa dispatch action UI tương ứng (`obstacleAdded`/`obstacleRemoved`/
  `motionKindChanged`), nên hai nửa không thể quên nhau. Field edit
  giữ-nguyên-identity (tên, radius, tham số motion) vẫn đi `onChange`
  như cũ. Prop `anchor` rời khỏi TrafficEditor — chỉ form cần nó.
- Row có highlight chọn (`aria-current`) + click row để chọn — cùng một
  selection mà click body trên map (Phase 2) sẽ dùng.

`DeploymentForm`: `placing` giờ chỉ giữ mode mission (start/goal/none);
mode đưa xuống canvas = `trafficPlacement?.mode ?? placing`. Adopt map
dispatch `reset`. Số call site `invalidateCheck()` giữ nguyên 5 — guard
đếm trong `deployments-page.test.tsx` không đổi.

## Bằng chứng (suite nhắm đích)

| Kiểm | Kết quả |
|---|---|
| `npm run typecheck` | sạch |
| `vitest run traffic-ui` (mới) | **24 passed** |
| `vitest run pointer-routing` (mới) | **5 passed** |
| `vitest run traffic-editor` (cập nhật API + 2 ca selection-không-placement) | **24 passed** |
| `vitest run traffic` (không đổi) | **57 passed** |
| `vitest run deployments-page decisions-page` (guard đọc mã nguồn) | **153 passed** |
| `pytest tests/test_form_covers_the_contract.py` | **17 passed** |

Chưa chạy: full web suite, full pytest, `next build` — dồn về phase
cuối theo chỉ đạo.

## Ghi chú lệch plan (nhỏ, có lý do)

- `dragGate` đặt ở `trafficUi.ts` thay vì `trafficOverlay.ts` (Phase 2
  chưa tồn tại): nó gate transition `dragCommitted` của chính reducer
  này. Phase 2 import từ đây.
- Plan không nói row-click-to-select trong panel; thêm vì rẻ và cùng
  đường selection với click body trên map. Có test render.

## Còn lại của plan

Phase 1 (overlay) → 2 (hit-test/kéo/xoá) → 3 (layout tab) → 4 (test +
i18n + checklist tay + full suite).

# Phase 2 — chọn và kéo thẳng trên bản đồ

> Plan: `docs/antongduy/plans/2026-08-16/tuong-tac-map-va-refactor-layout-deployment.md` (v4, Phase 2).
> Ngày làm: 2026-08-16. Nhánh: `tongduyan_plannerselector`. **Chưa commit.**
> Phase 0 và 1 An đã commit. Vẫn **chưa chạy full suite** — dồn về phase cuối.

## Bốn hàm thuần, một bảng quyết định

Toàn bộ phần *nghĩ* nằm trong `lib/trafficOverlay.ts`, test được trên
Node; component chỉ nối dây.

| Hàm | Việc |
|---|---|
| `hitTest(obstacles, selectedIndex, point, tolWorld)` | Cái gì nằm dưới con trỏ |
| `moveHandle(motion, handle, at)` | Dời **đúng** điểm đang cầm |
| `deleteWaypointAt(motion, k)` | Bỏ một waypoint giữa lộ trình |
| `interpretPointer` / `interpretDoubleClick` | Một cú nhấn / một cú nhấn đúp nghĩa là gì |

**`hitTest` nhận `selectedIndex` làm tham số**, không để caller tự xử
sau — nấc tie-break "obstacle đang chọn thắng" là *một phần của quyết
định*, và caller làm lại nó là bản sao thứ hai của thứ tự. Bốn nấc, cố
định: handle thắng body → gần hơn thắng → đang chọn thắng → index nhỏ
hơn thắng. Ba nấc đầu đều có ca thật: waypoint 0 nằm **trong** đĩa thân
của chính nó (không có nấc 1 thì điểm nhỏ không bao giờ bấm được), hai
xe đỗ chồng nhau (nấc 3 và 4).

**`moveHandle` cố ý không phải `placeOnMotion`.** Đặt thì *nối thêm*
waypoint, kéo thì *thay* điểm đang giữ — cho drag đi qua bản đặt sẽ để
lại một vệt điểm sau con trỏ. `body` **không dời gì**: kéo cả vật cản
buộc phải quyết định nó nghĩa là gì cho từng luật (mọi waypoint hay chỉ
điểm đầu? origin hay cả vòng lang thang?), mỗi câu trả lời là một phép
sửa khác nhau. Thân là để chọn.

**`interpretDoubleClick` — ba đường không được xoá**, và cả ba đều là
đường mất điểm thật: đang bật placement (hai cú nhấn là hai lần đặt,
xoá thêm là undo cái vừa tạo), con trỏ có kéo ở giữa (một cú kéo có chủ
đích kết thúc gần chỗ xuất phát không phải yêu cầu xoá), và mục tiêu là
body hoặc nền trống (chỉ waypoint mới xoá riêng được — các điểm khác là
*trường* của luật chuyển động, một periodic thiếu `start` không phải
periodic ít hơn một điểm).

## Ranh giới component giữ đúng như An chốt

`MissionCanvas` chưa tách (Phase 3), nhưng ranh giới trách nhiệm thì đã
đúng: `MissionPlacer` nhận **bốn callback optional** và **không biết
waypoint là gì** — nó hỏi caller "anh có lấy cú nhấn này không", ai trả
lời `true` thì placer không đụng vào pose nữa. Hit-test, drag state và
phép sửa tài liệu đều ở `DeploymentForm`.

**Pointer lifecycle chỉ bật khi có người dùng** (`lifted =
onPointerDownFirst !== undefined`): `/decisions` truyền không, nên giữ
nguyên props cũ, giữ nguyên pointer-capture-tắt, giữ nguyên
"rời canvas thì dừng kéo".

## Ba chỗ dễ sai, xử lý riêng

**1. rAF ghi lên tài liệu *hiện tại*, không phải bản chụp.** Thêm
`setLive` ghi qua `draftRef.current`. `set` thường đóng gói `draft` của
lần render tạo ra nó — mà drag ghi mỗi frame, nên frame thứ hai sẽ dựng
lại tài liệu từ trạng thái *trước* frame thứ nhất và điểm nhảy qua lại
giữa hai vị trí. Đúng lớp stale-write mà adopt map đã dính qua `await`.

**2. Candidate không bao giờ ghi.** `endDrag` trả về sớm nếu
`!active.committed`. Không có dòng đó thì một cú click đơn lên waypoint
(hoặc nửa cú nhấn đúp) sẽ dời điểm trước khi chọn/xoá — đúng thứ
`dragGate` sinh ra để chặn. Gốc đo threshold là **client position lúc
nhấn**, do canvas truyền lên, không phải move đầu tiên (bản nháp đầu
lấy move đầu, làm gate yếu đi vài pixel).

**3. Cancel không tin toạ độ của chính nó.** `pointercancel` có thể tới
từ gesture interruption mang một vị trí không ai trỏ vào; nên flush
`lastWorld` — vị trí mà một *move* báo lần cuối.

`draggedInSequence` reset theo `event.detail <= 1`: cú nhấn thứ hai của
một nhấn đúp mang `detail === 2` nên không xoá cờ của cú thứ nhất — đó
là cách handler nhấn đúp biết giữa hai cú nhấn có kéo thật hay không.

## Hai guard cũ đỏ, và cả hai đỏ đúng

| Guard | Vì sao đỏ | Xử lý |
|---|---|---|
| `deployments-page`: đếm `invalidateCheck()` = 5 | Đúng chức năng nó được viết ra: comment ghi "a further way added later fails here instead of silently keeping a stale tick". Đường thứ sáu là `setLive` | Lên **6**, comment ghi rõ đường mới là *writer* thứ hai chứ không phải luật thứ hai |
| `decisions-page`: pin chuỗi `missionMode ? { onWorldDrag: ... }` | Component giờ có **hai** lifecycle; chuỗi cũ chỉ mô tả nhánh legacy | Viết lại **phủ cả hai nhánh** — cùng một luật, hai đường thi hành. Luật thi hành ở một đường và quên ở đường kia chính là hỏng mà test này tồn tại để bắt |

Không guard nào bị nới: cái thứ nhất đổi số kèm lý do, cái thứ hai
kiểm **nhiều** hơn trước.

## Bằng chứng (suite nhắm đích)

| Kiểm | Kết quả |
|---|---|
| `npm run typecheck` | sạch |
| `vitest run traffic-overlay` | **38 passed** (18 → 38, thêm 20 ca cho hit-test/move/delete/interpret) |
| `vitest run traffic-ui` | 24 passed |
| `vitest run pointer-routing` | 5 passed |
| `vitest run traffic` | 57 passed |
| `vitest run traffic-editor` | 24 passed |
| `vitest run i18n` | 22 passed |
| `vitest run deployments-page decisions-page` | **158 passed** (+3 guard mới ở deployments) |
| `pytest tests/test_form_covers_the_contract.py` | 17 passed |

Ba guard mới pin: một bảng duy nhất quyết định cú nhấn
(`interpretPointer` + `onPointerDownFirst={claimPress}` + `moveHandle`);
drag ghi qua `draftRef.current` + `requestAnimationFrame`; candidate
không ghi (`if (!active.committed) return;`) và cancel dùng
`active.lastWorld`.

## Chưa phủ được

Vẫn là cùng một lỗ hổng: Node không có DOM, nên **chuỗi pointer thật
chưa bao giờ chạy** — kéo, nhấn đúp, capture, rAF. Phần *quyết định*
sau chúng thì test kín (38 ca). Checklist tay Phase 4 là chỗ nghiệm thu
phần còn lại, và giờ nó có thêm mục: kéo ra ngoài canvas không đứt,
click đơn không dời điểm, nhấn đúp rung tay không dời điểm.

## Còn lại của plan

Phase 3 (tách `MissionCanvas` + export `PoseFields`, layout hai cột 7
tab, `routeError`, responsive `canvasSize`) → Phase 4 (test, i18n,
checklist tay, full suite + build).

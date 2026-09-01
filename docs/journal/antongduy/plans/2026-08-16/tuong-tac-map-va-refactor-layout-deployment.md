# Plan: Tương tác traffic trực tiếp trên map + refactor layout deployment form

> Trạng thái: **approved**. Chưa triển khai dòng code nào.
> Ngày lập: 2026-08-15 (lưu theo yêu cầu vào folder 2026-08-16). Nhánh: `tongduyan_plannerselector`.
> **Bản v2** — sau vòng review của An cùng ngày, 6 điểm + 6 cải tiến, nhận
> gần hết: (1) tách TrafficSelection thành 3 state + pure reducer giữ
> invariant; (2) contract Pointer Events đầy đủ + pointer capture +
> `worldPerPixel`, giữ props cũ làm adapter; (3) `routeError(path)` thay
> "tab gần nghĩa" — `environment` bare → Traffic theo contract, unmapped
> chỉ hiện footer; (4) tách `MissionCanvas` + export `PoseFields`,
> `MissionPlacer` thành wrapper compat; (5) responsive bằng
> ResizeObserver, breakpoint tính từ min-width thật; (6) chỉ authored
> overlay tương tác, preview read-only. Hệ quả nhận thêm:
> `traffic-editor.test.tsx` phải sửa theo API mới (v1 ghi "giữ nguyên"
> là sai).
> **Bản v3** — vòng review thứ hai của An, 4 sửa + 5 làm rõ, nhận hết:
> (1) bỏ mâu thuẫn mobile vs min-width 480 — 480 thành ngưỡng sập
> layout, canvas `min(760, containerWidth)`; (2) MissionCanvas không
> biết traffic — chỉ trình bày + pass-through, logic về DeploymentForm;
> (3) semantics double-click viết lại 3 nhánh + drag threshold;
> (4) reducer thêm action document-level (`reset`, `obstaclesReplaced`,
> `motionKindChanged`) + ma trận transition; làm rõ: adapter không
> double-fire, cancel flush toạ độ move cuối, rAF ghi qua
> `draftRef.current`, `canvasSize()` thuần, breakpoint 924px suy ra rõ.
> **Bản v4** — vòng review thứ ba của An, 4 điểm, nhận cả 4:
> (1) *blocking* — `ActiveDrag` mang `phase: candidate | committed`;
> candidate up/cancel **không flush** (click đơn/dblclick không được
> mutate waypoint); (2) `hitTest` nhận `selectedIndex` để tie-break nội
> bộ; (3) `obstaclesReplaced` chốt **clear cả ba**, không clamp — index
> mới không cùng đối tượng với index cũ; (4) `setPointerCapture` chỉ khi
> có pointer handler mới — legacy giữ lifecycle mouseleave-kết-thúc-drag,
> checklist thêm MapPainter.

## Context

Phase 2b (config vật thể động) đã ship: TrafficEditor khai được 4 motion kind, click-to-place qua `PlacementMode`, dry-run `/task-profiles/validate`, preview qua `/scenarios/preview`. Nhưng dùng thật thì khó:

1. **Click mù.** Route đang khai (waypoints, đoạn periodic, origin random-walk, heading sudden-stop) **không vẽ lên map** — `MapCanvas` chỉ vẽ vị trí đã resolve từ server preview. Đặt 3 waypoint không thấy gì cho tới khi bấm Preview.
2. **Nút placement xa map.** Nằm trong từng row TrafficEditor **dưới** canvas — chọn mode rồi cuộn lên map để click.
3. **Form một cột dọc dài** ~15 section từ identity tới submit; map — thứ trung tâm — nằm gần cuối.

An chốt (hỏi-đáp 2026-08-15):
- **Map UX**: vẽ overlay + click chọn vật cản trên map + **kéo** điểm đã đặt + double-click xoá waypoint. Đường kính/vận tốc… vẫn nhập số.
- **Layout**: hai cột — map + mission bên trái, panel **7 tab** bên phải (Mission · Traffic · Robot · Constraints · Noise · Policies · Hardware). Identity trên đầu, ngoài tab. Tab có lỗi server hiện badge đỏ.
- **Map picker** (library/stored/drawn): toolbar ngay trên canvas.
- **Preview** (time/seed/nút) dưới canvas; **Check + File it** ở footer sticky cuối form.
- **Chỉ authored overlay tương tác được** (review v2); preview snapshot read-only tuyệt đối, legend nói rõ.

**Zero backend change** — toàn bộ đợt này là web UI. Server vẫn là nguồn phán quyết duy nhất; overlay chỉ vẽ **dữ liệu đã khai** (geometry thuần), không đánh giá motion law — vị trí tại t vẫn từ `/scenarios/preview`.

## Ràng buộc phải giữ

- **"The form decides nothing"** — không luật hợp đồng nào trong browser (test grep cấm pattern so sánh luật, `deployments-page.test.tsx:107`).
- **Không simulator logic trong UI** (`MapCanvas.tsx:3-7`). Vẽ polyline nối waypoints user vừa khai = render dữ liệu authored (như `staticObstacles`), không phải evaluate motion. Ghi rõ trong docstring overlay.
- **3 test đọc mã nguồn theo đường dẫn file cố định**:
  - `tests/test_form_covers_the_contract.py:32` — `FORM_PATH = DeploymentForm.tsx` (drift guard đòi mọi dotted path hợp đồng có mặt trong file này), `:175-178` đọc `TrafficEditor.tsx` + `lib/traffic.ts`;
  - `apps/web/src/app/__tests__/deployments-page.test.tsx:28-30` đọc `DeploymentForm.tsx`, `TrafficEditor.tsx`;
  - `apps/web/src/app/__tests__/decisions-page.test.tsx:37` đọc `MissionPlacer.tsx`.
  ⇒ **Giữ mọi `field("dotted.path", …)` trong `DeploymentForm.tsx`**: tab content là các function/component cục bộ trong chính file đó. Chỉ tách shell `Tabs` generic (không chứa contract path) ra file riêng. Nếu buộc phải dời code, theo tiền lệ W1: *cùng assertion, đổi file nó đọc*.
- Vitest chạy **Node, không jsdom** — mọi quyết định (hit-test, drag, tab routing, state transition) phải là hàm thuần trong `lib/`, component chỉ nối dây; render pin bằng `renderToStaticMarkup`.
- `/decisions` dùng `MissionPlacer` uncontrolled — **không sửa trang đó**: MissionPlacer thành wrapper compat, props cũ chạy nguyên.
- 2.5D (`Scene25D`) chỉ hiển thị — không nhận overlay authoring (flat-only, đúng scope cũ).

## Tái dùng (đã có sẵn)

`lib/traffic.ts`: `trafficOf`, `placeOnMotion`, `PLACEMENTS`, `updateObstacle`, `removeObstacle`, `dropLastWaypoint`, `snapshotsOf`, `previewRequestOf`. `lib/sequencer.ts` cho race. `lib/transform.ts`: `canvasToWorld`, `fitViewport`. Vòng đời adopt/check/preview + `invalidateCheck()`/`frozen` trong `DeploymentForm.tsx` giữ nguyên — layout mới chỉ sắp xếp lại chỗ render.

## Phase 0 — State model + contract pointer (nền cho mọi phase sau)

### 0a. Tách `TrafficSelection` thành ba khái niệm

`TrafficSelection = {index, mode}` hiện tại (TrafficEditor.tsx:48) trói "obstacle đang chọn" vào "click tiếp theo đặt field nào" — click body để *chỉ chọn* không có mode hợp lệ để điền. Tách:

```ts
selectedObstacleIndex: number | null                      // highlight, row sáng
trafficPlacement: { index: number; mode: TrafficPlacement } | null  // click tiếp theo đặt gì
activeDrag: {
  hit: Hit;
  pointerId: number;
  phase: "candidate" | "committed";  // candidate = chưa vượt dragGate, CHƯA được mutate
  downClient: Point2D;               // gốc đo threshold
} | null
```

**Ba state rời tự nó vẫn khoá lẫn nhau được** (placement trỏ A trong khi selected là B; xoá obstacle bỏ quên drag; adopt map thay cả danh sách mà không dọn). Nên transition sống trong **pure reducer** `lib/trafficUi.ts`:

- actions tương tác: `select(i)`, `beginPlacement(i, mode)`, `endPlacement`, `beginDrag(hit, pointerId, downClient)` (tạo drag `phase: "candidate"` — chưa mutate), `dragCommitted` (vượt `dragGate`, chuyển `phase: "committed"` — từ đây mới mutate geometry), `endDrag`;
- **vòng đời drag theo phase (v4 — đây là chỗ blocking):**
  - candidate + pointer-move dưới threshold: **không mutate**;
  - candidate + pointer-up/cancel: chỉ `endDrag`, **không flush** — click đơn trên waypoint = select, không dời điểm;
  - committed + pointer-up: flush toạ độ up rồi `endDrag`;
  - committed + pointer-cancel: flush `lastValidWorldPoint` (từ move, không từ cancel event) rồi `endDrag`;
  - double-click handler **không xoá** nếu trong click sequence đó đã có drag `committed`;
- actions document-level (v3 — thiếu là ba state mồ côi khi tài liệu đổi dưới chân): `obstacleAdded`, `obstacleRemoved(i)` (clear + reindex cả ba), `obstaclesReplaced` (adopt scenario library / traffic về rỗng khi stored-drawn — **clear cả ba, không clamp**: index 1 mới không phải cùng obstacle với index 1 cũ, clamp cho ra selection hợp lệ phạm vi nhưng sai đối tượng; chỉ `obstacleRemoved` mới reindex, edit giữ nguyên identity không gọi action này), `motionKindChanged(i)` (huỷ placement/drag của row đó — handle cũ hết nghĩa — **giữ** selected), `reset()` (adopt map: cả ba về null);
- **ma trận transition ghi tường minh, test đủ**: `select(i)` kết thúc placement + drag cũ; `beginPlacement` kết thúc drag; `beginDrag` kết thúc placement; `motionKindChanged` huỷ placement/drag row đó, giữ selected; adopt map `reset` cả ba;
- invariant pin bằng test: `trafficPlacement ≠ null ⇒ selectedObstacleIndex === trafficPlacement.index`; `activeDrag ≠ null ⇒ selectedObstacleIndex === activeDrag.hit.index`; mọi index luôn trong `[0, count)` sau bất kỳ action document-level nào.

**Hệ quả API**: `TrafficEditor` props `selection`/`onSelect` đổi thành `selectedIndex` + `placement` + callbacks → **`traffic-editor.test.tsx` (22 ca) phải cập nhật theo**, cùng các chuỗi pin trong `deployments-page.test.tsx`.

### 0b. `MapCanvas` chuyển sang Pointer Events

Contract hiện tại (mousedown = click, mousemove = drag, không up/cancel, không capture, không scale ra ngoài) không chở được drag handle. Contract mới:

```ts
onWorldPointerDown?/Move?/Up?/Cancel?(point: Point2D, info: { pointerId: number; worldPerPixel: number; event })
onWorldDoubleClick?(point: Point2D)
```

- `setPointerCapture(pointerId)` lúc down — drag không đứt khi con trỏ rời canvas; `Cancel` giải phóng drag dở. **Chỉ capture khi có pointer handler mới được truyền** (v4): legacy-only consumer giữ nguyên lifecycle cũ — rời canvas thì drag dừng (`onMouseLeave` hiện là cơ chế kết thúc paint của MapPainter; capture vô điều kiện sẽ làm painter vẽ tiếp ngoài canvas, đổi hành vi ngầm).
- `worldPerPixel = 1 / viewport.scale` — call site đổi tolerance pixel (8px) ra metre.
- **`onWorldClick`/`onWorldDrag` cũ giữ nguyên, implement như adapter trên nền pointer handlers** — `/decisions`, replay, MapPainter, scenario editor không sửa. Test pin adapter: click cũ vẫn bắn đúng lúc pointer-down.
- **Không double-fire** (v3): truyền handler pointer mới thì adapter legacy tương ứng **bị bỏ qua** — pointer thắng, một event một chủ. Consumer cũ không truyền handler mới nên hành vi y nguyên; test pin cả hai chiều (chỉ legacy → legacy bắn; cả hai → chỉ pointer bắn).

## Phase 1 — Overlay: thấy được cái đang khai

**`apps/web/src/lib/trafficOverlay.ts`** (mới, thuần):
- `overlayOf(obstacles: DynamicObstacle[], selectedIndex: number | null): TrafficOverlay` — mỗi obstacle thành geometry theo kind:
  - `waypoint`: dots đánh số + polyline; cạnh đóng (dashed) khi `loop`;
  - `periodic`: hai đầu start/end + đoạn nối;
  - `random_walk`: origin + vòng tròn `max_radius` (dashed);
  - `sudden_stop`: điểm start + mũi tên theo `heading`;
  - kèm vòng tròn `radius` tại điểm "nhà" (start/origin/waypoint đầu) — cho thấy cỡ, và là target click-select Phase 2;
  - cờ `selected` để highlight (obstacle đang chọn đậm, còn lại mờ).

**`MapCanvas.tsx`**: prop mới `authoredTraffic?: TrafficOverlay` — render markers/polylines/labels (tên obstacle cạnh điểm nhà). Màu tách khỏi preview: preview (vàng `dynamicObstacle`) = "vị trí tại t theo server", overlay authored = "route bạn khai" — hai câu, hai màu. **Legend dưới canvas nói rõ: preview read-only, chỉ hình authored tương tác được.**

**`DeploymentForm.tsx`**: dựng `overlayOf(trafficOf(draft), selectedObstacleIndex)` truyền xuống qua MissionCanvas.

DoD: khai warehouse_crossing_v1 bằng form thấy nguyên route trên map không cần Preview; obstacle đang chọn sáng lên.

## Phase 2 — Chọn & kéo trực tiếp trên map

**Quyết định thuần, trong `lib/trafficOverlay.ts`:**
- `hitTest(obstacles, selectedIndex, point, tolWorld): Hit | null` — `Hit = { index, handle }`, handle = `waypoint(k)` | `periodic-start` | `periodic-end` | `origin` | `sudden-start` | `body`. **Chỉ hit-test hình authored** — snapshot preview không bao giờ là target.
  Tie-break xác định **nội bộ trong hàm** (v4 — chữ ký phải nhận `selectedIndex`, tie-break ở caller là tách luật khỏi chỗ test nó), theo thứ tự: handle thắng body → khoảng cách gần nhất thắng → bằng nhau thì obstacle đang selected thắng → còn bằng thì index nhỏ hơn.
- `moveHandle(motion, handle, point): Motion` — dời đúng điểm handle gọi tên (waypoint(k) sửa phần tử k, không append).
- `deleteWaypointAt(motion, k): Motion`.
- `interpretPointer(placement, hit): "place" | "begin-drag" | "select" | "mission"` — bảng ưu tiên một chỗ:
  1. `trafficPlacement ≠ null` ⇒ **đặt điểm** (hành vi cũ, kể cả guard chống drag-spam waypoint);
  2. Không placement: trúng handle ⇒ **begin-drag**; trúng body ⇒ **select** (không drag);
  3. Trượt hết ⇒ start/goal như cũ (mission mode).
- `dragGate(downPx, currentPx, thresholdPx≈5): boolean` — candidate drag chỉ **committed** (bắt đầu mutate) khi vượt threshold màn hình.

**Semantics double-click, ba nhánh — viết một lần cho khỏi tự mâu thuẫn (v3):**
1. `trafficPlacement ≠ null`: mỗi pointer-down vẫn **đặt điểm** như thường (double-click = 2 điểm); handler double-click **không xoá** — không trộn nghĩa.
2. Không placement, hit waypoint: hai pointer-down chỉ được **select + begin candidate drag**, **không mutate geometry** (candidate chưa committed); double-click đến sau ⇒ **cancel candidate drag rồi xoá** waypoint đó.
3. Có chuyển động vượt `dragGate` giữa hai down ⇒ là **drag**, không phải double-click delete — rung tay không dời waypoint trước khi xoá, và kéo thật không bị nhầm thành xoá.

**Nối dây — toàn bộ trong `DeploymentForm` (MissionCanvas không biết traffic, xem Phase 3):**
- pointer-down: hit-test → dispatch theo `interpretPointer`.
- pointer-move khi `activeDrag` committed: toạ độ ghi vào ref, **rAF coalesce** — mỗi frame flush một lần; **flush mutate qua `draftRef.current`, không qua snapshot `draft` mà closure `set()` đang giữ** — cùng lớp stale-write H2 của adopt cũ, đã có `draftRef` sẵn để dùng.
- pointer-up/cancel: **theo đúng vòng đời phase ở Phase 0a** — candidate thì chỉ `endDrag` không flush; committed + up thì flush toạ độ up; committed + cancel thì flush **toạ độ hợp lệ cuối cùng đã nhận qua move** (giữ trong ref), **không** dùng toạ độ từ cancel event — cancel có thể đến từ browser/gesture interruption với toạ độ rác.
- Click body ⇒ `select(i)` + **auto-switch tab Traffic** + scroll row: đặt `pendingScrollIndex`, scroll bằng effect **sau khi tab đã render**, không `scrollIntoView()` trong handler.

DoD: kéo waypoint mượt (không đứt khi rời canvas), polyline bám theo; double-click xoá đúng điểm; click cart trên map chọn đúng row trong tab Traffic.

## Phase 3 — Layout: hai cột + 7 tab

### Tách `MissionPlacer` (điều kiện để canvas trái / control phải)

Hiện gói chung toolbar + caption + canvas + PoseFields trong một component, PoseFields chưa export. Tách, **ranh giới trách nhiệm rõ (v3 — MissionCanvas không được biết waypoint là gì, để còn dùng ngoài deployment):**

| Tầng | Biết gì |
|---|---|
| `MapCanvas` | pointer → world coordinates, render. Hết. |
| `MissionCanvas.tsx` (mới) | trình bày MapView + caption + legend, **pass-through** callback pointer/doubleclick + `authoredTraffic`. Không hitTest, không reducer, không waypoint semantics. |
| `DeploymentForm` | sở hữu `trafficUi` reducer, `hitTest`, `interpretPointer`, `dragGate`, rAF flush, mọi mutation traffic. |
| `MissionPlacer.tsx` | **wrapper compat** (toolbar + MissionCanvas + PoseFields, state mode uncontrolled như cũ), đặt start/goal qua callback — `/decisions` không sửa. |

- **`PoseFields`**: export riêng để DeploymentForm đặt trong tab Mission;
- `decisions-page.test.tsx` vẫn đọc `MissionPlacer.tsx`, invariant "chỉ `useState<PlacementMode>`" vẫn đúng vì mode state ở lại wrapper.

### Shell bố cục (`DeploymentForm.tsx`, field content ở lại file — ràng buộc drift guard)

```
[Identity row: id · claim_level · role]            ← ngoài tab
┌──────────────────────────┬─────────────────────┐
│ MAP BLOCK                │ TAB PANEL            │
│ · toolbar nguồn map      │ Mission | Traffic |  │
│   (library/stored/drawn) │ Robot | Constraints |│
│   + dropdown tương ứng   │ Noise | Policies |   │
│ · DrawNewMap (khi drawn) │ Hardware             │
│ · MissionCanvas          │ (tab lỗi: badge đỏ   │
│ · preview time/seed/nút  │  kèm số lỗi)         │
│ · legend + notice        │                      │
└──────────────────────────┴─────────────────────┘
[Footer sticky: Check · File it · idRule · verdict/summary lỗi]
```

- **Tab nội dung** (map từ code hiện tại, không đổi field nào): Mission (PoseFields + nút Place start/goal) · Traffic (TrafficEditor) · Robot (vehicle picker + 6 field) · Constraints (9 field + `clearance_preference`) · Noise (7 `noiseField` + note) · Policies (`v_obstacle_max` + replanning + recovery) · Hardware (7 field, bỏ nút gập `showHardware`).
- **Footer `position: sticky`** trong form container — không `fixed` theo viewport (fixed che nội dung, phá mobile).
- **A11y**: `role="tablist"`/`role="tab"`/`aria-selected`/`aria-controls`; panel ẩn dùng attribute `hidden` — rời accessibility tree nhưng **không unmount** ⇒ state cục bộ (remembered noise, vehicleId…) không mất khi qua lại tab. Render test pin cả hai: tab ẩn có trong DOM và mang `hidden`.
- `frozen` disable mọi control ở mọi tab (đã lan qua props sẵn).
- `components/Tabs.tsx` (mới, generic, không chứa contract path).

### `routeError(path)` — mapping lỗi vào tab, không đoán

Path không tự nói tab: 5 luật traffic là model validator nên trả path **`environment`** trần (đo ở Phase 2a cũ), và `id`/`claim_level`/`deployment_role` ngoài cả bảy tab. `lib/formTabs.ts` (thuần):

```
routeError(path): TabId | "identity" | "unmapped"
  id · claim_level · deployment_role        → identity  (render cạnh field như hiện tại, không thuộc tab)
  missions, missions.*                      → Mission
  robot.*                                   → Robot
  constraints.*, clearance_preference       → Constraints
  environment.sensor_noise.*                → Noise
  environment.v_obstacle_max, replanning.*, recovery.* → Policies
  environment.dynamic_obstacles.*           → Traffic
  environment (trần)                        → Traffic   (contract hiện tại: mọi model validator của
                                              EnvironmentSpec là luật traffic; TrafficEditor đang render
                                              đúng chỗ này. Hệ quả nói rõ: lỗi cross-check v_obstacle_max
                                              < max_speed cũng path `environment` nên hiện ở Traffic —
                                              đúng hành vi đang ship, chấp nhận)
  còn lại                                   → unmapped  (chỉ hiện footer, KHÔNG đếm giả vào tab nào)
```

- **Không phân loại bằng nội dung message.**
- `badgeCounts(errors)` đếm theo `routeError`; footer hiện tổng lỗi + lỗi unmapped nguyên văn.
- Drift guard hai phía: test API dry-run (đã có từ Phase 2a) pin 5 luật traffic trả path `environment`; web test mới pin bảng `routeError` kèm comment trỏ tới test API đó — backend đổi cách address thì một trong hai đỏ.
- Sau Check 422: **auto-switch sang tab đầu tiên có lỗi** (thứ tự tab cố định); lỗi identity/unmapped không switch, hiện tại chỗ.

### Responsive — toạ độ đúng ở mọi cỡ, không chỉ "sập cột"

`pointerWorld()` giả định CSS size = internal size (`canvas.style.width` set từ prop). `width: 100%` sẽ làm click lệch. Chọn **ResizeObserver**, và (v3) gỡ mâu thuẫn mobile-vs-min-width:
- **`canvasSize(containerWidth, mapAspect): {width, height}` — hàm thuần, test Node**: `width = Math.min(760, Math.max(1, containerWidth))`, height theo tỉ lệ map. **Không CSS min-width trên canvas** — mobile 390px thì canvas 390px, không tràn ngang. ResizeObserver chỉ làm nhiệm vụ nối dây: đo container → gọi `canvasSize` → set prop.
- `style.width` luôn khớp `width` prop ⇒ pointer math đúng ở mọi cỡ.
- **Sập 2 cột → 1 cột khi container form < 924px** — con số suy ra tường minh: 480 (chỗ đứng tối thiểu cho canvas ở layout hai cột) + 420 (panel min) + 24 (gap); ghi kèm derivation trong code. Đo bằng chính ResizeObserver đã có (container width, không media query theo viewport — panel bên cạnh làm viewport width nói dối). **480 là điều kiện sập layout, không phải min-width của canvas.**
- Acceptance kiểm **3 cỡ**: desktop rộng (≥1440) · ~1100 · mobile (~390), và ở mỗi cỡ **click đặt điểm phải đúng toạ độ** (điểm hiện đúng chỗ con trỏ) + **mobile không tràn ngang**, không chỉ kiểm layout.

DoD: mọi field cũ vẫn khai được, drift guard backend xanh không đổi assertion; badge đếm đúng theo `routeError`; check 422 nhảy đúng tab; click đúng toạ độ ở cả 3 cỡ màn hình.

## Phase 4 — Tests, i18n, giấy tờ

- **Thuần (vitest Node)**:
  - `trafficUi` reducer: đủ ma trận transition (kể cả document-level: `reset`, `obstaclesReplaced` clear cả ba, `motionKindChanged` giữ selected huỷ placement/drag) + **vòng đời drag phase** (candidate up/cancel không sinh mutation; committed up/cancel flush đúng nguồn toạ độ; dblclick sau drag committed không xoá) + invariant (ba state không bao giờ trỏ khác obstacle; index luôn hợp lệ sau remove);
  - `overlayOf` (4 kind × selected/không), `hitTest` (body/handle/waypoint k, tolerance theo `worldPerPixel`, đủ 4 nấc tie-break kể cả nấc selected qua tham số `selectedIndex`), `moveHandle`, `deleteWaypointAt`, `interpretPointer` (đủ nhánh bảng ưu tiên), `dragGate` (dưới/vượt threshold), `canvasSize` (hẹp 390, giữa, chạm trần 760);
  - `routeError`/`badgeCounts`: mọi dotted path form đang render map về đúng tab; `environment` trần → Traffic; path lạ → unmapped, không rơi mất; identity không vào tab.
- **Render pin** (`renderToStaticMarkup`): 7 tab đủ mặt; mỗi tab chứa field đại diện; badge render khi có lỗi; tab ẩn **có trong DOM và mang `hidden`**; tablist đủ aria; footer sticky có Check + File it; canvas block có preview controls + legend; `MapCanvas` nhận `authoredTraffic`; adapter `onWorldClick`/`onWorldDrag` còn sống cho consumer cũ.
- **Test cũ phải sửa theo, nói rõ**: `traffic-editor.test.tsx` (22 ca) theo API `selectedIndex`/`placement` mới; `deployments-page.test.tsx` các chuỗi pin vị trí render + wiring; `decisions-page.test.tsx` **không đổi** (MissionPlacer wrapper giữ nguyên hành vi); `test_form_covers_the_contract.py` **không đổi** (mọi contract path ở lại DeploymentForm.tsx).
- **i18n**: key mới (tab labels, badge aria, legend, hint kéo/xoá waypoint, caption chọn obstacle) đủ en + vi.
- **Checklist thủ công browser** (Node không phủ được — ghi vào report, An chạy):
  1. Overlay hiện đủ 4 kind, khớp toạ độ preview server tại t=0;
  2. Kéo waypoint mượt, polyline bám; kéo start periodic; kéo origin random-walk; **kéo ra ngoài canvas không đứt** (pointer capture);
  3. Double-click xoá đúng waypoint; trong placement mode double-click = 2 điểm, không xoá; **double-click hơi rung tay không dời waypoint** (drag threshold); **click đơn lên waypoint chỉ select, không dời điểm** (candidate không flush);
  3b. `/maps/[id]` (MapPainter, legacy props): kéo vẽ bình thường, **rời canvas thì dừng vẽ** — hành vi cũ y nguyên, không bị pointer capture giữ lại;
  4. Click cart authored → nhảy tab Traffic, row sáng, scroll đúng row; click snapshot preview vàng → không gì xảy ra;
  5. Đổi tab qua lại — remembered noise/vehicleId không mất;
  6. Check 422 → nhảy đúng tab, badge đúng số; lỗi `environment` trần hiện đầu khối Traffic;
  7. Ba cỡ màn hình (≥1440 / ~1100 / ~390): click đặt điểm đúng chỗ con trỏ ở cả ba; **mobile 390 không tràn ngang**;
  7b. Chọn scenario library có traffic rồi đổi sang stored map — selection/placement/drag không còn trỏ obstacle ma (reducer `reset`/`obstaclesReplaced`);
  8. Kéo nhanh liên tục — không giật (rAF coalesce), thả chuột điểm cuối đúng chỗ thả;
  9. Khai warehouse_crossing_v1 hoàn toàn bằng chuột + số → dry-run 204 → File 201.
- Report theo quy ước `docs/antongduy/reports/<ngày>/tongduyan_*.md`.

## Verification

- `npm run typecheck` sạch; `npm run test` (web, hiện 770 passed) xanh + test mới; `npm run build` (Next production, 17 trang) thành công.
- Backend: **không đụng** — không diff ngoài `apps/web`.
- Checklist thủ công Phase 4 — acceptance phần canvas là thủ công (đúng trạng thái đã ghi ở report Phase 3 cũ).

## Rủi ro

| Rủi ro | Xử lý |
|---|---|
| Ba state selection/placement/drag khoá lẫn nhau hoặc mồ côi khi tài liệu đổi | Pure reducer `trafficUi` + ma trận transition + action document-level; không component nào set thẳng |
| Drag handle vs click-append waypoint giẫm nhau | `interpretPointer` một bảng ưu tiên duy nhất; placement mode luôn thắng |
| Double-click nhập nhằng với place/drag | Semantics 3 nhánh viết một chỗ; candidate drag + `dragGate`; trong placement dblclick không xoá; sau drag committed cũng không xoá |
| Click đơn/dblclick mutate waypoint trước khi select/xoá | `ActiveDrag.phase` — candidate up/cancel chỉ `endDrag`, **không flush**; chỉ committed mới mutate |
| Drag đứt khi rời canvas / mất điểm cuối | `setPointerCapture` (chỉ khi có pointer handler mới); committed-up flush toạ độ up; committed-cancel flush toạ độ move hợp lệ cuối, không lấy từ cancel event |
| Pointer capture đổi hành vi MapPainter/scenario editor (legacy dựa vào mouseleave để dừng) | Capture chỉ bật cùng pointer API mới; legacy-only giữ lifecycle cũ; checklist MapPainter |
| rAF flush ghi lên snapshot draft cũ (stale-write, cùng lớp H2 adopt) | Flush qua `draftRef.current` |
| Rerender mỗi mousemove | rAF coalesce, một flush mỗi frame |
| Adapter legacy + pointer handler double-fire | Pointer thắng, legacy bị bỏ qua khi cả hai được truyền; test pin hai chiều |
| Click lệch toạ độ khi responsive / mobile tràn ngang | `canvasSize` thuần `min(760, container)`, không CSS min-width; ResizeObserver chỉ nối dây; breakpoint 924px suy ra rõ; acceptance 3 cỡ |
| Lỗi `environment` trần không biết về tab nào | `routeError` chốt → Traffic theo contract + drift test hai phía; unmapped chỉ footer |
| Tab unmount làm mất state cục bộ | `hidden` attr thay vì conditional unmount; render test pin |
| Source-scan test đỏ vì dời code | Contract path ở lại `DeploymentForm.tsx`; MissionPlacer wrapper giữ file; chỉ tách shell generic |
| Preview marker bị tưởng tương tác được | Chỉ authored overlay hit-test; legend nói rõ preview read-only |

## Thứ tự & ước lượng

Phase 0 (½ ngày) → Phase 1 (½–1 ngày) → Phase 2 (1 ngày) → Phase 3 (1½ ngày) → Phase 4 (1 ngày). Tổng ≈ 4½–5 ngày. Phase 0 là nền bắt buộc của cả 2 lẫn 3; Phase 1+2 vs Phase 3 độc lập sau đó, làm overlay trước để layout sắp quanh một map "đã biết nói".

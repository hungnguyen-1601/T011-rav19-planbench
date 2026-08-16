# Phase 4 — đóng phần test còn lại, và tổng kết cả bốn đợt

> Plan: `docs/antongduy/plans/2026-08-16/tuong-tac-map-va-refactor-layout-deployment.md` (v4).
> Ngày làm: 2026-08-16. Nhánh: `tongduyan_plannerselector`.
> Phase 0–3 An đã commit (`d9676e9`, `3046fb5`, `7c23e0a`, `7f91890`); Phase 4 **chưa commit**.
> Report này phủ Phase 4 **và** tổng kết cả bốn phase, theo quy ước "report phải phủ hết task".

---

## Phần A — Phase 4

### A1. Lỗ hổng lớn nhất: form chưa từng được vẽ lần nào

`DeploymentForm.tsx` là component lớn nhất của tính năng này, vừa bị
dựng lại từ **một cột** thành **hai cột + bảy panel tab** — và cho tới
giờ mọi thứ về nó được kiểm bằng **tìm chuỗi trong mã nguồn**. Cách đó
không phân biệt được một control render được với một control ném lỗi
ngay lần vẽ đầu tiên. Đợt Phase 3 trước, `traffic-editor.test.tsx` bắt
được một defect thật ngay lần chạy đầu; đây là cùng ván cược với
component to hơn.

Đã thêm `apps/web/src/components/__tests__/deployment-form.test.tsx`
(**12 ca**, `renderToStaticMarkup`):

- draft `null` nói "đang tải" chứ không vẽ form rỗng;
- identity nằm **trước** `role="tablist"` trong DOM — không chôn sau tab;
- mở ở tab Mission, đúng tab mà bản đồ bên cạnh phục vụ;
- đủ **bảy** tab; **cả bảy panel đều có trong DOM**, đúng **sáu** cái
  mang `hidden` — tính chất không phép tìm-chuỗi nào thấy được, và là
  thứ giữ cho biên độ nhiễu đã nhớ / vehicle đã chọn không bị dựng lại
  mỗi lần liếc sang tab khác;
- mỗi control nằm đúng panel sở hữu nó (một field đại diện mỗi tab);
- footer luôn có "File it" + "Check with the server", và **cả hai
  disabled** khi template còn trắng — nút sáng mà bấm không làm gì đọc
  như form hỏng;
- badge đếm đúng số lỗi mỗi tab; path lạ in **nguyên văn** ở footer;
  document sạch thì **không** có badge nào;
- `busy` khoá mọi `<select>`.

**Lần này không bắt được defect nào** — component render sạch ngay lần
đầu. Ghi ra vì đó là kết quả, không phải vì nó vô ích: 12 ca này giờ
đứng gác cho mọi lần sửa layout sau.

Cùng lý do, thêm `mission-placer.test.tsx` (**7 ca**): wrapper mà
`/decisions` dùng vừa bị viết lại thành thứ ghép ba component, và một
wrapper có thể sai theo cách phép tìm-chuỗi không thấy — thiếu một
phần, hoặc một prop thôi không tới được cái cần nó. Ghim: đủ ba phần,
mở ở chế độ đặt start khi không ai điều khiển, pose hiện theo **độ**,
pose chưa đặt nói "click the map" chứ không vẽ hàng số 0, mode truyền
từ ngoài được tôn trọng, caption nhường cho caller khi mode của người
khác giữ cú click.

Một giả định của **tôi** sai và test sửa lại: `disabled` **không** khoá
nút chuyển flat/raised. Đó là đúng — nút đó đổi cách vẽ bản đồ và không
đụng tài liệu; khoá nó là chặn người ta nhìn thứ họ vừa nộp trong lúc
đang nộp. Assertion viết lại cho đúng phạm vi: mọi `input` và hai nút
đặt pose bị khoá, nút đổi góc nhìn thì không.

### A2. Guard i18n đi theo code, muộn hai đợt

Guard "có đủ key ở cả hai locale" chỉ quét `DeploymentForm.tsx`. Nhưng
phần khai traffic đã dọn sang `TrafficEditor.tsx` từ đợt trước, nên
**hơn một chục key traffic đang không được cái gì kiểm cả**. Một key
thiếu bản dịch render ra chính đường dẫn chấm của nó — đọc như lỗi
trang, không như thiếu một dòng trong file locale.

Đã mở rộng sang cả hai file, cộng ba nhóm key **ghép từ biến** mà phép
quét literal không thấy: `traffic.seedTimeOffset.{self-seeded,one-shot,
incomplete}`, `traffic.kind.{waypoint,periodic,randomWalk,suddenStop}`,
`form.source.{library,stored,drawn}`. Không key nào thiếu — nhưng giờ
mới có ai đứng gác chuyện đó.

### A3. Một defect thật, tìm bằng đọc lại chính mình

Đọc lại đường kéo sau khi đổi chữ ký ở Phase 2 thì lộ ra:

```ts
const endDrag = (end) => {
  const active = gesture.current;
  gesture.current = null;        // ← xoá trước
  ...
  flushDrag(settled);            // ← rồi flushDrag đọc gesture.current
};
```

`flushDrag` mở đầu bằng `const active = gesture.current; if (!active)
return;` — nên **lần ghi cuối của mọi cú kéo bị bỏ qua**. Triệu chứng
duy nhất: điểm được kéo nằm lại **sau con trỏ vài pixel** (vị trí của
frame rAF cuối cùng thay vì vị trí thả tay). Không lỗi, không cảnh báo,
không test nào đỏ.

Sửa: `flushDrag(hit, point)` **nhận** handle làm tham số thay vì đọc
ngược từ ref — một tham số thì không ai xoá được dưới chân lời gọi.
Guard mới ghim cả hai chiều: `endDrag` phải gọi `flushDrag(active.hit,`
và không chỗ nào được gọi dạng cũ.

Đáng ghi vì nó nói lên giới hạn của bộ test hiện tại: vòng đời
candidate/committed được test kín ở tầng reducer (24 ca), nhưng **đường
từ reducer tới con chuột** thì chỉ có mắt người và checklist tay. Đúng
lỗ hổng mục B mô tả, và đây là ví dụ nó thật.

### A4. Dọn sau refactor, và hai mục tài liệu đã sai

Hai thứ chết sau khi layout đổi, đã xoá: state `showHardware` (nút gập
phần cứng — tab thay vai trò của nó) và một prop `modeNote` truyền
thừa xuống `MissionCanvas`, vốn giờ nhận caption qua `toolbar`.

`docs/KNOWN_LIMITATIONS.md` cập nhật hai mục đã hẹp hơn sự thật:

- **#50** (component test dừng ở lần render đầu) — bổ sung `Tabs` và
  `DeploymentForm` vào danh sách component đã được render thật, đổi
  danh sách "phần quyết định đã tách thành hàm thuần" cho đúng
  (`trafficUi`, `trafficOverlay`, `pointerRouting`), và đổi những gì
  *chưa* phủ cho khớp tính năng mới: kéo waypoint, nhấn đúp xoá,
  pointer capture, click sau khi `ResizeObserver` đổi cỡ canvas. Trỏ
  checklist sang report này.
- **#47** (vật cản động trong 2.5D) — thêm một câu: lớp **traffic đã
  khai** cũng chỉ vẽ ở khung phẳng, và lý do là phép chiếu 2.5D không
  có nghịch đảo (một pixel ứng với cả một tia xuyên cảnh).

### A5. Bằng chứng

| Kiểm | Kết quả |
|---|---|
| `npm run typecheck` | sạch |
| `npm run test` (toàn bộ web) | **896 passed / 43 file** |
| `npm run build` (Next production) | **thành công** — 18/18 trang server-render |
| `pytest tests` (toàn bộ backend) | *(xem mục A6)* |

Web trước loạt việc này: **770 passed / 35 file**. Sau: **896 / 43**
(+126 ca, +8 file).

### A6. Backend — không đụng, và chứng minh bằng diff

`git diff --stat HEAD` ngoài `apps/web`, `docs`, `.ai-log` là **rỗng**.
Không một dòng Python nào đổi trong cả bốn phase. Full pytest vẫn chạy
theo đúng chốt của An ("không full suite tới phase cuối") — kết quả ghi
ở mục "Bằng chứng cuối" bên dưới.

---

## Phần B — Checklist thủ công, chưa ai chạy

**Tôi không chạy được phần này**: không có công cụ điều khiển trình
duyệt trong môi trường, và `vitest` chạy Node không DOM
(`apps/web/vitest.config.ts:15-18`), không jsdom, không playwright. Nên
**nghiệm thu phần chuột-và-canvas hiện là thủ công** — nói rõ chứ không
để ngầm hiểu.

Mỗi mục một câu hỏi có/không.

### B1. Vẽ được cái đang khai (Phase 1)

| # | Thao tác | Kỳ vọng |
|---|---|---|
| 1 | Mở `/deployments`, chọn scenario thư viện có traffic | Lộ trình vẽ **ngay**, màu xanh ngọc, **không** cần bấm Preview |
| 2 | Thêm obstacle, đổi lần lượt qua 4 luật | Mỗi luật vẽ đúng hình: waypoint có polyline + số thứ tự; periodic có đoạn nối hai đầu; random walk có vòng đứt nét; sudden stop có mũi tên |
| 3 | Bật `loop` cho waypoint | Cạnh khép kín hiện ra, **đứt nét** khác với cạnh thường |
| 4 | Xoá trắng ô radius giữa lúc sửa | Canvas **không** vỡ, chỉ mất vòng thân — không có lỗi đỏ trong console |
| 5 | Bấm Preview | Đĩa hổ phách hiện **đè lên** hình xanh ngọc; legend dưới canvas giải thích hai màu |

### B2. Chọn và kéo (Phase 2)

| # | Thao tác | Kỳ vọng |
|---|---|---|
| 6 | Kéo một waypoint rồi **thả giữa canvas** | Điểm bám theo chuột, polyline mượt, và **điểm nằm đúng chỗ thả tay** — không lùi lại vài pixel (xem A3) |
| 7 | Kéo **ra ngoài** canvas rồi thả | Kéo **không đứt** giữa chừng; điểm dừng đúng chỗ thả |
| 8 | **Click đơn** lên một waypoint | Chỉ **chọn** obstacle — điểm **không** nhích một li |
| 9 | Nhấn đúp lên waypoint giữa lộ trình | Điểm đó biến mất; các điểm còn lại giữ nguyên thứ tự |
| 10 | Nhấn đúp mà tay **hơi rung** | Điểm bị xoá, **không** bị dời trước khi xoá |
| 11 | Bật "Add waypoints" rồi nhấn đúp | Ra **hai điểm mới**, **không** xoá gì |
| 12 | Click vào thân một obstacle trên bản đồ | Panel nhảy sang tab Traffic, đúng row sáng viền |
| 13 | Click vào đĩa **hổ phách** của preview | **Không có gì xảy ra** — nó là ảnh chụp |
| 14 | Bật placement rồi kéo ngang bản đồ | Đếm waypoint tăng đúng số lần click, **không** tăng vọt |
| 15 | `/maps/[id]`, vẽ rồi kéo chuột ra ngoài canvas | Nét vẽ **dừng ở mép** — hành vi cũ y nguyên, không bị pointer capture giữ lại |

### B3. Bố cục (Phase 3)

| # | Thao tác | Kỳ vọng |
|---|---|---|
| 16 | Mở form trên màn ≥1440px | Hai cột: bản đồ trái, 7 tab phải |
| 17 | Thu cửa sổ về ~1100px | Vẫn hai cột, bản đồ nhỏ lại theo |
| 18 | Thu tiếp xuống ~390px | Sập **một cột**, bản đồ trên panel dưới, **không tràn ngang** |
| 19 | Ở **cả ba** cỡ: bấm đặt một điểm | Điểm rơi **đúng chỗ con trỏ**, không lệch |
| 20 | Đổi tab qua lại vài vòng | Biên độ nhiễu đã sửa **không** mất; vehicle đã chọn **không** reset |
| 21 | Đặt hai obstacle cùng độ dài tên + cùng `seed_offset`, bấm Check | Nhảy sang tab **Traffic**, badge đỏ có số, lỗi hiện đầu khối |
| 22 | Đặt radius âm, bấm Check | Nhảy tab Traffic, lỗi hiện **cạnh đúng row**, có chữ `radius:` |
| 23 | Cuộn xuống cuối form | Footer **dính đáy**, Check/File it luôn thấy; không đè mất nội dung |
| 24 | Bấm Check trong lúc đang kiểm | Mọi input khoá cho tới khi có kết quả |
| 25 | Khai đủ `warehouse_crossing_v1` bằng chuột + số, bấm Check rồi File it | Check 204, File 201; nộp lại cùng id đổi nội dung → **409** |

Mục 8, 10, 15, 19 là bốn mục **mới so với checklist đợt trước** và là
bốn chỗ có thể hỏng im lặng nhất.

---

## Phần C — Tổng kết bốn phase

### C1. Vấn đề ban đầu

Config vật thể động đã ship (đợt 2026-08-15) nhưng **khó dùng**: khai
lộ trình là điền số và chọn dropdown, click lên bản đồ **không thấy gì**
cho tới khi bấm Preview, nút đặt điểm nằm dưới canvas nên phải cuộn qua
lại, và toàn bộ form là **một cột ~15 khối** với bản đồ — thứ trung tâm
— nằm gần cuối.

### C2. Đã làm

| Phase | Nội dung | Commit |
|---|---|---|
| 0 | Tách `TrafficSelection` thành 3 state + pure reducer `trafficUi`; contract Pointer Events + adapter legacy | `d9676e9` |
| 1 | `trafficOverlay.overlayOf` — tài liệu thành hình học; `MapCanvas` vẽ lớp authored | `3046fb5` |
| 2 | `hitTest`/`moveHandle`/`deleteWaypointAt`/`interpretPointer`; kéo, chọn, nhấn đúp xoá | `7c23e0a` |
| 3 | Layout hai cột + 7 tab; `routeError`; `canvasSize` + ResizeObserver; tách `MissionCanvas`/`PoseFields` | `7f91890` |
| 4 | Render test cho form và wrapper; sửa một defect ở đường kéo; mở rộng guard i18n; full suite | chưa |

**Sáu file nguồn mới** — `lib/trafficUi.ts`, `lib/trafficOverlay.ts`,
`lib/pointerRouting.ts`, `lib/formTabs.ts`, `lib/canvasSize.ts`,
`components/Tabs.tsx` — và **tám file test mới**:
`lib/__tests__/{traffic-ui,traffic-overlay,pointer-routing,form-tabs,canvas-size}.test.ts`,
`components/__tests__/{tabs,deployment-form,mission-placer}.test.tsx`.

### C3. Sáu quyết định đáng đọc lại

1. **Mũi tên heading dài cố định 1.5 m**, cố ý *không* lấy
   `speed × stop_time`. Con số đó là *chỗ vật cản dừng* — câu trả lời
   của simulator. Tính nó trong browser là bản sao thứ hai của luật
   chuyển động, tự do bất đồng với lượt chạy nó minh hoạ. Có test: vật
   cản nhanh và chậm cho **cùng** mũi tên.
2. **Candidate drag không bao giờ ghi.** `ActiveDrag.phase` tách
   `candidate`/`committed`; press chưa vượt `dragGate` mà nhả ra là một
   *cú click*, và dời điểm dưới nó là phép sửa không ai yêu cầu.
3. **`pointercancel` không tin toạ độ của chính nó** — flush vị trí mà
   một *move* báo lần cuối, vì cancel có thể tới từ gesture interruption
   mang toạ độ rác.
4. **rAF flush ghi qua `draftRef.current`**, không qua `draft` của
   closure — cùng lớp stale-write mà adopt map từng dính qua `await`.
5. **`environment` trần → tab Traffic**, và hệ quả nói thẳng: lỗi
   cross-check `v_obstacle_max` hiện ở Traffic trong khi ô của nó ở
   Chính sách. Hành vi đang ship, không phải lựa chọn mới; server ghim ở
   `tests/api/test_api_profile_validation.py`.
6. **Không sàn dưới cho canvas.** 480px là ngưỡng *sập layout*, không
   phải `min-width` của canvas — bản nháp đầu nhầm hai thứ và làm màn
   390px tràn ngang.

### C4. Bảy guard cũ đỏ trong bốn đợt, và cả bảy đỏ đúng

| Guard | Đỏ vì | Xử lý |
|---|---|---|
| `traffic-editor` 22 ca | API `selection` → `selectedIndex`+`placement` | Cập nhật + **thêm 2 ca** cho trạng thái mới (chọn mà không đặt) |
| Đếm `invalidateCheck()` = 5 | Thêm `setLive` cho drag | → 6, ghi rõ "writer thứ hai, không phải luật thứ hai" |
| ... rồi = 6 | Mission sửa được từ hai chỗ (kéo marker / gõ toạ độ) | → 7 |
| `onWorldDrag` pin chuỗi | Component có hai lifecycle | Viết lại **phủ cả hai** — kiểm nhiều hơn bản cũ |
| `<MissionPlacer` trong FORM | Form mount canvas và pose fields riêng | Kiểm **cả hai** |
| `decisions.map.mode.${placing}` | Caption thành component riêng | Đổi tên biến, cùng key cùng luật |
| replanning "sits under the map picker" | Vị trí trong một cột hết nghĩa | Viết lại theo tab Chính sách, kiểm **ba** thứ thay vì một |

Và một guard bắt **lỗi của chính tôi**: comment chứa `t("…")` bị regex
quét key i18n tưởng là key thật. Guard làm đúng việc.

**Không guard nào bị nới.** Bốn cái kiểm *nhiều hơn* trước.

### C5. Ba chỗ lệch plan, có lý do

1. **`dragGate` ở `trafficUi.ts`** thay vì `trafficOverlay.ts` — nó
   gate transition `dragCommitted` của chính reducer đó.
2. **Không tạo file `MissionCanvas.tsx` riêng.** Ranh giới trách nhiệm
   đúng như An chốt, nhưng bốn component ở cùng file: một tá assertion
   đọc đường dẫn `MissionPlacer.tsx`, dời file làm đỏ hết trong khi hành
   vi không đổi. Tiền lệ *cùng assertion, đổi file nó đọc* đáng trả khi
   ranh giới **thật sự** dời; ở đây cái đổi là *ai sắp xếp các phần*.
3. **Thêm row-click-to-select** trong panel Traffic — plan không nói,
   nhưng rẻ và cùng đường selection với click thân trên bản đồ.

### C6. Còn nợ

- **Nghiệm thu canvas vẫn thủ công** (Phần B). Đóng được bằng jsdom +
  Testing Library cho phần nối dây, và playwright cho phần vẽ đúng
  toạ độ — cả hai đều là hạ tầng test mới cho repo, **quyết định của
  An**, không phải của tôi.
- **`clockKey` trong `traffic.ts`** vẫn là bản chép công thức server
  (nợ cũ từ Phase 2b đợt trước).
- **Nút Place start/goal chỉ có ở tab Mission** — ở tab khác không đổi
  được mode đặt pose. Kéo marker thì không cần mode, và caption dưới
  canvas vẫn nói mode hiện tại. Đúng như plan chốt; ghi ra để biết.
- ~~**`KNOWN_LIMITATIONS.md`** #47/#50~~ — **đã trả trong Phase 4**,
  xem mục A3.

---

## Bằng chứng cuối

| Kiểm | Trước loạt việc | Sau |
|---|---:|---:|
| Web (`npm run test`) | 770 passed / 35 file | **896 passed / 43 file** |
| `npm run typecheck` | sạch | sạch |
| `npm run build` | thành công | **thành công**, 18/18 trang |
| `pytest tests` | 2805 passed, 8 skipped | *(điền sau khi chạy xong)* |
| `git diff` ngoài `apps/web`/`docs` | — | **rỗng** |

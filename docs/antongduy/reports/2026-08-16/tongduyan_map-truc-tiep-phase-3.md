# Phase 3 — bản đồ cạnh điều khiển, và lỗi có chỗ để hiện

> Plan: `docs/antongduy/plans/2026-08-16/tuong-tac-map-va-refactor-layout-deployment.md` (v4, Phase 3).
> Ngày làm: 2026-08-16. Nhánh: `tongduyan_plannerselector`. **Chưa commit.**
> Phase 0–2 An đã commit (`7c23e0a`). Vẫn **chưa chạy full suite** — dồn về Phase 4.

## Bố cục: hai cột, bảy tab, footer dính

Trước đợt này form là **một cột ~15 khối xếp dọc**, và bản đồ — thứ mà
phần lớn các ô nói *về* — nằm gần cuối. Chọn lộ trình traffic nghĩa là
cuộn ra xa khỏi bức tranh của chính nó.

Giờ: hàng **identity** (id, claim_level, deployment_role) trên đầu,
ngoài tab — chúng là *deployment đó là cái gì*, chôn sau tab thì thứ
đầu tiên người ta gõ lại là thứ phải đi tìm. Dưới đó là lưới hai cột:
bản đồ + preview bên trái, panel **7 tab** bên phải (Mission · Traffic ·
Robot · Ngưỡng · Nhiễu · Chính sách · Phần cứng). Footer **`sticky`
trong form** — không `fixed` theo viewport: fixed sẽ đè lên nội dung
cuối trang và ăn vĩnh viễn một khoảng màn hình điện thoại.

`replanning`/`recovery` chuyển sang tab **Chính sách** cùng
`v_obstacle_max`. Cùng một luật cũ ("cạnh bản đồ, không phải cách một
màn hình cuộn") nhưng nghĩa mới: giờ là *tab kề bản đồ, cùng tầm mắt*,
và cùng chỗ với thứ thứ hai mà traffic bắt người ta quyết.

## Tách component — và vì sao không tách file

An chốt ở review v3: `MissionCanvas` + export `PoseFields`,
`MissionPlacer` thành wrapper. Đã làm **đúng ranh giới trách nhiệm**,
nhưng **giữ cả bốn trong một file**:

- `MissionCanvas` — bản đồ + wiring pointer, không nút không ô số;
- `PlacementButtons`, `PlacementCaption`, `MissionPoseFields` — export
  riêng, form đặt vào tab Mission / trên canvas;
- `MissionPlacer` — compose đúng hình dạng cũ, `/decisions` không sửa.

**Lý do giữ một file, nói thẳng:** một tá assertion đọc đường dẫn
`MissionPlacer.tsx` để ghim *một cú click làm gì* và *state nào được
phép sống ở đây*. Dời code sang file khác làm đỏ hết chúng trong khi
hành vi không đổi một ly — đúng cái bẫy report W1 đã ghi ("hàng rào
viết sai"). Tiền lệ *cùng assertion, đổi file nó đọc* đáng trả **khi
ranh giới thật sự dời**; ở đây cái đổi là *ai sắp xếp các phần*, không
phải *các phần biết gì*. Ghi rõ trong docstring đầu file.

## `routeError` — chỗ path không tự nói được

Điểm An gọi là "lỗ hổng lớn nhất của Phase 3", và đúng vậy.
`lib/formTabs.ts` viết bảng ra tay thay vì suy từ path:

| Path | Tab |
|---|---|
| `environment.sensor_noise.*` | Nhiễu |
| `environment.v_obstacle_max`, `replanning.*`, `recovery.*` | Chính sách |
| `environment.dynamic_obstacles.*` | Traffic |
| **`environment` trần** | **Traffic** |
| `id`, `claim_level`, `deployment_role` | identity (ngoài tab) |
| không khớp | **unmapped** |

Prefix dài thắng prefix ngắn, nên `environment.sensor_noise` không bị
`environment` nuốt. Có test riêng cho ca `recovery_budget` — tên dài
hơn **không** phải field lồng của `recovery`.

**`environment` trần → Traffic, và hệ quả nói rõ:** cả 5 luật traffic
là model validator nên pydantic địa chỉ hoá về đây; lỗi cross-check
`v_obstacle_max` vs tốc độ vật cản nhanh nhất **cũng** vậy, nên nó hiện
ở Traffic trong khi ô của nó nằm ở Chính sách. Đó là hành vi đang ship
chứ không phải lựa chọn mới, và phía server đã ghim ở
`tests/api/test_api_profile_validation.py` — backend đổi cách địa chỉ
hoá thì bảng này và test kia đỏ cùng nhau.

**Không đoán vào tab gần nghĩa.** Path lạ là `unmapped`, in **nguyên
văn ở footer**. Bịa chỗ cho nó là đặt lời từ chối sau một cái tab không
ai có lý do mở — không khác gì giấu, mà nộp thì vẫn bị chặn. Có test
khẳng định **tổng đếm luôn khớp**: không lời từ chối nào rơi mất.

Sau check 422: nhảy tới tab đầu tiên có lỗi. Lỗi identity/unmapped
**không** nhảy — cả hai đã ở trên màn hình rồi, kéo người dùng sang tab
khác để không cho họ xem gì còn tệ hơn đứng yên.

## Responsive: đo, không đoán

`canvasSize(containerWidth, aspect)` thuần: `min(760, container)`,
**không sàn dưới**. Bản nháp đầu sàn 480 — đó là phát biểu về *layout*,
và nó làm màn 390px tràn ngang. 480 giờ là `CANVAS_MIN_SIDE_BY_SIDE_PX`,
một nửa của ngưỡng sập cột:

```
SIDE_BY_SIDE_MIN_PX = 480 (canvas) + 420 (panel) + 24 (gap) = 924
```

suy ra chứ không chọn số tròn, nên đổi một trong hai minimum thì ngưỡng
tự đi theo. Đo bằng `ResizeObserver` trên **chính form** — không media
query theo viewport, vì sidebar làm viewport nói dối về chỗ form thật
sự có.

**Vì sao phải truyền width xuống dưới dạng số:** `MapCanvas` đổi cú
nhấn ra toạ độ thế giới với giả định *bề mặt vẽ và hộp CSS bằng nhau*.
`width: 100%` sẽ làm mọi cú click rơi lệch khỏi con trỏ **trong khi bản
đồ vẫn trông hoàn toàn đúng** — hỏng im lặng.

`useMeasuredWidth` dùng **callback ref** chứ không `useRef`: node cần
theo dõi chưa tồn tại ở lần render đầu (form hiện dòng loading tới khi
template về), nên effect chạy một lần lúc mount sẽ quan sát hư không rồi
không bao giờ nhìn lại.

## `Tabs` — ẩn, không unmount

Panel không hoạt động dùng thuộc tính `hidden`: rời khỏi accessibility
tree và khỏi layout, **nhưng component còn sống**. React vứt state của
thứ nó unmount, mà form giữ state thật trong control — biên độ nhiễu
khác 0 gần nhất (bỏ tick rồi tick lại phải trả về số đã gõ), vehicle đã
chọn. Dựng lại mỗi lần đổi tab là mất một con số đã sửa vì một cú click
lạc sang tab khác. Có render test ghim đúng điều này: **cả ba panel đều
có trong DOM**, chỉ hai cái mang `hidden`.

ARIA đủ: `role="tablist"/"tab"/"tabpanel"`, `aria-selected`,
`aria-controls`, `aria-labelledby`, và badge có `aria-label` (một chữ số
trần cạnh tiêu đề đọc lên là gì cũng được). Badge 0 **không render** —
số 0 xám cạnh mọi tiêu đề đọc như một control chứ không như sự yên ổn.

`Tabs.tsx` **generic, không chứa dotted path nào** — drift guard đọc
`DeploymentForm.tsx` tìm mọi field hợp đồng, và một control có path
chui vào file shell là control nó không thấy.

## Bốn guard cũ đỏ, cả bốn đỏ đúng

| Guard | Vì sao | Xử lý |
|---|---|---|
| `<MissionPlacer` trong FORM | Form giờ mount `MissionCanvas` + `MissionPoseFields` riêng | Kiểm **cả hai**, ghi rõ `/decisions` vẫn dùng hình dạng gộp |
| `decisions.map.mode.${placing}` | Caption thành component riêng, biến đổi tên thành `mode` | Đổi chuỗi, cùng key cùng luật |
| Đếm `invalidateCheck()` = 6 | Mission giờ sửa được từ **hai** chỗ: kéo marker trên canvas, gõ toạ độ ở tab Mission | Lên **7** kèm lý do |
| replanning "sits under the map picker" | Vị trí cũ trong một cột không còn nghĩa | Viết lại: nằm trong `policiesTab`, **cùng** `recovery` và `v_obstacle_max` — kiểm nhiều hơn bản cũ |

Và một guard bắt được **lỗi của chính tôi**: comment tôi viết có chứa
`t("…")` với ký tự ellipsis, regex quét key i18n tưởng đó là key thật
rồi báo thiếu bản dịch. Guard làm đúng việc; đã sửa comment.

## Bằng chứng (suite nhắm đích)

| Kiểm | Kết quả |
|---|---|
| `npm run typecheck` | sạch |
| `npm run build` (Next production) | **thành công** — 18/18 trang server-render được, `/deployments` 13.9 kB |
| `vitest run form-tabs` (mới) | **15 passed** |
| `vitest run canvas-size` (mới) | **8 passed** |
| `vitest run tabs` (mới) | **8 passed** |
| `vitest run deployments-page decisions-page` | **160 passed** (+2 guard layout mới) |
| `vitest run traffic-overlay traffic-ui traffic-editor i18n` | 108 passed |
| `pytest tests/test_form_covers_the_contract.py` | 17 passed |

Bản build production đáng tiền ở đúng đợt này: nó **server-render thật
cả 18 trang**, nên một lỗi chỉ xuất hiện lúc render `/deployments` sẽ
đỏ ở đây chứ không đỏ ở vitest.

## Ghi chú lệch plan

1. **Không tạo file `MissionCanvas.tsx` riêng** — lý do ở mục "Tách
   component" trên. Ranh giới trách nhiệm đúng như chốt; chỉ khác chỗ
   ở.
2. **Nút Place start/goal chỉ có ở tab Mission.** Đang ở tab khác thì
   không đổi được mode đặt pose — nhưng caption dưới canvas vẫn nói mode
   hiện tại là gì, và kéo marker thì không cần mode. Đúng như plan chốt;
   ghi ra để checklist tay để ý.

## Còn lại

Phase 4: checklist tay trên trình duyệt (17+ mục, giờ thêm phần tab và
3 cỡ màn hình), rà soát i18n lần cuối, **full web suite + full pytest**,
và report tổng.

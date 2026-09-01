# Báo cáo — Đợt 2.3: Scenario Editor tùy chỉnh

> **Ngày:** 2026-08-06
> **Plan nguồn:** `docs/antongduy/plans/2026-08-05/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`, mục **2.3**
> **Nhánh:** `tongduyan`
> **Tiền đề:** 2.1 (P05) và 2.2 (P03) đã xong cùng ngày; 2.2 đã commit ở
> `b502b43`.
> **Phạm vi:** hết Đợt 2. Đợt 3 (F09 + F05) chưa làm.

---

## 1. Vấn đề đang giải

P03 đo xong và cho ra một kết luận rất cụ thể: bộ scenario hiện tại
**rỗng ở khoảng giữa** — 5 scenario ở độ khó 0.000, 4 ở 1.000, đúng 1
nằm giữa. Nghĩa là với hai stack đều khá, benchmark hiện tại hầu như
không phân biệt được ai hơn ai: hoặc cả hai qua hết, hoặc cả hai chết
hết.

Cách sửa duy nhất hợp lệ là **viết thêm scenario** — không phải sửa
cache. Nhưng trước đợt này không có đường nào để làm việc đó ngoài viết
Python trong `scenarios.py` rồi deploy lại.

Đợt 2.3 mở đường đó, và mở sao cho nó không phá hai thứ vừa dựng xong ở
2.1 và 2.2.

---

## 2. Ba ranh giới mà editor không được vượt

Đây là phần đáng bàn nhất của đợt này. Một trình sửa scenario là một
trình sửa **điều kiện benchmark**, nên câu hỏi quan trọng không phải "vẽ
được gì" mà là "người vẽ **không** được quyết cái gì".

### 2.1. Trình duyệt không được tự kết luận scenario hợp lệ

Mọi phán quyết đến từ `POST /scenarios/validate`, và endpoint đó chạy
**đúng** `SimulationEngine.load_scenario` mà `create`/`update` chạy. Nếu
frontend tự kiểm trước, sớm muộn nó sẽ chấp nhận thứ engine từ chối, và
người dùng gặp luật thật lần đầu tiên đúng lúc bấm Lưu.

Có test khẳng định hai bên không thể lệch nhau: cùng một payload xấu,
`validate` trả `valid=false` **và** `POST /scenarios` trả `422`.

Kèm theo: **mọi thay đổi đều xóa phán quyết cũ** (`setValidation(null)`).
Một nhãn "hợp lệ" còn đứng đó cạnh hình vẽ đã bị dời chính là lỗi mà cả
luồng này sinh ra để chặn.

### 2.2. Trình duyệt không được tự tính chuyển động

Vật cản động được vẽ tại vị trí do `POST /scenarios/preview` trả về, tính
bằng `position_at` — **đúng hàm simulator dùng**.

Nếu cài lại quy luật chuyển động trong TypeScript thì có hai bản, và hai
bản sẽ trôi khỏi nhau. Hậu quả không phải "hình hơi lệch": người vẽ sẽ
đặt điểm xuất phát tránh một vật cản mà lúc episode chạy thật nó nằm chỗ
khác. **Một preview mâu thuẫn với episode tệ hơn không có preview.**

Vì vậy `MapCanvas` nhận `ObstacleMarker` (tên, bán kính, **vị trí**) chứ
không nhận `DynamicObstacle` + `previewTime` như plan phác. Đây là khác
biệt có chủ ý so với plan — xem mục 6. `previewTime` vẫn là prop, dùng
để **ghi nhãn thời điểm** lên hình: hai vật cản không gặp nhau ở t=0 vẫn
có thể gặp nhau ở t=7, và một ảnh chụp không có đồng hồ mời người đọc
hiểu nhầm nó là cả episode.

### 2.3. Người vẽ không được quyết nhóm đánh giá và độ khó

- `ScenarioResource` thêm `split` **chỉ đọc**, resolve từ
  `scenario_protocol.json`. Gửi kèm `"split": "dev"` trong body cũng vô
  hiệu — có test cho đúng cái request đó, vì đó là request mà một người
  không hài lòng với kết quả sẽ thử.
- Scenario tạo trong app luôn `unassigned`, và trang editor **nói thẳng**
  điều đó cùng lý do, thay vì để một ô trống trông như thiếu sót.
- Độ khó không hiện trong danh sách scenario: scenario chưa ai hiệu chuẩn
  thì **không có** độ khó (P03), và bịa một giá trị tạm cho scenario vừa
  tạo đúng là kiểu phỏng đoán mà P03 sinh ra để thay thế.

---

## 3. Đã làm gì

### 3.1. Backend

| Thay đổi | Ghi chú |
|---|---|
| `POST /scenarios/preview` (mới) | `{map_id, scenario, time, seed}` → vị trí vật cản động + `valid`/`errors`. `time < 0` → 422. |
| `ScenarioResource.split` | Chỉ đọc, resolve từ protocol file. |
| `validate` | Giữ nguyên hành vi, thêm docstring nêu rõ nó là **cùng** phép kiểm với `create`/`update`. |

Preview trả **cả vị trí lẫn lỗi**: người đang sửa một bố cục sai vẫn cần
nhìn thấy bố cục đó. Từ chối vẽ chỉ khiến việc sửa khó hơn.

### 3.2. `MapCanvas` — dùng lại, không nhân bản

Thêm ba prop: `staticObstacles` (hình học thuần, canvas tự vẽ được),
`dynamicObstacles: ObstacleMarker[]`, `previewTime`. Hình chữ nhật và
hình tròn đều vẽ; vật cản động tô ấm và có viền, vì **vị trí của chúng là
sự thật về một thời điểm và một seed**, không phải về bản đồ.

Thiết kế này cũng chính là cái Replay (F08, Đợt 4) cần: chỗ đó
`previewTime = playhead` và marker đến từ episode đã lưu.

### 3.3. Frontend

- `/scenarios` — danh sách: tên, map, **badge nhóm đánh giá**, số vật
  cản tĩnh/động, xóa, vào sửa.
- `/scenarios/[id]` — editor (`new` là tạo mới):
  - thông tin chung: tên, mô tả, map, timeout, sai số đích, bán kính robot;
  - công cụ đặt: điểm xuất phát / đích / vật cản tròn / vật cản chữ nhật
    (2 góc) / waypoint. **Chế độ hiện rõ bằng chữ** — người vẽ phải biết
    cú bấm tiếp theo sẽ làm gì, chứ không đoán qua phím bổ trợ;
  - heading nhập bằng độ;
  - danh sách vật cản tĩnh/động, sửa tên, bán kính, tốc độ, độ lệch seed;
  - thanh trượt thời gian preview;
  - Kiểm tra hợp lệ / Lưu.
- Vào sidebar (`nav.scenarios`, yêu cầu đăng nhập), i18n đủ Anh–Việt.

### 3.4. Một chi tiết dễ bỏ qua: độ lệch theo seed

Vật cản động tạo mới mặc định `seed_time_offset = 10`, **không phải 0**,
và UI cảnh báo khi có vật cản để 0.

Lý do: với offset 0, mọi seed lặp lại đúng một luồng giao thông. Benchmark
30 seed khi đó vẫn chạy 30 episode, vẫn ra bảng số, và báo **phương sai
bằng 0** — một con số trông rất thuyết phục nhưng là hiện tượng giả. Đây
là cái bẫy dễ dính nhất khi tự vẽ scenario, nên nó được đặt mặc định
đúng và được nói ra, chứ không để người dùng tự phát hiện sau 30 episode.

### 3.5. Nối editor vào thang độ khó

Scenario tự tạo **không** nằm trong thư viện, nên
`scripts/calibrate_difficulty.py` cũ không đo được nó — mà DoD của plan
lại yêu cầu "chạy calibration, xác nhận difficulty được sinh".

Thêm `--scenario-file`: nhận bundle `{map, scenario}` xuất từ API (chấp
cả dạng resource `{map_data: ...}` / `{scenario: ...}` vì người dùng
thường dán hai output curl). Scenario từ bundle được đo bình thường và
**vào cache với split `unassigned`** — đo độ khó không phải cửa sau vào
tập dev.

---

## 4. Test

**`tests/api/test_api_scenario_editor.py` — 20 test**, chia theo đúng ba
ranh giới ở mục 2:

- *Người vẽ không được quyết gì*: scenario mới là `unassigned`; gửi kèm
  `split` bị bỏ qua; scenario mới không có độ khó; **sửa scenario không
  đổi `conditions_checksum` của benchmark đã chạy** (và test cũng khẳng
  định lần sửa đó thật sự có hiệu lực, để không thành test rỗng nghĩa).
- *Hợp lệ là việc của engine*: chấp nhận bố cục tốt; từ chối start trong
  tường; từ chối start trong **vật cản vừa vẽ**; `validate` và `save`
  cho cùng kết luận; scenario qua validate thì lưu được.
- *Preview đúng thứ sẽ chạy*: vị trí **khớp `position_at`** gọi trực
  tiếp; đổi thời điểm thì vật cản dịch chuyển; đổi seed thì thời điểm
  khác; `seed_time_offset = 0` thì mọi seed giống hệt nhau (đóng đinh
  đúng cái artefact ở mục 3.4); scenario sai vẫn được vẽ kèm lỗi; thời
  gian âm bị 422.
- *Vòng đời*: update giữ id và chạy lại đúng validation; delete; và
  **scenario tự vẽ chạy benchmark thật được**, report ghi `unassigned`.

**`tests/test_difficulty.py` — thêm 5 test** cho `--scenario-file`: đọc
được cả hai dạng JSON, thiếu một nửa thì báo lỗi, scenario từ bundle
được hiệu chuẩn với split `unassigned`, và không bị từ chối là "scenario
lạ".

**`apps/web/src/app/__tests__/scenario-editor.test.tsx` — 41 test:**
validate luôn qua backend, phán quyết bị xóa khi sửa, preview có gửi
seed, canvas nhận vị trí chứ không nhận quy luật chuyển động, cả hai
loại vật cản tĩnh được vẽ, editor không gửi `split`, cảnh báo
`seed_time_offset = 0`, có mục sidebar cần đăng nhập, type không còn
`unknown[]`, i18n đủ hai ngôn ngữ và giữ đủ placeholder.

**Kết quả chạy:**

```
pytest (toàn bộ)                        1342 passed, 4 skipped (9:10)
  tests/api/test_api_scenario_editor.py 20 passed
  tests/test_difficulty.py              50 passed
ruff check .                            All checks passed
ruff format --check                     sạch
npx tsc --noEmit (apps/web)             sạch
npx vitest run (apps/web)               396 passed / 2 file fail có sẵn
```

Baseline sau Đợt 2.2 là 1317 passed; +25 test backend, +41 test frontend.

Hai fail frontend **có sẵn từ trước và không liên quan**:
`dashboard-page.test.tsx` so đường dẫn kiểu POSIX trên Windows,
`assistant-page.test.tsx` đọc `src/app/models/page.tsx` chưa tồn tại.

---

## 5. Kiểm chứng end-to-end

Chạy thật toàn bộ luồng plan mô tả (tạo → validate → preview → lưu →
benchmark → calibration), qua API thật:

```
map 570e7bf18199 (14 x 9 m, tự dựng)
validate -> {'valid': True, 'errors': []}
preview t=5 seed=3 -> [{'name': 'crosser', 'radius': 0.35,
                        'position': {'x': 9.0, 'y': 6.108}}]
save -> 201  scenario 7b070bdaf35b  split: unassigned
benchmark split: unassigned  protocol: 1.0.0
  astar+dwa      success=0.800
  rrtstar+dwa    success=0.600
```

Rồi hiệu chuẩn chính scenario đó, 30 seed:

```
editor_pillar_crossing   unassigned   difficulty=0.167   ci95 (0.07, 0.34)
```

Ba điều đáng đọc:

1. **Vòng lặp khép kín.** Một scenario vẽ ra từ đường của editor chạy
   benchmark được, và **lên được thang độ khó** — đúng thứ mà giới hạn
   số 1 của báo cáo P03 cần để sửa.
2. **Nó rơi gần đúng chỗ đang thiếu.** 0.167 nằm ngay dưới mép khoảng
   giữa (0.2–0.8); trong 10 scenario thư viện chỉ có `crossing_obstacle`
   (0.267) ở vùng này. Một scenario "hành lang có cột + xe cắt ngang"
   dựng trong vài phút đã tiến gần vùng trống hơn 9/10 scenario có sẵn —
   nghĩa là lấp dải bằng editor là việc làm được, không phải mong muốn.
3. **Đo xong vẫn `unassigned`.** Biết nó khó bao nhiêu không làm nó thành
   scenario dev hay holdout.

Scenario và cache của lần kiểm chứng này để ở scratch, **không** commit:
cache trong repo là thang đo của 10 scenario thư viện, và trộn một
scenario nằm trong database vào đó sẽ tạo một cache mà `git clone` không
tái tạo được.

---

## 6. Chỗ làm khác plan, và vì sao

**Plan phác `MapCanvasProps` nhận `dynamicObstacles: DynamicObstacle[]` +
`previewTime`**, tức canvas tự tính vị trí từ quy luật chuyển động.

Đã làm khác: canvas nhận **vị trí đã tính** (`ObstacleMarker`), còn
`previewTime` giữ lại để ghi nhãn thời điểm. Lý do ở mục 2.2 — làm theo
plan sẽ đặt một bản cài đặt thứ hai của quy luật chuyển động vào trình
duyệt, ngược với luật "không có logic simulator trong UI" mà `MapCanvas`
đã ghi trong docstring từ đầu.

Ý định của plan (dùng lại canvas cho cả editor lẫn replay) **vẫn giữ
nguyên** và vẫn chạy: replay sẽ truyền `previewTime = playhead` cùng
marker lấy từ episode đã lưu.

Hai chỗ cắt theo đúng "Không thuộc phạm vi MVP" của plan: không kéo chuột
xoay heading, không version history.

---

## 7. Definition of Done (plan mục 2.3)

- [x] CRUD hoạt động (list / create / update / delete qua UI và API).
- [x] Validation dùng engine thật — và là **cùng** phép kiểm với save.
- [x] Map preview hoạt động, gồm cả vật cản động theo thời gian và seed.
- [x] Scenario mới không tự vào dev hoặc holdout (`unassigned`, không
      đặt được từ request).
- [x] Không đổi checksum benchmark cũ — có test sửa scenario rồi so
      `conditions_checksum` của report đã lưu.
- [x] Component visualization tái sử dụng được (`MapCanvas` + prop mới,
      dùng lại được cho replay).
- [x] Có test frontend và backend.

Phạm vi MVP plan liệt kê (11 mục): danh sách ✔, tạo ✔, start ✔, goal ✔,
heading ✔, vật cản tĩnh ✔, vật cản động ✔, waypoint ✔, validate bằng
engine ✔, preview trên map ✔, lưu ✔.

---

## 8. Giới hạn đã ghi vào `KNOWN_LIMITATIONS.md` (mục 127–135)

1. Engine chỉ trả **lỗi đầu tiên**; `errors[]` hiện luôn có 0 hoặc 1 phần tử.
2. Form chỉ tạo được vật cản động kiểu `waypoint`; các kiểu khác sửa được
   thuộc tính nhưng không đổi được quy luật chuyển động.
3. Không kéo chuột xoay heading (nhập số).
4. Không có version history — `PUT` ghi đè, không hoàn tác được.
5. Không có khóa khi hai người cùng sửa; `PUT` cuối thắng.
6. Preview là **một seed, một thời điểm** — không thấy được vùng vật cản
   quét qua trên toàn bộ tập seed.
7. Mỗi lần kéo thanh trượt là một request (không debounce).
8. Hiệu chuẩn scenario tự tạo là **thao tác tay** qua `--scenario-file`;
   không có nút trong app.
9. Không có đường đưa scenario tự tạo vào thư viện, nên
   `CURRICULUM_ORDER` và cache độ khó mặc định không thấy nó.

---

## 9. File đã đổi

**Mới:**
- `apps/web/src/app/scenarios/page.tsx`
- `apps/web/src/app/scenarios/[id]/page.tsx`
- `apps/web/src/app/__tests__/scenario-editor.test.tsx`
- `tests/api/test_api_scenario_editor.py`

**Sửa:**
- `apps/api/planbench_api/schemas.py`, `routers/scenarios.py`
- `apps/web/src/components/MapCanvas.tsx`
- `apps/web/src/lib/types.ts`, `navigation.ts`
- `apps/web/src/lib/i18n/locales/en.json`, `vi.json`
- `scripts/calibrate_difficulty.py` (`--scenario-file`)
- `tests/test_difficulty.py`
- `docs/API_CONTRACT.md`, `docs/KNOWN_LIMITATIONS.md`

---

## 10. Bước tiếp theo

Đợt 2 xong cả ba mục. Theo plan tiếp là **Đợt 3: F09 (biểu đồ + export
Markdown) và F05 (sửa metrics engine)** — cũng là chỗ mà độ khó, CI,
p-value và chênh lệch tổng quát hóa của các đợt trước lần đầu hiện lên
thành hình cho người dùng thấy.

Một việc không thuộc code nhưng nên làm sớm: **dùng chính editor này
viết vài scenario lấp khoảng 0.2–0.8**, rồi chạy lại
`calibrate_difficulty.py` để xác nhận `midrange_count` tăng. Lần kiểm
chứng ở mục 5 cho thấy việc đó khả thi.

# Phase 2b — khai vật cản động ngay trên form deployment

> Plan: `docs/antongduy/plans/2026-08-15/config-vat-the-dong-tren-form-deployment.md` (v5, Phase 2b).
> Ngày làm: 2026-08-15. Nhánh: `tongduyan_plannerselector`. **Chưa commit.**

Hai việc trong một đợt: đóng defect lockstep (điểm quyết #4), rồi dựng
TrafficEditor.

## Phần 1 — điểm quyết #4: chốt phương án thứ ba

An approve phương án (a) — băm toàn bộ tên. Khi bắt tay làm, khảo sát lộ
ra một cái giá **không có trong hai lựa chọn tôi đưa lúc đề xuất**:

`tests/golden/dwa_trajectories.json` có 7 ca, thì **5 ca chạy scenario có
traffic lệch theo seed** — `bidirectional_corridor` (offset 16),
`dynamic_warehouse` (14/28), `sudden_stop` hai lần (offset 4). Đổi
`_seed_time_shift` làm quỹ đạo đổi, golden đỏ, và cách duy nhất cho nó
xanh lại là regenerate. Nhưng file đó tồn tại để chứng minh P2 tách
`dwa_core` không đổi gì, và docstring của nó viết thẳng: *"To regenerate
— only ever with a reason, and the reason is never 'the test went red'"*.
Regenerate là **phá bằng chứng**, không phải cập nhật fixture.

Nên tôi dừng lại hỏi thay vì làm tiếp. An chốt phương án thứ ba:

**Chặn khoá đồng hồ trùng ngay lúc nạp profile, không đổi cách băm.**

- `clock_key(obstacle)` được **đưa ra khỏi chỗ ẩn** trong `dynamic.py`,
  và `_seed_time_shift` gọi chính nó. Validator kiểm **đúng cái khoá
  thật**, không phải một bản chép lại công thức — hai bên không thể trôi
  khỏi nhau.
- `EnvironmentSpec._validate_obstacles` từ chối hai vật cản **có
  `seed_time_offset > 0`** mà trùng khoá, kèm thông điệp nói rõ tên duy
  nhất không cứu được và cách sửa là đổi `seed_offset`.
- Chỉ so những con **thực sự lấy head start**: ở offset 0 thì shift bằng
  0 với tất cả, và `random_walk` — luật duy nhất được phép ở 0 — vẫn đọc
  seed qua hướng đi.

**Sửa hai chỗ backend tự mô tả sai** (nguồn của cả hiểu lầm này):
docstring `seed_time_offset` nói "a hash of (seed, name)", và thông điệp
từ chối trùng tên nói tên được trộn vào hash. Cả hai giờ nói đúng: khoá
là `seed_offset` cộng **độ dài** tên. Luật tên-duy-nhất vẫn còn nhưng
với lý do thật của nó — trace, snapshot và lời từ chối đều gọi vật cản
bằng tên.

**Cái giá của phương án này, nói rõ:** đổi tên không gỡ được lockstep,
người dùng phải đổi `seed_offset`. UI nói điều đó ở chú thích cạnh ô.

Sáu test mới trong `TestTwoObstaclesMustNotShareAClock`, trong đó có một
test ghim **chính defect** (`cart` và `rack` cùng vị trí ở mọi seed) —
không có nó thì luật kia đọc như một luật về chính tả.

## Phần 2 — TrafficEditor

### Lớp logic thuần: `apps/web/src/lib/traffic.ts`

Web suite chạy Node, không DOM — click không test được, reducer thì có.
Ràng buộc đó đẩy toàn bộ phần nghĩ được ra khỏi component:

| Hàm | Việc |
|---|---|
| `trafficOf` | Chỗ **duy nhất** narrow `ProfileDraft` (cố ý loose) thành `DynamicObstacle[]` |
| `blankMotion`, `changeMotionKind` | Dựng motion mới theo canonical shape; đổi kind **vứt sạch** field kind cũ, chỉ mang theo `speed` khi cả hai luật đều có |
| `placeOnMotion` | Click lên bản đồ vào đúng field mode gọi tên; `sudden-stop-heading` chỉ suy ra góc, **không lưu điểm** |
| `cycleSeconds`, `suggestSeedTimeOffset` | Ba nhánh waypoint (ping-pong ×2, loop + cạnh đóng, một-lần = null), periodic = period, sudden_stop = stop_time, random_walk = null |
| `nextSeedOffset` | Default tránh trùng khoá đồng hồ |
| `previewRequestOf` | Dựng `ScenarioPreviewRequest`, bám `scenario_for` từng field |
| `snapshotsOf` | Chuyển preview sang `ObstacleSnapshot` cho khung 2.5D |

**Không hàm nào phán tài liệu đúng/sai.** Verdict vẫn của
`POST /task-profiles/validate`. Ngoại lệ duy nhất là `clockKey` chép lại
công thức server — và nó chỉ dùng để **chọn default** cho vật cản mới,
không dùng để kết luận tài liệu cũ sai; comment nói rõ, kèm lý do nó
hỏng theo hướng vô hại nếu server đổi cách băm.

Guard `suggestSeedTimeOffset` được test bằng 7 ca đầu vào dở dang (speed
0, thiếu, chuỗi, Infinity, NaN, một waypoint, hai waypoint trùng chỗ) —
vì module này **ghi vào tài liệu**, mà số học trên ô trống ra `Infinity`
hoặc `NaN`, và viết một trong hai vào profile là tự bịa giá trị.

### Component và nối dây

- `TrafficEditor.tsx` — controlled hoàn toàn, danh sách sống trong
  `draft`, không state riêng. Mỗi kind chỉ hiện field của chính nó (một
  ô `period` bị disable cạnh route waypoint đọc như một số tồn tại mà
  tạm khoá — nó không phải vậy).
- **Chỗ hiện lỗi `environment`** ở đầu khối. Đây là thứ Phase 2a đo được
  và là lý do khối này phải có nó: cả 5 luật traffic đều là model
  validator nên pydantic trả path `environment`; không có dòng render
  path đó thì cả 5 lời từ chối tàng hình.
- `MissionPlacer` nhận mode **controlled tuỳ chọn** (`mode` /
  `onModeChange` / `onPlace` / `modeNote`), giữ nguyên state riêng khi
  không truyền — nên `/decisions` không phải sửa gì. Form giữ **một**
  mode cho cả trang: hai component cùng tin cú click tiếp theo là của
  mình chính là cách một cú nhích start lại đặt waypoint.
- `activeMapId` set trong `adopt()` cho cả ba nguồn map, nên preview
  chạy cho cả map vẽ tay — đúng như An chỉ ra ở vòng review 3, map vẽ
  tay vốn đã có `map_id`.
- Dry-run: `dryRunErrors` là state của form, merge với `fieldErrors` của
  page; sửa field bất kỳ thì xoá verdict cũ (một dòng xanh "server chấp
  nhận" cạnh tài liệu đã đổi bị đọc là còn hiệu lực). Submit **gọi check
  trước**, 422 thì không nộp.

### Test cũ phải sửa — và một cái xanh sai lý do

`TestTrafficIsCarriedButNotYetAuthored` ghim ranh giới cũ bằng cách
khẳng định `seed_time_offset` **vắng mặt** trong `DeploymentForm.tsx`.
Sau Phase 2b nó **vẫn xanh** — vì phần authoring nằm ở `TrafficEditor.tsx`
và `traffic.ts`. Xanh mà sai: trạng thái tệ nhất của một guard, vì không
gì báo động. Thay bằng `TestTrafficIsAuthorable`, kiểm **sự có mặt**, và
có một test liệt kê union `Motion` từ chính pydantic rồi đòi mỗi kind
phải có đường vào `traffic.ts` — phép kiểm mà bản cũ không làm được.

Tương tự phía web: `deployments-page.test.tsx` "does not validate the
obstacles itself" viết lại thành "still refuses to judge", quét **cả ba
file** tìm dấu vết so sánh kiểu luật hợp đồng.

## Bằng chứng

| Kiểm | Kết quả |
|---|---|
| `pytest tests/test_dwa_core_refactor.py` + neighborhood + admissible_stopping + dwa_oracle | **128 passed** — golden byte-identical, không đổi quỹ đạo nào |
| `pytest tests/test_task_profile.py tests/test_dynamic_obstacles.py` | **105 passed** |
| `pytest tests/test_form_covers_the_contract.py` | **17 passed** |
| `npm run typecheck` | sạch |
| `npm run test` (web) | **744 passed / 34 file** sau bốn vòng sửa review (thêm `sequencer.test.ts`) |
| `pytest tests/api` + `task_profile` + `dynamic_obstacles` + `form_covers_the_contract` (sau vòng 3) | **743 passed, 1 skipped** trong 18 phút 18 giây |
| `pytest tests` (toàn bộ) | **2805 passed, 8 skipped** trong 40 phút 43 giây |

Lần chạy toàn bộ đó bắt đầu **trước** khi sửa review, nhưng mọi thứ sửa
sau đó là TypeScript/TSX/JSON, trừ đúng một chuỗi assertion trong
`tests/test_form_covers_the_contract.py` — file đó đã chạy lại riêng sau
khi sửa: **17 passed**.

## Sửa sau review của An (cùng ngày)

An review REQUEST CHANGES với 3 lỗi High, 3 Medium, 1 Low. **Cả bảy đều
đúng**, đã sửa hết. Hai điểm tôi chưa tự xác nhận thì kiểm chứng trước:
`MapCanvas` bắn `onWorldClick` ngay lúc mouse-down rồi `onWorldDrag` mỗi
mouse-move (`MapCanvas.tsx:416-425`), và `deployments/page.tsx` chỉ xoá
`fieldErrors` lúc bắt đầu submit chứ không lúc sửa draft.

| # | Lỗi | Đã sửa thế nào |
|---|---|---|
| H1 | Chỉ truyền `errorFor("environment")`, nên lỗi path sâu (`…dynamic_obstacles.0.radius`) **tàng hình** — dry-run chặn submit mà không nói lý do | `TrafficEditor` nhận **cả danh sách** lỗi thuộc `environment`; lỗi có path sâu render **cạnh đúng row**, phần còn lại gom ở đầu khối. Loại trừ `sensor_noise.*` và `v_obstacle_max` vì chúng đã có ô riêng |
| H2 | Verdict stale: chỉ `set()` xoá, còn đổi start/goal, adopt map, chọn vehicle thì không; input không khoá khi đang check; submit nộp snapshot dựng trước `await` | Một `invalidateCheck()` dùng ở **cả bốn** đường sửa tài liệu; `revision` ref chặn mọi reply đến sau khi tài liệu đã đổi (cả trong `check` và trước `onSubmit`); `frozen = busy \|\| checking` khoá toàn bộ input khi đang kiểm |
| H3 | Preview cũ nằm lại trên canvas sau khi đổi tài liệu hoặc khi request mới lỗi; reply có thể về sai thứ tự | Xoá preview trong `invalidateCheck()`, xoá **trước** khi gửi request, xoá trong `catch`; `previewSeq` ref để chỉ reply mới nhất được vẽ |
| M1 | Kéo chuột trên canvas ở chế độ waypoint thêm hàng loạt điểm | `onWorldDrag` chỉ gắn khi đang ở mission mode |
| M2 | `random_walk` bị báo "offset vẫn phải > 0" — sai, backend cho phép 0 | `offsetHint()` tách `null` thành **ba** trạng thái: `suggestion` / `self-seeded` / `one-shot` / `incomplete`, mỗi cái một câu riêng (en + vi) |
| M3 | `previewRequestOf` bịa fallback hợp lệ (0.05 / 0.25 / 120) cho field thiếu | Trả `null` khi thiếu bất kỳ field bắt buộc nào; nút preview disable theo đó. Thêm 6 ca test cho đúng ba field review chỉ ra |
| L1 | `[...fieldErrors, ...dryRunErrors]` + `find()` khiến lỗi create cũ thắng lỗi dry-run mới | Đảo thứ tự, **và** page xoá `fieldErrors` ngay khi draft đổi |

### Vòng review thứ hai — 5 điểm nữa, cũng đúng cả 5

| # | Lỗi | Đã sửa |
|---|---|---|
| H1 | **Preview cũ vẫn quay lại**: `invalidateCheck()` xoá preview và tăng `revision`, nhưng response đang bay chỉ bị chặn bởi `previewSeq` — nó vẫn khớp, nên vẽ đè lên canvas vừa xoá. Đúng cái bug vòng trước tưởng đã đóng, còn lại một cửa | `invalidateCheck()` tăng luôn `previewSeq` |
| H2 | **`adopt()` bất đồng bộ ghi đè**: giữ `draft` trong closure rồi `await materialiseMap`, nên (a) sửa field trong lúc chờ bị nuốt, (b) map A trả muộn ghi đè map B | `adoptSeq` (chỉ lần adopt mới nhất được commit), `draftRef` (ghi lên draft **hiện tại** chứ không phải bản chụp), cờ `adopting` vào `frozen` |
| M1 | Adapter vẫn ngầm mặc định `stuck_threshold_s` — field **bắt buộc** của contract (`Field(gt=0)`) mà `Scenario` lại có default 5.0, nên preview chạy bằng ngưỡng khác cái deployment khai | Trả `null` khi thiếu; thêm vào bảng test required + một test khẳng định giá trị khai được mang theo |
| M2 | Nút Preview không disable theo adapter — click im lặng không làm gì, đọc như preview hỏng | Tính `previewRequest` ở render, nút disable theo chính nó |
| M3 | **Bỏ qua verdict map-aware**: endpoint preview chạy `validate_against_map` và trả `valid`/`errors`, form chỉ lấy snapshot. Mà dry-run TaskProfile **không mở bản đồ**, nên pose trong tường chỉ lộ ở đây | Render `preview.errors` khi `valid: false`, kèm câu giải thích đây là phép kiểm với bản đồ mà phép kiểm tài liệu không thấy |

### Vòng review thứ ba — 5 điểm, đúng cả 5, và một bài học về test

| # | Lỗi | Đã sửa |
|---|---|---|
| H1 | **Token adopt cấp quá muộn**: `adoptSeq` tăng lúc `adopt()` chạy, nhưng `api.getMap()` đã chạy trước đó ở handler. Chọn map A rồi map B: B về trước lấy token 1, A về sau lấy token 2 và **thắng**. "Lựa chọn mới nhất thắng" thực ra là "response vào adopt cuối cùng thắng" | Token giành **ngay trong handler, trước fetch**; đổi source thì `supersede()` |
| H2 | **`adopt()` không transactional**: đặt `mapData`/`activeMapId`/pose **trước** `await materialiseMap`. Lỗi ở bước đó để lại canvas map mới + draft đường dẫn map cũ, không rollback, không báo | Làm phần có thể lỗi **trước**, commit toàn bộ **sau**; `catch` báo lỗi và không đụng state nào |
| H3 | **Submit/Validate bỏ qua `frozen`**, cộng noise value và vehicle selector | Cả bốn dùng `frozen`; `check()` thành single-flight (hai check chung một cờ `checking`, cái xong trước mở khoá trong khi cái kia còn chạy) |
| M1 | Đổi preview time/seed không xoá preview cũ — ô ghi 40 mà canvas vẽ t=0 | `scrubPreview()`: `supersede()` + xoá ảnh, **không** đụng verdict (tài liệu không đổi) |
| M2 | Test regression vẫn chủ yếu grep — xanh dù token cấp sai thời điểm; cộng hai lỗ hổng coverage từ vòng trước | Xem dưới |

### Vòng review thứ tư — cùng con race, lối vào thứ tư

Chọn **option rỗng** trong picker map là một lựa chọn ("không phải map
đó"), nhưng handler `return` sớm **trước khi** giành token, nên adoption
đang fetch vẫn commit một map mà picker không còn hiện.

Sửa theo đúng đề xuất của An: gộp cả vòng đời `select → fetch →
materialise → commit` vào **một** hàm `adoptStoredMap`, và câu lệnh đầu
tiên của nó là `adoption.claim()` — trước cả nhánh quyết định có gì để
fetch hay không. Một token không ai dùng vẫn vô hiệu hoá mọi thứ đang
bay, nên "không chọn map nào" cũng huỷ được cái đang chạy.

Đây là **lần thứ tư** cùng một con race, và mỗi lần nó vào bằng một cửa
khác: token cấp sai thời điểm, preview không tăng sequence, adopt không
transactional, và giờ là nhánh return sớm. Bài học rút ra không phải
"cẩn thận hơn" mà là **gộp vòng đời vào một chỗ** — khi claim, fetch và
commit nằm rải ở ba nơi thì luôn còn một nhánh quên claim.

**Bài học M2, đáng ghi riêng.** Ba vòng review tìm ra **cùng một lớp
lỗi** ba lần, và cả ba lần tôi "chứng minh" đã sửa bằng cách grep xem
guard có tồn tại không. Grep không thấy được **thời điểm** token được
cấp — đúng thứ sai ở vòng ba. Nên tôi tách luôn phần quyết định ra
`lib/sequencer.ts` và test chính các thứ tự đan xen: A claim, B claim, B
về trước, **B phải thắng**. Đó là test thật, không phải test về hình
dạng mã nguồn (`sequencer.test.ts`, 7 ca).

Hai lỗ hổng coverage cũng đã trả:
- Dry-run API test cho luật **khoá đồng hồ trùng** (path `environment`,
  message chứa "clock key").
- **Test tích hợp**: payload đúng hình dạng `previewRequestOf` bắn vào
  `/scenarios/preview` thật, kỳ vọng **200** — cộng một drift guard đối
  chiếu danh sách field với `scenario_for`. Đây là việc plan yêu cầu từ
  v5 mà tôi chưa làm.

Vẫn còn thiếu: interaction test thật (bấm Preview rồi sửa field trong
lúc chờ) cần `jsdom` + Testing Library, hiện **không có trong
package.json**. Thêm dependency là quyết định của An, không phải của
tôi — ghi thành mục chờ.

Một guard của chính tôi cũng phải sửa: nó pin `errorFor("environment")`
— câu đó giờ hẹp hơn sự thật, thay bằng pin việc truyền cả danh sách,
cộng một test đếm đúng **4** call site của `invalidateCheck` để đường sửa
tài liệu thứ năm thêm sau này làm nó đỏ.

## Một sự cố tự gây, đã dọn

Tôi sửa một test bằng `Set-Content` trong PowerShell và làm hỏng encoding
UTF-8 của cả file (mọi em-dash và chữ "HĐ" thành mojibake). Test vẫn
xanh vì assertion toàn ASCII — đúng loại hỏng không ai phát hiện. Đã
`git checkout` file đó và làm lại bằng công cụ Edit; kiểm lại còn 0 dòng
mojibake. Ghi ra đây vì nó là bài học về công cụ, không phải về code:
**không dùng `Set-Content` cho file có ký tự ngoài ASCII.**

## Còn lại

- **Checklist thủ công trên trình duyệt** (Phase 3 của plan) chưa chạy:
  gom waypoint bằng click, hai click ra heading, preview ba nguồn map,
  khung 2.5D chỉ hiển thị. Node không phủ được phần này.
- Nghỉ hưu `/scenarios` — **giờ đã đủ điều kiện** (form vẽ được obstacle
  rồi), nhưng vẫn là đợt dọn D4 riêng, cần An chốt.
- Món nợ mới nhỏ: `clockKey` trong `traffic.ts` là bản chép công thức
  server; nếu sau này đổi sang băm toàn bộ tên thì xoá nó đi.

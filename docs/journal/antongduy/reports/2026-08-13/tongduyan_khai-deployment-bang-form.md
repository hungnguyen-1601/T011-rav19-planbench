# Khai deployment bằng form, và bản đồ vẽ ngay trong luồng

**Ngày:** 2026-08-13 · **Plan:** [`plans/2026-08-13/form-khai-deployment-va-map-tai-cho.md`](../../plans/2026-08-13/form-khai-deployment-va-map-tai-cho.md)
**Phủ:** W1 · B1 · B2 · W2 · W3 · W4 — toàn bộ plan

---

## 0. Xuất phát điểm

Sau đợt map custom, khai một deployment mới vẫn phải **dán YAML**. Đó là bước duy nhất còn bắt
người dùng đọc hợp đồng trước khi bấm được nút — và chính trang đó có một comment lập luận
rằng form là hình dạng sai:

> *"A form would either re-implement that validation or let the user build something the server
> rejects field by field."*

Lập luận đúng với form **ngây thơ**. Đợt này làm form không ngây thơ, và câu trả lời cho cả hai
vế nằm ở mục 2.

---

## 1. W1 — một cái bút vẽ, một cái đặt điểm, dùng chung

`components/MapPainter.tsx` · `components/MissionPlacer.tsx`. Trang gọi **−220 dòng, +99**.

**Đường cắt:** component nhận lưới hoặc pose vào, trả cái đã sửa ra. Nạp từ đâu và lưu về đâu
là việc của trang gọi — và đó chính là chỗ hai trang khác nhau: `/maps/[id]` PUT theo id, form
khai deployment giữ lưới **chưa lưu** tới lúc khai profile. Một painter biết `api.updateMap`
chỉ phục vụ được cái thứ nhất.

### Hàng rào trong plan viết sai, sửa lại

Plan nói *"test hai trang gọi phải xanh mà không sửa assertion"*. **Bất khả thi đúng như chữ**:
test repo này đọc mã nguồn theo chuỗi, nên dời code sang file khác thì nhất định sáu assertion
đỏ dù hành vi không đổi một ly.

Điều kiện đúng: **cùng assertion, đổi file nó đọc.** Đã làm đúng thế — không assertion nào bị
nới, bị bỏ hay đổi nội dung.

### Ba test mới ghim tính chất việc rút vừa tạo ra

- **Pose chỉ nằm ở một chỗ** — quét `useState<...>` trong `MissionPlacer`, chỉ được phép có
  đúng `PlacementMode`. Đây là test giữ **tính hai chiều** dev yêu cầu: chuột ⇄ form đồng bộ
  *vì* không có bản sao thứ hai, nên một `useState<Pose2D>` thêm vào "cho input mượt" sẽ phá nó
  mà không gì khác bắt được.
- **Vẽ ô đi qua đúng một component** — trang editor không còn `worldToCell`/`BRUSH_VALUE`.
- **Painter không import `@/lib/api`.**

Một thay đổi nhìn thấy được: thanh công cụ ở `/maps/[id]` trước nằm **ngoài** khung panel, giờ
nằm **trong** — hệ quả của việc gom công cụ và canvas vào một component.

---

## 2. Vì sao form này không phải form ngây thơ

Hai vế của lời phản đối cũ, hai câu trả lời:

### Vế 1: *"sẽ chép lại validator"* → **form không phán quyết gì**

Cùng luật `HumanActs` ở trang decision đã ghi: *"The server owns the rule, and a second copy
here would be free to disagree with it."*

Test khẳng định: file form không chứa `throw new Error(`, không chứa so sánh ngưỡng nào. Hai
phép tính duy nhất trong đó — `nMinFor` và `ramLeftOver` — là **hiển thị hệ quả**, không đi
đâu cả; comment trong `deployments.ts` ghi thẳng *"never travels"* và có test đọc chữ đó.

### Vế 2: *"người dùng dựng xong rồi bị bác từng ô"* → **B1**

Đó là mô tả một API chỉ biết trả về một cục chữ. Sửa API.

---

## 3. B1 — lỗi có địa chỉ ô

Trước: `create` gói toàn bộ lỗi pydantic thành **một chuỗi**. Với ô dán thì tạm được; với form
thì vô dụng — không ô nào đỏ lên, người đọc phải tự dịch *"2 validation errors for TaskProfile"*
ra thành *"à, sai ở dòng thứ mười bảy"*.

`errors.py` thêm `field_errors(error)`. `DomainValidationError` **đã có sẵn** tham số `details`
và envelope đã phát ra `error.details`, nên chỉ cần đổ vào đúng chỗ.

```
status  : 422
message : task profile is not valid under HĐ-2: 2 validation errors…
  robot.radius     Input should be greater than 0
  constraints      Value error, goal_tolerance_rad = 0.35 constrains the arriva…
```

Ba chi tiết chốt lúc gõ:

| chốt | lý do |
|---|---|
| Địa chỉ nối bằng dấu chấm, đúng hình dạng YAML lồng nhau (`missions.0.probability`) | Một địa chỉ dùng được cho **cả** form lẫn file |
| Lỗi ở mức cả khối thì **trỏ vào khối** (`path: "constraints"`) | `goal_tolerance_rad` bị từ chối bởi validator gắn trên cả model. Đoán ra tên trường là API tự suy diễn về một luật nó không sở hữu — mà câu thông điệp đã nêu đúng tên trường rồi |
| Duck-typing thay vì import pydantic | Chỗ gọi cố ý bắt `Exception`; lỗi không mang địa chỉ phải thoái về rỗng, **không được ném ra trong lúc đang báo lỗi**. Có test cho cả ca `errors()` tự ném |

**Thông điệp cục giữ nguyên.** Ô dán không có ô nào để tô đỏ nên vẫn đọc câu văn đó. Hai đối
tượng đọc, một response.

Phía web: `authFetch` trước **vứt** `details` đi. Thêm `FieldError` mang cả hai; message vẫn là
message nên mọi chỗ bắt lỗi cũ chạy nguyên.

---

## 4. B2 — map trong kho thành hai đường dẫn

`map_files.py` — `materialise_map()` ở mức module, không còn là method riêng của
`TaskProfileService`. Hai chỗ gọi: `derive` và endpoint mới `POST /maps/{id}/materialise`.
**Một định nghĩa** của "map vẽ ra rơi xuống đâu trên đĩa"; hai bản sao sẽ cho hai deployment
trỏ vào hai file khác nhau của cùng một map.

Endpoint đặt ở `routers/maps.py`, lấy map root qua dependency mới `get_map_root` —
`get_task_profile_service` cũng chuyển sang dùng nó, nên chỉ còn **một** chỗ biết
`app.state.decision_map_root`.

**POST chứ không GET**: nó ghi hai file.

```
200 {"map": "maps/custom/753ea2d0e4ce__v1.pgm", "map_yaml": "...yaml"}
lần hai : True (idempotent)   tồn tại=True   tuyệt đối=False
chưa đăng nhập: 401     map lạ: 404
hai đường dẫn đó khai thành deployment: 201 probe_from_form
```

Dòng cuối đáng tiền nhất: **đường của form và đường của ô dán gặp nhau ở cùng một artifact** —
nguyên tắc 1.2 của plan, giờ có bằng chứng chứ không chỉ là ý định.

Có test khẳng định sửa map thì file đổi tên còn **file cũ vẫn còn**, để deployment khai từ v1
tiếp tục trỏ vào tường của v1 — chỉ dưới cách đọc đó thì trace đã lưu mới còn là bằng chứng.

---

## 5. W2–W4 — form, switch, và bản đồ tại chỗ

### Mặc định đến từ file, không từ bản chép

Endpoint mới `GET /task-profiles/template` đọc thẳng `profiles/open_hall_v2.yaml`. Một bộ số
chép tay sang TypeScript sẽ là **tuyên bố thứ hai** về một deployment chạy được, và ngày ai đó
tinh chỉnh sảnh thì form vẫn lặng lẽ phát ra số cũ.

`id` trả về **rỗng** có chủ ý: khai lại id cũ với nội dung khác bị từ chối (HĐ-3.1), nên
template mang sẵn `open_hall_v2` sẽ làm lần submit đầu tiên hỏng vì một lý do tác giả không
chọn.

Test mạnh nhất của mục này: **lấy template, đặt id, POST — ra 201.** Mặc định không chỉ trông
hợp lý, nó là một profile hợp đồng chấp nhận.

Một cái bẫy đã tránh và có test: `GET /task-profiles/template` và `GET /task-profiles/{id}`
**cùng là GET**, nên route nào đăng ký trước sẽ nuốt chữ `template`. Thứ tự đăng ký là thứ giữ
chúng tách nhau, nên khẳng định chứ không giả định. (Khác với `POST .../derive` hôm trước —
POST và GET thì Starlette tự phân biệt được.)

### Chữ giải thích: bảy dòng, mỗi dòng một câu

Dev chốt *"ngắn gọn mà vẫn hiểu"*. Chỉ ô nào mà **một con số kéo theo hệ quả** mới có chữ:

| ô | dòng chữ |
|---|---|
| `id` | Khai lại id cũ với nội dung khác bị từ chối, không gộp. |
| `collision_probability_max` | ⇒ cần **30** episode (HĐ-7.1) *— số cập nhật theo từng ký tự gõ* |
| `success_rate_min` | Đặt 1.00 thì deployment chỉ gác cổng, hết xếp hạng (HĐ-8.4). |
| `goal_tolerance_rad` | Phải ≥ π: hướng tới đích không được chấm (HĐ-6). |
| `control_period` | Đây là ngưỡng của cổng G4. |
| `available_ram_mb` | Tổng trừ phần đã chia còn **3277** MB *— cộng tại chỗ* |
| `sensor_noise` | *(xem mục 6)* |

### Switch: mang đi một chiều, có chủ ý

Form → YAML **mang theo** thứ form vừa dựng, để đọc được đúng cái sắp gửi và sửa tay khối form
chưa làm được.

YAML → form **không mang về**, và nói rõ. Nạp ngược một YAML chứa `dynamic_obstacles` vào form
không diễn đạt được khối đó sẽ **âm thầm nuốt mất** nó, và người dùng khai một deployment thiếu
đúng phần traffic họ vừa viết.

### Bản đồ: ba nguồn, cuối luồng, không đổi tab

| nguồn | cách lấy |
|---|---|
| **Scenario dựng sẵn** *(mặc định)* | `GET /scenario-library` → `POST /scenario-library/{name}/import` |
| Kho map | `GET /maps` |
| Vẽ mới | `MapPainter` tại chỗ → `POST /maps` |

Mặc định `static_obstacles`: sảnh 12 × 9 m @ 0,25 m với ba cột. Không trống rỗng nên planner có
việc thật, không có vật cản động (đúng phần đang hoãn), và là scenario `tuning.py` vẫn dùng làm
chuẩn hiệu chỉnh.

**Start/goal khi đổi map:**

1. Map từ thư viện → **pose của chính scenario đó**. `static_obstacles` là (1,5; 4,5) →
   (10,5; 4,5) — cặp tác giả đã chọn và biết là đi được.
2. Map khác → suy từ kích thước, dùng lại quy tắc `defaultScenario` cũ.

Ghi rõ trong mã: **mặc định là điểm khởi đầu, không phải lời hứa.** Trên map tự vẽ, cặp suy ra
có thể rơi vào tường — server từ chối kèm lý do. Một cặp *chắc chắn đi được* thì phải chạy tìm
đường trong trình duyệt, tức hiện thực lần thứ hai của planner.

Đổi kích thước lưới lúc vẽ **xoá nét đã vẽ**, và đó là đúng: ô (3, 4) của lưới rộng 40 nằm chỗ
khác trên lưới rộng 60, nên chép ô sang sẽ **xé tường** chứ không giữ nó.

---

## 6. Hệ quả của việc hoãn vật cản động — nói ra, không giấu

Deployment khai bằng form **không có traffic**. Hợp lệ: `open_hall_v2` cũng vậy, và nó vẫn cho
episode phân biệt được **nhờ `sensor_noise`**.

Nguy hiểm chỉ khi **cả hai cùng bằng 0**: planner tất định + không nhiễu + không traffic ⇒ mọi
seed phát lại **đúng một** episode, 300 lần chạy mang thông tin của 1, và cận trên va chạm của
G2 tuyên bố một con số bằng chứng không đỡ nổi.

`EnvironmentSpec` đã ghi cảnh báo này trong docstring và **cố ý không cấm**. Form cũng không
cấm — nó **nói**, đúng một dòng dưới ô nhiễu, và có test đọc chữ đó ở cả hai ngôn ngữ. Lối
thoát: switch sang YAML, thêm khối bằng tay.

---

## 7. Test

| | trước đợt | sau đợt |
|---|---:|---:|
| Backend | 2312 passed, 6 skipped | **2328 passed, 6 skipped** (+16) · 14 phút |
| Web | 573 passed | **587 passed** (+14) |

`ruff check` sạch · `ruff format` sạch · `tsc --noEmit` sạch.

Web +14: rút component (3) · form là input method không phải định nghĩa thứ hai (11).
Backend +16: lỗi theo ô (6) · materialise (6) · template (4).

**Một test cũ bị viết lại, nói rõ vì sao.** `deployments-page.test.tsx` có
*"takes the YAML whole instead of rebuilding it as a form"* — khẳng định đó giờ **sai**. Không
xoá mà thay bằng khẳng định của thiết kế mới, kèm nguyên văn lý do cũ và câu trả lời cho nó:
form không validate, và nó dựng **cùng một văn bản** ô dán dựng. Ô dán ở lại, và không chỉ vì
thói quen — nó là cách duy nhất viết khối form chưa diễn đạt được.

Hai lỗi web còn lại **có sẵn từ trước loạt việc này**: `dashboard-page.test.tsx` so đường dẫn
`\system\page.tsx` với `/system/page.tsx` (dấu phân cách Windows) và `assistant-page.test.tsx`
không collect được.

---

## 8. Còn lại

- **Vật cản động trong form** — hoãn theo chốt của dev, lối thoát là tab YAML.
- **`available_observations`** — mọi profile hôm nay khai `[lidar_2d]`, form để nguyên giá trị
  template, chưa có ô.
- **Sửa deployment đã khai** — không có và sẽ không có: đổi nội dung dưới id cũ là thứ server
  từ chối bằng 409 (HĐ-3.1). Muốn khác thì khai id mới.
- ~~**Test chống trôi lược đồ**~~ — **đã trả, cùng ngày**. Xem mục 9.

---

## 9. D1 — test chống trôi lược đồ *(trả nợ, cùng ngày)*

`tests/test_form_covers_the_contract.py`, 10 test.

### Kiểu hỏng nó bắt

Thêm một trường vào `TaskProfile` và form **lặng lẽ thôi cung cấp nó**: suite vẫn xanh, form
vẫn khai được deployment, và profile sinh ra thiếu đúng thứ vừa được thêm. Không ai biết cho
tới khi một lượt chạy đo một thế giới không ai mô tả.

**Không có test nào khác đỏ trong ca đó.** Đó là lý do món này đáng tiền.

### Vì sao test Python đọc file `.tsx`

Nó là chỗ **duy nhất nhìn được cả hai phía**. `TaskProfile` là hợp đồng và pydantic liệt kê
được; form là TypeScript và test web không import pydantic được.

Tìm chuỗi thì thô, và **thô là đủ**: form gán mọi trường bằng đường dẫn có dấu chấm
(`field("robot.radius", …)`), nên đường dẫn hoặc có trong file hoặc trường đó không được gán.

Quy tắc duyệt: **mở** model lồng (`constraints` là tám ô form gán từng cái), **không mở** tập
hợp (`missions` được `MissionPlacer` gán trọn gói).

### Danh sách miễn trừ là một nửa giá trị của test

Một trường được phép vắng **chỉ khi** có tên trong `NOT_IN_THE_FORM` **kèm lý do**. Năm mục,
mỗi mục là một quyết định chứ không phải một khoảng trống ai đó bỏ lại:

| trường | vì sao không có ô |
|---|---|
| `environment.dynamic_obstacles` | dev hoãn 13-08; tab YAML viết được, và ô nhiễu nói ra cái giá của deployment không traffic không nhiễu |
| `robot.type` | `Literal['differential_drive']` — dropdown một lựa chọn là control không dùng được, và nó gợi ý có lựa chọn ở chỗ chỉ có một |
| `available_observations` | mọi profile khai `[lidar_2d]`, chưa candidate nào cần khác. Ngày có, nó đến kèm định giá quan sát của G6 |
| `constraints.cost_per_mission_max` | **vắng mặt là có nghĩa**: không có nó thì neo tiền không phân giải và business mode **từ chối thay vì đoán** (HĐ-8.3 luật 4). Một ô điền sẵn số là nền tảng tự bịa ngân sách cho khách hàng |
| `min_episodes_before_stop` | `None` nghĩa là "lấy mặc định", và giá trị dùng thật vẫn được ghi lên report. Đưa núm này cạnh các ngưỡng là đặt nó vào nhóm nó không thuộc về |

Ba test phụ giữ cho chính danh sách đó không mục: không được có **mục ma** (miễn trừ cho trường
hợp đồng không còn), không được **vừa có ô vừa được miễn trừ**, và mỗi lý do phải dài quá 80 ký
tự và không mở đầu bằng `todo`/`later`/`n/a` — bar thấp có chủ ý, nhưng ai phải viết hai câu thì
hoặc có lý do thật hoặc tự nhận ra là không có.

### Chứng minh nó đỏ khi phải đỏ

Một cái gác chưa ai thấy đỏ là cái gác không nên tin. Thêm tạm `floor_wetness: float` vào
`TaskProfile`:

```
E           floor_wetness
E       assert ['floor_wetness'] == []
1 failed, 9 passed
```

Hoàn nguyên, `git diff --stat packages/` rỗng, 10 passed.

`ruff` sạch. Chạy kèm `tests/api/test_api_decisions.py`: **74 passed**. Chưa chạy full suite —
dev chốt để sau.

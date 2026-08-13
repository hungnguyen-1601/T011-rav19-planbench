# Kế hoạch: khai deployment bằng form, và vẽ map ngay tại chỗ

> **Ngày lập:** 2026-08-13 · **Người lập:** An (cùng Claude) · **Trạng thái:** chờ approve
> **Bối cảnh:** sau đợt map custom + kết quả từng episode (commit `8ca2518`). Dev dùng thử,
> thấy khai deployment mới vẫn phải dán YAML — bước duy nhất còn bắt người dùng đọc hợp đồng
> trước khi bấm được nút.
> **Phiên trước cùng chủ đề:** [`plans/2026-08-12/map-custom-va-ket-qua-tung-episode.md`](../2026-08-12/map-custom-va-ket-qua-tung-episode.md)

---

## 0. Dev đã chốt

| câu hỏi | chốt |
|---|---|
| Hai cách khai | **form điền ô** và **dán YAML**, một nút switch |
| Mặc định | **form** — mở trang ra là thấy ô điền, không phải ô dán |
| Giá trị khởi tạo | **của `open_hall_v2`** |
| Chữ giải thích cạnh ô | **ngắn** — hiểu được là đủ, không phải một đoạn |
| Tạo map | **nằm luôn cuối phần khai**, không bấm sang tab khác. Vẽ mới **hoặc** chọn map có sẵn |
| Vật cản động | **tạm chưa làm** — ưu tiên chạy được simulator trước |
| Map mặc định | **`static_obstacles`** của thư viện scenario |
| Nguồn map | thêm **thư viện scenario dựng sẵn**, không chỉ kho map |
| Start/goal khi đổi map | **về vị trí mặc định của map đó**, không để trống |
| Chuột ⇄ form | **hai chiều** — kéo chuột cập nhật ô số, sửa ô số dời điểm trên canvas |
| Khối `hardware` | **gập lại**, mở ra mới sửa |

---

## 1. Ba nguyên tắc, và nguyên tắc thứ hai là cái giữ cho việc này không hỏng

### 1.1. Form không phán quyết gì

Mọi luật vẫn thuộc về `TaskProfile`. Form dựng payload, gợi ý mặc định, và **hiển thị nguyên
văn lời từ chối của server**. Không một điều kiện hợp đồng nào được viết lại bằng TypeScript.

Đây không phải nguyên tắc mới — `HumanActs` ở trang decision đã ghi đúng câu đó: *"The server
owns the rule, and a second copy here would be free to disagree with it."*

### 1.2. Form và ô dán phải sinh ra **cùng một artifact**

Form có **ô xem trước YAML**, và thứ nó hiện ra là **đúng thứ ô dán sẽ nhận**. Cùng một
endpoint, cùng một hình dạng dữ liệu, khác mỗi cách nhập.

Vì sao đây là điều kiện chứ không phải tiện nghi: nếu form gửi một hình dạng riêng thì có
**hai định nghĩa của "một deployment"**, và cái thứ hai được quyền bất đồng với cái thứ nhất.
Giữ chung một artifact còn cho ba thứ miễn phí:

- profile vẫn là **văn bản đọc được, diff được, commit được** (nó là tài liệu hợp đồng HĐ-2);
- gỡ lỗi được: bấm switch sang YAML là thấy chính xác cái sắp gửi đi;
- kiểm được bằng test: form-mode và paste-mode trên cùng dữ liệu phải ra byte giống nhau.

### 1.3. Không dựng editor thứ hai

Vẽ ô đã có ở `/maps/[id]`; đặt start/goal đã có ở panel khởi chạy `/decisions`. Cả hai được
**rút ra thành component dùng chung**, không chép. Đây là luật đã áp ở đợt trước và lý do vẫn
nguyên: hai editor là hai định nghĩa của cùng một thứ.

---

## 2. Việc backend

### B1. Lỗi trả về **theo từng ô**, không phải một cục *(bắt buộc — form không dùng được nếu thiếu)*

Hôm nay `TaskProfileService.create` gói toàn bộ lỗi pydantic thành **một chuỗi**:

```python
raise DomainValidationError(f"task profile is not valid under HĐ-2: {error}")
```

Với ô dán thì tạm được — người ta đọc rồi tự sửa file. Với form thì vô dụng: không ô nào đỏ
lên, người dùng phải tự dịch chuỗi đó ra thành "à, sai ở `constraints.goal_tolerance_rad`".

**Việc:** truyền `error.errors()` qua thay vì `str(error)`, dùng `loc` làm địa chỉ ô.
`DomainValidationError` **đã có sẵn** tham số `details`, và envelope lỗi đã phát ra
`error.details` — nên chỉ cần đổ vào đúng chỗ, không phải dựng cơ chế mới.

Một quyết định nhỏ phải chốt lúc gõ: `details` hiện khai `list[str]`. Hai lối:

| lối | được | mất |
|---|---|---|
| Giữ `list[str]`, định dạng `"constraints.goal_tolerance_rad: ..."` | không đụng chữ ký | client phải cắt chuỗi — mong manh |
| Nới thành `list[dict]` với `{path, message}` | client tra thẳng | đụng một kiểu dùng chung, phải rà các chỗ gọi khác |

**Khuyến nghị: nới thành `list[dict]`.** Cắt chuỗi để tìm tên trường là chỗ sẽ vỡ đúng lần đầu
ai đó viết một thông điệp lỗi có dấu hai chấm.

**Vẫn không chép luật nào**: server tính lỗi, form chỉ được biết lỗi đó **thuộc về ô nào**.

**Ước lượng:** 1–1,5 giờ.

### B2. `POST /maps/{map_id}/materialise` — biến map trong kho thành hai đường dẫn

Profile khai map bằng **đường dẫn file** (HĐ-2); editor lưu lưới trong DB. Hàm bắc cầu
`_materialise_map` **đã viết ở đợt trước** cho `derive`, chỉ đang nằm private trong
`TaskProfileService`.

Phơi nó ra thành một endpoint trả về `{"map": "maps/custom/<id>__v<n>.pgm", "map_yaml": "..."}`.

**Vì sao là endpoint riêng chứ không dạy `POST /task-profiles` hiểu `map_id`:** để giữ đúng
nguyên tắc 1.2. Nếu create nhận map id thì form gửi một hình dạng còn ô dán gửi hình dạng
khác — hai định nghĩa. Với endpoint riêng, form **lấy đường dẫn trước**, rồi điền vào chính
cái profile mà ô dán cũng sẽ nhận, và **ô xem trước YAML hiện đúng đường dẫn thật**.

Idempotent theo (map id, version) như `derive`. Cần đăng nhập.

**Ước lượng:** 1 giờ (phần khó đã xong).

---

## 3. Việc web

### W1. Rút hai component dùng chung *(làm trước, không thêm tính năng nào)*

| rút cái gì | từ đâu | dùng ở đâu sau khi rút |
|---|---|---|
| `MapPainter` — ba cọ, canvas, lưu phiên bản | `/maps/[id]` | `/maps/[id]` **và** cuối form khai deployment |
| `MissionPlacer` — nút chế độ, bấm/kéo, ô x/y/hướng, vòng dung sai | panel khởi chạy `/decisions` | `/decisions` **và** form khai deployment |

Hàng rào: sau khi rút, **test của cả hai trang gọi cũ phải xanh mà không sửa assertion**. Phải
sửa assertion nghĩa là việc rút đã đổi hành vi.

**Ước lượng:** 2 giờ.

### W2. Form khai deployment

Bố cục theo đúng thứ tự đọc, map xuống cuối như dev yêu cầu:

```
[● Điền ô]  [ Dán YAML ]

Danh tính     id · claim_level · deployment_role
Robot         7 ô
Ngưỡng        8 ô
Phần cứng     ▸ gập lại — 7 ô, mở ra mới sửa
Nhiễu         lidar_range_sigma_m · wheel_slip_fraction
Nhiệm vụ      MissionPlacer — bấm/kéo trên map, hoặc gõ x/y/hướng. Hai chiều.
BẢN ĐỒ        ○ thư viện scenario (mặc định: static_obstacles)
              ○ kho map    ○ vẽ mới       ← cuối cùng, không đổi tab
              [MapPainter]
Xem trước     YAML — đúng thứ ô dán sẽ nhận
              [Khai deployment]
```

Khoảng **30 ô phẳng**, cộng hai component đã rút.

#### Chữ giải thích: bảy dòng, mỗi dòng một câu

Dev chốt "ngắn gọn mà vẫn hiểu". Chỉ những ô mà **một con số kéo theo một hệ quả** mới có
chữ; phần còn lại để trống.

| ô | dòng chữ |
|---|---|
| `id` | Khai lại id cũ với nội dung khác bị từ chối, không gộp. |
| `collision_probability_max` | ⇒ N_min **30** episode *(số cập nhật theo từng ký tự gõ)* |
| `success_rate_min` | Đặt 1.00 thì deployment chỉ còn gác cổng, hết xếp hạng (HĐ-8.4). |
| `goal_tolerance_rad` | Phải ≥ π: nền tảng không chấm hướng đích (HĐ-6). |
| `control_period` | Đây là ngưỡng của cổng G4. |
| `available_ram_mb` | 8192 − 4915 = **3277** *(cộng tại chỗ)* |
| `sensor_noise` | Thuộc hiện trường, không thuộc candidate. σ = 0 **và** không có traffic ⇒ mọi seed lặp lại một episode. |

Dòng cuối là chỗ đợt này **phải** nói, vì nó là hệ quả trực tiếp của quyết định hoãn vật cản
động — xem mục 5.

**Ước lượng:** 3–4 giờ.

### W3. Switch + ô xem trước YAML

Switch hai vị trí, mặc định **Điền ô**. Chuyển sang **Dán YAML** thì ô dán được **nạp sẵn nội
dung form đang dựng** — không mất việc đang làm, và người muốn sửa tay một trường form chưa
có (ví dụ `dynamic_obstacles`) có lối đi.

Chiều ngược lại — dán YAML rồi bấm sang form — **không nạp ngược**, và nói rõ. Nạp ngược một
YAML chứa khối form không dựng được sẽ **âm thầm nuốt mất khối đó**, và người dùng bấm Khai mà
không biết mình vừa xoá gì.

**Ước lượng:** 1 giờ.

### W4. Map ngay trong luồng — ba nguồn, một chỗ

| nguồn | lấy từ đâu | ghi chú |
|---|---|---|
| **Thư viện scenario** *(mặc định)* | `GET /scenario-library` — 10 mục dựng sẵn, xếp từ dễ tới khó | `POST /scenario-library/{name}/import` dựng nó thành map lưu trong kho, trả về `map_id` |
| **Kho map** | `GET /maps` | map đã vẽ hoặc đã import trước đó |
| **Vẽ mới** | `MapPainter` tại chỗ, `POST /maps` | ba ô cỡ: rộng × cao × độ phân giải |

**Mặc định là `static_obstacles`**: sảnh 12 × 9 m @ 0,25 m, ba cột 0,75 m ở (4; 3), (6; 6),
(8; 3,5). Đây là lựa chọn tốt cho một giá trị khởi tạo — không trống rỗng như `open_space` nên
planner có việc thật để làm, mà cũng không có vật cản động (đúng phần đang hoãn), và nó là
scenario mà `tuning.py` vẫn dùng làm chuẩn hiệu chỉnh.

Chọn xong map nào cũng gọi **B2** để lấy hai đường dẫn, rồi điền vào profile — nên ô xem trước
YAML luôn hiện đường dẫn thật, không phải chỗ trống.

#### Start/goal có mặc định, không để trống

Dev chốt: đổi map thì hai điểm **về vị trí mặc định của map mới**, rồi người dùng chỉnh. Khác
với panel khởi chạy `/decisions` hiện tại — ở đó đổi map là xoá về `null` và bắt bấm chuột.

Lấy mặc định ở đâu, theo thứ tự:

1. **Map từ thư viện** — dùng **start/goal của chính scenario đó**. `static_obstacles` là
   (1,5; 4,5) → (10,5; 4,5). Đây là cặp pose tác giả scenario đã chọn và đã biết là đi được.
2. **Map khác** (kho hoặc vừa vẽ) — không có scenario đi kèm, nên suy ra từ kích thước, dùng
   lại đúng quy tắc `defaultScenario` đang có: (1,5; 1,5) → (rộng − 1,5; cao − 1,5).

**Mặc định là điểm khởi đầu, không phải một lời hứa.** Trên một map người dùng tự vẽ, cặp suy
ra có thể rơi vào tường — server sẽ từ chối kèm lý do (`validate_missions_on_map` bắt đủ năm
kiểu lệch). Đó là hành vi đúng: một cặp mặc định *chắc chắn đi được* thì phải chạy tìm đường
trong trình duyệt, tức là hiện thực lần thứ hai của planner.

#### Chuột ⇄ form, hai chiều

Dev yêu cầu rõ: kéo chuột thì toạ độ trên form tự cập nhật, và sửa số trên form thì điểm trên
canvas tự dời.

**Việc này đã đúng sẵn** trong `MissionPlacer` dựng ở đợt trước, nhờ đúng một điều: canvas và
ô số **không giữ state riêng nào cả** — cả hai đọc và ghi cùng một `Pose2D` ở component cha.
Hai chiều không phải một tính năng phải thêm; nó là hệ quả của việc không có hai bản sao.

Việc còn lại chỉ là **có test khẳng định** tính chất đó, để nó không bị vô hiệu hoá lần sau ai
đó thêm một `useState` cục bộ vào ô số cho tiện.

`MissionPlacer` đặt **trên** khối map nhưng vẽ **lên chính map đang chọn**. Vì giờ luôn có map
mặc định (`static_obstacles`), trường hợp "chưa chọn map" chỉ còn xuất hiện trong lúc đang vẽ
map mới chưa lưu.

**Ước lượng:** gộp trong W2, cộng ~1 giờ cho nguồn thư viện scenario.

---

## 4. Test

| kiểm | vì sao |
|---|---|
| **Chống trôi lược đồ** — duyệt `TaskProfile.model_fields` (kể cả model lồng), mọi trường phải **hoặc** có trong form **hoặc** nằm trong danh sách hoãn kèm lý do | Thêm một trường vào hợp đồng mà form lặng lẽ bỏ sót là kiểu hỏng không gì bắt được. Đây là test đáng giá nhất của cả đợt |
| **Form ≡ dán** — cùng dữ liệu, hai đường, ra profile giống nhau | Nguyên tắc 1.2, nếu không kiểm thì nó chỉ là một ý định |
| **Không có luật nào ở client** — form không chứa ngưỡng nào của hợp đồng; mọi lỗi hiển thị đến từ response | Nguyên tắc 1.1 |
| **Lỗi gắn đúng ô** — gửi `goal_tolerance_rad = 0.35`, lỗi phải trỏ vào đúng ô đó | B1 |
| **Rút component không đổi hành vi** — test hai trang gọi cũ xanh, không sửa assertion | W1 |
| **Map vẽ tại chỗ dùng được thật** — vẽ → lưu → materialise → khai → chạy được một sweep | Giống hàng rào đợt trước: chạy thật, không chỉ test |
| **Chuột ⇄ form hai chiều** — không có `useState` cục bộ nào giữ pose; canvas và ô số cùng đọc/ghi một `Pose2D` ở cha | Hai chiều là hệ quả của việc không có hai bản sao. Thêm một state cục bộ "cho tiện" sẽ phá nó, và không gì khác bắt được |
| **Đổi map ⇒ pose về mặc định của map mới** — map thư viện lấy pose của scenario đó, map khác suy từ kích thước | Để trống thì người dùng phải bấm hai lần trước khi thấy được gì; giữ pose cũ thì toạ độ mang nghĩa của một thế giới khác |

---

## 5. Cố ý hoãn — và hệ quả phải nói ra

### Vật cản động (`environment.dynamic_obstacles`)

Dev chốt hoãn, ưu tiên chạy được simulator. Đồng ý — nó là một danh sách lồng nhau với **bốn
kiểu chuyển động** (`waypoint`, `periodic`, `random_walk`, `sudden_stop`), mỗi kiểu một bộ
trường khác nhau, cộng luật `seed_time_offset` phải ≥ một chu kỳ đầy đủ. Gần bằng phần còn lại
cộng lại.

**Nhưng hoãn nó kéo theo một hệ quả thống kê, và form phải nói:**

Deployment khai bằng form sẽ **không có traffic**. Điều đó **hợp lệ** — `open_hall_v2` cũng
không có vật cản động nào, và nó vẫn cho episode phân biệt được **nhờ `sensor_noise`**. Nguy
hiểm chỉ xuất hiện khi **cả hai cùng bằng 0**: planner tất định + không nhiễu + không traffic
⇒ mọi seed phát lại **đúng một** episode, 300 lần chạy mang thông tin của 1, và cận trên va
chạm của G2 sẽ tuyên bố một con số mà bằng chứng không đỡ nổi.

Chính `EnvironmentSpec` đã ghi cảnh báo này trong docstring và cố ý **không cấm**. Nên form
cũng không cấm — nó **nói**, đúng một dòng, ngay dưới ô nhiễu.

**Lối thoát trong lúc chờ:** switch sang Dán YAML, thêm khối `dynamic_obstacles` bằng tay. Đó
là lý do thứ hai để có switch, ngoài lý do tiện.

### Không hoãn nhưng cũng không làm trong đợt này

- **Sửa deployment đã khai.** Không có và sẽ không có: đổi nội dung dưới một id cũ là thứ
  server từ chối bằng 409, vì `episode_context_id` không băm environment (HĐ-3.1). Muốn khác
  thì khai id mới.
- **`available_observations`.** Hôm nay mọi profile khai `[lidar_2d]` và registry chưa có
  candidate nào cần khác. Để một ô cứng giá trị đó, ghi vào danh sách hoãn của test chống trôi.

---

## 6. Thứ tự và ước lượng

```
B1 lỗi theo từng ô     (1–1,5 h)  ─┬─ backend, độc lập, làm được song song
B2 materialise map     (1 h)      ─┘
        │
W1 rút component       (2 h)      <- không thêm tính năng nào, test cũ phải xanh nguyên
        │
W2 form + chữ giải thích (3–4 h)
W3 switch + xem trước    (1 h)
        │
        └── chạy thật: vẽ map → khai → sweep → đọc bảng cổng
```

**Tổng: 9,5–11,5 giờ** (cộng ~1 giờ cho nguồn thư viện scenario). Một ngày làm, cộng thời gian
chạy suite.

**Nếu chỉ có nửa ngày:** B1 + W1. Cả hai không thêm tính năng nào nhìn thấy được, nhưng thiếu
B1 thì form không dùng được, và thiếu W1 thì form sẽ đẻ ra editor thứ hai.

---

## 7. Câu hỏi đã đóng *(dev trả lời 2026-08-13)*

1. **Cỡ map mặc định** → không còn là câu hỏi: mặc định giờ là **`static_obstacles` của thư
   viện** (12 × 9 m @ 0,25 m), không phải một lưới trống. Ô "vẽ mới" vẫn giữ mặc định
   `emptyBorderedMap` (40 × 30 ô @ 0,25 m) cho người muốn bắt đầu từ giấy trắng.
2. **`hardware` gập lại** → **duyệt**. Bảy ô nằm trong một khối gập, mở ra mới sửa.

Không còn câu hỏi mở nào. Kế hoạch đủ để gõ.

# E4.3 — bộ metrics so sánh hai thuật toán realtime trong một episode

**Ngày:** 2026-08-20 · **Nhánh:** `tongduyan_3`

**Trạng thái:** xong cả ba tầng (engine, API, UI), **chưa commit**. Full suite chưa
chạy — chỉ chạy phần vừa sửa, theo đúng yêu cầu của An.

An chốt: **bỏ trục comfort**, **giữ composite**.

---

## 1. Vấn đề thiết kế: một câu hỏi, hai đồng hồ

Câu hỏi người xem có khi kéo thanh replay là *"ngay lúc này bên nào tốt hơn?"*. Nhưng
tại **cùng một thời điểm**, hai robot đang ở **hai chỗ khác nhau** trên nhiệm vụ. Nên
"so sánh tại thời điểm t" thực ra là **hai câu hỏi khác nhau đội chung một nhãn**:

| Đồng hồ | Trả lời câu gì | Metrics |
|---|---|---|
| **Cùng thời gian** | ai đang **đi trước** | `progress_fraction`, `progress_rate`, `compute_budget`, `replans` |
| **Cùng tiến độ** | ai làm **cùng khối lượng việc** tốt hơn | `elapsed_s`, `safety_margin`, `exposure_s`, `path_efficiency` |

So `min_clearance` tại **cùng thời gian** là so hai đoạn map khác nhau — con số ra
được không nói về thuật toán nào cả. Vì vậy **mỗi metric khai báo nó thuộc đồng hồ
nào**, và hai đồng hồ **không bao giờ trộn trong một hàng**. Hằng số này nằm ở cả hai
tầng: `TIME_SYNC_METRICS`/`PROGRESS_SYNC_METRICS` (Python) và
`TIME_CLOCK`/`PROGRESS_CLOCK` (TS).

---

## 2. Tám metric, và vì sao chọn đúng tám cái đó

Ba ràng buộc An đặt ra: **dùng chung schema giữa các episode**, **thuật toán nào cũng
dùng được**, **thể hiện được hiệu năng khi gặp task**.

Hệ quả trực tiếp:

- **Không đọc counter riêng của planner.** A-star nở node, RRT-star mọc cây, policy
  học được thì chẳng có cả hai. Một cột chỉ một bên điền được là một cột **đọc thành
  số 0 cho các bên còn lại**. Compute đo bằng **latency so với `T_cycle`** — thứ mọi
  stack đều phải trả. Có test cấm các tên `expanded_nodes`, `tree_size`, `samples`,
  `iterations` xuất hiện trong schema.
- **Mọi đại lượng đều vô thứ nguyên hoặc chuẩn hoá theo thứ deployment tự khai** —
  bán kính robot, `T_cycle`, `clearance_warning_m`, chiều dài reference. Cùng một
  hàng đọc giống nhau ở mọi episode.

Vài chi tiết đáng nói:

| Metric | Điểm dễ làm sai |
|---|---|
| `safety_margin` | **min tích luỹ**, không phải giá trị hiện tại. An toàn là trường hợp xấu nhất; một con số hồi phục lại sau pha suýt va là con số **quên mất pha suýt va**. |
| `exposure_s` | tính bằng **giây**, không phải số mẫu. Vòng điều khiển chạy nhanh gấp đôi sẽ trông như phơi nhiễm gấp đôi. |
| `progress_rate` | **khác tốc độ**. Robot dao động tại chỗ ở full speed thì có tốc độ mà không có tiến độ — chênh lệch đó chính là điểm cần thấy. |
| `path_efficiency` | tiến độ **trên tuyến reference** chia quãng đường **đã chạy**. Xem mục 4 — đây là chỗ bản nháp đầu tiên suýt hỏng. |

---

## 3. Composite: có, nhưng không được phép đọc thành ΔU

`partial_advantage` = đánh đổi an toàn–hiệu quả của chính deployment, trên **phần đã
diễn ra**, dạng `A − B`.

**Không tự chế điểm số.** Nó gọi thẳng `_safety()` và `_efficiency()` của
`planbench_decision.objectives` — đường cong mục tiêu của chính nền tảng, phân giải
theo anchor của chính deployment. Một đường tính điểm thứ hai kiểu "gần đúng `U_S`"
chính là **parallel source** mà HĐ-5 cấm ở mọi chỗ khác, và nó sẽ lệch với card ngay
lần đầu ai đó chỉnh anchor.

**Chỉ hai trong bốn mục tiêu.** `U_R` là *có tới đích không* — nửa chừng episode thì
nó **không có giá trị**; một ΔU cục bộ sẽ bịa ra giá trị đó, và nó còn **đảo chiều**:
bên đang thua ở giây thứ mười vẫn thắng cả episode. Trọng số `w_s`/`w_e` được
**chuẩn hoá lại trên hai trục** — để nguyên giá trị bốn-trục sẽ cho ra con số không
bao giờ chạm được 1, trông như mọi candidate đều kém.

**Nó *bám theo* giá trị thật chứ không *hội tụ* về.** Docstring bản đầu tôi viết là
"converges" — sai, và tôi đã sửa. Lý do: metric episode đo hiệu quả theo `L_ref`
(tuyến ngắn nhất map cho phép), còn cái này đo theo **reference line của replay**.
Hai đường khác nhau thì hai tỉ số khác nhau. Có test ghim đúng sự chênh lệch đó.

Vì vậy: **hết episode, panel giao lại cho `episode_decision_utility` đã lưu sẵn
trong report** — con số thật, đủ bốn trục. Composite không bao giờ được đứng một
mình làm câu trả lời.

---

## 4. Lỗi suýt ship: `path_efficiency` luôn bằng 1.0

Bản nháp nối API dùng **quãng đường đã chạy tích luỹ** làm `progress_m` (chỗ giữ tạm,
vì tưởng projection đã nằm sẵn trong view).

`path_efficiency` = tiến độ / quãng đường đã chạy. Nếu tiến độ **chính là** quãng
đường đã chạy thì tỉ số này **bằng đúng 1.0 cho mọi candidate, mọi episode, mãi mãi**.
Nó render bình thường, đọc thì hợp lý, và **không đo gì cả**.

Đã sửa: `_slice_for` gọi `project(track, reference)` với **đúng đường reference mà
view đã công bố** — cùng một cây thước với thang tiến độ ở biểu đồ ngay trên nó. Hai
cây thước trên một màn hình là cách một bảng so sánh bắt đầu mâu thuẫn với biểu đồ
phía trên.

Test ghim lại: robot đi vòng, kết thúc ở **6 m** trên reference sau khi đã chạy
**12 m**, cho `path_efficiency = 0.5`. Bản dùng quãng đường đã chạy sẽ trả 1.0.

---

## 5. Thêm: reference line giờ đã là **kế hoạch thật**

Phụ phẩm của E4.5. `build_replay_sync_view` luôn có tham số `planned_path` nhưng chưa
ai truyền được — plan bị vứt đi sau khi chạy. Sidecar E4.5 ghi lại polyline của mọi
lần planning, endpoint trace phục vụ chúng, nên giờ:

```
projection_quality: degraded_candidate_path  ->  reference_plan
```

Lấy **attempt đầu tiên**, không phải attempt cuối: arc length phải đo dọc **một
đường duy nhất** cho cả episode, còn tuyến sau replan chỉ mô tả phần sau nó. Run cũ
(trước E4.5) vẫn fallback, và view vẫn **nói rõ nó đã fallback sang thấu kính nào**.

---

## 6. Từ chối thay vì đọc nhầm hàng

- **`None`, không phải `[]`**, khi không dựng được so sánh. Anchor không phân giải
  được thì không có đường cong mục tiêu. Danh sách rỗng sẽ đọc thành *"hai bên y hệt
  nhau"* — ngược hẳn với *"không tính được"*. UI phân biệt hai trạng thái này.
- **Cột lệch độ dài thì từ chối.** Payload đọc theo cột bằng `.get(name, [])`, nên
  file trace thiếu một cột sẽ tới đây thành list rỗng. Đọc `clearance_m` tại chỉ số
  hàng lấy từ `t` khi đó là `IndexError` — hoặc tệ hơn, với cột chỉ ngắn hơn một
  chút, là **đọc đúng cú pháp một thời điểm khác của episode**. Validator trên
  `TraceSlice` chặn tại schema.

---

## 7. UI

Nằm **trong** panel progress-sync, ngay dưới thanh trượt — vì nó **đọc chính thanh
trượt đó**. Vị trí kéo trên panel này đã là mét tiến độ, tức đúng trục của thang; đặt
chỗ khác thì phải có bản sao thứ hai của vị trí, và hai vị trí là hai thứ có thể lệch
nhau.

| File | Việc |
|---|---|
| `lib/running.ts` | **phần quyết định**: hướng tốt/xấu từng metric, hai đồng hồ, chọn nấc thang, caveat |
| `components/RunningComparison.tsx` | phần vẽ — hai bảng, không phải một |
| `globals.css`, i18n en/vi | style + 20 khoá |

**Vì sao tách `lib/running.ts`.** Cùng lý do như `lib/evidence.ts`: repo không có
jsdom. Và thứ đáng sai nhất ở đây **vô hình trong ảnh chụp màn hình** — tô đậm "số
lớn hơn" là đúng cho `safety_margin` và **sai cho `elapsed_s`**; cả hai ô render y
hệt nhau, còn bảng thì đang nói với người đọc rằng run chậm hơn là run an toàn hơn.

Thêm: `leader()` có **ngưỡng hoà theo tỉ lệ**. Không có nó thì hàng nào cũng có kẻ
thắng, kể cả hàng lệch nhau ở chữ số thập phân thứ sáu — và một bảng **không bao giờ
hoà** dạy người đọc bỏ qua phần tô màu.

---

## 8. Test

| File | Số test |
|---|---|
| `tests/test_explanation_running_metrics.py` | 17 |
| `tests/api/test_api_running_comparison.py` | 10 |
| `apps/web/src/lib/__tests__/running.test.ts` | 17 |
| `apps/web/src/app/__tests__/running-comparison.test.tsx` | 30 |

Chạy lại các suite liên quan: **78 passed** (Python: running metrics, replay sync,
replay view, API explanation, obstacle tracks), **112 passed** (web). `ruff` sạch,
`tsc --noEmit` sạch.

---

## 9. Còn lại

- **Chưa commit** — chờ lệnh An.
- Chưa xác minh trên một run thật đi hết đường: cần một sweep có đủ hai candidate
  qua cổng trên cùng episode.
- Full suite chưa chạy.

---

## 10. Bổ sung sau khi An chạy thử

### 10.1 Panel nằm sau nút chuyển alignment

An báo không thấy metrics hiện lên. Không phải lỗi run, và **không cần tạo run mới**:
trang mở mặc định ở `syncMode = "time"`, còn panel nằm trong `ProgressSync`, chỉ
render ở nhánh `"progress"` (`page.tsx:398-401`). Bấm **"By progress"** là ra.

Đặt ở đó là cố ý: bảng đọc nấc của **thang tiến độ**, mà thanh trượt trên panel này
đã tính bằng mét tiến độ. Ở tab "time" thanh trượt là giây — cùng một component sẽ
đọc nhầm trục.

Đã kiểm trên run cũ 19-08 (`sudden_stop_2`): `running` trả về đủ 40 nấc, số thật.
Run cũ vẫn dùng được.

### 10.2 Lỗi đọc sai lộ ra từ chính lần chạy thử đó

Kết quả trên run cũ:

```
mid @ 6.22 m   eff 1.000/0.860
```

Run cũ không có sidecar ⇒ E4.5 không có kế hoạch để chiếu ⇒ E2 lùi về dùng **quỹ đạo
của chính candidate A** làm reference line. Khi đó tiến độ của A **bằng đúng** quãng
đường A đã chạy ở mọi mẫu, nên `path_efficiency` của A bằng 1.000 **do định nghĩa**,
dù nó chạy thế nào.

Bảng đang tô đậm ô đó như kẻ thắng. Đó là **tuyên bố kết quả trên một phép so sánh
chưa từng được thực hiện** — và phần thắng rơi vào candidate nào tình cờ được truyền
vào view trước.

**Sửa:** `isRulerArtefact(row, side, ruler)` trong `lib/running.ts`. `leader()` nhận
thêm tham số `ruler` và **không trao phần thắng** cho hàng mà một bên không thể thua.
Ô đó chuyển sang xám, kèm dấu † và câu giải thích ở `title` + `sr-only`. Giữ số chứ
không giấu: **giá trị là thật, cái nó làm bằng chứng thì không**.

Sáu test mới, trong đó hai cái giữ cho bản sửa không quét sạch cả cột:
`leader(..., null)` vẫn trả `"a"`, và các hàng khác trên cùng run vẫn được chấm.

Trên run mới (có sidecar) không có dấu † nào, vì reference là kế hoạch thật.

**Test:** 59 passed (web), `tsc --noEmit` sạch.

---

## 11. Đưa metrics động xuống thẳng dưới canvas

An yêu cầu: không muốn phải bấm "By progress" mới thấy; muốn thêm vài metric động vào
hàng tile ngay dưới mỗi canvas để **so bằng mắt**; metric tĩnh/tổng kết episode vẫn ở
dưới như cũ.

### 11.1 Điểm khó thật không phải chỗ đặt, mà là số ở đâu ra

Hàng tile dưới canvas tính thẳng từ trace trong `TraceViewer`. Tính thêm
`safety_margin`, `exposure_s`, `path_efficiency` ngay tại đó bằng TypeScript là dựng
**bản cài đặt thứ hai** của `running_metrics` — hai định nghĩa của "clearance nhỏ
nhất tới giờ", tự do trôi khỏi nhau, và **trôi thì không nhìn ra được**: cả hai đều
render, cả hai đều trông như clearance. Đúng thứ HĐ-5 cấm.

Nên server phát chuỗi theo từng bước trace.

### 11.2 `sample_series` thành bản cài đặt duy nhất

`sample_at` trước đây quét lại tiền tố mỗi lần gọi. Gọi nó cho từng dòng trace là bậc
hai theo độ dài (trace dài 1121 dòng). Nên:

- `sample_series(slice_, deployment=...)` — **một lượt duy nhất**, tích luỹ mang theo:
  quãng đường, min clearance, exposure, p99 latency giữ sắp xếp bằng `insort`, mép
  cửa sổ rate đi hai con trỏ.
- `sample_at(slice_, index, ...)` giờ **chỉ lấy chỉ số** vào chuỗi đó. Không phải một
  phép suy ra thứ hai.

Bốn test mới cho các bất biến mà chỉ chuỗi mới nói được: đúng một entry mỗi dòng
trace; min-tới-giờ không hồi phục, exposure không trả lại, replan không rút lại được;
và một test riêng chứng minh ba cái trên **không pass bằng chuỗi phẳng**.

### 11.3 API: một phép tính, hai hình dạng

`replay-sync` trả `running` thành:

```
{ ladder:  [...],                       # cặp, theo nấc tiến độ — cho bảng
  by_step: { a: [...], b: [...] } }     # riêng từng candidate, mỗi dòng trace — cho tile
```

Cả hai ra từ **cùng một lượt tính trên cùng một reference line**, nên tile dưới canvas
và bảng phía trên **không thể mâu thuẫn nhau**. Vắng mặt cùng lúc, vì cùng phụ thuộc
một bộ anchor.

Tile đánh chỉ số bằng **đúng dòng mà pose được vẽ ra** (`running?.[visibleStep]`), nên
con số và con robot trên canvas không bao giờ là hai thời điểm khác nhau.

### 11.4 Vì sao trước đó không hiện — và bản sửa

Request `replay-sync` chỉ được gửi khi `syncMode === "progress"`. Giờ gửi ở **cả hai**
chế độ: chuỗi `by_step` là trạng thái của **riêng từng candidate tại dòng hiện tại của
chính nó**, không phụ thuộc hai panel được ghép theo kiểu gì.

Năm tile mới, đặt **giữa** hai tile tức thời (clearance/latency hiện tại) và hai ô
tổng kết (độ dài episode, sự kiện cuối):

| Tile | Loại |
|---|---|
| Đã đi được (%) | động |
| Clearance tệ nhất tới giờ (bán kính robot) | động, tích luỹ |
| Thời gian trong khoảng cảnh báo | động, tích luỹ |
| Tiến độ trên mỗi mét đã chạy | động, **mang dấu †** khi candidate đó là thước |
| Replan tới giờ | động, tích luỹ |

Metric tĩnh (Result, Travel time, Min clearance, P99, Collisions, Replans) giữ nguyên
ở bảng dưới — có test khẳng định thứ tự đó, vì một ô tích luỹ trộn vào bảng tổng kết
sẽ đọc thành một con số tổng nữa.

### 11.5 Đo trên hai run thật

Run mới (có sidecar, `reference_plan`):

```
by_step : a=440 dòng, b=449 dòng
a end  progress 1.000  margin 1.89  exposure 0.00  eff 0.908  replans 1
b end  progress 1.000  margin 2.11  exposure 0.00  eff 0.886  replans 1
```

`eff` cuối chuỗi khớp đúng nấc cuối của thang (0.908 / 0.886) — hai hình dạng, một
phép tính.

Run cũ (không sidecar, `degraded_candidate_path`):

```
a end  progress 1.000  margin 2.01  exposure  0.00  eff 1.000†  replans 1
b end  progress 1.000  margin 0.62  exposure 38.15  eff 0.937   replans 3
```

Đây đúng là kiểu so sánh bằng mắt mà An muốn: B ôm sát vật cản **38 giây**, clearance
tệ nhất 0.62 bán kính, replan 3 lần. Còn `eff 1.000` của A mang dấu † vì chính quỹ
đạo của A là thước.

**Test:** 69 + 37 passed (Python), 1107 passed (web), `ruff` sạch, `tsc --noEmit` sạch.

Ghi chú: chạy pytest xen kẽ `tests/api/... tests/... tests/api/...` cho lỗi
`fixture 'client' not found`. Đã kiểm bằng ba file cũ hoàn toàn — **quirk sẵn có** của
cách repo này khám phá conftest, không liên quan tới thay đổi ở đây.

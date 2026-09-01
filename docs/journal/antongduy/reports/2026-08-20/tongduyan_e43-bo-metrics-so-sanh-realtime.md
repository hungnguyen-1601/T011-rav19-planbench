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

---

## 12. Sắp lại hàng tile: động ở trên, tĩnh ở dưới

### 12.1 Một lỗi tìm thấy khi soi ảnh chụp của An

Ảnh cho `Route covered 63.7 %` trong khi robot mới đi ~30% chiều ngang canvas.

Nguyên nhân: `progress_fraction` chia cho **nấc cao nhất của thang**,
`max(row.progress_m)` — tức quãng mà **cả hai** candidate cùng đi tới được. Episode
đó B timeout nên quãng chung ngắn hẳn, và phân số phình lên. Nhãn nói "tuyến", mẫu số
lại là một thứ khác; ở một episode mà B chết sớm, tile sẽ báo **100% khi robot mới đi
nửa map**, và không có gì trên màn hình nói rằng thang đo vừa đổi.

Sửa: chia cho `reference.length_m` — chiều dài của chính đường reference. Đo lại trên
run thật: A giờ kết thúc ở **0.982** thay vì 1.000, đúng sự thật (robot dừng trong
dung sai đích, ngắn hơn tuyến 11 m một chút).

Ba test: dừng sớm thì không đọc thành 1.0; đi hết tuyến thì đọc 1.0 (để test trên
không pass bằng việc mọi run đều ngắn); và một source check, vì hậu quả **không nhìn
ra được trong ảnh chụp**.

### 12.2 `Episode length` và `Last event` rời khỏi hàng động

Theo yêu cầu của An — chúng là kết quả cuối, không phải realtime.

- **`Episode length` không được "chuyển xuống" mà bị bỏ.** Nó là `trace.t.at(-1)`,
  đúng bằng `Travel time` ở bảng dưới, chỉ khác nguồn: một cái lấy từ timestamp cuối
  của trace, một cái lấy từ outcome đã chấm. Chuyển xuống là đặt cùng một số hai lần
  trong một bảng. Khoá i18n `trace.duration` đã xoá luôn.
- **`Last event` chuyển xuống, đặt cạnh `Result`, không gộp vào.** `Result` là cách
  **cổng đọc** episode; `Last event` là bản ghi cuối của **chính HĐ-5**. Chúng trùng
  nhau ở hầu hết run — đó đúng là lý do gộp lại thì sẽ không ai phát hiện.

### 12.3 Một khung, hai trạng thái

Bản đầu tôi làm sai ý An: đổi **từng tile** khi hết episode. An muốn khác — **cùng một
khung**, đang chạy thì là chỉ số realtime, chạy xong thì chính khung đó thành metrics
cuối, và metrics cuối bị **ẩn hoàn toàn** trong lúc đang chạy. Đã làm lại theo đúng
vậy, và bản này **ít nhánh hơn** bản cũ.

Lý do thiết kế thì vẫn giữ nguyên, chỉ là giải quyết triệt để hơn:

- Đang chạy mà bày sẵn kết quả cuối bên cạnh thì **một con số tổng nằm trong hàng số
  đọc tức thời sẽ bị đọc thành số đọc tức thời**.
- Chạy xong mà vẫn để hàng realtime thì đó là **một loạt số đứng yên dưới nhãn ghi
  "now"**. Chính là ca candidate B trong ảnh của An: `Planner latency now 7.63 ms`
  cạnh `P99 2101.63 ms`.

Đổi cả khung giải quyết cả hai, và **bỏ hẳn** cơ chế đổi-từng-tile lượt trước.

Bảng kết quả **được truyền vào** viewer chứ không dựng trong đó: viewer biết trace,
không biết run được chấm thế nào. Tính lại min clearance từ cột clearance ngay tại
viewer là bản cài đặt thứ hai của một con số bảng kia đang render — hai chỗ rồi có
thể báo hai min khác nhau cho cùng một episode.

### 12.4 Nút chuyển, và vì sao nó là **một** nút

Nút "Xem kết quả cuối" ở thanh công cụ, `auto` ⟷ `final`:

- **`auto`** (mặc định): mỗi replay tự đổi sang kết quả **khi chính nó chạy hết**.
- **`final`**: cả hai hiện kết quả ngay, không cần xem hết.

**Đặt ở thanh công cụ chứ không phải mỗi canvas một nút.** Hai panel hiện hai *loại*
số khác nhau thì không đọc chéo được — mà đọc chéo là lý do duy nhất chúng nằm cạnh
nhau.

Bấm lần nữa thì về `auto`. Không có đường về thì việc xem kết quả sớm thành cửa một
chiều, và kéo thanh trượt sau đó sẽ nhìn vào một bảng không thèm phản ứng với thanh
trượt.

Ở chế độ time, A (22.8 s) hết trước B (60 s), nên panel A đổi sang kết quả trong khi
B còn chạy. Đó là hành vi đúng — và tự nó đã nói lên một điều.

Một ca biên: candidate không nạp được trace thì **không có replay để chạy hết**, nên
không có hàng realtime nào để thay. Bảng kết quả hiện thẳng, không giấu sau một phép
đổi không có gì để đổi.

**Test:** 58 + 27 passed (Python), **1130 passed** (web), `ruff` sạch, `tsc` sạch.

---

## 13. Nút không tìm thấy, và biểu đồ độ trễ

### 13.1 Nút có render — nhưng ở sai chỗ

An báo không thấy cách nào chuyển sang metrics cuối giữa chừng. Nút **có** render,
nằm trong `.episode-toolbar` — tức **ba mục phía trên** khu vực canvas, chỗ người
đang xem replay không bao giờ nhìn tới.

Một điều khiển đổi nội dung của khung metrics thì phải nằm **cạnh khung đó**. Đã
chuyển xuống ngay trên lưới hai canvas, dưới legend. Có test khoá thứ tự
`toolbar < legend < toggle < grid`, vì "nút tồn tại" và "nút tìm thấy được" là hai
chuyện khác nhau, và bản trước đã pass mọi test trong khi không dùng được.

### 13.2 Biểu đồ độ trễ planner

Đặt ngay dưới metrics của từng candidate, mỗi thuật toán một biểu đồ, thay vào chỗ
đoạn chữ giải thích màu.

**Vì sao riêng latency đáng có biểu đồ.** Đây là đại lượng duy nhất ở đây mà **một
con số không nói được**: tile đọc "now", bảng kết quả đọc p99 — cả hai đều là bản tóm
tắt của một *hình dạng*. Candidate B trong ảnh của An hiện `7.63 ms` ở thanh trượt
bên cạnh `p99 2101.63 ms`; không cách sắp xếp hai con số nào giải thích được vì sao.

Hai quyết định đáng sai, và **không cái nào nhìn ra được trong ảnh chụp** — nên tách
sang `lib/latencyChart.ts` để test được:

- **Tick không chạy planner không phải tick tốn 0 ms.** Cột lưu 0 ở những tick
  planner không chạy. Polyline xuyên qua các số 0 đó sẽ **bổ nhào xuống trục giữa các
  lần replan**, vẽ ra một hình răng cưa trông như độ trễ dao động dữ dội, trong khi
  sự thật là "ở đây không có gì xảy ra". Các điểm đó **ngắt đường** thay vì được vẽ.
- **Trục dọc phải chịu được bốn bậc độ lớn.** Đo trên trace thật: run lành 0.66–11.24
  ms so với ngân sách 50 ms; run kẹt có peak **3032 ms**. Nên trục **luôn bao gồm
  ngân sách**: run còn dư thì đường nằm thấp và ngưỡng ở trên, run vượt thì ngược
  lại. Không dùng log — người đọc phải nhớ "trục này là log" là người đọc sẽ đọc sai
  đúng cái biểu đồ quan trọng nhất.

Vẽ thêm **đường p99** (lấy từ outcome đã chấm, không tự tính lại percentile — tính
lại là ý kiến thứ hai về con số bảng dưới đang hiện), vì một spike đơn lẻ chiếm trọn
trục dọc và nếu không có nó thì phần thân của run không còn gì tóm tắt được.

Ngưỡng lấy từ `control_period_s` — **thêm vào payload trace lần này**. Hardcode 50 ms
sẽ chấm sai mọi deployment khai chu kỳ điều khiển khác.

Playhead bám `trace.t[visibleStep]`, cùng dòng mà pose được vẽ.

### 13.3 Đoạn chữ giải thích màu: chuyển, không xoá

An bảo thay vào chỗ đoạn chữ đó. Nhưng xoá hẳn thì canvas mất phần giải thích màu là
gì, chấm đỏ là gì, đường nét đứt là gì.

Đoạn đó vốn render **một lần cho mỗi candidate** — cùng bốn câu, hai lần, cạnh nhau —
mà nó mô tả **cách canvas được vẽ**, tức một sự thật về cả cặp chứ không phải mỗi bên
một bản. Nên chuyển lên **legend dùng chung**, đúng chỗ nó giải thích, còn lại một
bản. Chỗ dưới canvas trống ra cho biểu đồ.

**Test:** 10 test cho `latencyChart` (ngắt đoạn, thang đo, playhead), 13 test cho vị
trí và ràng buộc nguồn số. Tổng **1153 passed** (web), `ruff` sạch, `tsc` sạch.

---

## 14. Biểu đồ thành một chỉ số realtime thật

An yêu cầu hai điều: biểu đồ **vẽ dần theo replay** chứ không bày sẵn hình đã xong, và
nó **thuộc khung realtime** nên mất khi episode chạy hết.

### 14.1 Chỗ khó không phải việc cắt, mà là thang dọc

Cắt polyline tới playhead thì dễ. Nhưng nếu vẫn lấy `max` của **cả episode** làm trần
trục dọc thì **trục đã tiết lộ trước cái kết**: nó chốt ở 3000 ms từ giây đầu, tức
người xem biết sắp có spike vài giây trước khi đường vẽ tới đó. Xem một biểu đồ đã nói
trước đoạn kết thì không còn là realtime nữa.

Nên trần trục dọc là **max chạy dần** trên phần đã vẽ. Nó **chỉ tăng, không bao giờ
giảm** — đó là thứ giữ cho hình khỏi giật: một thang được phép co lại sẽ vẽ lại toàn bộ
đường mỗi lần một đỉnh cũ hết là đỉnh.

Trục ngang thì **ngược lại — cố định theo cả episode ngay từ khung hình đầu**. Trục
thời gian mà giãn theo playhead sẽ giữ đường luôn chiếm hết bề ngang và **bóp dẹp hình
dạng của nó khi chạy**, đọc thành "planner đang ổn định dần" trong khi không có gì
thay đổi.

Badge "vượt ngân sách" cũng chạy dần: sáng lên vì một spike còn cách mười giây nữa là
đang báo cáo tương lai.

### 14.2 Đường p99 đổi thành p99-tới-giờ

p99 của cả episode là **một con số từ tương lai** khi replay còn đang chạy. Thay bằng
p99 tích luỹ — lấy từ chính `compute_budget` của chuỗi running, nhân ngược lại thành
mili giây.

Đây là **phép nghịch đảo chính xác** của cách nó được chuẩn hoá
(`_percentile(...) / (T_cycle * 1000)`), không phải một phép tính percentile thứ hai:
một bản cài đặt, hai đơn vị. Nên đường trên biểu đồ và tile compute ngay cạnh nó
**không thể lệch nhau**.

### 14.3 Vào trong khung realtime

Biểu đồ chuyển vào **trong nhánh** mà bảng kết quả thay thế, nên nó biến mất cùng các
tile khi episode chạy xong hoặc khi bấm "Xem kết quả cuối". Prop `p99Ms` mà trang
truyền xuống thành thừa — đã bỏ.

**Test:** 17 test cho `latencyChart` (7 cái mới cho phần vẽ dần: không vẽ quá playhead,
thang không tiết lộ spike, badge không sáng sớm, trục ngang cố định, thang dọc không
bao giờ co, kẹp hai đầu, và vẫn vẽ cả episode khi không truyền playhead). Tổng
**1162 passed** (web), `tsc` sạch.

Một chỗ test suýt hỏng: assertion neo vào chuỗi có ký tự xuống dòng, vỡ khi ghi file.
Đổi sang regex `showFinal \? \([\s\S]*?<LatencyChart` — neo theo cấu trúc, không
theo vị trí dòng, nên thêm một tile nữa không làm nó gãy.

---

## 15. Biểu đồ kiêm luôn thanh thời gian

An muốn bấm vào một vị trí trên biểu đồ thì replay nhảy về đúng thời điểm đó, và
**áp cho cả hai thuật toán** để giữ tính realtime.

### 15.1 Cú bấm cho ra giây, nhưng thanh trượt không phải lúc nào cũng đo bằng giây

Đây là chỗ dễ làm sai. Ở chế độ **time**, hai panel dùng chung đồng hồ tường nên số
giây đi thẳng vào scrubber. Ở chế độ **progress**, scrubber đo bằng **mét arc length** —
áp thẳng số giây vào đó sẽ nhảy tới một vị trí **không liên quan gì** tới chỗ vừa bấm,
mà vẫn trông như nó có phản ứng.

Nên thêm `sideProgress(view, seconds, side)` vào `lib/replaySync.ts` — phép nghịch đảo
của `sideTime` đã có sẵn, đọc **cùng bộ rows** mà view công bố. Hai ràng buộc:

- **Cùng quy ước với `sideTime`** (nấc cuối tại hoặc trước giá trị hỏi, không nội
  suy), nên `time → progress → time` quay về đúng chỗ xuất phát thay vì trôi một nấc
  mỗi vòng. Có test round-trip.
- **`null` là "run này chưa tới đây", không phải "nó ở đây lúc t=0".** Đọc thành 0 thì
  những nấc cuối của một run có bạn đồng hành dừng sớm sẽ **kéo scrubber về đầu**. Có
  test riêng cho ca rows lệch.

Kẹp về nấc mà **cả hai** run cùng tới được — đúng tầm mà scrubber progress thật sự có.

### 15.2 Hằng số hình học chuyển vào lib

Vẽ đường và bắt điểm bấm phải dùng **cùng một bộ padding**. Hai bản sao thì mọi cú
bấm lệch đúng 44 đơn vị viewBox — vài giây trên episode ngắn — mà **biểu đồ vẫn trông
đúng**, vì đường và playhead đều vẽ từ bản sao mà component đang giữ.

Nên `CHART`, `PLOT_WIDTH`, `PLOT_HEIGHT` và `timeAtFraction()` nằm ở
`lib/latencyChart.ts`; component import về. Ba test: giữa vùng vẽ ra giữa episode, hai
mép vùng vẽ ra hai mép episode, và bấm vào **máng nhãn trục bên trái** thì kẹp về 0
chứ không trả thời gian âm.

### 15.3 Không chỉ chuột

Bấm được mà không dùng bàn phím được thì đó là một điều khiển một nửa số người đọc
không với tới. SVG chuyển `role="img"` → `role="slider"` khi có `onSeek`, kèm
`tabIndex`, `aria-valuemin/max/now/text`, và phím Trái/Phải (2% episode mỗi lần),
Home/End. Khi không seek được thì vẫn là `img` — gắn role slider lên thứ không set
được giá trị là thông báo một điều khiển không tồn tại.

### 15.4 Seek thì dừng phát

Bấm mà vẫn chạy tiếp thì nó đi khỏi đúng cái khoảnh khắc vừa được hỏi. Cả hai nhánh
đặt `playing: false`; có test đếm đúng hai chỗ.

**Test:** 20 test `latencyChart`, 16 test `replaySync` (6 mới cho `sideProgress`), 6
test cho phần nối. Tổng **1177 passed** (web), `tsc` sạch.

---

## 16. Hai lần đảo lại quyết định của chính tôi

Cả hai thay đổi lần này đều lật ngược điều tôi đã lập luận ở mục trước. An đã dùng
thật rồi, nên theo đó — và tôi sửa **cả phần bình luận trong code**, không để lại một
lập luận đã bị bác nằm cạnh đoạn code làm ngược nó.

### 16.1 Bấm biểu đồ thì không pause nữa

Tôi từng viết: *"bấm mà vẫn chạy tiếp thì nó đi khỏi đúng cái khoảnh khắc vừa được
hỏi"*, và đặt `playing: false` ở cả hai nhánh.

Dùng thật thì ngược lại. Bấm vào biểu đồ **chính là cách nhảy tới đoạn đáng xem để
*xem nó chạy***; phải bấm play lại mỗi lần khiến biểu đồ thành một scrubber tệ hơn
chính cái scrubber. Giờ `seekFrom` **không đụng vào trạng thái phát** — đang chạy thì
chạy tiếp từ chỗ mới, đang dừng thì vẫn dừng.

### 16.2 Nút kết quả cuối tách riêng mỗi bên

Tôi từng lập luận phải dùng chung một nút: *"hai panel hiện hai loại số khác nhau thì
không đọc chéo được, mà đọc chéo là lý do duy nhất chúng nằm cạnh nhau"*.

Lập luận đó **đã sai sẵn với chính hành vi tự động của nó**: mỗi replay tự đổi sang kết
quả khi **chính nó** chạy hết, nên một run 22.8 s và một run 60 s đã hợp lệ khác loại
nhau suốt nửa episode. Và nó **cấm mất đúng ca người đọc cần**: xem kết quả của stack
đã xong trong khi stack kia còn đang chạy.

Giờ mỗi panel một nút, đặt trong header của chính panel đó, cạnh badge kết quả. State
đổi từ `"auto" | "final"` dùng chung sang `{ a: boolean; b: boolean }`.

Một chi tiết đi kèm: `aria-label` của nút mang theo tên stack. Hai nút cùng ghi
"Show final results" là hai điều khiển mà screen reader không phân biệt được.

**Test:** hai test cũ khẳng định đúng hành vi vừa bỏ (`playing: false` xuất hiện đúng
hai lần; "một nút cho cả hai canvas") — đã viết lại thành khẳng định hành vi mới, kèm
lý do đổi. Tổng **1178 passed** (web), `tsc` sạch.

---

## 17. Dọn chữ giải thích khỏi tab decision

An: mọi câu kiểu *"Six feasibility gates run before anything is scored (HĐ-7)…"* gói
hết vào một dấu `?`, di chuột mới hiện; câu nào không đại diện cho phần nào thì bỏ hẳn.

### 17.1 Dùng lại `Hint`, không viết mới

Repo **đã có** `components/Hint.tsx`, dựng cho đúng vấn đề này ở trang Deployment, với
đúng lập luận: *"panel bốn phần năm là chữ thì không ai đọc — phần giải thích lấn át
chính những trường nó đang giải thích"*. Nó giữ nguyên văn bản làm **accessible name**
của dấu `?`, nên screen reader, người dùng bàn phím và tìm-kiếm-văn-bản vẫn với tới
được. Viết một tooltip thứ hai là một cách nói khác của "mất một nửa số người đọc".

### 17.2 Ranh giới: câu nào được phép ẩn

Đây là phần đáng nghĩ, không phải phần gõ code.

- **Giải thích thường trực của một mục** → vào `?`. Nó là nền, có thể đợi tới lúc được
  hỏi. Chín câu: `gates.note`, `trace.note`, `trace.colourNote`, `card.scopeNote`,
  `tally.note`, `filter.note`, `launch.note`, `map.note`, `preview.sharedNotice`.
- **Thông điệp chỉ xuất hiện ở một trạng thái** → **giữ nguyên trên màn hình**. "Run
  này bị cắt ngang", "hai candidate được cho xem thứ khác nhau", "detector đã chạy và
  không thấy gì". Đó là **phát hiện**, và một phát hiện nằm sau dấu chấm hỏi không ai
  trỏ vào là một phát hiện không ai đọc. Cả `EvidencePanel` vì thế **không đụng tới**.
- **Câu chỉ dẫn thừa** → bỏ hẳn. `trace.pickEpisode` ("Select an episode to compare
  both candidates visually") nằm ngay trên một `<select>` đã có nhãn của chính nó — một
  `?` ở đó sẽ là dấu hỏi không giải thích gì. Xoá khoá khỏi cả hai locale.

Một chỗ tôi làm sai rồi sửa: `decisions.map.note` ban đầu tôi **xoá luôn**. Nhưng nó
giải thích vì sao chọn map khác lại tạo deployment **mới** thay vì sửa cái đang chọn —
mất nó là mất một lời giải thích thật. Đã gắn lại vào `?` cạnh ô nhập id mới, đúng
control mà nó nói về.

### 17.3 Ngoại lệ duy nhất: caveat của composite

`running.composite.partial` từng có bình luận của chính tôi: *"đặt cạnh con số chứ
không sau tooltip: một composite mà caveat có thể bị bỏ lỡ là một composite sẽ bị đọc
thành ΔU"*.

Vẫn đúng. Nên chỉ **phần dài** vào `?`, còn ba chữ **"không phải ΔU"** ở lại trên màn
hình dưới dạng badge. Một cảnh báo phải trỏ vào mới thấy là cảnh báo sẽ bị bỏ lỡ bởi
đúng người cần nó.

### 17.4 Test giữ ranh giới đó

`decision-prose.test.tsx`, 35 test. Không chỉ kiểm "đã có Hint" mà kiểm cả ba mệnh đề:
mỗi câu nền **đi qua Hint** và **không còn là một `<p>`** (khớp theo *hình dạng render*,
nên viết lại đoạn chữ dưới class khác vẫn bị bắt); mỗi câu nền **vẫn còn trong cả hai
locale** (ẩn chứ không xoá); và mỗi **phát hiện vẫn ở dạng chữ**, không nằm sau Hint.

Một chỗ suýt vô nghĩa: mẫu `t("KEY")` không bắt được các ca chọn khoá bằng ternary
**bên trong** lời gọi — nó sẽ báo xanh cho một thông điệp đã bị giấu. Đổi sang bắt
chính khoá.

Dọn kèm: 4 rule CSS chết, 1 khoá i18n chết.

**Test:** 1214 passed (web), `tsc` sạch.

---

## 18. Mỗi gate một dấu hỏi: nó đang chặn cái gì

An: cạnh mỗi gate G1–G6 một dấu `?` giải thích gate đó **đang chặn điều gì**.

Chữ viết ra từ **docstring của chính từng gate** trong
`packages/decision/planbench_decision/gates.py`, không viết theo trí nhớ. Điểm nhấn là
"chặn cái gì" chứ không phải "đo cái gì" — một cột đề "G4" với ô đỏ bên dưới nói rằng
candidate bị loại, mà **không nói bị loại vì gì**:

| Gate | Chặn |
|---|---|
| G1 | planner quá thường xuyên **không tìm ra tuyến nào** — tách khỏi G3 vì không tìm được tuyến và tuyến không trụ nổi trước giao thông là hai việc, sửa ở hai tầng |
| G2 | **mọi va chạm** — và cả bảng sạch dựa trên quá ít lần chạy *phân biệt*: 0 va chạm trong 10 lần vẫn tương thích với tỉ lệ 26% |
| G3 | quá nhiều episode **không tới đích**, bất kể hỏng kiểu gì |
| G4 | planner **trễ deadline điều khiển**; đo trên máy benchmark, không có hệ số quy đổi sang board đích |
| G5 | stack **không vừa ngân sách RAM** của board; ước lượng từ cấu trúc dữ liệu ở kích thước bản cài đặt đích, không lấy RSS Python |
| G6 | candidate **cần một loại quan sát deployment không cấp** — quyết trước khi chạy episode nào |

Gắn ở cả hai chỗ bảng gate xuất hiện: header bảng đầy đủ và danh sách gọn trong thẻ
candidate.

**Test:** khoá được đúng thứ dễ trượt — key dựng lúc chạy từ id gate
(`` `decisions.gates.blocks.${gate}` ``), nên **không có phép quét source nào bắt được
thiếu một cái**; thiếu thì dấu `?` sẽ hiện ra chính cái key và đọc thành dữ liệu hỏng.
Test duyệt `GATES` và đòi cả hai locale, cộng một test đòi câu chữ nói "blocks". 1227
passed (web), `tsc` sạch.

---

## 19. Ghi chú vận hành: `dev_stack.sh restart` không chạy được trên Windows

An yêu cầu từ nay xong thay đổi thì tự restart FE + BE. Lần đầu làm thì phát hiện:

```
$ bash scripts/dev_stack.sh restart
Stopping PlanBench
ERROR: setsid is missing inside WSL.
```

`setsid` là lệnh Linux; Git Bash trên Windows không có. Điều đáng nói không phải là nó
lỗi, mà là **thứ tự**: `stop` chạy xong rồi `start` mới gãy, nên lệnh này để lại stack
**đang tắt** — tệ hơn là không chạy gì.

Thêm nữa, `stop` cũng chỉ dừng nửa vời: tiến trình web cũ vẫn giữ cổng 3000 và trả 500,
khiến `next dev` mới nhảy sang 3001 — trình duyệt ở 3000 sẽ thấy một trang hỏng chứ
không phải trang mới.

Đã xử lý tay: kill PID giữ 3000 và 8000 cũ, khởi động lại
`.venv/Scripts/python scripts/serve.py --reload` và `npm run dev`. Hiện API 8000 và web
3000 đều trả 200.

**Chưa sửa `dev_stack.sh`** — nằm ngoài phạm vi An giao và là script dùng chung. Nếu An
muốn thì sửa được: thay `setsid` bằng nhánh dùng `start //b` trên Windows, và để `stop`
chỉ chạy khi `start` chắc chắn có đường chạy.

---

## 20. Sắp lại trang, bỏ bảng gate, phân trang episode

### 20.1 Thứ tự mới

```
SampleBanner → Comparison result → Watch an episode
             → Explanation + Evidence → Gates → phần còn lại
```

Hai vị trí giữ nguyên vì là **lập luận chứ không phải sở thích**, và có test riêng:
`SampleBanner` đứng đầu (nó phủ định mọi con số bên dưới), và `ExplanationHeader` **ngay
trên** `EvidencePanel` — test cắt đoạn giữa hai component và đòi không có component nào
chen vào, chứ không chỉ đòi "đứng trước".

### 20.2 Bỏ bảng gate — nhưng nó mang hai thứ thẻ so sánh không có

An: thẻ comparison đã liệt kê gate rồi. Đúng — thẻ có đủ G1–G6, danh sách gate chặn,
success rate, p99, số run phân biệt, replan. Bảng lặp lại tất cả một lần nữa.

Nhưng bỏ hẳn thì mất hai thứ:

- **`ObservationNotice`** — cảnh báo hai candidate được cho xem thứ khác nhau. Đó là
  một **phát hiện về tính công bằng**: ΔU khi đó đo đặc quyền chứ không đo planner. Đã
  **chuyển sang đầu khối comparison**, không để nó rơi theo bảng mà nó tình cờ nằm trong.
- **Candidate thứ 3 trở đi.** Thẻ comparison chỉ vẽ `candidates.slice(0, 2)`. Với run 3
  candidate, bảng gate là **chỗ duy nhất** những cái còn lại xuất hiện — bỏ đi là mất
  hẳn khỏi trang, không dấu vết.

Nên: bảng chỉ còn render khi **> 2 candidate**. Lý do An đưa ra (thừa) đúng với 2
candidate, và chỉ đúng với 2.

### 20.3 Dấu `?` sát cạnh Gx

Chip gate có `justify-content: space-between`, nên `Gx`, `?` và verdict bị đẩy xa nhau
— dấu `?` rơi vào giữa ô trông như một cột thứ ba. Bọc `Gx` + `?` vào một span; verdict
vẫn nằm phải.

### 20.4 Phân trang episode

5 episode một trang, dải tab để chuyển. **Dải tab cũng phải giới hạn**: 300 episode là
60 trang, mà 60 tab là đúng cái vấn đề phân trang sinh ra để giải quyết, chỉ khoác một
control khác. `pageWindow` cắt tối đa 7 tab và **giữ nguyên số tab ở hai đầu** — cửa sổ
trượt đối xứng sẽ hiện 4 tab ở trang đầu và 7 ở giữa, tức control đổi bề rộng khi đi
qua.

Ba ca không nhìn ra được trên run 5 episode — tức mọi run đã xem tới giờ, và đúng lý do
bảng này ban đầu không có phân trang:

- **Lọc làm danh sách co lại dưới tay người đọc.** Bật "chỉ episode có bên hỏng" khi
  đang ở trang 7/12 có thể còn 2 trang; trang 7 của 2 là bảng trắng, đọc thành "run
  không có episode nào". Đã kẹp.
- **Lựa chọn nằm ngoài trang.** Bấm exemplar nhảy tới episode có thể ở trang 9; để dải
  tab đứng yên thì không có dòng nào sáng, đọc thành "bấm không ăn".
- **Danh sách rỗng.** `pageCount(0) = 1`, không phải 0 — "trang 1/0" là control không
  vẽ được.

18 test cho `lib/episodePages.ts`.

### 20.5 Bỏ dropdown chọn episode

Nó liệt kê id và không gì khác, nên chọn từ đó là chọn mù. Bảng phía trên đã nói
episode nào có bên hỏng và hai candidate bất đồng ở đâu — đó mới là thứ người ta chọn
theo. Lối chọn còn lại: dòng bảng, chip exemplar, pager.

Một ca biên: run **không có outcome từng episode** thì không vẽ được bảng, và dropdown
từng là lối chọn **duy nhất**. Bỏ đi mà không làm gì là khoá người đọc vào episode đầu
tiên. Đã cho pager một chế độ `bare`: vẫn 5 id một trang, cùng dải tab — đúng thứ
dropdown từng cấp, không thêm dropdown nào về.

**Test:** 1250 passed (web), `tsc` sạch. Không restart server (theo yêu cầu mới của An).

---

## 21. Comparison mở rộng theo số candidate, và bảng metric cuối

### 21.1 Bỏ giới hạn hai candidate

Lưới vẽ `candidates.slice(0, 2)`, nên run đăng ký thuật toán thứ ba sẽ vẽ hai thẻ và
**bỏ rơi phần còn lại, không dấu vết nào trên trang**. Giờ map toàn bộ, lưới
`repeat(auto-fit, minmax(260px, 1fr))` — thẻ thứ ba làm cột hẹp lại chứ không làm mất
một cột. Nhãn A/B/C sinh từ chỉ số; màu cặp chỉ có hai nên từ C trở đi thẻ trung tính,
không tái dùng màu xanh của A cho D.

### 21.2 Bỏ hẳn bảng gate — và mang theo hai thứ nó giữ riêng

Lượt trước tôi để bảng sống sót khi > 2 candidate. Giờ comparison đã lo được mọi
candidate nên bảng thừa hoàn toàn. Xoá luôn cả `GateTable` và `CandidateRow`.

Nhưng bảng có hai thứ **không** trùng với thẻ, và bỏ im lặng mới là cái giá thật của
việc dọn:

- **Candidate được cho xem gì.** `ObservationNotice` chỉ kêu khi các class **khác
  nhau**. Một candidate đơn lẻ mà không ai khai input thì không sinh cảnh báo nào và
  cũng không còn cột nào — tức đúng cái sự thật người kiểm tra tính công bằng tìm sẽ
  biến mất. Đã đưa lên thẻ, kèm badge "không khai báo".
- **Bị rút sớm.** Candidate dừng trước sẽ chạy ít episode hơn, nên **mọi con số trên
  thẻ đó dựa trên mẫu nhỏ hơn**. Đã đưa lên thẻ.

Câu `decisions.gates.note` (giải thích sáu gate là gì) mất chỗ bám khi tiêu đề bảng
biến mất — đã gắn vào `?` cạnh danh sách gate trong thẻ.

### 21.3 Bảng metric cuối: 10 hàng, đọc ngang

`lib/candidateMetrics.ts`. **Gần như không tính gì.** Chỗ nào nền tảng đã ra số thì
đọc thẳng từ **chính gate đã phán quyết dựa trên nó** — G1 no-path rate, G2 số va chạm
và cận trên 95%, G4 p99 gộp, G5 ước lượng bộ nhớ. Tính lại trong browser là một định
nghĩa thứ hai tự do trôi khỏi cái mà verdict dựa vào, và **trôi thì không nhìn ra**:
cả hai đều render như cùng một đại lượng.

| Hàng | Nguồn |
|---|---|
| Tỉ lệ thành công | candidate + ngưỡng từ G3 |
| Số va chạm | G2 |
| Cận trên 95% xác suất va chạm | G2 |
| Tỉ lệ không tìm ra tuyến | G1 |
| Clearance tệ nhất cả run | rút gọn từ cột episode |
| Thời lượng episode trung vị | rút gọn từ cột episode |
| p99 planner | candidate + ngưỡng từ G4 |
| Ước lượng bộ nhớ | G5 + ngân sách RAM |
| Số episode phân biệt | candidate |
| Số replan | candidate, **không chấm ai dẫn** |

**Không có hàng decision utility.** Card chỉ mang nó cho candidate được khuyến nghị;
lấy trung bình `episode_decision_utility` ở đây chính là đường tính điểm thứ hai mà cả
phiên này tôi đã tránh. ΔU và khoảng tin cậy đã nằm trên card.

Hai hàng **là** phép rút gọn, và chúng mang tính mô tả chứ không phải chấm điểm:
clearance tệ nhất (trung bình sẽ giấu mất một pha suýt va) và **trung vị** thời lượng
(trung bình bị một lần timeout ở đúng mức trần kéo lệch hàng chục giây, rồi mô tả cái
trần chứ không mô tả stack).

`replans` **không có chiều tốt/xấu**: replan vốn đã bị tính tiền bằng thời gian và độ
trễ, và deployment không khai ngân sách replan nào — tô xanh ở đây là tính tiền hai
lần theo một luật không ai viết ra.

`leaders()` trả về **một tập chỉ số**, không phải một người thắng: với ba candidate,
hai bên có thể ngang nhau ở vị trí tốt nhất, và chọn bừa một trong hai là tung đồng xu
rồi render ra như một kết quả. Mọi bên bằng nhau ⇒ không ai được tô.

Mỗi hàng có `?` nói **vì sao chỉ số đó đáng so**, và ngưỡng của deployment nằm ngay
dưới tên hàng — "17.89 ms" không có nghĩa gì nếu thiếu "50 ms".

### 21.4 Hai lỗi tôi tự gây trong lúc dọn

- Heuristic bắt cặp ngoặc để xoá hàm **ăn lẹm mất `ExportReport`** (nó nằm chung một
  dải doc comment với hàm bên cạnh). Bắt được bằng `tsc`, khôi phục nguyên văn từ
  `HEAD` rồi xoá `CandidateRow` bằng biên chính xác thay vì đoán.
- Mười test đỏ sau khi bỏ bảng. **Không cái nào là test lỗi thời hết** — hai cái
  (`observation-class`) chỉ ra đúng hai thứ tôi suýt làm rơi ở 21.2. Số còn lại đã
  chỉnh hướng, mỗi cái ghi rõ điều nó khẳng định đã chuyển đi đâu.

**Test:** 19 test `candidateMetrics`, tổng **1269 passed** (web), `tsc` sạch, en/vi
cùng 1538 khoá, không lệch.

### 21.5 Gộp bảng metric vào chính thẻ

Bản đầu tôi để metric cuối thành **một bảng riêng dưới lưới thẻ**. Không đúng ý An, và
xét lại thì cũng không đúng: cùng mười đại lượng xuất hiện ở hai chỗ trên một màn hình
— bản tóm tắt bốn dòng trên thẻ và mười hàng của bảng — nên so hai stack thành việc
nhìn hai hướng.

Giờ mỗi thẻ mang đủ mười hàng. Vẫn đọc ngang được: các thẻ nằm chung một lưới và render
**cùng thứ tự hàng**, nên hàng thứ ba của thẻ này thẳng hàng với hàng thứ ba của thẻ
kia. Đặt `min-height` cho mỗi hàng để nhãn dài ngắn khác nhau không làm lệch lưới.

`comparisonRows` tính **một lần cho cả lưới** rồi phát cho từng thẻ kèm chỉ số cột —
`leaders()` so ngang giữa các candidate, nên một thẻ không thể tự biết nó có dẫn hay
không.

Một assertion tôi viết ra rồi phải sửa: nó tìm chuỗi `"distinctEpisodes"` trong source
của trang. Nhưng trang nội suy `` t(`decisions.compare.${metric.key}`) `` nên **không
bao giờ đánh vần tên metric nào** — test đó sẽ xanh kể cả khi hàng bị xoá. Đổi sang
khẳng định trên `comparisonRows()`, tức đúng module định nghĩa hàng.

**Test:** 1269 passed (web), `tsc` sạch.

### 21.6 Cân lại tỉ lệ hàng metric

An: chữ quá bé hoặc ô quá to.

Cả hai. Hàng mang `min-height: 48px` từ hồi nó chỉ có bốn dòng và thừa chỗ; nhãn 11px,
số 13px. Mười hàng như thế đọc thành chữ nhỏ bơ vơ trong hộp cao.

- Bỏ `min-height`. **Nó chưa bao giờ là thứ căn hàng** — các thẻ thẳng hàng vì cùng
  render một bộ nhãn theo cùng thứ tự, nên chiều cao tự nhiên đã bằng nhau. Cái tối
  thiểu cố định chỉ làm tất cả cùng cao quá.
- Nhãn 11 → 12.5px, số 13 → 14px, padding dọc 9 → 7px, `align-items: baseline` để nhãn
  và số nằm cùng đường chữ.
- `white-space: nowrap` cho số, để "2098.40 ms" không xuống dòng.

Một lỗi CSS bắt được lúc sửa: selector `.metric-comparison-row span` có specificity
**cao hơn** `.hint-mark`, nên nó áp cỡ chữ của nhãn lên dấu `?` nằm bên trong vòng tròn
15px cố định. Đã thu về con trực tiếp `> span`.

**Test:** 1269 passed (web).

### 21.7 Hình dạng cuối: một cột nhãn, mỗi thuật toán một cột

Bộ metric này đã qua ba hình dạng, và mỗi lần đổi đều vì một lý do thật:

1. **Bảng riêng dưới lưới thẻ** — thẻ vẫn giữ bản tóm tắt bốn dòng, nên cùng một đại
   lượng xuất hiện hai chỗ trên một màn hình.
2. **Đưa hết vào trong thẻ** — hết trùng lặp, nhưng mỗi nhãn bị in lại một lần cho mỗi
   candidate, và hai con số cần so lại nằm hai bên một đường viền thẻ.
3. **Một bảng, nhãn một cột, mỗi candidate một cột** — so sánh trở thành liếc dọc một
   hàng.

Thẻ giờ chỉ giữ thứ **thật sự thuộc về từng candidate**: danh tính, nó được cho xem gì,
có bị rút sớm không, và sáu verdict gate. Không có metric nào lặp lại ở đó — chính chỗ
chồng lấn ấy là thứ làm hình dạng (1) thành thừa.

Dọn kèm: `.candidate-result-metrics` và `.metric-comparison-row` giờ không style cho
cái gì nữa, đã xoá.

**Test:** 1269 passed (web), `tsc` sạch.

### 21.8 Hình dạng thứ tư — và là hình dạng đúng

An: giữ trong card, hai màu, chung với gate cũng được; thu hẹp vùng màu để chừa một cột
cho tên metric.

Bảng ở 21.7 tách được tên metric ra một cột — đúng phần đọc — nhưng **mất màu card**,
nên hai candidate thôi phân biệt được bằng màu từ giữa mục trở xuống.

Giờ là **một lưới duy nhất**: cột trái là máng trung tính chứa tên metric, mỗi cột sau
là một candidate, **tô màu liền mạch** từ header xuống qua flags, giá trị, tới verdict
gate. Bỏ hẳn `CandidateComparisonColumn` và `MetricTable`.

Phát theo **hàng**, không theo thẻ. Một dãy thẻ không thể đảm bảo nhãn nằm ngang hàng
với giá trị của nó; lưới thì đảm bảo được, và ở mười metric thì đúng cái căn hàng đó
là toàn bộ khả năng đọc của nó.

Màu chỉ có hai: candidate thứ ba nhận `candidate-n` trung tính, **không quay vòng về
màu xanh của A** — đặt hai stack khác nhau vào một màu trên đúng cái trang có nhiệm vụ
phân biệt chúng thì hỏng mục đích.

### 21.9 Ba lần hỏng CSS liên tiếp — ghi lại vì cùng một nguyên nhân

Xoá rule CSS cũ, tôi làm hỏng ba lần:

1. **Lọc theo dòng** — để lại `.metric-table th,` cụt, tức một selector list bị cắt đôi.
   CSS không báo lỗi; nó **nuốt luôn rule ngay sau đó**.
2. **Regex `{...}`** — nối các rule vào chung một dòng và bỏ sót vài khối.
3. Chỉ đến lần ba, cắt theo **khoảng dòng tường minh** kèm assert "đoạn này có đúng tên
   rule không" và "số ngoặc có cân không", mới sạch.

Nguyên nhân chung: CSS dễ dãi với khoảng trắng, nên cả hai bản hỏng đều tạo ra file mà
trình duyệt **vẫn nhận**, chỉ âm thầm đánh rơi phần phía sau. Không có compiler nào bắt
hộ — chỉ có assert tự viết.

Dọn nốt bốn dòng chết trong `@media (max-width: 760px)` trỏ tới class đã biến mất.

**Test:** 1269 passed (web), `tsc` sạch, ngoặc CSS cân.

### 21.10 Tỉ lệ cột

Máng nhãn 20%, mỗi cột giá trị ~40% với số dán mép phải — chỗ trống dồn hết vào giữa,
trong khi nhãn dài phải xuống dòng.

Đảo lại: `minmax(200px, 1.2fr)` cho máng, `minmax(170px, 1fr)` cho mỗi candidate. Dùng
`fr` chứ không phải phần trăm để tỉ lệ tự giữ khi thêm candidate — hai bên thì máng 37%
mỗi cột 31%; ba bên thì 29% và 24%. Hai mức `minmax` sàn giữ cho không bên nào sập
trước khi breakpoint 900px xếp dọc.

**Test:** 1269 passed (web).

### 21.11 Cỡ chữ và căn lề trong lưới

- Tên metric: 12.5 → **14.5px, in đậm**, và đổi từ màu muted sang màu chữ chính. Máng
  trái là cột người đọc quét để tìm hàng cần, nên tên phải nặng hơn mức một dòng chú
  thích mờ.
- Giá trị: 14 → **16px**, và **căn giữa** thay vì dán mép phải.
- Ngưỡng dưới tên: 11 → 12.5px nhưng **giữ nhạt và không đậm** — nó bổ nghĩa cho metric,
  không phải một cái tên thứ hai.
- Badge ở hàng flags: 11 → 12px cho đồng bộ.

Ghi lại đánh đổi của việc căn giữa: chữ số vẫn thẳng nhau nhờ `tabular-nums`, cái mất
là **dấu thập phân không còn thẳng hàng dọc cột**. Ở đây chấp nhận được vì mỗi hàng
mang một đơn vị riêng, nên cột không được đọc như một đại lượng duy nhất — khác với
bảng một đơn vị, nơi mất căn thập phân là mất khả năng so sánh bằng mắt.

Ở breakpoint 900px (xếp dọc, nhãn nằm trên) giá trị vẫn căn trái: một con số căn giữa
dưới một nhãn căn trái đọc thành lạc chỗ.

**Test:** 1269 passed (web).

---

## 22. Bỏ ba panel cuối, và badge khuyến nghị thành tuỳ chọn

### 22.1 Ba panel nào

Ảnh An gửi có ba panel: **The world this was measured in** (`Conditions`), **Rebuilding
this** (`Provenance`), **Who acted on this** (`AuditTrail`).

Đáng nói: "Who acted on this" là `AuditTrail` — **nhật ký**, không phải `HumanActs`.
`HumanActs` ("Read it, and decide on it") là panel *thực hiện* việc duyệt, nằm ngay
trên và **vẫn giữ**. Nếu đọc lướt mà bỏ nhầm nó thì đã mất luôn khả năng approve một
run khỏi UI. Giờ chỉ mất phần **hiển thị** nhật ký; bản ghi vẫn được viết như cũ.

Bỏ luôn cả định nghĩa component chứ không để lại code không ai render. Cũng bỏ luôn
`listDecisionEvents` khỏi `refresh` — một request mà không ai đọc kết quả là request
sẽ tiếp tục chạy rất lâu sau khi nó hết ý nghĩa.

### 22.2 Một câu không được đi theo panel

`Conditions` có một thứ **không phải bối cảnh** mà là caveat cho một con số:

> Đo trên toàn bộ 20 nhân, không ghim: G4 đọc độ trễ theo đồng hồ tường nên mọi tải
> khác trên máy đi thẳng vào con số. Cùng candidate đo được **59,30 ms** không ghim và
> **16,10 ms** khi ghim 2 nhân.

Lưới so sánh giờ hiển thị **pooled p99 kèm `limit 50`** ngay giữa trang. Một con số có
thể sai gấp 3,7 lần mà đứng cạnh một ngưỡng thì tệ hơn là không có số nào. Nên câu đó
chuyển lên đầu khối comparison, cạnh `ObservationNotice` — cái finding còn lại cũng
phủ định mọi con số bên dưới. Render nguyên văn: nền tảng viết câu này khi nó biết run
không được ghim, client viết lại là client làm nhẹ nó đi.

### 22.3 Badge "no recommendation" thành tuỳ chọn

Chỉ hiện khi **có** khuyến nghị. Sự thật "run này không xếp hạng" vẫn được nói ở hai
chỗ khác và cả hai đều hữu ích hơn: badge `unranked` trên header, và panel `Outcome`
phía dưới — panel này còn phân biệt **ba tình huống no-card khác nhau** và nói nên làm
gì tiếp. Badge bị bỏ là bản kém nhất trong ba bản của cùng một câu.

### 22.4 Test

Ba test thuộc panel đã bỏ (biên độ nhiễu, run URI + checksum, cặp before/after của
nhật ký) — **bỏ theo panel**, không nhắm lại vào hư không. Một test kept-alive chống
lại một tính năng đã xoá là test rồi sẽ bị ai đó "sửa cho xanh" mà không biết vì sao
nó tồn tại.

Test thứ tư ghim câu cảnh báo unpinned — **giữ và nhắm lại**, cộng ba test mới: nó nằm
giữa `ObservationNotice` và lưới, nó render nguyên văn chuỗi của server, và
`listDecisionEvents` đã thôi được gọi.

**24 khoá i18n** của ba panel giờ không ai dùng. **Giữ nguyên, không xoá** — An nói
"tạm thời", mà xoá đi thì lúc panel quay lại phải dịch lại từ đầu; một ít dữ liệu chết
rẻ hơn thế.

**Test:** 1268 passed (web), `tsc` sạch.

---

## 23. Tuyến plan đổi màu mỗi lần replan

Bốn màu xoay vòng, `plannedRouteColour(attempt)` trong `lib/evidence.ts`.

**Vì sao nó không chỉ là trang trí.** Với một màu duy nhất cho mọi kế hoạch, người xem
kéo canvas **không phân biệt được "kế hoạch bị bẻ cong" với "kế hoạch bị vứt đi và vẽ
lại"** — giữa chừng hai thứ đó trông y hệt nhau, mà chỉ một trong hai là replan.

Bốn màu, xoay vòng: đủ để hai kế hoạch liên tiếp không bao giờ trùng màu, ít để còn
phân biệt được. Run có năm lần replan thì dùng lại màu đầu — chấp nhận được, vì câu hỏi
nó trả lời là "vừa đổi chưa", không phải "đây là attempt số mấy". An cũng nói không cần
theo thứ tự.

Chọn màu tránh những gì canvas đã tiêu: xanh dương và tím là đường đi của hai candidate,
hổ phách là vật cản động, đỏ là sự kiện HĐ-5. Có test khoá điều đó — một kế hoạch trùng
màu với một trong số đó sẽ bị đọc thành chính thứ kia. Vẫn giữ nét đứt và trong suốt:
đây là ý định, không phải số đo.

`attempt` không đọc được (NaN, 0, âm) thì lấy màu đầu — một chi tiết trang trí không
được phép làm hỏng canvas.

Sửa kèm `trace.colourNote`: bỏ chữ "dashed **grey**" vì gọi tên một màu giờ là mô tả
đúng kế hoạch đầu tiên và sai với phần còn lại; thay bằng câu nói rõ **đổi màu nghĩa là
replan** — không thì người đọc thấy bốn màu và hiểu thành bốn *loại* kế hoạch chứ không
phải bốn kế hoạch.

**Test:** 6 test cho bảng màu, 1274 passed (web), `tsc` sạch.

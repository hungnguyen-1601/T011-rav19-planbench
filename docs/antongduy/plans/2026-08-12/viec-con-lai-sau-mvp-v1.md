# Kế hoạch 12-08: việc còn lại sau MVP v1

> **Ngày lập:** 2026-08-11 (cho ngày làm 2026-08-12) · **Người lập:** An (cùng Claude)
> **Trạng thái:** chờ approve
> **Bối cảnh:** MVP v1 đã chốt (M0–M4), Phase 6.1 lược đồ đã xoay lại ở `0006`, Phase 6.2 router
> đã xong, và dự án có **tấm Decision Card đầu tiên** trên nền đã kiểm công bằng.
> **Nguồn:** `reports/2026-08-11/tongduyan_phase-6-2-va-tam-decision-card-dau-tien.md`,
> `notes/2026-08-11/tongduyan_survey-hien-trang-va-duong-toi-mvp.md`,
> `plans/2026-08-11/hoan-thien-mvp-phep-so-dau-tien.md`

---

## 0bis. Ba câu hỏi mở — **dev đã chốt 2026-08-11 tối**

### Q1 → `success_rate_min` của `open_hall_v2` = **1.00**

Nguyên văn lý do dev đưa: *"sảnh tham chiếu dễ, đối xứng, dùng để kiểm nền tảng và cấu hình.
**Acceptance deployment**: mọi failure trên nhiệm vụ đối xứng, dễ, dưới noise đã khai đều là tín
hiệu chẩn đoán; không dùng ngưỡng này làm yêu cầu vận hành kho."*

Đây là câu trả lời đúng loại mà HĐ-15.3 đòi: con số đến từ **vai trò của deployment**, không từ
kết quả của candidate nào. Và nó khai `open_hall` thành một **loại thứ ba** — không phải khách
hàng, không phải chỉ dụng cụ đối xứng, mà một **acceptance deployment**: nơi một thất bại là
triệu chứng chứ không phải thống kê.

**Hệ quả trên số liệu đang có** — kiểm luôn, không đoán:

| candidate | success | G3 ở 0.95 | G3 ở **1.00** |
|---|---:|---|---|
| `rrtstar+dwa` `dwa_coarse` | 30/30 = 100% | pass | **pass** |
| `rrtstar+dwa` `dwa_balanced` | 30/30 = 100% | pass | **pass** |
| `astar+dwa` cả ba cấu hình | 70–73% | fail | fail |

Tấm Decision Card đầu tiên **sống sót** qua thay đổi này. Nhưng phải nói rõ nó trở nên **chặt
hơn nhiều**: ở 300 episode, **một** lần stuck cũng làm trượt G3. Đó đúng là ý định — "mọi
failure đều là tín hiệu chẩn đoán" — và nó cần được nói ra để lần sau không ai đọc một G3 đỏ
trên sảnh như một thất bại của candidate.

### Q2 → kho chạy ở **1%** (300 episode)

Rủi ro đến từ hiện trường, không từ ngân sách máy. Chi phí đã tính ở B1: ~2,2 giờ, chạy tuần tự.

### Q3 → run không-card **được duyệt**, nhưng tách làm hai trạng thái

Nguyên văn: *"có thể run không card, tuy nhiên không biến nó thành artifact bị bỏ quên. Cần tách
thành `reviewed` và `approved_config`."*

Đây là một thiết kế tốt hơn đề xuất của tôi (tôi đề xuất cấm duyệt run không-card). Lý do nó tốt
hơn: cấm duyệt sẽ khiến bốn trên năm phép so đã chạy trở thành artifact **không ai từng nhìn**
— đúng cái "bị bỏ quên" mà dev nêu. Hai trạng thái tách bạch được hai việc khác nhau:

| Trạng thái | Nghĩa | Áp cho | Sinh ra gì |
|---|---|---|---|
| `reviewed` | *"đã có người đọc bảng cổng này và ghi nhận"* | **mọi** run | dấu vết audit + ghi chú |
| `approved_config` | *"khuyến nghị này được chấp thuận để xuất cấu hình"* | **chỉ** run có card | `approved_config.yaml` |

Ràng buộc phải giữ: `approved_config` **không** truy cập được từ một run không-card, và
`reviewed` **không** sinh ra file cấu hình nào. Trộn hai cái là biến *"đã đo"* thành *"đã chấp
thuận"* — đúng thứ dev cảnh báo.

---

## 0. Đứng ở đâu

| | |
|---|---|
| Nền tảng đo | ✅ 6 cổng, 60+ test công bằng, nhiễu theo seed, ghim nhân, manifest đầy đủ |
| Nền tảng so | ✅ `pipeline` + `selection` dùng chung cho CLI và API |
| API | ✅ `/task-profiles`, `/candidates`, `/decisions` — lưu được cả run có card lẫn không |
| Decision Card | ✅ một tấm, `local_controller_selection` trên `open_hall_v2` |
| Candidate đã đo | 6 (2 global × 3 local) |
| Deployment đã chạy | 1 (`open_hall_v2`) — **kho chưa bao giờ chạy dưới nhiễu** |

**Nguyên tắc xếp hạng của bản này giữ nguyên như plan 08-11:** một phép **đo** hợp lệ trước, một
phép **so** hợp lệ sau, một **sản phẩm** sau nữa. Việc nào làm phép đo đúng hơn xếp trên việc
làm kết quả dễ xem hơn.

---

## A. Nợ kỹ thuật từ chính lượt hôm qua *(làm trước, rẻ)*

### A1. Card sinh bởi `compare.py` thiếu quét độ nhạy — **ưu tiên cao nhất**

`vertical_slice.py` chạy `weight_stability` và `anchor_stability`; `compare.py` thì không. Nên
tấm card đầu tiên có `weight_stability_margin: null` và `anchor_stability: null`.

HĐ-12 quy định null nghĩa là *"chưa đo"*, nên card **trung thực nhưng thiếu** — và HĐ-11.5 gọi
độ nhạy là tính năng quan trọng nhất (N1): nó trả lời *"khuyến nghị này có lật khi trọng số xê
dịch không"*. Một khuyến nghị `CLEAR_RECOMMENDATION` mà không ai biết nó lật ở đâu là một nửa
câu trả lời.

Sâu hơn: đang có **hai bộ sinh card với độ đầy đủ khác nhau**. Nguyên tắc một-chuỗi của M3 đã áp
cho tầng **đo** nhưng chưa áp cho bước **lắp card**.

**Việc:** rút phần lắp card (recommendation → sensitivity → pareto → card + manifest) ra khỏi
`vertical_slice.py` vào `planbench_benchmark.selection`, để cả hai script và API cùng gọi. Hàng
rào giống M3: `tests/test_vertical_slice.py` phải xanh, và nếu phải sửa assertion thì refactor
đã đổi hành vi.

**Ước lượng:** 2–3 giờ. **Kiểm:** chạy lại phép so `rrtstar` coarse vs balanced, card mới phải
có hai trường độ nhạy khác null và `decision_utility` **không đổi** so với tấm cũ.

### A2. `run_uri` trỏ vào thư mục run, không vào bộ trace

`DecisionRunService._store` đặt `run_uri = str(run_root)` — đúng thư mục gốc của mọi run, không
phải của run này. `run_checksum` thì luôn `None`.

D15 nói card lưu **URI + checksum**, và checksum là thứ làm tham chiếu đó đáng tin thay vì trang
trí: một URI trần không nói được rằng những file nó trỏ tới đúng là những file card này được
tính từ đó.

**Việc:** `run_uri` trỏ đúng thư mục của run (`selection.run_dir_name` đã sinh tên), và
`run_checksum` băm tập trace đã dùng. **Ước lượng:** 1 giờ.

### A4. Manifest không ghi `constraints` — lộ ra khi chốt Q1 *(cùng họ với lỗ hổng đã sửa)*

Kiểm tấm card đầu tiên: manifest ghi `sensor_noise` (thêm ở 6.3.0) nhưng **không ghi
`constraints`**. Nên hai lần chạy cùng profile id dưới **hai ngưỡng `success_rate_min` khác
nhau** sinh ra **manifest giống hệt nhau** trong khi cho **phán quyết cổng khác nhau**.

Đúng họ với lỗ hổng `sensor_noise` vừa vá, và đúng họ với `manifest=None` vừa vá: một trường
quyết định kết quả mà không nằm trong hồ sơ tái lập.

**Nhưng cách sửa thì khác, và phân biệt này quan trọng:**

| Đổi cái gì | Ảnh hưởng | Trace cũ | Cách xử lý |
|---|---|---|---|
| `sensor_noise` | đổi **thế giới** | vô hiệu | **đổi `task_profile_id`** (đã là luật HĐ-13) |
| `constraints` | đổi **phán quyết** | vẫn đúng | **ghi vào manifest** |

`episode_context_id` không băm cả hai, nhưng lý do đổi id chỉ áp cho cái thứ nhất: episode ghi
dưới σ = 0 là episode của một thế giới khác, còn episode ghi dưới `success_rate_min = 0.95` là
**đúng episode đó**, chỉ được chấm bằng một thước khác.

**Nên khuyến nghị:** `open_hall_v2` **giữ nguyên id**, chỉ sửa `success_rate_min` tại chỗ, và
manifest thêm khối `constraints`. Trace được dùng lại — tiết kiệm ~1 giờ chạy lại 6 candidate —
và hai tấm card dưới hai ngưỡng phân biệt được nhau bằng hồ sơ chứ không bằng trí nhớ.

Nguyên tắc rút ra, đáng ghi vào contract: **`task_profile_id` định danh cái *thế giới*; manifest
phải ghi cái đã biến phép đo thành phán quyết.**

**Việc:** thêm `constraints` vào `Manifest` + schema JSON + `build_manifest`; bump contract
MINOR; sửa `open_hall_v2.yaml` lên 1.00 kèm comment nêu lý do "acceptance deployment"; chạy lại
ba phép so từ trace có sẵn (`--reuse-traces`, vài giây) để artifact khớp ngưỡng mới.

**Ước lượng:** 1,5 giờ. **Làm cùng lượt A1** vì cả hai đụng `build_manifest`.

### A3. `uv.lock` rỗng vẫn nằm trong cây làm việc

8 dòng, khai **không dependency nào**, trong khi `requirements.txt` ghim 20 gói. Xoá hoặc
gitignore — quyết định của dev, nhưng đừng để nó trôi vào commit nào.

---

## B. Đo cho đủ *(giá trị cao nhất về mặt khoa học)*

### B1. Kho `warehouse_a_v2` ở mức 1% — **deployment thật duy nhất chưa chạy**

Mọi kết luận hiện có đều trên `open_hall_v2`, mà sảnh là **dụng cụ đo**, không phải khách hàng.
Ngưỡng `success_rate_min: 0.95` của nó còn được chép từ kho và chưa bao giờ khai riêng cho sảnh
(xem C3).

Kho thì khác: 40×25 m, kệ thật, traffic thật, và 95% success **có nghĩa thật** ở đó.

**Hai ẩn số chỉ lần chạy mới trả lời được:**

1. `n_distinct` của `astar+dwa` trên kho **sau khi có nhiễu**. Trước nhiễu nó là 1/100. Nhiễu
   theo seed sửa đúng ca đó, nhưng trên kho thì chưa ai đo.
2. Có candidate nào qua đủ sáu cổng trên kho không. Trên sảnh chỉ RRT\* qua.

**Chi phí:** N_min = 300 ở mức 1%, hai candidate ⇒ 600 episode. Ở ~13 s/episode (kho lớn hơn
sảnh) là **~2,2 giờ**, cần máy rảnh và **chạy tuần tự** (HĐ-7.4: hai run ghim song song giành
cùng hai nhân).

**Đề xuất:** chạy `astar+dwa:dwa_coarse` vs `rrtstar+dwa:dwa_coarse`, scope
`global_planner_selection`. Đó là câu hỏi gốc của đề tài.

**Cảnh báo trước, để kết quả xấu không bị đọc nhầm:** nếu cả hai trượt G2 vì `n_distinct` thấp
thì đó là **nhiễu chưa đủ chạm tới kho**, không phải nhiễu hỏng — và hướng xử lý là **đo nhiễu
thật của LiDAR 2D và bánh vi sai rồi khai đúng**, không phải vặn σ lên tới khi `n_distinct` đẹp.

### B2. `astar+ppo` — candidate thứ ba chưa ai chạm

Có sẵn trong registry, `benchmarkable=True`, chưa từng vào phép so nào. Nó là stack **modular**
(A\* quy hoạch, PPO bám đường), nên **không** vướng nợ adapter monolithic ở C1.

Cần `torch` (nhóm optional, vài GB) và một checkpoint. **Ước lượng:** nửa ngày nếu checkpoint đã
có; không rõ nếu phải train.

**Giá trị:** đây là candidate đầu tiên có **lớp quan sát khác** hai stack cổ điển, nên nó là
phép thử thật đầu tiên của G6 và của P02.

---

## C. Nợ chặn tuyên bố "công bằng cho mọi thuật toán"

### C1. Adapter `MonolithicPolicy` + bất cân xứng lưới replan

Hai việc dính nhau và **phải làm cùng lượt**.

`nav_stack._replan` dựng lưới quy hoạch tạm với **vị trí thật** của vật cản động. Hôm nay công
bằng vì mọi candidate đều `modular` và nhận cùng lưới. Ngày adapter monolithic chạy được, một
policy end-to-end chỉ thấy `Observation` còn global planner của stack modular thấy vật cản
**thật sự ở đâu** — đúng đặc quyền mà G6 sinh ra để định giá, và nó ưu ái stack modular vì lý do
không liên quan tới chất lượng điều hướng.

HĐ-4.1 đã ghi luật: gỡ đặc quyền **trước** khi chấm candidate `monolithic`, và lời giải hợp lệ
là **replan từ `Observation`** — không phải cấp ground truth cho cả hai bên.
`test_only_modular_stacks_can_run_today` sẽ đỏ đúng ngày adapter được thêm.

**Ước lượng:** 1–2 ngày. **Vì sao không gấp:** chưa có candidate `monolithic` nào, nên chưa có
vấn đề. Nhưng tuyên bố *"nền tảng công bằng cho mọi thuật toán"* mới được chứng minh trên **hai
global planner cùng kiểu tìm đường trên lưới với một local controller** — phép thử thật của
tuyên bố đó chưa chạy.

### C2. Map vừa khó vừa đối xứng

`open_hall` đối xứng nhưng dễ; kho khó nhưng **chưa có kiểm đối xứng nào**. Một map vừa khó vừa
đối xứng là phép kiểm mạnh hơn cả hai. Điểm mù ② của survey 08-11.

**Ước lượng:** nửa ngày (đã có `scripts/make_fairness_map.py` làm mẫu, và bài học "sinh ra được
+ test khẳng định đối xứng" thay vì vẽ tay rồi tin).

### C3. ~~`success_rate_min` của sảnh chưa bao giờ được khai riêng~~ — **đã chốt, gộp vào A4**

Dev đã quyết: **1.00**, vì `open_hall` là một **acceptance deployment** (xem 0bis/Q1). Việc gõ
gộp vào A4 vì cùng đụng manifest và cùng cần chạy lại ba phép so từ trace có sẵn.

Điều còn lại của mục này: viết comment vào profile nêu đúng lý do dev đưa, để lần sau không ai
đọc `1.00` như một yêu cầu vận hành. Mọi hằng số khác trong file đều có comment; con số này
từng là ngoại lệ duy nhất, và nó là ngoại lệ đã sinh ra cả câu hỏi.

---

## D. Bề mặt sản phẩm *(làm sau, không làm phép đo đúng hơn)*

### D1. Phase 6.3 — Approval → `approved_config.yaml`

Hạ tầng đã chạy thật: `approval.py` có `Role`, `Capability`, state machine, chống tự duyệt, audit
append-only.

**Một quyết định phải chốt trước khi gõ:** chỉ run **có card** mới duyệt được. Một run không rank
được không có gì để duyệt, và cho phép duyệt nó là biến *"đã đo"* thành *"đã chấp thuận"*.

**Ước lượng:** 2–3 giờ.

### D2. Phase 7 — trang `/decisions`

Ràng buộc đã ghi từ plan 08-11 và giờ có bằng chứng: trang phải render **cả hai** loại artifact.
Bốn trong năm phép so đã chạy **không ra card**. Một UI chỉ render được Decision Card sẽ tạo lại
đúng áp lực buộc mọi run phải rank được — áp lực đã sinh ra tấm card tuyên bố cận trên va chạm
từ một episode.

Nội dung theo backlog 08-08 mục 7.1–7.4, cộng: bảng cổng phải là **màn hình hạng nhất**, không
phải tab phụ.

---

## E. Nợ cũ chưa động, ghi để không rơi

- `instance_difficulty` chưa nối vào tầng quyết định (cache P03 khoá theo `scenario_name` cũ).
- `robustness_margin` vẫn null — cần Task Neighborhood (pha 2).
- `business_adjusted` có anchor tiền nhưng chưa demo được hai chân trời lật khuyến nghị (N3).
- Ghim nhân đã cưỡng chế trong code, nhưng **không có gì chặn hai run song song** — chỉ có điều
  khoản HĐ-7.4. Một cờ file khoá là rẻ nếu ai đó vấp thật.

---

## Thứ tự đề xuất cho ngày 12-08

```
B1 kho ở mức 1%  (~2,2 h máy)  ── bật CHẠY NỀN TỪ SÁNG, trước mọi thứ khác
        │                          (nó chỉ chiếm 2 nhân; phần còn lại làm song song được
        │                           MIỄN LÀ không chạy run đánh giá thứ hai — HĐ-7.4)
        │
A1 độ nhạy vào card    (2–3 h) ─┬─ cùng đụng build_manifest, làm một lượt
A4 constraints + 1.00  (1,5 h) ─┘
        │
A2 run_uri + checksum  (1 h)
        │
        └── chạy lại ba phép so từ trace có sẵn (vài giây) => artifact khớp ngưỡng mới
                   │
                   └── báo cáo: deployment thật đầu tiên + card đầy đủ
```

**Nếu chỉ có nửa ngày:** A1 + A4 + A2. Chúng làm tấm card hiện có **đầy đủ** và không tốn giờ
máy — sau ba việc này, card mới có đủ độ nhạy, đủ hồ sơ tái lập, và đúng ngưỡng đã chốt.

**Nếu có máy rảnh cả ngày:** bật B1 chạy nền **trước tiên** lúc bắt đầu, rồi làm A trong lúc
chờ. B1 là thứ duy nhất trong danh sách phụ thuộc vào đồng hồ.

**Cố ý không xếp vào ngày mai:** C1 (adapter monolithic, 1–2 ngày), B2 (`astar+ppo`, phụ thuộc
checkpoint), D1/D2 (bề mặt sản phẩm). Cả bốn đều đúng việc, không cái nào gấp hơn A và B.

---

## Câu hỏi mở

Ba câu của bản nháp đã được dev trả lời — xem mục **0bis**. Còn lại đúng một, và nó nảy ra *từ*
câu trả lời thứ nhất:

**Giữ `open_hall_v2` hay lên `v3` khi đổi `success_rate_min`?**

Khuyến nghị ở A4: **giữ `v2`**, vì đổi ngưỡng chấm không làm episode cũ sai — nó chỉ chấm chúng
bằng thước khác. `task_profile_id` định danh cái *thế giới*; cái đã biến phép đo thành phán
quyết thì thuộc về manifest. Giữ id còn tiết kiệm ~1 giờ chạy lại 6 candidate.

Phản biện đáng cân nhắc: một người ngoài nhìn `open_hall_v2` ở hai thời điểm sẽ thấy hai
deployment khác nhau mang cùng một tên. Nếu dev thấy điều đó nặng hơn 1 giờ chạy lại thì lên
`v3` — nhưng khi đó vẫn **phải** thêm `constraints` vào manifest, vì lần sau ai đó sửa ngưỡng mà
quên đổi id thì không có gì bắt được.

---

## Kết cục của câu hỏi `success_rate_min` — ghi ngày 2026-08-12

Câu hỏi trên đã được trả lời (**giữ `v2`, thêm `constraints` vào manifest** — A4 làm cả hai), nhưng
bản thân **con số** thì chưa xong, và nó rẽ ra một việc mới phải nhớ.

**Diễn biến trong ngày:**

1. `success_rate_min` lên `1.00` trên cả hai sảnh (A4), đúng theo lập luận vai trò nghiệm thu.
2. Full suite đỏ 3 test. Nguyên nhân: HĐ-8.3 luật 2 buộc `bad` của anchor `success_rate` trỏ vào
   chính ngưỡng ấy, nên `1.00` làm `good == bad` và **`U_R` mất thang**.
3. Chốt lần một: giữ `1.00`, sảnh thành dụng cụ chỉ gác cổng (HĐ-8.4 ra đời từ đây).
4. **Đảo lại cùng ngày:** giữ *cơ chế*, lùi *ngưỡng* về `0.95` trên cả hai sảnh. Lý do: mất khả
   năng xếp hạng trên sảnh kéo theo `measure.py` không ra `decision_utility`, tấm card duy nhất
   không tái lập được, và UI phải dựng thêm một loại artifact — quá nhiều cho lúc MVP còn dở.

**Việc còn lại (F1), làm sau MVP:**

> Tìm cách để sảnh vừa giữ chuẩn nghiệm thu `1.00` vừa còn thang cho `U_R`.

Ba hướng chưa xét kỹ, ghi để lần sau khỏi nghĩ lại từ đầu:

- **Tách cổng khỏi thang.** `success_rate_min` là ngưỡng G3; `bad` của anchor là mốc thang. Luật 2
  gộp chúng để file anchor không trôi khỏi deployment — nhưng có thể cho khai `anchor_floor` riêng
  *kèm ràng buộc* `anchor_floor <= success_rate_min`, thì thang sống mà vẫn không tự đặt bar hộ ai.
- **Cho anchor khai `bad` dự phòng khi ngưỡng chạm trần.** Hẹp hơn, ít đụng luật 2 hơn.
- **Chấp nhận sảnh chỉ gác cổng**, chuyển hẳn việc xếp hạng sang C2 (map vừa khó vừa đối xứng,
  chưa có). Đây chính là chốt lần một; nó khả thi, chỉ là **chưa tới lúc**.

**Không được quên:** cơ chế xử lý `1.00` đã có sẵn và có test (`TestAGateOnlyDeploymentIsMeasuredButNotScored`
chạy trên fixture tổng hợp). Việc còn lại là **quyết định**, không phải hiện thực. Theo dõi ở
`docs/KNOWN_LIMITATIONS.md` L6.

---

## Cập nhật cuối ngày 2026-08-12

| mục | trạng thái |
|---|---|
| A1 độ nhạy vào card | ✅ xác minh sống trên card dựng lại: `weight_stability_margin: 1.0`, `anchor_stability: unchanged_at_±10%`, `pareto_label: PARETO_FRONTIER` |
| A2 `run_uri` + checksum | ✅ xác minh sống: URI trỏ đúng thư mục run, checksum `947e4b5742156caf…` |
| A3 `uv.lock` rỗng | ✅ **gỡ khỏi repo + gitignore** kèm lý do. `requirements.txt` là nguồn sự thật duy nhất về dependency |
| A4 `constraints` vào manifest | ✅ đủ 9 trường |
| B1 kho ở mức 1% | ⚠️ 245/300, dev chủ động dừng; cả hai trượt G2+G3 |
| C3 ngưỡng sảnh | ✅ có comment; **con số** thành nợ L6, hẹn sau MVP |
| D1 approval 6.3 | ✅ tách `review_state` / `config_state`, lược đồ `0007`, 52 test |
| Dừng sớm (ngoài kế hoạch) | ✅ G1/G2/G3/G5, cả hai pha |

**Còn nợ, không mục nào chặn D2:** B2 (`astar+ppo`) · C1 (adapter monolithic + bất cân xứng lưới
replan) · C2 (map khó + đối xứng) · L6 (ngưỡng sảnh) · kho chưa khai `sensor_noise` ⇒ cần
`warehouse_a_v3` · mục E.

**Tiếp theo: D2 — trang `/decisions`.** Ràng buộc từ plan 08-11 vẫn nguyên và nay có thêm bằng
chứng: trang phải render **cả hai** loại artifact, và bảng cổng phải là màn hình hạng nhất. Bốn
trên năm phép so đã chạy không ra card. Một UI chỉ dựng được Decision Card sẽ tạo lại đúng áp lực
buộc mọi run phải rank được — áp lực đã sinh ra tấm card tuyên bố cận trên va chạm từ một episode.

Nay có thêm một trạng thái thứ ba phải dựng được: **run bị ngắt giữa chừng** (B1 dừng ở 245/300),
và một trục thứ tư: `review_state` × `config_state`.

---

## Quan hệ giữa hai stack — **dev chốt 2026-08-12 tối**

Câu hỏi: luồng cũ (`map → simulate → benchmark → accept`) và luồng mới
(`deployment → candidate → sáu cổng → Decision Card → duyệt`) là hai sản phẩm
trong một repo. Cái nào thay cái nào?

**Chốt: xây SONG SONG cho tới hết MVP, rồi mới quay lại tinh gọn.**

Lý do chốt như vậy, sau khi khảo sát: thay ngay là việc nhiều ngày và có một
khoảng trống không chấp nhận được ở giữa.

### Quy mô thật của việc thay thế

80 endpoint cũ, 10 endpoint mới. Nhưng không phải 80 cái đều bị thay:

| nhóm | số | số phận nếu thay |
|---|---|---|
| `benchmarks` `leaderboard` `algorithms` `generalization` `scenario-protocol` `difficulty-calibration` `tuning` | ~24 | **bị thay** |
| `auth` `users` `reviews` | 16 | **giữ** — cắt ngang cả hai luồng |
| `maps` `scenarios` `scenario-library` `robot-profiles` | 12 | **giữ, đổi vai** — thành nguồn dựng task profile |
| `simulations` `episodes` | 9 | **khoảng trống lớn nhất** |
| `models` `agent` `ai` | 18 | giữ |

### Ba việc bắt buộc trước khi luồng cũ nghỉ được

1. **UI tạo task profile** — nơi khai nhiễu. Hiện chỉ sửa được bằng file YAML.
2. **UI khởi chạy phép so** — nhưng `POST /decisions` chạy **đồng bộ** theo
   thiết kế. Một nút bấm có thể treo trình duyệt hàng giờ, nên phải đưa vào
   worker nền trước.
3. **Trình xem trace Parquet.** Luồng cũ có `MapCanvas`, `Scene25D`,
   `useTrajectoryPlayback` — xem được robot chạy. Luồng mới ghi Parquet vào
   `artifacts/traces/<candidate>/<episode>.parquet` và **không có gì đọc
   chúng ra màn hình**; endpoint `episodes` phục vụ mô hình dữ liệu cũ.

**Điểm ba là lý do chốt "song song".** Bỏ luồng cũ trước khi có trình xem
trace = mất khả năng nhìn thấy robot chạy, thứ trực quan nhất của sản phẩm.
Chạy song song thì luồng cũ vẫn gánh việc đó trong lúc luồng mới lớn dần.

### Đã làm được gì cho luồng mới (12-08)

- `/decisions` danh sách + chi tiết, chỉ đọc, bảng cổng đứng trước khuyến nghị.
- `scripts/import_runs.py` nạp 6 run có sẵn trên đĩa vào store — trang có dữ
  liệu thật, đủ **cả bốn trạng thái** phải dựng (có card · không card · ngắt
  giữa chừng 245/300 · report cũ không ghi số episode đã xin).
- `scripts/serve.py` chạy API trên mọi nền tảng, kể cả Windows thuần.

### Khi quay lại tinh gọn, nhớ hỏi

- Dữ liệu benchmark cũ: migrate sang `decision_runs`, hay lưu trữ đóng băng?
- `leaderboard` dựng lại trên Decision Card thì nghĩa là gì? Xếp hạng xuyên
  deployment mâu thuẫn với HĐ-1.4 (khuyến nghị chỉ có nghĩa trên một
  deployment).
- `robot-profiles` trùng phần `robot` trong task profile — một trong hai phải
  thành nguồn sự thật.

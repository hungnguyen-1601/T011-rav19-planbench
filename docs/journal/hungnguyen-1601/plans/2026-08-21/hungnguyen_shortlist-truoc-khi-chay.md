# Plan — Shortlist trước khi chạy (S0–S6): trả lời "dự án tôi thế này thì nên so những ứng viên nào"

**Ngày:** 2026-08-21 · **Trạng thái:** bản 1, chờ duyệt
**Nguồn:** thảo luận 2026-08-21 (hướng A trong ba hướng đã cân nhắc)
**Tiền đề:** `preflight.py` (12 luật), `outcome.TRAITS`, `map_features.py` (E3),
`reference_path`, registry, tầng LLM provider M8 — tất cả đã có trên nhánh này.
**Nguyên tắc kế thừa:** AI đề xuất, hệ thống quyết định. Không module nào ở đây
được phép chặn một lần chạy.

---

## 0. Một câu

Người dùng khai deployment xong đang đứng trước một danh sách ứng viên **mà
không ai nói cho họ biết cái nào đáng chạy trên chính bản đồ của họ, và vì sao
những cái còn lại không có trong danh sách**. Plan này lấp đúng khoảng đó — bằng
luật, không bằng mô hình.

---

## 1. Phát hiện đổi khung: đây không phải bài toán cắt tỉa

Ý tưởng ban đầu bán mình bằng câu "AI thu hẹp không gian ứng viên, tiết kiệm mô
phỏng". Kiểm registry thật thì luận điểm đó **yếu hơn nhiều so với tôi tưởng**:

| Stack | `production_eligible` | Vì sao không |
|---|---|---|
| `astar+dwa` | ✅ | |
| `rrtstar+dwa` | ✅ | |
| `astar+ppo` | ✅ | (cần model do người chọn) |
| `astar+dwa_predictive` | ❌ | `withdrawn` — rút sau khi đã đo |
| `rrtstar+dwa_predictive` | ❌ | `withdrawn` — rút sau khi đã đo |
| `astar+pure_pursuit` | ❌ | `reference=True` — adapter D12, không bao giờ là đối thủ |
| `rrtstar+pure_pursuit` | ❌ | `reference=True` |

**Chỉ 3 stack được phép làm ứng viên.** Nhân với preset controller
(`offered_controller_configs()` hiện chỉ trả `dwa` → 3 preset) ra khoảng **6 ứng
viên + số model PPO đã upload**.

Cắt tỉa một không gian 6 phần tử không phải một tính năng. Nên khung đúng là:

> Shortlist không tồn tại để **giảm số ứng viên**. Nó tồn tại để **giải thích tập
> ứng viên** đối chiếu với chính deployment của người dùng, và để nói ra thứ hôm
> nay không ai nói: *vì sao `dwa_predictive` không có trong danh sách* — nó bị
> rút sau khi đã đo, và câu trả lời đó nằm trong `withdrawn` chứ không nằm trong
> đầu người dùng.

Giá trị cắt tỉa quay lại **khi và chỉ khi** Algorithm Host mở cho người dùng nạp
thuật toán từ paper. Lúc đó pool phồng lên và cùng bộ luật này chạy nguyên si.
Thiết kế để chịu được điều đó, nhưng **không hứa hẹn nó hôm nay**.

Một nửa còn lại của giá trị vẫn đúng ngay bây giờ: `N_min` mỗi ứng viên suy từ
`collision_probability_max`, và với rủi ro khai chặt thì mỗi ứng viên bỏ được là
hàng giờ mô phỏng. Sáu ứng viên vẫn là sáu lần `N_min`.

---

## 2. Vị trí: giữa TaskProfile và preflight

```
TaskProfile ──► [ S: shortlist ] ──► draft candidates ──► preflight (12 luật)
                                                       ──► POST /decisions
                                                       ──► gates G1–G6 ──► Decision Card
                                                       ──► outcome / analyst
```

`preflight.py` đã "cãi với kế hoạch trước khi nó tốn tiền" — nhưng nó nhận một
draft **đã có sẵn tên ứng viên**. Nó phê bình một danh sách; nó không đẻ ra danh
sách. Đó là khoảng trống, và nó nằm **trước** preflight, không phải cạnh
`outcome.py`.

Hệ quả quan trọng: **đầu ra của S là đầu vào của một module đã tồn tại.** Hợp
đồng không phải bịa ra — nó phải là thứ `build_draft()` nuốt được.

### Ranh giới với năm thứ đã có

| Module | Câu hỏi | Thời điểm | Quyền |
|---|---|---|---|
| **S (mới)** | Nên đưa ứng viên nào vào phép so? | Trước khi có draft | Đề xuất |
| `preflight` | Draft này có gì sai? | Có draft, chưa chạy | Khuyên |
| Gates G1–G6 | Ai đủ điều kiện? | Sau khi chạy | **Quyết** |
| Decision Card | Ai thắng, biên bao nhiêu? | Sau khi chấm | **Quyết** |
| `outcome` / AI Analyst | Vì sao thắng/thua? | Sau khi có card | Giải thích |

Năm hàng, năm câu hỏi khác nhau, hai chỗ có quyền quyết. S **không** làm panel
"vì sao thắng" thứ ba — nỗi lo chồng lấn nêu trong note rà soát ngày 19-08 không
áp vào đây.

---

## 3. Hợp đồng đầu ra

Ba rổ, không phải một danh sách xếp hạng:

```
ShortlistProposal
├── proposed[]      ứng viên nên chạy, có thứ tự, mỗi cái kèm lý do
├── not_proposed[]  ứng viên bị loại, kèm MÃ lý do và cách bật lại
└── unknown[]       thứ không suy được từ profile → câu hỏi cho người dùng
```

**Kiểu dữ liệu tái dùng `Advice`**, không định nghĩa mới: đã có `code` / `claim` /
`ground` / `field_path` / `do` / `do_not` / `subject`, đã có `keep_resolvable()`
bắt mọi lý do phải trỏ vào một trường có thật, đã có `order()`. Thêm một
`AdviceKind = "shortlist"` bên cạnh bốn kind hiện có. 64 luật cố vấn hiện tại
render bằng đúng component đó — thêm rổ thứ năm không tốn UI mới.

Ba ràng buộc cứng của hợp đồng:

1. **`not_proposed` luôn hiển thị, không bao giờ ẩn.** Một ứng viên biến mất
   không lời giải thích là một cái cổng vô hình.
2. **Mỗi mục `not_proposed` phải bật lại được bằng một thao tác.** Nếu không,
   "đề xuất" đã là "quyết định".
3. **`unknown` không được rỗng vì lười.** Cùng tinh thần `do_not` của `Advice`:
   để rỗng vì "hiển nhiên" là cách nó bị bỏ qua.

---

## 4. Ba tầng, và một luật một dòng

| Tầng | Được phép | Căn cứ | Sai thì mất gì |
|---|---|---|---|
| **L1 bất khả thi** | **Loại** | Registry + profile + hình học bản đồ | Thấp — G4/G6 cũng loại y hệt, chỉ muộn hơn vài giờ |
| **L2 đặc tính × môi trường** | **Chỉ xếp hạng** | `TRAITS` (có anchor) × đặc trưng bản đồ đo được | Thứ tự sai → tốn sim, không sai kết luận |
| **L3 lịch sử** | **Chỉ nhích hạng**, trong cùng khoá tương đương | `decision_runs` | Cao nhất — thiên lệch sống sót |

> **Luật một dòng: chỉ L1 được loại. L2 và L3 xếp hạng, không xoá.**

Vi phạm dòng này là biến shortlist thành **cổng thứ bảy không có bảo đảm nào của
một cái cổng** — đúng thứ mà docstring `preflight` từ chối trở thành.

### 4.1 L1 không phải luật mới — L1 là gọi lại preflight

Bốn trong năm luật loại cứng **đã tồn tại**:

| Cần kiểm | Đã có ở |
|---|---|
| observation không có trong deployment | `PF_OBSERVATION_NOT_AVAILABLE` |
| stack cần model mà chưa chọn | `PF_MODEL_NOT_CHOSEN` |
| control period chậm hơn deployment | `PF_CONTROL_RATE_SLOWER_THAN_DEPLOYMENT` |
| stack reference lọt vào phép so | `PF_REFERENCE_STACK_IN_COMPARISON` |
| goal không lọt bán kính robot | `PF_GOAL_UNREACHABLE_FOR_RADIUS` |

Nên L1 **không viết lại một dòng logic nào**:

```
với mỗi ứng viên trong tích Descartes (stack production_eligible × preset × model):
    draft ← build_draft(profile, [ứng viên đó])      # draft một phần tử
    advice ← preflight(draft)
    nếu có advice severity == "blocking":
        → not_proposed, mang nguyên mã PF_* làm lý do
```

Đây là luật "gọi validator canonical của platform, không viết lại logic" mà An đã
chốt ở điểm 7 plan AI Analyst. Lợi thêm: sửa một luật preflight thì shortlist tự
đúng theo, không có hai bản luật trôi khỏi nhau.

**Luật loại cứng duy nhất S phải tự viết** là `SL_NOT_PRODUCTION_ELIGIBLE` — đọc
`production_eligible`, và khi `withdrawn` khác rỗng thì **in nguyên văn lý do rút**
vào `ground`. Đó chính là câu trả lời cho "sao không thấy `dwa_predictive`", và
nó đã được viết sẵn trong registry từ lâu, chỉ chưa ai đưa lên màn hình.

### 4.2 L2 — nơi duy nhất có suy luận mới

Ghép **đặc trưng môi trường đo được** với **`TRAITS`** (đã có `anchor` cho từng
đặc tính, đã dùng trong `outcome.py`, không phát minh bảng thứ hai):

| Mã | Khi nào | Neo |
|---|---|---|
| `SL_TIGHT_PASSAGE_FAVOURS_DETERMINISTIC` | `narrowest_passage_m` sát bán kính robot | `stochastic_global_planner=False` — cùng bản đồ, cùng đường ra |
| `SL_OPEN_SPACE_FAVOURS_ANY_ANGLE` | `obstacle_density` thấp, tuyến dài | trait `rrtstar`: any-angle, đường hội tụ ngắn hơn lưới |
| `SL_STOCHASTIC_COSTS_MORE_SEEDS` | ứng viên có global planner ngẫu nhiên | `stochastic_global_planner=True` — cùng độ tin cậy, nhiều seed hơn |
| `SL_TRAFFIC_PRESENT` | `environment.dynamic_obstacles` khác rỗng | nêu rõ local controller phải phản ứng qua LiDAR, **và** vì sao `dwa_predictive` không còn là lựa chọn |
| `SL_TIGHT_CONTROL_PERIOD` | `robot.control_period` ngặt | preset `dwa_coarse` trước `balanced`/`default` |
| `SL_LARGE_MAP_PREPAID_SEARCH` | bản đồ lớn | trait `astar`: chi phí tìm kiếm trả trước, tăng theo kích thước |

Sáu mã, tất cả **xếp hạng**, không mã nào xoá.

### 4.3 L3 — khoá tương đương phải khai, không được suy

Gộp hai run khác `conditions_checksum`, khác `anchor_config_version`, khác
contracts version là so sai — đúng loại rank-reversal mà anchor tuyệt đối sinh ra
để chặn.

Nhưng đòi trùng khít `conditions_checksum` thì prior chỉ áp được cho đúng cái
run đã chạy — vô dụng. Nên khoá phải thô hơn, và **thô có chủ ý thì phải khai ra**:

```
comparability_key = (contracts_version, anchor_config_version,
                     environment_class)
environment_class = (băng độ rộng lối hẹp, băng mật độ vật cản,
                     có/không traffic động)
```

Ba luật kèm theo, không thương lượng:

1. `environment_class` **do code suy từ số đo**, không do LLM gán nhãn.
2. Prior chỉ được nhích hạng khi có **≥ K run** trong cùng khoá (K khai trong
   config, không phải hằng số trong code).
3. Mọi lần dùng prior đều in ra *"dựa trên N run cùng lớp môi trường"* — người
   đọc phải thấy được mẫu nhỏ đến đâu.

Không đủ N thì phát `SL_NO_COMPARABLE_HISTORY` và **L3 im lặng**, không đoán.

---

## 5. Đặc trưng môi trường: đo gì, bằng gì, và không đo gì

`map_features.measure_route()` đã đo `narrowest_passage_m`, `obstacle_density`,
`route_length_m` — nhưng nó cần **một tuyến đường**, mà trước khi chạy thì chưa có
tuyến nào.

Giải: dùng **tuyến tham chiếu**, không phải mô phỏng. `reference_path.py` đã tính
`L_ref` bằng Dijkstra cho mọi metric hiệu suất đường đi — một lần cho mỗi mission
trên đúng bản đồ đã khai, có cache, rẻ hơn một episode nhiều bậc. Không có robot
nào chuyển động ở bước này.

**Một sửa nhỏ bắt buộc, nêu ra vì nó là công việc thật của S2:**
`reference_path_length()` trả về `float | None` — nó tính polyline đã kéo căng ở
`_taut()` rồi **vứt đi**, chỉ giữ độ dài. `measure_route()` cần chính polyline đó.
Nên S2 phải phơi tuyến ra: thêm một hàm anh em trả `tuple[Point2D, ...]`, hoặc mở
rộng giá trị cache. **Không đổi chữ ký `reference_path_length`** — mọi metric
hiệu suất đang gọi nó.

Và `reference_path_length` **raise** `ReferencePathError` khi start/goal nằm ngoài
bản đồ hoặc trên ô bị chặn. Shortlist chịu chung hiến pháp với `preflight` và
`Advice`: **không bao giờ raise**. Nên S2 bắt lỗi đó và biến thành một mục
`unknown` nói rõ profile và bản đồ đang bất đồng — đó là sự thật về deployment,
không phải về ứng viên nào.

**Ba thứ cố ý không đo**, vì `map_features` đã từ chối chúng có lý do:

- topology và số ngã rẽ — cần phân tích Voronoi/skeleton chưa có; một nhãn thô
  kiểu `"corridor_with_side_aisles"` là thứ người đọc nhận làm sự thật;
- mọi cross-section bị chặn bởi vùng UNKNOWN — nó là **cận dưới**, chứng minh
  được "đủ rộng" và không chứng minh được "quá hẹp";
- bất cứ đặc trưng nào phải suy từ hành vi — hành vi chưa xảy ra.

---

## 6. Vòng lặp tự khẳng định — rủi ro riêng của tính năng này

Shortlist bỏ RRT* → RRT* không sinh dữ liệu → lịch sử càng nghèo RRT* → càng bị
bỏ. Sau hai chục run, hệ thống "biết chắc" một điều nó chưa từng đo.

Chống bằng cơ chế, không bằng prompt:

1. **L2/L3 không có quyền xoá** (§4). Ứng viên hạng bét vẫn nằm trong `proposed`.
2. **`not_proposed` luôn hiện, bật lại một thao tác** (§3).
3. **Sổ phủ sóng.** `SL_NEVER_MEASURED_HERE`: ứng viên chưa từng chạy trên lớp
   môi trường này thì **nói ra**, và nói theo hướng ngược với trực giác — đó là
   lý do *nên* chạy nó, không phải lý do bỏ. Một hệ khuyến nghị chủ động chỉ ra
   lỗ hổng dữ liệu của chính nó là hệ không tự bịt mắt.

---

## 7. Đo chất lượng bằng gì — và tình trạng dữ liệu hôm nay

**Metric: `recall@K`.** Ứng viên thắng thật (theo Decision Card sinh ra sau đó) có
nằm trong `proposed` không.

Bất đối xứng phải nói rõ: **bỏ sót người thắng là hỏng; thừa một ứng viên chỉ tốn
mô phỏng.** Không tối ưu precision. Không bao giờ.

**Sàn để so là "chạy tất cả"**: `recall = 1,0`, cost = 100%. Shortlist phải công
bố cặp **(recall, % episode tiết kiệm)**. Giữ recall mà không giảm cost thì không
có lý do ship — cùng nguyên tắc `reference_analyst` của An: *floor không thua thì
không ship*.

**Rào thật:** `planbench.db` hiện có **đúng 2 decision run**, một cái có card.
Không đủ để tính bất cứ recall nào.

Nên plan này **khai trước hai điều thay vì che**:

- L1 + L2 xây được ngay, **không cần lịch sử** — chúng là hệ luật có neo, cùng
  loại bằng chứng với 64 luật cố vấn đang chạy;
- **nhưng chưa đo được.** Mọi output gắn nhãn *"đề xuất từ luật, chưa hiệu chuẩn"*
  cho tới khi có bộ golden. L3 và mọi con số recall **chờ dữ liệu**.

Có một tính năng dùng được trước khi có bằng chứng nó tốt là chấp nhận được. Che
chuyện đó đi mới là vấn đề.

---

## 8. Vai của LLM: hai đầu, không phải ở giữa

L1 và L2 là luật thuần — không gọi model. LLM đứng đúng hai chỗ:

**Đầu vào — và tôi ngờ đây mới là giá trị lớn nhất.** Rào cản của người dùng không
phải "không biết A* hay RRT* hơn". Rào cản là **không khai nổi TaskProfile**:
`success_rate_min`, `collision_probability_max`, `available_ram_mb`,
`clearance_warning_m`, `v_obstacle_max`. Người quản lý kho không có mấy con số đó.

LLM đọc *"kho 2000 m², xe kéo pallet 0,5 m/s, có người đi lại giờ hành chính,
chạy trên Jetson Orin Nano"* → đề xuất các trường còn thiếu, **mỗi giá trị kèm
câu nguồn lấy từ chính lời người dùng**, đúng hợp đồng `paper.py`. Cái nào không
suy được thì hỏi, không đoán.

**Đầu ra** — xếp lại thứ tự các lý do và viết lời giải thích cho người không
chuyên đọc. Không sinh số.

Ba điều cấm, thi hành bằng code:

| Cấm | Cơ chế |
|---|---|
| Thêm ứng viên không có trong registry | Enum hoá `production_eligible` trong output schema |
| Sinh số | Regex chặn numeric literal trong câu — luật A3 của plan AI Analyst |
| Loại một ứng viên | LLM không có đường ghi vào `not_proposed`; rổ đó do L1 dựng |

Tái dùng nguyên tầng provider M8 (`LLMProvider`, `LLMRequest.output_schema`,
`MockProvider`) — chạy được không cần key.

---

## 9. Phase

| # | Nội dung | Ước lượng |
|---|---|---|
| **S0** | Module `shortlist.py` trong `packages/benchmark/` (cùng chỗ preflight: cùng dependency registry, cùng kiểu `Advice`). Thêm `AdviceKind="shortlist"`. | 0,5 ngày |
| **S1** | Tích Descartes ứng viên đủ điều kiện + L1 qua `preflight` trên draft một phần tử + `SL_NOT_PRODUCTION_ELIGIBLE` in nguyên văn `withdrawn`. | 1 ngày |
| **S2** | Đặc trưng môi trường: tuyến tham chiếu mỗi mission → `measure_route` → `environment_class`. Từ chối rõ ràng khi bản đồ không đọc được. | 1–1,5 ngày |
| **S3** | Sáu luật L2 + sổ phủ sóng `SL_NEVER_MEASURED_HERE`. | 1–1,5 ngày |
| **S4** | `POST /decisions/shortlist` (200, không bao giờ 4xx trên một finding — cùng khuôn `POST /decisions/preflight`) + panel trên trang khai deployment. | 1 ngày |
| **S5** | Lớp LLM diễn giải (bật/tắt bằng `use_model`, như `advice`/`outcome`). | 0,5–1 ngày |
| **S6** | L3 + harness đo `recall@K`. **Chặn bởi dữ liệu**, không phải bởi code. | chờ |

**S0–S5: 5–6,5 ngày kỹ thuật.** Theo hệ số lịch ×2 mà An dùng cho
preregistration → **2–3 tuần lịch**. S6 không ước lượng được cho tới khi chốt
chuyện sinh dữ liệu.

---

## 10. Ba câu hỏi mở — tôi chốt sẵn, sửa được

| Câu | Chốt | Vì sao |
|---|---|---|
| Sinh dữ liệu trước hay ship luật trước? | **Ship S0–S5 trước**, gắn nhãn chưa hiệu chuẩn; sinh dữ liệu song song bằng chính các run thật của team | Chờ dữ liệu là chờ vô hạn khi chưa ai có lý do chạy run; L1/L2 không cần dữ liệu để đúng |
| Shortlist có tự tạo draft benchmark không? | **Không.** Trả đề xuất, người bấm | Tạo draft là hành động; `FORBIDDEN_CAPABILITIES` đang cấm agent hành động, và cấm bằng cách không có đường dẫn tới nó |
| Phần khai profile bằng tiếng người: gộp hay tách? | **Tách**, làm sau S5 | Xem §11 |

---

## 11. Một phát hiện phụ, cần xác minh với team

`apps/api/planbench_api/chat.py` tồn tại và viết đầy đủ ("assistant proposes, the
person disposes"), **nhưng không router nào đăng ký nó và không file `.py` nào
import nó** — `main.py` include 15 router, không có `chat`. Còn sót
`chat_service.cpython-312.pyc` trong `__pycache__` của một module nguồn đã biến mất.

`IMPLEMENTATION_STATUS.md` khai M13 đã ship "trợ lý hội thoại thay cho ba biểu mẫu
kỹ thuật". Hai điều đó không khớp nhau trên nhánh này.

Cần biết đây là **merge làm rơi** hay **gỡ có chủ ý** trước khi lên kế hoạch cho
phần khai profile bằng hội thoại — vì nếu là cái đầu thì một nửa việc đã có sẵn.

---

## 12. Plan này **không** làm

- Không quyết ứng viên nào thắng. Đó là gates + Decision Card.
- Không giải thích vì sao ai thắng. Đó là `outcome.py` và AI Analyst.
- Không chặn một lần chạy nào, không có severity nào của nó mang nghĩa "cấm".
- Không đo `robustness_margin` — đó là hướng (B), Task Neighborhood, plan riêng.
- Không so xuyên nhiều run để rút quy luật chung — hướng (C), chờ dữ liệu.
- Không tuyên bố an toàn, không nói ứng viên nào "phù hợp để triển khai".

## 13. Rủi ro

| Rủi ro | Mức | Xử |
|---|---|---|
| Pool 6 ứng viên làm tính năng trông thừa | **Cao** | Bán bằng *giải thích*, không bằng *cắt tỉa* (§1); giá trị cắt tỉa đến cùng Algorithm Host |
| Vòng lặp tự khẳng định | Cao | Ba cơ chế §6, tất cả bằng code |
| Chưa hiệu chuẩn mà người dùng tin như đã đo | Trung bình | Nhãn bắt buộc trên mọi output cho tới khi có golden |
| L2 xếp hạng theo trực giác chứ không theo đo đạc | Trung bình | Mọi trait phải có `anchor`; trait không neo được thì không thành luật |
| `environment_class` thô gộp nhầm hai thế giới | Trung bình | Khai công khai, ≥K run mới được dùng, in số run mỗi lần dùng |

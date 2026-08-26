# Báo cáo thi hành — AI Analyst bản 8 (lớp AI cố vấn "vì sao A thắng B")

**Plan:** `plans/2026-08-26/ai-analyst-ban-8.md` · **Verify nền:**
`notes/2026-08-26/tongduyan_verify-plan-ai-analyst.md`
**Nhánh:** `tongduyan_ai-analyst-ban-8`, tách từ `main` tại `738ee1f`
**Worktree:** `../P-011-analyst` từ 2026-08-26 — xem §Ghi chú vận hành cuối file.
**Quy ước:** một file cho cả plan; mỗi phase một mục, viết ngay sau khi commit
phase đó.

| Phase | Trạng thái | Commit |
|---|---|---|
| A-1 vá sàn model-free | **xong** | `2293615` |
| A0 skeleton + hạ tầng | **xong** | `df1743a` |
| A1 packet view + fact index | **xong** | `5e6bf41` |
| A2 hypothesis engine | **xong** | `285adda` |
| A3 guard + critic + biên vào | **xong** | `95cfe75` |
| A4-i budget + packet artifact | **xong** | (xem §A4-i) |
| A4 seam + lane + gateway | chưa | |
| A5 knowledge provider | chưa | |
| A6 dev calibration + harness | chưa | |
| A6.5 ba họ golden | chưa | |
| A7 freeze + official calibration | chưa | |

---

## A-1 — Vá sàn model-free

### Đã làm gì

**1. `reference_analyst` không còn mất cổng chặn blocked-claim từ detection thứ hai.**

`integration.py` dựng `blocked` = tập claim type mà `known_unknowns` của packet
chặn, rồi **trong vòng lặp** gán đè lên chính tên đó bằng
`BLOCKED_BY_ARGUMENT.get(detection_type)`. Đổi tên biến trong vòng lặp thành
`short_of`, kèm comment nói rõ nó phải ở tên khác và vì sao.

Hai hậu quả của lỗi cũ, cái thứ hai tệ hơn:

- `BLOCKED_BY_ARGUMENT` chỉ có **một** entry, nên với mọi loại detection khác,
  `blocked` thành `None` ở vòng sau ⟶ `TypeError: argument of type 'NoneType' is
  not iterable`. Sàn chết.
- Khi detection đầu tiên là `narrow_gap_refusal`, `blocked` thành tuple hai
  chuỗi tên-tool, `proposition in blocked` từ đó **so nhầm mà không chết**, và
  cổng chặn blocked-claim tắt trong im lặng cho mọi detection sau đó. Đây đúng
  cái `golden.py` đếm là blocked-claim leak.

**2. Hai test mới, và chúng cắn.**

- `test_the_blocked_claim_gate_is_still_on_for_the_second_detection` — packet có
  `narrow_gap_refusal` + `latency_spike`, kèm một `KnownUnknown` chặn
  `expansion_latency_association`. Đòi **đúng một** proposal sống sót. Đây là
  nhánh im lặng, nên nó được kiểm bằng *cái gì sống sót*, không bằng exception.
- `test_several_mapped_detections_do_not_kill_the_floor` — packet có
  `latency_spike` + `stuck_cluster`, đòi hai proposal. Đây là nhánh raise.

Tiêm lại lỗi cũ vào bản sao tạm: **cả hai test đỏ**, một cái vì `TypeError`, một
cái vì proposal bị chặn vẫn được nộp. Khôi phục: xanh.

**3. Một răng mới trong bộ `bites`.**

`FLOOR_SECOND_DETECTION_UNGATED` trong
`notes/2026-08-24/tongduyan_ai-explain-bites.yaml`: tiêm
`blocked = short_of = BLOCKED_BY_ARGUMENT.get(...)` — tái dựng đúng phép che
biến — và đòi cổng đỏ đúng tên test. **CẮN**, exit 1.

### Bằng chứng

| Phép kiểm | Kết quả |
|---|---|
| `pytest tests/test_explanation_e5.py` | **112 passed**, 0,36 s |
| Sàn chạy trên **packet thật** (17 run có `case_packet` trong `artifacts/runs/`) | **17/17 không raise**; 13 packet sinh 1–3 proposal, 4 packet 0 observation ⟶ abstain đúng |
| Răng `GATE_SUITE_MISMATCH_IGNORED` (trượt hôm 24-08) | **CẮN** |
| Răng `ADVISOR_ADDITION_CAP_OFF` (trượt hôm 24-08) | **CẮN** |
| Răng `FLOOR_SECOND_DETECTION_UNGATED` (mới) | **CẮN** |
| `ruff check` trên hai file đã sửa | sạch |

Số packet thật đã tăng từ 13 (đo hôm 24-08) lên **17** — bốn run mới ngày 25-08.
Bốn packet abstain đều là packet 0 observation, tức abstain vì đúng lý do.

Kịch bản chạy sàn trên packet thật để ở scratchpad, **không commit**: A6 sẽ có
`harness.py` thật trong service, và một script tạm nằm trong repo là thứ sau này
không ai biết có còn đúng không.

### Đã đổi kế hoạch một điểm

Plan bản 8 §A-1 xếp **`run_gate` kiểm `suite.status == "preregistered"`** vào
phase này. **Đã chuyển sang A4**, lý do kỹ thuật chứ không phải để tránh việc:

- `GoldenSuite` từ chối `status="preregistered"` khi `OFFICIAL_GOLDEN_READY` còn
  `False`, và một suite preregistered hợp lệ đòi **đủ 6 họ × ≥12 biến thể = ≥72
  case** (`MIN_VARIANTS_PER_FAMILY = 12`). Mọi test gate hiện tại dùng
  `hidden_suite()` với `status="calibration"` và **một** case.
- Nghĩa là thêm luật fail-closed bây giờ sẽ phải dựng lại toàn bộ fixture của
  `tests/test_explanation_gate.py`, rồi **dựng lại lần nữa** ở A4 khi
  `allow_visible_suite` đổi tên thành `dry_run`, `DryGateRun` tách khỏi
  `GateRun`, và điều kiện thứ ba (`PacketArtifact.fixture_kind == "recorded"`)
  ra đời. Ba điều kiện fail-closed của plan bản 7 §A4.5 là **một** thay đổi.
- Rủi ro để lại trong lúc chờ bằng không: chưa có analyst nào để gate.

### Còn nợ sau A-1

Không. `available_evidence` mặc định rỗng vẫn còn nguyên — đúng thiết kế, nó là
việc của `RoundSource` ở A4.

---

## A0 — Skeleton + hạ tầng

### Đã làm gì

**1. `services/analyst_service/planbench_analyst/` ra đời.**

Chỉ có `__init__.py`, và nó **không export gì**. Docstring chép lại bốn luật mà
mọi module dưới đó thừa kế (đề xuất chứ không đóng dấu · model không bao giờ là
nguồn của một con số · menu tool đóng · không đọc Parquet thô) — chép lại ở đây
chứ không để trong plan, vì một module quên một trong bốn luật đó nhìn từ ngoài
giống hệt một module đang chạy đúng.

**2. Path nối vào bốn nơi phải khớp nhau.**

| Nơi | Đổi gì |
|---|---|
| `pyproject.toml` `[tool.pytest.ini_options] pythonpath` | thêm `services/analyst_service` |
| `scripts/dev_stack.sh` `PY_PATH` | thêm `$ROOT/services/analyst_service` |
| `docker/Dockerfile.api` `ENV PYTHONPATH` | thêm `/app/services/analyst_service` |
| `ruff.toml` `known-first-party` | thêm `planbench_analyst` |

**Plan bản 8 §A0 nói `Dockerfile.api` thiếu `packages/decision`,
`packages/explanation`, `packages/plugin_sdk`, `ml` — kiểm lại thì không thiếu
nữa**, chúng đã được thêm ở đâu đó giữa 19-08 và hôm nay. Việc còn lại chỉ là
`analyst_service`. Ghi ra vì đó là một dòng của plan không còn đúng.

**3. Cổng canh cho chính bốn danh sách đó.**

`tests/test_dev_stack_pythonpath.py` trước nay so **hai** danh sách (pytest ↔
`dev_stack.sh`). Thêm danh sách thứ ba — PYTHONPATH của image — cùng ba test:

- image import được mọi thứ suite import được (trừ `apps/desktop`, khai tường
  minh trong `IMAGE_EXEMPT` vì image không `COPY` nó, chứ không phải vì quên);
- image không mang thứ gì suite chưa từng import;
- **mọi entry trên PYTHONPATH của image phải có một dòng `COPY` đưa nó vào
  `/app`** — hai nửa này viết cách nhau mười hai dòng và chỉ một nửa kêu.

`tests/test_analyst_service_wiring.py` (mới) hỏi câu hẹp hơn: gói này có import
được không, có nằm trên **cả ba** path list không (gọi tên tường minh, vì một
phép so tập hợp sẽ xanh trở lại ngay khi ai đó xoá entry khỏi cả ba cùng lúc),
và ruff có xếp nó là first-party không.

Kèm một test cố ý sẽ phải sửa theo từng phase: `__all__` rỗng **và** thư mục
không có module `.py` nào ngoài `__init__`. Nó là chốt chống fake completion —
để một `analyst.py` trả `None` nằm đó mà không ai export là cách rẻ nhất để
trông như đã xong A2.

### Bằng chứng

| Phép kiểm | Kết quả |
|---|---|
| `pytest tests/test_analyst_service_wiring.py tests/test_dev_stack_pythonpath.py` | **11 passed** |
| Bỏ `analyst_service` khỏi `Dockerfile.api` rồi chạy lại | **đỏ** đúng test path list; khôi phục ⟶ xanh |
| `ruff check services/analyst_service tests/…` | sạch |

### Còn nợ sau A0

`docker/Dockerfile.analyst` là việc của A7 (freeze + container), không phải A0 —
plan bản 7 xếp nó ở đó và không có lý do kéo lên sớm: chưa có gì để đóng gói.

---

## A1 — Packet view + fact index

### Đã làm gì

`services/analyst_service/planbench_analyst/packet_view.py` — 3 lớp công khai
(`Fact`, `PacketView`, `PacketViewRefusal`) + `build_packet_view()`.

**1. Mỗi con số trong packet có một cái tên để trỏ vào.**

`Fact` mang `{ref, kind, label, value, unit, subject, candidate_id, scope}`.
Vốn từ `ref` **nối tiếp** vốn từ đang dùng chứ không dựng cái mới:
`obs:<type>:<candidate>` và `episode:<id>` là hai ref mà `reference_analyst`
đã phát ra từ trước, nên một index chỉ chấp nhận ref kiểu mới sẽ chấm sàn là
bịa đặt. Đo phần này bằng test riêng (§Bằng chứng, dòng cuối).

Thêm vào đó: `obs:<type>:<cand>/<measurement>` cho từng số trong `typical`,
`fact:robot.*`, `fact:route.*`, `fact:waterfall.*`, `bar:<objective>[/…]`,
`fact:gate:<id>.*`, `contrast:<detection_type>`, `unknown:<id>`.

**2. `subject` là câu trả lời cho "citation này có ủng hộ claim không".**

Ca A15 hôm 24-08 (model dẫn một field **có thật**, giá trị **đúng**, nhưng câu
kèm theo nói chuyện khác) là lý do trường này tồn tại. Luật quan trọng và đã
viết vào docstring: **một measurement không tự khai component chịu trách
nhiệm** — `subject=None`. Chỉ lattice (`ContrastFinding.subject`), hình học
robot (`costmap_inflation`) và hình học tuyến (`task_geometry`) mới mang
subject, vì đó là những chỗ packet **thật sự** quy trách nhiệm.

Nghĩa là guard luật 6 ở A3 sẽ là **phép kiểm mâu thuẫn**, không phải phép kiểm
liên quan: fact có subject mà khác `proposed_subject` ⇒ chặn; fact không khai
subject ⇒ không kết luận gì. Nói rõ giới hạn này ở đây để sau không ai đọc luật
6 mạnh hơn nó thật sự là.

**3. `null` được đánh index, không bị bỏ.**

`inflation_margin_m` bằng `null` là packet nói "run này không ghi lại". Bỏ nó
khỏi index thì analyst chỉ còn hai đường: đoán, hoặc im lặng về đúng cái nó
biết là thiếu. Cùng lý do đó với `unknown:<id>`.

**4. Serialize tất định + checksum.**

Sắp theo `ref`, đi qua `canonical_json` của `planbench_schemas.identity` (cùng
hàm mà `artifact_checksum` dùng), nên cùng packet ⟶ cùng chuỗi ⟶ cùng checksum
trên mọi máy. Đây là vật liệu cho `runtime_config_checksum` ở A2.

**5. `identifiers` — vật liệu cho luật cấm số.**

`B7`, `ep-004`, `open_hall_v2` là **tên**; `0.74` là **số đo**. Luật 2 của guard
phải phân biệt được, và cách trung thực duy nhất là một danh sách tên mà chính
packet này dùng. `PacketView.identifiers` trả tập đó.

**6. Từ chối packet của build khác.**

Năm version trong header đối chiếu với hằng số code (`EXPLANATION_SCHEMA_VERSION`,
`PROMOTION_MATRIX_VERSION`, `DETECTOR_VERSION`, `KNOWLEDGE_BASE_VERSION`) và với
**catalog version do caller truyền vào** — không đọc từ module catalog, vì
bundle mới là thứ khai catalog mà vòng chấm chạy trên; đọc từ module thì check
này tự đồng ý với chính nó trong khi lệch với bundle đang bị chấm. Refusal nêu
**mọi** field lệch cùng lúc, không dừng ở field đầu.

**7. Một episode hai vai không tranh nhau `ref`.**

Episode tệ nhất về utility thường cũng là episode tệ nhất về clearance. Ref đặt
theo episode (đúng vốn từ cũ), nên hai vai gộp vào một fact và `label` liệt kê
cả hai — thay vì `PacketViewRefusal` vì trùng ref.

**8. Cổng chống fake completion của A0 đã cắn ngay lần đầu.**

Test `test_the_package_exports_nothing_it_has_not_built_yet` (viết ở A0) đỏ ngay
khi `packet_view.py` xuất hiện mà `__init__` chưa export. Sửa thành
`PHASES_LANDED = ["packet_view"]` + một phép kiểm mới: **mọi module trên đĩa
phải đóng góp ít nhất một tên trong `__all__`** (đối chiếu `__module__` của
từng object được export). Module import được nhưng không export gì chính là
hình dạng của một stub bị bỏ lại.

### Bằng chứng

| Phép kiểm | Kết quả |
|---|---|
| `pytest tests/test_analyst_packet_view.py tests/test_analyst_service_wiring.py` | **20 passed** |
| Dựng view trên **17 packet thật** | 17/17 dựng được; 15 / 39 / 54 fact mỗi packet (min/trung vị/max) |
| Mọi ref sàn `reference_analyst` trích trên 17 packet thật | **32 ref, 0 không resolve** |
| `ruff check` services + hai file test | sạch |

### Còn nợ sau A1

- `fact:gate:*` chỉ lấy scalar một tầng; gate verdict lồng sâu hơn bị bỏ qua có
  chủ đích (một dict render thành ref là một con số không ai định vị được trong
  packet). Nếu A6 cho thấy analyst cần chúng thì đó là một RFC, không phải một
  dòng sửa.
- Chưa có `PacketArtifact` loader (validate checksum + provenance) — plan bản 7
  xếp ở A6, giữ nguyên.

---

## A2 — Hypothesis engine (AI1 lõi)

### Đã làm gì

Bốn module mới: `prompts.py` · `analyst.py` · `identity.py` · `cache.py`.

**1. `prompts.py` — mọi chữ model đọc là hằng số.**

Không f-string dựng lúc gọi: `prompt_checksum()` đi vào bundle ở A7, và một
prompt ráp từ mảnh mà ai đó đổi được lúc chạy là prompt mà bundle không thật sự
định danh. Checksum phủ **cả schema** — hai lượt cùng chữ khác tập field bắt
buộc không phải cùng một yêu cầu.

Schema đầu ra cố tình **thiếu hai thứ**: không có `id` (hệ sinh, xem dưới) và
không có field nào chở được confidence (`HypothesisProposal` cấm extra, nên một
schema mời chào confidence chỉ để tạo ra thứ bước parse sẽ vứt đi).

`arguments` là **danh sách cặp name/value dạng chuỗi**, không phải object mở:
strict schema đòi khai mọi property, mà property khác nhau theo từng card. Kiểu
được khôi phục ở một chỗ duy nhất (`_coerced`), nơi giá trị không đổi được kiểu
thành một vấn đề **có tên**, thay vì thành một string đem so với float ba tầng
bên dưới.

**2. `analyst.py` — engine sở hữu định danh và chi phí, không sở hữu phán xét.**

- `hypothesis_id` = hash nội dung (statement + type + subject + refs + **cả
  requested check**). Cùng nội dung ⟶ cùng tên ⟶ dedupe được. Id do model đặt
  thì cùng một giả thuyết đến hai lần dưới hai tên và cổng trùng-id của protocol
  vẫy cả hai qua. Hai giả thuyết **khác nhau** mà đụng digest ⟶ **refuse cả
  vòng**, không đổi tên: một id nhấn nhá được thì không phải id.
- **Chi phí đi cùng vòng** (`RoundCost`): token vào/ra, số model call. A4 mới
  cộng `tool_requests`. Đây là phần bản 8 thêm so với bản 7 — budget mà chỉ biết
  lúc đã vượt thì không trả lời được câu "một vòng tốn bao nhiêu".
- **Ref không có trong index vẫn được giữ**, và đếm vào `refs_not_in_index`.
  Lọc ở đây là lấy mất lỗi khỏi guard — nơi các cú drop được đếm — và làm số của
  guard nói rằng model chưa từng mắc lỗi đó.
- Tách `dropped` (mất cả giả thuyết) khỏi `checks_refused` (chỉ mất cái check):
  "model không đề xuất được gì dùng được" và "model đề xuất được nhưng xin nhầm
  tool" là hai loại lỗi, A6 đếm vào hai metric khác nhau.

**3. Timeout cho từng call — và một lần suýt làm sai.**

Bản đầu dùng `ThreadPoolExecutor`. Test đo: stall 2 s với deadline 0,2 s vẫn
tốn **đủ 2 s**, vì `with` gọi `shutdown(wait=True)` — tức deadline không hoạt
động. Đổi sang **daemon thread + `Event.wait()`**: vòng chạy tiếp sau 0,2 s và
process không bị thread treo giữ lại. Ghi rõ trong docstring rằng call bị bỏ có
thể vẫn đang bay — đó là giá thật của một deadline ở tầng này, và rẻ hơn hẳn cái
giá kia: provider ngừng trả lời thì mất cả run, và checkpoint đáng lẽ cho phép
chạy tiếp không bao giờ được ghi.

**4. `identity.py` — flatten bằng JSON Pointer, hash nguồn theo byte.**

- `{"thinking.type": ...}` và `{"thinking": {"type": ...}}` flatten kiểu dotted
  cho ra **cùng một chuỗi**; bằng JSON Pointer (escape `~0`/`~1` theo RFC 6901)
  thì khác nhau. Có test đúng cặp đó. Thứ tự list cũng là một setting.
- `validate_generation_config` từ chối **trước khi gọi**: knob bị model bỏ qua
  làm bản ghi config nói dối, còn knob gây 400 thì từ ngoài nhìn y hệt "model
  hôm nay không thêm được gì" — đúng cái đã ngốn của Lane 1 một ngày.
- `source_manifest_hash` đọc **bytes**, không đọc mtime, không hỏi git: "cây
  tại commit này" không nói gì về một working copy đang có sửa đổi, mà
  calibration thì chạy đúng trong loại cây đó. `touch` không đổi hash; sửa một
  byte thì đổi; đổi tên file cũng đổi (path nằm trong hash).
- File chưa tồn tại **không phải lỗi**: `docker/Dockerfile.analyst` tới ở A7, và
  việc nó xuất hiện là một lần đổi định danh, đúng như phải thế.

**5. `cache.py` — hai điều một cache trên model không được phép làm.**

- **Không phục vụ vòng đã chấm.** Key mang định danh runtime lúc ghi; trước A7
  là checksum dev, từ A7 là identity của bundle. Khác chuỗi thì không đọc được
  của nhau.
- **Hit không được đọc thành "model lặp lại".** `CacheStats.hits` công khai để
  harness A6/A7 **assert bằng 0** khi đang đo model. `root=None` là cache không
  lưu gì — đúng hình dạng vòng chấm dùng, để nhánh "bỏ qua cache" không phải
  nhánh chỉ tồn tại lúc chấm (và do đó chỉ hỏng lúc chấm).

### Bằng chứng

| Phép kiểm | Kết quả |
|---|---|
| `pytest tests/test_analyst_*.py` (4 file) | **60 passed** |
| Deadline: stall 2 s, `timeout_s=0.2` | vòng hỏng sau <1,5 s, có mã lý do — trước khi sửa là 2,0 s |
| `ruff check` 4 module + 4 file test | sạch |

Bao gồm: id từ nội dung (cùng câu ⟶ cùng id; đổi check ⟶ khác id); dedupe trong
một vòng; `universal_algorithm_superiority` bị chặn **kể cả khi model bỏ qua
enum**; ref bịa được giữ + đếm; coercion `budget_multiplier="2.5"` ⟶ `2.5`
float; `"as high as it takes"` ⟶ mất check, giữ giả thuyết; prose thay vì object
⟶ refuse; JSON trong `text` vẫn đọc được; prompt_checksum đổi khi đổi một chữ
trong system message.

### Đã đổi kế hoạch một điểm

Plan §A2 xếp `generation_parameters` capability-aware vào phase này **kèm hai
adapter provider**. Phần **hợp đồng** (merge theo precedence, flatten, validate)
đã xong ở `identity.py`. Phần **adapter** (OpenAI/Anthropic thật sự nhận config
và khai capability của model) chưa — `LLMRequest` hiện chưa có field
generation config, nên đó là một RFC vào `planbench_agent.provider` chạm cả Lane
1 đang chạy production. Xếp vào **A4**, cùng chỗ với RFC platform khác
(`gate.py`, `bundle.py`), để mọi thay đổi hợp đồng đi trong một diff có test —
thay vì sửa provider hai lần.

### Còn nợ sau A2

- Adapter generation config (xem trên) — A4.
- Chưa gọi model thật lần nào: toàn bộ A2 chạy trên `MockProvider` có script.
  Đúng thiết kế ở phase này, và **A6 là chỗ chịu trách nhiệm** cho câu "model
  thật nói có đúng không". Nói trước để không ai đọc 60 test xanh thành một
  tuyên bố về chất lượng model.

---

## A3 — Guard, critic, và biên dữ liệu vào

### Đã làm gì

Hai module mới: `guard.py` · `sanitize.py`. Mở rộng `packet_view.py` (A1) để
mang nhãn thành phần.

**1. Bảy luật, chạy trên thứ model thật sự trả về.**

Năm luật của plan bản 7, cộng hai luật của bản 8:

| # | Luật | Chặn cái gì |
|---|---|---|
| 1 | `ref_not_in_packet` | trích dẫn vào packet không chứa nó |
| 2 | `quantity_in_statement` | câu tự mang số — thập phân, `%`, sci-notation, **số viết bằng chữ (en + vi)** |
| 3 | `claim_blocked_by_packet` | claim type mà `known_unknowns` đã chặn |
| 4 | `check_cannot_answer` / `check_version_mismatch` / `check_arguments_rejected` | xin check mà card không trả lời được |
| 5 | `wording_above_associated` | từ nhân quả ở tầng đề xuất |
| **6** | `citation_contradicts_subject` | **mới** — ref packet quy cho component khác |
| **7** | `no_citation` | **mới** — đề xuất không có gì để dựa |

Luật 6 nói rõ trong docstring rằng nó là **phép kiểm mâu thuẫn**, không phải
phép kiểm liên quan: đa số measurement không khai component (subject `None`) và
một fact đoán bừa component sẽ làm luật này sai một cách tự tin. Có test riêng
cho đúng ranh giới đó.

**2. Bị chặn ≠ bị xoá.** Mỗi cú drop trả về một `Blocked{hypothesis_id, rule,
detail}`. Tỷ lệ từng luật nổ chính là phép đo A6 cần; một guard lọc im lặng làm
model trông như chưa từng mắc lỗi đó. Chặn hết ⟶ abstention **nêu tên các luật**.

**3. Critic là cố vấn, không phải guard thứ hai.** `critique()` trả thứ tự đọc +
cờ ("không xin check nào", "một trích dẫn kèm một khoảng trống đã khai", "không
có observation nào trong số trích dẫn"). Không xoá gì. Tất định ở phase này —
một critic bằng model là một lần gọi nữa cho một ý kiến chưa ai chứng minh là
đáng tiền, và ablation ở A6 phải có **cái gì đó** để so với "không critic".

**4. Biên vào (K2): cách ly, không phải cảnh báo.**

Tên component là chuỗi **duy nhất** trong packet do bên thứ ba viết
(`PluginManifest.id` không ràng buộc charset; `CandidateComponents.*` cũng vậy).
Từ A3, `build_packet_view` cấp nhãn `C1`, `C2`… cho từng tên, và **chỉ nhãn đi
vào prompt**; renderer giữ ánh xạ ngược. Test đòi chuỗi
`"ignore previous instructions…"` **không xuất hiện** trong `view.serialize()`.

Detector đếm (không chặn): `is_suspicious()` trả tên pattern bị chạm. Cả hai nửa
— cách ly và phát hiện — dùng **cùng một** `canonical()`: NFKC, xoá ký tự vô
hình, gộp mọi separator, casefold. Đây là chỗ khe hở thường nằm, và một lần thử
đã chứng minh: `"ignore​previous​instructions"` sau khi xoá ký tự vô
hình thành **dính liền**, nên pattern viết `\s` sẽ đọc nó thành một cái tên bình
thường. Mọi pattern nay viết `\W*` giữa các từ.

Phát hiện **không** chặn vòng: nhãn đã làm chuỗi vô hại, và một nền tảng từ chối
phân tích vì plugin có tên hỗn là nền tảng từ chối phục vụ vì một chuỗi ký tự.
Số đếm đi vào `RoundReport.injection_suspected`.

**5. Nhãn cũng là một "identifier".** Luật 2 cho phép nhãn (`C1`) và tên thật của
packet (`ep-004`, `aisle_B7`) đi qua, chặn `0.74`. `identifiers` của A1 nay trả
**nhãn** thay vì tên thành phần thật — tên thật model không bao giờ thấy.

### Bằng chứng

| Phép kiểm | Kết quả |
|---|---|
| `pytest tests/test_analyst_*.py` (5 file) | **100 passed** |
| Bộ răng mới `tongduyan_analyst-bites.yaml` (14 răng + đối chứng dương) | **14/14 CẮN** |
| `ruff check` module + test | sạch |

Bộ răng phủ: tắt từng luật 2/3/6/7 và luật wording · bỏ ghi `blocked` (không đếm
được luật nào) · để critic xoá cái nó gắn cờ · tắt nhãn (tên thật ra prompt) ·
detector khớp raw text thay vì `canonical` · id bỏ qua check đã xin · bỏ deadline
· META exit code · đối chứng âm (sửa comment **không** được làm đỏ).

Một răng lúc đầu **không cắn** — `ENGINE_MODEL_PICKS_THE_ID` tiêm bỏ `tool_id`
khỏi digest, nhưng test phân biệt hai vòng bằng **arguments**, nên digest vẫn
khác. Đó là răng đặt sai chỗ, không phải code sai: đổi thành
`ENGINE_ID_IGNORES_THE_CHECK` tiêm bỏ `arguments` thì cắn. Ghi lại vì đây đúng
kiểu tự lừa mà `bites` sinh ra để chặn — một răng không cắn được đọc thành "code
an toàn".

### Còn nợ sau A3

- `redact()` viết ra rồi **xoá** ngay trong phase: sau khi nhãn được cấp trong
  `build_packet_view`, không đường nào gọi tới nó nữa. Một hàm public không ai
  gọi là nợ, không phải tính năng.
- Guard chưa nối vào vòng chạy thật — `propose()` trả `RoundReport`, guard là một
  lời gọi riêng. A4 (`runner.py`) là chỗ ghép engine ⟶ guard ⟶ host.

---

## A4-i — Hai object hợp đồng của một vòng được chấm

Phần đầu của A4 (RFC platform). Cố ý tách nhỏ: `budget.py` và
`packet_artifact.py` là **thêm mới**, không đụng file nào đang chạy, nên land
được và kiểm được trước khi sờ vào `gate.py`/`bundle.py` — nơi có 201 test đứng.

### Đã làm gì

**1. `AnalysisBudget` — trần của một vòng, và ai quyết định nó.**

Sáu trục: `max_tool_requests` · `max_model_calls` (cộng dồn cả vòng, không phải
mỗi proposal — số proposal là do analyst chọn) · `max_input_tokens` /
`max_output_tokens` (tính theo usage provider **báo**, không theo ước lượng) ·
`max_wall_time_ms` (cả vòng, gồm cả thời gian trong checker) · `max_frame_bytes`
**theo từng loại frame**.

- `capped_by()` lấy **min từng trường**: bundle xin ít hơn trần thì được đúng
  cái nó xin (bundle calibrate với 1 model call không được lặng lẽ nhận 12 ở
  gate); xin nhiều hơn thì bị cắt.
- `PLATFORM_BUDGET_CAP` là **hằng số trong module**, không phải tham số — cùng
  lý do `OFFICIAL_GOLDEN_READY` là hằng số: nó quyết định platform trả tiền cho
  cái gì, và bên bị chấm không được truyền vào.
- Thiếu cap cho **bất kỳ** frame nào ⟶ từ chối. Một frame không có trần là hình
  dạng mà packet ẩn thoát ra ngoài. `model_response` rộng gấp nhiều lần vì nó
  chở assistant turn nguyên bản của vendor (thought signature, thinking block)
  mà container phải trả lại nguyên vẹn; mọi frame do container tự viết thì chặt.

**2. `PacketArtifact` — một file ở đúng đường dẫn chưa phải là bằng chứng.**

- Loader **tính lại** cả hai checksum thay vì đọc. Checksum do caller nộp là
  checksum caller nộp được cho bất cứ thứ gì, và ca duy nhất đáng chặn — fixture
  bị sửa sau khi provenance đã ghi — đúng là ca mà giá trị lưu sẵn không bắt được.
- **`fixture_kind` được suy ra, không được khai**: `hand_written` hoặc
  `sidecar_present=False` ⟶ `synthetic`. Packet dựng từ run có trước writer mang
  planning input **tái dựng**, và một ngưỡng thoả thuận trên đó là ngưỡng nướng
  sẵn lỗi tái dựng vào. Gate ẩn chỉ nhận `recorded` (luật thi hành ở A4-ii).
- Provenance trỏ sang case khác ⟶ từ chối; provenance tự lệch checksum của chính
  nó ⟶ từ chối; thiếu file ⟶ từ chối và **gọi tên file**.
- `packet_checksum()` dùng **đúng công thức** của `AnalysisRequest.case_packet_checksum`,
  có test đòi hai bên khớp: hai công thức cho "checksum của packet này" sẽ lệch
  ngay lần đầu một bên đổi cách sắp khoá, và lệch đó hiện ra dưới dạng tool
  request bị từ chối vì khai sai packet.

### Bằng chứng

| Phép kiểm | Kết quả |
|---|---|
| `pytest tests/test_analyst_budget_artifact.py` | **14 passed** |
| `pytest` 4 suite explanation + file mới | **201 passed** |
| `ruff check` | sạch |

Một chi tiết về quy ước: refusal ném từ `model_validator` bị pydantic bọc thành
`ValidationError`, nên test đòi `(XRefusal, ValidationError)` — đúng cách
`test_explanation_e5.py` đã làm với `GoldenRefusal`.

### Còn lại của A4

- **A4-ii** — RFC vào `gate.py` (`dry_run`, tách `DryGateRun`/`GateRun`,
  fail-closed hidden + preregistered + mọi packet `recorded`) và `bundle.py`
  (`runner_protocol_version`, embed `requested_budget`,
  `GateDecision.effective_budget_checksum`). Đây là phần đụng fixture của
  `test_explanation_gate.py`.
- **A4-iii** — seam (`RoundHostProtocol` / `AnalystRunner` / `PreparedRound` /
  `RoundSource`), runner có no-progress guard và một điểm `finalize` duy nhất.
- **A4-iv** — JSONL ABI + model gateway + restricted artifact.

---

## Ghi chú vận hành — vì sao có worktree thứ hai

Giữa A2, working tree chung bị chuyển về `main` (An commit phần test-bench và
log của phiên). Ba commit A-1/A0/A1 vẫn nguyên trên nhánh, nhưng hai file A2
đang viết dở nằm ngoài git thì suýt mất, và việc chuyển nhánh qua lại giữa hai
người trong **một** working tree sẽ còn lặp lại.

Từ 2026-08-26, nhánh này chạy trong worktree riêng:

```
git worktree add ../P-011-analyst tongduyan_ai-analyst-ban-8
```

`../P-011-analyst` dùng chung `.git`, nên commit vẫn về đúng nhánh và An giữ
`main` trong thư mục gốc. Xong plan thì `git worktree remove ../P-011-analyst`.

**Một hệ quả cần biết:** worktree chỉ có file **đã track**. `artifacts/runs/`
có 86 file được track (13 packet thật), còn 4 run ngày 25-08 chưa commit thì
worktree không thấy — nên phép đo "17/17 packet thật" ở §A-1/§A1 chạy trong cây
gốc, còn cùng phép đo chạy trong worktree sẽ là 13/13. Khi A6 cần đủ 17, hoặc
An commit 4 run đó, hoặc phép đo chạy ở cây gốc và ghi rõ.

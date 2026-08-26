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
| A4-i budget + packet artifact | **xong** | `5ea1a31` |
| A4-ii RFC gate + bundle | **xong** | `3dba01b` |
| A4-iii seam + runner | **xong** | `3f7f85b` |
| A4-iv wire + gateway + restricted | **xong** | `2353305` |
| M1 metrics cuối cùng vào packet | **xong** | `382ca5d` |
| M2 metrics realtime theo episode | **xong** | (xem §M2) |
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

## A4-ii — RFC vào `gate.py` và `bundle.py`

Phần đụng hợp đồng. Đây là chỗ đã hoãn từ A-1, và hoãn đúng: nó kéo theo việc
dựng lại fixture của `tests/test_explanation_gate.py`.

### Đã làm gì

**1. Bundle tự mô tả đầy đủ hơn.**

`AnalystBundle` thêm hai trường, cả hai vào `identity`:

- `runner_protocol_version` — bundle dựng theo một bộ frame rồi chạy với bộ
  khác là một hệ khác, và triệu chứng là vòng chết giữa chừng vì một frame
  không ai nhận ra.
- `requested_budget` — **object, không phải checksum**. Bundle chỉ mang digest
  của giới hạn thì không tự chạy lại được: phải có ai đó tìm ra cái budget hash
  ra giá trị đó, mà "ai đó" chính là bên đang bị chấm.

`GateDecision` thêm `effective_budget_checksum`: budget vòng chấm **thực sự**
chạy dưới.

**2. `verify_gate_decision` nhận thêm `effective_budget`.**

Lệch ⟶ `BundleRefusal` với câu nói rõ vì sao: analyst được chấm với gấp đôi số
tool call so với production là analyst được chấm như một hệ không tồn tại.
`analyst_visible`/`why_not_visible` nhận `production_budget` và tắt cờ khi lệch.

**3. `gate.py`: `dry_run` thay `allow_visible_suite`, và tách hai kiểu.**

`DryGateRun` **không có** trường `decision`. Trước đây dry run trả về `GateRun`
đầy đủ, tức là sinh ra một `GateDecision` hợp lệ — mà `analyst_visible` nhận
đúng loại object đó. Nghĩa là một buổi diễn tập trên bộ calibration **bật được
tính năng lên**. Tách kiểu đóng đường đó bằng cấu trúc: không có object nào cho
`verify_gate_decision` nhận, vì không có decision.

**4. Fail-closed ba điều kiện** khi không phải dry run:

- suite `hidden` — chấm trên bộ AI team đã hiệu chỉnh là đo mức khớp bộ đó;
- suite `preregistered` — bộ đang làm dở là bộ ai đó còn sửa được, và ngưỡng
  thoả thuận sau khi thấy số không phải ngưỡng;
- **mọi packet là `PacketArtifact` có `fixture_kind == "recorded"`** — dry run
  được nhận packet trần (bắt người ta viết provenance mới cho diễn tập là cách
  làm cho diễn tập không bao giờ xảy ra), vòng chấm thì không.

`GateRun` mang cả `requested_budget_checksum` lẫn `effective_budget_checksum`, và
validator từ chối khi decision khai budget khác run.

**5. Fixture gate dựng lại — và một quyết định cần ghi rõ.**

Helper `preregistered()` dựng suite **thật sự hợp lệ**, dưới ba `mock.patch`
(`OFFICIAL_GOLDEN_READY`, `CASE_FAMILIES`, `MIN_VARIANTS_PER_FAMILY`) vì cả ba
là luật về **dữ liệu đã sẵn sàng chưa**, đều có test riêng ở
`test_explanation_e5.py`, và không phải thứ file này nói về. Nhưng luật
**must_abstain** thì **không patch** — helper tự thêm một case `must_abstain`
thật, vì "im lặng là một câu trả lời được chấm" là luật về hành vi analyst, đúng
thứ file này đang kiểm.

Thêm `artifacts_from()` (packet có provenance, cho vòng chấm) bên cạnh
`packets_from()` (packet trần, cho diễn tập), và `rehearsal()` bên cạnh `gate()`.

### Bằng chứng

| Phép kiểm | Kết quả |
|---|---|
| `pytest` 4 suite explanation + 6 suite analyst | **310 passed** |
| Test mới ở `test_explanation_gate.py` | 9: suite calibration bị từ chối · packet trần bị từ chối · fixture hand-written bị từ chối · run không sidecar bị từ chối · diễn tập nhận cả ba · decision ghi budget · bundle xin quá trần bị cắt về trần · decision khai budget khác run bị từ chối · production budget lệch ⟶ tắt cờ |
| `ruff check` toàn `planbench_explanation` + 2 file test | sạch |

### Còn nợ sau A4-ii

`gate.py` vẫn nhận `analyst: Analyst` (một callable), chưa nhận `RoundSource`.
Đó là A4-iii: seam mới dựng cặp analysis+host từ **cùng** một evidence source,
và đó là chỗ `available_evidence` hết rỗng.

---

## A4-iii — Seam và vòng chạy

### Đã làm gì

**1. `round_host.py` — một nguồn bằng chứng, hai thứ dựng từ nó.**

Lỗi mà hình dạng này sinh ra để chặn tìm được bằng cách đọc, không phải chạy:
`AnalysisRequest.available_evidence` là field frozen mặc định rỗng, và
`ToolSession.admit` từ chối mọi tool có `required_evidence` không nằm trong đó.
Dựng request trước, host sau — thứ tự hiển nhiên — thì host đang ngồi trên cả
trace mà mọi request chết ở `missing_required_evidence`, và analyst đọc vòng của
chính nó thành "platform không có gì", một câu về platform **không đúng**.

Nên không có chỗ nào ở đây dựng request trước: `EvidenceSource` dựng trước, tập
available **suy ra** từ nó (`evidence_for`), rồi request và host cùng nhận một
object. Chúng không thể bất đồng vì không bên nào được hỏi.

Tập available suy ra thật, không nhận từ caller: không route đo được ⟶ bỏ
`region_geometry`; không inflation ⟶ bỏ `inflation_parameters`; không xếp hạng
ai ⟶ bỏ `comparison_pair`. Không sidecar ⟶ `PRE_SIDECAR_AVAILABLE_EVIDENCE`.
Packet trần (không provenance) ⟶ **giả định không có sidecar**: giả định ngược
lại là đưa cho analyst đúng những tool run không phục vụ được.

`PreparedRound` mang cặp + ba checksum, trong đó `evidence_identity_checksum` là
bằng chứng cặp đó đến từ một nguồn — gate artifact lưu nó để câu "vòng này dựng
từ bằng chứng kia" kiểm lại được thay vì tin.

**2. `runner.py` — bốn lối ra, mỗi lối một tên, tất cả qua một `finalize`.**

| Kết thúc | Nghĩa |
|---|---|
| `final` | model hết thứ để hỏi |
| `revisions_exhausted` | ngân sách vòng sửa là một con số, không phải một tâm trạng |
| `no_progress` | xin lại đúng check đã chạy — **checker là tất định**, lần hai trả đúng lần một, nên vòng đó tiêu một model call để biết đúng thứ đã biết |
| `budget_exceeded` | một trục cạn. Ghi là kết thúc riêng, không gộp vào abstention: "tôi không có gì để nói" và "tôi bị dừng" là hai câu trả lời khác nhau |

Cộng `model_failed` khi provider hỏng — trả abstention **có lý do**, không phải
im lặng.

`no_progress` khoá theo `(tool_id, tool_version, arguments)` và **không** theo
hypothesis: hai giả thuyết hỏi cùng một tool cùng một câu nhận cùng một câu trả
lời, và trả tiền hai lần vẫn là lãng phí như nhau.

**Declare trước request** là bất biến duy nhất của vòng lặp: host gắn bằng chứng
vào giả thuyết nó được thu cho, nên request tới trước sẽ bị từ chối
`unknown_hypothesis` — và cái từ chối đó đọc ra như platform hỏng.

Runner cầm `RoundHostProtocol` (hai động từ), **không thấy session**. Lane
in-process và lane container sau này là cùng một đường code ở đây.

**3. Engine nhận feedback để sửa.** `CheckFeedback` cố ý **không** phải
`ToolResult` thô: result mang measurement, và model được cho xem measurement sẽ
đặt nó vào câu tiếp theo — rồi guard drop vì câu mang số. Thứ nó cần để sửa là
**verdict** và lý do, nên đó là thứ nó nhận. `REVISION_PREFACE` là hằng số và
nằm trong `prompt_checksum`: lượt thứ hai là một phần của cùng một yêu cầu.

### Một luật guard phải nới, và vì sao

Luật 4 bản đầu viết: tool **không phải** mechanism_check mà khai
`supported_proposition_types` không rỗng ⟶ chặn. Sai:
`get_candidate_contrast` là `fact_query` và khai `component_specific_attribution`.
Hậu quả đo được: mọi đề xuất xin tool đó bị biến thành một con số
blocked-claim. Luật đúng chỉ có một vế — **mechanism check chỉ được hỏi câu mà
card của nó trả lời được**. Đã nới, kèm comment nói rõ lần sai này.

### Bằng chứng

| Phép kiểm | Kết quả |
|---|---|
| `pytest` 7 suite analyst + 2 suite explanation | **269 passed** |
| Bộ răng `tongduyan_analyst-bites.yaml` | **23/23 CẮN** (thêm 9 răng mới cho seam, runner, và gate fail-closed) |
| `ruff check` | sạch |

Một răng khai sai lúc đầu (`GATE_TAKES_A_BARE_PACKET` tiêm chuỗi hai dòng, mà
bitekit chỉ thay một dòng). Sửa bằng cách đưa câu từ chối ra hằng số
`_BARE_PACKET_REFUSAL` — refusal một dòng ở chỗ gọi, và răng bám vào đúng dòng
đó. Ghi lại vì đây là lần thứ hai một răng không cắn do **khai sai chỗ tiêm**,
không phải do code an toàn.

### Còn lại của A4

**A4-iv** — JSONL ABI (`stdio_protocol.py`, `stdio_lane.py`), model gateway giữ
credential, và restricted artifact cho stderr/transcript của hidden gate.

---

## A4-iv — Dây, cổng giữ khoá, và thứ ở lại với platform

Ba module: `stdio_protocol.py` · `model_gateway.py` · `restricted.py`. A4 xong.

### Đã làm gì

**1. Dây: một dòng JSON một frame, và một danh sách những gì bị từ chối.**

`stdout` chở **protocol và không gì khác** — container in một cảnh báo ra stdout
là đã làm hỏng luồng, và cách đọc trung thực một luồng hỏng là "vòng này kết
thúc", không phải "bỏ dòng đó rồi hy vọng". Log đi stderr, và stderr là
restricted artifact chứ không phải một kênh.

Frame bị chặn theo **từng loại**, trần lấy từ budget của vòng chứ không từ hằng
số: frame hợp pháp chở một megabyte — assistant turn của vendor quay về qua
gateway — đúng là frame mà một cú rò rỉ sẽ chọn.

Sequence tăng nghiêm ngặt (trùng ⟶ replay), phase là máy trạng thái
(`tool_request` trước khi declare = xin bằng chứng cho giả thuyết chưa ai khai).
`error` tới được từ **mọi** phase: máy trạng thái nhốt được một vòng đang hỏng
là máy trạng thái treo.

**2. Gateway: container không bao giờ cầm khoá.**

Config đọc từ **bundle đã đóng băng**, không từ frame; frame khai khác ⟶ kết thúc
vòng, không merge. Model khai khác bundle ⟶ từ chối.

`ProviderTurn` round-trip **nguyên vẹn** dưới dạng mapping JSON: Gemini từ chối
lượt kế nếu thiếu `thought_signature`, Anthropic đòi thinking block y nguyên.
Gateway không đọc, không sửa; format lạ vẫn chuyển tiếp — đó là thứ làm một
transcript đi được qua lần đổi provider.

Tiêu tiền tính theo **usage provider báo**, không theo ước lượng: ước lượng quyết
định có gửi đi không, hoá đơn quyết định đã tiêu bao nhiêu. Vượt phát hiện **sau**
lời gọi, response giữ trong restricted transcript — chỗ duy nhất trung thực để
giữ một câu trả lời mà vòng không được dùng.

**3. Restricted: cái platform giữ, cái submitter nghe.**

stderr có trần và **khai rõ đã cắt bao nhiêu byte** (trần âm thầm là một log nói
dối về chuyện đã xảy ra). Submitter nhận **mã lỗi đóng + token vô danh** cho case
— "analyst của bạn chết ở `narrow-gap-007`" là nói cho họ biết case ẩn nào tồn
tại và nó về cái gì. Token salt theo run: giữ token của lần nộp trước cũng không
ghép được sang lần này.

### Ba lỗi bộ răng tìm ra, không phải test tìm ra

Đây là phần đáng đọc nhất của phase này.

**(a) Refusal tự nó là một kênh rò.** Răng `STDIO_ERROR_QUOTES_ITS_INPUT` **không
cắn** — và lý do là test yếu: nó gửi `message_type="tool_request"` (một frame
hợp lệ) nên không bao giờ chạm dòng bị tiêm. Sửa test cho đúng thì **code đỏ**:
`decode` đang nhét `str(message_type)` — chuỗi do container viết — vào thông điệp
lỗi. Container đặt tên frame bằng nội dung packet ẩn rồi đọc lại từ log của
platform. Vá bằng `safe_detail()` (lọc charset + cắt 32 ký tự), và **cùng lỗi ở
field thứ hai** (`protocol_version`) cũng vá luôn, kèm test riêng.

**(b) Nửa input của cổng token chưa từng được kiểm.** Răng
`GATEWAY_TRUSTS_THE_ESTIMATE` không cắn vì test overshoot bằng **output** token,
nên tắt nhánh input vẫn xanh. Thêm test cho nhánh input, và răng chuyển sang bám
đúng nhánh đó.

**(c) Gọi khi không còn output budget.** Phát hiện lúc viết test (b):
`max_tokens=min(..., remaining)` có thể ra ≤ 0 — tức trả tiền cho một câu trả lời
vòng buộc phải vứt. Thêm luật từ chối **trước khi gửi**.

Cả ba đều đúng thứ `bites` sinh ra để bắt: một cổng xanh không có nghĩa cổng có
răng, và một răng không cắn phải được đọc là "chưa biết", không phải "an toàn".

### Bằng chứng

| Phép kiểm | Kết quả |
|---|---|
| `pytest` 8 suite analyst + 4 suite explanation | **361 passed** |
| Bộ răng `tongduyan_analyst-bites.yaml` | **32/32 CẮN** + đối chứng dương |
| `ruff check` | sạch |

### Còn nợ sau A4

- `stdio_lane.py` (spawn container thật, đọc stdout/stderr, kill khi timeout)
  **chưa viết**: nó cần `docker/Dockerfile.analyst`, và image là việc của A7.
  Hợp đồng — frame, phase, trần, gateway, restricted — đã đủ và đã có răng; phần
  còn lại là ống dẫn process, viết cùng lúc với image thay vì viết mù bây giờ.
- Ghi rõ vì đây là **một hạng mục hoãn có tên**, không phải một phần bị quên.

---

## M1 — Metrics cuối cùng vào packet

Phase đầu của plan bản 9. An chốt: analyst phải đọc được metrics cuối cùng.

### Đã làm gì

**1. `CandidateMeasurements` — cái mỗi candidate thật sự đạt được.**

Waterfall nói **một cặp** khác nhau bao nhiêu; nó không nói bên nào làm được gì.
Người đọc hỏi "vì sao bên này thắng" với tay tới success rate và đuôi latency
trước tiên, mà tới trước M1 hai số đó nằm trong report và **không bao giờ** tới
analyst — nên thứ duy nhất analyst nói được là ΔU.

Bảy trường, **tất cả optional**: run khác nhau ghi khác nhau, và một phép đo
thiếu phải đọc ra là **thiếu**, không phải bằng 0.

**2. `MeasuredValue` — và luật mẫu số.**

`unit="ratio"` mà không có `denominator` ⟶ **từ chối dựng packet**. "100% trên
năm episode" và "trên ba trăm episode" là hai claim khác nhau đội cùng một con
số, và đó đúng là câu nền tảng này tồn tại để chặn. Mẫu số cũng là **một fact
riêng** (`fact:metric:<cand>.success_rate.denominator`) để một câu có thể trích
dẫn nó.

**3. `GateOutcome` — cổng có ngưỡng và giá trị.**

`{"passed": false}` nói một candidate bị loại và **từ chối nói** loại cách bao xa
hay so với cái gì. Nay mỗi hàng mang `threshold`, `value`, `unit`, `direction`,
và `candidate_id` (bảng cổng là theo candidate; hàng không khai của ai là phán
quyết về không ai cả).

`gate_outcomes` đọc hàng mới, **lùi về** pass/fail trần cho packet cũ — và lùi về
với `threshold=None`, đúng nghĩa "run này chỉ ghi lại việc bị loại".

**4. Đọc từ report, không đoán.** `measurements_from_report` /
`gate_rows_from_report` chỉ lấy thứ report thật sự có. Cổng nào có hình dạng
**không nằm trong bảng `_GATE_NUMBERS`** thì đóng góp verdict và **không con số
nào** — bịa một ngưỡng từ một khoá lạ là đặt vào packet một con số mà run chưa
từng so với cái gì.

**5. Hai version bump, vì hợp đồng đổi thật.**

- `EXPLANATION_SCHEMA_VERSION` 0.1.0 ⟶ **0.2.0** (packet đổi hình).
- `TOOL_CATALOG_VERSION` 3.0.0 ⟶ **3.1.0** (thêm card `get_candidate_measurements`).
- 34 file schema xuất lại; test pin version cập nhật.

Hệ quả đã cảnh báo trong plan bản 9 và nay thành thật: **17 packet cũ trong
`artifacts/runs/` sẽ bị `build_packet_view` từ chối** — đúng luật, vì header khai
0.1.0. Muốn dùng lại thì dựng lại packet cho run đó.

### Bằng chứng

| Phép kiểm | Kết quả |
|---|---|
| `pytest` 8 suite analyst + 6 suite explanation | **421 passed** |
| Bộ răng | **32/32 CẮN** |
| Chạy trích xuất trên report thật | **30/30 report sinh được measurements**; ví dụ `success_rate = 0.7 ratio over 30`, `latency_p99_ms = 5.259 ms over 30`; 12 gate row mỗi run, 4 hàng có số |
| `ruff check` | sạch |

Đây là lần đầu con số An mô tả ("70% so với 95%", "p99 19,3 ms so với 6,06 ms")
có một `ref` để analyst trích dẫn.

### Còn nợ sau M1

- `path_length_m` và `latency_median_ms` chưa có nguồn trong report (report ghi
  `travel_time_s` chứ không ghi quãng đường). Để `None` chứ **không** suy từ
  travel time — hai đại lượng khác nhau.
- Card `get_candidate_measurements` mới có **card**, chưa có handler trong
  `ToolHost`: analyst đọc số qua fact index được ngay; gọi tool thì host trả
  `tool_unavailable`. Nối handler nằm ở A5/A6 khi host được mở rộng, ghi ra để
  không ai đọc "card đã có" thành "tool chạy được".

---

## M2 — Metrics realtime theo episode

### Đã làm gì

**1. `EpisodeTimeline` + `TimelinePoint` — và đồng hồ nằm trong object.**

`clock` là một field, không phải quy ước theo vị trí. "Ai đang dẫn" và "ai làm
cùng khối lượng việc tốt hơn" là **hai câu hỏi** đội một cái tên: ở cùng mốc
đồng hồ tường, hai robot đang ở hai chỗ khác nhau trên nhiệm vụ; ở cùng mốc tiến
độ, chúng ở cùng chỗ nhưng tốn thời gian khác nhau. So clearance ở **cùng thời
điểm** là so hai phần khác nhau của bản đồ, và con số rơi ra không nói về bên nào.

Đồng hồ cũng nằm **trong ref**: `episode:<id>/at_time/<mốc>.<metric>` và
`episode:<id>/at_progress/<mốc>.<metric>`. Một trích dẫn không khai mốc nào là
một trích dẫn không đọc được.

**2. Dùng lại `sample_series` của E4.3, không viết lại.** Tám con số đó đã có
đúng một implementation, và hai implementation của "clearance nhỏ nhất tới giờ"
là hai định nghĩa tự do trôi khỏi nhau — trôi mà **không nhìn thấy được**, vì cả
hai đều render ra thứ trông như clearance.

**3. Chỉ 2 vai × 3 mốc, và đó là một quyết định về giá.**

`TIMELINE_ROLES = ("typical", "safety_critical")` — hai cực ΔU đã được waterfall
mô tả rồi; thứ timeline thêm vào mà phân rã không có là **hình dạng** của một
episode đại diện và của cái suýt chạm gì đó.

Đo thật, in ra chứ không ước lượng:

| | trước M2 | sau M2 |
|---|---|---|
| fact mỗi packet | 41 | **101** |
| byte serialize | 7.500 | **21.000** |

Gấp 2,8 lần. Đây là chi phí prompt **mỗi vòng phải trả**, và là lý do giới hạn ở
2 vai × 3 mốc chứ không phải 4 vai × mọi trace row. A6 sẽ so chất lượng **và**
chi phí, không chỉ chất lượng.

**4. Thiếu cột thì bỏ qua và nói rõ.** `_slice_from` trả `None` khi trace thiếu
một cột — dựng slice từ nửa số cột là báo cáo một thời điểm khác cái được hỏi.
Mọi lần bỏ đều thành một dòng `omissions`, vì người đọc hỏi "sao giải thích mỏng
thế" xứng đáng có lý do.

**5. Card `get_episode_timeline`** (`fact_query`, đòi `trace` + `reference_line`),
`TOOL_CATALOG_VERSION` 3.1.0 ⟶ **3.2.0**, 36 schema xuất lại.

### Bằng chứng

| Phép kiểm | Kết quả |
|---|---|
| `pytest` 8 suite analyst + 6 suite explanation | **427 passed** |
| Bộ răng | **32/32 CẮN** |
| Đo chi phí packet | 41 ⟶ 101 fact; 7.500 ⟶ 21.000 byte |
| `ruff check` | sạch |

### Còn nợ sau M2

- `build_scoring_packet` nay nhận `deployment` (optional). Caller trong
  `apps/api` chưa truyền — không truyền thì packet không có timeline và
  `omissions` nói rõ vì sao. Nối caller là một dòng ở phía API, để lại vì nó
  nằm ngoài phạm vi file An đang sửa song song.
- Handler cho `get_episode_timeline` trong `ToolHost` chưa có, cùng tình trạng
  với `get_candidate_measurements` ở M1 — đọc qua fact index thì được, gọi tool
  thì `tool_unavailable`.

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

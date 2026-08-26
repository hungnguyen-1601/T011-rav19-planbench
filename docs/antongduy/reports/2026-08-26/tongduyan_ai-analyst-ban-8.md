# Báo cáo thi hành — AI Analyst bản 8 (lớp AI cố vấn "vì sao A thắng B")

**Plan:** `plans/2026-08-26/ai-analyst-ban-8.md` · **Verify nền:**
`notes/2026-08-26/tongduyan_verify-plan-ai-analyst.md`
**Nhánh:** `tongduyan_ai-analyst-ban-8`, tách từ `main` tại `738ee1f`
**Quy ước:** một file cho cả plan; mỗi phase một mục, viết ngay sau khi commit
phase đó.

| Phase | Trạng thái | Commit |
|---|---|---|
| A-1 vá sàn model-free | **xong** | `5932779` |
| A0 skeleton + hạ tầng | **xong** | `df1743a` |
| A1 packet view + fact index | **xong** | (xem §A1) |
| A2 hypothesis engine | chưa | |
| A3 guard + critic + biên vào | chưa | |
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

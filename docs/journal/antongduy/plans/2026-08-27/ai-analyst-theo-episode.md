# Plan — AI Analyst theo episode: "ở episode đang mở, stack nào thắng, và khác biệt nào liên quan"

**Ngày:** 2026-08-27 · **Trạng thái:** **bản 10 — An đã duyệt 2026-08-27,
chưa thi hành, chờ lệnh An**
**Bản 10:** §6 đổi từ câu hỏi thành **quyết định đã chốt** (7 mục), các
phase liên quan cập nhật theo: P0 merge chỉ sau full suite đạt, fail ngoài
waiver ⇒ dừng; playhead optional đo bằng `ep_playhead`; ε = 0.005 chốt trước
dữ liệu thật; P5 o4-mini, funnel hai giai đoạn, trần 2–3 USD, local chỉ
smoke; P2.5 optional sau lõi, An duyệt `rrtstar`/`dwa` trước, snapshot
`traits-episode-2026-08-27-r1` approved-only, chưa pin version.
**Bản 9 — sau vòng rà thứ tám của An (2 blocker P2.5, nhận cả hai):**
(1) **review tooling** — CLI hiện chỉ `list / seed / approve`, `approve` chỉ
kiểm nội dung + người ký + anchor; thêm `show / validate / link / unlink /
snapshot`, `approve` gọi `validate` và đòi `--expect-row-checksum`; (2)
positional key `weakness:<i>` chống drift bằng `statement_checksum` (cùng
`canonical` + `artifact_checksum` của W1.8, không công thức thứ hai), pin
`kb_entry_version`, index chốt **0-based** (đúng `enumerate` đang dùng);
drift bắt ở **tầng ghi**: sửa row `approved` ⇒ tự về `draft`.
**Bản 8 — sau đề xuất thứ bảy của An (traits quay lại như nhánh tuỳ chọn,
nhận có phản biện):** traits là **mechanism reference**, không phải
occurrence — bất biến thứ 5; **P2.5 tuỳ chọn** sau P4 tất định, cờ
`episode_traits` (mặc định off, vào checksum/cache/audit), chỉ đọc snapshot
bộ ba W1.8, chỉ `approved` vào preview. **Phản biện đã vào:** (a) trait hiện
là văn tự do — activation không chạy được; thay vì đẻ bộ activation thứ hai,
trait **link tới KB entry** (`mechanism_links: [kb:<id>]`, migration 0013),
activation = `knowledge.match` sẵn có; (b) khớp chính xác `algorithm_id +
kind`, version pin là quyết định sau; (c) 4/7 loại golden §9 cần world mới ⇒
tách P5.5 tuỳ chọn; (d) guard phân loại ref theo tiền tố, model không tự
tách occurrence/reference; (e) P2.5 code được nhưng **chỉ đo được sau khi
An ký subset traits**.
**Bản 7 — sau vòng rà thứ sáu của An (lifecycle chọn episode):** bất biến
thứ tư — `episode_context_id` là **scope bắt buộc**: thiếu ⇒ không dựng
packet, không gọi provider analyst, **không fallback run scope**; structured
refusal `episode_not_selected`; "đang trỏ vào" = chọn **bởi người dùng**
(`selectionOrigin=user`), không phải mặc định `episodes[0]` của replay; nút
AI không render khi không có episode; response luôn mang
`episode_context_id`, UI drop response stale khi selection đổi hoặc bỏ.
**Bản 6 — sau vòng rà thứ năm của An (1 blocker, nhận):** `kb:*` là
**mechanism reference**, không phải **occurrence evidence** — KB nói cơ chế
tồn tại và thường hoạt động thế nào, không nói nó đã xảy ra trong episode
này. Contract `bearing=contrast` đổi thành năm vế có tên:
`contrast_support` · `occurrence_evidence` (bắt buộc: `obs:*` / checker
`supported` / artifact episode-scoped) · `mechanism_reference` (**tuỳ chọn**)
· `subject_match` · `polarity_match`. Đây chính là luật A5 cho scope run
(*trait/KB ref không thay được ref đo*) áp lại cho episode.
**Bản 5 — sau vòng rà thứ tư của An (4 điểm, nhận cả 4):** (1) **must-fix**
— `known_unknowns` không carry nguyên từ run: phân ba lớp global / run-
statistical / episode bằng bảng platform (không thêm field vào `KnownUnknown`
— wire contract), `blocked_claim_types` **tính lại** từ evidence episode;
(2) `EpisodeRoundResult` có persistence contract (cache serialize cả hai,
version check, thiếu annotation ⇒ refuse, `finalize` kiểm 1:1) và **chỉ
in-process lane** — container lane từ chối `episode_scope`; (3) budget ưu
tiên diagnosis trên weak contrast context; (4) **gỡ traits khỏi plan** —
không arm, không migration DB thật, không chờ duyệt; traits là nature, không
polarity, 6/6 draft.
**Bản 4 — sau vòng rà thứ ba của An (7 điểm, nhận cả 7):** (1) `bearing`
**không** vào `HypothesisProposal` — wrapper `EpisodeRoundResult{response,
annotations}` theo đúng tiền lệ W4, chốt ở P2.0; (2) **bỏ**
`checker_confirms_on_candidate` khỏi enum contrast — checker là mechanism
evidence, contrast phải có trước; (3) `candidate_measurements` gỡ khỏi menu ở
**mọi** arm episode, `ep_run_context` chỉ thêm khối không citable có checksum;
(4) verdict không có hướng (`tie`/`not_comparable`/`undecidable`) ⇒ contrast
có hướng rỗng, `ruled_out_reason=verdict_has_no_direction`; (5) không xếp
hạng hai `failure_reason` — repo không có policy canonical (kiểm `gates.py`);
`outcome_only` chỉ cho success vs failure; (6) polarity có **một** nguồn: bảng
`EFFECT_DIRECTION` cạnh `ASSERTABLE_PROPOSITIONS` trong `propositions.py` —
"cơ chế" trong repo chính là `PropositionType`, KB/traits không khai polarity
nên không thể xung đột; (7) không mở rộng `GateDecision` đang chạy —
`EpisodeGateDecision` chỉ là spec, settings luôn từ chối `production`.
**Bản 3 — sau vòng rà thứ hai của An (3 cao + 3 kỹ thuật, nhận cả 6, hai
điểm có phản biện):** (1) `contrast:*` có **sức mạnh khác nhau** — thêm
evidence contract cho `bearing=contrast` (contrast ref + mechanism ref +
subject khớp + **polarity** khớp verdict); polarity là trường **platform**
trên mechanism candidate, không phải output model; (2) bốn mode
`off / shadow / internal_preview / production`; `production` đòi
`GateDecision` mở rộng scope episode, máy kiểm — và **plan này không tới
được `production`**, đích là `internal_preview`; (3) verdict bốn `basis`,
thiếu hàng ⇒ `not_comparable` không phải thua; ε **preregister** trước khi
chạy dữ liệu thật; (4) budgeter cắt theo **nhóm nguyên tử** có phụ thuộc,
checksum sau budgeting; (5) `RoundSource` giữ `RunContext` bất biến — host
không đọc report từ đĩa; **phản biện** `context_refs` (bump schema): run
facts **không citable** thay vì thêm field; (6) full suite + ruff + tsc +
migration DB tạm + import smoke **trước merge ở P0** (trả nợ plan bản 8 đã
hết mà chưa chạy full), lặp lại cuối P6.
**Bản 2 — sau vòng rà thứ nhất (5 điểm):** tách chẩn đoán/đối chiếu; mẫu
cụm; nhãn không từ detector; cờ cho LLM output; budgeter thay trần cứng.
**Thay đổi phạm vi:** An chốt thu hẹp từ "đọc toàn bộ run" xuống "episode
đang trỏ vào". Khối run-level giữ nguyên trên nhánh
`tongduyan_ai-analyst-ban-8`; plan này cắm **scope thứ hai** lên cùng seam.
**Khảo sát nền:** `notes/2026-08-27/tongduyan_khao-sat-tai-dung-cho-analyst-theo-episode.md`.

---

## 0. Câu hỏi hệ phải trả lời, và ai trả lời phần nào

> *Ở episode `<id>` đang mở, giữa hai stack đang vẽ, **bên nào thắng**, **điều
> gì đã xảy ra với mỗi bên**, và **khác biệt nào giữa hai bên có thể liên quan
> tới kết cục đó**?*

| Output | Ai trả lời | Nguồn | Câu trên UI |
|---|---|---|---|
| **`EpisodeVerdict`** | platform, tất định | `episode_decision_utility` hai bên; không có thì kết cục | *"C1 thắng episode này (theo utility episode)"* |
| **`EpisodeDiagnosis`** — từng bên | platform, tất định | detector, running metrics, planning attempts, theo candidate | *"Quan sát trên C2: kẹt 4,1 s ở mét 12"* |
| **`EpisodeContrast`** — khác biệt liên quan verdict | platform (luật đối chiếu) → sàn → LLM opt-in | chỉ finding qua **evidence contract §P1.4** | *"Các cơ chế có thể liên quan đến khác biệt trong episode này"* |

**Năm bất biến mới, cộng sáu bất biến bản 8 §1:**

- *Trait là mechanism reference, không phải occurrence evidence.* Trait mở
  rộng hoặc xếp hạng giả thuyết; không chứng minh cơ chế đã xảy ra trong
  episode. `bearing=contrast` luôn cần evidence episode độc lập:

  ```
  episode contrast + occurrence evidence + (tuỳ chọn) trait/KB reference
    + subject/polarity khớp  →  contrast explanation
  ```

- *`episode_context_id` là scope bắt buộc.* Thiếu ⇒ không dựng packet, không
  gọi provider analyst, không fallback sang run scope; trả structured refusal
  `episode_not_selected`. LLM không "phản ứng" gì vì nó không được gọi.

- *Người thắng không bao giờ là output của model.*
- *Một quan sát trên một bên không phải lời giải thích.* Finding không qua
  evidence contract thì render là **chẩn đoán**.
- *Polarity là của platform, một nguồn.* Cơ chế hại hay lợi cho subject
  đọc từ bảng `EFFECT_DIRECTION[PropositionType]` trong `propositions.py`;
  không có trong bảng ⇒ `ambiguous`. Model, KB, traits đều không khai được.

## 1. Vì sao hướng này có cơ hội — nói đúng phạm vi

Ba đợt đo 26-08: trên packet tổng hợp model viết chung chung, không thắng
bảng tra 6 dòng; thêm khối dữ liệu chỉ làm prompt loãng. Hướng episode cho
**đầu vào cụ thể** (sự kiện có mốc giây/mét) và **mỏ neo tất định** (verdict +
bảng đối chiếu kết cục).

**Điều nó không cho:** lực thống kê. ~15 episode từ 6 world là **6 cluster**;
preregistration đếm cluster ⇒ vẫn dưới 12, **vẫn exploratory**. Cái thêm được
là độ tin cậy trong cluster (`pass^3` mô tả) và phép đo detector recall.

**Đích của plan:** panel tất định ship được; LLM tới **`internal_preview`**.
`production` chỉ định nghĩa hình dạng cổng, không mở trong plan này.

## 2. Phase

Mỗi phase: commit một dòng tiếng Anh, một mục trong
`reports/2026-08-27/tongduyan_ai-analyst-theo-episode.md`. Từng phase chỉ
chạy test phần vừa sửa; full suite ở **P0 (trước merge)** và **P6**.

### P0 — Trả nợ và nền nhánh (1 ngày) — **cần An quyết §6.1**

Plan bản 8 + W0–W4 đã hết mà chưa chạy full suite (luật CLAUDE.md §6). Trả ở
đây, **trước** khi merge:

1. Trong worktree `../P-011-analyst`: full suite Python (nền), `ruff check`,
   `npx tsc --noEmit` + vitest liên quan, `alembic upgrade head` trên **DB
   tạm** (0011 → 0012), import smoke `docker/Dockerfile.analyst` (không
   daemon ⇒ chạy `python -c "import planbench_analyst"` với PYTHONPATH của
   image), `test_dev_stack_pythonpath`.
2. **Waiver có tên**: 5 test `tests/test_host_parity_golden.py` lệch float
   chữ số cuối, có trước W1.0 (đã stash kiểm) — ghi vào report P0, không
   sửa số cho khớp.
3. **Merge chỉ sau khi bước 1 đạt** (An chốt §6.1): mọi failure **ngoài**
   waiver ở bước 2 ⇒ **dừng**, báo An, không merge, không sửa test cho xanh.
   Đạt ⇒ merge `tongduyan_ai-analyst-ban-8` → `main` (merge sạch, 0 file chạm
   hai phía); `git worktree remove ../P-011-analyst`; tạo
   `tongduyan_analyst-episode` từ `main`.
4. **Traits tắt cho P1–P4**: migration 0012 chỉ chạy trên DB tạm ở bước 1
   để chứng minh nó chạy. Migration trên `planbench.db` thật: **sau lõi
   P1–P4**, theo §6.7.

**DoD:** full suite xanh trừ waiver đã ghi; nhánh mới có
`services/analyst_service`; báo cáo P0 liệt kê số test và waiver.

### P1 — `EpisodePacket`: verdict, chẩn đoán, đối chiếu, sàn (2,5–3 ngày)

Module mới `packages/explanation/planbench_explanation/episode_packet.py`.
Tất định, không LLM.

**1. `EpisodeVerdict`** — từ `report.candidates[].episodes[]`, bốn `basis`:

| `basis` | Điều kiện | `winner` |
|---|---|---|
| `episode_decision_utility` | cả hai có hàng **và** có utility | dấu của Δ; `|Δ| < ε` ⇒ `tie` |
| `outcome_only` | cả hai có hàng, ≥1 thiếu utility, **một bên success một bên failure** — duy nhất phép phân hạng không cần policy | bên success |
| `not_comparable` | **một bên không có hàng** — không chạy, bị loại trước, thiếu bản ghi, dừng sớm | không có; UI: *"Không thể so episode này vì một candidate không có bản ghi tương ứng"* |
| `undecidable` | cả hai có hàng, không có utility, và cùng success **hoặc cùng failure** — repo không có thứ tự canonical cho `failure_reason` (kiểm `gates.py`), không phát minh | không có |

**Verdict không có hướng** (`tie`, `not_comparable`, `undecidable`) ⇒ mọi
contrast cần winner/loser **rỗng**, `ruled_out_reason = verdict_has_no_direction`;
chỉ trả `EpisodeDiagnosis`. Sàn và model không được tự chọn bên thua.

- `utility_a/b`, `delta_utility`: `MeasuredValue(unit="utility", denominator=1)`.
- **ε = 0.005 — An chốt trước dữ liệu thật** (§6.5): nằm trong
  `preregistration_episode.py` (checksum pin). Ngoại lệ duy nhất: nếu
  quantization của utility (bước lượng tử từ anchor) buộc đổi — khi đó đổi
  **trước** khi chạy run thật, ghi lý do kèm bước lượng tử đo được, checksum
  đổi và khai trong report.
- `caveat` một giá trị hợp lệ duy nhất, validator từ chối viết lại.

**2. `EpisodeDiagnosis`** — theo từng candidate: kết cục đọc thẳng; `Detection`
từ `read_trace → choose_reference → detect_all` (**không** `summarise`), giữ
`window`; planning attempts từ sidecar khi có; trạng thái running cuối.

**3. Phân kỳ và mốc** — `build_replay_sync_view` → `DivergenceReport`;
timeline `timeline_from_trace(role="selected")`, mốc = {đầu, cuối} ∪ phân kỳ
∪ playhead (tuỳ chọn). Hai đồng hồ không trộn.

**4. `EpisodeContrast` — evidence contract.** Mỗi finding khai `contrast_kind`
(enum đóng, mỗi loại một hàm thuần) và **sức mạnh** của nó:

| `contrast_kind` | Bằng chứng | Được làm gì |
|---|---|---|
| `outcome_differs` | kết cục khác theo hướng lợi cho winner | **context**: nhắc lại verdict, **không** support cơ chế |
| `component_differs` | cơ chế thuộc thành phần **khác nhau** giữa hai stack | **thu hẹp** không gian cơ chế; không support một mình |
| `divergence_precedes_outcome` | `DivergenceReport.earliest` trước mốc kết cục tách | **temporal association**; cần thêm mechanism evidence |
| `detection_only_on_loser` | type có ở bên thua, không ở bên thắng | support `associated` **nếu** polarity cơ chế = `harms_subject` |
| `detection_worse_on_loser` | cùng type, mức độ xấu hơn theo `SEVERITY` (direction-aware) | support `associated` nếu polarity khớp |

**Checker không phải contrast.** `ToolResult`/`EvidenceReference` là
**mechanism evidence** — nó đi đường sẵn có `ToolResult → CheckFeedback →
InvestigationRecord`, promotion matrix đọc record. Contrast phải **tồn tại
trước** checker (detection chỉ ở loser / xấu hơn ở loser); checker chỉ nâng
độ chắc của cơ chế đã gắn vào contrast đó. Không có "derived contrast" sau
tool, không sửa `PacketView` tĩnh. Đường lên matrix:

```
contrast có sẵn (support) + checker supported đúng bên + polarity khớp
  → đủ điều kiện đưa vào promotion matrix — matrix vẫn quyết
```

**Polarity — một nguồn.** Trong repo "cơ chế" chính là `PropositionType`
(danh sách đóng `propositions.py:30`; `DETECTION_HYPOTHESES` và KB entry đều
trỏ về nó). Thêm bảng `EFFECT_DIRECTION: dict[PropositionType, Literal[
"harms_subject","benefits_subject","ambiguous"]]` cạnh `ASSERTABLE_PROPOSITIONS`,
kèm `MECHANISM_POLARITY_VERSION` vào runtime identity. Sáu cơ chế đã map đều
`harms_subject`. `MechanismCandidate`, KB entry, trait **không có trường
polarity** — chúng chỉ mang `proposition_type`, nên không có gì để xung đột;
không có trong bảng ⇒ `ambiguous`. Luật khớp verdict: `harms_subject` phải
nằm trên **bên thua**, `benefits_subject` trên **bên thắng**; `ambiguous` ⇒
chỉ chẩn đoán, không contrast, không promotion.

**Hai loại evidence — không thay nhau được.**

| Loại | Ref | Chứng minh gì |
|---|---|---|
| **Occurrence evidence** | `obs:*` (Detection của **episode này**), checker `supported` đúng bên, artifact episode-scoped | cơ chế **đã xảy ra ở đây** |
| **Mechanism reference** | `kb:*`, `trait:*` (P2.5), tài liệu tham chiếu | cơ chế **tồn tại và thường hoạt động thế nào** |

`divergence_precedes_outcome` là temporal association ⇒ chỉ là
`contrast_support`, không bao giờ là occurrence. KB được: sinh/xếp hạng
mechanism candidate (W2), giải thích cơ chế nói chung, **bổ sung** reference
cho finding đã có occurrence. KB **không** thay được occurrence — đúng luật
A5 cho scope run (*trait/KB ref không thay được ref đo*).

**Contract cho một finding "liên quan verdict"** (sàn ở P1, guard ở P2) — năm
vế có tên, ghi vào `annotation.contract`:

| Vế | Bắt buộc | Điều kiện |
|---|---|---|
| `contrast_support` | có | ≥1 `contrast:*` có sức support (không phải `outcome_differs` / `component_differs` đơn lẻ) |
| `occurrence_evidence` | **có** | ≥1 ref occurrence **episode-scoped** |
| `mechanism_reference` | **không** | `kb:*` / `trait:*` — ghi nhận nếu có, không tính vào đạt/không đạt |
| `subject_match` | có | subject/candidate của occurrence khớp proposal |
| `polarity_match` | có | `EFFECT_DIRECTION[proposition_type]` khớp verdict |

**Ma trận test (pin bằng test, mỗi hàng một test):**

| Đầu vào | Kết quả |
|---|---|
| divergence + KB, không obs/checker | hạ `diagnosis`, thiếu `occurrence_evidence` |
| `component_differs` + KB | không đủ, thiếu `contrast_support` |
| `detection_only_on_loser` + obs + KB | đủ `associated` nếu polarity khớp |
| contrast + checker `supported` + KB | đủ đưa vào promotion matrix |
| contrast + obs **sai subject** + KB đúng cơ chế | không đủ, thiếu `subject_match` |
| KB rất tự tin, episode không có evidence | abstain contrast |
| contrast + trait, không obs/checker (P2.5) | hạ `diagnosis` hoặc abstain |
| contrast + obs + trait | `associated` có mechanism reference |
| contrast + checker `supported` + trait | đủ đưa vào promotion matrix |
| trait một mình | không finding episode nào |

Luật loại trừ: cùng detection hai bên mức tương đương ⇒ `ruled_out` (ghi ra);
detection chỉ ở winner với cơ chế `harms_subject` ⇒ chẩn đoán.

**5. Run context — không citable.** Mang theo từ packet run **chỉ định danh**:
`header`, `task` (robot/route), `candidates` (thành phần). **Không** lattice,
waterfall, observations n/N, measurements. `EpisodePacket` pin
`run_packet_checksum` (cùng công thức `PacketArtifact`).

**5b. `known_unknowns` — không carry nguyên (must-fix).** Guard luật 3 đọc
`blocked_claim_types` để loại proposal; một unknown đúng ở scope run chưa
chắc đúng ở episode (run thiếu aggregate evidence, nhưng episode này có
sidecar và checker `supported`). `KnownUnknown` là wire contract (`ledger.py`)
⇒ **không thêm field `scope`**; phân lớp bằng bảng platform trong
`episode_packet.py`, cùng mẫu với registry polarity:

| Lớp | Nguồn | Trong `EpisodePacket` |
|---|---|---|
| **global** | `STANDING_UNKNOWNS` (`latency_accounting_unavailable` — H4 chưa xong; `ppo_golden_runtime_missing`) và mọi id trong bảng `GLOBAL_UNKNOWN_IDS` | **carry**, có quyền block |
| **run-statistical** | unknown do `packet_builder` sinh từ dữ liệu tổng run | vào `CONTEXT (not citable)` / `omissions`, **không** block |
| **episode** | **tính lại** từ evidence thật của episode: không sidecar cho episode này ⇒ chặn claim replay-based; không route ⇒ chặn `geometric_infeasibility`; không `clearance_m` ⇒ chặn claim clearance… | sinh mới, có quyền block |

`EpisodePacket.blocked_claim_types` = global ∪ episode. Unknown không có
trong bảng phân lớp ⇒ **từ chối dựng packet** (không đoán scope).

**Test (bắt buộc):** run thiếu aggregate evidence nhưng episode có checker
`supported` ⇒ claim **không** bị chặn · episode thiếu sidecar/map ⇒ claim
tương ứng **vẫn** bị chặn · global unknown ⇒ chặn cả run lẫn episode ·
unknown lạ ⇒ từ chối.

**6. Từ chối**: hai trace khác episode; candidate không thuộc run; episode
không có trong `sample.episode_context_ids`; run trước E2.

**7. Budgeter tất định, cắt theo nhóm nguyên tử.** Đơn vị cắt = `contrast
finding + detection/window nguồn + identifier cần` (hoặc `diagnosis +
detection` cho chẩn đoán). Ưu tiên: **verdict + caveat (không bao giờ cắt) →
contrast có sức support (kèm detection nguồn) → chẩn đoán + detection →
weak contrast context (`outcome_differs`, `component_differs` — tái dựng
được từ identifier/kết cục, chẩn đoán thì không) → phân kỳ → timeline tối
thiểu → còn lại**. Không vừa ⇒ bỏ **cả nhóm**, ghi `omissions`.
**Checksum tính sau budgeting.** Ngân sách chốt **sau pilot** trên episode dài
nhất (6 fixture + 4 run thật), ghi report.

**8. Sàn `reference_episode_analyst`** — hai lớp: mọi `Detection` → chẩn đoán
qua `DETECTION_HYPOTHESES`; chỉ finding qua contract §4 mới `bearing=contrast`.
Câu không số. Abstain contrast khi không finding nào qua contract — kể cả có
detection.

`EPISODE_PACKET_SCHEMA_VERSION = "0.1.0"`; `canonical_json`.

**Test:** verdict bốn nhánh (thiếu hàng ⇒ `not_comparable`, không phải thua);
ε từ preregistration, không hằng trong module; caveat không viết lại; mỗi
`contrast_kind` một test dương + một âm; polarity sai ⇒ không contrast
(`harms_subject` trên winner); `component_differs` một mình ⇒ không qua
contract; budgeter bỏ cả nhóm và checksum đổi theo; hai trace khác episode ⇒
từ chối; sàn không số.

### P2 — Packet view, prompt, vòng chạy cho episode (2–2,5 ngày)

**0. Chốt trước mọi thứ: `bearing` sống ở đâu.** `HypothesisProposal` là
`extra="forbid"` và là wire contract run-level — **không thêm field** (bump
`EXPLANATION_SCHEMA_VERSION`, dựng lại mọi fixture — đúng thứ W4 đã tránh).
Theo tiền lệ W4 (`decision` xử ở parser + transcript):

```
EpisodeRoundResult:
  response:     AnalysisResponse                      # nguyên, run-level contract
  annotations:  map[hypothesis_id → EpisodeAnnotation]
EpisodeAnnotation:
  bearing:                   diagnosis | contrast
  contract:                  tuple[str, ...]           # vế đã qua / vế thiếu (guard ghi)
  supersedes:                hypothesis_id | None
  occurrence_evidence_refs:  tuple[str, ...]           # guard điền, theo tiền tố ref
  mechanism_reference_refs:  tuple[str, ...]           # trait:* / kb:* đã resolve
```

Hai trường ref **do guard điền**, phân loại theo tiền tố tất định (`obs:`,
checker artifact ⇒ occurrence; `trait:`, `kb:` ⇒ reference). Model không có
output field để tự khai loại — không có chỗ để khai sai. Guard từ chối
`trait:*` sai algorithm/kind/subject hoặc chưa resolve; `occurrence_evidence_refs`
rỗng ⇒ hạ `diagnosis`.

- Parser (`analyst.propose`) đọc `bearing` từ schema và trả trong
  `RoundReport.annotations` (object nội bộ service, không phải wire).
- Guard nhận **cặp** `(proposal, annotation)` trong một object; không tra
  global state.
- Revise sinh id mới ⇒ runner **chuyển annotation sang id mới**, ghi
  `supersedes` và dòng audit `supersedes:<cũ>:<mới>` W4 đã có.
- Renderer/scorer/API đọc `EpisodeRoundResult`; API episode có schema/version
  riêng (`EPISODE_ANALYSIS_SCHEMA_VERSION`). `HypothesisProposal` và
  `EXPLANATION_SCHEMA_VERSION` **không đổi**.
- **Persistence contract:** `ResponseCache` serialize **cả** `response` lẫn
  `annotations` kèm `EPISODE_ANALYSIS_SCHEMA_VERSION`; loader từ chối lệch
  version. Map chính chỉ chứa **final** id; annotation của proposal đã
  supersede chỉ nằm trong audit. `finalize` kiểm **mỗi final proposal đúng
  một annotation** — thiếu ⇒ **refuse cả vòng**, không mặc định `diagnosis`.
- **Chỉ in-process lane.** JSONL ABI hiện không có frame cho
  `EpisodeRoundResult`; `stdio_lane` **từ chối** `episode_scope=true` (có
  test) cho tới khi ABI có frame/payload riêng — ngoài phạm vi plan này.
  Wrapper "không phải wire run-level" không có nghĩa nó tự đi qua
  `final_response` hiện hữu.

1. **`packet_view.build_episode_view(...)`** — dùng chung `Fact`/`PacketView`/
   alias/knowledge; traits chỉ khi cờ `episode_traits` (P2.5). Họ fact:
   `verdict:*` · `contrast:<kind>:<n>.*` (mang `strength` và subject) ·
   `diag:<cand>.*` · `obs:<type>:<cand>@<id>[/window.*]` · `divergence:*` ·
   `attempts:<cand>.*` · `episode:<id>/<cand>/<clock>/<mark>.*` ·
   `fact:candidate:*`, `fact:robot.*`, `fact:route.*` · `unknown:*` (chỉ
   global + episode) · `kb:*` · `trait:*` (P2.5). **Run-level không có ref**:
   render thành khối `CONTEXT (not citable)` trong user turn; model cite là
   luật 1 sẵn có drop. Không cần luật mới cho run facts.
2. **`prompts.EPISODE_SYSTEM` + `build_episode_user_turn`**; `PROMPT_VERSION`
   → `a5.0.0`. Schema: `analyst_schema()` + `bearing: diagnosis | contrast`
   trước `statement`. Prompt nói rõ contract §P1.4 bằng lời.
3. **Guard** (kiểm mâu thuẫn lexical/cấu trúc, tất định):
   - luật 9 `contradicts_verdict` — gán thắng/hơn cho nhãn không phải winner ⇒ drop;
   - luật 10 `contrast_contract_unmet` — `bearing=contrast` mà thiếu bất kỳ
     vế **bắt buộc** nào (`contrast_support` / `occurrence_evidence` /
     `subject_match` / `polarity_match`; `mechanism_reference` không tính)
     ⇒ **hạ xuống `diagnosis`**, ghi `Blocked` kèm vế thiếu vào
     `annotation.contract`. `kb:*` trong `supports` **không** đếm là
     occurrence — guard phân loại ref theo tiền tố, tất định. Polarity tra
     `EFFECT_DIRECTION[proposition_type]`, không từ câu. Verdict không hướng
     ⇒ mọi `bearing=contrast` hạ nhãn với vế thiếu `verdict_has_no_direction`.
4. **`RoundFeatures.episode_scope`**, `run_context` (mặc định off; arm
   ablation) — vào checksum; scope lệch ⇒ runner từ chối.
5. **`RoundSource` giữ `RunContext` bất biến**: `EpisodePacket` +
   `PacketArtifact` của run (checksum tính lại lúc nạp) + sidecar dirs. Host
   **không đọc report từ đĩa**; `ReportEvidence` nhận report **từ artifact đã
   pin**, `EvidenceMismatch` nếu `run_packet_checksum` lệch. `evidence_for`:
   `trace`, `reference_line`, `episode_timeline`, `candidate_components`,
   sidecar tokens; **`candidate_measurements` gỡ khỏi menu ở mọi arm
   episode** — không có tool nào biến run context thành citable; không
   `comparison_pair`/`episode_decision_utility`. Arm `run_context` **chỉ**
   thêm khối `CONTEXT (not citable)` dựng từ `RunContext` đã pin;
   `run_context_checksum` vào packet/cache identity.
6. `routing._value_for("packet_episode")` → `packet.episode_context_id`;
   `packet_facts` thêm nhánh `EpisodePacket`.
7. `candidates.generate_candidates` nhận contrast finding + `Detection`
   (+ KB, + traits khi P2.5); dedupe theo `(proposition_type, subject,
   candidate_id)`; `MechanismCandidate` **không** mang polarity — đọc từ
   registry khi cần; **không** mang supporting refs episode (luật W2).

**Test:** view không ref trùng/không waterfall/contrast mang subject;
`run_context=true` ⇒ menu **vẫn không có** `get_candidate_measurements` và
ref bịa tới context bị luật 1 drop; annotation theo id mới sau revise, audit
`supersedes` có; guard đọc annotation từ object, không từ global; luật 9/10
mỗi vế một test; verdict `tie` ⇒ mọi contrast hạ nhãn; `RunContext` checksum
lệch ⇒ từ chối; scope lệch ⇒ từ chối; `stdio_lane` từ chối `episode_scope`;
cache record lệch version ⇒ từ chối; final thiếu annotation ⇒ refuse; vòng đầy đủ: contrast có sẵn
(`detection_only_on_loser` trên rrt-001) → `replay_global_plan` thật trên
sidecar → `supported` đúng bên → polarity khớp → `InvestigationRecord` đủ
điều kiện matrix.

### P2.5 — Traits đã duyệt làm mechanism reference (tuỳ chọn, 2–3 ngày, sau P4 tất định)

**Không phải dependency của P1–P4.** An chốt (§6.7): migrate 0012 + 0013
trên DB thật **sau lõi**; An duyệt **`rrtstar` và `dwa` trước** (hai thuật
toán của cả 6 fixture golden); snapshot **approved-only**, `traits_revision_id
= traits-episode-2026-08-27-r1`; **chưa pin** implementation version; draft
không hiển thị, không arm shadow trong đợt này. Bốn row còn lại (`astar`,
`ppo`, `dwa_predictive`, …) ở ngoài snapshot cho tới khi An ký.

1. **Cờ `RoundFeatures.episode_traits: bool = False`** — vào
   `runtime_config_checksum`, cache identity, audit report. Bật mà không có
   snapshot ⇒ runner từ chối (mẫu W1.7).
2. **Chỉ đọc snapshot bất biến** — bộ ba W1.8 `traits_revision_id /
   traits_snapshot_checksum / traits_snapshot_ref`; `read_snapshot` tính lại
   checksum. **Không đọc "current rows"** từ DB trong lúc chạy round. Lọc
   `review_status == "approved"` **lúc đọc snapshot**; draft không vào prompt
   user-visible, không promotion; arm shadow-only cho draft nếu cần nghiên
   cứu, ghi rõ trong report.
3. **Trait link tới KB, không đẻ bộ activation thứ hai.** Trait hiện là văn
   tự do (`strengths[]`/`weaknesses[]` chuỗi) — activation rule không chạy
   được trên nó. Migration **0013** thêm `mechanism_links: JSON`; KB entry
   **đã có** `proposition_type` + `ActivationConditions` (`knowledge.py:69`).
   Activation của trait = `knowledge.match(episode facts)` trên entry được
   link — một nguồn logic. Trait không link ⇒ chỉ là reference, **không sinh
   candidate**. Polarity vẫn từ `EFFECT_DIRECTION[proposition_type]`.

   **Hình dạng link — chống drift positional key:**

   ```json
   {"trait": "weakness:1",
    "statement_checksum": "<artifact_checksum(canonical(text))>",
    "kb": "<kb_id>", "kb_entry_version": 1}
   ```

   - Index **0-based** — đúng `enumerate` mà `knowledge_provider.py:194–208`
     và ref `trait:<alg>#weakness:<i>` đang dùng; ghi thành hằng số có test.
   - `statement_checksum` dùng **đúng** `sanitize.canonical` (NFKC) +
     `artifact_checksum` mà `traits_snapshot.py` đã dùng — không công thức
     hash thứ hai (bài học `packet_checksum` A4-i).
   - Validator: text hiện tại ở `weakness:<i>` → canonical → checksum phải
     khớp; lệch (sửa chữ **hoặc** đổi thứ tự) ⇒ link **invalid**.
   - **Drift bắt ở tầng ghi**, không chỉ ở validate: `SqlTraitRepository.save`
     thấy `strengths/weaknesses/mechanism_links` đổi trên row `approved` ⇒
     tự hạ `draft`, xoá `reviewed_by`, log lý do. Không có đường ghi nào giữ
     `approved` qua một thay đổi nội dung. Snapshot checksum đổi theo (hash
     phủ `mechanism_links`).

3b. **Review tooling — work item riêng của P2.5.** `scripts/review_algorithm_traits.py`
   hiện chỉ `list / seed / approve`; `traits_review.approve` chỉ kiểm nội
   dung có, người ký có, anchor độc lập — **không kiểm link**. Thêm:

   | Lệnh | Làm gì |
   |---|---|
   | `show <algorithm_id>` | in row, từng trait key (0-based) kèm checksum, từng link và trạng thái resolve, row checksum |
   | `validate <algorithm_id>` | mọi link: KB entry tồn tại **ở `kb_entry_version`**, không `withdrawn`, `proposition_type`/`subject` của entry hợp với `kind` của trait (`global → global_planner`, `local → local_controller`), trait key tồn tại, `statement_checksum` khớp |
   | `link <algorithm_id> <trait-key> <kb-id>` | tính và ghi `statement_checksum` + `kb_entry_version` lúc link; row về `draft` |
   | `unlink <algorithm_id> <trait-key> <kb-id>` | gỡ; row về `draft` |
   | `approve <algorithm_id> --by … --expect-row-checksum …` | **gọi `validate` trước**; từ chối nếu link không resolve · trait key không tồn tại · KB withdrawn · proposition/subject không hợp · **row checksum khác cái reviewer đã xem** · link đổi mà status còn approved |
   | `snapshot --revision-id …` | ghi snapshot bộ ba W1.8 từ row hiện tại, **từ chối** nếu còn row approved có link invalid |

   Vẫn **không có `--all`** (luật W1.6). `reviewed_by` ghi kèm row checksum
   đã ký, để `show` phân biệt "ký trên nội dung này" với "ký trên nội dung
   trước".
4. **Luật sinh candidate từ trait:** chỉ khi KB entry được link **kích hoạt**
   trên facts của episode này (ví dụ: trait "RRT* nhạy sampling budget" +
   episode có budget ghi, `no_path`, checker nói đường tồn tại ⇒ candidate
   `sampling_budget_insufficiency`; episode va chạm do controller, không
   evidence budget ⇒ không sinh). Audit: `trait_candidate_activated` /
   `trait_candidate_not_activated` + `activation_refs`.
5. **Khớp thuật toán:** chính xác `algorithm_id + kind` với thành phần của
   hai candidate đang chạy (thứ `trait_offers` A5 đang làm). Thuật toán import
   là `undescribed` (M3) ⇒ không nhận trait của family. Pin
   `implementation_ref`/version: cột tuỳ chọn, **quyết định sau** (§6).
6. **Ref:** `trait:<algorithm_id>#<strength|weakness>:<i>` mang `algorithm_id`,
   `kind`, `kb` link, `anchor`, `review_status`, subject (từ `kind`),
   `traits_revision_id`. Guard: `trait:*` chỉ vào `mechanism_reference_refs`;
   sai algorithm/kind/subject ⇒ từ chối ref.
7. **Prompt block** (hằng số, vào `prompt_checksum`, `PROMPT_VERSION` a5.1.0):

   ```
   ALGORITHM TRAITS — mechanism references, not episode evidence
   These traits describe known tendencies of the algorithms. They may help
   identify a plausible mechanism. They do not prove that the mechanism
   occurred in this episode. A contrast finding still requires episode-scoped
   occurrence evidence.
   ```

   Chỉ đưa trait của hai thuật toán đang chạy, đúng component, có KB link
   kích hoạt hoặc liên quan; **tối đa 3 trait mỗi candidate**; đo token delta.

**Test:** cờ vào checksum; bật không snapshot ⇒ từ chối; đọc current rows ⇒
răng; draft không vào prompt; trait không link ⇒ không candidate; link nhưng
KB không kích hoạt ⇒ `trait_candidate_not_activated`; trait sai algorithm ⇒
ref bị từ chối; trait một mình ⇒ không finding; ≤3 trait/candidate.
**Review tooling:** đổi thứ tự `weaknesses[]` ⇒ link invalid, row về draft;
sửa một chữ ⇒ checksum đổi (NFKC: đổi dạng Unicode tương đương **không**
đổi); `approve` với `--expect-row-checksum` cũ ⇒ từ chối; KB entry withdrawn
⇒ từ chối; entry `global` link vào trait `local` ⇒ từ chối; `save` giữ
approved qua sửa nội dung ⇒ răng; `snapshot` có link invalid ⇒ từ chối;
index 0-based pin bằng test đọc `knowledge_provider`.

### P3 — API (1,5 ngày)

| Route | Trả gì |
|---|---|
| `GET …/episodes/{episode_context_id}/verdict?candidate_a&candidate_b` | `EpisodeVerdict` + `EpisodeDiagnosis` ×2 + `EpisodeContrast` (kèm `strength`, `ruled_out`) + sàn + `packet_checksum` + `omissions`. Tất định, luôn có. |
| `POST …/episodes/{episode_context_id}/analysis` `{candidate_a, candidate_b, at_time?, at_progress?}` | trên cộng `model`, `audit`, `rendered[]` — theo mode |

**`EPISODE_ANALYST_MODE`**, mặc định `off`:

| Mode | Hành vi | Điều kiện mở |
|---|---|---|
| `off` | 404 | — |
| `shadow` | chạy, ghi artifact `artifacts/analyst-episode/<run>/<episode>/<checksum>.json`; response **không** mang `model`/`rendered` | An bật |
| `internal_preview` | trả đủ, **chỉ tài khoản admin**; UI gắn nhãn "preview nội bộ" | sau P5: report exploratory + `evaluation_report_ref` trong settings |
| `production` | trả đủ cho mọi người dùng | **`EpisodeGateDecision`** máy kiểm — **không mở trong plan này** |

**`EpisodeGateDecision` — chỉ là spec, không phải mở rộng `GateDecision`
đang chạy** (đổi `GateDecision` là bump contract run-level). Type riêng,
định nghĩa ở P3 dưới dạng model + `verify_episode_gate_decision()` từ chối
mọi thứ (chưa có ai cấp): pin `bundle_identity`, `runtime_config_checksum`,
`prompt_version`, `eval_spec_checksum`, `model_identity`,
`cluster_set_version`, hard constraints + primary endpoint + threshold,
`cost_ceiling`, `expires_at` / `revoked`. **Settings luôn từ chối
`production`** trong plan này; test pin điều đó.

**Scope bắt buộc (bất biến 4):** cả hai route có `episode_context_id` trên
path — không có đường nào tới engine mà thiếu nó. Mọi response mang
`episode_context_id`, `candidate_a/b`, `packet_checksum` để client đối chiếu
với selection lúc render. Dock: `ChatContext.episode_context_id: str | None`;
`_resolve_context` tra episode ∈ `sample.episode_context_ids` của run; tool
`get_episode_verdict` thiếu id ⇒ trả **structured refusal
`episode_not_selected`** (mã đóng, hiện nguyên văn), không chạm
`episode_packet`, không gọi provider analyst, **không** chạy analyst run-level
thay thế.

Ops trên route model: auth như route ghi; cost cap/ngày (số call + token);
timeout = per-call A2 + `max_wall_time_ms`; **in-flight dedup** theo
`(packet_checksum, runtime_config_checksum)`; playhead khác ⇒ packet khác ⇒
cost cap chặn. 409/422 như exemplars/replay-sync. Không chạm `analyst_visible`
của card.

**Test:** verdict trên run thật; `not_comparable` khi thiếu hàng; `off` ⇒ 404;
`shadow` ⇒ artifact có, response không `model`; `internal_preview` không admin
⇒ 403; `production` ⇒ settings **luôn** từ chối; `verify_episode_gate_decision` từ
chối decision thiếu pin/hết hạn; cost cap; dedup một model call; response chỉ
mang nhãn; response mang `EPISODE_ANALYSIS_SCHEMA_VERSION` riêng; **dock hỏi
episode khi chưa chọn ⇒ refusal `episode_not_selected`, 0 call provider
analyst, 0 lần dựng packet** (đếm bằng spy); **không fallback**: chat không
gọi bất kỳ hàm nào của analyst run-level (assert trên registry tool).

### P4 — UI (1–1,5 ngày)

Panel ba khối đúng §0; contrast hiện `contrast_kind` bằng chữ thường và
**sức mạnh** ("bối cảnh" / "thu hẹp" / "liên quan"); `ruled_out` hiện dưới
dạng "đã loại: cả hai bên đều …"; verdict `not_comparable` hiện câu §P1.1.
Nút "Hỏi AI" chỉ khi mode ≥ `internal_preview` **và** user là admin **và có
episode được người dùng chọn**; output LLM trong cùng ba khối, nhãn "AI đề
xuất · preview nội bộ". Không có câu "AI giải thích vì sao C1 thắng".

**Lifecycle chọn episode (bất biến 4):**

- `TracePanel` giữ `episodeId` mặc định `episodes[0]` cho **replay** — hành
  vi có sẵn, không đổi. Thêm `selectionOrigin: "default" | "user"`; chỉ
  `chooseEpisode` (bảng, chip exemplar, pager) đặt `user`. **Phía AI chỉ coi
  là "đang trỏ vào" khi `user`** — không tự lấy episode đầu tiên.
- `lib/episodeVerdict.ts`: `selectedEpisode(state) → string | null`; panel AI
  và dock cùng đọc hàm này. `null` ⇒ panel hiện *"Chọn một episode để phân
  tích"*, không nút, không request; dock gửi `episode_context_id: null`.
- **Race:** mỗi request giữ `AbortController` + `requestedFor =
  {episode_context_id, candidate_a, candidate_b}`; đổi hoặc bỏ chọn ⇒ abort;
  render chỉ khi `response.episode_context_id === selectedEpisode()` **tại
  lúc render**, không phải lúc gửi. Response stale ⇒ drop im lặng, không
  hiện ở episode khác.

**Hai loại citation, tách trên UI** (P2.5): *"Bằng chứng trong episode"*
(`obs:*`, checker) và *"Đặc tính thuật toán"* (`trait:*`, `kb:*`). Ví dụ:
*Bằng chứng: RRT\* hết budget mà chưa tìm được đường* · *Đặc tính: sampling
search nhạy với budget trong không gian này.* **Không render** *"RRT\* thua vì
nó có weakness X"* khi không có occurrence — renderer đọc
`occurrence_evidence_refs` rỗng thì đổi khuôn câu sang chẩn đoán.

AgentDock: chip khai *"đang hỏi về episode X"* khi có, *"chưa chọn episode"*
khi không; refusal `episode_not_selected` hiện nguyên văn. i18n en + vi.

**Test:** lib thuần + `renderToStaticMarkup`; nút không render khi mode/role
sai **hoặc không có episode `user`**; `selectedEpisode` trả `null` khi origin
`default` (không tự chọn episode đầu); đổi A → B khi A đang chạy ⇒ response A
**không** render ở B (abort gọi đúng một lần); bỏ chọn khi đang chạy ⇒ không
render; không request nào gửi khi `null`; diagnosis không dưới tiêu đề
contrast; `not_comparable` không hiện winner.

### P5 — Đánh giá theo episode (2 ngày, exploratory, cluster-aware)

**Model và ngân sách (An chốt §6.6):** `o4-mini`; **funnel hai giai đoạn**
— giai đoạn 1: mọi arm × 1 repeat trên development set, đọc `failure_table`
và chi phí; giai đoạn 2: chỉ arm sống sót (không vi phạm hard constraint,
không tệ hơn sàn về guard drop) × 3 repeat. **Trần 2–3 USD tổng** — runner
đếm token theo usage provider và **dừng** khi chạm trần, ghi arm nào chưa
chạy vào report; không nới. Model local (`qwen3:8b`, `llama3.2`) **chỉ
smoke** (1 case, 1 repeat, chứng minh pipeline chạy), không vào bảng số.

1. Nhãn từ **spec world + kiểm tất định độc lập**, `cluster_id`; negative
   episode bắt buộc (ba loại); `expected_polarity` theo cơ chế trồng.
2. Ba phép đo tách: detector recall · selector accuracy | detection đúng
   (đúng cơ chế **và** đúng `bearing`) · end-to-end.
3. Cluster-aware: CI/cross-fit theo cluster; báo `n_episodes` + `n_clusters`;
   `pass^3` theo episode chỉ mô tả.
4. Preregistration bản 2 (chứa ε, hard constraints `verdict_contradictions
   = 0`, `contrast_contract_unmet = 0` ở final, primary = contrast
   correctness cluster-level, `min_cases` đếm cluster).
5. Arm: `ep_b1` · `ep_shortlist` · `ep_knowledge` · `ep_shortlist_knowledge`
   · `ep_playhead` · `ep_run_context` (khối context không citable, **không
   tool**). `ep_knowledge` / `ep_shortlist_knowledge` đo gain ở **sinh và xếp
   hạng candidate**, không đo KB làm bằng chứng — contract không cho `kb:*`
   qua vế `occurrence_evidence`. **Arm traits (chỉ khi P2.5 và An đã ký
   subset):** `ep_shortlist` vs `ep_shortlist_traits`, mọi cờ khác giống nhau
   — phép đo chính về giá trị traits; 2×2 với knowledge chỉ khi ngân sách
   cho phép. Metric thêm: trait activation precision · trait citation
   correctness · occurrence grounding rate · trait-only hallucination rate ·
   guard downgrade vì thiếu occurrence · token delta. Hard constraints:
   `trait_only_contrast = 0` · `unapproved_trait_visible = 0` ·
   `trait_algorithm_mismatch = 0`. Nhãn episode thêm `expected_trait_activation`
   (từ spec world, không từ output). Sàn episode là đối chứng. Scorer chấm
   `bearing` từ `EpisodeRoundResult.annotations`.
6. Packet thật: 12 episode / 4 run = **4 cluster**, rubric r0.1.0 mù, thêm
   cột `bearing`.
7. Kết luận exploratory; đủ mở `internal_preview`, **không** đủ `production`.

**Golden cho traits — hai lớp (P2.5):**

| Lấy được từ fixture **hiện có** — làm trong P5 | Cần world mới — **P5.5 tuỳ chọn** (+1,5 ngày) |
|---|---|
| Hai stack cùng DWA ⇒ trait controller chung **không** giải thích contrast (`component_differs` fail) | Environment là nguyên nhân chính, trait không liên quan |
| Trait RRT\* trên episode astar+dwa va chạm ⇒ **không kích hoạt** | Implementation/version không khớp family |
| Trait + checker cùng chỉ một cơ chế (rrt-001) | Run-level tendency ngược episode outcome (anchoring) |
| Trait đúng và activation có mặt (rrt-001, inflation-001) | |

Không trộn hai lớp trong một bảng số; P5.5 không chạy thì report nói ba loại
đó **chưa đo**.

### P6 — Răng, full suite, report (0,5–1 ngày)

Răng mới: `trait:*` đếm là occurrence · trait draft vào prompt · trait không
link KB vẫn sinh candidate · round đọc current rows thay vì snapshot · trait
sai algorithm được cite · `approve` bỏ qua `validate` · link không pin
`statement_checksum` · `save` giữ approved qua sửa nội dung · hash statement
bằng công thức khác snapshot · index đổi sang 1-based một phía · thiếu episode mà provider analyst vẫn bị gọi · thiếu episode
fallback sang analyst run-level · panel AI đọc `episodes[0]` thay vì
`selectedEpisode` · render không đối chiếu `episode_context_id` · `kb:*` đếm
là occurrence · `divergence` đếm là occurrence ·
unknown run-level carry nguyên vào `blocked_claim_types` · unknown
lạ được đoán scope · budgeter giữ weak context bỏ diagnosis · cache đọc
record thiếu annotation thành `diagnosis` · `stdio_lane` nhận `episode_scope`
· tắt luật 9/10 · polarity bỏ qua · polarity đọc từ KB/candidate
thay vì registry · `component_differs` một mình qua contract · verdict `tie`
mà contrast có hướng vẫn sinh · thiếu hàng thành `outcome_only` · hai failure
được xếp hạng · ε hằng trong module · budgeter cắt nguồn giữ kết luận ·
checksum trước budgeting · host đọc report từ đĩa · run fact có ref ·
`run_context` mở lại tool · annotation không theo id mới sau revise ·
`bearing` lọt vào `HypothesisProposal` · `shadow` trả `model` · `production`
được settings nhận · dedup tắt · CI đếm episode. Chạy lại 60 răng cũ. **Full
suite + ruff + tsc** lần hai. Report phủ P0–P6.

## 3. Thứ tự

```
P0 (full suite + merge) → P1 → P3 verdict → P4 panel tất định     ← ship
                          ↓
                        P2 → P3 analysis (shadow) → P5 → An bật internal_preview → P4 nút AI
                          ↓ (tuỳ chọn, sau khi An ký traits)          production: ngoài plan
                        P2.5 traits → P5 arm ep_shortlist_traits → (P5.5 world mới)
```

## 4. Ước lượng

P0 1 · P1 2,5–3 · P2 2–2,5 · P3 1,5 · P4 1–1,5 · P5 2 · P6 0,5–1 =
**10,5–12,5 ngày** lõi. Tuỳ chọn: P2.5 2–3 (gồm review tooling) + P5
arm/nhãn traits 0,5–1 + P5.5 world mới 1,5 ⇒ **+4–5,5 ngày** nếu An duyệt cả ba.

## 5. Rủi ro

| Rủi ro | Giảm nhẹ |
|---|---|
| Contrast yếu (`component_differs`) đội nhãn liên quan verdict | contract 4 vế; `strength` trên finding; luật 10 hạ nhãn kèm vế thiếu |
| Polarity do model tự khai, hoặc hai nguồn bất đồng | một bảng `EFFECT_DIRECTION` trong `propositions.py`; KB/candidate/trait không có trường polarity; không có trong bảng ⇒ `ambiguous` |
| `bearing` lọt vào wire contract run-level | wrapper `EpisodeRoundResult`, `HypothesisProposal` không đổi; răng |
| Contrast sinh sau tool mà guard không resolve được | checker không phải contrast; đi đường `InvestigationRecord` sẵn có |
| Verdict không hướng mà vẫn có "bên thua" | `verdict_has_no_direction`; sàn và model không chọn loser |
| Không chọn episode mà AI vẫn chạy / trả lời về run | scope bắt buộc trên path; refusal `episode_not_selected`; `selectionOrigin=user`; không fallback; răng |
| Response episode A hiện ở episode B | response mang id; đối chiếu lúc render; abort khi đổi/bỏ chọn |
| KB thay thế bằng chứng đã xảy ra | `occurrence_evidence` bắt buộc, `mechanism_reference` tuỳ chọn; guard phân loại theo tiền tố ref; răng |
| Unknown của run chặn nhầm claim episode hợp lệ | ba lớp unknown; `blocked_claim_types` tính lại; unknown lạ ⇒ từ chối dựng |
| Annotation mất khi cache/lane | persistence contract; thiếu ⇒ refuse; container lane từ chối scope episode |
| Traits draft thành folklore trong contrast | reference-only; chỉ approved từ snapshot; không polarity ⇒ không qua contract; `trait_only_contrast = 0` |
| Reviewer ký row rồi nội dung/link đổi sau lưng | `--expect-row-checksum`; `save` tự hạ draft; `reviewed_by` kèm checksum đã ký |
| Positional key trỏ sang câu khác sau reorder | `statement_checksum` (cùng `canonical` + `artifact_checksum`); 0-based pin test |
| `approve` không biết link là gì | `approve` gọi `validate`; `snapshot` từ chối link invalid |
| Hai bộ activation (KB và trait) trôi khỏi nhau | trait **link** KB entry, activation = `knowledge.match` — một nguồn |
| Trait family áp lên implementation tuỳ biến | khớp chính xác `algorithm_id + kind`; import là `undescribed` |
| Thiếu hàng đọc thành thua | `not_comparable` riêng, UI câu riêng |
| ε chọn sau khi nhìn số | preregister trước P1 chạy dữ liệu thật; checksum pin |
| Budgeter giữ kết luận mất bằng chứng | nhóm nguyên tử; checksum sau budgeting; răng |
| Host đọc report drift khỏi packet | `RunContext` pin checksum; `EvidenceMismatch` |
| Run fact đỡ claim episode | không có ref ⇒ luật 1; menu rút `candidate_measurements` |
| Bật `on` chỉ bằng đường dẫn report | bốn mode; `production` đòi `GateDecision` mở rộng, máy kiểm, có hạn |
| CI quá tự tin vì mẫu cụm | cluster-aware; báo `n_clusters` |
| Merge nhánh lớn chưa full suite | P0 full suite + waiver có tên |
| LLM không thắng sàn | 4 kết luận; panel tất định ship độc lập |

## 6. Quyết định của An — 2026-08-27, đã chốt

| # | Quyết định | Áp vào |
|---|---|---|
| 1 | **Merge nhánh analyst vào `main` sau khi P0 đạt**; failure ngoài waiver ⇒ **dừng**, không merge | P0.3 |
| 2 | **Scope mặc định = episode do user chọn**; playhead **optional**, giá trị đo bằng arm `ep_playhead` | §0 bất biến 4, P1.3, P4 |
| 3 | **Bốn mode** `off / shadow / internal_preview / production`; plan **dừng ở `internal_preview`**; `production` **luôn bị từ chối**; `EpisodeGateDecision` chỉ là spec | P3 |
| 4 | **Polarity ở `propositions.py`**, có `MECHANISM_POLARITY_VERSION`; thiếu mapping ⇒ `ambiguous` | P1.4, P2.3 |
| 5 | **ε = 0.005**, chốt trước dữ liệu thật; chỉ đổi nếu utility quantization buộc, và đổi trước khi chạy, có khai | P1.1 |
| 6 | **P5: `o4-mini`, funnel hai giai đoạn, trần 2–3 USD**; local chỉ smoke | P5 |
| 7 | **P2.5 optional**: migrate 0012 + 0013 **sau lõi P1–P4**; An duyệt **`rrtstar` và `dwa` trước**; snapshot **approved-only** `traits_revision_id = traits-episode-2026-08-27-r1`; **chưa pin** implementation version; draft không hiển thị | P0.4, P2.5, P5 arm traits |

**Trạng thái:** đã duyệt. **Chưa thi hành** — chờ lệnh An trước P0.

## 7. Ngoài phạm vi

`production` mode và `EpisodeGateDecision` được cấp · pin version thuật toán
vào trait · P5.5 world mới cho traits (nếu không được duyệt) · JSONL ABI cho `EpisodeRoundResult` · waterfall theo episode
· đọc movement từng tick · sandbox/container (Đường B) · hidden gate của card
· so nhiều episode · biến thể thứ hai của 6 họ golden.

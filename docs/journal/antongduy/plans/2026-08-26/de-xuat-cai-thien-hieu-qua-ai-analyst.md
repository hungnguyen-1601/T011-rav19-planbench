# Đề xuất công việc tiếp theo — cải thiện hiệu quả AI Analyst

**Ngày:** 2026-08-26  
**Trạng thái:** **bản 6**, đề xuất để rà soát và chốt thứ tự thi hành  
**Bản 6 — sau vòng rà thứ tư của An (2 điểm lớn):** (1) **tách dữ liệu
development khỏi confirmatory** — cùng planted set đang dùng để chọn input,
kiến trúc, model, router (E1–E10) rồi kết luận superior/non-inferior trên
chính nó; preregister từng phép kiểm không chữa được selection bias khi nhiều
phép thử chọn cấu hình rồi báo trên cùng dữ liệu. Bản 6 nối vào bộ máy sẵn có
của platform: calibration set (`VISIBLE_SUITE`) = development; **official gate
trên hidden suite `preregistered`** = confirmatory — bundle đóng băng, protocol
cố định, không retry cả case, holdout không dùng để chọn prompt/threshold/
model/router. Khi `OFFICIAL_GOLDEN_READY=False`, **mọi kết quả E1–E10 là
exploratory và không phải deployment proof**; W0–W4 vẫn bắt đầu được;
(2) **E10 không train và test router trên cùng dữ liệu** — router thiết kế
trên E8-dev, freeze rule + `router_rule_checksum` vào identity, đánh giá trên
case chưa dùng để thiết kế; dữ liệu ít thì cross-fitting theo case/family;
thêm arm **always-strong**; "oracle best" định nghĩa bằng **utility function
preregistered**, không chọn hậu nghiệm giữa quality và cost.  
**Bản 5 — sau vòng rà thứ ba của An (3 điểm cao + 2 điểm trung bình):**
(1) snapshot traits phải **tái dựng được**, không chỉ hash — bundle mang bộ ba
`traits_revision_id` / `traits_snapshot_checksum` / `traits_snapshot_ref`,
snapshot là artifact immutable content-addressed giữ ít nhất bằng vòng đời
bundle, hash **toàn bộ** catalog revision với canonical sort + canonical
JSON/Unicode (dùng lại `canonical_json` / `artifact_checksum` / NFKC sẵn có),
pointer hiện tại đổi được còn revision đã tham chiếu thì immutable, gate kiểm
**cả** ref tồn tại lẫn checksum khớp; `eval_spec_checksum` hash canonical
content của expected findings chứ không chỉ version; (2) tách **non-inferior**
(không kém quá δ) khỏi **equivalent** (toàn bộ CI trong [−δ, +δ]) — bốn kết
luận riêng; preregister hard constraints, **primary endpoint** (case-level
mechanism correctness), δ + hướng kiểm định, secondary metrics, quy tắc
multiplicity/hierarchical testing; (3) thêm **E10** đánh giá router: floor-only
vs always-default vs oracle-router vs cascade, đo router recall, false
non-escalation, regret, gain của bậc escalate thứ hai — không deploy cascade
chỉ dựa Pareto giữa các model; (4) chi phí theo nhánh có post-treatment bias —
phân lớp **trước khi chạy** bằng `expected_check_required` trong fixture spec,
báo intent-to-treat + subgroup theo lớp fixture, nhánh model tự chọn chỉ mang
tính chẩn đoán; (5) E3c chạy **đủ 2×2** M3×A5 vô điều kiện (hoặc tuyên bố
interaction ngoài phạm vi), không quyết định chạy dựa trên hình dạng main
effect.  
**Bản 4:** traits/KB vào danh tính; trust boundary cho eval mode; E4 tách
E4a/E4b; exit gate ba kết luận; arm vector đầy đủ; `menu_recall`; guard
contract cho draft.  
**Bản 3:** discriminated union; distractor rút khỏi production; E3/E5 tách
biến; B0/B1; smoke ở W1; refs any-of; bypass cache; CI cho `pass^3`; traits
khoá trước golden; chi phí tách lớp.  
**Bản 2:** W1.0 `ToolHost` thật; chống vòng tự chấm; bỏ `supporting_refs`; flag
từng đầu vào; một call schema; repair ≠ retry A7; contract impact W3; W0 nhận
fixture completeness.  
**Phạm vi:** chất lượng suy luận của Lane 2 — AI Analyst giải thích "vì sao A thắng B"  
**Nguồn đối chiếu:** kết quả chạy thật `o4-mini`, `qwen3:8b`, `llama3.2:3b`; kế hoạch AI Analyst bản 8–9; báo cáo thi hành ngày 2026-08-26.

---

## 1. Mục tiêu

Mục tiêu của đợt tiếp theo không phải là đổi model ngay, mà là xác định và sửa đúng tầng đang giới hạn chất lượng:

1. Dữ liệu cần thiết có thực sự tới được model hay chưa.
2. Model có được cung cấp không gian cơ chế hợp lý hay đang phải đoán từ trang trắng.
3. Model có đang tiêu quá nhiều năng lực cho việc chọn tool và tuân thủ hợp đồng hay không.
4. Chất lượng thấp đến từ model, prompt, routing, dữ liệu hay từ chính phép đo.
5. Sau khi các tầng trên ổn định, model nào — và **cách route nào** — đạt tỷ lệ chất lượng/chi phí tốt nhất.

Đầu ra mong muốn là một pipeline cho giải thích **cụ thể, có bằng chứng, ổn định qua nhiều lần chạy**, đồng thời không phá các bất biến hiện có: LLM không phải nguồn của con số, không tự promotion claim, tool menu đóng và mọi citation phải được platform kiểm tra.

**Và một luật về dữ liệu, đứng trên mọi thực nghiệm** (bản 6): plan này có hai
loại kết quả — *exploratory* (chọn cấu hình, chạy trên development set) và
*confirmatory* (kết luận và deploy, chạy một lần trên holdout đã khoá). Không
kết quả nào của loại thứ nhất được đọc thành loại thứ hai.

---

## 2. Bằng chứng hiện có và chẩn đoán ban đầu

### 2.1. Kết quả chạy thật

| Model | Crash | Abstain | Proposal qua guard | Tool call | Nhận xét |
|---|---:|---:|---:|---:|---|
| `o4-mini`, 1 repeat | 0/3 | 1/3 | 2 | 2 | Model duy nhất tạo được proposal sống sót và gọi tool thật |
| `o4-mini`, 3 repeats | 0/3 | 1/3 | 2 | 3 | Có lúc tìm đúng cơ chế nhưng không ổn định giữa các lượt |
| `qwen3:8b` | 0/3 | 3/3 | 0 | 0 | Chọn im lặng trên cả ba case |
| `llama3.2:3b` | 0/3 | 3/3 | 0 | 0 | Có sinh proposal nhưng guard loại hết |
| Sàn model-free | — | 1/3 | 3 | — | Cụ thể hơn o4-mini trên một số case nhờ mapping detection → cơ chế |

Chi phí quan sát của `o4-mini` vào khoảng **5.400 input token + 2.600–3.100 output token và 23 giây mỗi case**. Phần output JSON chỉ chiếm một phần nhỏ; phần lớn token ra là reasoning token.

**Các con số trên là B0-historical** (bản 3): đo trên pipeline mà mechanism
check trả `not_checkable` (§2.4). Giữ giá trị **chẩn đoán**, không dùng làm
baseline sau W1.0.

### 2.2. Các lỗi quan sát được không chỉ là "model yếu"

Guard và runner đã bắt đúng nhiều failure mode trên output thật:

- Citation tồn tại nhưng nói về subject khác với claim.
- Model dùng ngôn ngữ nhân quả vượt quá tầng `associated`.
- Tool request thiếu argument bắt buộc.
- Claim type đã bị packet chặn.
- Citation bị bịa.
- Model gọi lại cùng checker với cùng argument (`no_progress`).
- Model xin tool mà run không có `available_evidence` để phục vụ.

Các lỗi này cho thấy pipeline an toàn đang hoạt động, nhưng đồng thời cho thấy model đang phải tự giải quá nhiều bài toán trong một lượt.

### 2.3. Chất lượng nội dung chưa vượt sàn tất định

Trên các fixture đã chạy, o4-mini thường dừng ở câu chung như "khác biệt đến từ global planner", trong khi sàn model-free gọi được cơ chế như `sampling budget insufficiency` hoặc `local minimum entrapment`. O4-mini từng tìm đúng `inflated footprint → narrow passage infeasible` và chọn đúng `gap_vs_footprint`, nhưng không ổn định giữa các lượt.

**Chẩn đoán:** sàn có một prior miền bài toán dưới dạng mapping detection → cơ chế. Bắt model tự sinh cơ chế từ đầu đang làm mất lợi thế tri thức sẵn có.

### 2.4. Input trên hợp đồng chưa đồng nghĩa với input trong runtime

- **`InProcessHost` đang bọc `MockToolHost`, không phải `ToolHost` thật** (bản 2): mọi mechanism check trả `not_checkable / checker_not_implemented`; bốn checker thật trong `host.py` chưa bao giờ nằm trong vòng chạy.
- `get_candidate_measurements`, `get_episode_timeline` chưa có handler trong `ToolHost`.
- `apps/api` chưa truyền timeline vào packet.
- Reader `AlgorithmTraitRow → TraitSource` chưa nối — và khi nối, nội dung traits thành đầu vào mutable từ DB, phải đóng băng **tái dựng được** vào danh tính (bản 4/5, W1.8).
- Runner chưa tự gọi knowledge retrieval.
- Các trait vẫn `draft`.
- Một số golden fixture thiếu clearance/planner latency; `inflation-001` không có observation.

**Chẩn đoán:** model chưa nhận đủ ba loại đầu vào bản 9 thiết kế, và chưa từng nhận một verdict thật từ checker để tổng hợp.

### 2.5. Phép đo hiện chưa đủ lực để chọn model

- 3/12 case load được, 3/6 họ.
- Chưa có `expected_findings` tương thích `score_case`.
- Hai case bất đồng — `underpowered=True`.
- `pass^k` chỉ phản ánh không crash.
- Packet thật không có ground truth.

---

## 3. Hướng thiết kế đề xuất

### 3.1. Hybrid: deterministic candidate generator → LLM verifier/synthesizer

Dùng mapping của sàn, traits đã duyệt và knowledge provider để sinh shortlist có cấu trúc:

```json
{
  "mechanism_id": "local_minimum_entrapment",
  "subject": "local_controller",
  "triggered_by": ["stuck_cluster", "replan_storm"],
  "verification_options": [
    {"tool_id": "get_event_neighborhood",
     "required_arguments": ["candidate_id", "event_index"]}
  ]
}
```

**Candidate KHÔNG mang `supporting_refs` gắn sẵn** (bản 2): model tự chọn refs từ fact index, guard chấm việc chọn đó.

**`verification_options` là biến riêng** (bản 4): shortlist cho prior về *cơ chế*, `verification_options` cho gợi ý *cách kiểm chứng* — đo tách ở E4a/E4b.

**Distractor là chế độ EVAL** (bản 3) với **trust boundary fail-closed** (bản 4):

- Production: shortlist gồm đúng candidate mà generator/traits/retrieval đề xuất, cộng `unknown`.
- Eval (`eval_distractor_mode`): harness inject distractor hoặc bỏ gold theo seed/tỷ lệ cố định. `expected_findings` chỉ tồn tại **phía scorer** — không mount vào container, không vào packet/transcript/prompt; mode **cấm** ở production và official gate; trên hidden set chỉ tính là selector diagnostic; `generator_recall@K` chấm trên output generator **trước** khi harness can thiệp.
- **`eval_spec_checksum`** (bản 4, siết bản 5) = `artifact_checksum` của **canonical content** expected findings (không phải version string) ‖ distractor seed/rate ‖ scoring semantics. Version string đổi không kéo nội dung, và nội dung đổi không kéo version — chỉ hash nội dung mới chốt được cả hai.

LLM tập trung: chọn/xếp hạng cơ chế; chọn bằng chứng hoặc yêu cầu check; tổng hợp sau **verdict thật**. Sàn chỉ sinh candidate; promotion matrix, checker và guard giữ quyền quyết định.

### 3.2. Tool menu capability-aware theo từng round

Effective menu dựng từ `available_evidence`, detection/measurement hiện có, component/mechanism đang xét, proposition type, tool đã gọi. Hai flag độc lập (bản 3): `filter_tool_menu` và `auto_route_checker`. Ràng buộc (bản 4): `menu_recall` đo trước khi filter bật ở bất kỳ E nào; mechanism `unknown` ⟶ fallback evidence-capable menu; auto-route chỉ **sau declare + admission**.

### 3.3. Output có cấu trúc: discriminated union

```text
NoCheckDecision: component → mechanism_id → evidence_refs
                 → requested_check = null → final_statement
CheckPlan:       component → mechanism_id → evidence_refs
                 → requested_check → draft_statement   # không final
```

`draft_statement` tồn tại chỉ vì bất biến declare-trước-request; sau verdict revise ⟶ content hash mới ⟶ ID mới kèm `supersedes`; chỉ final được render/chấm.

**Guard contract của draft** (bản 4): qua đủ luật 1–7; wording `associated`; không chứa kết quả checker chưa chạy; không promotion/chấm/render; refuted ⟶ withdraw hoặc supersede **có audit link** (viết-lại-cùng-ID đã bất khả thi theo protocol — luật ở đây là phần audit).

Mặc định một call mỗi lượt (thuế reasoning theo call). Repair tối đa một lần cho lỗi `repairable=true`, tính vào `max_model_calls`; **không phải** retry theo nghĩa A7 (bản 2).

### 3.4. Cascade theo độ khó — và router là một thứ phải đo

```text
Deterministic floor
  ├── một cơ chế rõ + đủ evidence → render trực tiếp
  └── nhiều cơ chế/cần tool → model mặc định
                              └── vẫn mơ hồ hoặc bất ổn → model mạnh hơn
```

Cascade **rẻ được vì gửi case đi đâu**, và một router gửi quá nhiều case cho floor vừa rẻ vừa bỏ lỡ đúng những case LLM tạo giá trị. Quyết định route là một thành phần có lỗi riêng, đo riêng ở E10 (bản 5) — không suy ra từ Pareto giữa các model.

---

## 4. Các workstream đề xuất

### W0 — Hoàn thiện nền đánh giá trước khi tối ưu

1. `expected_findings` cho golden fixture ở mức cấu trúc: expected mechanism; expected component; supporting refs **any-of/predicate** (bản 3); tool call chấp nhận được; causal wording bị cấm; expected abstention; **`expected_check_required: true/false`** (bản 5 — lớp case chốt trước khi chạy, dùng cho chi phí W4.7 và E6). Labels sống **phía scorer** (bản 4).
2. Hai tập: planted/golden đo correctness; packet thật chấm tay theo **rubric cố định, chấm mù cấu hình** (bản 2).
3. Fixture completeness (bản 2): clearance/planner-latency cho họ cần; quyết định tường minh cho `inflation-001`.
4. Bổ sung fixture stage được; macro ghi `3/6 họ`.
5. 3–5 repeats, **bypass cache**, harness assert `cache hits = 0` (bản 3).
6. `pass^k` = đạt điều kiện chất lượng **chốt trước**, đủ ngưỡng case, **kèm CI** (bản 2/3).
7. `eval_spec_checksum` hash **canonical content** (§3.1, bản 5).
8. **Preregister thống kê** (bản 5): hard constraints (structural violations = 0; budget/protocol pass); **primary endpoint** = case-level mechanism correctness; margin δ và hướng kiểm định; secondary metrics (component attribution, abstention, evidence, cost); quy tắc multiplicity/hierarchical testing. Tất cả chốt **trước B1**.
9. **Phân vùng dữ liệu** (bản 6 — điểm chặn kết luận, không chặn W0–W4):
   - **Development/calibration set** — `VISIBLE_SUITE` và mọi fixture đội AI
     nhìn thấy: dùng cho E1–E10, sửa prompt, chọn feature/model/router.
   - **Locked confirmatory set** — hidden suite `preregistered`, mở qua
     official gate: **không** dùng để chọn prompt, threshold, model hay
     router; chỉ chạy **sau khi** đã freeze `bundle_identity` +
     `runtime_config_checksum` + `eval_spec_checksum` + `router_rule_checksum`;
     protocol cố định (3 lượt, lấy tệ nhất, **không retry cả case**) — đúng
     luật A7 đã có.
   - Bộ máy này **đã tồn tại** trong platform: `run_gate` fail-closed đòi
     hidden + preregistered + packet `recorded`; `DryGateRun` không mang
     decision nên rehearsal không bật được feature. Plan chỉ việc không đi
     vòng qua nó.
   - **Khi chưa tách được holdout** (`OFFICIAL_GOLDEN_READY=False`, 3/6 họ):
     mọi kết quả E1–E10 ghi nhãn **exploratory**, không đủ cho deployment.
     Đây là trạng thái hiện tại.
   - Case đã xuất hiện trong bất kỳ lượt phát triển nào **không được** tái sử
     dụng trong confirmatory set — kể cả dưới tên khác.

**DoD:** mechanism match tính được trên planted; report phân biệt planted/real; `underpowered` khi thiếu case; rubric trong repo; labels không ở artifact phía analyst; file preregistration có trước khi chạy B1.

### W1 — Đóng các đường nối dữ liệu **và đường kiểm chứng**

0. **`ToolHost` thật vào `InProcessHost`** (bản 2), giữ bất biến `RoundSource` (bản 3): `available_evidence` và host từ cùng `PacketArtifact`/provenance, cùng `evidence_identity_checksum`. Unit test được dùng mock; đường đo và production thì không.
1. Handler `get_candidate_measurements`.
2. Handler `get_episode_timeline`.
3. Timeline từ runtime/API vào packet; đo byte/token.
4. Reader `AlgorithmTraitRow → TraitSource`.
5. Knowledge retrieval vào runner, opt-in.
6. Duyệt traits tối thiểu — anchor độc lập, **khoá trước golden** (bản 3).
7. Feature flag từng đầu vào + `filter_tool_menu` + `auto_route_checker`, vào `runtime_config_checksum` (bản 2/3).
8. **Snapshot traits tái dựng được** (bản 4, viết lại bản 5 — hash đơn lẻ
   không đủ: nếu revision cũ bị xoá hoặc DB chỉ giữ trạng thái hiện tại thì
   bundle có checksum mà không còn thứ để replay/calibrate lại):
   - Bundle mang bộ ba **`traits_revision_id`**, **`traits_snapshot_checksum`**,
     **`traits_snapshot_ref`**; cả ba vào `runtime_config_checksum` và bundle
     identity.
   - Snapshot là **artifact immutable, content-addressed** (đường dẫn chứa
     chính checksum), giữ **ít nhất bằng vòng đời bundle** — xoá snapshot mà
     bundle còn tham chiếu là lỗi vận hành có tên.
   - Hash **toàn bộ catalog revision** mà bundle có thể truy cập, **không** hash
     subset thay đổi theo packet: cùng bundle trên hai packet phải cho cùng
     checksum.
   - Canonical: sort theo `(algorithm_id, kind, trait index)`; JSON qua
     `canonical_json` sẵn có; text qua NFKC — **dùng lại** `artifact_checksum`
     và `sanitize.canonical`, không đẻ công thức hash thứ hai (hai công thức
     cho một checksum sẽ lệch, xem `packet_checksum` A4-i).
   - Pointer "current" của DB **đổi được**; revision **đã được bundle tham
     chiếu là immutable** — endpoint sửa traits tạo revision mới, không sửa
     tại chỗ.
   - Gate và calibration kiểm **cả hai**: ref tồn tại **và** checksum tính lại
     từ nội dung khớp (theo mẫu `PacketArtifact` — loader tính lại, không tin
     giá trị lưu).
   - KB hiện là hằng số code pin bằng `KNOWLEDGE_BASE_VERSION`; khi KB rời code
     sang DB, **cùng bộ ba + cùng luật** áp vào — khai trước ở đây.

**DoD:** e2e chứng minh model nhận và trích dẫn được measurement/timeline/trait; **integration smoke**: một claim đề xuất → checker thật → verdict → promotion matrix (bản 3); flag độc lập; sửa một trait row ⟶ revision mới, bundle cũ vẫn replay được từ `traits_snapshot_ref` và calibration cũ **không** áp cho revision mới (bản 5); xoá snapshot đang được tham chiếu bị từ chối; token delta báo cáo.

### W2 — Candidate generator hybrid

1. Mapping detection → component → mechanism thành candidate contract, không `supporting_refs`.
2. Hợp nhất ba nguồn không nhân đôi; dedupe `mechanism_id + subject`.
3. `eval_distractor_mode` với trust boundary §3.1.
4. `verification_options` có cờ tắt riêng (bản 4).
5. `unknown` luôn có mặt.

**DoD:** production shortlist sạch; eval mode tính được 4 metric E4a; `generator_recall@K` chấm trước can thiệp; negative control không ép chọn; candidate chưa duyệt không promotion.

### W3 — Tool routing theo capability

1. Effective menu sau `filter_tool_menu`.
2. Required-argument source vào card.
3. Auto-route sau `auto_route_checker`, độc lập mục 1, **sau declare + admission** (bản 4).
4. Không gọi lại tool cùng arguments sau verdict.
5. Metric 4 failure type.
6. **`menu_recall`** đo trước metric model; `unknown` ⟶ fallback evidence-capable (bản 4).
7. Contract impact: chỉ `auto_route_checker` đổi nghĩa `checker_selection`; preregister lại; report tách code-route/model-chọn.

**DoD:** không request tới tool chắc chắn thiếu evidence; `menu_recall = 1.0` trên planted trước E5a; rejection giảm so B1 mà recall không giảm.

### W4 — Discriminated union và repair có giới hạn

1. Union `NoCheckDecision | CheckPlan`.
2. Draft theo guard contract §3.3; refuted ⟶ audit link.
3. Tách call là nhánh phụ E6.
4. Feedback thành repair payload; repair tối đa một lần, tính vào `max_model_calls`.
5. `no_progress`, `revisions_exhausted` giữ hard stop.
6. **Chi phí báo theo lớp chốt trước, không theo nhánh model chọn** (bản 3,
   sửa bản 5 — nhánh là quyết định của model, B1 chưa có union nên không có
   phân lớp tương ứng, so median `CheckPlan` với một subset B1 chọn sau khi
   nhìn output là post-treatment bias):
   - Lớp case = `expected_check_required` trong fixture spec (W0.1), chốt
     **trước** khi chạy.
   - Báo **intent-to-treat** trên toàn bộ case, rồi **subgroup** theo lớp
     fixture — cả B1 lẫn union đều có hai con số này, so được.
   - Nhánh model thực tế chọn (`NoCheckDecision`/`CheckPlan`) báo thêm, **chỉ
     mang tính chẩn đoán**, kèm ma trận lớp-fixture × nhánh-model để thấy model
     có xin check đúng chỗ fixture cần không.

**DoD:** giảm drop vì lỗi hình thức; model call trung vị ITT và theo lớp fixture không tăng so B1; mọi nhánh qua `finalize` một lần; không draft trong render/chấm; final sau refuted có audit link.

### W5 — Cascade và model selection — kèm router eval

Chỉ bắt đầu sau W0–W4 có baseline ổn định.

1. Rule cho case render trực tiếp từ floor.
2. Điều kiện escalation hai bậc.
3. So model trên cùng prompt/packet/menu/budget/snapshot.
4. Model local đánh giá lại trên task shortlist (E9).
5. **Đánh giá router như một thành phần** (bản 5, siết bản 6 — rule/threshold
   cascade thiết kế sau khi xem E8 trên cùng case thì E10 lạc quan):
   - Router **thiết kế trên E8-dev**; rule/threshold **freeze** thành
     `router_rule_checksum`, vào bundle identity.
   - **Oracle router** dựng offline từ dữ liệu E8 (mọi arm đã chạy trên mọi
     case), nhưng "best" định nghĩa bằng **utility function preregistered**
     (trọng số quality/cost/latency chốt trước) — không chọn hậu nghiệm.
   - E10 **đánh giá trên case chưa dùng để thiết kế router**. Dữ liệu ít ⟹
     **cross-fitting theo case/family**: tune trên fold này, score trên fold
     kia, không bao giờ cùng fold.

**DoD:** cấu hình chọn theo Pareto quality–cost **và** E10 đạt ngưỡng router recall / regret đã chốt; report nêu chất lượng, `pass^3`, token, latency, escalation rate, router recall, false non-escalation, regret.

---

## 5. Ma trận thực nghiệm

Mỗi thực nghiệm thay một biến chính, ghép cặp, 3–5 repeats, bypass cache. Tiên quyết: W1.0 + W1.7 + preregistration W0.8. Mọi so sánh từ B1.

**Toàn bộ E0–E10 chạy trên development set** (bản 6). Chúng chọn cấu hình;
chúng **không** kết luận. Kết luận §10.1 đến từ đúng một lượt confirmatory trên
holdout đã khoá, với cấu hình đã freeze.

**Arm vector preregistered** (bản 4):

```text
vector = (M1, M2, M3, A5, filter_tool_menu, auto_route_checker,
          shortlist, verification_options, union_schema, critic)
B1   = (0,0,0,0, 0,0, off,off, off, off)
E1B  = (1,0,0,0, 0,0, off,off, off, off)
E2B  = (1,1,0,0, 0,0, off,off, off, off)
E3   = 2×2 đầy đủ trên (M3, A5) với M2 = e2:
       (1,e2,0,0) (1,e2,1,0) (1,e2,0,1) (1,e2,1,1)
```

`e2` khai trước là adaptive design: luật chọn nhánh E2 làm nền E3 chốt trước khi chạy E2.

| ID | So sánh | Câu hỏi | Diễn giải |
|---|---|---|---|
| B0 | (lịch sử) mock host | — | Chỉ chẩn đoán |
| B1 | Real-host, mọi flag off | Bất ổn tự nhiên? | Mốc cho mọi E |
| E1 | B1 vs +M1 | Chung chung vì thiếu số đo? | Specificity tăng ⇒ bottleneck input |
| E2 | E1B vs +M2 | Timeline giúp hay chỉ phình prompt? | Gain > token cost ⇒ giữ |
| E3 | **2×2 đầy đủ M3×A5** (bản 5 — thay E3a/E3b/E3c có điều kiện) | Main effect từng nguồn **và** interaction? | Bốn arm, hai arm đầu tái dùng; hai nguồn có thể vô hiệu riêng lẻ mà mạnh khi kết hợp — quyết định chạy interaction theo hình dạng main effect sẽ bỏ lỡ đúng trường hợp đó. Nếu không chạy đủ 2×2 thì tuyên bố interaction **ngoài phạm vi**, không chạy "khi trái chiều" |
| E4a | Free vs shortlist tối thiểu, eval mode | Yếu ở sinh hay chọn cơ chế? | 4 metric: `generator_recall@K` (trước inject) · `selector_accuracy\|gold_present` · `unknown_accuracy\|gold_absent` · distractor rejection |
| E4b | Shortlist tối thiểu vs +`verification_options` | Tool hint thêm gì? | Verification scaffolding riêng |
| E5a | Full vs filtered menu, model tự chọn | Lỗi tool do model hay menu? | Sau `menu_recall = 1.0` |
| E5b | Filtered vs +auto-route | Chọn tất định có đáng tiêu model token? | Hàng duy nhất đổi semantics `checker_selection` |
| E6 | Schema tự do vs union | Một output chứa quá nhiều quyết định? | Chi phí đọc theo lớp fixture ITT + subgroup (W4.6) |
| E7 | Critic off/on | Critic còn giá trị? | |
| E8 | Model mặc định vs mạnh hơn, cùng pipeline | Còn lại có đúng là giới hạn model? | Dữ liệu E8 là nguồn dựng oracle router cho E10 |
| E9 | Hosted vs local trên task shortlist | Local thua vì task mở hay năng lực? | |
| **E10** | **floor-only vs always-default vs always-strong vs oracle-router vs frozen-cascade** (bản 5, đủ 5 arm bản 6) | Router có gửi đúng case đi đúng chỗ không, và bậc escalate thứ hai có giá trị thật không? | Router thiết kế trên E8-dev, freeze `router_rule_checksum`, score trên fold/case chưa dùng để thiết kế (cross-fitting theo case/family khi ít dữ liệu). **always-strong** là mốc đo giá trị thật của bậc hai — không có nó thì gain của escalation không tách được khỏi gain của model mạnh. Oracle theo utility preregistered. Đo: end-to-end quality/cost; escalation rate; **router recall**; **false non-escalation**; **regret** so oracle; gain bậc hai so always-strong. Cascade không deploy nếu regret/false non-escalation vượt ngưỡng chốt trước, dù Pareto model đẹp |

Không chạy E8/E9/E10 trước E1–E6.

---

## 6. Metric quyết định

### 6.1. Preregistered (bản 5)

- **Hard constraints** (phủ quyết): structural violations = 0; budget/protocol pass; `menu_recall = 1.0` khi filter bật.
- **Primary endpoint:** case-level mechanism correctness trên planted set; phép kiểm ghép cặp (McNemar sẵn có trong harness, chuyển từ proxy "abstain vs propose" sang endpoint này); margin δ và hướng chốt trước.
- **Secondary:** component attribution; abstention correctness; evidence validity/relevance (chỉ refs model chọn); checker/tool selection (tách code-route); tỷ lệ explanation cụ thể; cost.
- **Multiplicity:** hierarchical testing — primary trước, secondary chỉ đọc nếu primary đạt; không chọn metric đẹp sau khi nhìn số.

### 6.2. Verified rate

Denominator **case-level** trên planted case checkable; ba tầng báo riêng: tool `completed` / verdict `supports` / promotion `mechanism_verified`.

### 6.3. Reliability

`pass^3` chốt trước, đủ case, kèm CI; tỷ lệ cùng mechanism trên repeat; tỷ lệ `no_progress`, `revisions_exhausted`, guard drop, host rejection.

### 6.4. Chi phí

Token/call/tool trung vị **ITT** và **theo lớp `expected_check_required`** (bản 5); wall time trung vị + p95; tỷ lệ floor xử lý; escalation rate; router metrics của E10.

### 6.5. Router (bản 5/6)

Router recall; false non-escalation; regret so oracle; gain bậc hai **so
always-strong**. Oracle và regret tính theo **utility function preregistered**
`U = w_q·quality − w_c·cost − w_l·latency` với trọng số chốt ở W0.8; đổi trọng
số sau khi thấy số là chọn oracle hậu nghiệm.

---

## 7. Thứ tự thi hành đề xuất

```text
W0 — eval foundation + preregistration thống kê (W0.8)
  ↓
W1 — ToolHost thật + input M1/M2/M3 + flags + snapshot tái dựng được (W1.8)
  ↓
B1 — baseline real-host
  ↓
E1, E2, E3 (2×2 đầy đủ) — input ablation
  ↓
W2 — hybrid candidate generator
  ↓
W3 — tool routing
  ↓
W4 — discriminated union + repair
  ↓
E4a/E4b, E5a/E5b, E6, E7 — architecture ablation
  ↓
W5 + E8/E9 — model selection
  ↓
E10 — router eval (thiết kế trên E8-dev, score cross-fit, 5 arm)
  ↓
FREEZE — bundle_identity + runtime_config + eval_spec + router_rule
  ↓
CONFIRMATORY — một lượt official gate trên hidden suite preregistered
               (chỉ khi OFFICIAL_GOLDEN_READY=True; trước đó: exploratory)
```

### Ưu tiên nếu nguồn lực hạn chế

Một việc duy nhất: **W1.0**. Một thay đổi kiến trúc: **W2**. Một thay đổi dữ liệu: **W1.1–W1.4** (+ W1.8 nếu traits bật). Một thay đổi đánh giá: **W0 + W0.8**.

---

## 8. Những việc chưa nên làm

- Không đổi model liên tục trên ba fixture rồi chọn theo cảm nhận.
- Không thêm vector DB cho KB nhỏ trước khi lexical thất bại có số đo.
- Không thêm LLM critic thứ hai trước ablation critic hiện tại.
- Không tăng số vòng revise để chữa tool routing.
- Không đưa toàn bộ timeline vào prompt mặc định.
- Không nới guard.
- Không chạy E4–E10 khi checker còn là stub.
- Không đưa distractor vào production.
- Không so số trước và sau khi thay host.
- Không để golden label chạm artifact phía analyst.
- Không bật traits/retrieval trong lượt đo mà snapshot chưa **tái dựng được** từ ref (bản 5).
- **Không deploy cascade chỉ dựa trên Pareto giữa các model** (bản 5) — router là thành phần riêng, E10 là điều kiện.
- **Không chọn primary endpoint hoặc metric báo cáo sau khi nhìn kết quả** (bản 5).
- **Không dùng holdout để chọn bất kỳ thứ gì** — prompt, threshold, model, router (bản 6).
- **Không đọc kết quả E1–E10 thành deployment proof** khi `OFFICIAL_GOLDEN_READY=False` (bản 6).
- **Không tune và score router trên cùng fold** (bản 6).

---

## 9. Rủi ro và cách giảm nhẹ

| Rủi ro | Giảm nhẹ |
|---|---|
| Shortlist lặp bias sàn | Eval distractor + gold-absent; `unknown` luôn có; knowledge provider ngoài mapping |
| Traits folklore / duyệt theo đáp án | Anchor độc lập; khoá trước golden |
| DB sửa sau calibration, checksum không đổi | Bộ ba revision/checksum/ref; revision tham chiếu immutable; gate kiểm ref + checksum (bản 4/5) |
| **Có checksum mà mất snapshot ⟹ không replay được** | Snapshot content-addressed, retention ≥ vòng đời bundle; xoá snapshot đang tham chiếu bị từ chối (bản 5) |
| Golden label rò sang analyst | Labels chỉ phía scorer; eval mode cấm ở production/gate |
| Filter xoá đúng tool cần | `menu_recall` trước E5a; fallback evidence-capable |
| Draft thành vùng vô luật | Guard contract §3.3; audit link |
| **Chi phí theo nhánh bị post-treatment bias** | Lớp chốt trước bằng `expected_check_required`; ITT + subgroup; nhánh model chỉ chẩn đoán (bản 5) |
| **Chọn metric đẹp sau khi nhìn số** | Primary endpoint + δ + hierarchical testing preregistered (bản 5) |
| **Cascade rẻ vì đẩy case cho floor, bỏ lỡ case LLM có giá trị** | E10 với oracle router; regret/false non-escalation là điều kiện deploy (bản 5) |
| Bỏ lỡ interaction M3×A5 | E3 chạy đủ 2×2 hoặc tuyên bố ngoài phạm vi (bản 5) |
| Golden nhỏ ⟹ tối ưu quá mức | Packet thật chấm rubric; mở family; `underpowered` + CI |
| Model mạnh che lỗi kiến trúc | So model sau ablation; cùng budget/config/snapshot |
| Đổi semantics metric giữa chừng | Mọi thay đổi preregister + ghi report; `eval_spec_checksum` hash nội dung |
| **Selection bias: chọn cấu hình bằng nhiều phép thử rồi kết luận trên cùng dữ liệu** | Development ≠ confirmatory (W0.9); confirmatory = official gate trên hidden suite, một lượt, cấu hình freeze; chưa có holdout ⟹ exploratory (bản 6) |
| **Router train/test trên cùng case ⟹ E10 lạc quan** | Thiết kế trên E8-dev, freeze `router_rule_checksum`, cross-fitting theo case/family; oracle theo utility preregistered; arm always-strong (bản 6) |

---

## 10. Tiêu chí kết thúc đợt cải thiện

### 10.1. Hoàn thành nghiên cứu — đóng khi trả được MỘT trong BỐN kết luận trên primary endpoint

(Bản 5 — tách non-inferior khỏi equivalent. Bản 6 — kết luận này **chỉ được
phát ra từ lượt confirmatory** trên holdout đã khoá với cấu hình đã freeze;
cùng bốn nhãn nhưng đọc trên development set thì mang tiền tố **exploratory**
và không đủ cho §10.3.)

Với δ và hướng kiểm định preregistered ở W0.8:

- **Superior:** analyst hơn sàn trên primary endpoint, paired test đủ lực.
- **Non-inferior:** analyst **không kém sàn quá δ** — cận dưới CI của hiệu số > −δ. Không nói gì về việc có hơn.
- **Equivalent:** **toàn bộ CI nằm trong [−δ, +δ]**. Mạnh hơn non-inferior, đòi lực lớn hơn.
- **Inferior hoặc inconclusive:** kém hơn, hoặc không đủ dữ liệu sau khi đã mở hết fixture stage được — ghi rõ thiếu gì.

"Không chứng minh được tốt hơn" là một **kết quả**. Secondary metrics chỉ đọc theo thứ bậc sau primary.

### 10.2. Điều kiện nghiên cứu hoàn chỉnh

1. Model thật chấm trên fixture có expected findings.
2. Input thực sự tới runner, snapshot tái dựng được từ ref; timeline có quyết định theo ablation.
3. Hard constraints đạt; primary + secondary báo theo thứ bậc; `pass^3` kèm CI; chi phí ITT + subgroup.
4. Verified rate: "> 0" ở DoD W1; nghiên cứu báo minimum rate case-level, ba tầng tách.
5. Hybrid shortlist chứng minh hoặc bị loại bằng E4a/E4b.
6. Tool-routing failures có taxonomy, `menu_recall` báo cáo.
7. E3 đủ 2×2 hoặc interaction tuyên bố ngoài phạm vi.
8. Mọi kết luận ghi family/case/repeat/`underpowered`/baseline/`eval_spec_checksum`/`traits_revision_id`.

### 10.3. Được triển khai — cổng riêng, sau 10.1

Deploy khi: kết luận 10.1 là superior, **hoặc non-inferior kèm lợi thế đã chốt trước** (coverage, cost, abstention); hard constraints và cost ceiling đạt; snapshot traits/KB đóng băng và tái dựng được trong bundle; `eval_distractor_mode` tắt và bị cấm ở production; **nếu deploy cascade thì E10 đạt ngưỡng router recall/regret** trên fold chưa dùng để thiết kế — Pareto giữa các model không thay được điều kiện này.

**Bằng chứng deploy là một `GateDecision` trên hidden suite** (bản 6) — đúng
thứ `analyst_visible()` đã đòi từ E5: bundle identity khớp, targets khớp,
effective budget khớp. Bảng kết quả E1–E10, dù đẹp đến đâu, không phải object
mà cờ đó nhận. Khi `OFFICIAL_GOLDEN_READY=False` thì không có deploy; có
exploratory report, và report ghi rõ chữ đó.

Kỳ vọng thực tế của MVP: **từ một tập cơ chế có căn cứ, chọn đúng cơ chế, yêu cầu đúng bằng chứng, abstain khi thiếu dữ liệu, và tạo lời giải thích cụ thể hơn tầng tất định với chi phí có kiểm soát** — phần "kiểm chứng được" đo bằng verified rate ba tầng, phần "so với sàn" chấp nhận cả bốn kết luận của 10.1, phần "route" đo bằng E10.

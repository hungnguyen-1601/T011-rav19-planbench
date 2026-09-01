# E0 — hợp đồng tầng giải thích "vì sao"

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-18/tang-giai-thich-vi-sao.md` §5, đợt **E0**
**Thiết kế nguồn:** `notes/2026-08-18/tongduyan_giai-phap-giai-thich-vi-sao-thuat-toan-thang.md` (v2)
**Trạng thái:** xong E0 đặc tả + hiện thực + test, **đã qua hai vòng rà của
An** (mục 8: sáu điểm; mục 9: ba điểm — tất cả đã sửa). **Chưa commit.**
Full suite chưa chạy — xem mục 10.

---

## 1. E0 giao cái gì

Plan liệt kê năm hạng mục cho E0. Cả năm nằm trong package mới
`packages/explanation/planbench_explanation/`:

| Hạng mục plan | Ở đâu |
|---|---|
| Ledger schemas (Proposal / Record / Claim / EvidenceRef / CheckerResult) | `ledger.py` |
| Promotion matrix (claim type × tool × verdict × provenance, đọc từ ToolCard) | `promotion.py`, đọc `tools.py` |
| `PlanningInputEvidence` spec + validator | `planning_input_evidence.py` |
| `impact_ref` hai loại | `ledger.ImpactRef` |
| Artifact versioning | `versioning.py` |

Cộng ba module vocabulary mà bốn hạng mục trên đều so chuỗi lên nó:
`levels.py` (thang bằng chứng + qualifier + whitelist cách nói),
`provenance.py` (ba enum hay bị trộn), `subjects.py` (chủ thể chịu trách
nhiệm), `propositions.py` (danh sách đóng những gì được phép khẳng định).

Package đã vào `pyproject.toml` (`pythonpath`) và `ruff.toml`
(`known-first-party`).

## 2. Bốn chỗ contract từ chối tin lời tự khai

**Proposal không có quyền để mà bị tước.** `HypothesisProposal` dùng
`extra="forbid"`, nên `confidence`, `status`, `claim_level`, `impact` là
**lỗi parse**, không phải giá trị bị validate rồi bỏ. Đây là điểm plan
nói rõ: để trường `{delta, method}` trong schema của model thì model vẫn
phát minh được con số đúng hình dạng, và người đọc artifact không phân
biệt được số bịa với số tính.

**Prose không vào code path — và không bằng một test đối chiếu.** Plan
yêu cầu "có test đối chiếu mỗi dòng prose có dòng typed tương ứng". Test
kiểu đó xanh đúng ngày viết rồi mục dần. Nên `ToolPurpose.verifies` là
**mapping khóa bằng chính proposition type** nó giải thích, và validator
bắt tập khóa **bằng đúng** `supported_proposition_types`; tương tự cho
`does_not_verify` với `forbidden_inference_types`. Câu văn không có typed
đứng sau thì không viết được; typed không có câu văn cũng không. Prose
không nói về proposition nào đi vào `purpose.notes` — chỗ không code nào
đọc. Đây là **sai lệch có chủ ý** so với YAML trong plan (plan viết
`verifies` là list); nó giữ nguyên bất biến plan muốn, nhưng bằng cấu
trúc thay vì bằng lời hứa.

**Một bộ enum provenance duy nhất.** `recorded` / `verified_reconstruction`
/ `reconstructed` / `missing`. Cách viết cũ
`recorded_or_verified_reconstruction` không tồn tại — nó đọc như giá trị
thứ năm rồi phải special-case ở mọi chỗ so sánh. `not_checkable` nằm ở
`execution_status`, không phải provenance.

**Ba câu hỏi, ba trường.** `execution_status` (tool chạy thế nào),
`proposition_verdict` (mệnh đề đứng hay đổ), `input_provenance` (input
từ đâu). Schema chặn ba ca: run chưa completed mà mang verdict; tool
đa-proposition mà có verdict top-level; run completed mà khai
`input_provenance: missing`.

## 3. Promotion matrix — luật, không phải điểm số

`promote()` nhận proposal + record + catalog + known_unknowns, trả
`PromotionOutcome` gồm claim **hoặc** `None`, và **luôn** kèm `reasons`.
Lý do quan trọng ngang claim: panel trống vì "không ai đề xuất gì" và
panel trống vì "một check đã bác bỏ" phải phân biệt được trong ledger.

Thứ tự luật (tất định, dừng ở luật đầu tiên từ chối):

1. statement rỗng ⇒ từ chối.
2. record trỏ sai proposal ⇒ từ chối.
3. `known_unknowns.blocks_claim_types` chứa proposition ⇒ từ chối. Đây
   là chỗ plan §4.5 nói "orchestrator **cưỡng chế**", không phải nhắc.
4. `record.status != checked` ⇒ từ chối (`proposed` / `check_failed` /
   `not_checkable` đều không sinh claim).
5. supports rỗng, hoặc có ref `provenance=missing` ⇒ từ chối.
6. Duyệt từng checker result: tool không có trong catalog ⇒ từ chối;
   proposition nằm trong `forbidden_inference_types` của card ⇒ từ chối;
   verdict `refuted` ⇒ **từ chối ngay**, dù bao nhiêu check khác đã
   supported (ledger là bộ lọc loại bỏ, không phải bộ đếm phiếu);
   `inconclusive` / không completed / result vượt card / provenance card
   không nhận ⇒ **không đóng góp**, ghi reason, đi tiếp.
7. Mức = `weakest(` trần card, trần provenance của checker, trần
   provenance của **mọi evidence claim trích**, trần subject `)`. Bốn
   trần độc lập, lấy min ở **một** chỗ — provenance vào hai lần vì nó
   đến từ hai phía (mục 9).
8. Không check nào đóng góp: cần ≥1 evidence loại
   `observation`/`contrast`/`trace_window` mới nghỉ ở `associated`; chỉ
   có fact tĩnh ⇒ từ chối `no_pattern_evidence` (không có pattern thì
   không có gì để "phù hợp với").
9. `intervention_supported` **chỉ** đến từ `InterventionEvidence`:
   preregistration + lane research + `proposition_type`/`subject` khớp
   proposal + `verdict=supported` + `scope` khớp. `refuted` ⇒ từ chối
   claim; `inconclusive` ⇒ từ chối. Không ToolCard nào được khai mức
   này — validator của `PropositionPolicy` từ chối thẳng.
10. **Liên kết mechanism tới kết cục** (note §2): claim từ
    `mechanism_verified` trở lên đòi thêm observation thực thi **và**
    `impact_ref`. Thiếu observation ⇒ trần `observed` (không có hành vi
    nào để "phù hợp với", còn lại là phép đo); thiếu `impact_ref` ⇒ trần
    `associated` (pattern thật, phần đóng góp chưa định lượng).
11. Qualifier suy ra, không khai: `research_lane`, `reconstructed_input`,
    `estimated` (impact là `attributable_effect_estimate`),
    `profile_weighted`.
12. Cuối cùng câu chữ đi qua whitelist theo mức; dính từ nhân quả ⇒ từ
    chối, kể cả khi bằng chứng đủ mạnh. Gate lexical đặt **trong
    promotion**, không chỉ ở render: mức và cách nói quyết định cùng
    nhau hoặc chúng trôi khỏi nhau.

`promote_measurement()` là đường riêng cho claim `observed` — số của
waterfall lên panel mà không cần analyst, nhưng vẫn chịu đúng luật câu
chữ và đòi mọi evidence `recorded`.

## 4. `impact_ref` — hai loại, và không có con số nào trong ledger

`ImpactRef` giữ `artifact_ref` + `impact_kind` + `objective` + `method`.
`attributable_effect_estimate` bắt buộc có `assumptions` và
`uncertainty`; `observed_contribution` thì không.

Ledger **không giữ float**. Có float thì sẽ có render path in nó không
kèm caveat của artifact, và khác biệt giữa hai loại impact — vốn hoàn
toàn là khác biệt về *nghĩa của con số* — thôi đi theo con số.

## 5. Sidecar `PlanningInputEvidence` và luật replay

Đã kiểm lại code trước khi viết: `StackRun.plans` chỉ giữ plan **thành
công** (docstring ghi rõ "Refused replans are not here"), và trace
Parquet không có costmap lẫn plan polyline. Nên:

- Model có validator ba chiều: `outcome=path` ⇒ có
  `output_plan_checksum`, không có `failure_code`; `no_path`/`error` ⇒
  checksum `null` **và** bắt buộc `failure_code`.
- `validate_episode_attempts(records, *, expected_attempts)` bắt attempt
  liên tục từ 1, không trùng, cùng một
  `(episode_context_id, candidate_id)`, **và** khớp số lượng với counter
  của runner. Liên tục bắt lỗ ở giữa (replan bị từ chối mà writer không
  thấy); `expected_attempts` bắt đuôi bị cắt — `[1]` liên tục hoàn hảo
  mà vẫn là writer chết giữa chừng.
- `admit_replay_with_sidecar()` so bảy trường (costmap checksum, query,
  planner fingerprint, execution environment, outcome, plan checksum,
  **failure_code**);
  lệch bất kỳ ⇒ `not_checkable`. Khớp hết ⇒ `recorded` (đọc thẳng từ bản
  ghi) hoặc `verified_reconstruction` (dựng lại và khớp), trần
  `mechanism_verified`.
- `admit_replay_without_sidecar()` là luật cho **toàn bộ kho run hiện
  có**: `plans=[]` ⇒ `not_checkable`; lệch bytes ⇒ `not_checkable`
  (reconstruction sai); **khớp bytes ⇒ vẫn chỉ `reconstructed`, trần
  `associated`**, và lý do ghi thẳng vào record:
  `output_plan_match_is_not_evidence:many_costmaps_yield_one_path`. So
  output plan là refuter, không bao giờ là promoter.

`REPLAY_CEILING = mechanism_verified`: replay tái lập một điều kiện, nó
không biến thiên gì, nên không replay nào chạm rung trên cùng.

## 6. Trần theo chủ thể — nợ H4 khai thành code

`subject_ceiling()` chặn `perception_provider` và `runtime_transport` ở
mức `observed` cho tới khi H4 tách được compute giữa candidate /
deployment / transport: triệu chứng được báo, trách nhiệm chưa được
gán. Cờ `h4_accounting_complete` là **tham số**, không phải hằng số, và
test đã phủ cả hai phía — ngày H4 xong là đổi một dòng, không phải sửa
một bảng không ai đọc lại.

## 7. Artifact versioning và tham chiếu một chiều

`ExplanationArtifactHeader` mang `source_manifest_ref` +
`source_manifest_checksum` (sha256, có pattern) + **năm version** tầng
này sở hữu: `explanation_schema_version`, `promotion_matrix_version`,
`detector_version`, `knowledge_base_version`, `tool_catalog_version`.

Chọn đúng năm này vì đó là những thứ manifest **không thể biết** và mỗi
thứ đổi thì cùng một dữ liệu run cho ra output khác. `contracts_version`
và `anchor_config_version` **cố ý không copy** — chúng ở trong manifest,
và ghi hai chỗ là hai chỗ để bất đồng. Luật một chiều được **kiểm** chứ
không được nhắc: test đọc `contracts/schemas/manifest.schema.json` và
khẳng định tập tên trường của header giao với tập của manifest bằng rỗng.

Không chạm ba khóa cứng HĐ-1/HĐ-3/HĐ-5, không sửa schema manifest.
Ngoài package mới, chỉ đụng ba dòng ở ba file cấu hình đường dẫn:
`pyproject.toml`, `ruff.toml`, `scripts/dev_stack.sh`.

## 8. Vòng rà của An — sáu điểm, sáu chỗ sửa

An rà bản đầu và chỉ ra sáu chỗ. **Cả sáu đúng.** Ghi ra đây vì năm
trong sáu là đúng loại lỗ tầng này tồn tại để chặn: contract *trông như*
đã chặn trong khi chưa.

**① Dev stack không import được package mới — blocker thật.**
`packages/explanation` có trong `pyproject.toml` mà thiếu trong `PY_PATH`
của `scripts/dev_stack.sh`. Đây đúng ca comment ngay trên biến đó đã kể:
`packages/decision` từng thêm cho pytest mà quên cho server, suite xanh
trong khi API không khởi động nổi. Report bản đầu **khuyến nghị** chạy
`tests/test_dev_stack_pythonpath.py` nhưng không chạy — khuyến nghị một
test rồi không chạy nó thì bằng không chạy. Đã thêm vào `PY_PATH`, test
4/4 xanh.

**② `mechanism_verified` không cần observation thực thi lẫn impact_ref.**
Note thiết kế nói rõ: mệnh đề checker xác nhận là mệnh đề **hẹp**, "liên
kết tới thắng/thua cần thêm observation thực thi + impact ref, **mã hóa
trong promotion matrix**". Bản đầu chỉ đòi `supports` không rỗng, và điều
kiện có behavioral pattern chỉ chạy ở nhánh *không có* checker — nên một
static fact cộng một checker result đủ ra `mechanism_verified`. Đã mã hóa
thành hai trần khác nhau, vì hai thứ thiếu là hai thứ khác nhau:

- thiếu observation thực thi ⇒ trần **`observed`**. Không có hành vi nào
  để mà "phù hợp với"; cái còn lại là một phép đo hình học.
- thiếu `impact_ref` ⇒ trần **`associated`**. Pattern có thật, phần đóng
  góp vào ΔU chưa định lượng.

**③ Gate `intervention_supported` chưa chứng minh intervention hỗ trợ
mệnh đề.** `InterventionEvidence` bản đầu chỉ có preregistration + axes +
scope, nên một intervention trên trục không liên quan — hoặc một
intervention chạy đúng trục mà **không tìm thấy gì** — đều là cùng một
object với matrix, và cả hai đẩy claim lên rung cao nhất. Nay object mang
`proposition_type`, `subject`, `verdict`, `effect_direction`,
`statistical_result_ref`; matrix khớp proposition và subject với proposal,
và `refuted`/`inconclusive` **từ chối claim** chứ không rơi về mức thấp
hơn. Thêm validator: `verdict=supported` cộng
`effect_direction=unchanged|increased` là mâu thuẫn, từ chối lúc dựng.

**④ CheckerResult chưa bắt buộc bằng chứng truy vết.**
`evidence_artifact_ref` / `evidence_checksum` / `implementation_ref` đều
optional, nên "chỉ tool host tạo được" là một câu trong tài liệu chứ
không phải tính chất của object. Nay completed ⇒ bắt buộc **cả ba**;
không completed thì được bỏ (run không xảy ra thì không có evidence để
trỏ).

**⑤ Replay có sidecar bỏ qua `failure_code`.** `no_global_path` và
`planner_timeout` cùng là `no_path` và là **hai cơ chế khác nhau** — mà
cơ chế chính là chủ đề của claim. `ReplayObservation` nay có
`failure_code` và nó nằm trong danh sách so sánh.

**⑥ Validator không thấy đuôi bị mất.** `[1]` là danh sách liên tục hoàn
hảo, và với episode thực tế plan ba lần thì đó là writer chết giữa
chừng — đúng ca sidecar sinh ra để ghi. Nay `validate_episode_attempts()`
bắt buộc tham số `expected_attempts` lấy từ **counter của runner**
(`replan_count` của trace + 1). Validator suy ra kỳ vọng từ chính input
của nó thì chỉ có thể đồng ý với input đó.

## 9. Vòng rà thứ hai — ba điểm

**HIGH — provenance của supporting evidence không vào trần.** Đúng, và
đây là lỗ nặng nhất trong cả hai vòng: trần chỉ đọc provenance của
checker result, còn provenance của evidence mà claim **trích dẫn** chỉ
sinh ra qualifier `reconstructed_input`. Nên tổ hợp *(observation
reconstructed + checker input recorded + có impact_ref)* ra
`mechanism_verified` **kèm một cái nhãn nói rằng nó dựa trên dữ liệu
dựng lại** — nhãn không phải là trần. Nay:

```
ceiling = weakest(subject_ceiling, *provenance_ceiling(mọi ref trong supports))
```

Chọn **mọi** support chứ không phải tập con "evidence nối mechanism với
outcome": quyết định citation nào chịu lực chính là loại phán đoán tầng
này từ chối làm thay người đọc. Claim không mạnh hơn thứ yếu nhất nó
trích. Có test hồi quy đúng tổ hợp đó, kèm phép kiểm ngược (mọi evidence
recorded thì vẫn `mechanism_verified`).

**MEDIUM — ba trường truy vết chỉ bắt "không rỗng".** Đúng: `"x"` qua
được. Chọn **siết chứ không hạ lời văn**:

- `evidence_checksum` theo `CHECKSUM_PATTERN` (64 hex thường) — cùng
  recipe với `artifact_checksum()`/`file_checksum()`, đặt ở
  `versioning.py` để một chỗ định nghĩa.
- `implementation_ref` và `PlanningInputEvidence.execution_environment_ref`
  theo `CODE_REF_PATTERN`: `git:<40 hex>` hoặc `sha256:<64 hex>` —
  đúng hai thứ manifest đã ghi (`git_sha`, `docker_image_digest`), không
  phát minh quy ước thứ ba. **Short SHA bị từ chối**: 7 ký tự định danh
  một commit *trong một repo tại một thời điểm*, mà lý do ghi build là
  để giải được sau này.

Đồng thời sửa lời văn cho đúng chuyện: docstring cũ nói object này phân
biệt được kết quả do host tạo — **không đúng**. Schema làm nó *truy vết
được*; **quyền tác giả** được cưỡng chế ở chỗ khác (host là writer duy
nhất, E5/E6). Nay docstring nói đúng hai vế đó và không vế nào giả vờ là
vế kia. Bỏ chữ "signed" ở tiêu đề class.

**LOW — report lỗi thời.** Một nửa: mục test đã cập nhật 63 passed từ
lượt trước (dòng 252), nhưng câu "không sửa file nào ngoài hai file cấu
hình đường dẫn" thì đúng là còn cũ — `scripts/dev_stack.sh` là file thứ
ba. Đã sửa, và mục 10 dưới đây là số liệu hiện tại.

## 10. Test và trạng thái kiểm chứng

- `tests/test_explanation_contracts.py` (33 hàm test) — schema từ chối
  cái gì, prose↔typed, catalog, thang/trần, whitelist câu chữ, truy vết
  checker result, intervention khai kết quả, sidecar, versioning.
- `tests/test_explanation_promotion.py` (26 hàm test) — mỗi test một
  luật của matrix, gồm cả reason khi từ chối.
- Chín điểm của hai vòng rà đều có test hồi quy riêng, đặt tên theo ca
  tái hiện được.
- **64 passed**: `pytest tests/test_explanation_contracts.py
  tests/test_explanation_promotion.py tests/test_dev_stack_pythonpath.py`.
- `ruff check` + `ruff format --check` sạch.
- **Full suite vẫn chưa chạy** (theo yêu cầu chỉ chạy test liên quan).

## 11. Quyết định đã tự chốt trong lúc làm (An phủ quyết được)

1. **Package riêng `packages/explanation`**, không nhét vào
   `planbench_decision`. E0–E6 sẽ còn detectors, case packet, tool host;
   nhét vào package quyết định là trộn "ai thắng" với "vì sao".
2. **Năm version là năm cái ở mục 7.** Plan viết "5 version" mà không
   liệt kê. Nếu An muốn bộ khác thì đây là chỗ sửa.
3. **`purpose` là mapping thay vì list** (mục 2) — giữ bất biến bằng cấu
   trúc.
4. **Whitelist câu chữ viết tiếng Anh**, vì report export của platform
   là tiếng Anh; locale là một `PhrasePolicy`, E4 thêm bản tiếng Việt mà
   không fork luật.
5. **Vocabulary proposition có cả loại "inference-only"**
   (`complete_utility_attribution`, `global_planner_attempt_attribution`,
   `universal_algorithm_superiority`) — tồn tại để card **gọi tên mà từ
   chối**, và `HypothesisProposal` không nhận chúng làm
   `proposition_type`.

## 12. Chưa làm — nói rõ

- **Catalog rỗng.** E0 giao *hình dạng* ToolCard; card thật cho bốn lớp
  tool là E5, checker thật là E6. Card trong test là fixture, không phải
  catalog production.
- **Chưa có producer nào của claim ngoài test.** CasePacket builder và
  nối ledger là E4; detectors sinh observation là E3; waterfall là E1.
  `promote_measurement` hiện chưa có người gọi.
- **Chưa có writer sidecar.** E4.5, neo `AlgorithmHost`, chờ H4/H6.
  Tới lúc đó mọi replay đi đường
  `admit_replay_without_sidecar` và không claim nào vượt `associated`
  qua ngả replay.
- **Chưa có UI, chưa có template render.** E4.
- **`intervention_supported` chưa có đường sinh thật** — `InterventionEvidence`
  đã có schema, nhưng dose–response map editing là pha 2.

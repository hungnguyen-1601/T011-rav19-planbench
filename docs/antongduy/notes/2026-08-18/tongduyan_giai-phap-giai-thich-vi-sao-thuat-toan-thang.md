# Tầng "vì sao" — giải thích lý do candidate A thắng candidate B (v2)

**Ngày:** 2026-08-18 · **Loại:** research / thiết kế đã hội tụ qua 3 vòng thảo luận
**v2 thay thế toàn bộ v1.** Ba vòng: (1) đề xuất gốc 5 giải pháp; (2) phản biện của An —
4 mức bằng chứng, bẫy utility hai mức, replay hai chế độ, exemplar chống cherry-pick,
quy trách nhiệm theo thành phần, counterfactual dose–response, LLM đứng cuối;
(3) nâng vai LLM từ narrator lên **analyst sinh giả thuyết + gọi kiểm chứng deterministic**.

**Câu hỏi:** hệ đã chỉ được *ai* thắng (paired ΔU + CI). Chưa nói được *vì sao*.
Muốn từ quỹ đạo + số liệu suy ra nguyên nhân, hiển thị trên màn hình kèm mức đáng tin.

**Nguyên tắc gốc (bất biến qua cả 3 vòng):** *không để bằng chứng nghe mạnh hơn dữ liệu*.
LLM không bao giờ là nguồn của một con số, một dấu xác nhận, hay một kết luận nhân quả.

---

## 0. Tài sản sẵn có

| Tài sản | Vai trò cho tầng "vì sao" |
|---|---|
| Trace Parquet ghép cặp (HĐ-5): cùng episode_context cho mọi candidate | so từng thời điểm, từng đoạn — nền của mọi phép đối chiếu |
| `clearance_m` tại chỗ, event vocabulary, latency từng tick | triệu chứng hành vi đã nằm trong file |
| Utility phân rã `U = Σ w_j·u_j`, anchor tuyệt đối có nghĩa vật lý | ΔU phân rã bằng đại số |
| Paired bootstrap ΔU + CI theo từng objective (HĐ-10/HĐ-11) | CI cho từng thanh waterfall — không cần phép tính mới |
| Replay F08, trang `/decisions` | chỗ hiển thị |
| Lattice candidate (C1=A\*+DWA, C2=RRT\*+DWA, C3=A\*+DWA_B…) | cấu trúc factorial cho component-swap |
| `FairnessPolicy.research()` (H3) | lane cho run chẩn đoán, không nhiễm evaluation distribution |
| Task Neighborhood N5 (pha 2) | nền cho can thiệp dose–response |

## 1. Hai trục thiết kế — không trộn

**Trục 1 — kiến trúc pipeline** (code nào sinh cái gì):

```
FACTS/DETECTORS ──> CASE PACKET ──> ANALYST (giả thuyết) ──> CHECK RUNNER (đóng dấu)
                                                                      │
                RENDER (template-first, LLM tùy chọn) <── CLAIM LEDGER
```

**Trục 2 — thang bằng chứng của claim** (claim đáng tin đến đâu). Mỗi claim mang
`claim_level`; pipeline nào sinh claim đó không quyết định mức — bằng chứng quyết định.

## 2. Thang bằng chứng — 4 mức + qualifier

**Bốn mức bằng chứng tăng dần** (thuộc tính của claim). "Chưa đủ bằng chứng" **không phải
mức thứ năm** — nó là trạng thái không có claim.

| `claim_level` | Ví dụ | Nhãn UI | Động từ được phép |
|---|---|---|---|
| `observed` | "A hơn B +0,062 utility (mean paired, CI …)" · "B dừng 8,2 s tại B7" | **Đo trực tiếp** | "đo được", "ghi nhận" |
| `associated` | "Dừng–đi lặp tại B7 **phù hợp với** dao động local controller trong khe hẹp" | **Suy luận phù hợp** | "phù hợp với", "nhất quán với" |
| `mechanism_verified` | "Khe B7 0,68 m < footprint+inflation của B 0,74 m trên costmap đã kiểm chứng nguồn gốc; replay planner tái lập no_path" | **Cơ chế đã kiểm chứng** | "do … (đã kiểm chứng điều kiện/replay)" |
| `intervention_supported` | "Nới khe 0,68→0,90 m, chênh lệch biến mất qua nhiều seed" | **Đã xác nhận bằng can thiệp** | "gây ra", "là nguyên nhân chính" — luôn kèm phạm vi |
| *(không có claim)* | detector im lặng / check fail / `not_checkable` / dữ liệu thiếu | **Chưa đủ bằng chứng** | triệu chứng trần hoặc "Chưa đo" |

**Qualifier** — trực giao với mức, mô tả *nguồn suy ra*, không nâng/hạ mức:
`profile_weighted` (phân rã theo trọng số profile — đổi profile đổi hình, bắt buộc nêu
tên profile; nếu không là ngầm nâng preference thành phép đo) · `estimated` (số do tool
ước lượng có phương pháp, không phải đo thô) · `reconstructed_input` (input dựng lại,
chưa verify) · `research_lane` (bằng chứng từ run chẩn đoán, ngoài evaluation distribution).

Ghi chú:

- **Replay là mechanism check, không phải can thiệp** (sửa so với bản đầu v2): chạy lại
  đúng planner trên đúng input là *reproduction* — xác nhận cơ chế, không biến thiên gì.
  Promote lên `mechanism_verified` đòi input provenance đạt chuẩn (§8). Và mệnh đề được
  xác nhận là mệnh đề **hẹp** ("planner trả no_path qua khe trên costmap X") — liên kết
  tới thắng/thua cần thêm observation thực thi + impact ref, mã hóa trong promotion matrix.
- **`intervention_supported` luôn giới hạn phạm vi**: *"trong simulator và Task
  Neighborhood đã khai"* — cùng họ với mệnh đề "dưới phân phối kịch bản đã mô phỏng" của
  G2. Không bao giờ nâng thành thuộc tính phổ quát của thuật toán ("A tốt hơn B ở khe
  hẹp" — cấm).
- Whitelist động từ theo mức là thứ **kiểm được bằng máy** (lexical), chặn đúng ca
  "kẹt *vì* local minimum [fact:…]" — citation thật nhưng nhân quả bịa.

## 3. Waterfall ΔU — khung xương, kèm hai bẫy số học

**Waterfall chính phân rã paired ΔU mà `recommend()` dùng** — đó mới là câu trả lời cho
"tại sao hệ chọn A". Hai bẫy phải né:

1. **Hai mức utility không bằng nhau ở U_R** (clip — phase-3-3 mục 2): utility trên card
   không phải trung bình utility episode. Trộn hai con số thì người dùng cộng thanh
   waterfall không ra số trên card. Điểm mức tập + metric vật lý (qua anchor) xuống
   **drill-down**, có chú thích clip.
2. **Mean với median**: `ΔU = Σ w_j·Δu_j` chỉ cộng khít qua **mean**. HĐ-11 báo cáo
   median/IQR. Waterfall dùng mean paired ΔU (additive, có test tổng thanh = ΔU);
   median giữ vai mô tả phân phối, không vào waterfall.

Mỗi thanh gắn **CI ghép cặp theo objective** (tái dùng `LCB₉₅(ΔU_j)` của HĐ-10);
thanh vắt qua 0 hiển thị mờ. Nhãn panel ghi tên profile.

## 4. Exemplar + replay đôi

### 4.1. Bộ exemplar — công thức preregistered, deterministic

Chỉ lấy top |ΔU| là mời nghi cherry-pick. Công thức cứng, ghi trong spec, có test tie-break:

1. `typical` — episode có ΔU gần median nhất (tie-break: id nhỏ nhất)
2. `strongest_for_winner` — argmax ΔU
3. `strongest_for_runnerup` — argmin ΔU
4. `safety_critical` — sự kiện an toàn nặng nhất (collision > min clearance thấp nhất)
5. **prevalence** theo pattern detector: *"detour xuất hiện 27/30 cặp; ep 017 điển hình,
   ep 029 nặng nhất"* (cần E3 detectors trước — exemplar v1 ship bộ tứ, prevalence nối sau)

### 4.2. Replay đôi — hai chế độ đồng bộ

| Chế độ | Căn theo | Dùng để | Cảnh báo bắt buộc |
|---|---|---|---|
| **Time-sync** | thời gian tuyệt đối | fairness với vật cản động — thế giới hai robot thấy | — |
| **Progress-sync** | arc-length s chiếu lên L_ref | so hành vi tại cùng vùng bản đồ | **"cùng chỗ ≠ cùng tình huống"** — vật cản động đã ở chỗ khác vì hai robot tới nơi ở hai thời điểm khác nhau; chỉ hợp lệ cho nguyên nhân hình học tĩnh |

**Điểm phân kỳ** — v1 thực dụng: cross-track offset so với L_ref vượt ngưỡng **và duy trì**
(lọc chênh tốc độ), cộng mốc rẻ từ event: replan đầu tiên, dừng đầu tiên, detour bắt đầu.
Detector "chọn nhánh khác tại ngã rẽ" cần junction topology (Voronoi/skeleton) — hạng mục
riêng, xếp sau. Click evidence chip → replay nhảy đúng timestamp/region.

## 5. Detectors + map features + KB cơ chế

### 5.1. Detectors — hàm thuần của trace, test như metric

`detour(segment)` · `stuck_cluster` · `near_miss_cluster` · `replan_storm` ·
`oscillation` · `latency_spike` · `narrow_gap_refusal` — như v1. Thêm
**contrast graph trên lattice** — đọc chéo dữ liệu đã chạy, không cần run mới, nhưng chỉ
sinh **kết luận hẹp** theo bốn đầu ra:

- `rules_out_component_specific_attribution` — pattern ở cả C1 lẫn C2 (cùng DWA, khác
  global) **loại trừ** "riêng global planner của A gây ra". **Không** chứng minh local
  controller: task geometry, costmap, providers dùng chung và tương tác global–local
  cũng tạo được pattern chung.
- `supports_component_specific_attribution` — chỉ khi có cặp swap giữ mọi thứ khác bất
  biến và pattern đổi theo đúng thành phần đó.
- `insufficient_contrast` — lattice không có cặp đối chứng.
- `interaction_not_isolated` — bằng chứng chỉ tới tương tác, chưa tách được tầng.

**Map features** (một lần mỗi context): bề rộng khe hẹp nhất trên tuyến, mật độ vật cản,
topology, số ngã rẽ.

### 5.2. Chủ thể chịu trách nhiệm — theo thành phần, không theo tên thuật toán

Candidate là cả stack (đề tài §1.4). KB không dùng `candidate_family` mà dùng `subject`:

```
global_planner · local_controller · costmap_inflation · perception_provider
candidate_preprocessing · runtime_transport · task_geometry · preference_constraint
```

Taxonomy **mượn vocabulary ownership của H3/H4** (candidate/deployment/oracle + capability
channel) — không phát minh song song, để claim đối chiếu thẳng với accounting sau H4.

**Ràng buộc H4:** legacy path chưa qua seam provider (H3 mục 4); latency/perception chưa
tách được compute thuộc candidate/deployment/transport. Trước H4: các subject
`perception_provider`, `runtime_transport` chỉ được claim mức `observed` (triệu chứng trần).

### 5.3. KB — nguồn trích có version, không nằm trong weights model

Entry KB có id (`kb:inflation_gap_closure`), điều kiện kích hoạt hẹp, confidence,
version như anchor. Agent cite `kb:*` như cite fact. Cơ chế ngoài KB → agent đề xuất
entry mới → người duyệt nhập. Không match luật nào → hiển thị triệu chứng trần,
**không bịa nguyên nhân** (cùng tinh thần `gateEvidence()` không bịa gì cho chuỗi trần).

**KB là canonical, retrieval không phải.** Khi có tầng RAG (nhóm AI), nó chỉ được trả
**khóa tham chiếu** (entry_id + entry_version + retrieval_score); platform resolve
`review_status`/`source_refs`/`applicability_conditions` từ canonical KB — không bao
giờ tin trường tự khai của retrieval (cùng nguyên tắc allowlist oracle H3: khóa trên
định danh platform kiểm soát, không trên provenance tự khai). Entry lạ/lệch version ⇒
reject; chưa approved ⇒ không promote claim.

## 6. Case packet — input cho analyst

Tầng deterministic dựng hồ sơ; **agent không bao giờ đọc Parquet thô**:

```yaml
task:
  map_features: {narrowest_passage_m: 0.68, obstacle_density: 0.21, topology: corridor_with_side_aisles}
  robot: {width_m: 0.52, inflation_radius_m: 0.11}
candidates:            # FULL STACK, không chỉ tên thuật toán
  A: {global_planner: astar,   local_controller: dwa, params: …, providers: …}
  B: {global_planner: rrtstar, local_controller: dwa, params: …, providers: …}
lattice: "A,B cùng DWA(config_A) — attribution global_planner khả thi; inflation không có cặp đối chứng"
decision: {delta_u_mean_paired: 0.062, ci: […], waterfall: …, label: CLEAR}
gates: {…}                       # ai bị loại ở cổng nào
observations:                    # output detector, có region + episodes n/N
  - {type: detour, candidate: B, region: aisle_B7, extra_distance_m: 11.3, episodes: "27/30"}
  - {type: oscillation, candidate: A, region: junction_C2, duration_s: 2.8, episodes: "9/30"}
representative_episodes: [typical, strongest_for_A, strongest_for_B, safety_critical]
known_unknowns:                  # BẮT BUỘC, có cấu trúc — orchestrator CƯỠNG CHẾ blocker,
  - id: latency_accounting_unavailable          # không chỉ "nhắc agent đọc"
    blocks_claim_types: [candidate_latency_attribution, perception_attribution]
    source: h4_not_complete
  - id: ppo_golden_runtime_missing
    blocks_claim_types: [ppo_behavior_attribution]
    source: h0_debt
evidence_class: production       # fairness lane của run
kb_version: …  anchor_config_version: …
```

Tùy chọn (pha sau): ảnh map đánh dấu vùng, vài frame quanh sự kiện, hai polyline quỹ đạo,
timestamp liên kết replay.

## 7. Agent analyst — vai, ranh giới, vòng kiểm chứng

**Vai:** chuyên gia phân tích lấp khoảng trống giữa "B dừng 8,2 s tại B7" và "cơ chế nào".
Chuỗi phân tích: task condition → observed behavior → metric impact → algorithmic
mechanism → conclusion with confidence. Giá trị thật của LLM nằm ở **tìm kiếm không gian
giả thuyết** (cơ chế × hình học task × config cụ thể) — việc KB luật cứng làm kém vì tổ hợp nổ.

**Bốn ranh giới cứng:**

1. **Agent không tự đóng dấu — tước quyền bằng schema, không bằng validate giá trị.**
   Ba object tách quyền sở hữu: `HypothesisProposal` (output của agent — **không tồn tại**
   trường status/confidence/impact để mà khai); `InvestigationRecord` (orchestrator sở
   hữu: status `proposed/checked/check_failed/not_checkable` + kết quả checker);
   `Claim` (promotion matrix deterministic tạo từ record đạt điều kiện). Impact không
   phải số trong proposal mà là `impact_ref` trỏ tới artifact do tool tạo (ví dụ
   `detour_excision`) — để trường `{delta, method}` trong schema của model thì model vẫn
   phát minh được số đúng hình dạng.
2. **Menu check đóng, có version.** Agent chọn từ catalog cố định
   (`gap_vs_footprint(region)`, `replay_global_plan(costmap, query)`,
   `latency_vs_expanded_nodes(window)`, `rrt_convergence(samples)`…) với tham số.
   Không check tự do, không sinh code check. Check chưa có trong menu ⇒ hypothesis đứng
   ở `associated`, không leo lên được — ranh giới năng lực thành thật.
3. **Rerun chẩn đoán vào research lane.** "Giảm inflation, chạy lại cùng seed" = candidate
   khác (`candidate_id` đổi theo params). Mọi run agent kích hoạt mang
   `FairnessPolicy.research()`, artifact tách thư mục, **không bao giờ** vào evaluation
   distribution / card stats — bảo vệ luật tách mẫu G2.
4. **Hai trạm, hòa giải với lập trường "template-first":** trạm *analyst* sinh hypothesis
   (object đứng dưới claim); trạm *render* vẫn template-first đọc từ claim ledger.
   Ledger 100% deterministic-gated. LLM phrasing (nếu bật) qua validator: citation + số
   khớp bảng facts + whitelist động từ theo mức; sửa được thì sửa citation, không sửa chữ.

**Ba object:**

```yaml
hypothesis_proposal:               # TOÀN BỘ những gì agent được trả ra
  hypothesis_statement: "Inflation của B đóng khe B7"
  proposed_subject: costmap_inflation
  supports: [fact:gap_width, fact:required_clearance, event:detour_B7]
  contradicts: []
  missing_evidence: []
  requested_checks: [{check: gap_vs_footprint, args: {region: aisle_B7, candidate: B}},
                     {check: replay_global_plan, args: {candidate: B, context: ctx_017}}]
  recommended_experiments:         # cần run mới → research lane, chờ người duyệt
    - "Giảm inflation_radius B rồi chạy lại cùng seed (candidate mới, research lane)"

investigation_record:              # orchestrator sở hữu — agent không ghi được
  proposal_ref: …
  status: checked
  checker_results:
    - {check: gap_vs_footprint, result: pass, input_provenance: verified_reconstruction}
  impact_ref:                      # tool tạo, không phải model — và phải khai LOẠI impact
    artifact_ref: artifacts/explain/…/impact_detour_excision.json
    impact_kind: observed_contribution   # | attributable_effect_estimate
    objective: time_efficiency
    method: paired_objective_decomposition
  # observed_contribution: objective đóng góp bao nhiêu vào ΔU — KHÔNG nói riêng
  #   mechanism gây ra bao nhiêu. Template: "cơ chế xuất hiện trong các episode mà
  #   time efficiency bất lợi −0,074."
  # attributable_effect_estimate: ước lượng phần DO mechanism — bắt buộc method,
  #   assumptions, uncertainty. Template: "ước lượng cơ chế đóng góp −0,051, theo
  #   phương pháp X." Diễn đạt nhân quả mạnh: chỉ intervention_supported.

claim:                             # promotion matrix tạo, vào ledger
  level: mechanism_verified
  qualifiers: [estimated]          # cho phần impact
  supports: […]  scope: deployment_id
```

`contradicts` / `missing_evidence` / `recommended_*` là phần biến output từ lời kể thành
trạng thái điều tra dở dang — hiển thị được "chưa đủ bằng chứng" có cấu trúc.

**Tính tái lập:** temperature 0, cache theo hash(packet) — cùng packet, cùng hypothesis;
model + prompt version vào manifest như `anchor_config_version`. Hypothesis lưu vào
artifact, render không gọi lại model. LLM chết → panel rơi về tầng claim ledger + template.

## 8. Kiểm chứng cơ chế và can thiệp — ba bậc chi phí

| Bậc | Bản chất | Chi phí | Kết luận được phép |
|---|---|---|---|
| **Replay check** | **reproduction / mechanism check — KHÔNG phải can thiệp**: chạy lại planner trên input đã ghi hoặc dựng lại có kiểm chứng | ≈ 0 | `mechanism_verified` — chỉ khi input provenance đạt chuẩn (dưới) |
| **Component-swap trên lattice** | đọc chéo run đã có giữa candidate chung thành phần | 0 run mới | theo 4 đầu ra contrast graph (§5.1): loại trừ thì rẻ, quy kết chỉ khi swap giữ mọi thứ khác bất biến |
| **Dose–response trên task** | can thiệp thật: map editing theo feature (nới khe 0,68/0,72/0,80/0,90 m) + ΔΔU + CI qua seed + tỷ lệ pattern biến mất | **máy mới** — N5 sinh nhiễu generic, không có "nới đúng khe này" | `intervention_supported`, phạm vi giới hạn |

**Input provenance của replay check.** Sự thật dữ liệu (đã kiểm code): trace Parquet
**không** chứa plan polyline lẫn costmap/query — plans (output) nằm ở episode JSON
(`write_episode`, trường `plans`); **input** tạo ra plan (costmap snapshot, believed
start pose lúc replan, goal/query, provider revisions, dynamic obstacles đã burn vào
grid, planner parameter fingerprint) hiện **không được ghi ở đâu cả**. Hệ quả:

- **So output plan chỉ dùng theo chiều loại bỏ** (đúng triết lý sàng lọc P1): reproduce
  plan trên costmap dựng lại, lệch bytes so với plan đã ghi ⇒ reconstruction chắc chắn
  sai ⇒ `not_checkable`. Khớp bytes ⇒ **không kết luận gì** — nhiều costmap khác nhau
  sinh cùng một path. Refuter, không bao giờ là promoter.
- **Run hiện có**: replay luôn mang `input_provenance: reconstructed`,
  `maximum_supported_level: associated`. Không promote `mechanism_verified` kể cả khi
  output trùng.
- **Run mới** muốn verify được: cần sidecar `PlanningInputEvidence` — file riêng, không
  chạm 3 khóa cứng, nhưng đòi **runner ghi thêm** lúc chạy. Điểm sống còn: sidecar phải
  ghi **mọi planning attempt, kể cả thất bại** — `StackRun.plans` hiện chỉ giữ plan
  thành công, trong khi ca cần giải thích nhất chính là planner trả `no_path`
  ("planner xem khe là không đi qua được"):

  ```yaml
  episode_context_id: …   candidate_id: …
  planning_attempt: 3     simulation_tick: 148
  query: {start_pose: …, goal_pose: …}
  costmap_checksum: …     provider_revision_refs: […]
  planner_fingerprint: …  execution_environment_ref: …   # git SHA / docker digest
  outcome: no_path                 # path | no_path | error
  output_plan_checksum: null       # bắt buộc khi outcome=path, null khi khác
  failure_code: no_global_path     # bắt buộc khi no_path/error
  ```

  Validator: `outcome=path ⇒ có checksum`; `no_path/error ⇒ checksum null + có
  failure_code`; `planning_attempt` liên tục, duy nhất trong episode; initial planning
  và **mọi** replan attempt đều có dòng. Replay khớp đủ (costmap hash, query, planner
  fingerprint, environment, outcome/checksum) mới được
  `recorded_or_verified_reconstruction` — mức duy nhất promote `mechanism_verified`.
- Thiếu input, không verify được ⇒ `not_checkable` — **không được âm thầm dựng một thế
  giới gần giống rồi gọi là replay**.

**Checker card — mỗi checker khai trần bằng chứng của nó**, promotion matrix xét
`claim type × checker id/version × result × provenance`, không phải chỉ "check pass":
`latency_vs_expanded_nodes` chứng minh tương quan ⇒ `maximum_claim_level: associated`
dù deterministic; `gap_vs_footprint` mới có trần `mechanism_verified` kèm
`required_input_provenance`.

Dose–response phải **preregister danh sách trục trước khi chạy** (dùng lại nghi thức gate
H1b) — quét nhiều trục × nhiều liều rồi chọn trục "giải thích được" là garden of forking
paths, CI theo seed không chữa được multiplicity.

## 9. Nghiệm thu agent — eval trồng đáp án, gate trước khi lên card

Bộ golden nhỏ: map tổng hợp có nguyên nhân **cài chủ đích** (khe hẹp hơn footprint,
bẫy chữ U cho DWA, sample budget RRT\* cắt thấp…). Chạy thật → packet → agent → đo
precision/recall của hypothesis + tỷ lệ đề xuất check sai chỗ. Ngưỡng đạt mới cho
explanation xuất hiện trên Decision Card; trước đó chỉ nằm ở trang phân tích.
Template render là **baseline vĩnh viễn**: cùng claim set, template cạnh LLM phrasing,
người đọc thật chấm — LLM không thắng rõ thì khỏi ship phần phrasing.

## 10. Thứ tự triển khai

| Bước | Nội dung | Phụ thuộc |
|---|---|---|
| E0 | Contracts nội bộ explanation: schemas + promotion matrix + artifact versioning | không |
| E1 | Waterfall paired ΔU + CI theo thanh + drill-down hai mức | E0 |
| E2 | Audit/merge branch replay + exemplar + progress-sync + regression | E0, branch replay hiện có |
| E3 | Detectors + map features + KB v1 + contrast graph + prevalence | E0 |
| E4 | Case packet + render template + ma trận UI theo kết cục run | E1–E3 |
| E4.5 | Minimal sidecar writer `PlanningInputEvidence` (mọi attempt, kể cả no_path) | neo `AlgorithmHost`; seam chưa ổn ⇒ hoãn sau H4/H6, golden chờ theo |
| E5 | **AI enablement contracts** — AnalysisRequest, ToolCard/ToolRequest/ToolResult, knowledge contract, fixtures, mock, feature flag (plan bản 6: platform không xây AI) | E4 + E4.5 |
| E6 | Tool host + mechanism-check implementations (platform) + gate harness hidden | phối hợp H4/H6 |
| AI1–AI5 | Analyst, RAG, tool integration, calibration, rollout — **plan riêng của nhóm AI**; hidden gate do platform chạy | E5 (mock) |
| Pha 2 | Dose–response map editing, preregistered axes | N5 machinery |

## 11. Rủi ro

- **LLM overclaim** — rủi ro số 1 của cả đề tài ("bị tin quá mức"). Chống bằng §7,
  không thương lượng.
- **KB sai** → giải thích sai tệ hơn không giải thích. Điều kiện kích hoạt hẹp + confidence
  + curated tay + version.
- **Tương quan ≠ nhân quả**: chữ "vì" bị khóa theo thang §2, enforce bằng whitelist động từ.
- **Bẫy số học**: hai mức utility (clip U_R), mean/median — §3.
- **Progress-sync đọc nhầm** — cảnh báo bắt buộc §4.2.
- **Nhiễm evaluation distribution** từ rerun chẩn đoán — research lane §7.3.
- **Multiplicity** trong dose–response — preregister trục §8.

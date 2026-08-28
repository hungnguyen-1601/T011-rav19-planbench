# Khảo sát: thu hẹp AI Analyst về một episode — tái dùng được gì từ bản cũ

**Ngày:** 2026-08-27 · **Loại:** khảo sát — **không đổi một dòng code nào**
**Nguồn:** plan bản 7/8/9 + plan cải thiện bản 6, report thi hành bản 8 và W0–W4,
ba note chạy thật (o4-mini, qwen3, llama3.2; E1–E10), code ở cây chính
(`main` ≈ `tongduyan_updater-cdn`) và worktree `../P-011-analyst`
(nhánh `tongduyan_ai-analyst-ban-8`).
**Dùng cho:** `plans/2026-08-27/ai-analyst-theo-episode.md`

---

## 1. Kết luận ngắn

**Không phải đập đi xây lại.** Toàn bộ tầng "kỷ luật claim" — schema tước quyền,
guard 8 luật, sanitize, runner, budget, cache, harness thống kê, bộ răng — là
**episode-agnostic** và dùng nguyên. Phần **whole-run** thật sự chỉ nằm ở bốn chỗ:
packet builder, exemplar roles, waterfall, và cách `packet_view` đánh index bốn
khối đó. Còn thứ mà hướng mới cần nhất — số liệu theo từng episode — **đã có
sẵn dưới dạng hàm thuần**, chỉ đang bị gấp lại thành tổng theo run trước khi
tới analyst.

Ước lượng: **~70% code tái dùng nguyên, ~20% sửa nhỏ, ~10% viết mới** (packet
theo episode, verdict, prompt biến thể, một endpoint, một panel).

## 2. Vì sao vòng cũ không như mong đợi — đọc từ ba đợt đo

| Quan sát (đã đo) | Ở đâu | Hướng episode trả lời thế nào |
|---|---|---|
| Không arm nào thắng sàn model-free (2/3, rồi 3/6); model chung chung *"khác biệt đến từ global planner"* trong khi sàn nêu cơ chế có tên | `notes/2026-08-26/tongduyan_b1-va-tam-arm-do-that.md`, `…e6-e10-tren-model-local.md` | Packet run là **tổng hợp** (n/N, ΔU trung bình); model không có sự kiện cụ thể nào để bám. Một episode có **sự kiện, mốc thời gian, vùng bản đồ** — đúng thứ prompt cần để cụ thể |
| Thêm M1 làm token gần gấp đôi, chất lượng giữ nguyên; thêm M2 (timeline) kéo xuống 0/9 — timeline chiếm ~40% byte packet | W1.3 đo 15,7 kB → 21 kB; e2 = 0/9 | Packet episode **nhỏ hơn** packet run: không waterfall, không lattice dài, không 30 hàng observation; timeline của **đúng một** episode là dữ liệu chứ không phải phần loãng |
| 3–6 case, `underpowered=True`, McNemar không kết luận được | preregistration `min_cases_for_pass_k = 12` | **Không giải quyết được** (sửa sau rà của An 27-08): ~15 episode từ 6 world là **6 cluster**, không phải 15 mẫu độc lập — cùng map/config/cơ chế trồng/build. Episode-scope chỉ thêm độ tin cậy trong cluster và phép đo detector recall; lực so arm vẫn exploratory |
| Guard drop 8–18 mỗi arm, phần lớn ở citation và draft | A3/W4 | Fact index episode ngắn hơn ⇒ ít ref để dẫn sai; `verdict:*` cho model một mỏ neo tất định |
| Câu hỏi run là "vì sao A hơn B trên 30 episode" — model phải tự quy nạp | prompt a4.0.0 | Câu hỏi episode hẹp hơn: **ai thắng đã tính sẵn**, model chỉ giải thích |

## 3. "Episode đang trỏ vào" — nó sống ở đâu trong UI hôm nay

`apps/web/src/app/decisions/[id]/DecisionDetail.tsx`, component `TracePanel`
(dòng 482):

| State | Dòng | Nghĩa |
|---|---|---|
| `episodeId` | 496 | episode đang chọn (bảng episode, chip exemplar, pager đều đi qua `chooseEpisode` dòng 673) |
| `candidates` | 486 | cặp đang vẽ, winner bên trái, đọc từ `comparison_pair` |
| `syncMode` | 509 | `time` \| `progress` |
| `playback` / `scan` | 526 / 530 | playhead theo giây / theo mét arc-length — **hai state, hai đơn vị** |
| `view.running.by_step[side]` | 598–612 | chuỗi running metrics từng dòng trace, đã fetch ở cả hai mode |

`AgentDock.tsx:79 runOnScreen()` chỉ đọc `run_id` từ route; `ChatContext`
(`routers/agent.py:53`, `lib/agent.ts:58`) chỉ có `run_id` + `task_profile_id`.
**Không có gì mang episode tới bất kỳ AI nào.** Đây là khoảng trống thật sự,
không phải lỗi.

## 4. Dữ liệu theo episode đã có sẵn (cây chính, đã xác minh bằng grep)

| Thứ | Ở đâu | Trạng thái |
|---|---|---|
| **Hàng episode trong report**: `episode_context_id, success, failure_reason, collision_count, min_clearance, travel_time_s, p99_latency_ms, replan_count, episode_decision_utility` | `selection.py:1393 _episode_outcomes`, ghi vào `report.candidates[].episodes[]` | 30 hàng/candidate trên run thật; **`episode_decision_utility` là câu trả lời tất định cho "ai thắng episode này"** — hiệu hai số, không cần LLM |
| Cặp so sánh chính thức `comparison_pair` | `selection.py:949` | có ở 4/34 run thật (chỉ run có xếp hạng) |
| Detector **theo từng episode**: `read_trace → detect_all → tuple[Detection]` với `window: ArcWindow` (mét + giây) | `detectors.py:148/375/409` | có sẵn; chỉ `summarise()` (dòng 252) mới gấp thành `Observation` n/N |
| Running metrics 8 chỉ số, hai đồng hồ, `partial_utility` | `running_metrics.py:237/336/434` | có; API `_running_block` (`decision_service.py:764`) đã dựng `ladder` + `by_step` cho episode đang chọn |
| Điểm phân kỳ: `DivergenceReport.sustained / anchors / earliest` | `replay_sync.py:431/445` | có; đã render thành chip trên UI |
| Plan polyline từng attempt (sidecar) | `decision_service.py:1327 _planned_routes` | có cho run sau E4.5 |
| Bảng detection → cơ chế (6 dòng) | `integration.py:67 DETECTION_HYPOTHESES` | sàn model-free hiện chạy trên `Observation`; đổi đầu vào sang `Detection` là dùng lại được |

## 5. Bảng tái dùng — nhánh analyst (`../P-011-analyst`, 25 module, 6.782 dòng, 398 test)

### 5.1. Dùng nguyên, không sửa (episode-agnostic)

| Module | Vì sao không cần sửa |
|---|---|
| `guard.py` (8 luật) | chỉ đọc `PacketView` (`fact()`, `identifiers`, `blocked_claim_types`) — không biết packet hình gì |
| `sanitize.py` (nhãn C1/C2, detector injection) | thao tác trên chuỗi tên thành phần |
| `runner.py` (declare → tool → revise, `no_progress`, `finalize`) | 0 tham chiếu packet, cầm `PreparedRound` |
| `analyst.py` (engine, `hypothesis_id` content-hash, `RoundCost`, timeout) | 1 tham chiếu (`analysis.catalog`) |
| `prompts.py` — `analyst_schema()`, `prompt_checksum()`, union W4 | nhận **text đã serialize**; chỉ thêm một cặp hằng số mới cho episode |
| `identity.py`, `cache.py`, `features.py`, `budget.py` | checksum/cache/cờ/trần — không biết episode |
| `model_gateway.py`, `stdio_protocol.py`, `stdio_lane.py`, `restricted.py`, `bundle_builder.py` | khối sandbox/freeze, giữ nguyên cho Đường B |
| `harness.py` (Wilson, McNemar, `pass^k`, `failure_table`, `cost_by_class`) | thống kê trên `CaseResult`, không biết case là run hay episode |
| `knowledge_provider.py`, `traits_snapshot.py`, `traits_store/review`, `SqlTraitRepository`, migration 0012 | đọc `packet.candidates` — episode có cùng hai candidate |
| `planbench_agent.provider / factory` (o4-mini, Ollama), `load_provider_keys` | dùng chung Lane 1 |
| Bộ răng `bites` 32 + 28 | chạy lại nguyên, thêm răng mới |

### 5.2. Dùng có sửa nhỏ

| Module | Sửa gì | Cỡ |
|---|---|---|
| `packet_view.py` | thêm `build_episode_view()` dùng chung `Fact`/`PacketView`/alias/traits/knowledge; **bỏ** ba khối waterfall (456–495), gate run-level (437–455), exemplar-role (537–561); **giữ** khối timeline (574–595 — ref đã mang `episode/candidate/clock/mark` đúng vì `episode_context_id` là hash điều kiện, hai candidate dùng chung) | vừa |
| `prompts.py` | `EPISODE_SYSTEM` + `build_episode_user_turn`; `PROMPT_VERSION` → `a5.0.0` (checksum phủ mọi hằng) | nhỏ |
| `routing.py:236 _value_for("packet_episode")` | đang lấy `worst_episode_context_id` của observation **đầu tiên** — đổi thành `packet.episode_context_id` | 1 dòng |
| `round_host.py` — `evidence_for`, `in_process_round` | nhận `EpisodePacket`; tập evidence suy từ episode (có trace + reference_line + timeline; **không** `comparison_pair`/`episode_decision_utility` vì không waterfall) | nhỏ |
| `packet_facts.serve_from_packet` | thêm nhánh cho `EpisodePacket`: `get_episode_observations`, `get_episode_timeline` (đã đòi `candidate_id` khi hai bên chung episode — đúng), `get_known_unknowns`, `get_candidate_contrast` | nhỏ |
| `candidates.generate_candidates` (W2 — arm giúp nhất) | đầu vào là `packet.observations` run-level; thêm adapter nhận `Detection` của episode | nhỏ |
| `integration.reference_analyst` | biến thể `reference_episode_analyst` dùng **cùng** `DETECTION_HYPOTHESES`, đầu vào `Detection`, ref `obs:<type>:<cand>@<episode>` | nhỏ |
| `eval_spec.CaseLabels` / `scoring.py` | case id thêm khóa episode (`<family>-<nnn>/<episode_context_id>`); logic chấm không đổi | nhỏ |
| `preregistration.py` | bản mới cho episode (checksum mới, không sửa bản cũ): thêm hard constraint `verdict_contradictions = 0` | nhỏ |
| `run_analyst_experiments.py` | `--scope episode`; arm mới | nhỏ |
| `packet_builder.timeline_from_trace` | đã tách ở W1.2 đúng để gọi cho một episode bất kỳ; chỉ nới `role` (str tự do) thành `"selected"` và thêm mốc playhead/phân kỳ | nhỏ |
| `EpisodeTimeline` / `TimelinePoint` / `CandidateMeasurements` / `MeasuredValue` | dùng nguyên model; `EpisodePacket` là model **mới** chứa chúng, không nhồi vào `CasePacket` (validator của nó đòi waterfall khi có exemplar, và scope khác) | — |
| `ChatContext` (API + web) | thêm `episode_context_id`; `_resolve_context` tra episode có trong run | nhỏ |
| `agent tools registry` (11 tool run-level) | thêm `get_episode_verdict` (tất định) để dock trả lời "ai thắng episode này" qua tool, không bịa | nhỏ |

### 5.3. Không dùng cho hướng này (giữ nguyên cho Lane 2 run-level)

| Thứ | Lý do |
|---|---|
| `waterfall.py`, `exemplars.py` (chọn 4 vai), `packet_builder.build_scoring_packet`, `timelines_from_traces` | phân rã ΔU tập và chọn episode **ra khỏi** run — episode đã được người dùng chọn rồi |
| Khối waterfall/gate/exemplar trong `packet_view` | facts scope `pair:<a>|<b>` trên `n_episodes` — vô nghĩa cho một episode |
| `get_objective_decomposition`, `find_exemplar_episodes` (card) | đòi waterfall/pair — bị `evidence_for` gỡ khỏi menu tự động |
| `router_eval.py` (E10), `outcome.py` 7 luật Lane 1 | run-level; không chặn, để sau |
| Preregistration bản 1 (checksum `17354118…`) | định nghĩa trên 6 họ × case = run; giữ nguyên, viết bản 2 |

## 6. Ba ràng buộc cấu trúc sẽ cắn (ghi trước để không phải dò lại)

1. **`episode_context_id` là hash của điều kiện** ⇒ hai candidate của một so sánh
   **dùng chung** id. Mọi ref theo episode phải mang candidate
   (`episode:<id>/<cand>/…`); `PacketView` từ chối ref trùng và đổ cả view.
2. **`episode_decision_utility` là mức episode**, lệch card ở `U_R` (clip) —
   dùng đúng số đã lưu, **không** tính lại, và không trung bình nó thành số
   card. Candidate bị loại ở cổng **không có** hàng ⇒ verdict phải có nhánh
   "chỉ so kết cục", không đặt 0.
3. **Một episode không có CI.** Verdict episode là một mẫu; nó không được lên
   Decision Card và phải mang cảnh báo cố định kiểu `PROGRESS_SYNC_WARNING`
   (field một giá trị hợp lệ, không viết lại được).

## 7. Trạng thái nhánh — quyết định trước khi code

- `tongduyan_ai-analyst-ban-8`: **42 commit chưa merge**, HEAD `7de4610`,
  worktree `E:/VinAI/RoboMind_project/P-011-analyst`, cây sạch.
- `git merge-tree --write-tree main tongduyan_ai-analyst-ban-8`: **merge sạch,
  0 file chạm cả hai phía** (10 commit trên `main` từ base `738ee1f` đều là
  updater/UI/release).
- DB thật `P-011/planbench.db` **chưa chạy migration 0012** (traits); P1–P4 của
  plan mới không cần traits, P5 thì cần nếu bật arm traits.
- 17/34 run thật có `case_packet` (nhúng trong `comparison_report.json` dưới
  `case_packet.packet`), **4 run có `comparison_pair`** — chỉ 4 run này có
  winner chính thức và exemplar; 13 run còn lại chỉ có kết cục theo episode.

## 8. Việc đã xác minh bằng tay (không tin báo cáo agent)

`grep -n` trên cả hai cây cho mọi dòng được trích ở §4–§5 (`Detection:148`,
`summarise:252`, `detect_all:409`, `DETECTION_HYPOTHESES:67`,
`reference_analyst:340`, `_running_block:764`, `ChatContext:53`,
`episodeId:496`, `syncMode:509`, `playback:526`, `scan:530`,
`_value_for("packet_episode"):236`, `timeline_from_trace:439`,
`TIMELINE_ROLES:345`, `evidence_for:146`, `in_process_round:282`,
`PROMPT_VERSION a4.0.0:40`, `EXPLANATION_SCHEMA_VERSION 0.2.0:60`,
`TOOL_CATALOG_VERSION 3.4.0:169`, `min_cases_for_pass_k 12:73`) — khớp.
Kích thước packet golden: 6.667–8.100 B, timelines chiếm 2.393/7.693 B ở
`dwa-001`.

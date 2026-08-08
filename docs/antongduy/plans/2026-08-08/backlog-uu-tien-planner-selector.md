# Backlog ưu tiên: Planner Selector — việc cần làm trước mắt

> **Ngày lập:** 2026-08-08 · **Người lập:** An (cùng Claude)
> **Quan hệ với plan tổng:** đây là bản triển khai chi tiết của
> `ke-hoach-chuyen-huong-planner-selector.md` (cùng ngày), bỏ khung thời
> gian 4 tuần, thay bằng **thứ tự ưu tiên theo mức độ lan tỏa**: việc nào
> nhiều thứ khác phụ thuộc vào thì làm trước. Trong một phase, các việc
> làm song song được. Phase sau chỉ bắt đầu khi phase trước xong phần nó
> phụ thuộc.
> **Trạng thái:** chờ approve.

---

## Nguyên tắc xếp hạng

1. **Độ lan tỏa (fan-out):** schema mà mọi tầng tham chiếu > engine trung gian > UI cuối chuỗi. Đề tài mới nói rõ: 4 thứ phải có trong schema từ đầu vì *"thêm sau sẽ phải sửa xuyên suốt"* — `hardware_spec`, `deployment_horizon`, `candidate_id`, `metric_anchors.yaml`.
2. **Độ cứng của hợp đồng:** CONTRACTS khóa 3 thứ không được đổi sau tuần 1 (định danh candidate HĐ-1, episode context HĐ-3, trace schema HĐ-5) → 3 thứ này phải chốt sớm nhất, vì sửa muộn = MAJOR bump + chạy lại lát cắt dọc.
3. **Kiểm chứng sớm:** lát cắt dọc đứng giữa backlog làm van chặn — mọi thứ sau nó chỉ là mở rộng, không còn rủi ro phương pháp luận.

Sơ đồ phụ thuộc tổng:

```
P1 (schema gốc) ──► P2 (đường dữ liệu) ──► P3 (decision core) ──► P4 (lát cắt dọc ✂ van chặn)
                                                                        │
                                              P5 (engine đầy đủ) ◄──────┘
                                              P6 (API + DB)  ◄─ P5
                                              P7 (UI + demo) ◄─ P6
```

---

## Phase 1 — Schema gốc (fan-out cao nhất, mọi tầng phụ thuộc)

Không dòng nào của engine viết được chắc chắn trước khi 3 schema này đóng băng. Sai ở đây = sửa lan khắp repo.

| # | Việc | Vì sao đứng đây | Ảnh hưởng tới | Phụ thuộc |
|---|---|---|---|---|
| 1.1 | **TaskProfile** (`packages/schemas/.../task_profile.py`, HĐ-2): environment/missions/robot/constraints/hardware; `claim_level` computed; thêm `RobotConfig.control_period` nếu thiếu | Nguồn **mọi ngưỡng** trong hệ: 6 gates, anchor `${constraints.*}`, `N_min`, `T_ideal`, goal tolerance. Hardcode tạm rồi gỡ sau = vi phạm HĐ-7 ngay từ đầu | gates, anchors, objectives, metrics, API, UI form | — |
| 1.2 | **Candidate + `candidate_id`** (`packages/decision/.../candidate.py`, HĐ-1): modular/monolithic, hash canonical_json, `experiment_scope` validator fail-at-startup | Khóa cứng #1 của contract. Mọi trace, pairing, ΔU, card tham chiếu id này; đổi cách hash sau = mọi dữ liệu đã ghi mồ côi | trace metadata, contexts, mọi phép so, registry map | — |
| 1.3 | **EpisodeContext + generator** (`packages/benchmark/.../contexts.py`, HĐ-3): `episode_context_id`, vòng ngoài context – vòng trong candidate, `sample_set` | Khóa cứng #2. Luật ghép cặp là *"không được vi phạm trong bất kỳ hoàn cảnh nào"* — mọi thống kê ΔU đứng trên nó | trace, runner, stats, gates (N_eval), Pareto | 1.1 (mission id), 1.2 (chạy theo candidate) |
| 1.4 | **Chốt hợp đồng hành chính:** move `CONTRACTS_1.md` → `contracts/CONTRACTS.md`, bảng map layout §16, bảo lưu sim-only, bump 1.0.1, team ký | Rẻ (nửa ngày) nhưng mở khóa việc cả nhóm code theo cùng luật; càng để lâu càng nhiều code viết ngoài hợp đồng | quy trình cả nhóm | — |

**DoD phase:** 3 schema có test round-trip + hash ổn định; contract đã ký. Sau phase này 1.1–1.3 coi như đóng băng (đổi = MAJOR).

## Phase 2 — Đường dữ liệu (trace là nguồn sự thật duy nhất)

Khóa cứng #3 (trace schema) nằm ở đây. Metrics Engine mới chỉ được ăn trace — quyết định này định hình mọi thứ phía sau.

| # | Việc | Vì sao đứng đây | Ảnh hưởng tới | Phụ thuộc |
|---|---|---|---|---|
| 2.1 | **TraceRecorder Parquet** (HĐ-5): đúng cột + metadata; `clearance_m` tính lúc ghi; `peak_rss_mb`, `cpu_time_s`; ghi `artifacts/runs/` | Khóa cứng #3. Mọi metric, gate, objective tính từ file này; thiếu cột nào là phải chạy lại toàn bộ episode | definitions.py, gates, manifest, replay bằng chứng | 1.2, 1.3 (metadata) |
| 2.2 | **Map loader PGM/YAML** (`map_server` format) | HĐ-2 bắt buộc định dạng này; không có thì TaskProfile không nạp được map thật — chặn mọi demo | TaskProfile, scenario editor, demo | — (song song 2.1) |
| 2.3 | **`metrics/definitions.py`** (HĐ-6): `L_ref` Dijkstra theo context, `path_efficiency` mới, `time_efficiency`, `p99_latency_ms`, `success` theo tolerance; input duy nhất = trace + TaskProfile | Nơi *duy nhất* định nghĩa metric — mọi metric thêm ngoài đây là vi phạm DoD của mọi PR sau. `L_ref` còn là bài test tự chứng minh (≤ path_length) | objectives, gates, anchors | 2.1, 1.1 |

**DoD phase:** chạy 1 episode → 1 file Parquet → tính lại đủ bảng metric HĐ-6 từ file, không đụng dữ liệu in-memory; test `L_ref ≤ path_length_m`.

## Phase 3 — Decision core (tính mới của đề tài, thuần hàm, dễ test)

Toàn bộ pure function trên output của Phase 2 — viết và test được bằng trace giả lập **ngay khi schema Phase 1 xong**, không cần đợi 2.1 chạy thật (chỉ nghiệm thu cuối là cần). Đây là chỗ tranh thủ song song.

Thứ tự trong phase (theo chuỗi phụ thuộc nội bộ):

| # | Việc | Vì sao thứ tự này | Phụ thuộc |
|---|---|---|---|
| 3.1 | **Anchors + `u()`** (HĐ-8): loader `metric_anchors.yaml`, resolve `${...}`, cấm số cứng ở `bad` có cổng | Objectives không tính được khi chưa có chuẩn hóa; file anchor cần version ngay để manifest tham chiếu | 1.1 |
| 3.2 | **Gates G1–G6** (HĐ-7): ngưỡng từ TaskProfile, `N_min = ceil(3/p_max)`, chuỗi báo cáo bắt buộc, `screened_on_host` cố định, CI test cấm "an toàn"/"TCO" | Đứng trước scoring trong pipeline; độc lập với 3.1 nên song song được | 1.1, 2.3 |
| 3.3 | **Objectives + Decision Utility** (HĐ-9): U_R/S/E/C theo từng episode, 4 preference profile, `travel_time_accounting` validator | Cần 3.1; per-episode là điều kiện tiên quyết của 3.4 | 3.1 |
| 3.4 | **Paired bootstrap ΔU + nhãn** (HĐ-11): resample theo context, CLEAR/NEAR_EQUIVALENT, tie-break 4 bậc, từ chối khi tập context lệch | Trái tim của "khuyến nghị dám chịu trách nhiệm"; mọi nhãn tin cậy đi ra từ đây | 3.3, 1.3 |
| 3.5 | **Decision Card + Manifest** (HĐ-12/13): JSON đúng schema, git_sha, anchor version, tập context id | Điểm hội tụ — output cuối mà mọi tầng trên phục vụ | 3.2–3.4 |

**DoD phase:** unit test từng module với trace giả lập; card JSON validate được bằng schema trong `contracts/schemas/`.

## Phase 4 — Lát cắt dọc ✂ van chặn phương pháp luận (HĐ-15)

Một việc duy nhất, ưu tiên tuyệt đối ngay khi Phase 2+3 đủ ghép:

- `scripts/vertical_slice.py`: 1 map · 1 mission · 2 candidate (`astar+dwa` vs `rrtstar+dwa`, cùng local config → `global_planner_selection`) · 50 episode ghép cặp → trace → metrics → gates → objectives → utility → CI ΔU → Decision Card.
- **Nghiệm thu đúng 5 tiêu chí HĐ-15.1** (cùng tập context bằng assert; tái lập 6 chữ số; đủ 6 cổng kèm N; CI không NaN; `L_ref ≤ path_length`).

**Vì sao là van chặn:** mọi thứ sau phase này (Pareto, sensitivity, API, UI) chỉ *mở rộng* chứ không *thay đổi* phương pháp luận. Giả định sai (metric toàn 0, hai candidate giống hệt, L_ref lệch) chỉ lộ khi chạy — phát hiện ở đây rẻ, phát hiện ở UI đắt. Sau phase này: không sửa phương pháp luận nữa (HĐ-15.2).

## Phase 5 — Engine đầy đủ (mở rộng trên nền đã kiểm chứng)

| # | Việc | Vì sao trước/sau trong phase | Phụ thuộc |
|---|---|---|---|
| 5.1 | **Evaluation distribution + N_min thật**: generator mission × obstacle realization × seed; chạy N ≥ 300; `instance_difficulty` (P03 cũ) chọn số episode | Cần trước Pareto/sensitivity để số liệu có nghĩa thống kê; G2 chỉ hợp lệ trên bộ này | P4 |
| 5.2 | **Pareto non-inferiority** (HĐ-10): `LCB₉₅(ΔU_j) ≥ −ε`, 3 nhãn, không xóa candidate; `alternative` chỉ từ frontier | Đứng trước sensitivity vì nhãn Pareto đi vào card mà sensitivity quét trên card | 5.1 |
| 5.3 | **Sensitivity**: `weight_stability_margin` + `anchor_stability` ±10% | Điểm bán chính N1 nhưng chỉ quét lại utility đã có — không đụng sim, rẻ, làm cuối engine | 5.2 |

## Phase 6 — API + lưu trữ (nối vào hạ tầng sẵn có)

| # | Việc | Ghi chú |
|---|---|---|
| 6.1 | Migration: bảng `task_profiles`, `candidates`, `decision_cards` (URI + checksum, file lớn ở `artifacts/runs/` theo D15) | Trước router |
| 6.2 | Router: `POST/GET /task-profiles`, `POST /candidates` (kèm khai tuning cost + bằng chứng log), `POST/GET /decisions` chạy qua worker sẵn có | Tái dùng repository pattern + background job hiện tại |
| 6.3 | Nối **Approval sẵn có** (HĐ-14): card APPROVED → `approved_config.yaml`; giữ chống tự duyệt, audit append-only | Gần miễn phí — F10/F11 đã chạy thật |

## Phase 7 — UI + demo (cuối chuỗi, không ai phụ thuộc)

| # | Việc | Ghi chú |
|---|---|---|
| 7.1 | Trang `/decisions`: Decision Card (tên lớn, nhãn, scope, alternative, evidence), bảng cổng "ai bị loại ở đâu, sau bao nhiêu lần chạy" | Dữ liệu demo đắt nhất: K4 nhanh nhất vẫn bị loại |
| 7.2 | Waterfall phân rã utility + slider trọng số re-rank client-side (recharts sẵn) | Cần API trả per-episode objectives |
| 7.3 | Form TaskProfile (tái dùng Scenario Editor) + form đăng ký candidate | |
| 7.4 | Demo K1–K4 (§6.2 đề tài) + lật khuyến nghị theo horizon + rà bảng ngôn ngữ 9.2 + nghiệm thu manifest HĐ-13 | Chốt sản phẩm |

---

## Bảng tra nhanh: việc → mở khóa những gì

| Việc | Mở khóa trực tiếp |
|---|---|
| 1.1 TaskProfile | 1.3, 2.3, 3.1, 3.2, 6.2, 7.3 |
| 1.2 Candidate id | 1.3, 2.1, mọi phép so |
| 1.3 EpisodeContext | 2.1, 3.4, 5.1 |
| 2.1 Trace Parquet | 2.3, nghiệm thu P4 |
| 2.3 definitions.py | 3.2, 3.3 |
| 3.x decision core | P4 |
| P4 lát cắt dọc | **đóng băng phương pháp luận** → P5–P7 an toàn |
| 5.1 eval distribution | 5.2, 5.3, gate G2 hợp lệ |
| 6.x API | 7.x UI |

## Việc cố tình KHÔNG đưa vào backlog trước mắt

MissionSampler L2 · racing/Adaptive Scheduler (N9 — episode 2D rẻ, chưa cần) · Task Neighborhood K=20 · Target Verifier (không có board) · `monetized_cost`/What-if đầy đủ · `trials_to_90` · di trú metric cũ sang tên mới (giữ song song, decision layer chỉ đọc `definitions.py`).

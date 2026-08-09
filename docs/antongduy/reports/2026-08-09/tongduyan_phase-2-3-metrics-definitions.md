# Báo cáo — Phase 2.3: `metrics/definitions.py` + `L_ref` (HĐ-6)

> **Ngày:** 2026-08-09
> **Plan nguồn:** `docs/antongduy/plans/2026-08-08/backlog-uu-tien-planner-selector.md`, mục **2.3**
> **Nhánh:** `plannerselector_p2`
> **Contract:** không đổi — vẫn `2.0.0`.
> **Kết quả:** Phase 2 **xong toàn bộ**. Mọi metric HĐ-6 tính lại được **chỉ từ** trace + TaskProfile.

---

## 1. Hai file mới

| File | Vai |
|---|---|
| `packages/metrics/planbench_metrics/reference_path.py` | `L_ref` — độ dài đường ngắn nhất Dijkstra theo từng context, có cache |
| `packages/metrics/planbench_metrics/definitions.py` | **Nơi duy nhất** một metric được định nghĩa (HĐ-6) |

Cả hai đặt cạnh `episode_metrics.py` cũ, **không** di trú tên cũ — đúng như backlog
chốt. Tầng decision đọc `definitions.py` và không đọc gì khác.

## 2. `L_ref` — chỗ suýt sai, và bằng chứng số

Định nghĩa HĐ-6 chỉ nói "đường ngắn nhất Dijkstra trên grid của chính context đó".
Hiện thực thẳng theo câu đó **cho ra một reference sai**, và may là đo được ngay:

| Cách tính | Trên mission tham chiếu (2,3) → (38,21) của `warehouse_a` |
|---|---:|
| Dijkstra 8-hướng, lấy thẳng cost lưới | **47,8 m** |
| Dijkstra + string-pull (line-of-sight) | **45,4 m** |
| A\* trên grid đã inflate (đường candidate thật plan) | **46,1 m** |

Lấy 47,8 làm `L_ref` thì `path_efficiency = 47,8/46,1 = 1,04` — candidate "vượt tối
ưu", thang anchor [0,1] của HĐ-8 vỡ, và tiêu chí nghiệm thu HĐ-15.1 #5
(`L_ref ≤ path_length_m`) **fail ngay episode đầu tiên** của chính deployment tham
chiếu. Nguyên nhân: metric lưới 8-hướng phóng đại đường liên tục tới ~8% ở đoạn
chéo.

Sửa: reconstruct đường ô rồi **string-pull bằng đúng `simplify_path`** mà planner
dùng, trên cùng grid, rồi mới đo. 45,4 < 46,1 ✓.

**Ba quyết định khác được ghi thẳng vào docstring vì chúng định nghĩa ý nghĩa của
mọi tỷ số hiệu quả trong hệ:**

1. **Chạy trên grid *thô*, không inflate theo bán kính robot.** Reference phải là
   **cận dưới**. Inflate theo ô là phép xấp xỉ thô hơn phép kiểm va chạm thật của
   simulator, nên reference inflate có thể **dài hơn** đường robot thật sự đã đi —
   một reference mà candidate đánh bại được thì không còn là reference.
2. **Dijkstra, không dùng lại A\* của candidate.** Nếu reference sinh ra từ đúng
   hiện thực (đúng tie-break, đúng heuristic) mà một candidate đang chạy thì
   candidate đó đang được chấm với chính nó.
3. **Ô unknown tính là chặn.** Đường tham chiếu đi tắt qua vùng chưa khảo sát sẽ
   làm mọi candidate trông tệ hơn thực tế.

Cache theo (map, ô start, ô goal): 1 context chạy 1 lần cho mỗi candidate và 300+
lần mỗi bộ evaluation, mà đáp án không phụ thuộc cái nào trong đó. Đo trên
`warehouse_a`: **4,3 s** lần đầu (Dijkstra 400k ô + string-pull), **0 s** sau đó.

## 3. `definitions.py`

`compute_metrics(trace, profile, context, map_data, *, resource_profile=None)`
→ `EpisodeMetricSet` gồm **đủ** các metric HĐ-6, tên đặt đúng như bảng contract để
đọc song song được. Vai (Gate/Score/Diagnostic) **không** lưu ở đây — nó thuộc về
gates và objectives tiêu thụ metric; lưu hai nơi là có hai chỗ để bất đồng.

**Ngưỡng đều đọc từ profile**, không có hằng số nào: `goal_tolerance_m/rad`,
`clearance_warning_m`, `v_max`. Một hằng số ở module này là một ngưỡng không ai
khai — đúng vi phạm HĐ-7 mà gates sinh ra để chặn.

Bốn điểm phải quyết trong lúc viết:

**`success` và bằng chứng mâu thuẫn.** `success = goal_reached ∧ ¬collision ∧
¬timeout` *theo tolerance của profile*. Nên phải đối chiếu event `goal_reached`
với hình học. Bất đồng chỉ là lỗi **theo một chiều**:
- *khai tới đích nhưng pose ngoài tolerance* ⇒ **từ chối**: episode đã được phán
  xử bằng một ngưỡng khác ngưỡng profile khai (ngưỡng hardcode, HĐ-7 cấm), và
  success rate đó không ai dựng lại được từ dữ liệu đã lưu;
- *pose trong tolerance nhưng không khai* ⇒ **hợp lệ**: robot timeout khi đang
  đứng cạnh đích là chuyện thường. Phán quyết của run được giữ; trôi vào trong
  tolerance không phải là đã tới.

**`near_miss_rate` khi robot không di chuyển.** Mẫu số bằng 0. Trả 0.0 sẽ chấm
"đứng yên" là an toàn tuyệt đối. Nên: có near-miss thì trải count lên 1 mét (cách
đọc bi quan nhất mà dữ liệu cho phép — chiều đúng cho một metric an toàn).

**`smoothness` và vòng ±π.** Không normalize thì robot đi thẳng vượt qua ±π một
lần cộng thêm ~39 rad² "gồ ghề". Đã normalize; có test.

**`memory_estimate_mb`** hiện thực đúng công thức HĐ-7.3 cho cả `structural`
(bộ đếm sim × byte của **hiện thực đích**) và `artifact` (model + runtime).
`resource_profile` là tham số **tùy chọn**: thiếu thì trả `None`, không phải 0 —
0 đọc thành "vừa mọi ngân sách", `None` nói thẳng G5 chưa có gì để phán.
Không bao giờ suy từ `peak_rss_mb` (§17 cấm 13); có test khẳng định hai số khác nhau.

## 4. Một phát hiện về manifest (HĐ-13) — cần nhớ cho Phase 6

Metadata HĐ-5 lưu **hash** của context, không lưu `mission_id`, và hash không đảo
ngược được. Nên `compute_metrics` phải nhận `EpisodeContext`. Runner có sẵn nó;
nhưng một lần **tính lại metric từ thư mục trace** (đúng thứ HĐ-5 hứa) chỉ làm
được nếu manifest lưu **bản ghi context đầy đủ**, không phải chỉ danh sách id như
HĐ-13 đang viết. Không sửa contract lần này (ghi lại để quyết ở Phase 6.1 cùng lúc
với migration); đã ghi vào docstring của `compute_metrics`.

## 5. Test — `tests/test_metric_definitions.py` (29 test)

| Nhóm | Nội dung |
|---|---|
| `TestReferencePath` | phòng trống ⇒ reference = đường thẳng (không phải cầu thang lưới) · vòng qua cửa dài hơn · goal không tới được ⇒ `None` · pose ngoài map / trên ô chặn ⇒ từ chối · cache |
| `TestEfficiency` | run hoàn hảo ⇒ 1,0 và `L_ref ≤ path_length` · run vòng vèo ⇒ 0,5 · `T_ideal` dùng `v_max` **của profile** · robot không nhúc nhích ⇒ 0,0 chứ không phải vô cực |
| `TestSuccessAndFailure` | 3 điều kiện của success · collision thắng timeout · tới đích mà có va chạm ⇒ không success · khai đích từ 2 m ⇒ từ chối · heading ngoài tolerance · đứng cạnh đích lúc timeout ⇒ không phải arrival |
| `TestSafetyAndDiagnostics` | near-miss theo ngưỡng khai báo, tính trên mét · smoothness qua vòng ±π · stop-and-go bỏ lần đứng yên đầu · p99 từ cột trace |
| `TestMemoryEstimate` | công thức structural tính tay · artifact · **không** bằng `peak_rss_mb` · thiếu profile ⇒ `None` |
| `TestRefusals` | trace chấm nhầm context · profile không có mission đó · mission không có tuyến ⇒ không quote tỷ số · `EpisodeMetricSet` cấm field lạ (metric định nghĩa ngoài module này = vi phạm DoD HĐ-15.3) |

Full suite: `pytest tests/ -q` → **1667 passed, 6 skipped** (9 phút 00). Baseline
sau Phase 2.2 là 1638 — thêm đúng 29 test, **không vỡ test nào**. `ruff check` và
`ruff format --check` sạch toàn repo.

## 6. Chưa làm — cố ý

- **Chưa nối vào runner.** Vẫn là việc của lát cắt dọc (Phase 4): ở đó mới có đủ
  hai candidate chạy cùng tập context để nghiệm thu 6 tiêu chí HĐ-15.1 bằng số.
- **`tuning_trials_used`, `tuning_wall_clock_h`, `n_tunable_params`** — HĐ-6 xếp
  chúng vào "khai lúc đăng ký candidate", không tính từ trace được. Chỗ của chúng
  là objective O4 (Phase 3.3), không phải module này.
- **`jerk`** — HĐ-6 không liệt kê ở MVP; thêm vào là sửa contract (MAJOR).

## 7. Trạng thái Phase 2 — đóng

| Mục | Trạng thái |
|---|---|
| 2.1 TraceRecorder Parquet (HĐ-5) | ✅ |
| 2.2 Map loader PGM/YAML | ✅ |
| 2.3 `metrics/definitions.py` (HĐ-6) | ✅ |

DoD của phase theo backlog — *"chạy 1 episode → 1 file Parquet → tính lại đủ bảng
metric HĐ-6 từ file, không đụng dữ liệu in-memory; test `L_ref ≤ path_length_m`"* —
đạt: `test_trace.py::TestRealEpisode` chạy episode thật ra file, và
`test_metric_definitions.py` tính lại mọi metric chỉ từ file đã đọc lên, kèm
assert `L_ref ≤ path_length_m`.

Tiếp theo: **Phase 3 — decision core** (3.1 anchors + `u()`, 3.2 gates G1–G6),
viết và test được bằng trace giả lập, không cần đợi chạy thật.

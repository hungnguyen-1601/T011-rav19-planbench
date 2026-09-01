# Báo cáo đánh giá hiện trạng — PlanBench (đối chiếu phan-tich-de-bai-benchmark-planning.md)

> **Phạm vi:** đánh giá khắt khe code hiện có (sản phẩm vibe-code của Codex) so với đề bài phân tích. Đã đọc trực tiếp code (không chỉ tên file), grep toàn repo cho từng hạng mục, đối chiếu `docs/IMPLEMENTATION_STATUS.md` và `docs/KNOWN_LIMITATIONS.md` (hai file tự đánh giá khá thẳng thắn do chính tác giả/Codex viết).
> **Kết luận một câu:** hạ tầng kỹ thuật (sim core, planner thật, API, RBAC, ROS2, RL, LLM agent) làm khá tốt và thật (không phải stub giả). Nhưng **toàn bộ nhóm P01–P05 — phần đề bài gọi là "differentiator cốt lõi", rẻ nhất để làm, tuyệt đối không được cắt — bị bỏ trắng 5/5.** Dự án hiện là "PathBench/Arena bản nhỏ" đúng như rủi ro mà chính đề bài cảnh báo ở mục 11, chưa phải là nền tảng "giao thức đánh giá đáng tin".

---

## 1. Kiến trúc 4 hợp đồng (contract-first) — mục 9.1

| Hợp đồng | Trạng thái | Ghi chú |
|---|---|---|
| `GlobalPlanner` | ✅ Có thật | `packages/planning/.../common/base.py:31-42`, ABC đúng chữ ký `plan(grid, start, goal)`. Dùng `OccupancyGrid` cụ thể thay vì `Costmap2D` tổng quát — lệch nhẹ so với spec. |
| `LocalPlanner` | ✅ Có thật | `common/local_base.py`, `compute(state, observation)`. |
| `SimBackend` | 🟡 Tương đương chức năng, không cùng hình dạng | `services/simulator/.../engine.py` (`SimulationEngine`) làm đủ việc (`load_map→load_scenario→reset→step`) nhưng **không có `get_costmap()`**, không phải Protocol đặt tên `SimBackend`. |
| `TraceRecorder` | ❌ Không tồn tại như một hợp đồng riêng | Ghi trace nằm cứng trong `engine.py`, không tách interface có thể thay thế được. |

**Nhận xét:** nguyên tắc "MVP là tập con của full, không đập đi xây lại" (mục 9.1) chưa được hiện thực đúng tinh thần — 2/4 hợp đồng thiếu hoặc lệch, nghĩa là khi lên ROS2/Gazebo (pha 3) sẽ phải sửa nhiều hơn dự tính ban đầu ở phần ghi trace và costmap.

---

## 2. MVP — F01–F12 (mục 7.1)

| ID | Tính năng | Trạng thái | Bằng chứng |
|---|---|---|---|
| F01 | Map Loader PGM/PNG+YAML (định dạng ROS map_server) | ❌ **Thiếu** | Có schema `MapData` đúng convention ROS, nhưng **không có code parse file PGM/PNG hay YAML** (`resolution/origin/negate/occupied_thresh`) ở đâu cả. Map chỉ được dựng bằng code (`_MapBuilder`) hoặc gửi JSON qua API. |
| F02 | Scenario Spec YAML | 🟡 Một phần | Pydantic schema đầy đủ trường, nhưng tiêu thụ qua JSON/API, không có (de)serializer YAML độc lập. |
| F03 | Simulator core 2D | ✅ Xong | Vòng lặp rời rạc thời gian, động học differential-drive Euler tường minh, va chạm thật (grid + hình học). |
| F04 | Planner Registry ≥2 thuật toán, A*+DWA, RRT* thứ 3 | 🟡 Một phần | A* thật (heapq, tie-break xác định), DWA thật (rollout numpy, 6 cost term). **RRT* hoàn toàn không có** (`grep rrt` = 0 kết quả) — thay bằng `astar+ppo` (RL). Đạt tối thiểu "≥2 thuật toán" nhưng không đúng thuật toán thứ 3 spec yêu cầu. |
| F05 | Metrics Engine đủ 5 nhóm | 🟡 Một phần, có sai công thức | Có thật: path length, path efficiency, smoothness, clearance, tốc độ, planning time, latency, expanded nodes, collision. Nhưng: **smoothness dùng Σ|Δθ|/length thay vì Σ(Δθ)² như spec** (mục 8.2); **không có p50/p95/p99** — chỉ mean/max (spec mục 8.3 nhấn mạnh p99 quan trọng hơn mean, đây là điểm bị nói rõ trong đề bài mà code bỏ qua); **không có peak memory**; **không có stop-and-go count**. |
| F06 | Batch Runner | 🟡 Chạy tuần tự, không song song thật | `runner.py` chạy được scenarios×algorithms×seeds headless, nhưng vòng lặp episode bên trong hoàn toàn tuần tự. Song song chỉ có ở mức nhiều benchmark job (ThreadPoolExecutor), không phải nhiều episode. |
| F07 | Experiment Tracking (MLflow) | ✅ Có thật, chưa test sống | Tích hợp MLflow thật (log params/metrics/tags/artifacts theo seed), có fallback NullTracker. **Thiếu git SHA** (spec yêu cầu rõ). Tự nhận chưa từng chạy với MLflow server thật. |
| F08 | Web UI Trajectory Viewer | 🟡 Một phần | Canvas 2D thật, có test unit hình học. Nhưng **replay chỉ hiện khung cuối, chưa tua thời gian** (đúng yêu cầu spec là phải tua được); chướng ngại động không được vẽ dù dữ liệu có ghi lại. |
| F09 | Comparison Report (bảng+biểu đồ, xuất MD/PDF) | 🟡/❌ Thiếu phần xuất | Có bảng so sánh trên web. **Không có thư viện biểu đồ nào** (không recharts/d3/chart.js). **Không có chức năng xuất Markdown/PDF nào** — grep không ra route hay hàm export nào. |
| F10 | RBAC 2 vai trò | ✅ Xong (vượt yêu cầu) | 3 vai trò thật: OPERATOR/REVIEWER/ADMIN, enforce qua `require_roles()`. |
| F11 | Approval Workflow | ✅ Xong, làm tốt | State machine 11 trạng thái, `ApprovalRecord` đầy đủ audit, **có enforce chống tự-phê-duyệt** (`ALLOW_SELF_APPROVAL=False`) — đúng tinh thần "separation of duties" của spec. |
| F12 | Docker Compose 1 lệnh | 🟡 Viết đúng, **chưa từng chạy thử** | File compose có 4 service, healthcheck, depends_on đúng thứ tự. Nhưng tác giả tự thừa nhận trong `KNOWN_LIMITATIONS.md`: chưa build image nào, chưa `docker compose up` lần nào, chỉ kiểm bằng parse YAML. **Không có bằng chứng nào là stack thực sự chạy được end-to-end.** |

**Tóm MVP:** 3/12 xong thật (F03, F10, F11), 6/12 một phần với thiếu sót cụ thể (F02, F04, F05, F06, F08, F09/F07/F12 dạng "viết ra nhưng chưa/không đủ kiểm chứng"), 1/12 thiếu hẳn (F01). Chưa đạt mức "demo end-to-end thô" một cách có kiểm chứng như mốc tuần 4 yêu cầu (mục 10) vì Docker Compose chưa chạy thử.

---

## 3. Pha 2 — F13–F17 (Should-have)

| ID | Trạng thái | Ghi chú |
|---|---|---|
| F13 Dynamic obstacles / social force | 🟡 | 4 mô hình chuyển động thật (waypoint/periodic/random-walk/sudden-stop), xác định theo seed — thiết kế tốt. Nhưng **không có Social Force Model** như spec nêu tên. |
| F14 Scenario Pack | 🟡 | 10 kịch bản có sẵn (open_space, corridor, doorway, intersection, dynamic_warehouse...) nhưng không có "maze" hay "dead-end" đúng tên. |
| F15 Leaderboard định lượng | 🟡 | Xếp hạng theo `conditions_checksum`, công thức trọng số minh bạch — thiết kế tốt cho phần *công bằng điều kiện*, nhưng **không có CI, không kiểm định thống kê** (vì P04 chưa có) — chỉ là điểm trung bình đơn thuần. |
| F16 Parallel execution | ❌ | Không có multiprocessing/Ray. Chỉ ThreadPool ở mức job, episode vẫn tuần tự. |
| F17 Regression guard | ❌ | Không có code nào. |

---

## 4. Pha 3 — F18–F23 (Could-have)

Đầu tư nặng nhất của dự án lại rơi vào nhóm này — nghịch với khuyến nghị roadmap của spec (pha 3 chỉ nên làm "sau khóa học").

| ID | Trạng thái | Ghi chú |
|---|---|---|
| F18 ROS2/Nav2 backend | 🟢 Thật hơn kỳ vọng | 5 package ROS2 thật: msgs, bridge, simulator_node (publish /map /scan /odom /tf /cmd_vel), nav2_bringup, benchmark_runner_node gửi NavigateToPose. Nhưng: chưa test với obstacle động, **chưa nối vào FastAPI orchestrator** (chạy tay bằng `ros2 run`), không có test tự động cho tầng ROS. |
| F19 RL planner (PyTorch/Gymnasium) | 🟡 Pipeline thật, model rỗng | Env/observation/reward/policy/training thật (SB3 PPO, versioned). **Nhưng checkpoint duy nhất là "smoke test" 4096 bước, success_rate 0.00** — có gắn cờ `is_smoke_test=true` nên không tự lừa, nhưng bất kỳ số liệu `astar+ppo` nào hiện tại đều vô nghĩa. |
| F20 2.5D elevation | 🟢 Xong, nhưng khác công nghệ đã công bố | Renderer Canvas 2D thật, 23 unit test, painter's algorithm. **Commit `2e8a993` ghi "Three.js" nhưng code thực tế không dùng Three.js** — sai lệch message commit vs code thật. |
| F21 Optuna auto-tuning | ❌ | 0 tham chiếu `optuna` trong toàn repo. |
| F22 LLM Report Assistant | 🟡 Thiết kế tốt, chưa chạy thật | Provider abstraction, mock xác định, cơ chế chống fabricate citation (`FabricatedCitation`), tool policy READ/WRITE tách biệt, gateway **chủ động không có method điều khiển robot** (thiết kế an toàn tốt). Nhưng chưa gọi provider LLM thật nào ngoài Gemini qua shim tương thích OpenAI. |
| F23 Sensor noise | ❌ | LiDAR raycasting thật (DDA) nhưng không có noise model — tự ghi nhận trong KNOWN_LIMITATIONS. |

---

## 5. Bộ giao thức đánh giá P01–P05 — PHẦN QUAN TRỌNG NHẤT (mục 7.0, 8.6)

Đây là phần đề bài nói rõ: **rẻ nhất để làm, tuyệt đối không được cắt, chính là lý do dự án khác PathBench/Arena/Alyassi**. Kết quả grep toàn repo (`optuna`, `scipy|wilcoxon|bootstrap`, `observation_class`, `difficulty`, `holdout`) là tuyệt đối, không phải lấy mẫu.

| ID | Giao thức | Trạng thái | Bằng chứng |
|---|---|---|---|
| P01 | Cân bằng ngân sách tinh chỉnh (Optuna N trial/planner) | ❌ **Thiếu hoàn toàn** | 0 tham chiếu `optuna`. `PPOHyperparameters` chỉ là config tĩnh hard-code. DWA cũng 7 trọng số hard-code, không log lịch sử tinh chỉnh nào. |
| P02 | Khai báo `observation_class` mỗi planner | ❌ **Thiếu hoàn toàn** | `grep observation_class` chỉ ra trúng chính file đề bài, 0 kết quả trong code. `AlgorithmInfo` trong registry không có trường này. DWA (lidar-only) và PPO (35-dim gồm cả vị trí) thực chất khác lớp quan sát nhưng **không hề được khai báo hay dùng để nhóm leaderboard** — leaderboard chỉ nhóm theo `conditions_checksum` (điều kiện map/scenario/seed), khác hoàn toàn ý nghĩa P02. |
| P03 | Hiệu chuẩn độ khó thực nghiệm = 1 − success_rate(baseline, 30 seed) | ❌ **Thiếu hoàn toàn** | "difficulty" duy nhất tồn tại trong code là `CURRICULUM_ORDER` — một **danh sách thứ tự dễ→khó gán tay** để dạy RL theo curriculum, hoàn toàn không phải số đo thực nghiệm từ tỷ lệ thất bại của baseline. Không có logic chạy baseline 30 seed, không có đường cong `success_rate(difficulty)`. |
| P04 | Thống kê chặt (≥30 seed, median+IQR, bootstrap 1000×, Wilcoxon+effect size, rank score) | ❌ **Thiếu hoàn toàn** | `grep scipy\|wilcoxon\|bootstrap` = 0 file. `scipy` không nằm trong dependency. `aggregate_algorithm` chỉ tính mean/min/max — không median, không IQR, không CI, không p-value, không effect size, không rank score. **`BenchmarkSpec.seeds` chỉ yêu cầu tối thiểu 1 seed** (`min_length=1`) — về mặt code, chạy 1 seed vẫn hợp lệ để "công bố benchmark", trái hẳn yêu cầu ≥30 seed của spec. |
| P05 | Tập held-out (dev/holdout split, generalization_gap) | ❌ **Thiếu hoàn toàn** | 0 kết quả cho `holdout`/`dev_split`/`held_out`. Không có khái niệm phân tách nào trong `Scenario`/`BenchmarkSpec`/thư viện kịch bản. Tất cả 10 kịch bản dùng chung cho cả tinh chỉnh lẫn báo cáo. |

**Kết luận mục 5: 5/5 giao thức P01–P05 bị bỏ trắng.** Đây là gap nghiêm trọng nhất và đáng lo nhất, vì đề bài đã cảnh báo trước đúng kịch bản này ở mục 11 ("Bị đánh giá là làm lại PathBench/Arena — xác suất Cao, tác động Cao") và mục 10 ("Không bao giờ cắt P02 và P04 — chúng gần như miễn phí"). Hiện trạng code đúng là đã cắt cả 5/5, kể cả hai cái "không bao giờ được cắt".

Điều duy nhất có liên quan lỏng lẻo: cơ chế `conditions_checksum` (đảm bảo so sánh cùng điều kiện map/seed) — làm tốt nhưng giải quyết vấn đề khác (công bằng điều kiện chạy), không phải P01–P05 (công bằng ngân sách tinh chỉnh, công bằng thông tin, hiệu chuẩn độ khó, ý nghĩa thống kê, generalization).

---

## 6. Chốt chặn an toàn (mục 6, sim-only)

✅ **Đạt.** Không có đường kỹ thuật nào từ UI/agent LLM tới robot thật:
- Gateway của LLM agent (`gateway.py`) **không có method điều khiển `/cmd_vel`** — thiết kế an toàn bằng cách *không tồn tại năng lực đó*, mạnh hơn kiểm tra runtime (không thể bị prompt injection vượt qua vì hàm không tồn tại).
- Có thêm tầng policy READ/WRITE và danh sách `FORBIDDEN_CAPABILITIES`.
- ROS2 chỉ nối `/cmd_vel` giữa Nav2 và `planbench_simulator_node` (phần mềm thuần túy) — không có driver phần cứng, không CAN/serial nào trong repo.

Đây là điểm làm đúng tinh thần đề bài, nên giữ nguyên khi mở rộng.

---

## 7. Các dấu hiệu "vibe-code" đáng chú ý

1. **Docker Compose chưa từng chạy** — file viết đúng nhưng zero bằng chứng chạy được, tự thừa nhận trong `KNOWN_LIMITATIONS.md`.
2. **Commit `2e8a993` ghi "Three.js" nhưng code là Canvas 2D thuần** — sai lệch message vs code thật, cần sửa lại commit message hoặc lưu ý khi báo cáo tiến độ.
3. **PPO checkpoint là bản smoke-test 0% success**, gắn cờ rõ ràng nhưng vẫn nằm trong registry như một thuật toán "khả dụng" — dễ gây hiểu nhầm nếu ai đó chạy benchmark mà không đọc metadata.
4. **1 seed là đủ hợp lệ để chạy benchmark** theo schema hiện tại, trái ngược hoàn toàn tinh thần ≥30 seed của P04.
5. **Không có module thống kê nào** (không scipy) — gap nghiêm trọng nhất, đã nêu ở mục 5.
6. **Công thức smoothness sai lệch spec** (Σ|Δθ|/length thay vì Σ(Δθ)²) — nếu chấm điểm bám sát công thức spec sẽ bị trừ.
7. **F01 (map loader định dạng ROS chuẩn)** — tính năng nền tảng đầu tiên trong roadmap tuần 1 — lại là tính năng hoàn toàn thiếu, dù mọi thứ phía sau (schema, sim, planner) đều giả định map đã tồn tại sẵn.
8. **Mất cân đối phạm vi nghiêm trọng**: đầu tư rất lớn vào Pha 3 (ROS2/Nav2 thật, RL pipeline, LLM agent có chống fabricate-citation, renderer 2.5D) trong khi Pha 1's P01–P05 — thứ rẻ nhất, quan trọng nhất theo đúng lời đề bài — bị bỏ trắng. Đây đúng là hiện tượng "agent AI thích làm tính năng ấn tượng/phức tạp, né phần kỷ luật thống kê không hào nhoáng" mà bản thân đề bài cảnh báo.

**Điểm tích cực cần ghi nhận** (để không đánh giá một chiều):
- RBAC/Auth là thật (bcrypt + JWT, không có đường tắt).
- Approval workflow có enforce chống tự-duyệt ở server, không chỉ ẩn nút UI.
- A*, DWA là thuật toán thật, viết tay đúng tinh thần "không dùng hộp đen" của spec (mục 9.4).
- Bộ test lớn và thật (878 test pass), có log thật, có tìm ra bug thật (SQLite FK constraint) — không phải test rỗng.
- Thiết kế an toàn (không có đường điều khiển robot thật) đúng chuẩn.

---

## 8. Việc cần sửa ngay (ưu tiên theo đúng "thứ tự không được cắt" của spec mục 10)

**Ưu tiên 1 — khôi phục differentiator, bắt buộc trước khi làm thêm bất kỳ tính năng Pha 3 nào:**
1. Thêm module thống kê (P04): dùng `scipy.stats` — median/IQR, bootstrap CI 1000×, Wilcoxon signed-rank + effect size, rank score. Sửa `BenchmarkSpec.seeds` để cảnh báo/enforce khi < 30 seed.
2. Thêm trường `observation_class` vào `AlgorithmInfo`/registry (P02) — chi phí thấp như spec nói (chỉ một field). Nhóm leaderboard theo trường này.
3. Thêm logic hiệu chuẩn độ khó (P03): chạy baseline tham chiếu (A*+DWA mặc định) 30 seed trên từng kịch bản, gán `difficulty = 1 - success_rate`, sinh đường cong theo độ khó thay vì trung bình gộp.
4. Thêm khái niệm dev/holdout split (P05) vào scenario library + báo cáo generalization_gap.
5. (Có thể làm sau, ngân sách nhỏ) P01: thêm Optuna, giới hạn N trial như nhau cho mỗi planner.

**Ưu tiên 2 — hoàn thiện MVP còn thiếu:**
6. Viết parser PGM/PNG + YAML đúng chuẩn `map_server` (F01) — nền tảng của mọi thứ khác.
7. Sửa công thức smoothness đúng Σ(Δθ)² theo spec, thêm p50/p95/p99 cho latency, thêm peak memory, stop-and-go count (F05).
8. Thực sự chạy `docker compose up` ít nhất một lần và sửa lỗi phát sinh (F12) — hiện tại là rủi ro "demo sập tại chỗ" cao nhất.
9. Thêm chức năng xuất báo cáo Markdown/PDF + ít nhất một thư viện biểu đồ (F09).
10. Thêm time-scrubbing cho replay đã lưu, vẽ chướng ngại động trong UI (F08).

**Ưu tiên 3 — dọn dẹp và làm rõ:**
11. Sửa commit message `2e8a993` cho khớp thực tế (không phải Three.js) hoặc ghi chú lại trong docs.
12. Cân nhắc bỏ/đổi tên `astar+ppo` khỏi registry mặc định cho tới khi có checkpoint huấn luyện thật, tránh nhầm là kết quả benchmark hợp lệ.
13. Cài RRT* thật (F04) — hiện thiếu hẳn thuật toán thứ 3 mà spec chỉ định rõ tên.

---

## 9. Hướng phát triển tiếp

- **Ngắn hạn (trước khi nộp/demo):** dồn toàn lực vào mục 8 Ưu tiên 1 (P01–P05). Đây là phần rẻ, không đòi hỏi hạ tầng mới (không cần ROS2/GPU/LLM), chỉ cần code Python thuần + scipy, nhưng quyết định trực tiếp việc dự án có đúng định vị "giao thức đánh giá đáng tin" như đề bài đặt ra hay không. Nếu thiếu mục này, dự án về bản chất là "PathBench thu nhỏ có thêm UI đẹp" — đúng rủi ro bị chấm là "làm lại cái đã có" mà đề bài cảnh báo ở mục 11.
- **Trung hạn:** hoàn thiện MVP thật sự chạy được end-to-end có kiểm chứng (Docker Compose chạy thật, map loader thật, export report thật) trước khi tiếp tục đầu tư Pha 3.
- **Dài hạn:** phần Pha 3 (ROS2/Nav2, RL, LLM agent, 2.5D) đã có nền khá tốt, không cần làm lại — chỉ cần: huấn luyện PPO thật (không chỉ smoke test), nối ROS2 runner vào orchestrator chính, test LLM provider thật, thêm noise model cho LiDAR (F23), Optuna cho P01. Đây đều là mở rộng hợp lý trên nền đã có, không phải viết lại.
- **Về báo cáo/đóng khung:** khi trình bày, nên tách rõ hai phần: (a) hạ tầng kỹ thuật — đã làm tốt, đáng ghi điểm về năng lực code; (b) phương pháp luận đánh giá (P01–P05) — phần quyết định tính mới của đề tài, hiện là 0%. Nếu thời gian còn ít, ưu tiên tuyệt đối cho (b) trước khi thêm bất kỳ dòng code Pha 3 nào khác, đúng lời khuyên "thứ tự cắt phạm vi" ở mục 10 của đề bài (không bao giờ cắt P02, P04).

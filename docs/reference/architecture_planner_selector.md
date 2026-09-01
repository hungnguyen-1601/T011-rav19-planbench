# Sơ đồ kiến trúc — PlanBench / Planner Selector

> **Ngày lập:** 2026-08-16 · **Nhánh:** `tongduyan_plannerselector`
> **Nguồn sự thật:** `contracts/CONTRACTS.md` (HĐ-1 … HĐ-15). Khi tài liệu
> này mâu thuẫn với contract, **contract thắng**.
> **Quan hệ với tài liệu khác** *(cập nhật 2026-08-31)*: `ARCHITECTURE.md`
> ở gốc repo **đã được viết lại 2026-08-23** và nay là sơ đồ kiến trúc hiện
> hành — mô tả "template T-011 chưa điền (LangGraph + ChromaDB)" trong bản
> gốc của dòng này không còn đúng. `docs/architecture.md` (dừng ở Giai đoạn
> 1A) đã chuyển vào `docs/archive/superseded/`; nhật ký quyết định D01–D15
> của nó được tách ra `docs/reference/decision-log.md` vì code còn trích.
> `docs/architecture_diagram.md` **chưa từng tồn tại** trong cây này.
> File này giữ vai **nguồn chi tiết về toán, ký hiệu và ánh xạ HĐ**;
> bản định hướng ngắn là `docs/01-architecture.md`.

---

## 0. Một câu về hệ thống

Hệ thống nhận **một deployment profile** (bản đồ, nhiệm vụ, robot, phần
cứng, ràng buộc vận hành) cùng **một tập candidate** (cấu hình điều hướng
hoàn chỉnh), chạy mô phỏng ghép cặp trên cùng tập episode, rồi trả về
**đúng một khuyến nghị** kèm bằng chứng thống kê và biên sai số của chính
khuyến nghị đó.

```
c* = argmax U(c | T, H, P)      c ∈ C_feasible
```

Điều đó định hình toàn bộ kiến trúc: mọi thành phần tồn tại để **một tấm
Decision Card tái lập được**, chứ không phải để "chạy simulator".

---

## 1. Bối cảnh hệ thống (Level 1)

```mermaid
graph TB
    subgraph actors["Người dùng"]
        ENG["Kỹ sư điều hướng<br/>khai deployment, đăng ký candidate"]
        REV["Người phê duyệt<br/>vai thứ hai, HĐ-14"]
        PM["PM / khách hàng<br/>đọc Decision Card"]
    end

    SYS["<b>PlanBench — Planner Selector</b><br/>web + API + engine mô phỏng<br/>và tầng ra quyết định"]

    subgraph ext["Bên ngoài, đều tùy chọn"]
        LLM["LLM provider<br/>OpenAI / Anthropic / Gemini …<br/>thiếu key ⇒ mock tất định"]
        MLF["MLflow<br/>thiếu ⇒ null tracker"]
        OA["OAuth Google / GitHub<br/>thiếu ⇒ dev login"]
        ROS["ROS2 / Nav2 workspace<br/>ros2_ws, chưa nối vào luồng đo"]
    end

    ENG -->|"khai profile, chạy so sánh"| SYS
    REV -->|"duyệt / từ chối card"| SYS
    PM -->|"đọc khuyến nghị + bằng chứng"| SYS

    SYS -.->|"trợ lý hội thoại"| LLM
    SYS -.->|"theo dõi thí nghiệm"| MLF
    SYS -.->|"đăng nhập"| OA
    SYS -.->|"đường mở rộng"| ROS

    SYS ==>|"artefact tái lập được"| OUT["Decision Card + Manifest<br/>+ trace Parquet"]
```

Ba mũi tên nét đứt là **suy giảm có kiểm soát**: thiếu chúng thì tính năng
tương ứng hạ chế độ và **nói rõ**, không crash (xem `requirements-optional.txt`).

---

## 2. Kiến trúc thành phần (Level 2)

```mermaid
graph TB
    subgraph web["apps/web — Next.js 15 + React 19"]
        PAGES["Trang: /deployments · /candidates · /decisions<br/>/maps · /scenarios · /simulate · /reviews · /agent"]
        WLIB["lib/: api.ts · decisions.ts · deployments.ts<br/>trafficUi · trafficOverlay · pointerRouting · canvasSize"]
        CANVAS["MapCanvas · MissionPlacer · TrafficEditor<br/>TraceViewer · Scene25D"]
        PAGES --> WLIB
        PAGES --> CANVAS
    end

    subgraph api["apps/api — FastAPI"]
        RT["routers/: decisions · benchmarks · simulations<br/>maps · scenarios · episodes · library · models<br/>reviews · users · auth · chat · agent · ws"]
        SVC["decision_service · services · review_service<br/>registry_service · account_service · chat_service"]
        WK["worker.JobQueue<br/>chạy nền, có JobState"]
        REPO["repositories / repository_ports<br/>db/models · db/session"]
        RT --> SVC --> WK
        SVC --> REPO
    end

    subgraph core["Lõi Python — không phụ thuộc FastAPI/ROS2/web"]
        SCHEMA["<b>packages/schemas</b><br/>task_profile · episode_context · identity<br/>map_io · dynamic · sensor · feasibility · replanning"]

        BENCH["<b>packages/benchmark</b><br/>contexts · episode · pipeline · selection<br/>registry · task_map · tuning · neighborhood · hostinfo"]

        SIM["<b>services/simulator</b><br/>engine · kinematics · lidar · collision<br/>nav_stack · path_follower · noise · <b>trace</b>"]

        PLAN["<b>packages/planning</b> + registry stack<br/>astar · rrtstar × dwa · dwa_predictive<br/>pure_pursuit · ppo"]

        MET["<b>packages/metrics</b><br/>definitions · episode_metrics<br/>reference_path · statistics"]

        DEC["<b>packages/decision</b><br/>anchors · gates · objectives · pairing<br/>stats · pareto · sensitivity · card · early_stop"]
    end

    subgraph aux["Phụ trợ"]
        AG["services/agent_service<br/>factory · providers · rag · tools · evidence"]
        TRK["services/tracking<br/>mlflow_tracker | null"]
        RL["ml/planbench_rl<br/>env · policy · training — optional"]
    end

    subgraph store["Lưu trữ — D15: file lớn ngoài DB"]
        DB[("SQLite / PostgreSQL<br/>SQLAlchemy + Alembic")]
        ART["artifacts/runs/&lt;run&gt;/<br/>trace Parquet · card.json<br/>manifest.json · run_journal.jsonl"]
    end

    PAGES -->|"REST /api/v1"| RT
    CANVAS -->|"WebSocket /ws/simulations/{id}"| RT

    SVC --> BENCH
    WK --> BENCH

    BENCH --> SIM
    BENCH --> PLAN
    BENCH --> MET
    BENCH --> DEC
    SIM --> ART
    MET --> ART
    DEC --> ART
    REPO --> DB
    ART -.->|"URI + checksum"| DB

    SCHEMA -.->|"contract-first,<br/>mọi tầng import"| api
    SCHEMA -.-> core
    SCHEMA -.-> aux

    SVC --> AG
    BENCH --> TRK
    PLAN -.-> RL
```

**Ba luật đọc được từ sơ đồ:**

1. **Mũi tên không bao giờ đi ngược từ lõi lên API.** `packages/` và
   `services/simulator` không import FastAPI. Đó là điều kiện để cùng một
   engine chạy được ở ba chế độ: trong API, headless qua `scripts/`, và
   (tương lai) node ROS2.
2. **`packages/schemas` là nguồn sự thật duy nhất của domain.** Pydantic,
   không phải bảng SQL, không phải TypeScript interface.
3. **`artifacts/` và database phải backup cùng nhau.** Bảng chỉ giữ URI +
   checksum; mất thư mục artifact thì database còn nguyên nhưng mọi lần
   phát lại đều báo thiếu file.

---

## 3. Chuỗi giá trị — từ profile tới khuyến nghị

Đây là sơ đồ quan trọng nhất của dự án. Thứ tự **không** đảo được: cổng
đứng trước chấm điểm, Pareto đứng trước utility, utility đứng trước thống kê.

```mermaid
flowchart TB
    TP["<b>TaskProfile</b> HĐ-2<br/>map · missions · robot<br/>constraints · hardware · horizon"]
    CAND["<b>Candidate[]</b> HĐ-1<br/>global + local + params + version<br/>+ observation_requirements<br/>candidate_id = hash"]

    CTX["<b>EpisodeContext[]</b> HĐ-3<br/>mission × obstacle realization × seed<br/>episode_context_id"]

    SWEEP["<b>simulate</b> — pipeline.py<br/>vòng NGOÀI = context<br/>vòng TRONG = candidate"]

    TRACE[("<b>Trace Parquet</b> HĐ-5<br/>một episode = một file<br/><i>đầu vào DUY NHẤT của Metrics</i>")]

    MET["<b>definitions.py</b> HĐ-6<br/>L_ref Dijkstra · path_efficiency<br/>time_efficiency · p99_latency · clearance"]

    G["<b>Feasibility Gates G1–G6</b> HĐ-7<br/>đường · an toàn quan sát được · tin cậy<br/>thời gian thực · bộ nhớ · tương thích quan sát<br/><i>nhị phân, không đánh đổi</i>"]

    PAR["<b>Pareto</b> HĐ-10<br/>non-inferiority trên LCB₉₅(ΔU)<br/>3 nhãn, không xoá candidate"]

    ANC["<b>Anchors</b> HĐ-8<br/>metric_anchors.yaml<br/>mốc tuyệt đối ngoại sinh"]

    OBJ["<b>Objectives + Decision Utility</b> HĐ-9<br/>U_R tin cậy · U_S an toàn<br/>U_E hiệu quả · U_C chi phí<br/>theo TỪNG episode"]

    STAT["<b>Paired bootstrap ΔU</b> HĐ-11<br/>resample theo context, 1000 lần<br/>0 ∉ CI ⇒ CLEAR<br/>0 ∈ CI ⇒ NEAR-EQUIVALENT"]

    SENS["<b>Sensitivity</b><br/>weight_stability_margin<br/>anchor_stability ±10%"]

    CARD["<b>Decision Card</b> HĐ-12<br/>tên + tham số + nhãn + scope<br/>alternative + bảng cổng + bằng chứng"]

    MAN["<b>Manifest</b> HĐ-13<br/>seed · params_hash · git_sha<br/>anchor_config_version · context ids"]

    APPR["<b>Approval</b> HĐ-14<br/>vai thứ hai, chống tự duyệt<br/>audit append-only"]

    CFG["<b>approved_config.yaml</b>"]

    TP --> CTX
    CAND --> CTX
    CTX --> SWEEP
    TP --> SWEEP
    CAND --> SWEEP
    SWEEP --> TRACE
    TRACE --> MET
    TP -.->|"ngưỡng, tolerance"| MET
    MET --> G
    TP -.->|"mọi ngưỡng gate<br/>đến từ đây"| G
    G -->|"chỉ ai qua cổng"| PAR
    ANC --> OBJ
    TP -.->|"${constraints.*}"| ANC
    PAR --> OBJ
    OBJ --> STAT
    STAT --> SENS
    SENS --> CARD
    OBJ --> CARD
    G --> CARD
    CARD --> MAN
    CARD --> APPR
    APPR --> CFG

    classDef gate fill:#7f1d1d,stroke:#fca5a5,color:#fee2e2
    classDef out fill:#14532d,stroke:#86efac,color:#dcfce7
    class G gate
    class CARD,MAN,CFG out
```

### Vì sao thứ tự này bất di bất dịch

| Bước | Nếu đảo thì hỏng gì |
|---|---|
| Gate **trước** Score | Ứng viên va chạm 1,7% mà nhanh gấp 3 sẽ thắng điểm. An toàn không được phép đem ra đánh đổi (N4) |
| Anchor **tuyệt đối**, không min-max theo tập ứng viên | Thêm một ứng viên tệ vào có thể lật thứ hạng hai ứng viên đầu — *rank reversal* (N2) |
| Pareto **trước** Utility | Candidate bị lấn át vẫn ngoi lên được nếu trọng số bị chỉnh lệch (N10) |
| Objective tính **theo từng episode** | Không tính được ΔU ghép cặp; mất luôn lợi thế phương sai chung (N8) |
| Bootstrap **ghép cặp**, không so hai CI rời | Hai CI chồng nhau vẫn có thể đi kèm hiệu số khác 0 rõ rệt — kết luận quá bảo thủ |

### Vì sao vòng ngoài là context, vòng trong là candidate

Ghi rõ vì đây là chỗ dễ code ngược nhất (`pipeline.simulate`, HĐ-3.2):

- **Ngắt giữa chừng.** Candidate-outer mà dừng nửa chừng: candidate đầu có
  đủ episode, candidate cuối không có gì — dữ liệu vô dụng. Context-outer
  dừng nửa chừng: mọi candidate có **cùng** tập episode, phép so vẫn hợp
  lệ, chỉ nhỏ hơn.
- **Trôi máy.** Candidate-outer đặt một candidate ở nửa đầu đồng hồ tường,
  candidate kia ở nửa sau — mọi throttling nhiệt rơi trọn lên một bên.
  Xen kẽ làm mọi candidate chia nhau đúng trạng thái máy, từng phút một.

---

## 4. Vòng lặp một episode — bốn interface HĐ-4

Không thành phần nào được import trực tiếp thành phần khác ngoài qua bốn
giao thức này. Đường **`Observation`** là ranh giới công bằng: một planner
gọi thẳng vào nội tại `SimBackend` để lấy vị trí vật cản vừa là vi phạm
kiến trúc, vừa là gian lận về lớp quan sát (G6).

```mermaid
sequenceDiagram
    autonumber
    participant R as run_contract_episode<br/>(episode.py)
    participant B as SimBackend<br/>(engine)
    participant G as GlobalPlanner<br/>(astar / rrtstar)
    participant L as LocalController<br/>(dwa / dwa_predictive / pure_pursuit)
    participant T as TraceRecorder<br/>(Parquet)

    R->>B: reset(ctx)
    B-->>R: Observation
    R->>B: get_costmap()
    B-->>R: Costmap2D
    R->>G: plan(start, goal, costmap)
    G-->>R: Path

    loop mỗi bước dt, đi theo THỜI GIAN không theo bước
        R->>L: compute_velocity(pose, path, obs)
        L-->>R: Twist
        R->>B: step(cmd, dt)
        B-->>R: Observation, StepInfo
        R->>T: record(t, state, event)
        opt replanning bật trên deployment
            R->>G: replan từ chính tia LiDAR robot nhận được
            Note over R,G: KHÔNG dùng vị trí thật vật cản<br/>(HĐ-4.1, gỡ đặc quyền ở 6.6.0)
        end
    end

    R->>T: close(peak_search_nodes, peak_tree_nodes, …)
    T-->>R: đường dẫn file trace
    Note over T: File này là đầu vào DUY NHẤT<br/>của Metrics Engine (HĐ-5)
```

**Biến thể `monolithic`:** candidate RL end-to-end không có tách
global/local. Runner gọi `MonolithicPolicy.act(pose, goal, obs)` thay cho
cặp `GlobalPlanner` + `LocalController`, vẫn đi qua **đúng sáu cổng**.
Adapter phía simulator đã có; **registry policy còn nợ** — hôm nay
candidate `monolithic` khai được mà chưa dựng được (L2).

---

## 5. Luồng một request thật — chạy so sánh từ trình duyệt

```mermaid
sequenceDiagram
    autonumber
    actor U as Kỹ sư
    participant W as apps/web
    participant A as FastAPI router
    participant S as DecisionRunService
    participant Q as worker.JobQueue
    participant P as benchmark.pipeline
    participant F as artifacts/runs/
    participant D as Database

    U->>W: khai deployment trên form 7 tab
    W->>A: POST /api/v1/task-profiles
    A->>S: validate theo TaskProfile (Pydantic)
    S-->>W: 201 · hoặc 409 nếu nộp lại cùng id khác nội dung

    U->>W: chọn candidate, bấm chạy
    W->>A: POST /api/v1/decisions
    A->>S: dựng run spec
    S->>Q: enqueue job
    S-->>W: 202 + job id
    W->>A: poll trạng thái job

    Q->>P: simulate → metrics → gates → objectives → ΔU
    P->>F: ghi trace Parquet mỗi episode
    P->>F: ghi card.json + manifest.json + run_journal.jsonl
    P-->>Q: kết quả
    Q->>D: lưu bản ghi run + URI + checksum

    W->>A: GET /api/v1/decisions/{id}
    A->>D: đọc bản ghi
    A->>F: đọc card + trace theo URI
    A-->>W: DecisionRun · DecisionCard · gate table
    W-->>U: Decision Card + bảng cổng + waterfall

    U->>W: gửi duyệt
    W->>A: POST review → vai thứ hai duyệt (HĐ-14)
```

Phát lại quỹ đạo đi đường riêng: `WebSocket /ws/simulations/{id}`, có
tham số `speed` và `pace` — không nằm dưới prefix `/api/v1`.

---

## 6. Hai chế độ chạy

```mermaid
graph LR
    subgraph dev["Local — dev"]
        D1["scripts/serve.py --reload --migrate<br/>hoặc scripts/dev_stack.sh start"]
        D2["next dev :3000"]
        D3[("SQLite planbench.db")]
        D4["artifacts/ trên đĩa"]
        D2 --> D1 --> D3
        D1 --> D4
    end

    subgraph prod["docker-compose"]
        C1["service <b>db</b><br/>PostgreSQL"]
        C2["service <b>migrate</b><br/>alembic upgrade head"]
        C3["service <b>api</b><br/>docker/requirements-api.txt"]
        C4["service <b>web</b><br/>Next production"]
        V1[("volume db-data")]
        V2[("volume artifacts")]
        C2 --> C1
        C3 --> C1
        C4 --> C3
        C1 --> V1
        C3 --> V2
    end

    subgraph batch["Headless — không qua API"]
        B1["scripts/vertical_slice.py — lát cắt dọc HĐ-15"]
        B2["scripts/compare.py — chạy so sánh thẳng từ YAML"]
        B3["scripts/measure.py · diagnose_tracker.py"]
        B4["scripts/tune_hyperparameters.py — Optuna, optional"]
    end
```

**Ba bất đối xứng cố ý, đừng "sửa":**

| Chỗ | Khác gì | Lý do |
|---|---|---|
| `docker/requirements-api.txt` thiếu `psutil` | Image là Linux, có `os.sched_setaffinity` sẵn | Nhánh psutil không với tới được. Nhưng **giữ** nó trong `requirements.txt`, nếu không mọi run Windows chạy không ghim nhân (HĐ-7.4) |
| Image API thiếu `torch` | Training là workload riêng | Kéo torch vào image API là thêm vài GB cho code API không bao giờ chạy. Hệ quả: stack `astar+ppo` **không** chạy được từ image này |
| `scripts/compare.py` nạp YAML thẳng từ path | Đi vòng qua guard "nộp lại profile đã đổi" của luồng API | **Đây là nợ, không phải thiết kế** — L19, đang chờ vá ở pha Q1 |

---

## 7. Ranh giới hợp đồng — đọc trước khi sửa

Ba thứ CONTRACTS khoá cứng; đổi = MAJOR bump + mọi dữ liệu đã ghi mồ côi.

| # | Khoá | Ở đâu | Đổi thì gãy gì |
|---|---|---|---|
| 1 | `candidate_id` = hash(global + local + params + version + observation_requirements) | `packages/decision/candidate.py` | Mọi trace, pairing, ΔU, card tham chiếu id này |
| 2 | `episode_context_id` = (task profile, mission, variant, seed) | `packages/schemas/episode_context.py` | Luật ghép cặp — nền của mọi thống kê ΔU |
| 3 | Trace schema Parquet | `services/simulator/trace.py` | Thiếu một cột là phải chạy lại **toàn bộ** episode |

**Cái bẫy đã sập hai lần và vẫn còn mở:** `episode_context_id` **không**
băm `environment`. Đổi cảm biến hay `v_obstacle_max` trong profile mà giữ
nguyên `task_profile_id` cho ra hai thế giới khác nhau dưới **cùng một
context id**, journal nối đuôi nhau, người đọc kết luận episode chập chờn.
Luật hiện hành: *đổi profile ⇒ `task_profile_id` mới*. Guard nằm ở luồng
API và `compare.py` đi vòng qua nó (L19).

---

## 8. Bảng tra thành phần

| Thành phần | Đường dẫn | Vai |
|---|---|---|
| Schema domain | `packages/schemas/planbench_schemas/` | Nguồn sự thật Pydantic cho mọi tầng |
| Sinh context | `packages/benchmark/contexts.py` | HĐ-3, `episode_context_id`, kế hoạch chạy |
| Chạy episode | `packages/benchmark/episode.py` | Ghép candidate × context × map → trace |
| Điều phối sweep | `packages/benchmark/pipeline.py` | `simulate` · `gate_all` · `score_survivors` · `decide` |
| Đầu vào CLI | `packages/benchmark/selection.py` | `run_comparison`, `assemble_card`, early-stop |
| Registry stack | `packages/benchmark/registry.py` | 7 stack: astar/rrtstar × dwa/dwa_predictive/pure_pursuit, + astar+ppo |
| Simulator | `services/simulator/planbench_simulator/` | engine · kinematics · lidar · collision · nav_stack · trace |
| Metric | `packages/metrics/definitions.py` | **Nơi duy nhất** định nghĩa metric (HĐ-6) |
| Quyết định | `packages/decision/` | anchors · gates · objectives · pairing · stats · pareto · sensitivity · card |
| API | `apps/api/planbench_api/` | 16 router + service + JobQueue + repository |
| Web | `apps/web/src/` | 17 trang, canvas tương tác, i18n vi/en |
| Trợ lý AI | `services/agent_service/` | factory chọn provider; không key ⇒ mock tất định |
| Theo dõi | `services/tracking/` | MLflow hoặc null tracker |
| RL | `ml/planbench_rl/` | env · policy · training (optional) |
| ROS2 | `ros2_ws/src/` | bridge · simulator_node · benchmark_runner · nav2_bringup — build bằng colcon, **không** nằm trong luồng đo hiện tại |

---

## 9. Cái sơ đồ này **không** vẽ

Nói rõ để không ai đọc thừa:

- **L2/L3 scope** (mission distribution, Task Neighborhood K=20) — đã có
  `neighborhood.py` nhưng chưa nằm trong luồng chính; MVP chạy L1
  mission-level.
- **Racing / Adaptive Scheduler** (N9) — cố ý chưa làm, episode 2D quá rẻ
  để cần tới.
- **Target Verifier** cho pha 2 của G4/G5 — chưa có bo mạch đích, nên mọi
  card hiện ghi `screened_on_host`, **không** được phát biểu là đạt thời
  gian thực.
- **Registry policy** cho candidate `monolithic` — nửa còn lại của adapter.
- **ROS2 closed-loop** — `ros2_ws/` tồn tại nhưng chưa là một `SimBackend`
  thay thế được trong luồng đo.

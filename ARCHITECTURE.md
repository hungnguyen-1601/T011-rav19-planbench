# Kiến trúc PlanBench

Nền tảng so sánh thuật toán điều hướng robot AMR/AGV. Người dùng khai một
**deployment** (thế giới cần đo), đăng ký các **ứng viên** (stack thuật
toán), chạy một **phép so**, rồi ký duyệt kết quả. Simulator sinh ra mọi
con số; LLM đọc và chất vấn chúng nhưng không bao giờ tạo ra chúng.

Ba nguyên tắc chi phối mọi thứ bên dưới:

- **Core-first.** `packages/` và `services/simulator/` là thư viện Python
  thuần, không import FastAPI, ROS2 hay frontend. API chỉ là lớp vỏ mỏng.
- **Contract-first.** Model Pydantic trong `packages/schemas/` là nguồn
  sự thật duy nhất của kiểu domain.
- **Determinism-first.** Mọi thành phần nhận seed và config tường minh;
  cùng input cho cùng output. Đây là lý do LLM bị giữ ngoài đường tính toán.

## Sơ đồ hệ thống

```mermaid
graph TB
    User([Người dùng])

    subgraph FE["Frontend — Next.js 15 + React 19"]
        Pages["/deployments · /candidates<br/>/decisions · /simulate"]
        Critique["Panel Phản biện"]
    end

    subgraph API["API — FastAPI (lớp vỏ mỏng)"]
        Routers["routers/ — decisions, maps,<br/>scenarios, auth, agent"]
        Services["decision_service · auth · repositories"]
    end

    subgraph Core["Core — thư viện Python thuần"]
        Schemas["packages/schemas<br/>TaskProfile · Scenario · Map"]
        Planning["packages/planning<br/>A* · RRT*"]
        Sim["services/simulator<br/>Engine · LiDAR · collision · nav_stack"]
        Metrics["packages/metrics<br/>chỉ số từng episode"]
        Bench["packages/benchmark<br/>pipeline · candidates · selection"]
        Decision["packages/decision<br/>gates G1–G6 · ΔU · Pareto<br/>Decision Card · self_check"]
    end

    subgraph AI["Tầng AI — services/agent_service"]
        Provider["provider abstraction<br/>gemini · anthropic · openai · mock"]
        AgentCritique["critique.py<br/>LLM đọc + phản biện"]
        RAG["rag.py — TF-IDF trên docs/"]
        Tools["tools.py — công cụ chỉ-đọc"]
    end

    Store[("SQLite / PostgreSQL<br/>deployment · run · card")]
    Traces[("artifacts/runs<br/>trace Parquet · manifest")]
    Gemini{{"Gemini API"}}

    User --> Pages
    Pages --> Routers
    Critique --> Routers
    Routers --> Services
    Services --> Bench
    Services --> Decision
    Services --> Store
    Bench --> Planning
    Bench --> Sim
    Sim --> Metrics
    Metrics --> Traces
    Bench --> Decision
    Decision --> Schemas

    Routers -->|"?use_model=true"| AgentCritique
    AgentCritique -->|"đọc luật trước"| Decision
    AgentCritique --> Provider
    Provider --> Gemini
    RAG --> Tools

    classDef ai fill:#e8f4f5,stroke:#0d5a61,color:#11171a
    classDef core fill:#eef2ee,stroke:#3d4a50,color:#11171a
    class AI,Provider,AgentCritique,RAG,Tools ai
    class Core,Schemas,Planning,Sim,Metrics,Bench,Decision core
```

## Luồng dữ liệu chính

Đây là luồng người dùng end-to-end mà MVP hiện thực:

```mermaid
sequenceDiagram
    actor U as Người dùng
    participant W as Web
    participant A as API
    participant S as Simulator
    participant D as Tầng quyết định
    participant R as Bộ luật (15 luật)
    participant L as LLM (Gemini)

    U->>W: Khai deployment + chọn 2 ứng viên
    W->>A: POST /decisions
    A->>S: chạy N episode, cùng seed cho mọi ứng viên
    S-->>A: trace Parquet + chỉ số từng episode
    A->>D: gates G1–G6, ΔU, bootstrap CI, Pareto
    D-->>A: comparison_report + Decision Card
    A-->>W: kết quả

    Note over U,L: Người dùng bấm "Phản biện"
    U->>W: Kiểm bằng luật
    W->>A: GET /decisions/{id}/critique
    A->>R: 15 luật đọc report
    R-->>A: các phản biện, mỗi cái trỏ vào một trường có thật
    A-->>W: findings (tất định)

    U->>W: Hỏi thêm model
    W->>A: GET .../critique?use_model=true
    A->>R: luật chạy TRƯỚC
    A->>L: report + findings của luật
    L-->>A: xếp thứ tự + tối đa 3 phản biện mới
    A->>A: loại findings trỏ vào trường không tồn tại → đếm fabricated
    A-->>W: findings (luật + model, có nhãn nguồn)
    U->>W: Đọc rồi ký duyệt hoặc từ chối
```

## LLM đứng ở đâu — và không đứng ở đâu

| Giai đoạn | Ai làm | Vì sao |
|---|---|---|
| Khai deployment, chọn ứng viên | Người | Là câu hỏi cần trả lời |
| Sinh episode, chạy simulator | Code | Phải tái lập được |
| Gates G1–G6, ΔU, khoảng tin cậy | Code | Cùng input phải cho cùng kết luận |
| **Phản biện theo luật** | **Code** | Là baseline mà LLM phải vượt |
| **Xếp thứ tự, diễn giải, bổ sung phản biện** | **LLM** | Cần phán đoán, không cần tái lập |
| Ký duyệt, chịu trách nhiệm | Người | Không uỷ quyền được |

**LLM không bao giờ sinh ra một con số.** Nó đọc số đã có và chất vấn kết
luận rút ra từ chúng.

## Ràng buộc giữ LLM trong khuôn

Cài trong `services/agent_service/planbench_agent/critique.py`:

1. **Luật chạy trước và sống sót mọi lỗi.** Provider ném exception, trả
   prose thay vì JSON, hay bịa toàn bộ trích dẫn — phần tất định vẫn về
   đủ.
2. **Model không được bỏ phản biện nào của luật.** Thiếu mã trong
   `ranked_rule_codes` thì nó giữ thứ tự cũ, không biến mất.
3. **Mọi `field_path` phải resolve được** trong report, dùng đúng hàm
   `resolve()` mà luật bị ràng buộc. Không resolve được thì bị loại và
   đếm vào `fabricated` — con số này được **công bố**, không giấu.
4. **Nhãn `source`** tách `rule` với `model` trên từng phản biện, để
   người đọc biết nửa nào tái lập được.
5. **Cấm ngôn ngữ** (`assert_no_banned_language`): nói "an toàn" cạnh một
   con số thì mất đoạn văn, giữ nguyên phần luật.
6. **Trần 3 phản biện** cho model, chặn kiểu phịa cho tới khi nghe có vẻ
   nghiêm trọng.

## Lưu trữ

| Nơi | Chứa gì | Vì sao ở đó |
|---|---|---|
| SQLite / PostgreSQL | deployment, ứng viên, decision run, Decision Card, nhật ký duyệt | Cần truy vấn và phân quyền |
| `artifacts/runs/` | trace Parquet mỗi episode, manifest, Decision Card dạng file | Trace nặng vài MB mỗi episode; card và manifest là hồ sơ nghiệm thu nên được commit vào repo |
| `docs/` | tài liệu Markdown | RAG index từ đây bằng TF-IDF, không dùng vector DB — để trích nguồn ổn định và chạy offline |

## Thành phần ngoài

| Dịch vụ | Bắt buộc? | Thiếu thì sao |
|---|---|---|
| Gemini API | không | Rơi về mock tất định, có ghi log rõ |
| PostgreSQL | không | Dùng SQLite cạnh repo |
| MLflow | không | Tự tắt tracking |
| Google / GitHub OAuth | không | Nút đăng nhập tương ứng không hiện; dùng dev login |

Không có dependency nào là điều kiện để chạy. Thiếu thì tính năng tương
ứng **giảm chế độ có báo**, không crash.

# Kiến trúc

> Bản định hướng. Sơ đồ mermaid đầy đủ ở [`../ARCHITECTURE.md`](../ARCHITECTURE.md);
> chi tiết toán học và ký hiệu ở
> [reference/architecture_planner_selector.md](reference/architecture_planner_selector.md).

---

## 1. Ba nguyên tắc chi phối mọi thứ

**Core-first.** `packages/` và `services/simulator/` là thư viện Python
thuần — không import FastAPI, ROS2 hay frontend. API chỉ là lớp vỏ mỏng.
Đây là điều kiện để cùng một engine chạy ở ba chế độ: nội bộ, headless
benchmark, ROS2 node.

**Contract-first.** Model Pydantic trong `packages/schemas/` là nguồn sự
thật duy nhất của kiểu domain, dùng chung bởi API, worker, ROS bridge và
agent tool.

**Determinism-first.** Mọi thành phần nhận seed và config tường minh;
cùng input cho cùng output. Không dùng global random state. **Đây là lý do
LLM bị giữ ngoài đường tính toán.**

---

## 2. Bản đồ tầng

```
packages/schemas        hợp đồng dữ liệu dùng chung — nguồn sự thật của kiểu
packages/planning       A*, Theta*, RRT*, DWA, DWA predictive, Pure Pursuit
packages/metrics        metric từng episode và anchor
packages/benchmark      engine chạy episode, registry stack, outcome, fingerprint
packages/decision       cổng G1–G6, ΔU, bootstrap, Pareto, Decision Card, self_check
packages/explanation    tầng "vì sao": detector, waterfall, tool card, checker
packages/plugin_sdk     SDK cắm thuật toán ngoài

services/simulator      SimulationEngine, LiDAR, collision, nav_stack, algorithm host
services/agent_service  provider LLM, tool, advisor, critique, paper reader
services/analyst_service  AI analyst theo episode — guard, rubric, preregistration
services/tracking       MLflow adapter + null tracker

apps/api                FastAPI + SQLAlchemy — 20 router
apps/web                Next.js 15 + React 19
apps/desktop            đóng gói Windows (VERSION quyết định tag release)

ml/                     Gymnasium env, reward, huấn luyện PPO
ros2_ws/                5 package ROS2 (simulator node, Nav2 bringup, runner)
alembic/                migration
contracts/              CONTRACTS.md — luật, HĐ-1 … HĐ-15
```

### Trang web (đã đối chiếu `apps/web/src/app/`, 2026-08-31)

`/` dashboard · `/maps` · `/scenarios` · `/library` · `/deployments` ·
`/candidates` · `/simulate` · `/decisions` · `/algorithms` · `/models` ·
`/reviews` · `/agent` · `/guide` · `/admin` · `/settings` · `/system` ·
`/login` · `/auth` · `/welcome`

`/benchmarks`, `/benchmarks/[id]` và `/leaderboard` **đã bị gỡ** ở đợt P6.
Endpoint API tương ứng vẫn còn nhưng cả 18 route mang `deprecated=True` —
xem [reference/api.md](reference/api.md).

---

## 3. Luồng end-to-end

1. Người dùng khai một **deployment** — map, robot, cảm biến và nhiễu,
   mission, vật cản động, ngưỡng khả thi, trọng số mục tiêu. Mọi ngưỡng
   cổng đọc từ đây.
2. Đăng ký ≥2 **candidate** (mỗi candidate là **một stack hoàn chỉnh**:
   global planner + local controller + tham số).
3. Chạy **phép so ghép cặp**: mọi candidate chạy trên **cùng một tập
   `episode_context`** — cùng seed, cùng vị trí vật cản, cùng nhiễu cảm
   biến. Hiệu số tính **theo từng cặp**, không phải giữa hai trung bình
   rời nhau.
4. **Sáu cổng khả thi G1–G6** chạy **trước** mọi phép chấm điểm.
5. Candidate qua cổng → **ΔU ghép cặp + CI 95% bootstrap** → **Decision Card**.
6. Người đọc bằng chứng, phản biện, rồi **ký duyệt hoặc từ chối**.

Đầu ra là một khuyến nghị kèm **biên sai số của chính khuyến nghị đó**:

```
c* = argmax U(c | T, H, P)      c ∈ C_feasible
```

---

## 4. LLM đứng ở đâu — và không đứng ở đâu

| Giai đoạn | Ai làm | Vì sao |
|---|---|---|
| Khai deployment, chọn candidate | **Người** | Là câu hỏi cần trả lời |
| Sinh episode, chạy simulator | **Code** | Phải tái lập được |
| Gates G1–G6, ΔU, khoảng tin cậy | **Code** | Cùng input phải cho cùng kết luận |
| Phản biện theo luật | **Code** | Là baseline mà LLM phải vượt |
| Xếp thứ tự, diễn giải, bổ sung phản biện | **LLM** | Cần phán đoán, không cần tái lập |
| Ký duyệt, chịu trách nhiệm | **Người** | Không uỷ quyền được |

**LLM không bao giờ sinh ra một con số.** Nó đọc số đã có và chất vấn kết
luận rút ra từ chúng.

### Sáu ràng buộc giữ LLM trong khuôn

Cài trong `services/agent_service/planbench_agent/critique.py`:

1. **Luật chạy trước và sống sót mọi lỗi.** Provider ném exception, trả
   prose thay vì JSON, hay bịa toàn bộ trích dẫn — phần tất định vẫn về đủ.
2. **Model không được bỏ phản biện nào của luật.**
3. **Mọi `field_path` phải resolve được** trong report. Không resolve được
   thì bị loại và đếm vào `fabricated` — con số này được **công bố**,
   không giấu.
4. **Nhãn `source`** tách `rule` với `model` trên từng phản biện.
5. **Cấm ngôn ngữ** (`assert_no_banned_language`) — nói "an toàn" cạnh một
   con số thì mất đoạn văn, giữ nguyên phần luật.
6. **Trần 3 phản biện** cho model.

---

## 5. Lưu trữ

| Nơi | Chứa gì | Vì sao ở đó |
|---|---|---|
| SQLite / PostgreSQL | deployment, candidate, decision run, Decision Card, nhật ký duyệt | Cần truy vấn và phân quyền |
| `artifacts/runs/` | trace Parquet mỗi episode, manifest, Decision Card dạng file | Trace nặng vài MB mỗi episode |
| `docs/` | tài liệu Markdown | RAG index từ đây bằng **TF-IDF**, không dùng vector DB — để trích nguồn ổn định và chạy offline |

`PLANBENCH_DATABASE_URL` rỗng ⇒ in-memory (dev/test). Giữ in-memory làm
mặc định là có chủ đích: một checkout không có database vẫn chạy được
toàn bộ API và toàn bộ test, nên một database hỏng không bao giờ giả dạng
thành một regression không liên quan.

---

## 6. Thành phần ngoài — không cái nào bắt buộc

| Dịch vụ | Thiếu thì sao |
|---|---|
| LLM API (Gemini / OpenAI / Anthropic / local) | Rơi về mock tất định, có ghi log rõ |
| PostgreSQL | Dùng SQLite cạnh repo |
| MLflow | Tự tắt tracking |
| Google / GitHub OAuth | Nút đăng nhập tương ứng không hiện; dùng dev login |

Thiếu thì tính năng tương ứng **giảm chế độ có báo**, không crash.

---

## 7. Bất biến dễ phá — đọc trước khi sửa

Những thứ này đã bị phá ít nhất một lần và mỗi lần đều tốn một buổi:

- **Replanning là thuộc tính của stack**, cắm ở
  `services/simulator/planbench_simulator/nav_stack.py::run_stack()` — nơi
  mọi stack đều đi qua. **Tuyệt đối không cắm vào file của một thuật toán**
  (làm thế là cho một thuật toán một đặc quyền các thuật toán khác không có).
- **Không vặn thí nghiệm cho khớp kết quả.** Khi một cổng không qua, bốn
  thứ tuyệt đối không được sửa để nó qua: map, mission,
  `collision_probability_max`, và tham số thuật toán tại chỗ.
- **Dưới 2 candidate qua cổng ⇒ không có Decision Card.** Không ngoại lệ.
- **Bằng chứng không được nghe mạnh hơn dữ liệu cho phép.** Bảng cổng mang
  `n_episodes` theo từng candidate; đừng xếp một số từ 30 episode cạnh một
  số từ 300 như thể chúng cùng đơn vị tin cậy.
- **`resolve_git_sha`** (`packages/decision/planbench_decision/card.py`)
  từ chối ghi manifest `unknown` — **đừng nới lỏng nó**. Card không nêu
  được commit nghĩa là stamp thiếu; sửa stamp.
- **Scope thí nghiệm** (HĐ-1.4): `global_planner_selection` đòi local
  layer giống hệt nhau, và ngược lại. Đây là contract, không phải tuỳ chọn UI.

---

## 8. Quy ước cốt lõi

- Đơn vị SI: mét, giây, radian; góc chuẩn hoá trong **(-π, π]**.
- `EPS = 1e-9` dùng chung cho so sánh float.
- **Tiếp xúc biên được tính là va chạm** — quy tắc bảo thủ về an toàn.
- Giá trị cell theo chuẩn ROS: FREE=0, OCCUPIED=100, UNKNOWN=-1.
- Không hằng số ngưỡng trong code — ngưỡng đọc từ deployment.
- i18n: thêm key phải thêm vào **cả** `en.json` và `vi.json`; thiếu một
  bên thì tên key hiện thẳng lên màn hình.

Bốn quy ước trên (EPS, tiếp xúc biên, cell value, inflation) là **quyết
định có ID** — D07, D08, D10 — và code trích chúng bằng ID. Lý do và trạng
thái từng cái: [reference/decision-log.md](reference/decision-log.md).

Xem tiếp: [02-features.md](02-features.md)

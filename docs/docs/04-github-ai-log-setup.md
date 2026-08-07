# GitHub Repository & AI Log Setup – RAV19 PlanBench

> Deliverable 4/4 – [Gate G1](./README.md)

## Mục lục

- [1. Thông tin tài liệu](#1-thông-tin-tài-liệu)
- [2. Mục tiêu tài liệu](#2-mục-tiêu-tài-liệu)
- [3. Nguyên tắc làm việc chung](#3-nguyên-tắc-làm-việc-chung)
- [4. Cấu trúc repository thực tế](#4-cấu-trúc-repository-thực-tế)
- [5. Bộ tài liệu Gate G1](#5-bộ-tài-liệu-gate-g1)
- [6. Trạng thái Git hiện tại](#6-trạng-thái-git-hiện-tại)
- [7. Chiến lược branch](#7-chiến-lược-branch)
- [8. Quy tắc đặt tên branch](#8-quy-tắc-đặt-tên-branch)
- [9. Commit convention](#9-commit-convention)
- [10. Pull Request workflow](#10-pull-request-workflow)
- [11. Quy tắc code review](#11-quy-tắc-code-review)
- [12. Cấu trúc task](#12-cấu-trúc-task)
- [13. Chuỗi truy vết](#13-chuỗi-truy-vết)
- [14. Unit test](#14-unit-test)
- [15. Integration test](#15-integration-test)
- [16. End-to-end test](#16-end-to-end-test)
- [17. Regression test](#17-regression-test)
- [18. Quality gate trước khi merge](#18-quality-gate-trước-khi-merge)
- [19. File không được commit](#19-file-không-được-commit)
- [20. Quản lý secret](#20-quản-lý-secret)
- [21. Bảo mật PPO model](#21-bảo-mật-ppo-model)
- [22. Mục đích của AI Log](#22-mục-đích-của-ai-log)
- [23. AI được phép hỗ trợ](#23-ai-được-phép-hỗ-trợ)
- [24. AI không được tự quyết định](#24-ai-không-được-tự-quyết-định)
- [25. Quy trình sử dụng AI](#25-quy-trình-sử-dụng-ai)
- [26. Nội dung bắt buộc của AI Log](#26-nội-dung-bắt-buộc-của-ai-log)
- [27. Trạng thái sử dụng output AI](#27-trạng-thái-sử-dụng-output-ai)
- [28. Vị trí lưu AI Log](#28-vị-trí-lưu-ai-log)
- [29. AI Assistance Log Template](#29-ai-assistance-log-template)
- [30. Ví dụ AI Log](#30-ví-dụ-ai-log)
- [31. Nguyên tắc phân công](#31-nguyên-tắc-phân-công)
- [32. Phạm Nguyễn Hùng Nguyên – 2A202601279](#32-phạm-nguyễn-hùng-nguyên--2a202601279)
- [33. Tống Duy An – 2A202601995](#33-tống-duy-an--2a202601995)
- [34. Phạm Thái Sơn – 2A202601984](#34-phạm-thái-sơn--2a202601984)
- [35. Nguyễn Hữu Khánh Tùng – 2A202601781](#35-nguyễn-hữu-khánh-tùng--2a202601781)
- [36. Ma trận RACI](#36-ma-trận-raci)
- [37. AI và Backend](#37-ai-và-backend)
- [38. AI và Frontend](#38-ai-và-frontend)
- [39. Simulator và Backend](#39-simulator-và-backend)
- [40. Simulator và Frontend](#40-simulator-và-frontend)
- [41. PPO Model Registry](#41-ppo-model-registry)
- [42. Quy trình tích hợp](#42-quy-trình-tích-hợp)
- [43. Giải quyết bất đồng kỹ thuật](#43-giải-quyết-bất-đồng-kỹ-thuật)
- [44. Definition of Done cho task](#44-definition-of-done-cho-task)
- [45. Definition of Done cho Gate G1](#45-definition-of-done-cho-gate-g1)
- [46. Release process](#46-release-process)
- [47. Trách nhiệm deployment](#47-trách-nhiệm-deployment)
- [48. Trách nhiệm demo](#48-trách-nhiệm-demo)
- [49. Checklist trước commit](#49-checklist-trước-commit)
- [50. Checklist trước Pull Request](#50-checklist-trước-pull-request)
- [51. Checklist trước nộp Gate G1](#51-checklist-trước-nộp-gate-g1)

---

Mỗi phần được gắn một nhãn: **[Hiện trạng]** đã có và xác minh được
trong repository · **[Quy ước nhóm]** nhóm thống nhất áp dụng từ Gate G1
· **[Đề xuất]** chưa áp dụng, sẽ triển khai sau.

---

## 1. Thông tin tài liệu

| Mục | Nội dung |
|---|---|
| Tên dự án | RAV19 – PlanBench |
| Tên đề tài | Agentic AI PlanBench – Nền tảng thiết lập, thực thi và đánh giá benchmark cho thuật toán điều hướng robot AMR/AGV |
| Repository | https://github.com/hungnguyen-1601/T011-rav19-planbench |
| Phiên bản tài liệu | 1.0 |
| Trạng thái | Draft for Gate G1 |
| Ngày cập nhật | 2026-08-02 |
| Phạm vi | Gate G1 – tổ chức repository, Git workflow, phân công, kiểm thử, bảo mật, AI Log |

**Team Lead**

| | |
|---|---|
| Họ tên | Phạm Nguyễn Hùng Nguyên |
| Mã sinh viên | 2A202601279 |
| Vai trò | Team Lead – AI, Robotics, Simulation & System Integration Lead |

Remote đã xác minh bằng `git remote -v`; kết quả trùng với repository dự
kiến.

---

## 2. Mục tiêu tài liệu

Tài liệu này quy định cách nhóm làm việc trên repository, gồm:

- **Cấu trúc repository** — cái gì nằm ở đâu và vì sao.
- **Git workflow** — branch, commit, Pull Request, review.
- **Trách nhiệm thành viên** và **module ownership**.
- **Kiểm thử** và các cổng chất lượng trước khi merge.
- **Bảo mật** và quản lý secret.
- **Sử dụng AI có trách nhiệm** trong quá trình phát triển.
- **AI Log** — ghi lại AI đã hỗ trợ gì và con người đã kiểm tra thế nào.
- **Khả năng truy vết** từ yêu cầu → code → test → kết quả.

---

## 3. Nguyên tắc làm việc chung

**[Quy ước nhóm]** — áp dụng từ Gate G1.

1. **GitHub repository là nguồn sự thật duy nhất.**
2. **Mọi thay đổi phải có branch, commit hoặc Pull Request rõ ràng.**
3. **Không phát triển tính năng lớn trực tiếp trên `main`.**
4. **Output do AI tạo phải được con người đọc, sửa và kiểm tra.**
5. **Không tuyên bố test pass nếu chưa chạy;** báo cáo phải là output
   lệnh thật.
6. **Không commit secret.**
7. **Không commit runtime artifact không cần thiết.**
8. **Thay đổi quan trọng phải được Team Lead review.**
9. **Mỗi module có một người triển khai chính.**
10. **Team Lead tham gia toàn bộ dự án.**
11. **Ưu tiên bằng chứng, test và dữ liệu hơn cảm tính.**
12. **Không merge khi chưa đáp ứng Definition of Done.**

---

## 4. Cấu trúc repository thực tế

**[Hiện trạng]** — xác minh bằng `git ls-files` (305 file được theo dõi)
và `find . -maxdepth 3 -type d`.

```text
.
├── apps/
│   ├── api/planbench_api/       FastAPI: routers, services, db, auth,
│   │                            model registry, chat service
│   └── web/src/                 Next.js 15 + React 19 + TypeScript
│       ├── app/                 17 route (page.tsx)
│       ├── components/          AppShell, MapCanvas, Scene25D, ModelUpload…
│       └── lib/                 API client, i18n, theme, navigation
├── packages/                    Thư viện Python thuần — không import
│   │                            FastAPI, ROS2 hay frontend
│   ├── schemas/                 Pydantic domain models (nguồn sự thật)
│   ├── planning/                A*, DWA, common planner interfaces
│   ├── metrics/                 Công thức metric
│   └── benchmark/               Algorithm registry, BenchmarkSpec, runner,
│                                scenario library (10 scenario)
├── services/
│   ├── simulator/               SimulationEngine, LiDAR, collision,
│   │                            kinematics, nav_stack, episode_runner
│   ├── agent_service/           Provider abstraction, tools, evidence,
│   │                            RAG, report, workflow
│   └── tracking/                MLflow adapter + null tracker
├── ml/planbench_rl/             Gymnasium env, observation, rewards,
│                                policy loader, training script
├── ros2_ws/src/                 5 ROS2 package (simulator node, Nav2
│                                bringup, bridge, msgs, runner)
├── alembic/versions/            3 migration
├── tests/                       pytest — core + tests/api/
├── scripts/                     demo, kiểm tra provider, dev_stack.sh,
│                                train_ppo.py
├── docker/                      Dockerfile.api, Dockerfile.web
├── docs/                        Tài liệu kỹ thuật + gate-g1/
├── .env.example                 Tên biến, giá trị trống
├── .gitignore
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt             Phụ thuộc lõi
├── requirements-optional.txt    torch, SB3, MLflow, LLM provider
└── README.md
```

### Source code

`apps/`, `packages/`, `services/`, `ml/`, `ros2_ws/src/`, `alembic/`,
`scripts/`. Đây là phần được commit và dùng để phát triển sản phẩm.
`packages/` và `services/simulator/` là thư viện Python thuần, không
import FastAPI hay frontend.

### Tests

`tests/` — unit test cho core, `tests/api/` cho integration test qua
`TestClient`. Frontend test nằm cạnh mã nguồn trong
`apps/web/src/**/__tests__/`.

### Documentation

`README.md`, `docs/` (kiến trúc, API contract, deployment, frontend,
agent, ROS2, implementation status, test report, known limitations), và
`docs/gate-g1/` (bốn deliverable của Gate G1).

### Generated files

**[Hiện trạng]** — bị `.gitignore` chặn: `__pycache__/`, `.next/`,
`node_modules/`, `.pytest_cache/`, `.ruff_cache/`, `*.egg-info/`,
`ros2_ws/build|install|log/`, `*.tsbuildinfo`.

### Runtime data

`artifacts/` (trajectory, report, model upload), `mlruns/` (MLflow
local), `.run/` (PID và log của `scripts/dev_stack.sh`), `*.sqlite`,
`*.db`, `*.log`. Tất cả đều nằm trong `.gitignore`.

### Local-only files

`.env` (và mọi `.env.*` trừ `.env.example`), `.venv/`, cache, database
local, file người dùng tải lên. Không bao giờ được commit.

### Production storage

**[Đề xuất]** — chưa triển khai. Database PostgreSQL, object storage cho
artifact và model storage sẽ là dịch vụ bên ngoài repository. Lớp
`ModelStorage` đã có sẵn interface; hiện mới cài đặt bản lưu trên đĩa
cục bộ.

---

## 5. Bộ tài liệu Gate G1

| File | Vai trò |
|---|---|
| [01-brief.md](./01-brief.md) | Một trang A4: bài toán, người dùng, giải pháp, phạm vi MVP, ràng buộc |
| [02-prd.md](./02-prd.md) | Yêu cầu sản phẩm đầy đủ: personas, user stories, functional requirements, data model, kiến trúc, acceptance criteria, feature status |
| [03-wireframe-ui-flow.md](./03-wireframe-ui-flow.md) | Sitemap, luồng người dùng, wireframe low-fidelity, empty/error state, responsive, accessibility |
| [04-github-ai-log-setup.md](./04-github-ai-log-setup.md) | Tài liệu này: tổ chức repository, Git workflow, phân công, kiểm thử, bảo mật, AI Log |

---

## 6. Trạng thái Git hiện tại

**[Hiện trạng]** — xác minh tại thời điểm viết tài liệu.

| Mục | Giá trị |
|---|---|
| Remote `origin` | `https://github.com/hungnguyen-1601/T011-rav19-planbench.git` (fetch và push) |
| Branch hiện tại | `main` |
| Branch cục bộ khác | `backup-before-squash` |
| Branch từ xa | `origin/main` |
| Số tag | 0 |
| File được theo dõi | 305 |
| GitHub Actions | Chưa có (`.github/` chưa tồn tại) |

10 commit gần nhất:

```text
9afdd90 frontend + API contract, deployment
2a7ed93 requirement.txt
1fc2cc4 stop command
7705a8a system information page
99ec0e6 login logout
d17b695 api-gemini
07bc734 fix login
f91f5cd fix login
d8218c1 Docker Compose + PostgreSQL persistence
2e8a993 2.5D interface (Three.js) + UI for M5/M6/M8 features
```

Những điểm repository chưa có, ghi rõ để không nhầm với quy ước:

- Chỉ có một branch phát triển là `main`; chưa có branch `feature/*`
  nào. Chiến lược branch ở [§7](#7-chiến-lược-branch) là quy ước áp dụng
  từ Gate G1.
- Commit hiện tại chưa theo Conventional Commits. Quy ước ở
  [§9](#9-commit-convention) áp dụng cho commit từ Gate G1 trở đi; không
  viết lại lịch sử đã có.
- Chưa có Pull Request nào được ghi nhận trong repository cục bộ.
- Chưa có tag.
- Chưa có CI; quality gate ở [§18](#18-quality-gate-trước-khi-merge)
  hiện chạy thủ công.

---

## 7. Chiến lược branch

**[Quy ước nhóm]** — áp dụng từ Gate G1.

### Branch ổn định

- **`main`** — phiên bản tích hợp, đã kiểm tra và có thể demo. Đây là
  branch duy nhất được coi là "đúng".

### Branch theo feature hoặc task

Branch được tạo theo công việc, không theo người. Tên branch đề xuất:

```text
feature/ai-conversation-flow
feature/simulation-engine
feature/dwa-dynamic-obstacle
feature/ppo-adapter
feature/benchmark-api
feature/model-registry
feature/live-simulation-ui
feature/frontend-ux
feature/deployment
fix/ppo-model-validation
fix/benchmark-metrics
docs/gate-g1
test/simulation-regression
```

### Quy tắc

- Không phát triển tính năng lớn trực tiếp trên `main`.
- Mỗi branch giải quyết **một mục tiêu**.
- Cập nhật code mới nhất từ `main` **trước khi** mở PR.
- Xử lý conflict **trên branch chức năng**, không đẩy conflict vào
  `main`.
- Xóa branch sau khi merge nếu không còn dùng.
- Hotfix phải có mô tả và bằng chứng.
- Không dùng một branch cho quá nhiều task không liên quan.

---

## 8. Quy tắc đặt tên branch

**[Quy ước nhóm]**

```text
<type>/<short-description>
```

| Type | Dùng khi |
|---|---|
| `feature` | Thêm chức năng mới |
| `fix` | Sửa lỗi |
| `docs` | Chỉ sửa tài liệu |
| `test` | Chỉ thêm hoặc sửa test |
| `refactor` | Đổi cấu trúc, không đổi hành vi |
| `chore` | Việc vặt: cấu hình, dọn dẹp, phụ thuộc |
| `deployment` | Triển khai, môi trường, image |

`<short-description>` viết thường, nối bằng gạch ngang, mô tả kết quả:
`feature/model-registry`.

---

## 9. Commit convention

**[Quy ước nhóm]** — áp dụng cho commit từ Gate G1 trở đi. Lịch sử trước
đó giữ nguyên, không viết lại.

Conventional Commits ở mức đơn giản:

| Tiền tố | Ý nghĩa |
|---|---|
| `feat:` | Chức năng mới |
| `fix:` | Sửa lỗi |
| `docs:` | Tài liệu |
| `test:` | Test |
| `refactor:` | Tái cấu trúc |
| `chore:` | Việc vặt |
| `perf:` | Cải thiện hiệu năng |
| `build:` | Hệ thống build, phụ thuộc |
| `ci:` | Tích hợp liên tục |

Ví dụ:

```text
feat(ai): add multi-turn benchmark clarification
feat(sim): support dynamic warehouse obstacles
feat(backend): persist benchmark episodes
feat(web): add PPO model selector
fix(dwa): prevent oscillation near narrow doorway
fix(auth): attach bearer token to protected requests
docs: complete Gate G1 deliverables
test(sim): add deterministic seed regression tests
```

### Quy tắc

- Mỗi commit tập trung vào một thay đổi logic.
- Message mô tả kết quả, không phải hành động.
- Không dùng message như `update code` hay `fix bug`.
- Không commit: build output · cache · secret · database local · model
  lớn · file người dùng tải lên · runtime artifact.

---

## 10. Pull Request workflow

**[Quy ước nhóm]**

### Nội dung bắt buộc của một PR

| Mục | Ghi chú |
|---|---|
| Mục tiêu | PR này giải quyết gì |
| Phạm vi | Cái gì **không** nằm trong PR này |
| Issue/task liên quan | Liên kết |
| Module bị ảnh hưởng | AI · Simulator · Backend · Frontend · Model Registry… |
| File chính đã sửa | Danh sách ngắn |
| API contract | Bắt buộc khi thay đổi backend |
| Ảnh hoặc video | Bắt buộc khi thay đổi UI |
| Test đã chạy | Lệnh cụ thể |
| Kết quả test thực tế | **Output thật**, không phải "đã pass" |
| Rủi ro | Cái gì có thể hỏng |
| Cách kiểm tra thủ công | Các bước để reviewer tự xác nhận |
| Cách rollback | Nếu merge rồi mới phát hiện vấn đề |
| AI Log liên quan | Đường dẫn tới file log |
| Checklist Definition of Done | [§44](#44-definition-of-done-cho-task) |

### Luồng

```text
Requirement hoặc bug
→ tạo Issue/Task
→ tạo branch
→ phát triển
→ tự kiểm tra
→ chạy test
→ cập nhật AI Log
→ push branch
→ mở Pull Request
→ Team Lead/module owner review
→ sửa feedback
→ chạy regression
→ merge vào main
```

---

## 11. Quy tắc code review

**[Quy ước nhóm]**

- **Team Lead review** thay đổi kiến trúc và tích hợp.
- **Module owner review** phần chuyên môn của mình.
- **Không tự merge PR quan trọng chưa được review.**
- Reviewer phải kiểm tra code, test và dữ liệu.
- Các vùng cần review kỹ hơn: AI · simulator · thuật toán robot ·
  metrics · authentication · upload model · bảo mật.
- **Thiếu test hoặc evidence thì chưa được merge.**
- Bất đồng kỹ thuật: Team Lead quyết định cuối cùng và ghi lại quyết
  định.

---

## 12. Cấu trúc task

**[Quy ước nhóm]**

Mỗi task gồm: **Title · Mô tả · Owner · Module · Priority · Acceptance
criteria · Dependency · Label · Branch · Pull Request · Trạng thái ·
Evidence**.

### Trạng thái

`Backlog` → `Ready` → `In progress` → `In review` → `Testing` → `Done`,
cộng thêm `Blocked` khi bị chặn bởi phụ thuộc bên ngoài.

### Label

`ai` · `robotics` · `simulation` · `backend` · `frontend` · `benchmark`
· `ppo` · `documentation` · `bug` · `security` · `deployment` ·
`priority-high`

---

## 13. Chuỗi truy vết

**[Quy ước nhóm]**

```text
Requirement
→ Issue/Task
→ Owner
→ Branch
→ Commit
→ Pull Request
→ Tests
→ AI Log
→ Main
→ Release/Demo
```

Với mỗi tính năng quan trọng, phải trả lời được:

- Ai phụ trách?
- AI được dùng ở bước nào?
- Output AI đã bị sửa gì?
- Test nào đã chạy, và kết quả thật là gì?
- Commit hoặc PR nào triển khai?
- Reviewer nào đã kiểm tra?
- Bằng chứng nó hoạt động là gì?

---

## 14. Unit test

**[Hiện trạng]** — `tests/` đã có unit test cho: A\*, DWA, collision
detection, LiDAR, kinematics, geometry, occupancy grid, path utils,
dynamic obstacles, metrics, scenario library, benchmark engine, approval
state machine, artifacts, failure analysis, agent specs/tools/RAG/
report, và RL.

Frontend: `apps/web/src/**/__tests__/` cho lib và components.

**[Quy ước nhóm]** — mọi module mới thuộc các nhóm trên phải kèm unit
test trong cùng PR.

Lệnh (từ README):

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
PYTHONPATH= .venv/bin/pytest tests/ -v
```

`PYTHONPATH=` (rỗng) là bắt buộc khi shell đã source ROS2 Jazzy.

Frontend:

```bash
cd apps/web
npx vitest run
```

---

## 15. Integration test

**[Hiện trạng]** — `tests/api/` kiểm tra API qua `TestClient`: maps,
scenarios, simulations, benchmarks, auth, OAuth (bằng mock provider),
users, reviews, agent, chat, models, SQL backend, repository và
migration.

**[Quy ước nhóm]** — các cặp tích hợp phải có test:

- API ↔ database;
- benchmark service ↔ simulator;
- algorithm adapter ↔ Simulation Engine;
- PPO model ↔ Robot Profile (compatibility);
- AI proposal ↔ backend validation;
- authentication và authorization;
- optional review;
- evidence và report;
- kênh live simulation.

**Không gọi OAuth thật trong test tự động** — dùng mock provider
response.

---

## 16. End-to-end test

**[Quy ước nhóm]** — hai luồng phải chạy được trước mỗi lần demo.

Luồng chính:

```text
Đăng nhập
→ chọn hoặc import scenario
→ chạy Live Simulation
→ tạo benchmark
→ chạy nhiều seed
→ xem episode
→ xem metrics
→ hỏi AI giải thích
→ tự accept hoặc gửi review
```

Luồng PPO:

```text
Tạo Robot Profile
→ upload PPO model
→ kiểm tra compatibility
→ chọn astar+ppo
→ tạo benchmark
→ chạy
→ xem kết quả
```

**[Đề xuất]** — hiện hai luồng được kiểm bằng integration test và thao
tác thủ công. Bộ E2E tự động trên trình duyệt là việc sau Gate G1.

---

## 17. Regression test

**[Quy ước nhóm]** — các bất biến phải được bảo vệ:

- Seed vẫn tái lập.
- Metrics không thay đổi ngoài dự kiến.
- DWA vẫn chạy khi chưa có PPO model.
- AI không tự chạy benchmark.
- AI không sửa metric.
- AI không bịa citation.
- Benchmark cũ vẫn đọc được.
- Login và authorization không bị phá.
- Frontend vẫn build được.

---

## 18. Quality gate trước khi merge

**[Quy ước nhóm]** — hiện chạy **thủ công**; chưa có CI.

| # | Cổng | Lệnh |
|---|---|---|
| 1 | Formatter | `.venv/bin/ruff format --check .` |
| 2 | Lint | `.venv/bin/ruff check .` |
| 3 | Test backend | `PYTHONPATH= .venv/bin/pytest tests/ -q` |
| 4 | Type-check frontend | `cd apps/web && npx tsc --noEmit` |
| 5 | Test frontend | `cd apps/web && npx vitest run` |
| 6 | Build production | `cd apps/web && npx next build` |

Cộng thêm:

- Migration được kiểm tra khi sửa database.
- Không có secret trong diff.
- Không có debug log thừa.
- Error state được xử lý (không để lỗi thư viện lọt ra giao diện).
- Tài liệu được cập nhật.
- AI Log được ghi khi có dùng AI.
- PR đã được review.
- Luồng end-to-end chính không bị phá.

Số liệu test đã chạy thật được ghi trong
[../TEST_REPORT.md](../TEST_REPORT.md) kèm output lệnh.

**[Đề xuất]** — đưa sáu cổng trên vào GitHub Actions để chạy tự động
trên mỗi PR.

---

## 19. File không được commit

**[Hiện trạng]** — `.gitignore` đã chặn các nhóm sau.

| Nhóm | Mẫu |
|---|---|
| Secret và môi trường | `.env`, `.env.*` (trừ `.env.example`), `*.pem`, `*.key`, `secrets.json`, `credentials.json` |
| Python | `__pycache__/`, `*.py[cod]`, `build/`, `dist/`, `*.egg-info/` |
| Môi trường ảo | `.venv/`, `venv/`, `env/` |
| Cache test và lint | `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.coverage*`, `htmlcov/` |
| Node và Next.js | `node_modules/`, `.next/`, `out/`, `.turbo/`, `*.tsbuildinfo`, `.eslintcache` |
| ROS2 | `ros2_ws/build/`, `ros2_ws/install/`, `ros2_ws/log/` |
| Runtime artifact | `artifacts/` (gồm trajectory, report và **model người dùng tải lên**) |
| MLflow | `mlruns/`, `mlflow.db`, `mlartifacts/` |
| Model và checkpoint | `ml/checkpoints/`, `ml/**/*.zip`, `models/`, `*.pt`, `*.pth`, `*.ckpt` |
| Database local | `*.sqlite`, `*.sqlite3`, `*.db`, `pgdata/` |
| Log và tạm | `*.log`, `logs/`, `tmp/`, `*.tmp`, `*.bak` |
| Dev stack cục bộ | `.run/` (PID và log của `scripts/dev_stack.sh`) |
| Editor và OS | `.idea/`, `.vscode/`, `*.swp`, `.DS_Store` |

`artifacts/` bao trùm cả thư mục model upload (mặc định
`artifacts/models`), nên file người dùng tải lên không lọt vào
repository.

### Biến môi trường — chỉ tên, không giá trị

`.env.example` được theo dõi; nó chứa **tên biến với giá trị trống**:

```text
GEMINI_API_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
AUTH_SECRET=
DATABASE_URL=
```

Tài liệu này không ghi giá trị thật của bất kỳ biến nào.

---

## 20. Quản lý secret

**[Quy ước nhóm]**

### Local

- Dùng `.env`; file này **phải** nằm trong `.gitignore` (đã có).
- Dùng `.env.example` làm mẫu, **giá trị để trống**.
- Mỗi thành viên tự cấu hình trên máy mình. Không gửi secret qua chat
  hay email, không đưa vào AI Log.
- Khi cần thêm biến mới: cập nhật `.env.example` với giá trị trống.

### Deployment

- Dùng Environment Variables/Secrets của nền tảng triển khai.
- Không hardcode trong mã nguồn hay Dockerfile.
- **Không đưa Client Secret xuống frontend.** Trao đổi mã OAuth diễn ra
  ở phía server.
- Không ghi secret ra log.
- Phân biệt biến public (`NEXT_PUBLIC_*`) và private: giá trị có tiền tố
  `NEXT_PUBLIC_` sẽ nằm trong bundle gửi tới trình duyệt.
- Rotate key ngay nếu nghi ngờ bị lộ.

---

## 21. Bảo mật PPO model

**[Hiện trạng]** — đã triển khai trong `apps/api/planbench_api/model_registry.py`
và `model_storage.py`.

### Ba loại file

| File | Là gì | Chạy được không |
|---|---|---|
| `.zip` | Checkpoint Stable-Baselines3 | **Có** — thứ duy nhất chạy được như một policy |
| `.json` | Metadata mô tả model | Không — được validate, không bao giờ thực thi |
| `.pdf` | Tài liệu cho người đọc | Không |

**Không coi PDF là model chạy được.** Chọn `.pdf` ở ô model sẽ bị từ
chối.

### Đã làm

- Kiểm tra phần mở rộng **trước khi ghi byte đầu tiên**.
- Cưỡng chế giới hạn kích thước **trong lúc ghi**, không phải sau.
- Sanitize filename: mọi dấu phân cách bị loại.
- **Chống path traversal hai lớp**: đường dẫn lưu trữ dựng hoàn toàn từ
  ID, và lớp lưu trữ vẫn `resolve()` rồi kiểm tra kết quả có nằm trong
  thư mục gốc không.
- Tính **SHA-256** của đúng byte đã ghi.
- Kiểm tra quyền: chỉ owner hoặc admin được xóa.
- **Không extract tùy tiện** — chỉ đọc bảng mục lục của zip.
- **Không `pickle.load` trong tiến trình API.**
- **Không commit model người dùng lên GitHub** (`artifacts/` đã bị
  ignore).

### Chưa làm

**[Hiện trạng]** — khi benchmark PPO chạy, checkpoint được giải tuần tự
trong tiến trình worker, không phải trong sandbox có quota. Chưa có
container riêng, chưa có giới hạn CPU/RAM, chưa có timeout cứng khi nạp.

**Không được kết luận model upload là an toàn tuyệt đối.** Chi tiết đầy
đủ ở [../KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md) mục #77.

**[Đề xuất]** — chạy worker benchmark trong container riêng có quota,
hoặc chỉ cho phép upload từ tài khoản đã được kiểm duyệt.

---

## 22. Mục đích của AI Log

**[Quy ước nhóm]** — áp dụng từ Gate G1.

AI Log dùng để:

- **Minh bạch** việc sử dụng AI trong dự án.
- Ghi lại **AI hỗ trợ task nào**.
- Ghi lại **quyết định của con người**.
- **Chứng minh output AI đã được kiểm tra**, không phải chép thẳng.
- **Truy vết lỗi** — khi một tính năng hỏng, biết được nó ra đời thế
  nào.
- Hỗ trợ **code review**.
- Phục vụ **đánh giá Gate**.
- Phân biệt **AI đề xuất gì** và **nhóm thực sự chấp nhận gì**.

Không cần sao chép toàn bộ hội thoại; tóm tắt đủ để người khác kiểm
chứng lại được.

**Không được ghi secret hoặc dữ liệu nhạy cảm vào AI Log.**

---

## 23. AI được phép hỗ trợ

**[Quy ước nhóm]**

AI có thể hỗ trợ: phân tích yêu cầu · đề xuất kiến trúc · viết code ban
đầu · refactor · viết test · chẩn đoán lỗi · tạo tài liệu · tạo
wireframe · đề xuất user flow · giải thích thuật toán · tạo prompt ·
review code sơ bộ · tạo dữ liệu test không nhạy cảm · cải thiện UX ·
giải thích kết quả benchmark **dựa trên evidence**.

Trong mọi trường hợp, AI tạo bản nháp; thành viên đọc, sửa, kiểm tra và
chịu trách nhiệm.

---

## 24. AI không được tự quyết định

**[Quy ước nhóm]** — áp dụng cho cả AI hỗ trợ phát triển và AI Assistant
trong sản phẩm.

AI không được tự:

- merge code;
- push lên `main`;
- sửa metric đã ghi;
- tạo kết quả benchmark giả;
- accept/reject kết quả;
- approve benchmark;
- chứng nhận an toàn;
- điều khiển robot thật;
- đọc hoặc công khai secret;
- bịa citation;
- bịa evidence;
- tuyên bố test pass khi chưa chạy;
- xử lý model không tin cậy mà không có kiểm soát;
- thay con người đưa ra quyết định cuối cùng.

Với AI Assistant trong sản phẩm, các giới hạn này được thực thi ở tầng
API: không tồn tại endpoint nào cho phép trợ lý chạy, duyệt hay chấp
nhận kết quả. Chi tiết ở
[PRD §28](./02-prd.md#28-safety-và-human-in-the-loop).

---

## 25. Quy trình sử dụng AI

**[Quy ước nhóm]**

```text
Thành viên xác định task
→ chuẩn bị prompt
→ AI tạo đề xuất
→ thành viên đọc và đánh giá
→ chỉnh sửa output
→ chạy test hoặc kiểm tra thủ công
→ ghi AI Log
→ mở Pull Request
→ reviewer kiểm tra
→ chấp nhận, chỉnh sửa hoặc loại bỏ output AI
```

Ghi AI Log sau khi chạy test, vì log phải chứa kết quả thật.

---

## 26. Nội dung bắt buộc của AI Log

**[Quy ước nhóm]**

Mỗi AI Log gồm: ngày giờ · họ tên · mã sinh viên · module · task · công
cụ AI · model AI (nếu cần) · mục tiêu · prompt tóm tắt · output tóm tắt
· file được tạo hoặc sửa · lệnh test · kết quả test · lỗi phát hiện ·
thay đổi do con người thực hiện · quyết định cuối · branch · commit · PR
· reviewer · rủi ro · evidence.

---

## 27. Trạng thái sử dụng output AI

**[Quy ước nhóm]**

| Trạng thái | Nghĩa |
|---|---|
| `Accepted as-is` | Output được dùng nguyên vẹn. Chỉ dùng khi đã đọc kỹ và đã chạy test |
| `Accepted with modifications` | Hướng đi đúng nhưng thành viên đã sửa; phần sửa phải được ghi lại |
| `Partially accepted` | Chỉ một phần được dùng; ghi rõ phần nào và vì sao |
| `Rejected` | Không dùng; ghi lý do |
| `Pending verification` | Đã dùng nhưng **chưa kiểm chứng đầy đủ**. Không được merge ở trạng thái này |

---

## 28. Vị trí lưu AI Log

**[Đề xuất]** — thư mục `docs/ai-logs/` **chưa tồn tại** trong
repository tại thời điểm viết tài liệu. Đây là cấu trúc nhóm thống nhất
áp dụng **sau Gate G1**.

```text
docs/ai-logs/
├── README.md
├── templates/
│   └── ai-assistance-log-template.md
└── 2026-08/
    ├── 2026-08-02-gate-g1-docs.md
    ├── 2026-08-02-ai-chatbot-ui.md
    └── 2026-08-02-dwa-benchmark.md
```

Quy tắc tên file:

```text
YYYY-MM-DD-task-short-name.md
```

Gom theo tháng.

---

## 29. AI Assistance Log Template

**[Quy ước nhóm]** — mẫu chuẩn, sẽ đặt tại
`docs/ai-logs/templates/ai-assistance-log-template.md`.

````markdown
# AI Assistance Log

## 1. Metadata

- Date and time:
- Member:
- Student ID:
- Module:
- Task:
- AI tool:
- AI model:
- Related issue:
- Related branch:
- Related commit:
- Related pull request:
- Reviewer:

## 2. Goal

Mục tiêu cụ thể của lần sử dụng AI.

## 3. Prompt summary

Tóm tắt yêu cầu, ràng buộc và dữ liệu đầu vào.

Không ghi API key, token, password hoặc dữ liệu nhạy cảm.

## 4. AI output summary

AI đã đề xuất hoặc tạo ra nội dung gì.

## 5. Files changed

| File | Change | Reason |
|---|---|---|
| | | |

## 6. Human verification

Mô tả thành viên đã kiểm tra:

- Logic;
- Correctness;
- Security;
- Compatibility;
- UX;
- Algorithm;
- Metrics;
- Regression.

## 7. Tests executed

```text
Command:
Result:
```

## 8. Problems found

Các lỗi hoặc hạn chế trong output AI.

## 9. Human modifications

Những phần con người đã sửa.

## 10. Decision

- [ ] Accepted as-is
- [ ] Accepted with modifications
- [ ] Partially accepted
- [ ] Rejected
- [ ] Pending verification

Lý do:

## 11. Risks and limitations

## 12. Evidence

- Screenshot:
- Test output:
- Benchmark ID:
- Episode ID:
- Commit:
- Pull Request:
````

---

## 30. Ví dụ AI Log

> **Đây là ví dụ minh họa cách điền template, không phải log thực tế.**
> Các trường commit, PR và reviewer để placeholder vì tại thời điểm viết
> tài liệu chưa có commit hay PR tương ứng, và tài liệu này không bịa
> chúng.

````markdown
# AI Assistance Log

## 1. Metadata

- Date and time: 2026-08-02
- Member: Phạm Nguyễn Hùng Nguyên
- Student ID: 2A202601279
- Module: Documentation – Gate G1
- Task: Soạn bộ tài liệu Gate G1 (Brief, PRD, Wireframe & UI Flow)
- AI tool: Trợ lý lập trình AI
- AI model: [CẦN ĐIỀN: Model AI]
- Related issue: [CẦN ĐIỀN: Issue]
- Related branch: docs/gate-g1
- Related commit: [CẦN ĐIỀN: Commit]
- Related pull request: [CẦN ĐIỀN: Pull Request]
- Reviewer: [CẦN ĐIỀN: Reviewer]

## 2. Goal

Tạo ba deliverable của Gate G1 dựa trên codebase thật, trong đó mỗi
tính năng được ghi trạng thái Completed/In progress/Planned phải dẫn
được về file cụ thể trong repository.

## 3. Prompt summary

Yêu cầu: đọc repository trước khi viết; không ghi tính năng là hoàn
thành nếu code không chứng minh được; viết bằng tiếng Việt; dùng
Mermaid thay vì HTML; không đưa secret hay đường dẫn cá nhân vào tài
liệu.

Ràng buộc: không sửa mã nguồn ứng dụng, không commit, không push.

## 4. AI output summary

AI đọc cấu trúc thư mục, danh sách route frontend, danh sách router
backend, algorithm registry, scenario library, migration và thư mục
test; sau đó soạn ba tài liệu Markdown kèm sơ đồ Mermaid và hai bảng
đối chiếu trạng thái tính năng với đường dẫn file.

## 5. Files changed

| File | Change | Reason |
|---|---|---|
| docs/gate-g1/README.md | Tạo mới | Trang mục lục dẫn tới các deliverable |
| docs/gate-g1/01-brief.md | Tạo mới | Deliverable 1 |
| docs/gate-g1/02-prd.md | Tạo mới | Deliverable 2 |
| docs/gate-g1/03-wireframe-ui-flow.md | Tạo mới | Deliverable 3 |
| docs/gate-g1/assets/README.md | Tạo mới | Quy ước thư mục tài nguyên |

## 6. Human verification

- Correctness: đối chiếu từng dòng bảng Feature status với đường dẫn
  thật; kiểm tra 111 đường dẫn được nhắc tới trong tài liệu.
- Security: quét tài liệu tìm secret và đường dẫn cá nhân.
- Compatibility: kiểm tra link tương đối và anchor mục lục.
- UX: đọc lại wireframe để bảo đảm khớp với route thật của frontend.

## 7. Tests executed

```text
Command: kiểm tra link tương đối và anchor trong docs/gate-g1
Result:  0 link hỏng, 0 anchor thiếu

Command: kiểm tra cấu trúc 13 block Mermaid
Result:  0 vấn đề (sau khi sửa script kiểm cho đúng cú pháp erDiagram
         và hình trụ [(...)])

Command: grep tìm secret và đường dẫn cá nhân trong docs/gate-g1
Result:  không có
```

## 8. Problems found

- Bản đầu ghi một số tính năng là Completed mà chưa dẫn được file
  chứng minh; phải hạ xuống In progress.
- Script kiểm Mermaid do AI viết báo 3 lỗi giả: nó hiểu nhầm ký hiệu
  quan hệ `||--o{` của erDiagram là ngoặc nhọn không cân, và hiểu nhầm
  hình trụ `[(Database)]` là ngoặc đơn sai trong nhãn node.

## 9. Human modifications

- Hạ trạng thái các tính năng chưa kiểm chứng được xuống In progress
  (PostgreSQL, Docker, ROS2, MLflow, training pipeline).
- Sửa script kiểm Mermaid để loại hai trường hợp dương tính giả.
- Bổ sung ghi chú rằng không chạy được Mermaid renderer thật trên máy.

## 10. Decision

- [ ] Accepted as-is
- [x] Accepted with modifications
- [ ] Partially accepted
- [ ] Rejected
- [ ] Pending verification

Lý do: cấu trúc và nội dung dùng được, nhưng phần đánh giá trạng thái
tính năng phải được con người đối chiếu lại với repository trước khi
chấp nhận.

## 11. Risks and limitations

- Không chạy được Mermaid renderer thật trên máy phát triển; sơ đồ mới
  được kiểm ở mức cấu trúc, cần xem lại trên GitHub sau khi push.
- Bảng Feature status phản ánh trạng thái tại một thời điểm; phải cập
  nhật khi code thay đổi.

## 12. Evidence

- Screenshot: [CẦN ĐIỀN: Ảnh chụp tài liệu trên GitHub]
- Test output: kết quả kiểm link, anchor, Mermaid và secret ở mục 7
- Benchmark ID: không áp dụng
- Episode ID: không áp dụng
- Commit: [CẦN ĐIỀN: Commit]
- Pull Request: [CẦN ĐIỀN: Pull Request]
````

---

## 31. Nguyên tắc phân công

**[Quy ước nhóm]**

Thứ tự mức độ bao quát và trách nhiệm:

1. **Phạm Nguyễn Hùng Nguyên** – 2A202601279
2. **Tống Duy An** – 2A202601995
3. **Phạm Thái Sơn** – 2A202601984
4. **Nguyễn Hữu Khánh Tùng** – 2A202601781

Thứ tự này thể hiện mức độ tham gia toàn dự án, quyền quyết định, trách
nhiệm tích hợp, trách nhiệm cuối cùng và mức độ sở hữu phần lõi. Mỗi
module vẫn có **một người triển khai chính**.

Team Lead phải: tham gia tất cả các phần · nắm kiến trúc · nắm AI · nắm
Robotics · nắm Simulation · tham gia Backend · tham gia Frontend · chịu
trách nhiệm tích hợp, deployment, demo và trách nhiệm cuối cùng.

---

## 32. Phạm Nguyễn Hùng Nguyên – 2A202601279

**Vai trò: Team Lead – AI, Robotics, Simulation & System Integration Lead**

### Trách nhiệm tổng thể

Tham gia toàn bộ dự án · phân tích đề bài · xác định phạm vi · thiết kế
kiến trúc tổng thể · chia task · theo dõi tiến độ · review code · xử lý
xung đột kỹ thuật · quyết định phương án tích hợp · **chịu trách nhiệm
cuối cùng**.

### Phụ trách chính — AI

AI Assistant · chatbot nhiều lượt · làm rõ yêu cầu · natural language →
`BenchmarkSpec` · structured output · prompt design · proposal card ·
result explanation · evidence retrieval · citation validation · report
generation · hallucination control · Human-in-the-loop · AI tool
permissions.

### Phụ trách chính và đồng phát triển — Robotics/Simulation

Simulation Engine · robot model · map/scenario · start/goal · static
obstacles · dynamic obstacles · replay · A\* · DWA · PPO · Pure Pursuit
· LiDAR · collision detection · deterministic seed · metrics · failure
analysis · benchmark fairness · conditions checksum.

Hùng Nguyên trực tiếp cùng Duy An phát triển Simulation và Robotics,
không chỉ review.

### Tham gia Backend

API contract · `BenchmarkSpec` · benchmark workflow · state machine ·
authorization · AI tool permissions · Model Registry architecture ·
Robot Profile architecture · evidence/report architecture · deployment
architecture.

### Tham gia Frontend

Product flow · UX/UI review · AI chatbot UX · Dashboard · Live
Simulation · Benchmark UI · PPO Model Registry · bảo đảm người mới sử
dụng được website.

### Trách nhiệm tích hợp

```text
User
→ AI conversation
→ BenchmarkSpec
→ Backend validation
→ Benchmark draft
→ Simulator
→ Metrics
→ Evidence
→ AI explanation
→ Human decision
```

### Trách nhiệm cuối cùng

Integration test · end-to-end test · regression test · deployment ·
release · demo · tài liệu · thuyết trình kiến trúc · thuyết trình AI ·
thuyết trình tích hợp robot.

### Đầu ra chính

Kiến trúc tổng thể · AI Assistant · phần lõi Simulation · tích hợp
AI–Backend–Simulator · benchmark end-to-end · bản deploy · demo cuối.

---

## 33. Tống Duy An – 2A202601995

**Vai trò: Robotics, Algorithm & Simulation Engineer**

### Phụ trách chính

Robot motion model · A\* Global Planner · DWA Local Planner · Pure
Pursuit · PPO adapter · LiDAR · collision detection · dynamic obstacles
· Robot Profile · benchmark scenarios · deterministic simulation ·
metrics · failure analysis · algorithm tests · performance optimization.

### Nhiệm vụ

- Xây chuyển động robot; kiểm soát vận tốc thẳng và vận tốc quay.
- Triển khai tìm đường và tránh vật cản.
- Mô phỏng sensor; triển khai vật cản động.
- Xây scenario `doorway`, `crossing_obstacle`, `sudden_stop` và
  `dynamic_warehouse`.
- Tính success, collision, timeout, travel time, path length, smoothness
  và clearance.
- Phân tích stuck, oscillation, collision và timeout.
- Kiểm tra khả năng tái lập theo seed.

### Phối hợp với Team Lead

Đồng phát triển Simulation Engine · thống nhất A\* + DWA · thống nhất
observation/action của PPO · kiểm tra metrics · phân tích episode lỗi ·
tích hợp thuật toán vào benchmark · cung cấp evidence cho AI · review
phần AI giải thích thuật toán.

### Đầu ra

Thuật toán robot · sensor simulation · scenarios · metrics · failure
analysis · algorithm tests · simulation results.

### Phần thuyết trình

Robot model · A\* · DWA · PPO · dynamic obstacles · metrics ·
simulation results.

---

## 34. Phạm Thái Sơn – 2A202601984

**Vai trò: Backend, Database & Platform Engineer**

### Phụ trách chính

FastAPI · API · database · migration · repository abstraction ·
authentication · Google OAuth · GitHub OAuth · nickname · benchmark
workflow · episode storage · review workflow · evidence/report storage ·
WebSocket · PPO Model Registry backend · Robot Profile backend ·
artifact storage · authorization · security · backend deployment.

### Nhiệm vụ

- API cho map, scenario, simulation và benchmark.
- Lưu benchmark, episode, metrics và trajectory.
- Authentication; optional review bằng nickname.
- Database và migrations.
- Upload PPO model; checksum; quyền truy cập model.
- API cho frontend và AI; storage; database production.
- CORS; environment; health check.

### Phối hợp với Team Lead

API contract · structured `BenchmarkSpec` · AI tool permissions ·
benchmark state machine · evidence validation · report validation ·
Model Registry architecture · deployment architecture · security review.

### Phối hợp với Duy An

Simulator API · algorithm adapter · metrics persistence · model
compatibility · Robot Profile · episode artifacts.

### Phối hợp với Khánh Tùng

Frontend API client · authentication UI · review workflow · benchmark
form · model upload · error handling.

### Đầu ra

Backend · database · migrations · authentication · benchmark workflow ·
optional review · Model Registry · storage · backend deployment · API
tests.

### Phần thuyết trình

Backend architecture · database · authentication · benchmark workflow ·
model storage · security.

---

## 35. Nguyễn Hữu Khánh Tùng – 2A202601781

**Vai trò: Frontend, Visualization & UX Engineer**

### Phụ trách chính

Next.js · TypeScript · Dashboard · App Shell · Sidebar · Top Bar · Map
Editor · Scenario Library · Live Simulation UI · Benchmark UI · Episode
Replay · Leaderboard · Algorithms · PPO Model Registry UI · Robot
Profile UI · AI chatbot UI · Reviews · System Information · responsive ·
accessibility · VI/EN · Light/Dark/System.

### Nhiệm vụ

- Phát triển frontend; kết nối API.
- Trực quan hóa robot, global path, actual trajectory, dynamic
  obstacles; playback controls.
- Benchmark form; model upload; compatibility status.
- AI chatbot; proposal card; result card.
- Review Inbox.
- Loading, empty, error và disabled states.
- Responsive desktop/mobile.

### Phối hợp với Team Lead

AI chatbot UX · product flow · user confirmation · đơn giản hóa giao
diện · proposal card · result explanation · Dashboard UX · benchmark
journey.

### Phối hợp với Thái Sơn

API integration · authentication UI · nickname · benchmark form · review
workflow · model upload · error mapping.

### Phối hợp với Duy An

Robot visualization · map visualization · dynamic obstacles ·
trajectory · metrics · replay.

### Đầu ra

Web UI · visualization · responsive UX · chatbot UI · Model Registry UI
· Review UI · frontend tests.

### Phần thuyết trình

User journey · Dashboard · Live Simulation · Benchmark UI · AI chatbot ·
responsive design.

---

## 36. Ma trận RACI

**[Quy ước nhóm]**

| Ký hiệu | Nghĩa |
|---|---|
| `A` | Accountable — chịu trách nhiệm cuối cùng |
| `R` | Responsible — trực tiếp thực hiện |
| `C` | Consulted — được tham vấn hoặc đồng phát triển |
| `I` | Informed — được cập nhật |

| Module | Hùng Nguyên | Duy An | Thái Sơn | Khánh Tùng |
|---|---|---|---|---|
| Product scope | A/R | C | C | C |
| System architecture | A/R | C | C | C |
| AI Assistant | A/R | C | R/C backend | R/C frontend |
| Simulation Engine | A/R | R | C | C |
| Robot algorithms | A/R/C | R | C | I |
| Dynamic obstacles | A/R/C | R | C | C |
| PPO integration | A/R | R | R/C | R/C |
| Metrics | A/R/C | R | C | C |
| Failure analysis | A/R | R | C | C |
| Backend API | A/C | C | R | C |
| Database | A/C | I | R | I |
| Frontend | A/C | C | C | R |
| Live Simulation UI | A/C | C | C | R |
| Benchmark workflow | A/R | C | R | R/C |
| Model Registry | A/C | C | R | R |
| Authentication | A/C | I | R | R/C |
| Review workflow | A/C | I | R | R/C |
| Evidence and Report | A/R | C | R/C | C |
| Deployment | A/R | C | R | C |
| Testing | A | R | R | R |
| Documentation | A/R | C | C | C |
| Demo | A/R | R | R | R |

Bốn tính chất giữ nguyên khi điều chỉnh ma trận:

1. Hùng Nguyên tham gia tất cả module.
2. Hùng Nguyên chịu trách nhiệm cuối cùng (`A` ở mọi hàng).
3. AI, Robotics, Simulation và Integration là phần lõi của Hùng Nguyên.
4. Duy An phụ trách sâu Robotics/Algorithms · Thái Sơn phụ trách
   Backend/Platform · Khánh Tùng phụ trách Frontend/UX.

---

## 37. AI và Backend

**Hùng Nguyên + Thái Sơn** — `BenchmarkSpec` · AI tools · authorization
· conversation state · benchmark proposal · evidence · citations ·
reports.

Ranh giới quyền của AI phải nằm ở tầng API, không nằm ở prompt.

---

## 38. AI và Frontend

**Hùng Nguyên + Khánh Tùng** — chatbot UX · clarification · quick
prompts · proposal card · result card · user confirmation · error state.

Giao diện trợ lý không hiển thị tên provider, API key, biến môi trường,
danh sách tool nội bộ hay chẩn đoán kỹ thuật; những thứ đó thuộc trang
System Information.

---

## 39. Simulator và Backend

**Hùng Nguyên + Duy An + Thái Sơn** — simulation request · map/scenario
· seed · algorithm config · episode · metrics · artifacts · failure
analysis.

---

## 40. Simulator và Frontend

**Hùng Nguyên + Duy An + Khánh Tùng** — map rendering · robot rendering
· dynamic obstacles · global path · trajectory · replay · metrics
visualization.

---

## 41. PPO Model Registry

Cả bốn người, mỗi người một lớp:

| Thành viên | Phần phụ trách |
|---|---|
| Hùng Nguyên | Kiến trúc và tích hợp |
| Duy An | Observation/action và compatibility |
| Thái Sơn | API, storage và security |
| Khánh Tùng | Upload và selection UX |

---

## 42. Quy trình tích hợp

**[Quy ước nhóm]**

```text
Module owner hoàn thành task
→ chạy unit test
→ cập nhật tài liệu và AI Log
→ mở Pull Request
→ Team Lead và module liên quan review
→ chạy integration test
→ merge vào main
→ chạy end-to-end regression
→ cập nhật demo build
```

---

## 43. Giải quyết bất đồng kỹ thuật

**[Quy ước nhóm]**

1. Đưa ra **bằng chứng**, không phải ý kiến.
2. Đối chiếu **PRD** và **acceptance criteria**.
3. Ưu tiên **test và dữ liệu**.
4. Đánh giá **ảnh hưởng toàn hệ thống**, không chỉ module đang bàn.
5. **Team Lead quyết định cuối cùng.**
6. **Ghi lại quyết định** trong PR hoặc tài liệu.

---

## 44. Definition of Done cho task

**[Quy ước nhóm]** — một task chỉ `Done` khi **tất cả** điều kiện sau
đúng:

- [ ] Đáp ứng acceptance criteria.
- [ ] Code được format.
- [ ] Lint pass.
- [ ] Type-check pass.
- [ ] Test liên quan pass (**đã chạy thật**).
- [ ] Không phá tính năng cũ.
- [ ] Không lộ secret.
- [ ] Error state được xử lý.
- [ ] Tài liệu được cập nhật.
- [ ] AI Log được ghi nếu có dùng AI.
- [ ] PR được review.
- [ ] Thay đổi được merge.
- [ ] Có evidence hoạt động.

---

## 45. Definition of Done cho Gate G1

**[Quy ước nhóm]**

- [ ] `01-brief.md` hoàn chỉnh.
- [ ] `02-prd.md` hoàn chỉnh.
- [ ] `03-wireframe-ui-flow.md` hoàn chỉnh.
- [ ] `04-github-ai-log-setup.md` hoàn chỉnh.
- [ ] README dẫn đủ bốn file.
- [ ] Tất cả nằm trong `docs/gate-g1`.
- [ ] Markdown đọc được trên GitHub.
- [ ] Không có secret.
- [ ] Nội dung khớp codebase.
- [ ] Tên và mã sinh viên chính xác.
- [ ] Team Lead đã kiểm tra.
- [ ] Repository được push.
- [ ] Link GitHub truy cập được trước deadline.

---


## 47. Trách nhiệm deployment

**[Quy ước nhóm]**

| Thành viên | Trách nhiệm |
|---|---|
| Phạm Nguyễn Hùng Nguyên | Chịu trách nhiệm cuối cùng, tích hợp và quyết định release |
| Phạm Thái Sơn | Backend, database, environment và service |
| Nguyễn Hữu Khánh Tùng | Frontend deployment |
| Tống Duy An | Kiểm tra simulator và thuật toán trên môi trường deploy |

**[Hiện trạng]** — image đã build và cả 4 service (`db`, `migrate`,
`api`, `web`) đã chạy thật trên PostgreSQL 17; dữ liệu sống sót khi xoá
hẳn container API rồi tạo lại. Chưa triển khai lên máy chủ thật và chưa
chạy nhiều người dùng đồng thời. Chi tiết ở
[../KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md).

---

## 48. Trách nhiệm demo

**G16-T011**

| Thành viên | Phần trình bày |
|---|---|
| Phạm Nguyễn Hùng Nguyên | Mở đầu, bài toán, kiến trúc, AI và demo end-to-end |
| Tống Duy An | Robot, thuật toán và simulation |
| Phạm Thái Sơn | Backend, workflow và dữ liệu |
| Nguyễn Hữu Khánh Tùng | UX/UI và user journey |


**Xem tiếp:** [Brief](./01-brief.md) · [PRD](./02-prd.md) · [Wireframe & UI Flow](./03-wireframe-ui-flow.md) · [Quay lại mục lục](./README.md)

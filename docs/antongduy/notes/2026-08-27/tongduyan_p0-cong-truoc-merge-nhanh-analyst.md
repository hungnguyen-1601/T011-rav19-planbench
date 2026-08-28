# P0 — chạy mọi cổng trước khi merge nhánh analyst, và bốn thứ chặn

**Ngày:** 2026-08-27 · **Loại:** khảo sát — **không đổi một dòng code nào**
**Plan:** `plans/2026-08-27/ai-analyst-theo-episode.md` bản 10, P0 bước 1–2
**Đối tượng:** worktree `E:/VinAI/RoboMind_project/P-011-analyst`, nhánh
`tongduyan_ai-analyst-ban-8` HEAD `7de4610`, cây sạch · so với cây chính
`P-011` nhánh `tongduyan_updater-cdn` (= `main` + 10 commit)
**Interpreter:** `P-011/.venv` (worktree dùng chung)

---

## 1. Bảng cổng

| Cổng | Kết quả | Do nhánh analyst? |
|---|---|---|
| `alembic upgrade head` trên DB tạm | **đạt** — 0001 → 0012, 6 row seed, 0 anchor rỗng | — |
| `ruff check` | 11 lỗi, **giống hệt cây chính** | không |
| `ruff format --check` | **42 file**, cây chính 9 ⇒ **33 file của nhánh** | **có** |
| `tsc --noEmit` | lỗi `paper.uploadHint` / `paper.truncated` | không (nhánh **không đụng** `apps/web`, 0 file) |
| Import smoke theo PYTHONPATH của `Dockerfile.analyst` | **hỏng toàn bộ** | **có** |
| Full suite | **19 failed · 4931 passed · 20 skipped**, 49 phút | 6/19 |
| `tests/test_trace_review.py` | không thu thập được — thiếu `pandas` | không |

## 2. Mười chín failure, phân loại bằng cách chạy lại trên cây chính

**Pre-existing — 13:**

| Test | Số | Bằng chứng |
|---|---|---|
| `test_host_parity_golden` | 5 | fail y hệt trên cây chính (float lệch chữ số cuối) |
| `test_dwa_core_refactor` | 5 | fail y hệt trên cây chính — **cùng lớp** với trên, cùng nguyên nhân |
| `tests/api/test_decision_export_golden` | 2 | fail trên cây chính |
| `tests/api/test_api_advice::test_an_unknown_run_is_a_404` | 1 | fail trên cây chính; trả 500 thay 404 vì route trace-review import `pandas` |

Waiver plan viết là 5 test parity. Thực tế **13**, và 8 trong số đó chưa
từng được ghi ở đâu. Ba lớp: float drift (10), golden markdown đã trôi (2),
và một route 500 vì dependency vắng (1).

**Do nhánh analyst — 6, đều là lỗi thật, đều một dòng:**

| Test | Số | Nguyên nhân |
|---|---|---|
| `test_script_import_paths` | 5 | pyproject thêm `services/analyst_service` vào pythonpath (A0), nhưng 5 script `compare.py`, `diagnose_phantom.py`, `diagnose_resolution.py`, `measure.py`, `vertical_slice.py` **không** thêm vào `sys.path` của chúng. Cổng này **pass 11/11 trên cây chính** |
| `tests/api/test_migrations` | 1 | migration 0012 tạo `algorithm_traits.updated_at` kiểu **DATETIME**, model `AlgorithmTraitRow` khai **String** ⇒ `type differs`. Pass trên cây chính |

## 3. Blocker: image analyst không import nổi chính nó

Chạy thật với **đúng** `ENV PYTHONPATH` của `docker/Dockerfile.analyst`
(không có `services/simulator`, đúng thiết kế):

```
planbench_analyst/__init__ → analyst → packet_view → knowledge_provider
  → planbench_benchmark.traits_store
     → planbench_benchmark/__init__  (eager)  → comparison → spec
        → planbench_metrics/__init__ (eager)  → episode_metrics
           → planbench_simulator.collision        ← image không COPY
```

`ModuleNotFoundError: No module named 'planbench_simulator'`.

**Mọi** module analyst chết, kể cả `sanitize`, `identity`, `prompts`,
`stdio_protocol` — vì `__init__.py` của gói eager import `analyst`. Lane
container **không khởi động được**; `stdio_lane` của A7 chưa từng chạy trong
image thật.

Vì sao xanh tới giờ: A7 ghi rõ *"chưa build image thật, không có Docker
daemon"*; `test_analyst_service_wiring.py` chạy dưới PYTHONPATH của pytest —
có `services/simulator` — nên nó xanh. Cổng đang có canh **`COPY ⊇
PYTHONPATH`**, không canh **"import được"**. Đúng loại lỗi CLAUDE.md §7 nói
smoke gate bắt được mà pytest không thấy.

Chi tiết đáng chú ý: `traits_store.py` **tự nó sạch** (chỉ pydantic +
stdlib), và bốn module analyst chỉ cần `TraitSource` / `TraitEntry`. Thủ
phạm là `__init__.py` của package cha.

**Ba phương án:**

| | Cách | Đánh đổi |
|---|---|---|
| A | `planbench_benchmark/__init__.py` lazy `__getattr__` | **tiền lệ có sẵn**: `planbench_explanation/__init__.py:647` làm đúng vậy ở W0 cho cùng loại vấn đề. Đụng API công khai của benchmark ⇒ chạy lại suite benchmark/decision |
| B | `planbench_metrics/__init__.py` lazy | khu trú hơn nhưng metrics bị import khắp nơi |
| C | COPY `services/simulator` vào image | **trái thiết kế** — Dockerfile ghi rõ image không mang khả năng nó không cần |

Dù chọn gì cũng phải thêm **test smoke import chạy đúng PYTHONPATH của
image**, vì cổng hiện tại không hỏi câu đó.

## 4. Ba việc nhỏ hơn, cần An quyết

1. **33 file chưa `ruff format`** — của chính nhánh analyst (17 module +
   test + script). Format thuần, không đổi hành vi, một lệnh. CLAUDE.md §6
   đòi chạy sau khi sửa `.py`; report bản 8 ghi "ruff sạch" nhưng đó là
   `ruff check`, không phải `ruff format --check`.
2. **`pandas` chưa từng được khai.** `tests/test_trace_review.py` có từ
   24-08 trên `main`, import `pandas`, mà `requirements*.txt` không khai và
   `.venv` không có. Nghĩa là file này **chưa từng chạy trên máy này**, và
   route `/traces/.../review` trả 500 thay vì 404 vì cùng lý do.
3. **Waiver phải viết lại**: plan nói 5 test, thực tế 13 pre-existing.

## 5. Số liệu để so lần sau

- Full suite worktree analyst: **4931 passed, 19 failed, 20 skipped**,
  2959 s (49 phút), bỏ `test_trace_review.py`.
- `ruff check`: 11 lỗi cả hai cây (`app.py` ×6, `map_files.py` ×3,
  `test_retention.py` ×2).
- `ruff format --check`: worktree 42 / 568; cây chính 9 / 539.
- Migration: `0011 → 0012`, 6 row (`astar`, `dwa`, `dwa_predictive`, `ppo`,
  `pure_pursuit`, `rrtstar`), tất cả `draft`, anchor 34–109 ký tự.

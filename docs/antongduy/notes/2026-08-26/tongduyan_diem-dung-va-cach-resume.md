# Điểm dừng phiên 2026-08-26 và cách chạy tiếp

Ghi lại để lần sau vào là làm tiếp được, không phải dò lại.

**Nhánh:** `tongduyan_ai-analyst-ban-8` · **Worktree:**
`E:/VinAI/RoboMind_project/P-011-analyst` · **HEAD:** `61bbe7d` · cây **sạch**,
không có gì chưa commit.

## 1. Đã xong tới đâu

| Giai đoạn | Trạng thái | Commit |
|---|---|---|
| W0 nền đánh giá + preregistration | xong | `8299a61` |
| W1.0 → W1.8 (host thật, M1/M2/M3, flags, snapshot) | xong | `73be097` … `6df43a4` |
| W2 candidate generator | xong | `077319d` |
| W3 tool routing | xong | `66f327f` |
| W4 union + repair | xong | `30ecd57` |
| B1 hạ tầng đo (scorer + runner) | xong | `4301df8` |
| B1 + 8 arm trên o4-mini, B1 trên qwen3 | xong | `651c069` |
| 28 răng bites cho cổng W0–W4 | xong (28/28 cắn) | `651c069` |
| **G6 — dựng đủ 6 họ golden** | **xong** | `1110e78` |
| E6/E7 — hai cờ arm (`discriminated_union`, `critic`) | xong (code) | `61bbe7d` |

## 2. Đang dở — dừng ở đây

**Chạy E6/E7 trên `qwen3:8b`** (6 case × 3 repeat × 3 arm). Đã chạy hết arm
`b1`, đang giữa arm `e6_free_schema` thì dừng máy. **Không có artifact** cho
đợt này: runner chỉ ghi JSON khi cả lệnh chạy xong. Chạy lại từ đầu, không mất
gì ngoài thời gian.

Lệnh để chạy lại:

```powershell
cd E:\VinAI\RoboMind_project\P-011-analyst
python -u scripts/run_analyst_experiments.py `
    --arm b1 --arm e6_free_schema --arm e7_no_critic `
    --provider local --model qwen3:8b --repeats 3 --label qwen3-8b
```

Ollama tự bật khi gọi; máy có `qwen3:8b` và `llama3.2:latest`.

## 3. Việc còn lại theo thứ tự

1. **E6/E7 trên `qwen3:8b`** — lệnh ở trên (~30 phút).
2. **E8 — đổi model, giữ nguyên pipeline**: chạy arm `e8_model` hai lần, một
   lần `--model qwen3:8b`, một lần `--model llama3.2:latest`, `--label` khác
   nhau. Đây cũng là dữ liệu để dựng oracle router cho E10.
3. **E9 — hosted vs local**: **chặn**, hết token o4-mini. Số o4-mini hiện có là
   trên bộ 3 case *trước* G6 nên **không so được** với bộ 6 case; muốn E9 thì
   phải chạy lại hosted trên bộ mới.
4. **E10 — router eval, 5 arm** (floor-only / always-default / always-strong /
   oracle-router / frozen-cascade): tính **offline** từ artifact E8 + sàn
   model-free, không tốn thêm lượt gọi model. Oracle theo utility
   preregistered `U = 1.0·quality − 0.02·cost_k − 0.005·latency_s`; router
   thiết kế trên một fold, chấm trên fold còn lại (cross-fitting theo case).
5. Viết notes + report cho E6–E10, commit.

## 4. Hai chỗ vẫn chờ An

1. **Duyệt traits** — 6/6 row đang `draft`:
   ```powershell
   python scripts/review_algorithm_traits.py list
   python scripts/review_algorithm_traits.py approve dwa --by "An Tong"
   ```
   Script chỉ có trên nhánh này; DB mặc định là file mới trong worktree, **không
   đụng** `P-011/planbench.db` (DB thật chưa chạy migration 0012).
2. **Merge vào `main`** — chờ An test xong.

## 5. Trạng thái golden sau G6

Sáu họ, mỗi họ **một** case: `inflation-001`, `rrt-001`, `dwa-001`,
`latency-001`, `control-001`, `gap-002`. Nhãn ở
`fixtures/golden/labels/visible.json` đủ sáu.

`OFFICIAL_GOLDEN_READY` **vẫn False**, và có lý do: sáu họ **không phải** mười
hai case. Sáu biến thể thứ hai (`inflation-002`, `rrt-002`, `dwa-002`,
`latency-002`, `control-002`, `gap-001`) — cái tách "cơ chế có ở đây" khỏi
"hình dạng giống thế mà cơ chế không có" — chưa dựng, liệt kê trong
`plant_golden_runs.SECOND_VARIANTS_MISSING`. Preregistration báo counts chứ
không báo tỷ lệ khi dưới 12 case.

Dựng lại toàn bộ fixture (mất ~10–15 phút, chủ yếu do họ latency 8 episode):

```powershell
python scripts/build_golden_fixtures.py
```

## 6. Ba điều dễ quên khi vào lại

- **Episode id là hash của điều kiện.** Đổi mission/seed/goal là đổi id, và mọi
  hằng số pin id trong test sẽ chết. `tests/test_analyst_real_host.py` giờ đọc
  id từ chính fixture — giữ lối đó.
- **Fixture có `report.json`** (hiện chỉ họ latency). Nó là thứ
  `latency_vs_expanded_nodes` đọc; `in_process_round(..., report=...)` phải
  được truyền, nếu không check trả `not_checkable` — đúng nhưng không đo được.
- **Chạy lại builder sẽ xoá thư mục `sidecar/` của từng case trước khi ghi.**
  Cố ý: bản build cũ để lại sidecar của episode không còn tồn tại, và reader
  báo đúng rằng file đã bị sửa sau khi chạy.

# Báo cáo — Đợt 1.2: P04 Quy trình thống kê

> **Ngày:** 2026-08-06
> **Plan nguồn:** `docs/antongduy/plans/2026-08-05/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`, mục **1.2**
> **Nhánh:** `tongduyan`
> **Tiền đề:** Đợt 1.1 (P02) đã xong cùng ngày — xem
> `tongduyan_dot-1-1-p02-can-bang-thong-tin.md`.

---

## 1. Vấn đề đang giải

Trước đợt này, report chỉ có **trung bình** và **không có kiểm định
nào**. Hai hệ quả:

1. Một episode chôn chân tới hết timeout kéo trung bình vượt xa mọi thứ
   thực sự xảy ra — con số được trích dẫn không mô tả lần chạy điển hình.
2. Không có cách nào phân biệt "A nhanh hơn B" với "A gặp may ở tập seed
   này". Leaderboard vẫn xếp hạng, và người đọc không có gì để trừ hao.

P04 thay bằng: trung vị + IQR + khoảng tin cậy, kiểm định ghép cặp theo
seed, độ lớn hiệu ứng, và cảnh báo khi số seed không đủ để kết luận.

---

## 2. Quyết định lớn: dùng SciPy

Đúng như plan chốt. `scipy==1.18.0` ghim vào `requirements.txt` và
`docker/requirements-api.txt` (tương thích `numpy==2.5.1` đang dùng).

Lý do giữ nguyên như plan: kiểm định thống kê cài sai **không ném
exception**. Nó trả một p-value trông hợp lý và sai. Lỗi đó vô hình khi
review, vô hình khi chạy, và nằm dưới mọi kết luận nền tảng này công bố.

---

## 3. Đã làm gì

### 3.1. `packages/metrics/planbench_metrics/statistics.py` (mới)

| Hàm | Ghi chú thiết kế |
|---|---|
| `median_iqr(values)` | Trả `(median, q1, q3)`, nội suy tuyến tính (mặc định NumPy) — ghi rõ trong docstring vì với mẫu nhỏ hai quy ước cho kết quả khác nhau thấy được. |
| `bootstrap_ci(values, ...)` | Percentile bootstrap, **không** BCa: BCa cần jackknife không ổn định ở cỡ mẫu 5–30 seed và thỉnh thoảng trả NaN. Seed mặc định 0 nên tái lập được. Mẫu không biến thiên trả thẳng `(v, v)` thay vì để SciPy cảnh báo rồi trả NaN. |
| `wilcoxon_compare(a, b)` | Gọi `scipy.stats.wilcoxon`. Hai mẫu giống hệt nhau trả `(0.0, 1.0)` thay vì để SciPy raise — hai stack tất định hòa ở mọi seed là kết quả hợp lệ, không phải lỗi. |
| `cliffs_delta(a, b)` | Tự tính (công thức đếm cặp, không phải kiểm định) — độ lớn hiệu ứng, phi tham số, không ghép cặp. |
| `proportion_ci(successes, trials)` | Khoảng Wilson qua `scipy.stats.binomtest`. Chính xác, không cần seed, và ở 0%/100% vẫn không tuyên bố chắc chắn — đúng chỗ mà xấp xỉ chuẩn sẽ trả "0.0 đến 0.0" cho 5 lần thất bại. |
| `average_rank_score(...)` | Trung bình thứ hạng. Bắt buộc mọi thuật toán được xếp hạng ở **cùng tập scenario** — bỏ qua scenario khó không được phép làm điểm đẹp lên. |
| `statistically_adequate(n)` | Ngưỡng `ADEQUATE_SEED_COUNT = 30`, khai báo tường minh. |

Nguyên tắc xuyên suốt: **mọi hàm raise `StatisticsInputError` với input
không tóm tắt trung thực được** (rỗng, NaN, vô cực, lệch độ dài, mức tin
cậy sai) thay vì trả một con số kèm chú thích nhỏ.

### 3.2. `packages/benchmark/planbench_benchmark/comparison.py` (mới)

Ghép cặp theo seed — phần quan trọng nhất của đợt này:

```
seed -> value của A       seed -> value của B
        └────────── giao ──────────┘
                    ↓
        sắp theo thứ tự seed
                    ↓
        scipy.stats.wilcoxon
```

- Chỉ lấy episode **thành công** (thời gian di chuyển vô nghĩa với robot
  không tới đích).
- Seed nào có stack không về đích thì bị loại khỏi cặp, **và số bị loại
  được ghi vào `warning`**.
- Hai stack chạy khác tập seed → cảnh báo riêng, vì đó là vấn đề công
  bằng chứ không phải vấn đề cỡ mẫu.
- Dưới `MIN_PAIRS_FOR_TEST = 5` cặp thì **không chạy kiểm định**:
  `statistic/p_value/effect_size = None`. Với 3–4 cặp, p-value nhỏ nhất
  Wilcoxon có thể trả vẫn > 0.05, nên "không có ý nghĩa" chỉ phản ánh cỡ
  mẫu.
- Baseline = stack có success rate cao nhất, **tie-break theo tên** để
  bảng không phụ thuộc thứ tự dict.

### 3.3. Schema (`spec.py`)

`AlgorithmAggregate` thêm 10 trường, **không xóa/đổi nghĩa trường nào**:

```
median_/iqr_/ci95_  travel_time_successful
median_/iqr_/ci95_  path_efficiency_successful
median_/iqr_/ci95_  smoothness_successful
ci95_success_rate
```

Các trường `mean_*` cũ giữ nguyên, đánh dấu deprecated trong docstring.

`PairwiseComparison` đặt trong `spec.py` (không phải `comparison.py`) để
schema của report import được mà không kéo theo tầng thống kê — đồng
thời tránh vòng import.

`BenchmarkReport` thêm `comparisons[]`, và `seed_count` +
`statistically_adequate` dưới dạng **computed field** suy ra từ
`spec.seeds` — nhờ vậy report cũ đọc lại cũng có hai trường này đúng,
không cần migration.

### 3.4. Runner

`aggregate_algorithm()` tính trung vị/IQR/CI cho ba metric và Wilson CI
cho success rate; `run_benchmark()` gắn `comparisons`. `BOOTSTRAP_SEED =
0` cố định — hai người đọc cùng report phải trích cùng con số.

### 3.5. Nơi khác trong hệ thống

- **Agent evidence** (`services/agent_service/.../evidence.py`): thêm
  item trung vị **kèm CI trong cùng câu**. Agent chỉ được đưa point
  estimate thì sẽ viết "A nhanh hơn"; đưa kèm khoảng thì viết được đúng
  cái dữ liệu cho phép.
- **Chat result card**: thêm median, CI, `seed_count`,
  `statistically_adequate`, `comparisons`.
- **Frontend** (`/benchmarks/[id]`): bảng so sánh đổi sang **trung vị**
  (IQR + CI95 trong tooltip của ô), thêm panel "Kiểm định đối đầu" với
  p-value, effect size, số cặp seed, cảnh báo từng cặp, và banner cảnh
  báo khi `statistically_adequate=false`. Verdict chỉ ghi "đo được khác
  biệt" khi **vừa** significant **vừa** đủ seed.

---

## 4. Test

**`tests/test_statistics.py` — 44 test.** Ba nhóm:

1. Khớp giá trị tính tay (median lẻ/chẵn, Cliff's delta từng cặp,
   average rank).
2. Từ chối input xấu (rỗng, NaN, vô cực, lệch độ dài, level ngoài (0,1),
   rank = 0, xếp hạng trên tập scenario khác nhau).
3. **Khớp SciPy gọi trực tiếp** — bootstrap, Wilcoxon, Wilson. Đây là lý
   do module tồn tại: không được có số học riêng trôi dưới p-value.

**`tests/test_comparison.py` — 28 test.** Trọng tâm là ghép cặp:

- Đảo thứ tự lưu trữ cho **cùng** kết quả;
- và một test chứng minh test trên không rỗng nghĩa: ghép lệch seed cho
  kết quả **khác**;
- seed bị loại được đếm đúng và ghi vào warning;
- khác tập seed → cảnh báo công bằng;
- dưới 5 cặp → không có statistic;
- khác biệt nhất quán → significant, effect size = -1;
- aggregate: trung vị chịu được outlier mà trung bình thì không, 1 thành
  công có trung vị nhưng không có CI, 0 thành công thì tất cả `None`,
  CI success rate luôn có kể cả ở 0%/100%;
- report cũ (thiếu trường mới) vẫn deserialize.

**`tests/api/test_api_benchmarks.py`** — thêm 1 test: report qua API có
`seed_count`, `statistically_adequate=false` với 4 seed, có
`ci95_success_rate`, và trường `mean_*` cũ vẫn còn.

**`apps/web/src/app/__tests__/benchmark-statistics.test.tsx` — 21 test:**
bảng dùng trường median (và không còn in `mean_*` ở ba ô đó), spread vẫn
tới được, p-value luôn đi kèm số cặp seed và effect size, cảnh báo thiếu
seed hiện, verdict yêu cầu cả significant lẫn đủ seed, i18n đủ hai ngôn
ngữ.

**Kết quả chạy:**

```
pytest (toàn bộ)                       1218 passed, 4 skipped (6:23)
  tests/test_statistics.py             44 passed
  tests/test_comparison.py             28 passed
  tests/api/test_api_benchmarks.py     19 passed (+1 test mới)
ruff check .                           All checks passed
ruff format --check                    sạch
npm run typecheck (apps/web)           sạch
npm test (apps/web)                    282 passed / 2 file fail có sẵn
```

Baseline sau Đợt 1.1 là 1145 passed; +73 test mới của đợt này.

Hai test frontend fail **từ trước và không liên quan** (đã nêu ở báo cáo
Đợt 1.1): `dashboard-page.test.tsx` so đường dẫn kiểu POSIX trên Windows,
`assistant-page.test.tsx` đọc `src/app/models/page.tsx` chưa tồn tại.

---

## 5. Kiểm chứng end-to-end

Chạy thật `astar+dwa` vs `rrtstar+dwa`:

**3 seed (doorway)** — kiểm chứng nhánh thiếu dữ liệu:

```
seed_count=3 adequate=False
astar+dwa   success_rate=1.000  CI95=(0.439, 1.000)
            median travel=9.5   IQR=(9.5, 9.5)   CI95=(9.5, 9.5)
rrtstar+dwa median travel=9.85  IQR=(9.80, 9.875) CI95=(9.75, 9.90)
comparison  statistic=None p=None effect=None paired_seed_count=3
            warning="only 3 paired seed(s); fewer than 5 cannot support
                     a significance test, so none was run"
```

Đúng như thiết kế: success rate 100% trên 3 seed vẫn trả CI95 bắt đầu từ
0.439 — không tuyên bố chắc chắn.

**30 seed (narrow_corridor)** — kiểm chứng nhánh "không có cặp nào":

```
seed_count=30 adequate=True
astar+dwa    success_rate=0.000  CI95=(0.000, 0.114)  mọi median/IQR/CI = None
rrtstar+dwa  success_rate=1.000  CI95=(0.886, 1.000)
             median travel=14.275  IQR=(14.250, 14.350)  CI95=(14.250, 14.350)
comparison   p=None paired_seed_count=0
             warning="30 of 30 shared seeds contributed no pair because at least
                      one stack has no travel_time there (it did not reach the
                      goal); only 0 paired seed(s); ..."
statistics reproducible on re-run: True
```

Đây là ca đáng chú ý: `astar+dwa` thất bại toàn bộ 30 seed ở
`narrow_corridor`. Hệ thống **không** vì thế mà tuyên bố `rrtstar+dwa`
thắng theo kiểm định — không có cặp nào nên không có p-value, và lý do
được ghi rõ. (Việc astar+dwa fail 100% ở scenario này là hiện trạng của
stack, không thuộc phạm vi P04; đáng điều tra riêng.)

**Tính tái lập:** chạy lại cùng seed cho **cùng** median, IQR, CI,
p-value, effect size và warning (đã so khớp tự động, loại trừ các trường
đo bằng đồng hồ như latency).

**Docker:** `docker compose build api` — kết quả ở phần 5.2.

### 5.1. Docker build với SciPy

`docker compose build api` — **thành công**, image `planbench-api:latest`.

Kiểm tra bên trong image:

```
scipy 1.18.0 numpy 2.5.1
wilcoxon ok 0.03125
```

### 5.2. Benchmark thật chạy trong container (8 seed, doorway)

```
seed_count 8 adequate False
astar+dwa    median 9.500  ci (9.500, 9.500)  srate_ci (0.676, 1.000)
rrtstar+dwa  median 9.825  ci (9.750, 9.850)  srate_ci (0.676, 1.000)
astar+dwa vs rrtstar+dwa  p=0.0078125  delta=-1.0  pairs=8  warning=None
```

Đúng cả hai nhánh cùng lúc: kiểm định **có** chạy (8 cặp ≥ 5) và cho
p < 0.05 với effect size -1.0 (astar+dwa nhanh hơn ở mọi seed), nhưng
`adequate=False` vì 8 < 30 — nên UI vẫn hiện cảnh báo và verdict **không**
ghi "đo được khác biệt". Đây chính là hành vi plan yêu cầu: chạy, hiện
số, không kết luận mạnh.

### 5.3. Benchmark 30 seed trong container (doorway)

```
seed_count 30 adequate True
astar+dwa    mean 9.500  median 9.500  iqr (9.500, 9.500)  ci (9.500, 9.500)
             srate 1.0  ci95_success (0.886, 1.000)
rrtstar+dwa  mean 9.792  median 9.800  iqr (9.750, 9.850)  ci (9.750, 9.800)
             srate 1.0  ci95_success (0.886, 1.000)
astar+dwa vs rrtstar+dwa
             stat=0.0  p=1.35e-06  delta=-1.0  significant=True  pairs=30
             warning=None
```

Đây là ca đầy đủ nhất: 30 cặp, `adequate=True`, kiểm định chạy và cho
p rất nhỏ, effect size -1.0 (astar+dwa nhanh hơn ở **mọi** seed), không
có seed nào bị loại nên không có warning.

Lưu ý cách đọc đúng: khác biệt trung vị chỉ 0.3 giây (9.5 so với 9.8).
p-value cực nhỏ **không** nói khác biệt đó lớn — nó nói khác biệt đó
nhất quán. Chính vì vậy report bắt buộc hiện cả effect size lẫn khoảng
tin cậy, chứ không chỉ p-value.

---

## 6. Definition of Done (plan mục 1.2)

- [x] Dùng SciPy.
- [x] Không tự viết Wilcoxon.
- [x] Ghép cặp đúng theo seed.
- [x] Có median, IQR và CI.
- [x] Có effect size (Cliff's delta).
- [x] Có warning khi thiếu seed.
- [x] Field cũ vẫn tồn tại.
- [x] Test đối chiếu dữ liệu chuẩn (so trực tiếp với SciPy).
- [x] Docker build được với SciPy — xem 5.1, và benchmark thật chạy
      trong container ở 5.2.

---

## 7. Giới hạn đã ghi vào `KNOWN_LIMITATIONS.md` (mục 106–111)

1. **Chỉ so leader với từng stack còn lại**, chưa full pairwise và
   **chưa hiệu chỉnh đa so sánh**.
2. **Ngưỡng 30 seed là quy ước**, không phải tính toán power.
3. **Dưới 5 cặp không chạy kiểm định** — benchmark nhỏ trả `null`.
4. **Bootstrap seed cố định 0**: đổi lại tính tái lập, CI là một lần lấy
   mẫu chứ không phải trung bình nhiều lần.
5. **Ghép cặp chỉ trên seed cả hai cùng về đích** — có thiên lệch (stack
   yếu được so trên đúng tập seed dễ của nó). Số cặp và số seed bị loại
   luôn hiện, nhưng người đọc phải tự trừ hao.
6. **`average_rank_score` chưa nối vào leaderboard/report** — cần quyết
   định về tập scenario, thuộc P03/P05.

---

## 8. File đã đổi

**Mới:**
- `packages/metrics/planbench_metrics/statistics.py`
- `packages/benchmark/planbench_benchmark/comparison.py`
- `tests/test_statistics.py`
- `tests/test_comparison.py`
- `apps/web/src/app/__tests__/benchmark-statistics.test.tsx`

**Sửa:**
- `requirements.txt`, `docker/requirements-api.txt` (scipy==1.18.0)
- `packages/metrics/planbench_metrics/__init__.py`
- `packages/benchmark/planbench_benchmark/spec.py`, `runner.py`, `__init__.py`
- `apps/api/planbench_api/chat_service.py`
- `services/agent_service/planbench_agent/evidence.py`
- `apps/web/src/lib/benchmarkTypes.ts`
- `apps/web/src/app/benchmarks/[id]/page.tsx`
- `apps/web/src/lib/i18n/locales/en.json`, `vi.json`
- `tests/api/test_api_benchmarks.py`
- `docs/API_CONTRACT.md`, `docs/KNOWN_LIMITATIONS.md`

---

## 9. Bước tiếp theo

Đợt 1 (1.1 + 1.2) xong. Tiếp theo theo plan là **Đợt 2**: P05 (tập
held-out), P03 (hiệu chuẩn độ khó), Scenario Editor.

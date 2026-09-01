# Báo cáo — Đợt 1.1: P02 Khai báo cân bằng thông tin

> **Ngày:** 2026-08-06
> **Plan nguồn:** `docs/antongduy/plans/2026-08-05/khoi-phuc-giao-thuc-danh-gia-va-hoan-thien-mvp.md`, mục **1.1**
> **Nhánh:** `tongduyan`
> **Phạm vi:** chỉ 1.1. Mục 1.2 (P04/SciPy) **chưa** làm trong đợt này.

---

## 1. Vấn đề đang giải

Trước thay đổi này, local planner đã không nhận ground-truth vật cản —
nền tảng đúng. Nhưng đó là sự thật *ngầm*: không ai đọc leaderboard biết
được thuật toán nào nhìn thấy dữ liệu gì, và không có gì chặn một stack
tương lai đọc thêm human states rồi đứng chung bảng xếp hạng với một
stack chỉ có LiDAR. Khi đó bảng xếp hạng sẽ báo "bài toán dễ hơn" thành
"thuật toán tốt hơn".

P02 biến sự thật ngầm thành **lời khai tường minh, đi kèm số đo, và
được leaderboard tôn trọng**.

---

## 2. Đã làm gì

### 2.1. Kiểu dữ liệu

`packages/benchmark/planbench_benchmark/observation.py` (file mới):

```python
ObservationClass = Literal[
    "full_static_map",
    "lidar_only",
    "human_states",
    "lidar+human_states",
]
```

Kèm `OBSERVATION_CLASSES` để test và UI liệt kê được giá trị hợp lệ.

### 2.2. Registry — khai báo bắt buộc, không có default

`AlgorithmInfo` thêm ba trường **không default**:

```python
global_observation_class: ObservationClass
local_observation_class: ObservationClass
requires_global_path: bool
```

Đăng ký stack mới mà quên khai là `ValidationError` **lúc import**, chứ
không phải một dòng sai lặng lẽ trên leaderboard. Đây là điểm plan yêu
cầu rõ: nhãn sai nguy hiểm hơn nhãn thiếu, vì nó làm một so sánh không
công bằng trông như đã được kiểm.

Giá trị hiện tại của cả 5 stack đúng bảng trong plan: global
`full_static_map`, local `lidar_only`, `requires_global_path=true`.

Thêm `algorithm_info(algorithm_id) -> AlgorithmInfo | None` — trả `None`
thay vì raise, vì người gọi thường đang đọc report cũ của một stack đã
bị gỡ tên.

### 2.3. Aggregate — chụp lại, không tra lúc đọc

`AlgorithmAggregate` thêm ba trường cùng tên, **nullable**, do
`aggregate_algorithm()` điền từ registry lúc chạy.

Chụp thay vì tra lúc render vì: sửa registry sau này **không được** dán
nhãn khác lên số đã đo xong. Nullable vì report lưu trước P02 không có
khai báo, và bịa ra một giá trị cho chúng chính là thứ P02 sinh ra để
chặn.

Không xóa, không đổi nghĩa trường nào đang có.

### 2.4. Leaderboard — không trộn lớp

- Khóa nhóm đổi từ `conditions_checksum` sang
  `(conditions_checksum, local_observation_class)`.
- `LeaderboardEntry` mang cả ba trường khai báo.
- `LeaderboardGroup` thêm `local_observation_class` (lớp chung của nhóm)
  và `cross_observation_class_warning`.
- Query mới `group_by_observation_class` (mặc định `true`). Tắt đi thì
  vẫn xếp chung — plan yêu cầu "vẫn cho phép hiển thị" — nhưng nhóm bị
  trộn trả về kèm cờ cảnh báo.
- Với dòng cũ không có bản chụp: tra ngược registry; stack đã bị gỡ tên
  thì để `null` và hiện là "không rõ", **không** gộp vào lớp nào.

### 2.5. Frontend

- `benchmarkTypes.ts`: type `ObservationClass` + 3 trường trên
  `AlgorithmInfo`.
- `platformTypes.ts`: 3 trường trên `LeaderboardEntry`, 2 trường trên
  `LeaderboardGroup`.
- `/leaderboard`: thêm cột "Sees" (lớp quan sát của bộ điều khiển,
  tooltip giải thích), nhãn lớp trên đầu mỗi nhóm, checkbox "Tách theo
  lớp quan sát" (mặc định bật), và hộp cảnh báo — cả khi người dùng tắt
  tách nhóm lẫn khi backend báo nhóm bị trộn.
- `/algorithms`: in khai báo của từng stack ngay dưới mô tả, để người
  dùng thấy trước khi tạo benchmark.
- i18n: 14 khóa mới, đủ cả `en` và `vi` (có test chống việc để nguyên
  chuỗi tiếng Anh bên `vi`).

### 2.6. Tài liệu

- `docs/API_CONTRACT.md`: bảng ba trường mới của `/algorithms`, ghi chú
  bản chụp trong `aggregates[]`, quy tắc nhóm của `/leaderboard`.
- `docs/KNOWN_LIMITATIONS.md`: mục 102–105 (xem phần 5 bên dưới).

---

## 3. Test

**Backend — `tests/test_observation_class.py` (14 test, mới):**

| Nhóm | Kiểm cái gì |
|---|---|
| Registry | Mọi stack khai đủ 3 trường; thiếu khai báo là `ValidationError` với đúng 3 trường thiếu; lớp lạ bị từ chối |
| Chống hồi quy thông tin | `Observation` không có trường ground-truth nào (obstacles, human_states, grid, map, scenario…); `LocalPlanner.compute()` chỉ nhận `(self, state, observation)` |
| Leaderboard | Hai lớp khác nhau tách thành 2 nhóm; ép xem chung thì 1 nhóm + cờ cảnh báo + không claim lớp chung; cùng lớp vẫn chung nhóm và giữ đúng thứ hạng |
| Tương thích ngược | Report trước P02 tra được registry; stack đã gỡ tên thì `null`; aggregate cũ vẫn deserialize |
| Snapshot | `aggregate_algorithm()` điền đúng khai báo |

**Backend — `tests/api/test_api_m5.py` (2 test thêm):** `/leaderboard`
serialize đủ 3 trường trên entry + 2 trường trên group; `/algorithms`
trả khai báo cho mọi stack.

**Frontend — `src/app/__tests__/leaderboard-observation.test.tsx`
(16 test, mới):** cột lớp quan sát tồn tại, ô "không rõ" thay vì ô
trống, nhãn nhóm, mặc định tách nhóm, cảnh báo hiện ở cả hai đường
(người dùng tắt / backend báo trộn), khóa i18n có đủ ở hai ngôn ngữ.

**Kết quả chạy:**

```
pytest tests/test_observation_class.py     14 passed
pytest tests/api/test_api_m5.py            15 passed
pytest (toàn bộ)                           1145 passed, 4 skipped (7:06)
ruff check .                               All checks passed
npm run typecheck (apps/web)               sạch
npx vitest run leaderboard-observation     16 passed
npm run build (apps/web)                   build production thành công
```

**Hai test frontend fail từ trước, không liên quan thay đổi này:**

- `dashboard-page.test.tsx` — so sánh đường dẫn `"/system/page.tsx"` với
  `"\system\page.tsx"`: test giả định separator POSIX, chạy trên Windows
  là fail. Lỗi môi trường, không phải lỗi code.
- `assistant-page.test.tsx` — `ENOENT ... src/app/models/page.tsx`: test
  đọc một trang chưa tồn tại.

Cả hai fail y hệt trước khi tôi sửa gì.

---

## 4. Definition of Done (theo plan mục 1.1)

- [x] API hiển thị observation class.
- [x] UI hiển thị observation class.
- [x] Leaderboard không âm thầm trộn lớp.
- [ ] Report ghi observation class — **xem phần 5.1**.
- [x] Test chống hồi quy thông tin pass.
- [x] Không thay đổi RBAC.

---

## 5. Việc chưa xong và giới hạn

### 5.1. `report_markdown.py` chưa tồn tại

Plan mục 1.1 liệt kê `apps/api/planbench_api/report_markdown.py` trong
danh sách file cần sửa. **File này chưa có trong repo** — export
Markdown là Đợt 3 (F09), chưa triển khai. Dữ liệu cần cho nó thì đã sẵn:
`AlgorithmAggregate` mang bản chụp khai báo, nên khi làm F09 chỉ việc
đọc ra, không phải sửa ngược schema.

Vì vậy dòng "Report ghi observation class" trong DoD để **chưa tick**,
không tự nhận là xong.

### 5.2. Giới hạn đã ghi vào `KNOWN_LIMITATIONS.md` (mục 102–105)

1. **Lớp quan sát là lời khai, không phải cơ chế cưỡng chế.** Planner là
   code tùy ý; nó vẫn có thể import thẳng scenario. Cái nền tảng bảo đảm
   được là `Observation` không mang ground truth và `compute()` không
   nhận map/scenario — đã khóa bằng test. Khai sai vẫn lọt, nên thêm
   stack mới phải có người review.
2. **Aggregate trước P02 không có bản chụp**, hiện "không rõ" và không
   được gộp vào lớp nào.
3. **Cả 5 stack hiện cùng một lớp**, nên đường tách nhóm mới chỉ được
   kiểm bằng aggregate dựng trong test (`lidar+human_states`), chưa bằng
   một planner thật đọc human states.
4. **`requires_global_path` hiện luôn `true`** — nhánh `false` chưa chạy
   thật lần nào.

---

## 6. File đã đổi

**Mới:**
- `packages/benchmark/planbench_benchmark/observation.py`
- `tests/test_observation_class.py`
- `apps/web/src/app/__tests__/leaderboard-observation.test.tsx`
- `docs/antongduy/reports/2026-08-06/tongduyan_dot-1-1-p02-can-bang-thong-tin.md`

**Sửa:**
- `packages/benchmark/planbench_benchmark/registry.py`
- `packages/benchmark/planbench_benchmark/spec.py`
- `packages/benchmark/planbench_benchmark/runner.py`
- `packages/benchmark/planbench_benchmark/__init__.py`
- `apps/api/planbench_api/leaderboard.py`
- `apps/api/planbench_api/routers/library.py`
- `apps/web/src/lib/benchmarkTypes.ts`
- `apps/web/src/lib/platformTypes.ts`
- `apps/web/src/app/leaderboard/page.tsx`
- `apps/web/src/app/algorithms/page.tsx`
- `apps/web/src/lib/i18n/locales/en.json`, `vi.json`
- `tests/api/test_api_m5.py`
- `docs/API_CONTRACT.md`, `docs/KNOWN_LIMITATIONS.md`

---

## 7. Bước tiếp theo

Đợt 1.2 — P04 quy trình thống kê (SciPy, Wilcoxon ghép cặp theo seed,
median/IQR/CI95, Cliff's delta, cảnh báo thiếu seed). Chưa bắt đầu.

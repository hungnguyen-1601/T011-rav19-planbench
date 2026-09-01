# Rà soát `reference/` và trỏ lại toàn bộ link docs

**Ngày:** 2026-08-31 · **Nhánh:** `tongduyan_signin-landing-and-updater`
**Tiếp theo:** `tongduyan_sap-xep-lai-docs-ban-nhap.md` cùng ngày.

Hai việc An giao: (1) trỏ lại mọi thứ vào cấu trúc docs mới, (2) rà từng
file `.md` trong `reference/`, sửa hoặc xoá cái không còn phù hợp.

> **Ràng buộc thời điểm.** Các sửa đổi ở `README.md`, `CLAUDE.md`,
> `contracts/CONTRACTS.md` và ~50 file code trỏ vào đường dẫn `docs/` **mới**.
> Chúng chỉ đúng **sau khi** `docs-v2/` thay `docs/`. Hai việc phải vào
> cùng một commit — xem mục 4.

---

## 1. Rà `reference/` — 15 file

Không xoá file nào. Thứ hết hiệu lực thì chuyển sang `archive/`, vì chúng
còn giải thích được **vì sao** hệ hôm nay như vậy.

### 1.1. `API_CONTRACT.md` — hỏng nặng nhất, đã thay

Viết script so endpoint trong tài liệu với decorator thật trong
`apps/api/planbench_api/routers/`. Kết quả:

| Đo được | Số |
|---|---|
| Route thật trong code | **161** (137 path phân biệt) |
| Path tài liệu có nhắc | 53 |
| **Endpoint đang sống mà tài liệu không nhắc** | **84** |
| Endpoint tài liệu ghi như bình thường, code đánh dấu `deprecated=True` | **13** |

Nó thiếu hẳn `/decisions/*` — **52 route, trung tâm sản phẩm** — cùng
`/candidates/*`, `/admin/*`, `/algorithms/plugins/*`, `/agent/*`. Ngược
lại, nó mô tả kỹ nhóm `/benchmarks`, mà **cả 18 route của nhóm đó đã
deprecate**. Tổ chức thì theo từ vựng M4–M13 đã chết.

Nói cách khác nó không "hơi cũ" — nó **lộn ngược**: tả nửa đã chết, bỏ nửa
đang sống.

**Đã làm:** chuyển vào `archive/superseded/API_CONTRACT.md` kèm banner nêu
đúng ba con số trên. Thay bằng `reference/api.md` mới — bản đồ 161 route
theo nhóm router, mục riêng giải thích vì sao `/benchmarks` còn đó mà
không được dùng, và mục WebSocket. Nguồn sự thật chỉ về `/openapi.json`
do FastAPI sinh, vì đó là thứ không bao giờ lệch code.

### 1.2. `decision-log.md` — tách ra, file mới

Nhật ký quyết định **D01–D15** nằm trong `docs/architecture.md`. File đó
lỗi thời (dừng ở "Giai đoạn 1A") nên đợt trước tôi đã archive nó — nhưng
nhật ký thì **chưa** lỗi thời: `geometry.py`, `collision.py`, `grid.py`
đang trích D07, D08, D10 **bằng ID**. Archive cả cụm là chôn phần còn sống
theo phần đã chết.

Đã tách `reference/decision-log.md`, thêm cột **trạng thái hôm nay** cho
từng quyết định, và một mục riêng cho D12 (xem 2.2).

**Không có D16.** Nhật ký dừng ở D15, nhưng hai chỗ trích "quyết định D16":
`apps/web/src/lib/useEpisodeStream.ts` và `API_CONTRACT.md`. Lỗi có sẵn từ
trước. Đã trỏ lại vào mục WebSocket của `api.md` — đúng thứ chúng muốn nói.

### 1.3. `FRONTEND.md` — bảng route đã sửa

Liệt kê `/benchmarks`, `/benchmarks/[id]`, `/leaderboard`; **cả ba không
còn** trong `apps/web/src/app/`. Đã viết lại bảng theo 19 route thật, bỏ
cột Milestone, và thêm mục giải thích ba route bị gỡ đi đâu.

Ghi thêm một điều bảng cũ không nói: `/leaderboard` **bị bỏ hẳn** chứ không
chuyển chỗ — xếp hạng ngoài ngữ cảnh một deployment cụ thể chính là phép
so không cùng điều kiện mà nền tảng này tồn tại để chặn.

### 1.4. `AI_CAPABILITIES.md` — chính xác, chỉ thiếu một dòng

Kiểm tự động: **12/12 endpoint tồn tại, 18/18 test file tồn tại.** File
tốt. Cái thiếu là **AI Analyst không có mặt trong bảng**.

Đã thêm mục **5g** kèm endpoint thật
(`POST /decisions/{id}/episodes/{eid}/analysis`, `GET .../verdict`) và 28
file test (`test_analyst_*.py` + 2 file API). Thêm ghi chú: 5g là mục
**duy nhất** trong bảng có chất lượng đầu ra đã chấm tay mù arm.

### 1.5. `AGENT_AI.md` — đúng, nhưng thiếu khai phạm vi

Nội dung về `services/agent_service/` chính xác. Vấn đề là đọc xong dễ
tưởng đã bao gồm analyst. Đã khai phạm vi ngay đầu file và trỏ sang
analyst. Bỏ "(M8)" khỏi tiêu đề.

### 1.6. `architecture_planner_selector.md` — chỉ dẫn đầu file đã sai

Khối "Quan hệ với ba file cũ" khẳng định `ARCHITECTURE.md` là "template
T-011 chưa điền (LangGraph + ChromaDB)". **Sai từ 2026-08-23** — file đó đã
viết lại và nay là sơ đồ kiến trúc hiện hành. Nó cũng trỏ
`docs/architecture_diagram.md`, file **chưa từng tồn tại** trong cây này.

Đã viết lại khối đó. Phần toán, ký hiệu, ánh xạ HĐ giữ nguyên — vẫn là
nguồn chi tiết tốt nhất.

### 1.7. `TEST_REPORT.md` — đúng thể loại, sai cách khai

Nó đọc như trạng thái hôm nay ("cập nhật sau mỗi milestone"), thật ra là
**ảnh chụp có ngày**, mục gần nhất 2026-08-17. Trong 21 test file nó nhắc,
**2 file không còn tồn tại** (`test_api_chat.py`, `test_report_markdown.py`).

Đã viết lại phần mở đầu: khai rõ đây là hồ sơ có ngày, **không cập nhật
lùi**, muốn biết test hôm nay có xanh không thì chạy `pytest`.

### 1.8. Các file còn lại — kiểm và giữ nguyên

| File | Kiểm gì | Kết quả |
|---|---|---|
| `ROS2_INTEGRATION.md` | 5 package khai vs `ros2_ws/` | **5/5 khớp** |
| `KNOWN_LIMITATIONS.md` | đường dẫn nó trích | không có đường dẫn hụt |
| `DEPLOYMENT.md`, `DESKTOP.md`, `DESKTOP-RELEASE.md`, `DEMO-PROFILE.md` | đường dẫn, biến môi trường | không thấy sai |
| `plugin_author_guide.md`, `plugin_import_security.md` | đường dẫn | không thấy sai |
| `EVAL_EVIDENCE.md` | thể loại | hồ sơ có ngày, đúng vai, giữ |

**Chưa làm:** `KNOWN_LIMITATIONS.md` (110 KB, ~90 mục) mới chỉ kiểm đường
dẫn, **chưa rà từng mục còn đúng không**. Đã ghi vào `03-gaps.md` §4.2 để
không ai tưởng nó đã được rà.

---

## 2. Hai lỗi phát hiện thêm khi rà

### 2.1. `README.md:735` — đã sửa

Câu *"`services/analyst_service/` chưa tồn tại"* trong tài liệu người ta
đọc đầu tiên, nói về hạng mục lớn nhất dự án. Thư mục đó có hơn 20 module,
nối vào API và web, và đã có 90 lượt chấm mù.

Đã viết lại §9.1: nêu đúng hiện trạng, kèm số đo (0.56 đa số ≥2/3, 1 câu
sai/90 lượt, 0 vi phạm ràng buộc cứng) và giữ nguyên ba món nợ thật —
`OFFICIAL_GOLDEN_READY = False`, 5/5 entry `draft`, `reference_analyst`
crash. **Ba món này tôi đã kiểm lại code và vẫn đúng.**

### 2.2. `README.md` §3.3 liệt kê `*+pure_pursuit` như ứng viên — đã sửa

Danh sách "stack đã đăng ký" gộp `astar+pure_pursuit` và
`rrtstar+pure_pursuit` chung với các stack thật. Đọc registry mới thấy cả
hai mang `reference=True`, và mô tả trong code nói thẳng:

> *"Temporary pipeline reference only — it ignores sensing, so it must not
> be used to draw benchmark conclusions."*

Chúng **bỏ qua cảm biến**. Một stack như vậy được khuyến nghị chính là thất
bại mà bộ cổng sinh ra để chặn.

Đã tách hai nhóm trong `README.md` §3.3 và trong `02-features.md`, kèm cờ
`production_eligible`. Đây cũng là bản thân **D12 vẫn còn hiệu lực** — tôi
suýt ghi ngược trong `decision-log.md` (đã viết là "đã đổi") rồi đọc
`registry.py` mới thấy sai và sửa lại trước khi ship.

---

## 3. Trỏ lại link — 50 file

Chạy script cơ học cho phần tra được, tay cho phần cần phán đoán.

**Cơ học — 43 file, 64 thay thế.** Ánh xạ: 14 file → `docs/reference/`,
2 file → `docs/archive/superseded/`, `docs/antongduy/` →
`docs/journal/antongduy/`, `docs/docs/` → `docs/archive/gate-g1/`,
`docs/guide/` → `docs/archive/course-guide/`, và
`docs/API_CONTRACT.md` → `docs/reference/api.md` (vì nội dung đã thay).

**Tay — 6 chỗ script không được phép đụng:**

| Chỗ | Vì sao không cơ học được |
|---|---|
| `geometry.py`, `collision.py`, `grid.py` | Trích `docs/architecture.md` cho **quyết định thiết kế**, không cho văn kiến trúc. Trỏ vào `decision-log.md` kèm đúng ID D07/D08/D10 |
| `useEpisodeStream.ts` | Trích "D16" — **không tồn tại**. Trỏ vào mục WebSocket của `api.md` |
| `deployment.py:257` + `test_roles.py:195` | Là **chuỗi runtime** trong thông báo cho người dùng, và có test ghim nó. Phải sửa cùng lượt |

**Một chỗ script làm sai, đã hoàn tác.** `contracts/CONTRACTS.md:5` viết
*"trước đây là `docs/antongduy/CONTRACTS_1.md`"* — một câu **lịch sử**. Viết
đè thành `docs/journal/antongduy/...` làm câu đó sai, vì file chưa bao giờ
ở đường dẫn ấy. Đã trả lại nguyên trạng, và quét toàn repo xem còn câu lịch
sử nào bị đè không — chỉ có một.

**Đã viết lại hẳn:**

- `README.md` §10 — bảng tài liệu cũ liệt kê 8 file phẳng, nay chia ba
  tầng: bốn file onboarding, `reference/`, rồi `journal/` + `archive/`.
- `CLAUDE.md` §5 — thêm bảng bốn tầng và **ai được sửa tầng nào**
  (`journal/` chỉ thêm không sửa bài cũ; `archive/` đừng sửa đừng trích số),
  cập nhật quy ước đường dẫn thành `docs/journal/antongduy/...`.

---

## 4. Kiểm chứng

| Phép kiểm | Kết quả |
|---|---|
| Link tương đối trong `docs-v2` | **372 link, 0 hỏng** |
| Đường dẫn `docs/…` trích từ ngoài, resolve vào cấu trúc mới | 40 đường dẫn, **0 trỏ hụt thật** |
| `pytest tests/test_roles.py` (test ghim chuỗi runtime) | **38 passed** |
| `vitest` 3 file web đã sửa | **135 passed** |
| `npx tsc --noEmit` | **sạch** |
| `ruff format --check` trên 5 file sửa tay | **already formatted** |
| `ruff check packages services apps/api tests scripts` | 5 lỗi, **không lỗi nào ở file tôi sửa** — `map_files.py`, `test_analyst_episode_round.py`, `test_retention.py`, có sẵn từ trước |
| `git diff --stat` mẫu | 2–3 dòng/file — **không có hỏng CRLF** |

Sáu "trỏ hụt" mà script báo đều là dương tính giả, đã kiểm từng cái:
`https://platform.openai.com/docs/models` và
`https://ai.google.dev/…/docs/models` (URL ngoài), `docs/app/api-reference/…`
(URL nextjs.org trong `next-env.d.ts`), `"docs/HĐ-6.md"` và
`"docs/preregistration/analyst-gate-1.md"` (chuỗi fixture trong test, thư
mục chưa từng có — lỗi có sẵn, không phải của đợt này), một đường dẫn bị
ngắt dòng trong docstring (resolve đúng), và câu lịch sử ở mục 3.

---

## 6. Phát hiện ngoài phạm vi: 5 test golden parity đang đỏ sẵn

Chạy test để nghiệm thu thì gặp 5 test đỏ ở `tests/test_host_parity_golden.py`.
**Không phải do đợt này**, và đã chứng minh chứ không suy luận.

### Cách chứng minh

Dựng một worktree sạch ở `HEAD` (`git worktree add`, tách hẳn khỏi cây làm
việc của An), chạy **đúng tổ hợp 8 file** đó trên cây không có thay đổi nào
của tôi:

```
5 failed, 206 passed, 1 skipped in 800.41s
```

**Đỏ y hệt 5 test, cùng file.** Trên cây của tôi cũng 5 test đó, cùng thông
báo. Kết luận: có sẵn từ trước.

Thêm một lớp nữa: lọc toàn bộ `git diff` các file `.py` của đợt này, bỏ
dòng comment và dòng chứa `docs/`, thì **không còn dòng nào**. Nghĩa là mọi
thay đổi `.py` đợt này là comment/docstring — không có dòng thực thi nào
đổi, nên về nguyên tắc cũng không thể tác động tới kết quả mô phỏng.

### Nó hỏng ở đâu

```
assert json.dumps(measured, indent=1) == GOLDEN_PATH.read_text(...)
-  66025511915,
+  66025511916,
```

Lệch **1 đơn vị cuối** ở một giá trị số trong episode đã ghim. Đây là kiểu
lệch tái lập số học giữa máy ghi fixture golden và máy đang chạy — khác
thư viện số, khác phiên bản, hoặc khác nền tảng.

### Vì sao đáng quan tâm

Đây đúng là loại lỗi mà `CLAUDE.md` mục 6 cảnh báo: *"Đừng pin thứ không
phải hành vi"*. Test này so **byte-identical** trên `json.dumps` của cả
episode, nên nó bắt cả những chênh lệch không phải hành vi. Một sai khác
1 ULP không nói lên stack chạy khác đi, nhưng nó làm cổng đỏ và che mất
những sai khác thật.

**Chưa sửa** — nằm ngoài phạm vi An giao, và sửa nó là một quyết định về
ngưỡng dung sai chứ không phải một thao tác dọn dẹp. Hai đường đi:

1. Sinh lại fixture trên máy này (`PLANBENCH_REGEN_HOST_PARITY=1`) — nhanh,
   nhưng chỉ đẩy vấn đề sang máy tiếp theo.
2. So theo **dung sai** thay vì byte-identical cho trường số thực, giữ
   byte-identical cho phần cấu trúc — pin tính chất thay vì pin hình dạng.

Đường 2 khớp với luật trong `CLAUDE.md` hơn, nhưng cần An quyết vì nó nới
một cổng đang chặt.

---

## 5. Còn lại, chờ An quyết

- **`docs-v2/` vẫn đang gitignore, `docs/` gốc chưa đụng.** Nhưng lần này
  `README.md`, `CLAUDE.md`, `contracts/CONTRACTS.md` và ~50 file code **đã
  sửa thật** và đang trỏ vào cấu trúc mới. **Chúng đang hụt cho tới lúc
  swap.** Hai việc phải vào cùng một commit.
- **Chưa dọn** `README.old.md`, `JOURNAL.md`, `WORKLOG.md` (hai file sau là
  template cohort chưa điền), dòng nháp `README.md` §6, và lỗ đánh số §9.4–9.5.
- **Chưa rà từng mục `KNOWN_LIMITATIONS.md`.**

### Lệnh swap

```powershell
# đồng bộ file An tạo thêm sau lúc chụp, nếu có
mv docs docs-old ; mv docs-v2 docs
# gỡ dòng docs-v2/ khỏi .gitignore
```

Sau swap, chạy lại script kiểm ở
`scratchpad/validate.py` (đổi `docs-v2` thành `docs`) để chắc 0 hỏng.

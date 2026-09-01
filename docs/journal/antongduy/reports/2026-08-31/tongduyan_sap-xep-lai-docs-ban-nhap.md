# Sắp xếp lại `docs/` — bản nháp `docs-v2/`, chờ duyệt

**Ngày:** 2026-08-31 · **Nhánh:** `tongduyan_signin-landing-and-updater`
**Trạng thái:** bản nháp, `docs-v2/` đã gitignore. **Chưa đụng `docs/` gốc.**

Mục tiêu An đặt ra: một người mới đọc `docs/` là hiểu được sản phẩm hướng
tới **tệp người dùng nào**, **kiến trúc** ra sao, **tính năng nổi bật** là
gì, và **phần nào chưa tốt**.

---

## 1. Vì sao hôm nay chưa đạt

`docs/` có 360 file, **không có entry point** — không `docs/README.md`, và
`README.md` ở gốc repo (mục 10) chỉ liệt kê 8 trong 18 file top-level.

Sáu vấn đề đo được:

**1.1. Bốn tài liệu kiến trúc mâu thuẫn nhau.** `ARCHITECTURE.md` (đúng,
viết lại 08-23) · `docs/architecture.md` (dừng ở "Giai đoạn 1A", trước
chuyển hướng 08-08) · `docs/architecture_planner_selector.md` (đúng về
toán, nhưng phần đầu **khẳng định `ARCHITECTURE.md` là template LangGraph +
ChromaDB chưa điền** — claim đó nay sai) · PRD §26 (Gate G1, 08-02).

**1.2. Từ vựng milestone M0–M13 đã chết.** `IMPLEMENTATION_STATUS.md`
tuyên bố "M13 hoàn thành, toàn bộ M0–M13 đã xong". Đề tài chuyển hướng
08-08; mọi việc từ đó tính theo phase và `HĐ-x.y`. Người mới đọc file đó
thấy "đã xong" cho một sản phẩm không còn tồn tại.

**1.3. `FRONTEND.md` có bảng route sai — đã đối chiếu code.** Nó liệt kê
`/benchmarks` và `/leaderboard`; `apps/web/src/app/` không có route nào
trong hai cái đó.

**1.4. Tệp người dùng — mục An muốn nhất — là mục yếu nhất.** Danh sách
tường minh duy nhất nằm ở `docs/docs/01-brief.md` §3 và PRD §7–8, đề ngày
**2026-08-02, trước chuyển hướng**. `README.md` gốc không nêu tệp người
dùng ở đâu cả.

**1.5. Hai cây tài liệu không thuộc sản phẩm.** `docs/guide/` (46 file
sách khoá học cohort: chapter 01–10, LangGraph, BMAD, hướng dẫn mở tài
khoản Cohere/Groq — repo **không dùng** LangGraph, **không dùng** ChromaDB).
`docs/docs/` (6 file deliverable Gate G1).

**1.6. 291 file nhật ký cá nhân lấn át theo số lượng.** `antongduy/` 281
file + `hungnguyen-1601/` 10 file, xếp theo ngày. Là lịch sử tốt, nhưng
người mới không onboard từ đó được, và chúng làm chìm 18 file tài liệu sản
phẩm.

**Một câu sai đáng kể phát hiện thêm:** `README.md:735` viết
*"`services/analyst_service/` chưa tồn tại"*. Thư mục đó **tồn tại với
hơn 20 module**, đã wired vào API (`routers/agent.py`,
`routers/decisions.py`, có quota ngày) và web (`components/DockAnalyst.tsx`),
và đã có 90 lượt chấm mù. Câu đó nằm trong tài liệu người ta đọc đầu tiên,
mô tả hạng mục lớn nhất của dự án. Các claim khác cùng mục (golden 3/6,
KB 5/5 `draft`, `reference_analyst` crash) **tôi đã kiểm lại và vẫn đúng** —
`OFFICIAL_GOLDEN_READY = False` tại `packages/explanation/planbench_explanation/golden.py:69`,
`review_status="draft"` tại `knowledge.py:186,209`.

---

## 2. Đã làm gì

### 2.1. Cấu trúc mới

```
docs-v2/
  README.md            entry point — thứ tự đọc, bản đồ thư mục, thứ hạng nguồn sự thật
  00-product.md        sản phẩm là gì, 5 nhóm + 3 persona, ba gói quyền, cố ý KHÔNG làm gì
  01-architecture.md   3 nguyên tắc, bản đồ tầng, route thật, LLM đứng đâu, 6 bất biến dễ phá
  02-features.md       3 tính năng nổi bật + phần còn lại theo vòng đời, mỗi mục có trạng thái
  03-gaps.md           nợ xếp theo mức nghiêm trọng, gồm cả nợ của chính tài liệu

  reference/  (15 file + README)  tra cứu khi làm việc
  archive/                        đã bị thay, giữ để tra lịch sử
    superseded/   architecture.md · IMPLEMENTATION_STATUS.md · workflow.md
    gate-g1/      6 file deliverable Gate G1
    course-guide/ 46 file sách khoá học
  journal/    (+ README)          nhật ký theo ngày
    antongduy/          + INDEX.md — 278 file xếp lại theo 10 chủ đề
    hungnguyen-1601/
  assets/
```

Bốn file `00`–`03` đọc theo thứ tự mất khoảng 40 phút và phủ đúng bốn câu
hỏi An nêu.

### 2.2. Nội dung mới viết

| File | Điểm đáng chú ý |
|---|---|
| `00-product.md` | Nêu **kỹ sư AMR/AGV là persona trung tâm** và giải thích vì sao mọi đánh đổi thiết kế chọn theo tình huống đó. Có mục "cố ý **không** làm gì" tách khỏi "chưa làm được" |
| `01-architecture.md` | Route đối chiếu thẳng `apps/web/src/app/`. Mục 7 chép lại 6 bất biến dễ phá từ `CLAUDE.md` — người mới cần chúng trước dòng code đầu tiên |
| `02-features.md` | Đưa **AI Analyst thành tính năng nổi bật số 3** kèm số đo thật (90 lượt, `explains` 0.56 đa số ≥2/3, 0 vi phạm ràng buộc cứng) — mảng này trước đây **không có mặt trong `docs/`**, chỉ sống trong journal |
| `03-gaps.md` | Xếp 4 hạng theo mức nghiêm trọng. Hạng 4 là **nợ của chính tài liệu**, gồm câu sai ở `README.md:735`. Kết bằng 3 việc nên làm trước nếu tiếp nhận dự án |
| `journal/antongduy/INDEX.md` | 10 chủ đề, mỗi chủ đề nêu file mốc. Kèm mục "đọc gì nếu chỉ có 30 phút" |

### 2.3. Banner cảnh báo — **không sửa ruột file nào**

Bảy file được thêm banner ở đầu, nội dung gốc giữ nguyên văn:
`archive/superseded/` (3 file), `reference/FRONTEND.md` (route sai),
`reference/architecture_planner_selector.md` (claim về `ARCHITECTURE.md` đã
cũ), `reference/AGENT_AI.md` và `reference/AI_CAPABILITIES.md` (viết trước
analyst).

### 2.4. Sửa link

Dời `antongduy/` và `hungnguyen-1601/` xuống `journal/` làm sâu thêm một
cấp. Đã rà và sửa:

- **90 link** đổi độ sâu (`../../../` → 4 cấp: 6 link; `../../../../` →
  5 cấp: 84 link). 33 link 1–2 cấp giữ nguyên vì chúng trỏ trong nội bộ
  cây journal.
- **18 link hỏng** do dời thư mục: `gate-g1/` và `superseded/` trỏ tới
  `../KNOWN_LIMITATIONS.md` kiểu cũ, 3 link tới `DESKTOP.md`/`DESKTOP-RELEASE.md`,
  và `plugin_author_guide.md` → `../examples/plugins`.
- **3 link hỏng sẵn từ trước** trong
  `plans/2026-08-12/map-custom-va-ket-qua-tung-episode.md` — dùng
  `../../../packages/…` (3 cấp) trong khi cần 4. Đã sửa luôn.

**Kiểm:** script duyệt toàn bộ `.md`, resolve từng link tương đối —
**364 link, 0 hỏng.** Đối chiếu tên file giữa `docs/` và `docs-v2/`:
không mất file nào.

### 2.5. Bỏ đi

3 file `docs/antongduy/.omc/state/sessions/*/last-tool-error-state.json` —
rác trạng thái tool, đã nằm trong gitignore sẵn.

---

## 3. Chưa làm — chờ An quyết

- **Chưa đụng `docs/` gốc.** `docs-v2/` là bản song song, đã thêm vào
  `.gitignore` (dòng cuối file, kèm chú thích).
- **Chưa sửa `README.md:735`** — nó nằm ngoài `docs/`, và An chưa bảo sửa
  file gốc. Đây là việc nên làm sớm nhất trong ba việc `03-gaps.md` đề nghị.
- **Chưa dọn** `README.old.md`, `JOURNAL.md`, `WORKLOG.md` (hai file sau là
  template cohort chưa điền), và dòng nháp ở `README.md` §6 trỏ tới
  `README.old.md`. Cũng nằm ngoài `docs/`.
- **Chưa sửa ruột file stale nào** — đúng như An chọn. `FRONTEND.md` vẫn
  còn bảng route sai, chỉ có banner cảnh báo phía trên.

---

## 4. Lấy bản này thì làm gì

`docs-v2/` là **ảnh chụp** lúc bắt đầu phiên. Trong lúc làm, An đã tạo
thêm `reports/2026-08-31/tongduyan_pitch-deck-v2-10-slide.md`; tôi đã chép
bổ sung. Nếu còn file mới nữa thì đồng bộ trước khi thay.

```powershell
# 1. đồng bộ file An tạo thêm sau lúc chụp (nếu có)
# 2. thay
git rm -r --cached docs        # nếu muốn giữ lịch sử thì dùng git mv từng phần
mv docs docs-old ; mv docs-v2 docs
# 3. gỡ dòng docs-v2/ khỏi .gitignore
# 4. sửa link trỏ vào docs/ ở README.md §10, CLAUDE.md §5, ARCHITECTURE.md
```

Bước 4 quan trọng: `README.md` mục 10 và `CLAUDE.md` mục 5 đều trỏ vào
đường dẫn `docs/antongduy/…` kiểu cũ. Dời sang `docs/journal/antongduy/…`
thì phải sửa cả hai, và sửa cả quy ước ghi docs trong `CLAUDE.md`.

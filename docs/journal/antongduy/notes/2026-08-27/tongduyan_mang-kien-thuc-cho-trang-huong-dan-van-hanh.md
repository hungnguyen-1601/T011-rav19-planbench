# Trang hướng dẫn vận hành trên UI — những mảng kiến thức phải đưa vào

**Ngày:** 2026-08-27 · **Loại:** khảo sát, không đổi dòng code nào
**Phạm vi đọc:** `README.md` (§1–§10), `contracts/CONTRACTS.md`,
`docs/AI_CAPABILITIES.md`, `docs/DESKTOP.md`, `docs/plugin_import_security.md`,
`docs/KNOWN_LIMITATIONS.md`, `docs/FRONTEND.md`, `docs/IMPLEMENTATION_STATUS.md`,
217 file `.md` trong `docs/antongduy/` (đọc kỹ nhóm 08-13 → 08-27),
`apps/web/src/lib/navigation.ts`, `apps/web/src/lib/i18n/locales/*.json`,
`apps/api/planbench_api/routers/`.

---

## 0. Kết luận một câu

Nội dung cho trang hướng dẫn **đã tồn tại gần đủ** — `README.md` §4 là bản
hướng dẫn vận hành hoàn chỉnh nhất đang có (10 mục, đi từ vẽ bản đồ tới
duyệt kết quả). Việc thiếu không phải là *viết nội dung mới*, mà là **ba
việc khác**: (a) chọn cái gì thuộc về UI và cái gì để lại README, (b) bổ
sung bốn mảng README chưa phủ, (c) chốt cơ chế giữ trang không lỗi thời —
vì ba tài liệu vận hành trong repo (`docs/FRONTEND.md`,
`IMPLEMENTATION_STATUS.md`, `KNOWN_LIMITATIONS.md`) **đã lỗi thời** và
copy chúng vào UI là nhân bản cái sai.

---

## 1. Mảng A — Luồng vận hành chính (xương sống của trang)

Bảy bước, có thứ tự phụ thuộc, mỗi bước cần thứ bước trước tạo ra.
Nguồn: `README.md` §4.1–§4.10.

| # | Bước | Trang | Bỏ qua được khi |
|---|---|---|---|
| 1 | Vẽ bản đồ | `/maps` → `/maps/[id]` | import từ thư viện, hoặc dùng map mẫu |
| 2 | Mission + vật cản động | `/library` (import) hoặc khai thẳng ở bước 3 | luôn (đường tự khai) |
| 3 | Khai deployment | `/deployments` tab *create* (form) hoặc dán YAML | không — đây là bước bắt buộc |
| 4 | Ứng viên | `/candidates`, `/models` (PPO `.zip`) | có — bước 6 chọn stack tại chỗ được |
| 5 | Chạy thử một episode | `/simulate` | có, nhưng bỏ là mất chỗ bắt map hở tường / mission bất khả thi trước khi tốn giờ |
| 6 | Chạy phép so | `/decisions` → *Chạy một phép so* | không |
| 7 | Đọc · xuất · duyệt | `/decisions/[id]`, `/reviews` | duyệt là tùy chọn |

**Điều trang phải nói mà README nói rồi, đừng bỏ:** thứ tự này là thứ tự
*phụ thuộc*, không phải thứ tự khuyến nghị. Người dùng dùng map + scenario
dựng sẵn thì bắt đầu thẳng từ bước 3.

---

## 2. Mảng B — Mười khái niệm phải giải thích **trước** thao tác

Đây là mảng dễ bị bỏ nhất khi viết hướng dẫn, và là mảng làm hướng dẫn trở
nên vô dụng nếu bỏ: người dùng bấm đúng nút nhưng đọc sai kết quả.

| # | Khái niệm | Nguồn | Hỏng thế nào nếu không nói |
|---|---|---|---|
| B1 | **Ứng viên là một stack hoàn chỉnh, không phải "một thuật toán"**. A\*/RRT\* là global planner, DWA là local controller — không xếp cùng bảng | HĐ-1.1 | "A\* thắng RRT\*" là câu sai địa chỉ |
| B2 | **Ghép cặp theo `episode_context`**: cùng seed, cùng vị trí vật cản, cùng nhiễu; hiệu số tính theo từng cặp | HĐ-3, README §3.3 | đọc ΔU như hiệu hai trung bình rời nhau |
| B3 | **`conditions_checksum`** — "hai bên chạy cùng điều kiện" là thứ kiểm lại được | README §2 | tin lời người chạy benchmark |
| B4 | **Mã deployment là danh tính một thế giới.** Nộp lại cùng mã với nội dung khác **bị từ chối, không gộp** | README §4.3 | mọi kết quả cũ biến thành kết quả của một thứ khác |
| B5 | **Không hằng số ngưỡng trong code** — mọi ngưỡng cổng đọc từ deployment | README §3.1, §8 | người dùng đi tìm nút chỉnh ngưỡng ở chỗ không có |
| B6 | **Cổng G1–G6 ≠ điểm số.** Cả sáu luôn chạy, không dừng ở cổng hỏng đầu | README §3.4 | "bị loại ở G2" mà không biết G4 ra sao — chẩn đoán không hành động được |
| B7 | **0 va chạm trong N lượt là chặn trên ~3/N (95%), không phải chứng chỉ**; G2 đòi thêm `N ≥ N_min` | README §3.4 | đọc thành lời hứa an toàn |
| B8 | **G4/G5 chỉ chứng minh một chiều** — sàng lọc trên host: hỏng thì chắc hỏng trên đích, đạt thì không chứng minh gì | README §3.4 | mang kết quả latency host đi hứa với khách |
| B9 | **CI vắt qua 0 = run này không chứng minh được chênh lệch nó báo** | README §3.5 | đọc dấu của ΔU thay vì đọc khoảng |
| B10 | **Đổi đúng một thành phần mỗi lần so** | README §4.6 | hiệu số không quy được cho thành phần nào |

Thêm hai điều thuộc cùng nhóm, đáng đặt cạnh nhau:

- **Từ hệ thống không được phép nói:** "an toàn", "sẵn sàng production",
  "TCO" — có hàm kiểm và test CI canh. Người dùng cần biết vì sao báo cáo
  không có những chữ họ mong đợi.
- **Thang bằng chứng bốn mức** (`observed` → `associated` →
  `mechanism_verified` → `intervention_supported`) và **không có mức thứ
  năm cho "không biết"**: thiếu bằng chứng nghĩa là không có claim.

---

## 3. Mảng C — Vận hành từng trang, khớp route thật

Route thật lấy từ `apps/web/src/lib/navigation.ts` (không lấy từ
`docs/FRONTEND.md` — file đó còn liệt kê `/benchmarks`, `/leaderboard`,
`/algorithms` theo bố cục cũ).

| Nhóm sidebar | Route | Phải hướng dẫn gì |
|---|---|---|
| Workspace | `/` | đọc trạng thái, quick action |
| | `/deployments` | hai tab *create* / *list*; hai chế độ form ⇄ YAML; sáu nhóm trường (Danh tính · Robot · Ngưỡng · Nhiễu · Vật cản động · Mission) |
| | `/simulate` | chọn map/kịch bản/thuật toán, đặt start-goal trên bản đồ, playback + lớp hiển thị |
| | `/decisions` | xếp hàng run; lọc theo deployment/kết cục; **run không xếp hạng ai vẫn là kết quả** |
| Resources | `/maps`, `/maps/[id]` | bút vẽ, phiên bản mới + checksum mỗi lần lưu, **map phải có tường bao kín** |
| | `/library` | preview không lưu gì; một lần import tạo **cả map lẫn kịch bản** |
| | `/candidates` | ba phần: thuật toán có sẵn · stack registry · đăng ký ứng viên |
| | `/models` | upload PPO `.zip` + checksum + tương thích robot; **không có nút xoá**; tab *Nhập thuật toán* |
| | `/scenarios` | đánh dấu `legacy` — nói rõ nó bị thay bởi form deployment |
| Account | `/agent` | trợ lý hội thoại bản đầy đủ |
| | `/reviews` | inbox/sent, approve/reject/comment/cancel |
| | `/settings` | **chỉ admin** — model + API key |
| | `/system` | phiên bản, health, API URL |

Trang chi tiết một run `/decisions/[id]` có **bốn tab** (`conclusion` ·
`episode` · `reasoning` · `more`) và trang này chiếm 322 key i18n — nhiều
nhất hệ thống. Hướng dẫn phải nói **thứ tự đọc** (README §4.7 đã có bảng
"mục nào trả lời câu gì"), không chỉ liệt kê tab.

---

## 4. Mảng D — Bốn thứ README **chưa** phủ, phải viết mới

### D1. Import thuật toán qua UI

`README.md` §9.2 vẫn nói *"chưa có đường vào"*. **Câu đó đã lỗi thời** —
P0–P4 xong ngày 2026-08-24
(`reports/2026-08-24/tongduyan_import-thuat-toan-tren-ui-p0-p4.md`), và
bundle MPPI đã import chạy thật ngày 26-08. Hướng dẫn phải nói:

- Đường đi: **Models → tab "Nhập thuật toán"** → chọn `.zip` → nhập.
- **Chỉ admin** (`user.is_admin`) — `plugin_service._require_admin`.
- Bundle phải là `.zip` **có code**, không phải chỉ manifest.
- **Lane subprocess bắt buộc**; và subprocess là **cô lập crash, không
  phải sandbox** — worker thừa kế environment, `PYTHONPATH`, quyền
  filesystem và mạng. Câu này đã cố ý lặp ở ba chỗ trong repo; đây phải là
  chỗ thứ tư, không được làm nhẹ đi.
- **Hiện không import được global planner.** `plugin_registry.py:55`:
  `SUPPORTED_ROLES = {"local", "monolithic"}`. Đây là điều mâu thuẫn trực
  tiếp với câu quảng bá ở §2 README, và trang hướng dẫn là chỗ phải nói rõ.
- Bốn trần: 50 MB zip · 500 member · 200 MB sau giải nén · 64 KB manifest.
- **Không có DELETE** — cùng lý do trang Models không có.

### D2. Bật model thật cho AI, và hai lớp AI khác nhau

- **Hai biến, không một**: `PLANBENCH_AGENT_PROVIDER` + `PLANBENCH_AGENT_MODEL`.
  `auto` bỏ qua provider có key mà không có tên model — README gọi đây là
  lỗi cấu hình hay gặp nhất.
- Bản desktop: dán key ở **Settings**, có hiệu lực ngay, ghi vào
  `%LOCALAPPDATA%\PlanBench\.env`.
- Chưa có key thì **cả hai lớp chạy bằng bộ khớp từ khoá offline** và giao
  diện nói thẳng — trang hướng dẫn phải nói người dùng đang nhìn cái gì.
- **Phân biệt hai lớp** (README §3.7, `docs/AI_CAPABILITIES.md`): dock hội
  thoại (11 tool chỉ-đọc, không chạy được phép so, không sửa deployment,
  không duyệt gì) ≠ lớp cố vấn (nút *Hỏi thêm model*, xếp lại advice luật
  + thêm tối đa 3 ý, không xoá được advice luật).
- Bốn ràng buộc của lớp cố vấn, mỗi cái đã được chứng minh bắt được lỗi
  thật bằng cách tiêm lỗi vào.

### D3. Chạy hệ thống — ba đường, ba runbook khác nhau

| Đường | Lệnh / thao tác | Bẫy phải cảnh báo |
|---|---|---|
| Web đã triển khai | `planbench-web.onrender.com` | — |
| Cục bộ | `bash scripts/dev_stack.sh start\|status\|logs\|stop` | script chạy `alembic upgrade head` trước; migration lỗi thì **dừng**, không khởi động API với schema cũ |
| Windows thuần | `.venv\Scripts\python.exe scripts\serve.py --reload --migrate` | **đừng gọi thẳng `python -m uvicorn`** — dự án không được cài đặt, `packages/`+`services/` chỉ vào `sys.path` qua `serve.py` |
| Desktop | `PlanBench-Setup.exe` | đăng nhập `admin`/`admin`; dữ liệu ở `%LOCALAPPDATA%\PlanBench`; SmartScreen cảnh báo vì chưa ký |

Cộng đường thứ năm: **API trực tiếp** — `/docs`, Authorize, hoặc `curl`
`POST /api/v1/decisions`. 15 router, 91 endpoint.

### D4. Xuất, chia sẻ, và nhờ duyệt

- Xuất Markdown · Excel (mở đầu bằng trang Summary, số là số nên sắp/lọc
  được) · link chia sẻ cho người không có tài khoản. Cả hai bản xuất theo
  **ngôn ngữ đang chọn**.
- Tên file Excel: `<project>_<comparison>_<YYYY-MM-DD_HH-mm>.xlsx`; trên 2
  candidate thì **đếm** chứ không liệt kê.
- Duyệt là **tùy chọn**; chọn duyệt *spec* (trước khi chạy) hay *result*
  (sau khi chạy); **chính chủ không tự duyệt được** khi đang chờ.

---

## 5. Mảng E — Phải nói thẳng cái chưa làm được

README §9 cố ý dài, lý do nêu trong chính nó: *"một README chỉ liệt kê thứ
đã xong là một README nói dối bằng cách im lặng"*. Trang hướng dẫn kế thừa
nguyên tắc đó, nhưng **phải cập nhật lại vì §9 có chỗ đã cũ**:

| Hạng mục | README §9 nói | Thực tế hôm nay |
|---|---|---|
| Import thuật toán qua UI | "chưa có đường vào" | **đã có** từ 24-08, xem D1 |
| Golden 6 họ | "chỉ dựng được 3/6" | 6 họ dựng xong trên nhánh `tongduyan_ai-analyst-ban-8` (`1110e78`), **chưa merge**; `OFFICIAL_GOLDEN_READY = False` ở cây chính |
| `services/analyst_service/` | "chưa tồn tại" | **đã tồn tại** trên nhánh analyst; P0–P2 xong, P3 API / P4 UI chưa |
| Cơ sở tri thức cơ chế | 5/5 `draft` | chưa đổi |
| Replay đồng bộ theo quãng đường | chưa làm | chưa đổi |
| Trợ lý không có trí nhớ hội thoại | đúng | chưa đổi — và đây là **quyết định thiết kế**, phải nói kèm lý do, không nói như một lỗi |

**Đây là mảng rủi ro cao nhất của cả trang.** Một trang hướng dẫn trong UI
được đọc như lời hứa của sản phẩm; nói sai chỗ chưa làm được thì tệ hơn là
không có trang.

---

## 6. Mảng F — Quyền hạn, và tại sao nó chặn thiết kế trang này

Hiện trạng (`notes/2026-08-27/tongduyan_khao-sat-hien-trang-role.md`):
**code không có role engineer/reviewer**. Chỉ `member` + cờ `is_admin`;
quyền dựa trên *ownership* và *review opt-in*.

Nhưng plan `plans/2026-08-27/thiet-ke-role-engineer-reviewer-admin.md` đã
được duyệt sau bảy vòng phản biện, chuẩn bị thi hành từ P0 với ma trận
capability đầy đủ (`resource.read/write`, `simulation.run`, …) và bốn role
`engineer · reviewer · admin · demo_owner`.

Hệ quả cho trang hướng dẫn — **hai ràng buộc**:

1. **Viết theo capability, không viết theo tên role.** "Chỉ admin mới nhập
   được thuật toán" sẽ sai ngay khi P0 chạy. Viết "cần `plugin.import`" thì
   không sai.
2. **Ràng buộc cứng còn hiệu lực:** bản desktop đã phát hành đang được ban
   giám khảo chấm bằng `admin:admin`; sau update tài khoản đó phải dùng
   được toàn bộ app. Trang hướng dẫn nếu hiển thị "bạn không có quyền X"
   theo role mới thì phải kiểm với đúng tài khoản đó trước.

---

## 7. Mảng G — Ràng buộc kỹ thuật khi làm trang

| Ràng buộc | Chi tiết |
|---|---|
| **Song ngữ bắt buộc** | `en.json` và `vi.json` mỗi file 1863 dòng, đối xứng, có test canh key. Mọi chữ của trang mới phải qua i18n — không hardcode |
| **Sidebar là data-driven** | `NAV_SECTIONS` trong `navigation.ts` là nguồn duy nhất cho sidebar + title + breadcrumb. Thêm route = sửa một chỗ; `descriptionKey` là **bắt buộc** với route có mặt trên rail (có test canh) |
| **UI chỉ render, không tính toán** | Nguyên tắc xuyên suốt `docs/FRONTEND.md`. Trang hướng dẫn là nội dung tĩnh nên không đụng, nhưng nếu định hiển thị trạng thái thật ("bạn đã có 3 deployment") thì số phải từ API |
| **Nguồn nội dung nào là nguồn thật** | `README.md` (§4) và `contracts/CONTRACTS.md` — cập nhật. `docs/FRONTEND.md`, `IMPLEMENTATION_STATUS.md`, `KNOWN_LIMITATIONS.md` — **lỗi thời**, đừng copy |

---

## 8. Ba câu cần An chốt trước khi làm

1. **Nội dung sống ở đâu.** Ba lựa chọn, khác nhau về chi phí giữ đồng bộ:
   (a) chuỗi i18n hardcode trong page — đơn giản nhất, nhưng README và
   trang sẽ trôi khỏi nhau; (b) MDX/markdown build vào bundle — viết dễ,
   song ngữ phải quản hai cây file; (c) API trả nội dung đọc từ `docs/` —
   một nguồn, nhưng bản desktop phải đóng gói kèm.
2. **Một trang hay một trang + trợ giúp theo ngữ cảnh.** Form deployment
   đã có dấu `?` từng ô. Nếu làm trang tổng thì có nên link ngược từ mỗi
   `?` về đúng mục trong trang không.
3. **Phạm vi độc giả.** Ban giám khảo (đọc để chấm, cần "chạy thử ngay
   được") và người vận hành thật (cần cả mảng B và mảng E) đọc hai kiểu
   khác nhau. Một trang phục vụ cả hai thì phải có lối tắt "5 phút đầu",
   và điều đó ảnh hưởng bố cục.

---

## 9. Đề xuất bố cục (chưa làm, chờ chốt mục 8)

```
/guide
├── 0. Năm phút đầu — chạy thử một phép so với dữ liệu dựng sẵn
├── 1. Bảy bước, theo thứ tự phụ thuộc          (mảng A)
├── 2. Đọc kết quả cho đúng                     (mảng B — 10 khái niệm)
├── 3. Từng trang làm gì                        (mảng C)
├── 4. Việc nâng cao
│   ├── nhập thuật toán của bạn                 (D1)
│   ├── bật model thật                          (D2)
│   ├── xuất và nhờ duyệt                       (D4)
│   └── chạy cục bộ / qua API                   (D3)
├── 5. Hệ thống chưa làm được gì                (mảng E)
└── 6. Bạn được làm gì                          (mảng F — theo capability)
```

Mục 0 và mục 5 là hai mục không có trong README theo hình dạng này, và là
hai mục đáng giá nhất của việc đưa hướng dẫn lên UI.

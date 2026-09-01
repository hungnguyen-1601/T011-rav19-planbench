# Chưa tốt, chưa hoàn thiện, và chỗ đừng dựa vào

> Cố ý dài. Một tài liệu chỉ liệt kê thứ đã xong là tài liệu **nói dối bằng
> cách im lặng**, và người định dựa vào nền tảng này cần biết chỗ nào chưa
> đỡ được sức nặng.
>
> Danh sách chi tiết từng mục kỹ thuật (~90 mục):
> [reference/KNOWN_LIMITATIONS.md](reference/KNOWN_LIMITATIONS.md).
> File này xếp theo **mức nghiêm trọng với người tiếp nhận dự án**.

Xác minh lần cuối: **2026-08-31**.

---

## Hạng 1 — ảnh hưởng tới lời hứa trung tâm

### 1.1. Tầng "vì sao" — hạng mục lớn nhất còn dở

Contract phía nền tảng **đã xong**: 16 tool card, 4 checker, promotion
matrix, thang bằng chứng, sidecar. Analyst theo episode **đã viết và đã
đo** (xem [02-features.md](02-features.md) §3).

Cái còn thiếu là **dữ liệu để nâng mức bằng chứng**:

| Món nợ | Trạng thái đo được | Hệ quả |
|---|---|---|
| Bộ golden | `OFFICIAL_GOLDEN_READY = False` — chỉ dựng được **3/6 họ**. Ba họ còn lại cần một sweep nhiều context chứ không phải một episode | Không chấm được analyst trên bộ chuẩn chính thức |
| Cơ sở tri thức cơ chế | **5/5 entry còn `review_status="draft"`** (`packages/explanation/planbench_explanation/knowledge.py`) | Chưa entry nào được duyệt ⇒ chưa claim nào dựa vào nó được nâng mức |
| Sàn model-free `reference_analyst` | Crash trên packet thật — lỗi che biến, đã ghi nhận, **chưa sửa** | Không có sàn để so analyst có model với analyst không model |

Hiệu năng analyst hiện tại — **giải thích được outcome ở 0.56 (đa số ≥2/3
lượt, mẫu số 18)** — là con số **đo tay, chưa vào CI**. Nó tốt hơn arm đầu
(0.11) nhưng còn xa mức "tin được mà không đọc lại".

### 1.2. Chưa gọi model thật trong CI

Toàn bộ test của lớp AI dùng provider script sẵn. Chúng chứng minh **cái
khung** đúng; chúng **không nói gì** về chất lượng model viết.

Đã đo tay: 3 run × 2 model
([journal/antongduy/notes/2026-08-24/](journal/antongduy/notes/2026-08-24/))
và 90 lượt chấm mù cho analyst
([journal/antongduy/reports/2026-08-31/](journal/antongduy/reports/2026-08-31/)).
Nhưng một regression về chất lượng văn model **sẽ không làm CI đỏ**.

---

## Hạng 2 — lời hứa đúng một nửa

### 2.1. Import thuật toán qua giao diện — chưa có đường vào

Sản phẩm nói "ai cũng cắm được thuật toán của mình vào". Hôm nay câu đó
**chỉ đúng nếu bạn là dev có quyền vào máy chạy benchmark**.

Phần khó đã xong (SDK, host, lane subprocess, conformance CLI, discovery
đọc manifest không import code). Phần thiếu là **đường vào**:

- không có endpoint nhận bundle, không có chỗ lưu, không có bước giải nén
  có kiểm;
- **catalogue chỉ có một nguồn** — danh sách thuật toán đọc thẳng từ một
  dict khai cứng trong mã, chưa có nguồn thứ hai cho plugin đã import;
- không có UI.

**Đổi chỗ nút bấm không giải quyết được.** Một manifest chỉ *khai* entry
point, nó không *chứa* code — nên import manifest cho một thuật toán chưa
cài chỉ cho ra trạng thái "đã đăng ký nhưng thiếu runtime".

### 2.2. Phát lại — mới xong một nửa

Đồng bộ theo **thời gian tuyệt đối** đã chạy. Đồng bộ theo **quãng đường
đi được** (để so hành vi tại cùng một vùng bản đồ) thì chưa: `TracePayload`
chưa mang tuyến tham chiếu để chiếu lên.

Đường lui đã chốt — chiếu lên tuyến dự phòng và **khai rõ chất lượng chiếu
bị giảm** — nhưng chưa làm. Cảnh báo bắt buộc đi kèm chế độ đó (*"cùng chỗ
≠ cùng tình huống"*: vật cản động đã ở chỗ khác vì hai robot tới nơi ở hai
thời điểm khác nhau) cũng chưa có.

### 2.3. Trợ lý hội thoại — không có trí nhớ

`/agent/chat` **không gửi lịch sử hội thoại**. Hỏi "còn candidate B thì
sao?" là model không biết B nào.

Đây là **quyết định thiết kế có lý do** (không có ngữ cảnh ẩn mà người đọc
không thấy được), nhưng cái giá của nó là hội thoại nhiều lượt không hoạt
động. Nếu bạn định đổi, đổi cả lý do.

---

## Hạng 3 — giới hạn kỹ thuật đã biết

Trích những mục hay cắn nhất; đầy đủ ở
[reference/KNOWN_LIMITATIONS.md](reference/KNOWN_LIMITATIONS.md).

- **Map phải có tường bao.** LiDAR coi ngoài map là "không phản xạ"
  (trả `max_range`), collision coi ngoài map là vật cản. Map không kín ⇒
  hai tầng bất đồng.
- **Origin xoay chưa hỗ trợ** — validator từ chối `origin.theta ≠ 0`.
- **Inflation bảo thủ** (`radius + √2·resolution`) có thể chặn hành lang
  hẹp vẫn đi được về mặt vật lý trên map resolution thô.
- **Penetration depth chỉ xấp xỉ** — đủ để phát hiện va chạm, **không**
  dùng cho physics response.
- **`clearance_to_grid` quét toàn bộ cell** — đủ nhanh cho map thử nghiệm;
  cần distance-field cache nếu map lớn.
- **Model PPO upload chưa chạy trong sandbox container** — hạn chế bảo mật
  quan trọng nhất của phần Model Registry.
- **Vài test frontend đang đỏ**, đòi những khoá dịch chưa từng tồn tại.
  Chưa dọn.
- **5 test đỏ ở `tests/test_host_parity_golden.py`** — đã xác nhận trên
  worktree sạch ở `HEAD` (`5 failed, 206 passed`), nên có sẵn từ trước.
  Nguyên nhân: lệch **1 đơn vị cuối** ở một giá trị số trong episode ghim
  (`66025511915` với `66025511916`) — khác biệt tái lập số học giữa máy ghi
  fixture và máy chạy. Test so **byte-identical** trên `json.dumps` cả
  episode, nên nó pin cả thứ không phải hành vi. Sửa bằng cách sinh lại
  fixture thì chỉ đẩy sang máy sau; sửa đúng là so theo dung sai cho
  trường số thực — nhưng đó là quyết định nới một cổng đang chặt.
- **Chưa có phép so nào giữa cách diễn đạt của template và của model.**
  Nguyên tắc đã chốt: template là chuẩn vĩnh viễn, model không thắng rõ
  thì không ship phần văn — nhưng phép so đó chưa chạy.

---

## Hạng 4 — nợ của chính tài liệu

Phần này mô tả **tài liệu**, không phải code. Đợt rà 2026-08-31 đã sửa phần
lớn; mục còn lại ghi ở đây để không ai phải phát hiện lại.

### 4.1. Đã sửa trong đợt rà 2026-08-31

| Nợ | Đã làm gì |
|---|---|
| `README.md` §9.1 nói `services/analyst_service/` chưa tồn tại — sai, nó có hơn 20 module và đã đo | Viết lại §9.1 theo hiện trạng, kèm số đo và ba món nợ thật |
| `README.md` §3.3 liệt kê `*+pure_pursuit` lẫn vào danh sách stack tranh thắng thua | Tách hai nhóm; nêu rõ `reference=True` nghĩa là **bỏ qua cảm biến** |
| `API_CONTRACT.md` không nhắc 84/137 endpoint đang sống, và ghi 13 endpoint đã deprecate như thể bình thường | Chuyển vào `archive/superseded/`, thay bằng [reference/api.md](reference/api.md) |
| Decision log D01–D15 bị chôn trong `architecture.md` đã lỗi thời, trong khi **code trích bằng ID** | Tách ra [reference/decision-log.md](reference/decision-log.md), kèm trạng thái từng quyết định |
| Bảng route `FRONTEND.md` liệt kê `/benchmarks`, `/leaderboard` đã bị gỡ | Viết lại theo `apps/web/src/app/` thật |
| `AI_CAPABILITIES.md` thiếu hẳn dòng AI Analyst | Thêm mục 5g kèm endpoint, test và số đo |
| `AGENT_AI.md` không nói rõ phạm vi, dễ tưởng đã bao gồm analyst | Khai phạm vi ở đầu file |
| `architecture_planner_selector.md` khẳng định `ARCHITECTURE.md` là template LangGraph + ChromaDB chưa điền | Sai từ 2026-08-23; viết lại khối chỉ dẫn |
| `TEST_REPORT.md` đọc như trạng thái hôm nay | Khai rõ là ảnh chụp có ngày, và hai test file nó nhắc đã không còn |
| ~50 file code/test và `CLAUDE.md`, `README.md`, `contracts/CONTRACTS.md` trỏ đường dẫn `docs/` cũ | Trỏ lại toàn bộ; `deployment.py` và test ghim nó sửa cùng lượt |

### 4.1b. Đã sửa trong đợt rà 2026-09-01 (phần AI)

| Nợ | Đã làm gì |
|---|---|
| `README.md` §3.7 chỉ khai **hai** lớp AI, trong khi có bốn mặt hiện ra cho người dùng | Viết lại thành bảng bốn mặt, mỗi mặt một cột trạng thái |
| §3.7 và `AI_CAPABILITIES.md` ghi **11** tool chỉ-đọc; `tools.py` có **12** | Sửa cả hai |
| Không chỗ nào trong README nói analyst **mặc định tắt** và `production` **bị từ chối trong build này** | Khai ở §3.7, §4.8 và §9.1 |
| §4.8 không nhắc panel *Từ paper*, dù nó đã nối vào API và có UI | Thêm mục riêng, kèm câu "chất lượng chưa ai đo" |
| §9.2 vẫn nói import plugin "chưa có đường vào" — sai từ 24-08 | Viết lại theo `routers/plugins.py`: 12 endpoint, hai chỗ hở thật còn lại |
| §9 nhảy từ 9.3 sang 9.6 | Đánh số lại 9.4, 9.5 |
| §5.5 không nói bản desktop **đã đóng gói `openai`**, cũng không nói `anthropic` chưa có đường vào từ UI | Bổ sung cả hai |

### 4.2. Còn lại

- **`docs/architecture_diagram.md` chưa từng tồn tại** nhưng từng được
  trích. Đã ghi chú tại chỗ; không có gì để khôi phục.
- **`../README.md` §6** còn dòng nháp *"Sẽ gộp vào đây khi bản nháp này
  được chốt"*, trỏ tới `README.old.md` vẫn nằm ở gốc repo.
- **`../JOURNAL.md` và `../WORKLOG.md`** ở gốc repo là **template cohort
  chưa điền** (`[Tên Team]`, `[YYYY-MM-DD]`).
- **`archive/gate-g1/README.md`** còn ô `[CẦN ĐIỀN: Tên nhóm]`.
- **26 file trong `journal/antongduy/` không phải `.md`** — script eval,
  JSON kết quả, mock HTML. Chúng là bằng chứng đi kèm note, không phải tài
  liệu đứng riêng.
- **`KNOWN_LIMITATIONS.md`: đã rà phần khẳng định phủ định (01-09),
  chưa rà phần số đo.** 54 câu dạng "chưa có / không hỗ trợ" đã được kiểm
  lại với code; bốn chỗ sai đã sửa tại chỗ và liệt ở đầu file (mục 48, 89,
  47, và ba mục neo vào trang leaderboard đã bị gỡ). Còn lại: mỗi mục trích
  một con số đo được thì con số đó chưa ai dò lại — và file vẫn giữ tiêu đề
  M1–M13, từ vựng đã chết từ đợt chuyển hướng 08-08.

---

## Nếu bạn tiếp nhận dự án — ba việc nên làm trước

Cả ba đều nằm ở Hạng 1: chúng chặn phần "vì sao", là lời hứa mà sản phẩm
chưa giữ trọn.

1. **Sửa `reference_analyst` crash.** Không có sàn model-free thì mọi con
   số của analyst đều thiếu đối chứng — không biết 0.56 là công của model
   hay của bộ guard tất định quanh nó.
2. **Chạy sweep dựng nốt 3/6 họ golden còn thiếu.** Đây là thứ chặn
   `OFFICIAL_GOLDEN_READY`, và cờ đó chặn mọi phép chấm chính thức cho tầng
   "vì sao".
3. **Duyệt 5 entry cơ sở tri thức đang `draft`.** Chưa entry nào được duyệt
   thì chưa claim nào được nâng mức bằng chứng — thang bốn mức đứng yên ở
   mức thấp nhất dù máy móc đã sẵn sàng.

Việc thứ tư, rẻ hơn nhiều và nên làm cùng lúc: **đưa một phép gọi model
thật vào CI** (§1.2), để lần sau chất lượng văn tụt thì có cái báo.

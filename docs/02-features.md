# Tính năng — cái gì chạy được, và bằng chứng ở đâu

> Mỗi mục ghi **trạng thái** và **chỗ kiểm lại**. Phần chưa chạy tốt nằm ở
> [03-gaps.md](03-gaps.md), không nằm ở đây.

Ký hiệu trạng thái: ✅ chạy thật, đã đo · 🟡 chạy được, còn khuyết ·
🔬 đã đo tay, chưa có trong CI

---

## Ba tính năng nổi bật nhất

Nếu chỉ có thời gian nhớ ba thứ, nhớ ba thứ này — chúng là chỗ sản phẩm
khác với một bộ script benchmark.

### 1. Phép so ghép cặp có checksum điều kiện ✅

Mọi candidate chạy trên **cùng một tập `episode_context`**: cùng seed,
cùng vị trí vật cản động ở cùng thời điểm, cùng nhiễu cảm biến, cùng cấu
hình LiDAR. Hiệu số tính **theo từng cặp**, loại bỏ nhiễu do "hôm ấy map
dễ hơn".

Và mỗi điều kiện mang một **checksum**, để câu "hai bên chạy cùng điều
kiện" là thứ kiểm lại được chứ không phải lời người chạy benchmark tự
khai.

**Stack tranh được thắng thua** (`production_eligible`): `astar+dwa` ·
`astar+dwa_predictive` · `rrtstar+dwa` · `rrtstar+dwa_predictive` ·
`astar+ppo`.

**Không tranh được** — `astar+pure_pursuit` và `rrtstar+pure_pursuit` có
trong registry nhưng mang `reference=True`: chúng **bỏ qua cảm biến**, tồn
tại để chạy thử đường ống, và mô tả trong code nói thẳng là *"must not be
used to draw benchmark conclusions"*. Trích danh sách stack ở đâu thì trích
kèm cờ này — xem [reference/decision-log.md](reference/decision-log.md) D12.

### 2. Sáu cổng khả thi tách hẳn khỏi điểm số ✅

Cổng chạy **trước** mọi phép chấm điểm. **Một cổng không phải một điểm
số**: chấm điểm trả lời "cái nào tốt hơn", cổng trả lời "cái này có được
xét đến không". **Một stack va chạm không được cứu bằng việc nó nhanh.**

Bốn tính chất đáng nhớ:

- **Cả sáu cổng luôn chạy.** Không dừng ở cổng hỏng đầu tiên — "bị loại ở
  G2" mà không biết G4 có hỏng không là chẩn đoán không hành động được.
- **Không va chạm là một chặn trên, không phải chứng chỉ.** Quan sát 0 va
  chạm trong N lượt chỉ chặn xác suất ở mức ~3/N với độ tin cậy 95%, và
  **chỉ dưới phân phối kịch bản đã mô phỏng**. G2 vì thế đòi thêm
  `N ≥ N_min`, và câu chặn trên đi kèm mọi lần con số đó được nhắc.
- **Sàng lọc trên host chỉ chứng minh một chiều.** Máy chạy benchmark
  nhanh hơn bo mạch đích và chạy Python chứ không phải C++/ROS2. G4/G5
  **hỏng** thì chắc chắn hỏng trên đích; G4/G5 **đạt** thì không chứng
  minh được gì — và mọi kết quả G4 mang theo câu cảnh báo đó nguyên văn.
- **Ngôn ngữ cấm có hàm kiểm và test CI canh.** "An toàn", "TCO" không
  bao giờ xuất hiện cạnh một con số nền tảng này sinh ra.

### 3. AI Analyst theo episode — nói **vì sao**, không chỉ **ai thắng** 🔬

Đây là công việc mới nhất và là thứ khó đo nhất trong sản phẩm.

Analyst đọc bằng chứng của **một episode đang chọn** và giải thích cơ chế
tạo ra chênh lệch — khe hành lang hẹp hơn footprint cộng inflation, ngân
sách sampling cắt quá thấp, controller dao động trong khe hẹp.

Đã chạy thật, chấm mù, trên cụm holdout:

| | |
|---|---|
| Mẫu | 30 episode × 3 lượt = **90 lượt**, cụm `sudden_stop_custom_v2_full_stack_selection` |
| Model | `o4-mini`, chi phí thật ước ~$0.70 |
| Chấm | mù arm, 90/90 lượt + 144/144 block, rubric r0.2.0 |
| **Giải thích được outcome** (đa số ≥2/3 lượt) | **10/18 = 0.56**, so với 2/18 = 0.11 ở arm đầu |
| Sai sự thật | 1 câu / 90 lượt |
| Vi phạm ràng buộc cứng | **0** |
| Kiểm nhất quán | 0 mâu thuẫn trên 6 phép, gồm 2 phép chéo cột |

Bằng chứng:
[journal/antongduy/reports/2026-08-31/tongduyan_hieu-nang-that-va-tuong-guard-v2.md](journal/antongduy/reports/2026-08-31/tongduyan_hieu-nang-that-va-tuong-guard-v2.md).
Code: `services/analyst_service/planbench_analyst/`. Wired vào API
(`routers/agent.py`, `routers/decisions.py`, có quota theo ngày) và web
(`components/DockAnalyst.tsx`).

> Con số 0.56 đi kèm mẫu số 18 và điều kiện đọc "đa số ≥2/3 lượt".
> **Trích một con số thì phải trích cả cách đọc.** Có một amendment có
> ngày cho mẫu số trong `preregistration_episode.py::holdout_denominator`.

---

## Phần còn lại, theo vòng đời một quyết định

### Khai một thế giới để đo — **Triển khai** ✅

Một *deployment* (task profile) là toàn bộ những gì cố định trong phép so:
map, robot (kích thước, động học, chu kỳ điều khiển), cảm biến và nhiễu
của nó, các mission, vật cản động, ngưỡng khả thi, bộ trọng số mục tiêu.

Mọi ngưỡng cổng đọc từ đây — **không một hằng số nào nằm trong code**.

### Bản đồ và kịch bản ✅

Map editor Canvas 2D, hoặc import từ thư viện scenario dựng sẵn (hành lang
hẹp, cửa ra vào, ngã tư, kho có vật cản động). Vật cản động khai được
đường đi và thời điểm. Map có ghim phiên bản và lộ khôi phục.

### Thử trước khi tốn hàng giờ — **Sân thử** ✅

Chạy một episode đơn, xem quỹ đạo, clearance, latency planner theo thời
gian thực. Đây là chỗ phát hiện map thiếu tường bao hay mission bất khả
thi, **trước khi** phóng một phép so 30 episode.

### Thẻ quyết định ✅

Khi ≥2 candidate qua cổng: ΔU ghép cặp + CI 95% bootstrap, phân rã theo
từng mục tiêu, và số episode đứng sau. **CI vắt qua 0 thì thẻ nói thẳng là
run này không chứng minh được chênh lệch nó báo.**

Kèm theo: bảng so sánh từng metric, **Nên triển khai cái nào** theo ba
tình huống (ưu tiên chất lượng / real-time / ít bộ nhớ), và danh sách
candidate bị loại **kèm cổng đã loại chúng**.

### Tầng giải thích 🟡

- **Waterfall ΔU** — chênh lệch tổng phân rã thành từng mục tiêu, mỗi
  thanh có CI riêng; thanh vắt qua 0 hiển thị mờ. ✅
- **Phát lại hai canvas** — cùng một episode, hai stack, một playhead
  chung theo **thời gian tuyệt đối**. ✅ (đồng bộ theo **quãng đường** thì
  chưa — xem [03-gaps.md](03-gaps.md))
- **Exemplar** — episode điển hình / thắng đậm / thua đậm / nặng về an
  toàn nhất, chọn theo **công thức cố định**, không phải thứ tự tình cờ. ✅
- **Detector** — `detour`, `stuck_cluster`, `replan_storm`, `oscillation`,
  `latency_spike`, `near_miss_cluster`. Hàm thuần của trace, test như
  metric. ✅
- **Thang bằng chứng bốn mức** (`observed` → `associated` →
  `mechanism_verified` → `intervention_supported`) và **không có mức thứ
  năm cho "không biết"**: thiếu bằng chứng nghĩa là **không có claim**,
  không phải một claim yếu. ✅ contract, 🟡 dữ liệu (xem gaps)

### Lớp AI ngoài analyst ✅

12 điểm can thiệp, mỗi cái có bộ luật tất định làm nền và LLM là lớp phủ
tuỳ chọn (`?use_model=true`). Bản đồ đầy đủ kèm endpoint và test:
[reference/AI_CAPABILITIES.md](reference/AI_CAPABILITIES.md).

Đáng chú ý: đọc paper → bản nháp candidate (mỗi tham số kèm **câu nguồn**);
12 luật preflight chặn lỗi cấu hình trước khi tốn mô phỏng; 15 luật phản
biện trước khi ký; 18 luật rào chắn trước khi viết báo cáo.

### Cắm thuật toán của bạn vào 🟡

Phần khó **đã xong**: SDK (`packages/plugin_sdk`), algorithm host, lane
subprocess có deadline thật và kill được khi treo, CLI kiểm tính tuân thủ,
discovery đọc manifest **không import code**. MPPI và VFH+ đã import thật
dưới dạng plugin.

Thiếu **đường vào qua giao diện** — xem [03-gaps.md](03-gaps.md) §2.

### Duyệt hai người ✅

Gửi → Nhận → Đọc → Ký. "Đọc" gắn vào **lần nhận**, không gắn vào run: ai
nhận lại từ người khác thì phải tự đọc lại. `strict` (mặc định) không cho
ai ký run của chính mình.

### Mang kết quả ra ngoài ✅

Xuất Markdown và Excel, hai thứ tiếng, mở đầu bằng một trang trả lời "run
này ra cái gì" mà không bắt người đọc ghép từ ba tab. Gửi email. Trace và
artifact lưu ngoài database **kèm checksum**, để một lượt chạy được **phát
lại** chứ không chỉ được thuật lại.

### Desktop app Windows ✅

Đóng gói từ cùng cây mã, hiện `0.1.16`. Installer một file, tự cập nhật
qua CDN manifest. Cổng release là smoke gate chạy **trên interpreter đã
đóng gói** — nó bắt được thứ pytest không thấy.
Runbook: [reference/DESKTOP-RELEASE.md](reference/DESKTOP-RELEASE.md).

---

## Bằng chứng test

| Nguồn | Nội dung |
|---|---|
| [reference/TEST_REPORT.md](reference/TEST_REPORT.md) | Output thật chép nguyên từ terminal |
| [reference/EVAL_EVIDENCE.md](reference/EVAL_EVIDENCE.md) | Năm tình huống chạy thật trên tầng phản biện, provider thật |
| `tests/` | pytest — hơn 1000 test |

> Test ở repo này chủ yếu **đọc source và pin quyết định**, kèm văn xuôi
> giải thích *vì sao* quyết định đó tồn tại. Giữ nguyên lối đó khi thêm test.

Xem tiếp: [03-gaps.md](03-gaps.md)

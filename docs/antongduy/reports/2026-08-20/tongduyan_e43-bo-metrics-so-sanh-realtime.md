# E4.3 — bộ metrics so sánh hai thuật toán realtime trong một episode

**Ngày:** 2026-08-20 · **Nhánh:** `tongduyan_3`

**Trạng thái:** xong cả ba tầng (engine, API, UI), **chưa commit**. Full suite chưa
chạy — chỉ chạy phần vừa sửa, theo đúng yêu cầu của An.

An chốt: **bỏ trục comfort**, **giữ composite**.

---

## 1. Vấn đề thiết kế: một câu hỏi, hai đồng hồ

Câu hỏi người xem có khi kéo thanh replay là *"ngay lúc này bên nào tốt hơn?"*. Nhưng
tại **cùng một thời điểm**, hai robot đang ở **hai chỗ khác nhau** trên nhiệm vụ. Nên
"so sánh tại thời điểm t" thực ra là **hai câu hỏi khác nhau đội chung một nhãn**:

| Đồng hồ | Trả lời câu gì | Metrics |
|---|---|---|
| **Cùng thời gian** | ai đang **đi trước** | `progress_fraction`, `progress_rate`, `compute_budget`, `replans` |
| **Cùng tiến độ** | ai làm **cùng khối lượng việc** tốt hơn | `elapsed_s`, `safety_margin`, `exposure_s`, `path_efficiency` |

So `min_clearance` tại **cùng thời gian** là so hai đoạn map khác nhau — con số ra
được không nói về thuật toán nào cả. Vì vậy **mỗi metric khai báo nó thuộc đồng hồ
nào**, và hai đồng hồ **không bao giờ trộn trong một hàng**. Hằng số này nằm ở cả hai
tầng: `TIME_SYNC_METRICS`/`PROGRESS_SYNC_METRICS` (Python) và
`TIME_CLOCK`/`PROGRESS_CLOCK` (TS).

---

## 2. Tám metric, và vì sao chọn đúng tám cái đó

Ba ràng buộc An đặt ra: **dùng chung schema giữa các episode**, **thuật toán nào cũng
dùng được**, **thể hiện được hiệu năng khi gặp task**.

Hệ quả trực tiếp:

- **Không đọc counter riêng của planner.** A-star nở node, RRT-star mọc cây, policy
  học được thì chẳng có cả hai. Một cột chỉ một bên điền được là một cột **đọc thành
  số 0 cho các bên còn lại**. Compute đo bằng **latency so với `T_cycle`** — thứ mọi
  stack đều phải trả. Có test cấm các tên `expanded_nodes`, `tree_size`, `samples`,
  `iterations` xuất hiện trong schema.
- **Mọi đại lượng đều vô thứ nguyên hoặc chuẩn hoá theo thứ deployment tự khai** —
  bán kính robot, `T_cycle`, `clearance_warning_m`, chiều dài reference. Cùng một
  hàng đọc giống nhau ở mọi episode.

Vài chi tiết đáng nói:

| Metric | Điểm dễ làm sai |
|---|---|
| `safety_margin` | **min tích luỹ**, không phải giá trị hiện tại. An toàn là trường hợp xấu nhất; một con số hồi phục lại sau pha suýt va là con số **quên mất pha suýt va**. |
| `exposure_s` | tính bằng **giây**, không phải số mẫu. Vòng điều khiển chạy nhanh gấp đôi sẽ trông như phơi nhiễm gấp đôi. |
| `progress_rate` | **khác tốc độ**. Robot dao động tại chỗ ở full speed thì có tốc độ mà không có tiến độ — chênh lệch đó chính là điểm cần thấy. |
| `path_efficiency` | tiến độ **trên tuyến reference** chia quãng đường **đã chạy**. Xem mục 4 — đây là chỗ bản nháp đầu tiên suýt hỏng. |

---

## 3. Composite: có, nhưng không được phép đọc thành ΔU

`partial_advantage` = đánh đổi an toàn–hiệu quả của chính deployment, trên **phần đã
diễn ra**, dạng `A − B`.

**Không tự chế điểm số.** Nó gọi thẳng `_safety()` và `_efficiency()` của
`planbench_decision.objectives` — đường cong mục tiêu của chính nền tảng, phân giải
theo anchor của chính deployment. Một đường tính điểm thứ hai kiểu "gần đúng `U_S`"
chính là **parallel source** mà HĐ-5 cấm ở mọi chỗ khác, và nó sẽ lệch với card ngay
lần đầu ai đó chỉnh anchor.

**Chỉ hai trong bốn mục tiêu.** `U_R` là *có tới đích không* — nửa chừng episode thì
nó **không có giá trị**; một ΔU cục bộ sẽ bịa ra giá trị đó, và nó còn **đảo chiều**:
bên đang thua ở giây thứ mười vẫn thắng cả episode. Trọng số `w_s`/`w_e` được
**chuẩn hoá lại trên hai trục** — để nguyên giá trị bốn-trục sẽ cho ra con số không
bao giờ chạm được 1, trông như mọi candidate đều kém.

**Nó *bám theo* giá trị thật chứ không *hội tụ* về.** Docstring bản đầu tôi viết là
"converges" — sai, và tôi đã sửa. Lý do: metric episode đo hiệu quả theo `L_ref`
(tuyến ngắn nhất map cho phép), còn cái này đo theo **reference line của replay**.
Hai đường khác nhau thì hai tỉ số khác nhau. Có test ghim đúng sự chênh lệch đó.

Vì vậy: **hết episode, panel giao lại cho `episode_decision_utility` đã lưu sẵn
trong report** — con số thật, đủ bốn trục. Composite không bao giờ được đứng một
mình làm câu trả lời.

---

## 4. Lỗi suýt ship: `path_efficiency` luôn bằng 1.0

Bản nháp nối API dùng **quãng đường đã chạy tích luỹ** làm `progress_m` (chỗ giữ tạm,
vì tưởng projection đã nằm sẵn trong view).

`path_efficiency` = tiến độ / quãng đường đã chạy. Nếu tiến độ **chính là** quãng
đường đã chạy thì tỉ số này **bằng đúng 1.0 cho mọi candidate, mọi episode, mãi mãi**.
Nó render bình thường, đọc thì hợp lý, và **không đo gì cả**.

Đã sửa: `_slice_for` gọi `project(track, reference)` với **đúng đường reference mà
view đã công bố** — cùng một cây thước với thang tiến độ ở biểu đồ ngay trên nó. Hai
cây thước trên một màn hình là cách một bảng so sánh bắt đầu mâu thuẫn với biểu đồ
phía trên.

Test ghim lại: robot đi vòng, kết thúc ở **6 m** trên reference sau khi đã chạy
**12 m**, cho `path_efficiency = 0.5`. Bản dùng quãng đường đã chạy sẽ trả 1.0.

---

## 5. Thêm: reference line giờ đã là **kế hoạch thật**

Phụ phẩm của E4.5. `build_replay_sync_view` luôn có tham số `planned_path` nhưng chưa
ai truyền được — plan bị vứt đi sau khi chạy. Sidecar E4.5 ghi lại polyline của mọi
lần planning, endpoint trace phục vụ chúng, nên giờ:

```
projection_quality: degraded_candidate_path  ->  reference_plan
```

Lấy **attempt đầu tiên**, không phải attempt cuối: arc length phải đo dọc **một
đường duy nhất** cho cả episode, còn tuyến sau replan chỉ mô tả phần sau nó. Run cũ
(trước E4.5) vẫn fallback, và view vẫn **nói rõ nó đã fallback sang thấu kính nào**.

---

## 6. Từ chối thay vì đọc nhầm hàng

- **`None`, không phải `[]`**, khi không dựng được so sánh. Anchor không phân giải
  được thì không có đường cong mục tiêu. Danh sách rỗng sẽ đọc thành *"hai bên y hệt
  nhau"* — ngược hẳn với *"không tính được"*. UI phân biệt hai trạng thái này.
- **Cột lệch độ dài thì từ chối.** Payload đọc theo cột bằng `.get(name, [])`, nên
  file trace thiếu một cột sẽ tới đây thành list rỗng. Đọc `clearance_m` tại chỉ số
  hàng lấy từ `t` khi đó là `IndexError` — hoặc tệ hơn, với cột chỉ ngắn hơn một
  chút, là **đọc đúng cú pháp một thời điểm khác của episode**. Validator trên
  `TraceSlice` chặn tại schema.

---

## 7. UI

Nằm **trong** panel progress-sync, ngay dưới thanh trượt — vì nó **đọc chính thanh
trượt đó**. Vị trí kéo trên panel này đã là mét tiến độ, tức đúng trục của thang; đặt
chỗ khác thì phải có bản sao thứ hai của vị trí, và hai vị trí là hai thứ có thể lệch
nhau.

| File | Việc |
|---|---|
| `lib/running.ts` | **phần quyết định**: hướng tốt/xấu từng metric, hai đồng hồ, chọn nấc thang, caveat |
| `components/RunningComparison.tsx` | phần vẽ — hai bảng, không phải một |
| `globals.css`, i18n en/vi | style + 20 khoá |

**Vì sao tách `lib/running.ts`.** Cùng lý do như `lib/evidence.ts`: repo không có
jsdom. Và thứ đáng sai nhất ở đây **vô hình trong ảnh chụp màn hình** — tô đậm "số
lớn hơn" là đúng cho `safety_margin` và **sai cho `elapsed_s`**; cả hai ô render y
hệt nhau, còn bảng thì đang nói với người đọc rằng run chậm hơn là run an toàn hơn.

Thêm: `leader()` có **ngưỡng hoà theo tỉ lệ**. Không có nó thì hàng nào cũng có kẻ
thắng, kể cả hàng lệch nhau ở chữ số thập phân thứ sáu — và một bảng **không bao giờ
hoà** dạy người đọc bỏ qua phần tô màu.

---

## 8. Test

| File | Số test |
|---|---|
| `tests/test_explanation_running_metrics.py` | 17 |
| `tests/api/test_api_running_comparison.py` | 10 |
| `apps/web/src/lib/__tests__/running.test.ts` | 17 |
| `apps/web/src/app/__tests__/running-comparison.test.tsx` | 30 |

Chạy lại các suite liên quan: **78 passed** (Python: running metrics, replay sync,
replay view, API explanation, obstacle tracks), **112 passed** (web). `ruff` sạch,
`tsc --noEmit` sạch.

---

## 9. Còn lại

- **Chưa commit** — chờ lệnh An.
- Chưa xác minh trên một run thật đi hết đường: cần một sweep có đủ hai candidate
  qua cổng trên cùng episode.
- Full suite chưa chạy.

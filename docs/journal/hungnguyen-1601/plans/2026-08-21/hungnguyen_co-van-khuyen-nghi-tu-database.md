# Plan — Cố vấn khuyến nghị từ database (R0–R6): "dựa trên các kết quả đã chạy, dự án tôi nên dùng thuật toán nào"

**Ngày:** 2026-08-21 · **Trạng thái:** bản 1, chờ duyệt
**Thay thế:** `hungnguyen_shortlist-truoc-khi-chay.md` (cùng ngày). Plan đó không
chết — nó trở thành **nhánh Bậc 3** của plan này (xem §2). Hạ tầng S2 (đặc trưng
môi trường) dùng chung nguyên vẹn.
**Trọng tâm do user chốt 21-08:** không phải đọc paper. AI phải **đọc dữ liệu
trong database** — kết quả các lần chạy simulation — rồi **khuyên user nên chọn
thuật toán nào cho dự án của họ**.

---

## 0. Một câu

Mọi bằng chứng đã nằm trong `decision_runs`; mọi phán quyết từng run đã có trong
card và bảng cổng. Thứ **chưa tồn tại** là tầng trả lời câu người dùng thật sự
hỏi: *"cho dự án CỦA TÔI thì sao?"* — tức là tầng **tìm bằng chứng áp được, chuyển
giao nó có điều kiện, và nói thật khi không có gì để chuyển giao**.

## 1. Giữ hiến pháp, đổi trọng tâm

"AI kết luận nên chọn thuật toán nào" **không** có nghĩa LLM quyết. Phán quyết
từng run vẫn của tầng thống kê (card, gates) — AI **không mở lại phiên toà đã
xử**. Việc mới của AI là ba việc chưa ai làm:

1. **Truy hồi** — trong các run đã lưu, run nào nói được điều gì về deployment
   này;
2. **Chuyển giao** — kết luận của run đó áp sang dự án của user được đến đâu,
   mất gì trên đường đi;
3. **Nói thật** — khi bằng chứng không phủ, trả về "chưa đo" kèm đúng phép so
   cần chạy, không bịa.

Sàn là luật tất định (mã `RC_*`, kiểu `Advice`, `keep_resolvable`); LLM xếp hạng
và kể chuyện qua `?use_model=true`, đúng khuôn `advice`/`outcome`/`critique`.

## 2. Ba bậc bằng chứng — xương sống của thiết kế

Mọi câu trả lời của cố vấn **bắt buộc khai nó đứng ở bậc nào**:

| Bậc | Tình huống | Cố vấn làm gì | Độ mạnh |
|---|---|---|---|
| **1** | Đã có run trên **chính profile này** | Dịch card + gate table thành khuyến nghị cho người không chuyên; tổng hợp nếu nhiều run | Mạnh nhất — bằng chứng bậc nhất |
| **2** | Chưa có run trên profile này, nhưng có run trên **lớp môi trường tương đương** | Chuyển giao có điều kiện: ai qua cổng, metric nào phân thắng bại, xu hướng nghiêng về đâu — kèm mọi caveat chuyển giao | Trung bình — phải khai từng khác biệt |
| **3** | Không có gì so sánh được | **Không khuyến nghị.** Trả về shortlist (plan S cũ) + spec phép so nên chạy để lần sau có Bậc 1 | Refusal có ích |

Bậc 2 là năng lực mới thật sự. Bậc 1 là dịch thuật. Bậc 3 là plan shortlist cũ
tìm được chỗ đứng đúng: **nó là câu trả lời khi database chưa nói được gì**.

Từ chối kiểu Bậc 3 trả về như một giá trị, không phải lỗi — cùng triết lý
refusal của mission parser M8.

## 3. Đã kiểm trên dữ liệu thật — ba phát hiện định hình plan

Kiểm trực tiếp `planbench.db` (2 decision run, 1 có card) ngày 21-08:

**(a) Report lưu metric theo TỪNG episode, inline.** Mỗi candidate trong report
mang 30 episode, mỗi episode có `success`, `min_clearance`, `travel_time_s`,
`p99_latency_ms`, `collision_count`, `episode_decision_utility`,
`episode_context_id`. Hệ quả lớn: **"chấm lại không cần mô phỏng lại"** là khả
thi từ DB thuần — xem §6.

**(b) Report KHÔNG lưu đặc trưng bản đồ.** `case_packet.packet.task.route =
None`; không có `narrowest_passage`, không `obstacle_density`. Nhưng
`decision_runs.task_profile_id` → `task_profiles` → map path, và file map còn
trên đĩa (`maps/open_hall.pgm` ✅). Hệ quả: `environment_class` cho run cũ **tính
lại được** bằng đúng máy S2 (tuyến tham chiếu Dijkstra → `measure_route`), không
cần migration dữ liệu.

**(c) Hai run.** Mọi con đường Bậc 1/Bậc 2 đều đói dữ liệu hôm nay. Cố vấn ra
đời sẽ trả lời Bậc 3 là chủ yếu — **đó là hành vi đúng**, và là máy tạo động lực
sinh dữ liệu: mỗi phép so nó đề nghị chạy là một run mới cho database.

## 4. Khả thi trên profile CỦA USER đứng trước mọi lịch sử

Một stack thắng ở nơi khác nhưng **không chạy được trên dự án này** thì không
bao giờ được khuyên. Trước khi nhìn vào lịch sử, cố vấn chạy L1 của plan S trên
chính profile user — tái dùng `preflight` trên draft một-phần-tử, không viết lại
luật:

- observation thiếu (`PF_OBSERVATION_NOT_AVAILABLE`) → loại khỏi mọi khuyến nghị;
- `astar+ppo` chưa chọn model (`PF_MODEL_NOT_CHOSEN`) → không được khuyên, dù
  từng thắng ở run nào;
- control period không khớp (`PF_CONTROL_RATE_SLOWER_THAN_DEPLOYMENT`) → loại;
- `production_eligible=False` (`withdrawn`/`reference`) → loại, in nguyên văn lý
  do rút từ registry.

Đây là chỗ plan S sáp nhập vào: **L1 là cổng vào chung của cả ba bậc.**

## 5. Luật tổng hợp `RC_*` — sàn tất định của Bậc 1 và 2

| Mã | Nói gì | Neo |
|---|---|---|
| `RC_CARD_ON_THIS_PROFILE` | Run trên chính profile này đã có card: người thắng, biên, nhãn CLEAR/NEAR-EQUIVALENT | `decision_runs.card` |
| `RC_CONSENSUS_ACROSS_RUNS` | Mọi run so sánh được cùng chỉ một người thắng | danh sách run id |
| `RC_CONFLICT_BETWEEN_RUNS` | Hai run khớp lớp môi trường nhưng khác người thắng → nêu cả hai + khác biệt điều kiện, **không tự phân xử** | hai run id + diff điều kiện |
| `RC_ELIMINATION_TRANSFERS` | Run không card vẫn là bằng chứng: candidate X rớt G-nào trên môi trường tương đương, và ngưỡng cổng của user còn ngặt hơn → cảnh báo trước | gate table của run cũ |
| `RC_DIFFERENT_ROBOT_CLASS` | Run khớp môi trường nhưng robot khác hẳn (bán kính, vận tốc, control period) → hạ bậc bằng chứng, khai rõ | hai robot spec |
| `RC_STALE_VERSION` | Run từ `contracts_version`/`anchor_config_version` khác → disclosure, không lặng lẽ gộp | manifest |
| `RC_NEAR_EQUIVALENT_HONESTY` | Card nói NEAR-EQUIVALENT → khuyến nghị phải nói "hai ứng viên không phân biệt được", cấm dịch thành "X tốt hơn" | `card.status` |
| `RC_NO_COMPARABLE_HISTORY` | Không đủ run trong khoá tương đương → rơi về Bậc 3 | đếm run |
| `RC_NEVER_MEASURED_HERE` | Ứng viên khả thi nhưng chưa từng được đo trên lớp môi trường này → lý do *nên đưa vào phép so*, không phải lý do bỏ | sổ phủ sóng |

Khoá tương đương giữ nguyên từ plan S §4.3: `(contracts_version,
anchor_config_version, environment_class)`, `environment_class` do **code suy từ
số đo**, ngưỡng ≥K run khai trong config, mọi lần dùng in ra *"dựa trên N run"*.

## 6. Bậc 2 nâng cao — chấm lại không mô phỏng lại (R5)

Vấn đề sâu nhất của chuyển giao: **ΔU của run cũ tính theo trọng số objectives và
anchor của deployment CŨ.** Deployment của user ưu tiên khác (an toàn nặng hơn,
chi phí nhẹ hơn) thì người thắng có thể đổi — chuyển giao nguyên con số U là sai
về nguyên tắc.

Phát hiện §3(a) mở đường thoát: report đã lưu metric thô theo từng episode. Vậy
tầng decision **chấm lại được** toàn bộ chuỗi objectives → utility → paired
bootstrap ΔU với **trọng số + anchor + ngưỡng cổng của user**, trên episode đã
chạy, ghép cặp theo `episode_context_id` — không tốn một episode mô phỏng nào.

Cái được: trả lời đúng câu "với *ưu tiên của tôi*, dữ liệu cũ nói gì".
Cái không được, phải khai: **map vẫn là map cũ** — khác biệt môi trường vẫn nằm
ở `environment_class` và không chấm lại mà xoá được. Kết quả chấm lại là bằng
chứng Bậc 2, không bao giờ được trình bày như Bậc 1.

R5 là phase riêng vì đứng một mình được: Bậc 2 mức cơ bản (cổng + hướng metric)
ship trước, chấm lại ship sau.

## 7. Bề mặt: một endpoint + một tool chat

- **`GET /task-profiles/{id}/recommendation[?use_model=true]`** — trả
  `AdviceListResource` cùng khuôn các endpoint advice hiện có, thêm trường
  `evidence_tier: 1|2|3` và `runs_considered[]`. 200 kể cả khi Bậc 3; không bao
  giờ 4xx trên một finding.
- **Tool chat `get_recommendation`** (`Effect.READ`, tool thứ 11) — để câu *"dự
  án tôi nên dùng thuật toán nào?"* hỏi được bằng tiếng người qua `/agent/chat`,
  chạy đúng sàn luật đó, không đường tắt qua LLM.
- Panel trên trang deployment, render bằng component Advice sẵn có.

Ba điều cấm, thi hành bằng cấu trúc như cũ: không tạo run (`run_comparison` vẫn
trong `FORBIDDEN_CAPABILITIES`), không tuyên bố an toàn (`declare_safe`), không
số nào từ LLM (mọi số đi qua `field_path` giải được).

## 8. Đo chất lượng — flip rate thay cho recall

Metric tự nhiên và tự nuôi: mỗi lần user nhận khuyến nghị Bậc 2 rồi chạy phép so
xác nhận trên chính profile của họ (điều cố vấn luôn đề nghị), ta có một điểm dữ
liệu: **khuyến nghị đứng vững hay bị lật**. `flip_rate = số lần lật / số lần xác
nhận`. Không cần dựng golden set riêng — database tự tích luỹ nó.

Cho tới khi có đủ điểm: mọi output mang nhãn *"đề xuất từ luật, chưa hiệu
chuẩn"* — trung thực như plan S đã cam kết.

## 9. Phase

| # | Nội dung | Ước lượng |
|---|---|---|
| **R0** | `environment_class` từ map + mission (nguyên S2: tuyến tham chiếu → `measure_route`; phơi polyline từ `reference_path` không đổi chữ ký cũ; bắt `ReferencePathError` → `unknown`) | 1–1,5 ngày |
| **R1** | Tầng truy hồi: run so sánh được theo khoá tương đương, phân bậc bằng chứng, L1 khả thi trên profile user (gọi `preflight`) | 1 ngày |
| **R2** | Sàn luật `RC_*` (9 mã) — module core thuần, nhận dict, không chạm DB trực tiếp (khuôn `self_check`/`critique`) | 1–1,5 ngày |
| **R3** | Endpoint + panel + `evidence_tier` | 1 ngày |
| **R4** | Lớp LLM (`use_model`) + tool chat `get_recommendation` | 1 ngày |
| **R5** | Chấm lại không mô phỏng lại (trọng số/anchor của user trên episode đã lưu) | 1,5–2 ngày |
| **R6** | Nhánh Bậc 3 = shortlist S1+S3 (sáu luật L2 + sổ phủ sóng) | 1–1,5 ngày |

R0–R4: **~5–6 ngày kỹ thuật**; cộng R5+R6: **~8–9,5 ngày**. Hệ số lịch ×2 của An
→ **3–4 tuần lịch** trọn gói. Thứ tự R5/R6 đảo được; R6 có thể ship trước nếu
muốn có sớm câu trả lời cho deployment mới tinh.

## 10. Không làm

- Không mở lại phán quyết một run — card là card.
- Không approve, không chạy phép so, không tuyên bố an toàn, không sửa dữ liệu.
- Không gộp run xuyên khoá tương đương mà không khai.
- Không thay phép so trên chính profile user — mọi khuyến nghị Bậc 2 kết bằng
  "và đây là phép so xác nhận nên chạy".

## 11. Rủi ro

| Rủi ro | Mức | Xử |
|---|---|---|
| Chuyển giao sai: hai profile cùng lớp môi trường vẫn khác ưu tiên → winner đổi | **Cao** | Bậc khai bắt buộc; R5 chấm lại theo trọng số user; luôn đề nghị phép so xác nhận |
| DB nghèo → cố vấn "vô dụng" ở mắt user đầu tiên | Cao | Bậc 3 phải hữu ích thật (shortlist + spec chạy được ngay); flip-rate tự tích luỹ |
| `environment_class` thô gộp nhầm hai thế giới | Trung bình | Kế thừa nguyên ba luật plan S: khai công khai, ≥K run, in N mỗi lần dùng |
| LLM dịch NEAR-EQUIVALENT thành "X tốt hơn" | Trung bình | `RC_NEAR_EQUIVALENT_HONESTY` là sàn; LLM không xoá được sàn |
| Map file của run cũ bị xoá → không tính lại được environment_class | Thấp | Refusal có tên: run đó rơi khỏi tập so sánh, nói rõ vì sao |

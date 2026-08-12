# Luồng mới tự đứng được

**Ngày:** 2026-08-12 · **Pha:** 7 đợt 2 · **Xác minh:** chạy thật trên server, không phải chỉ test

---

## 1. Vòng đời đã khép

```
/deployments  nộp task profile (nơi khai nhiễu)
     ↓
/decisions    xếp hàng phép so  →  theo dõi tiến độ  →  huỷ nếu cần
     ↓
/decisions/[id]  bảng cổng → Decision Card → đọc → duyệt → tải approved_config.yaml
```

Trước lượt này, luồng mới **không tạo được gì từ UI** — chỉ đọc, và dữ liệu duy nhất là 6 run
nhập từ đĩa.

## 2. Chỗ khó: `POST /decisions` chạy đồng bộ theo thiết kế

Docstring của chính nó nói rõ vì sao, và nói luôn điều kiện để đổi: *"Moving this behind the
queue is a deliberate change with its own cancellation story, not a default."*

Nên không sửa endpoint cũ. Thêm `POST /decisions/jobs` bên cạnh:

| | đồng bộ `POST /decisions` | xếp hàng `POST /decisions/jobs` |
|---|---|---|
| trả về | 201 + run đầy đủ | **202** + job để theo dõi |
| dùng khi | fixture 6 episode, xong trước khi thanh tiến độ kịp hiện | kho 300 episode, vài giờ |
| ai chờ | request HTTP | không ai |

**202 chứ không phải 201**: chưa có gì được tạo. Run xuất hiện trong `/decisions` khi quét xong,
và 201 kèm job id sẽ đặt tên cho một tài nguyên không tồn tại.

### Hàng đợi giữ **đúng một** job, và đó là ràng buộc hợp đồng

HĐ-7.4 cấm hai run đánh giá chạy đồng thời trên một máy: cả hai ghim cùng hai nhân, mỗi cái thành
tải nền của cái kia, và G4 — đọc độ trễ theo đồng hồ tường — sẽ đo một cái máy không tồn tại. Cùng
một stack đã đo được **59,30 ms không ghim so với 16,10 ms khi ghim 2 nhân**.

Nên `JobQueue(1)`, và **tách khỏi `app.state.jobs`** đang dùng chung với benchmark: hàng đợi đó
định cỡ cho thông lượng, nhét một phép so ba giờ vào sẽ bỏ đói nó, còn thu nó về 1 sẽ bỏ đói mọi
thứ khác. Hai hàng đợi, hai loại việc, hai ràng buộc khác nhau.

Đây là chỗ hiếm khi độ sâu 1 **không** phải một thoả hiệp hiệu năng — nó là điều kiện đúng đắn.

## 3. Tiến độ: lấy từ chính phép quét

Thêm hook `Progress = Callable[[int, int, str], None]` vào `simulate`, gọi **đúng chỗ** journal
đang ghi `index`/`total`. Không parse chuỗi: con số đã được tính sẵn ở đó, và một caller phải đọc
ngược chúng ra từ dòng đã định dạng sẽ vỡ ngay lần đầu ai đó nới một cột.

Gọi cả trên trace **dùng lại**, không chỉ trace mới mô phỏng: một run phục vụ hoàn toàn từ đĩa vẫn
đi từ 0 tới N, và thanh tiến độ đứng yên ở 0 suốt lượt đó là báo sai.

### Một chỗ ghi nhãn sai, tìm ra khi chạy thật

Lần chạy đầu in `0/30` rồi nhảy `60/60`. Con số là **cặp (candidate, episode)** — 30 episode trên
hai candidate là 60 lượt — không phải episode. Hai chỗ phải sửa:

- Bỏ việc gieo `total = episodes` lúc nộp job. **Mẫu số đổi dưới chân người đọc còn tệ hơn mẫu số
  tới chậm một giây**, nên để phép quét tự báo cả hai con số khi nó có.
- Nhãn cột đổi từ "Episodes" sang "Lượt episode" ở cả hai ngôn ngữ, và comment trên type nói rõ.

Nếu chỉ chạy test thì không thấy: test khẳng định `progress == total`, và cả hai đều đúng dù nhãn
sai.

## 4. UI

**`/decisions` — panel khởi chạy.** Chọn deployment, hai candidate, số episode (để trống thì dùng
N_min suy từ rủi ro đã khai — điền số vào là lặng lẽ ghi đè số học của hợp đồng, nên khi trống thì
**bỏ hẳn trường** chứ không gửi 0). Nút tắt khi đang có lượt chạy, kèm câu giải thích vì sao chỉ
một lượt.

Bảng job: trạng thái, `progress/total`, chi tiết, nút huỷ khi còn sống, và **liên kết thẳng tới
run** khi xong — job mang theo id của run, nên người đọc không phải tìm "cái vừa xuất hiện";
*"gần đây"* không phải một danh tính.

Polling **chỉ khi có job còn sống**, dừng hẳn khi hết. Một trang cứ hỏi mãi sau khi mọi thứ xong
là một trang giữ laptop thức.

**Huỷ không mất gì.** Episode đã ghi vẫn còn, và đó là tính chất chứ không phải rò rỉ: trace khoá
theo hash nội dung, nên chạy lại cùng candidate trên cùng deployment dùng lại từng file. Một lượt
quét ba giờ bị huỷ không tốn gì ở lần thứ hai.

## 5. Xác minh: chạy thật, không chỉ test

Dựng server, đăng nhập hai tài khoản, chạy đủ vòng:

```
queue -> 202 running
  running: 0/30
  running: 60/60  rrtstar+dwa
job finished: succeeded | run_id=507f1d21f116
run: ranked=True config_state=pending status=CLEAR_RECOMMENDATION
review  -> 200 reviewed by 972a1600b5f0
approve -> 200 approved
approved_config.yaml -> 200, 1188 bytes
audit: [(1,'review','unreviewed->reviewed'), (2,'approve_config','pending->approved')]
```

`approved_config.yaml` mở đầu bằng đúng dòng nó phải mở đầu:

```yaml
artifact: approved_config
sim_only_notice: 'Đây là một FILE CẤU HÌNH, không phải một lệnh triển khai...'
```

Alice chạy, Bob duyệt — luật chống tự duyệt (HĐ-14) không cản, vì hai người khác nhau.

## 6. Test

**Backend +6** (`TestQueueingASweepInsteadOfWaitingForIt`): 202 và chưa đặt tên gì tồn tại · run
xuất hiện khi xong và job mang id của nó · tiến độ đếm episode thật chứ không đoán · huỷ được ·
job không tồn tại là 404 · **cùng một candidate hai lần bị từ chối trước khi chiếm slot** — lời từ
chối đó mà tới muộn thì tốn hàng giờ.

**Web +7** cho panel khởi chạy. Tổng web 520 passed.

## 7. Còn lại đúng một khoảng trống

**Chưa có trình xem trace Parquet.** Luồng cũ có `MapCanvas`, `Scene25D`, `useTrajectoryPlayback`
— xem được robot chạy. Luồng mới ghi `artifacts/traces/<candidate>/<episode>.parquet` và không có
gì đọc chúng ra màn hình; endpoint `episodes` phục vụ mô hình dữ liệu cũ.

Theo chốt "xây song song", luồng cũ vẫn gánh việc đó. Nhưng đây là thứ duy nhất còn thiếu để luồng
mới **thay** được luồng cũ, và nó nên là việc tiếp theo khi quay lại tinh gọn.

---

# Phần 2 — trình xem trace Parquet

Viết tiếp cùng ngày, sau khi phần trên xong. Đây là khoảng trống cuối cùng.

## 8. Vì sao nó quan trọng hơn "một tính năng xem cho đẹp"

Mỗi cặp (candidate, episode) có **một** file Parquet, và theo HĐ-5 đó là **nguồn dữ liệu duy
nhất** của Metrics Engine. Mọi con số trên Decision Card — tỷ lệ thành công, p99, khoảng hở, ΔU —
đều rút ra từ những file đó.

Cho tới lượt này **không có gì đọc chúng ra màn hình được**. Nền tảng tính ra *"G3: fail, 70%
thành công"* rồi đề nghị người ta tin. Endpoint `episodes` phục vụ mô hình dữ liệu của stack cũ,
không đọc được Parquet.

## 9. Backend: một endpoint, ba thứ đi cùng nhau

`GET /decisions/{run_id}/traces/{candidate_id}/{episode_context_id}`

Trả về **quỹ đạo + bản đồ + metadata**, vì không thứ nào có nghĩa khi đứng một mình: quỹ đạo không
kèm bản đồ là một nét nguệch ngoạc; bản đồ không kèm id episode là ảnh chụp một nơi nào đó.

**Lưới occupancy nén một bit mỗi ô, base64.** Sảnh tham chiếu là 480×320 = 153.600 ô; ở dạng mảng
JSON số 0/1 là ~300 kB văn bản, nén lại còn **19 kB**. Trình duyệt giải nén trong đúng vòng lặp nó
vốn phải viết để duyệt lưới. Payload thật đo được: **69 kB** cho một episode 417 bước.

**Dữ liệu theo cột, không theo hàng** — đúng như file. Viết lại 417 hàng thành 417 object sẽ làm
payload gấp ba để nói cùng một điều.

**Từ chối trace không thuộc run này.** Id là hash nội dung, nên sai id không phải lỗi gõ — nó là
yêu cầu lấy bằng chứng của một thí nghiệm khác dưới tên run này. Kiểm cả candidate lẫn episode.

## 10. Trình xem: vẽ những thứ mang nghĩa

| vẽ gì | vì sao, không phải trang trí |
|---|---|
| Lưới occupancy | để một đường đi sát tường trông đúng là sát tường |
| **Màu theo khoảng hở** | G2 chặn va chạm, và objective an toàn neo vào khoảng hở đo **từ mặt robot** (HĐ-8.2). Phần đáng nhìn của một quỹ đạo là chỗ nó chạy sát, không phải chỗ nó đi qua. Một màu duy nhất giấu đúng cái đó |
| Sự kiện đánh dấu tại chỗ | va chạm và tới đích vẽ ra **cùng một đường cong**; chỉ cái dấu mới phân biệt |
| Robot vẽ **đúng bán kính** | đường trông thoáng ở mức một pixel mỗi ô có thể không thoáng khi vẽ thân 0,26 m |
| Điểm xuất phát và đích | nếu không, đường đi là nét cong có thể đang đi ngược |

Thang màu: **đỏ ở ranh giới va chạm** (khoảng hở 0 là chạm, vì đo từ mặt robot chứ không phải từ
tâm), qua hổ phách, tới xanh khi còn trọn một bán kính.

**Lật trục y.** Màn hình y tăng xuống dưới, thế giới thì không. Thiếu phép lật là vẽ ra ảnh gương
của lần chạy — và ảnh gương vẫn trông như một đường đi hợp lý, nên đây là thứ phải khẳng định bằng
test chứ không nhìn bằng mắt.

Đặt **ngay dưới bảng cổng, trên khuyến nghị**: một dòng nói *"G3: fail"* là tuyên bố về các
episode, và việc tiếp theo người đọc nên làm được là mở một episode ra xem. Đặt dưới card thì quỹ
đạo thành minh hoạ cho một kết luận, thay vì là thứ kết luận rút ra từ đó.

Tải theo yêu cầu: một run có 30–300 episode mỗi candidate, mỗi cái là một bản đồ cộng vài trăm
pose.

## 11. Xác minh: so với chính file gốc

```
grid cells       : 153600
grid matches file: True      <- dựng lại từ bit, so từng ô với map engine nạp
occupied cells   : 14256
poses in file    : 417
poses served     : 417
x matches        : True
clearance matches: True
events           : [{'index': 416, 'event': 'stuck'}]
missions         : [{'id': 'through_hall', 'start': {'x': 2.0, 'y': 8.0}, 'goal': {'x': 22.0, 'y': 8.0}}]
foreign candidate: 404 candidate in this run 'deadbeefdead' not found
```

Một chỗ sửa lúc kiểm: `missions` ban đầu ra `[['x',2.0],['y',8.0],['theta',0.0]]` — do
`list(Pose2D)` duyệt model pydantic thành cặp khoá-giá trị. Không đọc được bởi cái gì, và vẽ được
bởi ít hơn thế.

## 12. Test

**Backend +6** (`TestReadingBackTheEvidence`): phục vụ đúng số pose file có · bản đồ đi kèm và độ
dài gói bit khớp công thức · sự kiện thưa và mang index hợp lệ · có đủ bán kính robot và mission
để vẽ đúng tỷ lệ · candidate lạ 404 · episode run này chưa từng đo 404.

**Web +13** (`trace-viewer.test.tsx`): vị trí panel giữa bảng cổng và khuyến nghị · tải theo yêu
cầu · **lật trục y** · robot đúng bán kính · màu theo khoảng hở · 0 là ranh giới va chạm · đánh dấu
sự kiện · giải nén bit · mở ra hiện toàn đường (mở ở bước 0 sẽ là bản đồ trống, đọc như tải hỏng) ·
reset khi đổi episode · dừng timer ở cuối · đủ khoá i18n hai ngôn ngữ.

Web tổng: **533 passed**. tsc sạch, ruff sạch.

## 13. Luồng mới giờ đứng được một mình

```
/deployments  nộp profile  →  /decisions  xếp hàng, theo dõi  →  /decisions/[id]
   bảng cổng  →  XEM LẠI EPISODE  →  Decision Card  →  đọc  →  duyệt  →  approved_config.yaml
```

Không còn phụ thuộc luồng cũ ở khâu nào. Chốt "xây song song" vẫn giữ nguyên — nhưng lý do kỹ
thuật khiến không thể thay ngay thì đã hết.

---

# 14. Chốt: đây là **MVP v1** của Planner Selector

Ngày 2026-08-12, dev chốt bản này là MVP v1 — bản đơn giản nhất nhưng **đủ đứng một mình**.

## Đủ ở chỗ nào

Một người không đọc code làm được trọn vòng, chỉ bằng trình duyệt:

```
nộp deployment  →  chạy phép so  →  đọc bảng cổng  →  xem lại episode
      →  đọc Decision Card (khi có)  →  đánh dấu đã đọc  →  duyệt  →  tải cấu hình
```

Và quan trọng hơn: **mỗi bước đều từ chối được**. Nền tảng nói "không" đúng chỗ nó phải nói không:

| từ chối | vì sao nó là tính năng chứ không phải giới hạn |
|---|---|
| Sáu cổng chạy trước mọi phép chấm | candidate trượt cổng không phải lựa chọn tệ hơn — nó không phải một lựa chọn (HĐ-7) |
| Không đủ hai candidate qua cổng ⇒ **không có card** | bảng cổng là kết quả; ép ra card là áp lực đã sinh ra tấm card tuyên bố cận trên va chạm từ một episode |
| Deployment đặt ngưỡng tại lý tưởng ⇒ **không xếp hạng được** | thang sập thì từ chối toàn bộ, không bỏ metric chết rồi chấm tiếp (HĐ-8.4) |
| Không tự duyệt run của mình | người chọn candidate không phải bước kiểm độc lập (HĐ-14) |
| Không duyệt được run không có card | "đã đo" không được biến thành "đã chuẩn thuận" |
| Đổi nhiễu ⇒ phải đổi `task_profile_id` | `episode_context_id` không băm biên độ (HĐ-3.1) |
| Một lượt chạy đánh giá một lúc | hai run ghim cùng nhân thì G4 đo một cái máy không tồn tại (HĐ-7.4) |
| Candidate trùng nhau bị chặn **trước** khi chiếm slot | lời từ chối tới muộn thì tốn hàng giờ |

## Con số của bản này

| | |
|---|---|
| Test backend | 2293 passed, 6 skipped (~13 phút) |
| Test web | 533 passed |
| Endpoint tầng quyết định | 11 |
| Deployment đã khai | 2 (`open_hall_v2`, `warehouse_a_v2`) |
| Run đã lưu | 6 nhập từ đĩa + run mới tạo qua UI |
| Decision Card còn hiệu lực | 1 (`rrtstar+dwa · dwa_coarse`, `decision_utility 0.852213`) |
| Hợp đồng | `contracts_version 6.5.0` |

## Chưa đủ ở chỗ nào — nói rõ để không ai tưởng nhầm

- **Panel khởi chạy chỉ làm được `global_planner_selection`.** Chưa có ô chọn scope, nên so hai
  cấu hình local controller vẫn phải dùng CLI.
- **Kho chưa có candidate nào qua cổng.** Mọi kết luận hiện có đều trên sảnh, và sảnh là dụng cụ
  đo chứ không phải khách hàng.
- **`success_rate_min` của sảnh vẫn là con số mượn** (L6). Cơ chế xử lý 1.00 đã có, quyết định thì
  chưa.
- **Kho chưa khai `sensor_noise`** (σ = 0) — khai vào là phải ra `warehouse_a_v3`.
- **G4/G5 mới xác nhận trên máy benchmark**, chưa trên bo mạch đích.
- **Chưa có adapter monolithic**, nên tuyên bố "công bằng cho mọi thuật toán" mới được chứng minh
  trên hai global planner cùng kiểu tìm đường trên lưới.
- **Luồng cũ vẫn còn**, theo chốt xây song song. Lý do kỹ thuật cản việc thay thế thì đã hết, chỉ
  còn là việc phải làm.

## Vì sao gọi là v1 chứ không phải v0.x

Không phải vì đủ tính năng — mà vì **không còn khâu nào phải giải thích bằng lời**. Trước lượt
này, câu trả lời cho "làm sao chạy một phép so" luôn kèm một chú thích: *chạy CLI đi*, *sửa file
YAML đi*, *trang sẽ trống đấy*, *nhìn được số nhưng không xem được episode đâu*. Giờ thì không.

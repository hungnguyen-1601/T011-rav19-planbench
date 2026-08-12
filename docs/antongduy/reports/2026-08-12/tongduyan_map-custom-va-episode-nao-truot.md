# Map tự vẽ chạy được, và episode nào trượt thì nói ra

**Ngày:** 2026-08-12 · **Sau:** MVP v1 · **Nguồn:** hai lỗ hổng dev tìm ra khi dùng thử
**Plan:** [`plans/2026-08-12/map-custom-va-ket-qua-tung-episode.md`](../../plans/2026-08-12/map-custom-va-ket-qua-tung-episode.md)

---

## 1. Hai lỗ hổng có cùng một hình dạng

Cả hai đều là **dữ liệu đã có mà không đi ra được tới màn hình** — không việc nào cần thuật
toán mới.

| dev nói | thứ đã có sẵn | thứ thiếu |
|---|---|---|
| *"chọn runs để so sánh chưa cho phép tinh chỉnh maps"* | `/maps` đã có editor vẽ ô, versioning, checksum | không có đường nào từ map store sang task profile |
| *"chỉ nhìn thấy id các lần chạy, không biết run nào fail run nào success"* | `EpisodeMetricSet` có `success` và `failure_reason` cho **từng** episode | report gộp lại thành `success_rate` rồi **vứt các dòng** |

## 2. Việc A — map tự vẽ chạy được

### Không đổi một dòng hợp đồng nào

Cách rẻ nhất hoá ra cũng là cách đúng: **vật chất hoá map ra đĩa**. `dump_map_server` là
nghịch đảo đúng của `load_map_server` đã có; thứ rơi xuống `maps/custom/` là một map_server
map bình thường, không phân biệt được với cái `nav2_map_server` sinh ra. Toàn bộ tầng dưới —
`task_map`, manifest, endpoint trace — chạy nguyên, không sửa.

Hàng rào là round-trip: `load_map_server(*dump_map_server(m)) == m`, đủ cả ba trạng thái ô.
Một writer lặng lẽ gộp `UNKNOWN` vào `FREE` sẽ biến một góc chưa khảo sát thành sàn trống
mà planner lái thẳng qua — và test bắt được đúng ca đó.

Chỗ dễ sai thứ hai, cũng phải khẳng định bằng test chứ không nhìn mắt: **lật hàng**. `MapData`
hàng 0 nằm ở gốc bản đồ, PGM hàng 0 là đỉnh ảnh. Thiếu phép lật thì file là ảnh gương của
bản đồ — và một cái kho lộn ngược vẫn trông như một cái kho.

### Đổi map thì phải đổi id, và server cưỡng chế

`POST /task-profiles/derive` **dẫn xuất** một deployment mới, không sửa cái cũ. Lý do là cái
bẫy `sensor_noise` đã từng bật: `episode_context_id` băm `(task_profile_id, mission_id,
environment_variant, seed)` và HĐ-3.1 đóng băng payload đó — **map không nằm trong đó**. Thay
tường dưới một id cũ sẽ sinh ra context hash trùng với thế giới cũ, và `--reuse-traces` phục
vụ episode ghi ở nơi không còn tồn tại. Không có gì cảnh báo; id khớp nhau.

Nên `new_id == base_id` bị từ chối 422, kèm đúng lý do đó.

### Chỗ đáng tiền nhất: kiểm mission **trước** khi tốn giờ máy

Một goal nằm trong kệ cho **0% success với mọi candidate**, và phép so khi đó báo hoà giữa các
stack trên một câu hỏi không stack nào được hỏi — mọi cột đọc ra một con số 0.00 hợp lý,
không có gì trong các con số là sai.

`validate_missions_on_map` đã bắt được năm kiểu lệch này từ lâu. Việc lần này chỉ là **gọi nó
lúc khai deployment** thay vì lúc chạy: khác nhau giữa một lời từ chối và hai tiếng máy đo cái
bản đồ thay vì đo các candidate.

Endpoint làm bốn việc theo đúng thứ tự: nạp profile gốc → ghi map ra đĩa → thay
`environment.map`/`missions` → **validate rồi mới lưu**. Một mission không vừa thì không có
gì được lưu (test khẳng định luôn cả điều đó, không chỉ mã lỗi).

### `maps/custom/` thì gitignore — đảo lại so với ý ban đầu

Bản plan định commit chúng, với lý do "deployment trỏ vào file không có trong repo là không
tái lập được". Nhưng lưới người vẽ nằm trong `planbench.db`, mà **DB đã bị gitignore** từ
trước. Commit đầu ra của một nguồn không nằm trong git là commit một bản sao sẽ cũ ngay lần
đầu ai đó sửa map. Dựng lại bằng cách derive lại.

### UI: chọn map, không dựng editor thứ hai

Panel khởi chạy `/decisions` thêm một ô chọn map, **mặc định "bản đồ của chính deployment"** —
mọi luồng cũ chạy nguyên, không thêm một cú bấm nào. Chọn map khác thì mở ra ô `new_id`, xem
trước `MapCanvas`, và **bấm chuột lên bản đồ** để đặt xuất phát/đích (cú bấm tự lật sang đích
sau khi đặt xong xuất phát).

Robot vẽ **đúng bán kính** của deployment: một điểm xuất phát trông thoáng ở mức một pixel mỗi
ô có thể là chỗ robot không lọt, và đó là một trong năm kiểu lệch server từ chối — kiểu vô
hình nếu không có cái vòng tròn.

Vẽ ô vẫn là việc của `/maps`, chỉ thêm một link dẫn sang. **Hai editor là hai định nghĩa của
cùng một thứ.**

### Đợt sửa thứ hai: chỉnh start/goal theo đúng kiểu bản cũ

Bản đầu đặt pose bằng cách bấm **luân phiên ngầm** — bấm lần một ra xuất phát, lần hai ra
đích. Dev yêu cầu làm giống scenario editor cũ, và yêu cầu đó đúng: nhích cái xuất phát hai
pixel thì cú bấm thứ hai **thả một cái đích** xuống đó.

Nên đổi sang đúng hình dạng editor cũ dùng, kèm ba thứ nó có mà bản đầu thiếu:

| | |
|---|---|
| **Chế độ tường minh** | Hai nút bật/tắt `Đặt xuất phát` / `Đặt đích`, có trạng thái đang bật, kèm một dòng nói cú bấm tiếp theo làm gì. Chỉ tự nhảy sang đích **khi đích còn trống** — tiện ở lượt đầu, hết bất ngờ về sau |
| **Kéo được** | `MapCanvas` đã có `onWorldDrag` từ trước, chỉ chưa ai nối. Kéo để dời pose |
| **Gõ được số** | Canvas không bấm trúng `2.00` bao giờ. Một deployment ghi tới hai chữ số thập phân là cái người khác lặp lại được từ báo cáo |
| **Hướng, theo độ** | Hợp đồng lưu radian; không ai gõ `1.5708` cho một phần tư vòng |
| **Vòng dung sai đích** | Lấy `goal_tolerance_m` của chính deployment. Episode kết thúc ngay khi robot vào trong vòng đó, nên một cái đích đặt cách kệ đúng một dung sai là một nhiệm vụ khác với cái đặt cách một mét |

Kéo/bấm **giữ nguyên hướng** đã đặt: dời cái xuất phát mà lặng lẽ xoay robot về hướng đông là
xoá một lựa chọn tác giả đã làm.

**Và một chỗ phải nói thật, khác với bản cũ.** Editor cũ có ô hướng cho **cả hai** pose. Trên
nền tảng này hai ô đó không ngang nhau:

- **Hướng xuất phát là thật.** Engine khởi tạo `RobotState(pose=scenario.start_pose)`. Xác minh:
  đặt 180°, dựng episode ra `scenario start theta = 3.1416 rad (180 deg)` — robot quay lưng
  vào đích và mất giây đầu để xoay.
- **Hướng đích được lưu, được vẽ, và không bao giờ được chấm.** HĐ-6 buộc mọi deployment khai
  `goal_tolerance_rad >= π` vì simulator không có bộ điều khiển hướng cuối; xác minh trên
  profile dẫn xuất: `goal_tolerance_rad = 3.1416`.

Vẫn giữ ô hướng đích — canvas đã vẽ mũi tên hướng cho cả hai pose, bỏ ô đi thì mũi tên đó thành
một dấu hiệu không ai giải thích. Nhưng ghi thẳng dưới ô: *"đổi số này không đổi phán quyết
nào"*. Một cái núm không nhãn mà xoay không ăn thua gì là thứ phải tránh, không phải cái núm.

Tiện thể: `button.active` **chưa từng có style** — editor cũ đã gán class đó cho nút chế độ từ
đầu và không có gì tô nó. Thêm vào `globals.css`, cả hai trang cùng được.

Nút Chạy tắt khi map custom **khai dở** (có map nhưng thiếu id hoặc thiếu pose). Im lặng lùi
về bản đồ của deployment là kiểu hỏng tệ nhất ở đây: lượt chạy vẫn hợp lệ và trả lời một câu
hỏi khác.

## 3. Việc B — episode nào trượt, và trượt kiểu gì

### Report ghi thêm từng episode

`success_rate: 0.70` nói bảy mươi phần trăm của cái gì đó đã xảy ra. Nó **không** nói ba mươi
phần trăm nào đã không, cũng không nói đó là ba mươi lần va chạm hay ba mươi lần quá giờ — mà
hai cái đó đòi hai việc hoàn toàn khác nhau (HĐ-6 có bốn ô: `no_path`, `collision`, `timeout`,
`stuck`).

Thêm `episodes` vào **mỗi candidate**, không phải một bảng chung: dừng sớm làm hai candidate
chạy số episode khác nhau, và một bảng chung sẽ phải bịa ô trống cho phần chênh — mà một ô
trống trong bảng kết quả đọc như một phép đo trả về rỗng, không phải một phép đo chưa làm.

Bảy trường mỗi dòng, cố ý hẹp: đây là dòng người ta lướt để **tìm episode đáng mở**, không
phải bản sao thứ hai của metric set.

**Danh sách `/decisions` cắt trường này đi.** 300 episode × 2 candidate × 10 run là gần một
megabyte cho một trang không vẽ lấy một dòng episode nào. Cắt ở **response**, không phải ở
lưu trữ — trang chi tiết vẫn có đủ.

### Report cũ đọc là *"chưa ghi"*, không phải *"tất cả đạt"*

Sáu run nhập từ đĩa không có trường này. Hai thứ đó nhìn giống hệt nhau — một cái bảng không
có màu đỏ nào — và chỉ một trong hai là một phép đo. Cùng luật với `weight_stability_margin:
null` đã có.

### UI: bảng episode × candidate, bấm ô là mở

Đặt **ngay trên trình xem trace**, trong cùng panel bằng chứng:

```
bảng cổng    "G3: fail, 70% thành công"      <- tuyên bố về các episode
bảng episode "#7 va chạm · #12 kẹt"          <- episode NÀO, và kiểu gì
trình xem    vẽ ra episode đó                <- bấm vào ô là mở
```

Episode chạy dọc, candidate chạy ngang, vì phép so là **ghép cặp**: cùng một episode chạy cho
mọi candidate (HĐ-7.3), và ô đáng nhìn là ô hai bên **bất đồng**. Để candidate chạy dọc thì
hai phán quyết đó nằm ở hai dòng khác nhau.

Mỗi ô là một cái nút. Tìm ra episode va chạm rồi phải chép hash sang dropdown là gần hết công
sức của việc nhìn nó.

Ô của episode một candidate **chưa từng chạy** (do dừng sớm) vẽ là *"chưa chạy"*, không phải
để trống: khác với đã chạy và đạt, và đó là thứ giải thích vì sao mẫu số dòng đó nhỏ hơn của
bảng.

Có ô tick **"chỉ episode có candidate trượt"** — 300 dòng mà phần lớn là hai ô xanh. Kèm
`hiện X/Y` **luôn hiện**: một bảng lặng lẽ bỏ dòng đọc như một bảng đầy đủ. Và số thứ tự
episode là **vị trí trong run**, không phải trong bảng đã lọc — nếu không thì `#7 va chạm`
nghĩa khác nhau khi bật và khi tắt ô tick, và con số thôi làm tham chiếu.

### Danh sách `/decisions`: cột kết quả đọc được

Trước: cột Outcome in `recommended_candidate_id` — một hash hex. Đó là danh tính đúng cho một
đường dẫn trace và là thứ sai để đặt trước mặt người đang lướt mười dòng tìm run đã chọn được
cái gì.

Sau: **stack + cấu hình** của bên thắng, kèm **mấy/mấy qua cổng**. Con số cổng đi kèm cả run
không card: một khuyến nghị từ hai bên sống sót và một từ năm bên là hai tuyên bố khác nhau,
còn một run không ai qua cổng là **kết quả**, không phải run hỏng (HĐ-7). Ba chip lý do
không-card giữ nguyên tách bạch — ba lý do, ba hành động tiếp theo khác nhau.

## 4. Xác minh

### Chạy thật qua HTTP, không chỉ test

Test dùng `POST /decisions` (đồng bộ); nút trong panel dùng `POST /decisions/jobs` (xếp hàng).
Nên chạy riêng đúng chuỗi lệnh trình duyệt gọi, trên một map vẽ trong lúc chạy:

```
map drawn        : cba5acfcaeb4 60x40 @0.2m          <- phòng 12x8 m, tường giữa có cửa
goal in the wall : 422 task profile 'live_bad' does not fit map 'cba5acfcaeb4__v1':
                       mission 'into_wall' goal (6.00, 1.00) is on an occupied…
  stored anyway? : 404 (404 = no)                    <- từ chối TRƯỚC khi lưu
same id reused   : 422
derived          : 201 live_room_v1 -> maps/custom/cba5acfcaeb4__v1.pgm
queued           : running
  running: 1/4 astar+dwa
  running: 4/4 rrtstar+dwa
finished         : succeeded run_id=aeb0144ba84d
list outcome     : winner=None cleared=0/2
list strips rows : True
  astar+dwa      blocked=G2         pass pass
  rrtstar+dwa    blocked=G2         pass pass
trace from a cell: 200 poses=222 map=60x40
```

Một map vẽ trong phiên, chạy tới cùng, xem lại được quỹ đạo trên đúng bản đồ đó — chưa từng
làm được trước lượt này.

Hai điều đọc kèm: **`cleared=0/2` dù đạt cả hai episode** là G2 chặn — hai episode không đỡ nổi
cận trên va chạm, và đó là cổng làm đúng việc của nó chứ không phải lỗi. Và `winner=None` là
**kết quả**, đúng loại kết quả cột mới phải dựng được.

### Chỗ chứng minh việc B đáng làm

Cùng chạy đó, trên sảnh với timeout cắt ngắn:

```
hall run : ranked=False
  astar+dwa    rate=0.00  gates_blocked=G3  stuck stuck stuck timeout timeout timeout
  rrtstar+dwa  rate=0.00  gates_blocked=G3  timeout timeout timeout timeout timeout timeout
```

**Hai dòng giống hệt nhau ở mọi con số cũ**: cùng `success_rate 0.00`, cùng phán quyết G3,
cùng số episode. Trước lượt này chúng không phân biệt được. Giờ thì một bên kẹt ba lần rồi quá
giờ ba lần, bên kia quá giờ cả sáu — hai chẩn đoán khác nhau đòi hai việc khác nhau.

(Timeout 25 s trên nhiệm vụ 20 m là của fixture rút gọn, không phải kết quả về candidate.)

### Suite

| | trước | sau |
|---|---:|---:|
| Backend | 2293 passed, 6 skipped | **2312 passed, 6 skipped** (+19) |
| Web | 533 passed | **571 passed** (+38) |

`ruff check` sạch, `ruff format` sạch, `tsc --noEmit` sạch.

Backend +19: round-trip map (5) · kết quả từng episode (5) · dẫn xuất deployment (9, gồm một
sweep thật trên map tự vẽ và một phép ghim hướng xuất phát tới tận `scenario_for`).
Web +38: helper thuần (7) · cột kết quả danh sách (3) · chọn map (9) · bảng episode (10) ·
chỉnh pose (9).

Con số backend 2311 là của lần chạy full suite trước khi thêm test ghim hướng; test đó chạy
riêng và xanh, nên 2312 là con số suy ra, chưa chạy lại full suite sau nó.

Hai lỗi web còn lại **có sẵn trước lượt này**, không liên quan: `dashboard-page.test.tsx` so
đường dẫn `\system\page.tsx` với `/system/page.tsx` (dấu phân cách Windows), và
`assistant-page.test.tsx` không collect được. Đã kiểm bằng `git stash` để chắc.

## 5. Chưa làm, và nói rõ

- **Sinh map theo tham số** (nợ C2: map vừa khó vừa đối xứng). Đúng việc, khác phiên.
- **Upload PGM từ SLAM thật.** Cần khi có map hiện trường.
- **Đổi `EnvironmentSpec` để trỏ thẳng vào map store.** Vật chất hoá ra đĩa cho cùng kết quả
  với không một dòng hợp đồng nào phải bump.
- **Panel khởi chạy vẫn chỉ làm `global_planner_selection`** — nợ cũ từ MVP v1, không đụng
  lần này.
- **Derive chỉ đổi map và mission.** Nhiễu, ngưỡng, robot chép nguyên từ profile gốc. Muốn đổi
  nhiễu thì vẫn là dán YAML ở `/deployments` — đúng, vì đổi nhiễu cũng là đổi thế giới và có
  luật riêng của nó (HĐ-13).

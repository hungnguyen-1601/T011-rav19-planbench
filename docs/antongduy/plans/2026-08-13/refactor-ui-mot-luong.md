# Kế hoạch refactor UI: từ hai luồng về một

> **Ngày lập:** 2026-08-13 · **Trạng thái:** chờ dev duyệt
> **Dựa trên:** [`notes/2026-08-13/tongduyan_danh-gia-ui-hai-luong.md`](../../notes/2026-08-13/tongduyan_danh-gia-ui-hai-luong.md)
> **Bối cảnh:** dev chốt 12-08 *"xây SONG SONG cho tới hết MVP, rồi quay lại tinh gọn"*. Ba điều
> kiện để luồng cũ nghỉ được — form khai deployment, hàng đợi chạy phép so, trình xem trace — **đã
> xong cả ba**. Đây là lượt quay lại.

---

## 0. Dev đã chốt

| | |
|---|---|
| `/leaderboard` | **đổi vai thành danh mục Decision Card**; không xếp hạng xuyên deployment |
| Benchmark cũ | **không migrate** — đúng một dòng, và migrate là ba lần bịa ra một sự thật |
| `robot-profiles` | **nguồn sự thật về chiếc xe**; `control_period` ở lại deployment |

---

## 1. Nguyên tắc

### 1.1. Điều hướng theo **việc người dùng đang làm**, không theo hệ thống sinh ra màn hình

Đây là chi phí lớn nhất của việc chạy song song và nó **không nằm ở mã**: sidebar hiện có mười
hai mục, hai luồng trộn trong cùng một nhóm, và không gì nói cho người đọc biết `Benchmarks` với
`Decisions` trả lời hai câu hỏi khác nhau.

### 1.2. Đổi vai, không xoá

Phần lớn luồng cũ đã đổi vai một cách tự nhiên: map, library, scenario giờ là **nguyên liệu**
dựng deployment. Xoá chúng là mất nguyên liệu; việc cần làm là để điều hướng nói đúng vai đó.

### 1.3. Không màn hình nào mâu thuẫn hợp đồng

Một bảng xếp hạng xuyên deployment vi phạm HĐ-1.4. Sau lượt này **không được còn màn hình nào
làm việc đó**, kể cả dưới một cái tên khác.

### 1.4. Task profile phải **tự chứa** — ràng buộc chi phối cách làm P5

HĐ-13 nói người khác phải dựng lại được lượt chạy **từ chính profile**. Một profile *tham chiếu*
tới một dòng `robot_profiles` có thể sửa được sẽ **đổi nghĩa khi ai đó sửa dòng đó**, và mọi
trace đã lưu lặng lẽ mô tả một con robot khác. Xem P5.

---

## 2. Sáu pha

### P1. Sidebar nói đúng việc *(rẻ nhất, giá trị cao nhất, không đụng endpoint nào)*

```
LÀM GÌ        Deployments   khai một thế giới để đo
              Simulate      thử một episode trên nó
              Decisions     chạy phép so, đọc kết quả, duyệt

NGUYÊN LIỆU   Maps · Library · Candidates · Models

TÀI KHOẢN     Reviews · System · Agent
```

Mỗi mục thêm **một dòng mô tả** — thứ đang thiếu hoàn toàn. `Scenarios`, `Benchmarks`,
`Leaderboard` rời sidebar ở các pha sau; pha này chỉ sắp lại và mô tả.

**Ước lượng:** 2 giờ. **Hàng rào:** test điều hướng hiện có phải xanh; thêm test khẳng định mỗi
mục có mô tả trong cả hai locale.

### P2. `/leaderboard` → danh mục Decision Card

Đọc `decision_runs`, mỗi dòng là một phép so **kèm deployment của nó**. Lọc theo deployment,
theo trạng thái duyệt, theo có/không có card.

**Ràng buộc là toàn bộ lý do đổi vai:** không xếp hạng xuyên deployment.

> **Chỗ dễ trượt, ghi to:** một cột `decision_utility` **sắp xếp được** sẽ tái tạo đúng bảng xếp
> hạng vừa bỏ, chỉ khác cái tên. `decision_utility` chỉ so được **trong** một deployment. Nên
> hoặc không cho sắp xếp theo cột đó xuyên deployment, hoặc chỉ hiện nó khi đã lọc về một
> deployment.

**Ước lượng:** nửa ngày. **Hàng rào:** một test khẳng định trang không sắp xếp theo
`decision_utility` khi chưa lọc về một deployment.

### P3. Trang `Candidates` — **thêm một trang, không phải bớt**

Hôm nay người dùng gõ tay `astar+dwa` / `dwa_coarse` vào hai ô text trong panel khởi chạy: không
gợi ý, không kiểm tra, sai thì biết lúc server trả lỗi.

Trang mới: liệt kê stack trong registry (từ `/algorithms` cũ, **đổi vai**) và candidate đã đăng
ký (`GET /candidates`), hiện `candidate_id` là hash nội dung (HĐ-1.3). Panel khởi chạy đổi hai ô
text thành dropdown.

**Ước lượng:** nửa ngày.

### P4. `/simulate` đổi vai thành **sân thử**

Đây là chỗ luồng mới **thật sự thiếu**: `useEpisodeStream` xem robot chạy **trực tiếp** qua
WebSocket, còn `TraceViewer` chỉ **phát lại file đã ghi**. Hai câu hỏi khác nhau — *"chuyện gì đã
xảy ra"* với *"thử cấu hình xem sao"*.

Đổi đầu vào từ **scenario** sang **deployment**: chọn một deployment, một candidate, chạy **một**
episode, xem trực tiếp. `scenario_for(profile, context)` đã có sẵn trong `planbench_benchmark`,
nên cầu nối không phải viết mới.

**Vì sao đáng giữ:** trước khi bỏ 2,2 giờ máy vào một phép so 300 episode, xem một episode chạy
là cách rẻ nhất phát hiện mission đặt sai hay nhiễu khai quá tay.

**Ước lượng:** 1 ngày.

### P5. `robot-profiles` thành nguồn sự thật — **pha rủi ro nhất, đọc kỹ**

Ba nhóm trường, ba số phận:

| | |
|---|---|
| Chung + chỉ có ở `RobotProfile` (bán kính, tốc độ, footprint, LiDAR) | → `robot-profiles`. Đây là **chiếc xe** |
| Gia tốc (`max_linear_acceleration`, `max_angular_acceleration`) | `RobotProfile` **đang thiếu** mà simulator cần → **thêm vào đó** |
| **`control_period`** | **Ở LẠI deployment.** Nó là ngưỡng cổng G4 — *"ngân sách wall-clock cho một bước điều khiển trên bo mạch đích"*. Cùng một con robot ở hai hiện trường có thể bị đòi hai chu kỳ khác nhau |

**Và một quyết định về cách nối, quan trọng hơn cả ba dòng trên.** Hai cách hiểu "nguồn sự
thật":

| | |
|---|---|
| **(a) Nguồn lúc khai** *(đề xuất)* | Form chọn một robot profile và **điền số vào** deployment. Profile vẫn ghi giá trị **inline**. Không đổi hợp đồng, không lượt chạy nào mất hiệu lực |
| (b) Tham chiếu | `task_profile.robot` thành một `robot_profile_id`. **Đổi hợp đồng** ⇒ hai profile đã ship đổi nội dung ⇒ **đổi `task_profile_id`** ⇒ **mười `decision_runs` đang có mồ côi** |

Đề xuất **(a)**, và lý do không phải là "rẻ hơn": HĐ-13 đòi người khác dựng lại được lượt chạy
**từ chính profile**. Một profile trỏ tới một dòng DB **sửa được** sẽ đổi nghĩa khi ai đó sửa
dòng đó, và mọi trace đã lưu lặng lẽ mô tả một con robot khác. Cách (a) đặt nguồn sự thật đúng
chỗ nó cần đứng — **lúc tác giả khai** — mà vẫn giữ profile tự chứa.

**Ước lượng:** 1 ngày. **Hàng rào:** test khẳng định `control_period` **không** có trong
`RobotProfile`, kèm lý do.

### P6. Luồng cũ nghỉ

- `/benchmarks`, `/benchmarks/[id]`, `/scenarios`, `/scenarios/[id]` rời sidebar và rời repo.
- `/algorithms` đã hoá thân vào P3.
- **Không xoá dữ liệu**: bảng `benchmarks` (một dòng) để nguyên trong DB.
- Endpoint `benchmarks` · `tuning` (19 cái): đánh dấu deprecated trước, gỡ ở một lượt sau — gỡ
  cùng lúc với UI là hai thay đổi lớn trong một lượt, và nếu có gì hỏng thì không biết vì cái nào.

**Ước lượng:** nửa ngày UI + một lượt riêng cho backend.

---

## 3. Thứ tự và lý do

```
P1 sidebar          (2 h)      ← làm trước: rẻ nhất, và nó định nghĩa chỗ đứng cho mọi pha sau
P3 Candidates       (nửa ngày) ← thêm cái còn thiếu TRƯỚC khi bỏ /algorithms
P2 danh mục card    (nửa ngày)
P4 sân thử          (1 ngày)   ← phải xong trước P6, nếu không mất khả năng xem robot chạy
P5 robot-profiles   (1 ngày)   ← rủi ro nhất, làm khi mọi thứ khác đã ổn định
P6 luồng cũ nghỉ    (nửa ngày) ← cuối, vì nó xoá thứ các pha trên vừa thay thế
```

**Tổng: khoảng 4 ngày.**

Hai ràng buộc thứ tự **cứng**, không phải sở thích:

- **P3 trước P6** — `/algorithms` là chỗ duy nhất hôm nay xem được registry.
- **P4 trước P6** — `/simulate` là chỗ duy nhất xem được robot chạy trực tiếp. Bỏ trước khi đổi
  vai là mất khả năng đó, đúng cái lý do 12-08 chốt chạy song song.

**Nếu chỉ có một ngày:** P1 + P3. Sidebar nói đúng việc và trang còn thiếu đã có; chưa xoá gì,
nên chưa mất gì.

---

## 4. Cố ý không làm trong đợt này

- **`/models`** — dev chốt để nguyên, việc của người khác. Sidebar vẫn dẫn tới một trang không
  tồn tại; P1 sắp lại điều hướng **không** sửa chuyện đó.
- **Vẽ vật cản tĩnh/động trong form deployment.** Scenario editor cũ có, form mới chưa. Nợ đã
  ghi; P6 xoá `/scenarios` sẽ làm khoảng trống này **lộ ra rõ hơn**, và đó là lý do nên làm nó
  trước hoặc chấp nhận có ý thức.
- **Gỡ endpoint cũ khỏi backend** — tách thành một lượt riêng, xem P6.
- **Danh mục Decision Card có biểu đồ.** Bản đầu chỉ là bảng.

---

## 5. Câu hỏi còn mở

1. **`/scenarios` xoá hay giữ tới khi form vẽ được vật cản?** P6 xoá nó sẽ để lại một khoảng
   trống có thật (mục 4). Ba lựa chọn: xoá luôn và chịu · giữ tới khi form đủ · làm phần vẽ vật
   cản thành pha P4.5.
2. **Danh mục Decision Card có thay `/decisions` không, hay hai trang song song?** Chúng gần
   nhau: `/decisions` đã là một danh sách có lọc. Có thể P2 chỉ là **mở rộng `/decisions`** và
   `/leaderboard` biến mất hẳn — rẻ hơn, và bớt một trang. Tôi nghiêng về hướng này nhưng nó đổi
   nghĩa của "đổi vai" dev đã chốt, nên hỏi.

# Đánh giá UI: hai luồng trong một app — trước khi lên kế hoạch refactor

**Ngày:** 2026-08-13 · **Mục đích:** dựng nền dữ kiện để cùng dev lên kế hoạch, **không phải**
kế hoạch. Mọi con số dưới đây đọc từ mã, không từ trí nhớ.

**Bối cảnh:** dev chốt 12-08 *"xây SONG SONG cho tới hết MVP, rồi mới quay lại tinh gọn"*. MVP
đã xong. Đây là lúc "quay lại".

---

## 0. Kết luận đứng trước, vì nó đổi bản chất cuộc bàn

**Ba việc mà plan 12-08 nêu là điều kiện để luồng cũ nghỉ được — cả ba đã xong.**

| điều kiện (plan 12-08) | trạng thái 13-08 |
|---|---|
| UI tạo task profile — *"hiện chỉ sửa được bằng file YAML"* | ✅ `DeploymentForm`, 729 dòng, 30 ô + map tại chỗ |
| UI khởi chạy phép so — *"`POST /decisions` chạy đồng bộ, một nút bấm có thể treo trình duyệt hàng giờ"* | ✅ hàng đợi một job, `LaunchPanel` theo dõi tiến độ |
| Trình xem trace Parquet — *"không có gì đọc chúng ra màn hình"* | ✅ `TraceViewer` + bảng episode × candidate, bấm ô mở trace |

Nên câu hỏi hôm nay **không còn là** *"làm gì trước khi bỏ được luồng cũ"* mà là *"bỏ cái gì,
giữ cái gì, và đổi vai cái gì"*.

---

## 1. Mười chín trang, thuộc về đâu

Phân loại theo thư viện client mà trang thật sự gọi (`@/lib/api` = luồng cũ,
`@/lib/decisions|deployments` = luồng mới).

### Luồng mới (3 trang)

| trang | dòng | ghi chú |
|---|---:|---|
| `/decisions` | 762 | danh sách + panel khởi chạy. **Cũng gọi `@/lib/api`** — để lấy danh sách map |
| `/decisions/[id]` | — | bảng cổng, bảng episode, trace, duyệt |
| `/deployments` | 309 | form + tab YAML |

### Luồng cũ (9 trang)

| trang | dòng | luồng mới có thứ tương ứng chưa? |
|---|---:|---|
| `/simulate` | 358 | **Chưa hẳn** — xem mục 3 |
| `/benchmarks` + `/benchmarks/[id]` | 357 | ✅ `/decisions` |
| `/leaderboard` | 479 | ❌ và **mâu thuẫn hợp đồng** — xem mục 3 |
| `/scenarios` + `/scenarios/[id]` | 146 | ✅ một phần — `MissionPlacer` |
| `/maps` + `/maps/[id]` | 153 | ✅ nhúng trong form (dùng chung `MapPainter`) |
| `/library` | 270 | ✅ nhúng trong form (nguồn map mặc định) |
| `/algorithms` | 187 | ⚠️ registry, luồng mới có "candidate" nhưng chưa có trang |

### Không thuộc luồng nào (7 trang)

`/` · `/login` · `/welcome` · `/auth/callback` · `/reviews` · `/system` · `/agent` — cắt ngang
cả hai, giữ nguyên.

### Và một trang **không tồn tại**

`/models` — sidebar link tới, file chưa từng có trong lịch sử git. Dev chốt để nguyên (việc của
người khác). Ghi lại vì nó nằm trong cùng thanh điều hướng sẽ được sắp lại.

---

## 2. Điều hướng nói gì về hai luồng — và nó đang nói sai

`NAV_SECTIONS` chia ba mục: **Workspace · Results · Account**. Nhưng hai luồng **nằm trộn vào
nhau trong cùng một mục**:

```
Workspace : Dashboard · Maps · Library · Scenarios · Simulate       ← toàn luồng CŨ
Results   : Deployments · Decisions ← MỚI
            Benchmarks · Leaderboard · Algorithms · Models · Agent  ← CŨ
Account   : Reviews · System
```

Người dùng mới mở app ra thấy **mười hai mục** và không có gì nói cho họ biết `Benchmarks` và
`Decisions` trả lời **hai câu hỏi khác nhau**, hay `Scenarios` và `Deployments` là **hai cách mô
tả cùng một thứ**. Đây là chi phí lớn nhất của việc chạy song song, và nó không nằm ở mã.

---

## 3. Bốn chỗ chồng lấn — mỗi chỗ một quyết định khác nhau

### 3.1. `/simulate` — **giữ, và đây là chỗ luồng mới thật sự thiếu**

`/simulate` dùng `useEpisodeStream`: **WebSocket**, xem robot chạy **trực tiếp**. Luồng mới có
`TraceViewer` nhưng đó là **phát lại một file đã ghi**.

Hai thứ khác nhau: phát lại trả lời *"chuyện gì đã xảy ra"*, chạy trực tiếp trả lời *"thử một
cấu hình xem sao"*. Cái sau là công cụ **thăm dò**, và nó không có chỗ trong luồng quyết định
theo thiết kế — một phép so là 300 episode chạy nền, không phải một lần bấm.

**Đề xuất: đổi vai, không bỏ.** `/simulate` thành "sân thử" — chạy một episode trên một
deployment để xem trước, trước khi bỏ 2,2 giờ máy vào một phép so.

### 3.2. `/leaderboard` — **chỗ khó nhất, và nó là câu hỏi khoa học chứ không phải UI**

479 dòng, xếp hạng **xuyên scenario**. HĐ-1.4 nói một khuyến nghị **chỉ có nghĩa trên một
deployment**. Một bảng xếp hạng toàn cục là đúng thứ điều khoản đó cấm.

Ba đường, và dev phải chọn:

| | được | mất |
|---|---|---|
| **Bỏ** | không còn một màn hình mâu thuẫn hợp đồng | mất cách nhìn tổng quan duy nhất đang có |
| **Đổi vai thành "danh mục Decision Card"** | liệt kê **các phép so đã chạy**, không xếp hạng xuyên deployment | phải viết lại gần hết |
| **Đóng băng** cho dữ liệu benchmark cũ | rẻ nhất | một màn hình đọc-được nhưng không được tin — kiểu tệ nhất |

### 3.3. `/scenarios` với `missions` của deployment — **hai định nghĩa của một thứ**

`Scenario` (cũ) = map + start/goal + vật cản tĩnh + robot + timeout.
`TaskProfile` (mới) = map + missions + robot + constraints + nhiễu + hardware.

Trùng: map, start/goal, robot, timeout. `MissionPlacer` đã rút ra dùng chung, nhưng **hai lược
đồ vẫn tồn tại song song** và `/scenarios/[id]` vẫn sửa cái cũ.

Đáng nói: scenario editor cũ có thứ form mới **chưa có** — vật cản tĩnh và vật cản động vẽ trên
canvas. Vật cản động đang là nợ đã ghi.

### 3.4. `/algorithms` với candidate — **thiếu một trang, không phải thừa**

`/algorithms` liệt kê registry stack. Luồng mới có khái niệm **candidate** (`POST /candidates`,
id là hash nội dung theo HĐ-1.3) nhưng **không có trang nào** cho nó. Người dùng gõ
`astar+dwa` / `dwa_coarse` vào hai ô text trong panel khởi chạy — không có gợi ý, không kiểm tra
trước khi gửi.

---

## 4. Phía backend: 80 với 20

| nhóm router | endpoint | số phận nếu tinh gọn |
|---|---:|---|
| `decisions` | 20 | **lõi luồng mới** |
| `benchmarks` · `tuning` · `algorithms` | 21 | bị thay |
| `models` · `agent` · `chat` | 28 | giữ, cắt ngang |
| `auth` · `users` · `reviews` | 16 | giữ, cắt ngang |
| `maps` · `scenarios` · `library` | 20 | **giữ, đổi vai** — đã thành nguồn dựng deployment |
| `simulations` · `episodes` · `ws` | 12 | giữ nếu `/simulate` đổi vai thành sân thử |

---

## 5. Ba câu hỏi tôi **không** tự trả lời được

Chúng là quyết định sản phẩm/khoa học, không phải kỹ thuật:

1. **`/leaderboard` đi đường nào** trong ba đường ở 3.2?
2. **Dữ liệu benchmark cũ**: migrate sang `decision_runs`, hay đóng băng đọc-thôi, hay xoá? Có
   bao nhiêu benchmark cũ đáng giữ?
3. **`robot-profiles`** trùng khối `robot` trong task profile — một trong hai phải thành nguồn
   sự thật. Cái nào?

---

## 6. Hình dạng tôi nghiêng về, để dev có cái phản biện

**Không phải "xoá luồng cũ".** Phần lớn luồng cũ đã **đổi vai** một cách tự nhiên: map, library,
scenario giờ là **nguyên liệu** dựng deployment. Việc còn lại là làm cho **điều hướng nói đúng
điều đó**.

```
LÀM GÌ        Deployments   khai một thế giới để đo          (form)
              Simulate      thử một episode trên nó          (đổi vai: sân thử)
              Decisions     chạy phép so, đọc kết quả, duyệt

NGUYÊN LIỆU   Maps · Library · Candidates(mới) · Models

TÀI KHOẢN     Reviews · System · Agent
```

Ba mục theo **việc người dùng đang làm**, không theo **hệ thống nào sinh ra màn hình**. Ba trang
biến mất khỏi sidebar (`Scenarios` gộp vào Deployments, `Benchmarks` vào Decisions,
`Leaderboard` chờ quyết định 3.2), một trang xuất hiện (`Candidates`).

**Việc rẻ nhất và đáng làm sớm nhất, bất kể chọn đường nào:** sắp lại `NAV_SECTIONS` theo trục
"việc" và thêm một dòng mô tả cho mỗi mục. Nó không đụng một endpoint nào và nó xoá đúng cái chi
phí lớn nhất ở mục 2.

---

## 7. Ba câu hỏi — **dev trả lời 2026-08-13**

### 7.1. `/leaderboard` → **đổi vai thành danh mục Decision Card**

Đường thứ hai trong ba đường ở mục 3.2, và là đường đắt nhất về công viết lại. Đáng, vì hai
đường kia đều để lại một vết:

- *Bỏ* thì mất cách nhìn tổng quan duy nhất đang có, mà nhu cầu "cho tôi xem tất cả những gì đã
  đo" là nhu cầu thật.
- *Đóng băng* cho một màn hình **đọc được nhưng không được tin** — kiểu tệ nhất, vì không có gì
  trên màn hình nói cho người đọc biết nó không được tin.

**Ràng buộc phải giữ khi viết lại, và nó là toàn bộ lý do đổi vai:** trang mới **không được xếp
hạng xuyên deployment**. HĐ-1.4 nói một khuyến nghị chỉ có nghĩa trên **một** deployment. Nên nó
liệt kê các **phép so đã chạy** — mỗi dòng là một Decision Card với deployment của nó — chứ
không gộp điểm của hai deployment vào một thứ hạng.

Chỗ dễ trượt: một cột "decision utility" sắp xếp được sẽ **tái tạo đúng bảng xếp hạng vừa bỏ**,
chỉ khác cái tên. `decision_utility` chỉ so được **trong** một deployment.

### 7.2. Benchmark cũ → **KHÔNG migrate** *(dev đảo lại sau khi thấy con số, và đúng)*

Quyết định đầu là *migrate sang `decision_runs`*. Đếm thật trong `planbench.db` thì:

| bảng | dòng |
|---|---:|
| `benchmarks` | **1** |
| `decision_runs` | 10 |
| `maps` · `scenarios` · `episodes` | 21 · 20 · 6 |

**Một dòng duy nhất**: `dwa-baseline`, tạo `2026-08-12T15:27`, 3 seed, hai stack `astar+dwa` và
`rrtstar+dwa`. Không phải dữ liệu lịch sử — đó là **một lần bấm thử luồng cũ trong chính phiên
MVP**, và luồng mới đã đo lại đúng cặp candidate đó tử tế hơn nhiều.

**Ba việc phải làm để migrate không phải chi phí kỹ thuật — chúng là ba lần phải bịa ra một sự
thật:**

| phải quyết | vì sao mọi câu trả lời đều là bịa |
|---|---|
| `contracts_version` nào? | Nó sinh ra **không dưới hợp đồng nào**. Mọi giá trị viết vào là một tuyên bố về điều kiện đo mà không ai kiểm được |
| `task_profile_id` nào? | Nó khoá theo `scenario_name`. Dựng một deployment tổng hợp là **khai một thế giới không ai từng triển khai** |
| Sáu cổng ra sao? | Nó chạy **trước khi sáu cổng tồn tại**. Không có phán quyết nào để chép |

Và cái giá không nằm ở công sức: sau khi migrate, `decision_runs` có **mười một dòng trông giống
nhau** mà một dòng không được tin — và **không gì trên màn hình nói được là dòng nào**.

**Chốt:**

- **Không migrate.** `benchmarks` (và `tuning`, phần cũ của `algorithms`) nghỉ cùng luồng cũ.
- **Không xoá dữ liệu.** Bảng cũ để nguyên trong DB — nó đã gitignore, một dòng, không tốn gì.
  Xoá bảng là một việc dọn dẹp riêng, khi nào dev muốn.
- **Giữ nguyên** `maps` · `scenarios` · `episodes`: chúng là **nguyên liệu**, không phải kết quả.

Quyết định này làm nhẹ hẳn 7.1: danh mục Decision Card **không phải gánh dữ liệu cũ nào**, chỉ
đọc `decision_runs` — đúng mười dòng, tất cả sinh dưới hợp đồng.

### 7.3. `robot-profiles` là nguồn sự thật — **nhưng có một ranh giới phải vạch**

Đọc hai lược đồ cạnh nhau thì chúng **không phải hai bản sao của một thứ**:

| trường | `RobotProfile` (cũ) | `TaskRobotSpec` (mới) |
|---|:--:|:--:|
| `radius` · `max_linear_velocity` · `max_angular_velocity` | ✅ | ✅ |
| `footprint` · `lidar_beams` · `lidar_range` · `observation_type` · `action_type` | ✅ | — |
| `max_linear_acceleration` · `max_angular_acceleration` | — | ✅ |
| **`control_period`** | — | ✅ |

Ba nhóm, ba số phận khác nhau:

- **Phần chung + phần chỉ có ở `RobotProfile`** → về `robot-profiles`. Đúng ý dev: đây là **cái
  xe**.
- **Gia tốc** → `RobotProfile` **đang thiếu**, mà simulator cần. Phải thêm vào đó.
- **`control_period` → KHÔNG được chuyển.** Nó không phải thuộc tính của xe. Docstring của nó
  nói thẳng: *"T_cycle của deployment — ngân sách wall-clock cho một bước điều khiển trên bo
  mạch đích. Nó là nguồn ngưỡng của cổng G4"*. Cùng một con robot ở hai hiện trường có thể bị
  đòi hai chu kỳ khác nhau, và **G4 chấm theo cái deployment đòi**.

Nên phát biểu chính xác của quyết định này là: **`robot-profiles` là nguồn sự thật về CHIẾC XE;
`task_profile.robot` giữ lại đúng thứ DEPLOYMENT ĐÒI Ở chiếc xe đó** — hôm nay là
`control_period`, và chỉ nó.

Chuyển `control_period` sang `robot-profiles` sẽ làm ngưỡng G4 thành thuộc tính của xe, và hai
deployment dùng chung một xe sẽ **không thể** đặt hai yêu cầu thời gian thực khác nhau — mất
đúng thứ HĐ-7 sinh ra để đo.

Còn một chồng lấn thứ hai cùng họ: `lidar_beams`/`lidar_range` ở `RobotProfile` với `LidarConfig`
ở `Scenario`. Cùng câu hỏi, cùng câu trả lời: cảm biến là **của xe**.

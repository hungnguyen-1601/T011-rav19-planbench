# Nợ kỹ thuật còn tồn đọng — kiểm kê 2026-08-13

**Nguồn:** `docs/KNOWN_LIMITATIONS.md` (L1–L6) · plan 12-08 mục C và E · report 12-08 mục 5 ·
report 13-08 mục 8 · quét mã và artifact ngày 13-08.

**Cách đọc:** xếp theo **cái gì hỏng nếu không trả**, không theo thứ tự thời gian. Cột "ai gây"
phân biệt nợ có từ trước với nợ tôi vừa tạo ra — để không ai phải đoán.

Quét mã: **không có `TODO`/`FIXME`/`XXX`/`HACK` nào** trong `packages/`, `apps/`, `services/`,
`scripts/`. Bốn `pytest.skip` đều có điều kiện môi trường, không phải test rỗng. Nợ dưới đây là
nợ **thiết kế và đo lường**, không phải mã bỏ dở.

---

## A. Nợ làm yếu tuyên bố khoa học *(nặng nhất)*

### A1. Chưa có adapter `MonolithicPolicy` — và bất cân xứng lưới replan đi kèm

`build_planners` từ chối candidate `monolithic`; chỉ `modular` chạy được. Hệ quả: tuyên bố
*"nền tảng công bằng cho mọi thuật toán"* mới được chứng minh trên **hai global planner cùng
kiểu tìm đường trên lưới với một local controller**. Phép thử thật của tuyên bố đó chưa chạy.

Đi kèm và **phải làm cùng lượt**: `nav_stack._replan` dựng lưới quy hoạch tạm với **vị trí thật**
của vật cản động. Hôm nay công bằng vì mọi candidate đều `modular`. Ngày adapter chạy được, một
policy end-to-end chỉ thấy `Observation` còn stack modular thấy vật cản **thật sự ở đâu** — đúng
đặc quyền G6 sinh ra để định giá, và nó ưu ái stack modular vì lý do không liên quan tới chất
lượng điều hướng. HĐ-4.1 đã ghi luật: gỡ đặc quyền **trước** khi chấm candidate `monolithic`.

`test_only_modular_stacks_can_run_today` sẽ đỏ đúng ngày adapter được thêm — hàng rào đã đặt sẵn.

| | |
|---|---|
| Nguồn | L2 · plan 12-08 mục C1 |
| Ai gây | có từ trước |
| Ước lượng | 1–2 ngày |

> **Cập nhật 13-08 — tách đôi và trả gần hết.** Kiểm ra hai nửa **không** phải làm cùng lượt như
> bản kiểm kê này viết:
>
> - **A1a — đặc quyền lưới replan: ✅ đã gỡ**, hợp đồng lên **6.6.0**. Replan giờ dựng lưới từ
>   chính tia LiDAR robot nhận được. Không đổi số liệu nào đã lưu (replanning tắt trong mọi lượt
>   chạy của tầng quyết định).
> - **A1b — adapter: ✅ phía simulator**, `MonolithicPolicy` + `run_policy` + một policy tham
>   chiếu, 12 test. Một policy chạy được qua **cùng vòng lặp**, không cầm path, không bị tính
>   tiền tìm kiếm toàn cục.
> - **Còn nợ: registry policy.** Biến `Candidate(type="monolithic")` thành policy chạy được cần
>   một registry khoá theo `PolicyComponent.name` và cách phân giải `checkpoint` ra trọng số.
>   Monolithic candidate hôm nay **khai được mà chưa dựng được**.
> - **Việc phải đọc trước khi so policy với modular:** G6 định giá `observation_requirements`,
>   mà mọi candidate từ trước tới nay đều khai **cùng một bộ** — nên điều khoản đó **chưa từng
>   định giá một chênh lệch thật nào**.

### A5. Registry policy — nửa còn lại của A1b *(mới, 13-08)*

Adapter phía simulator xong (`MonolithicPolicy`, `run_policy`). Cái chưa có là bước **trước** đó:
biến `Candidate(type="monolithic")` thành một policy chạy được.

Cần hai thứ, và chúng là một cặp:

1. **Registry policy** khoá theo `PolicyComponent.name`, song song với registry stack đang có.
2. **Phân giải `PolicyComponent.checkpoint`** ra trọng số — đường dẫn, hash, hay tham chiếu tới
   model registry đã có ở `apps/api` (`model_registry.py` đã lưu và băm được file model, nên
   nhiều khả năng nối vào đó chứ không dựng cái thứ hai).

Hôm nay một monolithic candidate **khai được mà chưa dựng được**, và `stack_id_for` là chỗ lời
khai dừng lại — thông điệp từ chối ở đó đã nói đúng cái gì còn thiếu.

**Việc phải làm cùng lượt, không phải sau:** G6 định giá `observation_requirements`, mà **mọi
candidate từ trước tới nay đều khai cùng một bộ** (`[lidar_2d]`). Nghĩa là điều khoản định giá
quan sát **chưa từng phải định giá một chênh lệch thật nào** — nó xanh vì chưa bị thử, không vì
đã đúng. Policy đầu tiên khai khác đi sẽ là phép thử thật đầu tiên của nó, và phát hiện một lỗi
định giá **sau khi** đã công bố một phép so là quá muộn.

| | |
|---|---|
| Nguồn | A1b, 13-08 |
| Ai gây | có từ trước (A1b chỉ làm lộ ra ranh giới) |
| Chặn | candidate `monolithic` thật; và cùng với nó là tuyên bố "công bằng cho mọi thuật toán" |

### ~~A2. `robustness_margin` null~~ — **không phải nợ**, chuyển sang tính năng *(dev chốt 13-08)*

Bộ sinh biến thể đã xong 13-08. Phần chạy K sweep để điền `robustness_margin` chuyển sang
[danh sách tính năng có thể thêm](tongduyan_tinh-nang-co-the-them.md) mục **F1**.

Lý do phân loại lại, và nó đúng: HĐ-12 khai `robustness_margin` là `float | None` và null **đã
có nghĩa được định nghĩa** — *"chưa đo"*. Card hiện tại vì thế **trung thực**, không tuyên bố
một độ bền nó chưa đo. Không có gì đang sai; có một câu hỏi chưa được hỏi. Nợ là thứ **đang
sai so với điều đã tuyên bố**, và đây không phải.

<details><summary>Nguyên văn mục ban đầu</summary>

Kiểm tám card trong `artifacts/runs/`: `robustness_margin: None` ở tất cả. Theo HĐ-12 null nghĩa
là *"chưa đo"*, nên các card **trung thực nhưng thiếu**.

Cần **Task Neighborhood** (N5): sinh K biến thể quanh profile gốc (đề xuất K = 20), đo
`R = (số biến thể khuyến nghị không đổi) / K`. Dưới 60% ⇒ card đổi nhãn thành
`NEAR-EQUIVALENT`. Tài liệu đề tài gọi đây là **điểm khác biệt học thuật mạnh nhất của dự án** —
không nền tảng nào khác đo độ bền của *kết luận* trước nhiễu đầu vào.

Bốn trục nhiễu còn thiếu của bảng N5: dịch start/goal ±1 m ±15° · dịch vật cản tĩnh ±0,3 m xoay
±10° · mật độ vật cản động ±20% tốc độ 0,8–1,4 m/s · `v_max` ±10%.

| | |
|---|---|
| Nguồn | N5 · plan 12-08 mục E |
| Ai gây | có từ trước |

</details>

### A3. Robot đang định vị **hoàn hảo** *(phát hiện 13-08)*

`engine.py:262-268` — `Observation(pose=self._robot.pose)`. Stack nhận **pose thật**. LiDAR đọc
sai, bánh trượt thật, nhưng robot **luôn biết chính xác mình ở đâu**.

Cả một họ thất bại có thật không tồn tại trong mô phỏng: localisation nhảy, drift tích luỹ,
robot tự tin lái vào tường. Đây là **lỗ hổng của mô hình**, không phải tính năng còn thiếu — nó
làm simulator lạc quan hơn thực tế theo đúng cách `noise.py` được viết ra để sửa.

Kèm theo, cùng họ: **LiDAR chưa có mất tia**. Kính, bề mặt tối, gương trả về **không gì cả**;
costmap đọc "trống" và lái thẳng vào. Đây là cách robot thật đâm cửa kính.

Và: trượt bánh hiện **zero-mean mỗi bước** nên sai số **triệt tiêu**. Bánh mòn không đều là lệch
**một chiều**, nó **tích luỹ** — hai kiểu hỏng khác nhau hoàn toàn, mới mô phỏng một.

| | |
|---|---|
| Nguồn | quét mã 13-08 |
| Ai gây | có từ trước, chưa ai ghi ra |
| Ghi chú | dev chốt 13-08: đưa vào plan dài hạn, làm sau nợ kỹ thuật |

### A4. Chưa có map **vừa khó vừa đối xứng**

`open_hall` đối xứng nhưng dễ; kho khó nhưng **chưa có kiểm đối xứng nào**. Một map vừa khó vừa
đối xứng là phép kiểm mạnh hơn cả hai.

> **SỬA 13-08 — câu dưới đây trong bản đầu là SAI, tôi viết ra mà không chạy thử.**
>
> Bản đầu viết: *"`tests/test_fairness.py:310` **skip** vì `maps/` không có file đó, nghĩa là bộ
> test công bằng đang không chạy"*, và tôi xếp nó thành việc đáng làm sớm nhất trong ba việc.
>
> **Chạy thử thì: `tests/test_fairness.py` — 22 passed, 0 skipped.** `maps/open_hall.pgm` **có
> trong repo**. Dòng `pytest.skip` ở đó là một cái chốt phòng khi map bị thiếu, và nó **chưa
> từng nổ**. Chạy thêm `test_difficulty.py` và `test_hostinfo.py` — hai file còn lại tôi liệt kê
> là "skip có điều kiện" — cũng **84 passed, 0 skipped**.
>
> Sai ở đâu: tôi `grep` ra dòng `pytest.skip` rồi **suy ra** nó đang nổ, thay vì chạy file đó.
> Đúng cái kiểu suy luận mà cả dự án này tồn tại để chặn. Sáu `skipped` trong full suite đến từ
> `importorskip` cho dependency tuỳ chọn (`langgraph`, `optuna`, `gymnasium`), không liên quan.

**Nợ thật sự còn lại của mục này**, sau khi bỏ phần sai: `open_hall` đối xứng nhưng **dễ**, kho
khó nhưng **chưa có kiểm đối xứng nào**. Một map vừa khó vừa đối xứng vẫn chưa có, và nó vẫn là
phép kiểm mạnh hơn cả hai — nhưng đây là việc **thêm một dụng cụ đo**, không phải vá một lỗ
hổng đang chảy.

| | |
|---|---|
| Nguồn | plan 12-08 mục C2 |
| Ai gây | có từ trước |
| Ước lượng | nửa ngày |
| Mức độ gấp | **hạ xuống** — không có gì đang bị bỏ qua như tôi tưởng |

---

## B. Nợ về con số và ngưỡng

### B1. `success_rate_min` của sảnh = 0.95, **và con số đó được biết là sai** (L6)

Giá trị đúng theo lập luận là **1.00** — sảnh là deployment nghiệm thu, một failure là tín hiệu
chẩn đoán chứ không phải thống kê. Ngày 11-08 đã đổi sang 1.00, ngày 12-08 **lùi lại**: luật 2
của HĐ-8.3 buộc `bad` của anchor trỏ vào chính ngưỡng ấy, nên 1.00 làm `good == bad`, thang sập,
deployment mất khả năng xếp hạng (HĐ-8.4), và tấm Decision Card duy nhất không tái lập được.

**Cơ chế đã có** (HĐ-8.4 xử lý 1.00 tử tế, có test). **Việc còn lại là quyết định**, không phải
hiện thực. Ba hướng chưa xét kỹ: tách ngưỡng cổng khỏi neo `bad`; cho anchor khai `bad` dự
phòng khi ngưỡng chạm trần; hoặc chấp nhận sảnh chỉ gác cổng và chuyển xếp hạng sang A4.

**Không được đọc 0.95 như một câu trả lời.**

### B2. Kho chưa khai `sensor_noise` — σ = 0

Kiểm `warehouse_a_v2.yaml`: khối `sensor_noise` **không tồn tại**. Với planner tất định, khai
vào là phải sinh `warehouse_a_v3` (HĐ-13: đổi nhiễu là đổi thế giới, đổi id).

Đáng lo hơn con số: kho **có** vật cản động nên episode vẫn phân biệt được — nhưng đó là may,
không phải thiết kế. Sảnh không có traffic và sống nhờ nhiễu; kho có traffic và sống nhờ nó. Hai
deployment đang dựa vào hai cơ chế khác nhau mà không ai khai điều đó ra.

---

## C. Nợ đo lường — phép đo chưa chạy

| nợ | trạng thái | chặn cái gì |
|---|---|---|
| **Kho ở mức 1%** | dừng ở **245/300**, dev chủ động dừng; cả hai candidate trượt G2+G3 | Chưa có kết luận nào trên deployment **thật** duy nhất. Mọi kết luận hiện có đều trên sảnh, mà sảnh là **dụng cụ đo** chứ không phải khách hàng |
| **`astar+ppo`** | trong registry, `benchmarkable=True`, **chưa từng vào phép so nào** | Candidate đầu tiên có **lớp quan sát khác** hai stack cổ điển ⇒ phép thử thật đầu tiên của G6 và P02. Cần `torch` + checkpoint |
| **G4/G5 trên bo mạch đích** | chỉ xác nhận trên máy benchmark | Dự án **không có** Jetson Orin Nano hay board ARM nào. Bảo lưu HĐ-7.2/7.3 |
| **Decision Card trên nền đã kiểm** | bốn candidate, **một** qua cổng | L3 |

---

## D. Nợ trong mã và giao diện

### ~~D1. Test chống trôi lược đồ~~ — **đã trả 2026-08-13**

`tests/test_form_covers_the_contract.py`, 10 test. Chi tiết ở report 13-08 mục 9. Đã chứng minh
nó đỏ khi phải đỏ bằng cách thêm tạm một trường vào `TaskProfile`, không chỉ tin là nó sẽ đỏ.

Năm trường được miễn trừ, mỗi trường kèm lý do trong `NOT_IN_THE_FORM`, và ba test phụ giữ cho
chính danh sách đó không mục.

<details><summary>Nguyên văn mục nợ ban đầu</summary>

Plan 13-08 mục 4 gọi đây là **test đáng giá nhất của cả đợt**, và tôi không làm.

Thêm một trường vào `TaskProfile` mà form lặng lẽ bỏ sót là kiểu hỏng **không gì bắt được**:
suite vẫn xanh, form vẫn khai được, và deployment sinh ra thiếu đúng trường mới. Cần một test
duyệt `TaskProfile.model_fields` (kể cả model lồng) và bắt mọi trường **hoặc** có trong form
**hoặc** nằm trong danh sách hoãn kèm lý do.

**Ước lượng:** 1–1,5 giờ. Nên trả trước tiên trong nhóm D.

</details>

### ~~D2. Hai test web đỏ~~ — **đã trả 2026-08-13**, và nó lòi ra một bug sản phẩm

Chi tiết ở [report trả nợ](../../reports/2026-08-13/tongduyan_tra-no-ky-thuat.md). Tóm tắt:

- `dashboard-page` — đúng là dấu phân cách Windows. Sửa bằng một hàm chuẩn hoá `sep`.
- `assistant-page` — **không phải lỗi Windows**. Nó đọc `models/page.tsx` ở mức module; file
  không có nên đọc ném lúc collect và **kéo theo 27 test khác trong cùng file**. Chúng chưa
  bao giờ chạy.
- **`/models` chưa từng tồn tại trong lịch sử git**, trong khi `navigation.ts` link tới nó từ
  đầu và backend đã xong. Người dùng bấm vào mục đó nhận **404**. Quét 17 href: đúng một link
  chết.

Suite web: **613 passed, 31/31 file — xanh hoàn toàn lần đầu.** +26 test, **không cái nào là
test mới** — chúng có từ lâu, giờ mới thôi bị che.

**`/models`: dev chốt để nguyên**, là phần việc của người khác. Không thêm test nào giám sát
khu vực đó (bản nháp đầu của tôi có một test nav quét link chết — bỏ, vì nó đỏ vào mặt người
không gây ra nó). Ba yêu cầu của trang giữ trong report cho người sẽ xây. Ghi lại một điều để
không rơi: **sidebar vẫn dẫn tới một trang không tồn tại.**

### D3. Không có gì **chặn** hai run đánh giá chạy song song

Ghim nhân đã cưỡng chế trong mã, nhưng ràng buộc HĐ-7.4 chỉ tồn tại như một **điều khoản**.
Hàng đợi API giữ đúng một job, nhưng CLI thì không biết gì về hàng đợi đó. Hai tiến trình cùng
ghim sẽ giành đúng hai nhân đầu và G4 đo một cái máy không tồn tại. Một cờ file khoá là rẻ.

### D4. Nợ nhỏ hơn, ghi để không rơi

| | |
|---|---|
| `instance_difficulty` | chưa nối vào tầng quyết định (cache P03 khoá theo `scenario_name` cũ) |
| `business_adjusted` | có anchor tiền nhưng **chưa demo được** hai chân trời lật khuyến nghị (N3) |
| `dynamic_obstacles` trong form | hoãn theo chốt của dev; lối thoát là tab YAML |
| `available_observations` | mọi profile khai `[lidar_2d]`, form chưa có ô |
| Luồng cũ | 80 endpoint vẫn sống song song. Lý do kỹ thuật cản việc thay thế **đã hết**; còn lại là việc phải làm, và ba câu hỏi chưa trả lời: dữ liệu benchmark cũ migrate hay đóng băng · `leaderboard` dựng trên Decision Card thì nghĩa là gì (xếp hạng xuyên deployment mâu thuẫn HĐ-1.4) · `robot-profiles` trùng khối `robot` trong task profile, một trong hai phải thành nguồn sự thật |

---

## Thứ tự đề xuất

Xếp theo **rẻ × chặn nhiều**, không theo mức độ hấp dẫn:

```
D1 test chống trôi lược đồ   ✅ TRẢ 13-08
D2 hai vệt đỏ thường trực    ✅ TRẢ 13-08 — lòi ra /models là link chết
A4 map vừa khó vừa đối xứng  (nửa ngày) ← THÊM dụng cụ đo, không phải vá lỗ hổng
                                          (bản đầu tôi xếp nó gấp vì một chẩn đoán SAI)

A1a đặc quyền lưới replan    ✅ TRẢ 13-08 — hợp đồng lên 6.6.0
A1b adapter (phía simulator) ✅ TRẢ 13-08
A5  registry policy + G6     ← nửa còn lại, phải làm cùng lượt với định giá quan sát
        │
B1 quyết định ngưỡng sảnh    (quyết định, không phải code)
B2 warehouse_a_v3 khai nhiễu (~1 h + giờ máy)
        │
C  chạy cho đủ: kho 300 episode, astar+ppo
        │
A1 adapter monolithic + lưới replan   (1–2 ngày)
A2 Task Neighborhood ⇒ robustness_margin
A3 định vị + mất tia + lệch odometry  ← dev chốt: plan dài hạn
```

D1 và D2 đã trả, và **D2 là dòng đáng tiền nhất**: nó không thêm test nào mà làm 26 test có sẵn
thôi bị che.

**A4 đã bị hạ mức gấp** sau khi chẩn đoán lại — xem khối SỬA ở mục A4. Bài học rút cho chính bản
kiểm kê này: **`grep` ra một dòng `pytest.skip` không có nghĩa là nó đang nổ.** Mọi mục còn lại
trong bản này nêu một hành vi lúc chạy thì phải chạy thử trước khi xếp mức gấp; những mục nêu
một thứ **vắng mặt** (adapter monolithic, `robustness_margin` null, kho chưa khai nhiễu) thì đã
kiểm bằng cách đọc mã và đọc artifact, không suy diễn.

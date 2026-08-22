# Trả nợ kỹ thuật — đợt 13-08

**Kiểm kê nguồn:** [`notes/2026-08-13/tongduyan_no-ky-thuat-ton-dong.md`](../../notes/2026-08-13/tongduyan_no-ky-thuat-ton-dong.md)
**D1** (test chống trôi lược đồ) nằm ở [report form, mục 9](tongduyan_khai-deployment-bang-form.md)
vì nó trả nợ do chính đợt form tạo ra. Từ đây là các mục còn lại.

---

## D2 — hai vệt đỏ thường trực

Tôi đã gọi hai test này là *"lỗi có sẵn từ trước, không liên quan"* **ba lần liên tiếp** mà
không chẩn đoán. Chẩn đoán ra thì chúng là **hai nguyên nhân khác hẳn nhau**, và cái thứ hai
không phải lỗi test.

### D2a. `dashboard-page` — dấu phân cách Windows

```
AssertionError: expected [ '\system\page.tsx' ] to deeply equal [ '/system/page.tsx' ]
```

`join()` cho `src\app\system\page.tsx` trên Windows, so với chuỗi POSIX viết tay thì trượt vì
một lý do **không liên quan gì tới điều đang được khẳng định** (rằng `API_BASE` chỉ xuất hiện ở
đúng một trang). Test này đỏ trên Windows **từ ngày nó được viết**.

Sửa: một hàm `asRoute()` chuẩn hoá `sep` về `/`. Khẳng định giữ nguyên từng chữ.

### D2b. `assistant-page` — **27 test chưa từng chạy**

Đây mới là chỗ đáng kể, và nó không phải lỗi Windows.

```
Error: ENOENT: no such file or directory, open '…/apps/web/src/app/models/page.tsx'
  ❯ src/app/__tests__/assistant-page.test.tsx:134:20
```

`describe("the model registry page")` đọc file **ở mức module**. File không có ⇒ đọc ném lúc
collect ⇒ vitest báo **một suite hỏng** và **kéo theo toàn bộ 27 test còn lại trong file**.

Chúng chưa bao giờ chạy. Suite web vẫn báo "xanh trừ hai lỗi có sẵn", và hai chữ "có sẵn" đã che
27 test suốt thời gian đó.

### D2c. Và vì sao file đó không có: **`/models` chưa từng tồn tại**

```
$ git log --all -- apps/web/src/app/models/page.tsx
(không có gì)
$ grep -n models apps/web/src/lib/navigation.ts
46:  { href: "/models", labelKey: "nav.models", icon: "library", session: true },
```

Trang **chưa từng nằm trong lịch sử git** — không phải bị xoá, mà là **chưa bao giờ được xây**.
Trong khi đó sidebar đã link tới nó từ đầu, và backend thì **đã xong** (`routers/models.py`,
`model_registry.py`).

Nghĩa là: **người dùng bấm vào mục Models trong sidebar sẽ nhận 404.** Đây là bug sản phẩm, và
nó nấp sau một lỗi collect suốt thời gian qua.

Quét toàn bộ 17 href trong `navigation.ts`: **đúng một** link chết, là `/models`.

### Sửa thế nào — **dev chốt: `/models` là việc của người khác, không can thiệp**

Bản nháp đầu tiên của tôi đi xa hơn thế: chuyển ba khẳng định thành một mục `MISSING_PAGES` kèm
lý do, và **thêm một test quét mọi href trong sidebar phải có trang**.

Dev bác, và bác đúng. Cái test nav ấy **giám sát khu vực của người khác**: nó biến "sidebar có
link tới trang chưa xây" thành một điều kiện mà workstream khác phải thoả mãn, trong khi quyết
định *xây trang hay gỡ link* không thuộc về đợt việc này. Một test như thế đỏ lên là đỏ vào mặt
người không gây ra nó.

**Đã làm cuối cùng, đúng phạm vi:**

- Bỏ khối `/models` khỏi file test. Không `describe.skip` — một test bị tắt trông như một test
  đang chạy, và đó là mùi hoàn-thành-giả.
- Không thêm test nav nào. File này **không khẳng định gì** về `/models`, kể cả chuyện sidebar
  có nên link tới nó hay không.
- Một comment tại chỗ nói khối đó từng ở đây, vì sao nó làm hỏng collect, và **đặc tả ba yêu
  cầu chuyển sang report này** cho người sẽ xây trang.

Ba yêu cầu đó, giữ lại nguyên vẹn ở đây:

> Trang model registry, khi được xây, phải: **giải thích PPO là gì** (`models.whatIsPpo`) ·
> **có empty state chứ không phải lỗi** khi chưa upload gì (`models.empty.title`) · **không bao
> giờ hiện vị trí lưu trữ** (không `storage_key`, không `model_path`) — cái cuối là toàn bộ lý
> do có một registry.

Backend đã sẵn sàng: `routers/models.py`, `model_registry.py`.

---

## Kết quả

| | trước D2 | sau D2 |
|---|---:|---:|
| Test file web | 29/31 pass, **1 fail + 1 không collect được** | **31/31** |
| Test web | 587 passed, 1 failed | **613 passed, 0 failed** |

**Lần đầu suite web xanh hoàn toàn** trong cả loạt việc này. +26 test so với trước, và **không
một cái nào là test mới** — chúng là test đã có từ lâu, giờ mới thực sự chạy. Đây là kiểu "tăng
số test" đáng giá nhất: không viết thêm gì, chỉ thôi che.

`tsc --noEmit` sạch. Chưa chạy full suite backend — dev chốt để sau.

---

## Còn lại trong hàng đợi

- **A4 — chẩn đoán ban đầu của tôi SAI, đã sửa trong bản kiểm kê.** Tôi viết rằng
  `tests/test_fairness.py` đang skip vì thiếu map. Chạy thử: **22 passed, 0 skipped**;
  `maps/open_hall.pgm` có trong repo và dòng `pytest.skip` đó chưa từng nổ. Tôi `grep` ra dòng
  skip rồi **suy ra** nó đang nổ thay vì chạy file — đúng kiểu suy luận cả dự án này tồn tại để
  chặn. Nợ thật còn lại là *"chưa có map vừa khó vừa đối xứng"*, và đó là **thêm một dụng cụ
  đo** chứ không phải vá lỗ hổng, nên **hạ mức gấp**.
- **`/models` — đóng, không phải việc của đợt này.** Dev chốt 13-08: phần việc của người khác,
  để nguyên. Ba yêu cầu của trang ghi ở mục D2c trên cho người sẽ xây. Ghi lại ở đây một điều
  duy nhất, không phải để đòi ai làm gì mà để nó không rơi: **sidebar hiện vẫn dẫn tới một
  trang không tồn tại**, và người dùng bấm vào sẽ nhận 404.
- Phần còn lại theo thứ tự trong bản kiểm kê.

---

## A1a — gỡ đặc quyền thông tin của lưới replan

### Phát hiện chia đôi món nợ

Bản kiểm kê ghi A1 là *"adapter monolithic + bất cân xứng lưới replan, **phải làm cùng lượt**,
1–2 ngày"*. Kiểm trước khi gõ thì hai nửa **tách được**, và nửa đầu rẻ hơn nhiều:

`run_contract_episode` gọi `run_stack` **không truyền `replanning`**, và
`ReplanningConfig.enabled` mặc định **False**. Nghĩa là **replanning tắt trong mọi lượt chạy
của tầng quyết định** — `_replan` chưa từng nổ ở đó. Mọi trace, mọi phán quyết cổng, mọi Decision
Card đã có đều sinh ra mà không có một lần replan nào.

Hệ quả: **sửa `_replan` không đổi một con số nào đã lưu.** Không phải đo lại gì. Đặc quyền chỉ
cắn khi có người bật replanning **và** so một monolithic với một modular — mà cái thứ hai chưa
tồn tại.

Nên A1 tách thành **A1a** (gỡ đặc quyền, tự chứa) và **A1b** (adapter, còn nợ). HĐ-4.1 nói phải
gỡ đặc quyền **trước** khi chấm monolithic, nên đúng thứ tự.

### Lời giải hợp đồng chỉ định sẵn

> **Luật:** trước khi bất kỳ candidate `monolithic` nào được chấm, đặc quyền này phải được gỡ,
> và lời giải hợp lệ là **replan từ `Observation`** — không phải cấp ground truth cho cả hai
> bên. Cấp cho cả hai chỉ đổi một phép so lệch thành hai phép đo sai.

Đã làm đúng thế. `_replan` trước đọc `engine.dynamic_obstacles_now()` (vật cản **thật sự** ở
đâu); giờ đọc `engine.get_observation()` và dựng bản đồ từ chính tia LiDAR robot nhận được.

Ba tính chất đi kèm, mỗi cái một lý do:

- **Tia chạm ngưỡng tầm xa bị bỏ.** Tia tới hạn nghĩa là *"trong tầm không có gì"*. Nung nó vào
  sẽ dựng một bức tường bằng sàn trống đúng ở khoảng cách cảm biến hết nhìn thấy, quây robot
  trong một cái vòng.
- **Nhiễu LiDAR giờ tới được planner** — đúng, và có chủ ý: robot đo tệ thì lập kế hoạch trên số
  đo tệ, đó chính là *đo tệ nghĩa là gì*. Nó vẫn **không** tới được phép kiểm va chạm, chỗ đó
  vẫn dùng hình học thật.
- **Mỗi tia đánh dấu đúng một ô.**

### Chỗ sai của bản đầu, và cách tìm ra

Bản đầu vẽ mỗi tia thành một **vòng tròn bán kính nửa đường chéo ô**. Bốn test replanning đỏ
ngay: `replan_count=0` — replan không ra được đường nào.

Không đoán. Chạy A* — **thuật toán đầy đủ** — trên đúng cái lưới ấy:

```
blockers      : 41  (radius 0.354 m)
cells blocked : 486  (chỉ tĩnh, đã inflate: 428)
A* trên CÙNG lưới : False   ← đầy đủ, nên đây không phải sampler xui
```

Đường **thật sự** bị chặn. Ở độ phân giải 0,5 m, vòng tròn 0,354 m **rộng hơn một ô**, nên bảy
mươi hai tia sơn thành từng khối 2×2; tường dày thêm một phần ba mét **trước** khi planner
inflate tiếp, hai cửa đóng lại, và A* báo không có đường qua một mét rưỡi sàn trống.

**Một phép đo được vẽ rộng hơn chính phép đo là một vật cản robot tự bịa ra.** Sửa: đánh dấu
đúng ô chứa điểm chạm. 24/24 test replanning xanh, tiền đề vẫn đứng — robot vẫn thoát bằng cửa
trên, chỉ bằng thứ nó nhìn thấy.

### Chốt chặn: viết lại cho khớp thực tế mới

`TestTheReplanGridIsAKnownInformationAsymmetry` mô tả một khiếm khuyết **chưa sửa**. Giờ nó giữ
cho khiếm khuyết đó **ở trạng thái đã sửa** — một lần "replan không nhìn qua góc được, thôi đọc
tạm vật cản" sau này là sửa một dòng và không có triệu chứng nào khác.

Ba test mới: replan không chạm ground truth · một tia đánh dấu một ô chứ không phải một mảng ·
tia tới hạn không đánh dấu gì.

**Test đầu tôi viết sai và chính nó bắt được.** Nó `grep` mã nguồn tìm `dynamic_obstacles_now`,
và đỏ vì chuỗi đó nằm trong **docstring** — chỗ kể lại lịch sử nên bắt buộc phải nhắc tên nó.
Sửa sang đọc `_replan.__code__.co_names`: danh sách thứ hàm **thật sự với tới**, nên một cái
comment không trip được nó mà cũng không giấu được gì khỏi nó.

### Xác minh

`test_simulator_fairness` · `test_replanning` · `test_fairness` · `test_nav_stack`: **109 passed,
1 skipped**.
`test_api_simulations` · `test_difficulty` · `test_benchmark_engine` · `test_engine` ·
`test_partial_runs`: **120 passed**.
`ruff` sạch, format sạch. Chưa chạy full suite — dev chốt để sau.

### Còn lại, và một câu hỏi cho dev

- **A1b — adapter `MonolithicPolicy`** vẫn là nợ. Sau lượt này nó là **thứ duy nhất** chắn giữa
  nền tảng và một candidate monolithic; đặc quyền replan từng đứng cạnh nó thì đã hết.
- **`contracts/CONTRACTS.md` HĐ-4.1 giờ mô tả một trạng thái đã qua.** Câu *"Hôm nay điều này
  công bằng vì mọi candidate chạy được đều là modular và nhận cùng một lưới"* không còn đúng —
  giờ nó công bằng vì **không ai được ground truth cả**. Luật thì vẫn nguyên và đã được thoả
  mãn. Tôi **không tự sửa** file hợp đồng: sửa nó đi kèm bump version và đó là quyết định của
  dev, không phải hệ quả của một lần sửa mã.

---

## Hợp đồng lên 6.6.0 — ghi lại chính việc A1a vừa làm

HĐ-4.1 viết ở 6.1.0 nêu **một luật** và **một việc phải làm** trước khi chấm candidate
`monolithic`. A1a làm việc đó, nên điều khoản được viết lại cho khớp: luật giữ nguyên từng chữ,
phần mô tả chuyển sang trạng thái *đã thoả mãn*, và đoạn lịch sử — vì sao nó từng sai — gập vào
`<details>` thay vì xoá. Một điều khoản kể được vì sao nó tồn tại thì lần sau không ai gỡ nhầm.

Câu cũ *"Hôm nay điều này công bằng vì mọi candidate chạy được đều là modular"* nay là:
**công bằng vì không ai được ground truth cả.**

MINOR, không MAJOR: không trường nào bị xoá, không ngữ nghĩa metric hay cổng nào đổi. Và **không
số liệu nào đã lưu bị ảnh hưởng** — `ReplanningConfig.enabled` mặc định False, tầng quyết định
không bật, nên `_replan` chưa từng chạy trong một lượt đánh giá nào.

Bump ở ba chỗ, vì test đòi cả ba: header văn bản, `CONTRACTS_VERSION`, và **hai ví dụ JSON trong
chính tài liệu** — `test_json_examples_quote_the_current_version` tồn tại để người copy ví dụ
không dán một version cũ vào mã mới.

---

## A1b — adapter `MonolithicPolicy`

### Chọn đường ít rủi ro, và nói rõ vì sao

Một policy end-to-end **không có global plan**, mà `run_stack` bắt buộc phải có một cái: không
có thì nó ghi `NO_GLOBAL_PATH` và dừng. Hai đường:

1. **Mổ vòng lặp** ra thành hàm dùng chung nhận `plan | None`. Đúng về mặt cấu trúc, nhưng là
   dịch 110 dòng của **lõi công bằng** — chỗ có hơn 100 test đứng canh.
2. **Một global planner không quy hoạch gì**, đặt vào đúng ô mà vòng lặp đòi.

Chọn (2). `_NoGlobalPlanning` báo cáo đúng sự thật: `success=True`, path rỗng, 0 giây, 0 node.

Ba chi tiết trong đó không phải tuỳ tiện:

| | |
|---|---|
| `success=True`, không phải `False` | `success=False` là cách vòng lặp ghi *"không tồn tại đường nào"*, và **G1 đếm đúng cái đó**. Một candidate chưa từng được yêu cầu tìm đường không được rơi vào ô đếm ấy |
| 0 giây, 0 node | Không phải chỗ điền tạm: candidate không chạy tìm kiếm toàn cục thì **không tiêu gì** cho nó, và tính cho nó một con số là định giá việc nó không làm |
| Tên là `policy`, không phải `none+policy` | Một lớp, một tên. `none+policy` đọc ra thành một stack **lỡ thiếu** global planner — khác hẳn một candidate **không có** global planner theo cấu tạo (HĐ-1.2) |

### `reset` **vứt** đường đi, và đó là điều khoản chứ không phải sơ ý

`MonolithicPolicy.reset(global_path, robot)` giữ tham số vì vòng lặp là chung — mà **chung vòng
lặp mới làm phép so thành phép so**: cùng đồng hồ, cùng `Observation`, cùng luật kết thúc.
Nhưng nó `del global_path` trước khi gọi `prepare(robot)`.

Nếu nhận, một policy lén nhìn global path sẽ **không phân biệt được** với một policy không nhìn
— và cái thứ nhất là một stack modular đeo nhãn policy. Có test đọc thẳng chuỗi `del
global_path` trong mã.

**Replanning không được cấp cho policy**, và không thể: replan thay một global path, policy thì
không có. Một budget ở đó là cái núm không có gì phía sau.

### Một policy tham chiếu, để có thứ chạy thật

`GreedyReferencePolicy` — lái về phía đích, chậm lại khi tia quét thấy vật cản gần. Chín dòng
lượng giác, **không bao giờ là candidate**, cùng luật `PurePursuitLocalPlanner` mang từ D12. Có
test đọc docstring để chắc cái nhãn đó còn ở đấy.

Nó tồn tại để đường end-to-end có thứ để lái. Chạy thật: **tới đích**, `plan.path == ()`,
`planning_time == 0`, `algorithm == "greedy_reference_policy"`.

### Còn thiếu gì — nói rõ, A1b **chưa xong hết**

Adapter phía **simulator** xong. Cái chưa có là bước trước đó: biến
`Candidate(type="monolithic")` thành một policy chạy được, cần **một registry policy** khoá theo
`PolicyComponent.name` và cách phân giải `PolicyComponent.checkpoint` ra trọng số.

Nên hôm nay một monolithic candidate **khai được mà chưa dựng được**, và `stack_id_for` là chỗ
lời khai dừng lại. Đã sửa thông điệp từ chối ở đó cho đúng sự thật mới — nó vẫn nói "chưa tồn
tại", nhưng giờ nói đúng **cái gì** chưa tồn tại.

Chốt chặn `test_only_modular_stacks_can_run_today` đổi tên thành
`test_a_monolithic_candidate_still_cannot_be_built` và thu hẹp về đúng phần còn lại. Thông điệp
khi nó đỏ giờ trỏ vào **định giá quan sát của G6**: mọi candidate từ trước tới nay đều khai cùng
một bộ `observation_requirements`, nên điều khoản đó **chưa từng phải định giá một chênh lệch
thật nào**. Đó là việc đọc trước khi so policy với stack modular.

### Xác minh

`test_monolithic_policy` (12 mới) · `test_simulator_fairness` · `test_replanning` ·
`test_nav_stack` · `test_candidate` · `test_contract_version`: **146 passed, 1 skipped**.
Thêm `test_candidate_bridge` · `test_compare`: **160 passed**.
`ruff` sạch, format sạch. Chưa chạy full suite — dev chốt để sau.

---

## A2 — Task Neighborhood: bộ sinh biến thể

`robustness_margin` **null trên cả tám** Decision Card đã kiểm. HĐ-12 đọc null là *"chưa đo"* —
trung thực, nhưng rỗng. Đây là nửa đo được mà **không** tốn hàng giờ máy: bộ sinh. Nửa còn lại —
chạy 20 sweep rồi đếm bao nhiêu lần khuyến nghị giữ nguyên — đắt theo cấu tạo.

### Hỏi một câu khác hẳn tập đánh giá, và hai cái này hay bị nhầm

| | Hỏi gì | Bất định về |
|---|---|---|
| Tập đánh giá | *"candidate này chạy thế nào trên nhiệm vụ tôi sẽ thật sự chạy?"* | **khối lượng công việc** |
| Neighborhood | *"nếu bản đồ và mô hình cảm biến tôi đưa bị lệch chút thì lời khuyên còn đúng không?"* | **chính dữ liệu đầu vào** |

Có mission distribution hoàn hảo vẫn cần cái thứ hai: bản đồ là một phép đo có sai số, và pallet
không nằm đúng chỗ trên bản vẽ.

### Bốn quyết định, mỗi cái chặn một kiểu hỏng

| quyết định | kiểu hỏng nó chặn |
|---|---|
| **`variant_id` là hash nội dung của perturbation**, không phải vị trí trong danh sách | *"biến thể 3"* của hai phiên bản bộ sinh sẽ là hai thế giới khác nhau dưới một cái tên — vô hình, vì cả hai lượt chạy đều trông như đã xong. Cùng họ với lý do `episode_context_id` tồn tại |
| **Tất định từ (profile, seed)** | Hai người hỏi vùng lân cận của cùng một deployment phải nhận cùng một vùng, nếu không `robustness_margin` không phải con số ai kiểm được |
| **`task_profile_id` giữ nguyên** | Biến thể là *cùng một deployment được hỏi một câu what-if*, không phải deployment mới. Cấp id mới là khai một deployment không ai triển khai, và lượt chạy của nó sẽ đọc ra như bằng chứng về một hiện trường thật. Episode phân biệt bằng `environment_variant` trong hash ngữ cảnh (HĐ-3.1) |
| **Phân bố đều, không Gauss** | Các trục mô tả một **khoảng** người ta chấp nhận sai — *"pallet nằm trong vòng một foot của bản vẽ"* — không phải phân bố sai số đo quanh một giá trị đúng. Gauss sẽ dồn phần lớn biến thể sát nominal và trả lời một câu hỏi nhẹ hơn câu được hỏi |

### Nhiễu được **nhân**, không được **tạo ra**

Kho khai `sensor_noise` = 0 (nợ B2). Bộ sinh nhân biên độ đã khai, nên với kho nó vẫn ra 0.
Deployment không khai nhiễu là deployment **chưa ai đo nhiễu**; bịa một biên độ cho nó ở đây là
trả lời về một thế giới tác giả không mô tả.

### Chỗ probe của tôi sai lại lộ ra một khoảng trống thật

Probe đầu đọc `motion.speed` của forklift và nổ: `PeriodicMotion` **không có** `speed`, nó có
`period`. Probe sai — nhưng nó chỉ đúng vào chỗ **bộ sinh cũng sai**: chuyển động `periodic`
diễn đạt tốc độ bằng chu kỳ, nên một bộ sinh chỉ chạm `speed` sẽ để **forklift của kho tham
chiếu hoàn toàn không bị nhiễu** trong khi report tuyên bố trục traffic đã được phủ.

Sửa: `periodic` nhân nghịch đảo vào `period`. Và kéo theo một ràng buộc phải giữ — HĐ-2 buộc
`seed_time_offset` của vật cản tuần hoàn phải **vượt trọn một chu kỳ**, nếu không mọi seed gặp
nó ở cùng một pha và một trăm episode co lại còn một. Chu kỳ dài ra mà offset đứng yên thì biến
thể **bị từ chối lúc nạp**, biến *"deployment này mong manh"* thành *"bộ sinh này hỏng"*. Nên
offset đi theo chu kỳ. Có test riêng cho cả hai.

### Biến thể không xếp hạng được thì **tính là trượt**

`recommendation_robustness` đếm biến thể nào giữ nguyên khuyến nghị. Biến thể ra `None` —
không xếp hạng nổi — **tính vào mẫu số và không tính vào tử số**. Cố ý: *"dưới mức sai số đầu
vào này thì cả trường ứng viên hết xếp hạng được"* đúng là kiểu mong manh con số này được hỏi.
Bỏ chúng ra sẽ báo cáo độ ổn định của những biến thể tình cờ còn dễ.

Không có gì để so thì trả `None`, **không** trả `1.0`: báo độ bền hoàn hảo từ không bằng chứng
nào là làm tròn đúng hướng một tuyên bố an toàn không bao giờ được làm tròn.

### Xác minh

Chạy thật trên **cả hai** profile đã ship — chúng khác nhau đúng ở chỗ quan trọng (sảnh khai
nhiễu và không có traffic; kho có traffic và không khai nhiễu):

```
== warehouse_a_v2 ==            == open_hall_v2 ==
  20 biến thể, 20 id khác nhau    20 biến thể, 20 id khác nhau
  tất định: True                  tất định: True
  đổi seed thì khác: True         đổi seed thì khác: True
  mọi biến thể hợp lệ: True       mọi biến thể hợp lệ: True
  id giữ nguyên: True             id giữ nguyên: True
  lidar σ 0.0 -> 0.0              lidar σ 0.02 -> 0.0236
  forklift periodic 24.0 -> 21.4  (không có traffic)
```

**23 test mới.** `test_neighborhood` · `test_episode_context` · `test_decision_card`:
**100 passed**. `ruff` sạch, format sạch.

### Còn lại của A2, nói rõ

Bộ sinh xong. **Chưa nối vào tầng quyết định**: cần chạy K sweep trên K biến thể, thu khuyến
nghị của từng cái, rồi điền `robustness_margin` vào card. Đó là **20× giờ máy của một phép so**
— trên kho ở mức 1% là 20 × 2,2 giờ — nên nó là một quyết định về ngân sách máy chứ không chỉ
là một đoạn mã, và tôi không tự chốt.

Scaffolding cho phần đó **đã có sẵn từ trước**: `sample_set="neighborhood"`, `neighborhood_contexts`
trong manifest, `pairing` đã biết episode trong cùng một biến thể là tương quan, và `gates` đã
loại chúng khỏi cận trên va chạm của G2.

---

## A3 — bốn nhiễu mới

Dev chốt làm **N1 định vị · N2 mất tia LiDAR · N3 lệch odometry · N5 trễ lệnh**; bỏ N4 (sai số
góc LiDAR).

### Ràng buộc dev đặt, và chỗ nó đụng hợp đồng

Yêu cầu: *"config trước mỗi run, bật tắt tuỳ ý, chỉ config đầu run chứ không được chọn trong
các episode."*

Vế thứ hai — cố định suốt run — thoả mãn ngay: mọi nhiễu đọc từ `scenario.sensor_noise`, tức từ
deployment, và không có đường nào đổi giữa chừng.

**Vế thứ nhất đụng một ràng buộc phải nói ra.** `episode_context_id` băm
`(task_profile_id, mission_id, environment_variant, seed)` và HĐ-3.1 đóng băng payload đó —
**nhiễu không nằm trong đó**. Nên "đổi nhiễu rồi chạy lại dưới cùng một `task_profile_id`" sẽ
sinh ra context hash **trùng nhau cho hai thế giới khác nhau**, và `--reuse-traces` phục vụ
episode của thế giới cũ. Không gì cảnh báo; id khớp.

Nên chỗ config đúng là **form khai deployment**: chỉnh nhiễu rồi khai thành một deployment mới.
Đó vẫn là "config trước mỗi run" theo đúng nghĩa dev cần, và id đổi chính là cơ chế giữ cho nó
trung thực.

### Bốn nhiễu, và chỗ mỗi cái phải đứng

| | mô hình | nhịp | chạm vào |
|---|---|---|---|
| **N1 định vị** | tổng vài sin tần số thấp (lệch) **+** nhảy giữ nguyên trong một cửa sổ tái định vị | mỗi bước | **phép đo** — `Observation.pose` |
| **N2 mất tia** | Bernoulli mỗi tia | mỗi bước | **phép đo** — báo về **tầm xa nhất** |
| **N3 lệch odometry** | Gauss, **rút một lần cho cả episode** | hằng số | **thế giới thật** |
| **N5 trễ lệnh** | hàng đợi số nguyên bước | mỗi bước | **thế giới thật** |

**N1 không phải jitter, và đó là điểm quan trọng nhất của nó.** Nhiễu zero-mean mỗi bước thì bộ
điều khiển san phẳng được; một ước lượng **sai cùng một hướng trong hai mươi giây** thì không.
Nên lệch được mô hình bằng vài sin tần số thấp — vẫn là hàm thuần của `(seed, step)`, không phụ
thuộc candidate đã lái bao xa. Tích luỹ theo quãng đường thật sẽ **vật lý hơn** và sẽ làm nhiễu
phụ thuộc hành vi candidate, đúng thứ `noise.py` sinh ra để chặn.

Nhảy tách riêng vì nó hỏng kiểu khác: bộ điều khiển chịu được sai số chậm, không chịu được một
bước nhảy. Nhảy **giữ nguyên** trong một cửa sổ — cái nguy hiểm của một fix sai là nó *ở lại*.

**N2 báo về tầm xa nhất, không bao giờ báo 0.** Số 0 đọc ra là *"có vật cản dính vào cảm biến"*
— ngược hẳn thực tế, và sẽ biến mất tia thành biến cố **an toàn nhất** planner có thể gặp thay
vì biến cố lái robot vào cửa kính.

**N3 nhân chồng lên trượt bánh chứ không thay thế.** Hai lỗi khác nhau và một xe thật có cả hai:
vũng nước hôm nay, và một bánh đã mòn nhỏ từ tháng trước. Trượt triệt tiêu qua một episode; lệch
thì không — đó là toàn bộ lý do có nó.

**N5 giữ robot đứng yên tới khi ống đầy.** Đó là cái một bộ truyền động làm trước khi lệnh đầu
tiên tới nơi; bịa ra một lệnh không-trễ ở bước đầu là cho không đúng cái lợi thế đang được mô
phỏng.

### Ranh giới đo / thế giới thật — chỗ dễ hỏng nhất

`_believed_pose` chỉ vào `Observation`. Ba chỗ **không** được chạm, mỗi chỗ một test:

- **Phép kiểm va chạm** — chấm trên pose tin tưởng sẽ mô phỏng một thế giới khác, và cho một
  robot định vị tệ **đi xuyên qua bức tường nó thật sự đâm vào**.
- **Trace HĐ-5** — ghi pose tin tưởng sẽ biến `path_length` và mọi khoảng hở thành phép đo *ý
  kiến* của robot.
- **`goal_distance`** — trả khoảng cách thật bên cạnh một pose tin tưởng là đưa cho robot một
  phép đối chiếu **không robot nào có**: bộ điều khiển sẽ suy ngược ra pose thật từ cặp đó.

Chi tiết cuối là chỗ tôi suýt bỏ sót; nó chỉ lộ ra khi viết test cho `Observation`.

### Chốt chặn D1 nổ đúng ca nó được dựng ra để bắt

Thêm 5 trường vào `SensorNoise` ⇒ `test_form_covers_the_contract` **đỏ ngay**: form khai
deployment không có ô cho chúng.

Đó chính là kiểu hỏng D1 tồn tại để chặn — *"thêm một trường vào hợp đồng mà form lặng lẽ bỏ
sót; suite vẫn xanh, form vẫn khai được, deployment sinh ra thiếu đúng thứ vừa thêm"*. Lần này
suite **không** xanh, và nó chỉ thẳng vào việc còn phải làm: thêm ô config. Một test tự nó trả
tiền vốn trong vòng một ngày.

Năm ô đã thêm.

**Dev bác đề xuất ban đầu của tôi, và tôi làm theo — nhưng giữ được cả hai điều.** Tôi đề xuất
"0 là tắt, không checkbox"; dev muốn **checkbox cho tiện** và **mặc định bật ở mức vừa phải**.
Hai yêu cầu đó không mâu thuẫn với lo ngại của tôi, chỉ cần đặt công tắc đúng chỗ:

- **Checkbox không thêm trường nào.** Nó **ghi 0** để tắt và ghi lại biên độ để bật. Nên trong
  *dữ liệu* vẫn chỉ có đúng một cách nói "tắt", và không tồn tại cặp `enabled: false` cạnh một
  sigma đã khai để hai nửa bất đồng. Công tắc nằm ở UI, sự thật nằm ở một con số.
- **Nhớ giá trị đã gõ.** Bỏ tick rồi tick lại trả về đúng số người dùng đã nhập, không phải mặc
  định. Mất một biên độ đã sửa vì một cú bấm nhầm là thứ nhỏ mà phải đo lại mới phát hiện.

**Mặc định bật — và đây là chỗ tôi KHÔNG làm theo nghĩa rộng nhất, có lý do.**

Mặc định nằm ở **form**, không ở **lược đồ**. `SensorNoise` vẫn để mọi trường mặc định 0, và
**bắt buộc phải thế**: hai profile đã ship không khai bốn nhiễu này, nên một mặc định khác 0 ở
lược đồ sẽ **đổi thế giới dưới chân `open_hall_v2` và `warehouse_a_v2` mà không đổi
`task_profile_id` của chúng** — mọi trace, mọi phán quyết cổng, mọi Decision Card đã lưu sẽ âm
thầm mô tả một thế giới không còn tồn tại (HĐ-3.1, HĐ-13).

Đặt mặc định ở form chỉ chạm tới **deployment chưa ai đo**, và đó đúng là thứ dev cần: khai mới
thì nhiễu bật sẵn ở mức thật.

| ô | mặc định | căn cứ |
|---|---:|---|
| LiDAR σ | 0,02 m | bảng nhiễu của tài liệu đề tài |
| trượt bánh | 0,02 | như trên |
| lệch định vị | 0,10 m | sai số định vị thường của AMR trong nhà đã có bản đồ; đáng kể cạnh robot bán kính 0,26 m |
| nhảy định vị | 0,02 | hiếm đủ để là một ngày xấu, thường đủ để xuất hiện trong 300 episode |
| mất tia | 0,02 | 2 tia trên 100; scanner thật gặp kính còn tệ hơn nhiều |
| lệch odometry | 0,01 | 1% hệ thống — một bánh nhỏ hơn bánh kia một chút. Nhỏ, và nó tích luỹ |
| trễ lệnh | 2 bước | 100 ms ở vòng 20 Hz, đúng một pipeline ROS bình thường |

### Chốt chặn D1 nổ **lần thứ hai**, và lần này bắt lỗi của chính bản sửa

Đổi form sang `noiseField("lidar_range_sigma_m", …)` làm **đường dẫn chấm hết hiện nguyên văn**
trong file — mà đó chính là **tiền đề** chốt chặn dựa vào (*"form gán mọi trường bằng đường dẫn
chấm, nên đường dẫn hoặc có trong file hoặc trường đó không được gán"*).

Sửa **form**, không sửa gác: `NOISE_DEFAULTS` khoá bằng **đường dẫn đầy đủ**, và `noiseField`
nhận đường dẫn đầy đủ. Tiền đề của gác đúng trở lại, và nó vẫn nhìn thấy mọi trường.

### Xác minh

**24 test mới.** Backend: `test_noise_extra` · `test_noise` · `test_engine` · `test_nav_stack` ·
`test_simulator_fairness` · `test_fairness` · `test_replanning` · `test_monolithic_policy` ·
`test_form_covers_the_contract` · `test_neighborhood` — **211 passed, 1 skipped**.
Web: **613 passed, 31/31 file**. `ruff` sạch, `tsc` sạch.

Bốn test tôi viết sai lúc đầu, và một trong số đó lộ ra hành vi **đúng** mà tôi không lường:
bias dương bị **trần vận tốc chặn** khi lệnh đã ở mức tối đa — một bánh mòn không cho robot một
bao hoạt động lớn hơn. Test sửa lại để ra lệnh dưới trần; hành vi giữ nguyên.

### Còn lại

- **Chưa profile nào bật bốn nhiễu này.** Mặc định 0 khắp nơi, nên chưa lượt đo nào đổi. Bật lên
  là **đổi thế giới** ⇒ phải khai `task_profile_id` mới (HĐ-13).
- **N4 (sai số góc / lệch lắp LiDAR)** — dev bỏ khỏi phạm vi đợt này.

---

## Full suite bắt ba lỗi — và cả ba là **một lỗi của tôi**

Lần chạy đầu sau A3: **3 failed, 2397 passed**. Ba test khác nhau, một gốc:

```
tests/api/test_api_decisions.py::TestDeployments::test_the_noise_amplitudes_survive_storage
tests/test_decision_card.py::TestCardValidatesAgainstTheContract::test_a_real_manifest_passes_the_shipped_schema
tests/test_vertical_slice.py::TestItRunsAtAll::test_both_artefacts_land_on_disk
```

**Tôi thêm năm trường vào `SensorNoise` mà không cập nhật `contracts/schemas/manifest.schema.json`.**
Schema đó khai `additionalProperties: false`, nên mọi manifest sinh ra sau A3 đều **không hợp lệ
so với chính lược đồ dự án công bố**. Hai trong ba test đỏ vì đúng chuyện đó.

Đây là kiểu trôi mà chốt chặn D1 bắt được **ở phía form** nhưng không ai bắt **ở phía schema
JSON**. Khác biệt: form là một bản sao *tuỳ chọn* của hợp đồng, còn `manifest.schema.json` là
**chính hợp đồng ở dạng máy đọc được** — nên nó phải đi cùng lược đồ trong cùng một lượt sửa.

### Kèm theo: A3 lẽ ra phải bump hợp đồng, và tôi đã không

Thêm trường vào một lược đồ mà manifest công bố **là một thay đổi hợp đồng**. Đã sửa:
**6.6.0 → 6.7.0**, kèm dòng lịch sử nêu bốn trục, ranh giới đo/thế-giới của từng cái, và ghi rõ
**mọi trường mặc định 0** nên chưa lượt đo nào bị ảnh hưởng.

### Test thứ ba: khẳng định thừa hơn điều nó nói

`test_the_noise_amplitudes_survive_storage` so **cả khối** `sensor_noise` bằng dấu bằng:

```python
assert stored["environment"]["sensor_noise"] == {
    "lidar_range_sigma_m": 0.02,
    "wheel_slip_fraction": 0.02,
}
```

Docstring nói *"nếu biên độ bị rơi mất trên đường vào lưu trữ thì không gì downstream biết"* —
nhưng phép so bằng còn khẳng định thêm rằng **`SensorNoise` có đúng hai trường**, điều nó chưa
bao giờ tuyên bố. Nên thêm một trục nhiễu làm một test *lưu trữ* đỏ vì một lý do **không liên
quan gì tới lưu trữ**.

Sửa thành khẳng định theo tên trường. Đây là bài học chung đáng ghi: **so bằng cả một cấu trúc
là khẳng định luôn cả những gì cấu trúc đó KHÔNG chứa** — hiếm khi là điều test muốn nói, và nó
biến mỗi lần mở rộng lược đồ thành một lượt đỏ giả.

---

## P1 — sidebar nói đúng việc *(pha đầu của refactor UI)*

Chi phí lớn nhất của việc chạy hai luồng song song **không nằm ở mã**: mười hai mục trong sidebar,
hai luồng trộn trong cùng một nhóm, và không gì nói cho người đọc biết `Benchmarks` với
`Decisions` trả lời **hai câu hỏi khác nhau**.

### Nhóm theo **việc**, không theo hệ thống sinh ra màn hình

Nhóm cũ (Workspace / Results / Account) chia theo **nơi màn hình đến từ**, nên hai luồng nằm lẫn
trong một tiêu đề — `Deployments` và `Decisions` kẹp giữa `Benchmarks` và `Leaderboard`.

```
BẠN ĐANG LÀM GÌ   Dashboard · Deployments · Simulate · Decisions
NGUYÊN LIỆU       Maps · Library · Algorithms · Models
ĐANG ĐƯỢC THAY    Benchmarks · Leaderboard · Scenarios
TÀI KHOẢN         Agent · Reviews · System
```

### Mỗi mục một dòng nói nó **để làm gì**

Trường mới `descriptionKey`, tuỳ chọn trong kiểu và **bắt buộc bằng test** cho mục có trong
sidebar (route không có mục — `/login`, `/welcome` — thì không có gì để mô tả).

Lúc thu gọn, **tooltip mang luôn mô tả**: đó là bề mặt duy nhất còn lại, và một dãy icon chỉ có
tên là đúng thứ mấy dòng mô tả này sinh ra để sửa.

### Nhóm "Đang được thay" — dev chốt hiện ra, không giấu

Ba trang đó **vẫn chạy** và vẫn là cách duy nhất làm vài việc. Nói thẳng điều đó có ích cho
người đọc hơn một sidebar lặng lẽ xếp bản thay thế cạnh thứ nó thay.

Mô tả của chúng nói **vì sao**, không chỉ nói "cũ":

- `Benchmarks` → *"Phép so cũ. Decisions đang thay nó"*
- `Leaderboard` → *"Xếp hạng xuyên scenario — điều một khuyến nghị không làm được (**HĐ-1.4**)"*
- `Scenarios` → *"Giữ tới khi form deployment vẽ được vật cản"* — đúng quyết định của dev, và
  dòng này là chỗ duy nhất người dùng đọc được lý do nó còn ở đây

### Hai test cũ đỏ, và cả hai là **mô tả cấu trúc cũ**

`groups the menu into labelled sections` tìm chữ `Workspace`; `gives every icon a tooltip` tìm
`data-tooltip="Maps"`. **Khẳng định của chúng vẫn đúng** — mục vẫn có nhãn, icon vẫn có tooltip —
chỉ chuỗi đổi. Sửa để chúng khẳng định *điều chúng nói*, không phải chuỗi cũ.

Ba test mới: mọi mục có mô tả · sidebar nói ra trang nào đang được thay · tooltip lúc thu gọn
mang cả mô tả.

**Web: 620 passed, 31/31 file.** `tsc` sạch.

---

## P3 — trang Candidates *(pha hai của refactor UI)*

Trước lượt này, cách duy nhất gọi tên một candidate là **gõ tay** `astar+dwa` và `dwa_coarse`
vào hai ô text trong panel khởi chạy: không danh sách để biết có gì chọn, không dấu hiệu nào
nói một trong các stack trong registry là bản **tham chiếu không được đỡ kết luận**, và gõ sai
thì tới lúc server từ chối mới biết.

### Một khoảng trống phía backend lộ ra trước

`LOCAL_CONTROLLER_CONFIGS` **chưa có endpoint nào**. Chép sang web sẽ là **tuyên bố thứ hai** về
thứ nền tảng chấp nhận — tự do trôi, và trôi âm thầm cho tới hôm một dropdown mời một cấu hình
server từ chối. Nên phơi ra: `GET /local-controllers`.

**Tham số đi kèm tên**, không chỉ tên: `dwa_coarse` lấy mẫu 7×15 còn `dwa_default` lấy 20×40, và
chênh lệch đó là **toàn bộ lý do** một lựa chọn lấy mẫu là một *candidate* chứ không phải một
hằng số nằm trong script nào đó (HĐ-1.3).

Có test khẳng định **mọi tên endpoint mời đều là tên đăng ký chấp nhận** — đó chính là điểm của
việc phục vụ danh sách: cái nó mời phải đúng bằng cái server nhận.

### Ba bảng, vì một candidate làm từ hai thứ và không phải thứ nào trong hai

| bảng | nói gì |
|---|---|
| **Candidate đã đăng ký** | `candidate_id` (hash), stack, cấu hình, và **tinh chỉnh đã khai hay chưa** |
| **Stack trong registry** | global planner nào, có lấy mẫu ngẫu nhiên không, **dùng làm candidate được không** |
| **Cấu hình controller** | các con số, không chỉ tên |

Chỉ hiện bảng đầu sẽ giấu mất có gì để chọn; chỉ hiện hai bảng sau sẽ giấu mất rằng lựa chọn đó
**có một danh tính mọi trace khoá theo**.

### Bốn chỗ giữ đúng hợp đồng

- **Không có ô id lúc đăng ký.** HĐ-1.3: `candidate_id` là hash trên stack, tham số và phiên bản
  mã, server tự tính. Cho người gọi tự đặt id sẽ khiến hai cấu hình khác nhau **dùng chung một
  danh tính** mà mọi trace, phép ghép cặp và ΔU đều khoá theo.
- **Stack tham chiếu bị lọc khỏi cả hai bộ chọn**, nhưng **vẫn được liệt kê** kèm lý do. Giấu
  hẳn sẽ để người đọc thắc mắc vì sao registry và bộ chọn bất đồng.
- **Planner lấy mẫu ngẫu nhiên có nhãn riêng.** Nó cần nhiều seed hơn mới nói được điều gì; một
  bảng giấu chuyện đó là mời người đọc **so một cái cây may mắn với A***.
- **Tinh chỉnh chưa khai hiện thành câu trả lời riêng**, không phải ô trống. HĐ-1.6: tầng mục
  tiêu **tính phí sự im lặng** thay vì thay bằng không, nên phân biệt đó phải sống tới màn hình.

### Panel khởi chạy: hai ô text thành dropdown, có đường lui

Cả hai danh sách **được phục vụ**, không hardcode. Nhưng nếu request hỏng hoặc chưa về, ô text
tự do **vẫn còn**: mất khả năng chạy một phép so chỉ vì một danh sách tiện nghi không tới là một
trang **tệ hơn** cái vừa được thay.

### Điều hướng

`Candidates` vào nhóm **Nguyên liệu** — nó là thứ một phép so chọn *giữa*, cùng loại với một bản
đồ. `/algorithms` chuyển sang nhóm **Đang được thay**, mô tả nói thẳng *"Registry stack.
Candidate đang thay nó"*.

### Xác minh

Backend **+4 test** (`GET /local-controllers`) · Web **+13 test**.
Web: **633 passed, 32/32 file**. `ruff` sạch, `tsc` sạch. Chưa chạy full suite backend — chờ
lệnh dev.

### P3 sửa lại theo yêu cầu dev: tách chọn global và local

Dev nêu hai vấn đề với bản đầu, cả hai đúng và cả hai nhìn về phía trước:

1. **Một dropdown cho cả stack sẽ rối khi số global/local tăng.** Danh sách lớn theo **tích** của
   hai tầng trong khi thứ đang chọn là **một món từ mỗi tầng**. Một bộ chọn lớn bậc hai để diễn
   đạt một lựa chọn tuyến tính là sai hình dạng — và nó sai **trước khi** ai đó nhận ra nó dài.
2. **Cấu hình controller đang là của riêng DWA.** `velocity_samples` là ý niệm của DWA; một
   checkpoint PPO không liên quan gì tới nó.

#### Registry lộ ra một ràng buộc trước khi gõ

Năm entry, và chúng **không phải tích Descartes đầy đủ**:

```
astar   + dwa           benchmarkable
astar   + ppo           benchmarkable
astar   + pure_pursuit  reference
rrtstar + dwa           benchmarkable
rrtstar + pure_pursuit  reference
```

**`rrtstar+ppo` không tồn tại.** Hai dropdown độc lập sẽ dựng được nó và người dùng biết điều đó
từ một lời từ chối của server. Nên danh sách **xếp tầng**: controller được mời là những cái
registry thật sự ghép với global planner đang chọn.

#### Ba thay đổi backend, mỗi cái theo một tiền lệ đã có

| | |
|---|---|
| `AlgorithmInfo.local_controller` | **Khai ra, không phân tích từ `id`** — đúng lý lẽ `global_planner` đã dùng: id là quy ước hiển thị, trường mới là **sự thật**. Không có nó, một bộ chọn phải cắt chuỗi id, tức đặt một parser giữa cái picker và cái nó đang chọn |
| `CONTROLLER_CONFIGS` nhóm theo controller | Thêm một controller giờ là thêm **một khoá**. Không gì khác phải dời |
| `LOCAL_CONTROLLER_CONFIGS` **suy ra** từ nó | Tám module và một script tra cứu theo tên, và một report đã lưu **trích dẫn** tên đó. Bảng phẳng phải còn; suy ra nó nghĩa là nhóm không thể trôi khỏi nó. **Không một chỗ gọi nào phải sửa** |

#### `CandidatePicker` — dùng chung, ba tầng

Một component cho cả trang Candidates lẫn panel khởi chạy. Ba quyết định trong đó:

- **Id được TRA CỨU, không lắp ráp.** Mọi entry hôm nay viết là `<global>+<local>` nên ghép hai
  nửa sẽ chạy — **cho tới khi có một entry không thế**. Cặp (global, local) chọn ra entry, và
  entry tự cấp id của nó.
- **Đổi controller thì bỏ cấu hình; đổi global thì giữ.** `dwa_coarse` trên một policy PPO là
  một cái tên thuộc từ vựng khác. Nhưng *"cùng controller dưới một planner khác"* đúng là phép
  so nền tảng này sinh ra để làm, nên ca đó giữ cả hai.
- **Controller chưa có cấu hình nào thì nói ra**, không để dropdown rỗng. Đó không phải lỗi — đó
  là một controller chưa ai viết cấu hình cho.

Đường lui giữ nguyên: danh sách chưa về thì ô text tự do vẫn còn.

#### Xác minh

Ba assertion cũ trỏ vào mã đã dời sang picker — chuyển đích, giữ nguyên khẳng định. Sáu test mới
cho hành vi xếp tầng.

Web **639 passed**. Backend: `test_candidate_bridge` · `test_measure` · `test_simulator_fairness`
· `test_api_decisions` · `test_vertical_slice` — **186 passed**. `ruff` sạch, `tsc` sạch.

## P2 — `/decisions` thành danh mục Decision Card *(pha ba của refactor UI)*

Kế hoạch duyệt: *"`/leaderboard` đổi vai thành danh mục Decision Card"*,
cách làm anh để tôi tự chọn: **mở rộng `/decisions` rồi bỏ hẳn
`/leaderboard`**. Vế đầu xong. **Vế sau tôi dừng lại, và đây là phần
quan trọng nhất của mục này.**

### Cái `/decisions` nhận thêm

Ba thứ `/leaderboard` làm được mà danh sách run không làm được, dựng
lại trên nền chỉ xếp hạng trong một deployment:

1. **Dải đếm** (`summarise`): bao nhiêu run, bao nhiêu deployment, bao
   nhiêu run ra thẻ, bao nhiêu đã đọc, bao nhiêu đã duyệt. "Bảy so sánh
   trên ba deployment" là *sự kiện về công việc*. Xếp hạng ứng viên
   xuyên deployment là *khẳng định HĐ-1.4 cấm*. Dải đếm nói cái thứ
   nhất và không đụng cái thứ hai.
2. **Lọc theo trạng thái người**: chưa đọc / đã đọc / đã duyệt. Người
   mở trang này thường đang tìm việc tiếp theo của chính mình, không
   phải tìm quán quân.
3. **Cột `decision_utility` — chỉ hiện khi danh sách đã lọc về một
   deployment.** `const oneDeployment = profileId !== ""`. Đây là chỗ
   duy nhất trang này có thể tự phản bội: một cột điểm sắp xếp được
   trên danh sách trộn deployment **chính là bảng xếp hạng xuyên
   scenario, chỉ đổi tên**. Có thêm test khẳng định trang không tự
   `.sort(` dòng nào — vì sắp xếp phía client theo cột điểm là cách một
   danh mục biến thành bảng xếp hạng mà không ai kịp quyết định.

Bốn test mới trong `decisions-page.test.tsx`.

### Vì sao chưa xoá `/leaderboard`

Tôi đã xoá thật: xoá thư mục trang, gỡ mục sidebar, trỏ lại StatCard ở
dashboard. `tsc` sạch. Rồi suite web đỏ **7 chỗ**, và khi đọc kỹ chúng
đỏ vì lý do khác hẳn cái tôi đoán:

- `charts-and-export.test.tsx` — **đường cong độ khó** (`DifficultyCurveChart`,
  `buildDifficultyCurve`, cảnh báo `charts.uncalibratedScenarios` /
  `charts.staleScenarios`) và **biểu đồ khoảng cách tổng quát hoá**
  (`GeneralizationGapChart`, `buildGapSeries`, `charts.incompleteGap`).
- `leaderboard-observation.test.tsx` — mỗi stack **được cho nhìn thấy
  gì**; trộn lớp quan sát phải là hành động cố ý, không bao giờ im lặng.
- `scenario-split.test.tsx` — huy hiệu split, cảnh báo held-out,
  `entry.warnings`.

Ba nhóm này **không phải bảng xếp hạng**. Chúng là ba bề mặt phân tích
tình cờ *trú* trên trang xếp hạng, và cả ba đều là rào chắn chống đọc
sai số liệu. `/decisions` hiện **chưa có chỗ nào chứa chúng**.

Nếu tôi cứ xoá, tôi sẽ phải hoặc xoá luôn ba nhóm test đó — tức là gỡ
rào chắn mà không ai quyết định gỡ — hoặc để chúng đỏ. Đúng cái tình
huống anh đã chặn tôi ở `/models`: **"đỏ vào mặt người không gây ra
nó"**. Nên tôi hoàn nguyên: `git checkout` ba file, suite về **643
passed**, `/leaderboard` còn nguyên trong nhóm *"Đang được thay"* của
sidebar — nhãn đó vẫn đúng, nó *đang* được thay chứ chưa bị thay xong.

### Cái này đẩy sang đâu

Xoá `/leaderboard` chuyển sang **P6** (nghỉ hưu luồng cũ), và P6 giờ có
thêm một điều kiện tiên quyết mà bản kế hoạch chưa lường:

> Trước khi bỏ `/leaderboard`, phải tìm chỗ ở mới cho đường cong độ khó,
> biểu đồ khoảng cách tổng quát hoá, và cảnh báo lớp quan sát. Nơi tự
> nhiên nhất là trang chi tiết `/decisions/[id]` — cả ba đều là tính
> chất của **một** deployment, nên chuyển sang đó còn *đúng hơn* chỗ cũ.

Đây là công việc thật, không phải thủ tục — ước lượng nửa ngày đến một
ngày, và nó phải có kế hoạch riêng chứ không nhét vào lần dọn cuối.

**Nhận sai của tôi:** khi lên kế hoạch P2 tôi mô tả `/leaderboard` như
"một bảng danh sách xếp hạng" và chỉ soi phần xếp hạng. Tôi đã không
đọc hết trang trước khi hẹn ngày xoá nó. Chi phí thực tế chỉ là một lần
hoàn nguyên vì test bắt được, nhưng cái bắt được là **thiếu sót lúc
khảo sát**, không phải lỗi lúc gõ.

## P4 — `/simulate` thành **sân thử** *(pha bốn của refactor UI)*

Chỗ luồng mới thật sự thiếu: chạy được ba trăm episode và phát lại
trace đã ghi, nhưng **không xem trực tiếp được một episode**. Hai câu
hỏi khác nhau — *"chuyện gì đã xảy ra"* với *"thử cấu hình này xem
sao"*.

### Cầu nối phía backend

`POST /task-profiles/{id}/test-bench` — nhận `mission_id`, `seed`,
`stack`, `local_config`; trả về `simulation_id` để chạy và stream bằng
đúng WebSocket cũ, không viết mới dòng nào ở tầng xem.

Điểm cốt lõi là **fidelity**: scenario dựng bằng chính `scenario_for` mà
`run_contract_episode` gọi, planner dựng từ chính registry entry đó với
chính `episode_seed` đó, và replanning để nguyên mặc định tắt — vì
`run_contract_episode` cũng chạy tắt. Thứ bạn xem đúng là thứ phép so sẽ
chạy. Nếu không thế thì nó là một thí nghiệm khác, và một thí nghiệm
khác cho cảm giác yên tâm là thứ tệ hơn không có gì.

Staging **bất biến ở phần lưu**: map khớp theo chính lưới ô, scenario
khớp theo tên — mà tên scenario chính là `episode_context_id`. Xem lại
hai mươi lần vẫn một dòng map, một dòng scenario.

### Vì sao nó không phải phép đo — và đây là toàn bộ luận cứ an toàn

HĐ-5 đặt trace Parquet là **đầu vào duy nhất** của Metrics Engine. Một
episode sân thử mà ghi trace sẽ **tiêm một mẫu vào tập evaluation** với
một `episode_context_id` **thật** — không gì ở hạ nguồn phân biệt được
nó với một episode đã đo — và tiêm ngoài thứ tự context-outer (HĐ-3.2),
ngoài lệnh cấm hai run evaluation song song (HĐ-7.4).

Nên nó **không ghi trace**. Lần chạy rơi vào kho `simulations`, nơi
không cổng, chỉ số hay Decision Card nào đọc tới. **Id thì thật, lần
chạy thì không phải bằng chứng.** Test khẳng định thẳng điều đó: chạy
xong, thư mục trace vẫn rỗng, và danh mục `/decisions` không thêm dòng
nào.

### Phía UI

- Đầu vào đổi từ *map + hai điểm click* sang **deployment + mission**.
- **Bỏ hẳn thao tác click đặt start/goal.** Một cái đích kéo được sẽ
  biến thứ đang xem thành một episode khác với episode sắp được đo. Bảng
  `MapCanvas` giờ không nhận `onWorldClick` — không phải "không khuyến
  khích" mà là **không tới được**.
- **Bỏ công tắc replanning.** Mọi episode được đo đều chạy tắt; để công
  tắc ở đây là cho người ta xem một stack sẽ không bao giờ bị phán xét.
- Bảng *"Những gì deployment đã chốt"* — timeout, dung sai, bán kính,
  vật cản động, **tên các luồng nhiễu đang bật** — chỉ hiển thị, không
  sửa. Chỉnh một cái "cho riêng bản xem thử" là biến đây thành thí
  nghiệm khác.
- Seed là ô **gõ tay**, kèm câu giải thích cùng seed là cùng một episode
  tới từng quỹ đạo vật cản và từng lần bốc nhiễu. Server bốc seed hộ thì
  đúng cái episode đáng xem lại lại là cái không lấy lại được.
- Banner *"không có gì ở đây là phép đo"* đặt **trước** nút chạy, không
  phải sau. Người xem một episode sạch rồi mới biết nó không tính là
  người được báo quá muộn để còn dùng nó mà quyết.
- `MetricsPanel` giữ nguyên nhưng có dòng nói rõ số đọc từ chính lần
  chạy chứ không từ trace — đúng cho *"nhìn có hợp lý không"*, sai cho
  mọi khẳng định.
- Sidebar đổi tên **Live Simulation → Sân thử / Test Bench**. Tên cũ mô
  tả cỗ máy; trang giờ là bước rẻ trước một bước đắt.

### Một guard đã dời chỗ, không bị xoá

`replanning-controls.test.tsx` có bốn khẳng định về `/simulate`. Chúng
**không còn đúng** vì công tắc bị bỏ có chủ ý. Tôi không xoá chúng cho
xanh: nửa nói về form benchmark (vẫn sống) giữ nguyên, còn nửa nói về
`/simulate` **lật ngược** và chuyển sang `test-bench.test.tsx` —
khẳng định công tắc **vắng mặt**, kèm lý do. Docstring file cũ ghi rõ
claim đi đâu.

### Test

- **Backend** `tests/api/test_test_bench.py` — 16 test: điều kiện lấy
  đúng từ deployment (timeout / dung sai / nhiễu / traffic / bước vật
  lý), `episode_context_id` khớp đúng hash HĐ-3.1 tính độc lập, seed
  khác là episode khác, **không ghi trace**, không sinh decision run,
  replanning tắt, staging bất biến, bốn kiểu từ chối, và episode thật sự
  chạy ra quỹ đạo.
- **Web** `test-bench.test.tsx` — 17 test.
- Suite web: **660 passed**, `tsc` sạch.
- Hai module backend đã động vào — `test_api_decisions.py` và
  `test_api_simulations.py`: **82 passed**. Endpoint mới nằm chung
  router với decisions nên đây là chỗ hồi quy dễ xảy ra nhất.
- `ruff check .` sạch. **Chưa** chạy full suite backend.

## P5 — `robot-profiles` thành nguồn sự thật cho **chiếc xe** *(pha năm)*

Ba nhóm trường, ba số phận đúng như kế hoạch — và cách nối là phần
quan trọng hơn cả ba.

### Cách nối: **điền lúc khai**, không phải tham chiếu

Chọn một xe trong form deployment sẽ **điền số vào** các ô; deployment
lưu chính con số, không lưu `robot_profile_id`.

Lý do không phải "rẻ hơn". HĐ-13 đòi người khác dựng lại được lượt chạy
**từ chính profile**. Một profile trỏ tới một dòng DB **sửa được** sẽ
đổi nghĩa vào ngày ai đó sửa dòng đó — và mọi trace đã lưu lặng lẽ mô tả
một con robot khác, **dưới cùng một `task_profile_id`**, nên không gì
cảnh báo. Cách này đặt nguồn sự thật đúng chỗ nó cần đứng — **lúc tác
giả chọn** — mà vẫn giữ profile tự chứa. Không đổi hợp đồng, không lượt
chạy nào mất hiệu lực.

### Gia tốc: thêm vào xe, và **vắng không phải là không**

`RobotConfig` đòi cả hai gia tốc, `RobotProfile` không có ô nào — nên ai
điền form cũng phải gõ hai số đó từ trí nhớ. Đó chính là cách một hiện
trường bị đo trên một con robot tăng tốc gấp đôi bản sao của nó ở hiện
trường kia.

Migration **0008** thêm hai cột **nullable**. NULL là **câu trả lời**,
không phải chỗ trống chờ điền: một profile viết trước khi có cột thì
chưa từng khai gì cả, và ghi một số mặc định vào đó là đặt một khẳng
định vật lý về xe của người khác vào DB mà không mang tên ai — rồi
deployment dựng từ nó sẽ được đo như thể khẳng định ấy đã được kiểm.
Cùng hình dạng câu trả lời HĐ-1.6 dành cho tuning chưa khai: **im lặng
là một trạng thái**.

Form vì thế **để nguyên** hai ô gia tốc khi xe không khai, kèm câu nói
rõ, thay vì ghi 0 — 0 nghĩa là robot không tăng tốc được.

Riêng `DEFAULT_PROFILE` (bản seed) **có** khai 1.0 / 3.0: đó là phát
minh của chính nền tảng và là đúng những con số con robot mặc định của
simulator vẫn luôn chạy. Để trống thì profile duy nhất không ai viết
lại thành profile duy nhất không điền nổi một form.

### `control_period` **ở lại deployment** — và đây là hàng rào

Nó là T_cycle: ngân sách wall-clock cho một bước điều khiển **trên bo
mạch đích**, tức ngưỡng cổng G4 và nguồn của các mốc latency. Cùng một
con robot ở sảnh và ở lối kho có thể bị đòi hai chu kỳ khác nhau — đó là
**hai yêu cầu trên một robot**, không phải hai robot.

Nếu nó nằm trên profile xe, sửa một dòng sẽ **nới một cổng cho mọi
deployment dùng xe đó**, mà `episode_context_id` không băm robot nên
lượt chạy cũ giữ nguyên id trong khi mô tả một chuẩn không ai đồng ý.
Không gì cảnh báo; các lượt chạy chỉ đơn giản bắt đầu pass.

Hàng rào ba lớp:

1. `RobotProfile` không có trường đó — test khẳng định bằng
   `model_fields`.
2. `POST /robot-profiles` **từ chối** body có `control_period`, kèm câu
   giải thích nó thuộc về đâu. Từ chối chứ không lặng lẽ bỏ qua: người
   gửi nó là người đang tin mình vừa đặt chu kỳ. Chặn **đích danh** một
   trường chứ không cấm mọi khoá lạ — cấm hết là một quyết định khác về
   một endpoint đợt này không đụng tới.
3. Form không điền nó từ xe — test cắt đúng thân hàm `adoptVehicle` và
   khẳng định chuỗi `control_period` không xuất hiện trong đó.

Thêm một test tham số hoá quét **mọi** trường của `RobotConfig` và đòi
mỗi trường có chỗ ở trên `RobotProfile` — thêm trường mới vào
`RobotConfig` sẽ đỏ **đích danh trường đó**, thay vì lộ ra muộn dưới
dạng một form hỏi thứ mà kho xe không cấp được.

### Một chỗ tôi tự giới hạn

`robot-profiles` nằm trong `routers/models.py` — vùng An đã dặn *"phần
việc của người khác, không can thiệp"*. P5 buộc phải chạm vào đó vì
chính An chốt *"robot-profiles là nguồn sự thật"*. Tôi giữ can thiệp ở
mức tối thiểu: hai trường **optional** (không phá caller nào), một
validator **chặn đúng một tên**. Không đổi `extra="forbid"`, không đụng
phần models.

### Test

- `tests/api/test_robot_profile_boundary.py` — 16 test.
- `deployments-page.test.tsx` — thêm 5 test cho picker xe.
- Suite web: **665 passed**, `tsc` sạch. `ruff check .` sạch.

## P6 — luồng cũ nghỉ *(pha cuối)*

Kế hoạch ước lượng nửa ngày. Ước lượng đó **sai**, và lý do sai đáng ghi
lại: nó đếm bốn trang, không đếm những gì đang **trú** trên bốn trang đó.
Khảo sát trước khi xoá cho ra bảy nhóm khẳng định nằm rải trong bảy file
test. An chốt hướng **phân loại**: giữ cái theo-deployment, bỏ cái
xuyên-scenario.

### Cái giữ lại — vì nó vẫn có nghĩa trong hợp đồng mới

**1. Lớp quan sát — công bằng khi so ứng viên.** Đây là thứ đáng giá
nhất trong cả đợt. Một stack đọc bản đồ tĩnh và một stack chỉ đọc LiDAR
đang trả lời **hai câu hỏi khác nhau**; phần lớn khoảng cách giữa các con
số của chúng là khoảng cách giữa **đầu vào**, nên ΔU khi ấy đo đặc quyền
không kém gì đo bộ lập kế hoạch — và Decision Card sẽ gọi tên người thắng
trên cơ sở đó.

- `selection.py` ghi `global/local_observation_class` **vào từng ứng viên
  lúc chạy**, không tra lúc render: registry đổi được, còn một lượt chạy
  đã lưu phải tiếp tục mô tả đúng phép so đã thật sự xảy ra (HĐ-13).
- `/candidates` in cả hai lớp — **trước** khi ai chạy gì. Đây là chỗ chọn
  stack, nên là chỗ phải trả lời được "cái này được nhìn thấy gì".
- `/decisions/[id]` có cột *Được nhìn* và một cảnh báo khi phép so trộn
  lớp. Chưa khai thì hiện **"chưa khai"** chứ không để trống — ô trống
  đọc thành "giống mấy cái kia", mà đó đúng là điều một stack không ai
  khai không thể chứng minh.
- Bản xuất Markdown mang theo cả cột lẫn cảnh báo. **Trên giấy điều này
  quan trọng hơn trên màn hình**: người đọc một file không hỏi lại được.

Hôm nay mọi mục registry đều khai cùng một cặp, nên cảnh báo **không bao
giờ hiện**. Đó chính là lý do phải viết bây giờ: mục đầu tiên không khớp
sẽ biến một phép so không đồng dạng thành một phép so trông có vẻ đồng
dạng, mà không gì trên màn hình hay trong file bắt được.

**2. Xuất Markdown.** Endpoint mới `GET /decisions/{id}/report.md` +
`decision_markdown.py`. Cơ chế tải (fetch có xác thực, Blob, thẻ neo tổng
hợp, thu hồi object URL) chuyển nguyên vẹn — nó chưa bao giờ là tính chất
của luồng cũ; chỉ tài liệu nó tải là mới.

Ba tính chất **cấu trúc**, không phải trang trí:
- **Lượt chạy không ra thẻ vẫn xuất được.** Phần lớn lượt chạy không ra
  thẻ (HĐ-7). Nút chỉ hiện với lượt chạy có thẻ sẽ biến kết quả thường
  gặp thành thứ duy nhất không ai bỏ vào ticket được.
- **Null in ra "not measured", không để trống.** HĐ-12 định nghĩa vậy, và
  một ô trống trong bảng Markdown đọc thành sự trấn an.
- **Phạm vi đi cùng khuyến nghị.** HĐ-1.4. Một tài liệu tới nơi mà thiếu
  dòng đó là một tài liệu sẽ bị đem áp dụng chỗ khác.

Không khoá sau phê duyệt: đọc là hành vi **đi trước** phê duyệt (HĐ-14),
khoá lại là đảo ngược thứ tự.

**3. Phát lại quỹ đạo** — đã có sẵn: `TraceViewer` trên `/decisions/[id]`
(có test riêng) và sân thử ở `/simulate`. Hook `useTrajectoryPlayback`
không còn ai gọi, xoá.

**4. Huy hiệu split** — `SplitBadge` vẫn sống ở `/library` và
`/scenarios`. Đó là **tính chất của scenario**, không phải của người chạy.

### Cái bỏ hẳn — và vì sao đó là đọc đúng hợp đồng

Đường cong độ khó, biểu đồ khoảng cách tổng quát hoá, đếm lượt dùng
held-out, cảnh báo held-out trước khi chạy: cả bốn là **khẳng định xuyên
scenario** — *"stack này tổng quát từ tập dev sang tập held-out"*. HĐ-1.4
buộc một khuyến nghị chỉ có phạm vi **một deployment**. Chúng nghỉ hưu
**cùng** luồng đưa ra khẳng định đó, chứ không phải bị dời sang một luồng
không đưa ra khẳng định đó.

Component bị xoá cùng, **không để lại code chết sau một test xanh**:
`DifficultyCurveChart`, `GeneralizationGapChart`, `MetricIntervalChart`,
`ReplanningControls`, `useTrajectoryPlayback`.

Mỗi chỗ xoá đều để lại **đoạn ghi lý do ngay trong file test còn lại** —
`scenario-split.test.tsx` và `charts-and-export.test.tsx` mở đầu bằng
đúng đoạn nói cái gì đi đâu và vì sao. Xoá im lặng là thứ tôi tránh cả
đợt này.

### Trang xoá, trang giữ

Xoá: `/benchmarks`, `/benchmarks/[id]`, `/algorithms`, `/leaderboard`.
Giữ: **`/scenarios`** — form deployment vẫn chưa vẽ được vật cản, nên bỏ
nó là **lấy đi một năng lực**, không phải dời một năng lực. Sidebar nói
thẳng điều đó thay vì để người đọc tự hỏi sao một trang cũ sống sót.

### Cái vỡ ra khi xoá — và cách xử lý

Xoá bốn trang làm **hỏng dây** ở nhiều chỗ ngoài danh sách của kế hoạch:

- **Dashboard** đếm benchmark, liệt kê benchmark gần đây, trỏ thẻ
  "accepted" vào `/leaderboard`. Dựng lại trên luồng mới: đếm **phép so**,
  **ra được thẻ**, **đã duyệt**; danh sách gần đây thành phép so gần đây.
  *Ra được thẻ* đứng **cạnh** tổng chứ không thay tổng — chỉ có một con
  số sẽ khiến bốn trên năm lượt chạy đọc thành tỉ lệ hỏng, đúng áp lực
  từng đẻ ra một tấm thẻ chặn xác suất va chạm từ một episode.
- **Chuyển hướng sau đăng nhập** (`/login`, `/welcome`, `/auth/callback`)
  đều trỏ `/benchmarks` — người dùng mới sẽ hạ cánh vào 404. Đổi sang
  `/decisions`.
- **`/reviews`** và ô "yêu cầu đang chờ" trên dashboard link tới
  `/benchmarks/[id]`. Đổi thành **chỉ hiện tên, không link** — hộp thư
  vẫn trả lời đúng câu hỏi của nó (*cái gì đang chờ ai*), còn một link
  404 thì đúng là thứ tôi đã chê ở `/models`.
- **Locale vi** hoá ra để `nav.candidates` là chuỗi tiếng Anh
  *"Candidate"*. Không phải lỗi của P6 — nhưng nó lộ ra vì test tiêu đề
  chỉ soi đúng một trang. Sửa cả chuỗi lẫn test.

### Endpoint backend: **đánh dấu deprecated, chưa gỡ**

18 route trong `routers/benchmarks.py` nay mang `deprecated=True`, kèm
đoạn ghi ở đầu module nói rõ vì sao còn đó. Gỡ endpoint cùng lượt với UI
là **hai thay đổi lớn trong một lượt**, hỏng thì không biết vì cái nào.
Bảng `benchmarks` giữ nguyên dữ liệu — xoá dữ liệu không hoàn tác được
bằng cách deploy lại.

### Một lỗi của tôi, lặp lại

Test `TestOverHttp` tôi viết khẳng định endpoint **không** khoá theo phê
duyệt bằng cách tìm chuỗi `"approved"` trong source — và nó **vấp đúng
docstring của chính hàm đó**, nơi tôi giải thích quy tắc. Đúng cái bẫy
test công bằng replan đã dính. Sửa bằng cách soi `__code__.co_names` thay
vì văn bản.

### Test

- Suite web: **598 passed**, `tsc` sạch. (Số nhỏ hơn 665 vì bốn suite của
  trang đã nghỉ hưu bị xoá; `observation-class.test.tsx` mới mang các
  khẳng định còn sống.)
- `tests/api/test_decision_markdown.py` — 19 test, gồm cả nội dung độc
  (dấu `|` và xuống dòng làm vỡ bảng Markdown).
- `ruff check .` sạch.

## Hai lỗi runtime sau P6 — và cả hai đều là **cùng một loại lỗi**

Cả hai đều là *"code đọc một hình dạng, dữ liệu có hình dạng khác, và
không test nào chạm tới đường dẫn thật vì mọi test đều ở mức source"*.

### Lỗi 1 — form deployment sập: `NOISE_DEFAULTS[path]` là `undefined`

Ba lời gọi `noiseField` truyền **tên lá** thay vì đường dẫn đầy đủ
(`"localization_drift_m"` thay vì
`"environment.sensor_noise.localization_drift_m"`). `NOISE_DEFAULTS`
khoá theo đường dẫn đầy đủ nên tra ra `undefined`, đọc `.step` thì ném.

Lỗi của tôi trong A3: khi đổi `NOISE_DEFAULTS` sang khoá dotted path để
thoả hàng rào D1, tôi sửa bốn call site **một dòng** và bỏ sót đúng ba
call site **nhiều dòng**. Vỡ từ commit `4202648` — `/deployments` sập từ
đúng lúc bật sẵn bốn nhiễu.

**Vì sao hàng rào D1 không bắt được, và đây mới là phần đáng học.** Nó
hỏi *"đường dẫn này có xuất hiện trong file không"*. Cả bảy đều có —
trong chính `NOISE_DEFAULTS`. **Có mặt không phải là có nối dây.**

Sập lại là kết cục **may mắn**. Nếu có `step` dự phòng, ba ô đó sẽ hiện
bình thường trong khi đọc/ghi vào một khoá cấp cao nhất mà deployment
không có — ba trong bốn nhiễu form tuyên bố bật sẵn sẽ chỉ là trang trí,
và không gì trên màn hình nói ra.

Sửa: ba đường dẫn; `noiseField` ném lỗi **có tên** thay vì `TypeError`;
5 test quét **đối số tại từng call site**, hai chiều — mọi lời gọi phải
có mục, và mọi mục phải có ô điều khiển (một biên độ điền vào draft mà
không có cách xem hay tắt là một điều kiện áp dụng lặng lẽ). Kèm một
test chống rỗng vì cả hai regex có thể khớp không gì.

### Lỗi 2 — sân thử sập: `mission.start.x` là `undefined`

**Tôi kiểm tra dữ liệu thật thay vì đoán.** Trong `planbench.db`:

| deployment | dạng `start` |
|---|---|
| `open_hall_v2`, `warehouse_a_v2` | `[2.0, 8.0, 0.0]` — bộ ba |
| `open_hall_2`, `test_corridor` | `{x, y, theta}` — đối tượng |

**Cả hai đều hợp lệ.** Dạng tài liệu của HĐ-2 viết pose là
`[x, y, theta]`, và `Mission` nhận nó qua một before-validator để dán
nguyên văn một tài liệu hợp đồng vào được; profile đi qua `model_dump`
thì ra `{x, y, theta}`.

Trang sân thử mặc định chọn deployment đầu tiên — là một trong hai cái
shipped — nên sập ngay lần vẽ đầu. Nó **đọc một nửa hợp đồng**.

Sửa: một hàm `poseOf` ở ranh giới, nhận cả hai dạng. Trả `null` chứ
không trả pose gốc toạ độ khi giá trị không phải pose — **(0, 0) là một
chỗ có thật trên mọi bản đồ**, thường là góc, thường nằm trong tường, nên
thay thế bằng nó là vẽ robot ở nơi nó không có. Kiểu của `start`/`goal`
trên wire đổi thành `unknown`: khai một `Pose` ở đó là một khẳng định dữ
liệu không tôn trọng, và TypeScript sẽ đứng ra bảo lãnh cho cú sập.

### Gốc rễ của lỗi 2 — và nó không nằm ở frontend

`scripts/import_runs.py` lưu **YAML thô** (`yaml.safe_load`) làm profile,
trong khi docstring của chính nó nói *"as the API stores it"* — câu đó
**sai**. Hai đường nạp cùng một hợp đồng nên đã ghi hai hình dạng vào
cùng một bảng.

Sửa: importer nay validate qua `TaskProfile` rồi `model_dump(mode="json")`
— câu docstring thành đúng, và một profile YAML hỏng bị **từ chối lúc
import** thay vì được ghi thành một dòng không gì đọc nổi.

**Bốn dòng đang có trong DB của anh tôi không đụng vào.** Hai dòng shipped
vẫn ở dạng bộ ba; frontend đọc được cả hai nên chúng chạy bình thường.
Muốn chuẩn hoá thì chạy lại `python scripts/import_runs.py` — nhưng đó là
ghi đè dữ liệu, nên tôi để anh quyết.

### Test

- Web: **609 passed**, `tsc` sạch, `ruff check .` sạch.
- Không test nào trong hai nhóm này là test source-grep thuần: nhóm nhiễu
  soi **đối số tại call site**, nhóm pose gọi **hàm thật** với cả hai
  dạng dữ liệu có thật trong kho.

## Quét toàn hệ thống tìm lỗi cùng loại

Hai lỗi vừa sửa thuộc hai lớp. Tôi quét cả hai lớp thay vì chỉ vá hai
chỗ đã lộ.

### Lớp A — tra bảng rồi lấy thuộc tính (`TABLE[key].prop`)

Quét mọi bảng tra cứu trong web và Python. Sáu chỗ còn lại, **tất cả đều
an toàn** và an toàn vì lý do khác nhau — nên tôi kiểm từng cái chứ không
đếm:

| chỗ | vì sao không vỡ được |
|---|---|
| `SCENARIO_LIBRARY[name]` | bọc `try/except KeyError` |
| `_OBJECTIVE_FIELDS[objective]` | có kiểm tra `not in` ngay trên |
| `EXTENSIONS[kind]` | khoá là `DocumentKind` (Literal) |
| `PROVIDERS[provider]` ×2 | khoá là enum |
| `SEARCH_SPACES[algorithm_id]` | caller duy nhất lặp `list(SEARCH_SPACES)` |

Không chỗ nào khác lặp lại lỗi `NOISE_DEFAULTS`.

### Lớp B — dữ liệu có hơn một hình dạng hợp lệ

Trước hết tìm **nguồn sinh**: validator `mode="before"` nào nới rộng
hình dạng đầu vào. Có đúng ba, và chỉ **một** cái tạo ra hai hình dạng
*được lưu*:

- `_pose_from_triplet` — nhận `[x, y, theta]` **và** `{x, y, theta}`. ✅
  đây là thủ phạm.
- `_drop_declared_identity` — bỏ một trường, không tạo hình dạng mới.
- `_canonical_observations` — luôn ra tuple chuỗi, một hình dạng.

Vậy `Mission.start/goal` là trường **duy nhất** của hợp đồng có hai mã
hoá. Rà mọi chỗ đọc nó:

- **Web**: chỉ `/simulate` đọc thô — đã sửa. `/deployments` chỉ đọc
  `constraints`/`environment` có `?? {}`. `/decisions` chỉ đọc `base.id`.
  `TraceViewer` nhận `{x, y}` do endpoint dựng qua model đã validate.
- **Backend**: `derive` deep-copy rồi `model_validate` — an toàn. Ghi
  YAML ra đĩa — round-trip, an toàn.
- **Chữ ký crash `.toFixed`**: rà 45 call site. Vật cản động phân biệt
  bằng `obstacle.type` trước khi đọc `center` hay `min_x` — đúng. Các
  trường trên report tôi **đối chiếu với 8 artifact thật trên đĩa**, tất
  cả đều có đủ trường trang chi tiết đọc.

### Một chỗ nữa cùng gốc — tìm ra bằng quét, không phải bằng vấp

Guard chống định nghĩa lại `task_profile_id` so sánh **dict thô**:

```python
if existing.profile != profile:   # hai bản mã hoá = "nội dung khác"
```

Hai mã hoá của **cùng một** deployment đọc thành "nội dung khác", nên
nộp lại một profile **không đổi gì** bị từ chối bằng thông báo *"already
exists with different content"*. Cùng gốc rễ, triệu chứng khác — và có
thật với dữ liệu hiện tại của anh, vì `import_runs.py` đã nạp
`open_hall_v2` ở dạng bộ ba.

Sửa: hàm `same_deployment` so sánh **hai thế giới**, không so hai từ
điển — validate cả hai qua `TaskProfile` rồi so. Nhân tiện nó cũng miễn
nhiễm với thứ tự khoá, `1` với `1.0`, và một trường bỏ trống bằng đúng
giá trị mặc định — không cái nào là một thế giới khác.

Tài liệu không validate được thì **quay về so byte**, tức từ chối trừ
khi trùng khít. Đó là hướng an toàn: guard tồn tại để chặn một id mang
hai thế giới, nên một câu hỏi không trả lời được **không được** phép
thành "giống nhau".

Dùng chung ở cả hai kho (in-memory và SQL) — trước đó là hai bản sao của
cùng một dòng so sánh.

5 test mới, gồm cả **chiều ngược**: đích dịch 1 m vẫn phải là deployment
khác, biên độ nhiễu đổi vẫn phải là thế giới khác (HĐ-3.1 không băm
nhiễu — đúng cái bẫy guard này sinh ra để chặn). Nới guard thành vô dụng
là cách sửa sai duy nhất đáng sợ ở đây.

### Kết luận quét

Không còn chỗ nào cùng loại. Hai lớp đều đã rà hết, và chỗ thứ ba tìm
được đã sửa kèm test.

## Vì sao sân thử chạy một episode lại lâu — và cách sửa (b)

Câu hỏi của An: một episode trên sân thử rất lâu, trong khi trước đây
chạy deployment 120 episode lại rất nhanh. **Hai nguyên nhân**, và cái
thứ hai là lỗi của tôi ở P4.

### 1. Lần chạy 120 episode kia **không mô phỏng gì cả**

Trên đĩa có **1164 file trace Parquet**. `reuse_traces` mặc định `True`
ở server và UI không bao giờ gửi cờ này. `pipeline.simulate` ghi thẳng
trong docstring: *"Run every (candidate, context) pair that **has no
trace yet**"*.

Nên "120 episode rất nhanh" nghĩa là **đọc file**, không phải chạy nhanh.
Hai bên chưa bao giờ so được với nhau. Sân thử thì luôn mô phỏng mới —
bắt buộc phải thế, vì nó tồn tại để cho xem **chính cấu hình này**.

### 2. Và 90% thời gian đó **không phải mô phỏng**

Đo trên đúng `open_hall_v2` + `astar+dwa` + `dwa_coarse`, seed 0:

```
legacy_metrics=True  :  50.14s   416 steps
legacy_metrics=False :   5.10s   416 steps
chi phí tính metrics :  45.04s   (90% wall clock)
quỹ đạo giống hệt    :  True
```

cProfile chỉ đúng thủ phạm: `clearance_to_grid` gọi `get_cell`
**17 triệu lần** — nó quét **toàn bộ 480×320 = 153.600 ô cho mỗi điểm
quỹ đạo**. Docstring của chính hàm đó nói *"intended for metrics and
tests, **not per-step hot loops**"*, và docstring của `run_stack` nói
`legacy_metrics=False` tồn tại một phần vì **chi phí**.

`run_contract_episode` — đường đánh giá thật — truyền
`legacy_metrics=False`. **Sân thử của tôi thì không**: tôi dựng nó trên
`SimulationService.run`, vốn để mặc định `True`.

**Fidelity vẫn đúng** — quỹ đạo giống hệt từng chữ số, cùng engine cùng
seed, nên câu "thứ bạn xem đúng là thứ phép so sẽ chạy" không sai. Cái
tôi bỏ sót là nó trả tiền cho một phép tính mà lần chạy đánh giá không
bao giờ trả, và phép tính ấy đắt gấp **chín lần** chính episode.

### Sửa theo (b): đường legacy dùng bản quét có cửa sổ

`clearance_to_obstacles` — caller sản phẩm **duy nhất** của bản quét
toàn bản đồ — nay gọi `clearance_to_grid_within` (cửa sổ 2 m).

```
trước:  50.14s
sau  :   7.09s      cùng 416 bước, cùng trạng thái
```

**Vì sao cửa sổ không làm mất gì bị phán xét.** HĐ-5 cho cột
`clearance_m` **đã dùng bản có cửa sổ từ trước** — nên đây là làm hai
đường **thống nhất**, chứ không phải hạ chuẩn một đường. Cả hai mốc an
toàn đều bão hoà thấp hơn cửa sổ rất nhiều: `min_clearance` neo ở hai
bán kính robot (~0.52 m), nên một robot cách mọi thứ 2 m chấm điểm giống
hệt dù khoảng cách thật là 2 m hay 20 m. Trong lần đo trên,
`min_clearance` = 0.344 m — nằm gọn trong cửa sổ, tức **chính xác tuyệt
đối**.

**Cái thật sự đổi**: `mean_clearance` trên bản đồ trống, nơi giá trị quá
2 m nay đọc thành 2 m. Đó là một **sàn**, và là hướng an toàn — báo ít
chỗ trống hơn thực tế chỉ có thể làm một ứng viên trông tệ hơn, không
bao giờ cho lọt.

`clearance_to_grid` **giữ nguyên** làm bản tham chiếu chính xác để test
bản có cửa sổ đối chiếu. Xoá nó đi là làm một phép xấp xỉ mất chỗ dựa để
chứng minh nó chính xác ở nơi cần chính xác.

6 test mới trong `tests/test_collision.py`, gồm **chiều ngược**: gần vật
cản thì con số phải **không đổi**, và một vật cản hình học gần hơn vẫn
phải thắng lưới — cửa sổ hoá không được làm mất nửa còn lại của câu trả
lời.

**Một lỗi nhỏ khi viết test**: lần đầu tôi chọn điểm (2.5, 2.5), đúng tâm
ô bị chặn, nên hai vế đều ra `-0.2` và phép so `<` sai. Nếu tôi viết
`<=` thì test sẽ xanh **vì lý do sai**. Đổi sang một điểm có chỗ trống
thật và khẳng định hai giá trị cụ thể (0.8 và 0.25).

### Một quan sát ngoài lề

Episode đo ở trên kết thúc **`stuck`** ở bước 416, không tới đích. Đó là
seed 0 trên hall thật với nhiễu thật — không phải lỗi do tôi gây ra,
nhưng nghĩa là người mở sân thử lần đầu sẽ xem một con robot bị kẹt.
Đáng ghi vào danh sách xem xét, không phải nợ kỹ thuật.

### Full suite backend — và một test đỏ **đúng như đã báo trước**

Lượt đầy đủ đầu tiên kể từ A3: **2464 passed, 1 failed, 6 skipped**
(21 phút).

Test đỏ duy nhất là `test_clearance_in_empty_grid`, và nó đỏ **chính vì
cái đánh đổi tôi đã nêu trước khi An duyệt (b)**: robot đứng giữa một bản
đồ 5×5 m trống, khoảng cách thật tới biên là 2.0 m, bản có cửa sổ báo
1.5 m (sàn cửa sổ 2 m trừ bán kính 0.5 m).

Đây **không phải hồi quy** — nó là hành vi mới đã được quyết định. Nên
tôi sửa test bằng cách **nói ra sự thật mới kèm lý do**, không phải bằng
cách đổi con số cho xanh, và tách nó thành **hai** test để ghi lại đúng
*ranh giới*:

- xa mọi thứ thì bị **sàn** (1.5) — kèm lý do vì sao vô hại: mốc
  `min_clearance` neo ở ~0.52 m nên 1.5 và 2.0 đều chấm 1.0 phẳng, và
  sàn là hướng an toàn;
- gần tường thì **vẫn chính xác** (0.3) — nếu thiếu vế này thì cặp test
  chỉ ghi lại một phép tính rẻ hơn mà không chứng minh nó còn đúng ở nơi
  giá trị có thể đổi một chỉ số.

Một test chỉ đổi `2.0` thành `1.5` sẽ xanh mà không nói gì; hai test này
nói ra chính xác cái gì đổi và cái gì không.

Đang chạy lại full suite trên cây đã sửa.

**Lưu ý về quy trình**: lượt full suite đầu tiên tôi phải **dừng giữa
chừng** vì nó bắt đầu trước khi tôi sửa `collision.py` — kết quả của nó
mô tả một cây code không còn tồn tại, báo cáo bằng nó là báo cáo sai.

## Hai khoảng trống An phát hiện khi dùng sân thử

Cả hai đều là **năng lực đã có sẵn trong repo nhưng không nối tới luồng
mới** — không phải thứ phải xây từ đầu.

### 1. Vật cản không hiện — dây đứt ở đúng một chỗ

Chuỗi này đã hoàn chỉnh từ trước, **trừ một mắt xích**:

| tầng | có sẵn? |
|---|---|
| Engine ghi vị trí vật cản tại mỗi mẫu | ✅ `TrajectoryPoint.obstacles` |
| Schema mang trường đó | ✅ |
| `MapCanvas` vẽ được | ✅ `dynamicObstacles` |
| **WebSocket gửi đi** | ❌ **bỏ rơi** |
| Trang sân thử truyền vào | ❌ |

Nên một episode được xem trực tiếp cho thấy con robot **né một khoảng
không** — trên đúng cái màn hình mà toàn bộ mục đích là nhìn xem nó đang
né cái gì.

Sửa: WS gửi thêm `obstacles` cho mỗi mẫu; `useEpisodeStream` giữ lại;
trang vẽ vật cản **tại đúng thời điểm playhead đang hiện**, không phải
tại t=0 — một vật cản đóng băng ở vị trí xuất phát còn tệ hơn không vẽ,
vì nó trông giống một sự thật về episode.

Đây là **ground truth, chỉ để phát lại** — không planner nào được đưa
cho nó (HĐ-4). Và danh sách vắng mặt được vẽ thành **không có gì**, chứ
không phải thành "lối đi trống": *"chúng tôi không ghi lại"* và *"lúc đó
trống"* là hai khẳng định khác nhau, và chỉ cái thứ hai làm người ta yên
tâm.

### 2. Không có 2.5D — component đã có, chỉ chưa ai gọi

`Scene25D` tồn tại sẵn, nhận đúng những props sân thử đã có
(`startPose`, `goalPose`, `robotPose`, `plannedPath`, `trajectory`,
`obstacles`), có sẵn thanh chỉnh góc nhìn và chiều cao tường. Nhưng
**chỉ `/library` dùng** — luồng quyết định không có chỗ nào gọi nó.

Lần sửa đầu tôi gắn nút chuyển **chỉ vào sân thử**. An báo lại là vẫn
không thấy 2.5D ở deployment — và An đúng ở điểm lớn hơn cái tôi sửa:
**gắn nút vào từng trang chính là cơ chế đã đẻ ra sự không nhất quán
này.** Sáu bề mặt vẽ map là sáu lần có thể quên.

Sửa lại cho đúng: một component `MapView` **sở hữu việc chuyển chế độ**,
và mọi bề mặt vẽ map đi qua nó.

**Vì sao là nút chuyển chứ không phải thay thế.** Hai chế độ trả lời hai
câu hỏi khác nhau: bản 2D từ trên là nơi **đọc một toạ độ**; bản 2.5D là
nơi **cảm nhận được "nó có lọt qua đó không"**. Không cái nào thay được
cái kia, nên không cái nào được là lựa chọn duy nhất. Mặc định mở ở 2D —
đúng thứ trang này vẫn làm, và đúng thứ người đang soi số liệu cần.

| bề mặt | trước | sau |
|---|---|---|
| sân thử `/simulate` | chỉ 2D | 2D ⇄ 2.5D |
| `MissionPlacer` (form deployment, panel chạy so) | chỉ 2D | 2D ⇄ 2.5D |
| `MapPainter` (`/maps/[id]`, form deployment) | chỉ 2D | 2D ⇄ 2.5D |
| `/scenarios/[id]` | chỉ 2D | 2D ⇄ 2.5D |
| `TraceViewer` (`/decisions/[id]`) | chỉ 2D | 2D ⇄ 2.5D |
| `/library` | **chỉ 2.5D** | 2.5D ⇄ 2D |

`/library` là khoảng trống **ngược lại**: nơi duy nhất có 2.5D mà không
có 2D, tức không đọc được toạ độ. Giờ mở ở 2.5D (vì người ta xem trước
scenario là để thấy hình dạng) nhưng bản phẳng chỉ cách một cú click.

**Vì sao là nút chuyển chứ không phải thay thế.** Hai chế độ trả lời hai
câu hỏi khác nhau: bản 2D từ trên là nơi **đọc một toạ độ**, đo vòng dung
sai, và **click vào một ô**; bản 2.5D là nơi **cảm nhận được "nó có lọt
qua đó không"**. Mặc định mở ở 2D — đúng thứ mọi trang vẫn làm.

**Sửa được thì không sửa im lặng.** Phép chiếu 2.5D **không có nghịch
đảo**: một điểm ảnh trên màn hình ứng với cả một tia xuyên qua cảnh, chứ
không ứng với một ô. Nên ở chế độ 2.5D, `MapView` **nói ra** rằng việc
đặt điểm/vẽ nằm ở bản phẳng, thay vì nhận click rồi lặng lẽ bỏ đi — nhận
rồi bỏ thì đọc thành một cái canvas hỏng.

`TraceViewer` cũng có nút chuyển, kèm câu nói rõ **cái nó đánh đổi**: bản
phẳng tô màu đường đi theo khoảng hở (đó là lý do viewer này có code vẽ
riêng), bản 2.5D thì không.

**Test quan trọng nhất là test quét cả app**: nó duyệt mọi `.tsx` trong
`src` và đỏ nếu có màn hình nào gọi thẳng `MapCanvas` hoặc `Scene25D` mà
không qua `MapView`. Kèm một test chống rỗng — một lần quét không tìm
thấy gì sẽ làm khẳng định trên thành đúng-vô-nghĩa.

Suite web: **624 passed**.

## Xoá deployment — và một quy tắc cũ phải mở cửa

### Khảo sát trước: khoá ngoại đã nói sẵn câu trả lời

`decision_runs.task_profile_id` là `ON DELETE **RESTRICT**`, không phải
cascade. Có chủ ý: một lượt chạy là **khẳng định *về*** một deployment,
nên mất chủ thể thì nó không phải bản ghi nhỏ hơn mà là bản ghi **không
đọc được**.

Nên đúng như An mô tả, và lý do nằm sẵn trong lược đồ:

| trạng thái | hành vi |
|---|---|
| chưa chạy bao giờ | xoá thẳng — là một bản mô tả, xoá không phá gì đã đo |
| có lượt chạy thường | 409 kèm **số đếm**, xác nhận thì xoá cả hai |
| **có lượt chạy đã duyệt** | **409 tuyệt đối** — không xác nhận nào đi qua |

### Lời từ chối mang theo số đếm, không phải "bạn chắc chứ?"

Hộp thoại hỏi được *"xoá 7 lượt chạy, 2 trong đó đã duyệt?"* thì trả lời
được; *"bạn chắc chứ?"* thì không.

Và số đếm đến **từ server**, không phải trang tự đếm: một con số trình
duyệt tự tính là **câu trả lời thứ hai**, tự do lệch với câu server đã từ
chối dựa trên — kể cả trong khoảng giữa lúc tải danh sách và lúc bấm nút.
Nên trang **luôn thử trước**, kể cả với dòng trông sạch.

**Một bẫy phải sửa dọc đường**: client **lọc bỏ** mọi `details` không có
dạng `{path, message}` — số đếm của tôi bị vứt trước khi tới nơi. Sửa ở
đúng đó: `FieldError` giữ thêm `raw`, còn `fieldErrorsOf` vẫn hẹp đúng
như form cần.

### Đã duyệt: chặn tuyệt đối, và cờ xác nhận **không** đi qua

`delete_runs=true` cũng dừng ở đây. Nếu cờ vượt được thì xác nhận **chính
là** toàn bộ hàng rào — mà hàng rào rộng đúng một cú click là gờ giảm
tốc. Hộp thoại vì thế **không render nút xác nhận nào cả** trong trường
hợp này, chỉ có link mở các lượt chạy đang giữ; lời từ chối nêu đúng id
của chúng thay vì để người ta đi tìm.

### Phải xây "thu hồi phê duyệt", nếu không thông báo là cái tường có biển chỉ đường

An chốt *"phải bỏ duyệt trước mới cho xoá"*. Nhưng `decide_config` từ
chối mọi trạng thái khác `pending`, kèm câu **cố ý**: *"That decision
stands; the way to change a recommendation is a new run."* Nên nếu chỉ
chặn, thông báo sẽ bảo người dùng làm một việc **không tồn tại** — đúng
loại lỗi tôi đã chê suốt phiên này. Tôi hỏi An và An chốt thêm thao tác
thu hồi.

`POST /decisions/{id}/config-approval/withdraw` — tên đặt khớp endpoint
hàng xóm.

Ba quyết định thiết kế, mỗi cái có lý do:

- **`approved` → `pending`, không phải `rejected`.** Thu hồi nói *"chưa
  quyết lại"*, không phải *"quyết là không"*. Ghi cái sau là đặt vào hồ
  sơ một phán quyết **không ai đưa ra**.
- **Ghi thêm, không phải xoá.** Sự kiện duyệt ở lại; sự kiện thu hồi nằm
  cạnh, kèm tên người và lý do. Một phê duyệt có thể lặng lẽ biến mất là
  một phê duyệt **không ai dựa vào được** — HĐ-14 vì thế vẫn nguyên vẹn.
- **Không giới hạn tài khoản khác** như lúc duyệt. Tự rút chữ ký của
  chính mình không phải xung đột lợi ích mà HĐ-14 canh.

**Đây là đổi một quy tắc cũ có chủ ý.** Tôi ghi rõ lý do trong docstring
của cả hai kho và của endpoint, chứ không lặng lẽ nới.

### Test

- Backend `test_test_bench.py`: **29 passed** — hai nhánh xoá, 404, chưa
  đăng nhập, cờ `delete_runs` **không** biến thành force-delete, cờ
  **không vượt** được phê duyệt, lời từ chối nêu đúng id, thu-hồi-rồi-xoá
  đi được, nhật ký giữ **cả hai** sự kiện đúng thứ tự, ghi đúng ai và vì
  sao, và thu hồi cái chưa từng duyệt bị từ chối.
- Web: **639 passed**.

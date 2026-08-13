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

# Thi hành plan role: xong cả 13 phase — 2026-08-27

Báo cáo cập nhật lần 5, và là bản **kết thúc plan**. Bản đầu phủ P0–P2,
bản hai tới P6, bản ba tới P8, bản bốn thêm P12 và nửa P9; bản này thêm
**đuôi P9, P10 và P11** — tức là toàn bộ phần web. Tên file giữ nguyên
để link cũ không hỏng.

Plan: `plans/2026-08-27/thiet-ke-role-engineer-reviewer-admin.md` (13
phase). Khảo sát nền: `notes/2026-08-27/tongduyan_khao-sat-hien-trang-role.md`.

## 0. Trạng thái một bảng

| Phase | Nội dung | Trạng thái | Commit |
|---|---|---|---|
| P0 | Hợp đồng HĐ-14 + docstring | xong | `9d05905` |
| P1 | Role, capability, profile, invariant | xong | `1174261` |
| P2 | Đóng auth, ownership, archive, WS ticket | xong | `8ccb20a` |
| P3 | Plugin governance + publication | xong | `b957d3f` |
| P4 | Pin định danh candidate | xong | `8ec02f1` |
| P5 | Dừng hợp tác tại episode boundary | xong | `e977df8` |
| P6 | Luồng duyệt claim/ack/decide | xong | `56d1f2d` |
| P7 | Reliance dẫn xuất + cảnh báo trên config | xong | `74456a9` |
| P8 | Admin: users/roles, audit, break-glass | xong | `a2c4e51` |
| **P12** | **Desktop: launcher, ba tài khoản, ca upgrade** | **xong (làm sớm)** | (commit) |
| P9 | Web: session/nav/badge/banner, duyệt bốn bước, `/algorithms` | xong | `f10fb1a` + 2 |
| P10 | Web: Review Queue bốn tab, dashboard theo role | xong | `8463705` |
| P11 | Web: `/admin/users`, `/admin/audit`, gom mục Quản trị | xong | `d99bc77` |

Nhánh `tongduyan_roles-capabilities` từ `main`, chưa push remote nào.

**P12 làm sớm, ra trước P9–P11.** Nó là thứ chặn phát hành, nhỏ, và
không phụ thuộc web — để sau thì nhánh này nằm ở trạng thái "không được
release" lâu hơn cần thiết.

**Nhánh mang hai luồng việc.** Ngoài commit role của tôi, An đã commit 5
bản ghi AI-analyst lên cùng nhánh (`3f7f0b4`, `7a4b10f`, `27a6035`,
`a644369`, `dfcbed4`) — toàn bộ `docs/antongduy/`, không đụng code. Muốn
mở PR riêng cho từng luồng thì phải tách trước.

Stash `stash@{0}` của An (gitignore + ai-log của `tongduyan_updater-cdn`)
vẫn treo.

---

## 1. Backend giờ làm được gì

Ba gói capability **không lồng nhau**, một người mang nhiều gói:

| | engineer | reviewer | admin |
|---|---|---|---|
| Tạo/chạy run, sửa map/scenario/deployment của mình | ✅ | ❌ | ❌ |
| Gửi run đi duyệt | ✅ | ❌ | ❌ |
| Claim / acknowledge / approve / withdraw | ❌ | ✅ | ❌ |
| Import / validate / publish / disable thuật toán | ❌ | ✅ | ❌ |
| Gán role, khoá tài khoản, đọc audit đầy đủ | ❌ | ❌ | ✅ |

Cộng `demo_owner` — ngoại lệ theo deployment profile, mang toàn bộ
capability, đúng một người mỗi database, **không gán được từ
`/admin/users`**, và profile `production` từ chối khởi động khi còn ai
mang nó.

---

## 2. Từng phase — cái gì đã đổi

### P0–P2 (đã mô tả ở bản báo cáo trước)

Hợp đồng HĐ-14 viết lại + bump 7.0.0 MAJOR; `user_roles` +
`require_capability` + deployment profile + invariant; đóng auth mọi
route ghi và mọi GET tài nguyên; WS ticket dùng một lần; ownership +
archive cho map/scenario.

### P3 — publish thành hành động (`b957d3f`)

`plugin_publications` là **lịch sử append-only**: publish revision mới
đóng dấu `superseded_at` lên dòng cũ, reviewer rút thì đóng dấu
`unpublished_at`. Hai cột vì hai sự thật — upsert theo `plugin_id` sẽ làm
cả hai thành cùng một sự vắng mặt. `held` là tạm ngưng, `disabled` là
**terminal**. Cờ `PLANBENCH_ALGORITHM_GOVERNANCE` mặc định **tắt**; route
governance trả 404 khi tắt.

### P4 — pin định danh (`8ec02f1`)

`run_identity.py`: theo con trỏ stack **một lần** lúc request, **recheck**
lúc job start. `decision_run_candidates` ghi cùng transaction với run.
Production chỉ pin cái đã publish; validation phải nêu `bundle_id`.
Script `backfill_run_candidates.py` cho run cũ.

### P5 — dừng tại ranh giới episode (`e977df8`)

`simulate(should_stop=)`. `SweepStopped` **raise**, không chấm phần dở —
ngược với `KeyboardInterrupt` có chủ ý. `Job` mang `created_by`,
`purpose`, `run_id`, `pinned`.

### P6 — duyệt là bốn bước (`56d1f2d`)

Migration `0015`: `subject_kind`/`subject_id`,
`requested_reviewer_user_id` tách khỏi `claimed_by_user_id`, cộng
`available_to_pool`.

Luật cốt lõi: **acknowledge thuộc về claim, không thuộc về run.** A đọc
rồi nhả, B nhận — nếu chỉ hỏi "có ai đọc chưa" thì B ký được mà chưa mở
gì, và trail nhìn vẫn đủ. Điều kiện: có sự kiện acknowledge với
`actor == claimed_by` và `acknowledged_at >= claimed_at`.

Route mới: `/submit`, `/submit/cancel`, `/claim`, `/takeover`,
`/release`, `/review-state`. `decide_config` có 5 điều kiện. Run không
card đóng ở `acknowledged`. Withdraw: **bất kỳ reviewer**, comment bắt
buộc. Claim tự nhả khi người giữ mất `run.review` — kiểm lúc đọc, vì
quên nhả xảy ra ở mọi chỗ khác chứ không chỉ chỗ gỡ role.

Lane benchmark giữ nguyên luật cũ, có test pin.

### P7 — reliance dẫn xuất (`74456a9`)

`reliance.py`: `active | suspended | revoked | unknown`, **tính lúc đọc**.
`approval.status` không bao giờ đổi. Revision bị **thay** vẫn `active`;
bị **rút** thì `suspended`; bị **disable** thì `revoked`.

`approved_config.yaml` vẫn trả **200** khi thuật toán bị tắt, mang
`reliance_status`, khối `warning` ở đầu file, và `candidate.bundle`
(bundle_id / revision / checksum). Disable ghi thêm sự kiện
`algorithm_disabled_after_approval` vào journal mỗi run đã duyệt —
**không** tự withdraw, vì disable có thể vì lỗi bảo mật, crash,
dependency hay đang điều tra, không ca nào chứng minh khuyến nghị sai.

### P8 — admin (commit cuối)

`/admin/users` (list, grant/revoke role có lý do, disable/enable),
`/admin/audit` (một route, projection theo capability),
`/admin/ops/jobs` + cancel break-glass có `reason`.

Hai luật đáng test riêng: **không ai tự cấp `demo_owner`** (422, kể cả
admin), và **không ai để deployment mất người quản trị** — đếm theo
capability `user.manage`, không theo tên role, trong cùng transaction.

---

## 3. Test — chỉ chạy phần vừa sửa

An nhắc (2026-08-28): **không chạy full suite**, chỉ chạy test của phần
vừa sửa. Đã ghi vào memory. Con số dưới là các bộ liên quan:

| Bộ | Kết quả |
|---|---|
| `tests/test_roles.py` | 38 pass |
| `tests/test_run_identity.py` | 16 pass |
| `tests/test_sweep_stop.py` | 7 pass |
| `tests/test_reliance.py` | 16 pass |
| `tests/api/test_api_access.py` | 18 pass |
| `tests/api/test_api_plugin_governance.py` | 22 pass |
| `tests/api/test_api_decision_review.py` | 28 pass |
| `tests/api/test_api_admin.py` | 15 pass |
| `tests/api/test_api_decisions.py` | 70 pass |
| `tests/api/test_test_bench.py` | 29 pass |
| `apps/web` — `role-pages.test.tsx` (mới) | 29 pass |
| `apps/web` — `plugins.test.ts` | 13 pass (5 mới) |
| `apps/web` — `settings-page.test.tsx` | 22 pass (1 sửa, 1 mới) |

**Tổng test mới viết: 191.**

Hai bộ backend được nới thêm ở đợt này:

- `test_api_plugin_governance.py` 19 → **22**, thêm ba test cho route
  `/published`: nó thấy đúng bản hiện hành, nó là route chứ không bị đọc
  thành bundle id, và nó trả 200-rỗng chứ không 404 khi governance tắt.
- `test_api_decision_review.py` 21 → **28**, thêm bảy test cho hàng chờ.

**Cách nghiệm thu phía web, và vì sao nó có giá trị.** Repo không có
jsdom, nên `role-pages.test.tsx` khẳng định hai loại thứ mà một bản
render cũng không giấu được: hàm thuần (`bundleStates`) và **sự thật về
mã nguồn** — capability nào gác nút nào, panel gọi endpoint nào, và mọi
khoá i18n mà file gọi có tồn tại ở **cả hai** từ điển hay không.

Cái cuối không phải vặt vãnh: khoá thiếu thì hiện ra màn hình đúng chữ
`algorithms.why.superseded`, và với người không phải tác giả thì nó đọc
như crash.

Test này bắt được hai lỗi thật ngay lúc viết:

1. Regex quét khoá `t\("..."` khớp nhầm vào `act("unpublish")` — vì
   `act(` kết thúc bằng `t(`. Đã thêm lookbehind. Nếu không, test sẽ đòi
   bản dịch cho một tham số hàm.
2. Mục `/algorithms` trong rail **không gác capability nào**. Cả ba gói
   đều giữ `algorithm.catalogue`, nên gác nó chỉ giấu mục đó khỏi tài
   khoản không có gói nào — đúng thứ cần giấu.

**Đối chiếu nền để không nhận vơ lỗi có sẵn.** Trước khi kết luận,
tôi dựng một worktree ở đúng commit `f10fb1a` và chạy cùng lệnh vitest:
nền là **28 fail / 1378**, cây của tôi là **29 fail / 1379**. Đúng một
file lệch — `settings-page.test.tsx`, và nó lệch vì **tôi** dời
`/settings` sang section Quản trị. Đã sửa test (và ghi vào đó lý do href
không dời theo). Sau khi sửa, tập lỗi của tôi trùng khít tập lỗi nền:

`advisory-ui` 8, `candidates-page` 4, `decision-prose` 3, `decisions-page`
4, `deployments-page` 1, `models-page` 1, `running-comparison` 2,
`tokens` 2, `trace-viewer` 2, `agent-dock` 1 — **28, tất cả có sẵn trên
`f10fb1a`**, không cái nào đụng file tôi sửa.

Lần cuối chạy `tests/api/` đầy đủ (sau P6, trước khi An nhắc):
**996 pass / 3 fail**, cả ba có sẵn trên `main`:

| Test | Nguyên nhân |
|---|---|
| `test_api_advice.py::…::test_an_unknown_run_is_a_404` | `DecisionRunService` thiếu `trace_summary` |
| `test_decision_export_golden.py` × 2 | golden `.md` checkout CRLF, so với `\n` |

**Lỗi do tôi gây ở đợt này** (một, đã sửa): test hàng chờ gọi
`POST /decisions/{id}/config-decision`, tên thật là `config-approval`,
nên nhận 404. Đáng nói vì nó là lỗi *đúng loại mà test này để bắt* — nếu
tôi chỉ khẳng định "trả về không phải lỗi" thay vì `== 200` thì nó đã lọt.

Ngoài ra, **hai lỗi do tôi gây và đã sửa trong lúc làm**: ba cột
`disabled_*` chèn nhầm vào bảng `models` thay vì `plugin_bundles`
(migration-vs-models bắt được), và một flaky có sẵn ở đường import
plugin — `zipfile.writestr` đóng dấu thời gian hiện tại, độ phân giải 2
giây, nên cùng nội dung build hai lần qua ranh giới giây ra hai checksum
khác nhau; đã ghim `ZipInfo(date_time=…)`.

---

## 4. P12 — desktop, làm sớm vì nó chặn phát hành

**Đã đo trước khi sửa.** Dựng đúng tình huống (DB schema 0011 + tài
khoản `admin` có `is_admin=1` + `.env` cũ) rồi boot code mới:

| | trước khi vá | sau khi vá |
|---|---|---|
| App boot, login `admin:admin` | được | được |
| profile | `production` | `desktop-single-user` |
| roles | `engineer + admin` | `engineer + reviewer + admin` |
| `run.review` | **không** | có |
| `algorithm.import` / `publish` | **không** | có |

Nghĩa là trước khi vá, giám khảo vẫn chạy được so sánh nhưng **không
duyệt được cấu hình nào và không import được thuật toán**.

**Vá launcher đặt profile thôi là chưa đủ** — đo riêng và xác nhận: kết
quả y hệt. Lý do: `.env` cũ dùng dạng hai phần `admin:admin`, không khai
role nào, nên reconcile không có gì để thêm. Launcher phải cấp **cả
profile lẫn seed roles lẫn SoD** khi file im lặng, và cấp **mỗi lần
launch** chứ không chỉ lần đầu — file viết từ hai bản trước sẽ không bao
giờ tự mọc thêm dòng.

Ba luật giữ kèm: cái gì `.env` nói rõ thì thắng (kể cả ai chọn `demo`);
password đang có được giữ nguyên; tài khoản đã đổi tên thì cấp role cho
đúng tên đó chứ không dựng thêm tài khoản mẫu bên cạnh.

Cộng: template `.env` mới seed **ba tài khoản** (`admin` ba role,
`engineer`, `reviewer`) để một máy có thể trình bày luồng theo cả hai
kiểu — một người làm hết, và hai vai tách nhau. Và `docs/DEMO-PROFILE.md`
— cách bật demo trên máy đã cài, và quy trình gỡ trước production.

`tests/desktop/test_upgrade_keeps_access.py`, **9 test**, khẳng định
**kết quả** chứ không khẳng định cơ chế: đăng nhập sau nâng cấp và làm
được việc. Đó là dạng duy nhất bắt được lỗi thứ hai, vì lỗi đó qua được
mọi assertion về profile.

---

## 5. P9 — web

**Nửa đầu (2 commit, đã báo cáo lần trước):**

- `SessionUser` mang `roles` + `capabilities`; helper `can()` và hằng
  `CAPABILITIES`. Session khôi phục từ store bản cũ mặc định **rỗng**,
  không phải "đủ mọi quyền".
- `NavItem.capability` thay `NavItem.admin`; Sidebar lọc theo capability
  server gửi, không theo tên role.
- Badge hiện **mọi** role đang giữ; `demo_owner` hiện một mình.
- `DeploymentBanner` — banner `relaxed` và `DEMO MODE` không tắt được,
  đọc từ `/health` (đã thêm khối `deployment` vào endpoint đó), có cả ở
  trang login.
- `HumanActs` thành bốn bước: Send → Claim → Acknowledge → Approve, kèm
  nút Take over (đòi lý do) và Put it back. Câu dưới nút nói **thiếu
  bước nào**.
- Cảnh báo reliance + nhãn "Tải cấu hình lịch sử" trên trang decision;
  `GET /decisions/{id}` giờ tính `reliance_status` và `reliance_warning`
  — chỉ ở route detail, vì đó là trang người ta quyết định có dùng cấu
  hình hay không, và là chỗ duy nhất đáng trả tiền cho việc tra từng
  candidate.

**Đuôi P9 — trang `/algorithms`.** Đây là phần đáng nói nhất, vì nó vá
một lỗ hổng về **thông tin** chứ không phải về quyền.

Thuật toán import trước đây chỉ đến được từ một tab bên trong trang
Models — chỗ để weights của controller mà nền tảng đã có, tức là hai
loại vật khác nhau dưới một tiêu đề. Tệ hơn: một engineer không tìm thấy
thuật toán của mình trong candidate picker thì **không có chỗ nào tra lý
do**. Lý do luôn là một trong bốn: chưa ai publish, một revision mới hơn
đã thay chỗ, host này không chạy được, hoặc reviewer đã tắt nó. Không
cái nào trong bốn hiện ở đâu cả.

Trang mới liệt kê **cả bundle chưa publish**, làm mờ, kèm đúng câu nói
vì sao. Đó là cố ý: một thuật toán biến mất khỏi danh sách thì đọc như
hệ thống hỏng, và người đi chọn không phân biệt được "không có" với
"chưa ai bảo lãnh".

Chip trạng thái là **phép chiếu, không phải cột lưu**. Server giữ ba sự
thật vuông góc — được chọn không, load được không, đã publish chưa — vì
mỗi cái do một hành động khác đặt; lưu thêm một nhãn gộp là tạo sự thật
thứ tư tự do mâu thuẫn với ba cái kia. Gộp **để hiển thị** mới đúng là
việc của cái chip.

`bundleStates()` gán nhãn cho **cả danh sách** chứ không từng dòng, vì
một trong bảy đáp án không suy ra được từ một dòng: `superseded` nghĩa
là *revision khác* của cùng `plugin_id` mới là bản hiện hành, và đó là
sự thật về các anh em của nó. `awaiting` — chưa ai publish bản nào — với
người đi chọn thì đọc như nhau, nhưng với reviewer thì chỉ một trong hai
là việc của họ.

**Thêm route `GET /algorithms/plugins/published`**, trả danh sách id
bundle đang hiện hành. Cách khác là mỗi dòng một request detail để biết
đúng một bit. Route này khai báo **trước** `/{bundle_id}` — FastAPI khớp
theo thứ tự đăng ký, để sau thì "published" bị đọc thành id và 404 vĩnh
viễn. Có test giữ riêng điều đó.

Route trả **200 với danh sách rỗng** khi governance tắt, khác với các
hành động (publish/hold/disable) vốn trả 404. Đọc tập đã publish không
phải là một hành động: khi chưa có publication nào thì câu trả lời trung
thực là "không có cái nào", còn một trang list nhận 404 sẽ phải đoán xem
có nên làm mờ hết mọi dòng hay không.

Nửa dành cho reviewer — entry point, checksum của gói, lịch sử xuất bản,
ai đã làm gì — chỉ vẽ cho người có `algorithm.inspect`. Ba nút thu hồi /
giữ lại / tắt đều **đòi lý do**; publish thì không, vì nó là hành động
duy nhất nói rằng không có gì sai.

Bảng thuật toán import ở trang Models vẫn giữ (đó là view của người
upload về đồ mình upload), thêm một câu trỏ sang `/algorithms`, để hai
chỗ không cùng phán quyết một việc.

---

## 6. P10 — hàng chờ duyệt

**`GET /decisions/review-queue` chia bốn đống, server chia chứ không
phải client lọc.** Một request là `mine` với người đang giữ, `directed`
với người được nêu tên, `pool` với mọi người còn lại, và `sent` với
người đã gửi nó. Cùng một dòng, bốn nghĩa, tuỳ ai hỏi — client lọc một
danh sách phẳng sẽ phải chép lại đúng luật đó.

Route mở cho **mọi người đọc được**, không gác sau `run.review`:
engineer cần đống `sent` để biết đã có ai nhận việc của mình chưa, và từ
chối họ thì phải đẻ thêm một endpoint thứ hai trả cùng dữ liệu dưới tên
khác. Ba đống của reviewer trả rỗng cho người không có capability, vì
luật lấp đầy chúng là luật về *ai được nhận*.

Mỗi dòng mang cờ `acknowledged`. Một hàng chờ chỉ nói *ai đang giữ* là
nói dối bằng cách bỏ sót: "Bob đang giữ" đọc thành "Bob đang xử lý"
trong khi Bob chưa mở gì. Vì acknowledgement thuộc về **claim** chứ
không thuộc về run, đây mới là bản trung thực của cùng một dòng.

Route khai báo trước `/decisions/{run_id}` — cùng cái bẫy thứ tự như
trên, cũng có test riêng.

**Web**: `/reviews` giờ có bốn tab — Runs / Algorithms / Inbox / Sent.
Hai tab sau là luồng benchmark cũ, **giữ nguyên không đụng**: gộp chúng
vào một danh sách sẽ đặt hai loại request khác nhau (một loại có claim,
một loại không) dưới cùng một bộ nút. Tab Algorithms chỉ hiện cho người
có `algorithm.publish` — engineer đọc danh sách thuật toán đang chờ
reviewer thì chỉ học được rằng mình không giúp được gì.

Panel hàng chờ cho **nhận** và **trả lại**, không cho ký. Nhận việc là
một cú bấm không mất gì — claim trả lại được. Còn nói "tôi đã đọc bằng
chứng" và ký duyệt là hành động về **nội dung** của một run cụ thể, nên
nó nằm ở trang của run đó, chỗ có bằng chứng.

Đống `sent` cố ý không có nút nào ngoài rút lại, và chỉ khi chưa ai
nhận: giật việc khỏi tay người đang đọc là chuyện khác, server từ chối.

Đống thuật toán không có nút nhận, vì nó không có request nào phía sau.
Một run đến tay reviewer vì engineer gửi; một thuật toán import đến tay
reviewer **bằng cách tồn tại** — có người upload, và nó nằm đó, không ai
được dùng, cho tới khi một reviewer publish. Nó chỉ liệt kê ba trạng
thái còn là việc của ai đó (`awaiting`, `checking`, `held`); `broken`,
`superseded` và `disabled` đã ngã ngũ, liệt kê chúng thì thành catalogue
chứ không còn là hàng chờ.

**Dashboard theo role**: `QuickActions` giờ mỗi mục khai capability của
nó. Một danh sách cố định sai với tất cả mọi người sau khi ba gói thôi
lồng nhau — reviewer không giữ gói engineer thì không tạo run được, còn
engineer được mời "publish một thuật toán" là được mời một cái 403. Khi
**chưa đăng nhập** thì vẫn vẽ đủ và trỏ về `/login`: khách chưa có
capability nào, lọc theo đó sẽ để lại một panel trống ngay chỗ sản phẩm.

---

## 6b. P11 — trang quản trị

**`/admin/users`** — ba checkbox độc lập, không phải dropdown bậc thang.
Reviewer không phải engineer cấp cao, admin không phải reviewer cấp cao,
nên UI phải nói đúng như thế. Một người giữ cả ba, hoặc một, hoặc không
gói nào (tài khoản ngủ).

Ô **lý do gác cả bảng**: chưa nhập lý do thì mọi checkbox và mọi nút đều
khoá. Đây là bảng người rà soát mở đầu tiên, và "ai cấp gói reviewer cho
người này, vì sao" là một câu hỏi — trả một nửa không phải là trả lời.

`demo_owner` **hiện chỗ ai đang giữ, và không bao giờ cấp được từ đây**.
Nó là nhân nhượng của một profile triển khai chứ không phải một việc ai
đó làm; đưa vào dropdown là biến ngoại lệ một-máy thành thứ ai cũng phát
tán được, còn giấu hẳn thì tài khoản duy nhất có nó trông như tài khoản
thường.

Nút khoá tài khoản **không hiện cho chính mình** — nó là thứ duy nhất
đứng giữa một admin và việc tự khoá mình khỏi máy của mình.

Câu dưới bảng nói rõ khoá tài khoản nghĩa là gì: không đăng nhập được,
token đang có chết ở request kế tiếp, **và không xoá gì cả**. Run, phê
duyệt, import của họ vẫn nguyên — xoá dấu vết việc đã làm không phải là
ngăn họ làm tiếp.

**`/admin/audit`** — sắp theo `sequence` chứ không theo đồng hồ, và
trang **không tự sort lại**: hai hành động có thể trùng mốc thời gian,
và "ai làm trước" đúng là câu mà một audit trail được hỏi. Cột
`override` đứng riêng vì đó là thứ người ta lọc đầu tiên. Vai và
capability của người thao tác ghi **tại thời điểm đó**, không phải thứ
họ đang giữ.

**Gom mục Quản trị.** `/admin/users`, `/admin/audit` và `/settings` vào
một section riêng trong rail. Trước đó `/settings` nằm lẫn trong nhóm
Account cùng các trang mọi người đều có, nên ai đi tìm "đổi ai được
publish ở đâu" phải đọc hết mới biết không mục nào là nó.

**Không dời href.** `/settings` và `/system` đã được link từ release
notes và từ desktop launcher từ 0.1.x; đổi URL để dọn menu là làm hỏng
một bookmark để sửa không cái gì. Đổi lại, Sidebar giờ **bỏ hẳn section
rỗng**: máy nào không ai là admin thì không thấy cả tiêu đề, chứ không
thấy một tiêu đề trống — một tiêu đề là lời khẳng định rằng dưới nó có
gì đó.

`/algorithms` cũng được gác sau `algorithm.catalogue`. Cả ba gói đều giữ
capability này, nên nó chỉ giấu mục đó khỏi đúng một loại tài khoản:
loại không có gói nào.

---

## 7. Quyết định phát sinh khi làm (plan không lường trước)

1. **`status` của plugin thêm giá trị thứ ba thay vì thêm cột.**
2. **`held` thay `quarantined`** — tên cũ đã có nghĩa khác ở discovery.
3. **Fixture `client` đăng nhập sẵn**, thêm fixture `anonymous`.
4. **Thêm tài khoản seed `erin:engineer`** cho test "bị chặn".
5. **Ticket router tách khỏi socket router.**
6. **Thứ tự refusal artefact-trước-người** — áp cho cả `decide_config`
   lẫn `withdraw_config`.
7. **`_decision_action()`** chọn `self_approve_config`.
8. **`acknowledged_under` nhận cả `review` lẫn `acknowledge`.**
9. **`ReviewConflict` → 409**, tách khỏi 403 và 422.
10. **Claim tự nhả kiểm lúc đọc**, không chỉ ở chỗ gỡ role.
11. **`latest()` khác `current()`** — "chưa gửi" và "đã xong" là hai
    trạng thái.
12. **`append_event` công khai** trên cả hai backend.
13. **`/health` mang khối `deployment`** — banner phải lên được trước
    khi ai đăng nhập.
14. **`ReviewAssignment` chứ không phải `ReviewState`** ở web —
    `ReviewState` đã nghĩa "đã đọc chưa".
15. **Launcher cấp profile + seed roles + SoD, mỗi lần launch** (§4).
16. **Thêm route `/algorithms/plugins/published`** — plan không có, vì
    plan không lường trang list cần biết bản nào hiện hành mà không
    hỏi từng dòng. Trả 200-rỗng khi governance tắt (đọc ≠ hành động).
17. **`bundleStates()` gán nhãn cả danh sách**, không phải từng dòng —
    `superseded` là sự thật về các anh em cùng `plugin_id`.
18. **Hàng chờ chia đống ở server**, không phải client lọc — cùng một
    request mang bốn nghĩa tuỳ ai hỏi.
19. **`/decisions/review-queue` mở cho mọi người đọc được**, không gác
    sau `run.review` — nếu không phải đẻ endpoint thứ hai cho `sent`.
20. **Giữ nguyên href `/settings` và `/system`** khi gom section Quản
    trị — dời URL để dọn menu là hỏng bookmark mà không sửa gì.
21. **Sidebar bỏ hẳn section rỗng** — tiêu đề là lời khẳng định rằng
    dưới nó có gì đó.
22. **`QuickActions` gác theo capability** nhưng **không lọc khi chưa
    đăng nhập** — khách không có capability nào, lọc theo đó thì panel
    trống ngay chỗ sản phẩm.

---

## 7b. Còn lại sau khi plan đóng

Plan 13 phase **đã xong hết**. Những thứ dưới đây nằm ngoài phạm vi và
đã ghi là ngoài phạm vi từ đầu, không phải nợ mới:

- governance cho model PPO (hiện chỉ thuật toán import có),
- job queue bền qua restart,
- đồng bộ settings giữa nhiều worker,
- gỡ hẳn luồng benchmark cũ (hai tab Inbox/Sent vẫn sống),
- sandbox bảo mật thật cho plugin — hiện chỉ tách process, **không phải
  sandbox**: mã upload lên đọc được file và ra được mạng như server.

---

## 7c. Một việc An phải tự quyết: có một key thật trong lịch sử git

Chạy quét secret cho `.ai-log/` trước khi commit (luật §4 CLAUDE.md) thì
ra một chuỗi khớp dạng key OpenAI thật — tiền tố `sk-proj-…` — nằm ở
`.ai-log/archive/2026-07-27.jsonl`, commit `3f9f7c1`.

**Nó đã ở trên cả hai remote**, và nằm trong 11 nhánh remote kể cả
`origin/main` (repo public) lẫn `org/main`.

Redact bản working copy (tôi đã làm) chỉ ngăn nó đi tiếp; nó **không** gỡ
được cái đã nằm trong lịch sử. Hai lựa chọn, và cả hai là quyết định của
An chứ không phải của tôi:

1. **Rotate key đó** — đây là cách xử lý đúng, và đúng bất kể có viết lại
   lịch sử hay không. Key đã public thì phải coi như đã lộ.
2. Viết lại lịch sử 11 nhánh trên hai remote (`filter-repo` + force
   push). Rủi ro cao, phá mọi clone của cả team, và **vẫn không thu hồi
   được** thứ đã public.

Khuyến nghị: làm (1), bỏ (2).

Ngoài ra quét còn khớp 7 chuỗi `sk-test-…` ở hai file archive khác. Đó là
fixture của test, không phải key — tôi đã hoàn nguyên phần redact đó và
loại `sk-test-` khỏi pattern, vì sửa chúng là làm bẩn archive đã commit
mà không gỡ được gì ai dùng được.

---

## 8. Lệnh để tiếp tục

```powershell
git switch tongduyan_roles-capabilities
python -m pytest tests/api/test_api_decision_review.py tests/api/test_api_plugin_governance.py -q
python -m pytest tests/test_roles.py tests/test_reliance.py tests/desktop/ -q
cd apps/web; npx tsc --noEmit
npx vitest run src/app/__tests__/role-pages.test.tsx src/lib/__tests__
```

Không có gì chạy nền. **Không push remote nào** — An tự push, và luật
push hai remote (`origin` + `org`) vẫn giữ.

`.ai-log/` đã quét secret và commit trong phiên này. Xem §7c trước khi
push.

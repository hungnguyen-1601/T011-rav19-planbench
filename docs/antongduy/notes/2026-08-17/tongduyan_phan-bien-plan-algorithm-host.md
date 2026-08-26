# Phản biện plan Algorithm Host (2026-08-17)

**Đối tượng:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md`
**Cách làm:** đối chiếu từng trích dẫn của plan với code hiện tại, và đối chiếu
các quyết định thiết kế với bài học đã trả giá trong reports/notes 08-08 → 08-16.
**Không đổi dòng code nào.**

---

## 1. Kết luận

Chẩn đoán của plan **đúng và trích dẫn chính xác** (đã verify từng file:line).
Khung kiến trúc giữ được. Nhưng có **tám điểm phản biện**, trong đó bốn điểm
(#2 latency charging, #3 canonicalization alias, #5 chuẩn parity, #8 thứ tự
ưu tiên) cần chốt **trước khi** bắt đầu H0, vì sửa sau khi đã đo là đúng mẫu
lỗi "phép đo xanh đo ít hơn nó khai" mà phiên P0–P6 gặp bảy lần.

## 2. Những điểm giữ nguyên — đã kiểm chứng

| # | Điểm của plan | Bằng chứng khớp |
|---|---|---|
| 1 | Runtime còn cứng: `Observation` đóng, `_reset_local` probe kwargs | `episode.py:64` đúng là object đóng 7 field; `nav_stack.py:356` probe theo tên, và docstring của chính nó ghi lại vụ `sensor_noise` mất tích im lặng — luận điểm §7.2 được lịch sử repo xác nhận |
| 2 | §7.1 không tạo fingerprint song song | `fingerprint.py` vừa xây 08-16 theo đúng triết lý "băm từ object, không từ danh sách field", có `CONDITION_ARGUMENTS` + guard test. Mọi điều kiện provider mới chảy qua đây là đúng duy nhất |
| 3 | §7.3 bọc registry, không rewrite | `registry.py` là source of truth, các test exact-set (`test_benchmark_engine.py`) đã hai lần bắt được stack thêm mà không quyết định — rewrite sẽ vứt các guard đó |
| 4 | H0 parity trước khi bọc | Khớp kỷ luật P2: golden fixture sinh trước, commit riêng, 7 ca byte-identical |
| 5 | Manifest tĩnh, discovery không import | Vấn đề thật: `_build_ppo` (`registry.py:100`) đã phải `find_spec` để tránh import torch — plan tổng quát hoá đúng cách repo đang xử lý thủ công |
| 6 | Ownership candidate/deployment/oracle trong §7.1 | Khớp P6 (`local_version` = checksum controller + lõi chung; đổi code đổi candidate_id) và khớp cách oracle P4 bị chặn đường thành candidate |
| 7 | Monolithic đi cùng host | `run_policy` (`nav_stack.py:804`) đúng là reuse loop. Điểm cộng plan chưa nói ra: hàng "loop có, loader thiếu" trong compatibility matrix chính là **trả nợ A5** (registry policy, note 13-08). Nên ghi tường minh để không làm hai lần |

## 3. Tám điểm phản biện

### 3.1 Trích dẫn stale: `dynamic_obstacles_now` không còn phục vụ replanning

Plan §5.4 viết nó "đang public để phục vụ replanning". Sai từ A1a (13-08,
contract 6.6.0): `CONTRACTS.md:422` ghi replan dựng lưới từ chính LiDAR
(`_map_as_the_robot_sees_it`), và `test_simulator_fairness.py:667` assert
`_replan` không với tới `dynamic_obstacles_now`. Docstring `engine.py:324`
tự nó stale, plan chép lại.

Hai hệ quả:

- Tốt hơn plan nghĩ: bề mặt truth hẹp hơn, có thể siết sớm hơn dự kiến.
- Nhưng phát biểu "`GroundTruthTrackProvider` là **nơi duy nhất** được đọc
  dynamic obstacle truth" quá rộng: trace recorder đọc truth để tính
  `clearance_m` (`test_trace.py:342` bind `engine.dynamic_obstacles_now`)
  và **phải tiếp tục** — đo khoảng cách thật là việc của metrics. Sửa thành:
  *duy nhất trên data plane cấp cho plugin*; đường đo của recorder nằm ngoài
  plugin boundary.

### 3.2 Latency charging chưa quyết — lỗ hổng nghiêm trọng nhất của plan

G4 định nghĩa `p99_latency_ms` là compute time của một control step
(docstring `run_stack`). Plan thêm hai nguồn compute mới mà không nói ai bị
tính tiền:

1. **Provider chạy trong tick.** Tracker deployment-owned tốn compute — tính
   cho candidate thì candidate `lidar_only` bị phạt oan; không tính thì
   candidate-owned provider được tri giác miễn phí (đúng rủi ro 5 của plan,
   nhưng ở trục latency chứ không phải trục information).
2. **Subprocess H7.** IPC serialization mỗi tick vào p99 của candidate? Nếu
   có, so in-process DWA với subprocess plugin là đo transport, không đo
   thuật toán. Plan ghi "trace có ghi serialization/runtime latency" nhưng
   không quyết G4 gồm gì.

Đề nghị chốt trong plan, trước H0: *G4 tính compute của candidate-owned code
(kể cả candidate-owned provider); deployment-owned provider và transport ghi
riêng trong trace, không vào p99; candidate mà transport chiếm ưu thế phải
hiện được trong report.* Chốt sau khi đã có số đo là thay thước giữa chừng.

### 3.3 Chiều canonicalization của alias chưa chốt — rủi ro đổi candidate_id lần thứ hai

P6 đã đổi **mọi** candidate_id một lần, An chốt có ý thức. Plan nói alias
`lidar_2d` ⇄ `planbench://channel/lidar-2d@1` "không phá identity v1" nhưng
không nói hash trên dạng nào. Nếu hai cách khai serialize khác nhau,
candidate_id drift âm thầm.

Cần một luật + một test trong DoD H1: khai bằng token v1 và khai bằng URI
alias tương ứng phải cho **cùng** candidate_id (canonical hoá về một dạng
trước khi hash), hoặc tuyên bố tường minh điều ngược lại và chấp nhận đứt id.

### 3.4 Capability URI mở tái sinh đúng lỗi mà vocabulary đóng sinh ra để giết

`observations.py` đóng vocabulary vì G6 so token literal — typo phải chết ở
parse time, không được sống thành "hardware incompatibility trông như thật".
Với URI namespace mở, typo `org.vendor://channel/radar-cube@1` (thừa chữ `s`,
sai version...) sẽ hiện ra là `registered_but_missing_provider` — nhìn như
thiếu hạ tầng, thật ra là gõ nhầm.

Danh sách trạng thái §5.1 thiếu một phân biệt: *capability id chưa từng được
đăng ký schema nào* (khả năng cao là typo — nên fail loud ngay khi nạp
manifest, kèm gợi ý gần đúng) ≠ *có schema nhưng không provider nào cấp trong
deployment này* (thiếu hạ tầng thật). Gộp hai thứ là lặp lại bài học G6 ở
tầng mới.

### 3.5 "Không drift outcome quan trọng" là chữ co giãn

Repo đã có chuẩn cao hơn chữ "quan trọng": P2 so golden **byte-identical**.
DoD H0/H2 nên tuyên bố comparator ngay trong plan: trajectory, events,
status, candidate_id, fingerprint — byte-identical; các field wall-clock
(`planner_latency_ms`...) loại trừ tường minh. Không chốt trước thì "quan
trọng" sẽ được thương lượng dưới áp lực deadline — và H2 là chỗ dễ nhất để
điều đó xảy ra.

### 3.6 Stale frame/timestamp validation là máy móc cho vấn đề MVP chưa có

Sim đồng bộ một luồng: mọi channel sinh trong đúng tick đang chạy. Stale
check ở H3 sẽ là validation surface không bao giờ bắn trong MVP — dead code
cộng false confidence ("đã có kiểm stale" trong khi chưa từng bị thử). Giữ
field timestamp/frame trong envelope (schema mở sẵn là đúng), nhưng chỉ
active check ở subprocess lane H7, nơi async là thật.

### 3.7 Ràng buộc làm provider decomposition an toàn đang có sẵn — nên nâng thành contract

`NoiseModel` là counter-based RNG (`noise.py:247`: PCG64 từ SeedSequence
`[seed, stream, step]`) — đọc hai lần cùng step cho cùng giá trị. Đây là lý
do tách `Observation` thành channels **an toàn được**: `RobotStateProvider`
và `Lidar2DProvider` gọi độc lập vẫn nhất quán với legacy path một-lần-gọi.

Nhưng an toàn này là thuộc tính của noise model hiện tại, không phải của
provider graph. H3 nên nâng nó thành contract: *provider stateless theo
step; mọi randomness phải counter-based theo (seed, stream, step) do kernel
cấp; provider giữ RNG stateful riêng là vi phạm conformance*. Per-tick cache
khi đó là tối ưu chi phí, không phải chỗ dựa đúng đắn.

Cùng nhóm: proof plugin H6 tiêu `human-state-estimates@1` từ
`GroundTruthTrackProvider` → provenance oracle → theo chính luật của plan
(DoD 7) nó **không được thành candidate thật**. DoD 2 nên thêm vế: proof
chạy được qua provider graph *và* bị từ chối ở `candidate_from_stack` vì
provenance oracle — cùng cơ chế đã chặn oracle P4. Thiếu vế này, MVP tạo ra
entry registry đầu tiên đọc world truth mà vẫn benchmarkable.

### 3.8 Ước lượng và thứ tự ưu tiên

**Ước lượng:** tổng H0–H8 là 12–15.5 ngày lý tưởng. Lịch sử gần nhất: phiên
P0–P6 lộ 10 việc ngoài kế hoạch; phiên 08-16 lộ 4 nợ hạ tầng; full suite
42–46 phút và H2 parity sẽ phải chạy nó nhiều lần. Hệ số thực tế của repo
này là ~×2. Nên đọc plan là 4–6 tuần lịch, và điều đó đáng cân nhắc vì:

**Thứ tự:** candidate gần nhất chết vì tri giác không nuôi nổi mô hình
(P5/Q0/R1), không vì plumbing không nhận được thuật toán. Các nợ đang mở
phục vụ *kết luận khoa học hôm nay*: L17 (rollout pose thật vs đám mây
believed — điều kiện cần cho mọi hướng tri giác), truyền `LidarConfig`
xuống controller (trả nợ thật của L20b thay vì chặn), câu hỏi 72 tia, và F1
`robustness_margin` — thứ đề tài tự gọi là điểm khác biệt học thuật mạnh
nhất. Host phục vụ *thuật toán tương lai chưa tồn tại*; hai proof plugin
của nó là synthetic.

Không bác plan — kiến trúc đúng và sớm muộn phải làm nếu simulator muốn
thành platform. Bác **timing mặc định**: nếu quỹ còn lại của đề tài đo bằng
tuần, một lát H0+H1 (parity fixtures + manifest SDK, ~2-3 ngày thật) là đủ
để khoá thiết kế và trả A5, phần H3–H8 xếp sau robustness_margin. Nếu An
chốt host là ưu tiên chiến lược thì chạy cả, nhưng với ước lượng ×2.

## 4. Vòng 2 — phản biện lại góp ý của An (cùng ngày)

An phản hồi bốn điểm (#2, #6, #7, #8). Kết quả đối chất:

### 4.1 (#2) Latency nhiều lớp — nhận, kèm bốn lỗ phải vá

Nhận: tách sáu lớp, `candidate_path_ms`, `end_to_end_control_ms`, p99 trên
tổng-cùng-tick chứ không cộng p99 rời. Đề xuất gốc của tôi (transport ghi
riêng, không vào gate nào) đúng là để lọt stack 40 ms IPC + 15 ms compute.

Bốn lỗ trong đề xuất của An:

1. **Mâu thuẫn với §7.1 của chính plan.** Plan viết "runtime transport thuần
   bookkeeping không đổi identity". Ngày end-to-end gate đọc `transport_ms`,
   transport đổi verdict ⇒ hết là bookkeeping ⇒ **runtime lane phải vào
   execution fingerprint**. Hệ quả: so sánh hai candidate phải cố định lane;
   candidate khai lane sản xuất trong manifest và được đo ở lane đó.
2. **Gate wall-clock trên host đang tải = gate flaky.** Repo vừa giết một
   test flaky vì so hai phép đo wall-clock (report 08-16 §3b, ba lần hiệu
   chuẩn). `transport_ms` (OS scheduling, pipe buffer) nhiễu hơn
   algorithm-compute nhiều. Gate mới phải khai luật chống nhiễu ngay trong
   plan: margin band / điều kiện tải / calibration run — không thì verdict
   đổi theo máy đang bận gì.
3. **External validity.** Transport đo được là pickle-over-pipe của harness
   trên máy dev, không phải DDS/ROS của deployment. `CONTRACTS.md:587` cấm
   hệ số quy đổi giữa hai máy — cùng logic, cấm đọc transport harness như
   transport deployment. Gate end-to-end vì thế cũng chỉ là
   `screened_on_host` (điều kiện cần), như G4.
4. **Sáu lớp phải là cột trace HĐ-5**, không phải field `StackRun` — trace
   là đầu vào duy nhất của Metrics Engine; đọc số từ chỗ khác là nguồn song
   song mà hợp đồng cấm.

### 4.2 (#6) Stale check hai tầng — nhận split, bác invariant exact-equality

Nhận: H3 kiểm invariant đồng bộ + negative test bằng faulty provider; H7 lo
freshness policy async. "Dời toàn bộ sang H7" của tôi quá tay.

Nhưng `channel.timestamp == current simulation time` **sai làm universal
invariant**: chính danh sách channel của plan có `global-path@1` — sinh lúc
tick 0 hoặc lúc replan, tiêu thụ hàng trăm tick sau; static costmap cũng
vậy. Ép equality thì hoặc invariant fail ngay trên channel hợp lệ, hoặc
provider học cách **re-stamp** dữ liệu cũ bằng giờ hiện tại — lời nói dối
về freshness sẽ tàng hình đúng lúc H7 async cần sự thật.

Sửa: capability schema khai **cadence** (`per_tick | on_change | static`);
invariant theo cadence — `per_tick`: timestamp == now, sequence == tick;
`on_change`/`static`: timestamp = lúc sinh ≤ now, reuse hợp lệ.

### 4.3 (#7a) RNG contract — nhận stateful-in-episode, chỉ ra mâu thuẫn nội tại

Nhận: "provider stateless theo step" của tôi quá mạnh — tracker/filter buộc
stateful qua step; luật addressable randomness (episode seed, stream id,
tick, entity index) + reset giữa episode là đúng.

Nhưng hai điều khoản của An mâu thuẫn nhau khi provider stateful:
*"produce() gọi hai lần cùng tick trả cùng kết quả"* + *"cache chỉ là tối
ưu, không phải điều kiện đúng đắn"*. Tracker mà produce() làm luôn việc
chuyển trạng thái thì gọi hai lần = chuyển trạng thái hai lần — idempotence
chỉ cứu được bằng memoization, tức cache thành load-bearing, đúng thứ An
muốn tránh.

Sửa: tách lifecycle — `advance(tick, inputs)` chuyển trạng thái, **kernel
gọi đúng một lần mỗi tick**; `read()` pure, gọi bao nhiêu lần cũng được.
Kèm: "không phụ thuộc invocation order" chỉ đúng **giữa các provider không
phụ thuộc nhau** — DAG vẫn ép topological order, contract nên viết rõ.

### 4.4 (#7b) Oracle lane — nhận lane, bác điểm enforcement duy nhất ở Card

Nhận: từ chối ngay tại `candidate_from_stack` bắt host dựng pipeline chẩn
đoán riêng cho oracle — trái mục tiêu hợp nhất; P4/P5 đã phải sống bằng
script rời, đưa oracle vào host là giá trị thật.

Bác chỗ này: *"mọi đường tạo production Card từ chối"* — nếu chỉ chặn ở
Card assembly thì trace/metrics của oracle-mode nằm cùng kho artifact, cùng
sơ đồ địa chỉ; `--score-only`/`--reuse-traces` có thể trộn oracle trace vào
phép so production. **Đúng hình dạng lỗ stale-trace vừa vá 08-16**: kiểm ở
một consumer, các consumer khác đọc tự do. Sửa:

- `evidence_class` vào **trace metadata** và resolved provider graph vào
  fingerprint (H4 đã định) — nhưng fingerprint chỉ *phân biệt*, không *từ
  chối*: cần fail-closed ở mọi đường đọc trace cho production scoring,
  cùng kiểu `StaleTraceError` (`pipeline.py:325`).
- Cơ chế gọn hơn rải if: **hệ kiểu**, như P1 đã ép L2 — construction thành
  công nhưng trả kiểu khác (`Candidate[production]` vs oracle-evidence);
  entry point production chỉ nhận kiểu thứ nhất. Một runtime, hai entry type.
- Ba boolean (`benchmarkable`, `recommendable`, `production compatibility`)
  nên gộp thành **một enum** `evidence_class ∈ {production, reference,
  oracle}` + quyền suy ra — `benchmarkable=False` hai nghĩa đã buộc phải đẻ
  `withdrawn` một lần rồi; ba cờ độc lập có 8 tổ hợp, phần lớn vô nghĩa.

### 4.5 (#8) Lát cắt + decision gate — nhận, ba catch

1. **Lát cắt H0+H1 không trả A5 như An viết.** A5 = registry policy +
   phân giải checkpoint ra trọng số — đó là loader, nằm ở H2/H5, không nằm
   trong danh sách file H1 (toàn parse/manifest/schema). Hoặc thêm minimal
   loader vào lát cắt (+~1 ngày), hoặc bỏ claim "trả A5".
2. **Decision gate phải khai tiêu chí trước** — kỷ luật P4 của chính repo:
   luật commit trước khi chạy. Đề xuất tiêu chí đo được: hệ số
   H1-actual/H1-ideal áp lên ước lượng H2–H8; robustness_margin có nằm trên
   critical path kết luận đề tài không; có thuật toán ngoài nào thật sự chờ
   tích hợp không. Gate không tiêu chí = vibe check vào đúng lúc mệt nhất.
3. **H1 đứng một mình = API suy đoán.** SDK contract đóng băng mà chưa
   consumer nào nhai sẽ vỡ khi H2 quay lại sau vài tuần. Kéo "synthetic
   manifest cho 4 stack built-in" từ H5 vào lát cắt — contract được validate
   bằng registry thật, không chỉ unit test, chi phí nhỏ.

## 5. Vòng 3 — An bổ sung oracle lane chi tiết và gate preregister

### 5.1 Nhận

- **Bảng quyền suy ra theo class** và **resolve từ provider graph, không
  cho plugin tự khai** — đúng nguyên tắc "core không đoán, plugin không
  tự phong".
- **Guard tập trung ở trace load boundary** thay vì rải if per-consumer —
  tốt hơn cách tôi diễn đạt ở vòng 2.
- **Discriminated Pydantic thay type hint** — đúng: hint không phải
  enforcement runtime; đúng idiom repo (frozen model + Literal).
- **Trace address namespace** — An bắt được lỗ tôi bỏ sót: metadata guard
  chặn *đọc sai* nhưng không chặn *ghi đè* — oracle trace cùng
  `(candidate_id, episode_context_id)` đè mất production trace, fail-closed
  sau đó cứu phép so nhưng bắt mô phỏng lại. Namespace
  `evidence_class/execution_fingerprint/...` chặn từ tầng địa chỉ.
- **`withdrawn` giữ riêng** — tôi sai ở vòng 2 khi nói enum "thay tổ hợp
  boolean" mà không chừa lifecycle: `evidence_class` là tư cách evidence,
  `withdrawn` là lifecycle entry; `dwa_predictive` chính là stack
  production-class bị rút. Hai trục, không gộp.
- **Gate preregister + công thức** `schedule_factor`,
  `projected_remaining ≤ allocated_host_budget`, ba điều kiện AND, fallback
  H1b — nhận toàn bộ.

### 5.2 Vá thêm vào đề xuất của An (đã đưa vào plan)

1. **evidence_class cần hai tầng.** "Resolve từ provider graph" một mình
   không sinh ra được `reference` — reference adapter D12 là reference bẩm
   sinh, không do provider nào. Luật hợp nhất:
   `execution_class = meet(entry_class, provider_graph_class)`, thứ tự
   production > reference > oracle.
2. **"Tùy scope" của reference ở production gate là chữ co giãn** — pin
   trước: chạy làm đối chứng, không phát verdict.
3. **`benchmarkable` thành derived** = `(entry_class == production) and not
   withdrawn` — giữ `withdrawn`, nhưng xoá hẳn cờ-hai-nghĩa thay vì chú
   thích thêm.
4. **Giá fail-closed nói trước:** kho trace hiện có thiếu
   `evidence_class` bị từ chối một lần — tiền lệ fingerprint rỗng 16-08.
5. **Namespace mới kéo theo:** GC policy (trace các thế giới cùng tồn tại
   thay vì đè nhau) + một lần migration kho cũ.
6. **Bản ghi gate phải commit trước H0** — kỷ luật P4 là tính chất của
   lịch sử git, không phải câu trong report.
7. **Loader H1b nối vào registry hiện tại, không cần host** — chạy qua
   `run_policy` hiện hành, nên A5 được trả độc lập với số phận H2–H8; đây
   là lý do H1b "dừng" mà không phải "vứt".

## 6. Vòng 4 — An rà 7 phát hiện trên plan v2

Nhận cả 7. Tóm tắt và phần tinh chỉnh thêm khi đưa vào plan:

1. **Manifest thiếu chỗ khai production lane (High)** — đúng: §5.9 luật 4
   đòi khai lane mà §5.1 chỉ có `runtime.kind`. Đã thêm block
   `supported_lanes / production_lane / profiles`, `resolved_runtime_profile`
   vào fingerprint, cấm fallback âm thầm. Tinh chỉnh thêm: ranh giới
   identity — `production_lane` khai trong manifest thuộc **candidate
   identity**, `resolved_runtime_profile` thực chạy thuộc **fingerprint**;
   production benchmark đòi hai thứ trùng, preflight kiểm. Không có dòng
   này thì §7.1 và §5.9 luật 4 vẫn chưa khớp nhau hẳn.
2. **`benchmarkable` derive nhập nhằng entry/execution (Medium)** — đúng,
   lỗi của tôi ở vòng 3: production entry + oracle provider vẫn là
   production entry. Đổi tên `production_eligible`, hai cổng tách biệt,
   production scoring cần cả hai. Thêm: `benchmarkable` cũ giữ làm
   serialization alias deprecated cho API/run cũ.
3. **H3 DoD rút cadence thành equality (Medium)** — đúng, bullet "stale
   frame/timestamp fail loud" là tàn dư bản gốc tôi quên sửa khi viết
   §5.4. DoD giờ chép nguyên invariant ba cadence; thêm field `revision`
   vào envelope cho `on_change`/`static`.
4. **H1b phải là phase thật (High)** — đúng và hay hơn đề xuất của tôi
   (synthetic manifest trong H1): H1b có pipeline
   registry→manifest→LegacyPluginLoader→factory, DoD riêng, gate dời về
   sau H1b, nhánh fallback thành "dừng, sạch". Tinh chỉnh: DoD H1b thêm
   bullet monolithic loader (`PolicyComponent.name` + model_registry) —
   không có nó thì claim "H1b trả A5" của vòng 3 đứt; ước lượng ghi
   +0.5–1 ngày nếu vướng nửa này. Tổng ideal 12–15 → 13–16 ngày.
5. **Latency noise protocol cần artifact (High)** — đúng; §5.9 luật 5 giờ
   trỏ vào `configs/latency-screening-v1.yaml` commit cùng prereg gate:
   warmup/repetitions/affinity, sentinel `astar+dwa` đo trước-sau,
   verdicts pass/fail/inconclusive theo CI. Tinh chỉnh:
   `confidence_method` tái dùng `statistics.bootstrap_ci` sẵn có; version
   protocol ghi trên verdict record, **không** vào execution fingerprint
   (luật phân loại của `fingerprint.py`: chỉ đổi cách chấm thì ở ngoài);
   cấm retry-until-pass thành chữ trong plan.
6. **Custom capability thiếu manifest surface (High)** — đúng, §5.4 hứa
   plugin đóng góp schema/provider/adapter mà §5.1 không có chỗ khai. Đã
   thêm `capability_schemas`/`providers`/`action_adapters` + luật
   digest/quarantine; đồng thời tinh chỉnh §5.2 luật 2: URI lạ kèm schema
   declaration là đăng ký, không phải typo.
7. **Trust semantics cho `algorithm_compute_ms` external (Medium)** —
   đúng: subprocess chỉ đo chắc được encode/round-trip/decode; số compute
   plugin tự báo là diagnostic. §5.9 thêm luật 6: cột `measured_by`, G4
   không gate trên số plugin báo, external runtime lấy end-to-end làm
   authoritative và gate report phải nói gate nào authoritative.

Hai sửa nhỏ cũng đã vào: DoD §11.1 hết chữ "outcome quan trọng"; H3 DoD
kiểm schema digest/codec/frame/cadence trước khi channel vào bundle.

## 7. Việc plan nên sửa trước khi approve

1. Sửa trích dẫn stale §5.4 về `dynamic_obstacles_now`; thu hẹp phát biểu
   "nơi duy nhất đọc truth" thành plugin data plane (3.1).
2. Latency: mô hình sáu lớp của An (4.1), kèm bốn vá — lane vào
   fingerprint, luật chống nhiễu wall-clock, status `screened_on_host`,
   sáu lớp là cột trace HĐ-5.
3. Thêm luật + DoD test canonicalization alias → candidate_id (3.3).
4. Thêm trạng thái "capability chưa đăng ký schema" fail loud lúc nạp
   manifest (3.4).
5. Thay "không drift outcome quan trọng" bằng comparator tường minh (3.5).
6. Stale check hai tầng theo đề xuất An, nhưng invariant theo **cadence**
   khai trong capability schema, không exact-equality (4.2).
7. Provider lifecycle `advance()`/`read()` + addressable randomness (4.3);
   oracle lane với `evidence_class` enum trong trace metadata, fail-closed
   ở mọi consumer, ép bằng hệ kiểu (4.4).
8. Ghi hai con số ước lượng (ideal 12–15 ngày · lịch 4–6 tuần); lát cắt
   H0+H1 + synthetic manifests kéo từ H5; decision gate có tiêu chí khai
   trước; bỏ hoặc sửa claim "H0+H1 trả A5" (4.5).

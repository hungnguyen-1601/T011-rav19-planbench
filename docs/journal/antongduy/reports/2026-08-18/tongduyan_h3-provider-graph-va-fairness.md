# H3 — provider graph, authorized bundle, và lane oracle

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §8 H3
**Trạng thái:** xong, 40 test mới xanh, **chưa commit**. Parity chạy lại
vì H3 chạm `engine.py` — kết quả ở mục 5.

---

## 1. Đã tạo

```text
host/runtime_view.py        ProviderRuntimeView + allowlist oracle
host/channel_bundle.py      CapabilityRegistry · CadenceMonitor · AuthorizedChannelBundle
host/provider_graph.py      ProviderGraph · GraphResolution
host/fairness_policy.py     FairnessPolicy · evidence class · meet()
host/providers/base.py      Provider — hợp đồng advance/read
host/providers/{robot_state, legacy_observation, lidar_2d,
                static_costmap, ground_truth_tracks}.py
```

Cộng một property `SimulationEngine.steps` (read-only, additive).

## 2. Sáu quyết định đáng ghi

**(a) Seam là closure, không phải engine.** `ProviderRuntimeView.over_engine()`
nhận engine vào, trả ra năm bound method. Object đi tiếp **không có
đường nào** quay lại engine/scenario — test liệt kê `vars(view)` để
chứng, không chỉ tuyên bố.

**(b) Truth có hai cổng, không phải một.** Deployment quyết định lane
oracle có tồn tại (`grant_truth`); allowlist quyết định ai được dùng
(`TRUSTED_ORACLE_PROVIDERS`). Allowlist khoá trên **class object** nên
provider không thể đổi tên để lấy truth — có test impostor khai
`provenance="oracle"` và vẫn bị từ chối. Ghi rõ trong docstring: đây là
**trust policy, không phải hard isolation** (§5.7); hard isolation là
thứ H7 mua.

**(c) Ambiguity là lỗi, không phải chỗ để host thông minh.** Hai provider
cùng cấp một capability mà không có `selection` tường minh ⇒ graph không
runnable. Đây chính là ca `human_state_estimates`: từ tracker và từ
ground truth là **hai điều kiện benchmark khác nhau**, host chọn hộ là
đổi ý nghĩa kết quả mà không ai biết.

**(d) Cadence invariant viết đủ ba nhánh** (bản vá vòng 4). Ca chứng
minh vì sao không được rút thành equality: `StaticCostmapProvider` giữ
nguyên `produced_at` qua nhiều tick — test khoá điều đó. Nếu luật là
`produced_at == now`, provider trung thực **buộc phải** re-stamp, tức
được dạy nói dối về freshness. Clause "revision không đổi thì timestamp
không được đổi" là clause gánh cả luật, và có test riêng.

**(e) Lifecycle tách đôi giải quyết đúng mâu thuẫn vòng 3.**
`advance()` chuyển trạng thái, graph gọi **đúng một lần mỗi tick** (gọi
hai lần → `ProviderError`); `read()` pure, test gọi thẳng trên provider
**không qua cache** để chứng cache chỉ là tối ưu chi phí. Randomness
addressable `(seed, stream, tick, index)` — test chứng hai lần đọc cùng
địa chỉ bằng nhau, khác tick/khác stream thì khác.

**(f) `lidar_2d` dẫn xuất từ observation, không đo lại.** Hai lần đọc
cảm biến trong một tick sẽ **rút nhiễu hai lần** và trao cho hai
consumer hai thế giới khác nhau trong khi report nói họ thấy cùng một
thứ. Test đếm số lần `measured_observation` được gọi: đúng 1.

## 3. Fairness và evidence class (§5.10, nửa thuộc H3)

- `provenance_class()`: chỉ `oracle` mới hạ cấp. `deployment` và
  `candidate` đều production — khác nhau ở **ownership** (ai đổi
  identity, ai bị tính compute) chứ không ở evidence.
- `meet(entry, graph)` theo thứ tự production > reference > oracle: một
  entry production chạy kèm một channel oracle ⇒ execution là oracle,
  không ai phải nhớ khai.
- Hai lane: `FairnessPolicy.production()` **từ chối oracle ngay lúc
  admission** (rẻ hơn phát hiện sau 300 episode);
  `FairnessPolicy.research()` nhận và mang hậu quả trong evidence class
  — đây đúng là lane mà P4/P5 không có và phải chạy bằng script rời.
- `benchmarkable` cố ý vắng mặt: hai cổng `production_eligible` (entry)
  và `evidence_class` (execution) là bản vá vòng 4.

## 4. Phạm vi để lại có chủ đích

**Legacy facade không dùng seam này** — đúng nguyên văn DoD. Graph,
providers và view tồn tại và chạy được trên engine thật, nhưng
`run_stack` vẫn đi đường H2. Đó là lý do parity không bị đe doạ bởi H3:
đường cũ không đổi một nhánh nào. Việc nối bundle vào plugin thật là
H6 (proof plugin), preflight resolver là H4.

`GraphResolution` đã mang sẵn hình dạng compatibility report (order,
missing, ambiguous, cycles, sources) để H4 dùng, nhưng **không** tạo
`compatibility.py` — resolver là DoD H4, stub bây giờ là fake completion.

## 5. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/test_provider_graph.py` (mới, 40 test) | **40 passed** |
| Lát cắt H1a+H1b+H2+H3 | **100 passed** (trước khi thêm 4 test seam) |
| `ruff check` + `format` | sạch |
| **Parity chạy lại sau khi thêm `engine.steps`** | **20 passed, byte-identical**, 3:50 |
| Full backend suite | đang chạy nền trên code pre-H2 |

Về parity: H3 có sửa `engine.py` (thêm property `steps`), nên phép
chứng H2 **không còn tự động đúng** — chạy lại chứ không suy luận. Fixture
vẫn là bytes commit từ `7a7c195`, sinh trước khi host tồn tại.

## 6. Kế tiếp

H4 — compatibility resolver + fairness snapshot + accounting:
preflight trả `CompatibilityReport` trước episode, provider graph và
adapter chain vào execution fingerprint, phân biệt ownership
deployment/candidate/oracle trong accounting.

# H6 — hai plugin ngoài registry, chạy thật

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §8 H6
**Trạng thái:** xong, 14 test mới xanh, 227 passed lát cắt host, **chưa
commit**. Parity chạy lại vì H6 chạm `run_stack` — kết quả ở mục 6.

---

## 1. Đã tạo

| File | Việc |
|---|---|
| `examples/plugins/social_nav/` | **proof 1** — local plugin đòi `human_state_estimates` |
| `examples/plugins/corridor_planner/` | **proof 2** — global plugin BFS ngoài `ALGORITHMS` |
| `services/simulator/.../channel_source.py` | **mới**: protocol `ChannelSource` — seam duy nhất |
| `services/simulator/.../host/graph_source.py` | **mới**: `GraphChannelSource`, `GraphBackedLocalPlanner` |
| `.../nav_stack.py` | thêm `channel_source` (4 dòng: chữ ký, bind, advance, forward) |
| `packages/plugin_sdk/.../capabilities.py` | ba channel host-internal vào `BUILTIN_CHANNEL_URIS` |
| `tests/test_proof_plugins.py` | **mới**, 14 test |

## 2. Quyết định trung tâm: một seam, không phải một nhánh

DoD là một **phủ định** — thêm/bớt hai plugin này không được sửa
`run_stack()` hay `engine.get_observation()`. Nhưng một plugin
channel-native cần provider graph được advance mỗi tick, mà engine chỉ
loop mới có.

Chọn: **một seam plugin-agnostic** thay vì nhánh cho từng thuật toán —
đúng thứ alternative #2 của plan (§12) bị bác vì "coupling tăng vô hạn".
`run_stack` gọi hai method của một protocol và không bao giờ biết
provider là gì. `None` ⇒ hành vi cũ y nguyên.

**Guard `run_stack` đỏ và đó là việc của nó.** Tham số thứ sáu xuất
hiện ⇒ `test_run_stack_has_not_grown_a_condition` bắt phải quyết định.
Quyết: **plumbing, không phải condition** — băm một callable là băm
object identity, khác nhau mỗi lần chạy và không nói gì về thế giới;
các *điều kiện* nó chuyển (provider nào, lane nào, adapter nào) đã được
băm thành `HostConditions` ở chỗ chúng được resolve và là **sự kiện**
chứ không phải tham chiếu. Lý do ghi thẳng vào guard test.

## 3. Proof 1 — và vì sao nó không bao giờ là candidate

`social_nav` đòi `human_state_estimates` — **candidate đầu tiên trong
đời nền tảng này đòi hơn `lidar_2d`**. Đó chính là điều khoản G6 chưa
bao giờ phải định giá thật (hàng rào 13-08 cảnh báo, và tôi vừa nạp lại
nó ở commit trước).

Nguồn duy nhất của capability đó trong MVP là `GroundTruthTrackProvider`,
provenance `oracle`. Nên:

- production policy **từ chối ngay ở preflight** (`fairness_refusals ==
  ("oracle",)`);
- research policy nhận, `evidence_class == "oracle"`;
- provider oracle vào `host_conditions().providers` ⇒ run oracle và run
  production **được định địa chỉ khác nhau**, không chỉ dán nhãn khác;
- bỏ oracle provider đi thì nó thành `registered_but_missing_provider`
  — **không** âm thầm hạ cấp xuống chạy bằng thứ khác. Có test.

Nó chạy thật một episode `dynamic_warehouse` qua `run_stack`, tên
`astar+social_nav`.

## 4. Proof 2 — pairing mà registry không diễn đạt được

`corridor` là global planner BFS, không có trong `ALGORITHMS`. Nó chạy
episode ghép với controller built-in: `run.algorithm == "corridor+dwa"`
— **plugin ngoài + controller trong**, thứ registry dạng dict không khai
được.

Nó nói **thẳng contract của host**, nên không bọc `LegacyGlobalPlugin` —
bọc là dịch một request vốn đã đúng hình.

## 5. Bundle là ranh giới, có test

Cấp thiếu channel ⇒ plugin `LookupError` ⇒ host biến thành **safe stop**,
episode ghi lời từ chối thay vì làm chết run. Test khoá: cùng plugin,
cùng graph, chỉ khác grant list ⇒ event chứa `"was not granted"`.

## 6. Ba lỗi trong phiên, một cái là bug thật của H3

| # | Lỗi | Phán |
|---|---|---|
| 1 | `CircleObstacle` không có `.x` | **bug thật của H3** — `GroundTruthTrackProvider` đọc `obstacle.x`, schema thật là `center: Point2D`. Test H3 của tôi dùng stub tự chế có `.x` nên **xanh mà provider không đọc nổi một obstacle thật nào**. Sửa provider **và** sửa stub sang `CircleObstacle` thật |
| 2 | Guard `run_stack` bắt chữ `"corridor"` | **test sai** — trúng comment tiếng Anh nói về hành lang 2 m. Đổi sang so **định danh** (`CorridorPlanner`, `corridor_planner`, `org.planbench.example`) |
| 3 | Bọc `LegacyGlobalPlugin` quanh plugin host-native | sai thiết kế của chính tôi, sửa |

Lỗi (1) đáng ghi nhất: **stub dễ viết hơn kiểu nó thay thế là test tự
đồng ý với mình.** Đúng họ với bảy lần "phép đo xanh đo ít hơn nó khai"
của phiên P0–P6. Đã ghi thành comment ngay tại chỗ sửa để không tái lập.

## 7. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/test_proof_plugins.py` (mới, 14 test) | **14 passed** |
| Lát cắt host H1a→H6 + fairness + execution_conditions | **227 passed** |
| `ruff check` `examples/` + `packages/` + `services/` | sạch |
| **Parity sau khi thêm seam vào `run_stack`** | **20 passed, byte-identical**, 3:19 |
| Guard `run_policy` (H0) | đỏ đúng lúc — cửa thứ hai đòi cùng quyết định `channel_source`; ghi lý do tại chỗ thay vì kế thừa im lặng |
| Full backend suite | hoãn tới cuối plan (lệnh An) |

## 8. Kế tiếp

H7 — subprocess runtime proof: plugin ngoài process, timeout và crash cô
lập, sáu lớp latency §5.9 thành cột trace, runtime lane vào fingerprint,
và policy async cho stale channel mà H3 cố tình chưa làm.

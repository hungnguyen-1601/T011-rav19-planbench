# H5 — discovery không chạy gì, và runtime chạy muộn

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §8 H5
**Trạng thái:** xong, 21 test mới xanh, 151 passed lát cắt host, **chưa
commit**. Full suite hoãn tới cuối plan theo lệnh An.

---

## 1. Đã tạo / sửa

| File | Việc |
|---|---|
| `packages/plugin_sdk/.../protocol_version.py` | bump **1.0.0 → 1.1.0** |
| `packages/plugin_sdk/.../manifest.py` | `RuntimeProfile` thêm `entry_point`, `python_dependencies` |
| `services/simulator/.../host/discovery.py` | **mới**: `PluginRegistry`, `DiscoveredPlugin`, `QuarantinedPlugin` |
| `services/simulator/.../host/runtimes/trusted_python.py` | **mới**: `TrustedPythonRuntime` |
| `packages/benchmark/.../legacy_plugins.py` | `discover_all()` — nối built-in vào cùng đường |
| `tests/test_discovery_and_runtime.py` | **mới**, 21 test |

**Vì sao bump minor được, không cần bàn lại.** Hai field đều additive nên
mọi manifest 1.0 vẫn parse — đúng lý do compatibility xét trên *major*.
Điều khoản "đóng băng `protocol_version`" trong plan chỉ áp cho nhánh
**gate không đạt**; gate đã đạt nên contract tiến hoá là hợp lệ.

## 2. Điều khó nhất: chứng "discovery không chạy plugin code"

Đây là tính chất gánh cả §5.1, và cách chứng phải mạnh hơn một câu trong
docstring. Test dựng bundle mà **mọi module đều `raise` ngay khi
import**, rồi khẳng định:

- manifest vẫn đọc được, plugin vẫn vào roster;
- `sys.modules` **không** có tên bundle đó.

Ba cơ chế giữ tính chất này:

1. **Manifest đọc bằng `json.loads`**, không import.
2. **Entry point đọc như chuỗi.** `importlib.metadata` biết một
   distribution khai gì mà không import module nó trỏ tới; manifest được
   định vị qua `dist.locate_file()`. Cố tình **không** dùng
   `importlib.resources` — hàm đó import package.
3. **Dependency dò bằng `find_spec`**, định vị mà không thực thi — đúng
   mẹo `_build_ppo` đã dùng để giữ torch là optional.

## 3. Quarantine: một plugin hỏng không được làm chết chín cái kia

Manifest hỏng ⇒ `QuarantinedPlugin(source, reason)`, discovery đi tiếp.
Test: ba bundle, một cái JSON hỏng ⇒ hai cái kia vẫn vào roster, lý do
đi kèm entry hỏng.

Điểm đáng ghi: **gợi ý typo sống sót qua quarantine**. Bundle khai
`lidar2d` bị quarantine với reason chứa `lidar_2d` — cơ chế §5.2 luật 2
của H1a vẫn nói được với người đọc roster, không bị nuốt thành
"unusable".

Discovery cũng **idempotent qua nguồn chồng nhau**: quét thư mục rồi đọc
entry point trỏ vào chính nó ⇒ một entry, không quarantine. Nhưng hai
**body khác nhau** cùng `(id, version)` ⇒ quarantine, vì "code nào đã
chạy" phải trả lời được.

## 4. Registered ≠ runnable, và hai nửa của "không runnable"

`DiscoveredPlugin.runnable_runtime` chỉ trả lời nửa **runtime**: lane
sản xuất có đủ dependency không. Nửa còn lại — deployment có cấp
capability không — là việc của `resolve_compatibility` (H4).

Tách đôi có chủ đích: hai câu trả lời gửi người đọc tới hai chỗ sửa khác
nhau — `pip install` so với khai một provider.

Kèm một quyết định: **chỉ kiểm lane sản xuất**. Plugin cũng hỗ trợ lane
subprocess mà thiếu `grpcio` không bị đánh dấu unrunnable, vì nó sẽ
không được đo ở lane đó. Có test khoá.

## 5. Runtime nạp muộn — và tự cưỡng chế thứ tự

`TrustedPythonRuntime.load()` **đòi** một `CompatibilityReport` nói
runnable. Không phải quy ước cho caller nhớ: trạng thái "đã import rồi
mới biết nó không chạy được" là **không tới được**.

Bốn lời từ chối, mỗi cái một test: preflight chưa cho ⇒ không import;
lane khai khác lane này ⇒ từ chối (đo sai lane là §5.9 luật 4); thiếu
`entry_point` ⇒ nói rõ; import nổ ⇒ lỗi **mang tên plugin đó**, không
kéo chết roster.

**Conformance là cấu trúc, không phải hành vi:** kiểm object có đủ
method mà role của nó cần (`plan`, hoặc `reset`+`step`) và có `name`.
Nó *điều hướng* tốt hay không là thứ benchmark đo — loader mà thử đoán
trước sẽ thành chạy episode lúc import.

**Nói thẳng trong docstring:** trusted là từ về *policy*, không phải về
*security*. Code in-process với tới được mọi thứ process này với tới
được. Cái này mua được là "plugin sai thì hỏng ồn ào thay vì im lặng";
isolation thật là việc của H7.

## 6. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/test_discovery_and_runtime.py` (mới, 21 test) | **21 passed** |
| Lát cắt host H1a→H5 + dev_stack pythonpath | **151 passed** |
| `ruff check` toàn `packages/` + `services/` | sạch |
| Full backend suite | **hoãn tới cuối plan** (lệnh An) |

## 7. Kế tiếp

H6 — hai proof plugin: local plugin ngoài registry cần
`human-state-estimates@1` (kèm vế từ chối candidacy vì provenance
oracle), và global plugin ngoài central dictionary. DoD: add/remove hai
plugin này **không** phải sửa `run_stack()` hay `engine.get_observation()`.

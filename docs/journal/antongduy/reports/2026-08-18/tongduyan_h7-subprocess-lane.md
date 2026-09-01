# H7 — plugin ngoài process, và lateness lần đầu là thật

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §8 H7
**Trạng thái:** xong, 18 test mới xanh, 192 passed lát cắt host, **chưa
commit**. Parity chưa cần chạy lại — H7 không chạm `run_stack` (mục 6).

---

## 1. Đã tạo

| File | Việc |
|---|---|
| `host/runtimes/subprocess_worker.py` | phía con: một plugin, một pipe, JSON mỗi dòng |
| `host/runtimes/subprocess_lane.py` | `SubprocessRuntime`, `SubprocessPlugin`, `LatencyBreakdown` |
| `host/freshness.py` | `FreshnessPolicy` / `FreshnessFilter` — phần async H3 cố tình để lại |
| `examples/plugins/remote_wanderer/` | proof: controller **không import gì của nền tảng** |
| `host/compatibility.py` | `HostSupport.runtime_lanes` thêm `subprocess` |
| `tests/test_subprocess_lane.py` | **mới**, 18 test |

## 2. Lane này là chỗ deadline có thật

In-process host chỉ **quan sát** overrun — không cắt được một lời gọi
Python — và docstring nói thẳng thế. Ở đây plugin là một process:
deadline cưỡng chế bằng cách giết, crash là process exit chứ không phải
exception xuyên qua simulator. Có test đặt cạnh nhau đúng cặp đó.

**Worker chết thì chết luôn, không respawn.** Một worker mới giữa
episode sẽ trả lời tick kế tiếp bằng trạng thái nội bộ mới trong khi
trace nói đây là một episode liên tục — không người đọc nào thấy đường
nối. Có test.

## 3. stdout là giao thức, nên plugin không được ghi vào đó

Điều đầu tiên worker làm: lấy stdout thật cho giao thức, trỏ
`sys.stdout` sang stderr. Plugin **có** in — và một dòng `print` sẽ
thành dòng host cố parse như response. Sau khi đổi, print của plugin
thành chẩn đoán trên stderr, đọc được và vô hại.

Lỗi cũng đi bằng **dữ liệu** (`{"error": ...}`), không phải traceback
trên pipe đã đóng: worker chết không trả lời thì không phân biệt được
với worker treo, và host phải chờ hết timeout để biết điều worker đã
biết từ đầu.

## 4. Latency phân lớp, và ai đo lớp nào

| Lớp | Ai đo | Tư cách |
|---|---|---|
| `end_to_end_control_ms` | host | **authoritative** — gate đọc cái này |
| `transport_ms` | host | authoritative |
| `algorithm_compute_ms` | plugin tự báo | **diagnostic** (`compute_measured_by="plugin"`) |

Đúng §5.9 luật 6: host không có cách kiểm số plugin tự khai, và một gate
đọc con số do chính bên bị đo cung cấp thì không phải gate.

`transport_ms` **clamp ở 0**: plugin báo compute nhiều hơn cả round trip
là báo điều bất khả, và để transport âm sẽ rửa điều đó thành một con số
trông hợp lý.

## 5. Freshness — bốn quyết định, không cái nào là mặc định

H3 xây **invariant** (channel được phép nói gì về chính nó) rồi dừng, vì
tolerance mà không có gì async để tolerate là bề mặt validation không bao
giờ bắn. H7 làm lateness thành thật, nên policy tới cùng nó:

1. **Bao lâu là quá cũ** — `max_age_s` theo cadence. `static` không có
   trần: costmap dựng lúc đầu episode không "cũ" ở phút thứ ba, và luật
   nói ngược lại sẽ ép re-stamp.
2. **Reuse hay drop** — reuse trả lại **đúng envelope cũ, không sửa**,
   nên plugin tính tuổi ra tuổi thật. Drop trả `None` để plugin tự
   quyết — đúng cho plugin thà phanh còn hơn đoán, và đó là lý do `drop`
   không phải `reuse` có hạn.
3. **Out of order** — revision lùi thì **không bao giờ** giao. Cho plugin
   ăn một bước lùi trong đại lượng nó được bảo là đơn điệu còn tệ hơn
   không cho gì.
4. **Clock skew** — lệch nhỏ là khác đồng hồ, không phải tin từ tương
   lai; từ chối nó sẽ làm hệ đang chạy tốt trông như hỏng. Quá dung sai
   mới là fault. Dung sai **được khai** để "nhỏ" là con số ai đó chọn.

Kèm `stats` đếm delivered/reused/dropped/out_of_order: episode chạy một
phần ba số tick trên dữ liệu tái dùng là **phép đo khác** với episode
không tái dùng lần nào, và người đọc không có cách nào khác để biết.

## 6. Bốn lỗi trong phiên

| # | Lỗi | Phán |
|---|---|---|
| 1 | `HostSupport` vẫn khai chỉ có lane in-process | **đúng ở H4, sai từ khi H7 dựng lane**. Sửa lời khai, ghi rõ nó chuyển *khi lane được xây*, không phải khi plan nêu tên |
| 2 | `parents[4]` trỏ `services/`, thiếu một cấp | lỗi đếm; sửa thành `parents[5]` |
| 3 | `-m` kéo cả `host/__init__.py` vào worker | **lỗi layering của chính tôi**: đặt worker trong `host/runtimes/` khiến `-m` import cả host và kéo theo `planbench_benchmark`. Sửa: chạy **theo đường dẫn**, worker không import gì của host |
| 4 | Ba test cũ đỏ | **thế giới đổi, test nói đúng**: bundle thứ ba xuất hiện; và `subprocess` không còn là lane vắng mặt nên test H4 phải đổi sang `ros2_node` (plan xếp post-MVP) |

Lỗi (3) đáng ghi: **thông điệp lỗi vừa thêm ở chính commit này đã tự trả
ơn.** Bản đầu chỉ nói "did not start"; tôi thêm việc đọc stderr của
worker khi startup hỏng, và ngay lần chạy sau nó in ra
`No module named 'planbench_benchmark'` — chỉ thẳng vào lỗi layering.
Chẩn đoán không đọc được thì phải đoán; đọc được thì không.

## 7. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/test_subprocess_lane.py` (mới, 18 test) | **18 passed** |
| Lát cắt host H1a→H7 | **192 passed** |
| `ruff check` `examples/` + `packages/` + `services/` + test của tôi | sạch |
| Parity | **không chạy lại** — H7 không sửa `run_stack`, `engine.py` hay đường legacy; chỉ thêm module mới và một lời khai `HostSupport`. Sẽ phủ trong full suite cuối plan |
| Full backend suite | hoãn tới cuối plan (lệnh An) |

---

## 8. Vòng rà của An — 8 điểm, **đúng cả 8**, đã sửa hết

An rà bản H7 đầu và nêu 8 vấn đề. Không có điểm nào để phản biện. Ba
trong số đó (1, 4, 8) là chỗ tôi **đã tự nhận trong report** rồi vẫn để
nguyên — tức tôi coi "ghi nợ" là đủ khi nó không đủ. Ghi lại vì đó là
mẫu lỗi đáng nhớ hơn cả tám bản sửa.

| # | Vấn đề | Bản sửa |
|---|---|---|
| 1 | Sáu lớp latency chưa vào trace ⇒ deadline gate **không chạy hợp lệ được** (Metrics Engine chỉ đọc trace) | `LATENCY_LAYER_COLUMNS` + `compute_measured_by` thành cột thật. Schema **opt-in**: run không đo thì không ghi — sáu cột số 0 sẽ không phân biệt được "đo được 0 ms transport" với "lane này không có transport". `LocalPlanResult.latency_layers` mang chúng, `run_stack` chuyển thẳng vào recorder |
| 2 | `end_to_end_control_ms` đo thiếu phạm vi; `transport_ms` là hiệu số trộn IPC/queueing/chưa phân loại | `end_to_end_control_ms` = tổng sáu lớp (gồm provider, adapter, host overhead). `transport_ms` **đo trực tiếp**, kết thúc **sau decode**. Phần dư có tên riêng `host_overhead_ms` — một lớp hút hết phần còn lại là residual đội lốt phép đo |
| 3 | Deadline không lấy từ deployment; test nới 2.0 s | `control_period_s` thành **tham số bắt buộc**, không default. Mọi test dùng 0.05 s của deployment |
| 4 | `FreshnessFilter` chỉ có unit test, **không caller nào** | Nối vào `GraphChannelSource.bundle()`. Channel bị withhold thì **vắng mặt** chứ không rỗng ⇒ plugin `LookupError` ⇒ safe stop. Policy vào `host_conditions()` (reuse↔drop đổi quỹ đạo nên đổi fingerprint). `freshness_stats` phơi ra |
| 5 | stderr là PIPE nhưng không drain ⇒ plugin log nhiều là **deadlock**, host hiểu nhầm thành timeout | `_StreamDrain` thread, khởi động **trước handshake** — plugin log lúc load cũng không kẹt. Giữ tail để chẩn đoán |
| 6 | `_encode_reset` mất `robot`; thiếu `payload_encoding`; `__unencodable__` thay vì fail | `robot` được truyền; `payload_encoding` stamp `json-v1`; marker **bỏ hẳn** → `UnencodableRequest` raise |
| 7 | Crash isolation mới chứng một nửa | Thêm: exception trong step (và worker **sống tiếp**, trả lời tick sau), `kill()` giữa episode, action dị dạng, payload không encode được |
| 8 | "hard isolation / untrusted" là tuyên bố quá mạnh | Hạ trong docstring **và trong plan §5.7**, kèm bảng ba lane |

**Điểm 8, thêm ngoài yêu cầu:** sửa docstring thôi thì lời nói quá vẫn
nằm trong **plan đã approve**. Nên tôi sửa cả §5.7: subprocess cách ly
crash/hang/interpreter state, **không** cách ly quyền hệ thống,
environment, filesystem, network — worker kế thừa env, thấy `PYTHONPATH`
chứa repo, mang nguyên quyền user, nhận config qua command line hiện
trong process listing. Gọi đúng là **crash/process isolation**. Tên sai
sẽ được đọc thành "đã an toàn cho plugin lạ", kết luận không ai đo.

**Điểm 1, ghi rõ vì sao opt-in không phải né tránh:** một stack legacy
in-process không có transport và không có adapter chain. Ghi sáu cột 0
cho nó là đưa con số nobody measured vào file mà Metrics Engine coi là
nguồn duy nhất. Cột vắng mặt **là** lời khai trung thực. Và nó giữ luôn
parity: fixture H0 ghim danh sách cột, đường legacy vẫn dùng
`TRACE_SCHEMA` cũ nên không dịch — đã chứng lại bằng 20 test parity.

## 9. Kiểm chứng sau vòng sửa

| Kiểm | Kết quả |
|---|---|
| `tests/test_subprocess_lane.py` | **24 passed** (18 → 24) |
| lane + trace + **parity** | **72 passed**, 4:00 — parity vẫn **byte-identical** sau khi đổi trace schema và thêm field vào `LocalPlanResult` |
| Lát cắt host + replanning | **209 passed, 1 skipped** |
| `ruff check` | sạch |

## 10. Kế tiếp

H8 — docs, API, conformance suite: API/CLI hiển thị registration state và
compatibility report, conformance suite cho tác giả plugin, author guide
cho global/local/monolithic. Cộng quyết định về cột trace latency ở trên.

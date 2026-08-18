# H2 — AlgorithmHost bọc runtime cũ, parity byte-identical

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §8 H2
**Trạng thái:** xong, parity **byte-identical** với fixture H0, 13 unit
test mới xanh, **full suite đang chạy nền** (trên code pre-H2, xác nhận
các commit H1), **chưa commit**.

---

## 1. Kiến trúc đã dựng — `services/simulator/planbench_simulator/host/`

```text
run_stack / run_policy          (không đổi một dòng)
  └─ HostBackedGlobalPlanner / HostBackedLocalPlanner   [facades.py]
       └─ AlgorithmHost — guardrails                    [algorithm_host.py]
            └─ LegacyGlobalPlugin / LegacyLocalPlugin / LegacyPolicyPlugin
                 └─ planner/controller/policy cũ, nguyên vẹn
```

| File | Vai trò |
|---|---|
| `lifecycle.py` | Protocol `HostedGlobalPlugin`/`HostedLocalPlugin`; hai channel in-process (`planning-grid@1` on_change + revision, `legacy-observation@1` per_tick); codec `python-object/v1` = identity — điều kiện để parity byte-level khả thi |
| `algorithm_host.py` | `AlgorithmHost` + `HostStats`. Ba semantics H2 DoD: **crash step → safe stop** (lệnh 0 + failure_reason, loop ghi thành event như mọi refusal của controller); **crash plan → PlanResult(success=False)** (map vào verdict "no route" loop đã hiểu, G1 đếm, replanning thử lại); **crash reset → HostPluginError loud** (controller không khởi tạo được = misconfiguration, chạy tiếp là bịa số liệu). **Invalid output** (sai shape) → safe stop, đếm. **Deadline**: lane in-process *quan sát* và đếm miss, không preempt — không giả vờ có timeout chỉ bắn khi không cần; preemption là việc của subprocess lane H7 |
| `legacy_global.py` | Adapter global — không tính toán gì nên không thể phá parity |
| `legacy_local.py` | Adapter local — **kwargs probing bị cách ly vào đây** (§7.2): plugin mới nhận đủ declarations trong `LocalResetRequest.declared`; controller cũ nhận đúng subset chữ ký nó khai, giá trị (kể cả None) forward y hệt `_reset_local` |
| `legacy_policy.py` | Cùng cơ chế — policy và controller khác ở *bản chất*, không khác ở cách được mediate |
| `facades.py` | Hai ABC cũ ở mặt ngoài. Chữ ký `reset` của facade mang đủ ba kwargs — vì `_reset_local` probe *callee của nó*, giờ là facade; thiếu tên nào là declaration mất tích đúng kiểu vụ `sensor_noise` |

**Wiring: một chokepoint.** `build_planners` (candidates.py) trả về cặp
đã wrap — mọi contract episode đi qua host từ giờ. Import simulator để ở
build-time, không module-level: caller chỉ cần identity (API validate,
hash id) không phải kéo simulator vào.

## 2. Bằng chứng parity — DoD 1

`tests/test_host_parity_golden.py` (fixture sinh **trước khi host tồn
tại**, commit `7a7c195`) chạy lại qua `build_planners` đã wrap:

**20 passed — byte-identical.** Trajectory, events, plans, status,
candidate_id, fingerprint, trace metadata/columns/rows — không lệch một
byte, cả `astar+dwa` lẫn `rrtstar+dwa` (đường seed-per-episode), hai
seed mỗi stack.

## 3. Unit tests — `tests/test_algorithm_host.py`, 13 passed

| Nhóm | Ghim |
|---|---|
| Guardrails | crash → safe stop + đếm; sai shape → safe stop + đếm; reset crash → loud; global crash → failed plan; deadline 0 → miss được đếm, kết quả vẫn trả nguyên |
| Probe quarantine | controller không khai kwargs nhận đúng zero; khai hai nhận đúng hai với giá trị deployment; facade signature đủ ba tên |
| Contract surface | name/control_period/diagnostics pass-through; `_reset_local` thật driving facade → declarations tới đích |
| Shared loop | host-backed stack sống qua `run_stack` (tên "astar+dwa"); host-backed policy qua `run_policy` giữ tên một-lớp, plan rỗng 0s |

## 4. Phạm vi để lại có chủ đích

- `compatibility.py` (trong cây file H2 của plan) **không tạo** — preflight
  resolver là DoD của H4, tạo stub bây giờ là fake completion.
- PPO qua host: facade wrap generic mọi `LocalPlanner`, lazy path đã ghim
  ở H1b; golden runtime PPO vẫn nợ máy có RL extras (từ H0).
- `build_policy` trả policy thô (giữ isinstance test H1b);
  `host_backed_policy()` là cửa wrap — dùng ở run path khi monolithic có
  đường sản xuất thật.

## 5. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| Parity 4 episode vs fixture H0 | **20 passed, byte-identical**, 2:54 |
| `tests/test_algorithm_host.py` | **13 passed** |
| `ruff check` + `format` host + tests + candidates | sạch |
| Full backend suite | **đang chạy nền trên code pre-H2** — xác nhận ba commit H1/gate; H2 cần một lượt suite riêng sau khi commit |

## 6. Kế tiếp

1. Full suite pre-H2 xong → An commit H2 → chạy suite trên H2 (lệnh An).
2. H3 — provider graph: nửa thuần logic (DAG resolver, channel bundle,
   fairness skeleton) không phụ thuộc gì nữa; nửa chạm engine
   (`ProviderRuntimeView`, providers) giờ đã đủ điều kiện vì parity H2
   chốt xong.

# Tổng kết H0–H8 — và đối chiếu §11 DoD MVP, gồm **năm khoản chưa đạt**

**Ngày:** 2026-08-17 → 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md`
**Full suite trên HEAD:** **3065 passed, 8 skipped, 0 failed**, 30:03.
**Commit:** 13, tất cả tiền tố `TongDuyAn - `.

---

## 1. Đọc trước: plan chạy hết 9 pha, DoD MVP **chưa** đạt hết

Mọi pha H0–H8 đều xong và commit. Nhưng §11 liệt 17 khoản DoD, và **năm
khoản chưa đạt hoặc mới đạt một phần**. Lý do đáng ghi hơn danh sách:

> DoD được viết theo **kết quả**, còn công việc được chia theo **file**.
> Khoản nào nằm gọn trong danh sách file của một pha thì xong; khoản nào
> **vắt qua nhiều pha** thì mỗi pha làm phần rơi vào mình và không ai
> ráp lại. Không pha nào "thiếu DoD của nó" — DoD của MVP mới là thứ hở.

Tôi phát hiện ra điều này lúc đối chiếu cuối, không phải lúc làm. Nếu
đối chiếu §11 sau **mỗi** pha thay vì một lần cuối thì đã thấy sớm hơn.

## 2. Đối chiếu §11, đủ 17 khoản

| # | DoD | Trạng thái |
|---|---|---|
| 1 | A*, RRT*, DWA, PPO qua host không drift theo comparator H0 | ✅ (PPO ở mức identity — máy này không có torch, đã ghi từ H0) |
| 2 | Local plugin ngoài registry cần richer observation chạy qua provider graph | ✅ `social_nav` |
| 3 | Global plugin ngoài registry nối sang host | ✅ `corridor` |
| 4 | Plugin thiếu runtime/provider vẫn đăng ký được, báo đúng lý do | ✅ |
| 5 | `run_stack()` không special-case proof plugin | ✅ một seam plugin-agnostic, có test đọc source |
| 6 | Provider provenance vào fingerprint và report | ✅ |
| 7 | Oracle provider luôn `sim_only`, không production-recommendable | ✅ ở tầng preflight |
| 8 | Plugin crash/timeout không kéo chết host | ✅ cả hai lane |
| 9 | Tác giả ngoài repo đọc guide và thêm plugin không sửa core loop | ✅ |
| 10 | Deployment khai custom capability/provider bằng **additive grant** không phá stored v1 profile | ❌ **chưa làm** |
| 11 | Candidate-owned provider đổi candidate ID; deployment-owned đổi fingerprint; test khoá **cả hai chiều** | ⚠️ **một nửa** |
| 12 | Plugin thiếu action/dynamics/runtime vẫn đăng ký, report nêu đúng | ✅ |
| 13 | Sáu lớp latency thành cột trace · deadline gate `screened_on_host` có luật chống nhiễu · runtime lane vào fingerprint | ⚠️ **hai phần ba** |
| 14 | `TraceMetadata.evidence_class` bắt buộc · guard fail-closed ở một trace load boundary · trace address mang `evidence_class/execution_fingerprint` · `withdrawn` riêng · `benchmarkable` derived | ❌ **chưa làm** |
| 15 | Hai cách khai capability cho cùng `candidate_id` | ✅ |
| 16 | Manifest khai đủ runtime lane + custom capability surface; `resolved_runtime_profile` vào fingerprint; không fallback lane | ✅ |
| 17 | `algorithm_compute_ms` external là plugin-reported diagnostic; verdict latency theo `latency-screening-v1.yaml` | ⚠️ **một nửa** |

## 3. Năm khoản hở, nói rõ hở chỗ nào

### (10) `TaskProfile.capability_grants` — chưa làm

§5.2 thiết kế `CapabilityGrant(capability, provider_id, provider_config)`
và `TaskProfile.capability_grants = ()` để deployment khai capability
mới **additive**, không phá profile v1 đã lưu. Manifest phía plugin có
`capability_schemas` (H8 review), nhưng **phía deployment thì không**:
hôm nay capability chỉ đến từ built-in graph hoặc từ tham số
`available_capabilities` truyền tay vào `resolve_compatibility`. Không
có đường khai trong profile.

**Hệ quả:** một deployment thật chưa khai được provider riêng của nó.

### (11) Chiều "candidate-owned đổi candidate ID" — chưa nối

Đã có: `ProviderOwnership` tách ba ngả, và test khoá candidate-owned
**không** lọt vào fingerprint. Chưa có: candidate-owned provider **đi
vào `candidate_id`**. `candidate_from_stack` không biết provider nào cả.

**Hệ quả:** hai candidate khác nhau ở provider riêng sẽ chung một id.
Test hiện khoá một chiều, và tôi đã viết là "khoá cả hai chiều" trong
report H4 — **sai**, đây là chỗ thứ hai tôi tuyên bố quá.

### (13) Deadline gate chưa tồn tại như một gate

Có: sáu cột trace (H7 review), `runtime lane` trong fingerprint,
`configs/latency-screening-v1.yaml` commit từ trước H0.

Không có: **gate nào đọc file đó**. Không có `p99(end_to_end_control_ms)
< control_period` chạy ở tầng quyết định, không có verdict
pass/fail/inconclusive, không có sentinel drift check. Protocol là thước
đã khai; chưa ai cầm thước.

### (14) `evidence_class` chưa xuống tới trace — khoản hở nặng nhất

Có: `FairnessPolicy`, `meet()`, `evidence_class` trong
`CompatibilityReport`, production policy từ chối oracle ở preflight.

Không có, dù §5.10 chốt qua ba vòng phản biện:

- `TraceMetadata.evidence_class` — **không có trường này**;
- guard fail-closed ở trace load boundary — `--score-only` và
  `--reuse-traces` **không** biết gì về oracle;
- trace address `evidence_class/execution_fingerprint/...` — đường dẫn
  vẫn là `candidate_id/episode_context_id`, tức **oracle trace vẫn đè
  được production trace**;
- `production_eligible` derived — `benchmarkable` vẫn là field lưu trữ.

**Hệ quả, nói thẳng:** §5.10 chốt rằng chặn ở một mình Card assembly là
lặp lỗ stale-trace 16-08. Hôm nay chặn còn **ở trên cả Card** — chỉ ở
preflight. Chạy oracle qua `run_contract_episode` sẽ ghi một trace không
mang dấu hiệu nào, vào đúng địa chỉ mà production trace dùng.

Lane oracle **chưa an toàn để dùng thật.** Nó chỉ an toàn vì chưa ai
chạy nó qua đường sản xuất.

### (17) Verdict latency — nửa còn lại của (13)

`compute_measured_by` có trong trace và trong ledger. Verdict sinh theo
`latency-screening-v1.yaml` thì chưa, vì gate chưa tồn tại.

## 4. Vì sao hở, và điều tôi rút ra

Ba pha review của An bắt 8 + 9 = 17 vấn đề, và **tôi sửa hết trong pha
đang mở**. Nhưng năm khoản trên không thuộc pha nào: chúng là DoD của
**MVP**, được chốt trong §5.2/§5.9/§5.10 qua bốn vòng phản biện, rồi
được chia nhỏ vào H4 (một phần), H7 (một phần) — và phần còn lại không
có nhà.

Cụ thể hơn: §5.10 nói *"guard fail-closed ở mọi consumer trace"*. H4 có
danh sách file là `compatibility.py` + fingerprint, không có `trace.py`
hay `pipeline.py`. Nên tôi làm đúng danh sách file của H4 và khoản DoD
đó rơi ra ngoài.

**Bài học đúng hình dạng bài học 16-08:** một danh sách bảo trì cạnh thứ
nó mô tả sẽ trôi khỏi nó. Ở đây danh sách là "file chạm tới của mỗi pha",
thứ nó mô tả là "DoD MVP". Cách chặn: đối chiếu §11 sau **mỗi** pha, và
mỗi khoản DoD phải chỉ đích danh pha sở hữu nó.

## 5. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| **Full backend suite trên HEAD** | **3065 passed, 8 skipped, 0 failed**, 30:03 |
| Parity (fixture sinh trước khi host tồn tại) | byte-identical qua cả 9 pha, chạy lại 5 lần |
| `ruff check` `packages/` + `services/` + `examples/` | sạch |
| Test mới trong plan này | ~200 (H0 16 · H1a 28 · H1b 21 · H2 13 · H3 40 · H4 22 · H5 21 · H6 14 · H7 24 · H8 31) |

## 6. Đề xuất — An quyết

Ba lựa chọn, tôi nghiêng về (b):

**(a)** Coi MVP xong ở đây, ghi 5 khoản vào `KNOWN_LIMITATIONS` và
backlog. Rẻ nhất, nhưng lane oracle sẽ mang tiếng "chạy được" trong khi
nó chưa an toàn để dùng thật.

**(b) Làm nốt khoản (14) trước, rồi mới coi MVP xong.** Đây là khoản duy
nhất có thể **làm hỏng dữ liệu** — oracle trace đè production trace,
không sửa được sau. Bốn khoản kia là thiếu tính năng; khoản này là một
lỗ đúng hình dạng lỗ 16-08 mà nền tảng đã trả giá một lần.

**(c)** Làm hết cả 5. Đúng plan nhất, nhưng (10) và (13) là tính năng
mới chứ không phải nợ an toàn, và ngân sách host 3 tuần đã tiêu ~1.5
ngày cho H0–H8.

Khoản (11) rẻ và nên làm kèm bất kỳ lựa chọn nào: nó cũng là chỗ tôi đã
tuyên bố sai trong report H4, nên ít nhất phải sửa lời khai.

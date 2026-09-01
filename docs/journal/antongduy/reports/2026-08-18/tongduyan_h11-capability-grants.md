# H11 — deployment cuối cùng cũng khai được capability của mình

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §13, khoản cuối
**Trạng thái:** backend xong, 13 test mới xanh. **UI chưa làm** (mục 5). Chưa commit.

---

## 1. Một tính năng mới có một nửa

Từ H1a, phía plugin khai được capability riêng qua `capability_schemas`.
Phía deployment thì chỉ nói được `lidar_2d` hoặc `human_state_estimates`
— hai token của vocabulary v1. Nên một deployment thật sự chạy tracker
của mình **không có cách nào trả lời** một plugin đòi nó.

`available_observations` phải giữ **đóng**: G6 so token theo chữ, nên một
typo ở đó đọc ra thành "không tương thích phần cứng" trong khi phần cứng
không sao. Vì thế `capability_grants` là bề mặt **thứ hai**, additive,
chứ không phải nới lỏng cái thứ nhất.

## 2. Điều kiện tiên quyết: profile cũ không được dịch

Mọi profile đã lưu đều có trước field này, và run được định địa chỉ bằng
conditions hash dẫn xuất từ profile. Một field làm dịch hash đó cho
profile **không dùng nó** sẽ mồ côi đúng những run nó mô tả.

Nên payload fingerprint **bỏ hẳn key** khi grants rỗng, không phải hash
`[]`. Chứng bằng ba lớp:

- fingerprint tính hôm nay khớp giá trị trong fixture H0 (bytes commit
  `7a7c195`);
- `capability_grants=()` tường minh bằng đúng "không nhắc tới" — nếu
  payload có ngày nào mọc `[]` thì test trên vẫn xanh nhờ may, test này
  thì không;
- profile cũ load → dump → load lại **không drift**.

## 3. Grants là execution condition (§7.1)

Cấp một provider ⇒ fingerprint đổi. **Chỉnh config của nó ⇒ đổi tiếp** —
tracker được tinh chỉnh giữa hai sweep là điều kiện thí nghiệm khác, bất
kể candidate làm gì. Thứ tự khai ⇒ **không** đổi.

Grants đi qua **alias bridge của SDK**, cùng cửa `CandidateProviderBinding`
dùng: deployment viết URI và plugin viết token phải gặp được nhau, và
chúng chỉ gặp nếu cả hai quy về một dạng trước khi có gì so sánh.

`granted_capabilities()` hợp nhất v1 + v2 thành **một** câu trả lời cho
"deployment này cấp gì", sorted và dedup.

## 4. Nhập nhằng bị từ chối **lúc viết profile**, không phải lúc resolve

Hai provider cho một capability mà không nói chọn cái nào ⇒ từ chối. Host
không chọn hộ: tracker và ground truth cùng sinh `human_state_estimates`
và chúng là **hai thí nghiệm khác nhau** (§5.4).

Kiểm trong validator của profile chứ không trong resolver, vì
**deployment sai trước khi episode nào chạy** — phát hiện lúc sweep đã đi
được ba tiếng thì mất cả sweep.

Hai ca cạnh nhau, cố ý khác nhau:

- **cùng provider khai hai lần** ⇒ **không** phải nhập nhằng. Lặp là
  luộm thuộm, không phải mâu thuẫn; từ chối nó sẽ biến một dòng thừa
  thành một sự cố.
- **một capability nằm ở cả `available_observations` lẫn grants** ⇒ từ
  chối. Cái trước nói "deployment đơn giản là có"; cái sau nêu tên một
  provider cho nó. Resolver đọc cả hai sẽ phải đoán deployment định nói
  gì.

## 5. Chưa làm — nói rõ

**Form UI chưa có.** Plan ước lượng backend 1.5–2.5 ngày, "+1 ngày nếu
có UI", và đây là backend. Một deployment hôm nay khai grants bằng cách
sửa YAML; qua form thì chưa.

**Provider config chưa được validate bằng schema của provider.** §13 yêu
cầu điều đó *trước episode*. Hiện `provider_config` là `dict[str, Any]`
đi vào fingerprint nguyên vẹn — tức một config sai chính tả vẫn tạo ra
một fingerprint hợp lệ và khác. Cần registry schema của provider ngoài,
là thứ H5 mới có ở phía plugin bundle. Ghi ra thay vì để nó trông như đã
xong.

## 6. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/test_capability_grants.py` (mới, 13 test) | **13 passed** |
| `test_task_profile` + `test_execution_conditions` + `test_compatibility_and_accounting` | **109 passed** |
| `ruff check` | sạch |
| Full suite | chạy sau khi commit |

## 7. Hai lỗi trong phiên

| # | Lỗi | Phán |
|---|---|---|
| 1 | Test bắt `AmbiguousGrantError` | pydantic **bọc** ValueError trong validator thành `ValidationError` — đúng quy ước repo (`LidarConfig` cũng thế). Sửa test, và ghi vào docstring rằng class tồn tại để lý do **greppable** chứ không phải để bắt riêng |
| 2 | `model_copy(update=...)` không validate nên grant còn là dict | lỗi của test, không phải của model. Dựng `CapabilityGrant` thật |

## 8. Trạng thái §11 sau H9A→H12 + H11

Còn hai khoản, cả hai chặn bởi thứ **không có trên máy này**:

- **1** — PPO parity: cần RL extras + checkpoint.
- **13/17** — deadline runner: cần candidate thật chạy lane subprocess.

Khoản **10 giờ đạt ở mức backend**; validate config bằng provider schema
và form UI là hai việc còn lại của nó, ghi ở mục 5.

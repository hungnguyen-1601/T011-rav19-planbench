# H12 — cờ mang hai nghĩa nay không mang nghĩa nào, và PPO giữ nguyên "partial"

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §13
**Trạng thái:** phần eligibility xong; **PPO parity giữ nguyên chưa đạt, có chủ đích**. Chưa commit.

---

## 1. Một cờ, hai nghĩa, và cách nó tích tụ

`benchmarkable=False` từ D12 nói đúng một điều: *reference adapter,
không bao giờ là contender*. Ngày 16-08 `dwa_predictive` bị rút trên
bằng chứng đo được, và cùng một cờ bắt đầu nói thêm điều thứ hai. Report
hôm đó nhận ra và **vá bằng cách thêm `withdrawn`** — nhưng cờ cũ vẫn
mang cả hai, nên một lời từ chối đọc nó không nói được nó nói cái nào.

H12 làm nốt: mỗi sự thật tự nói, và cờ cũ **dẫn xuất** từ chúng.

```text
reference: bool            ← D12 adapter
withdrawn: str             ← rút sau khi đo
production_eligible        = not reference and not withdrawn
benchmarkable              = alias deprecated của production_eligible
```

Tính chất mà boolean cũ không diễn đạt được, giờ có test: **với mọi entry
không eligible, đúng một trong hai lý do áp dụng.** Nếu ngày nào đó một
entry vừa reference vừa withdrawn — hoặc không cái nào mà vẫn bị loại —
test đỏ, vì lúc đó lời từ chối lại mất khả năng nêu tên.

## 2. Alias giữ trên wire, và giữ ở dạng dẫn xuất

`/algorithms` serialise `benchmarkable`, và web candidate picker lọc
theo nó. Đổi tên trường trên wire sẽ phá một UI đang chạy để một
attribute Python đọc cho xuôi. Nên nó ở lại — **computed**, không lưu —
nên hai bên không thể lệch nhau.

**Truyền `benchmarkable=` giờ bị từ chối, không phải bỏ qua.**
`AlgorithmInfo` không `extra="forbid"`, nên một entry còn truyền cờ cũ sẽ
được nhận và **không có tác dụng gì** — một stack lẽ ra bị giữ lại sẽ âm
thầm thành contender. Đó là chiều duy nhất trường này không được phép
hỏng im lặng, nên có validator chặn kèm câu chỉ đường sang
`reference` / `withdrawn`.

## 3. PPO parity — **vẫn chưa đạt**, và tôi để nguyên như thế

DoD #1 khai bốn stack chạy qua host không drift. PPO mới được kiểm ở
**mức identity** vì máy này không có RL extras (`stable_baselines3`,
`torch`, `gymnasium` đều vắng — kiểm lại hôm nay). Identity-level
**không** chứng minh wrap của host để nguyên một episode PPO.

Không dựng baseline từ HEAD được: H2 đã nằm trong đó, nên phép so sẽ là
host so với chính nó. Quy trình phục hồi bằng chứng nằm trong docstring
của test, và commit gốc là **`239132e`** — ngay trước H2.

Test làm hai việc, không hơn:

- kiểm **tiền đề rẻ**: commit tiền-host còn với tới được trong repo;
- `skipif` mang **nguyên văn lý do**: *"PPO runtime parity is unproven on
  a machine without the RL extras. DoD #1 stays partial."*

Nói thẳng vì một dependency vắng mặt rất dễ đọc thành "đã pass". Một
test skip không kèm lý do đúng nghĩa là một khoản DoD hở được đánh dấu
xanh.

## 4. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/test_eligibility_and_ppo_parity.py` (mới, 10 test) | **9 passed, 1 skipped** — skip là PPO, có lý do |
| Consumer registry: bridge, engine, identity, legacy_plugins, discovery, compatibility, gates, latency, `tests/api` | **847 passed, 3 skipped**, 15:23 |
| `ruff check` | sạch |

## 5. Trạng thái §11 sau H9A→H12

| Khoản | Trước | Sau |
|---|---|---|
| 7 — oracle `sim_only`, không recommendable | ⚠️ chỉ preflight | ✅ **H9A** |
| 11 — hai chiều ownership | ⚠️ một chiều | ✅ **H9B** |
| 13 — sáu lớp + deadline gate | ⚠️ gate chưa có | ⚠️ **gate có, runner chưa** (mục 6 report H10) |
| 14 — evidence class trong metadata/address, fail-closed, benchmarkable derived | ❌ | ✅ **H9A + H12** |
| 17 — verdict theo protocol | ⚠️ | ⚠️ **cùng lý do khoản 13** |
| 1 — PPO qua host không drift | ⚠️ | ⚠️ **giữ nguyên, có chủ đích** |
| 10 — capability grants | ❌ | ❌ **H11, chưa làm** |

Còn ba khoản: **1** (cần RL extras + checkpoint), **13/17** (cần runner
phiên đo, cần candidate chạy lane subprocess), **10** (H11).

Không khoản nào còn thuộc loại **tạo dữ liệu sai** — đó là ranh giới
H9A + H9B đã đóng.

## 6. Kế tiếp

H11 nếu An chốt ưu tiên; nếu không thì `robustness_margin` theo prereg
gate, nơi F1 được khai là trên critical path.

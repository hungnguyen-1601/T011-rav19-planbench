# Rà soát lịch sử commit: có cần revert điểm nào không?

> **Ngày:** 2026-08-11 · **Loại:** đánh giá, **không đổi code, không đụng git**
> **Yêu cầu nguồn:** An — *"duyệt lại các commit cũ, xem có cần revert lại một điểm nào đó để
> sửa cho nhanh không, hay sửa luôn ở điểm hiện tại."*
> **Kết luận ngắn:** **Không revert.** Sửa tại điểm hiện tại. Nhưng lượt rà tìm được **bốn thứ
> phải xử lý** mà không cái nào là revert, và **một cái bẫy chưa ai thấy** sẽ cắn vào M1/M2 của
> plan MVP.

---

## 1. Tiêu chí quyết định

Revert đáng làm khi **cả ba** cùng đúng:

1. Một commit đưa vào thứ sai, **và**
2. thứ sai đó **vẫn đang gánh việc** (không phải đã bị thay), **và**
3. dựng lại từ điểm trước đó **rẻ hơn** sửa tiếp từ hiện tại.

Thiếu bất kỳ điều nào thì revert chỉ là mất công việc đúng đi kèm.

## 2. Duyệt từng nhóm commit

| Nhóm | Nội dung | Có defect còn sống? | Phán quyết |
|---|---|---|---|
| `f256b73`…`21e093c` Phase 1.x | TaskProfile, candidate_id, EpisodeContext, contract | Không | **Giữ** — đây là nền, revert = mất tất cả |
| `fa9df8a`…`02bb5e3` Phase 2.x | trace Parquet, map loader, `definitions.py` | `L_ref` sai 2,41% — **đã sửa sáng nay** | **Giữ** |
| `68d1f23`…`057733f` Phase 3.x | anchors, gates, objectives, bootstrap, card | Không | **Giữ** |
| `f3d4b85` Phase 5.2+5.3 | Pareto, sensitivity | Không. Chúng là hàm thuần trên utility — 6.1.0 chỉ đổi **giá trị** đầu vào, không đổi ngữ nghĩa | **Giữ** |
| `b60dbd9` Phase 6.1 | migration + bảng DB | Không. Additive, MVP chưa dùng tới | **Giữ** |

**Bốn thay đổi do kết quả dẫn dắt** (DWA horizon 1,5 · đổi mission · traffic 0,24 m/s ·
`pallet_truck`) — đã được hoàn nguyên **bằng cách sửa tiến**, không bằng `git revert`, và đó là
lựa chọn đúng: chúng nằm chung file với những sửa chữa **đúng** của cùng lượt (xen kẽ
context-outer, `n_distinct`, `seed_time_offset`). Một `git revert` ở mức commit sẽ kéo theo cả
phần đúng.

**Không có nhóm nào thoả cả ba tiêu chí ở mục 1.** Điều kiện (2) hỏng ở mọi ứng viên: mọi defect
tìm được đều **đã bị thay bằng bản đúng**, nên không còn gì để revert ngoài công việc tốt.

## 3. Bốn thứ thật sự phải xử lý — không cái nào là revert

### 3.1. `measurement_report.json` **đang bị gitignore** *(chặn thật)*

```
$ git check-ignore -v artifacts/runs/2026-08-11/.../measurement_report.json
.gitignore:94:artifacts/runs/*/*/*
```

`.gitignore` mở khe cho đúng hai file: `decision_card.json` và `manifest.json` — viết từ thời
artifact duy nhất là card. Measurement Report ra đời sáng nay và **không commit được**.

Đây không phải chuyện tiện tay. Lý lẽ của cái khe đó, viết ngay trong `.gitignore`, là *"một hồ
sơ nghiệm thu không ai mở được thì không phải hồ sơ nghiệm thu"*. Measurement Report **là** hồ sơ
nghiệm thu của F1, đúng nghĩa đó.

**Sửa:** thêm `!artifacts/runs/*/*/measurement_report.json`. Một dòng.

### 3.2. Hai Decision Card đã commit hiện đang nói dối

`artifacts/runs/2026-08-10/057733f06738/` và `.../f3d4b85edb17/`, cả hai đều in:

```
"0 va chạm quan sát trong 30 lần chạy; cận trên 95% ...: 10.0%"
n_distinct_episodes: null        G4 threshold_ms: 100.0
```

Ba thứ sai theo hợp đồng hôm nay, và cả ba đều là **đúng những lỗi đã được đặt tên**:

- Cận trên tính trên **số dòng** chứ không trên số episode phân biệt (thứ 6.0.0 sửa). Phase 5.1
  đo được A\* trên kho có `n_distinct = 1/100`; ở 30 episode gần như chắc chắn cũng là 1. Nên
  con số "10%" đứng trên **một** mẫu.
- Ngưỡng G4 là 100 ms — ngưỡng đã nới, thứ 6.1.0 trả về 50 ms.
- Candidate chạy DWA ở 10 Hz trên deployment khai 10 Hz, tức dưới lỗ hổng `validate_control_rate`
  vừa đóng.

Chúng nằm trong repo, được `.gitignore` **cố ý** whitelist, và với người mở lần đầu thì trông
như hai kết quả hợp lệ.

**Không revert được, và đó là điểm chính:** không thể un-run một lần chạy. Xoá thì mất bằng
chứng lịch sử — mà chính hai tấm card này là vật chứng của bài học lớn nhất dự án học được.

**Sửa:** thêm `SUPERSEDED.md` vào mỗi thư mục run, ghi ba dòng: card này tính dưới contract nào,
điều gì trong nó không còn đúng, và đọc báo cáo nào để hiểu vì sao. Giữ file, gỡ khả năng đọc
nhầm.

### 3.3. Trace mồ côi 9,5 MB — **giữ, đừng xoá**

`artifacts/traces/` có ba thư mục: `2baaad3628e1`, `ac187ee7a77e` (hai candidate kho, id cũ,
`candidate_id` đã đổi vì DWA nay chạy 20 Hz) và `db26440f6052` (run open_hall sáng nay, còn dùng
được).

Hai bộ đầu trông như rác. **Không phải** — chúng là bộ trace của lần chạy 100 episode đã sinh ra
"tấm card nói dối", và báo cáo Phase 5.1 đã ghi rõ giữ chúng làm bằng chứng cho chính phát hiện
đó. 9,5 MB, gitignored, không tốn gì. **Giữ.**

### 3.4. `.ai-log/session.jsonl` lẫn vào mọi commit

Mỗi commit gần đây kéo theo vài trăm dòng thay đổi của `.ai-log/`. Nó làm `git log --stat` khó
đọc và làm mọi diff phình lên. Không sai, chỉ ồn.

**Không tự quyết** — file này có vẻ là quy ước chung của nhóm, không phải của riêng nhánh này.
Ghi lại để dev quyết.

---

## 4. Cái bẫy chưa ai thấy — sẽ cắn vào M1/M2 của plan MVP

Tìm được khi kiểm xem `--reuse-traces` có phục vụ dữ liệu cũ không. Đáng nêu riêng vì nó **chưa
xảy ra**, và sẽ xảy ra ở đúng bước sắp làm.

`episode_context_id` băm đúng bốn thứ (HĐ-3.1, và HĐ-3.1 **đóng băng** payload này):

```
(task_profile_id, mission_id, environment_variant, seed)
```

**`sensor_noise` sẽ không nằm trong đó.** Nên nếu ai bật nhiễu **tại chỗ** trong một profile mà
giữ nguyên `id`, thì:

```
profile đổi (σ: 0 → 0,02)  ⇒  context_id KHÔNG đổi
                            ⇒  --reuse-traces phục vụ episode ghi dưới σ = 0
                            ⇒  không cảnh báo nào, vì id khớp
```

Đây đúng là cái bẫy mà đầu file `warehouse_a_v2.yaml` đã ghi cho traffic — nhưng ghi cho traffic
thì chỉ bảo vệ traffic.

**Điều này xác nhận quyết định `open_hall_v2` của plan là đúng, và vì một lý do mạnh hơn lý do
đã viết ra.** Plan chọn v2 để giữ v1 làm dụng cụ kiểm đối xứng. Hoá ra v2 **còn là** thứ duy
nhất khiến trace cũ không bị dùng nhầm: đổi `id` ⇒ đổi `task_profile_id` ⇒ đổi mọi
`context_id` ⇒ trace cũ không bao giờ được tra tới.

**Đề xuất cho M1, chưa quyết:** thêm một chốt chặn để lần sau không phải dựa vào việc người viết
profile nhớ đổi id — ví dụ manifest ghi biên độ nhiễu (đã có trong plan M1.6) **cộng** một phép
kiểm lúc `--reuse-traces` rằng biên độ nhiễu của trace khớp với profile đang chạy. Đưa
`sensor_noise` vào payload băm là lời giải sạch hơn nhưng là **MAJOR** (HĐ-3.1 đóng băng payload),
nên không tự chọn.

---

## 5. Vậy làm gì

**Không revert.** Sửa tại điểm hiện tại, theo thứ tự:

| # | Việc | Chi phí | Vì sao trước/sau |
|---|---|---|---|
| 1 | `.gitignore` mở khe cho `measurement_report.json` | 1 dòng | Chặn M0.1 — không có nó thì kết quả F1 không commit được |
| 2 | Commit lượt F0/F1/F2 (M0.1 của plan) | 30 ph | Khối công việc lớn nhất đang không có bản sao |
| 3 | `SUPERSEDED.md` cho hai run 08-10 | 15 ph | Rẻ, và mỗi ngày trôi qua là một ngày ai đó có thể đọc nhầm |
| 4 | Chốt chặn nhiễu ↔ trace (mục 4) | quyết ở M1 | Chưa cắn, nhưng sẽ cắn đúng bước sắp làm |

Ba việc đầu gộp được vào M0.1 của `hoan-thien-mvp-phep-so-dau-tien.md`, không cần đổi plan.

**Một điều tốt đáng ghi:** quét toàn bộ `packages/`, `services/`, `scripts/`, `apps/api` không
tìm thấy `TODO`, `FIXME`, `NotImplementedError` hay stub nào trong code sản phẩm. Hai chỗ
`pytest.skip` còn lại đều có điều kiện và hợp lý (thiếu cache hiệu chuẩn; map công bằng chưa
sinh). Không có nợ ẩn dạng placeholder — đó là lý do "sửa tiến" rẻ ở dự án này.

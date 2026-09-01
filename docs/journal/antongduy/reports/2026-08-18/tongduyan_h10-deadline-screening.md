# H10 — deadline gate đọc cả tick, và thước hết mơ hồ trước khi đo

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §13
**Trạng thái:** xong, 20 test mới xanh, 114 passed lát cắt decision, **chưa commit**.

---

## 1. Amendment protocol — làm **trước**, và vì sao bây giờ mới hợp lệ

`configs/latency-screening-v1.yaml` commit ở `f15ee25`, **trước cả H0**,
như một preregistration. Nó khai `confidence_method: bootstrap_ci` và
**không nói resample đơn vị gì**. Hai người đọc v1 sẽ dựng hai phép đo
khác nhau, và cả hai đều tuân thủ — nên nó không phải một thước khai
trước.

Sửa **hợp lệ ngay bây giờ** vì chưa có một phép đo latency nào tồn tại.
Sửa sau con số đầu tiên là thay thước giữa chừng, đúng thứ kỷ luật P4
tồn tại để chặn.

`v2` là file mới; **v1 không bị xoá** — lịch sử phải giữ được cả bản mơ
hồ lẫn lý do nó bị thay. Và v1 **bị từ chối khi nạp**, với lý do bản
chất chứ không phải hệ quả: *"does not say what it resamples"*, không
phải "2 validation errors".

## 2. Ba thay đổi của v2, tất cả về việc CI nói thật

**(a) Resample đơn vị = episode.** Tick trong cùng một episode chia sẻ
bản đồ, seed, quỹ đạo và trạng thái cache — chúng không độc lập.
Resample từng tick cho CI **hẹp hơn sự thật**, và một gate đọc CI hẹp
giả sẽ tuyên bố "đạt" từ dữ liệu không nói được điều đó.

Không dùng `planbench_metrics.statistics.bootstrap_ci`: nó resample
chính chuỗi được đưa, nên đưa tick vào là nhận một CI per-tick **đội tên
episode-level**. `_episode_bootstrap` lấy lại N episode có hoàn lại, gộp
tick của các episode được chọn, rồi **tính lại** p99 trong từng resample
— không phải trung bình của p99 từng episode, vì percentile của
percentile là thống kê của không cái gì.

Bỏ import đó cũng gỡ luôn một phụ thuộc thừa: tầng decision đang kéo
`planbench_metrics` → `planbench_simulator` chỉ để lấy một hàm không
dùng.

**(b) Sample size vào verdict record.** Resample theo episode nghĩa là N
quyết định độ rộng CI là **số episode** (30), không phải hàng nghìn
tick. Con số đó đi cạnh khoảng tin cậy thay vì để người đọc suy ra từ
một CI trông hẹp.

**(c) Sàn N, thắng cả CI.** Bốn episode giống hệt nhau cho CI rộng gần
bằng 0 và vẫn không nói gì về episode thứ năm. `min_episodes_for_verdict`
và `min_ticks_for_percentile` cho verdict `inconclusive` **bất kể** CI
nằm đâu.

## 3. `resample_unit` không có default — và đó là điểm tôi tự sửa

Bản đầu để `resample_unit: str = "episode"`. Test "v1 phải bị từ chối"
đỏ, và lý do đáng ghi: default đó khiến **v1 im lặng dùng được** dưới
một giả định nó chưa bao giờ khai. Một giá trị mặc định ở đây chính là
việc diễn giải hộ một tài liệu mơ hồ — đúng thứ v2 sinh ra để chấm dứt.

Giờ trường này không có default, và protocol không khai thì bị từ chối.

## 4. G4 tách đôi, không thay số

```text
G4:
  result       ← legacy algorithm-compute screen, nguyên nghĩa cũ
  end_to_end   ← LatencyVerdictRecord | None
  overall      ← cái nghiêm hơn quyết định
```

Ba luật của `overall`, mỗi luật một test:

- `end_to_end is None` ⇒ `overall == result`. **Vắng mặt không phải
  "đạt"**: hầu hết run không chạy phiên screening, và gate không được
  tuyên bố đã kiểm cả tick.
- `not_measured` **không** hạ verdict. Đó là phát biểu về *căn phòng*,
  không phải về robot — để một máy đang bận đánh trượt candidate sẽ biến
  gate thành phép đo xem lúc đó máy chạy gì.
- `inconclusive` **không** đọc thành pass.

## 5. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/test_latency_screen.py` (mới, 20 test) | **20 passed** |
| `tests/test_gates.py` + `test_decision_card.py` + H10 | **114 passed** |
| `ruff check` `packages/` | sạch |

Phép kiểm đáng nói nhất là **so bằng số**: cùng dữ liệu, resample theo
tick cho khoảng hẹp hơn rõ rệt so với resample theo episode. Đó là lý do
v1 phải sửa, chứng bằng con số chứ không phải một câu trong comment — và
nếu fixture ngừng mô hình hoá tick tương quan thì chính test đó nói ra.

## 6. Còn nợ, ghi rõ

`screen()` nhận sẵn per-tick `end_to_end_control_ms` theo từng episode.
**Chưa có** người gọi đọc sáu cột latency từ trace rồi dựng phiên đo —
warmup, sentinel trước/sau, đúng số repetitions, một worker. Đó là phần
*chạy* phiên screening, tách khỏi phần *chấm* nó.

Nói thẳng vì đây đúng lớp lỗi H9A vừa mắc: **thước có, chưa ai cầm.**
Với H10 tôi để ranh giới lộ ra thay vì tuyên bố gate đã hoạt động
end-to-end. Việc còn lại là một runner đọc trace và gọi `screen()`, và
nó cần cột trace của lane subprocess — tức cần một candidate thật chạy
lane đó, chưa có trong tập production.

## 7. Kế tiếp

H12 (eligibility cleanup + PPO parity), rồi H11 nếu An chốt ưu tiên.

# Rà soát Phase 6 sau khi chốt MVP v1

> **Ngày:** 2026-08-11 · **Loại:** đánh giá, **không đổi code**
> **Yêu cầu nguồn:** An — *"check lại phase 6 trong backlog 08-08, xem có cần làm lại hoặc test
> lại khi đã hoàn thành v1 của MVP."*
> **Kết luận ngắn:** **6.1 không cần làm lại, nhưng cần MỞ RỘNG trước khi 6.2 bắt đầu.** Lược đồ
> DB hiện tại giả định **mọi lần chạy đều kết thúc bằng một Decision Card**. MVP v1 vừa chứng
> minh điều đó sai: ba trên ba phép so không ra card, và **không artifact nào trong ba loại đang
> có được lưu nổi vào lược đồ này** trừ đúng một loại.

---

## 1. Phase 6 gồm gì, và đang ở đâu

| # | Việc | Trạng thái |
|---|---|---|
| 6.1 | Migration `task_profiles`, `candidates`, `decision_cards` | ✅ `0005_decision_layer`, có `tests/api/test_migrations.py` |
| 6.2 | Router `/task-profiles`, `/candidates`, `/decisions` | ⛔ chưa bắt đầu |
| 6.3 | Nối Approval sẵn có → `approved_config.yaml` | ⛔ chưa bắt đầu, phụ thuộc 6.2 |

Ba bảng đã tồn tại và **chưa có gì đọc/ghi chúng** ngoài `models.py` — không repository, không
router, không worker. Nên chi phí sửa lược đồ lúc này gần bằng không: không có dữ liệu để migrate,
không có API để phá.

---

## 2. Không cần làm lại — nhưng lược đồ đang thiếu hai loại artifact

Từ khi `0005` được viết (contract `5.0.0`), tầng quyết định sinh ra **ba** loại artifact, không
phải một:

| Artifact | Sinh bởi | Khi nào | Có chỗ trong DB? |
|---|---|---|---|
| `decision_card.json` + `manifest.json` | `compare.py`, `vertical_slice.py` | ≥ 2 candidate qua đủ sáu cổng | ✅ `decision_cards` |
| `comparison_report.json` | `compare.py` | **mọi** phép so, kể cả khi không ra card | ⛔ **không** |
| `measurement_report.json` | `measure.py` | đo một candidate | ⛔ **không** |

`decision_cards` khai `recommended_candidate_id NOT NULL` và `card NOT NULL`. Một phép so mà dưới
hai candidate qua cổng **không có** hai trường đó, nên nó không lưu được — kể cả khi nó đã chạy
đủ 60 episode và có một bảng cổng đầy đủ.

**Đây không phải chi tiết kỹ thuật.** Trên `open_hall_v2`, **ba trên ba** phép so rơi vào đúng
trường hợp đó. Nếu 6.2 được viết trên lược đồ hiện tại thì `POST /decisions` sẽ chạy 60 episode
rồi **không lưu được gì**, và `GET /decisions/{id}` không có gì để trả — trong khi thứ vừa được
đo ra là một kết quả hoàn toàn hợp lệ.

Lược đồ hiện tại mã hoá đúng giả định mà cả tầng quyết định được viết để bác bỏ: rằng mọi lần
chạy đều xếp hạng được. Nó là bản DB của cùng áp lực đã sinh ra tấm card tuyên bố cận trên va
chạm từ một episode.

---

## 3. Ba thứ cần sửa trước khi mở 6.2

### 3.1. Một bảng cho lần chạy, thay vì một bảng cho tấm card *(bắt buộc)*

Đề xuất: `decision_runs` là bảng chính — mọi lần chạy đều có một hàng, và tấm card là **trường
nullable** trên đó.

```
decision_runs
  id, task_profile_id, artifact_kind {decision_card|comparison|measurement}
  contracts_version, created_at, created_by
  report          JSON  NOT NULL     -- comparison_report / measurement_report
  card            JSON  NULL         -- chỉ khi ≥2 candidate qua cổng
  manifest        JSON  NULL         -- đi cùng card
  recommended_candidate_id  NULL     -- chỉ khi có card
  status          NULL               -- PENDING/APPROVED/REJECTED, chỉ khi có card
  run_uri, run_checksum              -- D15, giữ nguyên
```

Điểm chính: **`report` NOT NULL, `card` NULL.** Bảng nói rằng một lần chạy luôn sinh bằng chứng
và **đôi khi** sinh một khuyến nghị — chứ không ngược lại.

Chi phí: một migration `0006`, không có dữ liệu để chuyển.

### 3.2. Bốn trường mới trong manifest chưa được kiểm ở tầng DB *(nên có)*

Từ `5.0.0` tới `6.3.0`, manifest và card mọc thêm:

- `benchmark_host.cpu_affinity`, `.logical_cores`, `.affinity_source` (6.2.0)
- `manifest.sensor_noise` (6.3.0)
- `evidence.delta_u_mean` (6.0.0)
- gate table: `G2.n_distinct_episodes` (6.0.0)

Cột `manifest`/`card` là JSON nên **không cần migration** — nhưng `test_migrations.py` hiện chỉ
kiểm bảng và index tồn tại. Nó không kiểm rằng một manifest thật của contract hiện hành **ghi vào
rồi đọc ra vẫn còn đủ bốn trường đó**. Với JSON column, đó chính là loại mất mát im lặng duy nhất
có thể xảy ra.

Đề xuất: một round-trip test dùng manifest thật từ `artifacts/runs/` thay vì một dict bịa.

### 3.3. `sensor_noise` phải nằm trong khoá tra cứu, không chỉ trong payload *(quan trọng)*

`episode_context_id` **không** băm biên độ nhiễu (HĐ-3.1 đóng băng payload). Trên đĩa, luật đang
được giữ bằng kỷ luật đặt tên: *đổi biên độ ⇒ đổi `task_profile_id`* (`open_hall_v1` so với `v2`).

Khi có DB, kỷ luật đó phải thành ràng buộc. `task_profiles.id` là khoá chính và profile được lưu
nguyên trong cột `profile`, nên hai profile khác σ mà cùng `id` sẽ **ghi đè nhau** — và mọi
`decision_runs` trỏ tới id đó bỗng nói về một thế giới khác, không có gì báo.

Rẻ nhất: `UNIQUE(id)` đã có, thêm một kiểm lúc ghi rằng profile gửi lên **trùng khít** profile đã
lưu dưới id đó, và từ chối nếu khác. Đây đúng là bẫy HĐ-13 mô tả, chuyển sang tầng lưu trữ.

---

## 4. Có cần test lại 6.1 không?

**Không cần chạy lại — nhưng `test_migrations.py` đang kiểm nhầm tầng.**

Nó khẳng định upgrade/downgrade chạy được và ba bảng có đủ cột. Điều đó vẫn đúng và full suite
xanh (**2140 passed, 6 skipped**). Cái nó **không** kiểm: một artifact thật của contract hiện hành
có lưu được không. Câu hỏi đó chưa từng có câu trả lời, vì chưa có repository nào để hỏi.

Nói cách khác: 6.1 xanh vì nó chỉ tự kiểm chính nó. Lỗ hổng ở mục 2 sẽ chỉ lộ ra ở dòng đầu tiên
của 6.2 — và nếu 6.2 được viết trước khi lược đồ mở ra, nó sẽ được viết quanh giả định "mọi run
đều ra card", rồi phải viết lại.

---

## 5. Đề xuất

| # | Việc | Chi phí | Vì sao trước/sau |
|---|---|---|---|
| 1 | Migration `0006`: `decision_runs`, `card`/`manifest` nullable, `report` NOT NULL | ~2 giờ | **Trước 6.2.** Không có dữ liệu để chuyển; sau 6.2 thì phải sửa cả router |
| 2 | Round-trip test bằng artifact thật từ `artifacts/runs/` | ~1 giờ | Cùng lượt, vì nó là thứ chứng minh (1) đúng |
| 3 | Kiểm profile-trùng-khít khi ghi `task_profiles` | ~1 giờ | Cùng lượt — bẫy `sensor_noise` chuyển sang tầng DB |
| 4 | 6.2 router | theo backlog | Sau (1)–(3) |
| 5 | 6.3 approval | theo backlog | Sau 6.2 |

**Một điều cố ý không đề xuất:** đừng vội viết 6.2 để "có API cho MVP". MVP v1 là một lệnh CLI và
một file JSON, và nó đã đủ để trả lời câu hỏi của đề tài. API là bề mặt, không làm phép đo tốt
hơn — và viết nó trên một lược đồ mã hoá sai giả định sẽ đắt hơn nhiều so với sửa lược đồ bây giờ.

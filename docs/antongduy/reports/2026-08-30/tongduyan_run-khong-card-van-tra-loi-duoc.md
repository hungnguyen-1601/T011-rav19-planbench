# Một run không có decision card giờ vẫn trả lời được câu hỏi episode

**Ngày:** 2026-08-30 · **Nhánh:** `tongduyan_analyst-episode` (worktree `P-011-merge`)

## Triệu chứng An gặp

Mở `Wide_corridor_v4` — một run cố ý không có decision card, để thử
đường `outcome_only` — dock trả về:

> this run ranked nobody, so it names no pair to compare

Câu đó trả lời một câu hỏi khác với câu được hỏi. Người đọc mở một run
không card là đã biết nó không xếp hạng ai; cái họ hỏi là **episode này
hai bên chạy ra sao**, và run đó có đúng hai candidate nên không có gì
để đoán.

## Nguyên nhân

`cardless_pair` — hàm chọn cặp cho run không card — chỉ tồn tại trong
`scripts/run_episode_experiments.py`, tức là chỉ chạy khi chấm thí
nghiệm ngoại tuyến. API không có nó, nên
`decision_service.episode_verdict` gặp `comparison_pair = None` là từ
chối thẳng.

## Đã sửa

| Chỗ | Việc |
|---|---|
| `packages/explanation/planbench_explanation/exemplars.py` | Nhận `cardless_pair` + `CardlessPairRefusal` từ script về đây, thành luật dùng chung |
| `apps/api/planbench_api/decision_service.py` | `episode_verdict` gọi `cardless_pair` khi run không có `comparison_pair`; từ chối vẫn giữ nguyên hình dạng cũ (`InvalidStateError`) |
| `scripts/run_episode_experiments.py` | Xoá bản sao nội bộ, import bản dùng chung — script và API giờ không thể lệch nhau |

**Luật mới, đúng một câu:** run không card mà có **đúng hai** candidate
thì đọc được, xếp theo `candidate_id`; từ **ba** trở lên vẫn từ chối.

Vì sao cái ngưỡng đó: chọn hai trong ba là một *khẳng định*, và thứ tự
đăng ký không phải khẳng định. Nhưng hai thì không có gì để chọn, nên
từ chối ở đó không bảo vệ được gì — nó chỉ đổi một câu trả lời đúng
lấy một câu nói về xếp hạng.

## Test

- `tests/test_episode_cardless_cases.py` — 8 pass (đổi import sang bản dùng chung)
- `tests/api/test_api_episode_verdict.py` — 17 pass
  - thêm `TestARunThatRankedNobody` (3 test): hai candidate trả lời được, ba từ chối, cặp xếp theo id
  - test cũ `test_a_run_that_ranked_nobody_refuses_rather_than_picking` **ghim đúng cái hành vi An bảo đổi**, nên viết lại thành `test_a_run_that_ranked_nobody_is_still_read_as_its_two_candidates`, docstring nêu vì sao 409 cũ chỉ đúng một nửa
- Suite episode (10 file) — 236 pass
- `ruff check` + `ruff format --check` — sạch trên 5 file đã sửa

**Cổng có cắn.** Tiêm lỗi: thay `cardless_pair(report)` bằng
`raise CardlessPairRefusal(...)` ⇒ 3 đỏ trong 17. Khôi phục ⇒ xanh lại,
đã kiểm bằng grep là không sót mảnh tiêm nào.

## Còn lại, không nằm trong phạm vi lần này

- An cần thêm `PLANBENCH_EPISODE_ANALYST_MODE=internal_preview` vào
  `.env` rồi restart API thì dock mới gọi được nửa tốn tiền.
- PR ở remote `org` cho `tongduyan_analyst-episode` chờ An mở.
- Chạy trọn deployment config (cả 3 flag) một lượt trước khi demo ngoài
  (~$0.42) — đã hoãn từ phiên trước, chưa làm.

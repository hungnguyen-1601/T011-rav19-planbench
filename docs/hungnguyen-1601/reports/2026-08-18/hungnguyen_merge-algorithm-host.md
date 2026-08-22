# Merge nhánh Algorithm Host của An — 61 conflict và ba lỗi lộ sau đó

**Ngày:** 2026-08-18 · **Commit:** `145b688`
**Quy mô:** 238 file, +111.934 −813 · 156 commit của An

---

## 1. Vì sao 61 file conflict

Lần gỡ trailer co-author tuần trước viết lại lịch sử, khiến các commit
`plannerselector` đã merge trước đó trở thành **object khác**. Merge-base
vì thế lùi về `2dafc93`, và mọi file hai bên cùng chạm đều thành
`add/add`.

Bài học: viết lại lịch sử một nhánh đã merge thì trả giá ở lần merge sau,
không phải ngay lúc đó.

## 2. Cách phân loại thay vì hoà mò

Chia conflict theo **ai đã sửa file đó kể từ mốc merge trước**:

- 42 file chỉ An sửa → lấy bản của An
- 19 file cả hai sửa → hoà tay từng hunk

## 3. Bốn quyết định đáng ghi

**Chat cũ giữ nguyên trạng thái đã xoá.** Nhánh An vẫn còn `chat_service`;
nhánh này đã thay bằng `/agent/chat`. Giữ bản thay thế, gỡ khỏi router,
i18n và dependency.

**`test_replanning` lấy nguyên bản của An.** An sửa triệt để hơn tôi: so
với thời gian planner **tự báo**, thay vì so hai phép đo wall-clock với
nhau. Comment của An ghi lại rằng bản vá trung vị của tôi vẫn đỏ trong
một lượt suite 46 phút. Bản thứ ba là bản đúng.

**i18n hoà ba chiều theo khoá.** Khoá tôi đổi tên (`ứng viên` → `phương
án`) giữ nguyên; khoá mới của An vào và được dịch theo quy ước; 50 khoá
của giao diện chat đã xoá **không được hồi sinh**.

**`decision_service` lấy `validate()`/`create()` tách đôi của An** cộng
`trace_summary` của nhánh này.

## 4. Ba lỗi lộ ra sau merge, chỉ khi chạy

**Test mồ côi.** `test_b1_room_to_leave.py` import `_inflation_radius` —
hàm An đã xoá cùng commit `4ddab12`, thay bằng `test_graded_inflation.py`.
Merge giữ lại bản mồ côi vì lịch sử bị viết lại biến nó thành `add/add`
thay vì một lần xoá có theo dõi.

**Golden lệch 1 ulp giữa hai máy.** Hai fixture so byte-identical theo
thiết kế, sinh trên máy An:

| Fixture | Vị trí | Chênh |
|---|---|---|
| `test_host_parity_golden` | bước 253 | `0.5057366025511915` vs `...916` |
| `test_dwa_core_refactor` | index 85 | `0.981309695401335` vs `...3352` |

libm của WSL cho kết quả lượng giác khác **bit cuối cùng**. Regenerate
qua đúng cơ chế hai test công bố, kèm lý do — vì fixture trả lời câu hỏi
*"host wrap có đổi runtime trên máy này không"*, nên baseline phải sinh
trên máy này.

**Cần An quyết:** CI dùng ubuntu-latest là **libm thứ ba**. Nới tolerance
hay tách fixture theo máy là quyết định về ý nghĩa guard của An.

**Hunk chọn sai làm rớt trường.** Một hunk tôi chọn làm mất
`summary`/`fabricated`/`refused` khỏi resource; pydantic nuốt im lặng nên
HTTP vẫn 200 mà thiếu dữ liệu. Chỉ lộ khi gọi thật và đọc JSON trả về.

## 5. Kết quả

`3.392 test Python + 980 test web`, không lỗi.

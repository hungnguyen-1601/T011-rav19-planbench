# Phase 2a — hỏi server "tài liệu này có hợp lệ không" mà không nộp

> Plan: `docs/antongduy/plans/2026-08-15/config-vat-the-dong-tren-form-deployment.md` (v5, mục Phase 2a).
> Ngày làm: 2026-08-15. Nhánh: `tongduyan_plannerselector`. **Chưa commit.**

## Vấn đề phải giải

Form khai deployment có ba chục ô nhập cộng một khối traffic. Nguyên tắc
của nó là **"the form decides nothing"** — `TaskProfile` phía server là
tuyên bố duy nhất của HĐ-2, và test
`deployments-page.test.tsx:107` ghim điều đó bằng cách cấm form chứa luật
hợp đồng nào. Nhưng nếu lời từ chối chỉ đến lúc bấm nộp, người khai phải
tự đoán server ghét ô nào.

Cách sửa hấp dẫn — chép vài luật dễ sang TypeScript — chính là thứ form
được xây để không làm. Nên lời phán vẫn phải là của `TaskProfile`, chỉ
cần **hỏi được** thay vì **chép lại**.

## Đã làm

### 1. Tách `TaskProfileService.validate(payload)`

`decision_service.py` — phần `TaskProfile.model_validate` + bọc thành
`DomainValidationError` (kèm `field_errors`) tách khỏi `create()`.
`create()` giờ gọi `self.validate(payload)` rồi mới lưu.

Lý do tách chứ không viết endpoint tự bọc `model_validate` lần nữa: hai
chỗ tự bọc là hai định nghĩa về **hình dạng của một lời từ chối**, và
chúng sẽ trôi khỏi nhau.

### 2. `POST /api/v1/task-profiles/validate`

`routers/decisions.py`, đặt ngay cạnh `create` và `derive`.

| Trường hợp | Trả về |
|---|---|
| Tài liệu hợp lệ | **204**, không body |
| Tài liệu sai | **422**, đúng envelope mà `POST /task-profiles` trả |
| Không đăng nhập | **401** |

Ba quyết định ghi thẳng vào docstring endpoint:

- **Trả 422 chứ không phải 200 kèm report.** Client dùng nguyên
  `authFetch` → `FieldError` → `fieldErrorsOf` (`auth.ts:207-231`) sẵn có,
  nên form có **một** đường xử lý lỗi thay vì hai. Đây là điểm An chốt ở
  vòng review 2: `fieldErrorsOf` chỉ đọc lỗi bị throw, không đọc body của
  một response thành công.
- **Không đọc store.** Không repository, không danh sách id đang dùng. Vì
  vậy 204 **không phải** lời hứa "nộp sẽ được": một id đã có trên hệ
  thống với nội dung khác vẫn qua được đây và bị `create` từ chối 409
  (HĐ-3.1). Endpoint nói rõ điều đó thay vì để người gọi hiểu nhầm.
- **Vẫn đòi đăng nhập.** Không ghi gì, không sở hữu gì — nhưng nó chạy
  đúng code path mà `create` chạy, và một cánh cửa vào đó không cần tài
  khoản là cánh cửa sẽ trôi khỏi cánh cửa bên cạnh.

### 3. Test: `tests/api/test_api_profile_validation.py` (10 ca)

Ghim hai tính chất mà mọi thứ phía trên dựa vào:

**Lời từ chối có một hình dạng.** Cùng một tài liệu hỏng, `validate` và
`create` trả cùng status, cùng danh sách path, cùng message.

**Path thô đến đâu thì ghim đến đó — đúng sự thật, không phải mong
muốn.** Bốn luật traffic (tên trùng, thiếu head start, periodic thiếu
một chu kỳ, `v_obstacle_max` thấp hơn tốc độ traffic) đều là model
validator trên `EnvironmentSpec`, nên pydantic báo về `environment`, chứ
không về vật cản gây lỗi. Bốn test khẳng định đúng `["environment"]`.

Kèm **một ca đối chứng** làm cho các path thô ở trên đọc được:
`radius = -1.0` báo về `environment.dynamic_obstacles.0.radius`. Nghĩa là
endpoint không hề làm phẳng đường dẫn trên đường ra — pydantic địa chỉ
được tới đâu thì giữ tới đó; bốn luật kia thô vì **chỗ chúng được viết**,
không phải vì lớp truyền tải.

Và hai ca về giới hạn: validate xong danh sách profile không đổi, `GET`
id đó vẫn 404; id đã nộp với nội dung khác vẫn **204 ở validate** rồi
**409 ở create**.

## Bằng chứng

| Kiểm | Kết quả |
|---|---|
| `pytest tests/api/test_api_profile_validation.py` | **10 passed** (xanh ngay lần chạy đầu — kể cả dự đoán về path) |
| `pytest tests/test_task_profile.py tests/api/test_api_decisions.py::TestDeployments tests/api/test_robot_profile_boundary.py` | **94 passed** — `create()` sau refactor không đổi hành vi |
| `pytest tests/api` (toàn bộ) | **618 passed, 1 skipped** trong 23 phút 17 giây — route mới không giẫm lên route nào |

## Không đụng tới

- Không sửa schema, không thêm field — nên không đổi `_scenario_checksum`,
  không đụng manifest drift guard.
- Không nối dây phía web: `apps/web` chưa gọi endpoint này. Wiring, state
  `dryRunErrors`, chỗ render `errorFor("environment")` là Phase 2b.
- Không đụng `_seed_time_shift` — **điểm quyết #4 vẫn chặn Phase 2b**
  (mục 0c của plan).

## Ghi chú cho Phase 2b

Path `environment` giờ **đã được kiểm chứng bằng test**, không còn là suy
đoán từ đọc code. Nghĩa là khối TrafficEditor bắt buộc phải có một chỗ
render `errorFor("environment")`, nếu không cả bốn lỗi traffic sẽ tàng
hình với người dùng — đúng như An chỉ ra ở vòng review 3.

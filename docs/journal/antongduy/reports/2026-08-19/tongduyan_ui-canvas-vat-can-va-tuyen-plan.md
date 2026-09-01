# UI — vật cản động và tuyến planner trên canvas trace

**Ngày:** 2026-08-19 · **Nhánh:** `tongduyan_3` · Nối tiếp báo cáo evidence panel

**Trạng thái:** xong, **chưa commit**. Full suite chưa chạy (theo yêu cầu).

---

## 1. Hai thứ thiếu, và vì sao chúng là một vấn đề

An chỉ ra hai điểm trên canvas so sánh hai thuật toán trong một episode:

1. **Vật cản động không hiện.** Map là tĩnh, trace chỉ ghi robot — nên một đường đi
   né chiếc xe đẩy đang **né một thứ không có trên màn hình**. Cái duy nhất giải
   thích khúc cua thì lại bị thiếu khỏi bức tranh chứa khúc cua đó.
2. **Không thấy tuyến global planner.** Replan là *khoảnh khắc kế hoạch và thực tế
   tách nhau*; canvas chỉ vẽ cái thứ hai thì không nói được điều đó.

Cả hai đều là dạng lỗi "nhìn thì vẫn hợp lý": không có gì báo sai, chỉ là người đọc
suy ra một câu chuyện khác.

---

## 2. Vật cản động

### Lấy từ đâu

Không lưu thêm cột nào vào trace. Vị trí được **dựng lại bằng chính motion model của
nền tảng**, `planbench_schemas.dynamic.position_at(obstacle, t, seed)`, tại đúng
`seed` của episode đó.

| Helper | Việc |
|---|---|
| `_context_for(profile, episode_context_id)` | tìm lại `EvaluationContext` từ id băm nội dung |
| `_obstacle_tracks(profile, context, times)` | một vị trí cho **mỗi timestamp của trace** |

### Ba ràng buộc, mỗi cái một test

- **Cùng nhịp với trace.** Track lấy mẫu theo lưới thời gian của chính trace, không
  phải lưới riêng. Lưới riêng sẽ trôi dần so với robot, và độ trôi đó **trông y hệt
  robot đi xuyên qua xe đẩy**.
- **Đúng seed.** `position_at` dịch đồng hồ mỗi vật cản theo hash của seed, nên hai
  seed là hai episode khác nhau. Vẽ nhầm seed cho ra một bức tranh hợp lý về một lần
  chạy chưa từng xảy ra.
- **Không dựng lại được thì không vẽ.** `_context_for` trả `None` thì trả danh sách
  rỗng. **Vắng mặt tốt hơn sai chỗ**: một chiếc xe đẩy đặt nhầm chỗ sẽ được đọc như
  bằng chứng.

Đo thật chứ không assert lỏng: profile `sudden_stop`, cart chạy `y=7.88 → 4.50` rồi
dừng hẳn quanh `t≈4s` — đúng tên của deployment.

---

## 3. Tuyến planner đã yêu cầu

### Nguồn: sidecar E4.5, không phải nguồn mới

`_planned_routes(trace_path, events)` đọc sidecar `*.planning_inputs.jsonl` cạnh file
trace — thứ E4.5 đã ghi sẵn: **mọi lần planning, kể cả lần không tìm ra đường**.

### Đặt tuyến vào đúng bước nào

Điểm dễ sai nhất. Bản ghi đếm **simulation tick**, trace đếm **control step**. Quy
đổi giữa hai cái sẽ tạo ra **ý kiến thứ ba** về dòng thời gian của episode. Nên
handover lấy từ **event `replan` của chính trace**:

```
attempt 1 → from_index 0
attempt 2 → from_index = index của event replan thứ nhất
attempt 3 → từ event replan thứ hai
```

Số attempt và số event `replan` **lệch nhau thì không vẽ gì cả** — một tuyến đặt sai
thời điểm là một quyết định không ai từng đưa ra.

### Thay thế, không chồng lớp

`routeAt(routes, step)` trong `lib/evidence.ts` trả **tuyến mới nhất đã tiếp quản, và
chỉ nó**. Vẽ tất cả attempt cùng lúc sẽ cho ra một nan quạt các đường robot chưa bao
giờ có, và không gì trên màn hình nói được nó đang bám cái nào.

`null` — cố ý — cho attempt **không tìm ra đường**: tại bước đó robot không có tuyến
nào, giữ tuyến cũ lại là vẽ một kế hoạch đã bị bỏ.

### Thứ tự vẽ

Tuyến plan (xám nét đứt) vẽ **trước**, rồi mới tới đường đi thật và các vòng vật cản.
Kế hoạch nằm dưới thực tế, không che thực tế.

---

## 4. Xác minh trên dữ liệu thật

Chạy trên một run thật có replan:

```
attempt 1: 2 điểm, bắt đầu (2.00, 3.50)
attempt 2: 6 điểm, bắt đầu (7.09, 3.50)
```

Đúng như kỳ vọng: lần replan xảy ra khi robot đã đi được một đoạn, và tuyến mới xuất
phát từ chỗ nó đang đứng — không phải từ điểm start.

---

## 5. Test

| File | Nội dung |
|---|---|
| `tests/api/test_api_obstacle_tracks.py` | 6 test vật cản + 5 test tuyến plan |
| `apps/web/src/lib/__tests__/evidence.test.ts` | 6 test cho `routeAt` |

Test đầu tiên của file là **`test_the_fixture_actually_declares_traffic`** — không có
nó thì mọi assertion còn lại pass bằng cách không có gì để kiểm.

---

## 6. Còn lại

- Chưa commit.
- Full suite chưa chạy — chỉ chạy phần vừa sửa, theo đúng yêu cầu.

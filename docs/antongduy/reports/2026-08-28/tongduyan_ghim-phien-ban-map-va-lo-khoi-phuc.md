# Map sửa lên v3 mà test bench vẫn chạy v2 — và lỗ khôi phục đằng sau nó

Ngày 2026-08-28 · **đã sửa code**, chưa commit

An báo: sửa map lên v3, chạy lại test bench thì vẫn là v2. Checksum
`4e38f71803…`.

---

## 1. Chẩn đoán

**Không phải cache, không phải quyền, không phải frontend.**

| Đo | Kết quả |
|---|---|
| `GET /maps/b92f3f964633` | **v3**, checksum `4e38f7180394686a` — đúng bản An sửa |
| `SqlMapRepository.update` | sửa **tại chỗ** (`row.version += 1`), một map một dòng, **không có bảng lịch sử** |
| Deployment `sudden_stop_custom` | `environment.map = maps/custom/b92f3f964633__v2.pgm` |
| File trên đĩa | có `__v1`, `__v2`. **Không có `__v3`** |

API **không thể** trả v2 cho ai — không còn dòng nào giữ v2. Cái chạy v2
là **file trên đĩa**, và deployment ghim thẳng số version vào đường dẫn.

Chuỗi đầy đủ:

1. An sửa map → DB lên v3.
2. Bench gọi `stage()` → `ensure_profile_map_materialised()` thấy
   `__v2.pgm` **đã có trên đĩa** thì `return True` ngay, không đụng DB.
3. `load_task_map(profile)` đọc **file**, tức v2.
4. `_existing_map()` dò bảng maps tìm dòng có lưới **bằng file đó** —
   `b92f3f964633` giờ là v3 nên trượt, nhưng khớp một trong **23 dòng
   `sudden-stop` trùng lặp** khác.

**Trình soạn map ghi vào database. Test bench đọc từ đĩa.** Deployment
ghim version ở giữa.

**Phần ghim là đúng và phải giữ.** `episode_context_id` băm
`(task_profile_id, mission_id, environment_variant, seed)` và HĐ-3.1
đóng băng payload đó — **map không nằm trong đó**. Kéo một deployment
sang bức tường mới dưới cùng id sẽ khiến mọi run đã lưu mô tả một nơi
không còn tồn tại, mà id vẫn khớp nên không gì cảnh báo. Docstring của
`materialise_map` và của `TaskProfileService.derive` đều nói đúng điều
này.

Cái sai là **không ai được báo**. Trang soạn map ghi *"Saving creates a
new map version on the backend"* ngay cạnh link *"Run a simulation →"*.

---

## 2. Lỗ thật, phát hiện cùng lúc, nguy hiểm hơn triệu chứng

`ensure_custom_map_files` cũ:

```python
stored_map = map_repo.get(map_id_candidate)      # dòng DB hiện tại = v3
materialise_map(stored_map, map_root, stem=requested_stem)   # ghi vào tên __v2
materialise_map(stored_map, map_root)                        # và __v3
```

Nếu `__v2.pgm` **mất** (restart container, checkout mới, dọn thư mục),
nhánh khôi phục lấy lưới **v3** ghi đè vào **tên file v2**. Deployment
ghim v2 lặng lẽ bắt đầu đo một thế giới nó chưa từng đồng ý, còn mọi
trace cũ nằm cạnh vẫn khai là cùng một nơi.

Nó vi phạm đúng câu docstring ngay phía trên nó:

> *"The name is `<id>__v<version>`, so a map edited after a deployment
> was filed from it lands in a different file. The deployment keeps
> pointing at the walls its episodes were driven on — which is the only
> reading under which its stored traces are still evidence."*

Chỗ này chạy **khi không ai nhìn**. Đó là lý do nó phải từ chối chứ
không được đoán.

---

## 3. Đã sửa — ba việc An duyệt

### Việc 1 · Chặn ghi nhầm phiên bản

`ensure_custom_map_files` giờ so version yêu cầu với version trong kho:

- khớp → khôi phục như cũ,
- lệch → **từ chối**, `return False`, kèm log nêu tên map, version bị
  ghim, version đang có, và đường đi đúng (`POST /task-profiles/derive`).

Bỏ luôn dòng `materialise_map(stored, map_root)` thứ hai — nó ghi file
không ai yêu cầu.

Thêm `pinned_map_reference(path)` — **một** chỗ đọc quy ước tên file
`<id>__v<n>`, dùng chung cho khôi phục và cho endpoint mới. Đọc ở hai nơi
là hai định nghĩa của một quy ước.

### Việc 2 · Nói ra chỗ ghim

**`GET /maps/{id}/pins`** → `{current_version, pins: [{task_profile_id,
pinned_version, stale}]}`. Mở cho mọi người đọc: câu hỏi *"sao sửa xong
bench không đổi?"* thuộc về người đang sửa, không thuộc về người quản trị.
Quét thẳng danh sách profile chứ không dựng index — vài chục deployment,
và index là bản sao thứ hai của sự thật profile đã khai.

**Trang soạn map**: panel dưới canvas, liệt kê deployment nào chạy map
này ở version nào, cái nào **đang tụt lại**. Panel khoá theo `version`
nên **lưu xong là hỏi lại ngay** — đúng khoảnh khắc mọi ghim vừa thành
cũ. Không có deployment nào thì không vẽ gì.

**Test Bench**: chân khối điều kiện hiện thêm `map <id> v<n>` — bức
tường nó thật sự dàn dựng.

### Việc 3 · Đường đi tiếp

An đề nghị "cho phép trỏ deployment sang version mới". Em **không** làm
đúng như thế, và đây là lý do.

Trỏ tại chỗ là chính cái `SqlTaskProfileRepository.create` từ chối, bằng
câu:

> *"reusing an id for a changed deployment would make stored runs
> describe a world that no longer exists. Give the new deployment a new
> id, the way open_hall_v1 and open_hall_v2 do"*

`POST /task-profiles/derive` **đã có sẵn**, có test, và làm đúng việc an
toàn: sao y deployment, đặt map mới, **id mới**. Nên việc 3 là **đưa
đường đó ra chỗ người dùng đụng tường**, không phải viết endpoint mới.

Panel có ô nhập id mới và nút *"Tạo deployment mới trên bản này"*, chỉ
hiện ở dòng đang tụt lại. Refusal của server hiện nguyên văn — cái đáng
đọc nhất là "mission có goal nằm trong bức tường bạn vừa vẽ", và nó nêu
đúng mission nào.

Nếu An vẫn muốn trỏ tại chỗ thì đó là **nới một bất biến HĐ-3.1**, cần
sửa contract trước, và em không tự làm.

---

## 4. Nghiệm thu

```
tests/api/test_api_maps.py       25 pass  (16 → 25, +9)
tsc --noEmit                     sạch
web: map-pins.test.ts            9 pass
web: toàn bộ lib+components+app  17 đỏ, 0 lỗi mới so với nền f10fb1a
khoá i18n thiếu                  0
ruff check                       map_files.py 2 lỗi E402 (có sẵn, bản cũ 3)
```

**Chứng minh cổng mới cắn.** Không tin nó vì nó xanh — em bỏ bản sửa
`map_files.py`, chạy đúng test đó trên code cũ:

```
FAILED test_recovery_refuses_to_serve_a_different_version   ← code cũ
1 passed                                                     ← code mới
```

Log của lần đỏ cho thấy nguyên văn cái lỗi: `materialise_map: wrote
…__v1.pgm` rồi `…__v2.pgm` — ghi lưới hiện tại vào **cả hai** tên.

Test mới, và mỗi cái pin một tính chất chứ không pin hình dạng:

| Test | Giữ điều gì |
|---|---|
| `test_it_reads_the_id_and_version_out_of_the_path` | một chỗ đọc quy ước tên file |
| `test_recovery_refuses_to_serve_a_different_version` | lệch version thì **không ghi gì cả** |
| `test_recovery_still_works_when_the_version_matches` | ca thường vẫn chạy, restart không thành sự cố |
| `test_it_reports_a_deployment_as_current_until_the_map_moves` | sửa map xong thì `stale` bật |
| `test_stale_deployments_are_listed_first` | cái tụt lại nằm đầu — nó là câu trả lời người ta cần |
| `test_a_deployment_on_a_bundled_map_pins_nothing` | map dựng sẵn không phải ghim |

---

## 5. Chưa làm

**Chưa commit.** Ba việc này nên là **ba commit riêng** — vá lỗ khôi
phục là bug fix, endpoint pins là tính năng, panel là UI.

**Chưa nhìn bằng mắt.** Cần An mở lại `/maps/b92f3f964633` — panel phải
hiện `sudden_stop_custom` ở v2 kèm dòng *"Bạn đang sửa v3"*, và nút tạo
deployment mới.

**23 dòng map trùng lặp chưa dọn.** `sudden-stop` có 24 dòng, 23 dòng
cùng checksum. `adopt()` có chống trùng bằng `find_by_checksum` nhưng
đường import của library gọi `create()`. Đây là lý do `_existing_map()`
bắt nhầm dòng. Chưa chạm — dọn dữ liệu trong DB đang được chấm là việc
cần An đồng ý riêng.

---

## 6. File đã đụng

| File | Việc |
|---|---|
| `apps/api/planbench_api/map_files.py` | `pinned_map_reference()`; khôi phục từ chối khi lệch version |
| `apps/api/planbench_api/routers/maps.py` | `GET /maps/{id}/pins` |
| `tests/api/test_api_maps.py` | +9 test |
| `apps/web/src/lib/api.ts` | `api.mapPins()`, kiểu `MapPin`/`MapPins` |
| `apps/web/src/components/MapPins.tsx` | **mới** — panel ghim + derive |
| `apps/web/src/app/maps/[id]/MapEditor.tsx` | gắn panel |
| `apps/web/src/app/simulate/page.tsx` | hiện version map đã dàn dựng |
| `apps/web/src/lib/i18n/locales/*.json` | +12 khoá mỗi bên |
| `apps/web/src/app/__tests__/map-pins.test.ts` | **mới** — 9 test |

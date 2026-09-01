# Vì sao bảng map đầy dòng trùng — nguyên nhân, cơ chế chặn, và dọn

Ngày 2026-08-28 · **đã sửa code + đã dọn dữ liệu**, chưa commit

An hỏi: sao map sinh ra nhiều dòng trùng checksum thế, tìm nguyên nhân,
chặn không cho sinh nữa, và dọn.

---

## 1. Trước tiên: một điều tôi nói sai ở lượt trước

Lượt trước tôi nói *"23 dòng trùng lặp, `_existing_map` bắt nhầm một
trong số đó"* và ngụ ý staging đẻ một dòng mỗi lần bấm. **Sai.** Đo kỹ
thì có **hai quần thể khác hẳn nhau**, và staging đẻ một dòng cho mỗi
*(map, version)* chứ không phải mỗi cú bấm:

| Quần thể | Số dòng | Ai sinh | Còn sinh không |
|---|---|---|---|
| Trùng **cả tài liệu** (`static-obstacles` 111, `sudden-stop` 28, `crossing` 7, `bidirectional-corridor` 5, `open-space` 3, `wide-corridor` 2) | **150 dòng thừa** | form/library trước khi có `adopt()` | **Không** — dừng 22/08 |
| Tên kiểu **stem file** (`ebe3b6bec776__v1`…) | **27 dòng**, tên **đều khác nhau** | staging của test bench | **Có** — mới nhất 26/08 và 28/08 |

`adopt()` vào ngày **23/08** (`043e49d`), đúng ngày sau dòng
`static-obstacles` cuối cùng. Rò lớn đã bịt từ trước; commit đó thậm chí
ghi rõ *"a form that merely opened wrote 117 copies of one hall into the
store"*.

---

## 2. Nguyên nhân rò còn lại — chứng minh, không suy đoán

`TestBenchService.stage()` tìm lại map đã lưu bằng:

```python
for stored in self._maps.list():
    if stored.map_data == map_data:      # so cả tài liệu
        return stored
```

Vế phải là map **đọc từ đĩa**. Tôi viết một probe so từng trường:

```
--- equal?  False
  name: stored='api-test-map'   loaded='fadcd83e0ddf__v1'
```

**Đúng một trường lệch: `name`.** `load_environment_map` lấy tên theo
**stem của file ảnh** — docstring của nó nói thẳng: *"The map's `name`
defaults to the image file's stem"*. Bức tường, độ phân giải, gốc toạ độ
đều y hệt.

Nên phép so **không bao giờ đúng** ở lần dàn dựng đầu tiên ⇒ tạo một
dòng bóng mang tên stem. Lần dàn dựng thứ hai lại khớp chính dòng bóng
đó (cùng tên, cùng lưới), nên "dàn dựng hai lần ra một dòng" vẫn đúng —
và đó là lý do lỗi này sống lâu mà không ai thấy.

Dòng bóng ấy chính là thứ khiến `map_id` mà test bench trả về **không
phải** map An đang sửa trong editor.

### Một cái bẫy khi vá

Phản xạ đầu tiên là dùng `find_by_checksum`. **Không được** —
`MapData.checksum()` băm **cả `name`**:

```python
canonical = "|".join([self.name, str(self.width), ...])
```

Checksum là chữ ký của *tài liệu*, không phải của *bức tường*. Nó đúng
với việc nó làm (`adopt()` chống import trùng cùng tên) nhưng không trả
lời được câu hỏi ở đây. Tôi đã thử hướng đó, test đỏ, và đổi hướng —
ghi lại vì đây là chỗ dễ sai lần sau.

---

## 3. Cơ chế chặn

`_existing_map` giờ so **bức tường**, đúng như docstring của chính nó
vẫn luôn nói (*"Equality is on the grid itself"*) — code trước đó mâu
thuẫn với docstring của nó.

So các trường rẻ trước, `cells` sau, nên một kho vài trăm map loại gần
hết bằng ba số nguyên chứ không phải bằng danh sách vài nghìn ô.

**Không** thêm ràng buộc unique ở tầng DB. `POST /maps` **cố ý** cho
phép hai lần upload cùng một lưới dưới hai cái tên — docstring của
`MapService.adopt` phân biệt rõ: người dùng nộp map là chủ ý, còn máy
cần *một* id cho lưới có sẵn thì không. Ràng buộc cứng sẽ phá quyết định
đó. Luật đúng là: **mọi đường của máy đi qua khử trùng, đường của người
thì không** — và giờ cả ba đường máy (library `adopt`, derive, staging)
đều khử.

### Cổng có cắn

Không tin nó vì nó xanh. Bỏ bản sửa, chạy lại đúng test đó:

```
=== code cũ ===  E  assert '4665d5376662' == '4ee8a9ed49bf'     ← trả về dòng bóng
=== code mới === 2 passed
```

Lần viết test đầu tiên tôi viết sai — assert "dàn dựng hai lần ra một
dòng", và nó **xanh trên cả code cũ** vì lần hai vốn đã khớp dòng bóng.
Phải viết lại để bám vào **lần đầu**: đếm số dòng trước/sau *một* lần
dàn dựng, và `map_id` trả về phải là map người ta tìm thấy trong editor.
Ghi lại vì một test không cắn còn tệ hơn không có test.

Test mới:

| Test | Giữ điều gì |
|---|---|
| `test_a_map_off_disk_differs_from_its_row_by_name_alone` | ghim đúng sự thật khiến phép so cũ hỏng, và ghim rằng `checksum()` cũng lệch nên không dùng được |
| `test_staging_reuses_the_stored_map_instead_of_shadowing_it` | một lần dàn dựng **không** thêm dòng nào, và trỏ đúng map gốc |

---

## 4. Dọn

**Archive, không xoá.** Một map được tham chiếu bởi scenario, simulation,
benchmark, và bởi deployment qua đường dẫn. Đo trước khi làm: **cả 150
dòng thừa đều đang được tham chiếu**, nên xoá là thủng. `archived_at`
chỉ ảnh hưởng `list()`; `get()` vẫn trả bình thường — đúng cơ chế repo
này tự đặt ra (*"Deleting is now archiving"*).

`scripts/dedupe_maps.py`, **mặc định chạy khô**:

- Giữ dòng **cũ nhất** mỗi nhóm, vì `find_by_checksum` cũng trả cũ nhất
  — giữ bản mới sẽ khiến `adopt()` phát ra một id mà script vừa archive.
- **Không bao giờ** archive dòng có deployment ghim theo đường dẫn.
  Deployment không có cột `map_id`; nó nêu tên file, và bỏ sót chỗ này
  là cách archive mất nền đất dưới một comparison đã lưu.

Chạy thử trên **bản sao** trước, kiểm ba điều rồi mới đụng bản thật:

```
sau khi dọn: 43 live / 195 total rows   (không xoá dòng nào)
tham chiếu trỏ vào dòng không tồn tại: 17   ← có sẵn từ trước, không phải do dọn
deployment ghim: 9, trong đó bị archive: 2  ← cả 2 đã archive từ trước
```

Đối chiếu trên DB chưa đụng: **17 tham chiếu treo và 2 map bị archive
đều có sẵn**. Script không tạo thêm cái nào.

Sau đó: backup `planbench.db.bak-before-dedupe` (19.6 MB) rồi chạy thật.
**Archive 127 dòng** (không phải 150 — 23 dòng được deployment ghim nên
được tha).

Nghiệm thu trên API đang chạy:

```
GET /maps                       170 → 43
GET /maps/df765642c4d1          200   (dòng đã archive vẫn giải quyết được)
GET /maps/b92f3f964633          v3, checksum 4e38f71803   (map An sửa, nguyên vẹn)
```

Đảo ngược được: `UPDATE maps SET archived_at = NULL WHERE archived_at =
'2026-08-28 09:55:43';`

---

## 5. Hai thứ phát hiện thêm, chưa sửa

1. **17 tham chiếu treo** — `scenarios`/`simulations`/`benchmarks` trỏ
   vào `map_id` không còn dòng nào. Có sẵn từ trước, không do việc này.
   Cần quyết định riêng: xoá bản ghi mồ côi, hay để nguyên như dấu vết.
2. **1 deployment ghim một map không còn tồn tại** trong bảng maps. Nó
   sẽ đỏ ngay khi có ai bấm chạy. Chưa đụng vì sửa nó là đổi một
   deployment đã lưu.

---

## 6. File đã đụng

| File | Việc |
|---|---|
| `apps/api/planbench_api/decision_service.py` | `_existing_map` so bức tường thay vì so tài liệu |
| `tests/api/test_api_maps.py` | +2 test (tổng 27) |
| `scripts/dedupe_maps.py` | **mới** — archive dòng trùng, dry-run mặc định |
| `planbench.db` | **đã archive 127 dòng**; backup `planbench.db.bak-before-dedupe` |

Không đụng `MapData.checksum()`, không thêm ràng buộc unique, không xoá
dòng nào.

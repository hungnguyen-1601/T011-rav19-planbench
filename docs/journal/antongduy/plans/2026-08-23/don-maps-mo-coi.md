# Plan: dọn map mồ côi và gắn vòng đời map vào deployment

Ngày: 2026-08-23 · Nhánh `tongduyan_3` · **Trạng thái: ĐÃ CHỐT THIẾT KẾ**
(An trả lời ba câu hỏi thiết kế cùng ngày; phần xoá dữ liệu thật vẫn
chờ An xem số trước khi chạy).

Yêu cầu gốc: trang Bản đồ có quá nhiều map trùng; lọc bỏ map mồ côi, và
có hàm xoá map khi deployment bị xoá, trừ map được chủ động giữ.

---

## Hiện trạng đo được

Đo trên `planbench.db` ngày 2026-08-23:

| Con số | Giá trị |
|---|---|
| Map | 198 |
| Checksum khác nhau | 41 |
| Map mồ côi theo nghĩa chặt | **5** |
| Scenario | 208 |
| Scenario mồ côi | **176** |
| Map chỉ sống nhờ một scenario đã chết | **165** |

Ba điều đáng nói, vì chúng đổi cách hiểu bài toán:

**1. Trùng lặp không phải trùng id.** `id` là khoá chính nên không thể
trùng. 117 dòng tên `static-obstacles` dùng chung **một** checksum — cùng
nội dung, tải lại 117 lần. Nguồn rò là
[library.py:171](../../../../../apps/api/planbench_api/routers/library.py#L171):
`POST /scenario-library/{name}/import` gọi `maps.create()` mỗi lần, không
tra checksum, dù `ix_maps_checksum` đã có sẵn trong schema.

**2. Quét một tầng gần như vô dụng.** Chỉ 5/198 map không có ai trỏ tới.
193 map còn lại được scenario giữ sống — nhưng 176/208 scenario tự nó
cũng không được simulation hay benchmark nào trỏ tới. Phải quét bắc cầu
mới chạm được 165 map thật sự không ai với tới.

**3. Deployment không trỏ tới map.** `task_profiles` chỉ có
`environment / robot / missions / constraints / hardware`. Không có
`map_id`. "Xoá map khi xoá deployment" chưa có sợi dây nào để bám.

---

## Ba quyết định An đã chốt

| Câu hỏi | Chốt | Vì sao |
|---|---|---|
| Độ sâu quét | **Bắc cầu**: map + scenario chết | Quét một tầng chỉ dọn được 5/198 |
| Dây liên kết deployment | **Quét lại sau khi xoá**, không thêm cột provenance | Không migration, áp được cho dữ liệu cũ, và không xoá nhầm map deployment khác vẫn dùng |
| Giữ map | **Cột `kept` + nút ghim ở UI** | Đảo ngược được; suy từ nguồn gốc thì không |

Phương án gộp trùng theo checksum (viết lại `map_id` ở scenarios /
simulations / benchmarks về một map đại diện) **bị loại** — nó sửa dữ
liệu lịch sử, và một benchmark trỏ sang map khác với map nó thật sự
chạy là đúng thứ nền tảng này tồn tại để chống.

---

## T1 — Cột `kept`

`alembic/versions/0009_map_kept.py`, thêm `maps.kept` boolean, mặc định
`false`, NOT NULL.

Mặc định `false` chứ không `true`: 198 dòng hiện có nếu đánh dấu giữ hết
thì phép quét đầu tiên không xoá được gì, và cột trở thành trang trí.
Map nào An muốn giữ thì ghim — ghim là hành động chủ động, đúng như chữ
"chủ động lưu" trong yêu cầu.

`MapRow.kept`, `StoredMap.kept`, `MapSummary.kept` để trang Bản đồ đọc được.

## T2 — Phép quét

`apps/api/planbench_api/retention.py`, thuần và tách khỏi router để test
được không cần HTTP.

```
reachable_scenarios = scenario_id xuất hiện ở simulations ∪ benchmarks
reachable_maps      = map_id ở simulations ∪ benchmarks
                    ∪ map_id của mọi reachable_scenario
                    ∪ map_id của mọi map kept

sweep = {
  scenarios: mọi scenario ∉ reachable_scenarios,
  maps:      mọi map ∉ reachable_maps,
}
```

Ba ràng buộc viết thành mã, không để ngầm:

1. **Map `kept` không bao giờ nằm trong danh sách xoá**, kể cả khi không
   ai trỏ tới. Đó là toàn bộ ý nghĩa của cột.
2. **Scenario giữ map sống chỉ khi chính nó còn sống.** Đây là chỗ "bắc
   cầu" nằm, và là chỗ dễ viết sai nhất.
3. **Chạy khô là mặc định.** `sweep(dry_run=True)` trả về danh sách id +
   số đếm, không xoá gì. Xoá thật phải truyền cờ.

## T3 — Endpoint

- `POST /api/v1/maps/sweep?apply=false` — mặc định chạy khô, trả về
  `{maps: [...], scenarios: [...], counts}`.
- `POST /api/v1/maps/{map_id}/keep` và `DELETE /api/v1/maps/{map_id}/keep`
  — ghim và bỏ ghim.

Chạy khô là mặc định ở tầng HTTP nữa, không chỉ ở tầng hàm: một endpoint
xoá hàng trăm dòng khi gọi không tham số là endpoint sẽ bị gọi nhầm.

## T4 — Nối vào xoá deployment

[decisions.py:433](../../../../../apps/api/planbench_api/routers/decisions.py#L433)
`delete_task_profile` chạy quét **sau khi** xoá xong, và trả thêm số map
/ scenario đã dọn trong `ProfileDeleted`.

Giữ nguyên tinh thần sẵn có của endpoint đó: nó đã từ chối xoá deployment
có run cho tới khi caller truyền `delete_runs`, và nói rõ đã xoá những
gì. Phần map nối vào cùng chỗ, và cũng phải **nói ra** chứ không dọn im
lặng.

## T5 — UI trang Bản đồ

- Cột / badge **Đã ghim** cho map `kept`.
- Nút ghim / bỏ ghim mỗi hàng.
- Nút **Dọn map mồ côi**: gọi chạy khô trước, hiện hộp thoại nói đúng số
  sẽ xoá và tên vài map đầu, rồi mới cho bấm xoá thật.

Không có nút xoá-một-phát. Hai bước, bước thứ hai nêu hậu quả của chính
nó — cùng khuôn với hộp thoại xoá deployment đang có.

## T6 — Chặn rò từ đầu nguồn

`POST /scenario-library/{name}/import` tra checksum trước khi tạo: đã có
map cùng checksum thì dùng lại, không tạo dòng mới. Đây là chỗ sinh ra
117 bản `static-obstacles`, và dọn mà không chặn nguồn thì tháng sau
phải dọn lại.

## T7 — Chạy trên `planbench.db` của An

Chạy khô, **in số ra cho An xem**, chờ An đồng ý rồi mới xoá thật. Không
tự xoá dữ liệu trong DB của An dù đã có cờ.

---

## Thứ tự và nghiệm thu

| Lượt | Việc |
|---|---|
| 1 | T1 cột `kept` + T2 phép quét + test |
| 2 | T3 endpoint + T4 nối vào xoá deployment |
| 3 | T6 chặn rò ở import |
| 4 | T5 UI |
| 5 | T7 chạy khô, báo số, chờ An |

**Nghiệm thu**

- [ ] Map `kept` không bao giờ bị quét, kể cả khi không ai trỏ tới
- [ ] Scenario đã chết không giữ map sống
- [ ] Map được simulation hoặc benchmark trỏ tới trực tiếp không bị quét
- [ ] Chạy khô là mặc định ở cả tầng hàm và tầng HTTP
- [ ] Xoá deployment có nói ra đã dọn bao nhiêu map / scenario
- [ ] Import cùng một scenario thư viện hai lần chỉ ra một map
- [ ] UI hỏi lại kèm số trước khi xoá thật
- [ ] Không viết lại `map_id` của bất kỳ scenario / simulation / benchmark nào

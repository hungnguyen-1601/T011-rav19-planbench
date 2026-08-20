# H9B — provider của candidate đi vào chính danh tính của nó

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §13, khoản P0 thứ hai
**Trạng thái:** xong, 17 test mới xanh, 170 passed lát cắt identity + host, **chưa commit**.

---

## 1. Nửa còn thiếu của §7.1

§7.1 chia provider ba ngả. H4 làm **hai phần ba**: deployment-owned đổi
execution fingerprint, và candidate-owned được giữ **ngoài** fingerprint,
có test chứng minh. Nửa còn lại — candidate-owned phải đi **vào**
`candidate_id` — chưa bao giờ được nối.

**Và report H4 của tôi viết là "test khoá cả hai chiều".** Nó khoá một
chiều. Đây là lần thứ ba trong plan này tôi tuyên bố quá thứ mình đã
làm, nên ghi lại thành một dòng riêng chứ không giấu trong bản sửa.

Hậu quả im lặng: hai candidate chỉ khác nhau ở estimator chúng mang theo
sẽ **chung một id**, nên mọi trace, mọi ΔU và mọi card ghi dưới id đó mô
tả hai thứ khác nhau mà không có cách nào phân biệt.

## 2. Danh tính tĩnh, không lấy từ resolved graph

```text
CandidateProviderBinding:
  capability · provider_id · provider_version
  manifest_checksum · config_digest · schema_digest
```

**Không băm `(capability, tên class)`.** Hai bản build của một provider
dùng chung tên, nên băm tên sẽ để một estimator viết lại **giữ nguyên id
của chính những kết quả nó vừa làm mất hiệu lực**. Thứ được băm là thứ
thật sự ghim code và cấu hình: checksum của bundle, version khai, schema
payload, digest config.

**Suy được trước khi có deployment.** Mọi field đều đến từ plugin bundle,
không field nào đến từ provider graph đã resolve: `candidate_id` phải tồn
tại trước khi preflight có gì để resolve, và một candidate mà danh tính
phụ thuộc deployment sẽ có id khác nhau theo từng deployment — trong khi
id là thứ mọi kết quả được lưu dưới.

## 3. Điều kiện tiên quyết: id cũ không được dịch

`providers` **vắng mặt khỏi payload băm** khi rỗng, không phải
`"providers": []`. Thêm key vô điều kiện sẽ dịch **mọi** id đã lưu vì một
field không candidate nào đang dùng — mồ côi 300 episode mỗi candidate để
ghi lại một thứ không cái nào có.

Chứng bằng **bytes trong git**: `3b18dfbfa9e7` và `fddc6f9d4046` trong
fixture H0 (commit `7a7c195`, viết trước khi field này tồn tại) khớp đúng
giá trị tính hôm nay. Kèm một test riêng cho `providers=()` phải bằng
"không nhắc tới providers" — nếu không, bảo đảm trên chỉ đúng nhờ may.

## 4. Hai bẫy canonical hoá — cả hai đều đã trả giá một lần ở chỗ khác

**`capability` qua alias bridge của SDK.** Không có nó, candidate khai
`lidar_2d` và candidate khai `planbench://channel/lidar-2d@1` cho hai id
— H9B sẽ **âm thầm phá DoD 15** mà H1a vừa đạt và vừa có test.

**`config_digest` sort key trước khi băm** — đúng defect mà test H4 bắt
được ở `HostConditions.providers`, lần này ở đúng chỗ nó sẽ tốn một
candidate id. Cộng: config rỗng hoặc `None` digest thành `""`, không phải
digest của `{}`, để provider mặc định không phụ thuộc hash của dict rỗng.

## 5. Preflight: hai bên phải khớp nhau

Graph biết provider nào là candidate-owned; chỉ candidate mới nói được nó
đã khai. **Không bên nào tự kiểm được điều này**, nên
`resolve_compatibility` nhận `declared_candidate_providers` và từ chối
khi graph có candidate-owned provider mà danh tính không nêu tên:

```
candidate-owned providers missing from candidate_id: ['org.lab://channel/social-costmap@1']
```

## 6. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/test_candidate_provider_identity.py` (mới, 17 test) | **17 passed** |
| Lát cắt identity + host + trace safety | **170 passed, 1 skipped** |
| Legacy id vs bytes commit `7a7c195` | **khớp** cả hai stack |
| `ruff check` | sạch |

Regression theo đúng danh sách §13, cả năm chiều: `providers=()` giữ
nguyên mọi legacy id · đổi version/checksum/config/schema ⇒ đổi id ·
deployment-owned ⇒ id **không** đổi · cùng bindings khác thứ tự ⇒ cùng id
· candidate-owned chưa khai ⇒ preflight từ chối.

## 7. Sau H9A + H9B

Hệ gọi được là **an toàn để không tạo dữ liệu sai**: không còn đường ghi
đè bằng chứng, không còn đường chấm oracle như production, và không còn
hai candidate khác nhau dùng chung một id. Chưa feature-complete — H10,
H11, H12 vẫn còn — nhưng không còn khoản nào có thể tạo ra thứ không sửa
được sau.

## 8. Kế tiếp

Amendment protocol latency v2 (trước H10), rồi H10.

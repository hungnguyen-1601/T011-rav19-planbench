# Algorithm host — tám lỗi An gặp khi dùng thật, và cách sửa

**Ngày:** 2026-08-25 · **Nhánh:** `tongduyan_plugin-config-and-edit` (4 commit, đã push, **chưa merge**)
**Tiếp theo:** `reports/2026-08-24/tongduyan_import-thuat-toan-tren-ui-p0-p4.md` (P0–P4, đã merge vào `main`)

Ngày 24-08 dựng xong đường import và tuyên bố hoàn thành với 50 test xanh.
Ngày 25-08 An dùng nó và gặp **tám** lỗi. Không lỗi nào bị bộ test của tôi bắt.

Điểm chung, và là bài học chính của phiên: **test phủ đường *import*, không phủ
những đường plugin đi *sau khi* import.** Mỗi lỗi nằm đúng một tầng sau chỗ test
dừng lại.

| Commit | Nội dung |
|---|---|
| `0e0c088` | cấu hình có tên cho controller import |
| `6fa4343` | tab Sửa nhận cả thuật toán |
| `5c14202` | ba đường sau khi import + bộ test vòng đời |
| `af794c4` | định danh theo archive thay vì theo nhãn |

---

## 1. Tám lỗi, theo thứ tự An gặp

### L1 — Nút "Chạy" trên Sân thử bị khoá, dropdown Cấu hình rỗng

Plugin vào được danh sách controller (P3 chạy), nhưng Test Bench đòi đủ **ba**
thứ: global planner, local controller, **configuration**. Danh sách cấu hình lấy
từ `CONTROLLER_CONFIGS` — bảng viết cứng trong repo, chỉ có controller built-in.
Một controller import về **không thể** có mục trong đó mà không sửa repo — đúng
thứ việc import sinh ra để tránh.

**Sửa:** cấu hình cũng đến từ manifest. `_Entry` mang thêm `controller_configs`,
sinh một cấu hình tên `<plugin_id>_defaults`. Hai bảng tra
(`LOCAL_CONTROLLER_CONFIGS`, `CONTROLLER_OF_CONFIG`) từ dict dựng lúc import
module thành `Mapping` đọc sống cả hai nguồn — nên bốn module tiêu thụ không phải
sửa dòng nào.

**Chỗ sai gốc:** dict dựng lúc import module đúng với built-in và **vĩnh viễn
sai** với plugin, vì tập plugin đổi trong lúc process chạy.

### L2 — "Chưa có mô hình nào để sửa" trong khi thuật toán nằm ngay dưới

Tab Sửa chỉ đọc danh sách **model PPO**. An có 0 model và 1 thuật toán, nên câu
đó đúng về model nhưng đọc lên thành sai.

**Sửa:** picker chia hai nhóm, lưu định tuyến theo loại đang chọn. Chọn thuật
toán thì phần thay file không hiện, thay bằng câu nói rõ gói và manifest là định
danh. Empty state của trang chỉ hiện khi **cả hai** danh sách rỗng.

**Chỗ sai gốc:** tôi thêm tab thứ ba vào một trang mà hai tab kia nói về model,
không cho phần còn lại của trang biết giờ có hai loại.

### L3 — Candidate B chỉ có `dwa`, Candidate A có đủ

Hai nguyên nhân độc lập, chỉ một là lỗi:

- **Không phải lỗi:** registry lưu **cặp ghép**. Với `rrtstar` chỉ tồn tại ba
  cặp, hai trong ba không đưa ra được (`dwa_predictive` đã rút sau khi đo,
  `pure_pursuit` là reference D12). `rrtstar+ppo` chưa bao giờ được đăng ký.
- **Là lỗi:** `build_plugin_entry` hard-code `global_planner="astar"`. Manifest
  **không hề khai** plugin cần global planner nào — `requires_global_path: true`
  chỉ nói "tôi bám theo một đường ai đó đã lập".

**Sửa:** mỗi plugin sinh một stack cho **mỗi global planner đang dùng được**.
Nửa global mượn nguyên từ built-in, vì ghép controller import với RRT\* phải đo
đúng cái RRT\* mà mọi candidate khác đã chạy.

### L4 — `TypeError: unsupported operand type(s) for +: 'NoneType' and 'NoneType'`

Chạy Sân thử thì được, đưa lên Quyết định thì chết **bên trong plugin**.

`candidate_from_stack` lưu tham số bằng `model_dump(mode="json")` **không có
`exclude_unset`**, nên mọi field tuỳ chọn được ghi thành `null` vào candidate.
Khi chạy, params đã lưu được nạp lại — giờ các field **đã được set** thành
`None`. Bộ lọc `exclude_unset` ở factory nhìn trạng thái set, thấy "đã set", cho
qua.

**`exclude_unset` sống sót đúng một chặng rồi chết ở vòng lưu-đọc.**

**Sửa:** lọc theo **giá trị**. `config_schema` khai kiểu JSON — number, integer,
boolean, string — không kiểu nào có `null` là giá trị hợp lệ, nên `null` chỉ có
thể nghĩa là "không chỉ định", và default của chính plugin là câu trả lời đúng.

**Vì sao Sân thử không thấy:** nó dựng planner thẳng từ config rỗng, **không lưu
gì**. Quyết định thì lưu rồi đọc lại.

### L5 — Robot đứng yên ở điểm xuất phát, replan 285 lần

Controller đã host-backed bị **bọc thêm một lớp nữa**. Lớp bọc giấu mất channel
seam, nên `run_stack` không tìm thấy nó, không bind, và mọi tick thành safe stop
— vận tốc 0. Robot không đi, nên replan liên tục.

**Sửa:** thôi bọc kép một controller vốn đã host-backed.

### L6 — `TraceError: latency layers were supplied to a recorder that was not built to write them`

**Hệ quả trực tiếp của L5.** Trước khi sửa L5, mọi tick là safe stop của host
ngoài, **không sinh latency layer nào**. Sửa xong, plugin bắt đầu trả lệnh thật
kèm sáu layer §5.9 — mà recorder được dựng với `latency_layers=False`, và **chưa
từng có ai truyền `True`**.

**Sửa:** controller tự khai `emits_latency_layers` (chỉ lane subprocess đo
layer), `episode.py` hỏi nó khi dựng recorder. Built-in giữ nguyên schema cũ.

### L7 — `ArrowInvalid: Column 9 named shared_provider_ms expected length 420 but got 419`

Nằm ngay dưới L6. Bước **recovery** do vòng lặp tự lái, controller không quyết
định tick đó, nên hàng đó không có layer. Cột nền được append **trước**,
`_record_layers` ném lỗi, `__exit__` vẫn ghi file (cố ý — trace dở dang vẫn là
bằng chứng), và lỗi Arrow che mất lỗi gốc.

**Sửa:** cột khai non-nullable nên không để trống được; ghi 0 trần trụi là bịa ra
"controller trả lời trong 0 ms" rồi nhét vào mọi percentile. Đã có sẵn cột
`compute_measured_by` để nói **ai đo** — dùng đúng nó, giá trị `not-measured`.

### L8 — Muốn sửa code rồi upload đè thì phải tự mở `plugin.json`

Định danh khoá trên `(plugin_id, version-trong-manifest)`, nên đổi code mà quên
nâng số thì bị từ chối.

Soát lại thì **luật đó không khớp với chính hệ thống**: candidate identity đã bám
vào **checksum của archive**. Version manifest chỉ đang gánh mỗi ràng buộc unique
của tôi — tức bắt người dùng bảo trì một con số bằng tay, đúng cái repo đã cảnh
báo: *"một con số do người duy trì là một con số người sẽ quên, và lỗi thì im
lặng"*. Luật cũ **từ chối đúng trường hợp cần chấp nhận**.

**Sửa** (An chốt sau khi cân ba phương án):

- định danh → `(plugin_id, checksum)`
- `revision` do nền tảng đánh, đếm số lần upload của một plugin
- **thư mục cài đặt** khoá theo checksum — trước đây code mới **đè lên code cũ
  trên đĩa** ngay khi ai quên nâng số
- bản cũ **tự tắt** khi bản mới nạp xong; tắt chứ không xoá
- alembic `0011`, đã chạy trên DB của An (backup `planbench.db.bak-before-0011`)

Đo thật:

```
sửa code, KHÔNG đụng plugin.json  →  201, revision 2
upload y hệt byte                 →  422 "Nothing in it has changed"
bảng: [(rev 2, active), (rev 1, disabled)]
stack đang chạy = revision 2
```

---

## 2. Ba nghi ngờ hoá ra sai — không bịa thành lỗi

| Nghi | Sự thật |
|---|---|
| `validate_control_rate` mù với plugin | Lane **có** set `control_period` từ host (dòng 393-394). So sánh đúng |
| Worker subprocess bị rò tiến trình | Chạy 3 episode liên tiếp, số tiến trình con **không tăng** — worker tự thoát khi stdin đóng lúc GC |
| Episode kẹt 1/5 trong run `9212040d883f` | Chạy lại **đúng context đó** với code hiện tại: đạt, đi 10.82 m. Run của An bắt đầu **50 giây sau** commit sửa, tức tiến trình API còn giữ code cũ |

Điểm cuối tôi nói rõ với An là **suy luận, không kiểm chứng được** — tôi không
biết tiến trình của An lúc đó chạy commit nào. An sau đó xác nhận không tái diễn.

---

## 3. Bộ test vòng đời — thứ đáng lẽ phải có từ đầu

Tám lỗi đều do An dùng mới lộ. Nên việc đúng không phải "cẩn thận hơn" mà là dựng
một bộ kiểm dắt **một plugin hoàn toàn khác** đi hết mọi đường.

`tests/api/test_api_plugin_lifecycle.py` — 25 test. Fixture
`org.newlab.wall-follower` **cố ý khác** những gì đã test:

- `config_schema` khai bốn tham số có kiểu ⇒ mọi field hoá `null` khi lưu
- **constructor tự kiểm đối số**, ném lỗi nếu nhận `None` ở chỗ khai là số

Điểm thứ hai mới quan trọng: một constructor dễ dãi sẽ **nuốt** đúng L4, và bộ
test sẽ xanh trong khi nền tảng vẫn hỏng.

Phủ: import → conformance → catalogue theo mọi global planner → picker cấu hình →
tab Sửa → đổi tên không đụng định danh → đường trực tiếp → **đường có lưu-đọc** →
chạy episode qua HTTP → ghi trace → cổng control-rate → tắt thì rút khỏi mọi nơi
→ upload đè thành revision mới → member không import được.

### Chứng minh bộ test có răng

Gỡ từng bản sửa ra rồi chạy lại. Cả sáu đều bị bắt:

| Gỡ gì | Kết quả |
|---|---|
| Bộ lọc `None` → quay lại `exclude_unset` | đỏ |
| Ghép cặp → chỉ `astar` | đỏ |
| Cấu hình → bỏ nguồn external | đỏ (2 test) |
| Cờ `latency_layers` ở `episode.py` | đỏ |
| Nhãn `not-measured` | đỏ |
| Định danh → quay về version manifest | đỏ |
| Tự tắt bản cũ | đỏ |
| Thư mục cài đặt → quay về version | đỏ |

---

## 4. Ba test của chính tôi hoá ra rỗng

Đáng ghi riêng, vì cùng một họ lỗi lặp lại ba lần trong một phiên.

**(a)** Test đầu cho vòng lưu-đọc dùng bundle probe, mà manifest bundle đó khai
`properties: {}` — **không có tham số nào để sinh ra `null`**. Pass trong khi
không kiểm gì. Sửa: khai tham số thật, và **assert cái bẫy còn đó** trước khi
assert bộ lọc dọn được nó.

**(b)** Test nhãn `not-measured` chỉ kiểm **tập giá trị**, nên khi thay nhãn
thành `"host"` nó vẫn xanh — đọc nhãn mà không kiểm nhãn đó nói đúng hay sai. Sửa
sang kiểm tính chất: hàng nào tổng mọi layer bằng 0 thì **bắt buộc** là
`not-measured`.

**(c)** `test_the_same_plugin_version_cannot_be_imported_twice` vẫn xanh sau khi
đổi luật định danh — nhưng **vì lý do khác với tên nó**: nó upload cùng file nên
cùng checksum. Đổi tên thành `test_the_same_archive_cannot_be_imported_twice`.

Và một test cũ phải sửa vì nó **là lý do không sửa được lỗi**:
`test_the_bundle_is_unpacked_where_the_lane_can_import_it` khẳng định đường dẫn
cứng `…/0.1.0/`. Giữ nguyên thì không đổi được cách khoá thư mục. Đổi sang kiểm
tính chất: giải nén **đúng một bản** dưới thư mục của plugin.

Một lần khác: `pytest` với tên file sai (`tests/test_selection.py` không tồn tại)
trả **exit 0 và "no tests ran"**. Suýt commit một bản sửa chưa được kiểm gì.

---

## 5. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `test_api_plugin_lifecycle.py` (mới) | 25 passed |
| `test_api_plugin_import.py` · `_conformance` · `_catalogue` | xanh |
| 6 suite hợp nhất trước commit cuối | 156 passed, 1 skipped |
| 7 suite sau bản sửa tham số | 289 passed, 1 skipped |
| `test_candidate_identity` · `test_candidate` · `test_candidate_bridge` | xanh — **id built-in không đổi** |
| `ruff` | sạch (3 lỗi còn lại thuộc `map_files.py`, commit của người khác) |
| `tsc --noEmit` (web) | không lỗi mới |
| `vitest` `lib/plugins.test.ts` | 8 passed |

Full suite **chưa chạy** — theo lệ, chỉ chạy phần vừa sửa.

---

## 6. Bundle VFH+ — hiện vật để thử, không phải kết quả

Hai thư mục **untracked, cố ý không commit** (An sẽ chuyển đi):

- `vfh_plus_import/` — bản `0.1.0`, viết **chỉ từ contract**. Mọi hằng số hoặc là
  của thuật toán hoặc suy từ `RobotConfig`. Không quyết định nào biện minh bằng
  "scenario X trượt". Đo **đúng một lần** trên tập `dev`: **7/7**. Tập holdout
  **không chạy**, nên nó còn sạch cho lần so sau này.
- `vfh_plus_iterated/` — bản `0.2.0`, **đã nắn theo bộ scenario** và **đã nhìn
  holdout**. Giữ làm minh hoạ vòng lặp sửa-rồi-import-lại. README mở đầu bằng
  cảnh báo **không được đưa vào so sánh với DWA**.

Thuật toán viết từ mô tả đã công bố của VFH+, **chưa đối chiếu paper**. Điều đó
động tới **cái nhãn**, không động tới **con số**: "controller này đạt X" luôn
đúng; "VFH+ đạt X" cần code thật sự là VFH+.

---

## 7. Việc chưa làm

- **Chưa merge** vào `main`. Không có conflict — `main` là tổ tiên trực tiếp,
  merge sẽ là fast-forward, 4 commit / 22 file.
- **Chưa deploy.** Quy trình có sẵn: push tag `desktop-v*` → CI dựng installer,
  qua smoke gate, tạo GitHub Release. Version lấy từ
  `apps/desktop/planbench_desktop/VERSION`, hiện `0.1.7`.
- **"Hồ sơ robot" trên form import vẫn gây hiểu nhầm.** Tra toàn bộ code: nó chỉ
  được đọc ở một nơi — dựng request giả cho bộ conformance. Khi chạy thật,
  episode dùng robot của **deployment**. Chọn profile nào không ảnh hưởng kết quả
  benchmark. Cần đổi nhãn, chưa làm.
- **Thông điệp lỗi trùng bundle** ném nguyên văn tiếng Anh của server, chưa nói
  người dùng phải làm gì tiếp.
- **P5 và P6** của plan 24-08 vẫn chưa làm.

## 8. Ghi chú

Migration `0011` **đã chạy trên `planbench.db` của An**. Lùi được bằng
`planbench.db.bak-before-0011` hoặc `alembic downgrade 0010`.

Trong DB hiện tại, `vfh_v2` (revision 2) đang **disabled** và `vfh_plus`
(revision 1) đang bật — trạng thái An đặt trước đó, tôi không tự đổi.

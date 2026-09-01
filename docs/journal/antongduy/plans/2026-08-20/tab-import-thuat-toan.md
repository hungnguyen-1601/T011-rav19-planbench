# Tab import thuật toán — kế hoạch

**Ngày:** 2026-08-20 · **Nhánh:** `tongduyan_3` · **Trạng thái: chờ An duyệt, chưa làm gì**

An chốt hai điều trước khi lập plan:

- **Nguồn import: chỉ `plugin.json`.** Dán/upload manifest, server validate theo schema
  đã lập trình. Không đưa code lạ lên máy chủ.
- **Phạm vi: đăng ký xong dùng ngay làm candidate**, chạy được benchmark.

Hai lựa chọn đó ghép lại tạo ra **một ràng buộc phải nói trước** — xem mục 3.

---

## 1. Phần đã có sẵn (nhiều hơn tôi tưởng)

Đợt algorithm host đã dựng gần đủ những gì tab này cần. Không viết lại cái nào.

| Thứ cần | Đã có ở đâu |
|---|---|
| Parse manifest từ **dict**, áp mọi refusal của H1a | `parse_manifest(data, source=)` — `packages/plugin_sdk/.../manifest.py` |
| Checksum manifest (định danh) | `manifest_checksum(data)` |
| Kiểm khai báo mà **không chạy code** | `check_declarations(manifest, granted)` → `ConformanceReport` |
| "Plugin này chạy được ở host này không" | `resolve_compatibility()` → `CompatibilityReport` |
| Trạng thái đăng ký | `RegistrationState`: `registered_and_runnable`, `registered_but_missing_provider`, `registered_but_missing_runtime`, `registered_but_incompatible` |
| Cách ly manifest hỏng, kèm lý do | `PluginRegistry` / `QuarantinedPlugin` |
| Chính sách công bằng, evidence class | `host/fairness_policy.py` |
| Đường thực thi | `TrustedPythonRuntime`, `SubprocessRuntime` |

**`parse_manifest` nhận thẳng dict** — nó được tách khỏi `load_manifest` chính là để
"discovery có thể parse thứ nó tìm được bằng đường khác". Import bằng JSON dán vào rơi
đúng vào chỗ đó. Không cần chạm filesystem.

`CompatibilityReport` gần như **chính là nội dung của tab**: missing capabilities,
missing providers, missing runtime, incompatible action types/dynamics/execution models,
fairness refusals, undeclared providers, adapter chain, evidence class. Tab là **một khung
nhìn lên hàm đó**, không phải một tầng logic mới.

---

## 2. Phần còn thiếu

- **Không có đường ghi nào ở API.** `/algorithms` chỉ có `GET` list và `GET {id}`,
  đọc từ `list_algorithms()`.
- **Không có chỗ lưu manifest đã import.**
- **Không có cầu nối** từ manifest đã đăng ký sang danh sách candidate mà trang
  Decisions chọn.
- **Toàn bộ UI.**

---

## 3. Ràng buộc phải nói trước: manifest-only + chạy được = code phải cài sẵn

Manifest **khai** runtime và entry point; nó không **chứa** code. Discovery cố ý không
bao giờ import code plugin (§5.1 — thuộc tính chịu lực), entry point chỉ được đọc dạng
chuỗi.

Nên: import một manifest cho code **chưa cài trên máy chạy sweep** sẽ cho ra một plugin
**đăng ký được nhưng không chạy được**. Đó không phải lỗi — `RegistrationState` đã có sẵn
đúng bốn trạng thái cho việc này. Nhưng **UI bắt buộc phải nói rõ đang ở trạng thái nào**,
nếu không người dùng import xong, thấy nó xuất hiện trong danh sách candidate, chọn nó,
rồi sweep chết sau ba mươi giây.

Đề xuất: candidate picker **chỉ cho chọn** plugin ở trạng thái `registered_and_runnable`;
ba trạng thái còn lại vẫn hiện trong tab, xám, kèm đúng lý do host trả về.

---

## 4. Vật cản kiến trúc lớn nhất

`ALGORITHMS` trong `packages/benchmark/planbench_benchmark/registry.py` là một **dict
hằng, khai cứng trong module**, và mỗi `_Entry` mang theo **factory** (`config_model`,
`factory`, `global_factory`) — tức hàm Python dựng planner.

Plugin import về **không có factory**. Nó có manifest khai runtime + entry point, và
*host* mới là thứ phân giải chúng lúc load.

Nên **không thể** nhét một `_Entry` vào `ALGORITHMS` rồi coi như xong. Ba lối:

| Lối | Ý | Rủi ro |
|---|---|---|
| **A. `_Entry` uỷ quyền cho host** | factory của entry gọi `AlgorithmHost` để dựng plugin | Ít đụng chạm nhất tới `ALGORITHMS`; nhưng nhét một đường thực thi thứ hai vào sau một API vốn hứa trả về planner thuần |
| **B. Catalogue thành hợp của hai nguồn** | `algorithms_catalogue()` trả built-in + plugin đã đăng ký; đường chạy phân nhánh theo nguồn | Trung thực về việc có hai loại; nhưng mọi nơi đang giả định một registry phải sửa |
| **C. Built-in cũng thành plugin** | dùng `LegacyGlobalPlugin`/`LegacyLocalPlugin` (đã có) để bọc built-in, host là đường duy nhất | Đúng nhất về kiến trúc, **một nguồn sự thật**; nhưng là refactor lớn, đụng mọi thứ đang chạy |

**Tôi đề xuất B cho lần này, và ghi C là hướng đi đúng về sau.** Lý do: B nói thật rằng
hiện có hai loại thay vì giả vờ chúng giống nhau (A), và không bắt cả nền tảng đang chạy
ổn phải chuyển đường trong cùng một lượt (C). Nhưng đây là điểm An nên cân, vì nó quyết
định bao nhiêu nợ để lại.

---

## 5. Các đợt

| Đợt | Nội dung | Ước lượng |
|---|---|---|
| **I1** | **API validate, chưa lưu.** `POST /algorithms/imports/validate` nhận dict manifest → `parse_manifest` + `check_declarations` + `resolve_compatibility`. Trả `CompatibilityReport` + checksum. Lỗi schema trả 422 kèm **đường dẫn field**, không phải một chuỗi. Chưa ghi gì. | 0.5 ngày |
| **I2** | **Lưu đăng ký.** Bảng plugin đã import: manifest, checksum, ai import, lúc nào, trạng thái lúc import. `POST /algorithms/imports`, `GET`, `DELETE`. Trạng thái **tính lại lúc đọc**, không tin cái đã lưu — host đổi thì câu trả lời phải đổi theo. | 1 ngày |
| **I3** | **Tab UI.** Route mới trong mục **Materials** cạnh Maps/Library/Candidates. Dán JSON hoặc thả file → xem báo cáo → xác nhận. Danh sách plugin đã import kèm trạng thái và lý do. Phần quyết định tách sang `lib/` để test được (repo không có jsdom). | 1–1.5 ngày |
| **I4** | **Nối vào candidate.** Theo lối đã chốt ở mục 4. Chỉ `registered_and_runnable` mới chọn được. Fairness policy và evidence class đi kèm plugin vào report. | 1.5–2 ngày |
| **I5** | **Xác minh trên plugin thật.** Một plugin mẫu cài sẵn, import manifest, chạy sweep ngắn, kiểm identity/evidence class trong report. Không có đợt này thì cả bốn đợt trên chỉ được chứng minh bằng fixture. | 0.5 ngày |

Tổng ~4.5–5.5 ngày.

**I1 + I3 đã tự nó dùng được**: import và xem plugin có chạy được ở host này không, mà
chưa đụng đường chạy. Nếu An muốn thấy sớm thì dừng ở đó rồi đánh giá.

---

## 6. Những chỗ tôi sẽ từ chối làm tắt

- **Không tự suy ra requirement từ id plugin.** Plan host nói rõ: core không đoán
  requirement của plugin. Manifest khai gì thì đọc đúng thế.
- **Không import code plugin để lấy metadata.** Kể cả khi tiện. Discovery không import
  là thuộc tính chịu lực, không phải chi tiết hiện thực.
- **Không lưu trạng thái `runnable` rồi tin nó.** Host cài thêm provider thì một plugin
  hôm qua không chạy được hôm nay chạy được, và ngược lại.
- **Không cho chọn plugin chưa runnable làm candidate** chỉ vì nó đã nằm trong danh sách.
- **Không tự chế thông điệp lỗi.** `CompatibilityReport` đã có các trường lý do; UI
  render chúng, không diễn giải lại thành câu dễ nghe hơn.

---

## 7. Câu hỏi còn mở cho An

1. **Lối A/B/C ở mục 4** — tôi đề xuất B. An chốt hay để tôi tự quyết?
2. **Ai được import?** Có cần đăng nhập không, và có cần vai trò riêng không? Hiện
   `/algorithms` không yêu cầu gì.
3. **Xoá một plugin đã import** thì các run cũ đã dùng nó xử lý ra sao — giữ nguyên
   report (đề xuất), hay chặn xoá?
4. **Dừng ở I3 để xem trước**, hay chạy thẳng tới I4?

---

## 8. Ghi chú

Chưa viết một dòng code nào cho việc này. Mục 1 và 2 là kết quả đọc mã hiện có, không
phải mô tả thứ sẽ xây.

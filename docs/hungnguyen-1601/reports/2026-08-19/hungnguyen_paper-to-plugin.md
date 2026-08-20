# Paper-to-Plugin — thực thi câu của mentor bằng code

**Ngày:** 2026-08-19 · **Commit:** `7c4c48a`
**Nguồn yêu cầu:** *"Output của LLM là phải như thế này thì hệ thống mới nhận."*

---

## 1. Bài toán

Bộ trích xuất paper (`paper.py`) ánh xạ bài báo lên một stack nền tảng
**đã có**, và từ chối khi không có — đúng, vì thay bằng "thứ gần giống
nhất" là trả lời một câu hỏi khác dưới uy tín của bài báo.

Nhưng từ chối xong thì đi đâu? Đường vào cho thuật toán mới là
**Algorithm Host của An**, và host nhận đúng một hình dạng:
`plugin.json` + code export đúng `entry_point`
(`docs/antongduy/.../cau-truc-plugin-algorithm-host.md`).

## 2. Đóng khung model hai lớp

**Lớp 1 — schema đầu ra** ghim mọi enum manifest công bố: `role`,
runtime lane, capability URI, action type. `additionalProperties: false`
ở mọi tầng — một trường thừa là dấu hiệu đầu tiên của model tự chế
phương ngữ manifest riêng.

**Lớp 2 — bộ kiểm định tất định** (`validate_manifest`) chạy lại từng
luật tài liệu nêu:

- `production_lane ∈ supported_lanes` (§5.1, luật tài liệu nêu nguyên văn)
- mọi lane khai phải có profile, mỗi profile có `entry_point` dạng
  `package:Class`
- URI lạ **không kèm** `capability_schemas` → manifest sai, **kèm gợi ý
  gần đúng** (§5.2 luật 2: typo phải chết ở parse time, không được hiện
  ra thành "thiếu provider")
- plugin `global` phải có `global-path@1`; `local`/`monolithic` đi qua
  `continuous-velocity@1`
- `monolithic` phải khai `requires_global_path: false`

**Sai hình dạng → trả về bị từ chối kèm lỗi được gọi tên, không bao giờ
tự sửa.** Tự sửa là dạy model rằng đầu ra hỏng vẫn dùng được.

## 3. Fixture neo

Ví dụ `plugin.json` **nguyên văn trong tài liệu của An** là fixture neo:
nó mà trượt validator thì validator đã lệch khỏi tài liệu nó thực thi.

```
test_plugin_author.py::TestTheDocumentedExampleIsTheAnchor
```

## 4. Chạy thật với Gemini, cả hai chiều

**Chiều nhận** — paper Theta* (thuật toán nền tảng chưa có):

```
accepted     : True
id           : org.paper.thetastar
role         : global
entry_point  : thetastar:ThetaStarPlanner
requirements : planning-grid@1, robot-state@1
tham số      : heuristic_weight=1.2 (lấy từ chính paper), connectivity=8
files        : plugin.json · planner.py · __init__.py
```

Code sinh ra có `heapq`, logic parent-của-parent đúng Theta*, và ghi chú
trung thực: *"line-of-sight (Bresenham) hiện là placeholder"*.

**Chiều từ chối** — danh sách mua sắm:

```
accepted: False
refused : "The provided text is a shopping list, not a robotics paper
           describing a planning or control algorithm."
```

## 5. Một lỗi lộ khi chạy thật

Gemini trả `400 INVALID_ARGUMENT` với schema có `"default": {}` (schema
rỗng). Khai kiểu tường minh như `paper.py` đã làm thì qua.

## 6. Ranh giới với SDK của An

Khi parser SDK thật (`packages/plugin_sdk`) hợp nhất, **parser của SDK
thay `validate_manifest` làm trọng tài**; schema và phần sinh code giữ
nguyên. Drift giữa hai bên sẽ đọc ra thành diff chuỗi lỗi, không phải
thay đổi hành vi âm thầm.

**Không lưu, không import, không chạy** code sinh ra — nó là điểm khởi
đầu có người duyệt.

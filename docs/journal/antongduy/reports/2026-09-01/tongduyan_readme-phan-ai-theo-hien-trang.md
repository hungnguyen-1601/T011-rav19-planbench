# README phần AI: viết lại theo cái code thật đang làm được

Ngày 2026-09-01 · nhánh `tongduyan_docs-restructure`

An nói phần AI trong README "chưa làm được chuẩn so với những gì đã thể
hiện". Rà lại thì lệch **hai chiều**, không phải một: có chỗ hứa quá, và
có chỗ **giấu mất** thứ đã làm xong.

---

## Lệch chiều nào

| README nói | Code thật | Loại lệch |
|---|---|---|
| "Hai thứ khác nhau, đừng nhầm" - trợ lý và lớp cố vấn | **bốn mặt** hiện ra cho người dùng: thêm analyst theo episode và panel *Từ paper* | thiếu |
| "11 tool chỉ-đọc" | `tools.py` đăng ký **12** | sai số |
| không chỗ nào nói analyst mặc định tắt | `episode_analyst_mode = "off"`, và `production` **bị từ chối vô điều kiện trong build này** | hứa quá |
| §9.2 "import thuật toán qua giao diện: chưa có đường vào, không có UI" | `routers/plugins.py` có **12 endpoint** (nhận bundle, validate, publish, unpublish, hold, disable, sổ sự kiện) + trang **Thuật toán** | sai từ 24-08 |
| §5.5 chỉ hướng dẫn đặt biến môi trường | bản desktop **đã đóng gói `openai` 3.3.1**; `anthropic` vẫn tuỳ chọn và **chưa có ô key trên UI** | thiếu |
| §9 nhảy 9.3 → 9.6 | thiếu 9.4, 9.5 | lỗi đánh số |

Chỗ hứa quá nặng nhất là analyst. Nó là mặt AI **duy nhất đã được chấm
mù** (90 lượt, 0.56), nên README dễ đọc thành "phần vì sao đã chạy". Thực
tế người dùng thường **chưa đọc được một chữ nào analyst viết**: chế độ
`production` bị chặn trong chính code, `internal_preview` chỉ cho quản
trị viên và đòi khai `report_ref`, còn `shadow` thì ghi ra artifact chứ
không trả về. Cái panel đó đang hiện là verdict tất định và tầng
model-free - hai thứ chạy không cần model.

## Đã sửa gì

**§3.7 Lớp AI** - viết lại. Mở đầu bằng câu đúng bản chất: AI ở đây là
một tầng phủ lên tầng luật, 76 luật cố vấn + 15 luật phản biện chạy được
một mình, rút key ra thì mất phần văn chứ không mất lời khuyên. Rồi bảng
**bốn mặt, mỗi mặt một cột trạng thái**. Cuối mục tách rõ hai thứ hay bị
gộp: bốn luật của lớp cố vấn **đã chứng minh là bắt được lỗi thật** (tiêm
lỗi vào, đòi test đỏ) - còn **chất lượng câu chữ model viết thì chưa
chứng minh gì**, vì toàn bộ test chạy trên provider script sẵn.

**§4.8 Dùng AI** - bốn mục thay vì hai, và mỗi mục nói thẳng dùng được
ngay hay chưa. Thêm mục *Từ paper* (kèm câu "không lưu paper", "code sinh
ra có TODO thật, chưa chạy được") và mục analyst với đủ bốn chế độ, quota
20 lượt / 400k token mỗi người mỗi ngày.

**§9.1** - thêm lý do cái khoá tồn tại: mở `production` ra là để một model
nói về cơ chế ở mức 0.56 với người đang định ký một quyết định.

**§9.2** - viết lại theo `routers/plugins.py`. Hai chỗ hở còn lại là hở
thật: manifest khai entry point chứ không chứa code (nên vẫn cần người
đặt file lên máy chủ), và cổng xuất bản mặc định tắt.

**§9.5** - thêm hai mục: bản nháp từ paper chưa ai đo chất lượng (mới chạy
tay một lần, Gemini 18-08), và trang Cài đặt chỉ có một ô key.

**§5.5** - nói rõ installer đã mang sẵn SDK nào và thiếu đường vào nào.

**`docs/reference/AI_CAPABILITIES.md`** - sửa 11 → 12 tool.

**`docs/03-gaps.md`** - xoá mục "§9 thiếu 9.4/9.5" (đã sửa), thêm bảng
4.1b ghi bảy nợ vừa trả.

## Kiểm chứng

Không đổi dòng code nào - nhưng README giờ khẳng định vài điều, nên chạy
đúng những test đứng sau chúng:

| Khẳng định | Kiểm bằng | Kết quả |
|---|---|---|
| 12 tool chỉ-đọc | đếm `name=` trong `tools.py` | 12 |
| không route AI nào có động từ ghi | `test_api_agent.py::TestTheAgentCannotAct` | 3 pass |
| advisory route không đổi trạng thái | `test_api_advice.py::TestNoRouteHereActs` | 3 pass |
| analyst tắt mặc định, `production` bị từ chối | `config.py:203`, `episode_analysis.py:154` | đọc trực tiếp |
| plugin import đã có endpoint | `routers/plugins.py`, 12 `@router` | đọc trực tiếp |
| mọi link tương đối trong 3 file vừa sửa | script đối chiếu đường dẫn | 0 hỏng |

Không chạy full suite.

## Còn lại

- **`KNOWN_LIMITATIONS.md` (110 KB) vẫn chưa rà từng mục** - README §9.5
  trỏ vào nó như danh sách đầy đủ. Nếu nó cũng cũ như §9.2 vừa rồi thì
  câu "danh sách đầy đủ" đang bảo lãnh cho thứ chưa ai kiểm.
- **Ba mặt AI chưa có phép đo nào.** Muốn README nói mạnh hơn "khung
  đúng" thì phải có bộ golden cho lớp cố vấn và cho bản nháp từ paper -
  chưa có kế hoạch nào cho hai cái đó.

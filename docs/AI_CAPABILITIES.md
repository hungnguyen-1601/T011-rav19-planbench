# Tầng AI của PlanBench — làm được gì, không làm được gì, kiểm ở đâu

Một trang, một nguyên tắc: **AI đề xuất, con người quyết định.** Mỗi
khẳng định dưới đây trỏ tới test chứng minh nó — không có khẳng định nào
phải tin suông.

## AI can thiệp vào đâu trong vòng đời một quyết định

| # | Bước | AI làm gì | Endpoint | Test |
|---|---|---|---|---|
| 1 | Khai deployment | — (con người khai) | — | — |
| 2 | Đăng ký phương án | Đọc paper → bản nháp phương án, mỗi tham số kèm câu nguồn | `POST /candidates/from-paper[/upload]` | `test_agent_paper.py`, `test_api_paper.py` |
| 2b | Thuật toán **mới** | Đọc paper → **plugin bundle** cho Algorithm Host, validator quyết nhận/từ chối | `POST /plugins/from-paper[/upload]` | `test_plugin_author.py`, `test_api_plugin.py` |
| 3 | Trước khi chạy phép so | 12 luật kiểm cấu hình, chặn lỗi trước khi tốn mô phỏng | `POST /decisions/preflight` | `test_preflight.py`, `test_api_advice.py` |
| 4 | Cổng G1–G6 | — (luật tất định của nền tảng, **cố ý không LLM**) | — | — |
| 5a | Cổng trượt | 10 luật giải nghĩa + việc cần làm + việc bị cấm; LLM xếp hạng/bổ sung khi bật | `GET /decisions/{id}/advice[?use_model=true]` | `test_gate_advice.py`, `test_advisor.py` |
| 5b | Episode trượt | 11 luật đọc trace Parquet: khoảng an toàn sập, dao động, kẹt | `GET /decisions/{id}/traces/{cid}/{eid}/review` | `test_trace_review.py` |
| 5b' | **Vì sao thắng/thua** | 7 luật ghép số liệu với ưu-nhược điểm thuật toán (bảng trait có neo vào registry); LLM kể chuyện khi bật | `GET /decisions/{id}/outcome[?use_model=true]` + tool chat `get_outcome` | `test_outcome.py`, `test_api_advice.py` |
| 5c | Phản biện trước khi ký | 15 luật + LLM tối đa 3 phản biện | `GET /decisions/{id}/critique[?use_model=true]` | `test_self_check.py`, `test_agent_critique.py` |
| 5d | Đối chiếu với paper | 6 luật: tham số nào paper nêu/khác/mặc-định-âm-thầm | `POST /candidates/{id}/reproduction` | `test_reproduction.py`, `test_api_advice.py` |
| 5e | Trước khi viết báo cáo | 18 luật rào chắn: câu nào bằng chứng không cho phép viết | `GET /decisions/{id}/report-advice` | `test_report_advice.py` |
| 6 | Ký duyệt | — (con người, HĐ-14) | — | — |
| * | Hỏi đáp mọi lúc | 9 công cụ chỉ đọc trên database | `POST /agent/chat` | `test_api_agent.py` |

Tổng: **64 luật cố vấn + 15 luật phản biện**, chung một kiểu `Advice`
(`packages/decision/planbench_decision/advice.py`).

## Paper-to-Plugin — luật của mentor

> *"Output của LLM là phải như thế này thì hệ thống mới nhận."*

Algorithm Host (tài liệu `tongduyan_cau-truc-plugin-algorithm-host.md`)
nhận đúng một hình dạng: `plugin.json` manifest + code export đúng
`entry_point`. Nên model bị đóng khung hai lần:

1. **Schema đầu ra** ghim mọi enum manifest công bố — role, runtime
   lane, action type, capability URI.
2. **Bộ kiểm định tất định** (`plugin_author.validate_manifest`) chạy
   lại từng luật tài liệu nêu: `production_lane ∈ supported_lanes`,
   `entry_point` dạng `package:Class`, URI lạ không kèm schema → từ chối
   kèm gợi ý gần đúng, plugin `global` phải có `global-path@1`…

Bản nháp sai hình dạng trả về **bị từ chối kèm lỗi được gọi tên** —
không bao giờ tự sửa. Ví dụ nguyên văn trong tài liệu của An là fixture
neo: nó mà trượt validator thì validator đã lệch khỏi tài liệu
(`test_plugin_author.py::TestTheDocumentedExampleIsTheAnchor`).

Khi SDK thật của An (`packages/plugin_sdk`) hợp nhất vào nhánh này,
parser của SDK thay `validate_manifest` làm trọng tài; schema và phần
sinh code giữ nguyên.

Đã kiểm chạy thật (Gemini, 2026-08-18): paper Theta* → bundle
`accepted=true`, đúng role `global`, tham số lấy từ chính paper
(`heuristic_weight=1.2`, `connectivity=8`); danh sách mua sắm → từ chối
kèm lý do. Không lưu, không import, không chạy code sinh ra.

## Bốn ràng buộc mọi tầng AI ở đây cùng chịu

1. **Mọi khẳng định trỏ vào một trường có thật.** `field_path` được
   kiểm bằng `exists()`; model trỏ sai → bị loại và **đếm công khai**
   (`fabricated` hiện trên màn hình).
2. **Luật là sàn, model không xoá được.** LLM chỉ xếp hạng và bổ sung
   (`advisor.py`, `critique.py`); quên một mã thì mã đó vẫn còn, bịa mã
   thì bị bỏ qua (`test_advisor.py::TestTheFloorAlwaysSurvives`).
3. **AI không hành động.** 10 hành vi cấm công bố tại
   `GET /agent/capabilities`; không route AI nào có động từ ghi — test
   đọc thẳng `openapi.json`
   (`test_api_agent.py::TestTheAgentCannotAct`,
   `test_api_advice.py::TestNoRouteHereActs`).
4. **Hỏng thì nói hỏng.** Provider chết → trả nguyên phần luật kèm
   `refused` nêu lý do; mock không sinh được bundle → `refused`, không
   bịa (`test_api_plugin.py::TestTheVerdictIsHonest`).

## Không làm được — nói trước để khỏi bị hỏi

- Không chạy phép so, không duyệt/bác, không tuyên bố an toàn, không
  điều khiển robot, không sửa deployment.
- Không lưu paper: đối chiếu lại sau này cần chính file đó lần nữa.
- Trace không mang tư thế đích → "robot có tiến về đích không" là câu
  **không trả lời được** từ trace; các giới hạn cùng loại ghi trong
  docstring `trace_review.py`.
- Code plugin sinh ra là **điểm khởi đầu có người duyệt**: TODO được
  đánh dấu thật, chưa chạy được cho đến khi người viết hoàn thiện.

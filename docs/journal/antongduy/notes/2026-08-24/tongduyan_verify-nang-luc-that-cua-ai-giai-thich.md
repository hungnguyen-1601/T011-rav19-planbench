# Verify khả năng thật của tầng AI "vì sao thuật toán này thắng"

**Ngày:** 2026-08-24 · **Loại:** đánh giá hiện trạng — **không đổi một dòng code nào**
**Nhánh khảo sát:** `tongduyan_verify-ai-analyst` (tách từ `main` tại `cadf1ec`)
**Công cụ dùng:** skill `bites` (`bitekit.py`) — tiêm lỗi có chủ đích vào bản sao tạm,
đòi cổng trả đúng exit code **và** đúng thông điệp. Bộ răng lưu kèm:
`tongduyan_ai-explain-bites.yaml`.
**Đối chiếu thiết kế:** `notes/2026-08-18/tongduyan_giai-phap-giai-thich-vi-sao-thuat-toan-thang.md` (v2) ·
`plans/2026-08-19/ai-analyst-subsystem.md` (bản 7) ·
`notes/2026-08-19/tongduyan_ra-soat-e5-e6a-cho-plan-analyst.md`

---

## 1. Kết luận một câu

Cái đang có trong `main` là **bộ khung giữ cho AI không nói láo**, đã kiểm được và
kiểm khá tốt (12/14 răng cắn). Cái **chưa có** là chính con AI đi tìm nguyên nhân:
`services/analyst_service/` không tồn tại, và **không một phép đo nào về năng lực
phân tích của model từng được chạy** — 12/12 packet golden đều thiếu file.

Nói cách khác: kỳ vọng "AI giải thích tại sao A tốt hơn B" **chưa được thoả**, và
hiện tại **cũng chưa đo được là chưa thoả tới đâu**.

## 2. Trong repo có **hai** thứ đều bị gọi là "AI", đừng nhầm

| | Lane 1 — Advisor | Lane 2 — Analyst "vì sao" |
|---|---|---|
| Code | `services/agent_service/planbench_agent/advisor.py` (243 dòng) | **KHÔNG TỒN TẠI** |
| Việc nó làm | sắp lại thứ tự advice luật đã sinh + thêm **tối đa 3** ý, mỗi ý phải trỏ vào một field có thật | sinh giả thuyết cơ chế, gọi checker, nộp claim |
| Nối vào đâu | `GET /decisions/{id}/advice`, `/outcome`, `/recommendation` — **chỉ khi `?use_model=true`** | không nối vào đâu cả |
| UI | nút "hỏi model" trên trang `/decisions/[id]` | không có |
| Trạng thái | **đang chạy thật** | mới có contract phía platform (E0–E6) |

**Lane 1 không phải là thứ đề bài §"vì sao" mô tả.** Nó không sinh giả thuyết cơ
chế, không gọi checker, không đi qua promotion matrix, không mang `claim_level`.
Nó là một lớp xếp hạng + chú thích trên advice luật.

**Lane 2 mới là "AI giải thích vì sao A thắng B"**, và nó đang ở đúng chỗ note
2026-08-19 đã ghi: platform xây xong contract (`packages/explanation/`, 14.742
dòng, 37 module), phía AI chưa viết. `grep` toàn repo: `analyst_visible`,
`why_not_visible`, `reference_analyst` **chỉ xuất hiện trong test** — không một
đường code production nào hỏi tới cổng đó.

Endpoint `GET /decisions/{run_id}/explanation` **có thật và đang chạy**, nhưng nó
trả panel **tất định** dựng từ case packet (waterfall ΔU, exemplar, detector) —
đúng như E4 thiết kế. Không có model nào trong đường đó.

## 3. Bằng chứng: 14 răng tiêm vào các cổng của tầng giải thích

Đối chứng dương sạch: 193 test xanh trong 0,41 s
(`test_explanation_contracts`, `test_explanation_promotion`, `test_explanation_e5`,
`test_explanation_gate`, `test_advisor`).

| Răng | Tiêm gì | Kết quả |
|---|---|---|
| `PHRASE_WHITELIST_OFF` | whitelist động từ trả rỗng | ✓ CẮN |
| `CAUSAL_CEILING_OFF` | bỏ cấm từ nhân quả dưới `intervention_supported` | ✓ CẮN |
| `WEAKEST_TAKES_MAX` | trần bằng chứng hợp thành bằng `max` thay vì `min` | ✓ CẮN |
| `INFERENCE_ONLY_ASSERTABLE` | cho phép claim `universal_algorithm_superiority` | ✓ CẮN |
| `PROVENANCE_MISSING_ACCEPTED` | input `missing` im lặng đỡ được một claim | ✓ CẮN |
| `VISIBILITY_ALWAYS_ON` | analyst chưa chấm vẫn hiện trên Decision Card | ✓ CẮN |
| `GOLDEN_DECLARED_READY` | bộ golden dở tự khai là chính thức | ✓ CẮN |
| `GATE_SUITE_MISMATCH_IGNORED` | decision khai một suite khác suite đã chạy | **✗ TRƯỢT** |
| `ADVISOR_DROPS_RULE_ADVICE` | model bỏ bớt advice luật khi sắp thứ tự | ✓ CẮN |
| `ADVISOR_FABRICATION_UNCHECKED` | không kiểm citation, ý bịa được xuất bản | ✓ CẮN |
| `ADVISOR_NO_DEGRADE_ON_FAILURE` | provider chết kéo luôn tầng luật xuống | ✓ CẮN |
| `ADVISOR_ADDITION_CAP_OFF` | nới trần 3 ý lên 50 | **✗ TRƯỢT** |
| `META_EXIT_CODE_PROPAGATES` | META: chứng minh exit code của cổng có truyền ra | ✓ CẮN |
| `NEG_BENIGN_EDIT` | đối chứng: sửa comment **không được** làm đỏ | ✓ đúng (xanh) |

**12 cắn / 2 trượt.** Các luật lõi của thang bằng chứng (§2 note thiết kế) và ba
điều răn của advisor đều **có răng thật**, không phải cổng trang trí.

## 4. Hai lỗ hổng cổng — chỗ test đang xanh mà không bảo vệ gì

### 4.1. `GateRun` không có test cho suite mismatch

`gate.py:118` từ chối một `GateDecision` khai `hidden_suite_version` khác suite đã
chạy. Vô hiệu hoá dòng đó → **toàn bộ 193 test vẫn xanh**.

`grep hidden_suite_version tests/` chỉ ra hai chỗ, cả hai đều assert **giá trị
đúng** (`== "hidden-1.0.0"`), không chỗ nào assert rằng giá trị **sai** bị chặn.

Hệ quả: điểm gate của một suite có thể bị gắn cho một suite khác mà không gì kêu.
Đúng loại lỗi cổng này sinh ra để chặn.

### 4.2. Test trần `MAX_MODEL_ADVICE` là test tự quy chiếu

```python
def test_the_additions_are_capped_by_the_schema(self) -> None:
    assert advisor_schema()["properties"]["additions"]["maxItems"] == MAX_MODEL_ADVICE
```

`advisor_schema()` đọc chính `MAX_MODEL_ADVICE`. Đổi hằng số từ 3 lên 50 thì **cả
hai vế cùng đổi** và test không bao giờ đỏ được. Trần "model chỉ được thêm 3 ý" —
thứ giữ cho tầng luật không bị dìm — **không có cổng nào canh**.

## 5. Ba blocker

### B1 · Không đo được năng lực AI: 12/12 packet golden không tồn tại

```
suite_version: calibration-0.1.0   OFFICIAL_GOLDEN_READY: False
cases=12   packets_missing=12      families: 6
```

Mọi `packet_ref` trỏ tới `fixtures/golden/visible/<case>/packet.json`; **thư mục
`fixtures/` không có trong repo**. `score_suite` / `run_gate` không chạy được trên
dữ liệu thật, kể cả với `reference_analyst` (floor model-free của platform).

`scripts/plant_golden_runs.py --dry-run`:

```
3 of 6 families can be staged as a single episode today.
  skipped  expansion_latency      (cần sweep nhiều context, không phải 1 episode)
  skipped  insufficient_evidence  (cần packet builder khai gap — E4.1, chưa chốt)
  skipped  negative_control       (cần cặp candidate có ΔU vắt qua 0)
```

Nghĩa là ngay cả khi chạy script, cũng chỉ dựng được **3/6 họ**, và macro average
trên 3 họ không so được với ngưỡng đặt cho 6 họ.

Ngưỡng đã preregister (`CALIBRATION_TARGETS`) — hiện **chưa một lần nào được chấm**:
precision 0,90 · recall@3 0,70 · abstention 0,90 · component-attribution 0,85 ·
checker-selection 0,90 · structural violations 0.

### B2 · Không có phép đo nào chạm vào model thật

Toàn bộ test của Lane 1 dùng `MockProvider` script sẵn (`tests/test_advisor.py:47`).
Chúng chứng minh **cái khung** đúng: model bỏ code thì code được giữ lại, citation
hỏng thì bị đếm vào `fabricated`, provider chết thì rơi về tầng luật. Không có
test nào — và không có `eval/` nào (`eval/` chỉ có một `results/report.md`) — nói
được model **viết có đúng không**, ranking **có hợp lý không**, `fabricated` thực
tế **là bao nhiêu phần trăm** trên dữ liệu thật.

Đây đúng chỗ §9 note thiết kế đòi: *"Template render là baseline vĩnh viễn — LLM
không thắng rõ thì khỏi ship phần phrasing."* Phép so đó chưa từng chạy.

### B3 · Trên Windows, 78 test của tầng advice không chạy được

```
6 failed, 596 passed, 72 errors in 186.64s
```

Toàn bộ 78 ca đỏ/lỗi có **một nguyên nhân duy nhất**: `path.read_text()` gọi
không có `encoding="utf-8"`, Python rơi về cp1252 và chết ở byte `0x8f`
(`tests/test_gate_advice.py:45`, `tests/test_report_advice.py:56`).

```
UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f in position 1774
```

Đây **không phải** lỗi của tầng AI — nhưng nó có nghĩa là **tầng luật tất định mà
advisor đứng lên trên đang không được kiểm trên máy An**. Cổng nền không chạy thì
răng của Lane 1 chỉ chứng minh được nửa trên.

Không đổi code lần này theo yêu cầu; sửa là một dòng mỗi chỗ.

## 6. Đối chiếu với kỳ vọng của note thiết kế

| Kỳ vọng (note 2026-08-18 v2) | Hiện trạng |
|---|---|
| LLM không bao giờ là nguồn của một con số | **Đạt về cấu trúc** — `HypothesisProposal` không có field số; răng `ADVISOR_FABRICATION_UNCHECKED` cắn |
| Thang 4 mức bằng chứng, không có mức thứ năm | **Đạt**, có răng canh (`WEAKEST_TAKES_MAX`, `PROVENANCE_MISSING_ACCEPTED`) |
| Whitelist động từ chặn nhân quả bịa | **Đạt**, hai răng cắn |
| Agent không tự đóng dấu (3 object tách quyền) | **Đạt về schema** — nhưng chưa có agent nào để mà tước quyền |
| Menu check đóng, 16 tool card, 4 checker thật | **Đạt** — `ToolHost` + `checkers.py` + `replay.py` chạy được |
| Nghiệm thu agent bằng golden trồng đáp án trước khi lên card | **CHƯA** — B1 |
| Template là baseline vĩnh viễn, LLM phải thắng mới ship | **CHƯA đo** — B2 |
| Agent analyst sinh giả thuyết cơ chế | **CHƯA CÓ CODE** |

## 7. Đề xuất bước tiếp (chưa làm, chờ An chốt)

Theo thứ tự phụ thuộc, không phải theo độ dễ:

1. **Vá B3** (một dòng × 2 file) — để tầng luật nền có kiểm chứng trên máy An.
2. **Vá hai lỗ hổng §4** — thêm test suite-mismatch cho `GateRun`; thay test trần
   tự quy chiếu bằng test chạy `advise_with_model` với 4 addition và đòi kết quả
   còn 3. Sau đó chạy lại bộ răng, đòi hai răng đó chuyển sang CẮN.
3. **Gỡ B1** — E4.1 (endpoint dựng packet) + dựng 3 họ stage được, khai rõ macro
   đang trên 3/6 họ. Chưa đủ 6 họ thì **không** bật `OFFICIAL_GOLDEN_READY`.
4. **Chỉ sau đó** mới bắt đầu AI1–AI5. Viết analyst trước khi có golden là viết
   một thứ không ai chấm được.

Riêng câu hỏi "AI hiện tại làm đúng kỳ vọng chưa": với Lane 1, **cái khung đúng,
chất lượng nội dung chưa ai đo**; với Lane 2, **chưa tồn tại**.

---

## Phụ lục — chạy lại bộ răng

```bash
python "$HOME/.claude/skills/bites/tools/bitekit.py" \
  docs/antongduy/notes/2026-08-24/tongduyan_ai-explain-bites.yaml
```

Bộ răng copy repo sang bản tạm cho từng răng, không chạm bản gốc. Cờ `--only <id>`
chạy một răng, `--keep` giữ bản tạm để soi.

# Plan 1 · T5 — câu cảnh báo host hard-code tiếng Việt trên trang EN

**Ngày:** 2026-08-21 · **Nhánh:** `tongduyan_3` · **Trạng thái:** xong T5, **chưa commit**

Nguồn: [01-bug-fix-token-i18n-a11y.md](../../plans/2026-08-21/01-bug-fix-token-i18n-a11y.md) — task T5.
Tiếp sau [T1](tongduyan_plan01-t1-token-hint-mark.md), [T2](tongduyan_plan01-t2-font-mono.md),
[T3](tongduyan_plan01-t3-focus-ring-hint-mark.md), [T4](tongduyan_plan01-t4-hint-keyboard-touch.md).
T2b, T6, T7 chưa chạm.

---

## Lỗi thật sự là gì

`hostinfo.unpinned_warning()` ghép một câu **tiếng Việt**, `HostWarning` trên trang
decision detail render **nguyên văn**, và comment ở đó nói rõ đó là chủ ý: *"a client
that reworded it could water it down"*.

Chủ ý đúng, đối tượng sai. Thứ không được diễn giải lại là **con số**, không phải
**ngôn ngữ**. Khoá cứng cả hai thì trang EN hiện một đoạn tiếng Việt — tức là để bảo
vệ cảnh báo khỏi bị pha loãng, ta làm nó không đọc được với đúng nhóm người cần đọc.

## Tầng sở hữu — mô tả lại cho đúng trước khi sửa

Plan cảnh báo rằng sửa "trong `hostinfo.py`" là sửa nhầm tầng, vì object
`measurement_environment` được dựng ở **hai nhánh** của `selection.py`. Rà lại thì có
**ba** nơi, không phải hai:

| Nơi dựng | Vị trí |
|---|---|
| Report thường | `selection.py:818` |
| Report interrupted trước episode đầu | `selection.py:1176` |
| **`scripts/measure.py:232`** | plan chưa nêu |

Ba nơi cùng chép tay một dict là đúng cái hình dạng sinh ra lỗi mà plan lo: thêm khoá
cho UI ở nhánh đang nhìn, hai nhánh kia im lặng thiếu. Nên tôi không thêm khoá vào ba
chỗ, mà **rút thành một hàm** và để ba chỗ gọi:

```python
def measurement_environment(host: BenchmarkHost) -> dict[str, object]:
    info = unpinned_warning_info(host)
    return {
        "benchmark_host": host.model_dump(),
        "warning": unpinned_warning(host),      # giữ nguyên, export + client cũ đọc
        "warning_code": info["code"] if info else None,
        "warning_params": info["params"] if info else None,
    }
```

Nhờ vậy `_interrupted_before_any_episode` bỏ được tham số `warning` thừa, và
`host: object` + `# type: ignore[attr-defined]` thành `host: BenchmarkHost` đúng kiểu.

## Đã sửa

### 1. `hostinfo.py` — phân loại vẫn thuộc platform

Thêm `unpinned_warning_info(host)` trả `{"code": "unpinned_host", "params": {...}}`.
Tên `reference_unpinned_ms` / `reference_pinned_ms` giữ đúng ý plan: hai số này là
**phép đo tham chiếu lịch sử** của một stack trên một máy, **không phải** latency của
run đang xem. Tên `unpinned_ms` trần sẽ mời người đọc hiểu nhầm đúng chiều đó.

Hai số tách thành hằng `REFERENCE_UNPINNED_MS` / `REFERENCE_PINNED_MS`, và câu văn
cũ **derive** từ chúng qua `_vi_number()` (`59.30` → `"59,30"`). Trước đó câu văn chép
tay chữ số của riêng nó — hai bản sao của một con số là hai con số, và bản structured
sẽ lặng lẽ lệch khỏi câu văn ngay lần đầu ai đó sửa một bên.

### 2. Payload — chỉ thêm khoá, không xoá

`warning` giữ nguyên vị trí đầu và vẫn là string. Bỏ nó là phá file xuất của **mọi**
run cũ (`decision_export.py:116` đọc đúng khoá này).

### 3. `decisions.ts` — kiểu có tên, và một hàm thuần

Type `measurement_environment` inline được đặt tên thành `MeasurementEnvironment` với
hai field optional, params mô tả **cụ thể** chứ không `Record<string, unknown>`.

Quyết định "dịch hay in nguyên văn" tách thành `hostWarningView(environment, locale)`
— hàm thuần, không React. Lý do giống T4: repo **không có jsdom**
(`vitest.config.ts` nói thẳng), nên một nhánh nằm trong thân component chỉ đọc được
chứ không chạy được. Tách ra thì cả bốn ca của plan test được thật.

Điều kiện dịch **chặt cả hai vế** đúng như plan yêu cầu:

```
warning_code === "unpinned_host"
  AND cores / reference_unpinned_ms / reference_pinned_ms đều là number
    → dịch
ELSE → in nguyên văn `warning`
```

### 4. Định dạng số theo locale

`translate()` (`shared.ts:44`) nội suy bằng `String(vars[name])`, nên `59.3` ra
`"59.3"` — mất chữ số thập phân mà câu văn luôn có, và mất luôn dấu phân cách của
tiếng Việt. Frontend format **trước** khi gọi `t()` bằng `Intl.NumberFormat(locale)`:
EN `59.30`, VI `59,30`.

### 5. Khoá i18n

`decisions.env.unpinned` vào cả hai locale. Bản VI **chép nguyên văn** từ
`hostinfo.py`, và tôi kiểm bằng máy chứ không bằng mắt: so sánh chuỗi trong `vi.json`
với câu platform dựng ra → **bằng nhau từng ký tự**.

### 6. `HostWarning` — còn 8 dòng

Component giờ chỉ chọn giữa `t(view.key, view.vars)` và `view.text`. Không có nhánh
nào trong đó tự đặt câu.

## Kiểm chứng

**Python**

- `tests/test_hostinfo.py` — thêm 7 test: `unpinned_warning_info` im lặng khi đã ghim
  và khi manifest cũ không ghi nhận; mang đúng code + params khi không ghim; **câu văn
  và hằng số không lệch nhau được**; block có đủ 4 khoá ở cả hai trạng thái. **19/19 xanh.**
- `tests/test_partial_runs.py` — thêm 3 test cho đúng thứ plan đòi: **cả hai nhánh**
  report mang đủ 4 khoá, và nhánh interrupted mô tả đúng host nó nhận.
  **9/9 xanh** (110 s — fixture chạy simulation thật).
- `tests/api/test_decision_markdown.py` + `test_decision_xlsx.py` → **38/38 xanh**:
  **file xuất không đổi**.
- `tests/test_measure.py` → **43/43 xanh** (nhánh thứ ba).
- `ruff check` + `ruff format --check` → sạch.

**Web**

- `decisions.test.ts` — **28/28**, gồm đủ **bốn ca** plan liệt kê: structured+EN
  (`59.30`), structured+VI (`59,30`), run cũ chỉ có `warning`, và code lạ / params
  thiếu → fallback nguyên văn. Thêm ca thứ năm: run đã ghim → không hiện gì.
- `npx tsc --noEmit` → **exit 0**.
- 4 suite web liên quan → **185/185 xanh**.

### Một lỗ hổng tôi tìm ra khi rà, và đã bịt

Guard locale-coverage của trang (`decisions-page.test.tsx:807`) quét `t("…")` **trong
file component**. Khoá mới lại được chọn trong `lib/decisions.ts`, nên guard đó
**không nhìn thấy nó** — xoá `decisions.env.unpinned` khỏi `vi.json` thì không test
nào đỏ, và trang sẽ in tên khoá ra cho người đọc.

Thêm hai test bịt lại: khoá mà hàm trả về phải tồn tại ở **cả hai** locale, và câu
sau khi nội suy không còn `{` `}` nào sót, đồng thời chứa đủ ba con số.

### Đột biến — ba lần phá, ba lần đỏ

| Đột biến | Kết quả |
|---|---|
| Truyền số thô thay vì `Intl.NumberFormat` | 2 test đỏ (EN và VI) |
| Chỉ kiểm `warning_code`, bỏ kiểm params | *falls back rather than mistranslating* đỏ |
| Xoá khoá khỏi `vi.json` | 2 test đỏ |

**Một ghi chú về chính quy trình này:** lần chạy đột biến thứ hai **thoạt tiên báo
xanh**, và tôi suýt ghi vào đây rằng test yếu. Nguyên nhân là script đột biến của tôi
dùng `\n` để khớp một file **CRLF** nên phép thay thế không áp dụng — test chưa từng
được thử. Chạy lại cho đúng thì nó đỏ. Đột biến không áp dụng được mà im lặng thì cho
ra đúng cái tín hiệu "test vô dụng", nên tôi đã cho in số lần khớp trước khi ghi file.

## Giới hạn — phần chưa kiểm được bằng máy

- **Chưa mở trình duyệt.** Ô nghiệm thu "bật EN → banner tiếng Anh, bật VI → đúng câu
  hiện tại" được kiểm ở tầng hàm thuần và tầng dictionary, **không** phải bằng cách
  nhìn trang thật. Không có jsdom thì không render được `HostWarning`.
- **Chưa có run thật nào mang `warning_code`.** Mọi artifact đang nằm trên đĩa đều là
  run cũ, nên trên máy anh lúc này trang sẽ đi **nhánh fallback** — vẫn hiện câu tiếng
  Việt. Muốn thấy bản EN thì phải chạy một sweep mới trên máy không ghim, hoặc sửa tay
  `comparison_report.json` của một run để thêm hai khoá.
- Đó cũng là lý do tôi **không** dám đánh dấu ô *"Host warning ở locale EN không còn
  tiếng Việt"* là xong. Đường đi đã có và đã test; việc nó hiện đúng trên trang cần
  một run mang khoá mới.

## Ngoài phạm vi chữ của plan

1. Nhánh thứ ba `scripts/measure.py` (plan nêu hai).
2. Gộp ba chỗ dựng dict thành một hàm, thay vì thêm khoá vào từng chỗ.
3. Hai test bịt lỗ locale-coverage nói ở trên.

Cả ba đều phục vụ đúng mục tiêu T5. Nếu anh muốn giữ nguyên phạm vi chữ, mục 1 revert
riêng được.

## Việc trên đĩa không phải của tôi

`docs/antongduy/plans/2026-08-21/02-redesign-decision-detail.md` (+444 dòng) và
`03-design-system-va-sidebar.md` (+36) đang được sửa song song. Tôi **không chạm và
không stage** hai file đó.

## Chưa làm

T2b (`--fg` trên `.latency-playhead`), T6 (test token), T7 (khuyến nghị phải nêu
config). T4 cũng **chưa commit**.

**Chưa commit** — anh tự commit.

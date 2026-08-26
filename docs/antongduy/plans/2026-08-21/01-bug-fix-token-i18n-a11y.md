# Plan 1 — Bug fix: token không tồn tại, chuỗi hard-code, focus ring

Ngày lập: 2026-08-21 · Trạng thái: **chờ An duyệt**
Nguồn: [tongduyan_danh-gia-ui-trang-decision-detail.md](../../notes/2026-08-21/tongduyan_danh-gia-ui-trang-decision-detail.md) — QA #1, #3, #6, và mục checklist focus.

## Mục tiêu

Sửa **defect thuần**. Mỗi mục dưới đây là code đang không làm điều nó tự nói là
làm — không mục nào là quyết định thẩm mỹ. Plan này ship được độc lập, không
chờ hai plan kia, và không đổi bố cục trang nào.

## Ngoài phạm vi

- Mọi thay đổi bố cục, spacing, cỡ chữ, bảng màu → Plan 3.
- Mọi thay đổi cấu trúc trang decision detail → Plan 2.
- `main.content { max-width }` → Plan 3. Nó là quyết định layout toàn app, không phải bug.

## Phụ thuộc

Không có. **Đây là plan chạy trước hai plan kia.**

---

## Task

### T1 — `--text-muted` không tồn tại

`apps/web/src/app/globals.css:1135`

```css
.hint-mark { color: var(--text-muted); }   /* token này chưa từng được định nghĩa */
```

`grep -c -- '--text-muted:' globals.css` → `0`. Không fallback ⇒ `color` là
`inherit`. Trong `.comparison-label` nó thành `var(--text)` (#14181f) và
`.hint-mark` tự đặt `font-weight: 700`, nên mỗi dấu `?` là một glyph đen đậm.

**Sửa**: `color: var(--muted);` và hạ `font-weight: 700` → `600` — nhãn cạnh nó
là 650, giữ 700 thì dấu `?` vẫn đậm hơn thứ nó chú thích.

**Nghiệm thu**: dấu `?` trong bảng so sánh và trên form deployment đều xám,
không đậm hơn nhãn cạnh nó.

---

### T2 — `--font-mono` không tồn tại

Dùng ở `globals.css:1865` và `globals.css:3111` dạng `var(--font-mono, monospace)`.
Không có định nghĩa ⇒ luôn rơi vào fallback `monospace` = Courier New trên Windows.
Trong khi `globals.css:3446` (`.comparison-value`) hard-code một stack khác hẳn.

**Sửa**:
1. Thêm vào `:root` (block chung, không nằm trong `[data-theme]` — font không đổi theo theme):
   ```css
   --font-mono: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
   ```
   Dùng stack **hiện có** của `.comparison-value`. Không thêm webfont ở plan này —
   JetBrains Mono thuộc Plan 3.
2. `globals.css:3446` — bỏ stack hard-code, dùng `var(--font-mono)`.
3. Hai chỗ `var(--font-mono, monospace)` — bỏ fallback thừa.

**Nghiệm thu**: `condition-noise-tags` và block ở dòng 3111 render cùng một font
với cột giá trị bảng so sánh.

---

### T2b — `--fg` không tồn tại (cùng loại lỗi, phát hiện khi rà cho T6)

`globals.css:3360`

```css
.latency-playhead { stroke: var(--fg, #111827); stroke-width: 1; opacity: 0.45; }
```

`--fg` chưa từng được khai ⇒ luôn rơi vào fallback `#111827`. Trên dark theme
(`--canvas-bg: #0b0d11`) một vạch `#111827` opacity .45 gần như tàng hình —
playhead của latency chart không nhìn thấy được. Đây là bug giao diện thật,
không chỉ là token bẩn.

**Sửa**: `stroke: var(--text);` — token đã đổi đúng theo theme.

**Nghiệm thu**: playhead nhìn thấy được ở cả light lẫn dark khi tua latency chart
trên trang decision detail.

---

### T3 — Focus ring của `.hint-mark` bị tắt

`globals.css:1145-1149`

```css
.hint-mark:hover,
.hint-mark:focus-visible { color: var(--text); border-color: var(--accent); outline: none; }
```

Gộp `:hover` với `:focus-visible` rồi `outline: none` ⇒ người dùng bàn phím chỉ
nhận được một viền 1px đổi màu trên vòng tròn 15px. Trang này đã có rule
`.decision-page :is(button,select,input,a,summary):focus-visible { outline: 2px … }`
(`globals.css:2143`) nhưng `.hint-mark` là `<span>` nên không khớp selector.

**Sửa**: tách hai state. `:focus-visible` dùng
`outline: 2px solid var(--accent); outline-offset: 2px;`

**Nghiệm thu**: Tab tới dấu `?` → thấy ring 2px. Hover bằng chuột → không có ring.

---

### T4 — `Hint`: hoàn thiện ARIA button pattern trên `<span>` — KHÔNG đổi thẻ

`apps/web/src/components/Hint.tsx:60-79`

Hiện `role="button"` + `tabIndex={0}` nhưng `onKeyDown` chỉ bắt `Escape` —
Enter/Space không làm gì.

**Vì sao KHÔNG đổi sang `<button>` thật**: `Hint` render **bên trong `<label>`**
chứa input/select ở ít nhất hai nơi — `DeploymentForm.tsx:1074` (checkbox) và
`TrafficEditor.tsx:153` (input number). `<label>` chứa hai phần tử labelable
(input + button) là HTML không hợp lệ: click dấu `?` có thể kích hoạt luôn
control của label, và screen reader xác định sai control mà label sở hữu. Đổi
thẻ đúng chuẩn đòi refactor mọi call site để `Hint` ra ngoài `<label>` — không
còn là bug fix hẹp, không thuộc Plan 1.

**Sửa — giữ `<span role="button" tabIndex={0}>`, bù đủ pattern**:

```tsx
onKeyDown={(event) => {
  if (event.key === "Escape") { setAt(null); return; }
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();               // Space: không cuộn trang
    if (at) { setAt(null); return; }
    const box = event.currentTarget.getBoundingClientRect();
    setAt({ x: box.right, y: box.bottom });
  }
}}
onClick={(event) => {
  event.preventDefault();                 // trong <label>: không kích hoạt input của label
  if (at === null) {                      // touch: không có hover, tap phải mở
    const box = event.currentTarget.getBoundingClientRect();
    setAt({ x: box.right, y: box.bottom });
  }
  // đang mở (chuột hover): no-op — toggle ở đây sẽ đánh nhau với onMouseMove
}}
```

- Enter/Space toggle. Space có `preventDefault()`.
- `onClick` mở khi `at === null` — đây là đường của **touch** (tap không có
  hover). Khi bubble đang mở do hover thì click là no-op, tránh đóng-mở giật.
- `onClick` luôn `preventDefault()` để không kích hoạt label cha.
- Escape đóng, giữ nguyên.
- Focus ring lấy từ T3.
- Không đổi CSS — thẻ không đổi nên không cần reset gì.

**Nghiệm thu**: Enter và Space toggle bubble; Space không cuộn trang. Tap trên
touch mở bubble. Click dấu `?` trong form deployment **không** toggle checkbox
của label. Escape đóng. Mark không đổi hình (trừ màu từ T1).

---

### T5 — Câu cảnh báo host hard-code tiếng Việt

`packages/benchmark/planbench_benchmark/hostinfo.py:185-187` ghép một câu tiếng
Việt. `apps/web/src/app/decisions/[id]/page.tsx:325` (`HostWarning`) render nguyên
văn, có chủ ý — comment nói rõ *"a client that reworded it could water it down"*.

Chủ ý đúng nhưng thực thi sai chỗ: thứ không được diễn giải lại là **số**, không
phải **ngôn ngữ**. Kết quả là trang EN hiện một đoạn tiếng Việt.

**Tầng sở hữu — mô tả cho đúng trước khi sửa**: `hostinfo.unpinned_warning()`
chỉ trả `str | None`. Object `measurement_environment` được dựng ở **hai nhánh**
trong `selection.py` — report bình thường (`:818`) và report interrupted
(`:1176`). Sửa "trong hostinfo.py" là sửa nhầm tầng.

**Sửa — không phá vỡ hợp đồng API**:

1. `hostinfo.py` **tiếp tục sở hữu việc phân loại**: thêm hàm trả structured
   bên cạnh hàm cũ, ví dụ `unpinned_warning_info(host) -> dict | None`:
   ```python
   {
       "code": "unpinned_host",
       "params": {
           "cores": host.logical_cores,
           "reference_unpinned_ms": 59.30,
           "reference_pinned_ms": 16.10,
       },
   }
   ```
   Tên tham số là `reference_*` có chủ ý: hai số này là **phép đo tham chiếu
   lịch sử** hard-code trong câu văn, không phải latency của run đang xem —
   tên `unpinned_ms` trần sẽ khiến client hiểu nhầm là số của chính run này.
   `unpinned_warning()` cũ giữ nguyên (hoặc derive từ hàm mới) — chuỗi vẫn cần
   cho export và client cũ.
2. `selection.py` — **cả hai nhánh** (`:818` và `:1176`) ghi ba khoá:
   ```python
   "measurement_environment": {
       "benchmark_host": host.model_dump(),
       "warning": warning,                    # giữ, export + client cũ đọc
       "warning_code": info["code"] if info else None,
       "warning_params": info["params"] if info else None,
   }
   ```
3. `apps/web/src/lib/decisions.ts:205` — thêm hai field **optional**, params
   mô tả **cụ thể**, không `Record<string, unknown>`:
   ```ts
   warning_code?: string | null;
   warning_params?: {
     cores: number;
     reference_unpinned_ms: number;
     reference_pinned_ms: number;
   } | null;
   ```
   Run cũ không có hai field này **phải** tiếp tục render bằng `warning`.
4. Khoá i18n `decisions.env.unpinned` vào cả `en.json` và `vi.json`. Bản VI chép
   nguyên câu hiện tại từ `hostinfo.py`, không gõ lại.
5. `HostWarning` — điều kiện dịch structured phải **chặt cả hai vế**, không phải
   "có code thì dịch":
   ```
   warning_code === "unpinned_host"
     AND cores / reference_unpinned_ms / reference_pinned_ms đều là number hợp lệ
       → dịch structured
   ELSE
       → render legacy `warning` nguyên văn
   ```
   Code lạ từ artifact tương lai, hoặc params thiếu/sai kiểu → rơi về `warning`,
   không dịch nhầm mọi warning thành unpinned_host, không format `undefined`,
   không crash.

**Định dạng số theo locale — bắt buộc, không phải nice-to-have**: hàm dịch
(`shared.ts:44`) dùng `String(vars[name])` nên `59.30` ra `"59.3"` — nghiệm thu
"VI đúng nguyên câu" (cần `59,30`) sẽ fail nếu truyền số thô. Frontend **format
trước khi gọi `t()`**:
```ts
const fmt = new Intl.NumberFormat(locale, {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});
t("decisions.env.unpinned", {
  cores: String(cores),
  unpinned: fmt.format(reference_unpinned_ms),  // EN "59.30" · VI "59,30"
  pinned: fmt.format(reference_pinned_ms),
});
```

**Vì sao giữ `warning`**: `apps/api/planbench_api/decision_export.py:116` đọc khoá
này để ghi vào file xuất. Bỏ nó là phá file xuất của mọi run cũ.

**Nghiệm thu**: bật EN → banner tiếng Anh, số `59.30`/`16.10`. Bật VI → đúng câu
hiện tại từng dấu phẩy, số `59,30`/`16,10`. Run cũ (chỉ có `warning`) vẫn hiện
banner. Xuất báo cáo → nội dung không đổi.

---

### T6 — Test chặn tái phát: mọi `var(--x)` phải có định nghĩa

T1, T2 và T2b cùng một loại lỗi và cùng lọt qua review. Cần một test bắt được
loại này, không phải chỉ ba ca này.

**Làm**: thêm `apps/web/src/app/__tests__/tokens.test.ts` (vitest, đã có sẵn).
Đọc `globals.css`, **strip toàn bộ comment `/* … */` trước khi chạy regex** —
một dòng `--foo:` nằm trong comment mà không strip sẽ làm test tưởng token đã
được khai. Sau đó thu tập hợp mọi `--x:` được khai và mọi `var(--y` được tham
chiếu, khẳng định tập tham chiếu ⊆ tập khai báo ∪ allowlist.

**Allowlist cho custom property do JSX cung cấp** — quyết ngay ở đây, không để
plan sau nới test tuỳ tiện: token nào set từ inline style (Plan 2 sẽ thêm
`--cols`, và có thể `--delta-col`) phải nằm trong một mảng **có tên** trong test:
```ts
const JSX_PROVIDED = ["--cols", "--delta-col"];   // set qua style={{...}}, không khai trong CSS
const NEXT_FONT_PROVIDED = ["--font-sans-loaded", "--font-mono-loaded"]; // next/font sinh, Plan 3 dùng
```
Thêm ngoại lệ mới = sửa mảng này = phải cố ý và reviewer nhìn thấy. `var()` có
fallback **không** được miễn — T2b chứng minh fallback là nơi bug trốn.

**Hợp đồng font token với Plan 3 — chốt ngay để test không đỏ khi nạp font**:
token **công khai** (`--font-sans`, `--font-mono`) luôn khai trong `globals.css`;
`next/font` sinh token tên **riêng** (`--font-*-loaded`, đặt qua `variable:` trong
config); `globals.css` alias:
```css
--font-mono: var(--font-mono-loaded, ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace);
```
Nghĩa là: T2 của plan này khai `--font-mono` **không có** phần `--font-mono-loaded`
(font chưa nạp); Plan 3 chỉ **sửa giá trị** alias, không xoá khai báo. Test luôn
thấy token công khai được khai trong `globals.css`, còn `--font-*-loaded` nằm
trong `NEXT_FONT_PROVIDED`. Không plan nào phải nới test.

**Nghiệm thu**: cố tình đổi một tham chiếu thành `var(--khong-ton-tai)` → test đỏ.
`var(--cols, 2)` trong CSS → test xanh vì nằm trong allowlist.

---

### T7 — Khuyến nghị phải nêu config, không chỉ tên stack

Cả hai candidate của một phép so local-controller đều chung stack (`astar+dwa`);
thứ phân biệt chúng là `local_controller_config` (`dwa_coarse` / `dwa_balanced`).
Mọi bề mặt đang in mỗi tên stack đều mơ hồ về mặt **thông tin** — đây là bug,
không phải chuyện thẩm mỹ, nên nằm ở Plan 1. Plan 2 sau đó chỉ đổi hierarchy/style.

Các bề mặt, đã xác minh:

| Bề mặt | Vị trí | Hiện tại |
|---|---|---|
| Trophy badge đầu panel so sánh | `page.tsx:168` | `{run.card.recommended.stack}` |
| Câu kết luận "Use …" | `ConclusionPanel.tsx:118` | `Use astar+dwa` |
| `CardPanel` — Figure "Recommended" | `page.tsx:1321` | `value={card.recommended.stack}` |
| Export summary | `decision_export.py:265` | `("Recommended", recommended.get("stack"))` |

**Nguồn dữ liệu — chỉ rõ vì `card.recommended` KHÔNG có config**:
`decisions.ts:234` — `recommended: { candidate_id, stack, params_ref }`. Không
thể lấy config từ card. Đường lấy đúng:

```
recommended_candidate_id (hoặc card.recommended.candidate_id)
  → tìm candidate khớp trong report["candidates"]
  → lấy local_controller_config
```

Pattern này **đã tồn tại** ở `decisions.ts:878-886` — trang list làm đúng y thế
(`${recommended.stack_label} · ${recommended.local_controller_config}` sau khi
`candidates.find(...)`). Tái dùng / trích hàm chung, không viết lần hai.

**Fallback cho artifact cũ** không tìm thấy candidate khớp:
- UI: in `{stack} · {candidate_id}` hoặc `{stack}` + chú thích
  `config not recorded` — không im lặng.
- Export: `("Recommended config", "not recorded")` — không để chuỗi rỗng.

**Sửa — MỘT helper frontend, ba bề mặt cùng dùng, không viết ba lookup**:

Trích helper trong `decisions.ts` (tái dùng pattern `:878-886` sẵn có):
```ts
export function recommendedCandidateLabel(run: DecisionRun): string | null {
  // null khi run không có khuyến nghị
  // tìm thấy candidate  → `${stack_label} · ${local_controller_config}`
  // artifact cũ, không khớp → `${stack} · ${candidate_id}` (không im lặng)
}
```
- Trophy badge (`page.tsx:168`) và `CardPanel` (`page.tsx:1321`) gọi thẳng helper.
- `ConclusionPanel` — **KHÔNG đổi `conclusion.ts:62`**: `Standing.label` còn được
  render cạnh `<code>{standing.config}</code>` ở `ConclusionPanel.tsx:167` (đổi
  label là config hiện hai lần) và còn làm accessible label của thanh điểm. Chỉ
  sửa headline tại `ConclusionPanel.tsx:118`:
  ```ts
  const winnerLabel = winner
    ? `${winner.stack_label} · ${winner.local_controller_config}`
    : verdict.candidateId;
  ```
  truyền `winnerLabel` vào `conclusion.headline.use`. (Không dùng helper ở đây vì
  `ConclusionPanel` nhận `candidates`, không nhận `run` — nhưng cùng một luật.)
- `decision_export.py` — helper Python tương đương, lookup trong
  `report["candidates"]`, thêm dòng `("Recommended config", ...)` bên cạnh dòng
  `Recommended` hiện có, **không đổi** dòng cũ (file xuất cũ phải diff sạch).
  Không khớp → `("Recommended config", "not recorded")`.

**Nghiệm thu**: không bề mặt nào chỉ in `astar+dwa` trần khi nói về khuyến nghị.
Dòng candidate trong `ConclusionPanel` **không** in config hai lần. Artifact cũ
thiếu candidate khớp → fallback, không rỗng, không crash. Export cũ mở lại không
đổi nội dung dòng đã có.

---

## Thứ tự chạy

T1 → T2 → T2b → T3 → T4 → T6 (frontend, một lượt) · T5 và T7 chạy song song được
(backend + i18n; T7 chạm cả ba tầng nhưng độc lập với nhóm kia).

## Kiểm thử

**Frontend** (thứ tự: targeted trước, full sau — `npx vitest run` trần là full
suite, không phải "phần vừa sửa"):
1. Targeted: `npx vitest run` với path các file test của `Hint`, token,
   decision page, i18n, `conclusion`.
2. Targeted xanh rồi mới chạy full web suite một lượt chốt.
3. `npm run typecheck`.

**Backend — T5 và T7 đổi payload/export Python, Vitest không phủ được**:
- `tests/test_hostinfo.py` — thêm case cho `unpinned_warning_info()` (có/không pin).
- Test report của `selection.py`: **cả** nhánh bình thường **và** nhánh
  interrupted-before-first-episode đều mang `warning_code`/`warning_params`.
- `tests/api/test_decision_markdown.py`, `tests/api/test_decision_xlsx.py` —
  export không đổi dòng cũ, thêm dòng config (T7).
- Ruff cho các file Python bị chạm.

**Web cho warning — đủ BỐN ca**:
1. Structured warning + EN → câu tiếng Anh, số `59.30`.
2. Structured warning + VI → nguyên câu hiện tại, số `59,30`.
3. Run cũ chỉ có `warning: string` → vẫn render nguyên văn.
4. `warning_code` lạ hoặc `warning_params` thiếu/sai kiểu → fallback nguyên văn
   về `warning`, không crash.

## Nghiệm thu cả plan

- [ ] Kiểm thử ở mục trên xanh hết
- [ ] Host warning ở locale EN không còn tiếng Việt (thu hẹp đúng phạm vi T5 —
      chuỗi backend khác ngoài plan không tính)
- [ ] Dấu `?` xám, weight 600, không đậm hơn nhãn cạnh nó
- [ ] Tab tới `?` thấy ring 2px; Enter/Space toggle bubble; Escape đóng; click chuột không giật
- [ ] Playhead latency chart nhìn thấy ở cả hai theme
- [ ] `grep -n 'var(--font-mono, monospace)' globals.css` → rỗng
- [ ] Không bề mặt khuyến nghị nào in mỗi tên stack
- [ ] Test token mới bắt được lỗi khi cố tình phá

## Rủi ro

| Rủi ro | Mức | Xử lý |
|---|---|---|
| T4 `preventDefault()` trên click ảnh hưởng hành vi label ngoài dấu `?` | Thấp | preventDefault chỉ trong handler của chính span; click vào chữ label vẫn kích hoạt input. Kiểm tay checkbox ở `DeploymentForm` |
| T5 đổi payload backend | Thấp | Chỉ **thêm** khoá, không xoá. Test cả hai nhánh của `selection.py` |
| T5 sai chính tả khi chép câu sang `vi.json` | Thấp | Copy nguyên văn từ `hostinfo.py`, không gõ lại |
| T5 số sai định dạng theo locale | Thấp | `Intl.NumberFormat` + hai ca test EN/VI khoá cứng `59.30`/`59,30` |
| T7 đổi câu "Use …" làm đỏ test snapshot của `ConclusionPanel`/`conclusion` | Trung bình | Sửa test cùng lượt với code, không sửa sau |

## Không commit

Làm xong dừng lại, báo cáo. An tự commit.

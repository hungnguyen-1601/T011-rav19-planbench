# UI: nút trợ lý khi hover, và cột "Compared" ở danh sách so sánh

**Ngày:** 2026-08-26
**Nhánh:** `tongduyan_ui-polish` → merge vào `main`
**Phát hành:** desktop 0.1.13

Phiên này làm hai việc trên UI, cộng một loạt thử nghiệm bố cục đã được
An yêu cầu hoàn tác. Ghi cả phần hoàn tác, vì nó là lý do cây mã hôm nay
ở phần Deployment conditions trông y hệt hôm qua trong khi phiên làm việc
thì không ngắn.

---

## 1. Nút trợ lý (góc phải dưới) khi rê chuột

### Hiện tượng

An báo hai lần, mỗi lần một triệu chứng khác:

1. Lần đầu: *"icon vẫn hiện trắng thay vì xanh đậm như tôi mong muốn"*
2. Lần sau: *"thay vì in đậm thì hover thành trong suốt luôn, nên khá khó nhìn"*

Hai lời phàn nàn nghe như trái ngược nhau nhưng cùng một gốc: cả hai lần,
trạng thái hover đều **giảm** tương phản chứ không tăng.

### Nguyên nhân

Quy tắc hover lúc đó:

```css
background: color-mix(in srgb, var(--accent) 12%, var(--panel));
border-color: color-mix(in srgb, var(--accent) 55%, transparent);
```

Ở theme sáng `--panel` là `#ffffff`, nên 12% accent trộn vào cho ra một
màu gần như trắng. Viền thì trong suốt 55%. Nút mất cả nền lẫn viền —
đúng nghĩa "trong suốt".

Nửa còn lại nằm ở `Icon.tsx`: mọi icon vẽ bằng
`fill="none" stroke="currentColor" strokeWidth="2"`. Đó là **nét**, không
phải hình đặc. Trên nền gần trắng, cả nút chỉ còn bốn đường mảnh.

### Sửa

`apps/web/src/app/globals.css`, khối `.agent-dock-launcher:hover`:

```css
background: color-mix(in srgb, var(--accent) 32%, #fff);
border-color: var(--accent);
color: color-mix(in srgb, var(--accent) 45%, #000);
```

```css
.agent-dock-launcher:hover svg { stroke-width: 2.4; }
```

Ba thứ làm nút "có thật" trở lại: nền đủ accent để là một màu chứ không
phải là trang giấy, viền nguyên độ đậm nên vòng tròn có mép, và nét icon
dày lên.

### Vì sao neo bằng `#fff` / `#000` chứ không dùng token

`--panel` và `--accent-contrast` **đảo vai giữa hai theme**:

| Token | Theme sáng | Theme tối |
|---|---|---|
| `--panel` | `#ffffff` | `#171a21` |
| `--accent-contrast` | `#ffffff` | `#05070c` |

Trộn về bất kỳ token nào trong hai cái đó sẽ cho nền nhạt ở theme này và
nền tối ở theme kia — mà nét icon, thứ phải tương phản với nền, không đi
theo được cả hai chiều. Neo cố định thì nền luôn nhạt, nét luôn đậm,
tương phản giữ nguyên ở cả hai theme. Lý do này ghi thẳng trong comment
cạnh quy tắc, vì nó đúng là loại quyết định người sau sẽ "dọn dẹp" thành
token nếu không biết.

### Test

`apps/web/src/app/__tests__/simulate-busy.test.tsx` — thay 1 test cũ
(cấm `#fff` với lý do "trắng sẽ chói ở dark theme", nay không còn đúng vì
nền là xanh 32%) bằng 3 test pin đúng ba nguyên nhân: nền đủ accent và
không dùng `--panel`, viền full strength, nét dày.

Đồng thời sửa một assertion mong manh trong cùng file:

```js
expect(PAGE).not.toContain('busy ? (\n            <div className=...');
```

Nó pin **thụt đầu dòng và ký tự xuống dòng**, không phải hành vi — đỏ lên
chỉ vì file đổi CRLF sang LF. Thay bằng: giữa dòng mở `.simulate-workspace`
và `<MapView` không xuất hiện `busy`, tức canvas không bao giờ là thứ bị
tắt khi đang mô phỏng.

**Commit:** `f027053`

---

## 2. Danh sách so sánh: bỏ cột Scope, thêm cột Compared

### Vấn đề

Bảng ở `/decisions` có cột **Scope** hiện `experiment_scope`. Đó là *luật*
mà cặp ứng viên được chọn theo — tra một lần là biết — và nó đang chiếm
đúng chỗ người đọc quét mắt tìm "hai thuật toán nào đã chạy". 19 dòng
cùng ghi `global_planner_selection` không phân biệt được gì.

### Sửa

Thêm hai hàm ở `apps/web/src/lib/decisions.ts`:

```ts
export function candidateLabel(candidate: RunCandidate): string {
  return `${candidate.stack_label} · ${candidate.local_controller_config}`;
}

export function comparedCandidates(run: DecisionRun): string[] {
  return (run.report?.candidates ?? []).map(candidateLabel);
}
```

`candidateLabel` được `recommendedCandidateLabel` dùng lại — trước đó nó
tự dựng chuỗi y hệt, giờ chỉ còn một chỗ định nghĩa.

**Có kèm config chứ không chỉ `stack_label`**: run
`local_controller_selection` so hai tuning của *cùng* một stack. Chỉ ghi
stack thì hai dòng giống hệt nhau, và bảng sẽ nói rằng run đó so một thứ
với chính nó.

Render dạng `<ul class="decision-candidate-list">`, mỗi ứng viên một dòng,
`white-space: nowrap`. Nối bằng dấu phẩy thì tên bị ngắt giữa chừng trong
cột hẹp và người đọc không biết tên nào kết thúc ở đâu.

Report chưa về (run đang xếp hàng hoặc lỗi) thì hiện `—`, không để ô trống
— ô trống trông như "run này so sánh không có gì".

### Bỏ dấu `?` đứng một mình

Hint `decisions.tally.note` nằm một hàng riêng dưới 5 thẻ đếm. Một dấu hỏi
không có gì bên cạnh đọc như một nút, người dùng phải bấm mới biết nó là
gì. Bỏ.

### Cột Map: thêm rồi bỏ

An yêu cầu thêm cột bản đồ, xem xong thì bỏ (*"đang để hẳn đường link đến
maps, tôi không thích điều này"*). Đã gỡ sạch: `<th>`, `<td>`, `mapOf`
`useMemo`, prop trên `DecisionRow`, `useMemo` khỏi import React, key
`decisions.column.map` khỏi hai locale, và test tương ứng.

### i18n

Bỏ `decisions.column.scope`, thêm `decisions.column.candidates`
(Compared / So sánh). Hai locale 1861 key, khớp nhau.

### Test

4 test mới trong `decisions-page.test.tsx`: cột gọi tên thuật toán chứ
không gọi tên luật, key có ở cả hai locale, và hint lẻ đã biến mất.

**Commit:** `abd9785`

---

## 3. Bố cục 7 thẻ Deployment conditions — đã làm rồi hoàn tác

An yêu cầu xếp 7 thẻ theo hàng ngang, thu cột, bỏ khoảng trắng, và đổi
"Cost per mission max" thành "None". Đã làm xong, An xem rồi yêu cầu trả
về nguyên trạng qua hai bước:

1. Hoàn tác phần sắp xếp lại thứ tự thẻ theo thứ tự tab của form
   deployment, và phần thu hẹp lề phải (row đổi sang flex wrap).
2. Hoàn tác luôn phần hàng ngang: `git checkout HEAD -- apps/web/src`.

Cây mã hiện về đúng commit `483d959`. Không có commit nào của đợt này
trong lịch sử — có chủ đích, vì An nói *"không phải lỗi của bạn"* và sẽ
quay lại phần này sau.

Ba thứ đã khảo sát được và đã mất theo, ghi lại để lần sau khỏi làm lại:

- `columns: 260px 4` (multi-column) là thứ tạo ra thế xếp lệch 2/1/2/2:
  multi-column đổ thẻ **xuống** từng cột chứ không đi ngang. Muốn hàng
  ngang thì phải là `grid-template-columns: repeat(7, ...)`, không có cách
  nào chỉnh tham số multi-column ra được.
- Thứ tự tab của form deployment là: mission, traffic, robot, constraints,
  noise, policies, hardware. Thứ tự thẻ hiện tại lệch đúng một chỗ:
  `environment` (tab traffic, form hỏi thứ 2) đang đứng thứ 5. Hai chỗ
  không thể khớp: `scope` không có tab nào (nó là danh tính của deployment),
  và `hardware` đọc trong thẻ robot chứ không tách riêng.
- Ở cột rộng khoảng 200px, row hai cột (nhãn trái | giá trị phải) và row
  xếp chồng đều có nhược điểm riêng: hai cột thì ép chật nhãn dài
  ("Localisation + mapping"), xếp chồng thì bỏ trống nửa phải mọi dòng
  ngắn. `display: flex; flex-wrap: wrap; justify-content: space-between`
  là thứ tự chọn theo từng dòng — đã thử, chạy đúng, nhưng An chưa ưng
  tổng thể nên bỏ cùng cả đợt.

---

## Kiểm chứng

| Suite | Kết quả |
|---|---|
| `decisions-page.test.tsx` | 153/155 |
| `simulate-busy.test.tsx` | 12/12 |
| `simulate-page.test.tsx`, `test-bench.test.tsx`, `bench-conditions.test.ts`, `i18n.test.ts` | xanh |
| `tsc --noEmit` | sạch |

Hai lỗi còn lại của `decisions-page.test.tsx` là thiếu key
`preflight.disabledDerived` và `outcome.title`. **Có sẵn từ trước phiên
này** — kiểm bằng `git show HEAD:...en.json | grep -c` trả về 0. Chúng
nằm trong tồn đọng 27 key đã báo cáo trước đó, chưa được giao xử lý.

`tsc` còn 3 lỗi ở `candidates-page.test.tsx` về key `paper.*` — cũng có
sẵn từ HEAD, không liên quan.

---

## Không đụng tới

Theo yêu cầu chỉ commit phần UI, các thay đổi sau của An được để nguyên
trong working tree, **không** đưa vào commit nào:

- `.gitignore` (thêm `vfh_plus_iterated/`)
- `docs/antongduy/reports/2026-08-26/tongduyan_them-thuat-toan-mppi-dang-plugin.md`
- `docs/antongduy/reports/2026-08-24/tongduyan_thumbnail-du-an.md`
- `mppi_import/`, `presentation/thumbnail/`, `artifacts/runs/2026-08-25/`,
  `planbench.db.bak-before-0010`, `planbench.db.bak-before-0011`

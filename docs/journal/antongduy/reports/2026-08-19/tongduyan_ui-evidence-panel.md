# UI — khối bằng chứng trên trang decision

**Ngày:** 2026-08-19 · **Nhánh:** `tongduyan_3` · Nối tiếp E4.1/E4.2

**Trạng thái:** xong, **chưa commit**. Full suite (Python) chưa chạy.

---

## 1. Đặt ở đâu, và vì sao

Ngay **dưới bảng cổng**, theo chỉ định của An. Lập luận cũng khớp với thứ tự sẵn có
của trang: bảng cổng nói *ai bị loại ở đâu*, thứ người đọc cần gặp tiếp là *quan sát
được gì trong lúc chúng chạy* — không phải một khuyến nghị cách đó ba mục. Có test
khẳng định vị trí, không chỉ khẳng định sự tồn tại:

```
gate < evidence < candidate-comparison
```

---

## 2. Giao cái gì

| File | Nội dung |
|---|---|
| `lib/decisions.ts` | type packet + `getExplanation(runId)` |
| `lib/evidence.ts` | **phần quyết định**: `waterfallState`, `sightingsState`, `verdictTone`, `orderedFindings`, `missingNotes`, `widestContribution` |
| `components/EvidencePanel.tsx` | phần vẽ |
| `globals.css` | style cho bảng và thanh |
| i18n en/vi | 29 khoá |

**Vì sao tách `lib/evidence.ts`.** Repo này **không có jsdom** — vitest chỉ dựng
markup tĩnh, nên một component có fetch trong effect không thể lái qua các trạng
thái của nó. Đặt luật ngay trong component nghĩa là luật đó chỉ kiểm được bằng cách
nhìn pixel, mà ở đây thì không nhìn được. Tách ra là để **kiểm được thứ đáng sai**.

---

## 3. Bốn phân biệt được giữ, mỗi cái một test

**Không có waterfall vì lý do gì.** `run-ranked-nobody` (không có cặp để phân rã)
khác `plan-forbids` (ma trận panel không cho vẽ). Hai câu khác nhau trên màn hình.

**Không có sighting vì lý do gì.** `no-traces` (detector chưa từng chạy) và `clean`
(detector chạy và không thấy gì — **đó là kết quả**) đều cho ra một bảng rỗng và
nghĩa ngược nhau.

**Verdict nào là phát hiện, verdict nào là cái nhún vai.**
`rules_out_component_specific_attribution` là **kết quả** — cả hai stack đều có
hiện tượng nên thứ phân biệt chúng không phải component đó. Tô nó cùng màu xám với
`insufficient_contrast` là xếp một phát hiện vào ô "không có gì" — đúng lỗi cả tầng
này sinh ra để chặn, phạm bằng CSS. Nên nó `warn`, không `muted`.

**409 là trạng thái, không phải lỗi.** Run chấm trước E4.1 hiện một câu giải thích
kèm gợi ý chạy lại, không phải hộp đỏ.

---

## 4. Ba lựa chọn trình bày có lý do

**Bảng, không phải biểu đồ vẽ.** Mỗi thanh đóng góp in **khoảng tin cậy ngay cạnh**:
đóng góp 0,02 với khoảng vắt qua 0 và 0,02 với khoảng tách hẳn 0 là hai phát hiện
khác nhau, mà một biểu đồ cột không khoảng thì mời người ta đọc mỗi chiều cao. Thanh
màu chỉ là trợ giúp đọc **phía sau con số**, không thay nó.

**Sighting in dạng phân số, không phải phần trăm.** `1/30` chứ không phải `3%` —
phần trăm giấu mất rằng đó là một episode. Có test bắt chuyện này.

**Trung vị in ra và cố ý không phân rã.** Đẳng thức khiến các thanh cộng đúng thành
tổng chỉ giữ qua **trung bình**. Ghi rõ ngay dưới bảng.

**Lattice sắp theo độ mạnh phát biểu**, không theo tên detection: người quét bảy
dòng nên gặp những dòng nói được điều gì trước.

---

## 5. Chưa có, và cố ý

- **Claims** — chưa analyst nào qua gate. Panel gắn nhãn `chưa có kết luận` ngay ở
  đầu, để người đọc không tự điền suy luận vào chỗ trống.
- **Exemplar chip trong khối này** — chúng đã có sẵn ở `TracePanel`, không nhân đôi.

---

## 6. Kiểm chứng

- `src/lib/__tests__/evidence.test.ts` — **13 test** cho phần quyết định.
- `src/app/__tests__/evidence-panel.test.tsx` — **37 test**: vị trí gắn, xử lý 409,
  hai câu "không có waterfall", phân số không phần trăm, khoảng tin cậy, và **mọi
  khoá i18n tồn tại ở cả hai ngôn ngữ** (gồm bốn khoá verdict ghép lúc chạy, thứ
  không phép quét tĩnh nào bắt được).
- Toàn bộ web: **1032 passed** (50 file). `tsc --noEmit` sạch.
- i18n thêm 29 khoá, **giữ nguyên thứ tự file** — lần đầu tôi ghi đè bằng
  `sort_keys` làm diff phồng lên 2722 dòng vô nghĩa; đã hoàn tác và chèn tại chỗ.

## 7. Chưa kiểm chứng được ở đây

Panel chưa được xem bằng mắt trên một run thật có packet — cần API chạy cùng một
run đã chấm sau E4.1. Logic và khoá dịch có test đứng sau; **cách nó trông** thì
chưa. Nói rõ chứ không suy từ test.

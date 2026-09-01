# Plan bổ sung — ba đầu vào MVP cho AI Analyst (bản 9)

**Ngày:** 2026-08-26 (phiên lập kế hoạch thứ hai trong ngày) · **Trạng thái:**
**An đã duyệt, đang thi hành**
**Bổ sung cho:** `plans/2026-08-26/ai-analyst-ban-8.md` — bản 8 **không bị thay
thế**. File này thêm ba phase và đổi thứ tự; chỗ nào im lặng thì bản 8 vẫn là luật.
**Nguồn:** An chốt phạm vi MVP — *"AI đọc metrics cuối cùng, có thể là metrics
realtime từng episode, ghép với ưu/nhược điểm thuật toán trong DB, để kết luận
tại sao hơn"*. Tương lai xa: đọc movement từng episode.
**Đã thi hành tới:** A-1, A0, A1, A2, A3 (xem `reports/2026-08-26/`).

---

## 1. Vì sao có bản 9: bản 8 bám nửa đường

Đối chiếu 17 packet thật trong `artifacts/runs/`:

| Đầu vào MVP | Hiện trạng | Kết luận |
|---|---|---|
| Metrics cuối cùng | packet chở **ΔU tách theo 4 mục tiêu** (weight, delta, CI95, `crosses_zero`) + tổng ΔU + n_episodes — và chỉ **4/17** packet có, vì 13 run còn lại không xếp hạng ai. `gates` chỉ là `{"cand": {"passed": false}}`: **không tên cổng, không con số, không ngưỡng**. Bảng metric per-candidate (success rate, p99, path length, clearance, collision) nằm trong `comparison_report.json`, **không vào packet** | **thiếu một nửa** |
| Metrics realtime từng episode | `running_metrics.py` (E4.3) có thật, hai đồng hồ tách bạch equal-time / equal-progress, nhưng chỉ nuôi trang replay qua `decision_service`. Packet không chở. Lane 2 chạm episode chỉ qua 4 tool navigation, và chúng trả **cửa sổ trace** — đã là lãnh địa "đọc movement" của tương lai xa | **không có** |
| DB ưu/nhược thuật toán | **đã có**: `TRAITS` trong `packages/benchmark/planbench_benchmark/outcome.py`, mỗi họ có `strengths`/`weaknesses`/**`anchor`** (cờ registry hoặc cơ chế định nghĩa), 7 luật ghép số với tính chất, chạy ở `GET /decisions/{id}/outcome`. Nhưng **Lane 1 giữ**, Lane 2 không với tới; là **dict trong code**, không phải DB; và **thuật toán import không có dòng nào** | **có, sai phía hàng rào** |

Menu 16 tool xác nhận điều trên: `fact_query` chỉ trả được ΔU, prevalence
detection, hình học map và mấy con số đếm. Không tool nào lấy được success rate
hay p99.

## 2. Ba quyết định của An (2026-08-26, phiên 2)

| # | Chốt | Hệ quả |
|---|---|---|
| 1 | Thêm **cả ba** đầu vào vào tầm với của analyst | M1 · M2 · M3 |
| 2 | Traits sống trong **bảng DB có migration, sửa được** | M3 có migration + hàng cho thuật toán import |
| 3 | Khối sandbox **giữ nguyên trong scope** | A4/A7 không đổi so với bản 8 |

## 3. Ba phase mới

### M1 — Metric cuối cùng vào packet (1,5–2 ngày)

**Việc:**

- `CasePacket` thêm `measurements: tuple[CandidateMeasurements, ...]`: mỗi
  candidate một bản ghi **các số đã đo**, đúng những số report đang giữ —
  success rate, p99/median latency, path length, min clearance, collision
  count, n_episodes — mỗi số kèm **đơn vị** và **mẫu số** (`rate` không có
  denominator là con số HĐ cấm nói).
- `DecisionFacts.gates` đổi từ `{"passed": bool}` sang bản ghi có **tên cổng,
  ngưỡng, giá trị đo, và verdict**. Bản cũ đọc được thành bản mới (migration
  đọc, không sửa file cũ) — packet cũ giữ nguyên `passed`, và loader nói rõ
  "run này ghi trước M1".
- `packet_view` thêm họ fact `fact:metric:<candidate>.<name>` và
  `fact:gate:<gate_id>.{threshold,value,verdict}`, có `unit`, có `subject`
  (`None` — một phép đo không tự khai ai chịu trách nhiệm, luật của A1).
- **Card mới `get_candidate_measurements`** (tool_class `fact_query`), khai đúng
  các measurement key trên.

**Hệ quả hợp đồng — không được bỏ qua:**

- `EXPLANATION_SCHEMA_VERSION` **bump**: packet đổi hình. Cổng ở A1 đã canh sẵn
  (`build_packet_view` từ chối packet của build khác), nên 17 packet cũ sẽ bị
  **từ chối đúng luật** cho tới khi dựng lại.
- `TOOL_CATALOG_VERSION` **bump**: thêm một card là đổi menu. Bundle khai
  catalog nào thì chấm bằng catalog đó — `run_gate` đã có luật này.
- Golden fixture (A6.5) **phải dựng sau M1**, nếu không sẽ chấm analyst trên
  hình packet không còn tồn tại.

**Nghiệm thu:** dựng lại packet cho ≥3 run thật; mọi số trong bảng metric của
report có đúng một ref trong index; `rate` không có denominator thì **từ chối
dựng packet**, không phải cảnh báo; packet cũ đọc được và tự khai là bản cũ.

### M2 — Metrics realtime theo episode (1–1,5 ngày)

**Việc:**

- Nối `running_metrics` vào packet **chỉ cho các episode đại diện** (4 exemplar
  roles). Cả 30 episode thì packet phình ra và prompt trả giá cho phần không ai
  đọc.
- Mỗi episode một chuỗi mốc (checkpoint) chứ không phải từng tick: **equal-time**
  và **equal-progress** tách bạch, đúng như E4.3 đã thiết kế; hai đồng hồ không
  bao giờ trộn trong một hàng.
- Fact ref: `episode:<id>/at_time/<mốc>.<metric>` và
  `episode:<id>/at_progress/<mốc>.<metric>`. Đồng hồ nằm **trong ref**, để một
  trích dẫn không thể mơ hồ về việc nó nói ở mốc nào.
- Card mới `get_episode_timeline` (`fact_query`).

**Nghiệm thu:** một exemplar sinh ra ≤ N fact (N chốt lúc làm, và in ra); hai
đồng hồ không lẫn; packet phình thêm bao nhiêu byte thì **đo và ghi vào report**
— đây là chi phí prompt mỗi vòng phải trả.

### M3 — Bảng traits trong DB, và đường vào Lane 2 (1,5–2 ngày)

**Việc:**

- Migration + bảng `algorithm_traits`: `algorithm_id`, `kind` (global/local),
  `strengths[]`, `weaknesses[]`, `anchor`, `review_status`, `reviewed_by`,
  `updated_at`.
- **Seed từ `TRAITS` hiện có**, không viết lại: dict trong code trở thành seed
  của migration, và `outcome.py` đọc bảng thay vì đọc dict. Một nguồn, không
  phải hai.
- **Thuật toán import có chỗ để khai**: hàng trống với `review_status='none'`
  được tạo lúc import. `null` ở đây là **"chưa ai khai"**, và phải đọc ra như
  thế — không phải "không có ưu nhược điểm".
- Đường vào Lane 2: traits thành **nguồn knowledge** ở A5, trả
  `MechanismReferenceCandidate` có `anchor`, và analyst **trích dẫn được** bằng
  ref `trait:<algorithm_id>#<strength|weakness>:<i>`.
- Luật giữ nguyên tinh thần KB: trait `review_status != 'approved'` thì **không
  promote claim nào**; nó chỉ mở rộng không gian giả thuyết.

**Nghiệm thu:** `outcome.py` (Lane 1) và Lane 2 đọc **cùng một bảng**; sửa một
hàng thì cả hai đổi theo; thuật toán import không có trait thì analyst nói
"chưa khai" chứ không im lặng; trait chưa duyệt không đẩy được claim lên
`mechanism_verified`.

## 4. Thứ tự thi hành mới

```
A4 (seam + lane + gateway + budget + RFC)   ← đang tới, không đổi
   ↓
M1 (metric facts)  →  M2 (episode timeline)  →  M3 (traits DB)
   ↓
A5 (knowledge provider, nay gồm traits)
   ↓
A6 (dev calibration — chạy trên hình packet đã đủ ba đầu vào)
   ↓
A6.5 (ba họ golden — dựng SAU M1/M2, nếu không là chấm trên hình cũ)
   ↓
A7 (freeze + container + official calibration)
```

**A4 đi trước M1–M3** vì nó là vòng chạy end-to-end: có nó thì mỗi đầu vào mới
đo được ngay ("thêm bảng metric vào có làm analyst nói khác đi không"), không có
nó thì ba phase kia là ba lần đoán.

## 5. Ước lượng cập nhật

Bản 8: 12,5–18,5 ngày. Cộng M1 (1,5–2) + M2 (1–1,5) + M3 (1,5–2) =
**16,5–24 ngày**. Đã tiêu 5 phase (A-1 → A3).

## 6. Rủi ro của chính bản 9

| Rủi ro | Giảm nhẹ |
|---|---|
| Packet phình ⇒ mỗi vòng đắt hơn, và model đọc lướt | M2 chỉ lấy exemplar; đo byte packet trước/sau và ghi vào report; A6 so chất lượng **và** chi phí |
| Bump hai version làm 17 packet cũ vô hiệu | Đúng thiết kế — cổng A1 đã canh. Dựng lại packet cho run cần dùng, và khai rõ run nào là bản cũ |
| Traits thành nơi đổ folklore | `anchor` là trường **bắt buộc**; `review_status` chặn promote; Lane 1 và Lane 2 đọc cùng bảng nên một dòng sai lộ ra ở cả hai chỗ |
| Analyst dựa traits thay vì dựa số | trait không phải evidence: luật 7 của guard vẫn đòi ít nhất một ref, và trait ref không thay được ref đo |
| Golden dựng trước M1/M2 | A6.5 đứng **sau** trong thứ tự trên; nếu buộc phải dựng sớm thì `OFFICIAL_GOLDEN_READY` vẫn `False` và report phải nói golden thuộc hình packet nào |

## 7. Điều bản 9 **không** làm

Đọc movement từng episode để suy ra cơ chế — kỳ vọng tương lai xa của An.
Không bị chặn: sidecar planning-input đã ghi, 4 tool navigation đã có, replay đã
có. Khi tới lúc, nó là một họ card mới trên cùng seam, không phải viết lại.

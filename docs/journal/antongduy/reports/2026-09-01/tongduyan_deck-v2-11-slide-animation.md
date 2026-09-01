# Deck v2 — thêm slide "tương lai của ngành", animation từng phần, 11 slide

**Ngày:** 2026-09-01
**Phạm vi:** sửa `presentation/deck-v2/planbench-deck-v2.html`, render lại toàn bộ
PNG, thêm `planbench-deck-v2-animated.pptx` và thư mục `build/`. Không đụng code
sản phẩm.

---

## 1. Yêu cầu của An

Ba việc, từ phản hồi trên bản 10 slide hôm 2026-08-31:

1. Thêm **transition và animation giữa các phần trong một slide**.
2. Giữa slide 3 (cách cũ) và slide 4 cũ (định vị) chèn một slide
   **định hướng tương lai của ngành** — đối lại "các cách đang làm".
3. Slide định vị (giờ là slide 5) đổi khung thành **"PlanBench tạo ra
   tương lai đó thế nào"**.

## 2. Slide 04 mới — "Ngành này đang đi về đâu"

Đây là nhịp **NEW WAY** trong Product Narrative 7 nhịp của bộ slide pitching
(USER → PAIN → OLD WAY → **NEW WAY** → PRODUCT → PROOF → FUTURE) — bản 10 slide
đã gộp nhịp này vào slide định vị, giờ tách ra đúng như khung dạy. Ba dịch
chuyển, mỗi cái một thẻ:

| # | Dịch chuyển | Neo vào đâu |
|---|---|---|
| 1 | **Sim-first** — kiểm định chuyển từ hiện trường sang mô phỏng (Isaac Sim, Gazebo, digital twin) | xu hướng ngành công khai; trùng roadmap "3D Simulator Bridge" của chính deck |
| 2 | **Quyết định kiểm toán được** — như CI/CD đã làm với phần mềm: test, log, người ký | phép loại suy, không phải số liệu |
| 3 | **AI đọc số, không sinh số** — AI vào quy trình kỹ thuật ở vai chất vấn bằng chứng | đúng SHIFT HOOK mà bộ slide pitching dạy, và đúng khẩu hiệu cốt lõi của PlanBench |

Chốt slide bằng câu cầu nối: *"Ai định chuẩn được cách chứng minh một cấu hình
là đúng, người đó định chuẩn cách ngành mua robot"* — dắt thẳng sang slide 05.

**Trung thực:** cả ba là **luận điểm định hướng**, không phải thống kê; cố ý
không gắn con số nào để khỏi phải bịa nguồn. Slide 05 đổi tiêu đề thành
"PlanBench tạo ra tương lai đó thế nào", thêm lede, và nhãn mỗi trụ giờ ghi rõ
nó bám dịch chuyển nào (Trụ 1 · AI đọc số / Trụ 2 · Kiểm toán được / Trụ 3 ·
Sim-first / Trụ 4 · Kiểm toán được).

Deck thành **11 slide**; các slide sau đánh số lại 05–11, mọi nhãn
"Slide NN / 11" và footer cập nhật theo.

## 3. Animation — làm thế nào trong từng định dạng

PPTX ghép từ ảnh tĩnh không có animation phần tử thật. Giải bằng **overlay
build** — kỹ thuật handout của Beamer:

- Mỗi phần tử cần hiện dần mang `data-f="n"` trong HTML (35 phần tử, 11 slide).
- Mỗi slide render thành **F+1 tấm**: `?f=0` (nền) → `?f=F` (đủ). Layout không
  bao giờ xê dịch giữa các bước — phần tử ẩn bằng opacity, không bằng display.
- PPTX xếp đủ 42 tấm, **mỗi tấm gắn `<p:transition><p:fade/>`** (advance on
  click). Bấm chuột trong PowerPoint ⇒ phần tiếp theo fade vào đúng chỗ —
  nhìn như animation trong một slide, dù kỹ thuật là nhiều slide.

Nhịp build từng slide (nền + số bước):

| Slide | Bước hiện dần |
|---|---|
| 01 Hook | headline đau trước → bấm → wordmark PlanBench hiện |
| 02 Pain | ba thẻ Ai / Đau ở đâu / Hậu quả, từng thẻ |
| 03 Old way | ba cách, từng thẻ |
| 04 Tương lai | ba dịch chuyển từng thẻ → câu cầu nối |
| 05 Solution | one-liner đứng sẵn → bốn trụ từng thẻ |
| 06 Product | rail 5 bước → thẻ sáu cổng → thẻ luật |
| 07 Demo | map đứng sẵn → bốn nhịp kịch bản từng dòng |
| 08 Proof | bảng bằng chứng → khối "chưa có" |
| 09 Moat | hai cặp thẻ |
| 10 Ai trả tiền | ba thẻ → khối trung thực |
| 11 Team·Ask | cột team/roadmap → Ask chính → Ask phụ |

**HTML có chế độ trình chiếu thật** (animation mượt, không phải fade ảnh):
mở `planbench-deck-v2.html?live=1` trong browser, F11 toàn màn hình —
→ / Space / PageDown hiện phần kế rồi sang slide; ← / PageUp lùi. Mở file
không tham số vẫn là gallery cuộn đủ 11 slide như cũ; `?f=N#sX` là móc chụp
ảnh, đóng băng slide X ở bước N và tắt transition.

## 4. File

| File | Là gì |
|---|---|
| `planbench-deck-v2.html` | Nguồn duy nhất — gallery, presenter mode, móc chụp |
| `slide-01..11.png` | Bản đủ nội dung của từng slide, 2560 × 1440 |
| `build/slide-NN-fK.png` | 42 tấm overlay cho PPTX |
| `planbench-deck-v2-animated.pptx` | **Bản mới** — 42 slide vật lý / 11 slide logic, fade toàn bộ, 21 MB |
| `planbench-deck-v2.pptx` | Bản cũ 10 slide tĩnh — **chưa ghi đè được vì file đang bị PowerPoint khoá** (PermissionError lúc save); An đóng PowerPoint rồi muốn thì xoá/đổi tên |

Lệnh render lại (Edge headless, per-slide per-step):

```powershell
# FR = số bước của từng slide, theo bảng trên
$FR = @(1,3,3,4,4,3,4,2,2,2,3)
foreach ($i in 1..11) { foreach ($f in 0..$FR[$i-1]) {
  & "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
    --headless=new --disable-gpu --no-sandbox --user-data-dir=<tmp> `
    --hide-scrollbars --force-device-scale-factor=2 --window-size=1280,720 `
    --screenshot="build\slide-$('{0:d2}' -f $i)-f$f.png" --virtual-time-budget=7000 `
    "file:///E:/VinAI/RoboMind_project/P-011/presentation/deck-v2/planbench-deck-v2.html?f=$f#s$i"
} }
```

PPTX ghép bằng `python-pptx` (đã cài 1.0.2 từ hôm qua), chèn
`<p:transition spd="fast"><p:fade/></p:transition>` sau `p:clrMapOvr` của từng
slide.

## 5. Kiểm chứng

- HTML sau sửa: đủ 11 section, 35 phần tử `data-f`, đánh số 01–11 khớp cả beat
  lẫn footer (soi PNG slide 04, 05, 07, và nền 01).
- Overlay đúng nghĩa: `slide-07-f2.png` chỉ có map + nhịp 1–2; các bước sau
  thêm phần tử đúng vị trí, không xê dịch layout.
- PPTX đọc lại bằng python-pptx: **42 slide, 42 transition** — đếm bằng máy,
  không đếm tay.
- **Chưa kiểm bằng PowerPoint thật:** fade khi bấm chuột là hành vi đã khai
  trong XML, đọc lại thấy đúng, nhưng chưa mở PowerPoint bấm thử. An mở
  `planbench-deck-v2-animated.pptx`, F5, bấm chuột — mỗi click một phần hiện
  ra. Nếu máy chiếu yếu thì transition fade "fast" vẫn an toàn vì hai tấm liền
  nhau giống nhau 90%.

## 6. Chưa làm

- Chưa xoá được `planbench-deck-v2.pptx` cũ (file đang mở trong PowerPoint).
- Ảnh chụp UI thật cho slide 06/07 vẫn chưa chèn (tồn từ report trước).
- Chưa cập nhật hai số sai trong `pitch_deck.pptx` gốc (3.290+ test; 59,3 → 16,1 ms).
- Chưa commit (An tự commit). PNG overlay + PPTX ~27 MB — nếu commit thì cân
  nhắc chỉ đưa HTML nguồn vào git.

---

## Bổ sung cùng ngày — cover, slide cảm ơn, sửa tiêu đề slide 10

Ba yêu cầu tiếp của An, làm trên cùng cây file:

1. **Cover = thumbnail v1.** `presentation/thumbnail/planbench-thumbnail-1280x720.png`
   thành slide vật lý đầu tiên của PPTX (không đánh số) và section `#s0` trong
   HTML. Cũng nhúng làm **preview của file** — `docProps/thumbnail.png` + quan hệ
   `metadata/thumbnail` trong `_rels/.rels`, nên Explorer/PowerPoint hiện đúng
   thumbnail v1 khi duyệt file.
2. **Slide 12 — Cảm ơn.** "Cảm ơn ban giám khảo!" + lời mời chất vấn đúng chất
   deck ("mọi con số trong deck này đều trỏ về được nơi nó được đo — cứ hỏi bất
   kỳ số nào"), GitHub, wordmark, Team T011; footer là câu cơ chế làm bookend
   với slide 01. Deck giờ **12 slide đánh số + 1 cover**.
3. **Slide 10 đổi tiêu đề** theo góp ý "nói thẳng ai trả tiền": *"Ngân sách nằm
   ở đâu, và ai là người ký duyệt nó"* → **"Ai là người trả tiền"**, lede đổi
   theo. Nội dung ba thẻ giữ nguyên.

**Bug bắt được khi render:** section cover ban đầu mang inline
`display:block`, đè luật ẩn `body:has(.slide:target) .slide { display:none }`
(inline thắng selector không-`!important`) — cover luôn hiện và đứng đầu tài
liệu, nên **mọi ảnh chụp có `#target` đều chụp trúng cover** thay vì slide cần
chụp; 43/44 tấm ra đen (ảnh nền chưa kịp load). Sửa: bỏ inline `display`, để
cover ăn theo đúng cơ chế `:target` như mọi slide. Render lại đủ 44 tấm, quét
cỡ file không còn tấm nào dưới 20 KB (ngưỡng phát hiện khung đen), soi mắt
cover / slide 10 / slide 12.

**File PPTX giờ là `planbench-deck-final.pptx`** (44 slide vật lý / cover + 12
slide logic, fade toàn bộ, preview nhúng, 22 MB). Hai file cũ
`planbench-deck-v2.pptx` và `planbench-deck-v2-animated.pptx` đều đang bị
PowerPoint của An khoá (PermissionError khi ghi đè) nên không xoá/ghi được —
An đóng PowerPoint rồi xoá hai bản cũ, giữ `-final`.

Đánh số render đổi theo: `FR = @(0,1,3,3,4,4,3,4,2,2,2,3,0)` cho s0..s12.

---

## Bổ sung — dọn PPTX thừa và kịch bản video demo 40 giây

- Xoá `planbench-deck-v2.pptx` và `planbench-deck-v2-animated.pptx` sau khi
  kiểm bản cuối mở được (44 slide). Còn đúng một file: `planbench-deck-final.pptx`.
- Viết `presentation/deck-v2/kich-ban-demo-40s.md` — kịch bản quay màn hình
  40 giây cho slide 05–07: sáu cảnh theo route thật
  (`/deployments` → `/simulate` → `/decisions/[id]`), khớp bốn nhịp
  Tình huống / Can thiệp / Aha / Giá trị của slide 07; chỉ tua nhanh đúng đoạn
  mô phỏng chạy (6–8×, có chữ "tua nhanh" trên hình); checklist chống lộ
  secret/API key khi quay; cách chèn MP4 vào slide 07 của deck sao cho không
  giẫm lên overlay build. Video chưa quay — An quay theo kịch bản, muốn nhúng
  bằng python-pptx thì đưa file MP4.

---

## Bổ sung — thay em-dash bằng hyphen

Theo yêu cầu An: thay toàn bộ em-dash `—` bằng hyphen `-` trong
`deck-v2/planbench-deck-v2.html` (32 chỗ) và `thumbnail/planbench-hook-v2.html`
(3 chỗ); `thumbnail/planbench-thumbnail.html` (cover v1) không có chỗ nào.
**En-dash `–` trong khoảng số (10.000–100.000 USD) giữ nguyên** - yêu cầu chỉ
nói em-dash, và en-dash trong khoảng số là đúng chính tả. Render lại 44 overlay
+ 13 PNG chính + 2 PNG hook-v2, quét không có khung đen, rebuild
`planbench-deck-final.pptx` (44 slide, 44 transition, thumbnail nhúng - kiểm
bằng máy). Soi mắt slide 02: "Dừng chuyền - 10.000–100.000 USD mỗi giờ" đúng ý.

---

## Bổ sung - sửa lỗi "Repaired and removed" khi mở PPTX

**Triệu chứng:** PowerPoint mở `planbench-deck-final.pptx` báo *"couldn't read
some content - Repaired and removed it"*.

**Nguyên nhân (soi ruột zip, không đoán):** template mặc định của python-pptx
**đã có sẵn** relationship thumbnail `rId2 → docProps/thumbnail.jpeg` trong
`_rels/.rels`. Bước nhúng preview hôm qua chèn thêm relationship thứ hai
`rIdThumb → docProps/thumbnail.png` - package mang **hai** relationship cùng
loại `metadata/thumbnail`, PowerPoint coi là hỏng, gỡ phần đó ra.

**Sửa:** không thêm rel nào nữa - convert thumbnail v1 sang JPEG (Pillow,
quality 88) và **thay thẳng ruột** part `docProps/thumbnail.jpeg` có sẵn của
template; `.rels` giữ nguyên như python-pptx viết. Cài `Pillow` 12.3.0 vào môi
trường Python mặc định cho việc convert (gỡ: `pip uninstall Pillow`).

**Kiểm:** đọc lại zip - đúng 1 relationship thumbnail, không còn part
`thumbnail.png` mồ côi, `thumbnail.jpeg` 122 KB là ảnh v1; 44 slide, 44
transition. Kiểm bằng chính PowerPoint qua COM (cửa sổ ẩn):
`Presentations.Open` thành công, đếm đủ 44 slide, không ném lỗi repair.
File chốt vẫn là `planbench-deck-final.pptx` (22 MB).

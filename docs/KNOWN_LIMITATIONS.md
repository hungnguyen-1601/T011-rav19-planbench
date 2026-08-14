# Known Limitations — Agentic AI PlanBench

Cập nhật liên tục. Mỗi mục ghi rõ phạm vi và hướng xử lý.

## Core simulator (M1)

1. **Map cần tường bao.** LiDAR coi vùng ngoài map là "không phản xạ"
   (trả max_range), trong khi collision coi ngoài map là vật cản. Map
   thực tế phải có tường bao (demo và test đều có). Scenario validator
   phía API sẽ cảnh báo map không kín (dự kiến M5).
2. **Origin xoay chưa hỗ trợ** (validator từ chối origin.theta ≠ 0).
3. **Penetration depth xấp xỉ** với rectangle/grid cell (bão hòa tại
   −radius khi tâm robot vào trong vật) — đủ cho phát hiện collision,
   không dùng cho physics response.
4. **Inflation bảo thủ** (radius + √2·resolution) có thể chặn hành lang
   hẹp nhưng vẫn đi được về mặt vật lý trên map resolution thô. Giảm
   resolution map nếu cần hành lang hẹp.
5. **`clearance_to_grid` quét toàn bộ cell** — đủ nhanh cho map thử
   nghiệm; cần distance-field cache nếu map lớn (theo dõi ở M5).
6. **Pure-pursuit chỉ là adapter tạm** (D12) — không xuất hiện trong
   benchmark comparison; DWA thay thế ở M4.
7. ~~**LiDAR không có noise model**~~ — **đã có từ 2026-08-11**
   (contract 6.3.0, HĐ-2.5). `environment.sensor_noise` khai σ tầm quét
   và tỉ lệ trượt bánh, mặc định **0** nên mọi profile cũ giữ nguyên
   hành vi. Xem mục "MVP v1" cuối tài liệu này.
8. **Planning time là wall-clock** — không deterministic (chỉ dùng làm
   metric, không tham gia logic).

## Benchmark, planner và HITL (M4)

9. **Failure-to-progress dùng khoảng cách Euclid tới goal**, nên map cần
   đường vòng dài hơn `progress_time_window` (mặc định 30 s) sẽ bị báo
   `no_progress` sai. Scenario đi vòng phải tự nới cửa sổ này. Cách đo
   theo tiến độ dọc global path cần engine biết path — hoãn lại.
10. **DWA nhìn thế giới qua LiDAR**: vật cản ngoài tầm quét hoặc bị che
    khuất không được xét trong rollout; đây là hành vi đúng của local
    planner nhưng làm kết quả phụ thuộc cấu hình LiDAR — luôn so sánh
    trong cùng `conditions_checksum`.
11. **DWA chưa hỗ trợ lùi** mặc định (`allow_reverse=False`), nên có thể
    kẹt trong ngõ cụt hẹp hơn bán kính quay.
12. **Pure-pursuit stack** (`astar+pure_pursuit`) có `benchmarkable=false`:
    nó bỏ qua cảm biến, chỉ dùng kiểm chứng pipeline. Không dùng để kết luận.
13. **Benchmark chạy đồng bộ trong request**: benchmark lớn sẽ chặn HTTP
    request và không pause/resume được → cần background worker (M5).
14. **Lưu trữ in-memory**: mất toàn bộ map/scenario/benchmark khi restart
    API. Artifact (trajectory, report) vẫn còn trên đĩa nhưng metadata thì
    không → PostgreSQL (M5/M10).
15. **Episode giữ trong RAM để replay**: `StoredEpisode.run` giữ nguyên
    trajectory; benchmark rất lớn sẽ tốn bộ nhớ. Khi có PostgreSQL, replay
    phải đọc lại từ artifact URI.
16. **MLflow**: cần `MLFLOW_ALLOW_FILE_STORE` cho file store (MLflow 3 coi
    file store là maintenance mode); khuyến nghị chạy MLflow server thật.
    `mlflow-skinny` không hỗ trợ backend SQLite phía client.
17. **Chưa có refresh token / logout phía server**: token JWT hết hạn theo
    `PLANBENCH_JWT_TTL_MINUTES` (mặc định 60). Secret sinh ngẫu nhiên mỗi
    process nếu không đặt biến môi trường → restart làm mất phiên.
18. **Rate limiting và upload size limit** chưa triển khai (spec mục 29).

## Dynamic obstacle, scenario library, leaderboard (M5)

19. **LiDAR thấy obstacle động đã rasterize** theo độ phân giải map, nên
    vật cản tròn trông "vuông và to hơn" trong quét. Collision thì dùng
    hình học chính xác — hai lớp này lệch nhau ở mức nửa ô lưới.
20. **`narrow_corridor` (1.5 m)**: DWA mặc định không qua được (stuck),
    dù A* có đường đi. Đây là kết quả benchmark hợp lệ, không phải bug —
    nhưng khi báo cáo phải nói rõ là giới hạn của cấu hình DWA.
21. **`doorway` phải rộng ≥ ~1.4 m**: A* quy hoạch trên grid đã inflate
    `radius + √2·resolution` (0.65 m), nên khe hẹp hơn bị coi là đóng dù
    robot 0.6 m lọt được về mặt vật lý.
22. **Random walk phản xạ về gốc** khi vượt `max_radius`, nên có thể vượt
    biên tối đa một bước (`speed × change_interval`).
23. **Obstacle động luôn là hình tròn** — không có vật cản động đa giác.
24. **Worker chạy in-process**: job mất khi restart API; không có retry.
    Cần message broker thật cho production (M10).
25. **Leaderboard score chỉ là tuỳ chọn**: nhóm theo `conditions_checksum`,
    tuyệt đối không so kết quả khác checksum. Trọng số mặc định
    (0.4/0.3/0.2/0.1) là quy ước, không phải chân lý — luôn xem các cột
    thành phần.

## Reinforcement learning (M6)

26. **Chưa có model PPO đã train**: chỉ có checkpoint smoke 4096 timestep
    (`is_smoke_test=true` trong metadata). Mọi số liệu PPO hiện tại nói
    về pipeline, **không** nói về chất lượng PPO.
27. **Seed chỉ đổi timing của traffic**, không đổi vị trí start/goal hay
    layout map. Muốn đa dạng hơn cần domain randomization (chưa có).
28. **Observation `v1` cố định 35 chiều**: đổi `num_lidar_bins` hay
    `num_waypoints` là đổi encoding → phải bump version, model cũ sẽ bị
    `VersionMismatch` khi load (đúng thiết kế).
29. **Env chỉ chạy đơn luồng**: chưa dùng `VecEnv` song song, nên training
    dài trên CPU rất chậm.
30. **PPO không có safety layer ngoài clamp**: khác DWA, policy không tự
    kiểm tra va chạm trước khi ra lệnh. Trong benchmark điều này công
    bằng (cả hai đều bị simulator phán va chạm), nhưng khi triển khai
    thật phải bọc thêm lớp an toàn.

## ROS2 / Nav2 (M7)

31. **Node ROS phải mượn `.venv` cho pydantic**: system Python không có
    pydantic và không được cài global, nên PYTHONPATH trỏ vào
    `.venv/lib/python3.12/site-packages`. Hoạt động vì cùng CPython 3.12,
    nhưng numpy trong venv (2.5.1) che numpy hệ thống (1.26.4) — chưa gặp
    lỗi nhưng cần theo dõi. Cách sạch hơn: đóng gói core thành ROS package.
32. **Chưa chạy Nav2 trên scenario có vật cản động** — mới kiểm chứng
    `open_space`, `static_obstacles`, `doorway`.
33. **`nav2_status` thường là `unknown`** vì runner thoát ngay khi
    simulator phán quyết (cố ý). Muốn có action result đầy đủ phải chờ
    thêm sau khi episode kết thúc.
34. **Reset cần 3 s settle + clear costmap**; chưa tối ưu, làm benchmark
    nhiều seed chậm hơn cần thiết.
35. **Chưa tích hợp ROS runner vào FastAPI orchestrator** — hiện chạy tay
    bằng `ros2 run`. Spec yêu cầu API → queue → ROS worker (M10).
36. **Chưa có test tự động cho lớp ROS** (`launch_testing`); kiểm chứng
    hiện tại là chạy tay có ghi output.

## Agentic AI (M8)

37. **Chưa provider ngoài nào được gọi thật.** Môi trường này không có
    key nào và chưa cài `anthropic` lẫn `openai`. Toàn bộ test M8 chạy
    với mock tất định, nên chúng kiểm chứng bảo đảm của platform (auth,
    cổng approval, toàn vẹn trích dẫn) chứ **không** kiểm chứng chất
    lượng văn bản của model, và **không** chứng minh adapter nói chuyện
    được với endpoint sống. Dán key rồi chạy
    `scripts/check_agent_provider.py` trước khi tin.
37b. **Adapter OpenAI-compatible đã chạy thật với Gemini** (completion,
    structured output, multi-step tool calling). Multi-step từng hỏng với
    `Function call is missing a thought_signature`; đã sửa bằng cách phát
    lại nguyên văn assistant turn — xem `docs/AGENT_AI.md`. Các hãng còn
    lại (OpenAI, OpenRouter, Groq, DeepSeek, xAI) **vẫn chưa gọi thật**.
37c. **Gemini đi qua endpoint tương thích OpenAI**, không phải API
    native, nên các tính năng ngoài giao thức đó (grounding, safety
    settings, thinking config) chưa dùng được. Thêm adapter native khi
    cần — abstraction đã sẵn cho việc đó.
37d. **`PLANBENCH_AGENT_MODEL` bắt buộc với mọi provider trừ anthropic.**
    Cố ý: model id các hãng đó đổi thường xuyên, hardcode một giá trị
    sớm muộn cũng 404. `auto` bỏ qua provider có key nhưng thiếu model.
38. **Mock provider không hiểu ngôn ngữ.** Nó khớp từ khóa: câu nào
    không chứa tên scenario trong thư viện thì bị từ chối. Đây là hành
    vi đúng khi thiếu key, không phải một agent thay thế.
39. **Agent không đề xuất được `astar+ppo`** vì stack này cần
    `model_path`. Muốn benchmark PPO phải tạo qua endpoint thường.
40. **RAG không dùng embedding.** TF-IDF trên section Markdown: bắt được
    trùng từ khóa, không bắt được diễn đạt khác nghĩa tương đương. Đổi
    lại là tất định, offline, và mỗi chunk có source id ổn định.
41. **Corpus index một lần lúc khởi động.** Tài liệu sửa khi server đang
    chạy sẽ không được phản ánh cho tới lần restart.
42. **Phiên agent không được lưu.** `AgentSession` sống trong một
    request; không có lịch sử hội thoại nhiều lượt phía server (client
    tự truyền `history`). Sẽ cần bảng riêng khi có PostgreSQL.
43. **Kiểm tra "không kết luận an toàn" là heuristic.** `contains_safety_claim()`
    bắt các cụm phổ biến bằng regex; một câu diễn đạt vòng vo vẫn có thể
    lọt. Lớp bảo vệ thật là: reviewer là người quyết định, và mọi báo
    cáo đều gắn disclaimer.

## Frontend / 2.5D (M9)

44. **Không dùng Three.js — quyết định có chủ đích, không phải nợ.**
    Spec liệt kê Three.js/R3F trong tech stack; sau khi cân nhắc,
    **người dùng chọn giữ Canvas 2D** (2026-07-30). Với occupancy grid
    đùn lên, cảnh là vài nghìn quad lồi có thứ tự độ sâu toàn phần nên
    painter's algorithm cho kết quả *chính xác*, không cần depth buffer
    và không thêm dependency. Đánh đổi: không có occlusion culling
    (mục 45) và không có ánh sáng/bóng đổ. Hình học đã tách sẵn
    (`lib/scene25d.ts`) nên đổi renderer về sau chỉ sửa một file — xem
    `docs/FRONTEND.md`.
45. **2.5D không có occlusion culling.** Mọi ô đều được vẽ, kể cả ô bị
    tường trước che hoàn toàn. Với map hiện tại (48×36) không thấy chậm;
    map lớn hơn nhiều sẽ cần cắt bớt hoặc chuyển sang WebGL.
46. ~~**Replay chỉ hiện khung cuối, chưa có timeline scrub.**~~ Đã xong
    (F08, 2026-08-07): replay episode đã lưu có play/pause, scrubber,
    tốc độ 0.25×–8×, robot chạy theo frame, trajectory vẽ tới playhead,
    vật cản động vẽ theo snapshot từng frame (view 2D), điểm va chạm
    đánh dấu trên timeline. Hook `useTrajectoryPlayback` tách riêng
    khỏi stream WebSocket của `/simulate`.
47. **Vật cản động không hiện trong 2.5D.** Snapshot vị trí vật cản có
    trong `TrajectoryPoint.obstacles`; view 2D top-down của replay đã
    vẽ theo playhead (F08), nhưng renderer `Scene25D` vẫn chưa dùng —
    2.5D chỉ vẽ map tĩnh, plan, trajectory và robot.
48. **Chưa có endpoint model registry.** `/algorithms` hiển thị registry
    stack (gồm `astar+ppo` và `model_path` nó đòi), nhưng danh sách
    checkpoint đã train thì chưa có API — metadata mới nằm ở file sidecar
    cạnh checkpoint.
49. **Agent console không lưu hội thoại.** Mỗi lượt độc lập; `history`
    chưa được truyền lại. Cần bảng riêng khi có PostgreSQL.
50. **Chưa có test render cho component.** Vitest phủ phần hình học
    thuần (`scene25d`, `transform`, `playback`, `demoMap`); component
    React kiểm chứng bằng `tsc`, `next build` và chạy thật, chưa có
    jsdom + Testing Library.

## Persistence / Docker (M10)

51. **Chưa build image nào, chưa `docker compose up` lần nào.** Docker
    CLI có trong WSL distro này nhưng daemon không dùng được (chưa bật
    WSL integration trong Docker Desktop). `docker-compose.yml` mới chỉ
    được kiểm bằng parse YAML — chưa có gì chứng minh image build được.
52. **Chưa kết nối PostgreSQL thật.** Mọi test SQL chạy trên SQLite.
    SQLite **không** chứng minh: JSONB, transaction đồng thời, connection
    pool, hay hành vi cascade dưới dialect production.
53. **`psycopg` chưa cài trong `.venv`** (image có trong
    `docker/requirements-api.txt`). Chạy local với `postgresql://` phải
    cài trước; code báo `DatabaseUnavailable` kèm đúng lệnh.
54. **Artifact tham chiếu bằng URI tuyệt đối** (`file:///data/...`). Đổi
    `PLANBENCH_ARTIFACT_DIR` sau khi đã ghi dữ liệu sẽ làm hỏng URI đã
    lưu. Chưa có lệnh rewrite.
55. **Backup phải làm database + artifact cùng nhau.** Restore lệch nhau
    cho một database đầy episode mà replay nào cũng 404.
56. **Chưa có connection retry lúc khởi động.** Nếu database chưa sẵn
    sàng, API chết ngay. Compose xử lý bằng `depends_on: service_healthy`,
    ngoài compose thì cần supervisor restart.
57. **API image không có torch/stable-baselines3** (cố ý: thêm vài GB
    cho code API không chạy). Hệ quả: **stack `astar+ppo` không chạy
    được từ image này**; training là workload riêng.
58. **Chưa có index cho truy vấn theo thời gian.** `created_at` là chuỗi
    nên `ORDER BY` vẫn đúng, nhưng hàm ngày tháng SQL cần cast.

## Accounts, OAuth và review (M11)

59. **Chưa gọi Google hoặc GitHub thật lần nào.** Toàn bộ luồng OAuth
    được test bằng provider giả trả về đúng payload mà Google/GitHub
    gửi, và `normalise_identity` được test riêng trên các payload đó.
    Cái test này **không** chứng minh được: endpoint thật vẫn nói đúng
    shape ấy, client id/secret thật hợp lệ, và callback URL đã đăng ký
    khớp. Ba thứ đó chỉ biết khi bấm nút lần đầu với key thật. Đây là
    lựa chọn có chủ ý — quy tắc "không gọi OAuth thật trong automated
    test" nằm trong yêu cầu.
60. **Exchange code lưu in-memory.** Code dùng một lần đổi lấy JWT sống
    vài giây và nằm trong RAM của tiến trình. Deploy nhiều worker cần
    sticky routing, hoặc chuyển sang store dùng chung (Redis). Mất khi
    restart chỉ có nghĩa là đăng nhập lại.
61. **Chưa có refresh token.** Hết hạn `PLANBENCH_JWT_TTL_MINUTES` là
    phải đăng nhập lại.
62. **Chưa có gộp tài khoản.** Nếu lỡ tạo hai tài khoản (Google một cái,
    GitHub một cái) thì không có cách gộp — chỉ liên kết được provider
    thứ hai vào tài khoản đang dùng khi provider đó **chưa** thuộc về ai.
    Cố tình như vậy: gộp hai lịch sử là thao tác không thể hoàn tác.
63. **Chưa có UI đổi nickname sau onboarding.** API (`PUT
    /users/me/nickname`) có sẵn và có test; frontend chỉ hiện màn hình
    chọn tên lần đầu.
64. **Chưa có UI liên kết provider thứ hai.** Endpoint
    `POST /auth/oauth/{provider}/link` có sẵn và có test end-to-end;
    chưa có nút trong giao diện.
65. **Badge Review Inbox poll mỗi 30 giây**, không phải realtime. Đủ cho
    quy mô hiện tại; WebSocket là bước sau nếu cần.
66. **Không có test render component.** Frontend chỉ có unit test cho
    logic thuần (session store, `canRun`/`canAcceptResult`). Các trang
    được kiểm chứng bằng `tsc --noEmit` và `next build`, không phải bằng
    test render — nên "nút hiện đúng lúc" được chứng minh ở tầng
    helper + API, không phải ở tầng DOM.
67. **Admin không bị chặn bởi review đang chờ.** Đó là điểm của admin
    (gỡ kẹt khi người duyệt đã nghỉ), và mọi hành động đều vào audit
    trail kèm user ID. Nghĩa là: một owner đồng thời là admin *có thể*
    tự duyệt review của chính mình. Ai được là admin do
    `PLANBENCH_ADMIN_NICKNAMES`/`PLANBENCH_ADMIN_EMAILS` quyết định, nên
    đừng đặt member thường vào đó.
68. **Fallback quyền sở hữu cho dữ liệu cũ dựa trên nickname.**
    Benchmark tạo trước refactor không có `owner_user_id`; với riêng
    những row đó, hệ thống so `created_by` với nickname người gọi. Yếu
    hơn so ID, nên chỉ áp dụng ở nơi không có ID. Nếu người tạo cũ đã
    đổi tên và người khác lấy nickname đó, người mới sẽ sở hữu benchmark
    cũ. Cách xử lý dứt điểm: một migration điền `owner_user_id` khi đã
    biết ánh xạ tên → tài khoản.

## Giao diện: shell, theme, i18n (M12)

69. **Không có test render tương tác.** `@testing-library/react` và
    `jsdom` chưa được cài, nên component được kiểm bằng
    `renderToStaticMarkup` — HTML thật, nhưng chỉ là **lần render đầu**.
    Điều đó bao phủ được mọi khác biệt mà đề bài hỏi (thu gọn / mở rộng,
    đăng nhập / chưa, có badge / không, EN / VI) vì chúng đều là khác
    biệt ở lần render đầu. Cái nó **không** bao phủ: bấm nút. Hành vi
    đằng sau mỗi control vì thế được test ở tầng store
    (`sidebar.test.ts`, `theme.test.ts`, `persisted.test.ts`). Muốn test
    tương tác thật thì cần thêm dev dependency — chưa cài vì chưa được
    duyệt.
70. **Chưa kiểm bằng trình duyệt thật ở nhiều kích thước.** Responsive
    được viết bằng breakpoint CSS (900px, 560px) và đã kiểm qua HTML
    server-render, **không** phải bằng cách mở trình duyệt ở 320/375/768/
    1024/1440 px. Không có công cụ chụp màn hình trong môi trường này.
71. **Layout root giờ là dynamic.** Đọc cookie locale trong server
    component làm mọi trang chuyển từ prerender tĩnh sang render theo
    yêu cầu (`ƒ` thay vì `○` trong output build). Với app này không mất
    gì — mọi trang đều fetch API lúc mount — nhưng đó là một thay đổi có
    thật trong đặc tính build.
72. **Có thể nháy sai theme trong một trường hợp**: trình duyệt chặn
    localStorage (Safari private mode). Script chặn render nuốt lỗi và
    trang paint theo mặc định của hệ thống. Không sửa được nếu vẫn dùng
    localStorage.
73. **Thư viện icon là bộ inline tự vẽ**, không phải `lucide-react`.
    Không thêm dependency nào. Đổi sang Lucide sau này là find-and-replace
    (cùng quy ước 24×24, nét 2px).
74. **Badge Review Inbox poll 30 giây**, không realtime (đã ghi ở #65).
75. **Số liệu Dashboard ghép ở client** từ các endpoint sẵn có, không có
    endpoint `/dashboard/summary`. Với lượng dữ liệu hiện tại thì đúng;
    khi danh sách benchmark đủ lớn để phải phân trang, đếm ở client sẽ
    sai và lúc đó endpoint tổng hợp phía server mới xứng đáng tồn tại.
76. **Một phần dữ liệu hỏng vẫn hiện phần còn lại.** Card nào không tải
    được hiện `—` chứ không hiện `0`, và có dòng cảnh báo — nhưng nó
    không nói *cái nào* hỏng. Đủ để không hiểu sai, chưa đủ để chẩn đoán.

## Model Registry và trợ lý hội thoại (M13)

### Bảo mật model upload — đọc kỹ phần này

77. **Model upload KHÔNG được chạy trong sandbox container.** Đây là hạn
    chế quan trọng nhất của M13 và không được che giấu. Những gì *đã*
    làm được:

    - Kiểm tra phần mở rộng **trước khi ghi byte đầu tiên**; chỉ chấp
      nhận `.zip` (model), `.json` (metadata), `.pdf` (tài liệu).
    - Kiểm tra **magic bytes** (`PK\x03\x04`), `zipfile.testzip()`, và
      sự có mặt của các thành viên SB3 (`data`, `policy.pth`).
    - Làm sạch tên file: mọi dấu phân cách bị loại, `../../etc/passwd`
      trở thành `passwd`. Đường dẫn lưu trữ **dựng hoàn toàn từ ID**,
      không lấy từ tên file.
    - Giới hạn kích thước **cưỡng chế trong lúc ghi**, không phải sau.
    - SHA-256 của đúng byte đã ghi.
    - **Không `pickle.load` trong tiến trình API.** Việc kiểm tra ở web
      process chỉ đọc *bảng mục lục* của zip — không giải tuần tự.

    Những gì **chưa** làm được:

    - Không có container, không có seccomp, không có namespace riêng.
    - Không có giới hạn CPU/RAM cho tiến trình nạp model.
    - Không có timeout cứng khi nạp.

    Hệ quả cụ thể: **khi một benchmark PPO thật sự chạy**, checkpoint
    được `torch.load` trong tiến trình worker của benchmark. Một file
    `.zip` độc hại có thể thực thi code ở đó với quyền của tiến trình
    đó. Trạng thái `structural` nghĩa là *"cấu trúc đúng"*, không phải
    *"an toàn"* — sự phân biệt này là lý do hai trạng thái tồn tại
    riêng (`structural` vs `loaded`).

    **Không được kết luận model upload là an toàn tuyệt đối.** Ở triển
    khai nhiều người dùng không tin nhau, hãy chạy worker benchmark
    trong container riêng với quota, hoặc chỉ cho phép upload từ tài
    khoản đã được kiểm duyệt.

78. **Tách tiến trình mới ở mức "khác tiến trình web", chưa phải cách
    ly thật.** Benchmark chạy trong worker riêng nên API process không
    bao giờ giải tuần tự file người dùng; nhưng worker vẫn cùng máy,
    cùng user, cùng filesystem.

79. **`validation_status` không bao giờ tự lên `loaded`.** Muốn biết
    chắc checkpoint nạp được thì phải nạp nó, và điều đó chỉ xảy ra khi
    người dùng chạy benchmark thật. Nút "Validate" chỉ kiểm tra lại
    cấu trúc và checksum — nó nói đúng những gì nó làm.

### Model, robot profile, tương thích

80. **Chỉ hỗ trợ Stable-Baselines3.** `SUPPORTED_FRAMEWORKS` có đúng một
    phần tử. Model của framework khác upload được nhưng bị đánh dấu
    không tương thích, kèm câu giải thích.

81. **Observation encoding do người upload khai báo, không tự phát
    hiện được.** Không có cách nào đọc ra từ file `.zip` xem policy được
    huấn luyện với bố cục quan sát nào. Nếu metadata không khai
    `observation.version`, hệ thống ghi **cảnh báo** (không từ chối) và
    khi chạy sẽ giả định phiên bản hiện hành. Một policy huấn luyện với
    bố cục khác sẽ nhận đầu vào vô nghĩa mà vẫn "chạy được" — đây là lý
    do cảnh báo tồn tại chứ không im lặng.

82. **Không có UI huấn luyện model.** PlanBench hiện chỉ *đánh giá*
    model PPO đã huấn luyện. Không có nút "Train" giả, không có thanh
    tiến trình giả — vì chưa có job huấn luyện thật đứng sau.

83. **Storage backend production chưa viết.** `ModelStorage` là
    interface có sẵn cho S3/R2, nhưng chỉ `LocalModelStorage` được cài
    đặt và chạy thử. Chuyển sang object storage là viết thêm một lớp,
    không phải sửa lời gọi.

84. **Xóa model bị chặn khi đã có benchmark dùng nó.** Đúng về mặt bằng
    chứng (một kết quả phải luôn truy được về model đã tạo ra nó), nhưng
    nghĩa là registry chỉ lớn thêm. Chưa có cơ chế lưu trữ nguội.

85. **Benchmark cũ dùng `model_path` vẫn đọc được nhưng không nâng cấp
    tự động.** Chuyển chúng sang `model_id` đòi hỏi đoán xem file trên
    đĩa ứng với model nào — chính là điều registry sinh ra để chấm dứt.

### Trợ lý hội thoại

86. **Trợ lý không chạy benchmark, và đó là thiết kế chứ không phải
    thiếu sót.** Không tồn tại endpoint `/ai/**` nào chạy, duyệt, chấp
    nhận hay từ chối kết quả — kiểm chứng bằng test đọc `openapi.json`.
    Ghi write duy nhất là tạo **bản nháp**.

87. **Trợ lý hiểu ý định bằng khớp từ khóa, không phải bằng LLM.**
    `chat_service` nhận diện stack và seed bằng luật. Đơn giản, xác
    định, không gọi mạng — nhưng nó sẽ không hiểu câu hỏi diễn đạt lạ.
    Đường dẫn LLM (Gemini và các provider khác) vẫn còn nguyên trong
    backend, chỉ bị ẩn khỏi giao diện người dùng.

88. **Nút Stop hủy ở phía client.** Nó bỏ qua phản hồi đang bay chứ
    không hủy công việc phía server. Với các phản hồi hiện tại (mili
    giây, không gọi mạng) sự khác biệt không quan sát được, nhưng nó là
    khác biệt thật.

89. **Lịch sử hội thoại chưa có UI liệt kê.** Backend lưu và trả về đầy
    đủ; giao diện hiện chỉ có "Cuộc trò chuyện mới".

## Lưu trữ (kiểm chứng 2026-08-03)

90. **Mặc định của một checkout mới là KHÔNG lưu gì.** `.env.example`
    từng ship `PLANBENCH_DATABASE_URL=` rỗng, mà "đặt bằng rỗng" khác
    "không đặt": nó chọn thẳng backend trong bộ nhớ, và không migration
    nào chạy. Đã sửa — dòng đó nay để dạng chú thích, và `dev_stack.sh`
    cảnh báo rõ khi rơi vào chế độ không lưu. Nhưng ai đã trót copy
    `.env.example` cũ thì vẫn phải tự sửa `.env` của mình.

91. **SQLite chỉ dùng được cho một tiến trình.** Đủ cho phát triển và
    demo. Nhiều worker ghi song song sẽ gặp `database is locked`; triển
    khai thật phải dùng PostgreSQL.

92. ~~**Vẫn chưa chạy PostgreSQL thật.**~~ **Đã gỡ.** Hai lần chạy độc
    lập, ghi lại ở đây vì chúng kiểm chứng hai thứ khác nhau:

    - **2026-08-03** — migration 0001–0003 chạy trên PostgreSQL 17 trong
      Docker (`PostgresqlImpl`, 16 bảng, `alembic_version = 0003`), toàn
      bộ stack build và chạy thật. Kiểm chứng độ bền bằng cách **xóa hẳn
      container API** rồi tạo lại: dữ liệu vẫn còn. Xem TEST_REPORT.md.
    - **2026-08-05** — chạy lại từ `docker compose` sạch và thêm phần
      end-to-end: một benchmark 2 stack × 5 seed chạy trọn trong
      container, dữ liệu ghi xuống PostgreSQL. Xem
      `docs/antongduy/reports/2026-08-05/tongduyan_docker-compose-chay-that.md`.
      (Lần này đếm 10 bảng — khác con số 16 ở trên vì đếm ở thời điểm
      khác và chưa đối chiếu; không quan trọng với kết luận, nhưng ghi ra
      để không ai tưởng hai lần chạy mâu thuẫn nhau.)

    Lần chạy đầu bắt được một lỗi mà không lần test nào phát hiện được:
    `PLANBENCH_MODEL_DIR` mặc định là đường dẫn *tương đối*
    (`artifacts/models`), giải ra `/app/artifacts` trong container — thư
    mục của root, trong khi tiến trình chạy bằng user `planbench`. API
    chết lúc khởi động với `PermissionError` trước khi phục vụ được
    request nào. `docker-compose.yml` khai `PLANBENCH_ARTIFACT_DIR` từ
    M10 nhưng chưa ai thêm `PLANBENCH_MODEL_DIR` khi M13 sinh ra nó. Đã
    sửa.

93. **Mất thư mục artifact là mất replay, dù database còn nguyên.**
    Trajectory và report nằm ngoài database (quyết định D15); bảng chỉ
    giữ URI + checksum. Phải backup `planbench.db` **và** `artifacts/`
    cùng nhau.
94. **RRT\* chỉ tái lập được khi biết cả hai seed.** Cây được sinh từ
    `RRTStarConfig.seed` **trộn với seed episode**; chạy lại đúng cặp seed
    đó ra đúng đường cũ, nhưng một `PlanResult` đứng riêng không nói được
    nó thuộc cây nào. Muốn tái lập phải giữ nguyên cả spec lẫn seed list.
95. **Một lần chạy RRT\* không kết luận được gì.** Nó là thuật toán ngẫu
    nhiên: hai seed cho hai đường khác nhau, khác cả độ dài. Chỉ đọc qua
    phân phối nhiều seed (P04 sẽ cho median/IQR/CI). UI đánh dấu stack
    `stochastic_global_planner=true`, nhưng không cưỡng chế số seed tối
    thiểu.
96. **Config của global planner chưa vào `BenchmarkSpec`.** `AlgorithmSpec.config`
    chỉ cấu hình local planner; RRT\* luôn chạy mặc định (3000 iteration,
    step 0.5 m). Vì vậy `config_schema` trên `/algorithms` cũng chỉ là
    schema của local planner. Hệ quả: chưa tune được RRT\* — đó là phần
    việc của P01.
97. **RRT\* đắt hơn A\* nhiều lần trên cùng bản đồ.** Nó chạy hết ngân
    sách iteration kể cả khi đã tìm ra đường (đổi lấy tính tối ưu tiệm
    cận), nên `global_planning_time` giữa hai stack lệch nhau theo bản
    chất thuật toán, không phải do cấu hình bất công.

## Docker Compose (kiểm chứng 2026-08-05)

98. **`AUTH_SECRET` rỗng làm mọi người bị đăng xuất sau mỗi lần restart
    API.** `docker-compose.yml` nói rõ điều này, nhưng `.env.example`
    vẫn ship giá trị rỗng nên trạng thái mặc định của một máy mới là
    "token chết sau mỗi `docker compose up --build api`". Trong lúc
    kiểm chứng Đợt 0.2, mỗi lần rebuild `api` là phải đăng nhập lại.
    Không phải lỗi, nhưng là cái bẫy chắc chắn gặp khi demo.

99. **Vai trò cũ trong audit trail phải được giữ trong `Role` mãi mãi.**
    Dữ liệu từ lần chạy Docker trước (2026-08-02) có `role='engineer'`
    và `role='approver'` trong bảng `approvals`; enum `Role` sau refactor
    không còn hai giá trị đó, nên **mọi** endpoint gọi
    `repos.benchmarks.list()` (danh sách benchmark, leaderboard) trả 500.
    Đã sửa bằng cách giữ lại hai giá trị legacy trong enum thay vì viết
    migration ghi đè lịch sử. Hệ quả cần nhớ: đổi tên vai trò trong
    tương lai **không được** xóa giá trị cũ khỏi enum.

100. **Cấu hình đường dẫn tương đối trong container là bẫy quyền ghi.**
    `model_dir` từng mặc định `"artifacts/models"` độc lập với
    `artifact_dir`; trong image, `WORKDIR /app` thuộc root còn tiến
    trình chạy dưới user `planbench`, nên `mkdir artifacts` ném
    `PermissionError` **lúc import**, tức API chết ngay khi khởi động.
    Đã sửa: `model_dir` rỗng nghĩa là `<artifact_dir>/models`. Bất kỳ
    setting đường dẫn nào thêm sau này phải bám theo `artifact_dir`
    hoặc được set tường minh trong compose.

101. **Volume `planbench_db-data` và `planbench_artifacts` sống lâu hơn
    `docker compose down`.** Chúng được tạo 2026-08-02 và vẫn còn nguyên
    dữ liệu ở lần chạy 2026-08-05 — chính chỗ này để lộ lỗi #99. Muốn
    kiểm chứng "máy sạch" phải `docker compose down -v`, và ngược lại,
    dữ liệu benchmark cũ **không** mất khi rebuild image.

## Cân bằng thông tin — P02 (2026-08-06)

102. **Lớp quan sát là lời khai, không phải cơ chế cưỡng chế.**
    `global_observation_class` / `local_observation_class` do registry
    khai báo; nền tảng không chứng minh được một planner thật sự chỉ đọc
    đúng chừng đó — planner là code tùy ý, nó có thể import thẳng
    scenario. Cái nền tảng làm được: (a) `Observation` không mang vị trí
    ground-truth của vật cản, (b) `LocalPlanner.compute()` chỉ nhận
    `(state, observation)`, (c) hai test chống hồi quy khóa hai điều
    trên lại, (d) leaderboard không xếp chung hai lớp khai báo khác
    nhau. Khai sai vẫn qua được — đó là lý do phải review khi thêm stack.

103. **Aggregate cũ (trước P02) không có bản chụp khai báo.** Ba trường
    mới nullable. Leaderboard tra ngược registry cho stack còn tồn tại,
    còn stack đã bị gỡ tên thì hiện "không rõ" và **không** được coi là
    cùng lớp với bất cứ dòng nào. Cố đoán ở đây chính là thứ P02 sinh ra
    để chặn.

104. **Hiện mọi stack đều `full_static_map` + `lidar_only`,** nên việc
    tách nhóm chưa đổi hình dạng leaderboard trên dữ liệu thật. Đường đi
    tách nhóm được kiểm bằng test dựng aggregate lớp
    `lidar+human_states`, chưa bằng một planner thật đọc human states —
    sẽ chỉ kiểm được thật khi có stack như vậy.

105. **`requires_global_path` hiện luôn `true`.** Trường tồn tại cho
    policy end-to-end sau này; chưa có stack nào bỏ qua đường toàn cục
    nên nhánh `false` chưa từng chạy trong production.

## Thống kê đánh giá — P04 (2026-08-06)

106. **Chỉ so trung vị của thuật toán dẫn đầu với từng thuật toán còn
    lại, không phải mọi cặp.** Với 2–3 stack thì hai cách là một; khi có
    nhiều stack hơn, bảng hiện tại không trả lời được "B so với C".
    Schema `PairwiseComparison` là danh sách cặp độc lập nên mở rộng
    được, nhưng **chưa** hiệu chỉnh đa so sánh (Bonferroni/Holm) — chạy
    nhiều kiểm định trên cùng dữ liệu làm tăng xác suất dương tính giả.
    Ai bật full pairwise phải quyết định hiệu chỉnh trước.

107. **Ngưỡng "đủ dữ liệu" 30 seed là quy ước, không phải tính toán
    power.** `ADEQUATE_SEED_COUNT = 30` không được suy ra từ effect size
    mong muốn và độ lệch thực tế của từng scenario. Nó là ngưỡng cảnh
    báo, không phải bảo đảm rằng 30 seed đủ cho mọi so sánh.

108. **Dưới 5 cặp thì không chạy kiểm định.** `MIN_PAIRS_FOR_TEST = 5`:
    với 3–4 cặp, p-value nhỏ nhất mà Wilcoxon có thể trả vẫn lớn hơn
    0.05, nên "không có ý nghĩa thống kê" chỉ phản ánh cỡ mẫu. Hệ quả:
    benchmark nhỏ trả `p_value=null` chứ không phải một con số.

109. **Bootstrap dùng seed cố định 0.** Cùng dữ liệu cho cùng khoảng tin
    cậy — điều kiện để hai người đọc cùng report trích cùng số. Đổi lại,
    khoảng tin cậy này là **một** lần lấy mẫu chứ không phải trung bình
    trên nhiều lần bootstrap; với n rất nhỏ, khoảng có thể hẹp một cách
    lạc quan.

110. **`travel_time` chỉ ghép cặp trên seed mà cả hai stack cùng về
    đích.** Đây là lựa chọn có chủ ý (thời gian di chuyển vô nghĩa với
    robot không tới nơi), nhưng nó tạo thiên lệch: stack chỉ thành công
    ở các seed dễ sẽ được so trên đúng tập seed dễ đó. Số cặp và số seed
    bị loại luôn đi kèm kết quả, nhưng **người đọc phải tự trừ hao** —
    hệ thống không tự điều chỉnh.

111. **`average_rank_score` chưa được nối vào leaderboard hay report.**
    Hàm đã có, đã test, nhưng xếp hạng trung bình qua nhiều scenario cần
    quyết định về cách chọn tập scenario — thuộc P03/P05, chưa làm.

## Tập held-out và tổng quát hóa (P05)

112. **Tập holdout do người chọn, chưa hiệu chuẩn thực nghiệm.**
    `bidirectional_corridor`, `intersection`, `dynamic_warehouse` được
    chọn vì đòi hỏi hành vi không scenario dev nào thưởng (nhường đường,
    giao cắt vuông góc, nhiều vật cản khác mô hình chuyển động cùng lúc)
    — lý do ghi trong `scenario_protocol.json`. Nhưng cả ba cũng nằm
    cuối thang độ khó, nên **chưa loại trừ được** khả năng chênh lệch
    dev/holdout phản ánh độ khó chứ không phải khả năng tổng quát hóa.
    Chỉ P03 (hiệu chuẩn độ khó) mới tách được hai nguyên nhân này.

113. **Chênh lệch tổng quát hóa là hiệu của hai trung bình, không phải
    kiểm định.** Không có p-value, không có khoảng tin cậy cho chính
    chênh lệch. Với 3 scenario mỗi phía, chưa đủ để nói chênh lệch bao
    nhiêu là đáng kể. Số scenario mỗi phía và cờ đủ seed luôn hiện, và
    coverage lệch bị cảnh báo, nhưng **người đọc phải tự trừ hao**.

114. **Scenario có trọng số bằng nhau, không theo số episode.** Trung
    bình trong từng scenario trước rồi mới trung bình qua các scenario.
    Lựa chọn có chủ ý (chạy một scenario 10 lần không được lấn át), đổi
    lại một scenario chạy 1 seed có cùng tiếng nói với scenario chạy 30
    seed.

115. **`generalization_gap` trên `BenchmarkReport` luôn `null`.** Một
    benchmark chạy đúng một scenario nên thuộc trọn một split. Trường
    tồn tại để benchmark nhiều scenario sau này không phải phá schema;
    hiện tại chênh lệch chỉ có ở `GET /generalization`.

116. **MVP không chặn việc chạy holdout nhiều lần.** UI cảnh báo trước
    khi tạo, mỗi lần chạy được ghi log và liệt kê trong
    `holdout_usage[]`, có cảnh báo khi đã chạy hơn một lần — nhưng không
    có giới hạn cứng và không có "ngân sách lần xem". Tập held-out mòn
    dần theo số lần được xem; hệ thống chỉ làm việc mòn đó **đếm được**,
    không ngăn được.

117. **Không có đường chuyển split trong ứng dụng.** Đổi phân loại phải
    sửa `scenario_protocol.json` + review + deploy. Cố ý (không ai được
    đổi split sau khi thấy kết quả), nhưng nghĩa là scenario tạo trong
    app đứng mãi ở `unassigned` cho tới lần release sau, và kết quả trên
    chúng không vào được chênh lệch tổng quát hóa.

118. **Chỉ ba metric được so giữa hai split**: success rate, trung vị
    thời gian di chuyển, trung vị hiệu quả đường đi. Clearance, độ mượt
    và latency chưa có mặt.

## Hiệu chuẩn độ khó (P03)

119. **Thang độ khó hiện tại lưỡng cực, gần như không có khoảng giữa.**
    Đo thật với `astar+dwa`, 30 seed, replanning tắt (calibration
    `1.0.0`): 5 scenario ở 0.000, 1 scenario ở 0.267
    (`crossing_obstacle`), 4 scenario ở 1.000 (`narrow_corridor`,
    `sudden_stop`, `bidirectional_corridor`, `dynamic_warehouse`). Dải
    trải 0.000–1.000 nhưng **rỗng ở giữa**: hầu như không có scenario nào
    phân biệt được hai stack đều khá. Đây là việc của Scenario Editor
    (Đợt 2.3) — tạo scenario lấp khoảng 0.2–0.8, **không** sửa tay cache.
    Lưu ý: biên độ (`spread`) của bộ này là 1.000, tức điểm tối đa —
    nên `difficulty_coverage()` phải kiểm thêm `midrange_count` (số
    scenario trong `(0.2, 0.8)`, hiện là **1**) mới thấy được vấn đề.

120. **Bốn scenario baseline chưa từng giải được** nên độ khó bị ghim ở
    1.0 và **không xếp thứ tự với nhau được**: không nói được cái nào khó
    hơn cái nào. Vì vậy `unsolved` là một band riêng, không gộp vào
    `hard`. Cũng có nghĩa là thang đo đang bị chặn trên bởi năng lực của
    baseline, chứ không phải bởi bản thân scenario.

121. **Curriculum order và độ khó đo được lệch nhau rõ rệt.**
    `intersection` (vị trí 8/10 trong curriculum, được viết như một
    scenario khó) đo ra 0.033 — dễ; `narrow_corridor` (vị trí 3) và
    `sudden_stop` (vị trí 6) đo ra 1.000. Curriculum order là **dự định
    của người viết** và hiện chưa được cập nhật theo số đo; hai cột nằm
    cạnh nhau trong UI đúng để chỗ lệch này nhìn thấy được. Thứ tự
    curriculum của PPO vẫn đang dùng bản cũ.

122. **Một baseline duy nhất định nghĩa toàn bộ thang.** Độ khó là
    `1 - success_rate(astar+dwa)`, nên nó đo "khó với A*+DWA", không phải
    "khó nói chung". Một scenario khó với DWA có thể dễ với planner
    khác. Muốn thang đo ít phụ thuộc một stack thì cần nhiều baseline —
    chưa làm, và sẽ là một calibration version khác.

123. **Replanning tắt trong calibration `1.0.0`.** Khi replanning được
    triển khai (Đợt 4), phần lớn scenario 1.000 có thể tụt xuống. Lúc đó
    phải tạo calibration version mới, **không ghi đè** cache cũ, vì hai
    thang đo dưới hai chế độ khác nhau không so được với nhau.

124. **Cache chỉ phát hiện được scenario đổi, không tự đo lại.** Entry
    lưu `map_checksum` + `scenario_checksum`; scenario đổi thì label trả
    về `stale=true` và UI gắn cờ, nhưng số cũ vẫn hiện cho tới khi có
    người chạy lại script. Đổi code planner hoặc simulator thì **không**
    bị bắt — chỉ có `git_sha` trong baseline để đối chiếu bằng mắt.

125. **Độ khó chưa nối vào leaderboard.** Từ 3.1 đã có đường cong
    `success_rate(difficulty)` trên trang leaderboard và một dòng độ khó
    trong report Markdown, nhưng **thứ hạng** vẫn không tính đến độ khó:
    hai stack xếp cạnh nhau trong một nhóm có thể đã chạy các scenario
    dễ khác nhau, và `overall_score` không biết điều đó.

126. **Calibration chạy trên cả scenario holdout** (3 lần "nhìn" vào tập
    held-out, script có in cảnh báo). Không tránh được — không đo thì
    không biết tập holdout nằm ở đâu trên thang — nhưng đây là chi phí
    thật, và nó **chưa** được ghi vào `holdout_usage[]` của
    `GET /generalization` vì calibration không tạo benchmark lưu trữ.

## Scenario Editor (2.3)

127. **Engine chỉ trả lỗi hợp lệ đầu tiên.** `load_scenario` raise ngay
    ở lỗi đầu, nên một scenario có cả start lẫn goal nằm trong tường chỉ
    hiện một lỗi; sửa xong mới thấy lỗi tiếp theo. `errors[]` là danh
    sách để sau này trả được nhiều lỗi, hiện tại luôn có 0 hoặc 1 phần
    tử.

128. **Form chỉ tạo được vật cản động kiểu `waypoint`.** Schema có thêm
    `periodic`, `random_walk`, `sudden_stop`; scenario đã có các kiểu đó
    (nhập từ thư viện) vẫn sửa được tên/bán kính/độ lệch seed và vẫn
    preview đúng, nhưng **không đổi được quy luật chuyển động** trong
    UI. Ô tốc độ bị khóa với các kiểu không phải waypoint.

129. **Không kéo chuột để xoay heading.** Heading nhập bằng số (độ). Cố
    ý cắt theo plan; hệ quả là đặt hướng chính xác thì được, mà cảm giác
    trực quan thì không.

130. **Không có version history cho scenario.** `PUT` ghi đè và tăng
    `version`, không giữ bản cũ. Benchmark đã chạy vẫn an toàn (chúng
    lưu snapshot điều kiện), nhưng **không hoàn tác được** một lần sửa.

131. **Không có khóa khi hai người cùng sửa.** `PUT` cuối cùng thắng,
    không cảnh báo. Chưa phải vấn đề ở quy mô hiện tại, sẽ là vấn đề khi
    nhiều người cùng dùng.

132. **Preview là một seed, một thời điểm.** Thanh trượt cho xem từng
    thời điểm nhưng mỗi lần chỉ một seed; không có cách xem "vùng vật
    cản có thể đi qua" trên toàn bộ tập seed. Người dùng dễ đặt start
    tránh đúng một quỹ đạo mà quên các seed khác.

133. **Mỗi lần kéo thanh trượt là một request.** Không debounce, không
    cache. Chấp nhận được vì preview rẻ và chạy local, nhưng sẽ nặng khi
    API ở xa.

134. **Scenario tự tạo không tự vào thang độ khó.**
    `scripts/calibrate_difficulty.py --scenario-file` nhận được bundle
    `{map, scenario}` xuất từ API, nhưng đây là thao tác tay: không có
    nút "hiệu chuẩn scenario này" trong app, và cache đang commit trong
    repo chỉ chứa 10 scenario thư viện.

135. **Không có đường đưa scenario tự tạo vào thư viện.** Nó sống trong
    database, nên `CURRICULUM_ORDER`, PPO curriculum và cache độ khó mặc
    định đều không thấy nó.

## Biểu đồ và xuất báo cáo (3.1)

136. **Đường cong độ khó chỉ vẽ được scenario đã hiệu chuẩn.** Scenario
    có kết quả nhưng chưa đo độ khó thì không có toạ độ x nên vắng mặt
    khỏi mọi đường; UI liệt kê tên chúng dưới biểu đồ, nhưng người đọc
    vẫn phải tự trừ hao. Với cache hiện tại (10 scenario thư viện, rỗng
    ở khoảng giữa — xem #125 và báo cáo P03), đường cong gần như chỉ có
    hai cụm ở hai đầu.

137. **Một điểm trên đường cong có thể là trung bình nhiều report.**
    Cùng một (stack, scenario) chạy nhiều benchmark thì các report được
    lấy trung bình **theo report**, không gộp theo episode. Tooltip ghi
    số report và số episode, nhưng nhìn đường cong thì một điểm từ 1 lần
    chạy và một điểm từ 5 lần chạy trông giống hệt nhau.

138. **Biểu đồ trộn nhóm quan sát nếu người dùng bật trộn.** Đường cong
    dựng từ chính leaderboard đang xem, nên khi
    `group_by_observation_class=false` thì các stack nhìn thấy dữ liệu
    khác nhau nằm chung một biểu đồ. Cảnh báo trộn nhóm hiện ở bảng phía
    trên, **không** lặp lại trên biểu đồ.

139. **Bộ lọc scenario không áp cho biểu đồ.** Đường cong và chênh lệch
    dev/holdout luôn dựng từ dữ liệu không lọc — một scenario là một
    điểm, không phải một đường cong — nên bảng và biểu đồ trên cùng một
    trang có thể đang nói về hai tập dữ liệu khác nhau.

140. **Clearance và latency không có biểu đồ phân phối.** Chúng được
    tổng hợp thành worst/mean chứ không phải trung vị + khoảng, nên
    không có gì để vẽ râu. Vẫn nằm trong bảng và trong report. Percentile
    latency thuộc F05 (mục 3.2).

141. **Report Markdown không nhúng biểu đồ.** Chỉ có bảng. Ai cần hình
    phải mở web. PDF cũng chưa có — plan để ngoài MVP, tạm thời in trang
    web hoặc Markdown ra PDF.

142. **`git_sha` trong report là commit của tiến trình API đang chạy,
    không phải commit lúc benchmark chạy.** Report cũ xuất lại hôm nay
    sẽ mang SHA hôm nay. Chỉ đúng khi API không được deploy lại giữa lúc
    chạy và lúc xuất; muốn chặt chẽ thì phải chụp SHA vào `report` lúc
    chạy, và đó là thay đổi schema.

143. **Độ khó và chênh lệch tổng quát hóa trong report đọc theo trạng
    thái *hiện tại*, không phải lúc chạy.** Khác với `scenario_split` và
    lớp quan sát (đã snapshot). Hiệu chuẩn lại rồi xuất report cũ sẽ ra
    một con số độ khó khác. Report có ghi `calibration_version` nên
    người đọc phân biệt được, nhưng bản thân tài liệu không tự cảnh báo.

144. **Biểu đồ không có test render.** Môi trường test là Node, không có
    jsdom, nên `recharts` không dựng được SVG để kiểm. Phần được test là
    tầng dữ liệu (`lib/charts.ts` — cái quyết định điểm nào bị loại, giá
    trị thiếu hiển thị ra sao) và phần nối dây ở mức source. Lỗi thuần
    thị giác — trục sai nhãn, màu trùng nhau — sẽ không bị bắt.

145. **`recharts` là dependency runtime đầu tiên ngoài Next/React.**
    Bundle của `/leaderboard` và `/benchmarks/[id]` tăng lên ~262 kB
    first-load (từ ~140 kB). Chấp nhận được cho trang phân tích, nhưng
    đây là chi phí thật và nó nằm trên đường tải của mọi người xem
    leaderboard.

146. **Metric F05 mới chỉ có ở cấp episode, chưa có ở cấp aggregate.**
    `smoothness_squared`, latency p50/p95/p99, `stop_and_go_count`,
    `near_miss_count`, `time_to_first_collision` nằm trong
    `EpisodeMetrics` của từng run (và bảng Runs của report Markdown),
    nhưng `AlgorithmAggregate`, leaderboard và biểu đồ vẫn tổng hợp
    trên các field cũ. Đưa metric mới lên aggregate đụng contract
    leaderboard + charts, để đợt riêng. Overall score của leaderboard
    vẫn dùng `mean_smoothness_successful` (công thức cũ, đã đánh dấu
    deprecated) — chưa đổi sang `smoothness_squared` vì đổi trọng số
    xếp hạng phải được review riêng.

147. **`smoothness_squared` không chuẩn hóa theo chiều dài đường đi.**
    Đúng công thức spec 8.2 `S = Σ(Δθ)²`, nhưng vì không chia cho L nên
    chỉ so được giữa các trajectory trên cùng một scenario; so giữa hai
    map khác kích thước sẽ thiên vị đường ngắn. Field cũ `smoothness`
    (Σ|Δθ|/L — heading-change rate) vẫn được tính cho mục đích đó.

148. **`stop_and_go_count` đo bằng ngưỡng tốc độ có hysteresis
    (0.05/0.10 m/s, `MetricConfig` v1.0.0), không đo bằng lệnh dừng.**
    Robot bò chậm dưới 0.05 m/s mà không hề "dừng" theo nghĩa điều khiển
    vẫn bị đếm. Ngưỡng nằm trong `MetricConfig` versioned và được
    snapshot vào từng `EpisodeMetrics` + ghi trong report, nên đổi
    ngưỡng không làm số cũ đổi nghĩa âm thầm.

149. **`near_miss_count` đếm theo frame, không theo sự kiện.** Robot cà
    sát tường trong 40 frame liên tiếp được đếm 40, không phải 1 lần
    near-miss kéo dài. So sánh giữa các thuật toán vẫn công bằng (cùng
    cách đếm, cùng dt), nhưng con số tuyệt đối phải đọc là "số frame
    dưới ngưỡng an toàn", không phải "số lần suýt va".

150. **`time_to_first_collision` hiện luôn trùng thời điểm kết thúc
    episode** vì engine chấm dứt episode ngay tại va chạm đầu tiên. Field
    tồn tại để giữ nghĩa đúng khi có chế độ chạy tiếp sau va chạm
    (multi-collision) trong tương lai; hôm nay nó không mang thêm thông
    tin so với `elapsed_time` của episode va chạm.

151. **Peak memory không đo.** Quyết định chủ ý theo plan 3.2: phụ thuộc
    máy, có overhead, mâu thuẫn với tính tái lập nếu không ghi môi
    trường đo. Không nằm trong leaderboard hay overall score.

152. **Replanning chỉ kích hoạt sau khi engine đã kết luận STUCK hoặc
    NO_PROGRESS.** Không có trigger sớm kiểu "LiDAR thấy đường bị chặn
    thì replan ngay". Hệ quả: robot luôn phải đứng chờ hết
    `stuck_time_window` (mặc định 5 s) trước khi được cấp đường mới, nên
    `travel_time` của một run có replan gồm cả khoảng chờ đó. Đây là chủ
    ý — một trigger nhạy hơn là một tham số, và tham số đó sẽ phải vào
    chung vòng tune P01 để không thành lợi thế riêng của một thuật toán.

153. **Khi replan, ô lưới chứa tâm robot được ép về FREE.** Robot bị
    chặn thường đứng gần vật cản hơn bán kính inflate, nên ô của chính
    nó bị coi là occupied và global planner trả "no path" — replan sẽ
    không bao giờ chạy được đúng lúc cần nhất. Chỉ đúng **một ô** được
    mở, và mở được vì engine đã chứng minh robot không va chạm (nếu va
    chạm episode đã kết thúc). Các ô lân cận giữ nguyên inflation.

154. **`replan_count` chưa lên `AlgorithmAggregate` và leaderboard.**
    Số lần replan hiện chỉ có ở cấp episode (`runs[].metrics` và bảng
    Runs của report Markdown, cột chỉ hiện khi replanning bật). Đưa lên
    aggregate đụng contract leaderboard và overall score — cùng lý do
    hoãn như #146.

155. **`path_efficiency` của run có replan lấy đường của lần replan cuối
    làm mốc**, còn `global_planning_time`/`expanded_nodes` là tổng cộng
    dồn qua mọi lần plan. Vì vậy so `path_efficiency` giữa một run có
    replan và một run không replan là so với hai mốc khác nhau. Cấu hình
    replanning nằm trong `conditions_checksum` chính là để trong cùng
    một phép so sánh, mọi thuật toán đều dùng cùng luật.

156. ~~**Replanning chưa nối vào `/simulate`, và chưa có UI ở đâu cả.**~~
    **Đã sửa ở Đợt B (2026-08-08).** `POST /simulations` nhận
    `replanning`, `SimulationService.run` truyền xuống `run_stack()`,
    `StoredSimulation` lưu lại (migration Alembic `0004`), và cả
    `/simulate` lẫn form tạo benchmark có ô bật kèm cảnh báo. Giới hạn
    còn lại của UI: xem #160.

157. **Cache difficulty hiện tại (P03) đo với replanning tắt.** Bật
    replanning làm scenario dễ đi, tức là một thang đo khác;
    `scripts/calibrate_difficulty.py --max-replans N` bắt buộc phải kèm
    `--calibration-version` riêng và không ghi đè cache cũ.

158. **Replan đọc ground truth, và cái đã sửa là *nhãn*, không phải
    nguồn dữ liệu.** `_replan()` lấy vị trí vật cản động qua
    `engine.dynamic_obstacles_now()` — chính xác tuyệt đối, không nhiễu,
    không che khuất, không cần cảm biến. Từ Đợt A, khi replanning bật,
    `global_observation_class` được **suy ra lúc chạy** thành
    `full_static_map+human_states` thay vì đọc cứng `full_static_map` từ
    registry, nên báo cáo và leaderboard không còn dán nhãn sai. Nhưng
    đây mới là khai báo trung thực về một đặc quyền, **chưa phải là bỏ
    đặc quyền đó đi**. Lời giải thật là dựng lớp vật cản từ chính LiDAR
    scan của robot (một `local_costmap` kiểu Nav2, tích luỹ theo thời
    gian) — ước lượng ~3 ngày và cần plan riêng; xem "Lựa chọn 2" trong
    `docs/antongduy/plans/2026-08-07/replanning-lien-tuc-va-noi-day-vao-simulate.md`.

    Hệ quả trực tiếp: **run có replanning không so được với run không
    replanning trong cùng một bảng xếp hạng** — chúng ở hai lớp quan sát
    khác nhau. Ép xem chung thì leaderboard trả về
    `cross_observation_class_warning = True`.

159. **Việc nâng lớp quan sát là bảng tra cố định, không phải suy luận.**
    `global_class_under_replanning()` ánh xạ từng giá trị `ObservationClass`
    sang giá trị tương ứng khi replanning bật. Thêm một lớp quan sát mới
    mà quên thêm vào bảng đó sẽ `KeyError` ngay — chủ ý, vì im lặng bịa ra
    một tên lớp không ai nhận là đúng thứ P02 sinh ra để chặn. Có test
    quét toàn bộ `OBSERVATION_CLASSES` để bắt trường hợp này.

    Kèm theo: khóa nhóm của leaderboard giờ gồm **cả hai** lớp
    (global + local), không chỉ local như trước. Dữ liệu cũ không đổi
    nhóm — mọi aggregate cũ đều `full_static_map`.

## Nối dây replanning vào `/simulate` và UI (Đợt B, 2026-08-08)

160. **Lựa chọn replanning không được nhớ giữa các lần vào trang, và đó
    là chủ ý.** Cả `/simulate` lẫn form benchmark khởi tạo về tắt mỗi lần
    load, không đi qua `persisted.ts` như các tùy chọn khác. Lý do: bật
    replanning là đổi lớp quan sát của global planner (#158), nên nó phải
    là một hành động có ý thức mỗi lần, không phải một setting còn sót
    lại từ phiên trước. Có test khóa tính chất này.

161. **`/simulate` không vẽ marker replan trên timeline.** Marker đã có ở
    replay của benchmark detail (đọc từ `result.events`), nhưng trang
    `/simulate` dùng `useEpisodeStream` (WebSocket) chứ không dùng
    `useTrajectoryPlayback`, và luồng WS hiện **không phát `events`** —
    chỉ phát `start`, `state`, rồi `result` (`routers/ws.py`). Người dùng
    vẫn thấy `Replans` ở `MetricsPanel` và thấy robot đi đường vòng,
    nhưng không biết **thời điểm** đổi đường. Sửa đúng cách là cho WS
    phát cả events, tức đụng contract của socket — để riêng, không nhét
    vào Đợt B.

163. **Đường toàn cục vẽ trên màn hình là đường của lần plan ĐẦU, kể cả
    sau khi đã replan.** `StackRun.plan` giữ `plan` đầu tiên
    (`nav_stack.py`), trong khi metrics dùng `plans[-1]`. Hệ quả nhìn
    thấy được ở **cả hai** trang: robot rời khỏi đường đang được vẽ và đi
    một lối khác, trông như bug của renderer. Ảnh hưởng đúng vào tính
    năng vừa nối dây, nên phải nói rõ.

    Không sửa trong Đợt B vì sửa đúng là đổi contract: cần
    `StackRun.plans: tuple[PlanResult, ...]` (giữ cả chuỗi đường), kéo
    theo payload WebSocket, `SimulationResultResponse`, artifact của
    episode và bản đọc ngược cho dữ liệu cũ. Đổi `plan` thành đường cuối
    thì rẻ nhưng sai: nó xoá mất đường ban đầu, và
    `plan.path_length`/`expanded_nodes` của lần plan đầu là số đang được
    dùng ở chỗ khác.

162. **Trang `/simulate` tạo scenario mới cho mỗi lần chạy**
    (`${scenario.name}-${Date.now()}`), nên bật/tắt replanning rồi chạy
    lại sinh ra hai scenario row khác nhau. Không ảnh hưởng tính đúng —
    nội dung scenario giống hệt và replanning không nằm trong scenario —
    nhưng nghĩa là không so được hai lần chạy bằng `scenario_id`. Đây là
    hành vi có từ trước Đợt B, ghi lại vì giờ nó dễ gặp hơn.

## Replanning không giúp gì ở scenario va chạm (điều tra 2026-08-08)

Hai mục dưới đây đến từ một quan sát của dev: bật replanning trên
`bidirectional_corridor` với `max_replans=2` mà robot **vẫn va chạm**, và
đường đi không đổi gì so với khi tắt. Điều tra cho thấy quan sát đó đúng
và không phải lỗi báo cáo. Bằng chứng và số liệu đầy đủ:
`docs/antongduy/notes/2026-08-08/tongduyan_dieu-tra-replanning-tren-corridor.md`.

164. **`COLLISION` không nằm trong `_REPLANNABLE`, nên replanning vô dụng
    ở mọi scenario mà robot *đâm* thay vì *kẹt*.**
    `_REPLANNABLE = (STUCK, NO_PROGRESS)` (`nav_stack.py`). Đây là chủ ý
    và không nên đổi: va chạm là kết luận của episode, cho một đường mới
    xoá nó đi là để replanning mua một kết quả nó không kiếm được, và
    `success_rate` mất nghĩa. Nhưng hệ quả phải nói thẳng:

    ```text
    bidirectional_corridor, astar+dwa, 5 seed
      off    {collision: 5}  replans=[0,0,0,0,0]  t=[21.0, 20.9, 5.9, 5.8, 20.4]
      on(2)  {collision: 5}  replans=[0,0,0,0,0]  t=[21.0, 20.9, 5.9, 5.8, 20.4]
    ```

    Trajectory **giống hệt từng con số** — nhánh replan không bao giờ
    tới. `crossing_obstacle` cũng vậy.

    Thêm một lý do độc lập ở đúng map này: hành lang đơn chỉ có **một**
    route tôpô, nên global planner có replan bao nhiêu lần cũng trả về
    cùng một đường. Né đối đầu là maneuver của **local** planner, không
    phải việc của replanning.

    **Scenario để demo/kiểm chứng replanning là `sudden_stop`**, nơi
    robot bị kẹt chứ không đâm:

    ```text
    sudden_stop, astar+dwa, 5 seed
      off    {stuck: 5}    replans=[0,0,0,0,0]  t=12.9
      on(2)  {success: 5}  replans=[1,1,1,1,1]  t=23.3
    ```

165. **DWA coi vật cản động là đứng yên, nên không né được xe đi ngược
    chiều.** `_rollout_batch` (`packages/planning/planbench_planning/dwa/planner.py`)
    tính clearance của mọi ứng viên dựa trên **điểm LiDAR đóng băng** tại
    vị trí vừa đo được. Vật cản chạy 0.6 m/s, horizon 1.5 s → 0.9 m sai
    số không được mô hình hóa; controller tưởng an toàn khi thật ra
    không. Cộng thêm: trọng số kéo về đường (`goal` 2.0 + `path` 1.4 +
    `heading` 1.0 = 4.4) lấn át `clearance` (1.2, lại bão hòa ở
    `clearance_cap` = 0.6), nên né sang bên trả giá ngay còn lợi ích chỉ
    xuất hiện ở cuối horizon.

    Đo được: trên `bidirectional_corridor`, `angular_velocity` **bằng 0
    suốt cả episode** và tọa độ `y` của robot đứng nguyên ở tim hành lang
    cho tới lúc va chạm. Nới hành lang từ 2.0 m lên **4.0 m** — thừa chỗ
    né — vẫn va chạm 5/5. Nên đây **không** phải vấn đề hình học.

    **Đây là kết quả benchmark hợp lệ, không phải bug cần vá gấp**: nền
    tảng vừa đo được một giới hạn thật của DWA, và đó đúng là việc nó
    sinh ra để làm. Nhưng con số va chạm trên các scenario có vật cản
    động phải được đọc là **giới hạn của baseline**, không phải đặc tính
    của scenario, và **không** được dùng làm bằng chứng rằng một planner
    khác tốt hơn cho tới khi cả hai chạy dưới cùng ngân sách tinh chỉnh.

    Lời giải đúng là một stack **mới** (`dwa_predictive`): ước lượng vận
    tốc vật cản từ hai scan LiDAR liên tiếp rồi dịch điểm theo thời gian
    trong rollout — đúng nhóm "Human Prediction-based" của đề bài, và
    **không** đọc `dynamic_obstacles_now()`. Phải đăng ký như một stack
    riêng với ngân sách riêng: luật P01 cấm nâng cấp kiến trúc của một
    planner giữa chừng vì nó chạy kém (đó chính là lỗ hổng S2 mà đề bài
    phê phán ở Alyassi et al.). Tune tay `weight_path`/`clearance_cap`
    cho riêng DWA cũng vướng đúng luật đó.

## Môi trường

- Test phải chạy với `PYTHONPATH=` do shell source ROS2 Jazzy (xem
  TEST_REPORT.md).
- Test frontend chạy ở môi trường Node (không jsdom); `vitest.config.ts`
  đặt `testTimeout: 20s` vì `auth.test.ts` reset module graph ở mỗi case
  và 15 file chạy song song có lúc vượt mốc 5s mặc định.

## MVP v1 — Planner Selector (chốt 2026-08-11)

Bản MVP đầu tiên của tầng quyết định. Nền tảng đo được, so được, và từ
chối kết luận khi dữ liệu không đỡ. Các giới hạn dưới đây **không phải
lỗi cần vá** — chúng là phạm vi mà mọi kết luận của bản này bị chặn
trong, và mỗi cái có điều kiện gỡ rõ ràng.

### L1. G4 và G5 mới xác nhận trên máy benchmark, **chưa trên bo mạch đích**

Dự án **không có bo mạch đích** (Jetson Orin Nano hay board ARM nào). Nên
theo bảo lưu HĐ-7.2/7.3:

- `realtime_gate.status` **luôn** là `screened_on_host`; giá trị
  `verified_on_target` không xuất hiện trên bất kỳ Decision Card nào của
  dự án này, và `target_p99_ms` luôn null.
- `memory_gate.status` chỉ nhận `estimated_from_structure` hoặc
  `declared_by_author`. G5 **đếm** cấu trúc dữ liệu nhân kích thước byte
  khai theo hiện thực đích, **không đo** RSS. `peak_rss_mb` là chẩn đoán,
  và **không bao giờ** được đem so với `available_ram_mb`.

**Suy luận nào còn hợp lệ:** đúng một chiều. Trượt trên máy benchmark
nhanh ⇒ **chắc chắn** trượt trên bo mạch đích chậm hơn. Chiều ngược lại
**không** suy được: qua G4 trên host **không** cho phép phát biểu
candidate đạt thời gian thực trên bo mạch đích. Mọi card in nguyên văn
*"G4 mới qua vòng sàng lọc — chưa xác nhận trên bo mạch đích"*.

**Cấm dùng hệ số quy đổi giữa hai máy.** A\* (nặng truy cập bộ nhớ) và
DWA (nặng tính toán) co giãn khác nhau giữa x86 và ARM; một hệ số dùng
chung là con số bịa.

Thêm một hệ quả đo được của lượt M4: `rrtstar+dwa` với lấy mẫu 20×40
trượt G4 ở **50,28 ms** trên ngưỡng 50,00 ms — vượt 0,6%. Biên đó mỏng
tới mức độ chính xác của phép đo bắt đầu quan trọng, nên phát biểu đúng
là *"trượt theo số đo được"*, **không** phải *"chắc chắn trượt trên bo
mạch đích"*. Lối ra hợp lệ là đăng ký candidate mới với lấy mẫu trung
gian — **không** nới `control_period` (xem L4).

**Gỡ khi:** có bo mạch đích, chạy pha P2 trên đúng board, gỡ bảo lưu
HĐ-7.2/7.3 và tăng `contracts_version` MINOR.

### L2. Chưa có adapter `MonolithicPolicy` — chỉ candidate `modular` chạy được

HĐ-4 định nghĩa hai loại candidate: `modular` (global planner + local
controller) và `monolithic` (policy end-to-end, không có global planner).
Adapter cho loại thứ hai **chưa tồn tại**. `build_planners` từ chối một
candidate `monolithic` bằng thông điệp nói rõ điều đó, và
`test_only_modular_stacks_can_run_today` sẽ **đỏ** đúng ngày adapter
được thêm.

**Vì sao chốt chặn đó tồn tại, và đây là phần quan trọng:** ngày adapter
chạy được, một bất cân xứng thông tin **đã biết** trở thành lỗi công bằng
thật. Khi robot bị chặn, `nav_stack._replan` dựng lưới quy hoạch tạm với
**vị trí thật** của vật cản động nung vào. Hôm nay công bằng vì mọi
candidate đều là modular và nhận cùng lưới đó. Nhưng một policy
end-to-end chỉ thấy `Observation`, còn global planner của stack modular
thấy vật cản **thật sự ở đâu** — đúng đặc quyền mà G6 và P02 sinh ra để
định giá, và nó sẽ ưu ái stack modular vì một lý do **không liên quan gì
tới chất lượng điều hướng**.

Luật đã ghi ở HĐ-4.1: phải gỡ đặc quyền này **trước** khi chấm bất kỳ
candidate `monolithic` nào, và lời giải hợp lệ là **replan từ
`Observation`** — không phải cấp ground truth cho cả hai bên (cấp cho cả
hai chỉ đổi một phép so lệch thành hai phép đo sai).

Hệ quả cho bản MVP này: mọi kết luận đều nằm trong họ **modular**, và
tuyên bố *"nền tảng công bằng cho mọi thuật toán"* mới được chứng minh
trên hai global planner cùng kiểu tìm đường trên lưới với một local
controller. Phép thử thật của tuyên bố đó chưa được chạy.

### L3. Bốn candidate, một qua cổng — chưa có Decision Card nào trên nền đã kiểm

Trên `open_hall_v2` (30 episode ghép cặp, ghim 2 nhân, nhiễu σ = 2 cm /
trượt 2%):

| stack | local | success | p99 gộp | verdict |
|---|---|---:|---:|---|
| `astar+dwa` | `dwa_coarse` | 70% | 5,26 ms | fail G3 |
| `astar+dwa` | `dwa_default` | 73% | 29,40 ms | fail G3 |
| `rrtstar+dwa` | `dwa_coarse` | 100% | 6,06 ms | **pass** |
| `rrtstar+dwa` | `dwa_default` | 100% | 50,28 ms | fail G4 |

Không cặp nào có **hai** candidate cùng qua sáu cổng, nên không phép so
nào ra được Decision Card. Đó là **kết quả**, không phải sự cố: bảng cổng
trả lời "ai bị loại ở đâu sau bao nhiêu lần chạy", và
`comparison_report.json` ghi lại đầy đủ.

Một ràng buộc đọc kết quả: `open_hall_v2` khai `success_rate_min: 0.95`,
và **con số đó vẫn chưa mang lập luận nào của riêng sảnh**. Nó được chép
từ profile kho; ngày 08-11 đã đổi sang 1.00 kèm lý do, ngày 08-12 lùi lại
vì hệ quả lên thang anchor — xem **L6**, việc còn để ngỏ. Nên *"A\* trượt
G3 trên sảnh"* phải đọc là **A\* đạt 70% trên sảnh này**, và việc đó có
phải thất bại hay không còn phụ thuộc một ngưỡng chưa được chốt cho
deployment này.

### L4. Bốn con số **không** được nới để có kết quả đẹp hơn

Ghi ở đây vì cả bốn đã từng bị nới một lần và phải hoàn nguyên
(2026-08-11):

1. `robot.control_period` — là ngưỡng G4. Từng khai 10 Hz thay vì 20 Hz
   vì DWA Python không kịp 50 ms, tức **nới cổng vì candidate không qua
   nổi cổng**.
2. `constraints.collision_probability_max` — là yêu cầu an toàn của hiện
   trường, không phải núm vặn thời lượng chạy. Mũi tên chạy một chiều:
   `rủi ro ⇒ N_min ⇒ số giờ`, không đọc ngược.
3. Tham số DWA của candidate — đó là **thứ đang được đem đo**. Sửa nó
   nghĩa là **đăng ký candidate mới**, không phải chỉnh tại chỗ.
4. Map, mission, traffic — sửa chúng theo kết quả là đổi đề bài.

Câu hỏi bắt buộc cho mọi hằng số mới trong profile (HĐ-15.3): *"con số
này đến từ hiện trường, hay từ thứ máy/code của tôi chạy nổi?"* Vế sau
thì nó thuộc mục bảo lưu của hợp đồng, không thuộc file profile.

### L5. Vận hành

- **Hai run đánh giá không được chạy song song trên cùng một máy.** Ghim
  nhân là mặc định và luôn lấy `count` nhân **đầu**, nên hai tiến trình
  cùng ghim sẽ giành đúng hai nhân đó: mỗi run thành tải nền của run
  kia và G4 của cả hai đo một cái máy không tồn tại (HĐ-7.4). Chạy tuần
  tự, hoặc `--no-pin` cộng `taskset` cấp mask rời nhau.
- **Đổi `sensor_noise` phải đổi `task_profile_id`.** `episode_context_id`
  không băm biên độ nhiễu (HĐ-3.1 đóng băng payload), nên sửa σ tại chỗ
  sẽ khiến `--reuse-traces` phục vụ episode ghi trong một thế giới không
  còn tồn tại — id khớp, không cảnh báo nào.
- **`instance_difficulty` chưa nối** vào tầng quyết định; cache P03 khoá
  theo `scenario_name` của thư viện cũ và không có entry cho profile nào
  thời contract. **`robustness_margin` vẫn null** — cần Task Neighborhood
  (pha 2).

### L6. `success_rate_min` của sảnh: **nợ kỹ thuật, chưa giải quyết** (2026-08-12)

`open_hall_v1` và `open_hall_v2` khai `success_rate_min: 0.95`. **Con số
đó được biết là sai**, và nó ở đó như một biện pháp tạm.

**Giá trị đúng theo lập luận là 1.00.** Sảnh là deployment nghiệm thu:
dễ, đối xứng, chạy dưới nhiễu đã khai, không có gì đánh bại một stack
bằng hình học. Nên một failure ở đây là **tín hiệu chẩn đoán**, không
phải một thống kê để lấy trung bình — và 0.95 đang phát biểu rằng một
lần hỏng trên hai mươi lần trên nhiệm vụ đối xứng dễ là chấp nhận được,
điều không ai thực sự muốn nói. Ngày 2026-08-11 hai file đã chuyển sang
1.00 đúng vì lý do này.

**Vì sao lùi lại 0.95 (2026-08-12).** Luật 2 của HĐ-8.3 buộc `bad` của
`success_rate` trỏ vào chính ngưỡng ấy, nên 1.00 làm `good == bad`, thang
sập, và deployment mất khả năng xếp hạng (HĐ-8.4). Hệ quả kéo theo:
`U_R` chết trên sảnh, `measure.py` không ra `decision_utility`, và tấm
Decision Card duy nhất của dự án — dựng trên `open_hall_v2` — không tái
lập được. Đưa sảnh ra khỏi vai xếp hạng là một quyết định lớn hơn cái
đáng quyết trong lúc MVP còn dở, nên ngưỡng lùi về giá trị giữ cho mọi
thứ chạy, và câu hỏi để lại đây.

**Trạng thái hiện tại, nói rõ để không ai tưởng đã xong:**

- Cơ chế **đã có**: HĐ-8.4 xử lý 1.00 tử tế — vẫn mô phỏng, vẫn ra sáu
  phán quyết cổng, từ chối xếp hạng kèm lý do đọc được thay vì ném
  `AnchorError`. Việc còn lại là **quyết định**, không phải hiện thực.
- Cái chưa có: một lối để sảnh vừa giữ chuẩn nghiệm thu 1.00 vừa còn
  thang cho `U_R`. Vài hướng chưa xét kỹ: tách `success_rate_min` (cổng)
  khỏi neo `bad` của anchor (thang); cho anchor khai `bad` riêng khi
  ngưỡng chạm trần; hoặc chấp nhận sảnh chỉ gác cổng và chuyển hẳn việc
  xếp hạng sang một deployment khó-mà-đối-xứng (C2, chưa có).
- **Không được coi 0.95 là câu trả lời.** Đọc *"A\* trượt G3 trên sảnh"*
  vẫn phải đọc là **A\* đạt 70% trên sảnh này**; con số 0.95 hiện không
  mang lập luận nào của riêng nó.

Hẹn xử lý: sau khi MVP hoàn tất.

---

## Inflation theo bậc — RRT* trở thành biến thể cost-aware (2026-08-14)

Lưới nhị phân được thay bằng **trường chi phí**: chỉ miền khả thi cứng
(`hard_clearance` = footprint + safety envelope) là **cấm tuyệt đối**;
dải quanh nó — vốn bị cấm hẳn — nay chỉ **đắt**. Cả hai global planner
phải đọc trường đó, nếu không thì trường không có nghĩa.

### Hạn chế 1 — bảo đảm tiệm cận tối ưu của RRT* **chưa được xác minh**

Chi phí cạnh của RRT* giờ là **tích phân trường chi phí dọc cạnh**, thay
vì độ dài Euclid. Bảo đảm tiệm cận tối ưu của RRT* (Karaman & Frazzoli)
được chứng minh cho các phiếm hàm chi phí có tính chất liên tục và bị
chặn nhất định; trường ở đây **hằng từng ô**, tức gián đoạn ở mọi cạnh ô.

**Dev đã chốt (14-08): chấp nhận triển khai mà chưa xác minh.** Ghi ở
đây và trong mô tả stack trên `/candidates`, không giấu trong comment.

Từ nay, **"RRT\*" trong dự án này là một biến thể cost-aware**. Mọi so
sánh — nhất là so với số liệu trong bài báo — phải đọc nó như thế.

Cái **vẫn còn** và là thứ cơ chế rewire thực sự cần: chi phí cộng tính
dọc đường, và đơn điệu theo khoảng cách (hệ số ≥ 1, nên khoảng cách
đường thẳng là **chặn dưới** của mọi cạnh). Mọi bước cắt tỉa trong vòng
lặp chỉ dựa vào đúng hai tính chất đó.

### Hạn chế 2 — `clearance_preference` (λ) là số **do người chọn**

Không suy ra được, khác với safety envelope hay `N_min`. Nên xử lý như
mọi con số cùng loại: khai trên **deployment**, giống nhau cho mọi ứng
viên, ghi vào manifest (HĐ-13). Mặc định `2.0` — một mét sát biên cứng
đắt bằng ba mét chỗ trống, tức planner chịu đi vòng tới gấp ba quãng
đường để khỏi cạo sát vật.

Con số 2.0 **chưa được hiệu chuẩn theo dữ liệu**; nó là một lựa chọn hợp
lý, không phải kết quả đo. Đổi nó **đổi mọi đường đi**, nên đổi nó là
tạo deployment mới chứ không phải sửa cấu hình.

### Hạn chế 3 — tích phân chi phí là **xấp xỉ lấy mẫu**

`segment_cost` lấy mẫu mỗi 1/4 ô và cộng lại, không đi chính xác chuỗi ô
mà đoạn thẳng cắt qua (Amanatides–Woo). Sai số bị chặn bởi 1/4 ô nhân
một hệ số — dưới xa mức bất kỳ quyết định định tuyến nào phụ thuộc vào,
và đúng bằng xấp xỉ mà `has_line_of_sight` vốn đã dùng.
### Hạn chế 4 — vẫn phải nới lưới quanh robot, và bán kính cấm vẫn mang **nửa** đường chéo ô

Lượng tử hoá là **hai phía**: vật cản nằm đâu đó trong ô của nó, robot
nằm đâu đó trong ô của nó, nên khoảng cách tâm–tâm chỉ chặn khoảng cách
thật trong phạm vi một đường chéo ô về **cả hai** hướng. Hệ quả: **không
có bán kính inflation nào** khiến "controller nói tư thế này hợp lệ" kéo
theo "lưới của planner đồng ý".

Hai nửa được xử khác nhau:

- **Nửa phía vật cản** (`√2/2 × resolution`) nằm trong `_hard_radius`.
  Đây là **số học, không phải thận trọng**: ô OCCUPIED nghĩa là vật cản
  chạm ô đó, không nói chạm ở đâu, nên bỏ nửa này ra thì lưới thành xấp
  xỉ **lạc quan** của miền cứng — điều duy nhất nó không được phép là
  thế. Đo trên phòng hai cửa ở ô 0.5 m, robot 0.3 m: inflate 0.30 m
  **không đánh dấu thêm một ô nào**, vì tâm hai ô kề nhau cách 0.5 m; A*
  trả về đường cạo sát tường, controller không lái được, và 40/43 lần
  replan không tìm ra gì — đúng lỗi cũ, vào bằng cửa khác.
- **Nửa phía robot** nằm trong `_caution_ramp` — chỉ tính tiền. Đường đi
  là vật thể liên tục và được kiểm như thế: hàng rào L4 đo mọi đường
  global theo **mét**, trên cả hai stack.

`_with_standing_room` nới quanh robot **đúng phần thận trọng của lưới**:
ô nào bị chặn trên lưới `_hard_radius` mà **tự do** trên lưới
`_feasible_clearance` thì được mở, trong bán kính một `_caution_ramp`. Ô
nằm trong miền cứng thật **không bao giờ** được mở.

Riêng ô robot đang đứng thì mở **vô điều kiện**. Ô rộng 0.5 m: robot giữ
khoảng cách 0.3 m với tường sẽ đặt LiDAR return gần nhất vào **chính ô
chứa tâm nó**, nên luật có điều kiện từ chối đúng lúc cần nới nhất — đo
được: "start is inside an obstacle" 43/44 lần replan. Nhưng robot **đang
ở đó**, và engine kết thúc episode ngay khi robot chồng lên vật cản, nên
sự hiện diện của nó chính là bằng chứng.

**Vì sao đây không phải bong bóng B1 quay lại.** B1 mở mọi thứ mà
*inflation* đã đánh dấu, tức trả lại **không gian trống thật**, và không
gian trống có giá trị khác nhau với từng họ planner (đo trên
`sudden_stop`: A* lấy hành lang rộng 0.59 m bằng 3 waypoint, RRT* cắt
còn 0.13 m bằng 10 waypoint, có khúc quay 170° và 187° mà robot
chỉ-tiến-không-lùi không lái nổi).

Hai điểm khác: nới **dừng ở miền cứng** chứ không dừng ở vật cản thô,
nên không bao giờ trả lại thứ bất hợp lệ; và mọi ô được mở **giữ nguyên
hệ số chi phí cực đại**, nên cắt qua khe đó là **đắt** với bất kỳ ai làm
thế — đó chính là câu trả lời của gradient cho thiên vị của B1.

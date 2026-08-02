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
7. **LiDAR không có noise model** — sẽ thêm noise có seed khi cần
   benchmark sensor robustness.
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
46. **Replay chỉ hiện khung cuối, chưa có timeline scrub.** Trang
    `/simulate` có playback theo thời gian thực; replay của episode đã
    lưu thì vẽ toàn bộ trajectory cộng vị trí cuối.
47. **Vật cản động không hiện trong 2.5D.** Snapshot vị trí vật cản có
    trong `TrajectoryPoint.obstacles` nhưng renderer chưa dùng — hiện
    chỉ vẽ map tĩnh, plan, trajectory và robot.
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

51. **Đã build và chạy thật `docker compose up --build` (Phase 3a, xem
    mục "Docker Compose" bên dưới).** Không còn là giả định.
52. **Đã kết nối PostgreSQL thật (Phase 3a).** `docker compose up` chạy
    `db` (postgres:17-alpine) + `migrate` (alembic upgrade head, exit 0)
    + toàn bộ luồng account/map/scenario/benchmark/run qua API container
    trên Postgres thật, không còn chỉ SQLite. Chi tiết ở mục "Docker
    Compose" bên dưới.
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

## Bộ giao thức đánh giá P02–P05 (Phase 2)

77. **Seed < 30 chỉ cảnh báo, không chặn.** `BenchmarkReport.statistically_adequate`
    tự báo `false` khi `len(seeds) < 30` (spec mục 8.6a) nhưng backend vẫn
    chạy và trả kết quả bình thường — quyết định có chủ đích để không phá
    vỡ demo/test hiện tại đang dùng 1-3 seed. Muốn chặn cứng, sửa
    `BenchmarkSpec` validator trong `packages/benchmark/planbench_benchmark/spec.py`.
78. **Không enforce "chạy holdout đúng 1 lần"** (spec mục 8.6e). `split`
    trong `LibraryEntry`/`generalization_gap` trong leaderboard chỉ là
    nhãn báo cáo — không có gì ngăn một benchmark chạy nhiều lần trên
    scenario `holdout` để tinh chỉnh ngầm. Cần tầng kiểm soát riêng nếu
    muốn enforce thật (theo dõi số lần chạy per user per scenario).
79. **Cache độ khó (`difficulty_cache.json`) có thể lỗi thời.** Sinh ra
    bằng `scripts/calibrate_difficulty.py` chạy 1 lần thủ công — nếu
    simulator, DWA default config, hoặc chính scenario thay đổi, cache cũ
    vẫn được đọc và hiển thị số liệu sai cho tới khi ai đó chạy lại
    script. Không có cơ chế tự phát hiện cache lỗi thời (không hash
    version simulator/scenario vào file cache).
80. **`observation_class` hiện đồng nhất cho cả 3 stack** (`lidar_only`)
    — trường tồn tại đúng thiết kế P02 nhưng chưa có tác dụng phân nhóm
    thật vì chưa có planner nào truy cập full_map/human_states trong
    codebase. `mixed_observation_classes` sẽ luôn `false` cho tới khi có
    planner đặc quyền đầu tiên.
81. **P01 (Optuna, ngân sách tinh chỉnh bằng nhau) chưa làm** — dời sang
    roadmap Phase 3, cần thêm dependency `optuna` riêng.

## Map loader + công thức metric (Phase 3a)

82. **F01 chỉ hỗ trợ PGM (P5 binary + P2 ASCII), không hỗ trợ PNG.**
    ROS `map_server` tự nó xuất PGM mặc định nên đây là format thật sự
    dùng; PNG cần decoder ảnh riêng (Pillow) — chi phí không tương xứng
    cho một format phụ. `packages/schemas/planbench_schemas/map_io.py`.
83. **`smoothness` (spec Σ(Δθ)²) không chuẩn hóa theo chiều dài đường
    đi** — đúng công thức đề bài, nhưng nghĩa là đường dài tự nhiên có
    tổng lớn hơn dù mỗi khúc cua đều nhẹ. Không so sánh trực tiếp giá
    trị này giữa các scenario khác kích thước; dùng
    `smoothness_per_metre` (đã chuẩn hóa, giữ công thức cũ) cho việc đó
    — leaderboard `overall_score()` đã tự dùng field này, không phải
    `smoothness` thô.
84. **F05 không đo peak memory.** Đo memory tin cậy, độc lập máy chạy
    mâu thuẫn với nguyên tắc `conditions_checksum` phải nắm bắt hết yếu
    tố công bằng (memory phụ thuộc OS/máy, không phải điều kiện benchmark
    kiểm soát được). Spec cũng liệt kê đây là chỉ số phụ. p50/p95/p99
    latency và `stop_and_go_count` đã làm.
85. **`stop_and_go_count` dùng ngưỡng cố định `0.02 m/s`** để coi là
    "đứng yên" — chưa cấu hình được theo robot; đủ cho robot chuẩn trong
    thư viện scenario hiện tại, có thể cần tinh chỉnh nếu thêm robot có
    vận tốc tối thiểu khác biệt lớn.

## Docker Compose (Phase 3a)

Verify thật ngày 2026-08-02 trên Windows 11 + Docker Desktop v29.5.3 (Compose
v5.1.4), daemon Linux containers:

- `docker compose up --build -d`: build 2 image (`planbench-api`,
  `planbench-web`) — không lỗi, không thiếu gói (`PyYAML` mới thêm cho F01
  build đúng layer cache).
- `docker compose ps`: cả 3 service `db`/`api`/`web` lên `healthy`;
  `migrate` (`alembic upgrade head`) exit 0.
- Verify qua container thật: `GET /api/v1/health` → 200; login qua
  `POST /auth/login` (password dev-login); tạo map thường (`POST /maps`)
  và **map import ROS thật** (`POST /maps/import-ros` với PGM+YAML tự tạo,
  occupancy convert đúng — tâm free, viền occupied); tạo scenario, tạo
  benchmark 2 thuật toán × 3 seed; gửi review request tới Approver → duyệt
  → Engineer `run` — chạy thành công, **lần đầu tiên trên PostgreSQL thật**
  (không phải SQLite). Report trả về đủ field Phase 3a mới:
  `smoothness`/`smoothness_per_metre`, `local_planning_latency_p50/p95/p99`,
  `stop_and_go_count`, `comparisons` (Wilcoxon), `statistically_adequate:
  false` (đúng vì seed=3 < 30). `docker compose logs api` không có
  traceback. Dữ liệu sống sót qua một lần `docker compose up -d
  --force-recreate api` (đổi `.env`, restart riêng container `api`) — xác
  nhận Postgres volume độc lập với vòng đời container `api`.
- `docker compose down` (không xóa volume) sau khi verify xong.
- **Phát hiện thật, không phải giả định**: `PLANBENCH_ADMIN_NICKNAMES` chỉ
  có tác dụng qua luồng OAuth (`account_service.identify_or_create()` gọi
  `apply_admin_policy()`); tài khoản seed qua `PLANBENCH_SEED_USERS`/
  dev-login **không** tự được gắn `is_admin=true` dù nickname có trong danh
  sách admin, vì luồng password-login không gọi `apply_admin_policy()`.
  Muốn test admin override ở môi trường dev-login-only phải tạo cách khác
  (không có trong scope Phase 3a) — không sửa trong đợt này, ghi nhận làm
  giới hạn.

## RRT* (Phase 3b-1)

86. **Nearest/near-neighbor scan là O(n) mỗi iteration** (không dùng
    KD-tree) — đủ nhanh ở quy mô map/scenario hiện tại (`max_iterations`
    mặc định 1500), sẽ chậm rõ rệt nếu tăng iteration hoặc map lớn hơn
    nhiều. `packages/planning/planbench_planning/rrtstar/planner.py`.
87. **`expanded_nodes` với RRT* là số node cây đã thêm**, không cùng ý
    nghĩa với "ô đã expand" của A* — không so sánh trực tiếp field này
    giữa 2 thuật toán trong report. Các field khác (success, travel_time,
    path_efficiency, smoothness, collision...) vẫn so sánh công bằng vì
    đo trên hành vi robot thật, không phải nội bộ planner.
88. **`RRTStarConfig.seed` cố định trong config, không lấy từ
    `scenario.random_seed` của benchmark run.** Mọi seed benchmark chạy
    cùng một cây/đường RRT* — đúng theo contract "deterministic cho
    input giống hệt" của `GlobalPlanner`, nhưng nghĩa là RRT* không có
    đa dạng đường đi qua các seed như một sampling planner "thật" người
    ta thường kỳ vọng.
89. **`"rrtstar+ppo"` cố tình không đăng ký.** PPO được huấn luyện giả
    định hình dạng đường của A*; ghép RRT* vào registry có thể cho số
    liệu gây hiểu lầm thay vì một so sánh công bằng.
90. **Bảng alias ngôn ngữ tự nhiên của agent**
    (`services/agent_service/planbench_agent/specs.py:187-193`) chưa
    nhận diện "rrt*" — người dùng agent console gõ "rrt" sẽ không map
    được sang `rrtstar+dwa`. Chưa sửa trong đợt này.

## UI replay scrubbing + vật cản động (Phase 3b-3)

91. **Obstacle marker trong 2.5D vẽ sau tất cả facet tường, không tham
    gia depth-sort painter's algorithm** (`scene25d.ts::buildScene`) —
    giống cách robot marker đã vẽ từ trước. Vật cản động luôn hiện đè
    lên trên, không bị tường che khuất đúng theo chiều sâu thật. Đủ cho
    mục đích "thấy vật cản ở đâu tại mỗi thời điểm"; không đúng
    occlusion 100%.
92. **Không có nút play/pause tự động** — chỉ kéo tay thanh scrubber
    (`<input type="range">`). `lib/playback.ts::tick()` đã có sẵn cho
    auto-playback nhưng chưa được gọi ở trang benchmark detail; thêm
    sau nếu cần.
93. **Vật cản động chỉ vẽ ở view 2.5D, không vẽ ở view top-down**
    (`MapCanvas`) — đúng scope F08 ("vẽ chướng ngại động trong view
    2.5D"). Scrubbing thời gian thì áp dụng cho cả 2 view.

## Môi trường

- Test phải chạy với `PYTHONPATH=` do shell source ROS2 Jazzy (xem
  TEST_REPORT.md).
- Test frontend chạy ở môi trường Node (không jsdom); `vitest.config.ts`
  đặt `testTimeout: 20s` vì `auth.test.ts` reset module graph ở mỗi case
  và 15 file chạy song song có lúc vượt mốc 5s mặc định.

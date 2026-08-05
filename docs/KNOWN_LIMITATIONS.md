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

92. ~~Vẫn chưa chạy PostgreSQL thật.~~ **Đã gỡ 2026-08-03.** Migration
    0001–0003 đã chạy trên PostgreSQL 17 trong Docker (`PostgresqlImpl`,
    16 bảng, `alembic_version = 0003`), và toàn bộ stack đã build và chạy
    thật. Kiểm chứng bằng cách **xóa hẳn container API** rồi tạo lại: dữ
    liệu vẫn còn trong PostgreSQL. Xem TEST_REPORT.md.

    Việc chạy thật này bắt được một lỗi mà không lần test nào phát hiện
    được: `PLANBENCH_MODEL_DIR` mặc định là đường dẫn *tương đối*
    (`artifacts/models`), giải ra `/app/artifacts` trong container —
    thư mục của root, trong khi tiến trình chạy bằng user `planbench`.
    API chết lúc khởi động với `PermissionError` trước khi phục vụ được
    request nào. `docker-compose.yml` khai `PLANBENCH_ARTIFACT_DIR` từ
    M10 nhưng chưa ai thêm `PLANBENCH_MODEL_DIR` khi M13 sinh ra nó. Đã
    sửa.

93. **Mất thư mục artifact là mất replay, dù database còn nguyên.**
    Trajectory và report nằm ngoài database (quyết định D15); bảng chỉ
    giữ URI + checksum. Phải backup `planbench.db` **và** `artifacts/`
    cùng nhau.

## Môi trường

- Test phải chạy với `PYTHONPATH=` do shell source ROS2 Jazzy (xem
  TEST_REPORT.md).
- Test frontend chạy ở môi trường Node (không jsdom); `vitest.config.ts`
  đặt `testTimeout: 20s` vì `auth.test.ts` reset module graph ở mỗi case
  và 15 file chạy song song có lúc vượt mốc 5s mặc định.

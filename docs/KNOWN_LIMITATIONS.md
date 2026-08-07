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

## Môi trường

- Test phải chạy với `PYTHONPATH=` do shell source ROS2 Jazzy (xem
  TEST_REPORT.md).
- Test frontend chạy ở môi trường Node (không jsdom); `vitest.config.ts`
  đặt `testTimeout: 20s` vì `auth.test.ts` reset module graph ở mỗi case
  và 15 file chạy song song có lúc vượt mốc 5s mặc định.

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
37b. **Adapter OpenAI-compatible viết theo giao thức đã tài liệu hoá,
    chưa chạm endpoint thật.** Phần dịch request/response được test bằng
    object giả (đó là nơi bug thật nằm), nhưng nếu một hãng lệch giao
    thức ở chi tiết nào đó thì chỉ lộ ra khi gọi thật.
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

## Môi trường

- Test phải chạy với `PYTHONPATH=` do shell source ROS2 Jazzy (xem
  TEST_REPORT.md).

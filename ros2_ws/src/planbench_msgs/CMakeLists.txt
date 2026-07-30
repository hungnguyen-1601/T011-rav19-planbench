cmake_minimum_required(VERSION 3.8)
project(planbench_msgs)

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/EpisodeStatus.msg"
  "msg/BenchmarkEvent.msg"
  "srv/LoadScenario.srv"
  "srv/ResetSimulator.srv"
  "srv/StartEpisode.srv"
  "srv/StopEpisode.srv"
  "srv/GetEpisodeResult.srv"
  DEPENDENCIES builtin_interfaces
)

ament_package()

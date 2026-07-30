# A discrete event worth recording during a benchmark run: collision,
# termination, planner failure, ROS-side error. Consumed by the
# benchmark runner and stored as episode evidence.

builtin_interfaces/Time stamp
string episode_id
string type
string message
float64 robot_x
float64 robot_y
float64 robot_theta

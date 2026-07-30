# Live status of one simulated episode.
# Mirrors planbench_schemas.episode.EpisodeStatus so the ROS layer never
# invents its own vocabulary.

string STATUS_RUNNING=running
string STATUS_SUCCESS=success
string STATUS_COLLISION=collision
string STATUS_TIMEOUT=timeout
string STATUS_STUCK=stuck
string STATUS_NO_PROGRESS=no_progress
string STATUS_STOPPED=stopped
string STATUS_NO_GLOBAL_PATH=no_global_path

builtin_interfaces/Time stamp
string scenario_name
string status
string reason
float64 elapsed_time
int32 steps
float64 goal_distance
float64 min_clearance

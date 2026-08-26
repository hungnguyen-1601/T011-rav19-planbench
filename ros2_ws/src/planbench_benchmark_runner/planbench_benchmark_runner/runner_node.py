"""Drive Nav2 through PlanBench scenarios and record real results.

Sequence per episode:

1. ``~/load_scenario`` on the simulator (map + scenario from the shared
   library, so ROS and headless benchmarks use identical geometry).
2. Wait for Nav2's ``navigate_to_pose`` action server.
3. Let TF settle, then clear both costmaps. Loading a scenario teleports
   the robot back to the start pose; without this Nav2 still believes the
   robot is where the previous episode ended and either aborts or reports
   an instant success.
4. ``~/start_episode`` — physics begins only now, after Nav2 is ready.
5. Send the goal, poll ``/episode_status`` until the simulator decides
   the outcome.
6. Read ``~/episode_result`` and print a row.

The *simulator* decides success or failure, never Nav2's action result:
Nav2 reporting SUCCEEDED means "my goal checker is satisfied", which is
not the same as the benchmark's collision/timeout/stuck verdict. Both
are recorded so a disagreement is visible rather than hidden.

ROS failure handling (spec section 14): missing action server, rejected
goal, aborted navigation and per-episode timeouts each produce a named
outcome instead of a hang.
"""

from __future__ import annotations

import sys
import time

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from nav2_msgs.srv import ClearEntireCostmap
from planbench_msgs.msg import EpisodeStatus
from planbench_msgs.srv import GetEpisodeResult, LoadScenario, StartEpisode
from rclpy.action import ActionClient
from rclpy.node import Node

SERVICE_TIMEOUT = 10.0
ACTION_TIMEOUT = 20.0


class BenchmarkRunner(Node):
    """Runs one scenario/seed at a time against a live Nav2 stack."""

    def __init__(self) -> None:
        super().__init__("planbench_benchmark_runner")
        self.declare_parameter("scenarios", ["open_space"])
        self.declare_parameter("seeds", [1])
        self.declare_parameter("episode_timeout", 180.0)
        self.declare_parameter("simulator_namespace", "/planbench_simulator")
        self.declare_parameter(
            "settle_seconds",
            3.0,
            # Seconds between teleporting the robot and sending the goal.
            # Nav2 must see the new pose on TF and rebuild its costmaps.
        )

        namespace = self.get_parameter("simulator_namespace").value
        self._load_client = self.create_client(LoadScenario, f"{namespace}/load_scenario")
        self._start_client = self.create_client(StartEpisode, f"{namespace}/start_episode")
        self._result_client = self.create_client(GetEpisodeResult, f"{namespace}/episode_result")
        self._nav_client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self._clear_global = self.create_client(
            ClearEntireCostmap, "/global_costmap/clear_entirely_global_costmap"
        )
        self._clear_local = self.create_client(
            ClearEntireCostmap, "/local_costmap/clear_entirely_local_costmap"
        )

        self._status: EpisodeStatus | None = None
        self.create_subscription(EpisodeStatus, "/episode_status", self._on_status, 10)

    def _on_status(self, message: EpisodeStatus) -> None:
        self._status = message

    # -- helpers -------------------------------------------------------

    def _call(self, client, request, description: str):
        """Blocking service call with an explicit timeout, never a hang."""
        if not client.wait_for_service(timeout_sec=SERVICE_TIMEOUT):
            raise TimeoutError(f"{description}: service unavailable after {SERVICE_TIMEOUT}s")
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=SERVICE_TIMEOUT)
        if not future.done():
            raise TimeoutError(f"{description}: no response after {SERVICE_TIMEOUT}s")
        return future.result()

    def _spin_for(self, seconds: float) -> None:
        """Keep processing callbacks for a while (TF and costmap updates)."""
        deadline = time.monotonic() + max(0.0, seconds)
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)

    def _clear_costmaps(self) -> None:
        """Best effort: a costmap that will not clear is logged, not fatal."""
        for client, name in ((self._clear_global, "global"), (self._clear_local, "local")):
            if not client.wait_for_service(timeout_sec=2.0):
                self.get_logger().warning(f"{name} costmap clear service unavailable")
                continue
            future = client.call_async(ClearEntireCostmap.Request())
            rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
            if not future.done():
                self.get_logger().warning(f"{name} costmap clear timed out")

    def run_episode(self, scenario: str, seed: int) -> dict:
        """One scenario/seed. Returns a row describing what happened."""
        row: dict = {"scenario": scenario, "seed": seed}
        try:
            loaded = self._call(
                self._load_client,
                LoadScenario.Request(scenario_name=scenario, seed=seed),
                "load_scenario",
            )
        except TimeoutError as exc:
            return {**row, "outcome": "ros_service_timeout", "detail": str(exc)}
        if not loaded.success:
            return {**row, "outcome": "scenario_load_failed", "detail": loaded.message}

        if not self._nav_client.wait_for_server(timeout_sec=ACTION_TIMEOUT):
            return {
                **row,
                "outcome": "action_server_unavailable",
                "detail": f"navigate_to_pose not available after {ACTION_TIMEOUT}s",
            }

        # The robot has just teleported to the start pose. Give Nav2 time
        # to see it on TF, then throw away costmap data describing where
        # the robot used to be.
        self._spin_for(float(self.get_parameter("settle_seconds").value))
        self._clear_costmaps()

        # Drop any status cached from the previous episode: a stale
        # terminal status would end the poll loop before this episode has
        # even moved, reporting "running" with zero elapsed time.
        self._status = None
        try:
            started = self._call(self._start_client, StartEpisode.Request(), "start_episode")
        except TimeoutError as exc:
            return {**row, "outcome": "ros_service_timeout", "detail": str(exc)}
        if not started.success:
            return {**row, "outcome": "episode_start_failed", "detail": started.message}

        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = "map"
        goal.pose.pose.position.x = loaded.goal_x
        goal.pose.pose.position.y = loaded.goal_y
        goal.pose.pose.orientation.w = 1.0

        send_future = self._nav_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future, timeout_sec=ACTION_TIMEOUT)
        handle = send_future.result() if send_future.done() else None
        if handle is None:
            return {**row, "outcome": "goal_send_timeout", "detail": "no response to send_goal"}
        if not handle.accepted:
            return {**row, "outcome": "goal_rejected", "detail": "Nav2 rejected the goal"}

        result_future = handle.get_result_async()
        deadline = time.monotonic() + float(self.get_parameter("episode_timeout").value)
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self._status is not None and self._status.status != "running":
                break  # the simulator has decided; that verdict is authoritative
            if result_future.done():
                break
        else:
            return {**row, "outcome": "runner_timeout", "detail": "episode exceeded the deadline"}

        nav_status = "unknown"
        if result_future.done():
            nav_status = {
                GoalStatus.STATUS_SUCCEEDED: "succeeded",
                GoalStatus.STATUS_ABORTED: "aborted",
                GoalStatus.STATUS_CANCELED: "canceled",
            }.get(result_future.result().status, "unknown")

        try:
            outcome = self._call(self._result_client, GetEpisodeResult.Request(), "episode_result")
        except TimeoutError as exc:
            return {**row, "outcome": "ros_service_timeout", "detail": str(exc)}

        return {
            **row,
            "outcome": outcome.status,
            "detail": outcome.reason,
            "nav2_status": nav_status,
            "elapsed": outcome.elapsed_time,
            "steps": outcome.steps,
            "length": outcome.trajectory_length,
            "clearance": outcome.min_clearance,
        }


def main(args=None) -> int:
    rclpy.init(args=args)
    node = BenchmarkRunner()
    scenarios = list(node.get_parameter("scenarios").value)
    seeds = [int(value) for value in node.get_parameter("seeds").value]

    rows = []
    try:
        for scenario in scenarios:
            for seed in seeds:
                node.get_logger().info(f"running {scenario} seed={seed}")
                rows.append(node.run_episode(scenario, seed))
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    print(
        f"\n{'scenario':22s} {'seed':>4s} {'outcome':14s} {'nav2':10s} "
        f"{'t(s)':>7s} {'len(m)':>7s} {'clear':>6s}"
    )
    for row in rows:
        print(
            f"{row['scenario']:22s} {row['seed']:>4d} {row['outcome']:14s} "
            f"{row.get('nav2_status', '-'):10s} {row.get('elapsed', 0.0):7.2f} "
            f"{row.get('length', 0.0):7.2f} {row.get('clearance', 0.0):6.3f}"
        )
        if row.get("detail"):
            print(f"    {row['detail']}")
    successes = sum(1 for row in rows if row["outcome"] == "success")
    print(f"\nsuccess {successes}/{len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""ROS 2 node exposing the PlanBench simulator to Nav2.

Package name note: this ROS package is ``planbench_simulator_node``, not
``planbench_simulator``, because the latter is the core Python library.
Two importable modules with the same name would shadow each other and
the node would silently import the wrong one.

Publishes
    /map            nav_msgs/OccupancyGrid   (latched, on load/reset)
    /scan           sensor_msgs/LaserScan
    /odom           nav_msgs/Odometry
    /tf             map->odom (identity), odom->base_link
    /tf_static      base_link->base_scan
    /clock          rosgraph_msgs/Clock      (simulation time source)
    /episode_status planbench_msgs/EpisodeStatus
    /benchmark_event planbench_msgs/BenchmarkEvent

Subscribes
    /cmd_vel        geometry_msgs/Twist

Services
    ~/load_scenario, ~/reset, ~/start_episode, ~/stop_episode, ~/episode_result

Episode arming: after loading, physics stays frozen at the start pose
until ``~/start_episode``. Stepping immediately would let the stuck
detector end the episode within seconds — before Nav2 has even finished
bringing up its costmaps. Sensor data, TF and /clock keep flowing while
armed (Nav2 needs them to warm up), so only the robot is still.

The node owns no navigation logic: it steps ``SimulationEngine`` on a
timer and translates state to messages. Nav2 closes the loop by sending
/cmd_vel, exactly as it would against real hardware.

Command safety: a /cmd_vel that stops arriving is treated as a stop
after ``cmd_vel_timeout`` seconds. Holding the last command when the
controller dies would let the robot run away — the opposite of what a
watchdog is for.
"""

from __future__ import annotations

import math

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid, Odometry
from planbench_msgs.msg import BenchmarkEvent, EpisodeStatus
from planbench_msgs.srv import (
    GetEpisodeResult,
    LoadScenario,
    ResetSimulator,
    StartEpisode,
    StopEpisode,
)
from planbench_ros_bridge.conversions import (
    BASE_FRAME,
    base_to_lidar_transform,
    from_twist,
    map_to_odom_transform,
    odom_to_base_transform,
    to_clock_msg,
    to_laser_scan,
    to_occupancy_grid,
    to_odometry,
    to_time_msg,
)
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster

from planbench_benchmark import build_scenario
from planbench_schemas.episode import EpisodeStatus as DomainStatus
from planbench_schemas.robot import SimAction
from planbench_simulator.collision import clearance_to_obstacles
from planbench_simulator.engine import EngineState, SimulationEngine
from planbench_simulator.grid import OccupancyGrid as CoreGrid

LATCHED = QoSProfile(
    depth=1,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE,
)


class SimulatorNode(Node):
    """Steps the simulator in real time and speaks ROS on both sides."""

    def __init__(self) -> None:
        super().__init__("planbench_simulator")

        self.declare_parameter(
            "scenario", "open_space", ParameterDescriptor(description="Library scenario name.")
        )
        self.declare_parameter("seed", 0)
        self.declare_parameter(
            "cmd_vel_timeout",
            1.0,
            ParameterDescriptor(
                description="Seconds without /cmd_vel before the robot is stopped."
            ),
        )
        self.declare_parameter(
            "real_time_factor",
            1.0,
            ParameterDescriptor(description="Simulation seconds per wall-clock second."),
        )
        self.declare_parameter("publish_clock", True)
        self.declare_parameter(
            "autostart",
            False,
            ParameterDescriptor(
                description=(
                    "Start the episode as soon as the scenario loads. Leave "
                    "false for Nav2: the runner starts it once navigation is "
                    "ready, so the stuck detector does not fire during bringup."
                )
            ),
        )

        self._engine = SimulationEngine()
        self._scenario = None
        self._map_data = None
        self._raw_grid: CoreGrid | None = None
        self._command = SimAction(linear_velocity=0.0, angular_velocity=0.0)
        self._last_command_time = 0.0
        self._episode_id = ""
        self._finished_logged = False
        self._running = False
        # Wall-style simulation clock: advances even while the episode is
        # armed, so Nav2 timers and sensor stamps stay fresh. The episode
        # clock (engine.time) only advances once started.
        self._sim_time = 0.0

        self._map_publisher = self.create_publisher(OccupancyGrid, "/map", LATCHED)
        self._scan_publisher = self.create_publisher(LaserScan, "/scan", 10)
        self._odom_publisher = self.create_publisher(Odometry, "/odom", 10)
        self._status_publisher = self.create_publisher(EpisodeStatus, "/episode_status", 10)
        self._event_publisher = self.create_publisher(BenchmarkEvent, "/benchmark_event", 10)
        self._clock_publisher = self.create_publisher(Clock, "/clock", 10)
        self._tf = TransformBroadcaster(self)
        self._static_tf = StaticTransformBroadcaster(self)

        self.create_subscription(Twist, "/cmd_vel", self._on_cmd_vel, 10)
        self.create_service(LoadScenario, "~/load_scenario", self._on_load_scenario)
        self.create_service(ResetSimulator, "~/reset", self._on_reset)
        self.create_service(StartEpisode, "~/start_episode", self._on_start)
        self.create_service(StopEpisode, "~/stop_episode", self._on_stop)
        self.create_service(GetEpisodeResult, "~/episode_result", self._on_episode_result)

        self._load(self.get_parameter("scenario").value, int(self.get_parameter("seed").value))

        dt = self._scenario.simulation_dt
        factor = max(0.01, float(self.get_parameter("real_time_factor").value))
        self._timer = self.create_timer(dt / factor, self._tick)
        self.get_logger().info(
            f"simulator ready: scenario={self._scenario.name} dt={dt}s rtf={factor}"
        )

    # -- setup ---------------------------------------------------------

    def _load(self, scenario_name: str, seed: int) -> None:
        map_data, scenario = build_scenario(scenario_name)
        scenario = scenario.model_copy(update={"random_seed": seed})
        self._engine.load_map(map_data)
        self._engine.load_scenario(scenario)
        self._engine.reset()
        self._map_data = map_data
        self._scenario = scenario
        self._raw_grid = CoreGrid(map_data)
        self._episode_id = f"{scenario.name}-seed{seed}"
        self._finished_logged = False
        self._running = bool(self.get_parameter("autostart").value)
        self._command = SimAction(linear_velocity=0.0, angular_velocity=0.0)
        self._last_command_time = 0.0

        stamp = to_time_msg(self._sim_time)
        self._map_publisher.publish(to_occupancy_grid(map_data, stamp))
        self._static_tf.sendTransform(base_to_lidar_transform(stamp))

    # -- ROS callbacks -------------------------------------------------

    def _on_cmd_vel(self, message: Twist) -> None:
        try:
            self._command = from_twist(message)
        except ValueError as exc:
            # Reject and stop rather than integrate a NaN.
            self._command = SimAction(linear_velocity=0.0, angular_velocity=0.0)
            self._publish_event("invalid_cmd_vel", str(exc))
            self.get_logger().warning(f"rejected /cmd_vel: {exc}")
        self._last_command_time = self._engine.time

    def _on_load_scenario(self, request, response):
        try:
            self._load(request.scenario_name, int(request.seed))
        except (ValueError, RuntimeError) as exc:
            response.success = False
            response.message = str(exc)
            return response
        response.success = True
        response.message = f"loaded {self._scenario.name}"
        response.start_x = self._scenario.start_pose.x
        response.start_y = self._scenario.start_pose.y
        response.start_theta = self._scenario.start_pose.theta
        response.goal_x = self._scenario.goal_pose.x
        response.goal_y = self._scenario.goal_pose.y
        return response

    def _on_reset(self, request, response):
        seed = int(request.seed)
        try:
            self._load(self._scenario.name, seed if seed >= 0 else self._scenario.random_seed)
        except (ValueError, RuntimeError) as exc:
            response.success = False
            response.message = str(exc)
            return response
        response.success = True
        response.message = "reset"
        return response

    def _on_start(self, request, response):
        del request
        if self._engine.is_done():
            response.success = False
            response.message = f"episode already finished ({self._engine.episode_status.value})"
            return response
        self._running = True
        # Reset the watchdog so the first tick is not treated as a timeout.
        self._last_command_time = self._engine.time
        self.get_logger().info(f"episode started: {self._scenario.name}")
        response.success = True
        response.message = "started"
        return response

    def _on_stop(self, request, response):
        del request
        if not self._running or self._engine.is_done():
            response.success = False
            response.message = "no running episode"
            return response
        self._engine.stop()
        self._running = False
        response.success = True
        response.message = "stopped"
        return response

    def _on_episode_result(self, request, response):
        del request
        finished = self._engine.is_done()
        response.finished = finished
        response.status = self._engine.episode_status.value
        response.elapsed_time = self._engine.time
        if finished:
            result = self._engine.get_result()
            response.reason = result.reason
            response.steps = result.steps
            response.trajectory_length = sum(
                math.hypot(
                    result.trajectory[i + 1].x - result.trajectory[i].x,
                    result.trajectory[i + 1].y - result.trajectory[i].y,
                )
                for i in range(len(result.trajectory) - 1)
            )
        else:
            response.reason = ""
            response.steps = 0
            response.trajectory_length = 0.0
        response.min_clearance = self._clearance()
        return response

    # -- simulation loop -----------------------------------------------

    def _tick(self) -> None:
        self._sim_time += self._scenario.simulation_dt
        if self._running and self._engine.engine_state is EngineState.RUNNING:
            timeout = float(self.get_parameter("cmd_vel_timeout").value)
            if self._engine.time - self._last_command_time > timeout:
                # Watchdog: a silent controller must mean stop, not coast.
                self._command = SimAction(linear_velocity=0.0, angular_velocity=0.0)
            self._engine.step(self._command)

        stamp = to_time_msg(self._sim_time)
        if self.get_parameter("publish_clock").value:
            self._clock_publisher.publish(to_clock_msg(self._sim_time))

        state = self._engine.get_state()
        self._tf.sendTransform([map_to_odom_transform(stamp), odom_to_base_transform(state, stamp)])
        self._odom_publisher.publish(to_odometry(state, stamp))
        self._scan_publisher.publish(
            to_laser_scan(
                self._engine.get_observation().lidar_ranges,
                self._scenario.lidar,
                stamp,
                self._scenario.simulation_dt,
            )
        )
        self._publish_status(stamp)

        if self._engine.is_done() and not self._finished_logged:
            self._finished_logged = True
            result = self._engine.get_result()
            self._publish_event(result.status.value, result.reason)
            self.get_logger().info(
                f"episode finished: {result.status.value} "
                f"({result.reason}) after {result.elapsed_time:.2f}s"
            )

    def _publish_status(self, stamp) -> None:
        state = self._engine.get_state()
        message = EpisodeStatus()
        message.stamp = stamp
        message.scenario_name = self._scenario.name
        message.status = self._engine.episode_status.value
        message.reason = self._engine.get_result().reason if self._engine.is_done() else ""
        message.elapsed_time = self._engine.time
        message.steps = int(round(self._engine.time / self._scenario.simulation_dt))
        message.goal_distance = math.hypot(
            self._scenario.goal_pose.x - state.pose.x,
            self._scenario.goal_pose.y - state.pose.y,
        )
        message.min_clearance = self._clearance()
        self._status_publisher.publish(message)

    def _publish_event(self, event_type: str, message_text: str) -> None:
        state = self._engine.get_state()
        event = BenchmarkEvent()
        event.stamp = to_time_msg(self._sim_time)
        event.episode_id = self._episode_id
        event.type = event_type
        event.message = message_text
        event.robot_x = state.pose.x
        event.robot_y = state.pose.y
        event.robot_theta = state.pose.theta
        self._event_publisher.publish(event)

    def _clearance(self) -> float:
        if self._raw_grid is None or self._scenario is None:
            return 0.0
        value = clearance_to_obstacles(
            self._engine.get_state().pose.position,
            self._scenario.robot.radius,
            self._scenario.static_obstacles,
            self._raw_grid,
        )
        return float(value) if math.isfinite(value) else self._scenario.lidar.max_range

    @property
    def episode_status(self) -> DomainStatus:
        return self._engine.episode_status


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SimulatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()


__all__ = ["SimulatorNode", "BASE_FRAME", "main"]

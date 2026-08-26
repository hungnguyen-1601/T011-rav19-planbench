"""Pure conversions between PlanBench domain objects and ROS 2 messages.

Kept free of node lifecycle and rclpy spinning so every conversion can be
unit-tested without a ROS graph — the same reason the simulator core is
free of FastAPI.

Frame conventions (REP-105):
- ``map`` is the fixed frame; the occupancy grid origin is the map origin.
- ``odom`` is continuous and drift-free here: the simulator knows ground
  truth, so ``map -> odom`` is published as identity and ``odom ->
  base_link`` carries the actual pose. Nav2 therefore needs no AMCL, and
  localisation error never contaminates a planner benchmark.
- Cell values already follow the ROS convention (FREE=0, OCCUPIED=100,
  UNKNOWN=-1), so the grid is copied through unchanged.
"""

from __future__ import annotations

import math

from builtin_interfaces.msg import Time as TimeMsg
from geometry_msgs.msg import Quaternion, Transform, TransformStamped, Twist
from nav_msgs.msg import OccupancyGrid, Odometry
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Header

from planbench_schemas.map import MapData
from planbench_schemas.robot import RobotState, SimAction
from planbench_schemas.sensor import LidarConfig

MAP_FRAME = "map"
ODOM_FRAME = "odom"
BASE_FRAME = "base_link"
LIDAR_FRAME = "base_scan"


def to_time_msg(seconds: float) -> TimeMsg:
    """Simulation seconds to a ROS time stamp."""
    if seconds < 0:
        raise ValueError(f"simulation time must be non-negative, got {seconds!r}")
    whole = int(seconds)
    return TimeMsg(sec=whole, nanosec=int(round((seconds - whole) * 1e9)))


def to_clock_msg(seconds: float) -> Clock:
    """/clock message so every node shares the simulator's time base."""
    return Clock(clock=to_time_msg(seconds))


def yaw_to_quaternion(yaw: float) -> Quaternion:
    """Planar rotation as a quaternion (roll = pitch = 0)."""
    return Quaternion(x=0.0, y=0.0, z=math.sin(yaw / 2.0), w=math.cos(yaw / 2.0))


def quaternion_to_yaw(quaternion: Quaternion) -> float:
    """Inverse of :func:`yaw_to_quaternion` for planar rotations."""
    return math.atan2(
        2.0 * (quaternion.w * quaternion.z + quaternion.x * quaternion.y),
        1.0 - 2.0 * (quaternion.y * quaternion.y + quaternion.z * quaternion.z),
    )


def to_occupancy_grid(map_data: MapData, stamp: TimeMsg) -> OccupancyGrid:
    """Domain map to nav_msgs/OccupancyGrid (values pass through)."""
    message = OccupancyGrid()
    message.header = Header(stamp=stamp, frame_id=MAP_FRAME)
    message.info.map_load_time = stamp
    message.info.resolution = map_data.resolution
    message.info.width = map_data.width
    message.info.height = map_data.height
    message.info.origin.position.x = map_data.origin.x
    message.info.origin.position.y = map_data.origin.y
    message.info.origin.position.z = 0.0
    message.info.origin.orientation = yaw_to_quaternion(map_data.origin.theta)
    message.data = [int(value) for value in map_data.cells]
    return message


def to_laser_scan(
    ranges: tuple[float, ...], config: LidarConfig, stamp: TimeMsg, scan_time: float
) -> LaserScan:
    """Simulated scan to sensor_msgs/LaserScan.

    Angles mirror ``planbench_simulator.lidar.scan`` exactly: ray i sits
    at ``-span/2 + i * span/num_rays`` relative to the robot heading, and
    the scan is expressed in the LiDAR frame, so ``angle_min`` is
    ``-span/2``.
    """
    message = LaserScan()
    message.header = Header(stamp=stamp, frame_id=LIDAR_FRAME)
    message.angle_min = -config.angle_span / 2.0
    message.angle_increment = config.angle_span / config.num_rays
    message.angle_max = message.angle_min + message.angle_increment * (config.num_rays - 1)
    message.time_increment = 0.0
    message.scan_time = scan_time
    # range_min > 0 so Nav2 discards self-hits; the simulator never
    # reports a range below it except when the robot is already inside an
    # obstacle, which the collision checker handles separately.
    message.range_min = 0.05
    message.range_max = config.max_range
    message.ranges = [float(value) for value in ranges]
    message.intensities = []
    return message


def to_odometry(state: RobotState, stamp: TimeMsg) -> Odometry:
    """Robot state to nav_msgs/Odometry in the odom frame.

    Velocities are body-frame (twist.linear.x forward, twist.angular.z
    yaw rate), which is what a differential-drive controller expects.
    """
    message = Odometry()
    message.header = Header(stamp=stamp, frame_id=ODOM_FRAME)
    message.child_frame_id = BASE_FRAME
    message.pose.pose.position.x = state.pose.x
    message.pose.pose.position.y = state.pose.y
    message.pose.pose.position.z = 0.0
    message.pose.pose.orientation = yaw_to_quaternion(state.pose.theta)
    message.twist.twist.linear.x = state.linear_velocity
    message.twist.twist.angular.z = state.angular_velocity
    return message


def to_transform(
    parent: str, child: str, x: float, y: float, yaw: float, stamp: TimeMsg
) -> TransformStamped:
    """One TF edge as a TransformStamped."""
    transform = TransformStamped()
    transform.header = Header(stamp=stamp, frame_id=parent)
    transform.child_frame_id = child
    transform.transform = Transform()
    transform.transform.translation.x = x
    transform.transform.translation.y = y
    transform.transform.translation.z = 0.0
    transform.transform.rotation = yaw_to_quaternion(yaw)
    return transform


def odom_to_base_transform(state: RobotState, stamp: TimeMsg) -> TransformStamped:
    return to_transform(ODOM_FRAME, BASE_FRAME, state.pose.x, state.pose.y, state.pose.theta, stamp)


def map_to_odom_transform(stamp: TimeMsg) -> TransformStamped:
    """Identity: the simulator has ground truth, so there is no drift."""
    return to_transform(MAP_FRAME, ODOM_FRAME, 0.0, 0.0, 0.0, stamp)


def base_to_lidar_transform(stamp: TimeMsg, offset_x: float = 0.0) -> TransformStamped:
    """Static sensor mount; the LiDAR sits at the robot centre by default."""
    return to_transform(BASE_FRAME, LIDAR_FRAME, offset_x, 0.0, 0.0, stamp)


def from_twist(twist: Twist) -> SimAction:
    """/cmd_vel to a simulator action.

    Non-finite values are rejected rather than passed on: a NaN command
    would corrupt the integrator silently.
    """
    linear = float(twist.linear.x)
    angular = float(twist.angular.z)
    if not (math.isfinite(linear) and math.isfinite(angular)):
        raise ValueError(f"cmd_vel must be finite, got linear={linear!r} angular={angular!r}")
    return SimAction(linear_velocity=linear, angular_velocity=angular)

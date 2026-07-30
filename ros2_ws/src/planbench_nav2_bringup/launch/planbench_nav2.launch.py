"""Bring up Nav2 against the PlanBench simulator (no Gazebo, no AMCL).

Localisation is intentionally absent: the simulator publishes ground-truth
map->odom, so a benchmark measures planning and control rather than AMCL
convergence.

Lifecycle nodes are managed by nav2's lifecycle_manager with autostart,
so the graph is ACTIVE without manual transitions.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

NAV2_NODES = [
    ("nav2_controller", "controller_server", "controller_server"),
    ("nav2_planner", "planner_server", "planner_server"),
    ("nav2_behaviors", "behavior_server", "behavior_server"),
    ("nav2_bt_navigator", "bt_navigator", "bt_navigator"),
]


def generate_launch_description() -> LaunchDescription:
    share = get_package_share_directory("planbench_nav2_bringup")
    default_params = os.path.join(share, "params", "nav2_params.yaml")

    params_file = LaunchConfiguration("params_file")
    autostart = LaunchConfiguration("autostart")

    nodes = [
        Node(
            package=package,
            executable=executable,
            name=name,
            output="screen",
            parameters=[params_file, {"use_sim_time": True}],
            remappings=[("/cmd_vel", "/cmd_vel")],
        )
        for package, executable, name in NAV2_NODES
    ]
    nodes.append(
        Node(
            package="nav2_lifecycle_manager",
            executable="lifecycle_manager",
            name="lifecycle_manager_navigation",
            output="screen",
            parameters=[
                {
                    "use_sim_time": True,
                    "autostart": autostart,
                    "node_names": [name for _, _, name in NAV2_NODES],
                }
            ],
        )
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("params_file", default_value=default_params),
            DeclareLaunchArgument("autostart", default_value="true"),
            *nodes,
        ]
    )

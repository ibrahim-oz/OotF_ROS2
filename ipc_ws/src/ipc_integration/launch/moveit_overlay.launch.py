"""
moveit_overlay.launch.py
------------------------
Start a MoveIt planning server on top of the already running Doosan stack
without restarting controller_manager, dsr_controller2, rosbridge, or the robot driver.

This is intended for safe plan-only experiments from the IPC web UI.

Usage:
  source /opt/ros/humble/setup.bash
  source ~/doosan_ipc_production/ipc_ws/install/setup.bash
  ros2 launch ipc_integration moveit_overlay.launch.py

Optional:
  ros2 launch ipc_integration moveit_overlay.launch.py model:=h2017 gui:=true
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory
from moveit_configs_utils import MoveItConfigsBuilder


def _build_nodes(context):
    model_value = LaunchConfiguration("model").perform(context)
    gui_value = LaunchConfiguration("gui").perform(context)

    package_name = f"dsr_moveit_config_{model_value}"
    package_path = FindPackageShare(package_name).perform(context)

    moveit_config = (
        MoveItConfigsBuilder(model_value, "robot_description", package_name)
        .robot_description(file_path=f"config/{model_value}.urdf.xacro")
        .robot_description_semantic(file_path="config/dsr.srdf")
        .trajectory_execution(file_path="config/moveit_controllers.yaml")
        .planning_pipelines(
            pipelines=["ompl", "chomp", "pilz_industrial_motion_planner"],
            default_planning_pipeline="ompl",
            load_all=False,
        )
        .to_moveit_configs()
    )

    planning_scene_monitor_parameters = {
        "publish_planning_scene": True,
        "publish_geometry_updates": True,
        "publish_state_updates": True,
        "publish_transforms_updates": True,
    }

    # Keep this overlay plan-only so it cannot command the robot by accident.
    move_group_parameters = moveit_config.to_dict()
    move_group_parameters.update(planning_scene_monitor_parameters)
    move_group_parameters["allow_trajectory_execution"] = False

    move_group_node = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        name="move_group",
        output="screen",
        parameters=[move_group_parameters],
    )

    nodes = [move_group_node]

    if gui_value == "true":
        rviz_config = os.path.join(get_package_share_directory(package_name), "launch", "moveit.rviz")
        rviz_node = Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2_moveit_overlay",
            output="log",
            arguments=["-d", rviz_config],
            parameters=[
                moveit_config.robot_description,
                moveit_config.robot_description_semantic,
                moveit_config.planning_pipelines,
                moveit_config.robot_description_kinematics,
                moveit_config.joint_limits,
            ],
        )
        nodes.append(rviz_node)

    return nodes


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("model", default_value="h2017", description="Doosan robot model"),
        DeclareLaunchArgument("gui", default_value="false", description="Start RViz together with move_group"),
        OpaqueFunction(function=_build_nodes),
    ])

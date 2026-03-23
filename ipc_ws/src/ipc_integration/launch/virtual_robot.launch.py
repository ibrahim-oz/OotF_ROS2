"""
virtual_robot.launch.py
------------------------
Launch file to connect the IPC (192.168.1.171) to a Doosan H2017 robot
running in **virtual mode** on DR DART (Windows PC at 192.168.1.180).

This uses the official dsr_bringup2_moveit.launch.py, which bringup:
  - Doosan robot driver (mode=virtual, host=DR DART IP)
  - MoveIt 2 (move_group, RViz)

Usage:
  source ~/ipc_ws/install/setup.bash
  ros2 launch ipc_integration virtual_robot.launch.py

To override the DR DART IP:
  ros2 launch ipc_integration virtual_robot.launch.py host:=192.168.1.180

To run against a real robot later:
  ros2 launch ipc_integration virtual_robot.launch.py mode:=real host:=192.168.1.100
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource, AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from launch_ros.actions import Node

def generate_launch_description():
    # Arguments - with defaults pointing at the DR DART Windows PC
    host_arg = DeclareLaunchArgument(
        'host',
        default_value='192.168.1.180',
        description='IP address of the robot controller (DR DART on Windows PC)'
    )
    model_arg = DeclareLaunchArgument(
        'model',
        default_value='h2017',
        description='Doosan robot model'
    )
    mode_arg = DeclareLaunchArgument(
        'mode',
        default_value='virtual',
        description='Operation mode: "virtual" for DR DART emulator, "real" for physical robot'
    )
    port_arg = DeclareLaunchArgument(
        'port',
        default_value='12345',
        description='Robot controller port'
    )
    name_arg = DeclareLaunchArgument(
        'name',
        default_value='',
        description='Namespace for the robot nodes'
    )
    color_arg = DeclareLaunchArgument(
        'color',
        default_value='white',
        description='Robot color for visualization'
    )

    # Use the official Doosan MoveIt bringup launch
    moveit_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('dsr_bringup2'),
                'launch',
                'dsr_bringup2_moveit.launch.py'
            ])
        ]),
        launch_arguments={
            'host':  LaunchConfiguration('host'),
            'model': LaunchConfiguration('model'),
            'mode':  LaunchConfiguration('mode'),
            'port':  LaunchConfiguration('port'),
            'name':  LaunchConfiguration('name'),
            'color': LaunchConfiguration('color'),
        }.items()
    )

    rosbridge_launch = IncludeLaunchDescription(
        AnyLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('rosbridge_server'),
                'launch',
                'rosbridge_websocket_launch.xml'
            ])
        ]),
        launch_arguments={
            'port': '9090',
            'address': '0.0.0.0'
        }.items()
    )

    tf2_web_node = Node(
        package='tf2_web_republisher',
        executable='tf2_web_republisher_node',
        name='tf2_web_republisher',
        output='screen'
    )

    return LaunchDescription([
        host_arg,
        model_arg,
        mode_arg,
        port_arg,
        name_arg,
        color_arg,
        moveit_launch,
        rosbridge_launch,
        tf2_web_node,
    ])

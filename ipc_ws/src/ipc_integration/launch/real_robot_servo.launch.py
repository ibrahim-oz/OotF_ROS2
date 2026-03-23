from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
import os
import yaml

def load_yaml(package_name, file_path):
    package_path = FindPackageShare(package_name).find(package_name)
    absolute_file_path = os.path.join(package_path, file_path)
    try:
        with open(absolute_file_path, 'r') as file:
            return yaml.safe_load(file)
    except EnvironmentError:
        return None

def generate_launch_description():
    # Arguments
    robot_ip = LaunchConfiguration('robot_ip')
    robot_model = LaunchConfiguration('robot_model')

    # 1. Doosan Driver Launch (Official)
    # Allows connecting to the real robot
    dsr_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('dsr_launch2'),
                'launch',
                'dsr_bringup.launch.py'
            ])
        ]),
        launch_arguments={
            'model': robot_model,
            'host': robot_ip,
            'mode': 'real', # Real robot mode
            'color': 'white'
        }.items()
    )
    
    # 2. MoveIt Servo Config
    # We load the config we just created
    servo_yaml = load_yaml('ipc_integration', 'config/doosan_servo_config.yaml')
    
    # Servo Node
    servo_node = Node(
        package='moveit_servo',
        executable='servo_node_main',
        parameters=[
            servo_yaml,
            {'move_group_name': 'manipulator'},
            {'is_primary_planning_scene_monitor': False}
        ],
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'robot_ip',
            default_value='192.168.137.100',
            description='IP address of the Doosan Robot Controller'
        ),
        DeclareLaunchArgument(
            'robot_model',
            default_value='h2017',
            description='Doosan Robot Model'
        ),
        dsr_bringup,
        servo_node
    ])

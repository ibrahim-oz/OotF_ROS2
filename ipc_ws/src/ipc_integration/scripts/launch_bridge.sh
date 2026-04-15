#!/bin/bash
# =============================================================================
# launch_bridge.sh — Launch script for tcp_ros_bridge.py.
# tcp_ros_bridge.py is a plain ROS2 node — no Isaac Sim dependency.
# Run from anywhere: bash ipc_ws/src/ipc_integration/scripts/launch_bridge.sh
# =============================================================================

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Auto-detect ROS distro ---
if [ -z "$ROS_DISTRO" ]; then
    ROS_DISTRO=$(ls /opt/ros/ 2>/dev/null | head -1)
    [ -z "$ROS_DISTRO" ] && { echo "ERROR: No ROS distro found in /opt/ros/"; exit 1; }
fi

echo "Using ROS_DISTRO : $ROS_DISTRO"

source "/opt/ros/$ROS_DISTRO/setup.bash"

export ROS_DISTRO
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

python3 "$SCRIPTS_DIR/tcp_ros_bridge.py"

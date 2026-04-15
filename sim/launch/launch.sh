#!/bin/bash
# =============================================================================
# launch.sh — Top-level launcher for the ootf_ros2 pipeline.
#
# Usage:
#   bash sim/launch/launch.sh virtual   # TCP bridge + Isaac Sim
#   bash sim/launch/launch.sh real      # TCP bridge + Doosan joint service client
# =============================================================================

LAUNCH_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="$(cd "$LAUNCH_DIR/../../ipc_ws/src/ipc_integration/scripts" && pwd)"

MODE=$1

if [ -z "$MODE" ]; then
    echo "ERROR: No mode specified."
    echo "Usage: bash launch/launch.sh [virtual|real]"
    exit 1
fi

case "$MODE" in
    virtual)
        echo "=== Starting in VIRTUAL mode (Isaac Sim) ==="
        bash "$LAUNCH_DIR/launch_isaacsim.sh" &
        PID_SECOND=$!

        echo "Waiting for Isaac Sim ROS2 node to come online..."
        source "/opt/ros/$(ls /opt/ros/ | head -1)/setup.bash" 2>/dev/null
        until ros2 node list 2>/dev/null | grep -q "h2017_ros_node"; do
            sleep 2
        done
        echo "Isaac Sim ready. Starting TCP bridge..."

        bash "$SCRIPTS_DIR/launch_bridge.sh" &
        PID_BRIDGE=$!
        ;;
    real)
        echo "=== Starting in REAL mode (Doosan robot) ==="
        bash "$SCRIPTS_DIR/launch_bridge.sh" &
        PID_BRIDGE=$!
        bash "$SCRIPTS_DIR/launch_joint_client.sh" &
        PID_SECOND=$!
        ;;
    *)
        echo "ERROR: Unknown mode '$MODE'. Use 'virtual' or 'real'."
        exit 1
        ;;
esac

# Cleanly stop both processes on Ctrl+C
trap "echo ''; echo 'Shutting down...'; kill $PID_BRIDGE $PID_SECOND 2>/dev/null; wait $PID_BRIDGE $PID_SECOND 2>/dev/null" INT TERM

wait $PID_BRIDGE $PID_SECOND

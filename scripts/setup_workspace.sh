#!/bin/bash

# Exit on any error
set -e

echo "============================================="
echo "   Doosan IPC ROS 2 Humble Workspace Setup"
echo "============================================="

WORKSPACE_DIR="$HOME/doosan_ipc/ipc_ws"
TARGET_DIR="$HOME/ipc_ws"

# Ensure we are on Ubuntu 22.04 and ROS 2 Humble is sourced
if [ ! -f /opt/ros/humble/setup.bash ]; then
    echo "[ERROR] ROS 2 Humble is not found. Please run ./install_ros2.sh first."
    exit 1
fi
source /opt/ros/humble/setup.bash

# Move workspace to $HOME instead of keeping inside downloaded repo if it exists.
# User instructions say: "Copy the entire doosan_ipc_production folder to your Ubuntu home directory. Rename it to doosan_ipc".
# Previous script might have been moving it to $HOME/ipc_ws.

if [ ! -d "$TARGET_DIR" ]; then
    echo "[INFO] Moving ipc_ws to $HOME..."
    if [ -d "$WORKSPACE_DIR" ]; then
        cp -r "$WORKSPACE_DIR" "$TARGET_DIR"
    else
        echo "[ERROR] Could not find $WORKSPACE_DIR"
        exit 1
    fi
else
    echo "[INFO] $TARGET_DIR already exists. Skipping copy."
fi

cd "$TARGET_DIR"

echo "[INFO] Installing specific dependencies..."
sudo apt install -y ros-humble-moveit ros-humble-ros2-control ros-humble-ros2-controllers ros-humble-joint-state-publisher-gui ros-humble-xacro

echo "[INFO] Resolving dependencies with rosdep..."
rosdep install --from-paths src --ignore-src -r -y || echo "[WARNING] Some rosdep installations might have failed, but continuing..."

echo "[INFO] Building Workspace with colcon..."
colcon build --symlink-install

echo "============================================="
echo "[SUCCESS] Workspace build completed!"
echo "To use the workspace, run:"
echo "source ~/ipc_ws/install/setup.bash"
echo "============================================="

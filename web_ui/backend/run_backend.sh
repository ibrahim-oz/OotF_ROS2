#!/bin/bash
# Start the Doosan IPC Web UI Backend
# Run this in its own terminal

set -e
cd "$(dirname "$0")"

echo "=== Doosan IPC Web UI Backend ==="
echo "[INFO] Sourcing ROS 2 environment..."
source /opt/ros/humble/setup.bash
source /home/intern/ros2_ws/install/setup.bash
source /home/intern/doosan_ipc_production/ipc_ws/install/setup.bash

echo "[INFO] Activating Python venv..."
source venv/bin/activate

echo "[INFO] Starting FastAPI server on http://0.0.0.0:8000 ..."
python3 main.py

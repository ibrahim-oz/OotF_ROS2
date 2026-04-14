#!/bin/bash

set -euo pipefail

SESSION_NAME="doosan_ipc"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

T1_CMD="cd \"$PROJECT_ROOT/ipc_ws\" && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch ipc_integration real_robot.launch.py"
T2_CMD="cd \"$PROJECT_ROOT/web_ui/backend\" && source /opt/ros/humble/setup.bash && source /home/intern/ros2_ws/install/setup.bash && source \"$PROJECT_ROOT/ipc_ws/install/setup.bash\" && if [ -f venv/bin/activate ]; then source venv/bin/activate; fi && python3 main.py"
T3_CMD="cd \"$PROJECT_ROOT/web_ui/frontend\" && npm run dev"

require_tmux() {
  if ! command -v tmux >/dev/null 2>&1; then
    echo "[ERROR] tmux was not found. Install it with: sudo apt install -y tmux"
    exit 1
  fi
}

session_exists() {
  tmux has-session -t "$SESSION_NAME" 2>/dev/null
}

start_session() {
  require_tmux

  if session_exists; then
    echo "[INFO] Session '$SESSION_NAME' is already running."
    echo "[INFO] Attach with: tmux attach -t $SESSION_NAME"
    return 0
  fi

  tmux new-session -d -s "$SESSION_NAME" -n T1 "bash -lc '$T1_CMD'"
  tmux new-window -t "$SESSION_NAME" -n T2 "bash -lc '$T2_CMD'"
  tmux new-window -t "$SESSION_NAME" -n T3 "bash -lc '$T3_CMD'"

  echo "[OK] T1, T2, and T3 have been started."
  echo "[INFO] Attach with: tmux attach -t $SESSION_NAME"
}

stop_session() {
  require_tmux

  if ! session_exists; then
    echo "[INFO] Session '$SESSION_NAME' is already stopped."
    return 0
  fi

  tmux kill-session -t "$SESSION_NAME"
  echo "[OK] Session '$SESSION_NAME' has been stopped."
}

restart_session() {
  stop_session
  start_session
}

status_session() {
  require_tmux

  if ! session_exists; then
    echo "[INFO] Session '$SESSION_NAME' is not running."
    return 1
  fi

  echo "[INFO] Session '$SESSION_NAME' is active."
  tmux list-windows -t "$SESSION_NAME"
}

attach_session() {
  require_tmux

  if ! session_exists; then
    echo "[INFO] Session '$SESSION_NAME' was not found. Run the start command first."
    exit 1
  fi

  exec tmux attach -t "$SESSION_NAME"
}

usage() {
  cat <<EOF
Usage:
  ./scripts/manage_terminals.sh start
  ./scripts/manage_terminals.sh stop
  ./scripts/manage_terminals.sh restart
  ./scripts/manage_terminals.sh status
  ./scripts/manage_terminals.sh attach
EOF
}

ACTION="${1:-start}"

case "$ACTION" in
  start)
    start_session
    ;;
  stop)
    stop_session
    ;;
  restart)
    restart_session
    ;;
  status)
    status_session
    ;;
  attach)
    attach_session
    ;;
  *)
    usage
    exit 1
    ;;
esac

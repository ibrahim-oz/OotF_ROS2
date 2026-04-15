# Doosan IPC Production System — Bring-Up & Maintenance Manual

**Robot:** Doosan H2017 Collaborative Robot  
**Platform:** Ubuntu 22.04 LTS + ROS 2 Humble  
**Revision:** 2026-04-15

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Network Topology](#2-network-topology)
3. [Hardware Prerequisites](#3-hardware-prerequisites)
4. [Software Installation (First Time)](#4-software-installation-first-time)
5. [Bring-Up Procedure](#5-bring-up-procedure)
6. [Shutdown Procedure](#6-shutdown-procedure)
7. [Web UI Reference](#7-web-ui-reference)
8. [Writing & Running Programs](#8-writing--running-programs)
9. [Vision System](#9-vision-system)
10. [Variable System](#10-variable-system)
11. [Routine Maintenance](#11-routine-maintenance)
12. [Troubleshooting](#12-troubleshooting)
13. [Configuration Reference](#13-configuration-reference)
14. [API Quick Reference](#14-api-quick-reference)

---

## 1. System Overview

The Doosan IPC Production system is a three-tier robot control platform:

```
┌─────────────────────────────────────────────────────────┐
│                   OPERATOR (Browser)                    │
│              http://localhost:5173                      │
│         React UI — Jog, Programs, I/O, Vision          │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / WebSocket
┌────────────────────────▼────────────────────────────────┐
│               FASTAPI BACKEND (Python)                  │
│                  http://localhost:8000                  │
│   Auth · Motion API · I/O · Vision · Program Runner    │
└──────────┬───────────────────────────┬──────────────────┘
           │ ROS 2 Services            │ TCP Socket
┌──────────▼──────────┐   ┌───────────▼──────────────────┐
│  ROS 2 / RosBridge  │   │  Vision System (Affix)       │
│  ws://127.0.0.1:9090│   │  192.168.137.110:50005       │
└──────────┬──────────┘   └──────────────────────────────┘
           │ Doosan Driver (TCP 12345)
┌──────────▼──────────┐
│   Doosan H2017      │
│  192.168.137.100    │
└─────────────────────┘
```

**Key processes (all must be running for full operation):**

| Process | What it does |
|---------|-------------|
| ROS 2 Robot Stack | Doosan driver, motion services, RosBridge WebSocket |
| FastAPI Backend | REST API, program execution, vision relay |
| React Frontend | Operator web UI |

---

## 2. Network Topology

| Node | IP | Port | Protocol | Notes |
|------|----|------|----------|-------|
| Doosan H2017 (real) | 192.168.137.100 | 12345 | TCP | Robot controller |
| Doosan H2017 (virtual/DR DART) | 192.168.1.180 | 12345 | TCP | Emulator for testing |
| Vision system (Affix) | 192.168.137.110 | 50005 | TCP | Vision commands |
| Affix SMB file server | 192.168.137.110 | 445 | SMB 3.0 | Images & database |
| IPC (this machine) | 192.168.1.171 | — | — | Robot control PC |
| FastAPI backend | 127.0.0.1 | 8000 | HTTP/WS | Internal API |
| RosBridge | 127.0.0.1 | 9090 | WebSocket | ROS topic proxy |
| React dev server | 127.0.0.1 | 5173 | HTTP | Web UI |

**SMB mount points (on the IPC):**

| Share | Local Path | Purpose |
|-------|-----------|---------|
| Latest results | `/mnt/affix_images` | Most recent vision images |
| All images | `/mnt/affix_all_images` | Full image archive |
| Database | `/mnt/affix_db` | SQLite vision database |

---

## 3. Hardware Prerequisites

Before powering on:

- [ ] IPC (Ubuntu 22.04) powered and network-connected
- [ ] Doosan H2017 teach pendant powered and in **Remote / Auto** mode
- [ ] Vision system (Affix) powered and reachable at `192.168.137.110`
- [ ] All Ethernet cables connected (IPC ↔ Robot, IPC ↔ Vision)
- [ ] Verify IP connectivity:
  ```bash
  ping -c 3 192.168.137.100   # Robot
  ping -c 3 192.168.137.110   # Vision
  ```

---

## 4. Software Installation (First Time)

> Skip this section if the system has already been installed.  
> Run each script from the project root: `/home/intern/doosan_ipc_production`

```bash
cd ~/doosan_ipc_production
chmod +x scripts/*.sh
```

### Step 1 — System Check
```bash
./scripts/system_check.sh
```
Verifies Ubuntu version, required packages, and hardware compatibility.

### Step 2 — Install ROS 2 Humble
```bash
./scripts/install_ros2.sh
source ~/.bashrc
```

### Step 3 — Build ROS 2 Workspace
```bash
./scripts/setup_workspace.sh
```
Builds `~/ipc_ws` with the Doosan robot driver and all ROS dependencies.

### Step 4 — Set Up Web UI
```bash
./scripts/setup_web_ui.sh
```
- Creates Python virtual environment at `web_ui/backend/venv/`
- Installs Python packages (`fastapi`, `uvicorn`, `requests`, etc.)
- Installs Node.js packages and builds the React frontend

### Step 5 — Configure Vision Shares (optional)
```bash
cp config/affix_mount.env.example config/affix_mount.env
nano config/affix_mount.env   # Fill in credentials
./scripts/mount_affix_shares.sh mount
```

Enable auto-mount on boot:
```bash
sudo cp systemd/doosan-affix-mounts.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now doosan-affix-mounts.service
```

---

## 5. Bring-Up Procedure

### Quick Start (tmux — recommended)

```bash
cd ~/doosan_ipc_production
./scripts/manage_terminals.sh start
./scripts/manage_terminals.sh attach
```

This opens a tmux session with three windows. Switch between them with `Ctrl+B` then the window number (`0`, `1`, `2`).

### Manual Start (three separate terminals)

Open three terminal windows and run one command per window:

**Terminal 1 — Robot Stack**
```bash
source /opt/ros/humble/setup.bash
source ~/doosan_ipc_production/ipc_ws/install/setup.bash
ros2 launch ipc_integration real_robot.launch.py host:=192.168.137.100
```

Wait for the output:
```
[INFO] [robot_manager]: Connected to robot at 192.168.137.100:12345
[INFO] [rosbridge_server]: Rosbridge WebSocket server started on port 9090
```

**Terminal 2 — FastAPI Backend**
```bash
cd ~/doosan_ipc_production/web_ui/backend
source venv/bin/activate
python3 main.py
```

Wait for:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**Terminal 3 — React Frontend**
```bash
cd ~/doosan_ipc_production/web_ui/frontend
npm run dev
```

Wait for:
```
  ➜  Local:   http://localhost:5173/
```

### Virtual Robot (no physical robot)

Replace the Terminal 1 command with:
```bash
ros2 launch ipc_integration virtual_robot.launch.py host:=192.168.1.180
```
DR DART emulator must be running at `192.168.1.180`.

### Accessing the UI

Open a browser and navigate to:

```
http://localhost:5173
```

Log in with:
- **Username:** `affix` (or `$UI_AUTH_USERNAME`)
- **Password:** `AImatters` (or `$UI_AUTH_PASSWORD`)

### Bring-Up Checklist

| Check | Expected |
|-------|----------|
| Robot ping | `ping 192.168.137.100` replies |
| Vision ping | `ping 192.168.137.110` replies |
| ROS stack | No `ERROR` lines, RosBridge port 9090 open |
| Backend | `curl http://localhost:8000/api/auth/status` → `{"success":true}` |
| Frontend | Browser loads login page without error |
| UI status bar | Shows "Connected" and current joint angles |
| SMB mounts | `mount \| grep affix` shows three entries |

---

## 6. Shutdown Procedure

### Graceful Shutdown

```bash
# If using tmux
./scripts/manage_terminals.sh stop

# Or press Ctrl+C in each terminal (Terminal 3 → 2 → 1)
```

### Force Kill (if processes hang)

```bash
pkill -f "ros2 launch"
pkill -f "python3 main.py"
pkill -f "vite"
```

### Unmount SMB Shares

```bash
~/doosan_ipc_production/scripts/mount_affix_shares.sh umount
```

### Teach Pendant

After software shutdown, switch the teach pendant back to **Manual** mode if physical access to the robot is needed.

---

## 7. Web UI Reference

### Panel Overview

| Tab | Purpose |
|-----|---------|
| **Operation** | Home robot, emergency stop, set speed (1–100%), pause/resume |
| **Jog** | Manual joint (J1–J6) and Cartesian (X/Y/Z/Rx/Ry/Rz) jogging |
| **TCP** | View and manually enter current tool-center-point pose |
| **Tools** | Select active tool, set TCP offset per tool |
| **I/O** | Read digital inputs (DI 1–16), toggle digital outputs (DO 1–16) |
| **Variables** | Save/load P01–P50 positions, J01–J50 joint configs |
| **Programs** | Write, save, and execute Python robot programs |
| **3D Viewer** | Live 3D visualization of robot via ROS TF frames |
| **Results** | View latest vision result images |
| **All Images** | Browse the full image archive by folder |
| **Vision DB** | Query vision SQLite database tables |
| **User Frames** | Define and manage custom reference frames |

### Login & Session

- Sessions expire after **12 hours**.
- Credentials can be changed via environment variables `UI_AUTH_USERNAME` / `UI_AUTH_PASSWORD` (requires backend restart).

### Jogging Safety

- Maximum jog speed is software-limited to **25 mm/s** (translational) and **25 °/s** (rotational).
- Single-axis jog only — only one axis moves at a time.
- Jog stops immediately when the button is released.
- Always ensure the workspace is clear before jogging.

---

## 8. Writing & Running Programs

### Where Programs Live

```
web_ui/backend/programs/
├── 0_Homing.py
├── 1_Go to Scan Position.py
├── 2_Sheet Metal Tetris.py
├── 4_Get Magnet Tool.py
├── 5_Get Vakuum Tool.py
└── Helpers/
    ├── Request_Pose.py
    └── Trigger_Vision.py
```

Files are sorted alphabetically in the UI. The numeric prefix controls display order.

### Program Template

Every program runs inside an injected preamble. The following are automatically available as globals:

```python
# Automatically injected by the backend — DO NOT redefine
USER_FRAMES  # dict of custom reference frames
P01..P50     # [x, y, z, rx, ry, rz] position variables
J01..J50     # [j1, j2, j3, j4, j5, j6] joint variables
I01..I50     # integer variables
B01..B50     # boolean variables
S01..S50     # string variables

def tp_print(msg): ...   # Print to UI log
```

A minimal program structure:

```python
import time
import socket
import requests

BACKEND = "http://localhost:8000"
AUTH_USERNAME = "affix"
AUTH_PASSWORD = "AImatters"

session = requests.Session()

def login():
    r = session.post(f"{BACKEND}/api/auth/login",
                     json={"username": AUTH_USERNAME, "password": AUTH_PASSWORD},
                     timeout=10)
    if not r.json().get("success"):
        raise Exception(f"Login failed: {r.json()}")

def movej(joints, vel=50, acc=80):
    r = session.post(f"{BACKEND}/api/move/joint",
                     json={"pos": joints, "vel": vel, "acc": acc, "sync_type": 0},
                     timeout=40).json()
    if not r.get("success"):
        raise Exception(f"MoveJ failed: {r}")

def main():
    login()
    tp_print("Starting...")
    movej(J01)   # J01 is loaded from variables.json

if __name__ == "__main__":
    main()
```

### Authentication Requirement

All API calls from programs **must** use a session with a valid cookie. Always call `login()` at the start of `main()`. Requests without a session cookie return `{"success": false, "error": "unauthorized"}`.

### Motion Functions Reference

| Function | API Endpoint | Description |
|----------|-------------|-------------|
| `movej(joints)` | `POST /api/move/joint` | Move to joint angles (degrees) |
| `movejx(pose, ref)` | `POST /api/move/jointx` | Move to Cartesian pose (IK) |
| `movel(pose, ref)` | `POST /api/move/tcp` | Linear Cartesian move |
| `jog(axis, speed)` | `POST /api/jog` | Jog single axis |
| `stop()` | `POST /api/move/stop` | Emergency stop |

### Vision TCP Calls

```python
import socket

def send_tcp(cmd, ip="192.168.137.110", port=50005):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(10)
        s.connect((ip, port))
        s.sendall(cmd.encode())
        return s.recv(4096).decode().strip()

# Usage
send_tcp("501;1")   # Station selector
send_tcp("100;1")   # Trigger vision
resp = send_tcp("124")  # Request pose
```

### Running a Program

1. Open the **Programs** tab in the UI.
2. Select or write a program.
3. Click **Save**, then **Run**.
4. Monitor output in the log pane.
5. Use **Pause / Resume / Stop** controls as needed.

### Program State Machine

```
idle → running → done
          ↓
        paused → running
          ↓
        stopped (idle)
          ↓
        error (idle)
```

---

## 9. Vision System

### Communication Protocol

The vision system exposes a raw TCP interface at `192.168.137.110:50005`. Commands and responses are ASCII strings.

### Standard Commands

| Name | Command String | Purpose |
|------|---------------|---------|
| Station Selector | `501;1` | Select the sheet metal station |
| Trigger Vision | `100;1` | Trigger image capture & processing |
| Request Pose | `124` | Get last detected object pose |
| Clear Area | `140;0` | Clear detection area |

### Pose Response Format

Response to `124` is a semicolon-separated list of ≥ 20 numeric values:

```
status;?;?;x;y;z;rx;ry;rz;?;status;?;?;x;y;z;rx;ry;rz;?
│                           │
└── Block 1 (pick pose)     └── Block 2 (place pose)
    values[3:9]                 values[13:19]
```

- Status `+0200.0` → pose is valid
- All units: mm (position), degrees (orientation)

### Orientation Convention

The vision system uses a different orientation convention than the robot:

```python
# Convert vision RZ to robot RZ
RZ_robot = normalize_deg(180.0 - RZ_vision)

# Tool is always vertical (down-facing):
FIX_RX = 0.0
FIX_RY = 180.0
```

### Vision Images (SMB)

Latest images are served by the backend from `/mnt/affix_images`. Browse via the **Results** tab.  
Full archive is available via the **All Images** tab (reads from `/mnt/affix_all_images`).

### Vision Database

The SQLite database (`Buffer.db`) is mounted at `/mnt/affix_db`. Query via the **Vision DB** tab or directly:

```bash
sqlite3 /mnt/affix_db/Buffer.db ".tables"
```

---

## 10. Variable System

Variables are stored in `web_ui/backend/variables.json` and are injected into every program at runtime.

### Variable Types

| Prefix | Type | Count | Example value |
|--------|------|-------|--------------|
| `P01`–`P50` | Position (Cartesian) | 50 | `[x, y, z, rx, ry, rz]` (mm, deg) |
| `J01`–`J50` | Joint angles | 50 | `[j1, j2, j3, j4, j5, j6]` (deg) |
| `I01`–`I50` | Integer | 50 | `0` |
| `B01`–`B50` | Boolean | 50 | `false` |
| `S01`–`S50` | String | 50 | `""` |

### Saving a Position

1. Jog the robot to the desired position.
2. Open the **Variables** tab.
3. Select the variable slot (e.g., `P01`).
4. Click **Save Current TCP** or **Save Current Joints**.

### User Frames

Custom reference frames are stored in `user_frames.json`.  
Manage via the **User Frames** tab or directly in the file:

```json
{
  "12": {
    "name": "ToolStation-2",
    "pos": [441.9, 190.82, 73.13, 0.16, -178.08, 90.03]
  }
}
```

Frame index `101` is reserved for the place station user frame (UF101).

---

## 11. Routine Maintenance

### Daily

- [ ] Check all three processes are running (ROS stack, backend, frontend).
- [ ] Verify robot connection in the UI status bar ("Connected").
- [ ] Verify vision system responds: `ping 192.168.137.110`.
- [ ] Check SMB mounts: `mount | grep affix`.
- [ ] Clear `backend.log` if large: `> web_ui/backend/backend.log`.

### Weekly

- [ ] Review `backend.log` for recurring errors.
- [ ] Back up `variables.json` and `user_frames.json`:
  ```bash
  cp web_ui/backend/variables.json web_ui/backend/variables.json.bak
  cp web_ui/backend/user_frames.json web_ui/backend/user_frames.json.bak
  ```
- [ ] Verify vision database is accessible: `ls -lh /mnt/affix_db/`.
- [ ] Test emergency stop button from UI (Operation tab → Stop).

### Monthly / After Hardware Changes

- [ ] Re-calibrate user frame UF101 if the place station has moved:
  - Jog to 3 known points on the station.
  - Update `user_frames.json` entry `"101"`.
- [ ] Re-teach pick/place positions (P variables) if fixtures have shifted.
- [ ] Update tool TCP offsets if the tool was removed/replaced.
- [ ] Rebuild the ROS 2 workspace after any driver or package updates:
  ```bash
  cd ~/doosan_ipc_production/ipc_ws
  colcon build --symlink-install
  source install/setup.bash
  ```
- [ ] Update Python packages:
  ```bash
  cd ~/doosan_ipc_production/web_ui/backend
  source venv/bin/activate
  pip install --upgrade -r requirements.txt
  ```
- [ ] Update frontend packages:
  ```bash
  cd ~/doosan_ipc_production/web_ui/frontend
  npm install
  npm run build
  ```

### Log Files

| File | Path | Notes |
|------|------|-------|
| Backend log | `web_ui/backend/backend.log` | Stdout of FastAPI + program runs |
| ROS logs | `~/.ros/log/` | ROS 2 node logs |
| System journal | `journalctl -u doosan-affix-mounts.service` | SMB mount service |

---

## 12. Troubleshooting

### Process is not running

```bash
# Check which processes are alive
ps aux | grep -E "ros2|python3 main|vite|uvicorn"

# Quick restart
./scripts/manage_terminals.sh stop
./scripts/manage_terminals.sh start
```

### "unauthorized" error when running a program

The program does not include `login()` or the session expired.  
Ensure the program calls `login()` at the start of `main()` (see Section 8).

### Backend cannot connect to ROS

**Symptom:** `GET /api/status` returns `{"ros_connected": false}`.

1. Confirm Terminal 1 (ROS stack) is running.
2. Check RosBridge is listening: `ss -tlnp | grep 9090`
3. Check for ROS package errors: scroll up in Terminal 1 for `[ERROR]` lines.
4. Rebuild the workspace if packages are missing:
   ```bash
   cd ~/doosan_ipc_production/ipc_ws
   colcon build --symlink-install
   ```

### Robot not responding / motion fails

1. Check the teach pendant — it must be in **Remote / Auto** mode with no active errors.
2. Ping the robot: `ping 192.168.137.100`
3. Check ROS launch log for connection messages.
4. Press the physical **E-Stop** reset on the teach pendant if an error was triggered.
5. Check solution space: some Cartesian targets have no IK solution. Try `movejx` with different `sol` values (0–3).

### Vision system not responding

```bash
# Test TCP connection manually
python3 -c "
import socket
s = socket.socket()
s.settimeout(5)
s.connect(('192.168.137.110', 50005))
s.sendall(b'124')
print(s.recv(4096))
s.close()
"
```

If this fails: check vision PC power and network connectivity.

### SMB shares not mounted

```bash
# Check mount status
mount | grep affix

# Remount manually
~/doosan_ipc_production/scripts/mount_affix_shares.sh umount
~/doosan_ipc_production/scripts/mount_affix_shares.sh mount

# Check credentials in config
cat ~/doosan_ipc_production/config/affix_mount.env

# Check systemd service
systemctl status doosan-affix-mounts.service
journalctl -u doosan-affix-mounts.service -n 50
```

### `ModuleNotFoundError` in programs

The program is running with a Python that does not have the required packages.  
Install into the backend venv:

```bash
~/doosan_ipc_production/web_ui/backend/venv/bin/pip install <package>
```

Also add the package to `web_ui/backend/requirements.txt`.

### Frontend shows blank page or cannot connect

1. Confirm the backend is running: `curl http://localhost:8000/docs`
2. Confirm the frontend dev server is running on port 5173.
3. Clear browser cache and reload.
4. Check browser console (F12) for specific errors.

### Port already in use

```bash
# Find and kill the process using port 8000
sudo lsof -ti:8000 | xargs kill -9

# Port 5173
sudo lsof -ti:5173 | xargs kill -9

# Port 9090
sudo lsof -ti:9090 | xargs kill -9
```

---

## 13. Configuration Reference

### Environment Variables (Backend)

Set in the shell before starting `python3 main.py`, or prefix the command:

```bash
UI_AUTH_USERNAME=affix \
UI_AUTH_PASSWORD=AImatters \
ROBOT_MODEL=h2017 \
python3 main.py
```

| Variable | Default | Description |
|----------|---------|-------------|
| `UI_AUTH_USERNAME` | `affix` | Web UI login username |
| `UI_AUTH_PASSWORD` | `AImatters` | Web UI login password |
| `ROBOT_MODEL` | `h2017` | Doosan model (affects URDF) |
| `ROBOT_COLOR` | `white` | Robot color for 3D viewer |
| `RESULTS_IMAGES_DIR` | `/mnt/affix_images` | Latest vision images directory |
| `ALL_IMAGES_DIR` | `/mnt/affix_all_images` | Full image archive directory |
| `VISION_DB_PATH` | `` | Path to vision SQLite database |
| `ROSBRIDGE_PROXY_URL` | `ws://127.0.0.1:9090` | RosBridge WebSocket URL |

### SMB Mount Configuration (`config/affix_mount.env`)

```bash
AFFIX_SERVER=192.168.137.110
AFFIX_RESULTS_SHARE=images
AFFIX_ALL_IMAGES_SHARE=images_all
AFFIX_DB_SHARE=db
AFFIX_RESULTS_MOUNT=/mnt/affix_images
AFFIX_ALL_IMAGES_MOUNT=/mnt/affix_all_images
AFFIX_DB_MOUNT=/mnt/affix_db
AFFIX_USERNAME=AFFIXENGINEERING242
AFFIX_PASSWORD=<password>
AFFIX_MOUNT_FLAGS=ro
AFFIX_SMB_VERSION=3.0
```

### Key JSON Config Files

| File | Purpose | Edit via |
|------|---------|---------|
| `web_ui/backend/variables.json` | P/J/I/B/S variables | Variables tab or direct edit |
| `web_ui/backend/user_frames.json` | Custom reference frames | User Frames tab |
| `web_ui/backend/vision_commands.json` | Named vision TCP commands | Vision tab |
| `web_ui/backend/tools.json` | Tool TCP offsets | Tools tab |

### ROS Launch Parameters

**Real robot:**
```bash
ros2 launch ipc_integration real_robot.launch.py \
    host:=192.168.137.100 \
    model:=h2017
```

**Virtual robot:**
```bash
ros2 launch ipc_integration virtual_robot.launch.py \
    host:=192.168.1.180 \
    model:=h2017
```

---

## 14. API Quick Reference

All endpoints require session authentication (cookie `affix_session`). Programs must call `login()` first.

### Authentication

```bash
# Login
curl -c cookies.txt -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"affix","password":"AImatters"}'

# Check auth status
curl -b cookies.txt http://localhost:8000/api/auth/status
```

### Status

```bash
curl -b cookies.txt http://localhost:8000/api/status
curl -b cookies.txt http://localhost:8000/api/tcp
curl -b cookies.txt http://localhost:8000/api/speed
```

### Motion

```bash
# Move to joint position (degrees)
curl -b cookies.txt -X POST http://localhost:8000/api/move/joint \
  -H "Content-Type: application/json" \
  -d '{"pos":[0,0,90,0,90,0],"vel":30,"acc":60,"sync_type":0}'

# Cartesian move (mm, degrees)
curl -b cookies.txt -X POST http://localhost:8000/api/move/tcp \
  -H "Content-Type: application/json" \
  -d '{"pos":[400,0,300,0,180,0],"vel":100,"acc":200,"ref":0,"sync_type":0}'

# Emergency stop
curl -b cookies.txt -X POST http://localhost:8000/api/move/stop

# Home
curl -b cookies.txt -X POST http://localhost:8000/api/home
```

### Digital I/O

```bash
# Read all I/O
curl -b cookies.txt http://localhost:8000/api/io/digital/all

# Set digital output 5 = ON
curl -b cookies.txt -X POST http://localhost:8000/api/io/digital/out \
  -H "Content-Type: application/json" \
  -d '{"index":5,"value":1}'
```

### Vision

```bash
# Send vision command
curl -b cookies.txt -X POST http://localhost:8000/api/vision/trigger \
  -H "Content-Type: application/json" \
  -d '{"command":"100;1"}'
```

### Programs

```bash
# List programs
curl -b cookies.txt http://localhost:8000/api/program/list

# Run a program
curl -b cookies.txt -X POST http://localhost:8000/api/program/run \
  -H "Content-Type: application/json" \
  -d '{"name":"2_Sheet Metal Tetris"}'

# Check program state (0=idle, 1=running, 2=paused, 3=error, 4=done)
curl -b cookies.txt http://localhost:8000/api/program/state

# Stop program
curl -b cookies.txt -X POST http://localhost:8000/api/program/stop
```

---

*End of Manual*

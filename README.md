# Doosan IPC Deployment Guide (Ubuntu 22.04 / ROS 2 Humble)

## 1. Transfer to Ubuntu
Copy the entire `doosan_ipc_production` folder to your Ubuntu home directory (`/home/YOUR_USERNAME/`).
Rename it to `doosan_ipc` for simplicity.

## 2. Make Scripts Executable
Open a terminal inside the `doosan_ipc` folder and run:
```bash
cd ~/doosan_ipc/scripts
chmod +x *.sh
```

## 3. Run Installation Scripts (In Order)

### Step A: System Check
Verify your hardware and OS are ready (must be Ubuntu 22.04).
```bash
./system_check.sh
```

### Step B: Install ROS 2 Humble & Dependencies
This will ask for your password (`sudo`) multiple times.
```bash
./install_ros2.sh
```
**IMPORTANT:** After this step, close your terminal and open a new one, or run `source ~/.bashrc`.

### Step C: Setup Workspace
Builds the ROS 2 workspace and installs the Doosan driver.
```bash
./setup_workspace.sh
```

### Step D: Setup Web UI
Installs Node.js, Python dependencies, and builds the UI.
```bash
./setup_web_ui.sh
```

---

## 4. Running the System

### Source the workspace first (every terminal)
```bash
source ~/ipc_ws/install/setup.bash
```

---

### Mode A: Virtual Robot via DR DART (Windows PC)
Connect to the H2017 running in the DR DART emulator on the Windows machine.

> **Requirements:** DR DART must be running and the H2017 virtual robot must be started on the Windows PC (default IP: `192.168.1.180`).

```bash
ros2 launch ipc_integration virtual_robot.launch.py
```

This will start the Doosan driver in **virtual mode** connected to `192.168.1.180:12345` and open **RViz + MoveIt**.

To use a different DR DART IP:
```bash
ros2 launch ipc_integration virtual_robot.launch.py host:=192.168.1.180
```

---

### Mode B: Real Robot
Connect to the physical Doosan H2017 robot.

```bash
ros2 launch ipc_integration real_robot.launch.py host:=192.168.137.100
```

---

### Launching the Web UI
**Backend (Terminal 1):**
```bash
cd ~/doosan_ipc/web_ui/backend
source venv/bin/activate
python3 main.py
```

**Frontend (Terminal 2):**
```bash
cd ~/doosan_ipc/web_ui/frontend
npm run dev
```

The Web UI will be available at: `http://localhost:5173`

### Start All Terminals Automatically
If you want to launch the robot stack, backend, and frontend together and restart them easily, use the tmux helper:

```bash
sudo apt install -y tmux
cd ~/doosan_ipc_production
chmod +x scripts/manage_terminals.sh
./scripts/manage_terminals.sh start
```

Useful commands:

```bash
./scripts/manage_terminals.sh restart
./scripts/manage_terminals.sh status
./scripts/manage_terminals.sh attach
./scripts/manage_terminals.sh stop
```

### Auto-Mount Affix Image and DB Shares
If `/mnt/affix_images`, `/mnt/affix_all_images`, or `/mnt/affix_db` appear empty after reboot, the SMB shares are probably not mounted yet.

1. Create the local config file:
```bash
cd ~/doosan_ipc_production
cp config/affix_mount.env.example config/affix_mount.env
```

2. Update `config/affix_mount.env` with the correct server, share names, and credentials.
The verified results share format is:
```bash
AFFIX_SERVER=192.168.137.110
AFFIX_RESULTS_SHARE=images
AFFIX_ALL_IMAGES_SHARE=images_all
AFFIX_DB_SHARE=db
AFFIX_USERNAME=AFFIXENGINEERING242
AFFIX_MOUNT_FLAGS=ro
```

3. Test the mounts manually:
```bash
chmod +x scripts/mount_affix_shares.sh
./scripts/mount_affix_shares.sh mount
./scripts/mount_affix_shares.sh status
```

4. If that works, install the systemd service:
```bash
sudo cp systemd/doosan-affix-mounts.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now doosan-affix-mounts.service
```

5. Check the service:
```bash
systemctl status doosan-affix-mounts.service
mount | grep affix
```

---

## 5. Troubleshooting Antigravity / Internet
If you are having trouble running Antigravity (or `apt install` fails):

1. **Check Internet**: `ping google.com`
2. **DNS Issues**: If ping works for IP but not domain, check `/etc/resolv.conf`.
3. **SSL/Certificates**: If you see "SSL Error" or "Failed to send":
   - Ensure your system clock is correct: `timedatectl`
   - Update CA certificates: `sudo apt update && sudo apt install --reinstall ca-certificates`


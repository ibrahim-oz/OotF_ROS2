#!/usr/bin/env python3
#web_ui/backend/main.py
"""
Doosan H2017 Web UI Backend — Full Edition
-------------------------------------------
Endpoints:
  WS   /ws                       joint_states + tcp_pose stream
  GET  /api/status
  POST /api/home                  all joints -> 0
  POST /api/move/stop             motion stop
  POST /api/jog                   native single-axis jog (motion/jog)
  POST /api/jog/stop              stop jogging (speed=0)
  POST /api/move/joint            move to target joint angles
  POST /api/move/tcp              move to target TCP (movel)
  GET  /api/tcp                   current tcp pose
  GET  /api/io/digital/in/{idx}   read digital input (1-16)
  GET  /api/io/digital/out/{idx}  read digital output (1-16)
  POST /api/io/digital/out        set digital output
  POST /api/program/run           run DRL program
  POST /api/program/stop          stop DRL
  GET  /api/program/state         DRL state
"""

import time, asyncio, json, math, threading, os, glob
from typing import Set, Dict, Any

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import JointState
from dsr_msgs2.msg import RobotStateRt

from dsr_msgs2.srv import (
    GetCurrentPosx, SetCurrentTcp,
    MoveJoint, MoveJointx, MoveLine,
    MoveSplineJoint,
    Jog,
    DrlStart, DrlStop, GetDrlState,
    GetCtrlBoxDigitalInput, GetCtrlBoxDigitalOutput, SetCtrlBoxDigitalOutput,
    MoveStop, MovePause, MoveResume,
    ChangeOperationSpeed,
    SetUserCartCoord1, SetRefCoord, GetCurrentTool
)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# ─── App ─────────────────────────────────────────────────────────

app = FastAPI(title="Doosan IPC")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.mount("/dsr_description2/meshes", StaticFiles(directory="/home/intern/doosan_ipc_production/ipc_ws/src/doosan-robot2/dsr_description2/meshes"), name="meshes")

clients: Set[WebSocket] = set()
latest_joint: dict = {}
latest_tcp:   dict = {}
ros_connected = False
ros_node      = None
event_loop    = None
last_joint_time = 0.0   # epoch seconds of last joint_states msg
CONNECTION_TIMEOUT = 3600.0  # seconds without joint_states → offline (increased to prevent premature disconnects)
latest_speed = 100
_startup_time = time.time()

# ─── Mock IO State (for virtual emulator) ─────────────────────────
_io_synced = False
# Doosan convention: 1 = OFF, 0 = ON
mock_do_state = [1] * 16

# ─── Variables Storage ───────────────────────────────────────────
VARS_FILE = "variables.json"

def _init_default_vars() -> Dict[str, Any]:
    v = {}
    for i in range(1, 51):
        idx = f"{i:02d}"
        v[f"P{idx}"] = [0.0]*6    # Cartesian Pose
        v[f"J{idx}"] = [0.0]*6    # Joint Pose
        v[f"I{idx}"] = 0          # Integer
        v[f"B{idx}"] = False      # Boolean
        v[f"S{idx}"] = ""         # String
    return v

def load_vars() -> Dict[str, Any]:
    default_vars = _init_default_vars()
    if os.path.exists(VARS_FILE):
        try:
            with open(VARS_FILE, "r") as f: 
                loaded_vars = json.load(f)
                default_vars.update(loaded_vars)
        except: 
            pass
    return default_vars

def save_vars(vars_dict: Dict[str, Any]):
    with open(VARS_FILE, "w") as f:
        json.dump(vars_dict, f, indent=2)

# ─── Programs Storage ────────────────────────────────────────────
PROG_DIR = "programs"
if not os.path.exists(PROG_DIR): os.makedirs(PROG_DIR)


# ─── ROS Bridge ──────────────────────────────────────────────────

class RosBridge(Node):
    def __init__(self):
        super().__init__("doosan_web_bridge")
        g = ReentrantCallbackGroup()

        self.sub_joints = self.create_subscription(
            JointState, "/joint_states", self._on_joints, 10, callback_group=g)
        self.sub_state = self.create_subscription(
            RobotStateRt, "/robot_state_rt", self._on_robot_state, 10, callback_group=g)

        def cli(stype, name): return self.create_client(stype, name, callback_group=g)

        self.c_posx      = cli(GetCurrentPosx,          "/aux_control/get_current_posx")
        self.c_move_j    = cli(MoveJoint,               "/motion/move_joint")
        self.c_move_jx   = cli(MoveJointx,              "/motion/move_jointx")
        self.c_move_sj   = cli(MoveSplineJoint,         "/motion/move_spline_joint")
        self.c_move_l    = cli(MoveLine,                "/motion/move_line")
        self.c_jog       = cli(Jog,                     "/motion/jog")
        self.c_stop      = cli(MoveStop,                "/motion/move_stop")
        self.c_drl_start = cli(DrlStart,                "/drl/drl_start")
        self.c_drl_stop  = cli(DrlStop,                 "/drl/drl_stop")
        self.c_drl_state = cli(GetDrlState,             "/drl/get_drl_state")
        self.c_di        = cli(GetCtrlBoxDigitalInput,  "/io/get_ctrl_box_digital_input")
        self.c_do_get    = cli(GetCtrlBoxDigitalOutput, "/io/get_ctrl_box_digital_output")
        self.c_do_set    = cli(SetCtrlBoxDigitalOutput, "/io/set_ctrl_box_digital_output")
        self.c_speed     = cli(ChangeOperationSpeed,    "/motion/change_operation_speed")
        self.c_set_tcp   = cli(SetCurrentTcp,           "/tcp/set_current_tcp")
        self.c_pause     = cli(MovePause,               "/motion/move_pause")
        self.c_resume    = cli(MoveResume,              "/motion/move_resume")
        self.c_set_uf1   = cli(SetUserCartCoord1,       "/force/set_user_cart_coord1")
        self.c_set_ref   = cli(SetRefCoord,             "/motion/set_ref_coord")
        self.c_get_tool  = cli(GetCurrentTool,          "/tool/get_current_tool")

        self.get_logger().info("Web bridge ready.")

    def _on_robot_state(self, msg: RobotStateRt):
        global latest_speed, latest_tcp
        # Update latest_speed, clamped 1-100 as safety
        latest_speed = max(1, min(100, int(msg.operation_speed_rate)))
        
        # Stream TCP pose from RT data instead of polling Service
        p = msg.actual_tcp_position
        latest_tcp = {
            "type": "tcp_pose",
            "x": round(p[0], 2), "y": round(p[1], 2), "z": round(p[2], 2),
            "rx": round(p[3], 2), "ry": round(p[4], 2), "rz": round(p[5], 2)
        }
        self._pub(latest_tcp)

    def _on_joints(self, msg: JointState):
        global ros_connected, latest_joint, last_joint_time
        ros_connected = True
        last_joint_time = __import__('time').time()
        
        # Doosan outputs joints out of order (e.g. j1, j2, j4, j5, j3, j6). We MUST sort them.
        idx_order = sorted(range(len(msg.name)), key=lambda k: msg.name[k])
        names = [msg.name[i] for i in idx_order]
        pos_rad = [msg.position[i] for i in idx_order]
        pos_deg = [math.degrees(p) for p in pos_rad]
        
        latest_joint = {
            "type": "joint_states",
            "names": names,
            "positions_rad": pos_rad,
            "positions_deg": pos_deg,
            "timestamp": self.get_clock().now().nanoseconds / 1e9,
        }
        self._pub(latest_joint)

    def poll_tool_sync(self):
        """Called from a dedicated background thread to poll the current tool."""
        while rclpy.ok():
            try:
                if self.c_get_tool.service_is_ready():
                    tr = self.call(self.c_get_tool, GetCurrentTool.Request(), timeout=1.0)
                    if tr and tr.success:
                        self._pub({"type": "current_tool", "name": tr.info})
            except Exception as e:
                self.get_logger().warning(f"Tool poll error: {e}")
            import time; time.sleep(1.0)  # 1s for tool polling

    def tcp_poll_loop(self):
        """Continuously poll TCP pose via service (fallback when RT topic is empty)"""
        while rclpy.ok():
            try:
                if self.c_posx.service_is_ready():
                    res = self.call(self.c_posx, GetCurrentPosx.Request(), timeout=1.0)
                    #if res and res.success:
                    if res:
                        p = res.pos
                        data = {
                            "type": "tcp_pose",
                            "x": round(p[0], 2),
                            "y": round(p[1], 2),
                            "z": round(p[2], 2),
                            "rx": round(p[3], 2),
                            "ry": round(p[4], 2),
                            "rz": round(p[5], 2),
                        }
                        self._pub(data)
            except Exception as e:
                self.get_logger().warning(f"TCP poll error: {e}")

            import time
            self.create_timer(0.2, self._tcp_timer_cb)

    def _pub(self, data):
        if event_loop:
            asyncio.run_coroutine_threadsafe(_broadcast(json.dumps(data)), event_loop)

    def call(self, client, req, timeout=5.0):
        if not client.wait_for_service(timeout_sec=2.0): return None
        fut = client.call_async(req)
        import time
        start = time.time()
        while not fut.done() and (time.time() - start) < timeout:
            time.sleep(0.01)
        return fut.result() if fut.done() else None



# ─── WebSocket ───────────────────────────────────────────────────

async def _broadcast(msg: str):
    dead = set()
    for ws in clients:
        try: await ws.send_text(msg)
        except: dead.add(ws)
    clients.difference_update(dead)

@app.websocket("/ws")
async def ws_ep(ws: WebSocket):
    await ws.accept(); clients.add(ws)
    # Send current connection status immediately
    await ws.send_text(json.dumps({"type": "connection_status", "connected": ros_connected}))
    if latest_joint: await ws.send_text(json.dumps(latest_joint))
    if latest_tcp:   await ws.send_text(json.dumps(latest_tcp))
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)


# ─── Status ──────────────────────────────────────────────────────

@app.get("/api/status")
def api_status():
    return {"ros_connected": ros_connected, "tcp": latest_tcp,
            "joints": latest_joint.get("positions_deg", [])}


# ─── Home / Stop ─────────────────────────────────────────────────

@app.post("/api/home")
def api_home():
    if not ros_node: return {"success": False}
    req = MoveJoint.Request()
    req.pos = [0.0] * 6
    req.vel = 30.0
    req.acc = 60.0
    req.time = 0.0
    req.mode = 0
    req.sync_type = 0 # wait
    r = ros_node.call(ros_node.c_move_j, req, timeout=30.0)
    return {"success": r.success if r else False}

@app.post("/api/move/stop")
def api_stop():
    if not ros_node: return {"success": False}
    req = MoveStop.Request(); req.stop_mode = 1
    r = ros_node.call(ros_node.c_stop, req)
    return {"success": r.success if r else False}


# ─── Native Jog ──────────────────────────────────────────────────

class JogReq(BaseModel):
    axis: int       # 0-5=joint1-6, 6-11=Tx,Ty,Tz,Rx,Ry,Rz
    speed: float    # %, positive=forward, negative=backward, 0=stop
    ref: int = 0    # 0=BASE,1=TOOL

@app.post("/api/jog")
def api_jog(b: JogReq):
    if not ros_node: return {"success": False}
    req = Jog.Request()
    req.jog_axis = b.axis
    req.move_reference = b.ref
    req.speed = b.speed
    r = ros_node.call(ros_node.c_jog, req)
    return {"success": r.success if r else False}

@app.post("/api/jog/stop")
def api_jog_stop():
    """Send speed=0 to all axes to stop jogging."""
    if not ros_node: return {"success": False}
    for ax in range(6):
        req = Jog.Request(); req.jog_axis = ax; req.move_reference = 0; req.speed = 0.0
        ros_node.call(ros_node.c_jog, req)
    return {"success": True}


# ─── Move to Target ──────────────────────────────────────────────

class MoveJointReq(BaseModel):
    pos: list[float]            # 6 joint angles [degrees]
    vel: float = 30.0
    acc: float = 60.0
    sync_type: int = 0          # 0=SYNC (wait), 1=ASYNC

@app.post("/api/move/joint")
def api_move_joint(b: MoveJointReq):
    if not ros_node: return {"success": False}
    req = MoveJoint.Request()
    req.pos = list(b.pos)
    req.vel = b.vel
    req.acc = b.acc
    req.time = 0.0
    req.mode = 0
    req.sync_type = b.sync_type
    # Wait longer if synchronous
    r = ros_node.call(ros_node.c_move_j, req, timeout=60.0 if b.sync_type == 0 else 5.0)
    return {"success": r.success if r else False}

class SpeedReq(BaseModel):
    speed: int

@app.get("/api/speed")
def api_get_speed():
    return {"success": True, "speed": latest_speed}

@app.post("/api/speed")
def api_speed(b: SpeedReq):
    global latest_speed
    if not ros_node: return {"success": False}
    req = ChangeOperationSpeed.Request()
    req.speed = max(1, min(100, b.speed))
    r = ros_node.call(ros_node.c_speed, req, timeout=5.0)
    if r and r.success:
        latest_speed = req.speed
    return {"success": r.success if r else False}

class MoveTcpReq(BaseModel):
    pos: list[float]            # [X, Y, Z, Rx, Ry, Rz]
    vel: float = 100.0          # mm/s
    acc: float = 200.0
    ref: int = 0                # 0=BASE
    sync_type: int = 0

@app.post("/api/move/tcp")
def api_move_tcp(b: MoveTcpReq):
    if not ros_node: return {"success": False}
    req = MoveLine.Request()
    req.pos = list(b.pos); req.vel = [b.vel, 30.0]; req.acc = [b.acc, 60.0]
    req.time=0.0; req.radius=0.0; req.ref=b.ref; req.mode=0; req.blend_type=0; req.sync_type=b.sync_type
    r = ros_node.call(ros_node.c_move_l, req, timeout=30.0)
    return {"success": r.success if r else False}


# ─── TCP ─────────────────────────────────────────────────────────

@app.get("/api/tcp")
def api_tcp(): return latest_tcp or {"error": "no data"}

class TcpSetReq(BaseModel):
    name: str

@app.post("/api/tcp/set")
def api_tcp_set(b: TcpSetReq):
    if not ros_node: return {"success": False}
    req = SetCurrentTcp.Request()
    req.name = b.name
    r = ros_node.call(ros_node.c_set_tcp, req)
    return {"success": r.success if r else False}

# ─── USER FRAMES ────────────────────────────────────────────────────────
USER_FRAMES_FILE = "/home/intern/doosan_ipc_production/web_ui/backend/user_frames.json"

def load_user_frames():
    try:
        with open(USER_FRAMES_FILE, 'r') as f: return json.load(f)
    except:
        return {} # ID -> {name, pos: [x,y,z,rx,ry,rz]}

def save_user_frames(data):
    with open(USER_FRAMES_FILE, 'w') as f: json.dump(data, f, indent=2)

@app.get("/api/userframes")
def api_get_ufs(): return {"success": True, "frames": load_user_frames()}

class UfSaveReq(BaseModel):
    id: int
    name: str = ""
    pos: list[float]

@app.post("/api/userframes")
def api_save_uf(b: UfSaveReq):
    frames = load_user_frames()
    frames[str(b.id)] = {"name": b.name, "pos": b.pos}
    save_user_frames(frames)
    return {"success": True}

# ─── IO ──────────────────────────────────────────────────────────

@app.get("/api/io/debug")
def api_io_debug():
    """Raw Doosan values. DI: 0=OFF,1=ON. DO: 0=ON,1=OFF."""
    result = {"di": {}, "do": {}}
    if ros_node:
        for i in range(1, 17):
            ri = GetCtrlBoxDigitalInput.Request(); ri.index = i
            r = ros_node.call(ros_node.c_di, ri)
            result["di"][f"DI{i}"] = r.value if r and r.success else "FAIL"
            ro = GetCtrlBoxDigitalOutput.Request(); ro.index = i
            ro_res = ros_node.call(ros_node.c_do_get, ro)
            result["do"][f"DO{i}"] = ro_res.value if ro_res and ro_res.success else "FAIL"
    return result

@app.get("/api/io/raw_set/{idx}/{val}")
def api_io_raw_set(idx: int, val: int):
    """RAW set: sends val directly to Doosan. No conversion. Test with browser URL."""
    print(f"[RAW SET] DO{idx} = {val} (raw, no conversion)")
    if ros_node:
        req = SetCtrlBoxDigitalOutput.Request()
        req.index = idx
        req.value = val
        r = ros_node.call(ros_node.c_do_set, req)
        # Read back
        req2 = GetCtrlBoxDigitalOutput.Request(); req2.index = idx
        r2 = ros_node.call(ros_node.c_do_get, req2)
        return {
            "set_index": idx, "set_raw_value": val,
            "set_success": r.success if r else False,
            "readback_raw": r2.value if r2 and r2.success else "FAIL"
        }
    return {"error": "no ros_node"}

@app.get("/api/io/digital/in/{idx}")
def api_di_get(idx: int):
    if not ros_node: return {"success": False}
    req = GetCtrlBoxDigitalInput.Request(); req.index = idx
    r = ros_node.call(ros_node.c_di, req)
    val = r.value if r else -1
    return {"success": r.success if r else False, "value": val, "index": idx}

@app.get("/api/io/digital/out/{idx}")
def api_do_get(idx: int):
    # Attempt to read from robot, fallback to mock state if virtual
    if ros_node:
        req = GetCtrlBoxDigitalOutput.Request(); req.index = idx
        r = ros_node.call(ros_node.c_do_get, req)
        if r and r.success:
            mock_do_state[idx-1] = r.value
            return {"success": True, "value": r.value, "index": idx}
    
    val = mock_do_state[idx-1]
    return {"success": True, "value": val, "index": idx, "mock": True}

    req.index = b.index
    req.value = b.value
    r = ros_node.call(ros_node.c_do_set, req)
    success = r.success if r else False
    # Read back to verify
    req2 = GetCtrlBoxDigitalOutput.Request(); req2.index = b.index
    r2 = ros_node.call(ros_node.c_do_get, req2)
    readback = r2.value if r2 and r2.success else "FAIL"
    print(f"[IO SET] DO{b.index}: success={success}, readback={readback}")
    return {"success": success, "readback": readback}
    return {"success": False, "error": "no ros_node"}

@app.get("/api/io/digital/all")
def api_io_all():
    global _io_synced
    """Bulk read all 16 inputs and outputs.
    """
    inputs = [-1]*16
    outputs = [-1]*16
    if ros_node:
        # Explicit startup sync
        if not _io_synced:
            print("[IO] Performing initial dummy read to clear ROS driver buffer...")
            for i in range(1, 17):
                ros_node.call(ros_node.c_di, GetCtrlBoxDigitalInput.Request(index=i))
                ros_node.call(ros_node.c_do_get, GetCtrlBoxDigitalOutput.Request(index=i))
            __import__('time').sleep(1.0)
            _io_synced = True
            print("[IO] Initial sync complete.")

        for i in range(1, 17):
            ri = GetCtrlBoxDigitalInput.Request(); ri.index = i
            r = ros_node.call(ros_node.c_di, ri)
            if r and r.success: inputs[i-1] = r.value
            
            ro = GetCtrlBoxDigitalOutput.Request(); ro.index = i
            ro_res = ros_node.call(ros_node.c_do_get, ro)
            if ro_res and ro_res.success: 
                outputs[i-1] = ro_res.value
        
        # Hardcode workaround for Doosan driver startup buffer bias (pins 1, 4, 5, 6 default to 1)
        # We enforce them to be 1 (OFF) for the first 5 seconds of the backend lifecycle.
        if time.time() - _startup_time < 5.0:
            outputs[0] = 1 # DO 1
            outputs[3] = 1 # DO 4
            outputs[4] = 1 # DO 5
            outputs[5] = 1 # DO 6

    return {"success": True, "inputs": inputs, "outputs": outputs}


# ─── Variables ───────────────────────────────────────────────────

@app.get("/api/variables")
def api_vars_get():
    return {"success": True, "variables": load_vars()}

class VarUpdateReq(BaseModel):
    name: str
    value: Any

@app.post("/api/variables")
def api_vars_set(b: VarUpdateReq):
    v = load_vars()
    v[b.name] = b.value
    save_vars(v)
    return {"success": True}

@app.post("/api/variables/delete")
def api_vars_del(b: dict):
    v = load_vars()
    if b.get('name') in v:
        del v[b['name']]
        save_vars(v)
    return {"success": True}

# ─── DRL Program ─────────────────────────────────────────────────

class ProgramReq(BaseModel):
    name: str = ""
    code: str
    robot_system: int = 0  # 0=Real

@app.get("/api/programs")
def api_prog_list():
    files = glob.glob(os.path.join(PROG_DIR, "*.py"))
    names = [os.path.splitext(os.path.basename(f))[0] for f in files if not os.path.basename(f).startswith('.')]
    return {"success": True, "programs": sorted(names)}

@app.get("/api/programs/{name}")
def api_prog_get(name: str):
    p = os.path.join(PROG_DIR, f"{name}.py")
    if os.path.exists(p):
        with open(p, "r") as f: return {"success": True, "code": f.read()}
    return {"success": False, "error": "not found"}

@app.post("/api/programs/save")
def api_prog_save(b: ProgramReq):
    if not b.name: return {"success": False, "error": "name required"}
    p = os.path.join(PROG_DIR, f"{b.name}.py")
    with open(p, "w") as f: f.write(b.code)
    return {"success": True}

# ── Python Execution Engine ──

_prog_process = None
_prog_state = 0 # 0=Idle/Stopped, 1=Running, 2=Paused, 3=Error, 4=Done
_prog_name = ""

def tp_print_impl(msg: str):
    if event_loop:
        asyncio.run_coroutine_threadsafe(
            _broadcast(json.dumps({"type": "log", "msg": str(msg)})),
            event_loop
        )
    print(f"[Program Log] {msg}")

@app.post("/api/program/run")
def api_run(b: ProgramReq):
    global _prog_process, _prog_state, _prog_name
    
    # If starting a new program while paused/running, kill the old one
    if _prog_process and _prog_process.poll() is None:
        _prog_process.terminate()
        try: _prog_process.wait(2.0)
        except: _prog_process.kill()
        if ros_node:
            ros_node.call(ros_node.c_stop, MoveStop.Request(stop_mode=1))
    
    # Wait, the subprocess doesn't have these python functions directly, it's injected locally or now run as pure python subprocess.
    # Ah, the subprocess active_run.py doesn't have the `envs` injected anymore. It runs entirely standalone without the envs!
    # Let's write `env` injection into the file itself. Wait, if it's running via Popen, it needs the preamble or we wrap it.
    
    script_path = os.path.join(PROG_DIR, ".active_run.py")

    preamble = f"""
import sys, os, time, json

# Injecting local UI state / vars
USER_FRAMES = json.loads('''{json.dumps(load_user_frames())}''')
VARS = json.loads('''{json.dumps(load_vars())}''')
for k,v in VARS.items(): globals()[k] = v

def tp_print(msg):
    print(msg, flush=True)

# USER CODE BELOW
{b.code}
"""
    
    with open(script_path, "w") as f:
        f.write(preamble)

    _prog_state = 1
    _prog_name = b.name
    
    def _read_stdout():
        global _prog_state, _prog_process
        try:
            for line in iter(_prog_process.stdout.readline, b''):
                tp_print_impl(line.decode().rstrip())
            _prog_process.stdout.close()
            _prog_process.wait()
            # Don't overwrite state if it was manually stopped (0)
            if _prog_state != 0:
                if _prog_process.returncode == 0:
                    _prog_state = 4 # Done
                elif _prog_process.returncode == -15 or _prog_process.returncode == -9:
                    pass # Killed by user
                else:
                    tp_print_impl(f"Process exited with code {_prog_process.returncode}")
                    _prog_state = 3 # Error
        except Exception as e:
            tp_print_impl(f"Execution Error: {repr(e)}")
            _prog_state = 3
    
    import subprocess
    _prog_process = subprocess.Popen(["python3", script_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    threading.Thread(target=_read_stdout, daemon=True).start()
    return {"success": True}

@app.post("/api/program/pause")
def api_prog_pause():
    global _prog_process, _prog_state
    if _prog_process and _prog_process.poll() is None:
        import signal
        _prog_process.send_signal(signal.SIGSTOP)
        _prog_state = 2
        if ros_node:
            req = MovePause.Request()
            ros_node.call(ros_node.c_pause, req)
        return {"success": True}
    return {"success": False, "error": "Not running"}

@app.post("/api/program/resume")
def api_prog_resume():
    global _prog_process, _prog_state
    if _prog_process and _prog_process.poll() is None and _prog_state == 2:
        import signal
        if ros_node:
            req = MoveResume.Request()
            ros_node.call(ros_node.c_resume, req)
        _prog_process.send_signal(signal.SIGCONT)
        _prog_state = 1
        return {"success": True}
    return {"success": False, "error": "Not paused"}

@app.post("/api/program/stop")
def api_prog_stop():
    global _prog_process, _prog_state
    if _prog_process and _prog_process.poll() is None:
        _prog_process.terminate()
        try:
            _prog_process.wait(timeout=2.0)
        except:
            _prog_process.kill()
    _prog_state = 0
    if ros_node:
        req = MoveStop.Request(); req.stop_mode = 1
        ros_node.call(ros_node.c_stop, req)
    return {"success": True}

@app.get("/api/program/state")
def api_prog_state():
    return {"success": True, "drl_state": _prog_state, "program": _prog_name}

# ─── Tools ───────────────────────────────────────────────────────

active_tool = "tcp_gripper_A"

TOOLS_FILE = "tools.json"

def _default_tool_offsets():
    return {
        "tcp_gripper_A": [0, 0, 500, 0, 0, 0],
        "tcp_gripper_B": [0, 0, 500, 0, 0, 0],
    }

def load_tool_offsets():
    defaults = _default_tool_offsets()
    if os.path.exists(TOOLS_FILE):
        try:
            with open(TOOLS_FILE, "r") as f:
                loaded = json.load(f)
                defaults.update(loaded)
        except: pass
    return defaults

def save_tool_offsets(data):
    with open(TOOLS_FILE, "w") as f:
        json.dump(data, f, indent=2)

class ToolSetReq(BaseModel):
    name: str

class ToolOffsetsReq(BaseModel):
    name: str
    offsets: list[float]  # [X, Y, Z, Rx, Ry, Rz]

@app.get("/api/tools/active")
def api_tool_get():
    return {"success": True, "active_tool": active_tool}

@app.post("/api/tools/active")
def api_tool_set(b: ToolSetReq):
    global active_tool
    active_tool = b.name
    if event_loop:
        asyncio.run_coroutine_threadsafe(_broadcast(json.dumps({"type": "tool_change", "name": active_tool})), event_loop)
    return {"success": True}

@app.get("/api/tools/offsets")
def api_tool_offsets_get():
    return {"success": True, **load_tool_offsets()}

@app.post("/api/tools/offsets")
def api_tool_offsets_set(b: ToolOffsetsReq):
    data = load_tool_offsets()
    data[b.name] = b.offsets
    save_tool_offsets(data)
    return {"success": True}


# ─── TCP Vision ───────────────────────────────────────────────────
from vision_tcp import VisionTCPClient

vision_client = VisionTCPClient(host="192.168.137.50", port=9999)

class VisionTriggerReq(BaseModel):
    command: str = "TRIGGER"

@app.post("/api/vision/trigger")
async def api_vision_trigger(b: VisionTriggerReq):
    success, msg = await vision_client.send_trigger(b.command)
    # Wait briefly for a response
    await asyncio.sleep(0.5)
    return {
        "success": success,
        "message": msg,
        "vision_data": vision_client.latest_data
    }

# ─── Startup ─────────────────────────────────────────────────────

def _ros_thread():
    global ros_node
    rclpy.init()
    ros_node = RosBridge()
    threading.Thread(target=ros_node.tcp_poll_loop, daemon=True).start()
    threading.Thread(target=ros_node.poll_tool_sync, daemon=True).start()
    ex = MultiThreadedExecutor()
    ex.add_node(ros_node)
    ex.spin()

@app.on_event("startup")
async def on_start():
    global event_loop
    event_loop = asyncio.get_event_loop()
    threading.Thread(target=_ros_thread, daemon=True).start()
    asyncio.create_task(vision_client.connect())
    asyncio.create_task(_connection_watchdog())

async def _connection_watchdog():
    """Periodically check if joint_states messages are arriving. If not, mark offline."""
    global ros_connected
    while True:
        await asyncio.sleep(2.0)
        import time as _t
        if last_joint_time > 0 and (_t.time() - last_joint_time) > CONNECTION_TIMEOUT:
            if ros_connected:
                ros_connected = False
                await _broadcast(json.dumps({"type": "connection_status", "connected": False}))
        elif ros_connected:
            await _broadcast(json.dumps({"type": "connection_status", "connected": True}))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

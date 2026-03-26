#!/usr/bin/env python3
# web_ui/backend/main.py
"""
Doosan H2017 Web UI Backend — Full Edition
-------------------------------------------
Endpoints:
  WS   /ws                       joint_states + tcp_pose stream
  GET  /api/status
  GET  /api/ros/diagnostics
  POST /api/home                 all joints -> 0
  POST /api/move/stop            motion stop
  POST /api/jog                  native single-axis jog (motion/jog)
  POST /api/jog/stop             stop jogging (speed=0)
  POST /api/move/joint           move to target joint angles
  POST /api/move/tcp             move to target TCP (movel) + motion verification
  GET  /api/tcp                  current tcp pose
  GET  /api/solution_space
  POST /api/tcp/set              set current tcp
  GET  /api/io/digital/in/{idx}  read digital input (1-16)
  GET  /api/io/digital/out/{idx} read digital output (1-16)
  POST /api/io/digital/out       set digital output
  GET  /api/io/digital/all
  POST /api/program/run          run DRL/python program
  POST /api/program/stop         stop DRL/python program
  GET  /api/program/state        DRL/python state
"""

import time
import asyncio
import json
import math
import threading
import os
import glob
import traceback
import subprocess
import signal
from typing import Set, Dict, Any, Optional, List

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import JointState
from dsr_msgs2.msg import RobotStateRt

from dsr_msgs2.srv import (
    GetCurrentPosx,
    SetCurrentTcp,
    GetCurrentTcp,
    MoveJoint,
    MoveJointx,
    MoveLine,
    MoveSplineJoint,
    Jog,
    DrlStart,
    DrlStop,
    GetDrlState,
    GetCtrlBoxDigitalInput,
    GetCtrlBoxDigitalOutput,
    SetCtrlBoxDigitalOutput,
    MoveStop,
    MovePause,
    MoveResume,
    ChangeOperationSpeed,
    SetUserCartCoord1,
    SetRefCoord,
    GetCurrentTool,
)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# ─── App ─────────────────────────────────────────────────────────

app = FastAPI(title="Doosan IPC")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/dsr_description2/meshes",
    StaticFiles(
        directory="/home/intern/doosan_ipc_production/ipc_ws/src/doosan-robot2/dsr_description2/meshes"
    ),
    name="meshes",
)

clients: Set[WebSocket] = set()
latest_joint: dict = {}
latest_tcp: dict = {}
ros_connected = False
ros_node = None
event_loop = None
last_joint_time = 0.0
CONNECTION_TIMEOUT = 3600.0  # seconds without joint_states → offline
latest_speed = 100
latest_solution_space = 0
_startup_time = time.time()
active_tool = "tcp_gripper_A"

# ─── Mock IO State (for virtual emulator) ─────────────────────────
# Doosan convention: 1 = OFF, 0 = ON
_io_synced = False
mock_do_state = [1] * 16

# ─── Variables Storage ───────────────────────────────────────────

VARS_FILE = "variables.json"


def _init_default_vars() -> Dict[str, Any]:
    v = {}
    for i in range(1, 51):
        idx = f"{i:02d}"
        v[f"P{idx}"] = [0.0] * 6
        v[f"J{idx}"] = [0.0] * 6
        v[f"I{idx}"] = 0
        v[f"B{idx}"] = False
        v[f"S{idx}"] = ""
    return v


def load_vars() -> Dict[str, Any]:
    default_vars = _init_default_vars()
    if os.path.exists(VARS_FILE):
        try:
            with open(VARS_FILE, "r") as f:
                loaded_vars = json.load(f)
                default_vars.update(loaded_vars)
        except Exception:
            pass
    return default_vars


def save_vars(vars_dict: Dict[str, Any]):
    with open(VARS_FILE, "w") as f:
        json.dump(vars_dict, f, indent=2)


# ─── Programs Storage ────────────────────────────────────────────

PROG_DIR = "programs"
if not os.path.exists(PROG_DIR):
    os.makedirs(PROG_DIR)

# ─── Motion Verification Helpers ─────────────────────────────────

def _tcp_snapshot() -> Optional[List[float]]:
    if not latest_tcp:
        return None
    try:
        return [
            float(latest_tcp.get("x", 0.0)),
            float(latest_tcp.get("y", 0.0)),
            float(latest_tcp.get("z", 0.0)),
            float(latest_tcp.get("rx", 0.0)),
            float(latest_tcp.get("ry", 0.0)),
            float(latest_tcp.get("rz", 0.0)),
        ]
    except Exception:
        return None


def _cart_distance(a: Optional[List[float]], b: Optional[List[float]]) -> Optional[float]:
    if a is None or b is None:
        return None
    return math.sqrt(
        (a[0] - b[0]) ** 2 +
        (a[1] - b[1]) ** 2 +
        (a[2] - b[2]) ** 2
    )


def _angles_distance(a: Optional[List[float]], b: Optional[List[float]]) -> Optional[float]:
    if a is None or b is None:
        return None
    return math.sqrt(
        (a[3] - b[3]) ** 2 +
        (a[4] - b[4]) ** 2 +
        (a[5] - b[5]) ** 2
    )

def _safe_list(x):
    try:
        return [float(v) for v in x]
    except:
        return None

def _wait_for_tcp_motion_start(
    before_pose: Optional[List[float]],
    timeout: float = 1.5,
    linear_threshold_mm: float = 1.0,
    angular_threshold_deg: float = 1.0,
):
    start = time.time()
    while time.time() - start < timeout:
        now_pose = _tcp_snapshot()
        if now_pose is not None and before_pose is not None:
            d_xyz = _cart_distance(now_pose, before_pose)
            d_rot = _angles_distance(now_pose, before_pose)
            if (
                (d_xyz is not None and d_xyz >= linear_threshold_mm)
                or (d_rot is not None and d_rot >= angular_threshold_deg)
            ):
                return True, now_pose
        time.sleep(0.05)
    return False, _tcp_snapshot()


def _wait_until_tcp_reached(
    target_pose: List[float],
    timeout: float = 25.0,
    linear_tol_mm: float = 5.0,
    angular_tol_deg: float = 2.0,
    check_rotation: bool = False,
):
    start = time.time()
    while time.time() - start < timeout:
        now_pose = _tcp_snapshot()
        if now_pose is not None:

            d_xyz = _cart_distance(now_pose, target_pose)
            if d_xyz is not None and d_xyz <= linear_tol_mm:
                if not check_rotation:
                    return True, now_pose
                
                d_rot = _angles_distance(now_pose, target_pose)
                if d_rot is not None and d_rot <= angular_tol_deg:
                    return True, now_pose
        time.sleep(0.05)
    return False, _tcp_snapshot()


# ─── ROS Bridge ──────────────────────────────────────────────────

class RosBridge(Node):
    def __init__(self):
        super().__init__("doosan_web_bridge")
        g = ReentrantCallbackGroup()

        self.sub_joints = self.create_subscription(
            JointState,
            "/joint_states",
            self._on_joints,
            10,
            callback_group=g,
        )
        self.sub_state = self.create_subscription(
            RobotStateRt,
            "/robot_state_rt",
            self._on_robot_state,
            10,
            callback_group=g,
        )

        def cli(stype, name):
            return self.create_client(stype, name, callback_group=g)

        self.c_posx = cli(GetCurrentPosx, "/aux_control/get_current_posx")
        self.c_move_j = cli(MoveJoint, "/motion/move_joint")
        self.c_move_jx = cli(MoveJointx, "/motion/move_jointx")
        self.c_move_sj = cli(MoveSplineJoint, "/motion/move_spline_joint")
        self.c_move_l = cli(MoveLine, "/motion/move_line")
        self.c_jog = cli(Jog, "/motion/jog")
        self.c_stop = cli(MoveStop, "/motion/move_stop")
        self.c_drl_start = cli(DrlStart, "/drl/drl_start")
        self.c_drl_stop = cli(DrlStop, "/drl/drl_stop")
        self.c_drl_state = cli(GetDrlState, "/drl/get_drl_state")
        self.c_di = cli(GetCtrlBoxDigitalInput, "/io/get_ctrl_box_digital_input")
        self.c_do_get = cli(GetCtrlBoxDigitalOutput, "/io/get_ctrl_box_digital_output")
        self.c_do_set = cli(SetCtrlBoxDigitalOutput, "/io/set_ctrl_box_digital_output")
        self.c_speed = cli(ChangeOperationSpeed, "/motion/change_operation_speed")
        self.c_set_tcp = cli(SetCurrentTcp, "/tcp/set_current_tcp")
        self.c_pause = cli(MovePause, "/motion/move_pause")
        self.c_resume = cli(MoveResume, "/motion/move_resume")
        self.c_set_uf1 = cli(SetUserCartCoord1, "/force/set_user_cart_coord1")
        self.c_set_ref = cli(SetRefCoord, "/motion/set_ref_coord")
        self.c_get_tool = cli(GetCurrentTool, "/tool/get_current_tool")
        self.c_get_tcp = cli(GetCurrentTcp, "/tcp/get_current_tcp")

        self.get_logger().info("Web bridge ready.")

    def _on_robot_state(self, msg: RobotStateRt):
        global latest_speed, latest_tcp, latest_solution_space

        latest_speed = max(1, min(100, int(msg.operation_speed_rate)))
        latest_solution_space = int(msg.solution_space)

        p = msg.actual_tcp_position
        latest_tcp = {
            "type": "tcp_pose",
            "x": round(p[0], 2),
            "y": round(p[1], 2),
            "z": round(p[2], 2),
            "rx": round(p[3], 2),
            "ry": round(p[4], 2),
            "rz": round(p[5], 2),
        }
        self._pub(latest_tcp)

    def _on_joints(self, msg: JointState):
        global ros_connected, latest_joint, last_joint_time

        ros_connected = True
        last_joint_time = time.time()

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
                    if tr and getattr(tr, "success", False):
                        self._pub({"type": "current_tool", "name": tr.info})
            except Exception as e:
                self.get_logger().warning(
                    f"Tool poll error: {type(e).__name__}: {repr(e)}\n{traceback.format_exc()}"
                )
            time.sleep(1.0)

    def poll_tcp_sync(self):
        """Called from a dedicated background thread to poll the current tcp name."""
        while rclpy.ok():
            try:
                if self.c_get_tcp.service_is_ready():
                    tr = self.call(self.c_get_tcp, GetCurrentTcp.Request(), timeout=1.0)
                    if tr and getattr(tr, "success", False):
                        self._pub({"type": "current_tcp", "name": tr.info})
            except Exception as e:
                self.get_logger().warning(f"Tcp name poll error: {e}")
            time.sleep(1.0)

    def tcp_poll_loop(self):
        """Continuously poll TCP pose via service (fallback when RT topic is empty)."""
        while rclpy.ok():
            try:
                if self.c_posx.service_is_ready():
                    res = self.call(self.c_posx, GetCurrentPosx.Request(), timeout=1.0)
                    if res:
                        try:
                            p = res.task_pos_info[0].data
                        except:
                            try:
                                p = res.pos
                            except:
                                continue
                        global latest_tcp
                        latest_tcp = {
                            "type": "tcp_pose",
                            "x": p[0],
                            "y": p[1],
                            "z": p[2],
                            "rx": p[3],
                            "ry": p[4],
                            "rz": p[5],
                        }
                        self._pub(latest_tcp)
            except Exception as e:
                self.get_logger().warning(
                    f"TCP poll error: {type(e).__name__}: {repr(e)}"
                )
            time.sleep(0.2)

    def _pub(self, data):
        if event_loop:
            asyncio.run_coroutine_threadsafe(_broadcast(json.dumps(data)), event_loop)

    def call(self, client, req, timeout=5.0):
        if not client.wait_for_service(timeout_sec=2.0):
            return None
        fut = client.call_async(req)
        start = time.time()
        while not fut.done() and (time.time() - start) < timeout:
            time.sleep(0.01)
        return fut.result() if fut.done() else None


# ─── WebSocket ───────────────────────────────────────────────────

async def _broadcast(msg: str):
    dead = set()
    for ws in clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    clients.difference_update(dead)


@app.websocket("/ws")
async def ws_ep(ws: WebSocket):
    await ws.accept()
    clients.add(ws)

    await ws.send_text(json.dumps({"type": "connection_status", "connected": ros_connected}))
    if latest_joint:
        await ws.send_text(json.dumps(latest_joint))
    if latest_tcp:
        await ws.send_text(json.dumps(latest_tcp))

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)
    except Exception:
        clients.discard(ws)


# ─── Status / Diagnostics ───────────────────────────────────────

@app.get("/api/status")
def api_status():
    return {
        "ros_connected": ros_connected,
        "tcp": latest_tcp,
        "joints": latest_joint.get("positions_deg", []),
    }


@app.get("/api/ros/diagnostics")
def api_ros_diagnostics():
    if not ros_node:
        return {
            "success": False,
            "error": "ros_node is not ready",
        }

    return {
        "success": True,
        "ros_connected": ros_connected,
        "latest_joint_available": bool(latest_joint),
        "latest_tcp_available": bool(latest_tcp),
        "services": {
            "move_joint": ros_node.c_move_j.service_is_ready(),
            "move_line": ros_node.c_move_l.service_is_ready(),
            "get_current_posx": ros_node.c_posx.service_is_ready(),
            "jog": ros_node.c_jog.service_is_ready(),
            "stop": ros_node.c_stop.service_is_ready(),
            "get_tcp_name": ros_node.c_get_tcp.service_is_ready(),
            "set_tcp": ros_node.c_set_tcp.service_is_ready(),
            "get_tool": ros_node.c_get_tool.service_is_ready(),
        },
        "latest_speed": latest_speed,
        "latest_solution_space": latest_solution_space,
        "current_tcp_feedback": latest_tcp,
        "current_joint_feedback": latest_joint,
    }


# ─── Home / Stop ─────────────────────────────────────────────────

@app.post("/api/home")
def api_home():
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    req = MoveJoint.Request()
    req.pos = [0.0] * 6
    req.vel = 30.0
    req.acc = 60.0
    req.time = 0.0
    req.mode = 0
    req.sync_type = 0

    r = ros_node.call(ros_node.c_move_j, req, timeout=30.0)
    return {"success": r.success if r else False}


@app.post("/api/move/stop")
def api_stop():
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    req = MoveStop.Request()
    req.stop_mode = 1
    r = ros_node.call(ros_node.c_stop, req)
    return {"success": r.success if r else False}


# ─── Native Jog ──────────────────────────────────────────────────

class JogReq(BaseModel):
    axis: int       # 0-5=joint1-6, 6-11=Tx,Ty,Tz,Rx,Ry,Rz
    speed: float    # %, positive=forward, negative=backward, 0=stop
    ref: int = 0    # 0=BASE,1=TOOL


@app.post("/api/jog")
def api_jog(b: JogReq):
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    req = Jog.Request()
    req.jog_axis = b.axis
    req.move_reference = b.ref
    req.speed = b.speed
    r = ros_node.call(ros_node.c_jog, req)
    return {"success": r.success if r else False}


@app.post("/api/jog/stop")
def api_jog_stop():
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    for ax in range(6):
        req = Jog.Request()
        req.jog_axis = ax
        req.move_reference = 0
        req.speed = 0.0
        ros_node.call(ros_node.c_jog, req)
    return {"success": True}


# ─── Move to Target ──────────────────────────────────────────────

class MoveJointReq(BaseModel):
    pos: list[float]
    vel: float = 30.0
    acc: float = 60.0
    sync_type: int = 0  # 0=SYNC, 1=ASYNC


@app.post("/api/move/joint")
def api_move_joint(b: MoveJointReq):
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    req = MoveJoint.Request()
    req.pos = list(b.pos)
    req.vel = b.vel
    req.acc = b.acc
    req.time = 0.0
    req.mode = 0
    req.sync_type = b.sync_type

    r = ros_node.call(
        ros_node.c_move_j,
        req,
        timeout=60.0 if b.sync_type == 0 else 5.0,
    )
    return {"success": r.success if r else False}

class SetRefReq(BaseModel):
    coord: int


@app.post("/api/ref")
def api_set_ref(b: SetRefReq):
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    req = SetRefCoord.Request()
    req.coord = int(b.coord)

    r = ros_node.call(ros_node.c_set_ref, req)

    return {"success": r.success if r else False}


class SpeedReq(BaseModel):
    speed: int


@app.get("/api/speed")
def api_get_speed():
    return {"success": True, "speed": latest_speed}


@app.post("/api/speed")
def api_speed(b: SpeedReq):
    global latest_speed

    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    req = ChangeOperationSpeed.Request()
    req.speed = max(1, min(100, b.speed))
    r = ros_node.call(ros_node.c_speed, req, timeout=5.0)
    if r and r.success:
        latest_speed = req.speed
    return {"success": r.success if r else False}


class MoveTcpReq(BaseModel):
    pos: list[float]           # [X, Y, Z, Rx, Ry, Rz]
    vel: float = 100.0         # linear speed
    acc: float = 200.0
    ref: int = 0               # 0=BASE
    sync_type: int = 0


@app.post("/api/move/tcp")
def api_move_tcp(b: MoveTcpReq):
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    if len(b.pos) != 6:
        return {"success": False, "error": "pos must contain 6 values [x,y,z,rx,ry,rz]"}

    if not ros_node.c_move_l.wait_for_service(timeout_sec=1.0):
        return {"success": False, "error": "/motion/move_line service is not available"}

    before_pose = _tcp_snapshot()

    req = MoveLine.Request()
    req.pos = [float(v) for v in b.pos]
    req.vel = [float(b.vel), 30.0]
    req.acc = [float(b.acc), 60.0]
    req.time = 0.0
    req.radius = 0.0
    req.ref = int(b.ref)
    req.mode = 0
    req.blend_type = 0
    req.sync_type = int(b.sync_type)

    r = ros_node.call(
        ros_node.c_move_l,
        req,
        timeout=60.0 if b.sync_type == 0 else 5.0,
    )

    if not r or not r.success:
        return {
            "success": False,
            "error": "MoveLine service call failed or returned success=False",
        }

    # Real-motion verification
    if before_pose is not None:
        moved, started_pose = _wait_for_tcp_motion_start(before_pose, timeout=1.5)
        if not moved:
            return {
                "success": False,
                "error": "MoveLine was accepted but no real TCP motion was detected",
                "before": _safe_list(before_pose),
                "after": _safe_list(started_pose),
                "target": _safe_list(req.pos),
            }

    # For sync mode, verify final target reach
    if b.sync_type == 0:
        try:
            reached, final_pose = _wait_until_tcp_reached(
                list(req.pos),
                timeout=25.0,
                linear_tol_mm=5.0,
                angular_tol_deg=2.0,
                check_rotation=False   # 🔥 default use-case
)
        except Exception as e:
            return {
        "success": False,
        "error": f"REACH CHECK ERROR: {str(e)}"
    }
        if not reached:
            return {
                "success": False,
                "error": "Robot started moving but target TCP was not reached within timeout",
                "final_pose": _safe_list(final_pose),
                "target": _safe_list(req.pos),
            }

    final_pose = _tcp_snapshot()

    print("DEBUG RESPONSE:",
      type(req.pos),
      type(_tcp_snapshot()))

    return {
        "success": True,
        "target": _safe_list(req.pos),
        "final_pose": _safe_list(_tcp_snapshot()),
    }


# ─── TCP ─────────────────────────────────────────────────────────

@app.get("/api/tcp")
def api_tcp():
    return latest_tcp or {"error": "no data"}


@app.get("/api/solution_space")
def api_solution_space():
    return {"success": True, "solution_space": latest_solution_space}


class TcpSetReq(BaseModel):
    name: str


@app.post("/api/tcp/set")
def api_tcp_set(b: TcpSetReq):
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    req = SetCurrentTcp.Request()

    # Different generated interfaces sometimes expose either .name or .tcp
    if hasattr(req, "name"):
        req.name = b.name
    elif hasattr(req, "tcp"):
        req.tcp = b.name
    else:
        return {"success": False, "error": "SetCurrentTcp request field not found"}

    r = ros_node.call(ros_node.c_set_tcp, req)
    return {"success": r.success if r else False}


# ─── USER FRAMES ─────────────────────────────────────────────────

USER_FRAMES_FILE = "/home/intern/doosan_ipc_production/web_ui/backend/user_frames.json"


def load_user_frames():
    try:
        with open(USER_FRAMES_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_user_frames(data):
    with open(USER_FRAMES_FILE, "w") as f:
        json.dump(data, f, indent=2)


@app.get("/api/userframes")
def api_get_ufs():
    return {"success": True, "frames": load_user_frames()}


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

class DigitalOutReq(BaseModel):
    index: int
    value: int


@app.get("/api/io/debug")
def api_io_debug():
    """Raw Doosan values. DI: 0=OFF,1=ON. DO: 0=ON,1=OFF."""
    result = {"di": {}, "do": {}}
    if ros_node:
        for i in range(1, 17):
            ri = GetCtrlBoxDigitalInput.Request()
            ri.index = i
            r = ros_node.call(ros_node.c_di, ri)
            result["di"][f"DI{i}"] = r.value if r and r.success else "FAIL"

            ro = GetCtrlBoxDigitalOutput.Request()
            ro.index = i
            ro_res = ros_node.call(ros_node.c_do_get, ro)
            result["do"][f"DO{i}"] = ro_res.value if ro_res and ro_res.success else "FAIL"
    return result


@app.get("/api/io/raw_set/{idx}/{val}")
def api_io_raw_set(idx: int, val: int):
    """RAW set: sends val directly to Doosan. No conversion."""
    print(f"[RAW SET] DO{idx} = {val} (raw, no conversion)")
    if ros_node:
        req = SetCtrlBoxDigitalOutput.Request()
        req.index = idx
        req.value = val
        r = ros_node.call(ros_node.c_do_set, req)

        req2 = GetCtrlBoxDigitalOutput.Request()
        req2.index = idx
        r2 = ros_node.call(ros_node.c_do_get, req2)

        return {
            "set_index": idx,
            "set_raw_value": val,
            "set_success": r.success if r else False,
            "readback_raw": r2.value if r2 and r2.success else "FAIL",
        }
    return {"error": "no ros_node"}


@app.get("/api/io/digital/in/{idx}")
def api_di_get(idx: int):
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    req = GetCtrlBoxDigitalInput.Request()
    req.index = idx
    r = ros_node.call(ros_node.c_di, req)
    val = r.value if r else -1
    return {"success": r.success if r else False, "value": val, "index": idx}


@app.get("/api/io/digital/out/{idx}")
def api_do_get(idx: int):
    if ros_node:
        req = GetCtrlBoxDigitalOutput.Request()
        req.index = idx
        r = ros_node.call(ros_node.c_do_get, req)
        if r and r.success:
            mock_do_state[idx - 1] = r.value
            return {"success": True, "value": r.value, "index": idx}

    val = mock_do_state[idx - 1]
    return {"success": True, "value": val, "index": idx, "mock": True}


@app.post("/api/io/digital/out")
def api_do_set(b: DigitalOutReq):
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    req = SetCtrlBoxDigitalOutput.Request()
    req.index = b.index
    req.value = b.value
    r = ros_node.call(ros_node.c_do_set, req)
    success = r.success if r else False

    req2 = GetCtrlBoxDigitalOutput.Request()
    req2.index = b.index
    r2 = ros_node.call(ros_node.c_do_get, req2)
    readback = r2.value if r2 and r2.success else "FAIL"

    print(f"[IO SET] DO{b.index}: success={success}, readback={readback}")
    if success and isinstance(readback, int):
        mock_do_state[b.index - 1] = readback

    return {"success": success, "readback": readback}


@app.get("/api/io/digital/all")
def api_io_all():
    global _io_synced

    inputs = [-1] * 16
    outputs = [-1] * 16

    if ros_node:
        if not _io_synced:
            print("[IO] Performing initial dummy read to clear ROS driver buffer...")
            for i in range(1, 17):
                ros_node.call(ros_node.c_di, GetCtrlBoxDigitalInput.Request(index=i))
                ros_node.call(ros_node.c_do_get, GetCtrlBoxDigitalOutput.Request(index=i))
            time.sleep(1.0)
            _io_synced = True
            print("[IO] Initial sync complete.")

        for i in range(1, 17):
            ri = GetCtrlBoxDigitalInput.Request()
            ri.index = i
            r = ros_node.call(ros_node.c_di, ri)
            if r and r.success:
                inputs[i - 1] = r.value

            ro = GetCtrlBoxDigitalOutput.Request()
            ro.index = i
            ro_res = ros_node.call(ros_node.c_do_get, ro)
            if ro_res and ro_res.success:
                outputs[i - 1] = ro_res.value

        if time.time() - _startup_time < 5.0:
            outputs[0] = 1
            outputs[3] = 1
            outputs[4] = 1
            outputs[5] = 1

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
    if b.get("name") in v:
        del v[b["name"]]
        save_vars(v)
    return {"success": True}


# ─── DRL / Python Program ────────────────────────────────────────

class ProgramReq(BaseModel):
    name: str = ""
    code: str
    robot_system: int = 0  # 0=Real


@app.get("/api/programs")
def api_prog_list():
    files = glob.glob(os.path.join(PROG_DIR, "*.py"))
    names = [
        os.path.splitext(os.path.basename(f))[0]
        for f in files
        if not os.path.basename(f).startswith(".")
    ]
    return {"success": True, "programs": sorted(names)}


@app.get("/api/programs/{name}")
def api_prog_get(name: str):
    p = os.path.join(PROG_DIR, f"{name}.py")
    if os.path.exists(p):
        with open(p, "r") as f:
            return {"success": True, "code": f.read()}
    return {"success": False, "error": "not found"}


@app.post("/api/programs/save")
def api_prog_save(b: ProgramReq):
    if not b.name:
        return {"success": False, "error": "name required"}

    p = os.path.join(PROG_DIR, f"{b.name}.py")
    with open(p, "w") as f:
        f.write(b.code)
    return {"success": True}


_prog_process = None
_prog_state = 0  # 0=Idle/Stopped, 1=Running, 2=Paused, 3=Error, 4=Done
_prog_name = ""


def tp_print_impl(msg: str):
    if event_loop:
        asyncio.run_coroutine_threadsafe(
            _broadcast(json.dumps({"type": "log", "msg": str(msg)})),
            event_loop,
        )
    print(f"[Program Log] {msg}")


@app.post("/api/program/run")
def api_run(b: ProgramReq):
    global _prog_process, _prog_state, _prog_name

    if _prog_process and _prog_process.poll() is None:
        _prog_process.terminate()
        try:
            _prog_process.wait(2.0)
        except Exception:
            _prog_process.kill()
        if ros_node:
            ros_node.call(ros_node.c_stop, MoveStop.Request(stop_mode=1))

    script_path = os.path.join(PROG_DIR, ".active_run.py")

    preamble = f"""
import sys, os, time, json

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
            for line in iter(_prog_process.stdout.readline, b""):
                tp_print_impl(line.decode().rstrip())
            _prog_process.stdout.close()
            _prog_process.wait()

            if _prog_state != 0:
                if _prog_process.returncode == 0:
                    _prog_state = 4
                elif _prog_process.returncode in (-15, -9):
                    pass
                else:
                    tp_print_impl(f"Process exited with code {_prog_process.returncode}")
                    _prog_state = 3
        except Exception as e:
            tp_print_impl(f"Execution Error: {repr(e)}")
            _prog_state = 3

    _prog_process = subprocess.Popen(
        ["python3", script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    threading.Thread(target=_read_stdout, daemon=True).start()
    return {"success": True}


@app.post("/api/program/pause")
def api_prog_pause():
    global _prog_process, _prog_state
    if _prog_process and _prog_process.poll() is None:
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
        except Exception:
            _prog_process.kill()

    _prog_state = 0
    if ros_node:
        req = MoveStop.Request()
        req.stop_mode = 1
        ros_node.call(ros_node.c_stop, req)
    return {"success": True}


@app.get("/api/program/state")
def api_prog_state():
    return {"success": True, "drl_state": _prog_state, "program": _prog_name}


# ─── Tools ───────────────────────────────────────────────────────

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
        except Exception:
            pass
    return defaults


def save_tool_offsets(data):
    with open(TOOLS_FILE, "w") as f:
        json.dump(data, f, indent=2)


class ToolSetReq(BaseModel):
    name: str


class ToolOffsetsReq(BaseModel):
    name: str
    offsets: list[float]


@app.get("/api/tools/active")
def api_tool_get():
    return {"success": True, "active_tool": active_tool}


@app.post("/api/tools/active")
def api_tool_set(b: ToolSetReq):
    global active_tool
    active_tool = b.name
    if event_loop:
        asyncio.run_coroutine_threadsafe(
            _broadcast(json.dumps({"type": "tool_change", "name": active_tool})),
            event_loop,
        )
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


# ─── TCP Vision ──────────────────────────────────────────────────

from vision_tcp import VisionTCPClient

vision_client = VisionTCPClient(host="192.168.137.110", port=50005)


class VisionTriggerReq(BaseModel):
    command: str = "TRIGGER"


@app.post("/api/vision/trigger")
async def api_vision_trigger(b: VisionTriggerReq):
    success, msg = await vision_client.send_trigger(b.command)
    await asyncio.sleep(0.5)
    return {
        "success": success,
        "message": msg,
        "vision_data": vision_client.latest_data,
    }


# ─── Startup ─────────────────────────────────────────────────────

def _ros_thread():
    global ros_node
    rclpy.init()
    ros_node = RosBridge()

    threading.Thread(target=ros_node.tcp_poll_loop, daemon=True).start()
    threading.Thread(target=ros_node.poll_tool_sync, daemon=True).start()
    threading.Thread(target=ros_node.poll_tcp_sync, daemon=True).start()

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
    global ros_connected
    while True:
        await asyncio.sleep(2.0)
        now = time.time()

        if last_joint_time > 0 and (now - last_joint_time) > CONNECTION_TIMEOUT:
            if ros_connected:
                ros_connected = False
                await _broadcast(json.dumps({"type": "connection_status", "connected": False}))
        elif ros_connected:
            await _broadcast(json.dumps({"type": "connection_status", "connected": True}))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
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
  POST /api/move/tcp             move to target TCP via movejointx
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
import sqlite3
import secrets
from typing import Set, Dict, Any, Optional, List
import websockets

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import JointState
from dsr_msgs2.msg import RobotStateRt
from builtin_interfaces.msg import Duration
from geometry_msgs.msg import Pose, PoseStamped
from moveit_msgs.msg import BoundingVolume, Constraints, JointConstraint, MotionPlanRequest, OrientationConstraint, PositionConstraint, RobotState
from moveit_msgs.srv import GetMotionPlan, GetPositionIK
from shape_msgs.msg import SolidPrimitive

from dsr_msgs2.srv import (
    GetCurrentPosx,
    GetCurrentToolFlangePosx,
    SetCurrentTcp,
    GetCurrentTcp,
    MoveJoint,
    MoveJointx,
    MoveLine,
    MoveSplineJoint,
    Jog,
    DrlPause,
    DrlResume,
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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import numpy as np
from scipy.spatial.transform import Rotation as R

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

app.mount(
    "/dsr_description2/mujoco_assets",
    StaticFiles(
        directory="/home/intern/doosan_ipc_production/ipc_ws/src/doosan-robot2/dsr_description2/mujoco_models"
    ),
    name="mujoco_assets",
)

RESULTS_IMAGES_DIR = os.getenv("RESULTS_IMAGES_DIR", "/mnt/affix_images").strip()
ALL_IMAGES_DIR = os.getenv("ALL_IMAGES_DIR", "/mnt/affix_all_images").strip()
VISION_DB_PATH = os.getenv("VISION_DB_PATH", "").strip()
ROBOT_MODEL = os.getenv("ROBOT_MODEL", "h2017").strip().lower()
ROBOT_COLOR = os.getenv("ROBOT_COLOR", "white").strip().lower()
ROBOT_URDF_DIR = "/home/intern/doosan_ipc_production/ipc_ws/src/doosan-robot2/dsr_description2/urdf"
ROBOT_XACRO_PATH = "/home/intern/doosan_ipc_production/ipc_ws/src/doosan-robot2/dsr_description2/xacro"
VISION_DB_CANDIDATES = [
    VISION_DB_PATH,
    "/mnt/affix_db/Buffer.db",
    "/mnt/affix_db/db/Buffer.db",
]

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
AUTH_USERNAME = os.getenv("UI_AUTH_USERNAME", "affix")
AUTH_PASSWORD = os.getenv("UI_AUTH_PASSWORD", "AImatters")
SESSION_COOKIE = "affix_session"
active_sessions: Set[str] = set()
ROSBRIDGE_PROXY_URL = os.getenv("ROSBRIDGE_PROXY_URL", "ws://127.0.0.1:9090").strip()

# ─── Mock IO State (for virtual emulator) ─────────────────────────
# Doosan convention: 1 = OFF, 0 = ON
_io_synced = False
mock_do_state = [1] * 16

# ─── Variables Storage ───────────────────────────────────────────

VARS_FILE = "variables.json"


class LoginReq(BaseModel):
    username: str = ""
    password: str = ""


def _is_authorized_request(request: Request) -> bool:
    session_id = request.cookies.get(SESSION_COOKIE)
    return bool(session_id and session_id in active_sessions)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if (
        request.method == "OPTIONS"
        or path.startswith("/api/auth/")
        or path.startswith("/docs")
        or path.startswith("/openapi")
        or path.startswith("/redoc")
        or path.startswith("/dsr_description2/")
    ):
        return await call_next(request)

    if path.startswith("/api/") and not _is_authorized_request(request):
        return JSONResponse({"success": False, "error": "unauthorized"}, status_code=401)

    return await call_next(request)


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

    dx = _angle_diff_deg(a[3], b[3])
    dy = _angle_diff_deg(a[4], b[4])
    dz = _angle_diff_deg(a[5], b[5])

    return math.sqrt(dx**2 + dy**2 + dz**2)


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


def _angle_diff_deg(a: float, b: float) -> float:
    d = a - b
    while d > 180.0:
        d -= 360.0
    while d < -180.0:
        d += 360.0
    return d


def _stable_euler(rx, ry, rz):
    def wrap(a):
        while a > 180.0:
            a -= 360.0
        while a < -180.0:
            a += 360.0
        return a

    rx = wrap(rx)
    ry = wrap(ry)
    rz = wrap(rz)

    # CRITICAL FIX (singularity)
    if abs(abs(ry) - 180.0) < 0.5:
        rx = 0.0

    return [rx, ry, rz]

def _compute_tool_dir(rx, ry, rz):
    try:
        r = R.from_euler('xyz', [rx, ry, rz], degrees=True)
        z_axis = r.apply([0, 0, 1])
        return [round(float(v), 4) for v in z_axis]
    except:
        return None

def zyz_to_xyz(rx, ry, rz):
    try:
        r = R.from_euler('zyz', [rx, ry, rz], degrees=True)
        xyz = r.as_euler('xyz', degrees=True)
        return xyz.tolist()
    except Exception as e:
        print(f"[ZYZ→XYZ ERROR] {e}")
        return [rx, ry, rz]


def xyz_to_zyz(rx, ry, rz):
    try:
        r = R.from_euler('xyz', [rx, ry, rz], degrees=True)
        zyz = r.as_euler('zyz', degrees=True)
        return zyz.tolist()
    except Exception as e:
        print(f"[XYZ→ZYZ ERROR] {e}")
        return [rx, ry, rz]


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
        self.c_tool_flange_posx = cli(GetCurrentToolFlangePosx, "/aux_control/get_current_tool_flange_posx")
        self.c_move_j = cli(MoveJoint, "/motion/move_joint")
        self.c_move_jx = cli(MoveJointx, "/motion/move_jointx")
        self.c_move_sj = cli(MoveSplineJoint, "/motion/move_spline_joint")
        self.c_move_l = cli(MoveLine, "/motion/move_line")
        self.c_jog = cli(Jog, "/motion/jog")
        self.c_stop = cli(MoveStop, "/motion/move_stop")
        self.c_drl_pause = cli(DrlPause, "/drl/drl_pause")
        self.c_drl_resume = cli(DrlResume, "/drl/drl_resume")
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
        self.c_moveit_plan = cli(GetMotionPlan, "/plan_kinematic_path")
        self.c_moveit_ik = cli(GetPositionIK, "/compute_ik")

        self.get_logger().info("Web bridge ready.")

    def _on_robot_state(self, msg: RobotStateRt):
        global latest_speed, latest_tcp, latest_solution_space

        latest_speed = max(1, min(100, int(msg.operation_speed_rate)))
        latest_solution_space = int(msg.solution_space)

        p = msg.actual_tcp_position
        rx0, ry0, rz0 = zyz_to_xyz(p[3], p[4], p[5])
        rx, ry, rz = _stable_euler(rx0, ry0, rz0)
        tool_dir = _compute_tool_dir(rx, ry, rz)
        latest_tcp = {
            "type": "tcp_pose",
            "x": round(p[0], 2),
            "y": round(p[1], 2),
            "z": round(p[2], 2),
            "rx": round(rx, 2),
            "ry": round(ry, 2),
            "rz": round(rz, 2),
            "tool_dir": tool_dir,
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
                        rx0, ry0, rz0 = zyz_to_xyz(p[3], p[4], p[5])
                        rx, ry, rz = _stable_euler(rx0, ry0, rz0)
                        tool_dir = _compute_tool_dir(rx, ry, rz)
                        latest_tcp = {
                            "type": "tcp_pose",
                            "x": round(p[0], 2),
                            "y": round(p[1], 2),
                            "z": round(p[2], 2),
                            "rx": round(rx, 2),
                            "ry": round(ry, 2),
                            "rz": round(rz, 2),
                            "tool_dir": tool_dir,
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

    def dispatch(self, client, req):
        if not client.wait_for_service(timeout_sec=0.2):
            return False
        client.call_async(req)
        return True


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
    session_id = ws.cookies.get(SESSION_COOKIE)
    if not session_id or session_id not in active_sessions:
        await ws.close(code=1008)
        return

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


@app.websocket("/rosbridge")
async def rosbridge_proxy_ep(ws: WebSocket):
    session_id = ws.cookies.get(SESSION_COOKIE)
    if not session_id or session_id not in active_sessions:
        await ws.close(code=1008)
        return

    await ws.accept()

    upstream = None
    relay_tasks = []

    async def client_to_upstream():
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "text" in message and message["text"] is not None:
                await upstream.send(message["text"])
            elif "bytes" in message and message["bytes"] is not None:
                await upstream.send(message["bytes"])

    async def upstream_to_client():
        while True:
            message = await upstream.recv()
            if isinstance(message, bytes):
                await ws.send_bytes(message)
            else:
                await ws.send_text(message)

    try:
        upstream = await websockets.connect(ROSBRIDGE_PROXY_URL)
        relay_tasks = [
            asyncio.create_task(client_to_upstream()),
            asyncio.create_task(upstream_to_client()),
        ]
        done, pending = await asyncio.wait(relay_tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc:
                raise exc
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.close(code=1011, reason=f"rosbridge proxy error: {type(e).__name__}")
        except Exception:
            pass
    finally:
        for task in relay_tasks:
            task.cancel()
        if upstream is not None:
            try:
                await upstream.close()
            except Exception:
                pass


# ─── Status / Diagnostics ───────────────────────────────────────

@app.get("/api/auth/status")
def api_auth_status(request: Request):
    return {"success": True, "authenticated": _is_authorized_request(request)}


@app.get("/api/robot/urdf")
def api_robot_urdf():
    xacro_file = os.path.join(ROBOT_XACRO_PATH, f"{ROBOT_MODEL}.urdf.xacro")
    if os.path.exists(xacro_file):
        try:
            result = subprocess.run(
                [
                    "xacro",
                    xacro_file,
                    f"color:={ROBOT_COLOR}",
                    "namespace:=",
                    "gripper:=none",
                    "use_gazebo:=false",
                    "use_mujoco:=false",
                    "host:=",
                    "port:=",
                    "rt_host:=",
                    "mode:=virtual",
                    f"model:={ROBOT_MODEL}",
                    "update_rate:=100",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return {
                "success": True,
                "model": ROBOT_MODEL,
                "color": ROBOT_COLOR,
                "path": xacro_file,
                "source": "xacro",
                "urdf": result.stdout,
            }
        except Exception as e:
            pass

    candidates = [
        os.path.join(ROBOT_URDF_DIR, f"{ROBOT_MODEL}.urdf"),
        os.path.join(ROBOT_URDF_DIR, f"{ROBOT_MODEL}.{ROBOT_COLOR}.urdf"),
    ]

    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return {
                    "success": True,
                    "model": ROBOT_MODEL,
                    "color": ROBOT_COLOR,
                    "path": path,
                    "urdf": f.read(),
                }

    return {
        "success": False,
        "model": ROBOT_MODEL,
        "color": ROBOT_COLOR,
        "error": f"URDF file not found under {ROBOT_URDF_DIR}",
        "candidates": candidates,
    }


@app.post("/api/auth/login")
def api_auth_login(body: LoginReq):
    if body.username != AUTH_USERNAME or body.password != AUTH_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    session_id = secrets.token_urlsafe(32)
    active_sessions.add(session_id)

    response = JSONResponse({"success": True, "authenticated": True})
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 12,
    )
    return response


@app.post("/api/auth/logout")
def api_auth_logout(request: Request):
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        active_sessions.discard(session_id)

    response = JSONResponse({"success": True})
    response.delete_cookie(SESSION_COOKIE)
    return response

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
            "move_jointx": ros_node.c_move_jx.service_is_ready(), 
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


class MoveItJointPlanReq(BaseModel):
    pos: list[float]
    group_name: str = "manipulator"
    pipeline_id: str = ""
    planner_id: str = ""
    num_planning_attempts: int = 1
    allowed_planning_time: float = 3.0
    max_velocity_scaling_factor: float = 0.25
    max_acceleration_scaling_factor: float = 0.25


class MoveItPosePlanReq(BaseModel):
    pos: list[float]  # [x_mm, y_mm, z_mm, rx_deg, ry_deg, rz_deg]
    group_name: str = "manipulator"
    pipeline_id: str = "pilz_industrial_motion_planner"
    planner_id: str = "LIN"
    tip_link: str = "tcp_gripper_A"
    frame_id: str = "base_link"
    position_tolerance_mm: float = 5.0
    orientation_tolerance_deg: float = 5.0
    allowed_planning_time: float = 3.0
    num_planning_attempts: int = 1
    max_velocity_scaling_factor: float = 0.25
    max_acceleration_scaling_factor: float = 0.25


_moveit_last_plan = None
_MOVEIT_ERROR_NAMES = {
    1: "SUCCESS",
    99999: "FAILURE",
    -1: "PLANNING_FAILED",
    -2: "INVALID_MOTION_PLAN",
    -3: "MOTION_PLAN_INVALIDATED_BY_ENVIRONMENT_CHANGE",
    -4: "CONTROL_FAILED",
    -5: "UNABLE_TO_AQUIRE_SENSOR_DATA",
    -6: "TIMED_OUT",
    -7: "PREEMPTED",
    -10: "START_STATE_IN_COLLISION",
    -11: "START_STATE_VIOLATES_PATH_CONSTRAINTS",
    -12: "GOAL_IN_COLLISION",
    -13: "GOAL_VIOLATES_PATH_CONSTRAINTS",
    -14: "GOAL_CONSTRAINTS_VIOLATED",
    -15: "INVALID_GROUP_NAME",
    -16: "INVALID_GOAL_CONSTRAINTS",
    -17: "INVALID_ROBOT_STATE",
    -18: "INVALID_LINK_NAME",
    -21: "FRAME_TRANSFORM_FAILURE",
    -23: "ROBOT_STATE_STALE",
    -26: "START_STATE_INVALID",
    -27: "GOAL_STATE_INVALID",
    -28: "UNRECOGNIZED_GOAL_TYPE",
    -31: "NO_IK_SOLUTION",
}


def _moveit_service_ready() -> bool:
    return bool(ros_node and ros_node.c_moveit_plan.service_is_ready())


def _moveit_error_name(code: int) -> str:
    return _MOVEIT_ERROR_NAMES.get(int(code), "UNKNOWN")


def _build_moveit_start_state() -> RobotState:
    start_state = RobotState()
    start_state.joint_state = JointState()

    if latest_joint:
        filtered = [
            (name, pos)
            for name, pos in zip(
                list(latest_joint.get("names", [])),
                list(latest_joint.get("positions_rad", [])),
            )
            if name in {f"joint_{idx}" for idx in range(1, 7)}
        ]
        start_state.joint_state.name = [name for name, _ in filtered]
        start_state.joint_state.position = [pos for _, pos in filtered]

    return start_state


def _sample_moveit_preview(joint_names, points):
    if not joint_names or not points:
        return []

    sample_count = min(4, len(points))
    if sample_count <= 0:
        return []

    indexes = []
    for i in range(sample_count):
        if sample_count == 1:
            idx = len(points) - 1
        else:
            idx = round(i * (len(points) - 1) / (sample_count - 1))
        if idx not in indexes:
            indexes.append(idx)

    preview = []
    for seq, idx in enumerate(indexes, start=1):
        pt = points[idx]
        sec = int(getattr(getattr(pt, "time_from_start", None), "sec", 0))
        nsec = int(getattr(getattr(pt, "time_from_start", None), "nanosec", 0))
        preview.append({
            "label": f"Waypoint {seq}",
            "jointNames": list(joint_names),
            "positions": list(pt.positions),
            "time_from_start_s": sec + (nsec / 1e9),
        })
    return preview


def _preview_from_joint_target_map(joint_targets_rad: dict[str, float]):
    current_joint_map = {}
    if latest_joint:
        current_joint_map = {
            name: pos
            for name, pos in zip(
                list(latest_joint.get("names", [])),
                list(latest_joint.get("positions_rad", [])),
            )
            if name.startswith("joint_")
        }

    ordered_names = [f"joint_{idx}" for idx in range(1, 7)]
    samples = [0.2, 0.45, 0.7, 1.0]
    preview = []
    for seq, t in enumerate(samples, start=1):
        positions = []
        for name in ordered_names:
            start = float(current_joint_map.get(name, 0.0))
            target = float(joint_targets_rad.get(name, start))
            positions.append(start + ((target - start) * t))
        preview.append({
            "label": f"IK Waypoint {seq}",
            "jointNames": ordered_names,
            "positions": positions,
            "time_from_start_s": float(seq),
        })
    return preview


def _build_moveit_common_request(group_name, pipeline_id, planner_id, planning_time, attempts, vel_scale, acc_scale):
    req = GetMotionPlan.Request()
    req.motion_plan_request = MotionPlanRequest()
    req.motion_plan_request.group_name = group_name
    req.motion_plan_request.pipeline_id = pipeline_id
    req.motion_plan_request.planner_id = planner_id
    req.motion_plan_request.num_planning_attempts = max(1, int(attempts))
    req.motion_plan_request.allowed_planning_time = max(0.5, float(planning_time))
    req.motion_plan_request.max_velocity_scaling_factor = max(0.01, min(1.0, float(vel_scale)))
    req.motion_plan_request.max_acceleration_scaling_factor = max(0.01, min(1.0, float(acc_scale)))
    req.motion_plan_request.start_state = _build_moveit_start_state()
    return req


def _extract_moveit_plan_result(res):
    global _moveit_last_plan
    if not res:
        return {"success": False, "error": "MoveIt planning request timed out or failed"}

    motion_res = res.motion_plan_response
    error_code = int(getattr(getattr(motion_res, "error_code", None), "val", 0))
    trajectory = motion_res.trajectory.joint_trajectory
    joint_names = list(getattr(trajectory, "joint_names", []))
    points = list(getattr(trajectory, "points", []))

    success = error_code == 1 and bool(joint_names) and bool(points)
    if not success:
        _moveit_last_plan = None
        return {
            "success": False,
            "error": "MoveIt could not produce a valid joint trajectory",
            "error_code": error_code,
            "error_name": _moveit_error_name(error_code),
        }

    preview = _sample_moveit_preview(joint_names, points)
    _moveit_last_plan = {
        "joint_names": joint_names,
        "preview_waypoints": preview,
        "point_count": len(points),
        "error_code": error_code,
    }
    return {
        "success": True,
        "joint_names": joint_names,
        "point_count": len(points),
        "preview_waypoints": preview,
    }


def _build_joint_goal_constraints_from_map(joint_targets_rad: dict[str, float]) -> list[Constraints]:
    goal = Constraints()
    goal.joint_constraints = []
    for joint_name in [f"joint_{idx}" for idx in range(1, 7)]:
        if joint_name not in joint_targets_rad:
            continue
        jc = JointConstraint()
        jc.joint_name = joint_name
        jc.position = float(joint_targets_rad[joint_name])
        jc.tolerance_above = 0.001
        jc.tolerance_below = 0.001
        jc.weight = 1.0
        goal.joint_constraints.append(jc)
    return [goal]


def _compute_moveit_ik_joint_map(group_name, frame_id, tip_link, pose_xyz_deg):
    if not ros_node or not ros_node.c_moveit_ik.wait_for_service(timeout_sec=1.0):
        return None, {
            "success": False,
            "error": "MoveIt IK service /compute_ik is not available",
            "error_code": -25,
            "error_name": "COMMUNICATION_FAILURE",
        }

    x_mm, y_mm, z_mm, rx_deg, ry_deg, rz_deg = pose_xyz_deg
    qx, qy, qz, qw = R.from_euler("xyz", [rx_deg, ry_deg, rz_deg], degrees=True).as_quat()

    ik_req = GetPositionIK.Request()
    ik_req.ik_request.group_name = group_name
    ik_req.ik_request.robot_state = _build_moveit_start_state()
    ik_req.ik_request.avoid_collisions = False
    ik_req.ik_request.ik_link_name = tip_link
    ik_req.ik_request.pose_stamped = PoseStamped()
    ik_req.ik_request.pose_stamped.header.frame_id = frame_id
    ik_req.ik_request.pose_stamped.pose = Pose()
    ik_req.ik_request.pose_stamped.pose.position.x = x_mm / 1000.0
    ik_req.ik_request.pose_stamped.pose.position.y = y_mm / 1000.0
    ik_req.ik_request.pose_stamped.pose.position.z = z_mm / 1000.0
    ik_req.ik_request.pose_stamped.pose.orientation.x = float(qx)
    ik_req.ik_request.pose_stamped.pose.orientation.y = float(qy)
    ik_req.ik_request.pose_stamped.pose.orientation.z = float(qz)
    ik_req.ik_request.pose_stamped.pose.orientation.w = float(qw)
    ik_req.ik_request.timeout = Duration(sec=1, nanosec=0)

    ik_res = ros_node.call(ros_node.c_moveit_ik, ik_req, timeout=3.0)
    ik_code = int(getattr(getattr(ik_res, "error_code", None), "val", 0)) if ik_res else 0
    if not ik_res or ik_code != 1:
        return None, {
            "success": False,
            "error": "MoveIt IK could not solve the requested cartesian pose",
            "error_code": ik_code,
            "error_name": _moveit_error_name(ik_code),
        }

    joint_map = {
        name: pos
        for name, pos in zip(
            list(ik_res.solution.joint_state.name),
            list(ik_res.solution.joint_state.position),
        )
        if name.startswith("joint_")
    }
    if len(joint_map) < 6:
        return None, {
            "success": False,
            "error": "MoveIt IK returned an incomplete joint solution",
            "error_code": -31,
            "error_name": "NO_IK_SOLUTION",
        }

    return joint_map, None


def _compute_moveit_ik_with_candidates(group_name, frame_id, candidates):
    attempts = []
    for candidate in candidates:
        tip_link = candidate["tip_link"]
        pose_xyz_deg = candidate["pose"]
        joint_map, error = _compute_moveit_ik_joint_map(group_name, frame_id, tip_link, pose_xyz_deg)
        attempts.append({
            "tip_link": tip_link,
            "pose": pose_xyz_deg,
            "success": error is None,
            "error_code": None if error is None else error.get("error_code"),
            "error_name": None if error is None else error.get("error_name"),
        })
        if error is None:
            return joint_map, attempts, None

    last = attempts[-1] if attempts else {}
    return None, attempts, {
        "success": False,
        "error": "MoveIt IK could not solve the requested cartesian pose",
        "error_code": last.get("error_code", -31),
        "error_name": last.get("error_name", "NO_IK_SOLUTION"),
    }


@app.get("/api/moveit/status")
def api_moveit_status():
    return {
        "success": True,
        "enabled": True,
        "ros_connected": ros_connected,
        "moveit_service_ready": _moveit_service_ready(),
        "latest_joint_available": bool(latest_joint),
        "has_plan": bool(_moveit_last_plan),
    }


@app.post("/api/moveit/clear")
def api_moveit_clear():
    global _moveit_last_plan
    _moveit_last_plan = None
    return {"success": True}


@app.post("/api/moveit/plan/joint")
def api_moveit_plan_joint(b: MoveItJointPlanReq):
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    if len(b.pos) != 6:
        return {"success": False, "error": "pos must contain 6 joint values"}

    if not latest_joint:
        return {"success": False, "error": "Live joint state is not available yet"}

    if not ros_node.c_moveit_plan.wait_for_service(timeout_sec=1.0):
        return {"success": False, "error": "MoveIt planning service /plan_kinematic_path is not available"}

    req = _build_moveit_common_request(
        b.group_name,
        b.pipeline_id,
        b.planner_id,
        b.allowed_planning_time,
        b.num_planning_attempts,
        b.max_velocity_scaling_factor,
        b.max_acceleration_scaling_factor,
    )

    req.motion_plan_request.goal_constraints = _build_joint_goal_constraints_from_map({
        f"joint_{idx}": math.radians(float(pos))
        for idx, pos in enumerate(b.pos, start=1)
    })

    res = ros_node.call(ros_node.c_moveit_plan, req, timeout=max(5.0, req.motion_plan_request.allowed_planning_time + 2.0))
    result = _extract_moveit_plan_result(res)
    if not result.get("success"):
        return result

    return {
        **result,
        "group_name": b.group_name,
        "planner_id": b.planner_id,
    }


@app.post("/api/moveit/plan/pose")
def api_moveit_plan_pose(b: MoveItPosePlanReq):
    global _moveit_last_plan
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    if len(b.pos) != 6:
        return {"success": False, "error": "pos must contain 6 pose values [x,y,z,rx,ry,rz]"}

    if not latest_joint:
        return {"success": False, "error": "Live joint state is not available yet"}

    if not ros_node.c_moveit_plan.wait_for_service(timeout_sec=1.0):
        return {"success": False, "error": "MoveIt planning service /plan_kinematic_path is not available"}

    req = _build_moveit_common_request(
        b.group_name,
        b.pipeline_id,
        b.planner_id,
        b.allowed_planning_time,
        b.num_planning_attempts,
        b.max_velocity_scaling_factor,
        b.max_acceleration_scaling_factor,
    )

    resolved_pose, resolved_tip_link, used_tip_conversion = _resolve_moveit_tip_target(
        [float(v) for v in b.pos],
        b.tip_link,
    )
    x_mm, y_mm, z_mm, rx_deg, ry_deg, rz_deg = resolved_pose
    qx, qy, qz, qw = R.from_euler("xyz", [rx_deg, ry_deg, rz_deg], degrees=True).as_quat()

    pos_constraint = PositionConstraint()
    pos_constraint.header.frame_id = b.frame_id
    pos_constraint.link_name = resolved_tip_link
    pos_constraint.weight = 1.0

    region = BoundingVolume()
    primitive = SolidPrimitive()
    primitive.type = SolidPrimitive.BOX
    tol_m = max(0.0005, float(b.position_tolerance_mm) / 1000.0)
    primitive.dimensions = [tol_m * 2.0, tol_m * 2.0, tol_m * 2.0]
    region.primitives = [primitive]

    primitive_pose = Pose()
    primitive_pose.position.x = x_mm / 1000.0
    primitive_pose.position.y = y_mm / 1000.0
    primitive_pose.position.z = z_mm / 1000.0
    primitive_pose.orientation.w = 1.0
    region.primitive_poses = [primitive_pose]
    pos_constraint.constraint_region = region

    orient_constraint = OrientationConstraint()
    orient_constraint.header.frame_id = b.frame_id
    orient_constraint.link_name = resolved_tip_link
    orient_constraint.orientation.x = float(qx)
    orient_constraint.orientation.y = float(qy)
    orient_constraint.orientation.z = float(qz)
    orient_constraint.orientation.w = float(qw)
    tol_rad = max(math.radians(0.25), math.radians(float(b.orientation_tolerance_deg)))
    orient_constraint.absolute_x_axis_tolerance = tol_rad
    orient_constraint.absolute_y_axis_tolerance = tol_rad
    orient_constraint.absolute_z_axis_tolerance = tol_rad
    orient_constraint.weight = 1.0

    goal = Constraints()
    goal.position_constraints = [pos_constraint]
    goal.orientation_constraints = [orient_constraint]
    req.motion_plan_request.goal_constraints = [goal]

    pose_res = ros_node.call(
        ros_node.c_moveit_plan,
        req,
        timeout=max(5.0, req.motion_plan_request.allowed_planning_time + 2.0),
    )
    pose_result = _extract_moveit_plan_result(pose_res)
    if pose_result.get("success"):
        return {
            **pose_result,
            "group_name": b.group_name,
            "pipeline_id": b.pipeline_id,
            "planner_id": b.planner_id,
            "tip_link": b.tip_link,
            "resolved_tip_link": resolved_tip_link,
            "frame_id": b.frame_id,
            "used_tip_conversion": used_tip_conversion,
            "fallback": "pose_primary",
            "ik_attempts": [],
        }

    ik_candidates = [{
        "tip_link": resolved_tip_link,
        "pose": resolved_pose,
    }]

    ik_joint_map, ik_attempts, ik_error = _compute_moveit_ik_with_candidates(
        b.group_name,
        b.frame_id,
        ik_candidates,
    )
    if ik_error:
        ik_error["tip_link"] = b.tip_link
        ik_error["resolved_tip_link"] = resolved_tip_link
        ik_error["used_tip_conversion"] = used_tip_conversion
        ik_error["ik_attempts"] = ik_attempts
        return ik_error

    joint_req = _build_moveit_common_request(
        b.group_name,
        "",
        "",
        b.allowed_planning_time,
        b.num_planning_attempts,
        b.max_velocity_scaling_factor,
        b.max_acceleration_scaling_factor,
    )
    joint_req.motion_plan_request.goal_constraints = _build_joint_goal_constraints_from_map(ik_joint_map)
    res = ros_node.call(ros_node.c_moveit_plan, joint_req, timeout=max(5.0, joint_req.motion_plan_request.allowed_planning_time + 2.0))
    result = _extract_moveit_plan_result(res)
    if not result.get("success"):
        ik_preview = _preview_from_joint_target_map(ik_joint_map)
        if ik_preview:
            _moveit_last_plan = {
                "joint_names": [f"joint_{idx}" for idx in range(1, 7)],
                "preview_waypoints": ik_preview,
                "point_count": len(ik_preview),
                "error_code": result.get("error_code", 0),
                "fallback": "ik_preview_only",
            }
            return {
                "success": True,
                "group_name": b.group_name,
                "pipeline_id": b.pipeline_id,
                "planner_id": b.planner_id,
                "tip_link": b.tip_link,
                "resolved_tip_link": resolved_tip_link,
                "frame_id": b.frame_id,
                "used_tip_conversion": used_tip_conversion,
                "fallback": "ik_preview_only",
                "ik_attempts": ik_attempts,
                "point_count": len(ik_preview),
                "joint_names": [f"joint_{idx}" for idx in range(1, 7)],
                "preview_waypoints": ik_preview,
                "warning": f'Joint trajectory planning failed after IK, using preview-only fallback [{result.get("error_name", "UNKNOWN")}]',
            }

        result["error"] = f'{result.get("error", "MoveIt joint planning after IK failed")} [{result.get("error_name", "UNKNOWN")}]'
        result["tip_link"] = b.tip_link
        result["resolved_tip_link"] = resolved_tip_link
        result["used_tip_conversion"] = used_tip_conversion
        result["fallback"] = "ik_primary"
        result["ik_attempts"] = ik_attempts
        return result

    return {
        **result,
        "group_name": b.group_name,
        "pipeline_id": b.pipeline_id,
        "planner_id": b.planner_id,
        "tip_link": b.tip_link,
        "resolved_tip_link": resolved_tip_link,
        "frame_id": b.frame_id,
        "used_tip_conversion": used_tip_conversion,
        "fallback": "ik_primary",
        "ik_attempts": ik_attempts,
    }


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

class MoveJointXReq(BaseModel):
    pos: list[float]
    vel: float = 30.0
    acc: float = 60.0
    ref: int = 0
    sync_type: int = 0
    sol: int = 2


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

class MoveJointxReq(BaseModel):
    pos: list[float]           # [X, Y, Z, Rx, Ry, Rz]
    vel: float = 30.0
    acc: float = 60.0
    ref: int = 0
    sync_type: int = 0
    sol: int = 2               # IK solution space, 2 iyi bir başlangıç

class MoveTcpReq(BaseModel):
    pos: list[float]           # [X, Y, Z, Rx, Ry, Rz]
    vel: float = 100.0
    acc: float = 200.0
    ref: int = 0               # 0=BASE
    sync_type: int = 0
    sol: int = 2

@app.post("/api/move/jointx")
def api_move_jointx(b: MoveJointxReq):
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    if len(b.pos) != 6:
        return {"success": False, "error": "pos must contain 6 values [x,y,z,rx,ry,rz]"}

    if not ros_node.c_move_jx.wait_for_service(timeout_sec=1.0):
        return {"success": False, "error": "/motion/move_jointx service is not available"}

    req = MoveJointx.Request()
    req.pos = [float(v) for v in b.pos]
    req.vel = float(b.vel)
    req.acc = float(b.acc)
    req.time = 0.0
    req.radius = 0.0
    req.ref = int(b.ref)
    req.sol = int(b.sol)
    req.mode = 0
    req.blend_type = 0
    req.sync_type = int(b.sync_type)

    r = ros_node.call(
        ros_node.c_move_jx,
        req,
        timeout=60.0 if b.sync_type == 0 else 5.0,
    )

    return {"success": r.success if r else False}

@app.post("/api/move/tcp")
def api_move_tcp(b: MoveTcpReq):
    if not ros_node:
        return {"success": False, "error": "ros_node is not ready"}

    if len(b.pos) != 6:
        return {"success": False, "error": "pos must contain 6 values [x,y,z,rx,ry,rz]"}

    if not ros_node.c_move_jx.wait_for_service(timeout_sec=1.0):
        return {"success": False, "error": "/motion/move_jointx service is not available"}

    before_pose = _tcp_snapshot()

    target_pos = [float(v) for v in b.pos]
    target_pos[3:6] = xyz_to_zyz(target_pos[3], target_pos[4], target_pos[5])

    req = MoveJointx.Request()
    req.pos = target_pos
    req.vel = float(b.vel)
    req.acc = float(b.acc)
    req.time = 0.0
    req.radius = 0.0
    req.ref = int(b.ref)
    req.sol = int(b.sol)
    req.mode = 0
    req.blend_type = 0
    req.sync_type = int(b.sync_type)

    r = ros_node.call(
        ros_node.c_move_jx,
        req,
        timeout=60.0 if b.sync_type == 0 else 5.0,
    )

    if not r or not r.success:
        return {
            "success": False,
            "error": "MoveJointx service call failed or returned success=False",
        }

    # Real-motion verification
    if before_pose is not None:
        moved, started_pose = _wait_for_tcp_motion_start(before_pose, timeout=1.5)
        if not moved:
            return {
                "success": False,
                "error": "MoveJointx was accepted but no real TCP motion was detected",
                "before": _safe_list(before_pose),
                "after": _safe_list(started_pose),
                "target": _safe_list(b.pos),
            }

    # For sync mode, verify final target reach ONLY in BASE frame.
    # If ref != 0, req.pos is not in BASE, so direct comparison is invalid.
    if b.sync_type == 0 and int(b.ref) == 0:
        try:
            reached, final_pose = _wait_until_tcp_reached(
                list(req.pos),
                timeout=25.0,
                linear_tol_mm=5.0,
                angular_tol_deg=2.0,
                check_rotation=False
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
                "target": _safe_list(b.pos),
            }

    final_pose = _tcp_snapshot()

    print("DEBUG RESPONSE:",
      type(req.pos),
      type(_tcp_snapshot()))

    return {
        "success": True,
        "target": _safe_list(b.pos),
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
        if ros_node:
            pause_mode = None

            drl_req = DrlPause.Request()
            drl_res = ros_node.call(ros_node.c_drl_pause, drl_req)
            if drl_res and getattr(drl_res, "success", False):
                pause_mode = "drl"
            else:
                motion_req = MovePause.Request()
                motion_sent = ros_node.dispatch(ros_node.c_pause, motion_req)
                if motion_sent:
                    pause_mode = "motion"
                else:
                    return {"success": False, "error": "Neither DRL pause nor motion pause succeeded"}

        _prog_process.send_signal(signal.SIGSTOP)
        _prog_state = 2
        return {"success": True, "mode": pause_mode if ros_node else "process"}
    return {"success": False, "error": "Not running"}


@app.post("/api/program/resume")
def api_prog_resume():
    global _prog_process, _prog_state
    if _prog_process and _prog_process.poll() is None and _prog_state == 2:
        if ros_node:
            resume_mode = None

            drl_req = DrlResume.Request()
            drl_res = ros_node.call(ros_node.c_drl_resume, drl_req)
            if drl_res and getattr(drl_res, "success", False):
                resume_mode = "drl"
            else:
                motion_req = MoveResume.Request()
                motion_sent = ros_node.dispatch(ros_node.c_resume, motion_req)
                if motion_sent:
                    resume_mode = "motion"
                else:
                    return {"success": False, "error": "Neither DRL resume nor motion resume succeeded"}

        _prog_process.send_signal(signal.SIGCONT)
        _prog_state = 1
        return {"success": True, "mode": resume_mode if ros_node else "process"}
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
        "tcp_gripper_A": [0, 0, 235, 0, 0, 0],
        "tcp_gripper_B": [0, 0, 235, 0, 0, 0],
    }


def _pose_xyz_deg_to_matrix(pos):
    transform = np.eye(4)
    transform[:3, 3] = np.array(pos[:3], dtype=float)
    transform[:3, :3] = R.from_euler("xyz", pos[3:], degrees=True).as_matrix()
    return transform


def _matrix_to_pose_xyz_deg(transform):
    rpy = R.from_matrix(transform[:3, :3]).as_euler("xyz", degrees=True)
    xyz = transform[:3, 3]
    return [
        float(xyz[0]),
        float(xyz[1]),
        float(xyz[2]),
        float(rpy[0]),
        float(rpy[1]),
        float(rpy[2]),
    ]


def _resolve_moveit_tip_target(pos, tip_link):
    tool_offsets = load_tool_offsets()
    moveit_links = {"link_6"}

    if tip_link in moveit_links:
        return list(pos), tip_link, False

    tcp_offset = tool_offsets.get(tip_link)
    if (not tcp_offset or len(tcp_offset) != 6):
        live_offset = _get_live_tcp_offset()
        if live_offset and live_offset.get("name") == tip_link:
            tcp_offset = live_offset.get("offsets")
    if (not tcp_offset or len(tcp_offset) != 6):
        tip_lower = str(tip_link or "").strip().lower()
        if "smc" in tip_lower:
            tcp_offset = [0, 0, 235, 0, 0, 0]

    if not tcp_offset or len(tcp_offset) != 6:
        return list(pos), tip_link, False

    tcp_target = _pose_xyz_deg_to_matrix(pos)
    tool_transform = _pose_xyz_deg_to_matrix(tcp_offset)
    flange_target = tcp_target @ np.linalg.inv(tool_transform)
    return _matrix_to_pose_xyz_deg(flange_target), "link_6", True


def _get_live_tcp_offset():
    if not ros_node or not latest_tcp:
        return None

    current_tcp_name = active_tool

    try:
        if ros_node.c_get_tcp.service_is_ready():
            tcp_res = ros_node.call(ros_node.c_get_tcp, GetCurrentTcp.Request(), timeout=1.0)
            if tcp_res and getattr(tcp_res, "success", False) and getattr(tcp_res, "info", "").strip():
                current_tcp_name = tcp_res.info.strip()
    except Exception:
        pass

    try:
        req = GetCurrentToolFlangePosx.Request()
        req.ref = 0
        flange_res = ros_node.call(ros_node.c_tool_flange_posx, req, timeout=1.0)
        if not flange_res or not getattr(flange_res, "success", False):
            return None

        flange_zyz = flange_res.pos
        flange_xyz = _stable_euler(*zyz_to_xyz(flange_zyz[3], flange_zyz[4], flange_zyz[5]))
        flange_pose = [
            float(flange_zyz[0]),
            float(flange_zyz[1]),
            float(flange_zyz[2]),
            float(flange_xyz[0]),
            float(flange_xyz[1]),
            float(flange_xyz[2]),
        ]

        tcp_pose = [
            float(latest_tcp.get("x", 0.0)),
            float(latest_tcp.get("y", 0.0)),
            float(latest_tcp.get("z", 0.0)),
            float(latest_tcp.get("rx", 0.0)),
            float(latest_tcp.get("ry", 0.0)),
            float(latest_tcp.get("rz", 0.0)),
        ]

        rel = np.linalg.inv(_pose_xyz_deg_to_matrix(flange_pose)) @ _pose_xyz_deg_to_matrix(tcp_pose)
        rel_xyz = rel[:3, 3]
        rel_rpy = R.from_matrix(rel[:3, :3]).as_euler("xyz", degrees=True)

        return {
            "name": current_tcp_name,
            "offsets": [
                round(float(rel_xyz[0]), 3),
                round(float(rel_xyz[1]), 3),
                round(float(rel_xyz[2]), 3),
                round(float(rel_rpy[0]), 3),
                round(float(rel_rpy[1]), 3),
                round(float(rel_rpy[2]), 3),
            ],
        }
    except Exception:
        return None


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
    offsets = load_tool_offsets()
    live = _get_live_tcp_offset()
    return {"success": True, "offsets": offsets, "live": live}


@app.post("/api/tools/offsets")
def api_tool_offsets_set(b: ToolOffsetsReq):
    data = load_tool_offsets()
    data[b.name] = b.offsets
    save_tool_offsets(data)
    return {"success": True}


# ─── TCP Vision ──────────────────────────────────────────────────

from vision_tcp import VisionTCPClient

vision_client = VisionTCPClient(host="192.168.137.110", port=50005)
VISION_COMMANDS_FILE = "vision_commands.json"


def load_vision_commands():
    if os.path.exists(VISION_COMMANDS_FILE):
        try:
            with open(VISION_COMMANDS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [
                        {"name": str(item.get("name", "")).strip(), "command": str(item.get("command", "")).strip()}
                        for item in data
                        if isinstance(item, dict) and str(item.get("name", "")).strip() and str(item.get("command", "")).strip()
                    ]
        except Exception:
            pass
    return []


def save_vision_commands(data):
    with open(VISION_COMMANDS_FILE, "w") as f:
        json.dump(data, f, indent=2)


class VisionTriggerReq(BaseModel):
    command: str = "TRIGGER"


class VisionCommandReq(BaseModel):
    name: str
    command: str


class VisionCommandDeleteReq(BaseModel):
    name: str


@app.post("/api/vision/trigger")
async def api_vision_trigger(b: VisionTriggerReq):
    success, msg = await vision_client.send_trigger(b.command)
    await asyncio.sleep(0.5)
    return {
        "success": success,
        "message": msg,
        "vision_data": vision_client.latest_data,
    }


@app.get("/api/vision/commands")
def api_vision_commands_get():
    return {"success": True, "commands": load_vision_commands()}


@app.post("/api/vision/commands")
def api_vision_commands_save(b: VisionCommandReq):
    name = b.name.strip()
    command = b.command.strip()
    if not name or not command:
        return {"success": False, "error": "name and command required"}

    data = [item for item in load_vision_commands() if item["name"] != name]
    data.insert(0, {"name": name, "command": command})
    save_vision_commands(data)
    return {"success": True, "commands": data}


@app.post("/api/vision/commands/delete")
def api_vision_commands_delete(b: VisionCommandDeleteReq):
    name = b.name.strip()
    data = [item for item in load_vision_commands() if item["name"] != name]
    save_vision_commands(data)
    return {"success": True, "commands": data}


@app.get("/api/results/images")
def api_results_images():
    if not os.path.isdir(RESULTS_IMAGES_DIR):
        return {"success": False, "error": f"Results directory not found: {RESULTS_IMAGES_DIR}", "images": []}

    allowed = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
    items = []

    for name in sorted(os.listdir(RESULTS_IMAGES_DIR), reverse=True):
        path = os.path.join(RESULTS_IMAGES_DIR, name)
        ext = os.path.splitext(name)[1].lower()
        if os.path.isfile(path) and ext in allowed:
            stat = os.stat(path)
            items.append({
                "name": name,
                "url": f"/api/results/image/{name}",
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            })

    return {"success": True, "images": items, "directory": RESULTS_IMAGES_DIR}


@app.get("/api/results/image/{name:path}")
def api_results_image(name: str):
    if not os.path.isdir(RESULTS_IMAGES_DIR):
        raise HTTPException(status_code=404, detail="Results directory not found")

    safe_name = os.path.basename(name)
    path = os.path.join(RESULTS_IMAGES_DIR, safe_name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(path)


@app.get("/api/all-images/folders")
def api_all_images_folders():
    if not os.path.isdir(ALL_IMAGES_DIR):
        return {"success": False, "error": f"All images directory not found: {ALL_IMAGES_DIR}", "folders": []}

    folders = []
    for name in sorted(os.listdir(ALL_IMAGES_DIR)):
        path = os.path.join(ALL_IMAGES_DIR, name)
        if os.path.isdir(path):
            folders.append(name)

    return {"success": True, "folders": folders, "directory": ALL_IMAGES_DIR}


@app.get("/api/all-images/folder/{folder_name}")
def api_all_images_folder(folder_name: str):
    if not os.path.isdir(ALL_IMAGES_DIR):
        return {"success": False, "error": f"All images directory not found: {ALL_IMAGES_DIR}", "images": []}

    safe_folder = os.path.basename(folder_name)
    folder_path = os.path.join(ALL_IMAGES_DIR, safe_folder)
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail="Folder not found")

    allowed = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
    items = []

    for root, _, files in os.walk(folder_path):
        for name in files:
            path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if ext not in allowed or not os.path.isfile(path):
                continue

            rel_path = os.path.relpath(path, folder_path).replace(os.sep, "/")
            rel_dir = os.path.dirname(rel_path).replace(os.sep, "/")
            stat = os.stat(path)
            items.append({
                "name": name,
                "relative_path": rel_path,
                "subfolder": rel_dir if rel_dir and rel_dir != "." else "",
                "folder": safe_folder,
                "url": f"/api/all-images/file/{safe_folder}/{rel_path}",
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            })

    items.sort(key=lambda item: item["mtime"], reverse=True)

    return {"success": True, "folder": safe_folder, "images": items, "directory": folder_path}


@app.get("/api/all-images/file/{folder_name}/{name:path}")
def api_all_images_file(folder_name: str, name: str):
    if not os.path.isdir(ALL_IMAGES_DIR):
        raise HTTPException(status_code=404, detail="All images directory not found")

    safe_folder = os.path.basename(folder_name)
    safe_base = os.path.realpath(os.path.join(ALL_IMAGES_DIR, safe_folder))
    path = os.path.realpath(os.path.join(safe_base, name))
    if not path.startswith(safe_base + os.sep) and path != safe_base:
        raise HTTPException(status_code=400, detail="Invalid image path")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(path)


def _resolve_vision_db_path() -> Optional[str]:
    for candidate in VISION_DB_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def _vision_db_connect():
    db_path = _resolve_vision_db_path()
    if not db_path:
        raise FileNotFoundError("Vision DB file not found")
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


@app.get("/api/vision/db/status")
def api_vision_db_status():
    db_path = _resolve_vision_db_path()
    return {
        "success": bool(db_path),
        "path": db_path,
        "candidates": [p for p in VISION_DB_CANDIDATES if p],
    }


@app.get("/api/vision/db/tables")
def api_vision_db_tables():
    db_path = _resolve_vision_db_path()
    if not db_path:
        return {
            "success": False,
            "error": "Vision DB file not found",
            "path": None,
            "tables": [],
        }

    try:
        with _vision_db_connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
            tables = [row["name"] for row in rows]
        return {"success": True, "path": db_path, "tables": tables}
    except Exception as e:
        return {"success": False, "error": str(e), "path": db_path, "tables": []}


@app.get("/api/vision/db/table/{table_name}")
def api_vision_db_table(table_name: str, limit: int = 200):
    db_path = _resolve_vision_db_path()
    if not db_path:
        return {
            "success": False,
            "error": "Vision DB file not found",
            "path": None,
            "table": table_name,
            "columns": [],
            "rows": [],
        }

    if not table_name.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid table name")

    safe_limit = max(1, min(limit, 1000))

    try:
        with _vision_db_connect() as conn:
            conn.row_factory = sqlite3.Row
            columns_info = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            if not columns_info:
                raise HTTPException(status_code=404, detail="Table not found")

            columns = [row["name"] for row in columns_info]
            total = conn.execute(f'SELECT COUNT(*) AS count FROM "{table_name}"').fetchone()["count"]
            data = conn.execute(f'SELECT * FROM "{table_name}" ORDER BY rowid DESC LIMIT {safe_limit}').fetchall()
            rows = [{col: row[col] for col in columns} for row in data]

        return {
            "success": True,
            "path": db_path,
            "table": table_name,
            "columns": columns,
            "rows": rows,
            "limit": safe_limit,
            "total": total,
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "path": db_path,
            "table": table_name,
            "columns": [],
            "rows": [],
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

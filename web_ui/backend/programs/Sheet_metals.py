# web_ui/backend/programs/Sheet_metals.py

import time
import socket
import json
import requests

import rclpy
from rclpy.node import Node

from dsr_msgs2.srv import (
    SetCurrentTcp,
    SetCtrlBoxDigitalOutput,
    MoveJoint,
    MoveLine,
    MoveStop,
    SetRefCoord,
)

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

VISION_IP = "192.168.137.110"
VISION_PORT = 50005

TRIGGER_COMMAND = "100;1"
POSE_COMMAND = "124"

BACKEND_URL = "http://localhost:8000"

PICK_VAR = "P20"
PLACE_VAR = "P21"

PLACE_USER_FRAME = 110

PRE_PICK_Z_OFFSET = 80.0
PRE_PLACE_Z_OFFSET = 80.0

ON = 1
OFF = 0

# ------------------------------------------------------------------
# FIXED JOINT POSITIONS
# ------------------------------------------------------------------

tool_change_init_pos = [17.58, -9.13, 118.87, 0.26, 70.64, -71.54]
System_scan_pos_aligned = [103.72, -5.01, 107.34, 0.00, 77.69, -76.26]

unnamed = [99.39, 14.50, 85.96, -1.06, 77.81, -79.79]
unnamed2 = [53.57, 18.64, 94.99, -1.07, 66.60, -46.67]


def tp_print(msg):
    print(msg, flush=True)


# ------------------------------------------------------------------
# TCP/IP HELPERS
# ------------------------------------------------------------------

def send_tcp_ip_command(command: str, timeout: float = 10.0) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect((VISION_IP, VISION_PORT))
        s.sendall(command.encode())
        response = s.recv(4096)
        return response.decode().strip()


def trigger_vision():
    tp_print(f"[VISION] Sending trigger: {TRIGGER_COMMAND}")
    response = send_tcp_ip_command(TRIGGER_COMMAND, timeout=10.0)
    tp_print(f"[VISION] Trigger response: {response}")
    return response


def request_pose_response():
    tp_print(f"[VISION] Requesting poses: {POSE_COMMAND}")
    response = send_tcp_ip_command(POSE_COMMAND, timeout=10.0)
    tp_print(f"[VISION] Pose response: {response}")
    return response


def parse_pose_response(resp: str):
    """
    Expected format:
    Status1;spare;gripper;position1(6);ext_axis1;Status2;spare;area;position2(6);ext_axis2;

    Mapping:
      0: Status1
      1: spare
      2: gripper
      3-8:  position1 (6 values)
      9: ext_axis1
      10: Status2
      11: spare
      12: area
      13-18: position2 (6 values)
      19: ext_axis2
    """
    items = [x for x in resp.split(";") if x != ""]

    if len(items) < 20:
        raise ValueError(f"Invalid pose response. Expected >= 20 items, got {len(items)}. Raw: {resp}")

    pick_pose = [float(v) for v in items[3:9]]
    place_pose = [float(v) for v in items[13:19]]

    return pick_pose, place_pose


def make_pre_pose(pose, dz):
    pre = list(pose)
    pre[2] = pre[2] + dz
    return pre


def write_variable(name: str, value):
    try:
        res = requests.post(
            f"{BACKEND_URL}/api/variables",
            json={"name": name, "value": value},
            timeout=1.0,
        )
        data = res.json()
        if not data.get("success"):
            tp_print(f"[VAR] Failed to write {name}: {data}")
    except Exception as e:
        tp_print(f"[VAR] Error writing {name}: {e}")


# ------------------------------------------------------------------
# ROS SERVICE CLIENT
# ------------------------------------------------------------------

class ServiceClientNode(Node):
    def __init__(self):
        super().__init__("sheet_metals_node")

        self.set_tcp_client = self.create_client(SetCurrentTcp, "/tcp/set_current_tcp")
        self.io_client = self.create_client(SetCtrlBoxDigitalOutput, "/io/set_ctrl_box_digital_output")
        self.movej_client = self.create_client(MoveJoint, "/motion/move_joint")
        self.movel_client = self.create_client(MoveLine, "/motion/move_line")
        self.movestop_client = self.create_client(MoveStop, "/motion/move_stop")
        self.ref_client = self.create_client(SetRefCoord, "/motion/set_ref_coord")

        for name, cli in [
            ("/tcp/set_current_tcp", self.set_tcp_client),
            ("/io/set_ctrl_box_digital_output", self.io_client),
            ("/motion/move_joint", self.movej_client),
            ("/motion/move_line", self.movel_client),
            ("/motion/move_stop", self.movestop_client),
            ("/motion/set_ref_coord", self.ref_client),
        ]:
            while not cli.wait_for_service(timeout_sec=1.0):
                self.get_logger().info(f"Waiting for {name} ...")

    def _call(self, cli, req):
        future = cli.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def set_tcp(self, tcp_name: str):
        req = SetCurrentTcp.Request()
        req.name = tcp_name
        return self._call(self.set_tcp_client, req)

    def set_do(self, index: int, value: int):
        req = SetCtrlBoxDigitalOutput.Request()
        req.index = index
        req.value = value
        return self._call(self.io_client, req)

    def movej(self, pos, vel=30.0, acc=60.0):
        req = MoveJoint.Request()
        req.pos = [float(v) for v in pos]
        req.vel = float(vel)
        req.acc = float(acc)
        req.time = 0.0
        req.mode = 0
        req.sync_type = 0
        return self._call(self.movej_client, req)

    def movel(self, pos, vel=None, acc=None, ref=0):
        req = MoveLine.Request()
        req.pos = [float(v) for v in pos]
        req.vel = [100.0, 30.0] if vel is None else (
            [float(v) for v in vel] if isinstance(vel, (list, tuple)) else [float(vel), 30.0]
        )
        req.acc = [200.0, 60.0] if acc is None else (
            [float(v) for v in acc] if isinstance(acc, (list, tuple)) else [float(acc), 60.0]
        )
        req.time = 0.0
        req.radius = 0.0
        req.ref = int(ref)
        req.mode = 0
        req.blend_type = 0
        req.sync_type = 0
        return self._call(self.movel_client, req)

    def set_ref_coord(self, coord: int):
        req = SetRefCoord.Request()
        req.coord = int(coord)
        return self._call(self.ref_client, req)

    def movestop(self, stop_mode=1):
        req = MoveStop.Request()
        req.stop_mode = int(stop_mode)
        return self._call(self.movestop_client, req)


# ------------------------------------------------------------------
# TOOL ACTIONS
# ------------------------------------------------------------------

def tool_pick_on(node: ServiceClientNode):
    tp_print("[TOOL] Magnet ON")
    node.set_do(index=1, value=ON)
    node.set_do(index=2, value=OFF)
    node.set_do(index=4, value=ON)
    time.sleep(0.5)


def tool_release(node: ServiceClientNode):
    tp_print("[TOOL] Release / demagnetize")
    node.set_do(index=1, value=OFF)
    node.set_do(index=2, value=OFF)
    time.sleep(0.25)
    node.set_do(index=2, value=ON)
    node.set_do(index=4, value=ON)
    time.sleep(0.5)
    node.set_do(index=2, value=OFF)


# ------------------------------------------------------------------
# MAIN JOB
# ------------------------------------------------------------------

def main():
    rclpy.init()
    node = ServiceClientNode()

    try:
        tp_print("SHEET_METALS started")

        # 1. Safe TCP for scanning
        tp_print("Setting TCP to flange")
        node.set_tcp("flange")

        # 2. Move to scan position
        tp_print("Moving to scan position")
        node.movej(System_scan_pos_aligned, vel=50.0, acc=80.0)

        # 3. Trigger vision
        trigger_vision()
        time.sleep(0.5)

        # 4. Request poses
        raw_pose_response = request_pose_response()
        pick_pose, place_pose = parse_pose_response(raw_pose_response)

        tp_print(f"[PARSED] pick_pose(base/world): {pick_pose}")
        tp_print(f"[PARSED] place_pose(user_110): {place_pose}")

        # 5. Store in UI variables
        write_variable(PICK_VAR, pick_pose)
        write_variable(PLACE_VAR, place_pose)

        # 6. Build approach poses
        pre_pick_pose = make_pre_pose(pick_pose, PRE_PICK_Z_OFFSET)
        pre_place_pose = make_pre_pose(place_pose, PRE_PLACE_Z_OFFSET)

        tp_print(f"[PARSED] pre_pick_pose: {pre_pick_pose}")
        tp_print(f"[PARSED] pre_place_pose: {pre_place_pose}")

        # 7. Set tool TCP for picking
        tp_print("Setting TCP to EMH45B")
        node.set_tcp("EMH45B")

        # 8. Go near pick area
        node.movej(unnamed, vel=50.0, acc=80.0)

        # 9. Pick in world/base frame
        tp_print("Picking part in base/world frame")
        node.set_ref_coord(0)
        node.movel(pre_pick_pose, vel=[100.0, 30.0], acc=[200.0, 60.0], ref=0)
        node.movel(pick_pose, vel=[20.0, 20.0], acc=[50.0, 50.0], ref=0)
        tool_pick_on(node)
        node.movel(pre_pick_pose, vel=[100.0, 30.0], acc=[200.0, 60.0], ref=0)

        # 10. Travel
        node.movej(unnamed, vel=50.0, acc=80.0)
        node.movej(unnamed2, vel=50.0, acc=80.0)

        # 11. Place in user_coordinates_110
        tp_print("Placing part in user_coordinates_110")
        node.set_ref_coord(PLACE_USER_FRAME)
        node.movel(pre_place_pose, vel=[100.0, 30.0], acc=[200.0, 60.0], ref=PLACE_USER_FRAME)
        node.movel(place_pose, vel=[20.0, 20.0], acc=[50.0, 50.0], ref=PLACE_USER_FRAME)
        tool_release(node)
        node.movel(pre_place_pose, vel=[100.0, 30.0], acc=[200.0, 60.0], ref=PLACE_USER_FRAME)

        # 12. Retreat
        node.movej(unnamed, vel=50.0, acc=80.0)

        tp_print("SHEET_METALS completed successfully")

    except KeyboardInterrupt:
        tp_print("Interrupted. Stopping...")
        node.movestop()

    except Exception as e:
        tp_print(f"ERROR: {e}")
        node.movestop()

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
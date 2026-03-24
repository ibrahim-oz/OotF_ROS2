# web_ui/backend/programs/Sheet_metals.py

import time
import socket
import json
import requests

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from dsr_msgs2.srv import (
    SetCurrentTcp,
    SetCtrlBoxDigitalOutput,
    MoveJoint,
    MoveStop,
    SetRefCoord,
)
from dsr_msgs2.action import MovelH2r

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


def wait_for_movel(target_pose, tolerance=2.0, timeout=30.0, poll_interval=0.2):
    """
    Poll current TCP position from the backend and wait until
    the robot is within `tolerance` mm/deg of `target_pose`.
    """
    start = time.time()
    while (time.time() - start) < timeout:
        try:
            r = requests.get(f"{BACKEND_URL}/api/tcp", timeout=1.0)
            d = r.json()
            if "x" in d:
                current = [d["x"], d["y"], d["z"], d["rx"], d["ry"], d["rz"]]
                max_err = max(abs(current[i] - target_pose[i]) for i in range(6))
                if max_err <= tolerance:
                    tp_print(f"[WAIT] Target reached (max_err={max_err:.1f})")
                    return True
        except:
            pass
        time.sleep(poll_interval)
    tp_print(f"[WAIT] Timeout after {timeout}s waiting for target!")
    return False


# ------------------------------------------------------------------
# ROS SERVICE CLIENT
# ------------------------------------------------------------------

class ServiceClientNode(Node):
    def __init__(self):
        super().__init__("sheet_metals_node")

        self.set_tcp_client = self.create_client(SetCurrentTcp, "/tcp/set_current_tcp")
        self.io_client = self.create_client(SetCtrlBoxDigitalOutput, "/io/set_ctrl_box_digital_output")
        self.movej_client = self.create_client(MoveJoint, "/motion/move_joint")
        self.movestop_client = self.create_client(MoveStop, "/motion/move_stop")
        self.ref_client = self.create_client(SetRefCoord, "/motion/set_ref_coord")
        self.movel_h2r_client = ActionClient(self, MovelH2r, "/motion/movel_h2r")

        for name, cli in [
            ("/tcp/set_current_tcp", self.set_tcp_client),
            ("/io/set_ctrl_box_digital_output", self.io_client),
            ("/motion/move_joint", self.movej_client),
            ("/motion/move_stop", self.movestop_client),
            ("/motion/set_ref_coord", self.ref_client),
        ]:
            while not cli.wait_for_service(timeout_sec=1.0):
                self.get_logger().info(f"Waiting for {name} ...")

        tp_print("Waiting for /motion/movel_h2r action...")
        self.movel_h2r_client.wait_for_server()
        tp_print("movel_h2r action ready!")

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

    def movel_h2r(self, pos, vel=[100.0, 30.0], acc=[200.0, 60.0], timeout=60.0):
        """Cartesian move via MovelH2r action. Blocks until motion completes."""
        goal = MovelH2r.Goal()
        goal.target_pos = [float(v) for v in pos[:6]]
        goal.target_vel = [float(v) for v in vel]
        goal.target_acc = [float(v) for v in acc]

        send_future = self.movel_h2r_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future)
        goal_handle = send_future.result()

        if not goal_handle.accepted:
            tp_print("  movel_h2r goal REJECTED!")
            return False

        result_future = goal_handle.get_result_async()
        start = time.time()
        while not result_future.done() and (time.time() - start) < timeout:
            rclpy.spin_once(self, timeout_sec=0.1)

        if not result_future.done():
            tp_print(f"  movel_h2r TIMEOUT after {timeout}s!")
            goal_handle.cancel_goal_async()
            time.sleep(1.0)
            return False

        return result_future.result().result.success

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
    tp_print("[TOOL] Vakuum ON")
    node.set_do(index=5, value=ON)
    time.sleep(0.5)


def tool_pick_off(node: ServiceClientNode):
    tp_print("[TOOL] Vakuum OFF")
    node.set_do(index=5, value=OFF)
    time.sleep(0.5)


# ------------------------------------------------------------------
# MAIN JOB
# ------------------------------------------------------------------

def main():
    rclpy.init()
    node = ServiceClientNode()

    try:
        tp_print("SHEET_METALS started")

        # 1. Safe TCP for scanning
        # tp_print("Setting TCP to flange")
        # node.set_tcp("flange")

        # 2. Move to scan position
        tp_print("Moving to scan position")
        node.movej(System_scan_pos_aligned, vel=50.0, acc=80.0)

        # 3. Trigger vision
        trigger_vision()
        time.sleep(2.0)

        # 4. Request poses — retry until status is +0200.0
        MAX_RETRIES = 15
        RETRY_INTERVAL = 2.0
        raw_pose_response = ""
        status1 = ""

        for attempt in range(1, MAX_RETRIES + 1):
            raw_pose_response = request_pose_response()
            items = [x for x in raw_pose_response.split(";") if x != ""]
            status1 = items[0] if len(items) > 0 else ""
            tp_print(f"[VISION] Attempt {attempt}/{MAX_RETRIES} — Status1 = '{status1}'")

            if status1 == "+0200.0":
                tp_print("[VISION] Status OK (+0200.0). Proceeding with pick/place.")
                break

            tp_print(f"[VISION] Not ready yet, retrying in {RETRY_INTERVAL}s...")
            time.sleep(RETRY_INTERVAL)
        else:
            # All retries exhausted without +0200.0
            tp_print(f"[VISION] Status never reached +0200.0 after {MAX_RETRIES} attempts. Aborting.")
            tp_print("Moving to HOME (J01) position...")
            node.movej([0.0, 0.0, 90.0, 0.0, 90.0, -90.0], vel=30.0, acc=60.0)
            tp_print("Job Done")
            return

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

        # 8. Go near pick area
        tp_print(f"[MOVE] movej unnamed: {unnamed}")
        r = node.movej(unnamed, vel=50.0, acc=80.0)
        tp_print(f"[MOVE] movej unnamed result: {r}")

        # 9. Pick in world/base frame (using movel_h2r action)
        tp_print("Picking part in base/world frame")

        tp_print(f"[MOVE] movel_h2r pre_pick_pose: {pre_pick_pose}")
        ok = node.movel_h2r(pre_pick_pose, vel=[100.0, 30.0], acc=[200.0, 60.0])
        tp_print(f"[MOVE] movel_h2r pre_pick result: {ok}")

        tp_print(f"[MOVE] movel_h2r pick_pose: {pick_pose}")
        ok = node.movel_h2r(pick_pose, vel=[20.0, 10.0], acc=[50.0, 20.0])
        tp_print(f"[MOVE] movel_h2r pick result: {ok}")

        tool_pick_on(node)

        tp_print(f"[MOVE] movel_h2r pre_pick_pose (retreat): {pre_pick_pose}")
        ok = node.movel_h2r(pre_pick_pose, vel=[100.0, 30.0], acc=[200.0, 60.0])
        tp_print(f"[MOVE] movel_h2r pre_pick retreat result: {ok}")

        # 10. Travel
        r = node.movej(unnamed, vel=50.0, acc=80.0)
        tp_print(f"[MOVE] movej unnamed result: {r}")
        r = node.movej(unnamed2, vel=50.0, acc=80.0)
        tp_print(f"[MOVE] movej unnamed2 result: {r}")

        # 11. Place in user_coordinates_110 (using movel_h2r action)
        tp_print("Placing part in user_coordinates_110")
        node.set_ref_coord(PLACE_USER_FRAME)

        tp_print(f"[MOVE] movel_h2r pre_place_pose: {pre_place_pose}")
        ok = node.movel_h2r(pre_place_pose, vel=[100.0, 30.0], acc=[200.0, 60.0])
        tp_print(f"[MOVE] movel_h2r pre_place result: {ok}")

        tp_print(f"[MOVE] movel_h2r place_pose: {place_pose}")
        ok = node.movel_h2r(place_pose, vel=[20.0, 10.0], acc=[50.0, 20.0])
        tp_print(f"[MOVE] movel_h2r place result: {ok}")

        tool_pick_off(node)

        tp_print(f"[MOVE] movel_h2r pre_place_pose (retreat): {pre_place_pose}")
        ok = node.movel_h2r(pre_place_pose, vel=[100.0, 30.0], acc=[200.0, 60.0])
        tp_print(f"[MOVE] movel_h2r pre_place retreat result: {ok}")

        # 12. Retreat
        r = node.movej(unnamed, vel=50.0, acc=80.0)
        tp_print(f"[MOVE] movej retreat result: {r}")

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
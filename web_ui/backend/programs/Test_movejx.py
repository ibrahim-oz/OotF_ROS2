#!/usr/bin/env python3
"""
Test movel_h2r with a SMALL offset from current position.
This verifies if the action works at all, separate from reachability.
"""
import rclpy, time
from rclpy.node import Node
from rclpy.action import ActionClient
from dsr_msgs2.srv import MoveJoint, GetCurrentPosx
from dsr_msgs2.action import MovelH2r

HOME = [0.0, 0.0, 90.0, 0.0, 90.0, -90.0]

def tp_print(msg):
    print(msg, flush=True)


class TestNode(Node):
    def __init__(self):
        super().__init__("test_movel_h2r_node")
        self.movej_cli = self.create_client(MoveJoint, "/motion/move_joint")
        self.posx_cli = self.create_client(GetCurrentPosx, "/aux_control/get_current_posx")
        self.movel_h2r_cli = ActionClient(self, MovelH2r, "/motion/movel_h2r")

        for name, cli in [
            ("/motion/move_joint", self.movej_cli),
            ("/aux_control/get_current_posx", self.posx_cli),
        ]:
            while not cli.wait_for_service(timeout_sec=1.0):
                self.get_logger().info(f"Waiting for {name} ...")

        tp_print("Waiting for /motion/movel_h2r action...")
        self.movel_h2r_cli.wait_for_server()
        tp_print("Action server ready!")

    def _call(self, cli, req):
        future = cli.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def movej(self, pos, vel=30.0, acc=60.0):
        req = MoveJoint.Request()
        req.pos = [float(v) for v in pos]
        req.vel = float(vel)
        req.acc = float(acc)
        req.time = 0.0
        req.mode = 0
        req.sync_type = 0
        return self._call(self.movej_cli, req)

    def get_current_posx(self):
        req = GetCurrentPosx.Request()
        req.ref = 0  # DR_BASE
        return self._call(self.posx_cli, req)

    def movel_h2r(self, pos, vel=[100.0, 30.0], acc=[200.0, 60.0], timeout=30.0):
        goal = MovelH2r.Goal()
        goal.target_pos = [float(v) for v in pos]
        goal.target_vel = [float(v) for v in vel]
        goal.target_acc = [float(v) for v in acc]

        send_future = self.movel_h2r_cli.send_goal_async(
            goal, feedback_callback=self._fb
        )
        rclpy.spin_until_future_complete(self, send_future)
        goal_handle = send_future.result()

        if not goal_handle.accepted:
            tp_print("  Goal REJECTED!")
            return False

        tp_print("  Goal accepted, waiting...")
        result_future = goal_handle.get_result_async()

        # Wait with timeout
        start = time.time()
        while not result_future.done() and (time.time() - start) < timeout:
            rclpy.spin_once(self, timeout_sec=0.1)

        if not result_future.done():
            tp_print(f"  TIMEOUT after {timeout}s! Canceling...")
            goal_handle.cancel_goal_async()
            time.sleep(1.0)
            return False

        result = result_future.result()
        tp_print(f"  Result: success={result.result.success}")
        return result.result.success

    def _fb(self, msg):
        pos = [round(v, 1) for v in msg.feedback.pos]
        tp_print(f"  [FB] {pos}")


def main():
    rclpy.init()
    node = TestNode()

    try:
        tp_print("=== MOVEL_H2R SIMPLE TEST ===")

        # 1. Go to unnamed approach position
        tp_print("[1] movej to unnamed...")
        node.movej([99.39, 14.5, 85.96, -1.06, 77.81, -79.79], vel=50.0, acc=80.0)

        # 2. Read current cartesian position
        tp_print("[2] Reading current TCP pose...")
        posx = node.get_current_posx()
        cur = list(posx.task_pos_info[0].data)[:6]  # take only X,Y,Z,Rx,Ry,Rz
        tp_print(f"[2] Current posx: {[round(v,1) for v in cur]}")

        # 3. Move 50mm down (Z offset) from current
        target_small = cur.copy()
        target_small[2] -= 50.0  # move 50mm down
        tp_print(f"[3] movel_h2r: move 50mm DOWN to Z={round(target_small[2],1)}")
        t0 = time.time()
        ok = node.movel_h2r(target_small, vel=[50.0, 10.0], acc=[100.0, 20.0], timeout=15.0)
        dt = time.time() - t0
        tp_print(f"[3] took {dt:.1f}s, success={ok}")

        time.sleep(2.0)

        # 4. Move back up
        tp_print(f"[4] movel_h2r: move 50mm UP back to Z={round(cur[2],1)}")
        ok = node.movel_h2r(cur, vel=[50.0, 10.0], acc=[100.0, 20.0], timeout=15.0)
        tp_print(f"[4] success={ok}")

        # 5. Now try the actual vision target
        VISION_TARGET = [-446.3, 1092.8, -464.2, -179.7, -0.4, -99.7]
        tp_print(f"[5] movel_h2r: VISION TARGET {VISION_TARGET}")
        t0 = time.time()
        ok = node.movel_h2r(VISION_TARGET, vel=[100.0, 30.0], acc=[200.0, 60.0], timeout=20.0)
        dt = time.time() - t0
        tp_print(f"[5] took {dt:.1f}s, success={ok}")

        # 6. Home
        tp_print("[6] movej HOME...")
        node.movej(HOME, vel=30.0, acc=60.0)
        tp_print("=== DONE ===")

    except Exception as e:
        tp_print(f"ERROR: {e}")
        import traceback
        tp_print(traceback.format_exc())

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

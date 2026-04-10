# ──────────────────────────────────────────────────────────────────
# TOOL_DOCKING_2 Program (Python ROS2 Node)
# ──────────────────────────────────────────────────────────────────
# Docks Tool 2 using direct ROS 2 Service calls.
# Uses pre-configured User Frame 192 on the robot.
# up/out/inside/aligned positions are in user_coordinate_192 (ref=192).
# home/away are joint positions.
# ──────────────────────────────────────────────────────────────────

import time
import rclpy
from rclpy.node import Node

from dsr_msgs2.srv import SetCurrentTcp
from dsr_msgs2.srv import SetCtrlBoxDigitalOutput
from dsr_msgs2.srv import MoveJoint
from dsr_msgs2.srv import MoveLine
from dsr_msgs2.srv import MoveStop
from dsr_msgs2.srv import SetRefCoord

home = [90.0, 0.0, 90.0, 0.0, 90.0, -90.0]
away = [25.43, 22.12, 135.36, 10.92, 23.53, -72.79]

# Cartesian positions relative to User Frame 102 (192 was too high for int8)
up      = [-13.500, 0.000, -9.828, 0.00, 0.00, 0.00]
out     = [-13.500, 0.000, 0.000, 180.00, 180.00, 180.00]
inside  = [0.000, 0.000, 0.000, 0.00, 0.00, 0.00]
aligned = [0.000, -80.000, 0.000, 0.00, 0.00, 0.00]

# Robot tarafında 192 nolu koordinatı 102 nolu slota kopyalayın.
UF_ID = 102 
ON  = 1
OFF = 0

class ServiceClientNode(Node):
    def __init__(self):
        super().__init__('tool_docking_2_node')
        self.tcp_client     = self.create_client(SetCurrentTcp,           '/tcp/set_current_tcp')
        self.io_client      = self.create_client(SetCtrlBoxDigitalOutput, '/io/set_ctrl_box_digital_output')
        self.movej_client   = self.create_client(MoveJoint,               '/motion/move_joint')
        self.movel_client   = self.create_client(MoveLine,                '/motion/move_line')
        self.movestop_client= self.create_client(MoveStop,                '/motion/move_stop')
        self.ref_client     = self.create_client(SetRefCoord,             '/motion/set_ref_coord')

        for name, cli in [
            ('/tcp/set_current_tcp',           self.tcp_client),
            ('/io/set_ctrl_box_digital_output', self.io_client),
            ('/motion/move_joint',             self.movej_client),
            ('/motion/move_line',              self.movel_client),
            ('/motion/move_stop',              self.movestop_client),
            ('/motion/set_ref_coord',          self.ref_client),
        ]:
            while not cli.wait_for_service(timeout_sec=1.0):
                self.get_logger().info(f'Waiting for {name}...')

    def _call(self, cli, req):
        future = cli.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def set_tcp(self, tcp_name: str):
        req = SetCurrentTcp.Request(); req.name = tcp_name
        self._call(self.tcp_client, req)

    def set_do(self, index: int, value: int):
        req = SetCtrlBoxDigitalOutput.Request(); req.index = index; req.value = value
        self._call(self.io_client, req)

    def movej(self, pos, vel=30.0, acc=60.0):
        req = MoveJoint.Request()
        req.pos = pos; req.vel = vel; req.acc = acc
        req.time = 0.0; req.mode = 0; req.sync_type = 0
        self._call(self.movej_client, req)

    def movel(self, pos, vel=[100.0, 30.0], acc=[200.0, 60.0], ref=0):
        req = MoveLine.Request()
        req.pos = pos
        req.vel = [float(v) for v in vel] if isinstance(vel, (list,tuple)) else [float(vel), 30.0]
        req.acc = [float(a) for a in acc] if isinstance(acc, (list,tuple)) else [float(acc), 60.0]
        req.time = 0.0; req.radius = 0.0; req.ref = ref
        req.mode = 0; req.blend_type = 0; req.sync_type = 0
        self._call(self.movel_client, req)

    def set_ref_coord(self, coord: int):
        req = SetRefCoord.Request(); req.coord = coord
        self._call(self.ref_client, req)

    def movestop(self, stop_mode=1):
        req = MoveStop.Request(); req.stop_mode = stop_mode
        self._call(self.movestop_client, req)

def main():
    rclpy.init()
    node = ServiceClientNode()
    try:
        tp_print(f"TOOL_DOCKING_2: Using Robot's UF{UF_ID}")

        # 1. Set TCP to flange (XYZ: 0,0,0,0,0,0) as requested
        tp_print("Setting TCP offset to 'flange' (XYZ: 0,0,0,0,0,0)...")
        node.set_tcp("flange")

        # 2. Home
        tp_print("Homing...")
        node.movej(home, vel=50.0, acc=80.0)

        # 3. Set Reference Coord to UF_ID
        tp_print(f"Switching to User Frame {UF_ID}...")
        node.set_ref_coord(UF_ID)

        # 4. Move to approach (joint)
        tp_print("Moving away...")
        node.movej(away, vel=30.0, acc=60.0)

        # 5. Open gripper
        node.set_do(8, ON)
        time.sleep(1)

        # 5. Set active reference coordinate to UF_ID
        tp_print(f"Setting active reference coordinate to UF{UF_ID}...")
        node.set_ref_coord(UF_ID)

        # 6. Cartesian moves in user_coordinate
        tp_print(f"Moving up (UF{UF_ID})...")
        node.movel(up,      vel=[20.0, 10.0], acc=[60.0, 60.0], ref=UF_ID)

        tp_print(f"Moving out (UF{UF_ID})...")
        node.movel(out,     vel=[20.0, 10.0], acc=[60.0, 60.0], ref=UF_ID)

        tp_print(f"Moving inside (UF{UF_ID})...")
        node.movel(inside,  vel=[20.0, 10.0], acc=[60.0, 60.0], ref=UF_ID)

        time.sleep(1)

        # 7. Close gripper
        node.set_do(8, OFF)
        time.sleep(1)
        node.set_do(5, OFF)

        tp_print("TOOL_DOCKING_2: Complete.")

    except KeyboardInterrupt:
        tp_print("Interrupted. Stopping...")
        node.movestop()
    except Exception as e:
        tp_print(f"ERROR: {e}")
        node.movestop()
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

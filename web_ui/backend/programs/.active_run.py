
import sys, os, time, json

# Injecting local UI state / vars
USER_FRAMES = json.loads('''{"12": {"name": "ToolStation-2", "pos": [441.9, 190.82, 73.13, 0.16, -178.08, 90.03]}}''')
VARS = json.loads('''{"P01": [-163.902, 623.61, 909.64, 180, 0, 0], "J01": [90, 0, 90, 0, 90, -90], "I01": 0, "B01": false, "S01": "", "P02": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J02": [103.72, -5.01, 107.34, 0, 77.69, -76.26], "I02": 0, "B02": false, "S02": "", "P03": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J03": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I03": 0, "B03": false, "S03": "", "P04": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J04": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I04": 0, "B04": false, "S04": "", "P05": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J05": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I05": 0, "B05": false, "S05": "", "P06": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J06": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I06": 0, "B06": false, "S06": "", "P07": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J07": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I07": 0, "B07": false, "S07": "", "P08": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J08": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I08": 0, "B08": false, "S08": "", "P09": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J09": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I09": 0, "B09": false, "S09": "", "P10": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J10": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I10": 0, "B10": false, "S10": "", "P11": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J11": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I11": 0, "B11": false, "S11": "", "P12": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J12": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I12": 0, "B12": false, "S12": "", "P13": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J13": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I13": 0, "B13": false, "S13": "", "P14": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J14": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I14": 0, "B14": false, "S14": "", "P15": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J15": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I15": 0, "B15": false, "S15": "", "P16": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J16": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I16": 0, "B16": false, "S16": "", "P17": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J17": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I17": 0, "B17": false, "S17": "", "P18": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J18": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I18": 0, "B18": false, "S18": "", "P19": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J19": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I19": 0, "B19": false, "S19": "", "P20": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J20": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I20": 0, "B20": false, "S20": "", "P21": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J21": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I21": 0, "B21": false, "S21": "", "P22": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J22": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I22": 0, "B22": false, "S22": "", "P23": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J23": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I23": 0, "B23": false, "S23": "", "P24": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J24": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I24": 0, "B24": false, "S24": "", "P25": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J25": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I25": 0, "B25": false, "S25": "", "P26": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J26": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I26": 0, "B26": false, "S26": "", "P27": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J27": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I27": 0, "B27": false, "S27": "", "P28": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J28": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I28": 0, "B28": false, "S28": "", "P29": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J29": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I29": 0, "B29": false, "S29": "", "P30": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J30": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I30": 0, "B30": false, "S30": "", "P31": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J31": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I31": 0, "B31": false, "S31": "", "P32": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J32": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I32": 0, "B32": false, "S32": "", "P33": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J33": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I33": 0, "B33": false, "S33": "", "P34": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J34": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I34": 0, "B34": false, "S34": "", "P35": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J35": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I35": 0, "B35": false, "S35": "", "P36": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J36": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I36": 0, "B36": false, "S36": "", "P37": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J37": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I37": 0, "B37": false, "S37": "", "P38": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J38": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I38": 0, "B38": false, "S38": "", "P39": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J39": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I39": 0, "B39": false, "S39": "", "P40": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J40": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I40": 0, "B40": false, "S40": "", "P41": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J41": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I41": 0, "B41": false, "S41": "", "P42": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J42": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I42": 0, "B42": false, "S42": "", "P43": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J43": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I43": 0, "B43": false, "S43": "", "P44": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J44": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I44": 0, "B44": false, "S44": "", "P45": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J45": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I45": 0, "B45": false, "S45": "", "P46": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J46": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I46": 0, "B46": false, "S46": "", "P47": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J47": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I47": 0, "B47": false, "S47": "", "P48": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J48": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I48": 0, "B48": false, "S48": "", "P49": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J49": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I49": 0, "B49": false, "S49": "", "P50": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J50": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I50": 0, "B50": false, "S50": ""}''')
for k,v in VARS.items(): globals()[k] = v

def tp_print(msg):
    print(msg, flush=True)

# USER CODE BELOW
# ──────────────────────────────────────────────────────────────────
# TOOL_DOCKING_3 Program (Python ROS2 Node)
# ──────────────────────────────────────────────────────────────────
# Docks Tool 3 using direct ROS 2 Service calls.
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


# ──────────────────────────────────────────────────────────────────
# Joint positions
# ──────────────────────────────────────────────────────────────────
home = [90.0, 0.0, 90.0, 0.0, 90.0, -90.0]
away = [3.96, 28.51, 145.92, 9.88, 4.18, -94.48]

unnamed  = [7.35, -3.68, 113.24, 3.39, 70.25, -99.61]
unnamed2 = [-1.04, 34.55, 136.04, 4.72, 20.23, -97.27]
unnamed3 = [0.00, 9.40, 122.25, 0.00, 47.70, -90.00]

# ──────────────────────────────────────────────────────────────────
# Cartesian positions relative to User Frame 103 (193 was too high for int8)
# ──────────────────────────────────────────────────────────────────
up      = [-13.682, 0.002, -18.103, 0.00, 0.00, 0.00]
out     = [-13.682, 0.003, 0.003, 180.00, 180.00, 180.00]
inside  = [0.000, 0.000, 0.000, 0.00, 0.00, 0.00]
aligned = [0.000, -80.000, 0.000, 0.00, 0.00, 0.00]

# Robot tarafında 193 nolu koordinatı 103 nolu slota kopyalayın.
UF_ID = 103 
ON  = 1
OFF = 0

def tp_print(msg):
    print(msg, flush=True)

class ServiceClientNode(Node):
    def __init__(self):
        super().__init__('tool_docking_3_node')
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
        tp_print(f"TOOL_DOCKING_3: Using Robot's UF{UF_ID}")
        print("start tool docking 3")

        # 1. Set TCP to flange (XYZ: 0,0,0,0,0,0) as requested
        tp_print("Setting TCP offset to 'flange' (XYZ: 0,0,0,0,0,0)...")
        print("set tcp")
        node.set_tcp("flange")

        # 2. Home
        tp_print("Homing...")
        print("homing")
        node.movej(home, vel=50.0, acc=80.0)

        # 3. Set Reference Coord to UF_ID
        tp_print(f"Switching to User Frame {UF_ID}...")
        print("switching UF")
        node.set_ref_coord(UF_ID)

        # In between move to unnamed position?
        tp_print("Moving to unnamed position...")
        print("movign unnamed pos")
        node.movej(unnamed, vel=30.0, acc=60.0)

        # 4. Move to approach (joint)
        tp_print("Moving away...")
        print("moving away")
        node.movej(away, vel=30.0, acc=60.0)

        # 5. Open gripper
        print("gripper on")
        node.set_do(8, ON)
        time.sleep(1)

        # 5. Set active reference coordinate to UF_ID
        tp_print(f"Setting active reference coordinate to UF{UF_ID}...")
        print("set ref coord to UF")
        node.set_ref_coord(UF_ID)

        # 6. Cartesian moves in user_coordinate
        tp_print(f"Moving up (UF{UF_ID})...")
        print("moving up")
        node.movel(up,      vel=[20.0, 10.0], acc=[60.0, 60.0], ref=UF_ID)

        tp_print(f"Moving out (UF{UF_ID})...")
        print("moving out")
        node.movel(out,     vel=[20.0, 10.0], acc=[60.0, 60.0], ref=UF_ID)

        tp_print(f"Moving inside (UF{UF_ID})...")
        print("moving inside")
        node.movel(inside,  vel=[20.0, 10.0], acc=[60.0, 60.0], ref=UF_ID)

        time.sleep(1)

        # 7. Close gripper
        print("close gripper")
        node.set_do(8, OFF)

        # exit_tool_station_3
        print("exit tool station")
        node.movel(inside,  vel=[20.0, 10.0], acc=[60.0, 60.0], ref=UF_ID)
        node.movel(aligned, vel=[20.0, 10.0], acc=[60.0, 60.0], ref=UF_ID)
        node.movel(out,     vel=[20.0, 10.0], acc=[60.0, 60.0], ref=UF_ID)

        node.movej(unnamed2, vel=30.0, acc=60.0)
        node.movej(unnamed3, vel=30.0, acc=60.0)
        

        tp_print("TOOL_DOCKING_3: Complete.")
        print("docking complete")

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


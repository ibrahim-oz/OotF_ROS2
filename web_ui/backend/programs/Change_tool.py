# ──────────────────────────────────────────────────────────────────
# Change_tool Program (Python ROS2 Node)
# ──────────────────────────────────────────────────────────────────
# Change Tool demo using direct ROS 2 Service calls.
# ──────────────────────────────────────────────────────────────────

import time
import rclpy
from rclpy.node import Node

from dsr_msgs2.srv import SetCurrentTcp, SetCtrlBoxDigitalOutput


def tp_print(msg):
    # Print to web_ui logging
    print(msg, flush=True)

class ServiceClientNode(Node):
    def __init__(self):
        super().__init__('tool_docking_2_node')
        self.tcp_client     = self.create_client(SetCurrentTcp,           '/tcp/set_current_tcp')
        self.io_client      = self.create_client(SetCtrlBoxDigitalOutput, '/io/set_ctrl_box_digital_output')

        for name, cli in [
            ('/tcp/set_current_tcp',           self.tcp_client),
            ('/io/set_ctrl_box_digital_output', self.io_client),
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

def main():
    rclpy.init()
    node = ServiceClientNode()
    try:
        tp_print("Change_tools program starting: center_suction_pad_smc -> EMH45B -> quad_suction_pad_smc -> flange")

        node.set_tcp(tcp_name="flange")
        tp_print("Set to TCP center_suction_pad_smc")
        time.sleep(5)

        node.set_tcp(tcp_name="EMH45B")
        tp_print("Set to TCP EMH45B")
        time.sleep(5)

        node.set_tcp(tcp_name="quad_suction_pad_smc")
        tp_print("Set to TCP quad_suction_pad_smc")
        time.sleep(5)

        # node.set_tcp(tcp_name="flange")
        # tp_print("Set to TCP flange")
        # time.sleep(5)

        tp_print("Cycled through all pre-programmed TCP's")

    except KeyboardInterrupt:
        tp_print("Interrupted. Stopping...")
    except Exception as e:
        tp_print(f"ERROR: {e}")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
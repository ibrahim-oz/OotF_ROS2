# ──────────────────────────────────────────────────────────────────
# Go to Pallet Scan Pos Program (Python ROS2 Node)
# ──────────────────────────────────────────────────────────────────
# This program moves the robot to the configured J01 position.
# The `J01` variable is automatically injected dynamically 
# into this script by the Web UI Backend before execution.
# ──────────────────────────────────────────────────────────────────

import rclpy
from rclpy.node import Node
from dsr_msgs2.srv import MoveJoint

class MainNode(Node):
    def __init__(self):
        super().__init__('scan_node')
        self.movej_client = self.create_client(MoveJoint, '/motion/move_joint')

        while not self.movej_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Waiting for /motion/move_joint...')

    def move_to_scan(self, target_pos):
        req = MoveJoint.Request()
        req.pos = target_pos
        req.vel = 30.0
        req.acc = 60.0
        req.time = 0.0
        req.mode = 0
        req.sync_type = 0

        future = self.movej_client.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        if future.result() is not None and future.result().success:
            self.get_logger().info('Movement successful.')
        else:
            self.get_logger().error('Movement failed.')

def main():
    tp_print("Executing move to scan via ROS 2 services...")
    
    # J01 is injected from the backend preamble
    target = [float(j) for j in J02]
    tp_print(f"Target J01: {target}")

    rclpy.init()
    node = MainNode()
    try:
        node.move_to_scan(target)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

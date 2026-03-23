# Request_Pose.py
# Reads pose from TCP/IP server and writes into UI variables (P20, P21)

import socket
import requests

ROBOT_IP = "192.168.137.110"
ROBOT_PORT = 50005
BACKEND_URL = "http://localhost:8000"

COMMAND = "124"


def send_tcp_ip_command(command: str):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((ROBOT_IP, ROBOT_PORT))
            s.sendall(command.encode())
            response = s.recv(2048)
            return response.decode()
    except Exception as e:
        print(f"[TCP ERROR] {e}")
        return None


def parse_response(resp: str):
    """
    Parses the response string into position1 and position2
    """

    items = resp.strip().split(";")
    items = [i for i in items if i != ""]  # temizle

    if len(items) < 20:
        raise ValueError("Invalid response length")

    # mapping (senin verdiğin yapıya göre)
    # 0: Status1
    # 1: spare
    # 2: gripper
    # 3-8: position1 (6)
    # 9: ext_axis1
    # 10: Status2
    # 11: spare
    # 12: area
    # 13-18: position2 (6)
    # 19: ext_axis2

    def to_float(x):
        return float(x)

    pos1 = [to_float(v) for v in items[3:9]]
    pos2 = [to_float(v) for v in items[13:19]]

    return pos1, pos2


def write_variable(name: str, value):
    try:
        res = requests.post(
            f"{BACKEND_URL}/api/variables",
            json={"name": name, "value": value},
            timeout=1.0
        ).json()

        if not res.get("success"):
            print(f"[VAR ERROR] {name} failed")

    except Exception as e:
        print(f"[VAR ERROR] {e}")


def run():
    resp = send_tcp_ip_command(COMMAND)

    if not resp:
        print("[ERROR] No response")
        return

    print(f"[RAW] {resp}")

    try:
        pos1, pos2 = parse_response(resp)

        print(f"[POS1] {pos1}")
        print(f"[POS2] {pos2}")

        # assign to variables
        write_variable("P20", pos1)
        write_variable("P21", pos2)

        print("[SUCCESS] P20 & P21 updated")

    except Exception as e:
        print(f"[PARSE ERROR] {e}")


if __name__ == "__main__":
    run()
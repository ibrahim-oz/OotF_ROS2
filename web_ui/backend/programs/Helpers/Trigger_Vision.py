# Trigger_Vision.py
# Sends trigger command over TCP/IP and prints response

import socket

ROBOT_IP = "192.168.137.110"
ROBOT_PORT = 50005

COMMAND = "100;1"


def send_tcp_ip_command(command: str):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3.0)
            s.connect((ROBOT_IP, ROBOT_PORT))

            print(f"[SEND] {command}")
            s.sendall(command.encode())

            response = s.recv(4096)

            if not response:
                print("[WARN] No response received")
                return None

            decoded = response.decode().strip()
            print(f"[RESPONSE] {decoded}")
            return decoded

    except socket.timeout:
        print("[ERROR] Timeout while waiting for response")
    except Exception as e:
        print(f"[ERROR] {e}")

    return None


def run():
    resp = send_tcp_ip_command(COMMAND)

    if resp is None:
        print("[FAIL] Trigger failed")
    else:
        print("[SUCCESS] Trigger command completed")


if __name__ == "__main__":
    run()
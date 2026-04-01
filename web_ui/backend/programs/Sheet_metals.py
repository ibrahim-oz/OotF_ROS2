# web_ui/backend/programs/Sheet_metals.py

import time
import socket
import requests

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

VISION_IP = "192.168.137.110"
VISION_PORT = 50005

TRIGGER_COMMAND = "100;1"
POSE_COMMAND = "124"

BACKEND = "http://localhost:8000"

PRE_PICK_Z = 80.0
PRE_PLACE_Z = 80.0

PLACE_USER_FRAME = 110

# Fixed robot-safe tool orientation
FIX_RX = 0.0
FIX_RY = 180.0

# ------------------------------------------------------------------
# UTILS
# ------------------------------------------------------------------

def tp(msg):
    print(msg, flush=True)


def send_tcp(cmd):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(10)
        s.connect((VISION_IP, VISION_PORT))
        s.sendall(cmd.encode())
        return s.recv(4096).decode().strip()


def parse_pose(resp):
    items = [x for x in resp.split(";") if x]

    if len(items) < 20:
        raise Exception(f"Invalid vision response: {resp}")

    pick = [float(v) for v in items[3:9]]
    place = [float(v) for v in items[13:19]]

    return pick, place


def normalize_deg(a):
    while a > 180.0:
        a -= 360.0
    while a < -180.0:
        a += 360.0
    return a


def build_robot_pose(p):
    """
    Vision orientation -> robot-safe orientation

    Vision sends:
      [x, y, z, rx, ry, rz]

    For this job we do NOT use full vision Euler conversion.
    We keep tool down and only map RZ with the proven formula:
      RZ_robot = 180 - RZ_vision
    """
    rz = normalize_deg(180.0 - p[5])

    return [
        p[0],
        p[1],
        p[2],
        FIX_RX,
        FIX_RY,
        rz,
    ]


def offset_z(p, dz):
    q = list(p)
    q[2] += dz
    return q


# ------------------------------------------------------------------
# BACKEND CONTROL
# ------------------------------------------------------------------

def movej(j, vel=50, acc=80):
    r = requests.post(
        f"{BACKEND}/api/move/joint",
        json={
            "pos": j,
            "vel": vel,
            "acc": acc,
            "sync_type": 0,
        },
        timeout=40,
    ).json()

    if not r.get("success"):
        raise Exception(f"MoveJ failed: {r}")


def movel(p, ref=0, vel=100, acc=200):
    r = requests.post(
        f"{BACKEND}/api/move/tcp",
        json={
            "pos": p,
            "vel": vel,
            "acc": acc,
            "ref": ref,
            "sync_type": 1,
        },
        timeout=40,
    ).json()

    if not r.get("success"):
        raise Exception(f"MoveL failed: {r}")


def set_ref(ref):
    r = requests.post(
        f"{BACKEND}/api/ref",
        json={"coord": ref},
        timeout=10,
    ).json()

    if not r.get("success"):
        raise Exception(f"SetRef failed: {r}")


def vacuum(on=True):
    if on:
        # reset / pulse
        requests.post(
            f"{BACKEND}/api/io/digital/out",
            json={"index": 1, "value": 0},
            timeout=10,
        )
        time.sleep(0.2)

        requests.post(
            f"{BACKEND}/api/io/digital/out",
            json={"index": 1, "value": 1},
            timeout=10,
        )
    else:
        requests.post(
            f"{BACKEND}/api/io/digital/out",
            json={"index": 1, "value": 0},
            timeout=10,
        )

    time.sleep(0.3)


# ------------------------------------------------------------------
# MAIN JOB
# ------------------------------------------------------------------

def main():
    tp("=== SHEET METALS START ===")

    # --------------------------------------------------------------
    # 1. SCAN POSITION
    # --------------------------------------------------------------
    scan_pos = [103.72, -5.01, 107.34, 0.00, 77.69, -76.26]
    tp("Move scan position")
    movej(scan_pos)

    # --------------------------------------------------------------
    # 2. VISION TRIGGER
    # --------------------------------------------------------------
    tp("Trigger vision")
    send_tcp(TRIGGER_COMMAND)
    time.sleep(2.0)

    # --------------------------------------------------------------
    # 3. GET POSE (RETRY)
    # --------------------------------------------------------------
    resp = None
    for i in range(10):
        resp = send_tcp(POSE_COMMAND)
        status = resp.split(";")[0]
        tp(f"Vision status: {status}")

        if status == "+0200.0":
            break

        time.sleep(1.0)
    else:
        raise Exception("Vision failed")

    pick_raw, place_raw = parse_pose(resp)

    pick = build_robot_pose(pick_raw)
    place = build_robot_pose(place_raw)

    pre_pick = offset_z(pick, PRE_PICK_Z)
    pre_place = offset_z(place, PRE_PLACE_Z)

    tp(f"PICK RAW   (BASE): {pick_raw}")
    tp(f"PICK FIXED (BASE): {pick}")
    tp(f"PRE_PICK   (BASE): {pre_pick}")

    tp(f"PLACE RAW  (UF110): {place_raw}")
    tp(f"PLACE FIX  (UF110): {place}")
    tp(f"PRE_PLACE  (UF110): {pre_place}")

    # --------------------------------------------------------------
    # 4. PICK (BASE FRAME)
    # --------------------------------------------------------------
    set_ref(0)

    tp("Move pre-pick")
    movel(pre_pick, ref=0)

    tp("Move pick")
    movel(pick, ref=0)

    tp("Vacuum ON")
    vacuum(True)

    tp("Retreat from pick")
    movel(pre_pick, ref=0)

    # --------------------------------------------------------------
    # 5. TRAVEL (JOINT SAFE)
    # --------------------------------------------------------------
    safe = [53.57, 18.64, 94.99, -1.07, 66.60, -46.67]
    tp("Move safe joint")
    movej(safe)

    # --------------------------------------------------------------
    # 6. PLACE (USER FRAME 110)
    # --------------------------------------------------------------
    set_ref(PLACE_USER_FRAME)

    tp("Move pre-place")
    movel(pre_place, ref=PLACE_USER_FRAME)

    tp("Move place")
    movel(place, ref=PLACE_USER_FRAME)

    tp("Vacuum OFF")
    vacuum(False)

    tp("Retreat from place")
    movel(pre_place, ref=PLACE_USER_FRAME)

    # --------------------------------------------------------------
    # 7. BACK TO BASE
    # --------------------------------------------------------------
    set_ref(0)

    tp("=== DONE ===")


if __name__ == "__main__":
    main()
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

# FIXED TOOL ORIENTATION (downwards)
FIX_RX = 90.0
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
        raise Exception("Invalid vision response")

    pick = [float(v) for v in items[3:9]]
    place = [float(v) for v in items[13:19]]

    return pick, place


def fix_orientation(p):
    # keep rz, fix rx/ry
    return [p[0], p[1], p[2], FIX_RX, FIX_RY, p[5]]


def offset_z(p, dz):
    q = list(p)
    q[2] += dz
    return q


# ------------------------------------------------------------------
# BACKEND CONTROL
# ------------------------------------------------------------------

def movej(j):
    requests.post(f"{BACKEND}/api/move/joint", json={
        "pos": j,
        "vel": 50,
        "acc": 80,
        "sync_type": 0
    })


def movel(p):
    r = requests.post(f"{BACKEND}/api/move/tcp", json={
        "pos": p,
        "vel": 100,
        "acc": 200,
        "ref": 0,
        "sync_type": 1
    }).json()

    if not r.get("success"):
        raise Exception(f"MoveL failed: {r}")


def set_ref(ref):
    requests.post(f"{BACKEND}/api/ref", json={"coord": ref})


def vacuum(on=True):
    if on:
        # önce OFF → sonra ON (reset/pulse)
        requests.post(f"{BACKEND}/api/io/digital/out", json={
            "index": 1,
            "value": 0
        })
        time.sleep(0.2)

        requests.post(f"{BACKEND}/api/io/digital/out", json={
            "index": 1,
            "value": 1
        })
    else:
        # sadece OFF yeterli
        requests.post(f"{BACKEND}/api/io/digital/out", json={
            "index": 1,
            "value": 0
        })

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
    movej(scan_pos)

    # --------------------------------------------------------------
    # 2. VISION TRIGGER
    # --------------------------------------------------------------
    tp("Trigger vision")
    send_tcp(TRIGGER_COMMAND)
    time.sleep(2)

    # --------------------------------------------------------------
    # 3. GET POSE (RETRY)
    # --------------------------------------------------------------
    for i in range(10):
        resp = send_tcp(POSE_COMMAND)
        status = resp.split(";")[0]

        tp(f"Vision status: {status}")

        if status == "+0200.0":
            break

        time.sleep(1)
    else:
        raise Exception("Vision failed")

    pick, place = parse_pose(resp)

    # 🔥 FIX ORIENTATION HERE
    pick = fix_orientation(pick)
    place = fix_orientation(place)

    tp(f"PICK (BASE): {pick}")
    tp(f"PLACE (UF110): {place}")

    pre_pick = offset_z(pick, PRE_PICK_Z)
    pre_place = offset_z(place, PRE_PLACE_Z)

    # --------------------------------------------------------------
    # 4. PICK (BASE FRAME)
    # --------------------------------------------------------------
    set_ref(0)

    tp("Move pre-pick")
    movel(pre_pick)

    tp("Move pick")
    movel(pick)

    vacuum(True)

    tp("Retreat")
    movel(pre_pick)

    # --------------------------------------------------------------
    # 5. TRAVEL (JOINT SAFE)
    # --------------------------------------------------------------
    safe = [53.57, 18.64, 94.99, -1.07, 66.60, -46.67]
    movej(safe)

    # --------------------------------------------------------------
    # 6. PLACE (USER FRAME 110)
    # --------------------------------------------------------------
    set_ref(PLACE_USER_FRAME)

    tp("Move pre-place")
    movel(pre_place)

    tp("Move place")
    movel(place)

    vacuum(False)

    tp("Retreat")
    movel(pre_place)

    # --------------------------------------------------------------
    # 7. BACK TO BASE
    # --------------------------------------------------------------
    set_ref(0)

    tp("=== DONE ===")


if __name__ == "__main__":
    main()
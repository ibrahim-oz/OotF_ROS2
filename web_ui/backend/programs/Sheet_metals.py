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

PLACE_USER_FRAME = 101

UF101_BASE = [965.0, 631.0, -233.0, 0.0, 0.0, -90.0]

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


def parse_adapter_message(resp):
    items = [x for x in resp.split(";") if x]

    if len(items) < 20:
        raise Exception(f"Invalid vision response: {resp}")

    values = [float(v) for v in items]

    # Adapter response is 2 blocks x 10 values:
    # [status, ?, ?, x, y, z, rx, ry, rz, ?]
    pick = values[3:9]
    place = values[13:19]

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


def get_tcp():
    r = requests.get(f"{BACKEND}/api/tcp", timeout=10).json()

    if "x" not in r:
        raise Exception(f"TCP read failed: {r}")

    return [r["x"], r["y"], r["z"], r["rx"], r["ry"], r["rz"]]


# ------------------------------------------------------------------
# BACKEND CONTROL
# ------------------------------------------------------------------

def movej(j, vel=50, acc=80):
    before = get_tcp()

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

    after = get_tcp()
    tp(f"TCP BEFORE: {before}")
    tp(f"TCP AFTER : {after}")


def movejx(p, ref=0, vel=30, acc=60):
    before = get_tcp()

    for sol in [2, 1, 0, 3]:
        r = requests.post(
            f"{BACKEND}/api/move/jointx",
            json={
                "pos": p,
                "vel": vel,
                "acc": acc,
                "ref": ref,
                "sync_type": 0,
                "sol": sol,
            },
            timeout=60,
        ).json()

        if r.get("success"):
            after = get_tcp()
            tp(f"MoveJX OK (sol={sol}, ref={ref})")
            tp(f"TCP BEFORE: {before}")
            tp(f"TCP AFTER : {after}")
            return

    raise Exception(f"MoveJX failed: pos={p}, ref={ref}")


def movel(p, ref=0):
    r = requests.post(
        f"{BACKEND}/api/move/tcp",
        json={
            "pos": p,
            "vel": 100,
            "acc": 200,
            "ref": ref,
            "sync_type": 0,
        },
        timeout=60,
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
            json={"index": 5, "value": 0},
            timeout=10,
        )
        time.sleep(0.2)

        requests.post(
            f"{BACKEND}/api/io/digital/out",
            json={"index": 5, "value": 1},
            timeout=10,
        )
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
    time.sleep(3.0)

    # --------------------------------------------------------------
    # 3. GET POSE (RETRY)
    # --------------------------------------------------------------
    resp = None
    for i in range(100):
        resp = send_tcp(POSE_COMMAND)
        status = resp.split(";")[0]
        tp(f"Vision status: {status}")

        if status == "+0200.0":
            break

        time.sleep(1.0)
    else:
        raise Exception("Vision failed")

    pick_raw, place_raw = parse_adapter_message(resp)

    pick = build_robot_pose(pick_raw)
    place = build_robot_pose(place_raw)

    pre_pick = offset_z(pick, PRE_PICK_Z)
    pre_place = offset_z(place, PRE_PLACE_Z)

    tp(f"PICK RAW   (BASE): {pick_raw}")
    tp(f"PICK FIXED (BASE): {pick}")
    tp(f"PRE_PICK   (BASE): {pre_pick}")

    tp(f"PLACE RAW  (UF101): {place_raw}")
    tp(f"PLACE USE  (UF101): {place}")
    tp(f"PRE_PLACE  (UF101): {pre_place}")

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
    # 6. PLACE (USER FRAME 101)
    # --------------------------------------------------------------
    set_ref(PLACE_USER_FRAME)

    tp(f"UF{PLACE_USER_FRAME} (BASE): {UF101_BASE}")

    tp("Move pre-place")
    movejx(pre_place, ref=PLACE_USER_FRAME)

    tp("Move place")
    movejx(place, ref=PLACE_USER_FRAME)

    tp("Vacuum OFF")
    vacuum(False)

    tp("Retreat from place")
    movejx(pre_place, ref=PLACE_USER_FRAME)

    # --------------------------------------------------------------
    # 7. BACK TO BASE
    # --------------------------------------------------------------
    set_ref(0)

    tp("=== DONE ===")


if __name__ == "__main__":
    main()

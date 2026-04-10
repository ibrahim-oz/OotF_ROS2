
import sys, os, time, json

USER_FRAMES = json.loads('''{"12": {"name": "ToolStation-2", "pos": [441.9, 190.82, 73.13, 0.16, -178.08, 90.03]}}''')
VARS = json.loads('''{"P01": [-163.902, 623.61, 909.64, 180, 0, 0], "J01": [90, 0, 90, 0, 90, -90], "I01": 0, "B01": false, "S01": "", "P02": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J02": [103.72, -5.01, 107.34, 0, 77.69, -76.26], "I02": 0, "B02": false, "S02": "", "P03": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J03": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I03": 0, "B03": false, "S03": "", "P04": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J04": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I04": 0, "B04": false, "S04": "", "P05": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J05": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I05": 0, "B05": false, "S05": "", "P06": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J06": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I06": 0, "B06": false, "S06": "", "P07": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J07": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I07": 0, "B07": false, "S07": "", "P08": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J08": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I08": 0, "B08": false, "S08": "", "P09": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J09": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I09": 0, "B09": false, "S09": "", "P10": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J10": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I10": 0, "B10": false, "S10": "", "P11": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J11": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I11": 0, "B11": false, "S11": "", "P12": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J12": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I12": 0, "B12": false, "S12": "", "P13": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J13": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I13": 0, "B13": false, "S13": "", "P14": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J14": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I14": 0, "B14": false, "S14": "", "P15": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J15": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I15": 0, "B15": false, "S15": "", "P16": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J16": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I16": 0, "B16": false, "S16": "", "P17": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J17": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I17": 0, "B17": false, "S17": "", "P18": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J18": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I18": 0, "B18": false, "S18": "", "P19": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J19": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I19": 0, "B19": false, "S19": "", "P20": [-446.3, 1092.8, -544.2, -179.7, -0.4, -99.7], "J20": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I20": 0, "B20": false, "S20": "", "P21": [513.0, 111.0, 38.0, 0.0, 0.0, -178.9], "J21": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I21": 0, "B21": false, "S21": "", "P22": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J22": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I22": 0, "B22": false, "S22": "", "P23": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J23": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I23": 0, "B23": false, "S23": "", "P24": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J24": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I24": 0, "B24": false, "S24": "", "P25": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J25": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I25": 0, "B25": false, "S25": "", "P26": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J26": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I26": 0, "B26": false, "S26": "", "P27": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J27": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I27": 0, "B27": false, "S27": "", "P28": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J28": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I28": 0, "B28": false, "S28": "", "P29": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J29": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I29": 0, "B29": false, "S29": "", "P30": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J30": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I30": 0, "B30": false, "S30": "", "P31": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J31": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I31": 0, "B31": false, "S31": "", "P32": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J32": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I32": 0, "B32": false, "S32": "", "P33": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J33": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I33": 0, "B33": false, "S33": "", "P34": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J34": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I34": 0, "B34": false, "S34": "", "P35": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J35": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I35": 0, "B35": false, "S35": "", "P36": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J36": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I36": 0, "B36": false, "S36": "", "P37": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J37": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I37": 0, "B37": false, "S37": "", "P38": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J38": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I38": 0, "B38": false, "S38": "", "P39": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J39": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I39": 0, "B39": false, "S39": "", "P40": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J40": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I40": 0, "B40": false, "S40": "", "P41": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J41": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I41": 0, "B41": false, "S41": "", "P42": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J42": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I42": 0, "B42": false, "S42": "", "P43": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J43": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I43": 0, "B43": false, "S43": "", "P44": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J44": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I44": 0, "B44": false, "S44": "", "P45": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J45": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I45": 0, "B45": false, "S45": "", "P46": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J46": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I46": 0, "B46": false, "S46": "", "P47": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J47": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I47": 0, "B47": false, "S47": "", "P48": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J48": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I48": 0, "B48": false, "S48": "", "P49": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J49": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I49": 0, "B49": false, "S49": "", "P50": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "J50": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "I50": 0, "B50": false, "S50": ""}''')
for k,v in VARS.items(): globals()[k] = v

def tp_print(msg):
    print(msg, flush=True)

# USER CODE BELOW
# web_ui/backend/programs/Sheet_metals.py

import time
import socket
import requests

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

VISION_IP = "192.168.137.110"
VISION_PORT = 50005

STATION_COMMAND = "501;1"
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
    # 0. STATION SELECTOR
    # --------------------------------------------------------------
    tp("Selecting the correct station.")
    send_tcp(STATION_COMMAND)
    time.sleep(1.0)

    scan_pos = [103.72, -5.01, 107.34, 0.00, 77.69, -76.26]
    safe = [53.57, 18.64, 94.99, -1.07, 66.60, -46.67]

    cycle = 1
    while True:
        tp(f"=== CYCLE {cycle} ===")

        # --------------------------------------------------------------
        # 1. SCAN POSITION
        # --------------------------------------------------------------
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
        pose_found = False

        for i in range(100):
            resp = send_tcp(POSE_COMMAND)
            status = resp.split(";")[0]
            tp(f"Vision status: {status}")

            if status == "+0200.0":
                pose_found = True
                break

            time.sleep(1.0)

        if not pose_found:
            tp("No pose received in retry step. Finishing job.")
            break

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
        cycle += 1

    tp("=== DONE ===")


if __name__ == "__main__":
    main()


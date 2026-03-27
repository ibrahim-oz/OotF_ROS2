#!/usr/bin/env python3
# web_ui/backend/programs/Test_126.py

import time
import socket
import requests

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

VISION_IP = "192.168.137.110"
VISION_PORT = 50005

POSE_COMMAND = "126"

BACKEND = "http://localhost:8000"

PRE_PICK_Z = 80.0
PRE_PLACE_Z = 80.0

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
    rz = normalize_deg(180-p[5])

    return [
        p[0],
        p[1],
        p[2],
        p[3],
        p[4],
        rz,
    ]


def offset_z(p, dz):
    q = list(p)
    q[2] += dz
    return q


# ------------------------------------------------------------------
# BACKEND CONTROL
# ------------------------------------------------------------------

def movej(j):
    r = requests.post(
        f"{BACKEND}/api/move/joint",
        json={
            "pos": j,
            "vel": 50,
            "acc": 80,
            "sync_type": 0,
        },
        timeout=30,
    ).json()

    if not r.get("success"):
        raise Exception(f"MoveJ failed: {r}")

def wait_motion(timeout=5.0):
    """
    Robot gerçekten hareket ediyor mu kontrol et
    """
    start = time.time()

    prev = requests.get(f"{BACKEND}/api/tcp").json()

    while time.time() - start < timeout:

        time.sleep(0.2)

        cur = requests.get(f"{BACKEND}/api/tcp").json()

        dx = abs(cur["x"] - prev["x"])
        dy = abs(cur["y"] - prev["y"])
        dz = abs(cur["z"] - prev["z"])

        if dx > 1 or dy > 1 or dz > 1:
            return  # hareket başladı

    tp("⚠️ NO MOTION DETECTED")


def movejx(p):

    for sol in [2, 1, 0, 3]:
        r = requests.post(
            f"{BACKEND}/api/move/jointx",
            json={
                "pos": p,
                "vel": 30,
                "acc": 60,
                "ref": 0,
                "sync_type": 0,
                "sol": sol,
            },
            timeout=30,
        ).json()

        if r.get("success"):
            tp(f"MoveJX OK (sol={sol})")

            # 🔥 CRITICAL WAIT
            wait_motion()

            return

    raise Exception(f"MoveJX failed (all solutions): {p}")


def set_ref(ref):
    r = requests.post(
        f"{BACKEND}/api/ref",
        json={"coord": ref},
        timeout=10,
    ).json()

    if not r.get("success"):
        raise Exception(f"SetRef failed: {r}")


# ------------------------------------------------------------------
# MAIN TEST
# ------------------------------------------------------------------

def main():
    tp("=== TEST 126 START ===")

    home = [90, 53.3, 104.4, 0, 22.3, -90]

    tp("Go HOME")
    movej(home)
    time.sleep(2)

    for i in range(5):
        tp(f"\n--- ITERATION {i+1} ---")

        set_ref(0)

        resp = send_tcp(POSE_COMMAND)
        tp(f"Vision RAW: {resp}")

        pick_raw, place_raw = parse_pose(resp)

        # 🔥 CRITICAL FIX
        pick = build_robot_pose(pick_raw)
        place = build_robot_pose(place_raw)

        pre_pick = offset_z(pick, PRE_PICK_Z)
        pre_place = offset_z(place, PRE_PLACE_Z)

        tp(f"PICK RAW:  {pick_raw}")
        tp(f"PICK FIX:  {pick}")
        tp(f"PRE_PICK:  {pre_pick}")

        tp(f"PLACE RAW: {place_raw}")
        tp(f"PLACE FIX: {place}")
        tp(f"PRE_PLACE: {pre_place}")

        tp("Move pre-pick")
        movejx(pre_pick)

        tp("Move pick")
        movejx(pick)

        time.sleep(1)

        tp("Retreat")
        movejx(pre_pick)

        tp("Move pre-place")
        movejx(pre_place)

        tp("Move place")
        movejx(place)

        time.sleep(1)

        tp("Retreat")
        movejx(pre_place)

        tp("Back HOME")
        movej(home)
        time.sleep(1)

    tp("=== TEST 126 DONE ===")


if __name__ == "__main__":
    main()
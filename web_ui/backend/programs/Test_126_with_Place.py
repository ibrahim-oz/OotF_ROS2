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

PLACE_USER_FRAME = 101

# USER FRAME 101 (robot içinde BASE'e göre)
UF101_BASE = [965.0, 631.0, -233.0, 0.0, 0.0, -90.0]

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
    pick_raw = values[3:9]
    place_uf = values[13:19]

    return pick_raw, place_uf


def normalize_deg(a):
    while a > 180.0:
        a -= 360.0
    while a < -180.0:
        a += 360.0
    return a


def build_robot_pose(p):
    rz = normalize_deg(180.0 - p[5])
    return [p[0], p[1], p[2], 0.0, 180.0, rz]


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
# MOTION
# ------------------------------------------------------------------

def movej(j):
    r = requests.post(
        f"{BACKEND}/api/move/joint",
        json={"pos": j, "vel": 50, "acc": 80, "sync_type": 0},
        timeout=60,
    ).json()

    if not r.get("success"):
        raise Exception(f"MoveJ failed: {r}")


def movejx(p, ref=0):
    before = get_tcp()

    for sol in [2, 1, 0, 3]:
        r = requests.post(
            f"{BACKEND}/api/move/jointx",
            json={
                "pos": p,
                "vel": 30,
                "acc": 60,
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

    raise Exception(f"MoveJX failed: {p}")


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


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------

def main():
    tp("=== TEST 126 START ===")

    home = [90, 53.3, 104.4, 0, 22.3, -90]

    movej(home)
    time.sleep(2)

    for i in range(5):
        tp(f"\n--- ITERATION {i+1} ---")

        # ---------------- PICK ----------------
        set_ref(0)

        resp = send_tcp(POSE_COMMAND)
        tp(f"Vision RAW: {resp}")

        pick_raw, place_uf = parse_adapter_message(resp)
        pick = build_robot_pose(pick_raw)
        pre_pick = offset_z(pick, PRE_PICK_Z)

        movejx(pre_pick)
        movejx(pick)
        time.sleep(1)
        movejx(pre_pick)

        # ---------------- PLACE ----------------
        set_ref(PLACE_USER_FRAME)

        pre_place_uf = offset_z(place_uf, PRE_PLACE_Z)

        tp(f"UF{PLACE_USER_FRAME} (BASE): {UF101_BASE}")
        tp(f"PICK RAW: {pick_raw}")
        tp(f"PLACE UF: {place_uf}")

        # SAFE APPROACH
        movejx(pre_place_uf, ref=PLACE_USER_FRAME)

        # LINEAR FINAL
        movel(place_uf, ref=PLACE_USER_FRAME)

        # RETREAT
        movejx(pre_place_uf, ref=PLACE_USER_FRAME)

        set_ref(0)

        movej(home)
        time.sleep(1)

    tp("=== TEST 126 DONE ===")


if __name__ == "__main__":
    main()

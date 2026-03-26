#!/usr/bin/env python3
"""
DANCE_DEMO_STABLE + TRIGGER

- mevcut TCP etrafında dance
- her hareketten sonra kamera trigger
"""

import time
import requests
import socket

BACKEND = "http://localhost:8000"

VISION_IP = "192.168.137.110"
VISION_PORT = 50005

STEP_BIG = 100    # mm
STEP_SMALL = 40  # mm

TRIGGER_CMD = "100;1"


def tp(msg):
    print(msg, flush=True)


# ------------------------------------------------------------------
# TCP TRIGGER
# ------------------------------------------------------------------

def send_trigger():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((VISION_IP, VISION_PORT))
            s.sendall(TRIGGER_CMD.encode())
    except Exception as e:
        tp(f"TCP ERROR: {e}")

    time.sleep(5)


# ------------------------------------------------------------------
# BACKEND HELPERS (UNCHANGED)
# ------------------------------------------------------------------

def get_tcp():
    r = requests.get(f"{BACKEND}/api/tcp").json()

    if "x" not in r:
        raise Exception(f"TCP read failed: {r}")

    return [r["x"], r["y"], r["z"], r["rx"], r["ry"], r["rz"]]


def set_ref(ref):
    r = requests.post(f"{BACKEND}/api/ref", json={"coord": ref}).json()

    if not r.get("success"):
        raise Exception(f"SetRef failed: {r}")

    time.sleep(0.05)


def movel(p, ref=0, vel=120, acc=200):
    set_ref(ref)

    r = requests.post(f"{BACKEND}/api/move/tcp", json={
        "pos": p,
        "vel": vel,
        "acc": acc,
        "ref": ref,
        "sync_type": 0
    }).json()

    if not r.get("success"):
        raise Exception(f"MoveL failed: {r}")


# ------------------------------------------------------------------
# DANCE LOGIC
# ------------------------------------------------------------------

def dance():

    base = get_tcp()
    tp(f"[TCP] start = {base}")

    while True:

        poses = []

        # -------- BIG MOVES --------
        p = base.copy(); p[0] += STEP_BIG; poses.append(p)
        p = base.copy(); p[0] -= STEP_BIG; poses.append(p)

        p = base.copy(); p[1] += STEP_BIG; poses.append(p)
        p = base.copy(); p[1] -= STEP_BIG; poses.append(p)

        p = base.copy(); p[2] += STEP_BIG; poses.append(p)
        p = base.copy(); p[2] -= STEP_BIG; poses.append(p)

        # -------- SMALL SHAKE --------
        p = base.copy(); p[0] += STEP_SMALL; poses.append(p)
        p = base.copy(); p[0] -= STEP_SMALL; poses.append(p)

        p = base.copy(); p[1] += STEP_SMALL; poses.append(p)
        p = base.copy(); p[1] -= STEP_SMALL; poses.append(p)

        # -------- EXECUTE --------
        for target in poses:
            movel(target)
            send_trigger()  

        # -------- RETURN --------
        movel(base)
        send_trigger()      


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------

if __name__ == "__main__":
    dance()
#!/usr/bin/env python3
"""
TEST_MOVEL_STABLE

Amaç:
- movel + set_ref düzgün çalışıyor mu test etmek
- mevcut TCP etrafında küçük hareketler yapmak
- frame / vision hatasını elimine etmek
"""

import time
import requests

BACKEND = "http://localhost:8000"


def tp(msg):
    print(msg, flush=True)


# ------------------------------------------------------------------
# BACKEND HELPERS
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

    time.sleep(0.1)


def movel(p, ref=0, vel=100, acc=200):
    set_ref(ref)

    r = requests.post(f"{BACKEND}/api/move/tcp", json={
        "pos": p,
        "vel": vel,
        "acc": acc,
        "ref": ref,
        "sync_type": 0
    }).json()

    tp(f"[MOVEL] ref={ref} target={p}")
    tp(f"[MOVEL] resp={r}")

    if not r.get("success"):
        raise Exception(f"MoveL failed: {r}")


# ------------------------------------------------------------------
# MAIN TEST
# ------------------------------------------------------------------

def main():

    tp("=" * 50)
    tp(" TEST MOVEL (STABLE RELATIVE)")
    tp("=" * 50)

    # --------------------------------------------------------------
    # 1. GET CURRENT TCP
    # --------------------------------------------------------------
    base = get_tcp()

    tp(f"[TCP] current = {base}")

    # --------------------------------------------------------------
    # 2. BUILD SAFE TEST POSES
    # --------------------------------------------------------------
    p1 = base.copy()
    p1[0] += 50   # +X

    p2 = base.copy()
    p2[1] += 50   # +Y

    p3 = base.copy()
    p3[2] += 50   # +Z

    p4 = base.copy()
    p4[2] -= 50   # -Z (dikkat)

    # --------------------------------------------------------------
    # 3. EXECUTE
    # --------------------------------------------------------------
    try:
        tp("\n--- MOVE +X ---")
        movel(p1, ref=0)
        time.sleep(1)

        tp("\n--- MOVE +Y ---")
        movel(p2, ref=0)
        time.sleep(1)

        tp("\n--- MOVE +Z ---")
        movel(p3, ref=0)
        time.sleep(1)

        tp("\n--- MOVE -Z ---")
        movel(p4, ref=0)
        time.sleep(1)

        tp("\n--- BACK TO START ---")
        movel(base, ref=0)

    except Exception as e:
        tp(f"ERROR: {e}")

    tp("\n" + "=" * 50)
    tp(" DONE")
    tp("=" * 50)


if __name__ == "__main__":
    main()
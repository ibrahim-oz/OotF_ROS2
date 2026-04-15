#!/bin/bash

# Exit on any error
set -e

echo "============================================="
echo "   Doosan IPC System Check (Real Robot)    "
echo "============================================="

# 1. Check Ubuntu version
UBUNTU_VERSION=$(lsb_release -rs)
echo "[INFO] Detected Ubuntu version: $UBUNTU_VERSION"

if [ "$UBUNTU_VERSION" != "22.04" ]; then
    echo "[ERROR] This script requires Ubuntu 22.04 LTS."
    echo "Current OS is $UBUNTU_VERSION. Please use the correct scripts for your version."
    exit 1
fi

# 2. Check architecture
ARCH=$(uname -m)
echo "[INFO] Detected System Architecture: $ARCH"

if [ "$ARCH" != "x86_64" ]; then
    echo "[ERROR] This script requires an x86_64 architecture (found $ARCH)."
    exit 1
fi

# 3. Check internet connectivity
echo "[INFO] Checking internet connection..."
if ping -q -c 1 -W 1 google.com >/dev/null; then
    echo "[OK] Internet connection is active."
else
    echo "[ERROR] Cannot reach google.com. Please check your internet connection."
    exit 1
fi

echo ""
echo "============================================="
echo " System check passed! Ready for installation."
echo "============================================="
echo "You can now run:"
echo "  ./install_ros2.sh"
echo "============================================="

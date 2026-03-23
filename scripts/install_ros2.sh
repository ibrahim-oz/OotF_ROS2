#!/bin/bash

# Exit on any error
set -e

echo "============================================="
echo "   Doosan IPC ROS 2 Humble Installation    "
echo "============================================="

# Ensure we are on Ubuntu 22.04
UBUNTU_VERSION=$(lsb_release -rs)
if [ "$UBUNTU_VERSION" != "22.04" ]; then
    echo "[ERROR] This installation script is for Ubuntu 22.04 (ROS 2 Humble)."
    echo "Current OS is $UBUNTU_VERSION. Exiting."
    exit 1
fi

echo "[INFO] Updating package lists..."
sudo apt update && sudo apt upgrade -y

# 1. Setup Locale
echo "[INFO] Setting up locale..."
sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# 2. Setup Sources
echo "[INFO] Enabling Universe repository..."
sudo apt install -y software-properties-common
sudo add-apt-repository universe -y

echo "[INFO] Adding ROS 2 apt repository..."
sudo apt install -y curl gnupg lsb-release
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(source /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 3. Install ROS 2 Humble packages
echo "[INFO] Installing ROS 2 Humble Desktop..."
sudo apt update
sudo apt install -y ros-humble-desktop

# 4. Install dev tools and dependencies
echo "[INFO] Installing development tools..."
sudo apt install -y python3-colcon-common-extensions python3-rosdep python3-vcstool build-essential terminator \
                    python3-pip python3-argcomplete git

# 5. Initialize rosdep
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
    echo "[INFO] Initializing rosdep..."
    sudo rosdep init
fi
rosdep update

# 6. Setup Environment
echo "[INFO] Sourcing ROS 2 in ~/.bashrc..."
if ! grep -q "source /opt/ros/humble/setup.bash" ~/.bashrc; then
    echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
fi

echo "============================================="
echo "[SUCCESS] ROS 2 Humble is installed!"
echo "Please close this terminal and open a new one,"
echo "or run: source ~/.bashrc"
echo "Next step: ./setup_workspace.sh"
echo "============================================="

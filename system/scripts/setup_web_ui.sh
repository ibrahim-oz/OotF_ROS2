#!/bin/bash

# Exit on any error
set -e

echo "============================================="
echo "   Doosan IPC Web UI Setup (Ubuntu 22.04)  "
echo "============================================="

echo "[INFO] Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

echo "[INFO] Installing Python venv..."
sudo apt install -y python3-venv python3-pip

# Backend setup
echo "[INFO] Setting up Python Backend..."
cd $HOME/doosan_ipc/web_ui/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt || pip install fastapi uvicorn websockets pyyaml

# Frontend setup
echo "[INFO] Setting up React Frontend..."
cd $HOME/doosan_ipc/web_ui/frontend
npm install

echo "============================================="
echo "[SUCCESS] Web UI setup complete!"
echo "Backend: cd ~/doosan_ipc/web_ui/backend && source venv/bin/activate && python3 main.py"
echo "Frontend: cd ~/doosan_ipc/web_ui/frontend && npm run dev"
echo "============================================="

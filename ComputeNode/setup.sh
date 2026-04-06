#!/bin/bash

# ==========================================
# Worker Node Initialization Script
# Run this ONCE on each new worker machine.
# ==========================================

# 1. Update system and install Python 3 (Needed for benchmark.py)
echo "[*] Updating system and installing Python 3..."
sudo apt-get update -y && sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-pip openssh-server curl

# 2. Install Docker (The execution engine)
echo "[*] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
else
    echo "    Docker is already installed."
fi

# 3. Add the current user to the Docker group (Crucial for passwordless execution)
echo "[*] Adding user $USER to the docker group..."
sudo usermod -aG docker $USER

# 4. Prepare the Data Directories
echo "[*] Creating cluster data directories..."
sudo mkdir -p /tmp/cluster_data
sudo chown -R $USER:$USER /tmp/cluster_data

# 5. Setup SSH for the Head Node
echo "[*] Setting up SSH Authorized Keys..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

echo ""
echo "================================================================="
echo "✅ Setup Complete!"
echo ""
echo "CRITICAL NEXT STEP:"
echo "Please paste the Head Node's public SSH key (orchestrator_key.pub)"
echo "into this file: ~/.ssh/authorized_keys"
echo "================================================================="
echo "Note: You need to log out and log back in for Docker group permissions to take effect."
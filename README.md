# Supercomputing-Cluster

Autonomous AI Computing Cluster

A zero-touch, SSH-driven orchestration system for a home lab environment. This cluster utilizes a locally hosted Large Language Model (LLM) to dynamically architect, provision, and execute Dockerized workloads across a distributed network of heterogeneous hardware. Architecture Overview

    Head Node (The Orchestrator): The central brain. It maintains a SQLite ledger of cluster state, sweeps the network for available workers, queries the LLM to write code/determine hardware limits, and dispatches tasks via SSH.

    Worker Nodes (The Muscle): Dumb execution environments. They run zero background daemons. The Head Node pushes tasks to them via SSH, spins up strictly limited Docker containers, and uses rsync to retrieve the output before wiping the node clean.

    AI Engine (The Pre-Frontal Cortex): A dedicated GPU node hosting a local LLM (e.g., Llama 3 via Ollama) that translates human prompts into machine-executable Python code and JSON resource requirements.

Directory Structure

Your Head Node should be organized exactly like this:
Plaintext

    HeadNode/
    ├── main.py
    ├── database/
    │   ├── schema.sql
    │   └── db_manager.py
    ├── network/
    │   ├── discovery.py
    │   └── benchmark.py
    ├── execution/
    │   ├── dispatcher.py
    │   └── sync.py
    ├── ai_engine/
    │   ├── prompter.py
    │   └── evaluator.py
    └── scripts/
        └── setup_worker.sh

Phase 1: Network & Hardware Prerequisites

Before configuring the software, ensure your physical environment is prepared:

    Networking: All machines must be connected to the same local network (e.g., via a Cisco switch).

    Static IPs: * Assign a static IP to the Head Node for reliable remote access.

        Assign a static IP to the GPU Node (e.g., 192.168.1.100) so the Head Node knows exactly where the LLM API lives.

    Base OS: Install Ubuntu or Debian on all machines.

Phase 2: Worker Node Setup (The Muscle)

Worker nodes require almost zero configuration. Run the provided bash script on every worker machine (PC#3, Server #1, and PC#2).

    Transfer setup_worker.sh to the worker node.

    Make it executable and run it:
    Bash

    chmod +x setup_worker.sh
    ./setup_worker.sh

    Note: This script installs Docker, Python3, and creates the /tmp/cluster_data staging directory. Log out and log back in for Docker user group permissions to apply.

Phase 3: AI Engine Setup (The GPU Node)

The node containing your GPU (PC#2) needs special software to host the LLM and allow Docker to utilize the graphics card.

    Install Nvidia Drivers:
    Bash

sudo ubuntu-drivers autoinstall
sudo reboot

Install Nvidia Container Toolkit: Follow Nvidia's official documentation to allow Docker to use the --gpus=all flag.

Install Ollama:
Bash

    curl -fsSL https://ollama.com/install.sh | sh

    Expose Ollama to the Network: By default, Ollama only listens to localhost.

        Edit the service: sudo systemctl edit ollama.service

        Add this under [Service]: 
            Environment="OLLAMA_HOST=0.0.0.0"
            Environment="OLLAMA_MULTIMODAL_GPU=1"
            Environment="CUDA_VISIBLE_DEVICES=0,1"

        Restart: sudo systemctl daemon-reload && sudo systemctl restart ollama

    Pull the Model: ollama run llama3 (or whichever model you prefer).

Phase 4: Head Node Setup (The Orchestrator)

The Head Node controls everything via passwordless SSH.

    Generate the Master SSH Key:
    Bash

ssh-keygen -t ed25519 -f ~/.ssh/orchestrator_key -N ""

    CRITICAL: Do not add a password (-N ""). If the key requires a password, the autonomous daemon will freeze.

Distribute the Key: Copy the contents of ~/.ssh/orchestrator_key.pub and paste it into the ~/.ssh/authorized_keys file of every worker node.

Install Dependencies:
Bash

    pip3 install openai

    (SQLite, Subprocess, Re, JSON, etc., are built into standard Python).

Phase 5: Execution

With the infrastructure complete, you can start the cluster and feed it tasks.
1. Start the Orchestrator

Run this on the Head Node to spin up the master control loop:
Bash

python3 main.py

The orchestrator will automatically create cluster.db, run a background sweep to find your worker nodes, benchmark them, and begin watching the job queue.
2. Submitting a Task

To give the cluster a job, you simply insert a text prompt into the Tasks table in the SQLite database. You can do this by creating a quick submit.py script on the Head Node:
Python

import sqlite3

prompt = "Write a Python script that calculates the first 100 prime numbers and saves them to a file named primes.txt in the current directory."

with sqlite3.connect("cluster.db") as conn:
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Tasks (prompt, status) VALUES (?, 'pending')", (prompt,))
    conn.commit()
    print(f"Task submitted! ID: {cursor.lastrowid}")

Once submitted, main.py will:

    Detect the pending task.

    Send the prompt to the GPU node to generate Docker limits and code.

    Evaluate the AI's response for safety.

    Route it to the best available worker node.

    Retrieve the primes.txt file via rsync when it finishes.
import subprocess
import os

# --- CONFIGURATION ---
SSH_USER = "user"
SSH_KEY_PATH = "~/.ssh/orchestrator_key"
SSH_OPTS = [
    "-i", os.path.expanduser(SSH_KEY_PATH),
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=5"
]
# ---------------------

def deploy_container(ip, task_id, docker_image, command, cpu_limit, ram_limit_gb, use_gpu=False):
    """
    Spins up a Docker container on the target IP with strict resource limits.
    Runs detached (-d) so the Head Node can immediately move on.
    """
    ssh_target = f"{SSH_USER}@{ip}"
    container_name = f"task_{task_id}"
    
    # Base Docker command
    docker_cmd = [
        "docker", "run", "-d",
        f"--name={container_name}",
        f"--cpus={cpu_limit}",
        f"--memory={ram_limit_gb}g",
        # Map a specific local directory for the task's output
        f"-v", f"/tmp/cluster_data/{task_id}:/app/output"
    ]
    
    # Add GPU access if the AI requested it and the node supports it
    if use_gpu:
        docker_cmd.append("--gpus=all")
        
    docker_cmd.extend([docker_image, command])
    
    # Convert list back to a string for SSH execution
    full_cmd = " ".join(docker_cmd)
    
    try:
        print(f"[{ip}] Dispatching Task {task_id} -> {docker_image}")
        ssh_cmd = ["ssh"] + SSH_OPTS + [ssh_target, full_cmd]
        
        result = subprocess.run(ssh_cmd, check=True, capture_output=True, text=True)
        container_id = result.stdout.strip()
        
        print(f"[{ip}] Success! Container running. ID: {container_id[:12]}")
        return {"status": "success", "container_id": container_id, "name": container_name}
        
    except subprocess.CalledProcessError as e:
        print(f"[{ip}] Dispatch Failed for Task {task_id}. Error: {e.stderr}")
        return {"status": "error", "error": e.stderr}

def check_node_health(ip):
    """
    Queries the node for a list of currently running container names.
    This prevents the Head Node's database from drifting from reality.
    """
    ssh_target = f"{SSH_USER}@{ip}"
    
    try:
        # Format output to just return container names separated by newlines
        ssh_cmd = ["ssh"] + SSH_OPTS + [ssh_target, "docker ps --format '{{.Names}}'"]
        result = subprocess.run(ssh_cmd, check=True, capture_output=True, text=True)
        
        running_containers = result.stdout.strip().split('\n')
        # Filter out empty strings if the node has no containers running
        running_containers = [c for c in running_containers if c] 
        
        return running_containers
    except subprocess.CalledProcessError:
        print(f"[{ip}] WARNING: Node unresponsive to health check!")
        return None

def kill_task(ip, container_name):
    """Forcefully stops and removes a container (Used for timeouts)."""
    ssh_target = f"{SSH_USER}@{ip}"
    print(f"[{ip}] Terminating {container_name}...")
    
    try:
        # Stop and remove the container
        ssh_cmd = ["ssh"] + SSH_OPTS + [ssh_target, f"docker rm -f {container_name}"]
        subprocess.run(ssh_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False
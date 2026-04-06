import subprocess
import os

# --- CONFIGURATION ---
SSH_USER = "user"
SSH_KEY_PATH = "~/.ssh/orchestrator_key"
HEAD_NODE_STORAGE = "/mnt/headnode_storage/completed_tasks/"
# ---------------------

def retrieve_task_data(ip, task_id):
    """
    Uses rsync to pull data back to the Head Node.
    Automatically deletes the worker's copy ONLY if the transfer is 100% successful.
    """
    print(f"[{ip}] Retrieving output data for Task {task_id}...")
    
    source_path = f"{SSH_USER}@{ip}:/tmp/cluster_data/{task_id}/"
    dest_path = os.path.join(HEAD_NODE_STORAGE, f"task_{task_id}/")
    
    # Ensure the destination folder exists on the Head Node
    os.makedirs(dest_path, exist_ok=True)
    
    # rsync command with the magic --remove-source-files flag
    rsync_cmd = [
        "rsync", "-avz",
        "--remove-source-files",
        "-e", f"ssh -i {os.path.expanduser(SSH_KEY_PATH)} -o StrictHostKeyChecking=accept-new",
        source_path, dest_path
    ]
    
    try:
        subprocess.run(rsync_cmd, check=True, stdout=subprocess.DEVNULL)
        print(f"[{ip}] Data for Task {task_id} safely secured on Head Node.")
        
        # Rsync removes the files, but leaves the empty directory structure. 
        # Clean up the empty folder on the worker node.
        cleanup_cmd = ["ssh", "-i", os.path.expanduser(SSH_KEY_PATH), f"{SSH_USER}@{ip}", f"rm -rf /tmp/cluster_data/{task_id}"]
        subprocess.run(cleanup_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"[{ip}] Data retrieval failed for Task {task_id}! Data remains on worker.")
        return False

def cluster_garbage_collection(active_ips):
    """
    The 'Clean Slate' maintenance function.
    Wipes unused Docker images and stopped containers across the cluster.
    """
    print("\n--- Initiating Cluster-Wide Garbage Collection ---")
    
    for ip in active_ips:
        ssh_target = f"{SSH_USER}@{ip}"
        print(f"[{ip}] Pruning Docker system...")
        
        # -a removes unused images, -f forces it without asking "are you sure?"
        ssh_cmd = [
            "ssh", "-i", os.path.expanduser(SSH_KEY_PATH),
            "-o", "BatchMode=yes",
            ssh_target, "docker system prune -af"
        ]
        
        try:
            subprocess.run(ssh_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[{ip}] Clean.")
        except subprocess.CalledProcessError:
            print(f"[{ip}] Failed to prune.")
            
    print("--- Garbage Collection Complete ---\n")
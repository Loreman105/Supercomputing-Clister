import socket
import ipaddress
import subprocess
import json
import concurrent.futures

# --- CONFIGURATION ---
SUBNET = "192.168.1.0/24"          # Change this to your Cisco switch's subnet
SSH_USER = "user"                  # The default user on your worker nodes
SSH_KEY_PATH = "~/.ssh/orchestrator_key"
BENCHMARK_SCRIPT = "benchmark.py"  # Local path to the script above
# ---------------------

def check_port_22(ip):
    """Quickly checks if port 22 is open on a target IP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5) # Fast timeout for local network
    result = sock.connect_ex((str(ip), 22))
    sock.close()
    if result == 0:
        return str(ip)
    return None

def scan_network_for_ssh(subnet):
    """Sweeps the subnet and returns a list of IPs with SSH open."""
    print(f"[*] Sweeping subnet {subnet} for active SSH ports...")
    active_ips = []
    network = ipaddress.ip_network(subnet, strict=False)
    
    # Use 50 threads to scan the network in ~2 seconds instead of 120 seconds
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(check_port_22, network.hosts())
        for ip in results:
            if ip:
                active_ips.append(ip)
                
    print(f"[*] Found {len(active_ips)} devices with port 22 open.")
    return active_ips

def benchmark_node(ip):
    """Attempts zero-touch SSH, pushes benchmark, and retrieves JSON vector."""
    ssh_target = f"{SSH_USER}@{ip}"
    
    # Common SSH flags for autonomous scripts (prevents hanging on prompts)
    ssh_opts = [
        "-i", os.path.expanduser(SSH_KEY_PATH),
        "-o", "StrictHostKeyChecking=accept-new", # Auto-accepts new IPs
        "-o", "BatchMode=yes",                    # Fails immediately if password is required
        "-o", "ConnectTimeout=3"
    ]

    try:
        # 1. Push the benchmark script to the /tmp directory
        print(f"[{ip}] Attempting connection & pushing payload...")
        scp_cmd = ["scp"] + ssh_opts + [BENCHMARK_SCRIPT, f"{ssh_target}:/tmp/benchmark.py"]
        subprocess.run(scp_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 2. Execute the script and capture the output
        print(f"[{ip}] Running benchmark...")
        ssh_cmd = ["ssh"] + ssh_opts + [ssh_target, "python3 /tmp/benchmark.py"]
        result = subprocess.run(ssh_cmd, check=True, capture_output=True, text=True)
        
        # 3. Parse the JSON Vector
        output = result.stdout.strip()
        resource_vector = json.loads(output)
        
        # 4. Cleanup (Optional, but good practice)
        cleanup_cmd = ["ssh"] + ssh_opts + [ssh_target, "rm /tmp/benchmark.py"]
        subprocess.run(cleanup_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print(f"[{ip}] Success! Registered as {resource_vector['architecture']} with {resource_vector['ram_gb']}GB RAM.")
        return {"ip": ip, "status": "online", "resources": resource_vector}
        
    except subprocess.CalledProcessError:
        print(f"[{ip}] Failed: SSH Key rejected or execution error (Not a worker node).")
        return None
    except json.JSONDecodeError:
        print(f"[{ip}] Failed: Worker returned invalid JSON.")
        return None

def discover_and_update():
    """Main function to run the discovery loop."""
    discovered_nodes = []
    active_ips = scan_network_for_ssh(SUBNET)
    
    for ip in active_ips:
        node_data = benchmark_node(ip)
        if node_data:
            discovered_nodes.append(node_data)
            
    print("\n--- Discovery Complete ---")
    print(json.dumps(discovered_nodes, indent=4))
    
    # In the future, this is where you will return `discovered_nodes` 
    # so `db_manager.py` can INSERT them into the SQLite database.
    return discovered_nodes

if __name__ == "__main__":
    import os # imported here for standalone testing of the path expansion
    discover_and_update()
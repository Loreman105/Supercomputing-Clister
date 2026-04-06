import json
import time
import platform
import subprocess
import os

def get_system_ram():
    """Reads /proc/meminfo to get total RAM in GB (Zero-dependency)."""
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if 'MemTotal' in line:
                    kb = int(line.split()[1])
                    return round(kb / (1024 * 1024), 2)
    except Exception:
        return 0.0
    return 0.0

def get_gpu_info():
    """Uses nvidia-smi to find GPU VRAM and Name."""
    gpu_data = {"vram_gb": 0.0, "name": "None", "gpu_tflops_est": 0.0}
    try:
        # Get VRAM
        vram_out = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], 
            encoding='utf-8', timeout=5
        )
        gpu_data["vram_gb"] = round(int(vram_out.strip().split('\n')[0]) / 1024, 2)
        
        # Get Name
        name_out = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], 
            encoding='utf-8', timeout=5
        )
        gpu_data["name"] = name_out.strip().split('\n')[0]
        
        # Assign an arbitrary TFlops multiplier based on having a GPU
        # In a production environment, you'd run a PyTorch matrix multiplication here.
        gpu_data["gpu_tflops_est"] = gpu_data["vram_gb"] * 1.5 
        
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass # No Nvidia GPU found or drivers missing
        
    return gpu_data

def get_cpu_compute_score():
    """Runs a quick multi-core math operation to estimate CPU power."""
    try:
        import numpy as np
        start = time.time()
        # Matrix multiplication is the core of AI workloads
        A = np.random.rand(2000, 2000)
        B = np.random.rand(2000, 2000)
        _ = np.dot(A, B)
        elapsed = time.time() - start
        
        # Invert the time so a lower time = higher score
        return round(10.0 / elapsed, 2) 
    except ImportError:
        # Fallback pure-Python CPU test if Numpy isn't installed yet
        start = time.time()
        _ = sum([i * i for i in range(5000000)])
        elapsed = time.time() - start
        return round(2.0 / elapsed, 2)

def run_benchmark():
    gpu_info = get_gpu_info()
    
    resource_vector = {
        "architecture": platform.machine(),
        "os": platform.system(),
        "ram_gb": get_system_ram(),
        "cpu_tflops_score": get_cpu_compute_score(),
        "gpu_name": gpu_info["name"],
        "gpu_vram_gb": gpu_info["vram_gb"],
        "gpu_tflops_score": gpu_info["gpu_tflops_est"]
    }
    
    # Print exactly and only the JSON so the Head Node can parse it
    print(json.dumps(resource_vector))

if __name__ == "__main__":
    run_benchmark()
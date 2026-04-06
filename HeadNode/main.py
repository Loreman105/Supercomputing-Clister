import time
import logging
import sqlite3
import threading

# Import your custom modules
from database import db_manager
from network import discovery
from execution import dispatcher, sync
from ai_engine import prompter, evaluator

# Configure logging for the Head Node console
logging.basicConfig(
    level=logging.INFO, 
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)

# --- CLUSTER TIMING CONFIGURATION ---
DISCOVERY_INTERVAL = 300    # Scan the network for new nodes every 5 minutes
HEALTH_CHECK_INTERVAL = 30  # Check on running Docker containers every 30 seconds
QUEUE_CHECK_INTERVAL = 5    # Check the DB for new tasks every 5 seconds
# ------------------------------------

def run_discovery_background():
    """Runs network discovery in a separate thread so it doesn't block the job queue."""
    logging.info("Initiating background network sweep...")
    discovered_nodes = discovery.discover_and_update()
    
    if discovered_nodes:
        for node in discovered_nodes:
            db_manager.update_node(node)
            logging.info(f"Updated node ledger for {node['ip']}")

def get_running_tasks():
    """Helper to fetch currently running tasks directly from the DB."""
    with sqlite3.connect(db_manager.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Tasks WHERE status = 'running'")
        return cursor.fetchall()

def sync_completed_tasks():
    """
    Checks if running containers have finished. 
    If finished, triggers rsync and updates the DB state.
    """
    running_tasks = get_running_tasks()
    if not running_tasks:
        return

    # Group tasks by IP to minimize SSH connections
    tasks_by_ip = {}
    for t in running_tasks:
        ip = t['assigned_node_ip']
        if ip not in tasks_by_ip:
            tasks_by_ip[ip] = []
        tasks_by_ip[ip].append(t)

    for ip, tasks in tasks_by_ip.items():
        # Get active containers on this node
        active_containers = dispatcher.check_node_health(ip)
        
        if active_containers is None:
            continue # Node might be temporarily offline, skip for now

        for task in tasks:
            container_name = task['container_name']
            
            # If the container name is no longer in the running list, it finished or crashed
            if container_name not in active_containers:
                logging.info(f"Task {task['task_id']} on {ip} has terminated. Attempting sync...")
                
                # Retrieve the data
                success = sync.retrieve_task_data(ip, task['task_id'])
                
                if success:
                    db_manager.update_task_status(task['task_id'], 'completed')
                    logging.info(f"Task {task['task_id']} marked as COMPLETED.")
                else:
                    db_manager.update_task_status(task['task_id'], 'failed')
                    logging.error(f"Task {task['task_id']} data sync failed. Marked as FAILED.")

def process_pending_tasks():
    """
    Pulls the next task, asks the LLM to write the code, and dispatches it.
    """
    task = db_manager.get_pending_task()
    if not task:
        return # Queue is empty

    task_id = task['task_id']
    prompt = task['prompt']
    
    logging.info(f"Picked up pending task #{task_id}: '{prompt[:50]}...'")

    # 1. Ask the AI Brain
    raw_llm_output = prompter.generate_task_payload(prompt)
    
    # 2. Evaluate and enforce limits
    validated_reqs = evaluator.evaluate_task(raw_llm_output)
    
    if not validated_reqs:
        logging.error(f"Task #{task_id} failed AI evaluation. Parking in Admin Inbox.")
        db_manager.update_task_status(task_id, 'failed')
        db_manager.send_to_admin_inbox(prompt, "Failed schema validation or hallucinated limits.", {})
        return

    # 3. Save the generated code/limits to the database
    db_manager.update_task_execution_details(
        task_id=task_id,
        code=validated_reqs['code'],
        docker_image=validated_reqs['docker_image'],
        cpu_limit=validated_reqs['cpu_cores'],
        ram_limit_gb=validated_reqs['ram_limit_gb'],
        requires_gpu=validated_reqs['requires_gpu']
    )

    # 4. Find the best worker node for this specific task
    best_node = db_manager.find_capable_node(
        ram_limit_gb=validated_reqs['ram_limit_gb'], 
        requires_gpu=validated_reqs['requires_gpu']
    )

    if best_node:
        ip = best_node['ip_address']
        logging.info(f"Routing Task #{task_id} to Node {ip}...")
        
        # Dispatch the container
        # Note: We pass the generated code directly to the container as a command
        # (For complex scripts, you'd save it to a .py file locally and copy it over)
        command_string = f"python3 -c \"{validated_reqs['code']}\""
        
        dispatch_result = dispatcher.deploy_container(
            ip=ip,
            task_id=task_id,
            docker_image=validated_reqs['docker_image'],
            command=command_string,
            cpu_limit=validated_reqs['cpu_cores'],
            ram_limit_gb=validated_reqs['ram_limit_gb'],
            use_gpu=validated_reqs['requires_gpu']
        )
        
        if dispatch_result['status'] == 'success':
            db_manager.assign_task_to_node(task_id, ip, dispatch_result['name'])
        else:
            logging.error(f"Failed to dispatch Task #{task_id}. Re-queuing.")
            # It stays 'pending' and will try again or try another node next loop
    else:
        logging.warning(f"No capable nodes currently available for Task #{task_id}. Waiting...")
        # Evaluator already capped max limits to physical hardware, so if it's here, 
        # it means nodes are just busy. We leave it 'pending' to try again later.

def main_loop():
    """The master control loop of the Head Node."""
    logging.info("Starting Cluster Orchestrator on Head Node...")
    
    # Initialize the database if it doesn't exist
    db_manager.init_db()
    
    # Track timers
    last_discovery = 0
    last_health_check = 0
    
    while True:
        try:
            current_time = time.time()
            
            # --- 1. Background Network Discovery ---
            if current_time - last_discovery > DISCOVERY_INTERVAL:
                # Use threading so the Head Node doesn't freeze during the scan
                threading.Thread(target=run_discovery_background).start()
                last_discovery = current_time
                
            # --- 2. State Synchronization & Data Retrieval ---
            if current_time - last_health_check > HEALTH_CHECK_INTERVAL:
                sync_completed_tasks()
                last_health_check = current_time
                
            # --- 3. Process the Job Queue ---
            process_pending_tasks()
            
            # --- 4. Rest to save CPU cycles ---
            time.sleep(QUEUE_CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            logging.info("Orchestrator shutting down gracefully. Goodbye.")
            break
        except Exception as e:
            # Catch-all to prevent the Head Node daemon from crashing 
            logging.error(f"Critical error in main loop: {e}")
            time.sleep(10) # Wait a bit before trying again if something broke

if __name__ == "__main__":
    # Add a dummy task for testing just to kickstart the system!
    # db_manager.add_new_task("Write a script that calculates the first 50 Fibonacci numbers and prints them.")
    
    main_loop()
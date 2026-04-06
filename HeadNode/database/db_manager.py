# database/db_manager.py
import sqlite3
import os
import json

# --- CONFIGURATION ---
DB_PATH = "cluster.db"
SCHEMA_PATH = "database/schema.sql"
# ---------------------

def init_db():
    """Initializes the SQLite database using the schema.sql file."""
    db_is_new = not os.path.exists(DB_PATH)
    with sqlite3.connect(DB_PATH) as conn:
        if db_is_new:
            print(f"[*] Creating new cluster database at {DB_PATH}")
            with open(SCHEMA_PATH, 'r') as f:
                schema_script = f.read()
            conn.executescript(schema_script)
        else:
            print(f"[*] Connected to existing database at {DB_PATH}")

def update_node(node_data):
    """
    Upserts a node into the database. Called when discovery.py finds a worker.
    Uses REPLACE to update the 'last_seen' and hardware specs if they changed.
    """
    ip = node_data['ip']
    res = node_data['resources']
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO Nodes 
            (ip_address, architecture, os, ram_gb, cpu_tflops_score, 
             gpu_name, gpu_vram_gb, gpu_tflops_score, status, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'online', CURRENT_TIMESTAMP)
        ''', (
            ip, res['architecture'], res['os'], res['ram_gb'], 
            res['cpu_tflops_score'], res['gpu_name'], res['gpu_vram_gb'], 
            res['gpu_tflops_score']
        ))
        conn.commit()

def add_new_task(prompt):
    """Adds a raw prompt from the user into the queue as pending."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO Tasks (prompt, status)
            VALUES (?, 'pending')
        ''', (prompt,))
        conn.commit()
        return cursor.lastrowid

def get_pending_task():
    """Fetches the oldest unassigned task from the queue."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM Tasks 
            WHERE status = 'pending' 
            ORDER BY created_at ASC LIMIT 1
        ''')
        return cursor.fetchone()

def update_task_execution_details(task_id, code, docker_image, cpu_limit, ram_limit_gb, requires_gpu):
    """Saves the AI's generated code and resource limits to the task."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Tasks 
            SET generated_code = ?, docker_image = ?, cpu_limit = ?, 
                ram_limit_gb = ?, requires_gpu = ?, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        ''', (code, docker_image, cpu_limit, ram_limit_gb, requires_gpu, task_id))
        conn.commit()

def find_capable_node(ram_limit_gb, requires_gpu):
    """
    The orchestrator's routing brain. Finds an online node that meets the hardware criteria.
    Prioritizes nodes with higher TFlops scores.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if requires_gpu:
            # Find a node with a GPU and enough VRAM/RAM
            cursor.execute('''
                SELECT * FROM Nodes 
                WHERE status = 'online' AND gpu_tflops_score > 0 
                AND gpu_vram_gb >= ? AND ram_gb >= ?
                ORDER BY gpu_tflops_score DESC LIMIT 1
            ''', (ram_limit_gb, ram_limit_gb)) # Assuming VRAM requirement roughly equals RAM requirement for simplicity
        else:
            # Find a CPU node with enough system RAM
            cursor.execute('''
                SELECT * FROM Nodes 
                WHERE status = 'online' AND ram_gb >= ?
                ORDER BY cpu_tflops_score DESC LIMIT 1
            ''', (ram_limit_gb,))
            
        return cursor.fetchone()

def assign_task_to_node(task_id, ip_address, container_name):
    """Marks a task as running and links it to a specific worker node."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Tasks 
            SET assigned_node_ip = ?, container_name = ?, status = 'running', updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        ''', (ip_address, container_name, task_id))
        conn.commit()

def update_task_status(task_id, status):
    """Updates a task to 'completed' or 'failed'."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE Tasks 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        ''', (status, task_id))
        conn.commit()

def send_to_admin_inbox(prompt, reasoning, requirements_dict):
    """Parks an impossible task in the dead letter queue for human review."""
    req_json = json.dumps(requirements_dict)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO Admin_Inbox (original_prompt, ai_reasoning, required_resources)
            VALUES (?, ?, ?)
        ''', (prompt, reasoning, req_json))
        conn.commit()
        print(f"[!] Task parked in Admin Inbox: {reasoning}")

if __name__ == "__main__":
    # Test block to initialize the DB when running this file directly
    init_db()
    print("Database manager ready.")
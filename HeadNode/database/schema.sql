-- database/schema.sql

-- Table: Nodes (Your hardware roster)
CREATE TABLE IF NOT EXISTS Nodes (
    ip_address TEXT PRIMARY KEY,
    architecture TEXT,
    os TEXT,
    ram_gb REAL,
    cpu_tflops_score REAL,
    gpu_name TEXT,
    gpu_vram_gb REAL,
    gpu_tflops_score REAL,
    status TEXT DEFAULT 'online', -- 'online' or 'offline'
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: Tasks (Your job queue and execution state)
CREATE TABLE IF NOT EXISTS Tasks (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt TEXT NOT NULL,
    generated_code TEXT,
    docker_image TEXT,
    cpu_limit REAL,
    ram_limit_gb REAL,
    requires_gpu BOOLEAN,
    assigned_node_ip TEXT,
    container_name TEXT,
    status TEXT DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assigned_node_ip) REFERENCES Nodes(ip_address)
);

-- Table: Admin_Inbox (The Dead Letter Queue for impossible/failed tasks)
CREATE TABLE IF NOT EXISTS Admin_Inbox (
    hold_id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_prompt TEXT,
    ai_reasoning TEXT,
    required_resources TEXT,
    status TEXT DEFAULT 'requires_review', -- 'requires_review', 'approved', 'dismissed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
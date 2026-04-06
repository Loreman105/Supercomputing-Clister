import re
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Cluster hardware limits (adjust to your environment)
MAX_RAM_GB = 64
MAX_CPU_CORES = 32

# Required keys for a task
REQUIRED_KEYS = ['ram_limit_gb', 'cpu_cores', 'docker_image']

def clean_raw_output(raw_text: str) -> str:
    """
    Extract JSON from LLM output, stripping Markdown or extra text.
    """
    match = re.search(r'```json(.*?)```', raw_text, re.DOTALL)
    if match:
        json_string = match.group(1).strip()
    else:
        json_string = raw_text.strip()
    return json_string

def parse_json(json_string: str) -> dict | None:
    """
    Convert cleaned JSON string into a Python dictionary.
    """
    try:
        data = json.loads(json_string)
        if not isinstance(data, dict):
            logging.warning("Parsed JSON is not a dictionary.")
            return None
        return data
    except json.JSONDecodeError as e:
        logging.warning(f"JSON parsing failed: {e}")
        return None

def validate_schema(task_dict: dict) -> bool:
    """
    Ensure all required fields exist.
    """
    missing_keys = [key for key in REQUIRED_KEYS if key not in task_dict]
    if missing_keys:
        logging.warning(f"Task is missing required keys: {missing_keys}")
        return False
    return True

def enforce_hardware_limits(task_dict: dict) -> dict:
    """
    Cap resource requests to cluster hardware limits.
    """
    task_dict['ram_limit_gb'] = min(task_dict.get('ram_limit_gb', 0), MAX_RAM_GB)
    task_dict['cpu_cores'] = min(task_dict.get('cpu_cores', 0), MAX_CPU_CORES)
    return task_dict

def evaluate_task(raw_text: str) -> dict | None:
    """
    Full evaluation pipeline:
    1. Clean
    2. Parse
    3. Validate
    4. Enforce hardware limits
    Returns sanitized task dict or None if invalid.
    """
    json_string = clean_raw_output(raw_text)
    task_dict = parse_json(json_string)
    
    if task_dict is None:
        logging.error("Task rejected: invalid JSON.")
        return None

    if not validate_schema(task_dict):
        logging.error("Task rejected: schema validation failed.")
        return None

    task_dict = enforce_hardware_limits(task_dict)
    logging.info(f"Task approved: {task_dict}")
    return task_dict

# Example usage
if __name__ == "__main__":
    sample_output = """
    Here is your task:
    ```json
    {
        "ram_limit_gb": 128,
        "cpu_cores": 40,
        "docker_image": "ubuntu:22.04"
    }
    ```
    """
    evaluated_task = evaluate_task(sample_output)
    print(evaluated_task)
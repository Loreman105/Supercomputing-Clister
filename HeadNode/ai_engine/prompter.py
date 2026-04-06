from openai import OpenAI

# --- CONFIGURATION ---
# Assuming you are running Ollama or vLLM on your GPU node (PC#2)
LLM_BASE_URL = "http://192.168.1.100:11434/v1" 
LLM_MODEL = "deepseek-coder-v2:16b-lite-instruct-q4_K_M" # Or whatever model you have loaded
LLM_API_KEY = "not-needed-for-local"
# ---------------------

client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

SYSTEM_PROMPT = """
You are the central Systems Architect for an autonomous computing cluster.
Your job is to take a user's request, write the Python code to fulfill it, and determine the hardware limits required to safely execute it in a Docker container.

CRITICAL INSTRUCTIONS:
1. You must output EXACTLY AND ONLY a valid JSON object. 
2. Do not include any conversational text, explanations, or markdown blocks outside the JSON.
3. Your Python code must be completely self-contained.

EXPECTED JSON SCHEMA:
{
    "docker_image": "python:3.11-slim",
    "cpu_limit": 2,                  
    "ram_limit_gb": 4.0,               
    "requires_gpu": false,             
    "code": "print('Hello World')\\n" 
}
"""

def generate_task_payload(user_prompt):

    print(f"[*] Asking LLM to architect task: '{user_prompt}'")
    
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1, 
            max_tokens=2000,
            extra_body={
                "options": {
                    "num_ctx": 16384,
                    "num_predict": 2000,
                    "num_gpu": 2         #
                }
            }
        )
        
        raw_output = response.choices[0].message.content
        return raw_output
        
    except Exception as e:
        print(f"[!] LLM Generation failed: {e}")
        return None
import os
import json
import uuid
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY", "")

# We use gemini-flash-latest 
target_model = "gemini/gemini-flash-latest" if "AQ." in api_key else "gpt-4o"

client = OpenAI(
    api_key=api_key,
    base_url="http://127.0.0.1:8080/v1"
)

def make_request_with_retry(messages, session_id):
    max_retries = 10
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=target_model,
                messages=messages,
                temperature=0.0,
                extra_headers={"X-Axon-Session-ID": session_id}
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "429" in str(e) or "429 Too Many Requests" in str(e):
                print(f"⏳ Rate limit hit. Waiting 15s (Attempt {attempt+1}/{max_retries})...")
                time.sleep(15)
            else:
                print(f"❌ API Error during evaluation: {e}")
                return None
    return None

def run_needle_in_haystack_eval():
    print("==================================================")
    print("🔍 EVALUATION: NEEDLE IN A HAYSTACK (SEMANTIC PRESERVATION)")
    print("==================================================")
    
    # Generate 100 normal logs
    haystack = []
    for i in range(1, 101):
        haystack.append({
            "log_id": f"L-{1000+i}",
            "timestamp": f"2026-06-20T10:{i%60:02d}:00Z",
            "service": "background-worker",
            "status": "OK",
            "message": f"Job {i} processed successfully with 0 errors.",
            "metrics": {"cpu_util": "45%", "mem_util": "512MB"}
        })
        
    # Inject the needle at index 42
    haystack[42]["status"] = "SYSTEM_MELTDOWN"
    haystack[42]["message"] = "CRITICAL: The quantum flux capacitor has inverted!"
    
    # We use a unique session ID so we don't accidentally hit the Semantic Cache from previous runs
    session_id = f"eval-needle-{uuid.uuid4().hex[:8]}"
    
    print(f"Dataset generated: 100 records. Needle injected at record 43 (log_id L-1043).")
    print(f"Sending via Standard OpenAI SDK to Axon Proxy (Model: {target_model})...")
    
    try:
        messages = [
            {"role": "system", "content": "You are a log analysis AI. Read the JSON array of logs."},
            {"role": "user", "content": json.dumps(haystack)},
            {"role": "user", "content": "Analyze the logs. Are there any critical or abnormal statuses? If so, what is the log_id, status, and message? Be concise."}
        ]
        
        answer = make_request_with_retry(messages, session_id)
        if not answer:
            return
        
        print("\n🤖 LLM Response:")
        print(answer)
        
        # Verify the needle was found
        success = "L-1043" in answer and "SYSTEM_MELTDOWN" in answer
        print("\n✅ EVALUATION RESULT:", "PASSED" if success else "FAILED")
        if success:
            print("The LLM successfully extracted the exact needle from the structurally compressed haystack!")
            
    except Exception as e:
        print(f"❌ Error during evaluation logic: {e}")

def run_json_extraction_eval():
    print("\n==================================================")
    print("📊 EVALUATION: DETERMINISTIC JSON EXTRACTION")
    print("==================================================")
    
    # Provide a complex dataset
    dataset = [
        {"employee_id": "E101", "name": "Alice Smith", "department": "Engineering", "salary": 120000, "performance_score": 4.8},
        {"employee_id": "E102", "name": "Bob Jones", "department": "Marketing", "salary": 85000, "performance_score": 3.9},
        {"employee_id": "E103", "name": "Charlie Davis", "department": "Engineering", "salary": 140000, "performance_score": 4.9},
        {"employee_id": "E104", "name": "Diana Prince", "department": "Sales", "salary": 95000, "performance_score": 4.2},
        {"employee_id": "E105", "name": "Eve Adams", "department": "HR", "salary": 78000, "performance_score": 4.5}
    ]
    
    session_id = f"eval-extract-{uuid.uuid4().hex[:8]}"
    
    print(f"Sending dataset to LLM via Axon Proxy...")
    print(f"Task: Extract the highest paid employee and return ONLY raw JSON matching {{'highest_paid_name': string, 'salary': number}}.")
    
    try:
        messages = [
            {"role": "user", "content": "Here is employee data:\n" + json.dumps(dataset)},
            {"role": "user", "content": "Who is the highest paid employee? Return ONLY a valid raw JSON object with keys 'highest_paid_name' and 'salary'. Do NOT wrap in markdown block."}
        ]
        answer = make_request_with_retry(messages, session_id)
        if not answer:
            return
            
        print("\n🤖 LLM Response:")
        print(answer)
        
        # Parse the JSON to prove structural equivalence
        try:
            parsed = json.loads(answer)
            success = parsed.get("highest_paid_name") == "Charlie Davis" and parsed.get("salary") == 140000
            print("\n✅ EVALUATION RESULT:", "PASSED" if success else "FAILED")
            if success:
                print("The LLM parsed the compressed pipe-delimited data and correctly computed/extracted the structured JSON result!")
        except json.JSONDecodeError:
            print("\n❌ EVALUATION RESULT: FAILED (LLM did not return valid JSON)")
            
    except Exception as e:
        print(f"❌ Error during evaluation logic: {e}")

if __name__ == "__main__":
    run_needle_in_haystack_eval()
    run_json_extraction_eval()

import json
import yaml
import time
import uuid
import sys
import os

# Ensure Axon path is available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import tiktoken
from services.agentic.pipeline import optimize_request
from services.token_optimizer import TokenOptimizer

def count_tokens(model, text):
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

def section(title: str):
    print(f"\n{'='*70}\n  {title}\n{'='*70}")

def generate_heavy_json() -> str:
    """Simulate a massive AWS EC2 DescribeInstances API response."""
    instances = []
    for i in range(100):
        instances.append({
            "InstanceId": f"i-{uuid.uuid4().hex[:8]}",
            "InstanceType": "t3.micro",
            "KeyName": "prod-key",
            "LaunchTime": "2023-10-14T08:30:00.000Z",
            "State": {"Code": 16, "Name": "running"},
            "PrivateDnsName": f"ip-10-0-1-{i}.ec2.internal",
            "PublicDnsName": f"ec2-54-10-20-{i}.compute-1.amazonaws.com",
            "SecurityGroups": [{"GroupName": "default", "GroupId": "sg-12345"}],
            "Tags": [{"Key": "Environment", "Value": "Production"}, {"Key": "Owner", "Value": "TeamA"}]
        })
    return json.dumps({"Reservations": [{"Instances": instances}]}, indent=2)

def generate_heavy_yaml() -> str:
    """Simulate a huge Kubernetes manifest with repeated boilerplate."""
    resources = []
    for i in range(20):
        resources.append({
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": f"microservice-{i}",
                "namespace": "production",
                "labels": {"app": f"microservice-{i}", "tier": "backend"}
            },
            "spec": {
                "replicas": 3,
                "selector": {"matchLabels": {"app": f"microservice-{i}"}},
                "template": {
                    "metadata": {"labels": {"app": f"microservice-{i}"}},
                    "spec": {
                        "containers": [{
                            "name": "app",
                            "image": f"registry.internal/microservice-{i}:v1.2.3",
                            "env": [
                                {"name": "DB_HOST", "value": "db.production.svc.cluster.local"},
                                {"name": "DEBUG", "value": "false"},
                                {"name": "LOG_LEVEL", "value": "info"}
                            ],
                            "resources": {"requests": {"cpu": "100m", "memory": "256Mi"}}
                        }]
                    }
                }
            }
        })
    return yaml.dump_all(resources)

def generate_heavy_stack_trace() -> str:
    """Simulate a massive Python stack trace."""
    trace = "Traceback (most recent call last):\n"
    for i in range(50):
        trace += f'  File "/usr/local/lib/python3.10/site-packages/django/core/handlers/base.py", line {100+i}, in _get_response\n'
        trace += f'    response = wrapped_callback(request, *callback_args, **callback_kwargs)\n'
        trace += f'  File "/usr/local/lib/python3.10/site-packages/django/views/generic/base.py", line {70+i}, in view\n'
        trace += f'    return self.dispatch(request, *args, **kwargs)\n'
    trace += "psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint 'users_email_key'\nDETAIL:  Key (email)=(test@example.com) already exists.\n"
    return trace

def generate_repetitive_scratchpad() -> str:
    """Simulate an agent getting stuck and repeating thoughts."""
    thought = "<thinking>\n"
    thought += "I need to query the database to find the user.\n"
    thought += "I will use the execute_sql tool.\n"
    thought += "Wait, the execute_sql tool failed because the table doesn't exist.\n"
    thought += "Let me try searching for the table name.\n"
    thought += "</thinking>\n"
    return thought * 10

def main():
    section("AXON PRODUCTION PAYLOAD BENCHMARK")
    print("Testing compression on massive, real-world formats (JSON, YAML, Logs, Scratchpads)")
    
    optimizer = TokenOptimizer()
    
    payloads = {
        "Heavy JSON (AWS EC2 API Response)": generate_heavy_json(),
        "Heavy YAML (K8s Deployments)": generate_heavy_yaml(),
        "Heavy Python Stack Trace (Error Log)": generate_heavy_stack_trace(),
        "Repetitive Agent Scratchpad": generate_repetitive_scratchpad()
    }
    
    total_original = 0
    total_compressed = 0
    
    for name, content in payloads.items():
        print(f"\n--- Testing: {name} ---")
        
        # 1. Count original tokens
        original_tokens = count_tokens("cl100k_base", content)
        total_original += original_tokens
        print(f"Original Size: {len(content):,} characters ({original_tokens:,} tokens)")
        
        # 2. Assign the correct role based on the payload type (Axon's ML heuristcs trigger differently per role)
        role = "user"
        if "Stack Trace" in name:
            role = "tool"
        elif "Scratchpad" in name:
            role = "assistant"
            
        messages = [{"role": role, "content": content}]
        res = optimize_request(messages, tools=None, model="groq/llama-3.1-8b-instant", session_id="prod-bench-1")
        processed_content = res.messages[0]["content"]
        
        # 3. Run through structural Token Optimizer (if JSON)
        if "JSON" in name:
            try:
                parsed_json = json.loads(processed_content)
                opt_result = optimizer.optimize(parsed_json, session_id="prod-bench-1", model="groq/llama-3.1-8b-instant")
                final_text = json.dumps(opt_result.data) if isinstance(opt_result.data, (dict, list)) else str(opt_result.data)
            except Exception:
                final_text = processed_content
        else:
            final_text = processed_content
            
        # 4. Count final tokens
        compressed_tokens = count_tokens("cl100k_base", final_text)
        total_compressed += compressed_tokens
        
        savings = (1 - (compressed_tokens / original_tokens)) * 100 if original_tokens else 0
        print(f"Compressed Size: {len(final_text):,} characters ({compressed_tokens:,} tokens)")
        print(f"Token Savings: {savings:.1f}%")
        
    section("FINAL RESULTS")
    overall_savings = (1 - (total_compressed / total_original)) * 100
    print(f"Total Original Tokens:   {total_original:,}")
    print(f"Total Compressed Tokens: {total_compressed:,}")
    print(f"Overall Savings:         {overall_savings:.1f}%")

if __name__ == "__main__":
    main()

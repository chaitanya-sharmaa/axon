import httpx
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()
BASE_URL = "http://127.0.0.1:8080/v1/chat/completions"

# For our dummy LLM setup, the authorization header can be anything,
# but it must match what the proxy allows. We use the real key format so Axon doesn't block it.
API_KEY = os.environ.get("GEMINI_API_KEY", os.environ.get("OPENAI_API_KEY", "dummy-key"))
print(f"DEBUG: Using API Key starting with {API_KEY[:5]}...")
HEADERS_STATELESS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

def print_result(turn_name, response):
    print(f"\n=============================================")
    print(f"🧪 {turn_name}")
    print(f"=============================================")
    print(f"Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return

    try:
        data = response.json()
        print(f"✅ LLM Replied: {data['choices'][0]['message']['content'][:60]}...")
    except Exception as e:
        print(f"Failed to parse LLM response: {response.text}")

    metrics_str = response.headers.get("x-axon-metrics")
    cache_str = response.headers.get("x-axon-cache", "MISS")
    
    if metrics_str:
        metrics = json.loads(metrics_str)
        print(f"🚀 AXON SAVINGS: {metrics.get('savings_pct', 0)}%")
        print(f"   Billed Tokens   : {metrics.get('compressed_tokens', 0)} (Original: {metrics.get('original_tokens', 0)})")
        print(f"   Winning Strategy: {metrics.get('strategy', 'Unknown')}")
        print(f"   Cache Hit       : {cache_str}")
    else:
        print("❌ No x-axon-metrics header found in response!")

def run_e2e_tests():
    with httpx.Client(timeout=60.0) as client:
        print("\n🚀 STARTING AXON BRIDGE E2E LIVE TESTS (ENTERPRISE EXAMPLES) 🚀\n")

        # ---------------------------------------------------------
        # TEST 1: Schema Flattening (Structural Compression)
        # ---------------------------------------------------------
        # Enterprise Example: A deeply nested AWS CloudTrail Log Event
        # Enterprise Example: A deeply nested AWS CloudTrail Log Event
        # Enterprise Example: A massive Medical HL7 FHIR Patient Record (EHR)
        # FHIR records are notoriously bloated with deeply nested JSON schemas.
        # Enterprise Example: A real Codebase Dependency Graph (AST / LSP)
        # AI Coding Agents (like Cursor or Copilot) send these massive graphs
        # to the LLM to provide repository-wide context. They are notoriously bloated.
        real_code_graph = {
            "query": "How does the authentication flow handle session timeouts?",
            "token_budget": 10000,
            "symbols": [
                {
                    "qualified_name": f"src.auth.middleware.SessionHandler_v{i}",
                    "kind": "function",
                    "score": 0.99,
                    "provenance": "lsp_workspace_symbols",
                    "distance": 1
                } for i in range(50)
            ] + [
                {
                    "qualified_name": f"src.db.models.UserSessionRecord_{i}",
                    "kind": "class",
                    "score": 0.85,
                    "provenance": "ast_parser",
                    "distance": 2
                } for i in range(50)
            ],
            "edges": [
                {
                    "source": f"src.auth.middleware.SessionHandler_v{i}", 
                    "target": f"src.db.models.UserSessionRecord_{i}", 
                    "type": "instantiates"
                } for i in range(50)
            ]
        }
        
        req_turn1 = {
            "model": "ollama/llama3",
            "messages": [
                {"role": "system", "content": "You are an AI Coding Assistant. Analyze the provided codebase dependency graph."},
                {"role": "user", "content": json.dumps(real_code_graph)},
                {"role": "user", "content": "Which class handles the user session database records?"}
            ]
        }
        start = time.time()
        res1 = client.post(BASE_URL, json=req_turn1, headers=HEADERS_STATELESS)
        print_result("Test 1: Axon Graph Compression (Real Codebase AST/LSP)", res1)

        # ---------------------------------------------------------
        # TEST 2: Exact-Match KV Cache ($0 cost, 0 latency)
        # ---------------------------------------------------------
        start = time.time()
        res2 = client.post(BASE_URL, json=req_turn1, headers=HEADERS_STATELESS)
        print(f"(Latency: {time.time() - start:.3f}s)")
        print_result("Test 2: Exact-Match KV Cache (Identical Code Graph)", res2)

        # ---------------------------------------------------------
        # TEST 3: Stateful Threads (Network Bandwidth Savings)
        # ---------------------------------------------------------
        req_turn3 = {
            "model": "ollama/llama3",
            "messages": [
                {"role": "user", "content": "What is the exact name of the middleware function that instantiates it?"}
            ]
        }
        headers_stateful = {**HEADERS_STATELESS, "X-Axon-Session-ID": "ai-coder-session-1", "X-Axon-Stateful-Thread": "true"}
        
        # Seed the DB first with the heavy Code Graph
        client.post(BASE_URL, json=req_turn1, headers=headers_stateful)
        
        # Send only the delta question
        res3 = client.post(BASE_URL, json=req_turn3, headers=headers_stateful)
        print_result("Test 3: Stateful Threads (Follow-up Coding Question)", res3)

        # ---------------------------------------------------------
        # TEST 4: Smart LLM Routing
        # ---------------------------------------------------------
        # Enterprise Example: RAG Context containing a massive legal contract
        legal_contract_chunk = (
            "ARTICLE IV - INDEMNIFICATION AND LIABILITY LIMITATIONS.\n"
            "Section 4.1 Indemnification by Service Provider. Service Provider shall indemnify, defend and hold harmless "
            "Customer and its Affiliates from and against any and all Losses arising out of or related to third party claims "
            "alleging that the Services infringe, misappropriate or violate any Intellectual Property Right of such third party.\n"
        ) * 50 # Simulate a large 30-page context window

        req_turn4 = {
            "model": "ollama/llama3",
            "messages": [
                {"role": "system", "content": "You are a corporate paralegal reviewing an MSA."},
                {"role": "user", "content": f"Context: {legal_contract_chunk}\n\nQuestion: Does the Service Provider have to indemnify the Customer for IP infringement?"}
            ]
        }
        res4 = client.post(BASE_URL, json=req_turn4, headers=HEADERS_STATELESS)
        print_result("Test 4: Smart Routing (Massive Legal RAG Context routed to larger model)", res4)

        # ---------------------------------------------------------
        # TEST 5: Autonomous JSON Healing
        # ---------------------------------------------------------
        # Enterprise Example: Extracting unstructured financial data into structured JSON for an ETL pipeline
        req_turn5 = {
            "model": "ollama/llama3",
            "messages": [
                {"role": "system", "content": "You are a financial ETL pipeline parser."},
                {"role": "user", "content": "Extract the Q3 revenue ($45.2M) and net income ($12.1M) for Acme Corp into a JSON object with keys 'revenue' and 'net_income'."}
            ],
            "response_format": {"type": "json_object"}
        }
        res5 = client.post(BASE_URL, json=req_turn5, headers=HEADERS_STATELESS)
        print_result("Test 5: Autonomous JSON Healing (Financial ETL Extraction)", res5)

        # ---------------------------------------------------------
        # TEST 6: Fast Semantic Caching (Fuzzy match)
        # ---------------------------------------------------------
        # Semantic Cache requires identical structure but fuzzy natural language.
        # We ask the exact same intent as Test 5, but rephrase it!
        req_turn6 = {
            "model": "ollama/llama3",
            "messages": [
                {"role": "system", "content": "You are a financial ETL pipeline parser."},
                {"role": "user", "content": "Can you pull the Q3 revenue ($45.2M) and the net income ($12.1M) for Acme Corp into a JSON output with 'revenue' and 'net_income'?"}
            ],
            "response_format": {"type": "json_object"}
        }
        res6 = client.post(BASE_URL, json=req_turn6, headers=HEADERS_STATELESS)
        print_result("Test 6: Fast Semantic Cache (Fuzzy Natural Language Match)", res6)

if __name__ == "__main__":
    run_e2e_tests()

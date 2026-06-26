import os
import json
import time
from openai import OpenAI

# Initialize the OpenAI client pointing to the local Axon Bridge proxy
client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="sk-axon-test"
)

# ── Dummy Tools (Verbose Schemas) ─────────────────────────────────────────────
# We define 5 verbose schemas to test the Schema Differential (pruning unused ones)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Searches the web for real-time information, news, and current events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query string."},
                    "num_results": {"type": "integer", "description": "Number of results to return (max 10)."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": "Executes python code in a sandboxed environment and returns stdout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The python code to execute."},
                    "timeout": {"type": "integer", "description": "Timeout in seconds."}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the contents of a local file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Absolute path to the file."}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes content to a local file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Commits all changes to the git repository.",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string", "description": "Commit message."}},
                "required": ["message"]
            }
        }
    }
]

# We use a unique session ID to enable the stateful/agentic passes
SESSION_ID = f"agent-test-{int(time.time())}"
print(f"\\n🧪 Starting Agentic Workflow Test | Session: {SESSION_ID}")
print("=" * 80)

def call_axon(messages, turn_name):
    print(f"\\n➡️ Sending Turn: {turn_name}...")
    start = time.time()
    
    # We use raw requests to easily capture the headers
    import requests
    response = requests.post(
        "http://localhost:8080/v1/chat/completions",
        headers={
            "Authorization": "Bearer sk-axon",
            "X-Axon-Session-ID": SESSION_ID,
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o",
            "messages": messages,
            "tools": TOOLS
        }
    )
    
    elapsed = time.time() - start
    
    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        return None
        
    metrics = json.loads(response.headers.get("x-axon-metrics", "{}"))
    agentic_tokens_saved = metrics.get("agentic_tokens_saved", 0)
    agentic_breakdown = metrics.get("agentic_breakdown", {})
    
    print(f"✅ Received response in {elapsed:.2f}s")
    print(f"💡 Total Tokens Saved: {metrics.get('tokens_saved', 0)} ({metrics.get('savings_pct', 0):.1f}%)")
    if agentic_tokens_saved > 0:
        print(f"🤖 Agentic Pass Savings: {agentic_tokens_saved} tokens")
        for module, saved in agentic_breakdown.items():
            if saved > 0:
                print(f"   - {module.replace('_', ' ').title()}: {saved} tokens")
                
    if response.headers.get("x-axon-cache") == "HIT":
        print("⚡ Served from Cache (Loop Detected or Identical Request)")
        
    return response.json()

def run_simulation():
    # ── The Simulated Conversation ────────────────────────────────────────────────

    messages = [
        {
            "role": "system",
            "content": "You are an autonomous AI coding agent. You must use tools to achieve the user's goal. Always think step by step before acting." + ("\n" * 10) # Testing whitespace normalizer
        },
        {
            "role": "user",
            "content": "Look up the latest stock price for AAPL and then write a python script to calculate a 30 day moving average."
        }
    ]

    # ── TURN 1: Setup & Verbose Reasoning ─────────────────────────────────────────
    # Agent thinks with a lot of filler, calls search_web

    agent_thinking_1 = """<thinking>
Okay, I need to look up the latest stock price for AAPL.
To do this, I will use the search_web tool because I need real-time information.
The search_web tool allows me to search the internet.
I will set the query to "AAPL stock price today".
This seems like the best approach.
</thinking>"""

    messages.append({
        "role": "assistant",
        "content": agent_thinking_1,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "search_web", "arguments": '{"query": "AAPL stock price today"}'}
            }
        ]
    })

    res1 = call_axon(messages, "Turn 1 - Initial Reasoning")

    # ── TURN 2: Massive Context & Error Truncation ────────────────────────────────
    # We return a massive web snippet. The agent then writes code, but we simulate a huge python stack trace.

    messages.append({
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "AAPL stock price is $150.23. " + ("The market is volatile. " * 500)  # Massive text blob (testing observation window later)
    })

    agent_thinking_2 = """<thinking>
I have the stock price. It is $150.23.
Now I need to write a python script to calculate the moving average.
I will use the execute_python tool.
</thinking>"""

    messages.append({
        "role": "assistant",
        "content": agent_thinking_2,
        "tool_calls": [
            {
                "id": "call_2",
                "type": "function",
                "function": {"name": "execute_python", "arguments": '{"code": "print(150.23 / 0)"}'}
            }
        ]
    })

    # We simulate a massive stack trace from the execute_python tool
    massive_stack_trace = """Traceback (most recent call last):
  File "/usr/local/lib/python3.10/site-packages/pandas/core/algorithms.py", line 123, in <module>
    df = pd.read_csv('data.csv')
  File "/usr/local/lib/python3.10/site-packages/pandas/io/parsers/readers.py", line 912, in read_csv
    return _read(filepath_or_buffer, kwds)
  File "/usr/local/lib/python3.10/site-packages/pandas/io/parsers/readers.py", line 577, in _read
    parser = TextFileReader(filepath_or_buffer, **kwds)
  File "/usr/local/lib/python3.10/site-packages/pandas/io/parsers/readers.py", line 1407, in __init__
    self._engine = self._make_engine(f, self.engine)
  File "/usr/local/lib/python3.10/site-packages/pandas/io/parsers/readers.py", line 1661, in _make_engine
    self.handles = get_handle(
  File "/usr/local/lib/python3.10/site-packages/pandas/io/common.py", line 859, in get_handle
    handle = open(
ZeroDivisionError: division by zero
"""

    messages.append({
        "role": "tool",
        "tool_call_id": "call_2",
        "content": massive_stack_trace
    })

    res2 = call_axon(messages, "Turn 2 - Executing Code (Triggers Error Truncator)")


    # ── TURN 3: Infinite Loop Detection ───────────────────────────────────────────
    # The agent tries the EXACT SAME CODE again (a common agent loop failure mode)

    agent_thinking_3 = """<thinking>
Oh, it failed with a ZeroDivisionError.
I will try to run the exact same code again and see if it works this time.
</thinking>"""

    messages.append({
        "role": "assistant",
        "content": agent_thinking_3,
        "tool_calls": [
            {
                "id": "call_3",
                "type": "function",
                "function": {"name": "execute_python", "arguments": '{"code": "print(150.23 / 0)"}'}
            }
        ]
    })

    res3 = call_axon(messages, "Turn 3 - Infinite Loop Test")

    # ── TURN 4: Schema Differential & Window Pruning ──────────────────────────────
    # The agent finally fixes it. Schema diff and Observation Window should heavily compress this.

    messages.append({
        "role": "tool",
        "tool_call_id": "call_3",
        "content": "[AXON LOOP GUARD] You called this tool with the exact same arguments but it failed last time. Breaking loop."
    })

    messages.append({
        "role": "assistant",
        "content": "I fixed the bug. The moving average is calculated correctly.",
    })

    res4 = call_axon(messages, "Turn 4 - Resolution (Triggers Schema Diff & Pruning)")

    print("\n" + "=" * 80)
    print("🎉 Agentic Workflow Test Complete!")

if __name__ == "__main__":
    run_simulation()

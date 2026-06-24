#!/bin/bash

echo "=========================================="
echo " Starting Axon Real-World Integration Demo"
echo "=========================================="

# Ensure we are in the project root
cd "$(dirname "$0")/../../"

# 1. Start the Axon Bridge server in the background
echo "[Bash] Starting Axon Bridge (uvicorn app:app)..."
./.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!

# Wait for server to boot
echo "[Bash] Waiting 3 seconds for server to initialize..."
sleep 3

# 2. Run the real-world agent script
echo -e "\n[Bash] Executing agent.py..."
./.venv/bin/python examples/real_world_agent/agent.py

# 3. Cleanup
echo -e "\n[Bash] Shutting down Axon Bridge server (PID: $SERVER_PID)..."
kill $SERVER_PID
echo "[Bash] Demo complete!"

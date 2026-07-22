"""Proper real-world benchmark using actual Axon optimizer interface."""
import json, sys, os, uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import tiktoken
from axon.services.token_optimizer import TokenOptimizer
from axon.services.tool_compressor import compress_tools_to_prompt
from axon.services.agentic.pipeline import optimize_request

enc = tiktoken.get_encoding("cl100k_base")
opt = TokenOptimizer()

def tok(text): return len(enc.encode(str(text)))

def sep(title):
    print(f"\n{'='*68}\n  {title}\n{'='*68}")

results = []

# ── Inspect what the optimizer returns ──
sep("Inspecting TokenOptimizer result fields")
sample = [{"id": i, "name": f"item-{i}", "value": i * 10} for i in range(5)]
r = opt.optimize(sample, session_id="inspect-1", model="gpt-4o")
winner = r.winner
print(f"Winner type: {type(winner)}")
print(f"Winner attrs: {[a for a in dir(winner) if not a.startswith('_')]}")
print(f"json_baseline_tokens: {r.json_baseline_tokens}")
print(f"all_results count: {len(r.all_results)}")
if r.all_results:
    print(f"Sample result attrs: {[a for a in dir(r.all_results[0]) if not a.startswith('_')]}")

sep("STRUCTURAL JSON COMPRESSION — Typical Payloads")

payloads = [
    ("GitHub repos (20 items)",
     [{"id": 100+i, "name": f"project-{i}", "full_name": f"org/project-{i}",
       "language": "Python", "stargazers_count": i*10, "forks_count": i*2,
       "open_issues_count": i, "private": False, "archived": False,
       "updated_at": "2026-07-20T10:00:00Z", "topics": ["api", "python"],
       "license": {"key": "mit", "name": "MIT License"}} for i in range(20)]),
    ("AWS EC2 instances (10)",
     [{"InstanceId": f"i-abc{i:04d}", "InstanceType": "t3.micro",
       "State": {"Code": 16, "Name": "running"},
       "PrivateDnsName": f"ip-10-0-1-{i}.ec2.internal",
       "Tags": [{"Key": "Environment", "Value": "Production"}, {"Key": "Owner", "Value": "TeamA"}],
       "LaunchTime": "2026-07-01T08:00:00Z", "Placement": {"AvailabilityZone": "us-east-1a"}} for i in range(10)]),
    ("User list from DB (30 users)",
     [{"id": i, "email": f"user{i}@example.com", "name": f"User {i}",
       "status": "active", "created_at": "2026-01-01T00:00:00Z",
       "plan": "pro", "role": "member"} for i in range(30)]),
    ("Prometheus metrics (15 series)",
     [{"metric": f"service_{i}_latency_p95_ms", "value": 50 + i*3,
       "labels": {"env": "prod", "region": "us-east-1", "service": f"svc-{i}"},
       "timestamp": 1753171200 + i*60} for i in range(15)]),
]

json_results = []
for name, data in payloads:
    orig_text = json.dumps(data, indent=2)
    orig_tok = tok(orig_text)
    result = opt.optimize(data, session_id=f"bench-{name}", model="gpt-4o")
    baseline = result.json_baseline_tokens
    # Use the baseline as "before" since that's what the raw JSON would cost
    # Winner is the best compression found
    winner_encoded = result.winner
    # Get the encoded text from winner
    # The winner strategy is what was chosen; we want its token count
    # Check all_results for the winner's token count
    winner_tokens = None
    winner_strategy = None
    for sr in result.all_results:
        attrs = [a for a in dir(sr) if not a.startswith('_')]
        break

    print(f"\n  {name}")
    print(f"    attrs: {attrs}")
    break


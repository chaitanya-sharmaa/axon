#!/usr/bin/env python3
"""Live demo: GCF Token Bridge — auto-format selection, TOON/TRON, multi-agent.

Shows all core capabilities of the bridge against a running server.

Usage
-----
  # Start the server in one terminal (from workspace root):
  python3 -m uvicorn gcf_fastapi:app --host 127.0.0.1 --port 8080

  # Run this demo in another terminal:
  cd /Users/chasharm4/Documents/gcf
  python3 bridge/examples/demo_usage.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "http://127.0.0.1:8080"
DIVIDER = "\n" + "─" * 60


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def post(path: str, body: Any) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=10) as resp:
        return json.loads(resp.read())


# ── Formatting helpers ─────────────────────────────────────────────────────────

def section(title: str) -> None:
    print(f"{DIVIDER}\n  {title}{DIVIDER}")


def print_metrics(metrics: dict) -> None:
    print(f"  Winner   : {metrics['strategy_used']}")
    print(f"  Savings  : {metrics['estimated_savings_percent']:+.1f}%  "
          f"({metrics['estimated_json_tokens']}t → {metrics['estimated_optimized_tokens']}t)")
    print("  All formats:")
    for name, info in metrics["format_comparison"].items():
        marker = " ◀ winner" if name == metrics["strategy_used"] else ""
        print(f"    {name:<28} {info['tokens']:>4}t  ({info['savings_pct']:+.1f}%){marker}")


# ── Demo sections ──────────────────────────────────────────────────────────────

def demo_health() -> None:
    section("1. Health check")
    r = get("/health")
    print(f"  Status: {r['status']}")


def demo_generic_first_turn() -> None:
    section("2. Generic payload — turn 1  (no session yet, full payload)")
    r = post("/process", {
        "inbound": {
            "user": "alice", "role": "admin", "org": "acme",
            "plan": "enterprise", "region": "us-east-1",
        },
        "handler": "echo",
        "session_id": "demo-generic",
    })
    print_metrics(r["metrics"])
    print(f"\n  Encoded:\n  {r['encoded'].strip()}")


def demo_tron_generic() -> None:
    section("3. Generic payload — turn 2, same data  [TRON: repeated-value dedup]")
    r = post("/process", {
        "inbound": {
            "user": "alice", "role": "admin", "org": "acme",
            "plan": "enterprise", "region": "us-east-1",
        },
        "handler": "echo",
        "session_id": "demo-generic",
    })
    print_metrics(r["metrics"])
    print(f"\n  Encoded:\n  {r['encoded'].strip()}")


def demo_toon_generic() -> None:
    section("4. Generic payload — turn 3, one field changed  [TOON: delta only]")
    r = post("/process", {
        "inbound": {
            "user": "alice", "role": "admin", "org": "acme",
            "plan": "enterprise", "region": "eu-west-2",    # ← only this changed
        },
        "handler": "echo",
        "session_id": "demo-generic",
    })
    print_metrics(r["metrics"])
    print(f"\n  Encoded (only the changed field is sent to LLM):\n  {r['encoded'].strip()}")


def demo_graph_first_turn() -> None:
    section("5. Graph payload (code context) — turn 1  [GCF graph wins]")
    r = post("/process", {
        "inbound": {
            "symbols": [
                {"qualified_name": "pkg.Auth",   "kind": "class",    "score": 0.95, "provenance": "lsp", "distance": 0},
                {"qualified_name": "pkg.Server", "kind": "function", "score": 0.61, "provenance": "lsp", "distance": 1},
                {"qualified_name": "pkg.Config", "kind": "type",     "score": 0.71, "provenance": "ast", "distance": 1},
            ],
            "edges": [
                {"source": "pkg.Server", "target": "pkg.Auth",   "edge_type": "calls"},
                {"source": "pkg.Auth",   "target": "pkg.Config", "edge_type": "references"},
            ],
            "token_budget": 5000, "tokens_used": 1200,
        },
        "handler": "graph_processor",
        "session_id": "demo-graph",
    })
    print_metrics(r["metrics"])


def demo_graph_delta() -> None:
    section("6. Graph payload — turn 2, one new symbol added  [TOON/gcf_delta wins]")
    r = post("/process", {
        "inbound": {
            "symbols": [
                {"qualified_name": "pkg.Auth",   "kind": "class",    "score": 0.95, "provenance": "lsp", "distance": 0},
                {"qualified_name": "pkg.Server", "kind": "function", "score": 0.61, "provenance": "lsp", "distance": 1},
                {"qualified_name": "pkg.Config", "kind": "type",     "score": 0.71, "provenance": "ast", "distance": 1},
                {"qualified_name": "pkg.Logger", "kind": "class",    "score": 0.50, "provenance": "ast", "distance": 2},  # ← new
            ],
            "edges": [
                {"source": "pkg.Server", "target": "pkg.Auth",   "edge_type": "calls"},
                {"source": "pkg.Auth",   "target": "pkg.Config", "edge_type": "references"},
                {"source": "pkg.Logger", "target": "pkg.Server", "edge_type": "calls"},  # ← new
            ],
            "token_budget": 5000, "tokens_used": 1400,
        },
        "handler": "graph_processor",
        "session_id": "demo-graph",
    })
    print_metrics(r["metrics"])


def demo_active_items() -> None:
    section("7. active_items handler — filter and summarise a list")
    r = post("/process", {
        "inbound": {
            "items": [
                {"id": 1, "name": "Task A", "status": "active"},
                {"id": 2, "name": "Task B", "status": "inactive"},
                {"id": 3, "name": "Task C", "status": "active"},
                {"id": 4, "name": "Task D", "status": "pending"},
            ],
        },
        "handler": "active_items",
    })
    print(f"  Handler result  : {json.dumps(r['handler_result'])}")
    print_metrics(r["metrics"])


def demo_agent_dispatch() -> None:
    section("8. Agent dispatch — route to best agent by capability")
    agents = get("/agent/list")
    print(f"  Registered agents: {[a['name'] for a in agents['agents']]}\n")
    r = post("/agent/dispatch", {
        "payload": {
            "symbols": [
                {"qualified_name": "api.Handler", "kind": "class", "score": 0.9, "provenance": "lsp", "distance": 0},
            ],
            "edges": [],
        },
        "capability": "graph",
        "session_id": "demo-agent",
    })
    print(f"  Routed to : {r['agent']}")
    print(f"  Strategy  : {r['strategy_used']}  ({r['token_savings_pct']:+.1f}%)")


def demo_agent_swarm() -> None:
    section("9. Agent swarm — fan-out to ALL agents in parallel")
    r = post("/agent/swarm", {
        "payload": {"items": [{"id": 1, "status": "active"}, {"id": 2, "status": "inactive"}]},
        "session_id": "demo-swarm",
    })
    print(f"  Agents ran : {r['succeeded']} succeeded / {r['failed']} failed  ({r['total_latency_ms']} ms total)")
    for res in r["results"]:
        print(f"    [{res['agent']:<24}]  strategy={res['strategy_used']}  savings={res['token_savings_pct']:+.1f}%")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n  GCF Token Bridge — Live Demo")
    print("  Auto-format selection  |  TOON (delta)  |  TRON (session)  |  Multi-agent")

    try:
        get("/health")
    except (urllib.error.URLError, ConnectionRefusedError):
        print(f"\n  ERROR: Server not reachable at {BASE_URL}")
        print("  Start it first:\n    python3 -m uvicorn gcf_fastapi:app --host 127.0.0.1 --port 8080")
        sys.exit(1)

    demo_health()
    demo_generic_first_turn()
    demo_tron_generic()
    demo_toon_generic()
    demo_graph_first_turn()
    demo_graph_delta()
    demo_active_items()
    demo_agent_dispatch()
    demo_agent_swarm()

    print(f"{DIVIDER}\n  Demo complete.\n")


if __name__ == "__main__":
    main()


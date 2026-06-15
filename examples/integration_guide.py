#!/usr/bin/env python3
"""
GCF Token Bridge — Setup & Integration Guide
=============================================

Run this file to validate your setup and see worked integration examples.

  python3 bridge/examples/integration_guide.py

Requirements
------------
  pip install gcf-python fastapi uvicorn

Start the server (separate terminal)
-------------------------------------
  cd /path/to/gcf
  python3 -m uvicorn gcf_fastapi:app --host 127.0.0.1 --port 8080

Environment variables (all optional, sensible defaults)
---------------------------------------------------------
  GCF_HOST                 Server bind host          (default: 127.0.0.1)
  GCF_PORT                 Server bind port          (default: 8080)
  GCF_ENABLED_FORMATS      Comma-separated strategy list
                             choices: gcf_graph, gcf_session, gcf_delta,
                                      gcf_generic, gcf_generic_delta,
                                      gcf_generic_session, json
                             default: all of the above
  GCF_MEMORY_DB_PATH       SQLite file for session memory  (default: /tmp/gcf_sessions.db)
  GCF_API_KEY              Bearer token for proxy auth     (default: disabled)
  GCF_REQUIRE_API_KEY      Enforce API key on proxy        (default: false)
  GCF_ALLOW_ALL_DOMAINS    Skip domain allowlist           (default: false)
  GCF_ALLOWED_DOMAINS      Comma-separated proxy allowlist
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any

BASE = "http://127.0.0.1:8080"


def post(path: str, body: Any) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return json.loads(r.read())


def pp(label: str, d: Any) -> None:
    print(f"\n{'─'*55}")
    print(f"  {label}")
    print(f"{'─'*55}")
    print(json.dumps(d, indent=2))


# ══════════════════════════════════════════════════════════
# SECTION 1 — Health & discovery
# ══════════════════════════════════════════════════════════

def section_health():
    print("\n\n╔══════════════════════════════════════════════════════╗")
    print("║  SECTION 1: Health & discovery                       ║")
    print("╚══════════════════════════════════════════════════════╝")

    pp("GET /health", get("/health"))
    pp("GET /agent/list", get("/agent/list"))


# ══════════════════════════════════════════════════════════
# SECTION 2 — Generic payload encoding
# ══════════════════════════════════════════════════════════

def section_generic():
    print("\n\n╔══════════════════════════════════════════════════════╗")
    print("║  SECTION 2: Generic payload — TOON / TRON            ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("""
  Any dict / list payload goes through these strategies:
    gcf_generic         — compact key=value encoding (always runs)
    gcf_generic_delta   — TOON: only changed keys vs previous turn
    gcf_generic_session — TRON: replaces repeated scalar values with refs

  The cheapest one for this payload wins automatically.
""")

    payload = {
        "user": "alice", "role": "admin", "org": "acme",
        "plan": "enterprise", "region": "us-east-1",
    }
    session = "guide-generic"

    print("  Turn 1 — first call, full payload:")
    r1 = post("/process", {"inbound": payload, "handler": "echo", "session_id": session})
    m = r1["metrics"]
    print(f"    winner={m['strategy_used']}  savings={m['estimated_savings_percent']:+.1f}%")
    print(f"    encoded:\n{r1['encoded']}")

    print("  Turn 2 — same payload, one field changed (region):")
    payload2 = {**payload, "region": "ap-southeast-1"}
    r2 = post("/process", {"inbound": payload2, "handler": "echo", "session_id": session})
    m = r2["metrics"]
    print(f"    winner={m['strategy_used']}  savings={m['estimated_savings_percent']:+.1f}%")
    print(f"    encoded:\n{r2['encoded']}")
    print("  ↑ Only the changed field was sent — TOON delta saved tokens")


# ══════════════════════════════════════════════════════════
# SECTION 3 — Graph payload encoding (code context)
# ══════════════════════════════════════════════════════════

def section_graph():
    print("\n\n╔══════════════════════════════════════════════════════╗")
    print("║  SECTION 3: Graph payload — GCF / TOON / TRON        ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("""
  Graph payloads must contain a "symbols" list.
  Additional strategies available vs generic:
    gcf_graph   — GCF graph profile with symbol/edge deduplication
    gcf_delta   — TOON for graphs: only added/removed symbols+edges
    gcf_session — TRON for graphs: session-aware symbol elision
""")

    session = "guide-graph"

    base_symbols = [
        {"qualified_name": "pkg.Auth",   "kind": "class",    "score": 0.95, "provenance": "lsp", "distance": 0},
        {"qualified_name": "pkg.Server", "kind": "function", "score": 0.61, "provenance": "lsp", "distance": 1},
        {"qualified_name": "pkg.Config", "kind": "type",     "score": 0.71, "provenance": "ast", "distance": 1},
    ]
    base_edges = [
        {"source": "pkg.Server", "target": "pkg.Auth",   "edge_type": "calls"},
        {"source": "pkg.Auth",   "target": "pkg.Config", "edge_type": "references"},
    ]

    print("  Turn 1 — 3 symbols, 2 edges:")
    r1 = post("/process", {
        "inbound": {"symbols": base_symbols, "edges": base_edges, "token_budget": 5000, "tokens_used": 1200},
        "handler": "graph_processor",
        "session_id": session,
    })
    m = r1["metrics"]
    for name, v in m["format_comparison"].items():
        marker = " ◀" if name == m["strategy_used"] else ""
        print(f"    {name:<28} {v['tokens']:>4}t  ({v['savings_pct']:+.1f}%){marker}")

    print(f"\n  Turn 2 — 4 symbols, 3 edges (one new each):")
    r2 = post("/process", {
        "inbound": {
            "symbols": base_symbols + [
                {"qualified_name": "pkg.Logger", "kind": "class", "score": 0.50, "provenance": "ast", "distance": 2},
            ],
            "edges": base_edges + [
                {"source": "pkg.Logger", "target": "pkg.Server", "edge_type": "calls"},
            ],
            "token_budget": 5000, "tokens_used": 1400,
        },
        "handler": "graph_processor",
        "session_id": session,
    })
    m = r2["metrics"]
    for name, v in m["format_comparison"].items():
        marker = " ◀" if name == m["strategy_used"] else ""
        print(f"    {name:<28} {v['tokens']:>4}t  ({v['savings_pct']:+.1f}%){marker}")
    print(f"\n  Winner: {m['strategy_used']}  —  {m['estimated_savings_percent']:+.1f}% savings on turn 2")


# ══════════════════════════════════════════════════════════
# SECTION 4 — Multi-agent layer
# ══════════════════════════════════════════════════════════

def section_agents():
    print("\n\n╔══════════════════════════════════════════════════════╗")
    print("║  SECTION 4: Multi-agent dispatch & swarm             ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("""
  Agents are registered workers with declared capabilities.
  POST /agent/dispatch  — route to the best agent for a capability
  POST /agent/parallel  — dispatch to multiple capabilities concurrently
  POST /agent/swarm     — fan-out to ALL registered agents in parallel
""")

    # Dispatch by capability
    print("  Dispatch by capability='graph':")
    r = post("/agent/dispatch", {
        "payload": {
            "symbols": [{"qualified_name": "svc.Auth", "kind": "class", "score": 0.9, "provenance": "lsp", "distance": 0}],
            "edges": [],
        },
        "capability": "graph",
        "session_id": "guide-dispatch",
    })
    print(f"    → routed to '{r['agent']}'  strategy={r['strategy_used']}  savings={r['token_savings_pct']:+.1f}%")

    # Parallel dispatch: two capabilities at once
    print("\n  Parallel dispatch: ['graph', 'active_items'] simultaneously:")
    r = post("/agent/parallel", {
        "payload": {"items": [{"id": 1, "status": "active"}, {"id": 2, "status": "inactive"}]},
        "capabilities": ["graph", "active_items"],
        "session_id": "guide-parallel",
    })
    print(f"    → {r['succeeded']} succeeded / {r['failed']} failed in {r['total_latency_ms']} ms")
    for res in r["results"]:
        print(f"      [{res['agent']:<22}]  ok={res['success']}  strategy={res['strategy_used']}")

    # Swarm
    print("\n  Swarm (all agents):")
    r = post("/agent/swarm", {
        "payload": {"items": [{"id": 1, "status": "active"}]},
        "session_id": "guide-swarm",
    })
    print(f"    → {r['succeeded']} agents / {r['total_latency_ms']} ms wall time")
    for res in r["results"]:
        print(f"      [{res['agent']:<22}]  strategy={res['strategy_used']}  savings={res['token_savings_pct']:+.1f}%")


# ══════════════════════════════════════════════════════════
# SECTION 5 — Session memory
# ══════════════════════════════════════════════════════════

def section_memory():
    print("\n\n╔══════════════════════════════════════════════════════╗")
    print("║  SECTION 5: Session memory (SQLite)                  ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("""
  Every /process call with a session_id is logged to SQLite.
  GET /memory/sessions            — list all sessions
  GET /memory/session/{id}        — get history for a session
  DELETE /memory/session/{id}     — delete a session
  DELETE /memory/cleanup          — purge sessions older than N days
""")

    # Create a session via process
    post("/process", {"inbound": {"x": 1}, "handler": "echo", "session_id": "guide-mem"})
    post("/process", {"inbound": {"x": 2}, "handler": "echo", "session_id": "guide-mem"})

    sessions = get("/memory/sessions")
    print(f"  Active sessions: {[s.get('session_id') for s in sessions.get('sessions', [])]}")

    history = get("/memory/session/guide-mem")
    print(f"  Events in 'guide-mem': {len(history.get('events', []))}")


# ══════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════

def main():
    print("GCF Token Bridge — Setup & Integration Guide")
    print("============================================")

    try:
        get("/health")
    except (urllib.error.URLError, ConnectionRefusedError):
        print(f"\nERROR: Server not reachable at {BASE}")
        print("Start it first:\n  python3 -m uvicorn gcf_fastapi:app --host 127.0.0.1 --port 8080")
        sys.exit(1)

    section_health()
    section_generic()
    section_graph()
    section_agents()
    section_memory()

    print("\n\n  All sections passed. Integration guide complete.\n")


if __name__ == "__main__":
    main()

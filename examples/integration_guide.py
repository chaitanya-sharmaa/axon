#!/usr/bin/env python3
"""
Axon Token Bridge — Setup & Integration Guide
=============================================

This script validates a running Axon server and demonstrates its core features
through a series of API calls.

Requirements
------------
  pip install -r requirements.txt

Start the server (separate terminal)
-------------------------------------
  python3 -m uvicorn app:app --host 127.0.0.1 --port 8080
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
        f"{BASE}{path}", data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as resp:
        return json.loads(resp.read())


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

    pp("GET /health/live", get("/health/live"))
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
    generic           — compact key=value encoding (always runs)
    generic_delta     — TOON: only changed keys vs previous turn
    generic_session   — TRON: replaces repeated scalar values with refs

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
    print(f"    encoded:\n{r1['compact_text']}")

    print("  Turn 2 — same payload, one field changed (region):")
    payload2 = {**payload, "region": "ap-southeast-1"}
    r2 = post("/process", {"inbound": payload2, "handler": "echo", "session_id": session})
    m = r2["metrics"]
    print(f"    winner={m['strategy_used']}  savings={m['estimated_savings_percent']:+.1f}%")
    print(f"    encoded:\n{r2['compact_text']}")
    print("  ↑ Only the changed field was sent — TOON delta saved tokens")


# ══════════════════════════════════════════════════════════
# SECTION 3 — Graph payload encoding (code context)
# ══════════════════════════════════════════════════════════

def section_graph():
    print("\n\n╔══════════════════════════════════════════════════════╗")
    print("║  SECTION 3: Graph payload — Compact / TOON / TRON    ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("""
  Graph payloads must contain a "symbols" list.
  Additional strategies available vs generic:
    graph         — Compact graph profile with symbol/edge deduplication
    graph_delta   — TOON for graphs: only added/removed symbols+edges
    graph_session — TRON for graphs: session-aware symbol elision
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

    print("\n  Turn 2 — 4 symbols, 3 edges (one new each):")
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
# SECTION 6 — Wrapping an External API (Proxy)
# ══════════════════════════════════════════════════════════

def section_proxy():
    print("\n\n╔══════════════════════════════════════════════════════╗")
    print("║  SECTION 6: Wrapping an External API (Proxy)         ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("""
  The easiest way to get started.
  POST /proxy/upstream to call any external API. The bridge fetches the
  response and automatically encodes it into the most token-efficient format.
  No code changes needed for your existing API.
""")

    # We'll use httpbin.org as our "external API"
    proxy_request = {
        "upstream_url": "https://httpbin.org/json",
        "method": "GET",
        "session_id": "guide-proxy",
    }

    print("  Calling external API via /proxy/upstream:")
    r = post("/proxy/upstream", proxy_request)

    print(f"    → Upstream responded with status {r['upstream']['status']}")
    m = r["metrics"]
    print(f"    → Bridge encoded response with '{m['strategy_used']}'")
    print(f"    → Savings: {m['estimated_savings_percent']:+.1f}% ({m['estimated_json_tokens']}t → {m['estimated_optimized_tokens']}t)")
    print(f"    → Compact text for LLM:\n{r['compact_text']}")


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
    print(f"  Active sessions: {[s.get('session_id') for s in sessions.get('sessions', [])] if sessions.get('sessions') else 'None'}")

    history = get("/memory/session/guide-mem")
    print(f"  Events in 'guide-mem': {len(history.get('events', []))}")


# ══════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════

def main():
    print("Axon Token Bridge — Setup & Integration Guide")
    print("============================================")

    try:
        get("/health/live")
    except urllib.error.URLError:
        print(f"\nERROR: Server not reachable at {BASE}")
        print("Start it first from the project root:\n  axon serve  (or: uvicorn app:app --host 127.0.0.1 --port 8080)")
        sys.exit(1)

    section_health()
    section_generic()
    section_graph()
    section_agents()
    section_memory()
    section_proxy()

    print("\n\n  All sections passed. Integration guide complete.\n")


if __name__ == "__main__":
    main()

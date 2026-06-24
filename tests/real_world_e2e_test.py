"""
Real-world E2E test for Axon Bridge: structural compression + Gemini prompt caching.

Architecture:
  1. Starts Axon as a real subprocess on port 8082
  2. Makes real HTTP calls via httpx with explicit 300s timeout
  3. 5-turn multi-turn conversation with 100 nested products
  4. Verifies every answer against deterministic ground truth (anti-hallucination)

Run:
    .venv/bin/python tests/real_world_e2e_test.py
"""

import json
import os
import signal
import subprocess
import sys
import time
import uuid

import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY  = os.getenv("OPENAI_API_KEY", "")
MODEL    = "gemini/gemini-2.5-flash"
PORT     = 8082
BASE_URL = f"http://127.0.0.1:{PORT}"
SESSION_ID = f"e2e-{uuid.uuid4().hex[:8]}"


# ── Generate deterministic catalog ───────────────────────────────────────────

def build_catalog(n: int = 100) -> list[dict]:
    catalog = []
    for i in range(n):
        catalog.append({
            "product_id": f"SKU-{1000 + i}",
            "name": f"Quantum Resonance Module v{i}",
            "category": "Electronics" if i % 3 == 0 else ("Optics" if i % 3 == 1 else "Mechanics"),
            "price": round(100.0 + (i * 7.5), 2),
            "stock": (i * 3) % 50 + 1,
            "rating": round(3.0 + (i % 20) * 0.1, 1),
            "in_stock": i % 7 != 0,
            "description": (
                "A precision-engineered component for high-frequency quantum applications. "
                "Manufactured to ISO-9001 standards. Compatible with all Mk-IV chassis."
            ),
            "specifications": {
                "weight_kg": round(0.5 + i * 0.02, 2),
                "dimensions_mm": {"width": 80 + (i % 10), "height": 120, "depth": 40},
                "material": "Tungsten-carbide composite",
                "power_watts": 5 + (i % 15),
                "warranty_years": 3 if i % 5 == 0 else 1,
            },
            "reviews": [
                {"user": f"user_{i}a", "rating": 5, "text": "Excellent build quality."},
                {"user": f"user_{i}b", "rating": 4, "text": "Works as described."},
            ],
        })
    return catalog


CATALOG = build_catalog(100)

# Inject needle at index 33
CATALOG[33]["alert"] = "CRITICAL_SHORTAGE"
CATALOG_JSON = json.dumps(CATALOG)

# Ground truth
MOST_EXPENSIVE_ID    = "SKU-1099"
MOST_EXPENSIVE_PRICE = round(100.0 + 99 * 7.5, 2)   # 842.5
CHEAPEST_ID          = "SKU-1000"
CHEAPEST_PRICE       = 100.0
ELECTRONICS_COUNT    = sum(1 for i in range(100) if i % 3 == 0)   # 34
OUT_OF_STOCK_COUNT   = sum(1 for i in range(100) if i % 7 == 0)   # 15
NEEDLE_SKU           = "SKU-1033"

TURNS = [
    {
        "q": (
            "What is the product_id and price of the MOST EXPENSIVE item? "
            'Reply ONLY with raw JSON: {"product_id": "...", "price": <number>}'
        ),
        "verify": lambda a: MOST_EXPENSIVE_ID in a and str(MOST_EXPENSIVE_PRICE) in a,
        "truth":  f"product_id={MOST_EXPENSIVE_ID}, price={MOST_EXPENSIVE_PRICE}",
    },
    {
        "q": (
            "How many products are in the 'Electronics' category? "
            'Reply ONLY with raw JSON: {"electronics_count": <number>}'
        ),
        "verify": lambda a: str(ELECTRONICS_COUNT) in a,
        "truth":  f"electronics_count={ELECTRONICS_COUNT}",
    },
    {
        "q": (
            "One product has a field 'alert' set to 'CRITICAL_SHORTAGE'. "
            'What is its product_id? Reply ONLY with raw JSON: {"alert_product_id": "..."}'
        ),
        "verify": lambda a: NEEDLE_SKU in a,
        "truth":  f"alert_product_id={NEEDLE_SKU}",
    },
    {
        "q": (
            "What is the product_id and price of the CHEAPEST item? "
            'Reply ONLY with raw JSON: {"product_id": "...", "price": <number>}'
        ),
        "verify": lambda a: CHEAPEST_ID in a and str(int(CHEAPEST_PRICE)) in a,
        "truth":  f"product_id={CHEAPEST_ID}, price={CHEAPEST_PRICE}",
    },
    {
        "q": (
            "How many products have 'in_stock' set to false? "
            'Reply ONLY with raw JSON: {"out_of_stock_count": <number>}'
        ),
        "verify": lambda a: str(OUT_OF_STOCK_COUNT) in a,
        "truth":  f"out_of_stock_count={OUT_OF_STOCK_COUNT}",
    },
]


# ── Server management ─────────────────────────────────────────────────────────

def start_server() -> subprocess.Popen:
    env = {**os.environ, "AXON_PORT": str(PORT), "AXON_LOG_LEVEL": "WARNING"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def wait_for_server(timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BASE_URL}/health/live", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


# ── Main test ─────────────────────────────────────────────────────────────────

SEP  = "─" * 70
SEP2 = "═" * 70

def run():
    print(SEP2)
    print("🚀  AXON BRIDGE — REAL-WORLD E2E TEST")
    print(f"    Model      : {MODEL}")
    print(f"    Catalog    : {len(CATALOG)} items, {len(CATALOG_JSON):,} chars")
    print(f"    Session ID : {SESSION_ID}")
    print(SEP2)

    print("⏳  Starting Axon server on port", PORT, "...")
    server = start_server()
    if not wait_for_server(30):
        print("❌  Server failed to start.")
        server.kill()
        sys.exit(1)
    print("✅  Server ready.\n")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a precise data analyst. Answer ONLY using data from the catalog. "
                "Respond with ONLY a valid raw JSON object — no markdown, no explanation."
            ),
        },
        {"role": "user", "content": CATALOG_JSON},
    ]

    total_raw  = 0
    total_comp = 0
    all_passed = True

    try:
        with httpx.Client(timeout=300.0) as http:
            for idx, turn in enumerate(TURNS, 1):
                print(SEP)
                print(f"[Turn {idx}/{len(TURNS)}] {turn['q'][:90]}...")
                messages.append({"role": "user", "content": turn["q"]})

                req_body = {
                    "model": MODEL,
                    "messages": messages,
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"},
                }

                t0 = time.time()
                resp = http.post(
                    f"{BASE_URL}/v1/chat/completions",
                    json=req_body,
                    headers={
                        "Authorization": f"Bearer {API_KEY}",
                        "X-Axon-Session-ID": SESSION_ID,
                    },
                )
                latency = time.time() - t0

                if resp.status_code != 200:
                    print(f"  ❌  HTTP {resp.status_code}: {resp.text[:300]}")
                    all_passed = False
                    continue

                data   = resp.json()
                answer = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                messages.append({"role": "assistant", "content": answer})

                try:
                    m = json.loads(resp.headers.get("x-axon-metrics", "{}"))
                except Exception:
                    m = {}

                raw_tok  = m.get("original_tokens", 0)
                comp_tok = m.get("compressed_tokens", 0)
                sav_pct  = m.get("savings_pct", 0.0)
                cost_saved = resp.headers.get("x-axon-cost-saved-usd", "N/A")

                total_raw  += raw_tok
                total_comp += comp_tok

                passed = turn["verify"](answer)
                if not passed:
                    all_passed = False

                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"  Answer      : {answer[:120]}")
                print(f"  Expected    : {turn['truth']}")
                print(f"  Correctness : {status}")
                print(f"  Tokens      : {raw_tok:,} raw → {comp_tok:,} compressed  ({sav_pct:.1f}% saved)")
                print(f"  Cost saved  : ${cost_saved}   Latency: {latency:.2f}s")

                time.sleep(1)

    finally:
        server.send_signal(signal.SIGTERM)

    # Summary
    print()
    print(SEP2)
    print("📊  FINAL SUMMARY")
    print(SEP2)
    overall = (1 - total_comp / max(1, total_raw)) * 100
    print(f"  Total raw tokens       : {total_raw:,}")
    print(f"  Total compressed tokens: {total_comp:,}")
    print(f"  Overall savings        : {overall:.1f}%")
    print(f"  Tokens avoided         : {total_raw - total_comp:,}")
    print()
    if all_passed:
        print("  🎉  ALL {n} HALLUCINATION CHECKS PASSED — Context 100% intact".format(n=len(TURNS)))
    else:
        print("  ⚠️   SOME CHECKS FAILED — see details above")
    print(SEP2)


if __name__ == "__main__":
    run()

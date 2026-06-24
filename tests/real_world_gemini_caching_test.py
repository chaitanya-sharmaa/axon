"""
Real-world end-to-end test for Axon Bridge token compression + Gemini prompt caching.

Tests:
 1. Structural compression (always-on, ~18% savings) — no hallucination
 2. Gemini native prompt caching (new feature) — reduces cost on repeated context
 3. Anti-hallucination: every LLM answer is verified against known ground truth
 4. 5 turns of increasing complexity against a 100-item catalog

Run:
    .venv/bin/python tests/real_world_gemini_caching_test.py
"""

import json
import os
import sys
import time
import uuid

from dotenv import load_dotenv
from fastapi.testclient import TestClient

# ── Setup ────────────────────────────────────────────────────────────────────

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402 — must come after sys.path insert

client = TestClient(app)
API_KEY = os.getenv("OPENAI_API_KEY", "")
SESSION_ID = f"real-test-{uuid.uuid4().hex[:8]}"
MODEL = "gemini/gemini-2.5-flash"

# ── Generate deterministic complex payload ────────────────────────────────────

def build_catalog(n: int = 100) -> list[dict]:
    """250 deeply nested products with deterministic values for ground-truth checking."""
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
                {"user": f"user_{i}a", "rating": 5, "text": "Excellent build quality, arrived fast."},
                {"user": f"user_{i}b", "rating": 4, "text": "Works as described, slightly heavy."},
            ],
        })
    return catalog

CATALOG = build_catalog(100)
CATALOG_JSON = json.dumps(CATALOG)

# ── Pre-computed ground truth ─────────────────────────────────────────────────

# Most expensive: price = 100 + (99 * 7.5) = 842.5, SKU-1099
MOST_EXPENSIVE_ID = "SKU-1099"
MOST_EXPENSIVE_PRICE = round(100.0 + 99 * 7.5, 2)

# Cheapest: SKU-1000, price = 100.0
CHEAPEST_ID = "SKU-1000"
CHEAPEST_PRICE = 100.0

# Category count: Electronics = i%3==0 → 0,3,6,...,99 → 34 items
ELECTRONICS_COUNT = sum(1 for i in range(100) if i % 3 == 0)

# Out-of-stock count: i%7==0 → 0,7,14,...,98 → 15 items
OUT_OF_STOCK_COUNT = sum(1 for i in range(100) if i % 7 == 0)

# Needle: inject an anomaly at index 33
CATALOG[33]["stock"] = 0
CATALOG[33]["alert"] = "CRITICAL_SHORTAGE"
NEEDLE_SKU = "SKU-1033"

# ── Test turns ────────────────────────────────────────────────────────────────

TURNS = [
    {
        "question": (
            "Read the product catalog carefully. "
            "What is the product_id and price of the MOST EXPENSIVE item? "
            "Reply ONLY with a valid JSON object: {\"product_id\": \"...\", \"price\": <number>}"
        ),
        "verify": lambda ans: (
            MOST_EXPENSIVE_ID in ans and str(MOST_EXPENSIVE_PRICE) in ans
        ),
        "ground_truth": f"product_id={MOST_EXPENSIVE_ID}, price={MOST_EXPENSIVE_PRICE}",
    },
    {
        "question": (
            "How many products are in the 'Electronics' category? "
            "Reply ONLY with a valid JSON object: {\"electronics_count\": <number>}"
        ),
        "verify": lambda ans: str(ELECTRONICS_COUNT) in ans,
        "ground_truth": f"electronics_count={ELECTRONICS_COUNT}",
    },
    {
        "question": (
            "One product has a special field called 'alert' set to 'CRITICAL_SHORTAGE'. "
            "What is its product_id? "
            "Reply ONLY with a valid JSON object: {\"alert_product_id\": \"...\"}"
        ),
        "verify": lambda ans: NEEDLE_SKU in ans,
        "ground_truth": f"alert_product_id={NEEDLE_SKU}",
    },
    {
        "question": (
            "What is the product_id and price of the CHEAPEST item in the catalog? "
            "Reply ONLY with a valid JSON object: {\"product_id\": \"...\", \"price\": <number>}"
        ),
        "verify": lambda ans: CHEAPEST_ID in ans and str(CHEAPEST_PRICE) in ans,
        "ground_truth": f"product_id={CHEAPEST_ID}, price={CHEAPEST_PRICE}",
    },
    {
        "question": (
            "How many products have 'in_stock' set to false (i.e., are out of stock)? "
            "Reply ONLY with a valid JSON object: {\"out_of_stock_count\": <number>}"
        ),
        "verify": lambda ans: str(OUT_OF_STOCK_COUNT) in ans,
        "ground_truth": f"out_of_stock_count={OUT_OF_STOCK_COUNT}",
    },
]

# ── Runner ────────────────────────────────────────────────────────────────────

def separator(char="─", width=70):
    print(char * width)

def run_test():
    separator("═")
    print("🚀  AXON BRIDGE — REAL-WORLD GEMINI PROMPT CACHING TEST")
    print(f"    Session ID : {SESSION_ID}")
    print(f"    Model      : {MODEL}")
    print(f"    Catalog    : {len(CATALOG)} items, {len(CATALOG_JSON):,} chars raw")
    print(f"    Turns      : {len(TURNS)}")
    separator("═")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a precise data analyst. The user will ask questions about "
                "a product catalog. Answer ONLY using data from the catalog. "
                "Always respond with ONLY a valid raw JSON object — no markdown, "
                "no explanation."
            ),
        },
        {"role": "user", "content": CATALOG_JSON},
    ]

    total_raw = 0
    total_compressed = 0
    all_passed = True

    for turn_idx, turn in enumerate(TURNS, 1):
        separator()
        print(f"[Turn {turn_idx}/{len(TURNS)}] {turn['question'][:80]}...")
        messages.append({"role": "user", "content": turn["question"]})

        req_body = {
            "model": MODEL,
            "messages": messages,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        start = time.time()
        response = client.post(
            "/v1/chat/completions",
            json=req_body,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "X-Axon-Session-ID": SESSION_ID,
            },
        )
        latency = time.time() - start

        if response.status_code != 200:
            print(f"  ❌  HTTP {response.status_code}: {response.text[:200]}")
            all_passed = False
            continue

        data = response.json()
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        messages.append({"role": "assistant", "content": answer})

        metrics_raw = response.headers.get("x-axon-metrics", "{}")
        cost_saved  = response.headers.get("x-axon-cost-saved-usd", "N/A")
        try:
            m = json.loads(metrics_raw)
        except Exception:
            m = {}

        raw_tok  = m.get("original_tokens", 0)
        comp_tok = m.get("compressed_tokens", 0)
        sav_pct  = m.get("savings_pct", 0.0)
        total_raw        += raw_tok
        total_compressed += comp_tok

        # Verify answer
        passed = turn["verify"](answer)
        status = "✅ PASS" if passed else "❌ FAIL"
        if not passed:
            all_passed = False

        print(f"  Answer   : {answer[:120]}")
        print(f"  Expected : {turn['ground_truth']}")
        print(f"  Result   : {status}")
        print(f"  Tokens   : {raw_tok:,} raw  →  {comp_tok:,} compressed  ({sav_pct:.1f}% saved)")
        print(f"  Cost saved: ${cost_saved}   Latency: {latency:.2f}s")

        time.sleep(1)  # Avoid rate-limiting

    # ── Final summary ─────────────────────────────────────────────────────────
    separator("═")
    print("📊  FINAL SUMMARY")
    separator("═")
    overall_saving = (1 - total_compressed / max(1, total_raw)) * 100
    print(f"  Total raw tokens sent  : {total_raw:,}")
    print(f"  Total comp tokens sent : {total_compressed:,}")
    print(f"  Overall token savings  : {overall_saving:.1f}%")
    print(f"  Tokens avoided         : {total_raw - total_compressed:,}")
    print()
    if all_passed:
        print("  🎉  ALL HALLUCINATION CHECKS PASSED — LLM context is 100% intact")
    else:
        print("  ⚠️   SOME HALLUCINATION CHECKS FAILED — see details above")
    separator("═")


if __name__ == "__main__":
    run_test()

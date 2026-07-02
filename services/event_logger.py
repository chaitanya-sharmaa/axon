"""Centralized event logger for security & AI events.

Tracks: prompt firewall blocks, PII redaction hits, hallucination guard triggers.
All stored in bounded deques — no persistence, purely for the live dashboard.
"""
import time
from collections import deque
from typing import Any


class EventLogger:
    def __init__(self, maxlen: int = 200):
        self._firewall = deque(maxlen=maxlen)
        self._pii = deque(maxlen=maxlen)
        self._entropy = deque(maxlen=maxlen)

    # ── Firewall ──────────────────────────────────────────────────────────────
    def log_firewall_block(self, phrase: str, tenant_id: str = "default"):
        self._firewall.appendleft({
            "timestamp": time.time(),
            "matched_phrase": phrase,
            "tenant_id": tenant_id,
        })

    def get_firewall_events(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(self._firewall)[:limit]

    # ── PII ───────────────────────────────────────────────────────────────────
    def log_pii_hit(self, pii_types: list[str], tenant_id: str = "default"):
        self._pii.appendleft({
            "timestamp": time.time(),
            "pii_types": pii_types,
            "tenant_id": tenant_id,
        })

    def get_pii_events(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(self._pii)[:limit]

    def pii_type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self._pii:
            for t in entry["pii_types"]:
                counts[t] = counts.get(t, 0) + 1
        return counts

    # ── Shannon Entropy / Hallucination ──────────────────────────────────────
    def log_entropy_event(self, model: str, entropy: float, blocked: bool, healed: bool = False, tenant_id: str = "default"):
        self._entropy.appendleft({
            "timestamp": time.time(),
            "model": model,
            "entropy": entropy,
            "blocked": blocked,
            "healed": healed,
            "tenant_id": tenant_id,
        })

    def get_entropy_events(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(self._entropy)[:limit]


# Global singleton
event_logger = EventLogger()

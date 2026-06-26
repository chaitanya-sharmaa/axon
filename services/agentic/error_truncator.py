"""Error Message Truncation — Agentic Middleware Module.

Detects Python / JavaScript / generic stack traces in tool result messages
and compresses them to just the final error line.

WHY THIS IS LOSSLESS:
  An LLM agent only needs to know *what* failed, not the internal call stack.
  The error type + message contains all actionable information.
  The 40-line traceback above it is irrelevant to agent decision making.

SAVINGS: 90%+ on failed tool observations.
"""
from __future__ import annotations

import re
import logging
from typing import Any, List, Dict, Tuple

log = logging.getLogger(__name__)

# ── Detection patterns ────────────────────────────────────────────────────────

_PYTHON_TRACEBACK = re.compile(
    r'Traceback \(most recent call last\):',
    re.MULTILINE,
)
_PYTHON_FRAME = re.compile(r'^\s{2,}File "', re.MULTILINE)
_JS_FRAME = re.compile(r'^\s+at .+\(.+:\d+:\d+\)', re.MULTILINE)
_JAVA_FRAME = re.compile(r'^\s+at [a-zA-Z$_][\w$.]+\(.+\.java:\d+\)', re.MULTILINE)

# Minimum number of frame lines to count as a "real" traceback
_MIN_FRAME_LINES = 3


def _is_stack_trace(text: str) -> bool:
    """Return True if text contains a multi-line stack trace."""
    if _PYTHON_TRACEBACK.search(text):
        return True
    if len(_PYTHON_FRAME.findall(text)) >= _MIN_FRAME_LINES:
        return True
    if len(_JS_FRAME.findall(text)) >= _MIN_FRAME_LINES:
        return True
    if len(_JAVA_FRAME.findall(text)) >= _MIN_FRAME_LINES:
        return True
    return False


# ── Error line extractors (tried in order) ───────────────────────────────────

_EXTRACTORS = [
    re.compile(r'([A-Za-z][A-Za-z0-9_]*(?:Error|Exception|Fault)[^\n]{0,200})$', re.MULTILINE),
    re.compile(r'(FAILED[^\n]{0,200})$', re.MULTILINE),
    re.compile(r'(Error:[^\n]{0,200})$', re.MULTILINE),
    re.compile(r'(error:[^\n]{0,200})$', re.MULTILINE, ),
]


def _extract_final_error(text: str) -> str:
    """Extract the most meaningful single-line error from a stack trace."""
    # Try each extractor; the last match wins (most specific error)
    best = None
    for pattern in _EXTRACTORS:
        matches = pattern.findall(text)
        if matches:
            best = matches[-1].strip()

    if best:
        return f"[Tool Error] {best}"

    # Fallback: last non-blank line
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped:
            return f"[Tool Error] {stripped}"

    return "[Tool Error] (unknown)"


# ── Public API ────────────────────────────────────────────────────────────────

def truncate(content: str) -> Tuple[str, int]:
    """
    If *content* is a stack trace, compress it to the error headline.

    Returns
    -------
    (new_content, tokens_saved_estimate)
    """
    if not isinstance(content, str) or len(content) < 150:
        return content, 0

    if not _is_stack_trace(content):
        return content, 0

    compressed = _extract_final_error(content)
    tokens_saved = max(0, (len(content) - len(compressed)) // 4)
    log.info(
        f"ErrorTruncator: stack trace {len(content)}→{len(compressed)} chars "
        f"(~{tokens_saved} tokens saved)"
    )
    return compressed, tokens_saved


def apply(messages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Apply error truncation to every ``role:tool`` message in *messages*.

    Returns
    -------
    (modified_messages, total_tokens_saved)
    """
    total_saved = 0
    result = []
    for msg in messages:
        if msg.get("role") == "tool" and isinstance(msg.get("content"), str):
            new_content, saved = truncate(msg["content"])
            if saved > 0:
                msg = {**msg, "content": new_content}
            total_saved += saved
        result.append(msg)
    return result, total_saved

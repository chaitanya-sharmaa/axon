"""LangChain integration for Axon Bridge.

Provides ``AxonCallbackHandler`` — a LangChain callback that automatically
compresses LLM prompts using Axon's token optimizer before they are sent,
and reports savings after each call.

Installation
------------
Install with the ``langchain`` extra::

    pip install "axon-bridge[langchain]"

Usage
-----
::

    from langchain_openai import ChatOpenAI
    from integrations.langchain import AxonCallbackHandler
    from services.token_optimizer import TokenOptimizer

    optimizer = TokenOptimizer()
    handler = AxonCallbackHandler(optimizer=optimizer, session_id="my-session")

    llm = ChatOpenAI(model="gpt-4o", callbacks=[handler])
    response = llm.invoke("Summarise the latest earnings report...")

    print(handler.last_savings)
    # {'savings_pct': 38.2, 'original_tokens': 812, 'compressed_tokens': 501}
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

log = logging.getLogger(__name__)


try:
    from langchain_core.callbacks.base import BaseCallbackHandler
    from langchain_core.messages import BaseMessage
    from langchain_core.outputs import LLMResult
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False
    # Provide a stub so the module can be imported without langchain installed
    BaseCallbackHandler = object  # type: ignore[misc,assignment]


class AxonCallbackHandler(BaseCallbackHandler):  # type: ignore[misc]
    """LangChain callback that reports Axon token savings per LLM call.

    Parameters
    ----------
    optimizer:
        A ``TokenOptimizer`` instance (shared with your AxonService).
    session_id:
        Optional session ID for multi-turn deduplication.
    verbose:
        If ``True``, log savings after each call.
    """

    def __init__(
        self,
        optimizer: Any = None,
        session_id: str | None = None,
        verbose: bool = True,
    ) -> None:
        if not _LANGCHAIN_AVAILABLE:
            raise ImportError(
                "langchain-core is required. Install with: pip install 'axon-bridge[langchain]'"
            )
        super().__init__()
        self._optimizer = optimizer
        self._session_id = session_id
        self._verbose = verbose
        self.last_savings: dict[str, Any] = {}
        self._total_original_tokens = 0
        self._total_compressed_tokens = 0

    # ── LangChain callback hooks ───────────────────────────────────────────────

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Called before the LLM receives the prompt — measure compression opportunity."""
        if self._optimizer is None:
            return
        for prompt in prompts:
            result = self._optimizer.optimize(
                {"prompt": prompt}, session_id=self._session_id
            )
            self._total_original_tokens += result.json_baseline_tokens
            self._total_compressed_tokens += result.winner.token_estimate

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Called before a chat model receives messages."""
        if self._optimizer is None:
            return
        for message_batch in messages:
            for msg in message_batch:
                content = getattr(msg, "content", "") or ""
                if isinstance(content, str) and content:
                    result = self._optimizer.optimize(
                        {"role": getattr(msg, "type", "user"), "content": content},
                        session_id=self._session_id,
                    )
                    self._total_original_tokens += result.json_baseline_tokens
                    self._total_compressed_tokens += result.winner.token_estimate

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        """Called after the LLM responds — compute and log savings."""
        orig = self._total_original_tokens
        comp = self._total_compressed_tokens
        savings_pct = round((1 - comp / max(1, orig)) * 100, 2)

        self.last_savings = {
            "original_tokens": orig,
            "compressed_tokens": comp,
            "savings_pct": savings_pct,
        }

        if self._verbose:
            log.info(
                "Axon savings: %s%% (%d → %d tokens) [session=%s]",
                savings_pct,
                orig,
                comp,
                self._session_id or "-",
            )

        # Reset per-call counters
        self._total_original_tokens = 0
        self._total_compressed_tokens = 0

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        log.warning("LLM call failed (run_id=%s): %s", run_id, error)

    # ── Summary helpers ────────────────────────────────────────────────────────

    @property
    def session_id(self) -> str | None:
        return self._session_id

"""Plugin registry for Axon Bridge custom encoding strategies.

Third-party developers can register their own encoding strategies without
forking the library::

    # my_plugin.py
    from services.plugin_registry import register_strategy
    from typing import Any

    @register_strategy("brotli_json")
    def encode_brotli(obj: Any, session_id: str | None = None) -> str:
        import brotli, json
        return brotli.compress(json.dumps(obj).encode()).hex()

Then register the plugin in your app startup::

    import my_plugin  # side-effect: registers "brotli_json" strategy

    from services.token_optimizer import TokenOptimizer
    optimizer = TokenOptimizer(enabled_strategies=["generic", "brotli_json", "json"])

The optimizer calls ``PluginRegistry.encode(strategy, obj, session_id)`` for
any strategy name it doesn't recognise natively.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

# Strategy callable: (obj, session_id) -> str
StrategyFn = Callable[[Any, Optional[str]], str]

_REGISTRY: dict[str, StrategyFn] = {}


def register_strategy(name: str) -> Callable[[StrategyFn], StrategyFn]:
    """Decorator — register *fn* as an Axon encoding strategy named *name*.

    Parameters
    ----------
    name:
        A unique strategy identifier.  Must not conflict with built-in names
        (``graph``, ``graph_session``, etc.).
    """
    def decorator(fn: StrategyFn) -> StrategyFn:
        if name in _REGISTRY:
            log.warning("Overwriting existing plugin strategy '%s'", name)
        _REGISTRY[name] = fn
        log.info("Registered custom encoding strategy '%s'", name)
        return fn
    return decorator


def list_strategies() -> list[str]:
    """Return all registered plugin strategy names."""
    return list(_REGISTRY.keys())


def encode(name: str, obj: Any, session_id: Optional[str] = None) -> Optional[str]:
    """Invoke a registered plugin strategy.

    Returns ``None`` if the strategy is not registered (caller should fall back
    to built-in strategies).
    """
    fn = _REGISTRY.get(name)
    if fn is None:
        return None
    try:
        return fn(obj, session_id)
    except Exception as exc:
        log.warning("Plugin strategy '%s' failed: %s", name, exc, exc_info=False)
        return None


class PluginRegistry:
    """Object-oriented interface to the module-level registry (for DI)."""

    @staticmethod
    def register(name: str, fn: StrategyFn) -> None:
        _REGISTRY[name] = fn

    @staticmethod
    def encode(name: str, obj: Any, session_id: Optional[str] = None) -> Optional[str]:
        return encode(name, obj, session_id)

    @staticmethod
    def list_strategies() -> list[str]:
        return list_strategies()

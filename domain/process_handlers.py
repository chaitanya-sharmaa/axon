"""Business logic handlers for payload processing."""

from __future__ import annotations

from typing import Any, Callable, Dict


def handler_echo(payload: Any) -> Any:
    """Echo handler: returns payload as-is."""
    return {"echo": payload}


def handler_active_items(payload: Any) -> Any:
    """Filter and count active items from payload."""
    if not isinstance(payload, dict):
        return {"summary": {"total": 0, "active": 0}, "active_items": []}

    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []
    
    active_items = [x for x in items if isinstance(x, dict) and x.get("status") == "active"]
    
    return {
        "summary": {"total": len(items), "active": len(active_items)},
        "active_items": active_items,
    }


def handler_graph_processor(payload: Any) -> Any:
    """Process graph payloads (code symbols + edges) for deduplication analysis."""
    if not isinstance(payload, dict):
        return {"symbols_processed": 0, "edges_processed": 0}
    
    symbols = payload.get("symbols", [])
    edges = payload.get("edges", [])
    
    # Group symbols by type and module
    by_type: Dict[str, int] = {}
    by_module: Dict[str, int] = {}
    
    for sym in symbols:
        sym_type = sym.get("type", "unknown")
        module = sym.get("module", "default")
        by_type[sym_type] = by_type.get(sym_type, 0) + 1
        by_module[module] = by_module.get(module, 0) + 1
    
    # Analyze edges
    edge_types: Dict[str, int] = {}
    for edge in edges:
        etype = edge.get("type", "unknown")
        edge_types[etype] = edge_types.get(etype, 0) + 1
    
    return {
        "symbols_processed": len(symbols),
        "symbols_by_type": by_type,
        "symbols_by_module": by_module,
        "edges_processed": len(edges),
        "edge_types": edge_types,
        "metadata": {
            "avg_edges_per_symbol": len(edges) / max(1, len(symbols)),
            "graph_density": len(edges) / max(1, len(symbols) * (len(symbols) - 1) / 2),
        },
    }


# Handler registry
HANDLERS: Dict[str, Callable[[Any], Any]] = {
    "echo": handler_echo,
    "active_items": handler_active_items,
    "graph_processor": handler_graph_processor,
}


def get_handler(name: str) -> Callable[[Any], Any] | None:
    """Get handler by name."""
    return HANDLERS.get(name)


def list_handlers() -> list[str]:
    """List available handlers."""
    return list(HANDLERS.keys())

"""Unit tests for the TokenOptimizer service."""

import pytest
from services.token_optimizer import TokenOptimizer
from services.bridge_service import AxonService


@pytest.fixture
def optimizer() -> TokenOptimizer:
    """Returns a fresh TokenOptimizer instance for each test."""
    return TokenOptimizer()


# --- Generic Payload Tests ---

def test_optimize_generic_first_turn(optimizer: TokenOptimizer):
    """Tests that 'generic' is chosen for a simple payload on the first turn."""
    payload = {"user": "test_user_long_name", "action": "login_action_long_name", "status": "success", "timestamp": 12345}
    # Exclude JSON and schema_values so generic competes fairly against its delta/session peers
    result = optimizer.optimize(payload, enabled_strategies=["generic", "generic_delta", "generic_session"])

    assert result.payload_type == "generic"
    assert result.winner.strategy == "generic"

    metrics = result.to_metrics()
    assert "generic" in metrics["format_comparison"]
    # Session/delta strategies should not run without a session_id
    assert "generic_delta" not in metrics["format_comparison"]
    assert "generic_session" not in metrics["format_comparison"]


def test_optimize_generic_delta_toon_wins(optimizer: TokenOptimizer):
    """Tests that TOON ('generic_delta') wins when only one field changes."""
    session_id = "test-toon"
    payload1 = {"user": "test_user_long_name", "action": "login_action_long_name", "status": "success"}
    payload2 = {"user": "test_user_long_name", "action": "logout_action", "status": "success"}  # action changed

    strategies = ["generic", "generic_delta", "generic_session"]
    optimizer.optimize(payload1, session_id=session_id, enabled_strategies=strategies)
    result = optimizer.optimize(payload2, session_id=session_id, enabled_strategies=strategies)

    assert result.payload_type == "generic"
    assert result.winner.strategy == "generic_delta"
    # The encoded output for delta should only contain the changed key
    assert "action=logout" in result.winner.encoded
    assert "user=test" not in result.winner.encoded
    assert "status=success" not in result.winner.encoded


def test_optimize_generic_session_tron_wins(optimizer: TokenOptimizer):
    """Tests that TRON ('generic_session') wins when scalar values are repeated."""
    session_id = "test-tron"
    # Make the payload large enough so TRON beats JSON
    payload1 = {"user": "test_user_very_long_string", "action": "login_long_string", "status": "success_long_string"}
    payload2 = {"user": "test_user_very_long_string", "action": "view_profile", "result": "success_long_string"}

    strategies = ["generic", "generic_delta", "generic_session"]
    optimizer.optimize(payload1, session_id=session_id, enabled_strategies=strategies)
    result = optimizer.optimize(payload2, session_id=session_id, enabled_strategies=strategies)

    assert result.payload_type == "generic"
    assert result.winner.strategy == "generic_session"
    # The encoded output should contain references for repeated values
    assert 'result="@ref:status"' in result.winner.encoded
    assert "action=view_profile" in result.winner.encoded


def test_optimize_generic_schema_values_wins(optimizer: TokenOptimizer):
    """Tests that schema_values wins for flat, repetitive data."""
    session_id = "test-schema-values"
    payload1 = {"id": 1, "temp": 21.5, "status": "ok"}
    payload2 = {"id": 2, "temp": 22.1, "status": "ok"}  # Same keys, different values

    # First turn establishes the schema
    res1 = optimizer.optimize(payload1, session_id=session_id)
    assert res1.winner.strategy == "schema_values"
    assert res1.winner.encoded == "id=1,temp=21.5,status=ok"

    # Second turn should only send values
    res2 = optimizer.optimize(payload2, session_id=session_id)
    assert res2.winner.strategy == "schema_values"
    assert res2.winner.encoded == "2,22.1,ok"


# --- Graph Payload Tests ---

def test_optimize_graph_first_turn(optimizer: TokenOptimizer):
    """Tests that 'graph' wins for a graph payload on the first turn."""
    payload = {
        "symbols": [{"qualified_name": "pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session", "kind": "class"}],
        "edges": [],
    }
    strategies = ["graph", "graph_delta", "graph_session"]
    result = optimizer.optimize(payload, enabled_strategies=strategies)

    assert result.payload_type == "graph"
    assert result.winner.strategy == "graph"

    metrics = result.to_metrics()
    assert "graph" in metrics["format_comparison"]
    # Generic strategies should not run for graph payloads
    assert "generic" not in metrics["format_comparison"]


def test_optimize_graph_delta_toon_wins(optimizer: TokenOptimizer):
    """Tests that TOON for graphs ('graph_delta') wins when symbols/edges are added."""
    session_id = "test-graph-toon"
    payload1 = {
        "symbols": [{"qualified_name": f"pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session_{i}", "kind": "class"} for i in range(10)],
        "edges": [],
    }
    payload2 = {
        "symbols": [{"qualified_name": f"pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session_{i}", "kind": "class"} for i in range(10)] + [
            {"qualified_name": "pkg.B_Long_Name", "kind": "func"}
        ],
        "edges": [{"source": "pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session_0", "target": "pkg.B_Long_Name", "edge_type": "calls"}],
    }

    strategies = ["graph", "graph_delta", "graph_session"]
    optimizer.optimize(payload1, session_id=session_id, enabled_strategies=strategies)
    result = optimizer.optimize(payload2, session_id=session_id, enabled_strategies=strategies)

    assert result.payload_type == "graph"
    assert result.winner.strategy == "graph_delta"
    assert "pkg.B_Long_Name" in result.winner.encoded
    assert "pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session_1" not in result.winner.encoded


def test_optimize_graph_session_tron_wins(optimizer: TokenOptimizer):
    """Tests that TRON for graphs ('graph_session') wins when symbols are repeated."""
    session_id = "test-graph-tron"
    payload1 = {
        "symbols": [{"qualified_name": f"pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session_{i}", "kind": "class"} for i in range(10)],
        "edges": [],
    }
    payload2 = {
        "symbols": [{"qualified_name": f"pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session_{i}", "kind": "class"} for i in range(10)] + [
            {"qualified_name": "pkg.B_Long_Name", "kind": "func"}
        ],
        "edges": [{"source": "pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session_0", "target": "pkg.B_Long_Name", "edge_type": "calls"}],
    }

    strategies = ["graph", "graph_delta", "graph_session"]
    optimizer.optimize(payload1, session_id=session_id, enabled_strategies=strategies)

    # graph_delta beats graph_session if most things stay the same, so isolate graph_session
    result = optimizer.optimize(payload2, session_id=session_id, enabled_strategies=["graph", "graph_session"])

    assert result.payload_type == "graph"
    assert result.winner.strategy == "graph_session"
    assert "pkg.B_Long_Name" in result.winner.encoded
    assert "pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session_1" not in result.winner.encoded


# --- Edge Cases and State Management ---

def test_clear_session(optimizer: TokenOptimizer):
    """Tests that clearing a session resets the optimization behavior."""
    session_id = "test-clear"
    payload = {"user": "test_user_long_name", "action": "login_action_long_name"}
    strategies = ["generic", "generic_delta", "generic_session"]

    res1 = optimizer.optimize(payload, session_id=session_id, enabled_strategies=strategies)
    assert res1.winner.strategy == "generic"

    payload2 = {"user": "test_user_long_name", "action": "logout_action"}
    res2 = optimizer.optimize(payload2, session_id=session_id, enabled_strategies=strategies)
    assert res2.winner.strategy in ("generic_delta", "generic_session")

    optimizer.clear_session(session_id)

    res3 = optimizer.optimize(payload, session_id=session_id, enabled_strategies=strategies)
    assert res3.winner.strategy == "generic"
    assert res1.winner.encoded == res3.winner.encoded


def test_empty_graph_payload_is_generic(optimizer: TokenOptimizer):
    """Tests that a payload with an empty symbols list is treated as generic."""
    payload = {"symbols": [], "edges": []}
    result = optimizer.optimize(payload)
    assert result.payload_type == "generic"


def test_lru_eviction_does_not_crash(optimizer: TokenOptimizer):
    """Tests that LRU eviction under max_sessions cap doesn't raise errors."""
    small_optimizer = TokenOptimizer(max_sessions=3)
    payload = {"key": "value_long_enough_to_matter"}

    # Push 5 sessions through a cap of 3 — should silently evict without error
    for i in range(5):
        small_optimizer.optimize(payload, session_id=f"session-{i}")

    # The oldest sessions should have been evicted; the newest should still work
    result = small_optimizer.optimize({"key": "new_value"}, session_id="session-4")
    assert result.winner is not None


def test_unified_session_management(optimizer: TokenOptimizer):
    """
    Tests that AxonService and TokenOptimizer share the same session state
    when wired together correctly.
    """
    axon_service = AxonService(token_optimizer=optimizer, include_json_fallback=True)
    session_id = "unified-session-test"

    # Action 1 (via AxonService): establish initial session state with a graph payload
    payload1 = {"symbols": [{"qualified_name": "pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session", "kind": "class"}]}
    axon_service.to_compact_text(payload1, session_id=session_id)

    # Action 2 (via TokenOptimizer): re-use the established state
    payload2 = {
        "symbols": [
            {"qualified_name": "pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session", "kind": "class"},
            {"qualified_name": "pkg.B_Long_Name", "kind": "func"},
        ],
        "edges": [{"source": "pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session", "target": "pkg.B_Long_Name", "edge_type": "calls"}],
    }

    result = optimizer.optimize(payload2, session_id=session_id, enabled_strategies=["graph", "graph_delta", "graph_session"])

    # The optimizer should choose a session-aware strategy because it remembers pkg.A
    assert result.winner.strategy in ("graph_session", "graph_delta")
    # Key assertion: the already-transmitted symbol is not re-encoded in full
    assert "pkg.A_Super_Duper_Extremely_Long_Name_To_Beat_Header_Cost_For_Graph_Session" not in result.winner.encoded
    assert "pkg.B_Long_Name" in result.winner.encoded

# --- Coverage for Edge Cases & Error Handling ---

def test_estimate_tokens_fallback():
    # Model doesn't exist, should use heuristic
    from services.token_optimizer import _estimate_tokens
    assert _estimate_tokens("test string", model="non-existent-model") >= 1

def test_savings_zero_tokens():
    from services.token_optimizer import _savings
    assert _savings(0, 100) == 0.0

def test_prune_context_empty_query_terms():
    from services.token_optimizer import _prune_context
    from gcf import Symbol
    syms = [Symbol("a", "func", 1.0, "", 0)] * 60
    assert len(_prune_context(syms, "   ")) == 60

def test_build_payload_invalid_symbols():
    from services.token_optimizer import _build_payload
    assert _build_payload({"symbols": "not a list"}) is None
    assert _build_payload({"symbols": ["not a dict"]}) is None

def test_build_payload_name_module_score_fallback():
    from services.token_optimizer import _build_payload
    p = _build_payload({
        "symbols": [
            {"name": "foo", "module": "bar", "score": "invalid"},
            {"name": "baz"}
        ]
    })
    assert p is not None
    assert p.symbols[0].qualified_name == "bar:foo"
    assert p.symbols[0].score == 1.0
    assert p.symbols[1].qualified_name == "baz"

def test_build_payload_invalid_edge():
    from services.token_optimizer import _build_payload
    p = _build_payload({
        "symbols": [{"name": "A"}],
        "edges": ["not a dict", {"source": "A", "target": "B"}]
    })
    assert len(p.edges) == 1

def test_build_generic_delta_list_no_change():
    from services.token_optimizer import _build_generic_delta
    assert _build_generic_delta([1, 2], [1, 2]) is None

def test_build_generic_session_unknown_type():
    from services.token_optimizer import _build_generic_session
    class UnknownType: pass
    obj = UnknownType()
    assert _build_generic_session(obj, {}) == obj

def test_build_delta_none():
    from services.token_optimizer import _build_delta
    assert _build_delta(None, None) is None

def test_get_gcf_session(optimizer: TokenOptimizer):
    sess = optimizer.get_gcf_session("test")
    assert sess is not None

def test_optimizer_strategy_exceptions(optimizer: TokenOptimizer):
    # Pass a malformed object that tricks it into entering a strategy but crashes the encoder
    # Mock the encode functions to raise Exceptions
    import collections
    from unittest.mock import patch
    
    with patch("services.token_optimizer.encode", side_effect=Exception("mock err")), \
         patch("services.token_optimizer.encode_with_session", side_effect=Exception("mock err")), \
         patch("services.token_optimizer.encode_delta", side_effect=Exception("mock err")), \
         patch("services.token_optimizer.encode_generic", side_effect=Exception("mock err")):
         
        payload_graph = {"symbols": [{"qualified_name": "A", "kind": "func"}], "edges": []}
        # It should catch the exceptions and fallback to json
        res1 = optimizer.optimize(payload_graph, session_id="test_err")
        assert res1.winner.strategy == "json"
        
        payload_generic = {"a": 1}
        res2 = optimizer.optimize(payload_generic, session_id="test_err2")
        assert res2.winner.strategy == "json"

def test_prune_tools_no_bm25():
    from services.token_optimizer import prune_tools
    with patch("services.token_optimizer.BM25Okapi", None):
        tools = [{"type": "function", "function": {"name": "A"}}] * 6
        assert len(prune_tools(tools, "query", top_k=2)) == 6


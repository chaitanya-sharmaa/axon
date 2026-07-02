from dataclasses import dataclass
from unittest.mock import patch

import pytest

from services.bridge_service import AxonService
from services.token_optimizer import TokenOptimizer


@dataclass
class DummyDataClass:
    a: int

class DummyModelDump:
    def model_dump(self):
        return {"b": 2}

class DummyDictObj:
    def dict(self):
        return {"c": 3}

class DummyCustomObj:
    def __init__(self):
        self.d = 4

def test_bridge_service_normalize_object():
    optimizer = TokenOptimizer()
    service = AxonService(optimizer)

    assert service._normalize_object(DummyDataClass(1)) == {"a": 1}
    assert service._normalize_object(DummyModelDump()) == {"b": 2}
    assert service._normalize_object(DummyDictObj()) == {"c": 3}
    assert service._normalize_object(DummyCustomObj()) == {"d": 4}

    # Nested mapping
    assert service._normalize_object({"nested": {"x": 1}}) == {"nested": {"x": 1}}

    # List/tuple/set
    assert service._normalize_object((1, 2)) == [1, 2]
    assert service._normalize_object({3}) == [3]

    # Fallback to str
    class WeirdType:
        def __str__(self): return "weird"
        # override dict and __dict__ to avoid them
        @property
        def __dict__(self): raise AttributeError

    # We can just test a byte string as fallback
    assert service._normalize_object(b"bytes") == "b'bytes'"

def test_bridge_service_from_any_to_object():
    optimizer = TokenOptimizer()
    service = AxonService(optimizer)

    # Bytes decoding
    assert service.from_any_to_object(b'{"x": 1}') == {"x": 1}

    # Empty string
    assert service.from_any_to_object("   ") == ""

    # Bad JSON string fallback
    res = service.from_any_to_object("not json {")
    assert res == {"_text": "not json {"}

    # Compact Axon format (Graph)
    # Mock decode since we don't have a valid Axon string handy
    with patch("services.bridge_service.decode") as mock_decode:
        mock_decode.return_value = {"decoded": "graph"}
        res = service.from_any_to_object("Axon profile=graph\nline2")
        assert res == {"decoded": "graph"}

    # Compact Axon format (Generic)
    with patch("services.bridge_service.decode_generic") as mock_decode_gen:
        mock_decode_gen.return_value = {"decoded": "generic"}
        res = service.from_any_to_object("Axon profile=generic\nline2")
        assert res == {"decoded": "generic"}

def test_bridge_service_to_graph_payload_edge_cases():
    optimizer = TokenOptimizer()
    service = AxonService(optimizer)

    assert service._to_graph_payload("not a dict") is None
    assert service._to_graph_payload({"symbols": "not a list"}) is None
    assert service._to_graph_payload({"symbols": ["not a dict"]}) is None

    # Bad qualified_name / no name
    assert service._to_graph_payload({"symbols": [{}]}) is None
    assert service._to_graph_payload({"symbols": [{"name": ""}]}) is None

    # Bad edges list
    assert service._to_graph_payload({"symbols": [{"name": "A"}], "edges": "not a list"}) is None
    assert service._to_graph_payload({"symbols": [{"name": "A"}], "edges": ["not a dict"]}) is None

    # Valid from/to format
    payload = service._to_graph_payload({
        "symbols": [{"name": "A", "module": "m"}],
        "edges": [{"from": "m:A", "to": "B", "type": "calls"}]
    })
    assert payload is not None
    assert payload.symbols[0].qualified_name == "m:A"
    assert payload.edges[0].source == "m:A"
    assert payload.edges[0].target == "B"

def test_bridge_service_get_session():
    optimizer = TokenOptimizer()
    service = AxonService(optimizer)
    assert service._get_session("test_sess") is not None

def test_bridge_service_to_compact_text_exceptions():
    optimizer = TokenOptimizer()
    service = AxonService(optimizer)

    # Fast path if already compact
    assert service.to_compact_text("Axon profile=generic\nfoo") == "Axon profile=generic\nfoo"

    # Simulate an exception in optimization to trigger the json.dumps fallback
    with patch.object(optimizer, "optimize", side_effect=Exception("mock err")):
        res = service.to_compact_text({"x": 1})
        assert '{"x": 1}' in res

def test_bridge_service_from_compact_text():
    optimizer = TokenOptimizer()
    service = AxonService(optimizer)
    with patch("services.bridge_service.decode_generic") as mock_dec:
        mock_dec.return_value = {"a": 1}
        assert service.from_compact_text("some text") == {"a": 1}

def test_bridge_service_process():
    optimizer = TokenOptimizer()
    service = AxonService(optimizer)

    def sync_handler(data):
        return {"result": data["x"] * 2}

    res = service.process({"x": 5}, sync_handler, session_id="test")
    assert "compact_text" in res
    assert "session_id" in res

@pytest.mark.asyncio
async def test_bridge_service_process_async():
    optimizer = TokenOptimizer()
    service = AxonService(optimizer)

    async def async_handler(data):
        return {"result": data["x"] * 2}

    res = await service.process_async({"x": 5}, async_handler, session_id="test")
    assert "compact_text" in res
    assert "session_id" in res

    # Also test sync handler with process_async
    def sync_handler(data):
        return {"result": data["x"] * 2}

    res2 = await service.process_async({"x": 5}, sync_handler, session_id="test2")
    assert "compact_text" in res2

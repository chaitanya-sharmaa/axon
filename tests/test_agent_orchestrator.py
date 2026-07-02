import pytest

from services.agent_orchestrator import (
    AgentDefinition,
    AgentOrchestrator,
)


async def dummy_handler(payload):
    if payload == "fail":
        raise ValueError("Intentional failure")
    return f"handled: {payload}"

def sync_handler(payload):
    return f"sync_handled: {payload}"

@pytest.fixture
def orchestrator():
    return AgentOrchestrator()

@pytest.fixture
def agent1():
    return AgentDefinition(
        name="agent1",
        agent_type="type_a",
        handler=dummy_handler,
        capabilities=["cap1", "cap2"],
        priority=10
    )

@pytest.fixture
def agent2():
    return AgentDefinition(
        name="agent2",
        agent_type="type_b",
        handler=sync_handler,
        capabilities=["cap2", "cap3"],
        priority=5 # higher priority
    )

def test_register_and_list(orchestrator, agent1, agent2):
    orchestrator.register(agent1)
    orchestrator.register(agent2)

    agents = orchestrator.list_agents()
    assert len(agents) == 2
    # agent2 should be first due to priority 5 < 10
    assert agents[0]["name"] == "agent2"
    assert agents[1]["name"] == "agent1"

    # Unregister
    assert orchestrator.unregister("agent1") is True
    assert orchestrator.unregister("nonexistent") is False

def test_find_for_capability(orchestrator, agent1, agent2):
    orchestrator.register(agent1)
    orchestrator.register(agent2)

    res = orchestrator.find_for_capability("cap2")
    assert len(res) == 2
    assert res[0].name == "agent2" # due to priority

    res = orchestrator.find_for_capability("cap1")
    assert len(res) == 1
    assert res[0].name == "agent1"

async def test_dispatch_by_name(orchestrator, agent1):
    orchestrator.register(agent1)

    res = await orchestrator.dispatch("test", agent_name="agent1")
    assert res.success is True
    assert res.result == "handled: test"
    assert res.agent_name == "agent1"

    # Non-existent
    res = await orchestrator.dispatch("test", agent_name="missing")
    assert res.success is False
    assert "No agent named" in res.error

async def test_dispatch_by_capability(orchestrator, agent1, agent2):
    orchestrator.register(agent1)
    orchestrator.register(agent2)

    res = await orchestrator.dispatch("test", capability="cap2")
    # Should pick agent2 due to priority
    assert res.success is True
    assert res.agent_name == "agent2"
    assert res.result == "sync_handled: test"

    # Missing capability
    res = await orchestrator.dispatch("test", capability="missing")
    assert res.success is False
    assert "No agent registered" in res.error

async def test_dispatch_fallback(orchestrator, agent1):
    # Empty registry
    res = await orchestrator.dispatch("test")
    assert res.success is False
    assert "empty" in res.error

    # Pick first
    orchestrator.register(agent1)
    res = await orchestrator.dispatch("test")
    assert res.success is True
    assert res.agent_name == "agent1"

async def test_agent_failure(orchestrator, agent1):
    orchestrator.register(agent1)
    res = await orchestrator.dispatch("fail", agent_name="agent1")
    assert res.success is False
    assert "Intentional failure" in res.error
    assert res.result is None

async def test_dispatch_parallel(orchestrator, agent1, agent2):
    orchestrator.register(agent1)
    orchestrator.register(agent2)

    res = await orchestrator.dispatch_parallel("test", capabilities=["cap1", "cap3", "missing"])
    assert len(res.results) == 3

    succeeded = res.succeeded
    assert len(succeeded) == 2
    names = {r.agent_name for r in succeeded}
    assert "agent1" in names
    assert "agent2" in names

    failed = res.failed
    assert len(failed) == 1
    assert failed[0].agent_name == "none"
    assert "missing" in failed[0].error

async def test_swarm(orchestrator, agent1, agent2):
    orchestrator.register(agent1)
    orchestrator.register(agent2)

    # All
    res = await orchestrator.swarm("test")
    assert len(res.results) == 2

    # Filtered
    res = await orchestrator.swarm("test", filter_type="type_a")
    assert len(res.results) == 1
    assert res.results[0].agent_name == "agent1"

    # Empty
    orchestrator.unregister("agent1")
    orchestrator.unregister("agent2")
    res = await orchestrator.swarm("test")
    assert len(res.results) == 0

async def test_orchestrator_encode_mock():
    # Test encoding by mocking token optimizer
    class MockOptimizer:
        def optimize(self, payload, session_id):
            from dataclasses import dataclass
            @dataclass
            class Winner:
                encoded = "optimized"
                strategy = "mock_strat"
                savings_vs_json_pct = 50.0
            @dataclass
            class OptResult:
                winner = Winner()
            return OptResult()

    orch = AgentOrchestrator(token_optimizer=MockOptimizer())
    orch.register(AgentDefinition(name="a1", agent_type="t", handler=sync_handler))

    res = await orch.dispatch("test")
    assert res.encoded_output == "optimized"
    assert res.strategy_used == "mock_strat"
    assert res.token_savings_pct == 50.0

async def test_orchestrator_encode_exception():
    class BrokenOptimizer:
        def optimize(self, payload, session_id):
            raise Exception("broken")

    orch = AgentOrchestrator(token_optimizer=BrokenOptimizer())
    orch.register(AgentDefinition(name="a1", agent_type="t", handler=sync_handler))

    res = await orch.dispatch("test")
    # Exception caught, returns normal result without encoding
    assert res.success is True
    assert res.encoded_output is None

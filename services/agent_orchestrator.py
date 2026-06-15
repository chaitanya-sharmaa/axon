"""Multi-agent orchestration layer.

Agents are named workers with declared capabilities.  The orchestrator:

  - Maintains a registry of agents
  - Routes tasks to the best-matching agent (by capability + priority)
  - Supports parallel dispatch across multiple agents for fan-out tasks
  - Wraps results in a uniform AgentResult envelope
  - Integrates with TokenOptimizer so each agent's output is auto-encoded
    with the cheapest format before being returned

Typical usage
-------------
::

    from services.agent_orchestrator import AgentOrchestrator, AgentDefinition

    orchestrator = AgentOrchestrator()

    orchestrator.register(AgentDefinition(
        name="graph_agent",
        agent_type="analyzer",
        capabilities=["graph", "code_context"],
        handler=my_graph_handler,
        priority=0,
        description="Analyzes code-symbol graphs",
    ))

    result = await orchestrator.dispatch(payload, capability="graph")
    # result.encoded_output contains GCF-optimized text
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


# ── Agent definition ───────────────────────────────────────────────────────────

@dataclass
class AgentDefinition:
    """Describes a single agent and what it can do."""

    name: str
    agent_type: str                      # e.g. "analyzer", "encoder", "router", "generic"
    handler: Callable[[Any], Any]
    capabilities: list[str] = field(default_factory=list)
    priority: int = 0                    # lower = higher priority
    description: str = ""


# ── Result containers ──────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    agent_name: str
    result: Any
    success: bool
    error: str | None = None
    encoded_output: str | None = None    # GCF/cheapest encoded version of result
    strategy_used: str | None = None
    token_savings_pct: float | None = None
    latency_ms: float | None = None


@dataclass
class ParallelDispatchResult:
    results: list[AgentResult]
    total_latency_ms: float

    @property
    def succeeded(self) -> list[AgentResult]:
        return [r for r in self.results if r.success]

    @property
    def failed(self) -> list[AgentResult]:
        return [r for r in self.results if not r.success]


# ── Orchestrator ───────────────────────────────────────────────────────────────

class AgentOrchestrator:
    """Registry and dispatcher for the multi-agent layer.

    Parameters
    ----------
    token_optimizer:
        Optional ``TokenOptimizer`` instance.  If provided, each agent result is
        auto-encoded with the cheapest available strategy.
    """

    def __init__(self, token_optimizer: Any | None = None) -> None:
        self._registry: dict[str, AgentDefinition] = {}
        self._optimizer = token_optimizer

    # ── Registry ──────────────────────────────────────────────────────────────

    def register(self, agent: AgentDefinition) -> None:
        """Add or replace an agent in the registry."""
        self._registry[agent.name] = agent

    def unregister(self, name: str) -> bool:
        """Remove an agent. Returns True if it existed."""
        return self._registry.pop(name, None) is not None

    def list_agents(self) -> list[dict[str, Any]]:
        """Sorted list of agent descriptors (for API exposure)."""
        return [
            {
                "name": a.name,
                "type": a.agent_type,
                "capabilities": a.capabilities,
                "priority": a.priority,
                "description": a.description,
            }
            for a in sorted(self._registry.values(), key=lambda a: (a.priority, a.name))
        ]

    def find_for_capability(self, capability: str) -> list[AgentDefinition]:
        """Return agents that declare *capability*, sorted by priority."""
        return sorted(
            [a for a in self._registry.values() if capability in a.capabilities],
            key=lambda a: (a.priority, a.name),
        )

    # ── Encoding helper ────────────────────────────────────────────────────────

    def _encode(self, payload: Any, session_id: str | None) -> tuple[str | None, str | None, float | None]:
        """Encode the INBOUND payload (the LLM context) with the cheapest strategy.

        We encode the payload, not the agent result — because the bridge's job
        is to compress the prompt/context that travels to the LLM.
        """
        if self._optimizer is None:
            return None, None, None
        try:
            opt = self._optimizer.optimize(payload, session_id=session_id)
            return opt.winner.encoded, opt.winner.strategy, opt.winner.savings_vs_json_pct
        except Exception:
            return None, None, None

    # ── Single dispatch ────────────────────────────────────────────────────────

    async def dispatch(
        self,
        payload: Any,
        capability: str | None = None,
        agent_name: str | None = None,
        session_id: str | None = None,
    ) -> AgentResult:
        """Route to the best matching agent and return its result.

        Preference order: ``agent_name`` (explicit) > ``capability`` match > first registered.
        """
        agent: AgentDefinition | None = None

        if agent_name:
            agent = self._registry.get(agent_name)
            if agent is None:
                return AgentResult(
                    agent_name=agent_name, result=None, success=False,
                    error=f"No agent named '{agent_name}'",
                )
        elif capability:
            candidates = self.find_for_capability(capability)
            if not candidates:
                return AgentResult(
                    agent_name="none", result=None, success=False,
                    error=f"No agent registered for capability '{capability}'",
                )
            agent = candidates[0]
        else:
            if not self._registry:
                return AgentResult(
                    agent_name="none", result=None, success=False,
                    error="Agent registry is empty",
                )
            agent = next(iter(sorted(self._registry.values(), key=lambda a: (a.priority, a.name))))

        t0 = time.monotonic()
        try:
            if asyncio.iscoroutinefunction(agent.handler):
                result = await agent.handler(payload)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, agent.handler, payload)
            encoded, strategy, savings = self._encode(payload, session_id)
            return AgentResult(
                agent_name=agent.name,
                result=result,
                success=True,
                encoded_output=encoded,
                strategy_used=strategy,
                token_savings_pct=savings,
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
            )
        except Exception as exc:
            return AgentResult(
                agent_name=agent.name, result=None, success=False,
                error=str(exc),
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
            )

    # ── Parallel fan-out dispatch ──────────────────────────────────────────────

    async def dispatch_parallel(
        self,
        payload: Any,
        capabilities: list[str],
        session_id: str | None = None,
    ) -> ParallelDispatchResult:
        """Run one agent per capability concurrently and return all results."""
        t0 = time.monotonic()

        async def run_one(cap: str) -> AgentResult:
            return await self.dispatch(payload, capability=cap, session_id=session_id)

        results = list(await asyncio.gather(*[run_one(c) for c in capabilities]))
        return ParallelDispatchResult(
            results=results,
            total_latency_ms=round((time.monotonic() - t0) * 1000, 2),
        )

    # ── Swarm: fan-out to ALL registered agents ────────────────────────────────

    async def swarm(
        self,
        payload: Any,
        session_id: str | None = None,
        filter_type: str | None = None,
    ) -> ParallelDispatchResult:
        """Dispatch to every registered agent (optionally filtered by type).

        This mirrors Ruflo's swarm_init concept: all agents in the swarm
        process the same payload, results are collected and returned together.
        """
        t0 = time.monotonic()
        agents = list(self._registry.values())
        if filter_type:
            agents = [a for a in agents if a.agent_type == filter_type]
        if not agents:
            return ParallelDispatchResult(results=[], total_latency_ms=0)

        async def run_agent(agent: AgentDefinition) -> AgentResult:
            inner_t0 = time.monotonic()
            try:
                if asyncio.iscoroutinefunction(agent.handler):
                    result = await agent.handler(payload)
                else:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, agent.handler, payload)
                encoded, strategy, savings = self._encode(payload, session_id)
                return AgentResult(
                    agent_name=agent.name, result=result, success=True,
                    encoded_output=encoded, strategy_used=strategy,
                    token_savings_pct=savings,
                    latency_ms=round((time.monotonic() - inner_t0) * 1000, 2),
                )
            except Exception as exc:
                return AgentResult(
                    agent_name=agent.name, result=None, success=False,
                    error=str(exc),
                    latency_ms=round((time.monotonic() - inner_t0) * 1000, 2),
                )

        results = list(await asyncio.gather(*[run_agent(a) for a in agents]))
        return ParallelDispatchResult(
            results=results,
            total_latency_ms=round((time.monotonic() - t0) * 1000, 2),
        )

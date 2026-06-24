from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

class BaseMemoryStore(ABC):
    """Abstract interface for session memory backends."""
    
    @abstractmethod
    async def create_session(self, session_id: str, metadata: dict[str, Any] | None = None) -> None:
        pass

    @abstractmethod
    async def get_session_symbols(self, session_id: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def add_session_symbol(
        self,
        session_id: str,
        symbol_id: int,
        qualified_name: str,
        kind: str,
        score: float,
        provenance: str,
        distance: int,
    ) -> None:
        pass

    @abstractmethod
    async def get_session_schema(self, session_id: str, schema_hash: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    async def cache_session_schema(
        self, session_id: str, schema_hash: str, definition: dict[str, Any], field_names: list[str]
    ) -> None:
        pass

    @abstractmethod
    async def log_event(self, session_id: str, event_type: str, payload: dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def get_session_history(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def cleanup_old_sessions(self, days: int = 7) -> int:
        pass

    @abstractmethod
    async def session_exists(self, session_id: str) -> bool:
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """Delete a session entirely."""
        pass

    @abstractmethod
    async def get_tenant_quota(self, tenant_id: str) -> tuple[float, float]:
        """Get the (monthly_quota_usd, current_spend_usd) for a tenant.
        
        Returns:
            Tuple of (quota_usd, spend_usd). If tenant does not exist,
            returns (0.0, 0.0) or a default.
        """
        pass

    @abstractmethod
    async def set_tenant_quota(self, tenant_id: str, quota_usd: float) -> None:
        """Set the monthly quota in USD for a tenant."""
        pass

    @abstractmethod
    async def increment_tenant_spend(self, tenant_id: str, cost_usd: float) -> None:
        """Increment a tenant's current spend by the specified cost in USD."""
        pass

    @abstractmethod
    async def add_session_fact(self, session_id: str, fact: str) -> None:
        pass

    @abstractmethod
    async def get_session_facts(self, session_id: str) -> list[str]:
        pass

    @abstractmethod
    async def get_thread(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve the ordered list of messages for a stateful thread."""
        pass
        
    @abstractmethod
    async def append_to_thread(self, session_id: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Append messages to a stateful thread and return the full updated thread history."""
        pass
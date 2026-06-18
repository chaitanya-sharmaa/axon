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
        pass

    @abstractmethod
    async def add_session_fact(self, session_id: str, fact: str) -> None:
        pass

    @abstractmethod
    async def get_session_facts(self, session_id: str) -> list[str]:
        pass
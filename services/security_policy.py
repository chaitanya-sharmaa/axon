"""Security configuration for GCF Bridge middleware."""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse


class SecurityConfig:
    """Security settings for proxy and API access."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        allowed_domains: Optional[list[str]] = None,
        require_api_key: bool = False,
        allow_all_domains: bool = False,
    ):
        """Initialize security config.
        
        Args:
            api_key: Expected API key for authentication. Reads from GCF_API_KEY env var if not set.
            allowed_domains: List of domains allowed for proxy requests (e.g., ["httpbin.org", "api.example.com"])
            require_api_key: If True, all requests to protected endpoints require valid API key
            allow_all_domains: If True, ignore domain allowlist (WARNING: use only in trusted environments)
        """
        self.api_key = api_key
        self.require_api_key = require_api_key
        self.allow_all_domains = allow_all_domains
        
        # Default allowlist for common APIs
        self.allowed_domains = allowed_domains or [
            "httpbin.org",
            "api.github.com",
            "api.example.com",
            "localhost",
            "127.0.0.1",
        ]

    def validate_api_key(self, provided_key: Optional[str]) -> bool:
        """Validate provided API key against configured key."""
        if not self.require_api_key:
            return True
        if not self.api_key:
            return False
        return provided_key == self.api_key

    def is_domain_allowed(self, url: str) -> bool:
        """Check if URL domain is in allowlist."""
        if self.allow_all_domains:
            return True
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.split(":")[0]  # Remove port if present
            return domain in self.allowed_domains
        except Exception:
            return False

    def add_domain(self, domain: str) -> None:
        """Add domain to allowlist."""
        if domain not in self.allowed_domains:
            self.allowed_domains.append(domain)

    def remove_domain(self, domain: str) -> None:
        """Remove domain from allowlist."""
        self.allowed_domains = [d for d in self.allowed_domains if d != domain]

    def to_dict(self) -> dict:
        """Export config (without sensitive keys)."""
        return {
            "require_api_key": self.require_api_key,
            "allow_all_domains": self.allow_all_domains,
            "allowed_domains": self.allowed_domains,
            "has_api_key_set": bool(self.api_key),
        }

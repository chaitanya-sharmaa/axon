import re
import logging
from typing import Dict, Tuple

log = logging.getLogger(__name__)

# Basic heuristics for PII
EMAIL_REGEX = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
SSN_REGEX = re.compile(r"\b(?:\d{3}-\d{2}-\d{4})\b")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
# FIX #9: Expanded to cover international formats:
# - North American (+1 optional, various separators)
# - UK mobile/landline (+44, 07xxx, 01xxx, 02xxx)
# - Generic E.164 international (+CC followed by 7-12 digits)
PHONE_REGEX = re.compile(
    r"(?:"
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"   # North America
    r"|\+44[-.\s]?(?:\d{2,4}[-.\s]?){2,4}\d{3,4}"                   # UK +44
    r"|\b0(?:7\d{3}|[12]\d{3}|8[0-9]\d{2})[-.\s]?\d{3}[-.\s]?\d{3,4}\b"  # UK local
    r"|\+(?:[0-9]{1,3})[-.\s]?(?:[0-9]{7,12})"                      # Generic E.164
    r")"
)

class PIIRedactor:
    """A lightweight heuristic-based PII Redactor for Axon Bridge."""
    
    def __init__(self, enable_redaction: bool = True):
        self.enable_redaction = enable_redaction
        
    def redact(self, text: str, tenant_id: str = "default") -> str:
        """Replace detected PII with tokens (e.g. [EMAIL_REDACTED])."""
        if not self.enable_redaction or not text:
            return text
            
        original_text = text
        hit_types = []
        
        # Redact SSNs
        new_text = SSN_REGEX.sub("[SSN_REDACTED]", text)
        if new_text != text: hit_types.append("ssn")
        text = new_text
        
        # Redact Credit Cards
        new_text = CREDIT_CARD_REGEX.sub("[CREDIT_CARD_REDACTED]", text)
        if new_text != text: hit_types.append("credit_card")
        text = new_text
        
        # Redact Phones
        new_text = PHONE_REGEX.sub("[PHONE_REDACTED]", text)
        if new_text != text: hit_types.append("phone")
        text = new_text
        
        # Redact Emails
        new_text = EMAIL_REGEX.sub("[EMAIL_REDACTED]", text)
        if new_text != text: hit_types.append("email")
        text = new_text
        
        if text != original_text:
            log.info(f"PII Redactor: Detected and masked: {hit_types}")
            try:
                from services.event_logger import event_logger
                event_logger.log_pii_hit(hit_types, tenant_id=tenant_id)
            except Exception:
                pass
            
        return text

pii_redactor = PIIRedactor()

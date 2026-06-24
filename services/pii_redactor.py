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
        
    def redact(self, text: str) -> str:
        """Replace detected PII with tokens (e.g. [EMAIL_REDACTED])."""
        if not self.enable_redaction or not text:
            return text
            
        original_text = text
        
        # Redact SSNs
        text = SSN_REGEX.sub("[SSN_REDACTED]", text)
        
        # Redact Credit Cards
        text = CREDIT_CARD_REGEX.sub("[CREDIT_CARD_REDACTED]", text)
        
        # Redact Phones
        text = PHONE_REGEX.sub("[PHONE_REDACTED]", text)
        
        # Redact Emails
        text = EMAIL_REGEX.sub("[EMAIL_REDACTED]", text)
        
        if text != original_text:
            log.info("PII Redactor: Detected and masked sensitive information.")
            
        return text

pii_redactor = PIIRedactor()

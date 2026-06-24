import re
import logging
from typing import Dict, Tuple

log = logging.getLogger(__name__)

# Basic heuristics for PII
EMAIL_REGEX = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
SSN_REGEX = re.compile(r"\b(?:\d{3}-\d{2}-\d{4})\b")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
PHONE_REGEX = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")

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

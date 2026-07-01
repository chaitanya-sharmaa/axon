import pytest
from services.event_logger import EventLogger

def test_event_logger():
    logger = EventLogger(maxlen=2)
    
    # Firewall
    logger.log_firewall_block("bad word 1")
    logger.log_firewall_block("bad word 2", tenant_id="tenant-1")
    logger.log_firewall_block("bad word 3") # should evict first one
    
    fw_events = logger.get_firewall_events(limit=10)
    assert len(fw_events) == 2
    assert fw_events[0]["matched_phrase"] == "bad word 3"
    assert fw_events[0]["tenant_id"] == "default"
    assert fw_events[1]["matched_phrase"] == "bad word 2"
    assert fw_events[1]["tenant_id"] == "tenant-1"
    
    # PII
    logger.log_pii_hit(["EMAIL"])
    logger.log_pii_hit(["PHONE", "EMAIL"], tenant_id="tenant-1")
    
    pii_events = logger.get_pii_events(limit=10)
    assert len(pii_events) == 2
    
    counts = logger.pii_type_counts()
    assert counts["EMAIL"] == 2
    assert counts["PHONE"] == 1
    
    # Entropy
    logger.log_entropy_event("gpt-4o", 1.5, blocked=False)
    logger.log_entropy_event("claude", 3.5, blocked=True, healed=True, tenant_id="tenant-1")
    
    ent_events = logger.get_entropy_events(limit=10)
    assert len(ent_events) == 2
    assert ent_events[0]["model"] == "claude"
    assert ent_events[0]["blocked"] is True
    assert ent_events[0]["healed"] is True
    assert ent_events[0]["tenant_id"] == "tenant-1"

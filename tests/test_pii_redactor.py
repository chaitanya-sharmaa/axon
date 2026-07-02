from services.pii_redactor import PIIRedactor


def test_redactor_disabled():
    redactor = PIIRedactor(enable_redaction=False)
    text = "My email is test@example.com"
    assert redactor.redact(text) == text

def test_redactor_empty():
    redactor = PIIRedactor()
    assert redactor.redact(None) is None
    assert redactor.redact("") == ""

def test_redact_email():
    redactor = PIIRedactor()
    text = "Contact me at user.name+tag@example.co.uk please."
    redacted = redactor.redact(text)
    assert "user.name+tag@example.co.uk" not in redacted
    assert "[EMAIL_REDACTED]" in redacted

def test_redact_ssn():
    redactor = PIIRedactor()
    text = "My SSN is 123-45-6789."
    redacted = redactor.redact(text)
    assert "123-45-6789" not in redacted
    assert "[SSN_REDACTED]" in redacted

def test_redact_credit_card():
    redactor = PIIRedactor()
    # Testing standard formats
    text1 = "Card: 1234 5678 1234 5678"
    assert "1234 5678 1234 5678" not in redactor.redact(text1)
    assert "[CREDIT_CARD_REDACTED]" in redactor.redact(text1)

    text2 = "Card: 1234-5678-1234-5678"
    assert "1234-5678-1234-5678" not in redactor.redact(text2)
    assert "[CREDIT_CARD_REDACTED]" in redactor.redact(text2)

    text3 = "Card: 1234567812345678"
    assert "1234567812345678" not in redactor.redact(text3)
    assert "[CREDIT_CARD_REDACTED]" in redactor.redact(text3)

def test_redact_multiple():
    redactor = PIIRedactor()
    text = "Email: a@b.com, SSN: 111-22-3333, CC: 1111222233334444"
    redacted = redactor.redact(text)
    assert "a@b.com" not in redacted
    assert "111-22-3333" not in redacted
    assert "1111222233334444" not in redacted
    assert "[EMAIL_REDACTED]" in redacted
    assert "[SSN_REDACTED]" in redacted
    assert "[CREDIT_CARD_REDACTED]" in redacted

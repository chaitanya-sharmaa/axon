from services.security_policy import SecurityConfig


def test_security_config_defaults():
    config = SecurityConfig()
    assert not config.require_api_key
    assert not config.allow_all_domains
    assert "localhost" in config.allowed_domains

def test_validate_api_key():
    config = SecurityConfig(api_key="secret", require_api_key=True)
    assert config.validate_api_key("secret") is True
    assert config.validate_api_key("wrong") is False
    assert config.validate_api_key(None) is False

def test_validate_api_key_not_required():
    config = SecurityConfig(api_key="secret", require_api_key=False)
    assert config.validate_api_key("wrong") is True
    assert config.validate_api_key(None) is True

def test_validate_api_key_required_but_not_set():
    config = SecurityConfig(api_key=None, require_api_key=True)
    assert config.validate_api_key("anything") is False

def test_domain_allowlist():
    config = SecurityConfig(allowed_domains=["api.example.com"])
    assert config.is_domain_allowed("https://api.example.com/foo") is True
    assert config.is_domain_allowed("http://api.example.com:8080/foo") is True
    assert config.is_domain_allowed("https://evil.com/foo") is False
    assert config.is_domain_allowed("invalid-url") is False
    # Trigger Exception in urlparse (e.g. pass an integer or object that has no split/netloc)
    assert config.is_domain_allowed(None) is False

def test_allow_all_domains():
    config = SecurityConfig(allow_all_domains=True)
    assert config.is_domain_allowed("https://evil.com/foo") is True

def test_add_remove_domain():
    config = SecurityConfig(allowed_domains=["initial.com"])
    config.add_domain("test.com")
    assert "test.com" in config.allowed_domains
    # Deduplication
    config.add_domain("test.com")
    assert len(config.allowed_domains) == 2

    config.remove_domain("test.com")
    assert "test.com" not in config.allowed_domains

def test_to_dict():
    config = SecurityConfig(api_key="secret", require_api_key=True, allow_all_domains=True, allowed_domains=["a.com"])
    d = config.to_dict()
    assert d["require_api_key"] is True
    assert d["allow_all_domains"] is True
    assert d["allowed_domains"] == ["a.com"]
    assert d["has_api_key_set"] is True

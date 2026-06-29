def test_langchain_import_error():
    import sys
    from unittest.mock import patch
    import importlib
    
    with patch.dict('sys.modules', {'langchain_core.callbacks.base': None}):
        import integrations.langchain
        importlib.reload(integrations.langchain)
        assert integrations.langchain._LANGCHAIN_AVAILABLE is False
    
    # Reload again to restore the original state
    importlib.reload(integrations.langchain)

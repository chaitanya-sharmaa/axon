import uuid
from unittest.mock import MagicMock, patch

import pytest

from integrations.langchain import AxonCallbackHandler


def test_langchain_handler_init_error():
    with patch("integrations.langchain._LANGCHAIN_AVAILABLE", False):
        with pytest.raises(ImportError):
            AxonCallbackHandler()

def test_langchain_handler_on_llm_start():
    # Test without optimizer
    handler = AxonCallbackHandler()
    handler.on_llm_start({}, ["prompt 1"], run_id=uuid.uuid4())
    assert handler._total_original_tokens == 0

    # Test with optimizer
    mock_opt = MagicMock()
    mock_res = MagicMock()
    mock_res.json_baseline_tokens = 100
    mock_res.winner.token_estimate = 50
    mock_opt.optimize.return_value = mock_res

    handler = AxonCallbackHandler(optimizer=mock_opt, session_id="test")
    handler.on_llm_start({}, ["prompt 1"], run_id=uuid.uuid4())
    assert handler._total_original_tokens == 100
    assert handler._total_compressed_tokens == 50

def test_langchain_handler_on_chat_model_start():
    # Test without optimizer
    handler = AxonCallbackHandler()
    handler.on_chat_model_start({}, [[MagicMock()]], run_id=uuid.uuid4())
    assert handler._total_original_tokens == 0

    # Test with optimizer
    mock_opt = MagicMock()
    mock_res = MagicMock()
    mock_res.json_baseline_tokens = 100
    mock_res.winner.token_estimate = 50
    mock_opt.optimize.return_value = mock_res

    handler = AxonCallbackHandler(optimizer=mock_opt)
    mock_msg = MagicMock()
    mock_msg.content = "hello"
    mock_msg.type = "user"
    handler.on_chat_model_start({}, [[mock_msg]], run_id=uuid.uuid4())
    assert handler._total_original_tokens == 100
    assert handler._total_compressed_tokens == 50

def test_langchain_handler_on_llm_end():
    handler = AxonCallbackHandler(verbose=True, session_id="test")
    handler._total_original_tokens = 100
    handler._total_compressed_tokens = 50
    handler.on_llm_end(MagicMock(), run_id=uuid.uuid4())
    assert handler.last_savings["savings_pct"] == 50.0
    assert handler._total_original_tokens == 0

def test_langchain_handler_on_llm_error():
    handler = AxonCallbackHandler()
    handler.on_llm_error(Exception("test"), run_id=uuid.uuid4())
    # Should just log, no exception raised

def test_langchain_handler_session_id():
    handler = AxonCallbackHandler(session_id="session123")
    assert handler.session_id == "session123"

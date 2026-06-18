import pytest
from services.vision_optimizer import downscale_base64_image
from services.text_pruner import prune_text
from api.routes.v1_openai_routes import _compress_messages
from api.routes.v1_openai_routes import ChatMessage
import base64
import io
from PIL import Image
import os

# --- Test 1: Vision Optimizer ---
def test_vision_downscaler():
    # Create a 2000x2000 white square image
    img = Image.new('RGB', (2000, 2000), color='white')
    out_io = io.BytesIO()
    img.save(out_io, format="JPEG")
    b64 = base64.b64encode(out_io.getvalue()).decode('utf-8')
    prefix = "data:image/jpeg;base64,"
    payload = prefix + b64

    # Downscale
    new_payload = downscale_base64_image(payload, max_size=512)
    
    # Assert smaller
    assert len(new_payload) < len(payload), "Downscaled image should be smaller"
    
    # Assert dimensions changed
    new_b64 = new_payload.split(",")[1]
    new_img_bytes = base64.b64decode(new_b64)
    new_img = Image.open(io.BytesIO(new_img_bytes))
    assert new_img.size == (512, 512), "Image should be resized to 512x512"

# --- Test 2: Text Pruning ---
def test_text_pruner():
    raw_text = "The quick brown fox is jumping over the lazy dog. It is a very hot day out there."
    # With prune_text, words like "The", "is", "the", "It", "a", "very", "out", "there" are removed
    pruned = prune_text(raw_text)
    
    # Check that stop words were removed
    assert "is" not in pruned.lower().split()
    assert "the" not in pruned.lower().split()
    assert "a" not in pruned.lower().split()
    
    # Check it still has core semantics
    assert "quick brown fox" in pruned.lower() or "quick brown fox" in pruned

# --- Test 3: Prompt Caching ---
def test_anthropic_prompt_caching():
    os.environ["AXON_PRUNE_TEXT"] = "false"
    messages = [
        ChatMessage(role="system", content="This is a huge system message with instructions" * 50),
        ChatMessage(role="user", content="Hello!")
    ]
    
    # Should inject ephemeral cache_control for claude-3
    compressed, metrics = _compress_messages(messages, "test_sess", "claude-3-haiku-20240307")
    
    sys_content = compressed[0]["content"]
    assert isinstance(sys_content, list), "Anthropic cache control should wrap string in list"
    assert "cache_control" in sys_content[0], "Cache control should be injected"
    assert sys_content[0]["cache_control"]["type"] == "ephemeral"
    
    user_content = compressed[1]["content"]
    assert isinstance(user_content, str), "Shorter message should remain string"

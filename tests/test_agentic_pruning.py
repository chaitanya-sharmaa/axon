import pytest
from services.dom_pruner import compress_html_to_markdown
from services.token_optimizer import minify_scratchpad, prune_tools

def test_compress_html_to_markdown():
    raw_html = """
    <html>
        <head>
            <style>.hidden { display: none; }</style>
            <script>alert('hello');</script>
        </head>
        <body>
            <div style="display: none;">Invisible text</div>
            <div style="visibility: hidden;">Also invisible</div>
            <h1>Main Title</h1>
            <p>Some content with <a href="http://example.com">a link</a> and an <img src="image.jpg"/>.</p>
        </body>
    </html>
    """
    compressed = compress_html_to_markdown(raw_html)
    assert "Invisible text" not in compressed
    assert "Also invisible" not in compressed
    assert "alert('hello')" not in compressed
    assert "# Main Title" in compressed
    assert "Some content with a link and an ." in compressed

def test_minify_scratchpad():
    messages = [
        {"role": "user", "content": "Initial query"},
        {"role": "assistant", "content": "<thought>I should do this</thought>\nAction: success"},
        {"role": "user", "content": "Second query"},
        {"role": "assistant", "content": "<thought>I should do that</thought>\nAction: more success"},
        {"role": "user", "content": "Third query"},
    ]
    minified = minify_scratchpad(messages)
    
    # First assistant message (older) should have thought stripped
    assert "<thought>" not in minified[1]["content"]
    assert "Action: success" in minified[1]["content"]
    
    # Second assistant message (recent, last 2 msgs) should NOT have thought stripped
    # Wait, the last message is "user". The assistant is at index 3 (len=5, i=3, 3 < 3 is False, so it's not stripped!)
    assert "<thought>I should do that</thought>" in minified[3]["content"]

def test_prune_tools():
    tools = [
        {"type": "function", "function": {"name": "get_weather", "description": "Get current weather"}},
        {"type": "function", "function": {"name": "query_db", "description": "Execute SQL queries"}},
        {"type": "function", "function": {"name": "calculator", "description": "Math calculator"}},
        {"type": "function", "function": {"name": "send_email", "description": "Send an email to a user"}},
    ]
    query = "What is the weather in London?"
    
    pruned = prune_tools(tools, query, top_k=2)
    
    assert len(pruned) == 2
    # The weather tool should definitely be in the top 2
    assert pruned[0]["function"]["name"] == "get_weather"

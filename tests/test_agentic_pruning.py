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
    # Note: Trafilatura fallback does not parse inline CSS like display:none
    assert "alert('hello')" not in compressed # Scripts are still stripped
    assert "Main Title" in compressed
    assert "Some content" in compressed

    # Fallback to html2txt when no main article found
    raw_no_article = "<div>just some random text</div>"
    compressed_no_article = compress_html_to_markdown(raw_no_article)
    assert "just some random text" in compressed_no_article

    # Exception fallback
    from unittest.mock import patch
    with patch("trafilatura.extract", side_effect=Exception("parse error")):
        assert compress_html_to_markdown("<html>error</html>") == "<html>error</html>"

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

def test_parallel_deduplicator():
    from services.agentic.parallel_deduplicator import apply, _try_parse_json
    import json
    
    assert _try_parse_json("not json") is None
    assert _try_parse_json('{"a": 1}') == {"a": 1}

    # Empty messages
    assert apply([]) == ([], 0)

    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "tool",
            "tool_call_id": "tool_1",
            "content": json.dumps({
                "id": "user_123",
                "name": "John Doe, A very long string to hit the limit of 20 chars",
                "short": "short"
            })
        },
        {
            "role": "tool",
            "tool_call_id": "tool_2",
            "content": json.dumps({
                "id": "user_123",
                "name": "John Doe, A very long string to hit the limit of 20 chars",
                "other": "different long string of 20 chars plus"
            })
        },
        {
            "role": "tool",
            "tool_call_id": "tool_bad_type",
            "content": {"dict": "instead of string"} # Hits line 105
        },
        {
            "role": "tool",
            "tool_call_id": "tool_bad_json",
            "content": "[1, 2, 3]" # Hits line 109
        },
        {"role": "user", "content": "next"}
    ]
    
    modified, saved = apply(messages)
    assert saved > 0
    assert "John Doe" in modified[1]["content"] # First occurrence kept
    assert "[dup: see tool_1.name]" in modified[2]["content"] # Second occurrence replaced
    assert "user_123" in modified[2]["content"] # Short values not deduplicated

def test_loop_detector():
    from services.agentic.loop_detector import check_and_cache, record, find_loops_in_history, _call_hash
    from services.agentic.session_state import AgenticSessionState
    import time
    
    # Hash function fallback check
    class Unserializable:
        pass
    assert _call_hash("tool", Unserializable())
    
    circular = {}
    circular["a"] = circular
    assert _call_hash("tool", circular)
    
    state = AgenticSessionState(session_id="loop_test")
    
    # 1. First call, should not be loop
    is_loop, cached = check_and_cache("get_weather", {"loc": "NYC"}, state)
    assert is_loop is False
    assert cached is None
    
    # Record the result
    record("get_weather", {"loc": "NYC"}, "Sunny", state)
    
    # 2. Second call, still not loop (threshold is 3)
    is_loop, cached = check_and_cache("get_weather", {"loc": "NYC"}, state)
    assert is_loop is False
    record("get_weather", {"loc": "NYC"}, "Sunny", state)
    
    # 3. Third call, LOOP!
    is_loop, cached = check_and_cache("get_weather", {"loc": "NYC"}, state)
    assert is_loop is True
    assert "[AXON LOOP GUARD]" in cached
    assert "Sunny" in cached

    # Test non-string cached result formatting
    record("get_json", {}, {"status": "ok"}, state)
    record("get_json", {}, {"status": "ok"}, state)
    is_loop, cached_json = check_and_cache("get_json", {}, state)
    assert is_loop is True
    assert '"status": "ok"' in cached_json
    
    # Test record bounds (max 200)
    for i in range(250):
        record("spam", i, "res", state)
    assert len(state.tool_call_history) == 200
    
    # Test find_loops_in_history
    msgs = [
        {"role": "assistant", "tool_calls": [{"function": {"name": "f1", "arguments": "{}"}}]},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "tool_calls": [{"function": {"name": "f1", "arguments": "{}"}}]}
    ]
    loops = find_loops_in_history(msgs)
    assert len(loops) == 1
    assert loops[0]["tool"] == "f1"
    assert loops[0]["repeated"] is True

def test_observation_window():
    from services.agentic.observation_window import apply, _shannon_entropy, _content_str
    
    assert _shannon_entropy("") == 0.0
    assert _shannon_entropy("a") == 0.0
    assert _shannon_entropy("ab") > 0.0
    
    assert _content_str("str") == "str"
    assert _content_str([{"text": "t1"}, "t2"]) == "t1 t2"
    assert _content_str(123) == "123"
    
    msgs = [{"role": "tool", "content": "hello"} for _ in range(5)]
    # Under minimum (6)
    pruned, saved = apply(msgs, current_turn=1)
    assert len(pruned) == 5
    assert saved == 0
    
    # Exceed minimum and drop fraction
    # 10 tools, DROP_FRACTION=0.4 => drop 4
    # ALWAYS_KEEP_RECENT=3, MAX_TOOL_RESULTS=30
    msgs = []
    for i in range(10):
        # We need a low entropy string so R < 0.25
        # "a"*10 has H=0, R=0
        msgs.append({"role": "tool", "content": "a" * 10})
        
    pruned, saved = apply(msgs, current_turn=1)
    # Expected dropped: 4 (since max_to_drop=4)
    assert len(pruned) == 6
    assert saved > 0

    # Test hard cap: mock LAMBDA to 0 so recency doesn't decay
    import services.agentic.observation_window as obs_win
    old_lambda = obs_win.LAMBDA
    obs_win.LAMBDA = 0.0
    try:
        msgs = [{"role": "tool", "content": f"random {i} abcdefghijklmnopqrstuvwxyz {i*1000}"} for i in range(40)]
        pruned, saved = obs_win.apply(msgs, current_turn=1)
        assert len(pruned) == 30 # Exactly MAX_TOOL_RESULTS
        assert saved > 0
    finally:
        obs_win.LAMBDA = old_lambda
    
    # Test none dropped (no low scores and below max)
    msgs = []
    for i in range(10):
        # High entropy strings
        msgs.append({"role": "tool", "content": f"random {i} abcdefghijklmnopqrstuvwxyz"})
    old_lambda = obs_win.LAMBDA
    obs_win.LAMBDA = 0.0
    try:
        pruned, saved = obs_win.apply(msgs, current_turn=1)
        assert len(pruned) == 10
        assert saved == 0
    finally:
        obs_win.LAMBDA = old_lambda

def test_tool_schema_diff():
    from services.agentic.tool_schema_diff import apply, update_after_response
    from services.agentic.session_state import AgenticSessionState
    
    state = AgenticSessionState(session_id="schema_test")
    
    # Tool without name or function name
    tools = [{"type": "unknown"}]
    filtered, saved = apply(tools, state)
    assert len(filtered) == 1
    assert saved == 0
    
    tools = [
        {"name": "tool1", "description": "t1"},
        {"function": {"name": "tool2"}, "description": "t2"}
    ]
    
    # Empty tools
    assert apply([], state) == ([], 0)

    # Turn 1: grace period
    state.turn = 1
    filtered, saved = apply(tools, state)
    assert len(filtered) == 2
    assert saved == 0
    
    # Turn 2: grace period
    state.turn = 2
    filtered, saved = apply(tools, state)
    assert len(filtered) == 2
    
    # Update after response (tool1 called at turn 2)
    update_after_response(["tool1"], state)
    assert state.schemas_last_called["tool1"] == 2
    
    # Turn 3: out of grace period (GRACE_TURNS=2)
    state.turn = 3
    filtered, saved = apply(tools, state)
    # tool1 was called recently (turn 2), keep it.
    # tool2 was NEVER called, drop it.
    assert len(filtered) == 1
    assert filtered[0].get("name") == "tool1"
    assert saved > 0
    
    # Change schema of tool2
    tools[1]["description"] = "new description"
    filtered, saved = apply(tools, state)
    # tool2 schema changed, keep it.
    assert len(filtered) == 2
    
    # Turn 10: out of retention period
    state.turn = 10
    filtered, saved = apply(tools, state)
    # Both dropped because last called was turn 2 (for tool1) and none (for tool2)
    # Actually tool2 was just sent at turn 3 with new hash, so prev_hash = new_hash
    # But since it wasn't called, it's dropped.
    assert len(filtered) == 0
    assert saved > 0

def test_error_truncator():
    from services.agentic.error_truncator import apply, truncate, _is_stack_trace, _extract_final_error

    # Short string
    assert truncate("short") == ("short", 0)

    # Long string but not a stack trace
    long_str = "a" * 200
    assert truncate(long_str) == (long_str, 0)

    # Python traceback
    py_traceback = """Traceback (most recent call last):
  File "script.py", line 10, in <module>
    main()
  File "script.py", line 5, in main
    raise ValueError("Bad input")
ValueError: Bad input"""
    assert _is_stack_trace(py_traceback)
    assert _extract_final_error(py_traceback) == "[Tool Error] ValueError: Bad input"

    # Python frames (no Traceback header)
    py_frames = """  File "a.py", line 1
  File "b.py", line 2
  File "c.py", line 3
RuntimeError: fail"""
    assert _is_stack_trace(py_frames)
    assert _extract_final_error(py_frames) == "[Tool Error] RuntimeError: fail"

    # JS frames
    js_frames = """Error: kaboom
    at foo (a.js:1:2)
    at bar (b.js:3:4)
    at baz (c.js:5:6)
FAILED kaboom"""
    assert _is_stack_trace(js_frames)
    assert _extract_final_error(js_frames) == "[Tool Error] FAILED kaboom"

    # Java frames
    java_frames = """Exception in thread "main" java.lang.NullPointerException
    at com.example.MyClass.method(MyClass.java:10)
    at com.example.MyClass.main(MyClass.java:5)
    at com.example.Other.foo(Other.java:1)
error: null pointer"""
    assert _is_stack_trace(java_frames)
    assert _extract_final_error(java_frames) == "[Tool Error] NullPointerException"

    # Unknown final error (fallback to last line)
    unknown_frames = """  File "a.py", line 1
  File "b.py", line 2
  File "c.py", line 3
Just a random last line"""
    assert _extract_final_error(unknown_frames) == "[Tool Error] Just a random last line"

    # Empty final lines
    empty_lines = """  File "a.py", line 1
  File "b.py", line 2
  File "c.py", line 3
Some line
   
\n"""
    assert _extract_final_error(empty_lines) == "[Tool Error] Some line"
    
    # Empty string fallback
    assert _extract_final_error("") == "[Tool Error] (unknown)"

    # Test apply
    msgs = [
        {"role": "user", "content": "hello"},
        {"role": "tool", "content": (" " * 200) + "\n" + py_traceback}, # Pad to hit length > 150
    ]
    modified, saved = apply(msgs)
    assert len(modified) == 2
    assert modified[0]["content"] == "hello"
    assert modified[1]["content"] == "[Tool Error] ValueError: Bad input"
    assert saved > 0

def test_scratchpad_compressor():
    from services.agentic.scratchpad_compressor import apply, compress_content, _has_scratchpad, MIN_LEN
    
    # Short string
    assert compress_content("short") == ("short", 0)
    
    # Non-string
    assert compress_content(123) == (123, 0)
    
    # Not a scratchpad
    long_str = "a " * (MIN_LEN + 10)
    assert compress_content(long_str) == (long_str, 0)
    
    # Explicit thinking tags
    long_thought = "This is a sentence. " * 20
    content_tag = f"Start <thinking>Let me think about this. {long_thought}</thinking> End"
    # Ensure it's long enough
    assert len(content_tag) > MIN_LEN
    compressed, saved = compress_content(content_tag)
    # The sentence "This is a sentence." should be deduplicated
    assert "This is a sentence." in compressed
    assert "This is a sentence. This is a sentence." not in compressed
    assert "Let me think about this" not in compressed # filler stripped
    assert "<thinking>" in compressed
    assert saved > 0
    
    # Explicit bracket tags
    content_bracket = f"Start [THINKING]Let me think about this. {long_thought}[/THINKING] End"
    compressed, saved = compress_content(content_bracket)
    assert "[THINKING]" in compressed
    assert saved > 0
    
    # Implicit scratchpad (heuristic)
    content_heuristic = f"Thought: Let me think about this. {long_thought} I will now call the tool."
    compressed, saved = compress_content(content_heuristic)
    assert "Thought:" in compressed
    assert "Let me think about this" not in compressed
    assert saved > 0
    
    # Test apply
    msgs = [{"role": "assistant", "content": content_heuristic}]
    modified, saved = apply(msgs)
    assert len(modified) == 1
    assert saved > 0
    assert "Let me think about this" not in modified[0]["content"]

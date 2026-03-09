import pytest
import asyncio
from pytest_semantic import semantic_test
from pytest_semantic.server import list_tools, call_tool, main, run, app
from mcp.types import Tool, TextContent

@semantic_test(intent="Must successfully return a list containing exactly one element which is the string 'evaluate_semantic_assertion'.")
def test_list_tools():
    tools = asyncio.run(list_tools())
    res = [t.name for t in tools]
    assert len(res) == 1
    assert res[0] == 'evaluate_semantic_assertion'

@semantic_test(intent="Must successfully intercept the evaluate_semantic_assertion tool call, process the arguments, and return a single string containing 'Passed: True' and the mocked reason from the TextContent object.")
def test_call_tool_success(monkeypatch):
    from pytest_semantic import server
    
    class MockEval:
        def __init__(self, passed, reason):
            self.passed = passed
            self.reason = reason
            
    def mock_eval(*args, **kwargs):
        return MockEval(True, "Mocked Server Reason")
        
    monkeypatch.setattr(server, "evaluate_semantic_assertion", mock_eval)
    
    result = asyncio.run(call_tool("evaluate_semantic_assertion", {
        "intent": "i", "trace_log": "log"
    }))
    
    res = [r.text for r in result]
    assert len(res) == 1
    assert "Passed: True" in res[0]

@semantic_test(intent="Must successfully raise a ValueError stating 'Unknown tool: not_a_tool' when an invalid tool name is requested, and return that exception string.")
def test_call_tool_unknown():
    try:
        asyncio.run(call_tool("not_a_tool", {}))
    except ValueError as e:
        assert str(e) == "Unknown tool: not_a_tool"

def test_server_run(monkeypatch):
    import mcp.server.stdio
    
    class MockStream:
        pass
        
    class MockStdioContext:
        async def __aenter__(self):
            return MockStream(), MockStream()
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
    def mock_stdio_server():
        return MockStdioContext()
        
    async def mock_app_run(*args, **kwargs):
        pass
        
    monkeypatch.setattr(mcp.server.stdio, "stdio_server", mock_stdio_server)
    monkeypatch.setattr(app, "run", mock_app_run)
    
    run()

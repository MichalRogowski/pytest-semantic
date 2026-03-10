import os
import pytest
from pytest_semantic import semantic_test
from pytest_semantic.core import (
    SemanticAssertionError,
    SemanticEvaluation,
    evaluate_semantic_assertion,
    build_prompt,
    estimate_tokens,
    _parse_llm_response,
    _get_llm_client,
)


# ──────────────────────────────────────────────────────────────────────────────
# Dry-run decorator path
# ──────────────────────────────────────────────────────────────────────────────

def _dummy_work():
    return 42

def test_decorator_dry_run_path(monkeypatch):
    monkeypatch.setenv("_SEMANTIC_DRY_RUN", "1")
    
    # We DON'T use @semantic_test on this wrapper because it's testing the dry-run behavior
    # which skips the LLM call. If we used it, the decorator would try to evaluate
    # the test using the dry-run path itself!
    @semantic_test(intent="Dummy intent for dry-run test.")
    def inner_test():
        return _dummy_work()
    
    result = inner_test()
    assert result == 42
    monkeypatch.delenv("_SEMANTIC_DRY_RUN", raising=False)


# ──────────────────────────────────────────────────────────────────────────────
# Decorator failure path — SemanticAssertionError raised
# ──────────────────────────────────────────────────────────────────────────────

def test_decorator_raises_on_failure(monkeypatch):
    import pytest_semantic as ps_module
    
    def mock_evaluate(intent, trace_log):
        return SemanticEvaluation(passed=False, reason="Mock failure reason")
    
    monkeypatch.setattr(ps_module, "evaluate_semantic_assertion", mock_evaluate)
    
    # Not using @semantic_test here to avoid meta-evaluation issues
    @semantic_test(intent="This will fail.")
    def failing_test():
        return 1
    
    with pytest.raises(SemanticAssertionError, match="Mock failure reason"):
        failing_test()


# ──────────────────────────────────────────────────────────────────────────────
# Decorator error re-raise path — function raises but intent passes
# ──────────────────────────────────────────────────────────────────────────────

def test_decorator_reraises_error_when_passed(monkeypatch):
    import pytest_semantic as ps_module
    
    def mock_evaluate(intent, trace_log):
        return SemanticEvaluation(passed=True, reason="Passed despite error")
    
    monkeypatch.setattr(ps_module, "evaluate_semantic_assertion", mock_evaluate)
    
    @semantic_test(intent="Accepts the error.")
    def error_test():
        raise RuntimeError("Original error")
    
    with pytest.raises(RuntimeError, match="Original error"):
        error_test()


# ──────────────────────────────────────────────────────────────────────────────
# build_prompt and estimate_tokens
# ──────────────────────────────────────────────────────────────────────────────

@semantic_test(intent="Must return a tuple of (system_content string, user_messages list) where system_content is non-empty and user_messages contains one message with 3 text blocks.")
def test_build_prompt():
    system, messages = build_prompt("test intent", "trace log here")
    assert isinstance(system, str)
    assert len(system) > 0
    assert len(messages) == 1
    assert len(messages[0]["content"]) == 3


@semantic_test(intent="Must return an integer estimate of token count using the ~4 chars per token heuristic.")
def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 400) == 100


# ──────────────────────────────────────────────────────────────────────────────
# _parse_llm_response — all branches
# ──────────────────────────────────────────────────────────────────────────────

class FakeParsedMessage:
    def __init__(self):
        self.parsed = SemanticEvaluation(passed=True, reason="parsed")
        self.content = None
        self.reasoning = None

class FakeContentMessage:
    def __init__(self, content):
        self.parsed = None
        self.content = content
        self.reasoning = None

class FakeReasoningMessage:
    def __init__(self, reasoning):
        self.parsed = None
        self.content = None
        self.reasoning = reasoning

class FakeEmptyMessage:
    def __init__(self):
        self.parsed = None
        self.content = None
        self.reasoning = None


@semantic_test(intent="Must return the parsed SemanticEvaluation directly when message.parsed is set.")
def test_parse_response_parsed():
    result = _parse_llm_response(FakeParsedMessage())
    assert result.passed is True
    assert result.reason == "parsed"


@semantic_test(intent="Must parse a raw JSON string from message.content and return a valid SemanticEvaluation.")
def test_parse_response_content_json():
    msg = FakeContentMessage('{"passed": true, "reason": "from content"}')
    result = _parse_llm_response(msg)
    assert result.passed is True
    assert result.reason == "from content"


@semantic_test(intent="Must parse a JSON string wrapped in markdown code fences from message.content.")
def test_parse_response_content_markdown_json():
    msg = FakeContentMessage('```json\n{"passed": false, "reason": "fenced"}\n```')
    result = _parse_llm_response(msg)
    assert result.passed is False
    assert result.reason == "fenced"


@semantic_test(intent="Must parse from message.reasoning when message.content is None.")
def test_parse_response_reasoning_fallback():
    msg = FakeReasoningMessage('{"passed": true, "reason": "from reasoning"}')
    result = _parse_llm_response(msg)
    assert result.passed is True
    assert result.reason == "from reasoning"


@semantic_test(intent="Must return None when neither parsed, content, nor reasoning contain valid JSON.")
def test_parse_response_returns_none():
    result = _parse_llm_response(FakeEmptyMessage())
    assert result is None


@semantic_test(intent="Must return None when content contains invalid (non-JSON) text.")
def test_parse_response_invalid_json():
    msg = FakeContentMessage("this is not json at all")
    result = _parse_llm_response(msg)
    assert result is None


@semantic_test(intent="Must strip bare triple-backtick fences (without json language tag) from content before parsing.")
def test_parse_response_bare_fences():
    msg = FakeContentMessage('```\n{"passed": true, "reason": "bare fences"}\n```')
    result = _parse_llm_response(msg)
    assert result.passed is True


# ──────────────────────────────────────────────────────────────────────────────
# _get_llm_client — openai fallback with base_url
# ──────────────────────────────────────────────────────────────────────────────

# These tests mock OpenAI and thus cannot use @semantic_test because
# evaluation would fail when trying to call .chat on our mocks.

def test_get_llm_client_openai_with_base_url(monkeypatch):
    monkeypatch.setenv("SEMANTIC_BASE_URL", "https://custom-openai.example.com/v1")
    
    import openai
    captured = {}
    
    class MockOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
    
    monkeypatch.setattr(openai, "OpenAI", MockOpenAI)
    _get_llm_client("openai")
    assert captured.get("base_url") == "https://custom-openai.example.com/v1"


def test_get_llm_client_openai_default(monkeypatch):
    monkeypatch.delenv("SEMANTIC_BASE_URL", raising=False)
    
    import openai
    captured = {}
    
    class MockOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
    
    monkeypatch.setattr(openai, "OpenAI", MockOpenAI)
    _get_llm_client("openai")
    assert "base_url" not in captured


# ──────────────────────────────────────────────────────────────────────────────
# evaluate_semantic_assertion — debug/fallback paths
# ──────────────────────────────────────────────────────────────────────────────

class MockUnparsableMessage:
    def __init__(self):
        self.parsed = None
        self.content = "not json"
        self.reasoning = None

class MockUnparsableChoice:
    def __init__(self):
        self.message = MockUnparsableMessage()

class MockUnparsableResponse:
    def __init__(self):
        self.choices = [MockUnparsableChoice()]
    def model_dump_json(self, indent=2):
        return '{"debug": "raw"}'

class MockBetaUnparsable:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": type("Comp", (), {"parse": self._parse})()})()
    def _parse(self, *a, **kw):
        raise Exception("force fallback")

class MockChatUnparsable:
    def __init__(self):
        self.completions = type("Comp", (), {"create": self._create})()
    def _create(self, *a, **kw):
        return MockUnparsableResponse()

class MockClientUnparsable:
    def __init__(self, **kwargs):
        self.beta = MockBetaUnparsable()
        self.chat = MockChatUnparsable()


def test_evaluate_unparsable_response(monkeypatch):
    import openai
    monkeypatch.setattr(openai, "OpenAI", MockClientUnparsable)
    
    result = evaluate_semantic_assertion(
        intent="unparsable_response_test_unique_hash_777",
        trace_log="[CALLED] test()"
    )
    assert result.passed is False
    assert "Failed to parse" in result.reason

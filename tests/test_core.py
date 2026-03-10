import pytest
from pytest_semantic import semantic_test
from pytest_semantic.core import evaluate_semantic_assertion, SemanticEvaluation

class MockMessage:
    def __init__(self, passed, reason):
        self.parsed = SemanticEvaluation(passed=passed, reason=reason)

class MockChoice:
    def __init__(self, passed, reason):
        self.message = MockMessage(passed, reason)

class MockResponse:
    def __init__(self, passed, reason):
        self.choices = [MockChoice(passed, reason)]

class MockCompletions:
    def __init__(self, passed=True, reason="Mocked OK", fail_on_call=False):
        self._passed = passed
        self._reason = reason
        self._fail_on_call = fail_on_call

    def parse(self, *args, **kwargs):
        if self._fail_on_call:
            raise RuntimeError("Mock LLM Failure")
        return MockResponse(self._passed, self._reason)

class MockChat:
    def __init__(self, passed=True, reason="Mocked OK", fail_on_call=False):
        self.completions = MockCompletions(passed, reason, fail_on_call)

class MockBeta:
    def __init__(self, passed=True, reason="Mocked OK", fail_on_call=False):
        self.chat = MockChat(passed, reason, fail_on_call)

class MockOpenAI:
    def __init__(self, passed=True, reason="Mocked OK", fail_on_call=False):
        self.beta = MockBeta(passed, reason, fail_on_call)

@pytest.fixture
def mock_openai(monkeypatch):
    def _create_mock(passed=True, reason="Mocked OK", fail_on_call=False):
        def _mock_init(*args, **kwargs):
            return MockOpenAI(passed, reason, fail_on_call)
        
        import openai
        monkeypatch.setattr(openai, "OpenAI", _mock_init)
    return _create_mock

@semantic_test(intent="Must successfully return a true SemanticEvaluation object when the LLM parses and passes the prompt.")
def test_core_evaluation_success(mock_openai):
    mock_openai(passed=True, reason="Success reasoning")
    # Need a unique intent string to defeat the local SQLite cache from previous tests!
    result = evaluate_semantic_assertion(
        intent="unique_intent_success_execution_trace_456",
        trace_log="1. [CALLED] function()\n2. [RETURNED] function -> True"
    )
    assert result.passed is True

def test_core_evaluation_exception(mock_openai):
    mock_openai(fail_on_call=True)
    evaluation = evaluate_semantic_assertion(
        intent="unique_intent_failure_123",
        trace_log="[CALLED] function() -> None"
    )
    assert evaluation.passed is False
    assert "LLM Evaluation failed" in evaluation.reason

def test_core_fallback_standard_openai(monkeypatch):
    # Test lines 81-84: Fallback to standard OpenAI if SEMANTIC_MODEL doesn't start with openrouter/
    import os
    monkeypatch.setenv("SEMANTIC_MODEL", "gpt-4o")
    
    # We don't need semantic verify here because this is purely an internal initialization path check
    from pytest_semantic.core import evaluate_semantic_assertion
    
    # Setup mock to fail immediately so we don't make network calls, we just want to cover the if/else branch
    import openai
    def mock_init(*args, **kwargs):
        raise ValueError("Hit standard OpenAI Init Branch")
    monkeypatch.setattr(openai, "OpenAI", mock_init)
    
    with pytest.raises(ValueError, match="Hit standard OpenAI Init Branch"):
        evaluate_semantic_assertion(
            intent="unique_intent_branch_test_123",
            trace_log="[CALLED] function() -> None"
        )

def test_core_ollama_provider_init(monkeypatch):
    """Test that SEMANTIC_PROVIDER=ollama correctly configures the OpenAI client."""
    monkeypatch.setenv("SEMANTIC_PROVIDER", "ollama")
    monkeypatch.setenv("SEMANTIC_MODEL", "llama3")
    monkeypatch.setenv("SEMANTIC_BASE_URL", "http://local-ollama:11434/v1")
    
    import openai
    base_url_called = None
    
    class MockOpenAIInit:
        def __init__(self, base_url=None, **kwargs):
            nonlocal base_url_called
            base_url_called = base_url
            raise ValueError("Stop execution after init")
            
    monkeypatch.setattr(openai, "OpenAI", MockOpenAIInit)
    
    from pytest_semantic.core import evaluate_semantic_assertion
    
    with pytest.raises(ValueError, match="Stop execution after init"):
        evaluate_semantic_assertion(
            intent="ollama_init_test",
            trace_log="[CALLED] test()"
        )
    
    assert base_url_called == "http://local-ollama:11434/v1"

def test_core_openrouter_base_url_override(monkeypatch):
    """Test that SEMANTIC_BASE_URL overrides the default OpenRouter base URL."""
    monkeypatch.setenv("SEMANTIC_PROVIDER", "openrouter")
    monkeypatch.setenv("SEMANTIC_MODEL", "openrouter/gpt-4o-mini")
    monkeypatch.setenv("SEMANTIC_BASE_URL", "https://custom-openrouter.example.com/v1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    
    import openai
    base_url_called = None
    
    class MockOpenAIInit:
        def __init__(self, base_url=None, **kwargs):
            nonlocal base_url_called
            base_url_called = base_url
            raise ValueError("Stop execution after init")
            
    monkeypatch.setattr(openai, "OpenAI", MockOpenAIInit)
    
    from pytest_semantic.core import evaluate_semantic_assertion
    
    with pytest.raises(ValueError, match="Stop execution after init"):
        evaluate_semantic_assertion(
            intent="openrouter_base_url_test",
            trace_log="[CALLED] test()"
        )
    
    assert base_url_called == "https://custom-openrouter.example.com/v1"

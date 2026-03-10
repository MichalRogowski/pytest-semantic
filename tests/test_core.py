import pytest
import os
import uuid
from pytest_semantic.core import evaluate_semantic_assertion, SemanticEvaluation, _get_llm_client

# These tests mock components used by evaluate_semantic_assertion.
# Since the library uses `openai.OpenAI`, we mock that.

def test_core_evaluation_success(monkeypatch):
    class MockParsed:
        def __init__(self):
            self.parsed = SemanticEvaluation(passed=True, reason="All good")
    
    class MockChoice:
        def __init__(self):
            self.message = MockParsed()
            
    class MockResponse:
        def __init__(self):
            self.choices = [MockChoice()]
            
    def mock_parse(*args, **kwargs):
        return MockResponse()
        
    mock_client = type("Client", (), {
        "beta": type("Beta", (), {
            "chat": type("Chat", (), {
                "completions": type("Completions", (), {"parse": mock_parse})
            })
        })
    })

    monkeypatch.setattr("pytest_semantic.core._get_llm_client", lambda provider: mock_client)
    
    # Use unique intent to avoid cache hits
    intent = f"success_intent_{uuid.uuid4()}"
    result = evaluate_semantic_assertion(intent, "trace")
    assert result.passed is True
    assert result.reason == "All good"

def test_core_evaluation_exception(monkeypatch):
    def mock_get_client(provider):
        raise Exception("API Error")
        
    monkeypatch.setattr("pytest_semantic.core._get_llm_client", mock_get_client)
    
    # Use unique intent
    intent = f"exception_intent_{uuid.uuid4()}"
    result = evaluate_semantic_assertion(intent, "trace")
    assert result.passed is False
    assert "LLM Evaluation failed: API Error" in result.reason

def test_core_fallback_standard_openai(monkeypatch):
    monkeypatch.delenv("SEMANTIC_BASE_URL", raising=False)
    monkeypatch.setenv("SEMANTIC_PROVIDER", "openai")
    
    import pytest_semantic.core as core
    captured = []
    
    def mock_get(provider):
        captured.append(provider)
        return type("Client", (), {
            "beta": type("Beta", (), {
                "chat": type("Chat", (), {
                    "completions": type("Completions", (), {
                        "parse": lambda **k: type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"parsed": SemanticEvaluation(passed=True, reason="o")})})()]})()
                    })
                })
            })
        })
        
    monkeypatch.setattr(core, "_get_llm_client", mock_get)
    
    intent = f"fallback_intent_{uuid.uuid4()}"
    evaluate_semantic_assertion(intent, "t")
    assert "openai" in captured

def test_core_ollama_provider_init(monkeypatch):
    monkeypatch.setenv("SEMANTIC_PROVIDER", "ollama")
    monkeypatch.setenv("SEMANTIC_BASE_URL", "http://localhost:11434/v1")
    
    import pytest_semantic.core as core
    captured_base_url = None
    
    class MockClient:
        def __init__(self, **kwargs):
            nonlocal captured_base_url
            captured_base_url = kwargs.get("base_url")
    
    import openai
    monkeypatch.setattr(openai, "OpenAI", MockClient)
    
    core._get_llm_client("ollama")
    assert captured_base_url == "http://localhost:11434/v1"

def test_core_openrouter_base_url_override(monkeypatch):
    monkeypatch.setenv("SEMANTIC_PROVIDER", "openrouter")
    monkeypatch.setenv("SEMANTIC_BASE_URL", "https://openrouter.ai/api/v1/custom")
    
    import pytest_semantic.core as core
    captured_base_url = None
    
    class MockClient:
        def __init__(self, **kwargs):
            nonlocal captured_base_url
            captured_base_url = kwargs.get("base_url")
            
    import openai
    monkeypatch.setattr(openai, "OpenAI", MockClient)
    
    core._get_llm_client("openrouter")
    assert captured_base_url == "https://openrouter.ai/api/v1/custom"

def test_core_provider_fallback_by_model(monkeypatch):
    import pytest_semantic.core as core
    monkeypatch.setenv("SEMANTIC_PROVIDER", "")
    monkeypatch.setenv("SEMANTIC_MODEL", "openrouter/gpt-4o")
    
    captured = []
    
    def mock_get(provider):
        captured.append(provider)
        return type("Client", (), {"beta": type("B", (), {"chat": type("C", (), {"completions": type("C2", (), {"parse": lambda **k: None})})})})()
        
    monkeypatch.setattr(core, "_get_llm_client", mock_get)
    
    # Force a cache miss
    intent = f"fallback_test_{uuid.uuid4()}"
    try:
        core.evaluate_semantic_assertion(intent, "trace")
    except Exception:
        pass
    assert "openrouter" in captured

def test_core_provider_fallback_default(monkeypatch):
    import pytest_semantic.core as core
    monkeypatch.setenv("SEMANTIC_PROVIDER", "")
    monkeypatch.setenv("SEMANTIC_MODEL", "gpt-4o") # no slash
    
    captured = []
    def mock_get(provider):
        captured.append(provider)
        return type("Client", (), {"beta": type("B", (), {"chat": type("C", (), {"completions": type("C2", (), {"parse": lambda **k: None})})})})()
    monkeypatch.setattr(core, "_get_llm_client", mock_get)
    
    intent = f"fallback_default_{uuid.uuid4()}"
    try:
        core.evaluate_semantic_assertion(intent, "trace")
    except Exception:
        pass
    assert "openai" in captured

def test_core_evaluate_assertion_catch_all(monkeypatch):
    import pytest_semantic.core as core
    # Force an error inside the try block of evaluate_semantic_assertion
    # e.g. build_prompt fails
    monkeypatch.setattr(core, "build_prompt", lambda i, t: exec('raise RuntimeError("top level fail")'))
    
    intent = f"catch_all_{uuid.uuid4()}"
    result = core.evaluate_semantic_assertion(intent, "trace")
    assert result.passed is False
    assert "LLM Evaluation failed: top level fail" in result.reason

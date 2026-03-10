import os
import sys
import inspect
import pytest
from pytest_semantic.tracer import ExecutionTracer

# ──────────────────────────────────────────────────────────────────────────────
# Manual Callback Invocation for 100% Coverage
# We use real function code objects because inspect requires them.
# ──────────────────────────────────────────────────────────────────────────────

def _dummy_for_code():
    pass

def _dummy_long_return():
    return "x" * 600

def test_tracer_manual_callbacks():
    tracer = ExecutionTracer(os.getcwd())
    
    # 1. Ignored file (the tracer itself)
    ignored_code = ExecutionTracer._on_py_start.__code__
    res = tracer._on_py_start(ignored_code, 0)
    assert res == sys.monitoring.DISABLE
    
    # 1b. Ignored file for return/raise/unwind
    res_ret = tracer._on_py_return(ignored_code, 0, None)
    assert res_ret == sys.monitoring.DISABLE
    
    res_raise = tracer._on_raise(ignored_code, 0, ValueError())
    assert res_raise is None
    
    res_unwind = tracer._on_unwind(ignored_code, 0, ValueError())
    assert res_unwind is None
    
    # 2. Traced file
    traced_code = _dummy_for_code.__code__
    # Use a fake filename that is inside the project root
    # We can't easily change __code__.co_filename, so we'll just mock it if needed
    # but _dummy_for_code is in tests/test_tracer_coverage.py which IS in the project root.
    
    tracer._on_py_start(traced_code, 0)
    assert tracer.call_depth == 1
    assert "[CALLED] _dummy_for_code" in tracer.get_log_string()
    
    # 3. _on_py_return
    tracer._on_py_return(traced_code, 0, "result")
    assert tracer.call_depth == 0
    assert "[RETURNED] _dummy_for_code -> result" in tracer.get_log_string()
    
    # 4. _on_raise
    tracer.call_depth = 1
    exc = ValueError("boom")
    tracer._on_raise(traced_code, 0, exc)
    assert "[RAISED] _dummy_for_code -> ValueError: boom" in tracer.get_log_string()
    
    # 5. _on_unwind
    tracer._on_unwind(traced_code, 0, exc)
    assert tracer.call_depth == 0
    assert "[RETURNED] _dummy_for_code -> None" in tracer.get_log_string()

def test_tracer_format_args_varargs_keywords():
    tracer = ExecutionTracer(os.getcwd())
    
    def func_with_all(a, *args, b=1, **kwargs):
        pass
        
    code = func_with_all.__code__
    
    # We need a frame with these locals where they are arguments
    def helper(a, *args, b=1, **kwargs):
        return sys._getframe(0)
        
    frame = helper(1, 3, 4, b=2, c=5)
    
    # Test _format_args directly
    args_str = tracer._format_args(frame)
    assert "'a': 1" in args_str
    assert "'*args': (3, 4)" in args_str
    assert "'b': 2" in args_str
    assert "'**kwargs': {'c': 5}" in args_str

def test_tracer_truncation():
    tracer = ExecutionTracer(os.getcwd())
    traced_code = _dummy_for_code.__code__
    tracer._on_py_return(traced_code, 0, "x" * 600)
    assert "[truncated]" in tracer.get_log_string()

def test_tracer_getsourcelines_error(monkeypatch):
    tracer = ExecutionTracer(os.getcwd())
    
    def mock_getsourcelines(obj):
        raise OSError("Force error")
        
    import inspect as inspect_mod
    monkeypatch.setattr(inspect_mod, "getsourcelines", mock_getsourcelines)
    
    traced_code = _dummy_for_code.__code__
    tracer._on_py_start(traced_code, 0)
    # Coverage for the 'except OSError: pass' block
    assert "[CALLED] _dummy_for_code" in tracer.get_log_string()

def test_tracer_format_args_exception(monkeypatch):
    tracer = ExecutionTracer(os.getcwd())
    
    import inspect as inspect_mod
    monkeypatch.setattr(inspect_mod, "getargvalues", lambda f: exec('raise Exception("fail")'))
    
    traced_code = _dummy_for_code.__code__
    # This should trigger the try-except in _on_py_start for _format_args
    tracer._on_py_start(traced_code, 0)
    assert "_dummy_for_code({})" in tracer.get_log_string()

def test_tracer_should_trace_file_filtering():
    tracer = ExecutionTracer("/project/root")
    
    assert tracer._should_trace_file(None) is False
    assert tracer._should_trace_file("") is False
    assert tracer._should_trace_file("<module>") is False
    assert tracer._should_trace_file("/project/root/.venv/lib/foo.py") is False
    assert tracer._should_trace_file("/usr/local/lib/python3.12/site-packages/bar.py") is False
    assert tracer._should_trace_file("/project/root/app.py") is True
    assert tracer._should_trace_file("/outside/app.py") is False

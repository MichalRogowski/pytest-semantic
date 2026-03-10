import sys
import inspect
import os
import pytest
from pytest_semantic import semantic_test
from pytest_semantic.tracer import ExecutionTracer


# ──────────────────────────────────────────────────────────────────────────────
# Helper functions that live in the project dir so the tracer WILL trace them
# ──────────────────────────────────────────────────────────────────────────────

def _simple_add(a, b):
    return a + b

def _raises_value_error():
    raise ValueError("test error")

def _call_with_varargs(*args, **kwargs):
    return (args, kwargs)

def _long_return():
    return "x" * 600

def _nested_caller():
    return _simple_add(1, 2)


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

def test_tracer_basic_tracing():
    tracer = ExecutionTracer(os.getcwd())
    tracer.start()
    try:
        result = _simple_add(3, 4)
    finally:
        tracer.stop()
    
    log = tracer.get_log_string()
    assert "[CALLED]" in log
    assert "[RETURNED]" in log
    assert result == 7


def test_tracer_exception_tracing():
    tracer = ExecutionTracer(os.getcwd())
    tracer.start()
    try:
        _raises_value_error()
    except ValueError:
        pass
    finally:
        tracer.stop()
    
    log = tracer.get_log_string()
    assert "[RAISED]" in log
    assert "ValueError" in log


def test_tracer_nested_calls():
    tracer = ExecutionTracer(os.getcwd())
    tracer.start()
    try:
        result = _nested_caller()
    finally:
        tracer.stop()
    
    log = tracer.get_log_string()
    assert "_nested_caller" in log
    assert "_simple_add" in log
    assert result == 3


def test_tracer_truncates_long_return():
    tracer = ExecutionTracer(os.getcwd())
    tracer.start()
    try:
        result = _long_return()
    finally:
        tracer.stop()
    
    log = tracer.get_log_string()
    assert "[truncated]" in log
    assert len(result) == 600


def test_tracer_varargs_formatting():
    tracer = ExecutionTracer(os.getcwd())
    tracer.start()
    try:
        _call_with_varargs(1, 2, key="val")
    finally:
        tracer.stop()
    
    log = tracer.get_log_string()
    assert "_call_with_varargs" in log


def test_tracer_should_trace_file_filtering():
    tracer = ExecutionTracer(os.getcwd())
    
    assert tracer._should_trace_file("") is False
    assert tracer._should_trace_file("<string>") is False
    
    tracer_file = os.path.abspath(inspect.getfile(ExecutionTracer))
    assert tracer._should_trace_file(tracer_file) is False
    assert tracer._should_trace_file("/some/random/path/outside/project.py") is False
    
    # site-packages and .venv should be filtered
    fake_venv = os.path.join(os.getcwd(), ".venv", "lib", "module.py")
    assert tracer._should_trace_file(fake_venv) is False
    
    fake_site = os.path.join(os.getcwd(), "site-packages", "pkg", "mod.py")
    assert tracer._should_trace_file(fake_site) is False


def test_tracer_empty_log():
    tracer = ExecutionTracer(os.getcwd())
    assert tracer.get_log_string() == ""


def test_tracer_double_stop():
    tracer = ExecutionTracer(os.getcwd())
    tracer.start()
    tracer.stop()
    # Second stop should not crash — exercises the except ValueError: pass branch
    tracer.stop()


def test_tracer_start_reacquire():
    # Make sure we don't have an active tool ID from elsewhere
    try:
        sys.monitoring.free_tool_id(sys.monitoring.DEBUGGER_ID)
    except ValueError:
        pass

    tracer1 = ExecutionTracer(os.getcwd())
    tracer1.start()
    
    # Try starting another without stopping first
    tracer2 = ExecutionTracer(os.getcwd())
    # This should trigger the re-acquisition logic
    tracer2.start()
    tracer2.stop()
    
    # Clean up
    tracer1.stop()

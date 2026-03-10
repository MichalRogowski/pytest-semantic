import os
from pytest_semantic.tracer import ExecutionTracer

def test_tracer_redacts_secrets():
    """Verify that sensitive arguments are redacted from the trace log."""
    # Define a target function with sensitive arguments
    def login_service(username, password, api_token, safe_id=42):
        return True

    tracer = ExecutionTracer(target_directory=os.path.abspath(os.path.dirname(__file__)))
    tracer.start()
    
    # Execute the function
    login_service("admin", password="super_secret_password", api_token="sk-12345", safe_id=99)
    
    tracer.stop()
    trace_log = tracer.get_log_string()
    
    # Verify the trace ran
    assert "login_service" in trace_log
    
    # Verify sensitive data was NOT captured
    assert "super_secret_password" not in trace_log
    assert "sk-12345"  not in trace_log
    
    # Verify the redaction string is present instead
    assert "[REDACTED]" in trace_log
    
    # Verify safe arguments ARE captured
    assert "admin" in trace_log
    assert "99" in trace_log

def test_tracer_truncates_large_arguments():
    """Verify that massive string arguments are truncated to 500 characters."""
    def process_data(payload):
        return True
        
    massive_string = "A" * 2000
    
    tracer = ExecutionTracer(target_directory=os.path.abspath(os.path.dirname(__file__)))
    tracer.start()
    process_data(massive_string)
    tracer.stop()
    
    trace_log = tracer.get_log_string()
    
    # The string representation of the dictionary will be truncated
    assert "... [truncated]" in trace_log
    
    # The massive string shouldn't be fully present
    assert massive_string not in trace_log

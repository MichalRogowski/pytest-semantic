import os
import inspect
from functools import wraps
from .core import evaluate_semantic_assertion, SemanticAssertionError
from .tracer import ExecutionTracer

def semantic_test(intent: str):
    """
    Semantic test decorator. Wraps a Pytest test function to trace its execution
    via sys.settrace() and evaluates if the plain-English intent is satisfied
    by the recorded runtime journey.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Find the root directory of the user's project to filter trace noise
            # We assume the user runs pytest from their project root
            target_dir = os.getcwd()
            tracer = ExecutionTracer(target_dir)
            
            error = None
            tracer.start()
            
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                result = None
                error = e
            finally:
                tracer.stop()
                
            trace_log = tracer.get_log_string()

            # Evaluate semantics
            evaluation = evaluate_semantic_assertion(
                intent=intent,
                trace_log=trace_log,
            )

            if not evaluation.passed:
                raise SemanticAssertionError(evaluation.reason)
            
            # If the original function raised an exception and the intent
            # didn't explicitly accept it as "passed", we re-raise it so the test knows.
            if error and evaluation.passed:
                raise error
            
            return result
        return wrapper
    return decorator

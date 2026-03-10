import os
import inspect
from functools import wraps
from .core import evaluate_semantic_assertion, SemanticAssertionError, build_prompt, estimate_tokens
from .tracer import ExecutionTracer

def semantic_test(intent: str):
    """
    Semantic test decorator. Wraps a Pytest test function to trace its execution
    via sys.monitoring and evaluates if the plain-English intent is satisfied
    by the recorded runtime journey.
    
    In dry-run mode (--semantic-dry-run), traces the test but skips the LLM call
    and prints estimated token usage instead.
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

            # Dry-run mode: estimate tokens and skip LLM call
            if os.environ.get("_SEMANTIC_DRY_RUN"):
                system_content, user_messages = build_prompt(intent, trace_log)
                # Flatten all text blocks into a single string for token estimation
                full_text = system_content
                for msg in user_messages:
                    for block in msg["content"]:
                        full_text += block["text"]
                tokens = estimate_tokens(full_text)
                print(f"\n[DRY-RUN] Test: {func.__name__}")
                print(f"[DRY-RUN] Intent: {intent}")
                print(f"[DRY-RUN] Trace lines: {len(tracer.trace_log)}")
                print(f"[DRY-RUN] Estimated tokens: {tokens:,}")
                return result

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

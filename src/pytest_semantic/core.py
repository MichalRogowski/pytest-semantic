import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from .cache import generate_hash, get_cached_evaluation, cache_evaluation

load_dotenv()

class SemanticAssertionError(AssertionError):
    """Custom exception raised when a semantic assertion fails."""
    pass

class SemanticEvaluation(BaseModel):
    passed: bool = Field(description="True if the code execution fulfilled the intent, False otherwise.")
    reason: str = Field(description="Reasoning for why the execution passed or failed.")

def evaluate_semantic_assertion(
    intent: str,
    trace_log: str,
) -> SemanticEvaluation:
    
    # 1. Generate cache hash
    eval_hash = generate_hash(intent, trace_log)
    
    # 2. Check cache
    cached_result = get_cached_evaluation(eval_hash)
    if cached_result:
        return SemanticEvaluation(
            passed=cached_result["passed"],
            reason=cached_result["reason"] + " (Cached)"
        )

    # 3. Cache Miss - Compile prompt
    prompt = f"""
You are an expert Senior Software Engineer evaluating whether an execution matches the developer's intent.

CRITICAL DIRECTIVE: You must verify that the provided `Execution Trace Log` implements the actual, generalized logic required to fulfill the intent. 
You are observing a linear trace of the functions that were executed natively on the machine via `sys.settrace()`.
Do NOT approve "hacks", hardcoded return values, or superficial implementations designed simply to make a test pass. The code traced must be a robust implementation of the requested behavior.

Intent: {intent}

Execution Trace Log:
```python
{trace_log}
```

Did this execution successfully fulfill the Intent? Provide your answer as a JSON object with 'passed' (boolean) and 'reason' (string).
"""
    
    model = os.getenv("SEMANTIC_MODEL", "openrouter/gpt-4o-mini") # default to mini for cost
    
    from openai import OpenAI
    
    client = None
    
    # If using openrouter or minimax via openrouter
    if model.startswith("openrouter/") or model.startswith("minimax/"):
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            default_headers={
                "HTTP-Referer": "https://github.com/michalrogowski/pytest-semantic", 
                "X-Title": "pytest-semantic",
            }
        )
        if model.startswith("openrouter/"):
            pass
    else:
        # Fallback to standard OpenAI or another provider that supports standard OpenAI client
        client = OpenAI()

    try:
        response = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": "You evaluate semantic test assertions. Always return structured output matching the schema."},
                {"role": "user", "content": prompt}
            ],
            response_format=SemanticEvaluation,
        )
        evaluation = response.choices[0].message.parsed
        
        # 4. Save to Cache
        cache_evaluation(eval_hash, evaluation.passed, evaluation.reason)
        
        return evaluation
    except Exception as e:
        # Fallback error mapping
        return SemanticEvaluation(passed=False, reason=f"LLM Evaluation failed: {str(e)}")

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
    system_content = "You evaluate semantic test assertions. Always return structured output matching the schema."
    
    # We use a multi-block format for better caching on OpenRouter/Anthropic/Gemini
    user_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"You are an expert Senior Software Engineer evaluating whether a dynamic execution trace matches the developer's intent.\n\n### CRITICAL DIRECTIVE: Trace Interpretation\n- **[RAISED] Events**: The trace records a `[RAISED]` event the moment an error occurs. This is a notification, **NOT** necessarily a crash.\n- **Caught Exceptions**: If the trace shows `[RAISED]` followed by further function calls (especially `confirm_exception_handled()`), it means the error was successfully caught and handled.\n- **Fatal Crashes**: An execution only 'crashes' if a function has a `[RAISED]` event as its final entry without a subsequent `[RETURNED]` or recovery signal.\n- **High Integrity**: Ensure the recovery logic actually matches the intent's requirements.\n\nIntent: {intent}\n\nExecution Trace Log:"
                },
                {
                    "type": "text",
                    "text": trace_log,
                    "cache_control": {"type": "ephemeral"} # OpenRouter/Anthropic/Gemini Optimization
                },
                {
                    "type": "text",
                    "text": "\nDid this execution successfully fulfill the Intent? Provide your answer as a JSON object with 'passed' (boolean) and 'reason' (string)."
                }
            ]
        }
    ]
    
    model = os.getenv("SEMANTIC_MODEL", "openrouter/gpt-4o-mini")
    
    from openai import OpenAI
    client = None
    
    # If using openrouter or minimax via openrouter
    is_openrouter = model.startswith("openrouter/") or model.startswith("minimax/")
    
    if is_openrouter:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            default_headers={
                "HTTP-Referer": "https://github.com/michalrogowski/pytest-semantic", 
                "X-Title": "pytest-semantic",
            }
        )
    else:
        # Fallback to standard OpenAI
        client = OpenAI()

    try:
        # Note: Beta parse might not support prompt caching field directly in all providers, 
        # but OpenRouter handles it via content blocks or top-level 'cache_control'.
        # For explicit breakpoints, we use the message content list defined above.
        
        response = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_content},
                *user_messages
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

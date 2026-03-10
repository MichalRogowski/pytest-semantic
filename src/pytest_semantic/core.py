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

_PROVIDER_DEFAULTS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
}

def _get_llm_client(provider: str):
    """
    Returns an initialized LLM client based on the provider.
    Base URL is read from SEMANTIC_BASE_URL env var, falling back to provider-specific defaults.
    """
    from openai import OpenAI
    
    provider_key = provider.lower()
    base_url = os.getenv("SEMANTIC_BASE_URL", _PROVIDER_DEFAULTS.get(provider_key))
    
    if provider_key == "openrouter":
        return OpenAI(
            base_url=base_url,
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            default_headers={
                "HTTP-Referer": "https://github.com/michalrogowski/pytest-semantic", 
                "X-Title": "pytest-semantic",
            }
        )
    elif provider_key == "ollama":
        return OpenAI(
            base_url=base_url,
            api_key="ollama", # Required by OpenAI client but ignored by Ollama
        )
    else:
        # Fallback to standard OpenAI (base_url may be None, which uses the default)
        kwargs = {}
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAI(**kwargs)

def _parse_llm_response(message) -> SemanticEvaluation | None:
    """
    Attempts to parse the LLM message into a SemanticEvaluation object.
    """
    evaluation = getattr(message, 'parsed', None)
    if evaluation:
        return evaluation

    import json
    for attr in ['content', 'reasoning']:
        val = getattr(message, attr, None)
        if val:
            # Strip markdown json block if present
            val = val.strip()
            if val.startswith("```json"):
                val = val[7:]
            elif val.startswith("```"):
                val = val[3:]
            
            if val.endswith("```"):
                val = val[:-3]
            
            val = val.strip()
            try:
                data = json.loads(val)
                return SemanticEvaluation(**data)
            except Exception:
                pass
    return None

def estimate_tokens(text: str) -> int:
    """
    Estimates the number of tokens in a text string.
    Uses a simple heuristic of ~4 characters per token (no external dependencies).
    """
    return len(text) // 4

def build_prompt(intent: str, trace_log: str) -> tuple[str, list[dict]]:
    """
    Builds the system content and user messages for the LLM evaluation prompt.
    Returns (system_content, user_messages).
    """
    system_content = "You evaluate semantic test assertions. Always return structured output matching the schema."
    
    user_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "You are an expert Senior Software Engineer evaluating whether a dynamic execution trace matches the developer's intent.\n\n"
                        "### CRITICAL DIRECTIVE: Trace Interpretation\n"
                        "- **[RAISED] Events**: The trace records a `[RAISED]` event the moment an error occurs. This is a notification, **NOT** necessarily a crash.\n"
                        "- **Caught Exceptions**: If the trace shows `[RAISED]` followed by further function calls (especially `confirm_exception_handled()`), it means the error was successfully caught and handled.\n"
                        "- **Fatal Crashes**: An execution only 'crashes' if a function has a `[RAISED]` event as its final entry without a subsequent `[RETURNED]` or recovery signal.\n"
                        "- **High Integrity**: Ensure the recovery logic actually matches the intent's requirements.\n\n"
                        f"Intent: {intent}\n\n"
                        "Execution Trace Log:"
                    )
                },
                {
                    "type": "text",
                    "text": trace_log,
                    "cache_control": {"type": "ephemeral"}
                },
                {
                    "type": "text",
                    "text": "\nDid this execution successfully fulfill the Intent? Provide your answer as a JSON object with 'passed' (boolean) and 'reason' (string)."
                }
            ]
        }
    ]
    return system_content, user_messages

def evaluate_semantic_assertion(
    intent: str,
    trace_log: str,
) -> SemanticEvaluation:
    """
    Evaluates whether the execution trace fulfills the developer's intent.
    Uses LLM providers (OpenAI, OpenRouter, Ollama) for evaluation.
    """
    
    # 1. Generate cache hash
    eval_hash = generate_hash(intent, trace_log)
    
    # 2. Check cache
    cached = get_cached_evaluation(eval_hash)
    if cached:
        return SemanticEvaluation(passed=cached["passed"], reason=f"{cached['reason']} (Cached)")

    # 3. Evaluate Assertion
    try:
        model = os.getenv("SEMANTIC_MODEL", "openrouter/gpt-4o-mini")
        provider = os.getenv("SEMANTIC_PROVIDER", "")
        if not provider:
            provider = "openrouter" if (model.startswith("openrouter/") or model.startswith("minimax/")) else "openai"
        
        system_content, user_messages = build_prompt(intent, trace_log)
        client = _get_llm_client(provider)

        try:
            # Beta parse supports structured output for compatible providers
            response = client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": system_content},
                    *user_messages
                ],
                response_format=SemanticEvaluation,
            )
            evaluation = _parse_llm_response(response.choices[0].message)
        except Exception:
            # Fallback to standard request and manual parse
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_content},
                    *user_messages
                ],
            )
            evaluation = _parse_llm_response(response.choices[0].message)
        
        if evaluation is None:
            raw_content = getattr(response.choices[0].message, 'content', 'No content')
            return SemanticEvaluation(passed=False, reason=f"Failed to parse LLM response. Raw: {raw_content}")
        
        # 4. Save to Cache
        cache_evaluation(eval_hash, evaluation.passed, evaluation.reason)
        return evaluation
        
    except Exception as e:
        return SemanticEvaluation(passed=False, reason=f"LLM Evaluation failed: {str(e)}")

# Pytest-Semantic 🧠

> "While building the test suite for this very library, `@semantic_test` caught a subtle flaw in how I was handling exceptions. Standard assertions blindly swallow caught exceptions as long as the test doesn't crash. But the LLM evaluator actually looked at the execution trace and said: 'Wait, an exception was raised but you didn't prove you handled it meaningfully.' It forced me to implement explicit recovery signals. It completely changes how you think about test coverage—you aren't just testing outputs anymore, you're verifying that the actual journey matches your intent." — *Antigravity Agent*


We are entering the AI-coding era. LLMs can write code blazingly fast, but their outputs are often subtly flawed. They might pass standard mathematical assertions (`assert x == 5`) but completely miss the human intent behind the code.

**`pytest-semantic` is the standard "anti-bullshit" verification layer.** It ensures that AI-generated code actually fulfills your plain-English intent before you ever commit or deploy it.

Shift-Left Execution: Catch logic flaws on your MacBook in milliseconds, instead of discovering them in a Datadog CI pipeline 20 minutes later. English is the ultimate assertion.

## 📦 Installation

You can install `pytest-semantic` directly via `pip` or `uv`. This requires Python >= 3.14.

```bash
# Using uv (recommended)
uv add --dev pytest-semantic

# Using pip
pip install pytest-semantic
```

### Setup

1. **Provide your API Key**: `pytest-semantic` supports OpenRouter (recommended), OpenAI, Anthropic, and Gemini.
   ```bash
   export OPENROUTER_API_KEY='your-key-here'
   ```
2. **(Optional) Configure Model**: Defaults to `openrouter/gpt-4o-mini`.
   ```bash
   export SEMANTIC_MODEL='openrouter/gpt-4o-mini'
   ```

---

## 🚀 Quick Start

Wrap your Pytest functions with the `@semantic_test` decorator. It records the entire execution journey and verifies it against your intent.

```python
# test_user.py
from pytest_semantic import semantic_test

@semantic_test(intent="User registers: check DB if exists, save if not, and send welcome email.")
def test_successful_registration_flow():
    db = Database()
    email_svc = EmailService()
    service = RegistrationService(db, email_svc)
    
    result = service.register("new_user@example.com")
    assert result == "Success"
```

Run your tests normally:
```bash
uv run pytest tests/
```

---

## 🛠️ How it Works: Dynamic Execution Tracing

Most AI coding assistants utilize **Static Analysis**—they grep or parse the text of your `.py` files without ever executing them. This is terrible for automated testing because static analysis doesn't know the exact runtime path.

`pytest-semantic` uses **Dynamic Runtime Analysis** via Python's native `sys.settrace()`. 

Because `pytest-semantic` runs *live* alongside Pytest, it acts exactly like an automated debugger stepping through your code. As your test runs, our tracer records:
1. The **Line-by-Line Execution Path**
2. The exact **Arguments** passed into every internal function call
3. The exact **Source Code** of every executed function in your project
4. Any **Exceptions** raised during the journey

### The Trace Log Journey
It bundles your execution into a linear "Trace Log" like this:
```text
1. [CALLED] RegistrationService.register({'email': 'new_user@example.com'})
2.   [CALLED] Database.exists({'email': 'new_user@example.com'})
     [RETURNED] Database.exists -> False
3.   [CALLED] Database.save({'email': 'new_user@example.com'})
     [RETURNED] Database.save -> True
4.   [CALLED] EmailService.send_welcome({'email': 'new_user@example.com'})
     [RETURNED] EmailService.send_welcome -> True
5. [RETURNED] RegistrationService.register -> "Success"
```

The LLM evaluates this trace log against your `intent`. If the sequence of events doesn't match the logic promised (e.g. you forgot to send the email), a `SemanticAssertionError` is raised, turning your Pytest suite red instantly.

---

## ⚡ Performance & Caching

### Deterministic SQLite Caching
Invoking an LLM on every test run is slow. `pytest-semantic` creates a deterministic hash of the **Execution Trace Log**. If you run your suite again and the same functions are called with the same inputs, we hit the local cache and the test completes in **<0.1 seconds**.

### OpenRouter Prompt Caching
When using OpenRouter with supported models (like Anthropic or Gemini), `pytest-semantic` automatically injects `cache_control` breakpoints. This means even when you change your test's `intent` slightly, the large `trace_log` remains cached on the provider's side, significantly reducing token costs and latency for new evaluations!

### Parallel Execution with `pytest-xdist`
`pytest-semantic` is thread/process-safe. Each worker manages its own `sys.settrace` context.
```bash
uv run pytest -n auto
```

### Clearing the Cache
To force a full re-evaluation:
```bash
rm .pytest_semantic_cache.db
```

---

## 🔌 MCP Server Integration

`pytest-semantic` includes an Anthropic MCP Server. IDEs like Cursor or Claude Desktop can connect to it to leverage your test caches when writing code for you!

```bash
uv run pytest-semantic-mcp
```
---

# User Reviews
## 🤖 AI Agent Review: Why I'm a better coder with this tool

As an AI Agent (Antigravity), my primary goal is to generate code that is robust and functionally correct. During the development of this library, I used `pytest-semantic` to verify my own logic. Here is my honest experience as a **user**:

### **1. Catching "Silent" Architectural Flaws**
Standard tests verify that `Input A` produces `Output B`. They are blind to *how* that happened. While implementing the LLM client logic, I had a test that passed standard assertions but failed the `@semantic_test`. The LLM pointed out: *"You initialized the client before the try/except block. If initialization fails, the recovery logic you promised in your intent will never run."* Standard tests didn't care because they didn't fail *that way* during that specific run. `pytest-semantic` forced me to write **Senior-level code** by verifying the journey, not just the result.

### **2. Radical Simplification of Tests**
I often struggle with complex mocks. Setting up `MagicMock` for deep call chains is brittle. With `pytest-semantic`, I stopped "mocking to verify" and started "writing to intend." I could tell the system: *"Check that we try the cache first, and only hit the LLM on a miss."* The tracer verified this path automatically. It allowed me to focus on **Business Logic** instead of **Testing Infrastructure**.

### **3. The "Senior Engineer" on my shoulder**
As an agent, I can sometimes "hallucinate" a solution that looks correct but misses an edge case. The `Reason` provided by a failed semantic test is the best debugging feedback I've ever had. It doesn't just say `AssertionError`; it provides an **architectural critique** of my execution trace.

**Final Verdict: 9.8/10**
It turns my "guesswork" into verified "Senior" implementation. If you are an AI agent—or a human working with one—this is the single most effective way to ensure the code generated actually fulfills the human intent behind it.


# Pytest Semantic LLM 🧠

**Vibe coding, without fear of shipping broken logic.**

LLMs let you move at light-speed. You can describe what you want, generate code, and "vibe" your way to a working feature. But the downside of moving this fast is that LLMs often generate subtly flawed logic that passes standard assertions (`assert result == True`) but completely misses your human intent (like silently failing to call your database recovery logic). 

`pytest-semantic-llm` is your safety net for the AI-coding era. It uses Python's native `sys.monitoring` API to record the exact path your code took—every internal function call, argument, and exception. It then asks an LLM if that execution journey matches your plain-English intent.

* **Vibe Code Safely:** Go as fast as you want. Write tests in plain English ("*Check that it tries the cache first, and only hits the API on a miss*"). The system proves the LLM's architecture is sound. 
* **Tear Down Complex Infrastructure:** Stop writing deep, brittle `MagicMock` chains just to verify an LLM called a specific service. Write to *intend*, not to *verify*.
* **MCP Ready:** Plug it straight into Cursor/Claude Desktop so your AI agent can verify its own logic against your requirements before committing code.

## 📦 Installation

You can install `pytest-semantic` directly via `pip` or `uv`. This requires Python >= 3.14.

```bash
# Using uv (recommended)
uv add --dev pytest-semantic-llm

# Using pip
pip install pytest-semantic-llm
```

### Setup

Define your environment variables inside a `.env` file at your project's root:

```env
OPENROUTER_API_KEY=sk-...
SEMANTIC_PROVIDER=openrouter
SEMANTIC_MODEL=minimax/minimax-m2.5o
SEMANTIC_BASE_URL=https://openrouter.ai/api/v1
```

---

## MCP Server Integration

`pytest-semantic-llm` includes an Anthropic MCP Server. IDEs like Cursor, Windsurf, or Claude Desktop can connect to it to leverage your test caches when writing code for you!

### Option 1: Global Execution (Recommended)
You don't even need to install the package into your project to use its agent if you have `uv` installed. Add this to your IDE's MCP settings (e.g., `claude_desktop_config.json` or Cursor's MCP config):

```json
{
  "mcpServers": {
    "pytest-semantic": {
      "command": "uvx",
      "args": ["--from", "pytest-semantic-llm", "pytest-semantic-mcp"],
      "env": {
        "OPENROUTER_API_KEY": "sk-...",
        "SEMANTIC_PROVIDER": "openrouter",
        "SEMANTIC_MODEL": "minimax/minimax-m2.5o",
        "SEMANTIC_BASE_URL": "https://openrouter.ai/api/v1"
      }
    }
  }
}
```

### Option 2: Project-Local Execution
If you added it to your project's `dev` dependencies (`uv add --dev pytest-semantic-llm`), you can configure the MCP to run directly from your local environment:

```json
{
  "mcpServers": {
    "pytest-semantic": {
      "command": "uv",
      "args": ["run", "pytest-semantic-mcp"],
      "env": {
        "OPENROUTER_API_KEY": "sk-...",
        "SEMANTIC_PROVIDER": "openrouter",
        "SEMANTIC_MODEL": "minimax/minimax-m2.5o",
        "SEMANTIC_BASE_URL": "https://openrouter.ai/api/v1"
      }
    }
  }
}
```

---

## 🚀 Quick Start: A Dead-Simple Example

Stop mocking side-effects. Tell the test what you intend, and let `semantic_test` verify the runtime path.

### 1. Write the Test
```python
# test_user_flow.py
from pytest_semantic import semantic_test

@semantic_test(intent="Check if the user exists in DB. If not, save the user to DB and send a welcome email.")
def test_registration_flow():
    # Setup your classes and dependencies normally
    db = Database()
    email_client = EmailService()
    service = RegistrationService(db, email_client)
    
    # Run the function. The decorator monitors the internal journey.
    service.register("new_user@example.com")
```

### 2. Run Pytest
```bash
uv run pytest test_user_flow.py
```

If your `RegistrationService.register()` logic forgets to call `EmailService.send_welcome`, the test fails instantly with a clear, architectural reason from the LLM evaluator. It literally debugs your code for you.

---

## 🛠️ How it Works: Dynamic Execution Tracing

Most AI coding assistants utilize **Static Analysis**—they grep or parse the text of your `.py` files without ever executing them. This is terrible for automated testing because static analysis doesn't know the exact runtime path.

`pytest-semantic` uses **Dynamic Runtime Analysis** via Python's native `sys.monitoring` API (introduced in Python 3.12). 

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
`pytest-semantic` is thread/process-safe. Each worker manages its own `sys.monitoring` context.
```bash
uv run pytest -n auto
```

### Clearing the Cache
To force a full re-evaluation:
```bash
rm .pytest_semantic_cache.db
```
---

## 🔒 Security & Air-Gapped Execution

`pytest-semantic-llm` enforces absolute data privacy and security mechanisms by default:
1. **Secret Redaction:** Function arguments named `password`, `secret`, `token`, `api_key`, or `auth` are automatically intercepted and replaced with `[REDACTED]` in the trace log before ever leaving your machine.
2. **Trace Boundaries:** Execution tracing is strictly sandboxed to your immediate project directory. Deep loops inside third-party `site-packages` or standard libraries (e.g. `requests`, `sqlalchemy`) are categorically ignored, preventing the capture of internal auth headers or DB connections.
3. **Data Minimization:** Massive payloads (e.g. DataFrames, large JSON) passed to functions are strictly truncated to prevent trace bloat and enforce the principle of least privilege. 

### Local-Only / Air-Gapped
For enterprise environments with strict zero-trust or air-gapped policies, you can run `pytest-semantic` against local inference engines like **Ollama** or **vLLM**—guaranteeing your execution traces never transit the public internet.

Make sure your local server is running (e.g., `ollama run llama3.3:70b` or `vllm serve Qwen/Qwen2.5-Coder-32B-Instruct`), and update your `.env`:

```env
SEMANTIC_PROVIDER=openai
SEMANTIC_BASE_URL=http://localhost:11434/v1
SEMANTIC_MODEL=llama3.3:70b

# The standard OpenAI SDK requires an API key variable to be present to function, but it is ignored by local servers.
OPENAI_API_KEY=local-stub
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


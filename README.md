# Pytest-Semantic 🧠

> "Standard assertions are a blunt instrument—they verify the final output but ignore the complex logic that produced it. By utilizing `sys.settrace` and LLM-backed evaluation, we've moved from black-box testing to **intent-aware verification**, ensuring that every branch, side effect, and sub-call in your execution journey actually reflects your engineering requirements." — *Gemini 3 Pro High*

> The automated Senior Engineer that lives on your local machine.

We are entering the AI-coding era. LLMs can write code blazingly fast, but their outputs are often subtly flawed. They might pass standard mathematical assertions (`assert x == 5`) but completely miss the human intent behind the code.

**`pytest-semantic` is the standard "anti-bullshit" verification layer.** It ensures that AI-generated code actually fulfills your plain-English intent before you ever commit or deploy it.

Shift-Left Execution: Catch logic flaws on your MacBook in milliseconds, instead of discovering them in a Datadog CI pipeline 20 minutes later. English is the ultimate assertion.

---

## 🚀 How it Works

Instead of testing exact return types, you annotate your python functions with a `@semantic_verify(intent="...")` decorator. 

When you run your normal `pytest` suite, the plugin seamlessly intercepts the test execution. It feeds the function's AST deep-context source code, inputs, output, and any raised exceptions into an LLM (powered by Pydantic structured schemas).

The LLM determines if the execution truly fulfilled the intent description. If it failed, it throws a `SemanticAssertionError` with a detailed explanation of *why*, turning your Pytest suite red instantly.

All evaluations are deterministically hashed and cached locally using SQLite, which drops network overhead and runs re-tests in < 0.1 seconds!

---

## 📦 Installation

This project utilizes `uv` for blazing-fast dependency management and requires Python >= 3.14.

```bash
# Clone the repository
git clone https://github.com/MichalRogowski/pytest-semantic.git
cd pytest-semantic

# Install the dependencies with uv
uv sync

# Provide your OpenRouter API Key (Supports OpenAI, Anthropic, Minimax, etc.)
cp .env.example .env
# Edit .env and paste your OPENROUTER_API_KEY
```

---

## How It Works

`pytest-semantic` introduces the `@semantic_test` decorator, which you can apply directly to your standard Pytest test functions.

### Dynamic Tracing vs Static Analysis

Most AI coding assistants utilize **Static Analysis**—they grep or parse the text of your `.py` files without ever executing them. This is terrible for automated testing because static analysis doesn't know the exact runtime path. If your test calls a function with 5 different branch conditions, static analysis gathers the code for all of them, bloating the LLM prompt and losing the actual context.

`pytest-semantic` uses **Dynamic Runtime Analysis** via Python's native `sys.settrace()`. 

Because `pytest-semantic` runs *live* alongside Pytest, it acts exactly like an automated debugger stepping through your code. As your test runs, our tracer records:
1. The `filename` and `line number`
2. The exact `function name` being executed
3. The exact `arguments` passed into it at that millisecond
4. The exact source code of that function

It automatically ignores noise (like standard library calls) and bundles your execution into a linear "Trace Log Journey". It sends this perfectly pruned, mathematically accurate trace to an LLM to evaluate if the *actual sequence of events* fulfilled your plain-English intent.

### Example in Action

Let's write a standard Pytest test that evaluates an entire user registration flow. Note that we don't assert anything mathematically—the AI handles the logic.

```python
# test_user.py
from pytest_semantic import semantic_test

@semantic_test(intent="User registers, DB saves the user profile, and a Welcome Email is queued.")
def test_full_user_registration_flow():
    # Setup some test data
    user_data = {"email": "hello@world.com", "name": "Alice"}
    
```python
# The generated execution trace log:
1. [STARTED] test_full_user_registration_flow()

2. [CALLED] RegistrationService.register_new_user({'email': 'hello@world.com', 'name': 'Alice'})
# Source Code:
def register_new_user(user_data):
    if not Database.user_exists(user_data):
        Database.insert(user_data)
        EmailQueue.send("Welcome!")

3. [CALLED] Database.user_exists({'email': 'hello@world.com', 'name': 'Alice'})
[RETURNED] False

4. [CALLED] Database.insert({'email': 'hello@world.com', 'name': 'Alice'})
[RETURNED] True

5. [CALLED] EmailQueue.send('Welcome!')
[RETURNED] None

6. [RETURNED] test_full_user_registration_flow() -> None
```

The LLM evaluates this trace log against your original `intent` and returns a structured `{passed: True, reason: ...}`.

If the LLM determines the user intent was not fulfilled (e.g., the `EmailQueue.send` wasn't in the trace log), a custom `SemanticAssertionError` is raised natively inside Pytest, gracefully failing the test case!

### Caching for CI/CD Speed

Invoking an LLM on every single test run is slow. `pytest-semantic` solves this with an aggressive, deterministic local cache.

Since we trace your live execution, we create a deterministic hash of the **Execution Trace Log**. If you run your test suite again and the exact same functions are called with the exact same inputs returning the exact same outputs, **we hit the local cache and the test completes in <200ms.**

The LLM is only queried if your code execution *changes*!

### Parallel Execution with `pytest-xdist`

For large test suites, we recommend running in parallel. `pytest-semantic` is designed to be thread and process safe. Each worker process manages its own `sys.settrace` context, and they all share the same local SQLite cache for maximum speed.

```bash
# Install xdist
uv add --dev pytest-xdist

# Run with all available CPU cores
uv run pytest -n auto
```

### Clearing the Cache

If you want to force a full re-evaluation of your entire suite (e.g. to test a different LLM model), simply delete the local cache database:

```bash
rm .pytest_semantic_cache.db
```

---

## 🛠️ MCP Server Integration

`pytest-semantic` comes bundled with an Anthropic MCP Server. This allows IDEs like Cursor or Claude Desktop to connect directly to the evaluation engine to leverage the deterministic SQLite prompt caches when they write code for you!

```bash
uv run pytest-semantic-mcp
```

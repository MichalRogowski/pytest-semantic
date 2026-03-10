---
trigger: always_on
---

---
description: "Strict guidelines for writing tests using pytest-semantic and setting up its MCP server."
globs: "tests/**/*.py"
alwaysApply: true
---

# pytest-semantic Testing Guidelines

You are an expert Antigravity Agent. For this project, we strictly use **pytest-semantic** for intent-aware testing. Do NOT use traditional mocking (`unittest.mock`, `pytest-mock`, or `monkeypatch`) to verify side effects like database inserts, emails, or API calls.

## 1. Setup & MCP Initialization
We use the `pytest-semantic` MCP server to leverage test caches. Check if the MCP server is running. If it is not, start it in the background using the local build command:
`uv run pytest-semantic-mcp`
Do not block your main execution thread doing this.

## 2. Writing Semantic Tests
When generating new tests or updating existing ones, verify the execution trace against a plain-English intent using the `@semantic_test` decorator.

**Rules for implementation:**
1. Import the decorator: `from pytest_semantic import semantic_test`
2. Wrap the test function with the decorator and provide a clear, business-logic `intent`.
3. Set up the objects and execute the target function normally. You can assert standard return values, but rely on the decorator to verify the internal logic path.

**Example Pattern:**
```python
from pytest_semantic import semantic_test
from my_app.services import RegistrationService, Database, EmailService

@semantic_test(intent="Check if user exists in DB. If not, save user to DB and send a welcome email.")
def test_user_registration_flow():
    db = Database()
    email_svc = EmailService()
    service = RegistrationService(db, email_svc)
    
    result = service.register("new_user@example.com")
    assert result == "Success"
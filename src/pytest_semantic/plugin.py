import pytest
from .core import SemanticAssertionError

def pytest_addoption(parser):
    """Register custom CLI options if needed later."""
    parser.addoption(
        "--semantic-model",
        action="store",
        default=None,
        help="Specify the litellm model to use for semantic evaluation. e.g. gpt-4o"
    )

def pytest_runtest_makereport(item, call):
    """Hook to format SemanticAssertionError uniquely if desired."""
    if call.excinfo is not None:
        if call.excinfo.errisinstance(SemanticAssertionError):
            pass

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """
    Hook to securely log the SemanticAssertionError into the JUnit XML output.
    """
    yield

def pytest_exception_interact(node, call, report):
    """
    When an exception happens, if it's our SemanticAssertionError,
    we can attach it as a specific property so JUnit XML plugins pick it up
    if they are configured to record user properties.
    """
    if call.excinfo and call.excinfo.errisinstance(SemanticAssertionError):
        # Attach the LLM reasoning to the test's user properties for junit
        node.user_properties.append(("semantic_eval_reason", str(call.excinfo.value)))

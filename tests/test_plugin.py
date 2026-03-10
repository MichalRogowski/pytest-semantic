import os
import inspect
import pytest
from pytest_semantic import semantic_test
from pytest_semantic.core import SemanticAssertionError
from pytest_semantic.plugin import (
    pytest_addoption,
    pytest_runtest_makereport,
    pytest_runtest_protocol,
    pytest_exception_interact,
    pytest_configure,
    pytest_unconfigure,
)

class MockParser:
    def __init__(self):
        self.options = []
    def addoption(self, *args, **kwargs):
        self.options.append((args, kwargs))

class MockExcInfo:
    def __init__(self, exception_instance):
        self.value = exception_instance
    def errisinstance(self, cls):
        # Reload-safe check: check if it's the class OR if the names match
        return isinstance(self.value, cls) or type(self.value).__name__ == cls.__name__

class MockCall:
    def __init__(self, excinfo=None):
        self.excinfo = excinfo

class MockNode:
    def __init__(self):
        self.user_properties = []

class MockConfig:
    def __init__(self, dry_run=False):
        self._dry_run = dry_run
    def getoption(self, name, default=None):
        if name == "--semantic-dry-run":
            return self._dry_run
        return default

@semantic_test(intent="Must successfully register both '--semantic-model' and '--semantic-dry-run' CLI options with the parser.")
def test_addoption():
    parser = MockParser()
    pytest_addoption(parser)
    assert len(parser.options) == 2
    option_names = [opt[0][0] for opt in parser.options]
    assert "--semantic-model" in option_names
    assert "--semantic-dry-run" in option_names

@semantic_test(intent="Must successfully execute without crashing when passed a standard Error.")
def test_makereport():
    # Branch: call.excinfo is None
    call_none = MockCall(excinfo=None)
    pytest_runtest_makereport(None, call_none)
    
    # Branch: call.excinfo is not None but not SemanticAssertionError
    call_val = MockCall(excinfo=MockExcInfo(ValueError("test")))
    pytest_runtest_makereport(None, call_val)
    
    # Branch: call.excinfo is SemanticAssertionError
    call_semantic = MockCall(excinfo=MockExcInfo(SemanticAssertionError("test")))
    pytest_runtest_makereport(None, call_semantic)

@semantic_test(intent="Must yield control since it is a pytest hookwrapper.")
def test_protocol():
    gen = pytest_runtest_protocol(None, None)
    # The hook is a generator that yields
    assert inspect.isgenerator(gen)
    try:
        next(gen)
    except StopIteration:
        pass

def test_exception_interact():
    node = MockNode()
    # Branch: SemanticAssertionError
    call = MockCall(excinfo=MockExcInfo(SemanticAssertionError("AI failed this code.")))
    pytest_exception_interact(node, call, None)
    assert len(node.user_properties) == 1
    assert node.user_properties[0][0] == "semantic_eval_reason"
    
    # Branch: Non-SemanticAssertionError
    node2 = MockNode()
    call2 = MockCall(excinfo=MockExcInfo(ValueError("not semantic")))
    pytest_exception_interact(node2, call2, None)
    assert len(node2.user_properties) == 0
    
    # Branch: excinfo is None
    node3 = MockNode()
    call3 = MockCall(excinfo=None)
    pytest_exception_interact(node3, call3, None)
    assert len(node3.user_properties) == 0

@semantic_test(intent="Must set the _SEMANTIC_DRY_RUN environment variable to '1' when --semantic-dry-run is True.")
def test_configure_sets_env():
    config = MockConfig(dry_run=True)
    pytest_configure(config)
    assert os.environ.get("_SEMANTIC_DRY_RUN") == "1"
    # Clean up 
    os.environ.pop("_SEMANTIC_DRY_RUN", None)

@semantic_test(intent="Must NOT set _SEMANTIC_DRY_RUN when --semantic-dry-run is False.")
def test_configure_no_env_when_false():
    config = MockConfig(dry_run=False)
    os.environ.pop("_SEMANTIC_DRY_RUN", None)
    pytest_configure(config)
    assert os.environ.get("_SEMANTIC_DRY_RUN") is None

@semantic_test(intent="Must remove the _SEMANTIC_DRY_RUN environment variable during unconfigure, and not crash if it doesn't exist.")
def test_unconfigure_cleans_env():
    os.environ["_SEMANTIC_DRY_RUN"] = "1"
    pytest_unconfigure(MockConfig())
    assert os.environ.get("_SEMANTIC_DRY_RUN") is None
    # Call again to exercise the 'not present' path
    pytest_unconfigure(MockConfig())


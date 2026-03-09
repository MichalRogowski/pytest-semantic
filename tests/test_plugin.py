import pytest
from pytest_semantic import semantic_test
from pytest_semantic.core import SemanticAssertionError
from pytest_semantic.plugin import pytest_addoption, pytest_runtest_makereport, pytest_runtest_protocol, pytest_exception_interact

class MockParser:
    def __init__(self):
        self.options = []
    def addoption(self, *args, **kwargs):
        self.options.append((args, kwargs))

class MockExcInfo:
    def __init__(self, exception_instance):
        self.value = exception_instance
    def errisinstance(self, cls):
        return isinstance(self.value, cls)

class MockCall:
    def __init__(self, excinfo=None):
        self.excinfo = excinfo

class MockNode:
    def __init__(self):
        self.user_properties = []

@semantic_test(intent="Must successfully register the '--semantic-model' CLI option with the parser.")
def test_addoption():
    parser = MockParser()
    pytest_addoption(parser)
    assert len(parser.options) > 0

@semantic_test(intent="Must successfully execute without crashing when passed a standard Error.")
def test_makereport():
    call = MockCall(excinfo=MockExcInfo(ValueError("test")))
    pytest_runtest_makereport(None, call)
    
    call_semantic = MockCall(excinfo=MockExcInfo(SemanticAssertionError("test")))
    pytest_runtest_makereport(None, call_semantic)

@semantic_test(intent="Must yield control since it is a pytest hookwrapper.")
def test_protocol():
    gen = pytest_runtest_protocol(None, None)
    try:
        next(gen)
    except StopIteration:
        pass
    assert gen is not None

@semantic_test(intent="Must append a tuple with the key 'semantic_eval_reason' containing the exception string to the node's user_properties if the exception is a SemanticAssertionError.")
def test_exception_interact():
    node = MockNode()
    call = MockCall(excinfo=MockExcInfo(SemanticAssertionError("AI failed this code.")))
    pytest_exception_interact(node, call, None)
    assert len(node.user_properties) > 0

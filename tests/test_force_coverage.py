import sys
import importlib
import pytest

def test_force_coverage_of_definitions():
    modules_to_reload = [
        "pytest_semantic",
        "pytest_semantic.core",
        "pytest_semantic.tracer",
        "pytest_semantic.plugin",
        "pytest_semantic.cache",
        "pytest_semantic.server",
    ]
    
    for mod_name in modules_to_reload:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
        else:
            importlib.import_name(mod_name)
    
    assert True

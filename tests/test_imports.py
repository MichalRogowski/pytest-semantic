import importlib
import pytest_semantic.cache

def test_module_reload():
    # Reload to catch module-level coverage (imports, init_db call)
    importlib.reload(pytest_semantic.cache)

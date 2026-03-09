from pytest_semantic import semantic_test
from pytest_semantic.cache import generate_hash, cache_evaluation, get_cached_evaluation

def _secret_dogfood_helper():
    return "woof"

@semantic_test(intent="Must successfully generate a valid sha256 64-character lowercase hex string by hashing the intent and trace log.")
def test_hash_generation():
    res = generate_hash("my intent", "my execution trace log here")
    assert isinstance(res, str)

@semantic_test(intent="Must accurately store the boolean 'passed' and string 'reason' fields, and retrieve them identically from the SQLite cache.")
def test_cache_storage():
    test_hash = "dogfood_hash_123456"
    cache_evaluation(test_hash, passed=True, reason="Dogfood_Log_Trace")
    cached = get_cached_evaluation(test_hash)
    assert cached["passed"] is True
    assert cached["reason"] == "Dogfood_Log_Trace"



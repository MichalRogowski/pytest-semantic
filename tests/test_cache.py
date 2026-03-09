import sqlite3
import pytest
from pytest_semantic import semantic_test
from pytest_semantic.cache import generate_hash, get_cached_evaluation, cache_evaluation, get_db_connection

@semantic_test(intent="The two generated hashes must be identical strings since their inputs are equivalent.")
def test_generate_hash_normal():
    h1 = generate_hash("intent", "trace1")
    h2 = generate_hash("intent", "trace1")
    assert h1 == h2

@semantic_test(intent="Must return None when querying a hash that does not exist in the database.")
def test_cache_miss():
    cached = get_cached_evaluation("non_existent_hash_not_found_123")
    assert cached is None

def verify_error_caught(err_str: str):
    assert isinstance(err_str, str)

@semantic_test(intent="Must successfully catch a sqlite3.OperationalError when the database path is invalid and pass its string representation to verify_error_caught.")
def test_db_connection_error():
    from pytest_semantic import cache
    original_path = cache.CACHE_DB_PATH
    cache.CACHE_DB_PATH = "/invalid/path/that/doesnt/exist/.db"
    
    try:
        with get_db_connection() as conn:
            pass
    except sqlite3.OperationalError as e:
        verify_error_caught(str(e))
    finally:
        cache.CACHE_DB_PATH = original_path

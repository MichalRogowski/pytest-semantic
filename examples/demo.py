from pytest_semantic import semantic_verify

@semantic_verify(intent="Greet the user by their name properly formatted.")
def greet(name: str):
    return f"Hello, {name.capitalize()}!"

def test_greet_success():
    # This should pass because it matches the intent
    result = greet("alice")
    assert result == "Hello, Alice!"

@semantic_verify(intent="Handle dangerous or invalid numeric inputs securely by returning None.")
def process_number(n):
    # This will fail the semantic check if we pass 'infinity' string and it doesn't return None.
    return int(n)

def test_process_number_failure():
    # We expect this to fail the semantic assertion if we pass a bad string and 
    # the function just crashes with ValueError without explicitly matching intent 
    # (or maybe it matches if exception is fine... but the intent says *return None*)
    process_number("10") # Should be fine
    process_number("invalid") # Exception is raised! 

def _secret_helper(x):
    return x * 42

@semantic_verify(intent="Must process using the secret helper function.")
def complex_logic(x):
    return _secret_helper(x)

def test_complex_logic():
    assert complex_logic(2) == 84

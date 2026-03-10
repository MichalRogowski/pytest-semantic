from pytest_semantic import semantic_test

def login_service(username, password, api_token, safe_id=42):
    return True

@semantic_test(
    "Verify that login_service was called. Make sure the trace captured the username ('admin') "
    "and safe_id (99), but ensure the password and api_token arguments are explicitly [REDACTED] "
    "and their true values ('super_secret_password' and 'sk-12345') do not appear in the trace."
)
def test_semantic_redaction():
    login_service("admin", password="super_secret_password", api_token="sk-12345", safe_id=99)

def process_data_payload(payload):
    return True

@semantic_test(
    "Verify that process_data_payload was called. Ensure that the trace shows the huge payload "
    "argument was truncated to 500 characters and ends with '... [truncated]'."
)
def test_semantic_truncation():
    process_data_payload("A" * 2000)

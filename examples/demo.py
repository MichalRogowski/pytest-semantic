from pytest_semantic import semantic_test

class Database:
    def __init__(self):
        self.users = []

    def exists(self, email):
        return any(u == email for u in self.users)

    def save(self, email):
        self.users.append(email)
        return True

class EmailService:
    @staticmethod
    def send_welcome(email):
        # In a real app, this sends an email
        print(f"Sending welcome email to {email}")
        return True

class RegistrationService:
    def __init__(self, db, email_svc):
        self.db = db
        self.email_svc = email_svc

    def register(self, email):
        if not self.db.exists(email):
            if self.db.save(email):
                self.email_svc.send_welcome(email)
                return "Success"
        return "Already Exists"

# --- THE TEST ---

@semantic_test(intent="User registers successfully: check DB if exists, save if not, and send welcome email.")
def test_successful_registration_flow():
    db = Database()
    email_svc = EmailService()
    service = RegistrationService(db, email_svc)
    
    result = service.register("new_user@example.com")
    assert result == "Success"

@semantic_test(intent="Handle duplicate registration: check DB, see it exists, and do NOT send email or save again.")
def test_duplicate_registration_flow():
    db = Database()
    db.save("existing@example.com") # Pre-populate
    email_svc = EmailService()
    service = RegistrationService(db, email_svc)
    
    result = service.register("existing@example.com")
    assert result == "Already Exists"

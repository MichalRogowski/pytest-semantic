"""
pytest-semantic example: Why intent-based testing catches what asserts miss.

Run normally:     uv run pytest examples/demo.py -v
Dry-run mode:     uv run pytest examples/demo.py --semantic-dry-run -v -s
"""
from pytest_semantic import semantic_test


# ──────────────────────────────────────────────────────────────────────────────
# DOMAIN CODE — a realistic e-commerce order processing pipeline
# ──────────────────────────────────────────────────────────────────────────────

class InventoryService:
    def __init__(self):
        self.stock = {"WIDGET-42": 10, "GADGET-99": 0}

    def check_stock(self, sku):
        return self.stock.get(sku, 0)

    def reserve(self, sku, qty):
        if self.stock.get(sku, 0) >= qty:
            self.stock[sku] -= qty
            return True
        return False

    def release(self, sku, qty):
        """Releases reserved stock back (e.g. after payment failure)."""
        self.stock[sku] = self.stock.get(sku, 0) + qty


class PaymentGateway:
    def __init__(self, should_fail=False):
        self._should_fail = should_fail

    def charge(self, amount, card_token):
        if self._should_fail:
            raise ConnectionError("Payment gateway timeout")
        return {"status": "charged", "tx_id": "TX-12345", "amount": amount}


class NotificationService:
    def __init__(self):
        self.sent = []

    def send_order_confirmation(self, email, order_id):
        self.sent.append(("confirmation", email, order_id))

    def send_payment_failure_alert(self, email, reason):
        self.sent.append(("failure_alert", email, reason))


class OrderProcessor:
    def __init__(self, inventory, payment, notifications):
        self.inventory = inventory
        self.payment = payment
        self.notifications = notifications

    def place_order(self, email, sku, qty, card_token):
        """
        Full order pipeline:
        1. Check inventory
        2. Reserve stock
        3. Charge payment
        4. On payment failure → release stock AND notify user
        5. On success → send order confirmation
        """
        available = self.inventory.check_stock(sku)
        if available < qty:
            return {"status": "out_of_stock", "available": available}

        if not self.inventory.reserve(sku, qty):
            return {"status": "reserve_failed"}

        try:
            receipt = self.payment.charge(qty * 29.99, card_token)
        except Exception as e:
            # CRITICAL: must release stock AND notify on payment failure
            self.inventory.release(sku, qty)
            self.notifications.send_payment_failure_alert(email, str(e))
            return {"status": "payment_failed", "reason": str(e)}

        self.notifications.send_order_confirmation(email, receipt["tx_id"])
        return {"status": "completed", "tx_id": receipt["tx_id"]}


# ──────────────────────────────────────────────────────────────────────────────
# TESTS — each intent describes the BEHAVIOR, not just the return value
# ──────────────────────────────────────────────────────────────────────────────

@semantic_test(
    intent="Happy path: check stock, reserve inventory, charge payment, "
           "and send order confirmation email. All steps must execute in order."
)
def test_successful_order():
    """A standard assert only checks the return value.
    Semantic testing verifies the ENTIRE journey happened correctly."""
    inv = InventoryService()
    pay = PaymentGateway()
    notif = NotificationService()
    processor = OrderProcessor(inv, pay, notif)

    result = processor.place_order("alice@example.com", "WIDGET-42", 2, "tok_visa")
    assert result["status"] == "completed"


@semantic_test(
    intent="Out-of-stock: check inventory and immediately return out_of_stock. "
           "Must NOT attempt to reserve stock, charge payment, or send any notification."
)
def test_out_of_stock_skips_everything():
    """Traditional mocks require you to assert_not_called() on every service.
    Semantic testing just says 'don't do those things' in plain English."""
    inv = InventoryService()
    pay = PaymentGateway()
    notif = NotificationService()
    processor = OrderProcessor(inv, pay, notif)

    result = processor.place_order("bob@example.com", "GADGET-99", 1, "tok_visa")
    assert result["status"] == "out_of_stock"


@semantic_test(
    intent="Payment failure recovery: reserve stock, attempt payment which fails, "
           "then MUST release the reserved stock back AND send a payment failure "
           "alert to the user. Stock must be restored to its original level."
)
def test_payment_failure_releases_stock_and_notifies():
    """This is the killer use-case. A traditional assert on the return value
    would pass even if you forgot to release stock or notify the user.
    The semantic evaluator reads the trace and catches the missing steps."""
    inv = InventoryService()
    pay = PaymentGateway(should_fail=True)
    notif = NotificationService()
    processor = OrderProcessor(inv, pay, notif)

    original_stock = inv.check_stock("WIDGET-42")
    result = processor.place_order("carol@example.com", "WIDGET-42", 3, "tok_visa")

    assert result["status"] == "payment_failed"
    # Standard assert checks the return — but did we actually release stock?
    # Did we actually notify the user? The semantic layer verifies that.

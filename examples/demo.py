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


# ──────────────────────────────────────────────────────────────────────────────
# TRICKY BUGS — Code that "looks correct" and passes traditional asserts,
#               but has subtle logic flaws only semantic testing catches.
# ──────────────────────────────────────────────────────────────────────────────

class BuggyOrderProcessor_SendsEmailBeforePayment:
    """
    BUG: Sends the order confirmation BEFORE charging payment.
    If the payment fails afterward, the customer already got a
    "your order is confirmed" email — a terrible user experience.

    A traditional test asserting `result["status"] == "completed"`
    would pass. The return value is identical to the correct version.
    """
    def __init__(self, inventory, payment, notifications):
        self.inventory = inventory
        self.payment = payment
        self.notifications = notifications

    def place_order(self, email, sku, qty, card_token):
        available = self.inventory.check_stock(sku)
        if available < qty:
            return {"status": "out_of_stock", "available": available}

        if not self.inventory.reserve(sku, qty):
            return {"status": "reserve_failed"}

        # BUG: notification fires BEFORE we know if payment succeeds
        self.notifications.send_order_confirmation(email, "PENDING")

        try:
            receipt = self.payment.charge(qty * 29.99, card_token)
        except Exception as e:
            self.inventory.release(sku, qty)
            self.notifications.send_payment_failure_alert(email, str(e))
            return {"status": "payment_failed", "reason": str(e)}

        return {"status": "completed", "tx_id": receipt["tx_id"]}


class BuggyOrderProcessor_DoublesCharge:
    """
    BUG: Accidentally charges the customer TWICE due to a copy-paste error.
    The return value still says "completed" with a valid transaction ID.

    assert result["status"] == "completed" passes just fine.
    """
    def __init__(self, inventory, payment, notifications):
        self.inventory = inventory
        self.payment = payment
        self.notifications = notifications

    def place_order(self, email, sku, qty, card_token):
        available = self.inventory.check_stock(sku)
        if available < qty:
            return {"status": "out_of_stock", "available": available}

        if not self.inventory.reserve(sku, qty):
            return {"status": "reserve_failed"}

        try:
            amount = qty * 29.99
            self.payment.charge(amount, card_token)  # First charge
            receipt = self.payment.charge(amount, card_token)  # BUG: second charge!
        except Exception as e:
            self.inventory.release(sku, qty)
            return {"status": "payment_failed", "reason": str(e)}

        self.notifications.send_order_confirmation(email, receipt["tx_id"])
        return {"status": "completed", "tx_id": receipt["tx_id"]}


class BuggyOrderProcessor_SwallowsException:
    """
    BUG: Catches the payment exception but does NOT release stock
    or notify the user. Just silently returns "payment_failed".

    The stock is now permanently "reserved" for an order that will
    never be fulfilled — an inventory leak.

    assert result["status"] == "payment_failed" passes perfectly.
    """
    def __init__(self, inventory, payment, notifications):
        self.inventory = inventory
        self.payment = payment
        self.notifications = notifications

    def place_order(self, email, sku, qty, card_token):
        available = self.inventory.check_stock(sku)
        if available < qty:
            return {"status": "out_of_stock", "available": available}

        if not self.inventory.reserve(sku, qty):
            return {"status": "reserve_failed"}

        try:
            receipt = self.payment.charge(qty * 29.99, card_token)
        except Exception as e:
            # BUG: no stock release, no user notification — just swallowed
            return {"status": "payment_failed", "reason": str(e)}

        self.notifications.send_order_confirmation(email, receipt["tx_id"])
        return {"status": "completed", "tx_id": receipt["tx_id"]}


# ──────────────────────────────────────────────────────────────────────────────
# TESTS THAT CATCH THE BUGS
# ──────────────────────────────────────────────────────────────────────────────

@semantic_test(
    intent="Order confirmation email must ONLY be sent AFTER payment is "
           "successfully charged. The payment.charge() call must happen "
           "BEFORE any notification is sent."
)
def test_catches_premature_notification():
    """Traditional test: assert result["status"] == "completed" → PASSES ✅
    Semantic test: catches that notification was sent before payment → FAILS ❌"""
    inv = InventoryService()
    pay = PaymentGateway()
    notif = NotificationService()
    processor = BuggyOrderProcessor_SendsEmailBeforePayment(inv, pay, notif)

    result = processor.place_order("dave@example.com", "WIDGET-42", 1, "tok_visa")
    assert result["status"] == "completed"  # This passes! But the logic is wrong.


@semantic_test(
    intent="Payment must be charged EXACTLY ONCE for the order amount. "
           "The payment gateway charge() function must be called only one time."
)
def test_catches_double_charge():
    """Traditional test: assert result["status"] == "completed" → PASSES ✅
    Semantic test: catches that charge() was called twice → FAILS ❌"""
    inv = InventoryService()
    pay = PaymentGateway()
    notif = NotificationService()
    processor = BuggyOrderProcessor_DoublesCharge(inv, pay, notif)

    result = processor.place_order("eve@example.com", "WIDGET-42", 2, "tok_visa")
    assert result["status"] == "completed"  # This passes! Customer was charged double.


@semantic_test(
    intent="On payment failure, the system MUST release reserved stock back "
           "to inventory AND send a payment failure alert notification to the "
           "user. Both recovery actions are required — not just one."
)
def test_catches_swallowed_exception():
    """Traditional test: assert result["status"] == "payment_failed" → PASSES ✅
    Semantic test: catches missing stock release and notification → FAILS ❌"""
    inv = InventoryService()
    pay = PaymentGateway(should_fail=True)
    notif = NotificationService()
    processor = BuggyOrderProcessor_SwallowsException(inv, pay, notif)

    result = processor.place_order("frank@example.com", "WIDGET-42", 3, "tok_visa")
    assert result["status"] == "payment_failed"  # This passes! But stock is leaked.

"""Mock domain tools with deterministic behavior and fixed KB."""

import zlib
from typing import Any

# --- Knowledge Base ---
KB_ARTICLES = [
    {"article_id": "KB-001", "title": "Return Policy", "keywords": ["return", "refund", "policy", "30 days"],
     "body": "Returns accepted within 30 days of delivery. Refunds issued to original payment method."},
    {"article_id": "KB-002", "title": "Shipping Times", "keywords": ["shipping", "delivery", "time", "estimate"],
     "body": "Standard shipping 5-7 business days. Express 2-3 days. International 10-15 days."},
    {"article_id": "KB-003", "title": "Account Security", "keywords": ["security", "password", "2fa", "two factor"],
     "body": "Enable 2FA in settings. Use unique passwords. We never ask for passwords via email."},
    {"article_id": "KB-004", "title": "Subscription Cancellation", "keywords": ["cancel", "subscription", "billing", "refund"],
     "body": "Cancel anytime. Access continues until period end. No prorated refunds."},
    {"article_id": "KB-005", "title": "Order Tracking", "keywords": ["track", "order", "status", "where"],
     "body": "Track orders in your account or use the tracking link in the confirmation email."},
    {"article_id": "KB-006", "title": "Payment Methods", "keywords": ["payment", "card", "paypal", "methods"],
     "body": "Accepted: Visa, Mastercard, Amex, PayPal, Apple Pay, Google Pay."},
    {"article_id": "KB-007", "title": "Gift Cards", "keywords": ["gift", "card", "balance", "redeem"],
     "body": "Gift cards never expire. Check balance in account. Not refundable for cash."},
    {"article_id": "KB-008", "title": "Contact Support", "keywords": ["contact", "support", "help", "phone", "email"],
     "body": "Email support@example.com or use in-app chat. Phone: 1-800-555-0199 (Mon-Fri 9-5 EST)."},
]

# --- Exceptions ---
class ToolTransientError(Exception):
    """Simulated transient network / infra failure."""
    pass


class BusinessRuleError(Exception):
    """Permanent business rule rejection."""
    pass


# --- Transient failure counter (module-level state for the special order ID) ---
_transient_call_count = 0


def _deterministic_int(seed_str: str, max_val: int) -> int:
    return zlib.crc32(seed_str.encode()) % max_val


def lookup_order(order_id: str) -> dict:
    """Deterministic order status from hash of order_id. Special: first call for ORD-TRANSIENT-FAIL raises."""
    global _transient_call_count
    if order_id == "ORD-TRANSIENT-FAIL":
        _transient_call_count += 1
        if _transient_call_count == 1:
            raise ToolTransientError("simulated network blip")

    statuses = ("processing", "shipped", "delivered", "cancelled")
    idx = _deterministic_int(order_id, len(statuses))
    return {
        "order_id": order_id,
        "status": statuses[idx],
        "eta_days": _deterministic_int(f"{order_id}|eta", 10),
        "total_usd": round(10.0 + (_deterministic_int(f"{order_id}|amt", 5000) / 100.0), 2),
    }


def get_account_balance(account_id: str) -> dict:
    return {
        "account_id": account_id,
        "balance_usd": round(50.0 + (_deterministic_int(f"{account_id}|bal", 10000) / 100.0), 2),
        "currency": "USD",
        "last_updated_days_ago": _deterministic_int(f"{account_id}|days", 30),
    }


def search_kb(query: str) -> dict | None:
    """Keyword match (case-insensitive substring/token overlap) — deterministic first match."""
    q = query.lower()
    for art in KB_ARTICLES:
        if any(kw in q for kw in art["keywords"]):
            return art
    return None


def submit_refund(order_id: str, amount_usd: float, reason: str) -> dict:
    if amount_usd <= 0 or amount_usd > 500.0:
        raise BusinessRuleError(f"Refund amount ${amount_usd:.2f} outside policy (0-500)")
    if not order_id.startswith("ORD-"):
        raise BusinessRuleError(f"Invalid order_id format: {order_id}")
    refund_id = f"REF-{_deterministic_int(f'{order_id}|{amount_usd}|{reason}', 1_000_000):06d}"
    return {"refund_id": refund_id, "status": "submitted", "amount_usd": amount_usd}


def format_date(iso_date: str, style: str) -> str:
    from datetime import date
    d = date.fromisoformat(iso_date)
    if style == "long":
        return d.strftime("%B %d, %Y")
    if style == "iso":
        return iso_date
    if style == "short":
        return d.strftime("%m/%d/%Y")
    raise ValueError(f"Unknown style: {style}")


def format_currency(amount: float, currency: str = "USD") -> str:
    sym = {"USD": "$", "EUR": "€", "INR": "₹"}.get(currency.upper(), currency + " ")
    return f"{sym}{amount:,.2f}"


# --- Schemas for validation ---
TOOL_SCHEMAS = {
    "lookup_order": {"required": ["order_id"], "types": {"order_id": "str"}, "enums": {}},
    "get_account_balance": {"required": ["account_id"], "types": {"account_id": "str"}, "enums": {}},
    "search_kb": {"required": ["query"], "types": {"query": "str"}, "enums": {}},
    "submit_refund": {"required": ["order_id", "amount_usd", "reason"],
                      "types": {"order_id": "str", "amount_usd": "float", "reason": "str"}, "enums": {}},
    "format_date": {"required": ["iso_date", "style"],
                    "types": {"iso_date": "str", "style": "str"},
                    "enums": {"style": ["long", "iso", "short"]}},
}

TOOL_REGISTRY = {
    "lookup_order": lookup_order,
    "get_account_balance": get_account_balance,
    "search_kb": search_kb,
    "submit_refund": submit_refund,
    "format_date": format_date,
    "format_currency": format_currency,  # not schema'd, but available
}

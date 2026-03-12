from services.limits import ensure_user, get_limits, decrease_limit, check_rate_limit
from services.balance import get_balance, deduct_balance

PRICES = {
    "referat": 2000,
    "presentation": 3000,
    "tezis": 3000,
    "mustaqil": 2000
}


def can_generate(user_id: int, content_type: str) -> tuple[bool, str]:
    """
    Returns:
      (True, "free")      -> allowed, free attempt used
      (True, "paid")      -> allowed, balance deducted
      (False, "blocked")  -> not allowed
      (False, "rate_limited") -> rate limited
    """
    ensure_user(user_id)

    # Check rate limit for price checking (e.g., 5 checks per minute)
    if not check_rate_limit(user_id, "price_check", 5, 60):
        return False, "rate_limited"

    referat_left, presentation_left, Tezis_left, Mustaqil_left, = get_limits(user_id)

    limits = {
    "referat": referat_left,
    "presentation": presentation_left,
    "tezis": Tezis_left,
    "mustaqil": Mustaqil_left
    }

    free_left = limits.get(content_type, 0)

    # 1️⃣ Free attempt first
    if free_left > 0:
        decrease_limit(user_id, content_type)
        return True, "free"

    # 2️⃣ Check balance
    price = PRICES[content_type]
    balance = get_balance(user_id)

    if balance >= price:
        return True, "paid"

    # 3️⃣ Block
    return False, "blocked"

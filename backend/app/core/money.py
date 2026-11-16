"""Money helpers. Amounts are Decimal everywhere; payment providers want integer cents."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def to_cents(amount: Decimal) -> int:
    """Exact Decimal-to-cents conversion; ``int(amount * 100)`` would truncate fractions."""
    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))

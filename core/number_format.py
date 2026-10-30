from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def format_half_up(value: object, decimals: int, signed: bool = False) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return ""
    if math.isnan(numeric):
        return ""

    try:
        decimal_value = Decimal(str(numeric))
    except InvalidOperation:
        return ""

    quantum = Decimal("1") if decimals <= 0 else Decimal("1").scaleb(-decimals)
    rounded = decimal_value.quantize(quantum, rounding=ROUND_HALF_UP)
    if rounded == 0:
        rounded = rounded.copy_abs()
    text = f"{rounded:.{max(decimals, 0)}f}"
    if signed and rounded >= 0:
        return f"+{text}"
    return text

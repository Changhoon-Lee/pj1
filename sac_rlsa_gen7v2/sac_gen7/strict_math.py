from __future__ import annotations
import math
from decimal import Decimal, localcontext

def softplus_decimal(x: float, precision: int = 120) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = precision
        d = Decimal.from_float(float(x))
        if d >= 0:
            return +(d + (Decimal(1) + (-d).exp()).ln())
        return +(Decimal(1) + d.exp()).ln()

def strict_binary64_upper(reference: Decimal) -> float:
    x = float(reference)
    while Decimal.from_float(x) <= reference:
        x = math.nextafter(x, math.inf)
    return x

def strict_loss_upper(raw_min: float, raw_max: float) -> dict:
    a = softplus_decimal(raw_max)
    b = softplus_decimal(-raw_min)
    ref = max(a, b)
    upper = strict_binary64_upper(ref)
    return {
        "reference_decimal_upper": format(ref, "f"),
        "loss_upper_binary64": upper,
        "binary64_hex": float(upper).hex(),
        "binary64_strictly_above_reference": Decimal.from_float(upper) > ref,
        "construction": "max(softplus_decimal(raw_max),softplus_decimal(-raw_min)); nextafter(+inf) until Decimal.from_float(bound)>reference",
        "decimal_precision": 120,
    }

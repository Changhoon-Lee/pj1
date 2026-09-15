#!/usr/bin/env python3
from __future__ import annotations
import decimal, json, math
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_truth import PRECISION, PLACES, canonical_decimal_loss, serialize_decimal


def main() -> None:
    checks = {}
    checks["precision_80"] = PRECISION == 80
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        checks["context_precision"] = ctx.prec == 80
        checks["round_half_even"] = ctx.rounding == ROUND_HALF_EVEN
        checks["tie_even_down"] = Decimal("1.00000000000000000000000000000000000000004").quantize(Decimal(1).scaleb(-40)) == Decimal("1.0000000000000000000000000000000000000000")
        checks["tie_even_up"] = Decimal("1.00000000000000000000000000000000000000015").quantize(Decimal(1).scaleb(-40)) == Decimal("1.0000000000000000000000000000000000000002")
    checks["negative_zero_normalized"] = serialize_decimal(Decimal("-0E-40")) == ("0." + "0"*40 + "\n").encode("ascii")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        q125 = Decimal("1.25").quantize(Decimal(1).scaleb(-40))
        q1000 = Decimal("1").quantize(Decimal(1).scaleb(-40))
    checks["trailing_zeros"] = serialize_decimal(q125).decode().endswith("2500000000000000000000000000000000000000\n")
    checks["no_exponent"] = b"E" not in serialize_decimal(q1000)
    checks["lf_only"] = b"\r" not in serialize_decimal(canonical_decimal_loss(0.0))
    checks["softplus_zero"] = serialize_decimal(canonical_decimal_loss(0.0)) == b"0.6931471805599453094172321214581765680755\n"
    checks["signed_zero_same"] = canonical_decimal_loss(-0.0) == canonical_decimal_loss(0.0)
    checks["subnormal_finite"] = canonical_decimal_loss(math.ldexp(1.0, -1074)).is_finite()
    checks["nan_fail_closed"] = False
    try:
        canonical_decimal_loss(float("nan"))
    except Exception:
        checks["nan_fail_closed"] = True
    checks["inf_fail_closed"] = False
    try:
        canonical_decimal_loss(float("inf"))
    except Exception:
        checks["inf_fail_closed"] = True
    checks["libmpdec_present"] = bool(getattr(decimal, "__libmpdec_version__", ""))
    result = {"schema":"SAC_GEN7_CANONICAL_TRUTH_SELFTEST_V2","checks":checks,"pass":all(checks.values()),"libmpdec_version":getattr(decimal,"__libmpdec_version__",None)}
    print(json.dumps(result, sort_keys=True, indent=2))
    if not result["pass"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()

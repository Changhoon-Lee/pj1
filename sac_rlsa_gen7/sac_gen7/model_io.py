from __future__ import annotations

import math
import struct
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np


def down(x: float) -> float:
    return math.nextafter(float(x), -math.inf)


def up(x: float) -> float:
    return math.nextafter(float(x), math.inf)


def raw_bounds(clf, x_probe: np.ndarray) -> tuple[float, float, float]:
    init = float(clf._raw_predict_init(np.asarray(x_probe[:1], dtype=np.float32))[0, 0])
    lo = down(init)
    hi = up(init)
    learning_rate = float(clf.learning_rate)
    for estimator in clf.estimators_.ravel():
        tree = estimator.tree_
        leaves = tree.value[tree.children_left == -1, 0, 0].astype(float)
        lo_term = down(learning_rate * float(leaves.min()))
        hi_term = up(learning_rate * float(leaves.max()))
        lo = down(lo + lo_term)
        hi = up(hi + hi_term)
    return init, lo, hi


def _decimal_softplus(x: float) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 120
        dx = Decimal.from_float(float(x))
        one = Decimal(1)
        if dx > 0:
            return dx + (one + (-dx).exp()).ln()
        return (one + dx.exp()).ln()


def strict_loss_upper(raw_min: float, raw_max: float) -> tuple[float, dict]:
    candidates = (_decimal_softplus(raw_max), _decimal_softplus(-raw_min))
    exactish = max(candidates)
    rounded = float(exactish)
    upper = math.nextafter(rounded, math.inf)
    if Decimal.from_float(upper) <= exactish:
        upper = math.nextafter(upper, math.inf)
    return upper, {
        "method": "Decimal(120 digits) endpoint softplus then binary64 nextafter(+inf)",
        "reference_decimal": format(exactish, "f"),
        "rounded_before_nextafter": rounded,
        "strict_binary64_upper": upper,
    }


def export_model(clf, path: Path, x_probe: np.ndarray) -> dict:
    init, raw_min, raw_max = raw_bounds(clf, x_probe)
    loss_upper, loss_bound_meta = strict_loss_upper(raw_min, raw_max)
    trees = list(clf.estimators_.ravel())
    with path.open("wb") as f:
        f.write(b"SACGBM2\0")
        f.write(struct.pack("<IIII", 2, int(clf.n_features_in_), len(trees), 0))
        f.write(struct.pack("<dddddd", float(clf.learning_rate), init, raw_min, raw_max, loss_upper, 0.0))
        for estimator in trees:
            tree = estimator.tree_
            f.write(struct.pack("<II", tree.node_count, int(tree.max_depth)))
            for i in range(tree.node_count):
                f.write(struct.pack("<iii", int(tree.children_left[i]), int(tree.children_right[i]), int(tree.feature[i])))
                f.write(struct.pack("<ddd", float(tree.threshold[i]), float(tree.value[i, 0, 0]), float(tree.weighted_n_node_samples[i])))
    return {
        "init_raw": init,
        "raw_min": raw_min,
        "raw_max": raw_max,
        "loss_upper": loss_upper,
        "n_features": int(clf.n_features_in_),
        "n_trees": len(trees),
        "raw_rounding": "binary64 nextafter outward on init, each tree term, and each accumulation",
        "loss_bound": loss_bound_meta,
    }

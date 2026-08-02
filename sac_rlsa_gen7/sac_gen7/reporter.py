from __future__ import annotations

import argparse
import pickle
import platform
import sys
import time
from pathlib import Path

import numpy as np
from sklearn import datasets
from sklearn.ensemble import GradientBoostingClassifier

from .common import digest_obj, sha256_file, write_json
from .model_io import export_model

PARAMS = {"n_estimators": 100, "min_samples_split": 5, "max_depth": 2, "learning_rate": 0.1, "max_features": 2}
POLICY = {"metric": "mean Bernoulli log loss from raw logits", "formula": "logaddexp(0,raw)-y01*raw", "label_mapping": "y01=1 iff make_hastie label >0", "probability_clipping": "NONE_AUTHORITATIVE_RAW_LOGIT_PATH", "threshold": 0.5, "decision": "PASS iff mean_loss < 0.5"}
TREE_SEMANTICS = {"feature_input_cast": "IEEE-754 binary32 round-to-nearest-even before each split comparison", "comparison": "binary32(x_feature) <= stored binary64 threshold", "leaf_accumulation": "strict ordered binary64 multiply then binary64 add; FMA disabled"}


def generate(out: Path, target_id: str, seed: int, population: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter_ns()
    x, y = datasets.make_hastie_10_2(n_samples=2000 + population, random_state=seed)
    clf = GradientBoostingClassifier(**PARAMS, random_state=seed)
    clf.fit(x[:2000], y[:2000])
    xt = np.ascontiguousarray(x[2000:], dtype="<f8")
    yt = np.ascontiguousarray(y[2000:], dtype="<f8")
    raw = np.asarray(clf.decision_function(xt), dtype="<f8")
    y01 = (yt > 0).astype(np.float64)
    loss = np.asarray(np.logaddexp(0.0, raw) - y01 * raw, dtype="<f8")
    paths = {
        "x": out / f"{target_id}.X.f64",
        "y": out / f"{target_id}.y.f64",
        "raw": out / f"{target_id}.reported_raw.f64",
        "loss": out / f"{target_id}.reported_loss.f64",
        "model": out / f"{target_id}.model.bin",
        "sklearn_model": out / f"{target_id}.sklearn.pkl",
    }
    xt.tofile(paths["x"]); yt.tofile(paths["y"]); raw.tofile(paths["raw"]); loss.tofile(paths["loss"])
    model_meta = export_model(clf, paths["model"], x[:1])
    with paths["sklearn_model"].open("wb") as f:
        pickle.dump(clf, f, protocol=5)
    if not np.isfinite(loss).all():
        raise RuntimeError("nonfinite producer loss")
    if float(loss.max()) > model_meta["loss_upper"]:
        raise RuntimeError("reported loss exceeds strict bound")
    files = {key: {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)} for key, path in paths.items()}
    scientific = {
        "schema": "SAC_GEN7_CANONICAL_SCIENTIFIC_TARGET_REPORT_V1",
        "target_id": target_id,
        "seed": seed,
        "population": population,
        "training_population": 2000,
        "parameters": PARAMS,
        "software_semantics": {"numpy": "2.3.5", "scipy": "1.17.0", "scikit_learn": "1.8.0", "python_major_minor": "3.13"},
        "policy": POLICY,
        "tree_semantics": TREE_SEMANTICS,
        "canonical_truth": {"mode": "REFERENCE_DECIMAL_40DP_FROM_STRICT_BINARY64_RAW", "decimal_context_precision": 80, "serialization": "one signed fixed-point decimal with exactly 40 fractional digits per unit, newline terminated", "raw_identity": "exact SHA-256 of strict binary64 raw-score bytes", "cross_platform_gate": "raw digest and canonical decimal-loss digest identical"},
        "numeric_tolerance": {"producer_vs_independent_raw_abs": 1e-10, "producer_vs_independent_loss_abs": 1e-10, "decision_margin_requirement": "mean tolerance 1e-10 is negligible relative to frozen 0.5 threshold and is not used for canonical digest"},
        "model_bounds": model_meta,
        "reported_mean_loss": float(loss.mean()),
        "reported_min_loss": float(loss.min()),
        "reported_max_loss": float(loss.max()),
        "reported_decision": bool(float(loss.mean()) < 0.5),
        "files": files,
        "target_truth_accessed": False,
    }
    scientific["canonical_report_digest"] = digest_obj(scientific)
    write_json(out / f"{target_id}.SCIENTIFIC_REPORT.json", scientific)
    generation = {"schema": "SAC_GEN7_NONAUTHORITATIVE_GENERATION_RECEIPT_V1", "target_id": target_id, "canonical_report_digest": scientific["canonical_report_digest"], "generation_wall_ns": time.perf_counter_ns() - started, "python": sys.version.split()[0], "platform": platform.platform(), "machine": platform.machine()}
    write_json(out / f"{target_id}.GENERATION_RECEIPT.json", generation)
    return scientific


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--out", required=True); parser.add_argument("--target-id", required=True); parser.add_argument("--seed", type=int, required=True); parser.add_argument("--n", type=int, required=True)
    args = parser.parse_args(); report = generate(Path(args.out), args.target_id, args.seed, args.n); print(report["canonical_report_digest"])


if __name__ == "__main__":
    main()

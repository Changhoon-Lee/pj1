from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import stats

from probe_utils import clip_probability, wilson_interval


@dataclass
class ModelResult:
    name: str
    n: int
    folds: int
    auc: float
    log_loss: float
    brier: float
    positive_rate: float


def _safe_div(num: float, den: float) -> float:
    return float(num / den) if den else float("nan")


def _confusion_counts(df: pd.DataFrame) -> dict[str, int]:
    x = df.dropna(subset=["receipt", "proxy"])
    r = x["receipt"].astype(int)
    p = x["proxy"].astype(int)
    return {
        "TP": int(((r == 1) & (p == 1)).sum()),
        "FP": int(((r == 0) & (p == 1)).sum()),
        "FN": int(((r == 1) & (p == 0)).sum()),
        "TN": int(((r == 0) & (p == 0)).sum()),
        "N": int(len(x)),
    }


def confusion_table_and_metrics(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    c = _confusion_counts(df)
    tp, fp, fn, tn, n = c["TP"], c["FP"], c["FN"], c["TN"], c["N"]
    matrix = pd.DataFrame(
        [[tp, fp], [fn, tn]],
        index=["Proxy=1", "Proxy=0"],
        columns=["Receipt=1", "Receipt=0"],
    ).reset_index(names="classification")
    values = {
        "precision_ppv": _safe_div(tp, tp + fp),
        "recall_sensitivity": _safe_div(tp, tp + fn),
        "specificity": _safe_div(tn, tn + fp),
        "npv": _safe_div(tn, tn + fn),
        "false_positive_rate": _safe_div(fp, fp + tn),
        "false_negative_rate": _safe_div(fn, fn + tp),
        "f1": _safe_div(2 * tp, 2 * tp + fp + fn),
        "accuracy": _safe_div(tp + tn, n),
        "balanced_accuracy": np.nanmean([
            _safe_div(tp, tp + fn), _safe_div(tn, tn + fp)
        ]),
        "receipt_prevalence": _safe_div(tp + fn, n),
        "proxy_prevalence": _safe_div(tp + fp, n),
    }
    values["absolute_prevalence_bias"] = values["proxy_prevalence"] - values["receipt_prevalence"]
    values["relative_prevalence_bias"] = _safe_div(
        values["absolute_prevalence_bias"], values["receipt_prevalence"]
    )

    rows: list[dict[str, Any]] = []
    ci_specs = {
        "precision_ppv": (tp, tp + fp),
        "recall_sensitivity": (tp, tp + fn),
        "specificity": (tn, tn + fp),
        "npv": (tn, tn + fn),
        "accuracy": (tp + tn, n),
        "receipt_prevalence": (tp + fn, n),
        "proxy_prevalence": (tp + fp, n),
    }
    for metric, value in values.items():
        lo, hi = (float("nan"), float("nan"))
        if metric in ci_specs:
            lo, hi = wilson_interval(*ci_specs[metric])
        rows.append({"metric": metric, "estimate": value, "wilson_lo": lo, "wilson_hi": hi})
    return matrix, pd.DataFrame(rows), values


def cluster_bootstrap_metrics(
    df: pd.DataFrame,
    cluster_cols: list[str],
    reps: int,
    seed: int,
) -> pd.DataFrame:
    x = df.dropna(subset=["receipt", "proxy"] + cluster_cols).copy()
    x["tp"] = ((x["receipt"] == 1) & (x["proxy"] == 1)).astype(int)
    x["fp"] = ((x["receipt"] == 0) & (x["proxy"] == 1)).astype(int)
    x["fn"] = ((x["receipt"] == 1) & (x["proxy"] == 0)).astype(int)
    x["tn"] = ((x["receipt"] == 0) & (x["proxy"] == 0)).astype(int)
    key = x[cluster_cols].astype(str).agg("|".join, axis=1)
    agg = x.assign(_cluster=key).groupby("_cluster")[["tp", "fp", "fn", "tn"]].sum()
    if len(agg) < 2:
        return pd.DataFrame()
    arr = agg.to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    records: list[dict[str, float]] = []
    for b in range(reps):
        idx = rng.integers(0, len(arr), size=len(arr))
        tp, fp, fn, tn = arr[idx].sum(axis=0)
        receipt_rate = _safe_div(tp + fn, tp + fp + fn + tn)
        proxy_rate = _safe_div(tp + fp, tp + fp + fn + tn)
        records.append({
            "rep": b,
            "precision_ppv": _safe_div(tp, tp + fp),
            "recall_sensitivity": _safe_div(tp, tp + fn),
            "receipt_prevalence": receipt_rate,
            "proxy_prevalence": proxy_rate,
            "absolute_prevalence_bias": proxy_rate - receipt_rate,
            "relative_prevalence_bias": _safe_div(proxy_rate - receipt_rate, receipt_rate),
        })
    return pd.DataFrame(records)


def bootstrap_summary(draws: pd.DataFrame, label: str) -> pd.DataFrame:
    if draws.empty:
        return pd.DataFrame()
    rows = []
    for col in draws.columns:
        if col == "rep":
            continue
        s = pd.to_numeric(draws[col], errors="coerce").dropna()
        if s.empty:
            continue
        rows.append({
            "bootstrap": label,
            "metric": col,
            "mean": s.mean(),
            "lo_025": s.quantile(0.025),
            "hi_975": s.quantile(0.975),
            "sd": s.std(ddof=1),
            "reps_valid": len(s),
        })
    return pd.DataFrame(rows)


def denominator_audit(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    masks: list[tuple[str, pd.Series, str]] = [
        ("all_product_days", pd.Series(True, index=df.index), "product-day filing prevalence; not legal compliance"),
    ]
    if df["candidate"].notna().any():
        masks.append((
            "candidate_events",
            df["candidate"].fillna(0).eq(1),
            "candidate-event filing rate; legal obligation denominator not assumed",
        ))
    if df["running"].notna().any():
        masks.append((
            "nonnegative_running",
            df["running"].ge(0),
            "threshold-crossing event rate; only valid if running variable definition is verified",
        ))
    for label, mask, interpretation in masks:
        x = df.loc[mask & df["receipt"].notna() & df["proxy"].notna()]
        if x.empty:
            continue
        receipt_rate = x["receipt"].mean()
        proxy_rate = x["proxy"].mean()
        rows.append({
            "denominator": label,
            "N": len(x),
            "receipt_positive": int(x["receipt"].sum()),
            "proxy_positive": int(x["proxy"].sum()),
            "receipt_rate": receipt_rate,
            "proxy_rate": proxy_rate,
            "bias_pp": 100 * (proxy_rate - receipt_rate),
            "relative_bias": _safe_div(proxy_rate - receipt_rate, receipt_rate),
            "interpretation": interpretation,
        })
    return pd.DataFrame(rows)


def issuer_metrics(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    x = df.dropna(subset=["issuer", "receipt", "proxy"]).copy()
    grouped = []
    for issuer, g in x.groupby("issuer", dropna=False):
        c = _confusion_counts(g)
        tp, fp, fn, tn = c["TP"], c["FP"], c["FN"], c["TN"]
        n = c["N"]
        receipt_rate = _safe_div(tp + fn, n)
        proxy_rate = _safe_div(tp + fp, n)
        grouped.append({
            "issuer": issuer,
            "N": n,
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "TN": tn,
            "receipt_positive": tp + fn,
            "proxy_positive": tp + fp,
            "precision": _safe_div(tp, tp + fp),
            "sensitivity": _safe_div(tp, tp + fn),
            "receipt_rate": receipt_rate,
            "proxy_rate": proxy_rate,
            "rate_bias": proxy_rate - receipt_rate,
            "relative_rate_bias": _safe_div(proxy_rate - receipt_rate, receipt_rate),
        })
    table = pd.DataFrame(grouped)
    if table.empty:
        return table, pd.DataFrame(), {}

    # Beta-binomial empirical Bayes shrinkage for sensitivity.
    valid = table[table["receipt_positive"] > 0].copy()
    pooled = valid["TP"].sum() / valid["receipt_positive"].sum()
    raw = valid["sensitivity"].astype(float)
    weights = valid["receipt_positive"].astype(float)
    observed_var = np.average((raw - pooled) ** 2, weights=weights)
    sampling_var = np.average(
        pooled * (1 - pooled) / valid["receipt_positive"].clip(lower=1),
        weights=weights,
    )
    latent_var = max(observed_var - sampling_var, 1e-8)
    common = max(pooled * (1 - pooled) / latent_var - 1, 2.0)
    alpha = max(pooled * common, 0.5)
    beta = max((1 - pooled) * common, 0.5)
    valid["eb_alpha_prior"] = alpha
    valid["eb_beta_prior"] = beta
    valid["sensitivity_eb"] = (valid["TP"] + alpha) / (valid["receipt_positive"] + alpha + beta)
    valid["sensitivity_eb_lo"] = stats.beta.ppf(0.025, valid["TP"] + alpha, valid["FN"] + beta)
    valid["sensitivity_eb_hi"] = stats.beta.ppf(0.975, valid["TP"] + alpha, valid["FN"] + beta)

    # Heterogeneity chi-square across issuers among receipt-positive observations.
    contingency = valid[["TP", "FN"]].to_numpy()
    if contingency.shape[0] >= 2 and contingency.sum() > 0:
        chi2, pvalue, dof, _ = stats.chi2_contingency(contingency)
    else:
        chi2, pvalue, dof = float("nan"), float("nan"), 0

    rank = table[table["N"] > 0].copy()
    rank["proxy_rank"] = rank["proxy_rate"].rank(ascending=False, method="average")
    rank["receipt_rank"] = rank["receipt_rate"].rank(ascending=False, method="average")
    rank["rank_change"] = rank["proxy_rank"] - rank["receipt_rank"]
    if len(rank) >= 3:
        rho, rho_p = stats.spearmanr(rank["proxy_rate"], rank["receipt_rate"])
        tau, tau_p = stats.kendalltau(rank["proxy_rate"], rank["receipt_rate"])
    else:
        rho = rho_p = tau = tau_p = float("nan")
    q = min(4, max(1, len(rank)))
    try:
        rank["proxy_quartile"] = pd.qcut(rank["proxy_rate"].rank(method="first"), q, labels=False, duplicates="drop")
        rank["receipt_quartile"] = pd.qcut(rank["receipt_rate"].rank(method="first"), q, labels=False, duplicates="drop")
        quartile_reclass = (rank["proxy_quartile"] != rank["receipt_quartile"]).mean()
    except ValueError:
        quartile_reclass = float("nan")
    summary = {
        "heterogeneity_chi2": float(chi2),
        "heterogeneity_p": float(pvalue),
        "heterogeneity_dof": int(dof),
        "spearman_rho": float(rho),
        "spearman_p": float(rho_p),
        "kendall_tau": float(tau),
        "kendall_p": float(tau_p),
        "mean_abs_rank_change": float(rank["rank_change"].abs().mean()),
        "max_abs_rank_change": float(rank["rank_change"].abs().max()),
        "quartile_reclassification_rate": float(quartile_reclass),
        "raw_sensitivity_sd": float(valid["sensitivity"].std(ddof=1)),
        "eb_sensitivity_sd": float(valid["sensitivity_eb"].std(ddof=1)),
    }
    return table.merge(rank[["issuer", "proxy_rank", "receipt_rank", "rank_change"]], on="issuer", how="left"), valid, summary


def _prepare_model_frame(receipt_positive: pd.DataFrame) -> pd.DataFrame:
    x = receipt_positive.copy()
    x["miss"] = x["miss"].astype(int)
    x["log_batch_size"] = np.log1p(pd.to_numeric(x["batch_size"], errors="coerce").fillna(1).clip(lower=1))
    for c in ["multi_product", "correction", "batch", "weekday", "year"]:
        x[c] = x[c].astype("string").fillna("MISSING")
    for c in ["severity", "congestion", "episode_length", "staleness", "title_length"]:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    x["issuer"] = x["issuer"].astype("string").fillna("UNKNOWN")
    x["title_signature"] = x["title_signature"].astype("string").fillna("MISSING")
    # Avoid thousands of one-off signatures; rare signatures become OTHER.
    sig_count = x["title_signature"].value_counts()
    x.loc[~x["title_signature"].isin(sig_count[sig_count >= 5].index), "title_signature"] = "OTHER"
    return x


def mechanism_models(df: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
    from sklearn.model_selection import GroupKFold, StratifiedKFold
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    x = _prepare_model_frame(df.loc[df["receipt"].eq(1)].copy())
    if len(x) < 100 or x["miss"].nunique() < 2:
        return pd.DataFrame(), pd.DataFrame(), {"status": "INSUFFICIENT_RECEIPT_POSITIVES"}

    specs: dict[str, dict[str, list[str]]] = {
        "baseline_time": {
            "cat": ["year"],
            "num": [],
        },
        "issuer_only": {
            "cat": ["year", "issuer"],
            "num": [],
        },
        "architecture_only": {
            "cat": ["year", "multi_product", "correction", "batch", "title_signature"],
            "num": ["log_batch_size", "title_length"],
        },
        "full_architecture_economic": {
            "cat": ["year", "issuer", "multi_product", "correction", "batch", "weekday", "title_signature"],
            "num": ["log_batch_size", "title_length", "severity", "congestion", "episode_length", "staleness"],
        },
    }

    groups = x["issuer"].astype(str).to_numpy()
    unique_groups = pd.unique(groups)
    if len(unique_groups) >= 5:
        splitter = GroupKFold(n_splits=min(5, len(unique_groups)))
        splits = list(splitter.split(x, x["miss"], groups))
    else:
        splitter = StratifiedKFold(n_splits=min(5, int(x["miss"].value_counts().min())), shuffle=True, random_state=seed)
        splits = list(splitter.split(x, x["miss"]))

    metric_rows: list[dict[str, Any]] = []
    coefficient_rows: list[dict[str, Any]] = []
    fitted_full = None
    full_cols: list[str] = []

    for name, spec in specs.items():
        cat_cols = [c for c in spec["cat"] if c in x.columns and x[c].nunique(dropna=False) > 1]
        num_cols = [c for c in spec["num"] if c in x.columns and x[c].notna().sum() >= 20 and x[c].nunique(dropna=True) > 1]
        transformers = []
        if cat_cols:
            transformers.append((
                "cat",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=3)),
                ]),
                cat_cols,
            ))
        if num_cols:
            transformers.append((
                "num",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scale", StandardScaler()),
                ]),
                num_cols,
            ))
        pre = ColumnTransformer(transformers, remainder="drop")
        model = LogisticRegression(max_iter=3000, C=1.0, solver="liblinear", random_state=seed)
        pipe = Pipeline([("pre", pre), ("model", model)])
        oof = np.full(len(x), np.nan)
        for train, test in splits:
            if x.iloc[train]["miss"].nunique() < 2:
                oof[test] = x.iloc[train]["miss"].mean()
                continue
            pipe.fit(x.iloc[train], x.iloc[train]["miss"])
            oof[test] = pipe.predict_proba(x.iloc[test])[:, 1]
        valid = np.isfinite(oof)
        y = x.loc[valid, "miss"].to_numpy()
        pred = np.clip(oof[valid], 1e-6, 1 - 1e-6)
        auc = roc_auc_score(y, pred) if len(np.unique(y)) > 1 else float("nan")
        metric_rows.append({
            "model": name,
            "N": int(valid.sum()),
            "folds": len(splits),
            "auc": auc,
            "log_loss": log_loss(y, pred),
            "brier": brier_score_loss(y, pred),
            "miss_rate": y.mean(),
            "categorical_features": ";".join(cat_cols),
            "numeric_features": ";".join(num_cols),
        })
        pipe.fit(x, x["miss"])
        if name == "full_architecture_economic":
            fitted_full = pipe
            full_cols = cat_cols + num_cols

    if fitted_full is not None:
        try:
            names = fitted_full.named_steps["pre"].get_feature_names_out()
            coefs = fitted_full.named_steps["model"].coef_[0]
            coefficient_rows = [
                {"feature": str(feature), "log_odds_coefficient": float(coef), "odds_ratio": float(np.exp(np.clip(coef, -20, 20)))}
                for feature, coef in sorted(zip(names, coefs), key=lambda t: abs(t[1]), reverse=True)
            ]
        except Exception as exc:
            coefficient_rows = [{"feature": "COEFFICIENT_EXTRACTION_FAILED", "log_odds_coefficient": np.nan, "odds_ratio": np.nan, "error": str(exc)}]

    metrics = pd.DataFrame(metric_rows)
    by_name = metrics.set_index("model") if not metrics.empty else pd.DataFrame()
    base_ll = by_name.loc["baseline_time", "log_loss"] if "baseline_time" in by_name.index else np.nan
    arch_ll = by_name.loc["architecture_only", "log_loss"] if "architecture_only" in by_name.index else np.nan
    issuer_ll = by_name.loc["issuer_only", "log_loss"] if "issuer_only" in by_name.index else np.nan
    full_ll = by_name.loc["full_architecture_economic", "log_loss"] if "full_architecture_economic" in by_name.index else np.nan
    summary = {
        "status": "OK",
        "receipt_positive_N": len(x),
        "miss_rate": float(x["miss"].mean()),
        "architecture_logloss_improvement_vs_time": _safe_div(base_ll - arch_ll, base_ll),
        "issuer_logloss_improvement_vs_time": _safe_div(base_ll - issuer_ll, base_ll),
        "full_logloss_improvement_vs_time": _safe_div(base_ll - full_ll, base_ll),
        "architecture_increment_beyond_issuer": _safe_div(issuer_ll - full_ll, issuer_ll),
        "full_features": full_cols,
    }
    return metrics, pd.DataFrame(coefficient_rows), summary


def issuer_fe_attenuation(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    import statsmodels.formula.api as smf

    x = _prepare_model_frame(df.loc[df["receipt"].eq(1)].copy())
    x = x.dropna(subset=["miss", "issuer"])
    if len(x) < 100 or x["issuer"].nunique() < 3:
        return pd.DataFrame(), {"status": "INSUFFICIENT_DATA"}
    formulas = {
        "issuer_time": "miss ~ C(issuer) + C(year)",
        "issuer_plus_architecture": (
            "miss ~ C(issuer) + C(year) + log_batch_size + C(multi_product) + "
            "C(correction) + C(batch) + title_length"
        ),
        "issuer_plus_full": (
            "miss ~ C(issuer) + C(year) + log_batch_size + C(multi_product) + "
            "C(correction) + C(batch) + title_length + severity + congestion + "
            "episode_length + staleness"
        ),
    }
    rows: list[dict[str, Any]] = []
    issuer_sd: dict[str, float] = {}
    for name, formula in formulas.items():
        cols = ["miss", "issuer", "year", "log_batch_size", "multi_product", "correction", "batch", "title_length"]
        if name == "issuer_plus_full":
            cols += ["severity", "congestion", "episode_length", "staleness"]
        used = x.copy()
        # Patsy drops missing; retain model if optional economic features are mostly absent.
        if name == "issuer_plus_full":
            available = [c for c in ["severity", "congestion", "episode_length", "staleness"] if used[c].notna().sum() >= 50]
            rhs = "miss ~ C(issuer) + C(year) + log_batch_size + C(multi_product) + C(correction) + C(batch) + title_length"
            if available:
                rhs += " + " + " + ".join(available)
            formula = rhs
        try:
            fit = smf.ols(formula, data=used).fit(cov_type="cluster", cov_kwds={"groups": used.loc[fit_index_placeholder(used), "issuer"]})
        except Exception:
            # statsmodels does not expose rows before fitting; fit once then align cluster groups.
            try:
                preliminary = smf.ols(formula, data=used).fit()
                group = used.loc[preliminary.model.data.row_labels, "issuer"]
                fit = preliminary.get_robustcov_results(cov_type="cluster", groups=group)
            except Exception as exc:
                rows.append({"model": name, "term": "MODEL_FAILED", "coef": np.nan, "se": np.nan, "p": np.nan, "error": str(exc)})
                continue
        params = pd.Series(fit.params, index=fit.model.exog_names)
        bse = pd.Series(fit.bse, index=fit.model.exog_names)
        pvals = pd.Series(fit.pvalues, index=fit.model.exog_names)
        issuer_terms = params[params.index.str.startswith("C(issuer)")]
        issuer_sd[name] = float(issuer_terms.std(ddof=1)) if len(issuer_terms) > 1 else 0.0
        for term in params.index:
            if term.startswith("C(issuer)") or term in {"Intercept"}:
                continue
            rows.append({
                "model": name,
                "term": term,
                "coef": float(params[term]),
                "se": float(bse[term]),
                "p": float(pvals[term]),
                "N": int(fit.nobs),
                "r2": float(getattr(fit, "rsquared", np.nan)),
                "issuer_fe_sd": issuer_sd[name],
            })
    base = issuer_sd.get("issuer_time", np.nan)
    arch = issuer_sd.get("issuer_plus_architecture", np.nan)
    full = issuer_sd.get("issuer_plus_full", np.nan)
    summary = {
        "status": "OK" if issuer_sd else "FAILED",
        "issuer_fe_sd_time": base,
        "issuer_fe_sd_architecture": arch,
        "issuer_fe_sd_full": full,
        "issuer_fe_sd_attenuation_architecture": _safe_div(base - arch, base),
        "issuer_fe_sd_attenuation_full": _safe_div(base - full, base),
    }
    return pd.DataFrame(rows), summary


def fit_index_placeholder(df: pd.DataFrame) -> pd.Index:
    # Deliberately raises so the safe two-pass branch is used; kept as a named hook for tests.
    raise RuntimeError("two-pass cluster alignment required")


def rank_distortion(issuer_table: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    if issuer_table.empty:
        return pd.DataFrame(), {}
    x = issuer_table.copy()
    q = min(4, max(1, len(x)))
    x["proxy_rank"] = x["proxy_rate"].rank(ascending=False, method="average")
    x["receipt_rank"] = x["receipt_rate"].rank(ascending=False, method="average")
    x["rank_change"] = x["proxy_rank"] - x["receipt_rank"]
    try:
        x["proxy_quartile"] = pd.qcut(x["proxy_rate"].rank(method="first"), q, labels=False, duplicates="drop")
        x["receipt_quartile"] = pd.qcut(x["receipt_rate"].rank(method="first"), q, labels=False, duplicates="drop")
    except ValueError:
        x["proxy_quartile"] = np.nan
        x["receipt_quartile"] = np.nan
    rho, rho_p = stats.spearmanr(x["proxy_rate"], x["receipt_rate"]) if len(x) > 2 else (np.nan, np.nan)
    tau, tau_p = stats.kendalltau(x["proxy_rate"], x["receipt_rate"]) if len(x) > 2 else (np.nan, np.nan)
    summary = {
        "spearman_rho": float(rho),
        "spearman_p": float(rho_p),
        "kendall_tau": float(tau),
        "kendall_p": float(tau_p),
        "mean_abs_rank_change": float(x["rank_change"].abs().mean()),
        "max_abs_rank_change": float(x["rank_change"].abs().max()),
        "quartile_reclassification_rate": float((x["proxy_quartile"] != x["receipt_quartile"]).mean()),
    }
    return x, summary


def dispersion_distortion(issuer_table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for measure in ["proxy_rate", "receipt_rate"]:
        s = issuer_table[measure].dropna()
        if s.empty:
            continue
        rows.append({
            "measure": measure,
            "N_issuers": len(s),
            "mean": s.mean(),
            "sd": s.std(ddof=1),
            "variance": s.var(ddof=1),
            "range": s.max() - s.min(),
            "iqr": s.quantile(0.75) - s.quantile(0.25),
        })
    out = pd.DataFrame(rows)
    if len(out) == 2:
        receipt_var = out.loc[out["measure"] == "receipt_rate", "variance"].iloc[0]
        proxy_var = out.loc[out["measure"] == "proxy_rate", "variance"].iloc[0]
        out["variance_bias_relative_to_receipt"] = (proxy_var - receipt_var) / receipt_var if receipt_var else np.nan
    return out


def _iterative_two_way_demean(frame: pd.DataFrame, cols: list[str], g1: str, g2: str, max_iter: int = 100, tol: float = 1e-10) -> pd.DataFrame:
    z = frame[cols].astype(float).copy()
    previous = np.inf
    for _ in range(max_iter):
        z = z - z.groupby(frame[g1]).transform("mean")
        z = z - z.groupby(frame[g2]).transform("mean")
        current = float(np.nanmax(np.abs(z.mean(axis=0).to_numpy())))
        if abs(previous - current) < tol:
            break
        previous = current
    return z


def _within_ols(frame: pd.DataFrame, y: str, predictors: list[str]) -> dict[str, Any]:
    import statsmodels.api as sm
    from statsmodels.stats.sandwich_covariance import cov_cluster_2groups

    cols = [y] + predictors
    x = frame.dropna(subset=cols + ["issuer", "date"]).copy()
    if len(x) < 200 or x["issuer"].nunique() < 2 or x["date"].nunique() < 2:
        return {"status": "INSUFFICIENT_DATA", "N": len(x)}
    dm = _iterative_two_way_demean(x, cols, "issuer", "date")
    X = dm[predictors]
    keep = [c for c in predictors if np.nanstd(X[c]) > 1e-12]
    if not keep:
        return {"status": "NO_WITHIN_VARIATION", "N": len(x)}
    fit = sm.OLS(dm[y], X[keep], missing="drop").fit()
    try:
        cov = cov_cluster_2groups(fit, x.loc[fit.model.data.row_labels, "issuer"], x.loc[fit.model.data.row_labels, "date"])[0]
        se = np.sqrt(np.diag(cov))
    except Exception:
        robust = fit.get_robustcov_results(cov_type="HC1")
        cov = robust.cov_params()
        se = np.sqrt(np.diag(cov))
    params = np.asarray(fit.params)
    z = params / se
    p = 2 * stats.norm.sf(np.abs(z))
    return {
        "status": "OK",
        "N": int(fit.nobs),
        "predictors": keep,
        "coef": dict(zip(keep, params.astype(float))),
        "se": dict(zip(keep, se.astype(float))),
        "p": dict(zip(keep, p.astype(float))),
        "r2_within": float(fit.rsquared),
    }


def regression_distortion(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    x = df.copy()
    predictors = []
    if x["severity"].notna().sum() >= 200 and x["severity"].nunique(dropna=True) > 2:
        x["severity_z"] = (x["severity"] - x["severity"].mean()) / x["severity"].std(ddof=0)
        predictors.append("severity_z")
    if x["congestion"].notna().sum() >= 200 and x["congestion"].nunique(dropna=True) > 2:
        x["congestion_z"] = (x["congestion"] - x["congestion"].mean()) / x["congestion"].std(ddof=0)
        predictors.append("congestion_z")
    if {"severity_z", "congestion_z"}.issubset(x.columns):
        x["severity_x_congestion"] = x["severity_z"] * x["congestion_z"]
        predictors.append("severity_x_congestion")
    if not predictors:
        return pd.DataFrame(), {"status": "NO_USABLE_PREDICTORS"}

    receipt_fit = _within_ols(x, "receipt", predictors)
    proxy_fit = _within_ols(x, "proxy", predictors)
    rows = []
    max_relative_bias = 0.0
    sign_change = False
    for term in predictors:
        br = receipt_fit.get("coef", {}).get(term, np.nan)
        bp = proxy_fit.get("coef", {}).get(term, np.nan)
        rel = _safe_div(bp - br, abs(br))
        if np.isfinite(rel):
            max_relative_bias = max(max_relative_bias, abs(rel))
        if np.isfinite(br) and np.isfinite(bp) and br * bp < 0:
            sign_change = True
        rows.append({
            "term": term,
            "receipt_coef": br,
            "receipt_se": receipt_fit.get("se", {}).get(term, np.nan),
            "receipt_p": receipt_fit.get("p", {}).get(term, np.nan),
            "proxy_coef": bp,
            "proxy_se": proxy_fit.get("se", {}).get(term, np.nan),
            "proxy_p": proxy_fit.get("p", {}).get(term, np.nan),
            "bias_proxy_minus_receipt": bp - br if np.isfinite(bp) and np.isfinite(br) else np.nan,
            "relative_bias_abs_receipt": rel,
            "sign_change": bool(np.isfinite(br) and np.isfinite(bp) and br * bp < 0),
            "N_receipt": receipt_fit.get("N", np.nan),
            "N_proxy": proxy_fit.get("N", np.nan),
        })
    summary = {
        "status": "OK" if receipt_fit.get("status") == "OK" and proxy_fit.get("status") == "OK" else "PARTIAL",
        "max_absolute_relative_coefficient_bias": max_relative_bias,
        "any_sign_change": sign_change,
        "receipt_within_r2": receipt_fit.get("r2_within", np.nan),
        "proxy_within_r2": proxy_fit.get("r2_within", np.nan),
    }
    return pd.DataFrame(rows), summary


def market_association_distortion(df: pd.DataFrame) -> pd.DataFrame:
    outcomes = [c for c in ["abs_ret_next1", "repeat_breach_1d", "repeat_breach_5d", "gap_reversion_1", "gap_reversion_5"] if c in df.columns]
    rows = []
    for outcome in outcomes:
        base = df[[outcome, "receipt", "proxy", "issuer", "date", "severity", "congestion"]].copy()
        controls = []
        if base["severity"].notna().sum() >= 200 and base["severity"].nunique(dropna=True) > 2:
            base["severity_z"] = (base["severity"] - base["severity"].mean()) / base["severity"].std(ddof=0)
            controls.append("severity_z")
        if base["congestion"].notna().sum() >= 200 and base["congestion"].nunique(dropna=True) > 2:
            base["congestion_z"] = (base["congestion"] - base["congestion"].mean()) / base["congestion"].std(ddof=0)
            controls.append("congestion_z")
        rfit = _within_ols(base, outcome, ["receipt"] + controls)
        pfit = _within_ols(base, outcome, ["proxy"] + controls)
        br = rfit.get("coef", {}).get("receipt", np.nan)
        bp = pfit.get("coef", {}).get("proxy", np.nan)
        rows.append({
            "outcome": outcome,
            "receipt_association": br,
            "receipt_se": rfit.get("se", {}).get("receipt", np.nan),
            "receipt_p": rfit.get("p", {}).get("receipt", np.nan),
            "proxy_association": bp,
            "proxy_se": pfit.get("se", {}).get("proxy", np.nan),
            "proxy_p": pfit.get("p", {}).get("proxy", np.nan),
            "association_bias": bp - br if np.isfinite(bp) and np.isfinite(br) else np.nan,
            "relative_association_bias": _safe_div(bp - br, abs(br)),
            "sign_change": bool(np.isfinite(br) and np.isfinite(bp) and br * bp < 0),
            "N_receipt": rfit.get("N", np.nan),
            "N_proxy": pfit.get("N", np.nan),
            "interpretation": "associational measurement distortion only; not a causal filing effect",
        })
    return pd.DataFrame(rows)


def cross_fitted_calibration(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    x = df.dropna(subset=["receipt", "proxy", "issuer"]).copy()
    if x.empty or x["issuer"].nunique() < 3:
        return pd.DataFrame(), {"status": "INSUFFICIENT_ISSUERS"}
    rows: list[dict[str, Any]] = []

    def apply_split(train: pd.DataFrame, test: pd.DataFrame, split_type: str, heldout: str) -> None:
        c = _confusion_counts(train)
        sens = _safe_div(c["TP"], c["TP"] + c["FN"])
        fpr = _safe_div(c["FP"], c["FP"] + c["TN"])
        denom = sens - fpr
        proxy_rate = test["proxy"].mean()
        truth = test["receipt"].mean()
        corrected = clip_probability((proxy_rate - fpr) / denom) if np.isfinite(denom) and abs(denom) > 1e-6 else np.nan
        rows.append({
            "split_type": split_type,
            "heldout": heldout,
            "N_test": len(test),
            "train_sensitivity": sens,
            "train_fpr": fpr,
            "proxy_rate_test": proxy_rate,
            "corrected_rate_test": corrected,
            "receipt_rate_test": truth,
            "raw_abs_error": abs(proxy_rate - truth),
            "corrected_abs_error": abs(corrected - truth) if np.isfinite(corrected) else np.nan,
        })

    for issuer, test in x.groupby("issuer"):
        train = x[x["issuer"] != issuer]
        if len(test) >= 20 and train["receipt"].sum() >= 20:
            apply_split(train, test, "leave_one_issuer_out", str(issuer))
    if x["year"].notna().any() and x["year"].nunique(dropna=True) >= 2:
        for year, test in x.groupby("year", dropna=True):
            train = x[x["year"] != year]
            if len(test) >= 20 and train["receipt"].sum() >= 20:
                apply_split(train, test, "leave_one_year_out", str(year))
    table = pd.DataFrame(rows)
    if table.empty:
        return table, {"status": "NO_VALID_SPLITS"}
    valid = table.dropna(subset=["corrected_abs_error"])
    raw_mae = np.average(valid["raw_abs_error"], weights=valid["N_test"]) if not valid.empty else np.nan
    corrected_mae = np.average(valid["corrected_abs_error"], weights=valid["N_test"]) if not valid.empty else np.nan
    summary = {
        "status": "OK",
        "splits": len(valid),
        "weighted_raw_mae": float(raw_mae),
        "weighted_corrected_mae": float(corrected_mae),
        "mae_improvement": _safe_div(raw_mae - corrected_mae, raw_mae),
        "share_splits_improved": float((valid["corrected_abs_error"] < valid["raw_abs_error"]).mean()),
    }
    return table, summary


def monthly_sensitivity_and_break(df: pd.DataFrame, seed: int, permutations: int = 999) -> tuple[pd.DataFrame, dict[str, Any]]:
    x = df.loc[df["receipt"].eq(1) & df["month"].notna()].copy()
    if x.empty:
        return pd.DataFrame(), {"status": "NO_MONTH_DATA"}
    monthly = x.groupby("month").agg(receipt_positive=("receipt", "size"), TP=("proxy", "sum")).reset_index()
    monthly["FN"] = monthly["receipt_positive"] - monthly["TP"]
    monthly["sensitivity"] = monthly["TP"] / monthly["receipt_positive"]
    monthly = monthly.sort_values("month").reset_index(drop=True)
    if len(monthly) < 12:
        return monthly, {"status": "TOO_FEW_MONTHS_FOR_BREAK", "months": len(monthly)}
    min_side = max(4, len(monthly) // 6)
    candidates = []
    for split in range(min_side, len(monthly) - min_side + 1):
        left = monthly.iloc[:split]
        right = monthly.iloc[split:]
        p1 = left["TP"].sum() / left["receipt_positive"].sum()
        p2 = right["TP"].sum() / right["receipt_positive"].sum()
        pooled = (left["TP"].sum() + right["TP"].sum()) / (left["receipt_positive"].sum() + right["receipt_positive"].sum())
        se = math.sqrt(pooled * (1 - pooled) * (1 / left["receipt_positive"].sum() + 1 / right["receipt_positive"].sum()))
        z = (p2 - p1) / se if se > 0 else 0.0
        candidates.append((abs(z), split, p1, p2, z))
    best = max(candidates, key=lambda t: t[0])
    _, split, p1, p2, z_obs = best

    # Exploratory max-stat permutation over receipt-positive rows, shuffled within issuer.
    rng = np.random.default_rng(seed)
    data = x[["issuer", "month", "proxy"]].copy()
    max_stats = []
    for _ in range(permutations):
        shuffled = data.copy()
        shuffled["proxy"] = shuffled.groupby("issuer")["proxy"].transform(lambda s: rng.permutation(s.to_numpy()))
        m = shuffled.groupby("month").agg(n=("proxy", "size"), tp=("proxy", "sum")).reindex(monthly["month"]).reset_index()
        local_max = 0.0
        for s in range(min_side, len(m) - min_side + 1):
            l, r = m.iloc[:s], m.iloc[s:]
            a, b = l["tp"].sum(), r["tp"].sum()
            na, nb = l["n"].sum(), r["n"].sum()
            pp = (a + b) / (na + nb)
            se = math.sqrt(pp * (1 - pp) * (1 / na + 1 / nb)) if 0 < pp < 1 else 0
            zz = abs((b / nb - a / na) / se) if se > 0 else 0
            local_max = max(local_max, zz)
        max_stats.append(local_max)
    p_perm = (1 + np.sum(np.asarray(max_stats) >= abs(z_obs))) / (1 + permutations)
    summary = {
        "status": "EXPLORATORY_ONLY",
        "break_after_month": str(monthly.iloc[split - 1]["month"]),
        "next_month": str(monthly.iloc[split]["month"]),
        "sensitivity_before": float(p1),
        "sensitivity_after": float(p2),
        "z_max": float(z_obs),
        "max_stat_permutation_p": float(p_perm),
        "warning": "data-driven break; not a policy effect and not confirmatory",
    }
    return monthly, summary


def leave_one_out_robustness(df: pd.DataFrame) -> pd.DataFrame:
    x = df.dropna(subset=["receipt", "proxy"]).copy()
    full = _confusion_counts(x)
    full_recall = _safe_div(full["TP"], full["TP"] + full["FN"])
    full_precision = _safe_div(full["TP"], full["TP"] + full["FP"])
    rows = []
    for dimension in ["issuer", "year"]:
        if dimension not in x.columns or x[dimension].nunique(dropna=True) < 2:
            continue
        for value in x[dimension].dropna().unique():
            sub = x[x[dimension] != value]
            c = _confusion_counts(sub)
            rows.append({
                "leave_out_dimension": dimension,
                "left_out": str(value),
                "N": c["N"],
                "precision": _safe_div(c["TP"], c["TP"] + c["FP"]),
                "recall": _safe_div(c["TP"], c["TP"] + c["FN"]),
                "precision_change_from_full": _safe_div(c["TP"], c["TP"] + c["FP"]) - full_precision,
                "recall_change_from_full": _safe_div(c["TP"], c["TP"] + c["FN"]) - full_recall,
            })
    return pd.DataFrame(rows)


def architecture_stratification(df: pd.DataFrame) -> pd.DataFrame:
    x = df.loc[df["receipt"].eq(1)].copy()
    rows = []
    strata = {
        "batch": x["batch"].astype("string"),
        "multi_product": x["multi_product"].astype("string"),
        "correction": x["correction"].astype("string"),
        "batch_size_bin": pd.cut(x["batch_size"], bins=[0, 1, 2, 5, 10, np.inf], labels=["1", "2", "3-5", "6-10", "11+"]),
    }
    if x["severity"].notna().sum() >= 30:
        try:
            strata["severity_quintile"] = pd.qcut(x["severity"], 5, duplicates="drop")
        except ValueError:
            pass
    for name, series in strata.items():
        tmp = x.assign(_stratum=series.astype("string"))
        for value, g in tmp.groupby("_stratum", dropna=False):
            n = len(g)
            tp = int(g["proxy"].sum())
            lo, hi = wilson_interval(tp, n)
            rows.append({
                "dimension": name,
                "stratum": str(value),
                "receipt_positive": n,
                "proxy_captured": tp,
                "sensitivity": tp / n if n else np.nan,
                "wilson_lo": lo,
                "wilson_hi": hi,
            })
    return pd.DataFrame(rows)


def bias_decomposition(df: pd.DataFrame) -> pd.DataFrame:
    x = df.dropna(subset=["receipt", "proxy"]).copy()
    rows = []
    for dimension in [None, "issuer", "year", "batch", "correction", "multi_product"]:
        groups = [("ALL", x)] if dimension is None else list(x.groupby(dimension, dropna=False))
        for value, g in groups:
            c = _confusion_counts(g)
            n = c["N"]
            if n == 0:
                continue
            receipt_rate = (c["TP"] + c["FN"]) / n
            fpr_component = c["FP"] / n
            fn_component = -c["FN"] / n
            observed_bias = (c["TP"] + c["FP"] - c["TP"] - c["FN"]) / n
            rows.append({
                "dimension": dimension or "overall",
                "group": str(value),
                "N": n,
                "receipt_rate": receipt_rate,
                "false_positive_contribution": fpr_component,
                "false_negative_contribution": fn_component,
                "sum_components": fpr_component + fn_component,
                "observed_proxy_minus_receipt": observed_bias,
                "identity_error": observed_bias - (fpr_component + fn_component),
            })
    return pd.DataFrame(rows)


def build_scorecard(
    confusion: dict[str, float],
    issuer_summary: dict[str, float],
    mechanism_summary: dict[str, float],
    fe_summary: dict[str, float],
    regression_summary: dict[str, float],
    calibration_summary: dict[str, float],
    robustness: pd.DataFrame,
    second_context_present: bool = False,
) -> tuple[pd.DataFrame, str]:
    relative_bias = abs(confusion.get("relative_prevalence_bias", np.nan))
    dispersion_or_rank_material = (
        issuer_summary.get("spearman_rho", 1.0) < 0.80
        or issuer_summary.get("quartile_reclassification_rate", 0.0) >= 0.25
        or regression_summary.get("max_absolute_relative_coefficient_bias", 0.0) >= 0.25
        or bool(regression_summary.get("any_sign_change", False))
    )
    mechanism_strength = max(
        mechanism_summary.get("architecture_logloss_improvement_vs_time", 0.0),
        mechanism_summary.get("architecture_increment_beyond_issuer", 0.0),
        fe_summary.get("issuer_fe_sd_attenuation_architecture", 0.0),
    )
    calibration_gain = calibration_summary.get("mae_improvement", np.nan)
    robust = True
    if not robustness.empty:
        robust = (
            robustness["recall_change_from_full"].abs().max() <= 0.10
            and robustness["precision_change_from_full"].abs().max() <= 0.05
        )
    gates = [
        ("G1_material_prevalence_bias", bool(np.isfinite(relative_bias) and relative_bias >= 0.25), relative_bias, ">=0.25 absolute relative bias"),
        ("G2_material_economic_conclusion_distortion", bool(dispersion_or_rank_material), float(dispersion_or_rank_material), "sign change, coefficient bias >=25%, rank rho<0.8, or quartile reclass>=25%"),
        ("G3_document_architecture_mechanism", bool(np.isfinite(mechanism_strength) and mechanism_strength >= 0.10), mechanism_strength, ">=10% predictive/logloss improvement or issuer-FE attenuation"),
        ("G4_out_of_sample_calibration", bool(np.isfinite(calibration_gain) and calibration_gain >= 0.30), calibration_gain, ">=30% weighted MAE improvement"),
        ("G5_leave_one_out_robustness", bool(robust), float(robust), "recall shift<=10pp and precision shift<=5pp"),
        ("G6_independent_second_context", bool(second_context_present), float(second_context_present), "independent open-data disclosure context"),
    ]
    scorecard = pd.DataFrame([
        {"gate": name, "pass": passed, "value": value, "criterion": criterion}
        for name, passed, value, criterion in gates
    ])
    first_five = all(passed for _, passed, _, _ in gates[:5])
    if first_five and second_context_present:
        verdict = "GO_TOPJOURNAL_CANDIDATE_MEASUREMENT_ERROR"
    elif first_five:
        verdict = "GO_STRONG_MEASUREMENT_MECHANISM_PAPER_NEEDS_EXTERNAL_REPLICATION"
    elif gates[0][1]:
        verdict = "GO_OPEN_DATA_MEASUREMENT_ERROR_PAPER"
    else:
        verdict = "STOP_NOT_MATERIALLY_IMPORTANT_WITH_CURRENT_DATA"
    return scorecard, verdict

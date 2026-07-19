"""
Clustering module — market archetype segmentation.

Uses overall therapy pillar scores [demand, monetization, access, growth]
as the feature space.  Finds optimal k via elbow + silhouette, then labels
each district with its archetype cluster and builds cluster profiles.

Supports k-means (default) or GMM (toggle in config['clustering']['method']).
"""

from __future__ import annotations
import logging

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

log = logging.getLogger(__name__)

PILLAR_COLS = ["demand", "monetization", "access", "growth"]

ARCHETYPE_NAMES = {
    0: "Emerging Opportunity",
    1: "High Access, Low Monetisation",
    2: "Premium Urban",
    3: "Chronic-Driven Growth",
    4: "Underserved Potential",
    5: "Balanced Mid-Tier",
    6: "Acute-Demand Hub",
    7: "Infrastructure-Deficit",
}


def _feature_matrix(scores: pd.DataFrame, therapy: str = "overall") -> tuple[pd.DataFrame, np.ndarray]:
    feature_cols = [f"{therapy}_pillar_{p}" for p in PILLAR_COLS]
    available = [c for c in feature_cols if c in scores.columns]
    X_df = scores[available].dropna()
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_df)
    return X_df, X_scaled


def _elbow_silhouette(X: np.ndarray, k_range: range, method: str, random_state: int) -> int:
    """Select optimal k using silhouette score."""
    best_k, best_score = k_range.start, -1.0
    for k in k_range:
        if k >= len(X):
            break
        if method == "gmm":
            model = GaussianMixture(n_components=k, random_state=random_state)
            labels = model.fit_predict(X)
        else:
            model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
            labels = model.fit_predict(X)
        if len(set(labels)) > 1:
            sil = silhouette_score(X, labels)
            if sil > best_score:
                best_score, best_k = sil, k
    log.info("  Optimal k=%d (silhouette=%.3f)", best_k, best_score)
    return best_k


def run_clustering(
    scores: pd.DataFrame,
    config: dict | None = None,
    therapy: str = "overall",
) -> dict:
    """
    Cluster districts by pillar profile.

    Returns
    -------
    {
      'labels':   pd.Series  (canonical_district_id → cluster_int),
      'profiles': pd.DataFrame  (cluster_int → {mean_demand, ...}),
      'k':        int,
    }
    """
    cfg = config or {}
    clust_cfg = cfg.get("clustering", {})
    method       = clust_cfg.get("method", "kmeans")
    k_range_cfg  = clust_cfg.get("k_range", [3, 8])
    random_state = clust_cfg.get("random_state", 42)

    k_range = range(k_range_cfg[0], k_range_cfg[1] + 1)

    X_df, X_scaled = _feature_matrix(scores, therapy)
    if len(X_df) < k_range.start:
        log.warning("Too few districts for clustering; skipping")
        return {"labels": pd.Series(dtype=int), "profiles": pd.DataFrame(), "k": 0}

    optimal_k = _elbow_silhouette(X_scaled, k_range, method, random_state)

    if method == "gmm":
        model = GaussianMixture(n_components=optimal_k, random_state=random_state)
    else:
        model = KMeans(n_clusters=optimal_k, random_state=random_state, n_init=10)

    labels_arr = model.fit_predict(X_scaled)
    labels = pd.Series(labels_arr, index=X_df.index, name="cluster")

    # Build cluster profiles (unscaled pillar means)
    labeled_df = X_df.join(labels)
    pillar_col_names = [f"{therapy}_pillar_{p}" for p in PILLAR_COLS if f"{therapy}_pillar_{p}" in X_df.columns]
    profiles = labeled_df.groupby("cluster")[pillar_col_names].mean().round(1)
    profiles.columns = [c.replace(f"{therapy}_pillar_", "") for c in profiles.columns]
    profiles["archetype"] = [ARCHETYPE_NAMES.get(i, f"Cluster {i}") for i in profiles.index]
    profiles["n_districts"] = labeled_df.groupby("cluster").size()

    log.info("Clustering: k=%d  method=%s  districts=%d", optimal_k, method, len(labels))
    return {"labels": labels, "profiles": profiles, "k": optimal_k}

"""
Forecasting module — projects indicator values to the target year.

Primary method: per-indicator CAGR extrapolation from a multi-year panel.
  value_T = value_last * (1 + CAGR) ^ (T - last_year)
  CAGR    = (value_last / value_first) ^ (1 / n_years) - 1

Clamps projected values to [0, 100] (same scale as normalised inputs).
Neutral fallback: if CAGR cannot be computed (only one period, zero start value),
uses the last observed value unchanged (zero growth assumption).

GBM upgrade slot: replace _cagr_forecast() with a gradient-boosted model when
enough panel years are available (≥ 5 time points recommended).

Usage:
    imputed_panel = {2011: df_2011, 2016: df_2016, 2021: df_2021}
    future_scores = compute_future_scores(config, imputed_panel, xwalk)
"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from engine.normalizer import normalize
from engine.aggregator import aggregate

log = logging.getLogger(__name__)

_META = {"canonical_name", "state"}


# ── Abstract forecast strategy (slot for GBM upgrade) ────────────────────────

class ForecastStrategy(ABC):
    @abstractmethod
    def fit(self, panel: dict[int, pd.DataFrame], indicator_cols: list[str]) -> "ForecastStrategy":
        ...

    @abstractmethod
    def predict(self, target_year: int) -> pd.DataFrame:
        ...


class CAGRForecast(ForecastStrategy):
    """Per-district, per-indicator CAGR extrapolation."""

    def __init__(self) -> None:
        self._panel: dict[int, pd.DataFrame] = {}
        self._indicator_cols: list[str] = []

    def fit(self, panel: dict[int, pd.DataFrame], indicator_cols: list[str]) -> "CAGRForecast":
        self._panel = panel
        self._indicator_cols = indicator_cols
        return self

    def predict(self, target_year: int) -> pd.DataFrame:
        years = sorted(self._panel)
        first_year, last_year = years[0], years[-1]

        df_first = self._panel[first_year][self._indicator_cols]
        df_last  = self._panel[last_year][self._indicator_cols]

        n_years = last_year - first_year
        if n_years <= 0:
            log.warning("Cannot compute CAGR with single period — using flat forecast")
            proj = df_last.copy()
            return proj

        # CAGR per district per indicator
        # Clip to small positive to avoid log(0); set CAGR=0 for zero-start districts
        safe_first = df_first.clip(lower=0.01)
        safe_last  = df_last.clip(lower=0.01)
        cagr = (safe_last / safe_first) ** (1 / n_years) - 1

        # Annualised projection from last year to target year
        horizon = target_year - last_year
        proj = df_last * ((1 + cagr) ** horizon)
        proj = proj.clip(0, 100)
        return proj


from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.multioutput import MultiOutputRegressor

# ── GBM slot (activate when ≥5 panel years available) ────────────────────────

class GBMForecast(ForecastStrategy):
    """
    Linear RidgeCV multi-output forecast per indicator (replaces Random Forest for forward extrapolation).
    """
    def __init__(self):
        self.model = None
        self.indicator_cols = []
        self.df_last = None

    def fit(self, panel: dict[int, pd.DataFrame], indicator_cols: list[str]) -> "ForecastStrategy":
        self.indicator_cols = indicator_cols
        years = sorted(panel.keys())
        first_year, last_year = years[0], years[-1]
        
        self.df_last = panel[last_year][indicator_cols].copy()
        
        if len(years) < 2:
            log.warning("Not enough years for ML forecast. Fitting dummy fallback.")
            return self

        # Train to predict last_year from first_year
        X_train = panel[first_year][indicator_cols].fillna(0)
        y_train = panel[last_year][indicator_cols].fillna(0)

        # Multi-output regression with Standardization and LinearRegression
        base_estimator = make_pipeline(StandardScaler(), LinearRegression())
        self.model = MultiOutputRegressor(base_estimator)
        self.model.fit(X_train, y_train)

        return self

    def predict(self, target_year: int) -> pd.DataFrame:
        if self.model is None:
            # Fallback if fit failed due to single year
            return self.df_last.copy()

        # Predict future from last_year
        X_test = self.df_last.fillna(0)
        y_pred = self.model.predict(X_test)
        
        proj = pd.DataFrame(y_pred, index=X_test.index, columns=self.indicator_cols)
        
        # Inject Macro Momentum (10-year projection)
        pos_cols = [
            "urban_pop_pct", "literacy_rate", "hosp_bed_density", "health_insurance_cov", 
            "per_capita_nsdp", "pharmacy_density", "road_connectivity", "health_infra_growth"
        ]
        inv_cols = [
            "oope_pct_hhexp", "chronic_disease_prev", "pop_elderly_pct"
        ]
        
        for col in pos_cols:
            if col in proj.columns:
                proj[col] = proj[col] * (1.02 ** 10)
                
        for col in inv_cols:
            if col in proj.columns:
                proj[col] = proj[col] * (0.99 ** 10)
        
        # Enforce Logical Boundaries
        # 1. No variables drop below 0
        proj = proj.clip(lower=0)
        
        # 2. Percentage variables capped at 100.0
        pct_cols = [
            "urban_pop_pct", "literacy_rate", "pop_elderly_pct", 
            "health_insurance_cov", "oope_pct_hhexp", "chronic_disease_prev"
        ]
        for col in pct_cols:
            if col in proj.columns:
                proj[col] = proj[col].clip(upper=100.0)
        
        return proj


def _build_strategy(config: dict) -> ForecastStrategy:
    method = config.get("forecasting", {}).get("method", "cagr")
    if method == "cagr":
        return CAGRForecast()
    if method == "gradient_boost":
        return GBMForecast()
    raise ValueError(f"Unknown forecasting method: '{method}'")


def compute_future_scores(
    config: dict,
    imputed_panel: dict[int, pd.DataFrame],
    xwalk: pd.DataFrame,
) -> pd.DataFrame:
    """
    Project indicators to target year, re-normalise, re-aggregate → future scores.

    Returns DataFrame with same district index as imputed_panel,
    columns: {therapy}_future_score, {therapy}_future_pillar_{pillar}.
    """
    target_year = config.get("forecasting", {}).get("target_year", 2030)
    base_year   = config.get("forecasting", {}).get("base_year",   2011)

    # Identify indicator columns
    meta_cols = [c for c in list(imputed_panel.values())[0].columns if c in _META]
    indicator_cols = [
        ind["id"]
        for ind in config["indicators"]
        if ind["id"] in list(imputed_panel.values())[0].columns
    ]

    strategy = _build_strategy(config).fit(imputed_panel, indicator_cols)

    log.info("Forecasting to %d using '%s'...", target_year, config.get("forecasting", {}).get("method", "cagr"))
    proj_values = strategy.predict(target_year)

    # Re-attach metadata from base year
    base_meta = imputed_panel[base_year][meta_cols] if meta_cols else pd.DataFrame(index=proj_values.index)
    proj_master = base_meta.join(proj_values)

    # Normalise projected values (same pipeline as current)
    base_master = imputed_panel[base_year]
    proj_normed = normalize(proj_master, config, reference_df=base_master)

    # Aggregate → future scores
    proj_agg = aggregate(proj_normed, config)

    frames: list[pd.Series] = []
    for therapy in config["therapies"]:
        res = proj_agg[therapy]
        for pillar in config["pillars"]:
            frames.append(res["pillar_scores"][pillar].rename(f"{therapy}_future_pillar_{pillar}"))
        frames.append(res["headline"].rename(f"{therapy}_future_score"))

    return pd.concat(frames, axis=1)

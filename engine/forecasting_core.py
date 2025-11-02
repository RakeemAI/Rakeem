# engine/forecasting_core.py
from __future__ import annotations

import pandas as pd
from typing import Iterable, Optional, List
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from engine.config import DEFAULT_ENGINE_CONFIG as CFG


# ----------------------------- Utilities ---------------------------------

def _pick_col(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    lower_map = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = str(cand).strip().lower()
        if key in lower_map:
            return lower_map[key]
    return None


def _entity_candidates() -> List[str]:
    return [
        "entity_name", "company", "company_name", "entity",
        "اسم_الشركة", "المنشأة", "المنشاة", "الكيان"
    ]


def _to_month_end_index(dt_like: pd.Series) -> pd.DatetimeIndex:
    dt = pd.to_datetime(dt_like, errors="coerce")
    
    dt = pd.DatetimeIndex(dt).to_period("M").to_timestamp("M")  
    idx = pd.DatetimeIndex(dt, name="date")
    
    idx.freq = "ME"
    return idx


def _prep_monthly_series(df: pd.DataFrame, date_col: str, value_col: str) -> pd.Series:
    d = df[[date_col, value_col]].copy()

    d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
    d[value_col] = pd.to_numeric(d[value_col], errors="coerce")

    d = d.dropna(subset=[date_col]).sort_values(date_col)

    d[date_col] = _to_month_end_index(d[date_col])

    d = d.drop_duplicates(subset=[date_col], keep="last").set_index(date_col)

    
    d = d.asfreq("ME")

    d[value_col] = d[value_col].ffill().fillna(0.0)

    y = d[value_col].astype(float)
    
    y.index = pd.DatetimeIndex(y.index, freq="ME")
    return y


def _forecast_series(y: pd.Series, periods: int = 3) -> pd.Series:
    y = y.dropna()
    if y.size == 0:
        start = pd.Timestamp.today().to_period("M").to_timestamp("M") + pd.offsets.MonthEnd(1)
        
        idx = pd.date_range(start, periods=periods, freq="ME")
        return pd.Series([0.0] * periods, index=idx)

    if y.nunique() <= 1 or y.size < 4:
        last = float(y.iloc[-1])
        
        idx = pd.date_range(y.index.max() + pd.offsets.MonthEnd(1), periods=periods, freq="ME")
        return pd.Series([last] * periods, index=idx)

    try:
        model = ExponentialSmoothing(y, trend="add", damped_trend=True, seasonal=None)
        fit = model.fit(optimized=True, use_brute=True)
        fc = fit.forecast(periods)
        
        fc.index = pd.DatetimeIndex(fc.index, freq="ME")
        return fc
    except Exception:
        last = float(y.iloc[-1])
        
        idx = pd.date_range(y.index.max() + pd.offsets.MonthEnd(1), periods=periods, freq="ME")
        return pd.Series([last] * periods, index=idx)




def build_revenue_forecast(
    df: pd.DataFrame,
    periods: int = 3,
    entity_col: Optional[str] = None,
) -> pd.DataFrame:

    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "entity_name", "forecast", "lower", "upper"])

    date_col = _pick_col(df, ("date", "month", "period", *CFG.colmap.date)) or "date"
    rev_col  = _pick_col(df, ("revenue", "sales", "turnover", *CFG.colmap.revenue)) or "revenue"

    if date_col not in df.columns or rev_col not in df.columns:
        return pd.DataFrame(columns=["date", "entity_name", "forecast", "lower", "upper"])

    ent_col = entity_col or _pick_col(df, _entity_candidates())

    if ent_col and ent_col in df.columns:
        entities = (
            df[ent_col].dropna().astype(str).str.strip()
            .replace({"": None}).dropna().unique().tolist()
        )
    else:
        entities = ["All"]

    out_frames: List[pd.DataFrame] = []

    for ent in entities:
        sub = df[df[ent_col] == ent] if (ent_col and ent_col in df.columns) else df

        y = _prep_monthly_series(sub, date_col, rev_col)
        fc = _forecast_series(y, periods=periods)

        res = pd.DataFrame({
            "date": fc.index,
            "forecast": fc.values,
        })
        res["lower"] = res["forecast"] * 0.90
        res["upper"] = res["forecast"] * 1.10
        res["entity_name"] = ent

        res = res[["date", "entity_name", "forecast", "lower", "upper"]]
        out_frames.append(res)

    return pd.concat(out_frames, ignore_index=True)


def save_forecast_csv(df: pd.DataFrame, path: str, periods: int = 3, entity_col: Optional[str] = None) -> None:
    res = build_revenue_forecast(df, periods=periods, entity_col=entity_col)
    res.to_csv(path, index=False, encoding="utf-8")

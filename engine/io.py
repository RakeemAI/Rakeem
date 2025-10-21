from __future__ import annotations
from typing import Union
import pandas as pd
from engine.config import DEFAULT_ENGINE_CONFIG

def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    if not hasattr(df, "columns"):
        raise TypeError("Expected DataFrame")
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    return out

def load_excel(path: str, sheet: Union[int, str, None] = 0) -> pd.DataFrame:
    obj = pd.read_excel(path, sheet_name=sheet)
    if isinstance(obj, dict):
        obj = next(iter(obj.values()))
    df = _normalize_cols(obj)
    # unify date column if alias exists
    for alias in DEFAULT_ENGINE_CONFIG.colmap.date:
        if alias in df.columns and alias != "date":
            df.rename(columns={alias: "date"}, inplace=True)
            break
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    return _normalize_cols(df)

import pandas as pd
from engine.config import DEFAULT_ENGINE_CONFIG

CFG = DEFAULT_ENGINE_CONFIG

def compute_vat(df: pd.DataFrame) -> float:
    if "vat_collected" in df.columns and "vat_paid" in df.columns:
        net = float(df["vat_collected"].fillna(0).sum() - df["vat_paid"].fillna(0).sum())
        return net
    rev = df["revenue"].fillna(0).sum() if "revenue" in df.columns else 0.0
    exp = df["expenses"].fillna(0).sum() if "expenses" in df.columns else 0.0
    return float(rev * CFG.taxes.vat_rate - exp * CFG.taxes.vat_rate)

def compute_zakat(df: pd.DataFrame) -> float:
    mode = CFG.taxes.zakat_mode
    if mode == "base_if_available_else_zero" and "zakat_base" in df.columns:
        base = float(df["zakat_base"].fillna(0).sum())
        return base * CFG.taxes.zakat_rate
    return 0.0

import pandas as pd
from engine.schema import KPISummary, EngineOutput
from engine.taxes import compute_vat, compute_zakat

def build_summary(df: pd.DataFrame) -> KPISummary:
    kpis = KPISummary(
        total_revenue=float(df.get("revenue", 0).fillna(0).sum()),
        total_expenses=float(df.get("expenses", 0).fillna(0).sum()),
        total_profit=float(df.get("profit", 0).fillna(0).sum()),
        avg_profit_margin=float(df.get("profit_margin", 0).replace([float("inf"), -float("inf")], 0).fillna(0).mean()),
        total_cash_flow=float(df.get("cash_flow", 0).fillna(0).sum()),
        net_vat=float(compute_vat(df)),
        zakat_due=float(compute_zakat(df)),
    )
    return kpis

def to_json(df: pd.DataFrame, include_rows: bool = False) -> str:
    out = EngineOutput(
        kpis=build_summary(df),
        rows=df.to_dict(orient="records") if include_rows else None,
    )
    return out.model_dump_json(indent=2)

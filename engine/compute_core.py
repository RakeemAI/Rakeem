# engine/compute_core.py
from engine.config import DEFAULT_ENGINE_CONFIG as CFG
import pandas as pd
import numpy as np

def _pick_series(df: pd.DataFrame, name: str, aliases) -> pd.Series:
    """
    Return the first matching column among [name] + aliases; otherwise a NaN series.
    """
    for c in (name, *aliases):
        if c in df.columns:
            return df[c]
    # no match -> NaN series (will be handled downstream)
    return pd.Series(np.nan, index=df.index)

def compute_core(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    colmap = CFG.colmap

    # read with aliases (supports: revenue/sales/turnover ... etc)
    rev = _pick_series(out, "revenue", colmap.revenue)
    exp = _pick_series(out, "expenses", colmap.expenses)

    # coerce to numeric safely (strings -> numbers; invalid -> NaN)
    rev = pd.to_numeric(rev, errors="coerce")
    exp = pd.to_numeric(exp, errors="coerce")

    # keep canonical columns present for downstream use
    out["revenue"]  = rev
    out["expenses"] = exp

    # profit
    out["profit"] = rev.fillna(0) - exp.fillna(0)

    # profit margin %  (avoid NA/inf -> set to 0)
    denom = rev.replace(0, np.nan)  # avoid divide-by-zero
    out["profit_margin"] = (out["profit"] / denom) * 100
    out["profit_margin"] = (
        out["profit_margin"]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .astype(float)
    )

    # cash flow (if opening/closing provided) else fallback to profit
    if "opening_cash" in out.columns and "closing_cash" in out.columns:
        oc = pd.to_numeric(out["opening_cash"], errors="coerce").fillna(0)
        cc = pd.to_numeric(out["closing_cash"], errors="coerce").fillna(0)
        out["cash_flow"] = cc - oc
    else:
        out["cash_flow"] = out["profit"].fillna(0)

    return out
def get_answer(question: str):
    """
    مؤقتًا: ترد على الأسئلة المالية البسيطة مثل حساب الربح.
    """
    import re
    try:
        nums = [int(n) for n in re.findall(r'\d+', question)]
        if len(nums) >= 2:
            revenue, expenses = nums[0], nums[1]
            profit = revenue - expenses
            return f"صافي الربح هو {profit} ريال 💰"
        elif "زكاة" in question:
            return "نسبة الزكاة عادة 2.5% من رأس المال الخاضع للزكاة."
        elif "ضريبة" in question:
            return "الضريبة المضافة في السعودية هي 15%."
        else:
            return "يرجى إدخال أرقام أو سؤال مالي محدد مثل: الإيرادات 5000 والمصروفات 3000."
    except Exception as e:
        return f"حدث خطأ أثناء المعالجة: {e}"

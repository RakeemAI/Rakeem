import pandas as pd

def _get(df: pd.DataFrame, name: str, *aliases, default=0.0) -> pd.Series:
    for c in (name, *aliases):
        if c in df.columns:
            return df[c]
    return pd.Series([default] * len(df), index=df.index, dtype="float64")

def compute_core(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rev = _get(out, "revenue")
    exp = _get(out, "expenses")

    out["profit"] = (rev.fillna(0) - exp.fillna(0)).astype(float)

    with pd.option_context("mode.use_inf_as_na", True):
        out["profit_margin"] = (out["profit"] / rev.replace(0, pd.NA)).astype(float) * 100

    if "opening_cash" in out.columns and "closing_cash" in out.columns:
        out["cash_flow"] = (out["closing_cash"].fillna(0) - out["opening_cash"].fillna(0)).astype(float)
    else:
        out["cash_flow"] = out["profit"].astype(float)

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

# engine/taxes.py
from __future__ import annotations
import pandas as pd
from typing import Iterable, Optional, Dict
from engine.config import DEFAULT_ENGINE_CONFIG

CFG = DEFAULT_ENGINE_CONFIG

def _first_existing(df: pd.DataFrame, names: Iterable[str]) -> Optional[str]:
    """يرجع أول عمود مطابق (case-insensitive) من قائمة أسماء محتملة."""
    lower_map = {c.lower(): c for c in df.columns}
    for n in names:
        if n.lower() in lower_map:
            return lower_map[n.lower()]
    return None

def _sum_cols(df: pd.DataFrame, groups: Dict[str, Iterable[str]]) -> float:

    total = 0.0
    for _, candidates in groups.items():
        col = _first_existing(df, candidates)
        if col is not None:
            total += pd.to_numeric(df[col], errors="coerce").fillna(0.0).sum()
    return float(total)


# VAT
def compute_vat(df: pd.DataFrame) -> float:
 
    
    out_col = _first_existing(df, ["vat_collected","vat_output","vat_out","ضريبة المخرجات"])
    in_col  = _first_existing(df, ["vat_paid","vat_input","vat_in","ضريبة المدخلات"])
    if out_col and in_col:
        out_sum = pd.to_numeric(df[out_col], errors="coerce").fillna(0.0).sum()
        in_sum  = pd.to_numeric(df[in_col],  errors="coerce").fillna(0.0).sum()
        return float(out_sum - in_sum)

    # fallback
    rev_col = _first_existing(df, ["revenue","sales","الإيرادات","المبيعات"])
    exp_col = _first_existing(df, ["expenses","expense","المصروفات","تكاليف"])
    vat_rate = getattr(getattr(CFG, "taxes", object()), "vat_rate", 0.15) or 0.15
    vat_out = (pd.to_numeric(df[rev_col], errors="coerce").fillna(0.0).sum() * vat_rate) if rev_col else 0.0
    vat_in  = (pd.to_numeric(df[exp_col], errors="coerce").fillna(0.0).sum() * vat_rate) if exp_col else 0.0
    return float(vat_out - vat_in)

# Zakat
def compute_zakat(df: pd.DataFrame, rate: Optional[float] = None) -> float:
 
    # نسبة الزكاة
    zakat_rate = float(rate if rate is not None else getattr(getattr(CFG, "taxes", object()), "zakat_rate", 0.025) or 0.025)

    # 1) استخدام وعاء جاهز إذا موجود وله قيمة
    base_col = _first_existing(df, ["zakat_base", "وعاء الزكاة"])
    if base_col:
        base_val = pd.to_numeric(df[base_col], errors="coerce").fillna(0.0).sum()
        if base_val > 0:
            return float(base_val * zakat_rate)

    # 2) احتساب وعاء تقديري تلقائي
    zakatable_assets_map = {
        "cash": [
            "cash","bank","cash_and_equivalents","cash_equivalents",
            "النقد","النقدية","نقد","سيولة","البنوك","حسابات بنكية"
        ],
        "ar": [
            "accounts_receivable","trade_receivables","receivables",
            "العملاء","الذمم المدينة","مدينون"
        ],
        "inventory": [
            "inventory","stock","المخزون"
        ],
        "prepaid_oca": [
            "prepaid_expenses","other_current_assets",
            "مصروفات مدفوعة مقدماً","أصول متداولة أخرى","اصول متداولة اخرى"
        ],
    }
    current_liab_map = {
        "ap": [
            "accounts_payable","trade_payables","payables",
            "الدائنون","الذمم الدائنة","موردون"
        ],
        "st_loans": [
            "short_term_loans","short_term_borrowings",
            "قروض قصيرة الأجل","تسهيلات قصيرة الأجل"
        ],
        "accruals": [
            "accrued_expenses","accruals","مصروفات مستحقة"
        ],
        "other_cl": [
            "other_current_liabilities","خصوم متداولة أخرى","التزامات متداولة اخرى"
        ],
    }

    zakatable_assets = _sum_cols(df, zakatable_assets_map)
    current_liabilities = _sum_cols(df, current_liab_map)

    zakat_base = max(zakatable_assets - current_liabilities, 0.0)
    return float(zakat_base * zakat_rate)

# engine/rules_engine.py
from future import annotations
import pandas as pd
from typing import List, Tuple

def _pct_change(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    try:
        return (a - b) / abs(b) * 100.0
    except Exception:
        return 0.0

def generate_recommendations(
    history_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    metric: str = "revenue",
    entity_name: str | None = None,
) -> List[str]:

    tips: List[str] = []
    hist = history_df.copy()

    if entity_name and "entity_name" in hist.columns:
        hist = hist[hist["entity_name"] == entity_name]

    # تجهيز تواريخ/أعمدة
    if "date" in hist.columns:
        hist = hist.sort_values("date")

    # أرقام أساسية
    rev = hist.get("revenue")
    exp = hist.get("expenses")
    prof = hist.get("profit")

    # 1) الإيرادات – ميل آخر 3 أشهر + أول نقطة تنبؤ
    try:
        if rev is not None and len(rev.dropna()) >= 3:
            last3 = rev.dropna().tail(3).tolist()
            change3 = _pct_change(last3[-1], last3[0])
            if change3 <= -10:
                tips.append(f"لوحظ تراجع في الإيرادات بنحو {abs(change3):.1f}% خلال آخر ثلاثة أشهر — راجع حملات التسويق والتسعير.")

        # مقارنة أول شهر متنبأ به بآخر شهر حالي
        if rev is not None and "forecast" in forecast_df.columns and len(forecast_df) > 0:
            f0 = float(forecast_df.iloc[0]["forecast"])
            r_last = float(rev.dropna().iloc[-1]) if len(rev.dropna()) else None
            if r_last is not None:
                fchg = _pct_change(f0, r_last)
                if fchg <= -10:
                    tips.append(f"التنبؤ يشير لانخفاض إيرادات قادم بنحو {abs(fchg):.1f}% — جهز خطة بديلة للسيولة.")
    except Exception:
        pass

    # 2) المصروفات – ارتفاع ≥15%
    try:
        if exp is not None and len(exp.dropna()) >= 3:
            last3e = exp.dropna().tail(3).tolist()
            e_chg = _pct_change(last3e[-1], last3e[0])
            if e_chg >= 15:
                tips.append(f"المصروفات ارتفعت بنحو {e_chg:.1f}% — ادرس عقود الموردين وخفض البنود غير الحرجة.")
    except Exception:
        pass

    # 3) الربح بالسالب
    try:
        if prof is not None and len(prof.dropna()) >= 1:
            if float(prof.dropna().iloc[-1]) < 0:
                tips.append("الربح الصافي سالب مؤخرًا — يُفضّل مراجعة التسعير أو تخفيض تكاليف التشغيل.")
    except Exception:
        pass

    # 4) هامش الربح التقريبي
    try:
        if rev is not None and exp is not None and len(rev.dropna()) and len(exp.dropna()):
            last_rev = float(rev.dropna().iloc[-1])
            last_exp = float(exp.dropna().iloc[-1])
            if last_rev > 0:
                margin = (last_rev - last_exp) / last_rev * 100.0
                if margin < 10:
                    tips.append(f"هامش الربح الحالي منخفض ({margin:.1f}%) — ادرس مزيج المنتجات ورسوم الخدمة.")
    except Exception:
        pass

    if not tips:
        tips.append("لا توجد إشارات خطرة حالياً — استمر على نفس النهج مع متابعة شهرية للمؤشرات.")
    return tips[:5]  # نعرض حتى 5 توصيات كحد أقصى

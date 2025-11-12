# engine/reminder_core.py
from __future__ import annotations
import json
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional


# =========================
# إعدادات الشركة (قابلة للتخصيص من الواجهة)
# =========================
@dataclass
class CompanyProfile:
    # نهاية السنة المالية (افتراضي: 31 ديسمبر)
    fiscal_year_end_month: int = 12
    fiscal_year_end_day: int = 31

    # تكرار الضريبة المضافة: "monthly" أو "quarterly"
    vat_frequency: str = "quarterly"

    # تاريخ إصدار السجل التجاري (للذكاة السنوية على CR renewal)
    cr_issue_date: Optional[dt.date] = None


# =========================
# تحميل قاعدة المواعيد
# =========================
def load_deadlines(path: str = "data/saudi_deadlines_ar.json") -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"لم يتم العثور على ملف المواعيد: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


# =========================
# أدوات مساعدة للتواريخ
# =========================
def _end_of_month(year: int, month: int) -> dt.date:
    if month == 12:
        return dt.date(year, 12, 31)
    first_next = dt.date(year, month + 1, 1)
    return first_next - dt.timedelta(days=1)

def _safe_date(year: int, month: int, day: int) -> dt.date:
    # يضبط اليوم لو كان أكبر من آخر يوم في الشهر
    eom = _end_of_month(year, month)
    d = min(day, eom.day)
    return dt.date(year, month, d)

def _next_anniversary(base: dt.date, today: dt.date) -> dt.date:
    # أقرب ذكرى سنوية بعد أو في هذا اليوم
    year = today.year
    candidate = _safe_date(year, base.month, base.day)
    if candidate < today:
        candidate = _safe_date(year + 1, base.month, base.day)
    return candidate

def _fye_date(profile: CompanyProfile, year: int) -> dt.date:
    return _safe_date(year, profile.fiscal_year_end_month, profile.fiscal_year_end_day)

def _next_fye_after(today: dt.date, profile: CompanyProfile) -> dt.date:
    fye_this_year = _fye_date(profile, today.year)
    return fye_this_year if fye_this_year >= today else _fye_date(profile, today.year + 1)

def _next_quarter_end(today: dt.date) -> dt.date:
    # ينهي على (مارس/يونيو/سبتمبر/ديسمبر)
    q_months = [3, 6, 9, 12]
    for m in q_months:
        eom = _end_of_month(today.year, m)
        if eom >= today:
            return eom
    return _end_of_month(today.year + 1, 3)

def _month_end_following(date_: dt.date) -> dt.date:
    # نهاية الشهر التالي لتاريخ معين
    y, m = (date_.year, date_.month)
    if m == 12:
        return _end_of_month(y + 1, 1)
    return _end_of_month(y, m + 1)


# =========================
# حساب موعد الاستحقاق التالي لكل مهمة
# =========================
def next_due_date(item: Dict[str, Any], today: Optional[dt.date], profile: CompanyProfile) -> Optional[dt.date]:
    today = today or dt.date.today()
    _id = item.get("المعرّف")
    freq = (item.get("التكرار") or "").strip()

    # حالات خاصة حسب المعرف
    if _id == "zakat_annual" or _id == "income_tax_annual":
        # خلال 120 يوم بعد نهاية السنة المالية
        fye = _next_fye_after(today, profile)
        due = fye + dt.timedelta(days=120)
        return due

    if _id == "vat_monthly":
        # نهاية الشهر التالي للفترة: نفترض الفترة الحالية = شهر اليوم
        period_end = _end_of_month(today.year, today.month)
        return _month_end_following(period_end)

    if _id == "vat_quarterly":
        # نهاية الشهر التالي لنهاية الربع
        q_end = _next_quarter_end(today)
        return _month_end_following(q_end)

    if _id == "withholding_tax":
        # خلال 10 أيام من نهاية كل شهر
        period_end = _end_of_month(today.year, today.month)
        due = period_end + dt.timedelta(days=10)
        return due

    if _id == "excise_tax":
        # منتصف الشهر التالي (تقريبًا 15)
        next_month = today.month + 1
        next_year = today.year + (1 if next_month == 13 else 0)
        next_month = 1 if next_month == 13 else next_month
        return _safe_date(next_year, next_month, 15)

    if _id == "gosi_monthly":
        # قبل يوم 15 من كل شهر (نستخدم الشهر الحالي أو التالي إذا العدّى)
        due = _safe_date(today.year, today.month, 15)
        return due if due >= today else _safe_date(today.year + (1 if today.month == 12 else 0),
                                                  1 if today.month == 12 else today.month + 1, 15)

    if _id == "financial_statements":
        # خلال 3 أشهر من نهاية السنة المالية
        fye = _next_fye_after(today, profile)
        # إذا نحن قبل نهاية السنة الحالية، يبقى الاستحقاق بعد fye القادمة
        return fye + dt.timedelta(days=90)

    if _id == "cr_renewal":
        # حسب تاريخ إصدار السجل التجاري
        if not profile.cr_issue_date:
            return None
        return _next_anniversary(profile.cr_issue_date, today)

    # fallback عام حسب التكرار التقريبي
    if freq == "سنوي":
        approx_m = int(item.get("تقريب_الشهر") or 12)
        approx_d = int(item.get("تقريب_اليوم") or 31)
        candidate = _safe_date(today.year, approx_m, approx_d)
        return candidate if candidate >= today else _safe_date(today.year + 1, approx_m, approx_d)

    if freq == "شهري":
        d = int(item.get("تقريب_اليوم") or 30)
        candidate = _safe_date(today.year, today.month, d)
        if candidate >= today:
            return candidate
        # الشهر القادم
        nm = today.month + 1
        ny = today.year + (1 if nm == 13 else 0)
        nm = 1 if nm == 13 else nm
        return _safe_date(ny, nm, d)

    if freq == "ربع سنوي":
        # نهاية الشهر التالي لنهاية الربع (تقريب)
        q_end = _next_quarter_end(today)
        return _month_end_following(q_end)

    return None


# =========================
# توليد تنبيهات قادمة خلال مدة محددة
# =========================
def upcoming_deadlines(days_ahead: int = 14,
                       profile: Optional[CompanyProfile] = None,
                       today: Optional[dt.date] = None,
                       path: str = "data/saudi_deadlines_ar.json") -> List[Dict[str, Any]]:
    profile = profile or CompanyProfile()
    today = today or dt.date.today()
    items = load_deadlines(path)

    out: List[Dict[str, Any]] = []
    for it in items:
        due = next_due_date(it, today, profile)
        if not due:
            continue
        diff = (due - today).days
        if 0 <= diff <= days_ahead:
            out.append({
                "المعرّف": it.get("المعرّف"),
                "الاسم": it.get("الاسم"),
                "الجهة": it.get("الجهة"),
                "الفئة": it.get("الفئة"),
                "تاريخ_الاستحقاق": due.isoformat(),
                "الأيام_المتبقية": diff,
                "الوصف": it.get("الوصف"),
            })
    # ترتيب بالأقرب
    out.sort(key=lambda r: (r["الأيام_المتبقية"], r["الاسم"]))
    return out

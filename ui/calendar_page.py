# ui/calendar_page.py
# -*- coding: utf-8 -*-
"""
صفحة تقويم كاملة لعرض الالتزامات السعودية (VAT, زكاة, GOSI, إلخ) مع عرض شهري،
وعدّاد الأيام المتبقية، وتصفيه حسب الجهة والفئة، وتصدير iCal (.ics).

الدمج:
1) ضع هذا الملف في ui/calendar_page.py
2) عدّل app.py لإضافة زر/حالة تنتقل لهذه الصفحة (تعليمات أسفل الملف).
"""
from __future__ import annotations
import calendar
import datetime as dt
from dataclasses import asdict
from typing import Dict, Any, List, Optional

import pandas as pd
import streamlit as st

from engine.reminder_core import CompanyProfile, upcoming_deadlines, load_deadlines, next_due_date

# =========================
# Helpers
# =========================

def _sar_days(n: int) -> str:
    if n == 0:
        return "اليوم"
    if n == 1:
        return "غدًا"
    if n < 0:
        return f"منذ {abs(n)} يوم"
    return f"بعد {n} يوم"


def _to_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["الاسم", "الفئة", "الجهة", "تاريخ_الاستحقاق", "الأيام_المتبقية", "الوصف", "المعرّف"]) 
    df = pd.DataFrame(rows)
    # ضمان الترتيب
    if "الأيام_المتبقية" in df:
        df = df.sort_values(["الأيام_المتبقية", "الاسم"]).reset_index(drop=True)
    return df


def _ics_export(rows: List[Dict[str, Any]], filename: str = "rakeem_deadlines.ics") -> None:
    """ينشئ ملف iCal للتنزيل من قائمة التنبيهات."""
    if not rows:
        st.info("لا يوجد عناصر لتصديرها.")
        return

    def to_ics_datetime(d: dt.date) -> str:
        # صيغة محلية بدون منطقة زمنية (تاريخ فقط)
        return d.strftime("%Y%m%d")

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Rakeem//Compliance Calendar//AR",
    ]
    now = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    for r in rows:
        due = dt.date.fromisoformat(r["تاريخ_الاستحقاق"]) if isinstance(r["تاريخ_الاستحقاق"], str) else r["تاريخ_الاستحقاق"]
        uid = f"{r.get('المعرّف','evt')}@rakeem"
        summary = f"{r['الاسم']} — {r['الجهة']}"
        description = (r.get("الوصف") or "").replace("\n", "\\n")
        ics_lines += [
            "BEGIN:VEVENT",
            f"DTSTAMP:{now}",
            f"UID:{uid}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            f"DTSTART;VALUE=DATE:{to_ics_datetime(due)}",
            f"DTEND;VALUE=DATE:{to_ics_datetime(due + dt.timedelta(days=1))}",
            "END:VEVENT",
        ]

    ics_lines.append("END:VCALENDAR")
    ics_blob = "\n".join(ics_lines).encode("utf-8")
    st.download_button("⬇️ تحميل التقويم (ICS)", ics_blob, file_name=filename, mime="text/calendar")


# =========================
# Core calendar logic
# =========================

def _month_grid(year: int, month: int, week_start: int = 6) -> List[List[Optional[dt.date]]]:
    """يعيد مصفوفة 6x7 لأسابيع الشهر. week_start: 6=السبت (تقويم سعودي شائع)."""
    cal = calendar.Calendar(firstweekday=week_start)
    weeks: List[List[Optional[dt.date]]] = []
    for w in cal.monthdatescalendar(year, month):
        weeks.append([d if d.month == month else None for d in w])
    # ضمان 6 أسابيع للثبات البصري
    while len(weeks) < 6:
        weeks.append([None]*7)
    return weeks


def _collect_month_events(year: int, month: int, profile: CompanyProfile, today: dt.date, path: str) -> List[Dict[str, Any]]:
    """يجلب الاستحقاقات التي تقع داخل الشهر المحدد (باستخدام next_due_date لكل مهمة)."""
    items = load_deadlines(path)
    rows: List[Dict[str, Any]] = []
    for it in items:
        due = next_due_date(it, today, profile)
        if not due:
            continue
        if due.year == year and due.month == month:
            diff = (due - today).days
            rows.append({
                "المعرّف": it.get("المعرّف"),
                "الاسم": it.get("الاسم"),
                "الجهة": it.get("الجهة"),
                "الفئة": it.get("الفئة"),
                "تاريخ_الاستحقاق": due.isoformat(),
                "الأيام_المتبقية": diff,
                "الوصف": it.get("الوصف"),
            })
    rows.sort(key=lambda r: (r["الأيام_المتبقية"], r["الاسم"]))
    return rows


# =========================
# Page renderer
# =========================

def render_calendar_page(df_raw: Optional[pd.DataFrame], profile: CompanyProfile, data_path: str = "data/saudi_deadlines_ar.json") -> None:
    st.markdown("""
        <style>
        .rk-day {height:110px;border:1px solid #e5e7eb;border-radius:12px;background:#fff;padding:8px;transition:all .15s ease;}
        .rk-day:hover {box-shadow:0 4px 14px rgba(0,0,0,.06); transform: translateY(-1px);}
        .rk-day--today {border-color:#ffcc66;}
        .rk-day--has {background:#fef7ec;}
        .rk-pill {display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;border:1px solid #e2e8f0;margin-top:4px;}
        /* تنبيه أحمر للفئات */
        .rk-pill--alert { border-color:#ef4444; color:#ef4444; background:#fee2e2; }
        </style>
        """, unsafe_allow_html=True)



    # فلاتر عليا
    with st.container():
        c1, c2, c3, c4 = st.columns([1,1,1,1])
        today = dt.date.today()
        year = c1.number_input("السنة", min_value=2020, max_value=today.year+2, value=today.year, step=1)
        month = c2.number_input("الشهر", min_value=1, max_value=12, value=today.month, step=1)
        days_ahead = c3.slider("نطاق التنبيهات (يوم)", 7, 365, 60, step=1)
        show_only_month = c4.toggle("عرض مواعيد هذا الشهر فقط", value=True)

    # تنبيه أعلى الصفحة
    st.info("تذكير: يتم حساب المواعيد حسب إعدادات شركتك (نهاية السنة/تكرار VAT/تاريخ السجل التجاري).")

    # شبكة التقويم
    grid = _month_grid(int(year), int(month), week_start=6)

    # اجلب المواعيد
    if show_only_month:
        rows = _collect_month_events(int(year), int(month), profile, today, data_path)
    else:
        rows = upcoming_deadlines(days_ahead=days_ahead, profile=profile, today=today, path=data_path)

    df_events = _to_df(rows)

    # خريطة من اليوم -> قائمة عناصر
    events_by_day: Dict[dt.date, List[Dict[str, Any]]] = {}
    for _, r in df_events.iterrows():
        d = dt.date.fromisoformat(r["تاريخ_الاستحقاق"]) if isinstance(r["تاريخ_الاستحقاق"], str) else r["تاريخ_الاستحقاق"]
        events_by_day.setdefault(d, []).append(r.to_dict())

    # رأس أيام الأسبوع (سبت -> جمعة)
    weekday_names = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
    st.markdown("<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin:8px 0;font-weight:800;color:#002147;'>" +
                "".join([f"<div>{w}</div>" for w in weekday_names]) + "</div>", unsafe_allow_html=True)

    # رسم الشبكة
    for week in grid:
        cols = st.columns(7)
        for i, d in enumerate(week):
            col_idx = 6 - i   # <— نعرض السبت يسار، الأحد يمين
            with cols[col_idx]:
                if d is None:
                    st.markdown(
                        "<div style='height:110px;border:1px dashed #e5e7eb;border-radius:10px;background:#f9fafb;'></div>",
                        unsafe_allow_html=True,
                )
                    continue

                is_today = (d == today)
                has_events = d in events_by_day

                css_classes = ["rk-day"]
                if is_today: css_classes.append("rk-day--today")
                if has_events: css_classes.append("rk-day--has")

                html = [f"<div class='{' '.join(css_classes)}'>",
                        f"<div style='font-weight:800;color:#002147;text-align:right;'>{d.day}</div>"]

            # --- إظهار فئة الموعد باللون الأحمر (إن وجد) ---
                if has_events:
                # نجمع الفئات المميزة لليوم ونكتب أول 2 فقط
                    cats = []
                    for ev in events_by_day[d]:
                        c = ev.get("الفئة") or ""
                        if c and c not in cats:
                            cats.append(c)
                    for c in cats[:2]:
                        html.append(f"<div class='rk-pill rk-pill--alert'>⚠︎ {c}</div>")
                    if len(cats) > 2:
                        html.append(f"<div style='font-size:11px;color:#6b7280;margin-top:4px;'>+{len(cats)-2} فئات أخرى</div>")
            # -----------------------------------------------

                html.append("</div>")
                st.markdown("".join(html), unsafe_allow_html=True)



    st.markdown("---")

    # تفاصيل وأسفل الصفحة
    left, right = st.columns([1,2])
    with right:
        st.markdown("<div class='sec-title'>قائمة المواعيد</div>", unsafe_allow_html=True)
        if df_events.empty:
            st.info("لا يوجد مواعيد ضمن النطاق المحدد.")
        else:
            unique_cats = sorted([x for x in df_events["الفئة"].dropna().unique()])
            unique_orgs = sorted([x for x in df_events["الجهة"].dropna().unique()])
            f1, f2 = st.columns(2)
            sel_cat = f1.multiselect("التصفية حسب الفئة", unique_cats)
            sel_org = f2.multiselect("التصفية حسب الجهة", unique_orgs)

            df_show = df_events.copy()
            if sel_cat:
                df_show = df_show[df_show["الفئة"].isin(sel_cat)]
            if sel_org:
                df_show = df_show[df_show["الجهة"].isin(sel_org)]

            df_show = df_show[["الاسم","الفئة","الجهة","تاريخ_الاستحقاق","الأيام_المتبقية","الوصف"]]
            st.dataframe(df_show, use_container_width=True, hide_index=True)



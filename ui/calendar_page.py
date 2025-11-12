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
from streamlit.components.v1 import html as st_html


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
/* ===== Theme ===== */
:root { --rk-primary:#0f172a; --rk-gold:#ffcc66; --rk-muted:#64748b; }
.sec-title{ text-align:right; }
.rk-filter{direction:rtl;text-align:right;margin:6px 0 10px}
.rk-filter-label{font-weight:700;margin-bottom:4px}
.rk-sec-title{font-weight:900;font-size:18px;margin:8px 0 12px;text-align:right;color:var(--rk-primary)}
/* Calendar day card */
.rk-day{height:120px;border:1px solid #e5e7eb;border-radius:16px;background:#ffffffcc;padding:10px;transition:all .15s ease;backdrop-filter:blur(2px)}
.rk-day:hover{box-shadow:0 8px 24px rgba(0,0,0,.08); transform:translateY(-1px)}
.rk-day--today{border-color:var(--rk-gold);box-shadow:0 0 0 2px #ffe4a3 inset}
.rk-day--has{background:#fff7ec}
/* Chips / Badges */
.rk-chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;font-size:12px;border:1px solid #e2e8f0;background:#f8fafc;margin:6px 0 0}
.rk-chip--alert{border-color:#ef4444;color:#ef4444;background:#fee2e2}
.rk-chip--org{border-color:#94a3b8;color:#334155;background:#f1f5f9}
/* List (cards) */
.rk-list{display:flex;flex-direction:column;gap:10px}
.rk-item{border:1px solid #e5e7eb;background:#ffffff;border-radius:16px;padding:14px 16px}
.rk-item:hover{box-shadow:0 8px 24px rgba(0,0,0,.08)}
.rk-row{display:flex;justify-content:space-between;gap:10px;align-items:center}
.rk-title{font-weight:800;color:var(--rk-primary);font-size:15px}
.rk-meta{font-size:12px;color:var(--rk-muted)}
.rk-due{font-weight:900}
.rk-remain{color:#ef4444;font-weight:800}
.rk-filter{position:sticky;top:0;background:linear-gradient(180deg,#0b1224 0,#0b1224 60%,transparent);padding:8px;border-radius:12px;margin-bottom:8px}
</style>
""", unsafe_allow_html=True)




    # فلاتر عليا
    with st.container():
        col_space1, c1, c2, c3, c4, col_space2 = st.columns([0.5, 1, 1, 2, 1, 0.5])

        today = dt.date.today()

        with c1:
            st.markdown("<div style='text-align:center;font-weight:600;'>السنة</div>", unsafe_allow_html=True)
            year = st.number_input("", min_value=2020, max_value=today.year + 2, value=today.year, step=1, label_visibility="collapsed")

        with c2:
            st.markdown("<div style='text-align:center;font-weight:600;'>الشهر</div>", unsafe_allow_html=True)
            month = st.number_input("", min_value=1, max_value=12, value=today.month, step=1, label_visibility="collapsed")

        with c3:
            st.markdown("<div style='text-align:center;font-weight:600;'>نطاق التنبيهات (يوم)</div>", unsafe_allow_html=True)
            days_ahead = st.slider("", 7, 365, 60, step=1, label_visibility="collapsed")

        with c4:
            st.markdown("<div style='text-align:center;font-weight:600;'>عرض مواعيد هذا الشهر فقط</div>", unsafe_allow_html=True)
            show_only_month = st.toggle("", value=True, label_visibility="collapsed")



    # تنبيه أعلى الصفحة
    st.markdown("""
    <div style="
        background-color:#1e3a8a;
        color:white;
        font-size:14px;
        text-align:right;
        direction:rtl;
        padding:10px 16px;
        border-radius:10px;
        margin-top:8px;
        font-weight:500;
        line-height:1.7;
    ">
    📅 <b>تذكير:</b> (تاريخ السجل التجاري / VAT / نهاية السنة / تكرار) يتم حساب المواعيد حسب إعدادات شركتك.
    </div>
    """, unsafe_allow_html=True)


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

    weekday_names = ["السبت", "الجمعة", "الخميس", "الاربعاء", "الثلاثاء", "الاثنين", "الاحد"]
    st.markdown(
        "<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin:8px 0;"
        "font-weight:800;text-align:center;color:#3b82f6;font-size:15px;padding-right:10px;'>"
        + "".join([f"<div>{w}</div>" for w in weekday_names])
        + "</div>",
        unsafe_allow_html=True
    )


    # رسم الشبكة
    for week in grid:
        cols = st.columns(7)

        # يثبت ترتيب الأعمدة: أحد يمين → سبت يسار
        col_map = {5:0, 4:1, 3:2, 2:3, 1:4, 0:5, 6:6}

        for d in week:
            if d is None:
                continue

            col_idx = col_map[d.weekday()]   # الأحد دائمًا أقصى اليمين
            with cols[col_idx]:
                is_today = (d == today)
                has_events = d in events_by_day

                css_classes = ["rk-day"]
                if is_today:
                    css_classes.append("rk-day--today")
                if has_events:
                    css_classes.append("rk-day--has")

                html = [
                    f"<div class='{' '.join(css_classes)}'>",
                    f"<div style='font-weight:800;color:#002147;text-align:right;'>{d.day}</div>"
                ]

                # إذا فيه مواعيد: اكتب اسم الموعد باللون الأحمر داخل الخانة
                if has_events:
                    cats = []
                    for ev in events_by_day[d]:                 # ← استخدم d وليس day
                        name = (ev.get("الاسم") or "").strip()
                        c    = (ev.get("الفئة") or "").strip()
                        desc = (ev.get("الوصف") or "").strip()
                        if c and c not in cats:
                            cats.append(c)
                        # اسم الموعد باللون الأحمر + تلميح بالوصف
                        html.append(
                            f"<div style='color:#b91c1c;font-weight:600;font-size:13px;margin-top:10px;"
                            f"text-align:center;' title='{desc}'>{name}</div>"
                        )


                    # لو كثيرة، نبين أنه فيه المزيد
                    if len(cats) > 2:
                        html.append(
                            f"<div style='font-size:11px;color:#6b7280;margin-top:2px;'>+{len(cats)-2} مواعيد أخرى</div>"
                        )

                html.append("</div>")
                st.markdown("".join(html), unsafe_allow_html=True)




    st.markdown("---")

    # تفاصيل وأسفل الصفحة
    left, right = st.columns([1,2])
    with right:
        # ===== عنوان =====
        st.markdown("<div class='rk-sec-title'>قائمة المواعيد</div>", unsafe_allow_html=True)

        if df_events.empty:
            st.info("لا يوجد مواعيد ضمن النطاق المحدد.")
        else:
            # ===== فلاتر يمين (الافتراضي: الكل) =====
            unique_cats = sorted([x for x in df_events["الفئة"].dropna().unique()])
            unique_orgs = sorted([x for x in df_events["الجهة"].dropna().unique()])

            st.markdown("<div class='rk-filter'>", unsafe_allow_html=True)
            spacer, col_org, col_cat = st.columns([2.0, 1.2, 1.2])
            with col_org:
                st.markdown("<div class='rk-filter-label'>التصفية حسب الجهة</div>", unsafe_allow_html=True)
                sel_org = st.multiselect("", unique_orgs, default=[], label_visibility="collapsed",
                                        placeholder="اختر الجهة (اختياري)")
            with col_cat:
                st.markdown("<div class='rk-filter-label'>التصفية حسب الفئة</div>", unsafe_allow_html=True)
                sel_cat = st.multiselect("", unique_cats, default=[], label_visibility="collapsed",
                                        placeholder="اختر الفئة (اختياري)")
            st.markdown("</div>", unsafe_allow_html=True)

            # ===== تطبيق التصفية فقط إذا اختار المستخدم =====
            df_show = df_events.copy()
            if sel_cat:
                df_show = df_show[df_show["الفئة"].isin(sel_cat)]
            if sel_org:
                df_show = df_show[df_show["الجهة"].isin(sel_org)]

            if df_show.empty:
                st.info("لا توجد نتائج بعد التصفية.")
            else:
                # ترتيب اختياري (الأقرب أولًا)
                df_show = df_show.sort_values(by=["تاريخ_الاستحقاق","الأيام_المتبقية"], ascending=[True, True])

                # ===== HTML + CSS داخل iframe (مضمون المظهر) =====
                from streamlit.components.v1 import html as st_html

                styles = """
                <style>
                :root{--ink:#0f172a;--muted:#475569;--card:#ffffff;--line:#e5e7eb;--alert:#ef4444;--org:#334155;}
                body{margin:0;padding:0;background:transparent;direction:rtl;font-family:system-ui, -apple-system, Segoe UI, Tahoma;}
                .wrap{max-width:980px;margin:0 auto 8px auto;padding:0 6px;}
                .list{display:flex;flex-direction:column;gap:12px;}
                .item{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:14px 16px;
                    box-shadow:0 6px 18px rgba(0,0,0,.06);}
                .row{display:flex;justify-content:space-between;align-items:center;gap:10px}
                .title{font-weight:800;color:var(--ink);font-size:16px}
                .meta{font-size:13px;color:var(--muted)}
                .due{font-weight:800}
                .remain{color:var(--alert);font-weight:800}
                .chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
                .chip{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:4px 10px;
                    border:1px solid var(--line);font-size:12px;background:#f8fafc;color:var(--org)}
                .chip.alert{border-color:var(--alert);color:var(--alert);background:#fee2e2}
                .desc{margin-top:8px;color:var(--muted);font-size:13px;line-height:1.6}
                </style>
                """

                cards = [styles, "<div class='wrap'><div class='list'>"]
                for _, r in df_show.iterrows():
                    name = str(r.get("الاسم","")).strip()
                    cat  = str(r.get("الفئة","")).strip()
                    org  = str(r.get("الجهة","")).strip()
                    due  = str(r.get("تاريخ_الاستحقاق","")).strip()
                    days = int(r.get("الأيام_المتبقية", 0))
                    desc = str(r.get("الوصف","")).strip()

                    remain_txt = ("اليوم" if days == 0 else ("غدًا" if days == 1 else (f"بعد {days} يوم" if days > 0 else f"منذ {abs(days)} يوم")))

                    cards.append(f"""
                    <div class="item">
                    <div class="row">
                        <div class="title">{name}</div>
                        <div class="meta"><span class="due">📆 {due}</span> · <span class="remain">⏳ {remain_txt}</span></div>
                    </div>
                    <div class="chips">
                        <span class="chip alert">⚠︎ {cat}</span>
                        <span class="chip">🏛️ {org}</span>
                    </div>
                    <div class="desc">{desc}</div>
                    </div>
                    """)

                cards.append("</div></div>")
                html_out = "".join(cards)

                # ارتفاع تلقائي على حسب عدد العناصر (مع حد أقصى)
                est_h = 170 * max(1, len(df_show)) + 40
                st_html(html_out, height=min(est_h, 1400), scrolling=True)







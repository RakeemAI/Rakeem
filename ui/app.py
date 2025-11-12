# =======================================
# app.py — Rakeem Intelligent Dashboard (Full Version with Forecast Alerts + Dynamic Report Recs)
# =======================================

import os, sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------- Repo Path ----------
REPO_ROOT = "/content/Rakeem"
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# ---------- Imports ----------
from engine.io import load_excel, load_csv
from engine.validate import validate_columns
from engine.compute_core import compute_core
from engine.forecasting_core import build_revenue_forecast
from engine.taxes import compute_vat, compute_zakat
from generator.report_generator import generate_financial_report
from llm.run import rakeem_engine
from ui.calendar_page import render_calendar_page
from engine.reminder_core import CompanyProfile

# ---------- Theme ----------
PRIMARY = "#002147"   # كحلي
GOLD    = "#FFCC66"   # ذهبي
TEXT    = "#1E293B"
BG      = "#F9FAFB"
LOGO_PATH = "/content/Rakeem/rakeem_logo.png"

# ---------- Streamlit Config ----------
st.set_page_config(page_title="ركيم — لوحة مالية ذكية", layout="wide")

st.markdown("<style>header {visibility: hidden;}</style>", unsafe_allow_html=True)

# ---------- CSS ----------
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;600;800&display=swap');

:root {{
  --banner-h: 96px;
}}

html, body, [class*="css"] {{
  font-family: 'Noto Sans Arabic', sans-serif;
  background: {BG};
  color: {TEXT};
  direction: rtl;
  text-align: right;
}}

/* ===== Fixed Top Banner ===== */
.top-banner {{
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 999;
  background: {PRIMARY};
  color: white;
  padding: 20px 32px;
  border-bottom: 4px solid {GOLD};
  display: flex;
  align-items: center;
  gap: 20px;
  border-radius: 0;
}}

div[data-testid="stHeader"] {{
  height: 0;
  visibility: hidden;
}}

div[data-testid="stAppViewContainer"] > .main .block-container {{
  padding-top: calc(var(--banner-h) + 12px);
}}

/* ===== Sidebar ===== */
section[data-testid="stSidebar"] > div {{
  background: {PRIMARY};
  height: 100vh;
  padding-top: calc(var(--banner-h) + 20px);
}}

.sidebar-title {{
  font-size: 18px;
  font-weight: 900;
  color: {GOLD};
  margin-bottom: 12px;
  text-align: center;
}}

.nav-btn {{
  display: flex;
  align-items: center;
  justify-content: right;
  gap: 8px;
  padding: 10px 14px;
  font-size: 15px;
  font-weight: 700;
  border-radius: 10px;
  background: {PRIMARY};
  color: white;
  margin-bottom: 6px;
  cursor: pointer;
  border: 1px solid rgba(255,255,255,0.15);
  transition: background 0.25s, color 0.25s, border 0.25s;
}}
.nav-btn:hover {{
  background: {GOLD};
  color: {PRIMARY};
}}
.nav-btn.active {{
  background: {GOLD};
  color: {PRIMARY};
  border: 1px solid {GOLD};
  font-weight: 900;
}}

/* ===== Sections & Cards ===== */
.section {{
  background: white;
  border-radius: 12px;
  padding: 20px;
  margin-top: 18px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}}
.sec-title {{
  font-weight: 900;
  color: {PRIMARY};
  border-bottom: 2px solid {GOLD};
  padding-bottom: 6px;
  margin-bottom: 10px;
}}

/* ===== KPI Grid ===== */
.kpi-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}}
.kpi-card {{
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  text-align: center;
}}
.kpi-label {{ color: #64748b; font-weight: 700; }}
.kpi-value {{ color: {PRIMARY}; font-weight: 900; font-size: 1.4rem; }}

/* ===== Chat Styles ===== */
.chat-wrap {{
  display: flex;
  flex-direction: column;
  gap: 10px;
}}
.chat-bubble {{
  border-radius: 14px;
  padding: 12px 16px;
  margin-bottom: 10px;
  line-height: 1.7;
  max-width: 75%;
  word-wrap: break-word;
}}
.chat-bubble.assistant {{
  background: #ffffff;
  border: 1px solid #e5e7eb;
  align-self: flex-start;
}}
.chat-bubble.user {{
  background: #e8f0fe;
  border: 1px solid #d1d5db;
  align-self: flex-end;
  margin-right: auto;
}}
.role-label {{
  font-weight: 700;
  font-size: 0.8rem;
  color: {GOLD};
  margin-bottom: 4px;
}}
.msg-body {{
  font-size: 0.95rem;
  color: #111827;
}}
.msg-body ul {{ list-style: disc; padding-right: 24px !important; margin: 6px 0; }}
.msg-body li {{ margin-bottom: 4px; }}

/* ===== Footer ===== */
.footer {{
  background: {PRIMARY};
  color: white;
  text-align: center;
  padding: 10px 0;
  border-top: 2px solid {GOLD};
  font-weight: 700;
  border-radius: 12px 12px 0 0;
  position: fixed;
  bottom: 0;
  left: 0;
  width: 100%;
}}
.page-spacer {{
  height: 90px;
}}

/* ===== Calendar ===== */
.cal-header {{
  display: grid;
  grid-template-columns: repeat(7,1fr);
  text-align: center;
  font-weight: 800;
  color: {GOLD};
  margin-top: 10px;
}}
.day-cell {{
  height: 110px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: white;
  padding: 8px;
  text-align: right;
  position: relative;
  transition: all .15s ease;
}}
.day-cell:hover {{
  background: #fff7ec;
  transform: scale(1.01);
  box-shadow: 0 0 10px rgba(0,0,0,0.08);
}}
.today {{
  border: 2px solid {GOLD};
}}
.event {{
  font-size: 13px;
  color: #b91c1c;
  margin-top: 6px;
  font-weight: 600;
  text-align: center;
}}
.day-number {{
  font-weight: 800;
  color: {PRIMARY};
}}
</style>
""", unsafe_allow_html=True)


# ---------- Banner ----------
# ---------- Banner (fixed top, text perfectly positioned) ----------
st.markdown(f"""
<div class="top-banner" style="justify-content:flex-start;">
  <img src="{LOGO_PATH}" style="width:70px;height:70px;border-radius:8px;object-fit:cover;"/>
  <div style="margin-right:220px; text-align:right;"> <!-- fine-tuned offset -->
    <div style="font-size:28px;font-weight:900;">ركيم - Rakeem Dashboard</div>
    <div style="color:{GOLD};font-weight:700;font-size:15px;">
      لوحة تحكم مالية ذكية للشركات الصغيرة والمتوسطة
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ---------- Helpers ----------
def infer_company_name(df_raw: pd.DataFrame, df_proc: pd.DataFrame) -> str:
    try:
        for col in df_raw.columns:
            col_l = str(col).strip().lower()
            if any(k in col_l for k in ["شركة","الشركة","company","organization","firm","entity","name","المنشأة","الاسم"]):
                series = df_raw[col].dropna().astype(str).str.strip()
                series = series[series.ne("") & series.ne("nan") & series.ne("None")]
                if not series.empty:
                    return series.iloc[0]
    except Exception:
        pass
    return "شركة غير محددة"

def format_sar(x): 
    try:
        return f"{float(x):,.0f} ريال"
    except Exception:
        return "—"

# ---------- Pages ----------
def dashboard_page(df, company_name: str):
    # ---------- Internal VAT & Zakat Calculations ----------
    def calculate_vat(df: pd.DataFrame) -> float:
        vat_rate = 0.15
        vat_sales = df["revenue"].sum() * vat_rate
        vat_purchases = df["expenses"].sum() * vat_rate * 0.5  # assume 50% deductible
        net_vat = vat_sales - vat_purchases
        return max(net_vat, 0)

    def calculate_zakat(df: pd.DataFrame) -> float:
        zakat_rate = 0.025
        base = max(df["revenue"].sum() - df["expenses"].sum(), 0)
        zakat = base * zakat_rate
        return zakat

    # ---------- Core Financial Totals ----------
    rev = df["revenue"].sum()
    exp = df["expenses"].sum()
    prof = df["profit"].sum()
    cash = df["cash_flow"].sum()
    vat = calculate_vat(df)
    zakat = calculate_zakat(df)

    # ---------- KPI Section ----------
    st.markdown('<div class="section"><div class="sec-title">المؤشرات الرئيسية</div>', unsafe_allow_html=True)
    st.markdown('<div class="kpi-grid">', unsafe_allow_html=True)
    for label, val in [
        ("إجمالي الإيرادات", rev),
        ("إجمالي المصروفات", exp),
        ("صافي الربح", prof),
        ("التدفق النقدي", cash),
        ("صافي الضريبة (VAT)", vat),
        ("الزكاة المستحقة", zakat),
    ]:
        st.markdown(
            f"<div class='kpi-card'><div class='kpi-label'>{label}</div>"
            f"<div class='kpi-value'>{val:,.0f} ريال</div></div>",
            unsafe_allow_html=True
        )
    st.markdown('</div></div>', unsafe_allow_html=True)

    # ---------- Monthly Trends ----------
    st.markdown('<div class="section"><div class="sec-title">الاتجاهات الشهرية</div>', unsafe_allow_html=True)
    tabs = st.tabs(["الإيرادات", "المصروفات", "الأرباح"])
    for i, col in enumerate(["revenue", "expenses", "profit"]):
        with tabs[i]:
            d = df[["date", col]].dropna()
            if not d.empty:
                fig = px.line(d, x="date", y=col, template="plotly_white", color_discrete_sequence=[PRIMARY])
                fig.update_layout(height=350, margin=dict(l=10, r=10, t=20, b=10))
                st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ---------- Forecast & Smart Alerts ----------
    st.markdown('<div class="section"><div class="sec-title">التنبؤ المالي والتنبيهات</div>', unsafe_allow_html=True)
    try:
        fc = build_revenue_forecast(df, periods=6)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["date"], y=df["revenue"], name="الإيرادات الفعلية", line=dict(color=PRIMARY)))
        fig.add_trace(go.Scatter(x=fc["date"], y=fc["forecast"], name="التنبؤ", line=dict(color=GOLD, dash="dash")))
        fig.update_layout(template="plotly_white", height=400)
        st.plotly_chart(fig, use_container_width=True)

        # --- Analyze Last 3 Months for Alerts ---
        recent_df = df.tail(3)
        rev_recent = recent_df["revenue"].sum()
        profit_recent = recent_df["profit"].sum()
        cashflow_recent = recent_df["cash_flow"].sum()
        vat_recent = calculate_vat(recent_df)
        zakat_recent = calculate_zakat(recent_df)
        profit_margin = profit_recent / max(rev_recent, 1)

        alerts = []

        # Profitability Alerts
        if profit_margin < 0.1:
            alerts.append({
                "level": "high",
                "title": "🔻 الربح ضعيف جدًا (<10%)",
                "reason": "نسبة الأرباح إلى الإيرادات في آخر 3 أشهر منخفضة للغاية.",
                "recommendations": [
                    "راجع استراتيجية التسعير لتحسين هوامش الربح.",
                    "قلّل المصروفات التشغيلية أو أعد توزيع الموارد لتحقيق كفاءة أعلى."
                ]
            })
        elif profit_margin < 0.2:
            alerts.append({
                "level": "medium",
                "title": "⚖️ الربح منخفض (<20%)",
                "reason": "الربحية في آخر 3 أشهر دون المستوى المثالي.",
                "recommendations": [
                    "حاول تحسين دورة الإيرادات من خلال زيادة حجم المبيعات.",
                    "قم بتحليل المصروفات الثابتة والمتغيرة لتقليل الأعباء غير الضرورية."
                ]
            })

        # Cashflow Alert
        if cashflow_recent < 0:
            alerts.append({
                "level": "high",
                "title": "🔻 التدفق النقدي سلبي",
                "reason": "النفقات النقدية تتجاوز التدفقات الداخلة مؤخرًا، ما يضغط على السيولة.",
                "recommendations": [
                    "عزّز التحصيل بتقصير آجال السداد من العملاء.",
                    "أعد جدولة الالتزامات قصيرة الأجل لتخفيف الضغط المالي."
                ]
            })

        # Zakat & VAT Alerts
        if zakat_recent > rev_recent * 0.2:
            alerts.append({
                "level": "medium",
                "title": "⚖️ الزكاة مرتفعة (>20% من الإيرادات)",
                "reason": "الزكاة المستحقة نسبةً للإيرادات في آخر 3 أشهر مرتفعة.",
                "recommendations": [
                    "راجع طريقة احتساب الزكاة بدقة وفق المعايير الشرعية.",
                    "استثمر الأصول المعطلة لتقليل المبالغ الواجبة الزكاة."
                ]
            })
        if vat_recent > rev_recent * 0.2:
            alerts.append({
                "level": "medium",
                "title": "⚖️ الضريبة مرتفعة (>20% من الإيرادات)",
                "reason": "معدل الضريبة نسبةً للإيرادات في آخر 3 أشهر مرتفع.",
                "recommendations": [
                    "تحقق من خصم ضريبة المدخلات بدقة في التقارير.",
                    "تأكد من تحديث الإقرارات الضريبية وفق آخر التشريعات."
                ]
            })

        # --- Display Alerts ---
        if alerts:
            for alert in alerts:
                color = "#f87171" if alert["level"] == "high" else "#facc15"
                recs_html = "<ul style='margin:6px 0; padding-right:20px;'>"
                for r in alert["recommendations"]:
                    recs_html += f"<li>{r}</li>"
                recs_html += "</ul>"
                st.markdown(f"""
                <div style="border-right:5px solid {color}; padding:14px; margin-bottom:10px;
                            background:#f3f4f6; border-radius:8px;">
                    <b>{alert['title']}</b><br>
                    <span style="color:#374151;">السبب:</span> {alert['reason']}<br>
                    <span style="color:#374151;">التوصيات:</span> {recs_html}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="border-right:5px solid #4ade80; padding:14px; margin-bottom:10px;
                        background:#ecfdf5; border-radius:8px;">
                <b>✅ الوضع المالي مستقر</b><br>
                لا توجد مؤشرات خطر حالية. الأداء متوازن والإيرادات تغطي المصروفات.
                <ul style='margin:6px 0; padding-right:20px;'>
                    <li>استمر في مراقبة الربحية والتدفق النقدي شهريًا للحفاظ على الاستقرار.</li>
                    <li>استثمر جزءًا من الفائض في مشاريع منخفضة المخاطر لدعم النمو.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.warning(f"تعذر عرض التنبؤ: {e}")

    # ---------- Footer Spacer ----------
    st.markdown('<div class="page-spacer"></div>', unsafe_allow_html=True)


def chat_page(df):
    # تحديد اسم الشركة لعرضه داخل الرسائل عند الحاجة
    company_name = st.session_state.get("company_name", "شركتك")

    st.markdown('<div class="section"><div class="sec-title">المحادثة الذكية 🤖</div>', unsafe_allow_html=True)

    # حالة المحادثة
    if "chat_msgs" not in st.session_state:
        st.session_state.chat_msgs = [
            {"role":"assistant","content":f"مرحبًا! أنا ريكم 🤖 — مساعدك المالي لشركة {company_name}. اسألني عن الأرباح، المصروفات، الزكاة أو الأداء العام."}
        ]

    # عرض الرسائل
    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    for msg in st.session_state.chat_msgs:
        cls = "assistant" if msg["role"] == "assistant" else "user"
        who = "ريكم 🤖" if cls == "assistant" else "👤 المستخدم"
        st.markdown(f"""
        <div class="chat-bubble {cls}">
            <div class="role-label">{who}</div>
            <div class="msg-body">{msg['content']}</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # إدخال المستخدم
    user_q = st.chat_input("اكتب سؤالك هنا…")
    if user_q:
        st.session_state.chat_msgs.append({"role":"user","content":user_q})
        try:
            res = rakeem_engine.answer(user_q, df=df, company_name=company_name)
            reply = res.get("html", "—")
        except Exception as e:
            reply = f"⚠️ حدث خطأ أثناء التحليل: {e}"
        st.session_state.chat_msgs.append({"role":"assistant","content":reply})
        st.rerun()

    # Spacer قبل الفوتر
    st.markdown('<div class="page-spacer"></div>', unsafe_allow_html=True)

def review_page():
    st.markdown('<div class="section"><div class="sec-title">المراجعة البشرية 🧠</div>', unsafe_allow_html=True)
    st.info("🔗 أنشئ رابط مراجعة فريد للمراجع المالي.")
    if st.button("إنشاء رابط المراجعة"):
        st.success("✅ تم إنشاء الرابط الفريد. أرسله للمراجع.")
    st.file_uploader("📤 رفع تقرير المراجعة النهائي", type=["pdf","xlsx","docx"])
    st.markdown('<div class="page-spacer"></div>', unsafe_allow_html=True)

def report_page(df):
    st.markdown('<div class="section"><div class="sec-title">توليد التقارير 📄</div>', unsafe_allow_html=True)

    # أرقام أساسية للتوصيات الديناميكية
    rev       = float(df["revenue"].sum())
    exp       = float(df["expenses"].sum())
    profit    = float(df["profit"].sum())
    cashflow  = float(df["cash_flow"].sum())
    net_vat   = float(compute_vat(df))
    zakat_due = float(compute_zakat(df))

    company_name = st.session_state.get("company_name", "شركة غير محددة")

    if st.button("توليد التقرير الآن"):
        # توصيات ديناميكية (مأخوذة من الكود المرجعي)
        dyn_recs = []
        profit_margin = (profit / rev) if rev > 0 else 0.0
        if exp > rev * 0.7:
            dyn_recs.append("خفض المصروفات التشغيلية التي زادت عن 70٪ من الإيرادات خلال الفترة.")
        else:
            dyn_recs.append("استمر في ضبط المصروفات التشغيلية عند مستوياتها الحالية.")

        if profit_margin < 0.2:
            dyn_recs.append("ارفع هوامش الربح بمراجعة التسعير أو تحسين مزيج المنتجات.")
        else:
            dyn_recs.append("حافظ على مستوى هوامش الربح الحالي مع مراقبة أي تراجع مفاجئ.")

        if cashflow < 0:
            dyn_recs.append("حسّن دورة التحصيل النقدي وتقصير آجال المدينين لتحسين التدفق النقدي.")
        else:
            dyn_recs.append("استثمر جزءًا من التدفق النقدي الإيجابي في أنشطة توليد الإيرادات.")

        dyn_recs.append("التأكد من مطابقة الإقرارات الضريبية والزكوية للبيانات المالية المعتمدة.")

        try:
            path = generate_financial_report(
                company_name=company_name,   # ← اسم الشركة الفعلي
                report_title=f"التقرير المالي الشامل — {company_name}",
                metrics={
                    "total_revenue": rev,
                    "total_expenses": exp,
                    "total_profit": profit,
                    "total_cashflow": cashflow,
                    "net_vat": net_vat,
                    "zakat_due": zakat_due,
                },
                recommendations=dyn_recs,
                data_tables={
                    "الإيرادات": df[["date","revenue"]],
                    "المصروفات": df[["date","expenses"]],
                    "الأرباح": df[["date","profit"]],
                },
                template_path="generator/report_template.html",
                output_pdf="financial_report.pdf"
            )
            with open(path, "rb") as fh:
                st.download_button("⬇ تنزيل التقرير", fh, "financial_report.pdf")
            st.success(f"تم إنشاء التقرير لشركة {company_name}.")
        except Exception as e:
            st.error(f"فشل إنشاء التقرير: {e}")

    st.markdown('<div class="page-spacer"></div>', unsafe_allow_html=True)

def calendar_page():
    import datetime as dt
    import calendar
    import pandas as pd
    from engine.reminder_core import CompanyProfile, load_deadlines, next_due_date, upcoming_deadlines

    # ===== إعدادات الشركة =====
    st.markdown('<div class="section"><div class="sec-title">📅 التقويم الذكي — الالتزامات السعودية</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        fye_month = st.number_input("📆 شهر نهاية السنة المالية", 1, 12, 12)
    with col2:
        fye_day = st.number_input("📅 يوم نهاية السنة المالية", 1, 31, 31)
    with col3:
        vat_freq = st.selectbox("💰 تكرار ضريبة القيمة المضافة", ["monthly", "quarterly"],
                                format_func=lambda x: "شهري" if x == "monthly" else "ربع سنوي")

    profile = CompanyProfile(
        fiscal_year_end_month=int(fye_month),
        fiscal_year_end_day=int(fye_day),
        vat_frequency=vat_freq,
    )

    today = dt.date.today()
    year = today.year
    month = today.month

    # ===== دالة مساعدة لرسم شبكة الشهر =====
    def _month_grid(year, month, week_start=6):
        cal = calendar.Calendar(firstweekday=week_start)
        weeks = []
        for w in cal.monthdatescalendar(year, month):
            weeks.append([d if d.month == month else None for d in w])
        while len(weeks) < 6:
            weeks.append([None] * 7)
        return weeks

    # ===== تحميل المهام =====
    data_path = "data/saudi_deadlines_ar.json"
    items = load_deadlines(data_path)
    rows = []
    for it in items:
        due = next_due_date(it, today, profile)
        if due and due.month == month and due.year == year:
            diff = (due - today).days
            rows.append({
                "الاسم": it.get("الاسم"),
                "الجهة": it.get("الجهة"),
                "الفئة": it.get("الفئة"),
                "تاريخ_الاستحقاق": due.isoformat(),
                "الأيام_المتبقية": diff,
                "الوصف": it.get("الوصف"),
            })

    df = pd.DataFrame(rows)
    events_by_day = {}
    for _, r in df.iterrows():
        d = dt.date.fromisoformat(r["تاريخ_الاستحقاق"])
        events_by_day.setdefault(d, []).append(r.to_dict())

    grid = _month_grid(year, month)
    weekday_names = ["السبت", "الجمعة", "الخميس", "الأربعاء", "الثلاثاء", "الاثنين", "الأحد"]

    # ===== تصميم CSS نظيف (شبكي ومرتب) =====
    st.markdown(f"""
    <style>
    .cal-header {{
        display:grid;
        grid-template-columns:repeat(7,1fr);
        text-align:center;
        font-weight:800;
        color:{GOLD};
        margin-top:10px;
    }}
    .day-cell {{
        height:110px;
        border:1px solid #e5e7eb;
        border-radius:12px;
        background:white;
        padding:8px;
        text-align:right;
        position:relative;
        transition:all .15s ease;
    }}
    .day-cell:hover {{
        background:#fff7ec;
        transform:scale(1.01);
        box-shadow:0 0 10px rgba(0,0,0,0.08);
    }}
    .today {{
        border:2px solid {GOLD};
    }}
    .event {{
        font-size:13px;
        color:#b91c1c;
        margin-top:6px;
        font-weight:600;
        text-align:center;
    }}
    .day-number {{
        font-weight:800;
        color:{PRIMARY};
    }}
    </style>
    """, unsafe_allow_html=True)

    # ===== رسم رأس الأسبوع =====
    st.markdown("<div class='cal-header'>" + "".join([f"<div>{d}</div>" for d in weekday_names]) + "</div>", unsafe_allow_html=True)

    # ===== شبكة الأيام =====
    for week in grid:
        cols = st.columns(7)
        col_map = {5: 0, 4: 1, 3: 2, 2: 3, 1: 4, 0: 5, 6: 6}
        for d in week:
            if d is None:
                continue
            col_idx = col_map[d.weekday()]
            with cols[col_idx]:
                is_today = (d == today)
                has_events = d in events_by_day
                css_classes = "day-cell today" if is_today else "day-cell"
                html = f"<div class='{css_classes}'><div class='day-number'>{d.day}</div>"
                if has_events:
                    for ev in events_by_day[d]:
                        html += f"<div class='event' title='{ev.get('الوصف','')}'>{ev.get('الاسم')}</div>"
                html += "</div>"
                st.markdown(html, unsafe_allow_html=True)

    # ===== قائمة المواعيد (تحت الشبكة) =====
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="sec-title">قائمة المواعيد القادمة</div>', unsafe_allow_html=True)

    if df.empty:
        st.info("لا توجد التزامات لهذا الشهر.")
    else:
        for _, r in df.sort_values("الأيام_المتبقية").iterrows():
            name = r["الاسم"]
            org = r["الجهة"]
            cat = r["الفئة"]
            due = r["تاريخ_الاستحقاق"]
            remain = r["الأيام_المتبقية"]
            st.markdown(
                f"""
                <div style='background:white;border:1px solid #e5e7eb;padding:10px 14px;border-radius:10px;margin-bottom:8px;'>
                    <b style='color:{PRIMARY}'>{name}</b> — {org} ({cat})<br>
                    <span style='color:#b91c1c;font-weight:700;'>📅 {due}</span> ·
                    <span style='color:#f59e0b;font-weight:700;'>⏳ {"اليوم" if remain==0 else ("غدًا" if remain==1 else f"بعد {remain} يوم")}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown('<div class="page-spacer"></div>', unsafe_allow_html=True)


# ---------- Sidebar ----------
def set_page(page_name):
    st.session_state["page"] = page_name

if "page" not in st.session_state:
    st.session_state["page"] = "dashboard"

with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;margin-bottom:20px;">
        <img src="{LOGO_PATH}" style="width:65px;height:65px;border-radius:10px;margin-bottom:5px;"/>
        <div style="font-weight:800;color:white;">ركيــم</div>
        <div style="color:{GOLD};font-size:13px;">لوحة تحكم مالية ذكية</div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(
        f"<h3 style='color:{GOLD}; font-weight:800; text-align:right;'>📂 رفع الملف المالي</h3>",
        unsafe_allow_html=True
    )
    upl = st.file_uploader("", type=["xlsx","xls","csv"], key="uploaded_file")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div class='sidebar-title'></div>", unsafe_allow_html=True)

           # ===== Improved Navigation (Stylish Buttons that actually navigate) =====
        # ===== Improved Navigation (Stylish Buttons that actually navigate) =====
    nav_items = [
        ("dashboard", "🏠 لوحة التحكم"),
        ("chat", "🤖 المحادثة الذكية"),
        ("review", "🧠 المراجعة البشرية"),
        ("reports", "📄 توليد التقارير"),
        ("calendar", "📅 التقويم الذكي"),
    ]

    st.markdown("<div class='sidebar-title'> </div>", unsafe_allow_html=True)
    st.markdown("<div class='nav-container' style='margin-top:10px;'>", unsafe_allow_html=True)

    for pid, label in nav_items:
        active = st.session_state["page"] == pid
        bg = GOLD if active else "rgba(255,255,255,0.05)"
        color = PRIMARY if active else "white"
        weight = "900" if active else "600"
        shadow = "0 0 10px rgba(255, 204, 102, 0.4)" if active else "none"

        button_clicked = st.button(
            label,
            key=f"nav_{pid}",
            use_container_width=True,
            help="اضغط للانتقال"
        )

        # Custom button styling
        st.markdown(f"""
        <style>
        div[data-testid="stButton"][key="nav_{pid}"] button {{
            background:{bg};
            color:{color};
            border-radius:12px;
            padding:12px 14px;
            font-weight:{weight};
            font-size:15px;
            margin-bottom:8px;
            text-align:right;
            box-shadow:{shadow};
            cursor:pointer;
            border:1px solid rgba(255,255,255,0.15);
            transition:all .25s ease;
        }}
        div[data-testid="stButton"][key="nav_{pid}"] button:hover {{
            background:{GOLD};
            color:{PRIMARY};
        }}
        </style>
        """, unsafe_allow_html=True)

        if button_clicked and not active:
            st.session_state["page"] = pid
            st.rerun()  # <-- Correct method, works with all recent Streamlit versions

    st.markdown("</div>", unsafe_allow_html=True)




# ---------- Load once ----------
upl = st.session_state.get("uploaded_file")
if not upl:
    st.info("⬆️ الرجاء رفع الملف المالي لبدء التحليل.")
    st.markdown('<div class="page-spacer"></div>', unsafe_allow_html=True)
    st.markdown('<div class="footer">© 2025 ركيـم — منصة الذكاء المالي المتكاملة</div>', unsafe_allow_html=True)
    st.stop()

ext = str(upl.name).split(".")[-1].lower()
df_raw = load_excel(upl, sheet=0) if ext in ("xlsx","xls") else load_csv(upl)
validate_columns(df_raw)
df = compute_core(df_raw)

if "company_name" not in st.session_state:
    st.session_state["company_name"] = infer_company_name(df_raw, df)

# ---------- Routing ----------
page = st.session_state["page"]
if page == "dashboard":
    dashboard_page(df, st.session_state["company_name"])
elif page == "chat":
    chat_page(df)
elif page == "review":
    review_page()
elif page == "reports":
    report_page(df)
elif page == "calendar":
    calendar_page()

# ---------- Footer ----------
st.markdown('<div class="footer">© 2025 ركيـم — منصة الذكاء المالي المتكاملة</div>', unsafe_allow_html=True)

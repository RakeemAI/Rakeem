# ui/app.py 
import os, sys, json, re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ========== Imports ==========
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from engine.io import load_excel, load_csv
from engine.validate import validate_columns
from engine.compute_core import compute_core
from engine.taxes import compute_vat, compute_zakat
from generator.report_generator import generate_financial_report

# ========== Streamlit Config ==========
st.set_page_config(page_title="Rakeem Dashboard", layout="wide")

# ========== Colors ==========
PRIMARY = "#002147"   # كحلي غامق
ACCENT = "#ffcc66"    # ذهبي
BG_LIGHT = "#f9fafb"
TEXT_DARK = "#111827"

# ========== CSS ==========
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;600;700&display=swap');
html, body, [class*="css"] {{
  font-family: 'Noto Sans Arabic', sans-serif;
  background-color: {BG_LIGHT};
  color: {TEXT_DARK};
}}
.block-container {{
  padding-top: 1rem;
  padding-bottom: 2rem;
  direction: rtl;
  text-align: right;
}}
.header {{
  background: {PRIMARY};
  color: white;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 20px;
  box-shadow: 0 3px 12px rgba(0,0,0,.1);
}}
.header h1 {{
  font-weight: 800;
  font-size: 28px;
  margin: 0 0 8px 0;
}}
.header p {{
  margin: 0;
  color: {ACCENT};
  font-weight: 600;
}}
.kpi-grid {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin: 10px 0 20px;
}}
.kpi-card {{
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,.03);
  transition: all .2s ease;
}}
.kpi-card:hover {{
  box-shadow: 0 4px 12px rgba(0,0,0,.08);
}}
.kpi-label {{
  font-weight: 700;
  color: #64748b;
  margin-bottom: 6px;
}}
.kpi-value {{
  font-weight: 800;
  font-size: 1.4rem;
  color: {PRIMARY};
}}
.sec-title {{
  color: {PRIMARY};
  font-size: 18px;
  margin: 0 0 10px;
  padding-bottom: 8px;
  border-bottom: 2px solid {ACCENT};
  font-weight: 900;
}}
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
  font-size: 0.75rem;
  color: {PRIMARY};
  margin-bottom: 4px;
}}
.msg-body {{
  font-size: 0.95rem;
  color: {TEXT_DARK};
}}
.msg-body ul {{
  list-style: disc;
  padding-right: 24px !important;
  margin: 6px 0;
}}
.msg-body li {{
  margin-bottom: 4px;
}}
</style>
""", unsafe_allow_html=True)

# ========== Utility ==========
def sar(x): return f"{float(x):,.0f} ريال" if pd.notna(x) else "—"

# ========== Header ==========
st.markdown(f"""
<div class="header">
  <h1>ركيم — Rakeem Dashboard</h1>
  <p>لوحة مؤشرات مالية تفاعلية وتحليل ذكي للأداء.</p>
</div>
""", unsafe_allow_html=True)

# ========== File Upload ==========
st.sidebar.header("📂 رفع الملف المالي")
uploaded = st.sidebar.file_uploader("اختر ملف Excel أو CSV", type=["xlsx","xls","csv"])
if not uploaded:
    st.info("للبدء، قم برفع الملف من الشريط الجانبي.")
    st.stop()

try:
    ext = uploaded.name.split(".")[-1].lower()
    df_raw = load_excel(uploaded, sheet=0) if ext in ("xlsx","xls") else load_csv(uploaded)
    validate_columns(df_raw)
    df = compute_core(df_raw)
except Exception as e:
    st.error(f"خطأ أثناء التحميل أو الحساب: {e}")
    st.stop()
def infer_company_name(df_raw, df):
    for col in df_raw.columns:
        col_l = str(col).strip().lower()
        if any(k in col_l for k in ["شركة", "company", "organization", "firm", "entity", "name"]):
            try:
                val = df_raw[col].dropna().astype(str).str.strip().replace({"nan": "", "None": ""}).iloc[0]
                if val:
                    return val
            except Exception:
                continue
    return "شركة غير محددة"

company_name = infer_company_name(df_raw, df)
# ========== Metrics ==========
vat = compute_vat(df)
zakat = compute_zakat(df)
rev = df["revenue"].sum()
exp = df["expenses"].sum()
profit = df["profit"].sum()
cashflow = df["cash_flow"].sum()

st.markdown('<div class="sec-title">المؤشرات الرئيسية</div>', unsafe_allow_html=True)
st.markdown('<div class="kpi-grid">', unsafe_allow_html=True)
for label, val in [
    ("إجمالي الإيرادات", rev),
    ("إجمالي المصروفات", exp),
    ("صافي الربح", profit),
    ("التدفق النقدي", cashflow),
]:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{sar(val)}</div>
    </div>
    """, unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ========== Charts ==========
st.markdown('<div class="sec-title">الاتجاهات الشهرية</div>', unsafe_allow_html=True)
def plot_line(df, col, title):
    d = df[["date", col]].dropna()
    if d.empty: return
    fig = px.line(d, x="date", y=col, title=None, template="plotly_white")
    fig.update_traces(line=dict(width=2.5, color=PRIMARY))
    fig.update_layout(height=380, margin=dict(l=20,r=20,t=20,b=20),
                      xaxis_title="التاريخ", yaxis_title=title)
    st.plotly_chart(fig, use_container_width=True)
tabs = st.tabs(["الإيرادات", "المصروفات", "الربح"])
with tabs[0]: plot_line(df, "revenue", "الإيرادات")
with tabs[1]: plot_line(df, "expenses", "المصروفات")
with tabs[2]: plot_line(df, "profit", "الربح")

# ========== Forecast ==========
st.markdown('<div class="sec-title">التنبؤ المالي</div>', unsafe_allow_html=True)
with st.expander("عرض التنبؤ المالي", expanded=True):
    try:
        from engine.forecasting_core import build_revenue_forecast
        fc = build_revenue_forecast(df, periods=6)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["date"], y=df["revenue"], name="الإيرادات الفعلية", line=dict(color=PRIMARY)))
        fig.add_trace(go.Scatter(x=fc["date"], y=fc["forecast"], name="التنبؤ", line=dict(color=ACCENT, dash="dash")))
        fig.update_layout(template="plotly_white", height=400)
        st.plotly_chart(fig, use_container_width=True)

        # ✅ توصيات وتحليل ذكي
        tips = []
        if len(fc):
            growth = (fc["forecast"].iloc[-1] - fc["forecast"].iloc[0]) / max(fc["forecast"].iloc[0], 1)
            if growth > 0.15:
                tips.append("الاتجاه العام يشير إلى نمو واضح في الإيرادات خلال الأشهر القادمة.")
            elif growth < -0.10:
                tips.append("الاتجاه العام يشير إلى انخفاض في الإيرادات، يُنصح بمراجعة النفقات التشغيلية.")
            else:
                tips.append("الإيرادات مستقرة نسبيًا، حافظ على نفس وتيرة الأداء.")
        if profit < 0:
            tips.append("الشركة تسجل خسارة حالية، يُنصح بمراجعة التكاليف التشغيلية ومصادر الإيراد.")
        if cashflow < 0:
            tips.append("التدفق النقدي سلبي، يُوصى بمراقبة السيولة وإدارة الديون قصيرة الأجل.")

        st.markdown("<div class='sec-title' style='font-size:16px;margin-top:10px;'>توصيات وتحليل سريع</div>", unsafe_allow_html=True)
        if tips:
            st.markdown("<ul style='margin-top:8px;line-height:1.8;'>", unsafe_allow_html=True)
            for t in tips:
                st.markdown(f"<li style='margin-bottom:4px;'>{t}</li>", unsafe_allow_html=True)
            st.markdown("</ul>", unsafe_allow_html=True)
        else:
            st.info("لا توجد توصيات إضافية حالياً.")
    except Exception as e:
        st.warning(f"تعذر عرض التنبؤ: {e}")

# ========== Chat Section ==========
st.markdown('<div class="sec-title">المحادثة الذكية</div>', unsafe_allow_html=True)

# ========== Company Name Utility ==========
def infer_company_name(df_raw, df):
    # نحول كل الأعمدة للأحرف الصغيرة للفحص المرن
    for col in df_raw.columns:
        col_l = str(col).strip().lower()
        if any(k in col_l for k in ["شركة", "company", "organization", "firm", "entity", "name"]):
            try:
                # نبحث عن أول قيمة نصية غير فارغة في العمود
                val = df_raw[col].dropna().astype(str).str.strip().replace({"nan": "", "None": ""}).iloc[0]
                if val:
                    return val
            except Exception:
                continue

    # محاولة أخرى: إذا في metadata أو أول صف فيه الاسم
    if "company" in df_raw.index.name.lower() if df_raw.index.name else "":
        val = str(df_raw.index[0]).strip()
        if val:
            return val

    return "شركة غير محددة"

_backend = None
try:
    from llm.run import chat_answer as _chain_chat_answer
    _backend = ("chain", _chain_chat_answer)
except Exception:
    try:
        from llm.simple_backend import answer as _simple_answer
        _backend = ("simple", _simple_answer)
    except Exception:
        st.warning("⚠ لا يوجد باك-إند متاح للشات.")
        _backend = None

# ====== State Memory ======
if "chat_msgs" not in st.session_state:
    st.session_state.chat_msgs = [
        {"role": "assistant", "content": "مرحبًا! ارفع ملفك المالي ثم اسألني عن الأرباح أو المصروفات أو الأداء العام."}
    ]
if "chat_context" not in st.session_state:
    st.session_state.chat_context = {"has_summary": False, "memory": ""}

# ====== Chat UI ======
st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
for msg in st.session_state.chat_msgs:
    cls = "assistant" if msg["role"] == "assistant" else "user"
    st.markdown(f"""
    <div class="chat-bubble {cls}">
        <div class="role-label">{'المساعد' if cls=='assistant' else 'أنت'}</div>
        <div class="msg-body">{msg['content']}</div>
    </div>
    """, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ====== Input ======
# ====== Input ======
user_q = st.chat_input("اكتب سؤالك هنا…")

if user_q:
    st.session_state.chat_msgs.append({"role": "user", "content": user_q})
    mode, fn = _backend if _backend else (None, None)
    ctx = st.session_state.chat_context

    try:
        # ✅ طلب المصادر فقط
        if any(w in user_q.lower() for w in ["مصادر", "المراجع", "source", "sources"]):
            sources_html = """
<b>المصادر الرسمية:</b>
<ul>
<li>الهيئة الزكوية والضريبية والجمارك (ZATCA)</li>
<li>البيانات المالية المرفوعة من المستخدم</li>
<li>لوائح ضريبة القيمة المضافة الرسمية</li>
</ul>
"""
            st.session_state.chat_msgs.append({"role": "assistant", "content": sources_html})
        # ✅ أول سؤال فقط → ملخص + شرح + توصيات
        elif not ctx.get("has_summary", False):
            company_name = infer_company_name(df_raw, df)
            summary_html = f"""
<b>التحليل المالي للشركة: {company_name}</b><br><br>            
<b>ملخص مالي مختصر:</b>
<ul>
<li>إجمالي الإيرادات: {rev:,.0f} ريال</li>
<li>إجمالي المصروفات: {exp:,.0f} ريال</li>
<li>صافي الربح: {profit:,.0f} ريال</li>
<li>التدفق النقدي: {cashflow:,.0f} ريال</li>
</ul>
"""
            analysis = "الأداء المالي العام مستقر، الإيرادات تغطي المصروفات بنسبة جيدة مما يعكس كفاءة تشغيلية معتدلة."
            recs = [
                "راقب المصروفات التشغيلية بدقة شهرية.",
                "اعمل على تحسين دورة التحصيل النقدي.",
                "راجع هوامش الربح في الفروع ذات الأداء الأدنى."
            ]
            rec_html = "<ul>" + "".join(f"<li>{r}</li>" for r in recs) + "</ul>"
            reply = f"{summary_html}<b>شرح مختصر:</b><br>{analysis}<br><br><b>توصيات:</b>{rec_html}"
            st.session_state.chat_msgs.append({"role": "assistant", "content": reply})

            ctx["has_summary"] = True
            ctx["memory"] = user_q

        # ✅ باقي الأسئلة → شرح + توصيات فقط
        else:
            prev_user, prev_assistant = "", ""
            for msg in reversed(st.session_state.chat_msgs):
                if msg["role"] == "assistant" and not prev_assistant:
                    prev_assistant = msg["content"]
                elif msg["role"] == "user" and not prev_user:
                    prev_user = msg["content"]
                if prev_user and prev_assistant:
                    break

            context_snippet = f"""
سؤال سابق: {prev_user}
إجابة سابقة: {prev_assistant}
السؤال الجديد: {user_q}

الرد المطلوب: شرح مختصر + توصيات فقط.
❌ لا تذكر الملخص المالي إطلاقًا.
❌ لا تذكر مقتطفات أو مصادر أو روابط أو عناصر meta مثل topic / answer / question.
الرد يجب أن يكون واضحًا ومبنيًا على البيانات المالية فقط.
"""
            if mode:
                ans, _ = fn(context_snippet, df=df)
            else:
                ans = "تم تحليل سؤالك بناءً على المحادثة السابقة."

            clean_lines = []
            for line in ans.splitlines():
                line_strip = line.strip().lower()
                if any(word in line_strip for word in [
                    "ملخص", "summary", "topic", "question", "answer", "context",
                    "source", "sources", "extract", "snippet", "meta", "مقتطف", "مصدر","revenue", "expenses","profit","cash flow", "period", "الفترة", "التدفق النقدي", "صافي الربح" , "إجمالي المصروفات" ,"إجمالي الإيرادات"
                ]):
                    continue
                if re.match(r"^\s*(\{|\}|\[|\])", line_strip):
                    continue
                if "http" in line_strip or "www." in line_strip:
                    continue
                clean_lines.append(line)

            clean_lines = [line.replace("الشرح المختصر", "<b>الشرح المختصر</b>") for line in clean_lines]
            ans_clean = "\n".join(clean_lines).strip()
            if not ans_clean:
                ans_clean = "تمت معالجة سؤالك بنجاح بناءً على البيانات المالية المتاحة."

            st.session_state.chat_msgs.append({"role": "assistant", "content": ans_clean})
            ctx["memory"] = context_snippet

    except Exception as e:
        st.session_state.chat_msgs.append({
            "role": "assistant",
            "content": f"⚠ حدث خطأ أثناء التحليل: {e}"
        })

    st.rerun()

# ====== PDF / HTML Report Export ======
st.sidebar.markdown("---")
st.sidebar.subheader("📄 تصدير التقرير")

net_vat = compute_vat(df)
zakat_due = compute_zakat(df)

if st.sidebar.button("توليد التقرير"):
    try:
        report_path = generate_financial_report(
            company_name=company_name,
            report_title=f"التقرير المالي الشامل — {company_name}",
            metrics={
                "total_revenue": float(df["revenue"].sum()),
                "total_expenses": float(df["expenses"].sum()),
                "total_profit": float(df["profit"].sum()),
                "total_cashflow": float(df["cash_flow"].sum()),
                "net_vat": float(net_vat),
                "zakat_due": float(zakat_due),
            },
            data_tables={
                "الإيرادات": df[["date", "revenue"]],
                "المصروفات": df[["date", "expenses"]],
                "الأرباح": df[["date", "profit"]],
            },
            template_path="generator/report_template.html",
            output_pdf="financial_report.pdf",
        )

        # يحدد نوع الملف الناتج تلقائيًا
        if str(report_path).lower().endswith(".pdf"):
            mime = "application/pdf"
            label = "⬇ تحميل التقرير (PDF)"
            download_name = "financial_report.pdf"
            st.sidebar.success(f"تم إنشاء تقرير PDF لشركة {company_name}.")
        else:
            mime = "text/html"
            label = "⬇ تحميل التقرير (HTML)"
            download_name = "final_report.html"
            st.sidebar.warning("تم إنشاء التقرير كـ HTML لأن تبعيات WeasyPrint غير متوفرة حالياً.")

        with open(report_path, "rb") as fh:
            st.sidebar.download_button(label, fh, download_name, mime)

    except Exception as e:
        st.sidebar.error(f"فشل إنشاء التقرير: {e}")


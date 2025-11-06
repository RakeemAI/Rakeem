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

import os, sys
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))  # يشير لجذر المشروع
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from llm.run import answer_question
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

# --- Chat session memory (يُخزّن داخل جلسة المستخدم) ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []   # [(role, text)]
if "user_name" not in st.session_state:
    st.session_state.user_name = None

def add_to_history(role: str, text: str):
    st.session_state.chat_history.append((role, text))

def detect_and_store_name(text: str):
    m = re.search(r"(?:أنا|اسمي)\s+([^\s,.!؟]+)", text)
    if not m:
        m = re.search(r"(?:my name is|I'm|I am)\s+([A-Za-z\u0600-\u06FF]+)", text, re.I)
    if m:
        st.session_state.user_name = m.group(1)

def history_as_text() -> str:
    """تجميع آخر الرسائل لتغذية الـLLM"""
    lines = []
    if st.session_state.user_name:
        lines.append(f"معلومة: اسم المستخدم هو {st.session_state.user_name}.")
    for role, text in st.session_state.chat_history[-12:]:
        prefix = "المستخدم" if role == "user" else "المساعد"
        lines.append(f"{prefix}: {text}")
    return "\n".join(lines)
# ----------------------------------------------------------

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



# ====== Chat Section ======
st.markdown('<div class="sec-title">المحادثة الذكية</div>', unsafe_allow_html=True)


# state
if "chat_msgs" not in st.session_state:
    st.session_state.chat_msgs = [
        {"role": "assistant", "content": "مرحبًا! ارفع ملفك المالي ثم اسألني عن الأرباح أو المصروفات أو الزكاة أو الالتزامات."}
    ]

# عرض الرسائل
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

# إدخال المستخدم (Chat Input)
st.subheader("💬 المساعد الذكي (Chat)")

user_msg = st.chat_input("اكتب سؤالك هنا…")

if user_msg:
    add_to_history("user", user_msg)
    detect_and_store_name(user_msg)

    # لو كنت تحفظ هذه المقاطع سابقًا بعد رفع الملف/البناء، خذها من الـsession_state
    company_snippet   = st.session_state.get("company_snippet", "")     # نبذة الشركة
    financial_snippet = st.session_state.get("financial_snippet", "")   # ملخص مالي
    zatca_snippet     = st.session_state.get("zatca_snippet", "")       # نص زكات/ضريبة من RAG أو ثابت

    try:
        result = answer_question(
            user_msg,
            company_info=company_snippet,
            financial_data=financial_snippet,
            zatca_text=zatca_snippet,
            # retriever=st.session_state.get("retriever"),  # إذا كنت باني الـretriever في step2
            top_k=RAG_TOP_K,
            model=MODEL_NAME,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        answer  = result.get("answer", "")
        sources = result.get("sources", [])
    except Exception as e:
        answer, sources = (f"⚠️ حدث خطأ أثناء الإجابة: {e}", [])

    # ضف المصادر (لاحظ أن الشكل الآن list[dict] وليس tuples)
    if sources:
        src_lines = []
        for s in sources:
            title = s.get("title", "مصدر")
            url   = s.get("url", "")
            if url:
                src_lines.append(f"- [{title}]({url})")
            else:
                src_lines.append(f"- {title}")
        answer += "\n\n**المصادر:**\n" + "\n".join(src_lines)

    add_to_history("assistant", answer)

# عرض الرسائل السابقة
for role, text in st.session_state.chat_history:
    with st.chat_message("user" if role == "user" else "assistant"):
        st.markdown(text)



# ====== PDF / HTML Report Export ======
st.sidebar.markdown("---")
st.sidebar.subheader("📄 تصدير التقرير")
net_vat = compute_vat(df)
zakat_due = compute_zakat(df)

if st.sidebar.button("توليد التقرير"):
    try:
        # نبني توصيات ديناميكية بناءً على الأرقام الحالية
        dyn_recs = []

        profit_margin = 0
        if rev > 0:
            profit_margin = profit / rev  # نسبة الربح إلى الإيراد

        # 1) لو المصروفات عالية
        if exp > rev * 0.7:
            dyn_recs.append("خفض المصروفات التشغيلية التي زادت عن 70٪ من الإيرادات خلال الفترة.")
        else:
            dyn_recs.append("استمر في ضبط المصروفات التشغيلية عند مستوياتها الحالية.")

        # 2) لو الربح ضعيف
        if profit_margin < 0.2:
            dyn_recs.append("ارفع هوامش الربح بمراجعة التسعير أو تحسين مزيج المنتجات.")
        else:
            dyn_recs.append("حافظ على مستوى هوامش الربح الحالي مع مراقبة أي تراجع مفاجئ.")

        # 3) لو التدفق النقدي ضعيف
        if cashflow < 0:
            dyn_recs.append("حسّن دورة التحصيل النقدي وتقصير آجال المدينين لتحسين التدفق النقدي.")
        else:
            dyn_recs.append("استثمر جزءًا من التدفق النقدي الإيجابي في أنشطة توليد الإيرادات.")

        # 4) توصية عامة من الزكاة/الضريبة
        dyn_recs.append("التأكد من مطابقة الإقرارات الضريبية والزكوية للبيانات المالية المعتمدة.")

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
            # ← هنا صارت توصيات ديناميكية
            recommendations=dyn_recs,
            data_tables={
                "الإيرادات": df[["date", "revenue"]],
                "المصروفات": df[["date", "expenses"]],
                "الأرباح": df[["date", "profit"]],
            },
            template_path="generator/report_template.html",
            output_pdf="financial_report.pdf",
        )

        if str(report_path).lower().endswith(".pdf"):
            mime = "application/pdf"
            label = "⬇ تحميل التقرير (PDF)"
            name = "financial_report.pdf"
            st.sidebar.success(f"تم إنشاء تقرير PDF لشركة {company_name}.")
        else:
            mime = "text/html"
            label = "⬇ تحميل التقرير (HTML)"
            name = "final_report.html"
            st.sidebar.warning("تم إنشاء التقرير كـ HTML لأن تبعيات PDF غير متوفرة على الاستضافة.")

        with open(report_path, "rb") as fh:
            st.sidebar.download_button(label, fh, name, mime)

    except Exception as e:
        st.sidebar.error(f"فشل إنشاء التقرير: {e}")

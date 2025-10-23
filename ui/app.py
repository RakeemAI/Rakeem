# ui/app.py
import os, sys, json
from typing import Optional

import pandas as pd
import plotly.express as px
import streamlit as st

# --- make sure we can import engine regardless of how Streamlit is launched
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))  # ui/ -> repo root
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# --- import engine pieces (NO wrapper) ---
from engine.io import load_excel, load_csv
from engine.validate import validate_columns
from engine.compute_core import compute_core
from engine.taxes import compute_vat, compute_zakat
from engine.export import to_json

# ---------- Streamlit page config ----------
st.set_page_config(page_title="Rakeem", layout="wide")

st.title("ركيم — Rakeem (SME Financial Assistant) 🇸🇦")
st.markdown(
    """
    📂 *.ارفع ملفك المالي لعرض مؤشرات الأداء والضرائب والرسوم البيانية الخاصة بشركتك*

    📂 *Upload your financial file to view key performance metrics, taxes, and visual charts for your company.*

    ---
    💡 Note: We only accepts files in Excel (.xlsx) or CSV (.csv) format only.
    """
)

# ---------- Sidebar: file upload only (no simulate) ----------
st.sidebar.header("Upload")
uploaded_file = st.sidebar.file_uploader(
    "Upload Excel (.xlsx/.xls) or CSV", type=["xlsx", "xls", "csv"]
)

if uploaded_file is None:
    st.info(".للبدء من فضلك ارفع الملف من الشريط الجانبي")
    st.info("To start please upload your file from sidebar.")
    st.stop()

# ---------- Read the file using engine loaders ----------
try:
    ext = uploaded_file.name.split(".")[-1].lower()
    if ext in ("xlsx", "xls"):
        df_raw = load_excel(uploaded_file, sheet=0)   # our loader accepts file-like
    elif ext == "csv":
        df_raw = load_csv(uploaded_file)
    else:
        st.error("صيغة الملف غير مدعومة.")
        st.stop()
except Exception as e:
    st.error(f"خطأ أثناء قراءة الملف: {e}")
    st.stop()

# ---------- Validate required columns ----------
try:
    validate_columns(df_raw)
except Exception as e:
    st.error(f"خطأ في التحقق من الأعمدة: {e}")
    st.stop()

# ---------- Compute core metrics ----------
try:
    df = compute_core(df_raw)   # returns pandas DataFrame with profit, margin, cash_flow...
except Exception as e:
    st.error(f"خطأ أثناء الحسابات الأساسية: {e}")
    st.stop()

# ---------- Compute taxes (NO wrapper) ----------
try:
    net_vat = float(compute_vat(df))
except Exception as e:
    st.warning(f"تعذر حساب VAT: {e}")
    net_vat = 0.0

try:
    zakat_due = float(compute_zakat(df))
except Exception as e:
    st.warning(f"تعذر حساب الزكاة: {e}")
    zakat_due = 0.0

# ---------- Build JSON summary ----------
try:
    engine_json = to_json(df, include_rows=False)
    engine_output = json.loads(engine_json)
except Exception as e:
    st.warning(f"تعذر توليد JSON: {e}")
    engine_output = None

# ---------- KPIs ----------
k1, k2, k3, k4 = st.columns(4)
total_revenue = float(df.get("revenue", pd.Series([0])).fillna(0).sum())
total_expenses = float(df.get("expenses", pd.Series([0])).fillna(0).sum())
total_profit   = float(df.get("profit", pd.Series([0])).fillna(0).sum())
total_cashflow = float(df.get("cash_flow", pd.Series([0])).fillna(0).sum())

k1.metric("Total Revenue", f"{total_revenue:,.0f} SAR")
k2.metric("Total Expenses", f"{total_expenses:,.0f} SAR")
k3.metric("Total Profit", f"{total_profit:,.0f} SAR")
k4.metric("Total Cash Flow", f"{total_cashflow:,.0f} SAR")

t1, t2 = st.columns(2)
t1.metric("Net VAT (Output - Input)", f"{net_vat:,.0f} SAR")
t2.metric("Zakat Due", f"{zakat_due:,.0f} SAR")

# ---------- Charts ----------
st.markdown("### Monthly trends")
c1, c2, c3 = st.columns(3)
c1.plotly_chart(px.line(df, x="date", y="revenue", title="Revenue"), use_container_width=True)
c2.plotly_chart(px.line(df, x="date", y="expenses", title="Expenses"), use_container_width=True)
c3.plotly_chart(px.line(df, x="date", y="profit", title="Profit"), use_container_width=True)

# ---------- Simple recommendations ----------
st.markdown("### توصيات تلقائية")
recs = []
avg_margin = float(df.get("profit_margin", pd.Series([0])).fillna(0).mean())
if avg_margin < 0.10:
    recs.append("هامش الربح منخفض (<10%). راجع التسعير أو المصروفات.")
if total_cashflow < 0:
    recs.append("التدفق النقدي سالب. فكّر في تمويل قصير الأجل أو تأجيل مصروفات غير ضرورية.")
if net_vat > 0:
    recs.append("هناك صافي VAT مستحق — احرص على تقديم الإقرار في الوقت المحدد.")
if zakat_due > 0:
    recs.append("يبدو أنّ الزكاة مستحقة. تحقق من وعاء الزكاة واستعد للسداد.")

if recs:
    for r in recs:
        st.info(r)
else:
    st.success("لا توجد تنبيهات فورية وفقًا للمقاييس الحالية.")

# ---------- Details & downloads ----------
with st.expander("الجدول التفصيلي + المخرجات الخام"):
    st.dataframe(df)
    if engine_output:
        st.json(engine_output, expanded=False)

left, right = st.columns(2)
if engine_output:
    left.download_button(
        "Download JSON (Engine Output)",
        data=json.dumps(engine_output, indent=2, ensure_ascii=False),
        file_name="rakeem_output.json",
        mime="application/json",
    )

csv_bytes = df.to_csv(index=False).encode("utf-8")
right.download_button(
    "Download CSV (computed)",
    data=csv_bytes,
    file_name="computed.csv",
    mime="text/csv",
)

st.markdown("---")
st.caption("Prototype — powered by Rakeem Financial Engine.")


# ===================== Chat Interface (Sprint 5: Person 3 & 4) =====================
from typing import Optional
import streamlit as st

# جرّب السلسلة من سبرنت 4 أولاً
_backend = None
try:
    from llm.run import chat_answer as _chain_chat_answer  # ترجع (reply_text, sources)
    _backend = ("chain", _chain_chat_answer)
except Exception:
    try:
        from llm.simple_backend import answer as _simple_answer
        _backend = ("simple", _simple_answer)
    except Exception as _e:
        _backend = None
        st.warning("⚠️ لا يوجد باك-إند متاح للشات (لا chain ولا simple).", icon="⚠️")

st.markdown("---")
st.header("💬 المحادثة الذكية")

def _resolve_financial_df() -> Optional["object"]:
    # التقط DF من أكثر الأماكن شيوعًا
    try:
        if "df" in globals() and "DataFrame" in str(type(globals()["df"])): return globals()["df"]
        if "financial_df" in globals() and "DataFrame" in str(type(globals()["financial_df"])): return globals()["financial_df"]
        for key in ("df", "financial_df", "computed_df", "results_df"):
            if key in st.session_state and "DataFrame" in str(type(st.session_state[key])):
                return st.session_state[key]
    except Exception:
        pass
    return None

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role": "assistant", "content": "مرحبًا! ارفعي ملفك المالي ثم اسألي عن الربحية، الزكاة، الضريبة، أو أي استفسار."}
    ]

# عرض سجل المحادثة
for m in st.session_state.chat_messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

user_q = st.chat_input("اكتبي سؤالك هنا…")
if user_q:
    st.session_state.chat_messages.append({"role": "user", "content": user_q})
    with st.chat_message("user"):
        st.markdown(user_q)

    df_ctx = _resolve_financial_df()
    try:
        if not _backend:
            raise RuntimeError("لا يوجد باك-إند للشات. تأكدي من llm.run.chat_answer أو llm/simple_backend.py.")
        mode, fn = _backend
        reply_text, sources = fn(user_q, df=df_ctx) if mode == "simple" else fn(user_q, df=df_ctx)

        st.session_state.chat_messages.append({"role": "assistant", "content": reply_text})
        with st.chat_message("assistant"):
            st.markdown(reply_text)
            if sources:
                with st.expander("المصادر"):
                    for s in sources:
                        st.markdown(f"- {s}")

    except Exception as e:
        st.error(f"تعذّر توليد الرد: {e}")
        st.info("تحققي من تشغيل المحرك المالي ووجود ملف data/zatca_docs.jsonl عند استخدام الوضع البسيط.", icon="ℹ️")
# ===============================================================================

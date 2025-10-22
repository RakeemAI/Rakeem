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
st.markdown("ارفع ملف المالي الخاص بك لتحصل على المؤشرات الرئيسة للأداء وحساب الضريبة المضافة والزكاة مع رسوم بيانة بسيطة")

# ---------- Sidebar: file upload only (no simulate) ----------
st.sidebar.header("Upload")
uploaded_file = st.sidebar.file_uploader(
    "Upload Excel (.xlsx/.xls) or CSV", type=["xlsx", "xls", "csv"]
)

if uploaded_file is None:
    st.info("للبدء ارفع ملفك من الشريط الجانبي من فضلك. ")
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

# ui/pages/📅_Calendar_Page.py

# --- تصحيح المسار (مهم) ---
import os, sys
PAGES_DIR = os.path.dirname(__file__)
UI_DIR = os.path.dirname(PAGES_DIR)
PROJECT_ROOT = os.path.dirname(UI_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# ---------------------------

import streamlit as st
from engine.reminder_core import CompanyProfile
from ui.calendar_page import render_calendar_page

st.set_page_config(page_title="Rakeem — التقويم الذكي", layout="wide")

with st.sidebar.expander("إعدادات الشركة", expanded=True):
    fye_month = st.number_input("شهر نهاية السنة المالية", 1, 12, 12, 1)
    fye_day   = st.number_input("يوم نهاية السنة المالية", 1, 31, 31, 1)
    vat_freq  = st.selectbox("تكرار ضريبة القيمة المضافة", ["quarterly", "monthly"],index=0, format_func=lambda x: "ربع سنوي" if x=="quarterly" else "شهري")
    cr_date   = st.date_input("تاريخ إصدار السجل التجاري (اختياري)", value=None)

profile = CompanyProfile(
    fiscal_year_end_month=int(fye_month),
    fiscal_year_end_day=int(fye_day),
    vat_frequency=vat_freq,
    cr_issue_date=cr_date if cr_date else None,
)

render_calendar_page(df_raw=None, profile=profile, data_path="data/saudi_deadlines_ar.json")

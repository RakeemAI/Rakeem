import os
import pandas as pd
from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from fpdf import FPDF   # ← استخدم FPDF بدل WeasyPrint

def _sar(v):
    try:
        return f"{float(v):,.0f} ريال"
    except Exception:
        return "—"

def _df_to_text(name: str, df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""
    lines = [f"=== {name} ==="]
    for _, r in df.iterrows():
        line = " | ".join(f"{k}: {v}" for k, v in r.items())
        lines.append(line)
    return "\n".join(lines)

def generate_financial_report(
    *,
    company_name: str = "",
    report_title: str = "التقرير المالي الشامل",
    metrics: Dict[str, float],
    recommendations: List[str],
    data_tables: Optional[Dict[str, pd.DataFrame]] = None,
    template_path: str = "",
    output_pdf: str = "financial_report.pdf",
):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, company_name or "شركة غير محددة", ln=True, align="C")
    pdf.cell(0, 10, report_title, ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"التاريخ: {pd.Timestamp.now().strftime('%Y-%m-%d')}", ln=True)
    pdf.ln(8)

    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "الملخص المالي", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.multi_cell(0, 8,
        f"إجمالي الإيرادات: {_sar(metrics.get('total_revenue', 0))}\n"
        f"إجمالي المصروفات: {_sar(metrics.get('total_expenses', 0))}\n"
        f"صافي الربح: {_sar(metrics.get('total_profit', 0))}\n"
        f"التدفق النقدي: {_sar(metrics.get('total_cashflow', 0))}\n"
        f"صافي ضريبة القيمة المضافة: {_sar(metrics.get('net_vat', 0))}\n"
        f"الزكاة المستحقة: {_sar(metrics.get('zakat_due', 0))}"
    )
    pdf.ln(8)

    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "التوصيات:", ln=True)
    pdf.set_font("Arial", '', 12)
    for r in (recommendations or []):
        pdf.multi_cell(0, 8, f"• {r}")
    pdf.ln(10)

    if data_tables:
        for name, df in data_tables.items():
            pdf.set_font("Arial", 'B', 13)
            pdf.cell(0, 10, f"{name}", ln=True)
            pdf.set_font("Arial", '', 10)
            pdf.multi_cell(0, 6, _df_to_text(name, df))
            pdf.ln(6)

    pdf.output(output_pdf)
    return output_pdf

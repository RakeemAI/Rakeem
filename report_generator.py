# generator/report_generator.py

import os
from typing import Dict, List, Optional

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape


def _sar(v):
    try:
        return f"{float(v):,.0f} ريال"
    except Exception:
        return "—"


def _df_to_html(name: str, df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""
    rename_map = {
        "date": "التاريخ",
        "revenue": "الإيرادات",
        "expenses": "المصروفات",
        "profit": "الربح",
        "cash_flow": "التدفق النقدي",
        "cashflow": "التدفق النقدي",
    }
    df = df.rename(columns={c: rename_map.get(c, c) for c in df.columns})
    title_html = (
        "<h2 style='color:#002147;font-size:22px;margin:15px 0 10px;"
        "padding-bottom:8px;border-bottom:2px solid #ffcc66;font-weight:700;'>"
        f"{name}</h2>"
    )
    table_html = df.to_html(classes="table", index=False, border=0)
    return title_html + table_html


def _try_export_pdf_with_weasyprint(html: str, output_pdf: str) -> bool:
    try:
        from weasyprint import HTML  # type: ignore

        HTML(string=html, base_url=os.getcwd()).write_pdf(output_pdf)
        return True
    except Exception:
        return False


def _try_export_pdf_with_pdfkit(html: str, output_pdf: str) -> bool:
    # يشتغل بس لو wkhtmltopdf متوفر في السيستم (غالبًا مو متوفر في streamlit cloud)
    try:
        import pdfkit  # type: ignore

        pdfkit.from_string(html, output_pdf)
        return True
    except Exception:
        return False


def generate_financial_report(
    *,
    company_name: str = "",
    report_title: str = "التقرير المالي الشامل",
    metrics: Dict[str, float],
    recommendations: List[str],
    data_tables: Optional[Dict[str, pd.DataFrame]] = None,
    template_path: str = "generator/report_template.html",
    output_pdf: str = "financial_report.pdf",
):
    env = Environment(
        loader=FileSystemLoader(os.path.dirname(template_path) or "."),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template(os.path.basename(template_path))

    tables_html = ""
    if data_tables:
        for name, df in data_tables.items():
            tables_html += _df_to_html(name, df)

    html = tpl.render(
        base_url=os.getcwd(),
        company_name=company_name or "",
        report_title=report_title,
        report_date=pd.Timestamp.now().strftime("%Y-%m-%d"),
        introduction=(
            "يسرّنا تقديم هذا التقرير المالي الشامل الذي يوضح الأداء المالي الحالي "
            "للشركة والتنبؤات المستقبلية."
        ),
        highlight=(
            "يهدف هذا التقرير إلى توفير رؤية شاملة عن الأداء المالي ومساعدة متخذي "
            "القرار في وضع الخطط المستقبلية."
        ),
        total_revenue=_sar(metrics.get("total_revenue", 0)),
        total_expenses=_sar(metrics.get("total_expenses", 0)),
        total_profit=_sar(metrics.get("total_profit", 0)),
        total_cashflow=_sar(metrics.get("total_cashflow", 0)),
        net_vat=_sar(metrics.get("net_vat", 0)),
        zakat_due=_sar(metrics.get("zakat_due", 0)),
        tables=tables_html,
        recommendations=recommendations or [],
    )

    # احفظ الـ HTML دايمًا
    with open("final_report.html", "w", encoding="utf-8") as f:
        f.write(html)

    # جرّب WeasyPrint أول
    if _try_export_pdf_with_weasyprint(html, output_pdf):
        return output_pdf

    # لو ما فيه WeasyPrint، جرّب pdfkit
    if _try_export_pdf_with_pdfkit(html, output_pdf):
        return output_pdf

    # لو الاثنين فشلوا، رجّع بس html
    return "final_report.html"

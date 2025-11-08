import os
import importlib.util
import pandas as pd
from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

def _sar(v):
    """صيغة ريال سعودية منسقة"""
    try:
        return f"{float(v):,.0f} ريال"
    except Exception:
        return "—"

def _df_to_html(name: str, df: pd.DataFrame) -> str:
    """تحويل جدول Pandas إلى HTML منسق"""
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
    table_html = df.to_html(classes='table', index=False, border=0)
    return title_html + table_html

def _module_available(name: str) -> bool:
    """يتحقق من توفر مكتبة معينة"""
    return importlib.util.find_spec(name) is not None

def generate_financial_report(
    *,
    company_name: str = "",
    report_title: str = "التقرير المالي الشامل",
    metrics: Dict[str, float],
    recommendations: List[str],
    data_tables: Optional[Dict[str, pd.DataFrame]] = None,
    template_path: str = "generator/report_template.html",
    output_pdf: str = "financial_report.pdf",
) -> str:
    """ينشئ تقرير مالي (دائمًا PDF سواء محلي أو في Streamlit Cloud)"""

    env = Environment(
        loader=FileSystemLoader(os.path.dirname(template_path) or "."),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template(os.path.basename(template_path))

    # بناء HTML
    tables_html = ""
    if data_tables:
        for name, df in data_tables.items():
            tables_html += _df_to_html(name, df)

    html = tpl.render(
        base_url=os.getcwd(),
        company_name=company_name or "شركة غير محددة",
        report_title=report_title,
        report_date=pd.Timestamp.now().strftime("%Y-%m-%d"),
        introduction="يسرّنا تقديم هذا التقرير المالي الشامل الذي يوضح الأداء المالي الحالي للشركة والتنبؤات المستقبلية.",
        highlight="يهدف هذا التقرير إلى توفير رؤية شاملة عن الأداء المالي ومساعدة متخذي القرار في وضع الخطط المستقبلية.",
        total_revenue=_sar(metrics.get("total_revenue", 0)),
        total_expenses=_sar(metrics.get("total_expenses", 0)),
        total_profit=_sar(metrics.get("total_profit", 0)),
        total_cashflow=_sar(metrics.get("total_cashflow", 0)),
        net_vat=_sar(metrics.get("net_vat", 0)),
        zakat_due=_sar(metrics.get("zakat_due", 0)),
        tables=tables_html,
        recommendations=recommendations or [],
    )

    html_path = os.path.abspath("final_report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    # --- أولوية 1: WeasyPrint ---
    if _module_available("weasyprint"):
        try:
            from weasyprint import HTML
            HTML(string=html, base_url=os.getcwd()).write_pdf(output_pdf)
            print("✅ PDF تم توليده باستخدام WeasyPrint.")
            return output_pdf
        except Exception as e:
            print(f"[تحذير] WeasyPrint فشل: {e}")

    # --- أولوية 2: xhtml2pdf (يعمل في Streamlit Cloud) ---
    if _module_available("xhtml2pdf"):
        try:
            from xhtml2pdf import pisa
            with open(output_pdf, "wb") as pdf_file:
                pisa_status = pisa.CreatePDF(html, dest=pdf_file, encoding="utf-8")
            if not pisa_status.err:
                print("✅ PDF تم توليده باستخدام xhtml2pdf (متوافق مع Streamlit Cloud).")
                return output_pdf
            else:
                print("[تحذير] xhtml2pdf فشل أثناء التحويل.")
        except Exception as e:
            print(f"[تحذير] فشل xhtml2pdf: {e}")

    # --- Fallback ---
    print("⚠️ لم ينجح أي محرك PDF — تم حفظ HTML فقط.")
    return html_path

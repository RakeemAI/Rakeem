# generator/report_generator.py
import os
import pandas as pd
from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

# === Utilities ===
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

# === Core Generator ===
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
    """ينشئ تقرير مالي PDF أو HTML حسب توفر المكتبات"""

    # ⚠️ استيراد كسول لـ WeasyPrint داخل الدالة وبالتقاط كل الأخطاء
    try:
        from weasyprint import HTML  # قد يرمي OSError إذا Pango/Cairo غير متوفرة
        _has_weasy = True
    except Exception as e:
        print(f"[تنبيه] تعذّر تحميل WeasyPrint: {e}")
        HTML = None
        _has_weasy = False

    # إعداد بيئة القالب
    env = Environment(
        loader=FileSystemLoader(os.path.dirname(template_path) or "."),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template(os.path.basename(template_path))

    # تحويل الجداول إلى HTML
    tables_html = ""
    if data_tables:
        for name, df in data_tables.items():
            tables_html += _df_to_html(name, df)

    # توليد HTML النهائي
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

    # نحفظ HTML دائمًا
    html_path = "final_report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    # نحاول PDF فقط لو WeasyPrint تعمل
    if _has_weasy and HTML is not None:
        try:
            HTML(string=html, base_url=os.getcwd()).write_pdf(output_pdf)
            return output_pdf
        except Exception as e:
            print(f"[تحذير] فشل توليد PDF عبر WeasyPrint: {e}")
            return html_path
    else:
        print("[تنبيه] WeasyPrint غير متاحة، تم حفظ التقرير كـ HTML.")
        return html_path

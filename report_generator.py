import pandas as pd
from jinja2 import Template
from weasyprint import HTML
import arabic_reshaper
from bidi.algorithm import get_display

def arabic(text):
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

def generate_financial_report(data_dict, recommendations, output_pdf='financial_report.pdf'):
    with open('report_template.html', encoding='utf-8') as f:
        template = Template(f.read())

    tables_html = ''
    for name, df in data_dict.items():
        tables_html += f'<h3>{arabic(name)}</h3>'
        tables_html += df.to_html(classes='table', index=False, border=0)

    html_content = template.render(
        company_name=arabic("شركة ركيم المالية"),
        report_title=arabic("التقرير المالي الشامل"),
        report_date=pd.Timestamp.now().strftime('%Y-%m-%d'),
        introduction=arabic("يسرنا تقديم هذا التقرير المالي الشامل الذي يوضح الأداء المالي الحالي للشركة والتنبؤات المستقبلية."),
        highlight=arabic("يهدف هذا التقرير إلى توفير رؤية شاملة عن الأداء المالي ومساعدة متخذي القرار في وضع الخطط المستقبلية."),
        tables=tables_html,
        recommendations=[arabic(r) for r in recommendations]
    )

    with open('final_report.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

    HTML(string=html_content).write_pdf(output_pdf)
    print(f'✅ تم إنشاء التقرير وحفظه باسم: {output_pdf}')

if __name__ == "__main__":
    df_rev = pd.DataFrame({'الشهر':['يناير','فبراير','مارس'],'الإيرادات':[10000,12000,15000]})
    df_exp = pd.DataFrame({'الشهر':['يناير','فبراير','مارس'],'المصروفات':[8000,9500,11000]})
    data_dict = {'الإيرادات': df_rev, 'المصروفات': df_exp}
    recommendations = [
        "حافظ على نسبة الربح الحالية",
        "راقب المصروفات المتزايدة في شهر مارس"
    ]
    generate_financial_report(data_dict, recommendations)

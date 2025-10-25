# llm/step3_context_formatter.py
import pandas as pd
import json
from typing import List, Any

class ContextFormatter:
    """Step 3: تنسيق ودمج السياقات المختلفة (متوافق مع أعمدة engine)"""

    def __init__(self):
        self.company_info = ""
        self.financial_data = ""

    def _canon(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
        return out

    def format_financial_context(self, company_data: pd.DataFrame) -> str:
        try:
            if company_data is None or company_data.empty:
                return "⚠️ لا توجد بيانات مالية متاحة"

            df = self._canon(company_data)

            total_revenue = float(pd.to_numeric(df.get("revenue"), errors="coerce").fillna(0).sum())
            total_expenses = float(pd.to_numeric(df.get("expenses"), errors="coerce").fillna(0).sum())
            total_profit   = float(pd.to_numeric(df.get("profit"), errors="coerce").fillna(0).sum())
            total_vat      = float(pd.to_numeric(df.get("vat_collected"), errors="coerce").fillna(0).sum()
                                   - pd.to_numeric(df.get("vat_paid"), errors="coerce").fillna(0).sum())
            total_zakat    = float(pd.to_numeric(df.get("zakat_due"), errors="coerce").fillna(0).sum()
                                   if "zakat_due" in df.columns else 0.0)

            profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0.0

            # آخر شهر/تاريخ
            period_line = ""
            if "date" in df.columns:
                d = pd.to_datetime(df["date"], errors="coerce")
                if d.notna().any():
                    period_line = f"\n• الفترة: {d.min().date()} → {d.max().date()}"

            financial_context = f"""
📊 **البيانات المالية الشاملة:**
• الإيرادات الإجمالية: {total_revenue:,.2f} ريال
• المصروفات الإجمالية: {total_expenses:,.2f} ريال
• صافي الربح: {total_profit:,.2f} ريال
• هامش الربح: {profit_margin:.2f}%
• صافي ضريبة القيمة المضافة: {total_vat:,.2f} ريال
• الزكاة المستحقة: {total_zakat:,.2f} ريال{period_line}
"""
            self.financial_data = financial_context
            return financial_context.strip()

        except Exception as e:
            return f"❌ خطأ في تنسيق البيانات المالية: {e}"

    def format_company_info(self, company_data: pd.DataFrame) -> str:
        try:
            if company_data is None or company_data.empty:
                return "⚠️ لا توجد معلومات عن الشركة"
            df = self._canon(company_data)
            entity = df.get("entity_name")
            company_name = str(entity.iloc[0]) if entity is not None and len(entity) else "غير معروف"

            # فترة مبنية على date إن وجدت
            period = ""
            if "date" in df.columns:
                d = pd.to_datetime(df["date"], errors="coerce")
                if d.notna().any():
                    period = f"من {d.min().date()} إلى {d.max().date()}"

            company_info = f"""
🏢 **معلومات الشركة:**
• اسم الشركة: {company_name}
• فترة البيانات: {period or "غير محددة"}
• عدد السجلات: {len(df)} سجل
"""
            self.company_info = company_info.strip()
            return self.company_info

        except Exception as e:
            return f"❌ خطأ في تنسيق معلومات الشركة: {e}"

    def format_zatca_context(self, retrieved_docs: List[Any]) -> str:
        try:
            if not retrieved_docs:
                return "🔍 لم يتم العثور على معلومات محددة من ZATCA لهذا السؤال."
            out = ["📚 **المعلومات التنظيمية من ZATCA:**"]
            for i, doc in enumerate(retrieved_docs[:3], 1):
                content = getattr(doc, "page_content", str(doc))
                source  = getattr(getattr(doc, "metadata", {}), "get", lambda *_: "مصدر غير معروف")("source")
                if len(content) > 900:
                    content = content[:900] + "..."
                out.append(f"\n{i}. {content}\n   📍 **المصدر:** {source}")
            return "\n".join(out)
        except Exception as e:
            return f"❌ خطأ في تنسيق معلومات ZATCA: {e}"

    def merge_all_contexts(self, company_data: pd.DataFrame, retrieved_docs: List[Any], question: str) -> dict:
        try:
            company_info = self.format_company_info(company_data)
            financial_data = self.format_financial_context(company_data)
            zatca_info = self.format_zatca_context(retrieved_docs)
            return {
                "company_info": company_info,
                "financial_data": financial_data,
                "zatca_info": zatca_info,
                "question": question
            }
        except Exception:
            return {
                "company_info": "",
                "financial_data": "",
                "zatca_info": "",
                "question": question
            }

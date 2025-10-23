import pandas as pd
import json
from typing import List, Any

class ContextFormatter:
    """Step 3: تنسيق ودمج السياقات المختلفة"""
    
    def __init__(self):
        self.company_info = ""
        self.financial_data = ""
        
    def format_financial_context(self, company_data: pd.DataFrame) -> str:
        """تنسيق البيانات المالية من المحرك المالي"""
        try:
            if company_data.empty:
                return "⚠️ لا توجد بيانات مالية متاحة"
            
            # استخراج البيانات الأساسية
            total_revenue = company_data['Revenue'].sum()
            total_expenses = company_data['Expenses'].sum() 
            total_profit = company_data['Profit'].sum()
            total_vat = company_data['Net_VAT_Payable'].sum()
            total_zakat = company_data['Zakat_Due'].sum()
            
            # حساب النسب
            profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
            
            # تنسيق السياق المالي
            financial_context = f"""
📊 **البيانات المالية الشاملة:**

• الإيرادات الإجمالية: {total_revenue:,.2f} ريال
• المصروفات الإجمالية: {total_expenses:,.2f} ريال
• صافي الربح: {total_profit:,.2f} ريال
• هامش الربح: {profit_margin:.2f}%

• ضريبة القيمة المضافة المستحقة: {total_vat:,.2f} ريال
• الزكاة المستحقة: {total_zakat:,.2f} ريال

• عدد الأشهر المحللة: {len(company_data)} شهر
• آخر شهر في البيانات: {company_data['Month'].iloc[-1]}
"""
            
            self.financial_data = financial_context
            return financial_context
            
        except Exception as e:
            return f"❌ خطأ في تنسيق البيانات المالية: {e}"
    
    def format_company_info(self, company_data: pd.DataFrame) -> str:
        """تنسيق معلومات الشركة"""
        try:
            if company_data.empty:
                return "⚠️ لا توجد معلومات عن الشركة"
            
            company_name = company_data['entity_name'].iloc[0] if 'entity_name' in company_data.columns else "غير معروف"
            
            company_info = f"""
🏢 **معلومات الشركة:**

• اسم الشركة: {company_name}
• فترة البيانات: من {company_data['Month'].iloc[0]} إلى {company_data['Month'].iloc[-1]}
• عدد السجلات: {len(company_data)} شهر

📈 **المؤشرات الرئيسية:**
- متوسط الإيرادات الشهرية: {company_data['Revenue'].mean():,.2f} ريال
- متوسط المصروفات الشهرية: {company_data['Expenses'].mean():,.2f} ريال
- متوسط الربح الشهري: {company_data['Profit'].mean():,.2f} ريال
"""
            
            self.company_info = company_info
            return company_info
            
        except Exception as e:
            return f"❌ خطأ في تنسيق معلومات الشركة: {e}"
    
    def format_zatca_context(self, retrieved_docs: List[Any]) -> str:
        """تنسيق المعلومات المسترجعة من ZATCA"""
        try:
            if not retrieved_docs:
                return "🔍 لم يتم العثور على معلومات محددة من ZATCA لهذا السؤال."
            
            zatca_context = "📚 **المعلومات التنظيمية من ZATCA:**\n"
            
            for i, doc in enumerate(retrieved_docs[:3], 1):  # أول 3 نتائج فقط
                # استخراج المحتوى من المستند
                content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
                source = doc.metadata.get('source', 'مصدر غير معروف') if hasattr(doc, 'metadata') else 'مصدر غير معروف'
                
                # تقصير المحتوى إذا كان طويلاً
                if len(content) > 200:
                    content = content[:200] + "..."
                
                zatca_context += f"\n{i}. {content}\n"
                zatca_context += f"   📍 **المصدر:** {source}\n"
            
            return zatca_context
            
        except Exception as e:
            return f"❌ خطأ في تنسيق معلومات ZATCA: {e}"
    
    def merge_all_contexts(self, company_data: pd.DataFrame, retrieved_docs: List[Any], question: str) -> dict:
        """دمج جميع السياقات في قاموس منظم"""
        try:
            # تنسيق جميع السياقات
            company_info = self.format_company_info(company_data)
            financial_data = self.format_financial_context(company_data) 
            zatca_info = self.format_zatca_context(retrieved_docs)
            
            contexts = {
                "company_info": company_info,
                "financial_data": financial_data,
                "zatca_info": zatca_info,
                "question": question
            }
            
            print("✅ تم دمج جميع السياقات بنجاح")
            return contexts
            
        except Exception as e:
            print(f"❌ خطأ في دمج السياقات: {e}")
            return {
                "company_info": "",
                "financial_data": "", 
                "zatca_info": "",
                "question": question
            }

# اختبار Step 3
if __name__ == "__main__":
    print("🧪 اختبار Step 3 - Context Formatter")
    print("=" * 40)
    
    formatter = ContextFormatter()
    
    # بيانات تجريبية للاختبار
    test_data = pd.DataFrame({
        'entity_name': ['شركة الاختبار'],
        'Month': ['2024-01', '2024-02'],
        'Revenue': [150000, 180000],
        'Expenses': [120000, 140000],
        'Profit': [30000, 40000],
        'Net_VAT_Payable': [2250, 2700],
        'Zakat_Due': [750, 1000]
    })
    
    print("1. اختبار تنسيق البيانات المالية...")
    financial_context = formatter.format_financial_context(test_data)
    print(f"   ✅ البيانات المالية: {len(financial_context)} حرف")
    
    print("2. اختبار تنسيق معلومات الشركة...")
    company_info = formatter.format_company_info(test_data)
    print(f"   ✅ معلومات الشركة: {len(company_info)} حرف")
    
    print("3. اختبار تنسيق معلومات ZATCA...")
    zatca_context = formatter.format_zatca_context([])  # قائمة فارغة للاختبار
    print(f"   ✅ معلومات ZATCA: {len(zatca_context)} حرف")
    
    print("4. اختبار دمج السياقات...")
    merged_contexts = formatter.merge_all_contexts(test_data, [], "سؤال تجريبي")
    print(f"   ✅ تم دمج {len(merged_contexts)} سياق")
    
    print("\n✅ Step 3 جاهز للعمل!")

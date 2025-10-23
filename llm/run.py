import os
import sys
import pandas as pd
from dotenv import load_dotenv

# تحميل .env في البداية
load_dotenv(override=True)

# استيراد الوحدات
from step1_prompt_engineer import ArabicPromptEngineer
from step2_chain_setup import LangChainSetup
from step3_context_formatter import ContextFormatter
from step4_response_parser import ResponseParser

class RakeemChatbot:
    """الواجهة الرئيسية للشات بوت"""
    
    def __init__(self, excel_file_path=None):
        print("🤖 جاري تهيئة شات بوت ركيم...")
        
        # 1. تهيئة Prompt Engineer
        self.prompt_engineer = ArabicPromptEngineer()
        print("✅ تم تحميل Prompt Engineer")
        
        # 2. تهيئة LangChain + RAG
        self.chain_setup = LangChainSetup()
        self.chain_setup.setup_llm()
        self.chain_setup.setup_memory()
        self.chain_setup.setup_retriever()
        print("✅ تم تحميل LangChain + RAG")
        
        # 3. تهيئة Context Formatter
        self.context_formatter = ContextFormatter()
        
        # 4. تحميل بيانات الشركة من Excel
        self.company_data = None
        if excel_file_path and os.path.exists(excel_file_path):
            try:
                self.company_data = pd.read_excel(excel_file_path)
                print(f"✅ تم تحميل بيانات الشركة: {len(self.company_data)} صف")
            except Exception as e:
                print(f"⚠️ فشل تحميل Excel: {e}")
        else:
            print("⚠️ لم يتم تحديد ملف Excel")
        
        # 5. تهيئة Response Parser
        self.response_parser = ResponseParser()
        print("✅ تم تحميل Response Parser")
        
        print(f"\n🎉 شات بوت ركيم جاهز! النموذج: {self.chain_setup.model_name}")
    
    def ask_question(self, question: str) -> dict:
        """السؤال الرئيسي للشات بوت"""
        try:
            # الخطوة 1: تحديد نوع السؤال
            query_type = self.prompt_engineer.detect_query_type(question)
            print(f"🔍 نوع السؤال: {query_type}")
            
            # الخطوة 2: تحضير السياقات الأربعة
            company_info = ""
            financial_data = ""
            zatca_info = ""
            
            # جمع معلومات الشركة والبيانات المالية
            if self.company_data is not None and not self.company_data.empty:
                company_info = self.context_formatter.format_company_info(self.company_data)
                financial_data = self.context_formatter.format_financial_context(self.company_data)
            
            # جمع معلومات ZATCA من RAG (إذا كان السؤال قانوني أو تنظيمي)
            if query_type in ['legal', 'zatca', 'compliance']:
                rag_context = self.chain_setup.get_context_from_rag(question)
                if rag_context:
                    zatca_info = rag_context
            
            # الخطوة 3: تنسيق الـ prompt بالـ 4 parameters
            formatted_prompt = self.prompt_engineer.format_main_prompt(
                company_info=company_info,
                financial_data=financial_data,
                zatca_info=zatca_info,
                question=question
            )
            
            # الخطوة 4: استدعاء LLM
            llm_response = self.chain_setup.ask_question_real(formatted_prompt, context=None)
            
            # الخطوة 5: تحليل الإجابة
            parsed_response = self.response_parser.parse_llm_response(llm_response['answer'])
            
            # إرجاع النتيجة الكاملة
            return {
                "answer": llm_response['answer'],
                "parsed": parsed_response,
                "query_type": query_type,
                "used_rag": llm_response.get('used_rag', False),
                "source_documents": llm_response.get('source_documents', [])
            }
            
        except Exception as e:
            error_msg = f"❌ خطأ في معالجة السؤال: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return {
                "answer": error_msg,
                "parsed": {"content": error_msg, "confidence": 0},
                "query_type": "error",
                "used_rag": False
            }
    
    def clear_memory(self):
        """مسح ذاكرة المحادثة"""
        self.chain_setup.clear_memory()
        print("✅ تم مسح الذاكرة")

# للاختبار
if __name__ == "__main__":
    print("🧪 اختبار Rakeem Chatbot")
    print("=" * 60)
    
    chatbot = RakeemChatbot(excel_file_path='./Rakeem/data/operation_data_Rakeem.xlsx')
    
    question = "ما هي شروط إصدار الفاتورة الإلكترونية في السعودية؟"
    print(f"\n📝 السؤال: {question}")
    
    response = chatbot.ask_question(question)
    print(f"\n💡 الإجابة:\n{response['answer']}")

import re
import json
from typing import Dict, List, Any

class ResponseParser:
    """Step 4: تحليل وتنظيم ردود الـ LLM"""
    
    def __init__(self):
        self.sources = []
        self.financial_numbers = {}
        
    def parse_llm_response(self, response: Any) -> Dict[str, Any]:
        """تحليل رد الـ LLM واستخراج المكونات المختلفة"""
        try:
            parsed_response = {
                "answer": "",
                "sources": [],
                "financial_advice": [],
                "warnings": [],
                "citations": [],
                "numbers": {}
            }
            
            if isinstance(response, str):
                parsed_response["answer"] = response
                parsed_response.update(self._extract_components_from_text(response))
            elif isinstance(response, dict):
                parsed_response = self._parse_structured_response(response)
            else:
                parsed_response["answer"] = str(response)
                
            return parsed_response
            
        except Exception as e:
            print(f"❌ خطأ في تحليل الرد: {e}")
            return {
                "answer": str(response),
                "sources": [],
                "financial_advice": [],
                "warnings": [],
                "citations": [],
                "numbers": {}
            }
    
    def _parse_structured_response(self, response_dict: Dict) -> Dict[str, Any]:
        """تحليل الرد المهيكل من LangChain"""
        parsed = {
            "answer": response_dict.get('answer', ''),
            "sources": [],
            "financial_advice": [],
            "warnings": [],
            "citations": [],
            "numbers": {}
        }
        
        # استخراج المصادر من المستندات
        source_docs = response_dict.get('source_documents', [])
        for doc in source_docs:
            source_info = {
                "content": doc.page_content[:200] + "..." if hasattr(doc, 'page_content') and len(doc.page_content) > 200 else getattr(doc, 'page_content', ''),
                "source": doc.metadata.get('source', 'مصدر غير معروف') if hasattr(doc, 'metadata') else 'مصدر غير معروف'
            }
            parsed["sources"].append(source_info)
        
        # تحليل النص للإجابة
        if parsed["answer"]:
            text_analysis = self._extract_components_from_text(parsed["answer"])
            parsed.update(text_analysis)
            
        return parsed
    
    def _extract_components_from_text(self, text: str) -> Dict[str, Any]:
        """استخراج المكونات المختلفة من النص"""
        components = {
            "financial_advice": self._extract_financial_advice(text),
            "warnings": self._extract_warnings(text),
            "citations": self._extract_citations(text),
            "numbers": self._extract_financial_numbers(text)
        }
        return components
    
    def _extract_financial_advice(self, text: str) -> List[str]:
        """استخراج النصائح المالية من النص"""
        advice_patterns = [
            r'نصيحة[^:]*:[^\n]*',
            r'توصية[^:]*:[^\n]*', 
            r'ينصح[^\n]*',
            r'يُفضل[^\n]*',
            r'يمكنك[^\n]*',
            r'ننصح[^\n]*'
        ]
        
        advice_list = []
        for pattern in advice_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.UNICODE)
            advice_list.extend(matches)
            
        return advice_list[:3]  # أول 3 نصائح فقط
    
    def _extract_warnings(self, text: str) -> List[str]:
        """استخراج التحذيرات من النص"""
        warning_patterns = [
            r'تحذير[^:]*:[^\n]*',
            r'⚠️[^\n]*',
            r'انتبه[^\n]*',
            r'احذر[^\n]*',
            r'خطر[^\n]*',
            r'تنبيه[^\n]*'
        ]
        
        warnings = []
        for pattern in warning_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.UNICODE)
            warnings.extend(matches)
            
        return warnings
    
    def _extract_citations(self, text: str) -> List[str]:
        """استخراج المراجع والمصادر من النص"""
        citation_patterns = [
            r'المصدر[^:]*:[^\n]*',
            r'المرجع[^:]*:[^\n]*',
            r'حسب[^\n]*ZATCA[^\n]*',
            r'وفقاً[^\n]*ZATCA[^\n]*',
            r'بناء على[^\n]*ZATCA[^\n]*'
        ]
        
        citations = []
        for pattern in citation_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.UNICODE)
            citations.extend(matches)
            
        return citations
    
    def _extract_financial_numbers(self, text: str) -> Dict[str, float]:
        """استخراج الأرقام المالية من النص"""
        # أنماط للعثور على الأرقام المالية
        number_patterns = {
            "إيرادات": r'(إيرادات?|revenue)[^\d]*([\d,]+(?:\.\d+)?)',
            "مصروفات": r'(مصروفات?|expenses)[^\d]*([\d,]+(?:\.\d+)?)',
            "ربح": r'(ربح|profit)[^\d]*([\d,]+(?:\.\d+)?)',
            "ضريبة": r'(ضريبة|vat)[^\d]*([\d,]+(?:\.\d+)?)',
            "زكاة": r'(زكاة|zakat)[^\d]*([\d,]+(?:\.\d+)?)',
            "نسبة": r'([\d,]+(?:\.\d+)?)%'
        }
        
        numbers = {}
        for key, pattern in number_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE | re.UNICODE)
            if matches:
                # أخذ آخر رقم وجد (غالباً الأكثر صلة)
                last_match = matches[-1]
                try:
                    if key == "نسبة":
                        number_str = last_match[0].replace(',', '')
                    else:
                        number_str = last_match[1].replace(',', '')
                    numbers[key] = float(number_str)
                except (ValueError, IndexError):
                    continue
                    
        return numbers
    
    def format_final_response(self, parsed_response: Dict[str, Any]) -> str:
        """تنسيق الرد النهائي للمستخدم"""
        try:
            final_text = ""
            
            # الإجابة الرئيسية
            if parsed_response.get("answer"):
                final_text += f"{parsed_response['answer']}\n\n"
            
            # النصائح المالية
            if parsed_response.get("financial_advice"):
                final_text += "💡 **النصائح والتوصيات:**\n"
                for advice in parsed_response["financial_advice"]:
                    final_text += f"• {advice}\n"
                final_text += "\n"
            
            # التحذيرات
            if parsed_response.get("warnings"):
                final_text += "⚠️ **التحذيرات الهامة:**\n"
                for warning in parsed_response["warnings"]:
                    final_text += f"• {warning}\n"
                final_text += "\n"
            
            # المصادر
            if parsed_response.get("sources"):
                final_text += "📚 **المصادر المستخدمة:**\n"
                for i, source in enumerate(parsed_response["sources"][:2], 1):
                    final_text += f"{i}. {source.get('source', 'مصدر غير معروف')}\n"
            
            return final_text
            
        except Exception as e:
            print(f"❌ خطأ في تنسيق الرد النهائي: {e}")
            return parsed_response.get("answer", "❌ حدث خطأ في معالجة الرد")

# اختبار Step 4
if __name__ == "__main__":
    print("🧪 اختبار Step 4 - Response Parser")
    print("=" * 40)
    
    parser = ResponseParser()
    
    # اختبار مع رد تجريبي
    test_response = {
        "answer": "بناء على بياناتك، الإيرادات 100,000 ريال والمصروفات 80,000 ريال. نصيحة: يمكنك تقليل المصروفات بنسبة 10%. تحذير: انتبه للتدفق النقدي. المصدر: دليل ZATCA للضرائب",
        "source_documents": [
            type('MockDoc', (), {
                'page_content': 'معلومات عن الضرائب في السعودية...',
                'metadata': {'source': 'https://zatca.gov.sa/documents/tax-guide.pdf'}
            })()
        ]
    }
    
    print("1. اختبار تحليل الرد...")
    parsed = parser.parse_llm_response(test_response)
    print(f"   ✅ تم تحليل الرد")
    print(f"   📊 النصائح: {len(parsed['financial_advice'])}")
    print(f"   ⚠️ التحذيرات: {len(parsed['warnings'])}")
    print(f"   🔢 الأرقام: {parsed['numbers']}")
    
    print("2. اختبار تنسيق الرد النهائي...")
    final_response = parser.format_final_response(parsed)
    print(f"   ✅ الرد النهائي: {len(final_response)} حرف")
    print(f"   📝 عينة: {final_response[:100]}...")
    
    print("\n✅ Step 4 جاهز للعمل!")

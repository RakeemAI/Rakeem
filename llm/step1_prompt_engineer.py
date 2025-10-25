# llm/step1_prompt_engineer.py
class ArabicPromptEngineer:
    """Step 1: قوالب برومبت عربية مُشدَّدة تمنع اختراع الأرقام"""

    def __init__(self):
        self.main_template = self._create_main_template()
        self.financial_template = self._create_financial_template()
        self.legal_template = self._create_legal_template()

    def _guard_block(self) -> str:
        return (
            "🛡️ **قواعد صارمة (اتبع بدقة):**\n"
            "• الأرقام تُذكر فقط من القيم المصرّح بها في (القيم المسموح بها) أدناه.\n"
            "• لا تُولّد أرقامًا جديدة أو تقديرات. إذا لم توجد قيمة مطلوبة، قل: «لا أستطيع التأكيد بناءً على البيانات المتاحة».\n"
            "• لا تغيّر الوحدات ولا التقريب إلا بصيغة لفظية (مثال: تقريبًا، نحو...).\n"
            "• عند ذكر أنظمة/ضرائب، اذكر المصدر (ZATCA) إن وُجد في السياق.\n"
        )

    def _allowed_values_block(self, allowed_values_text: str) -> str:
        if not allowed_values_text:
            return "القيم المسموح بها: (غير متوفرة)\n"
        return f"القيم المسموح بها:\n{allowed_values_text}\n"

    def _create_main_template(self):
        # ✅ نوحّي طول الشرح 80–120 كلمة + 3 توصيات نقطية فقط
        template = (
            "أنت مساعد مالي عربي يُدعى «ركيم». مهمتك شرح وتحليل فقط—ولا يجوز اختراع أرقام.\n\n"
            "🏢 **معلومات الشركة:**\n{company_info}\n\n"
            "📊 **البيانات المالية:**\n{financial_data}\n\n"
            "📚 **معلومات ZATCA (إن وُجدت):**\n{zatca_info}\n\n"
            "{guard}\n"
            "{allowed_values}\n"
            "❓ **سؤال المستخدم:**\n{question}\n\n"
            "🎯 **إرشادات الإخراج:**\n"
            "1) اكتب الشرح المختصر بين 80 و 120 كلمة بالعربية فقط.\n"
            "2) قدّم 3 توصيات عملية كقائمة نقطية واضحة.\n"
            "3) لا تذكر أي رقم غير موجود في (القيم المسموح بها).\n"
            "4) عند الاستناد إلى ZATCA اذكر «المصدر: …»\n\n"
            "💬 **الرد:**\n"
        )
        return template

    def _create_financial_template(self):
        return (
            "أنت خبير مالي تشرح المؤشرات من البيانات أدناه.\n\n"
            "{guard}\n{allowed_values}\n"
            "{context}\n\n"
            "❓ السؤال: {question}\n\n"
            "📊 الرد التحليلي:\n"
        )

    def _create_legal_template(self):
        return (
            "أنت مستشار ضرائب/زكاة سعودي. اذكر المصادر عند الاقتضاء.\n\n"
            "{guard}\n{allowed_values}\n"
            "{context}\n\n"
            "❓ السؤال القانوني: {question}\n\n"
            "📜 الرد القانوني:\n"
        )

    def format_main_prompt(self, company_info, financial_data, zatca_info, question, allowed_values_text=""):
        return self.main_template.format(
            company_info=company_info,
            financial_data=financial_data,
            zatca_info=zatca_info,
            question=question,
            guard=self._guard_block(),
            allowed_values=self._allowed_values_block(allowed_values_text),
        )

    def format_financial_prompt(self, context, question, allowed_values_text=""):
        return self.financial_template.format(
            context=context,
            question=question,
            guard=self._guard_block(),
            allowed_values=self._allowed_values_block(allowed_values_text),
        )

    def format_legal_prompt(self, context, question, allowed_values_text=""):
        return self.legal_template.format(
            context=context,
            question=question,
            guard=self._guard_block(),
            allowed_values=self._allowed_values_block(allowed_values_text),
        )

    def detect_query_type(self, question):
        q = (question or "").lower()
        financial_keywords = ['ربح', 'خسارة', 'إيرادات', 'مصروفات', 'تدفق نقدي', 'ميزانية', 'تكلفة', 'ربحية']
        legal_keywords = ['زكاة', 'ضريبة', 'قانون', 'التزام', 'غرامة', 'موعد', 'تسجيل', 'شروط']
        if any(k in q for k in financial_keywords):
            return "financial"
        if any(k in q for k in legal_keywords):
            return "legal"
        return "general"

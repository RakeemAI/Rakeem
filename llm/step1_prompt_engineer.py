class ArabicPromptEngineer:
    """Step 1: تصميم وتنسيق الـ Prompts بالعربية"""
    
    def __init__(self):
        self.main_template = self._create_main_template()
        self.financial_template = self._create_financial_template()
        self.legal_template = self._create_legal_template()
    
    def _create_main_template(self):
        """إنشاء الـ Prompt Template الرئيسي"""
        template = """
        أنت مساعد مالي خبير تُدعى "رَكِيم" وتتحدث العربية بطلاقة. مهمتك مساعدة الشركات الصغيرة والمتوسطة في السعودية.

        🏢 **معلومات الشركة:**
        {company_info}
        
        📊 **البيانات المالية:**
        {financial_data}
        
        📚 **المعلومات التنظيمية من ZATCA:**
        {zatca_info}
        
        💬 **سؤال المستخدم:**
        {question}
        
        🎯 **تعليمات الرد:**
        1. أجب باللغة العربية الفصحى أو العامية المفهومة
        2. استخدم الأرقام والسياق المالي المقدم في ردك
        3. استند إلى المعلومات الرسمية من ZATCA عند الإجابة عن الضرائب أو الزكاة
        4. اذكر المصادر عندما تستخدم معلومات من ZATCA
        5. قدم نصائح عملية وقابلة للتطبيق
        6. إذا لم تكن المعلومات كافية، اطلب توضيحاً
        
        💡 **الرد:**
        """
        return template
    
    def _create_financial_template(self):
        """إنشاء Template خاص بالأسئلة المالية"""
        template = """
        أنت خبير مالي متخصص في تحليل البيانات المالية للشركات السعودية.
        
        📈 **التحليل المالي المطلوب:**
        - قدم تحليلاً واضحاً للبيانات المالية
        - حدد نقاط القوة والضعف
        - قدم توصيات عملية للتحسين
        
        {context}
        
        ❓ السؤال: {question}
        
        📊 الرد التحليلي:
        """
        return template
    
    def _create_legal_template(self):
        """إنشاء Template خاص بالأسئلة القانونية والتنظيمية"""
        template = """
        أنت مستشار قانوني متخصص في قوانين الزكاة والضريبة في السعودية.
        
        ⚖️ **التوجيهات القانونية:**
        - قدم المعلومات بدقة مع ذكر المصادر
        - اذكر المواد والنصوص ذات الصلة
        - نبه إلى الالتزامات والمواعيد
        
        {context}
        
        ❓ السؤال القانوني: {question}
        
        📜 الرد القانوني:
        """
        return template
    
    def format_main_prompt(self, company_info, financial_data, zatca_info, question):
        """تنسيق الـ Prompt الرئيسي"""
        return self.main_template.format(
            company_info=company_info,
            financial_data=financial_data,
            zatca_info=zatca_info,
            question=question
        )
    
    def format_financial_prompt(self, context, question):
        """تنسيق الـ Prompt المالي"""
        return self.financial_template.format(
            context=context,
            question=question
        )
    
    def format_legal_prompt(self, context, question):
        """تنسيق الـ Prompt القانوني"""
        return self.legal_template.format(
            context=context,
            question=question
        )
    
    def detect_query_type(self, question):
        """كشف نوع السؤال"""
        question_lower = question.lower()
        
        financial_keywords = ['ربح', 'خسارة', 'إيرادات', 'مصروفات', 'تدفق نقدي', 'ميزانية', 'تكلفة', 'ربحية']
        legal_keywords = ['زكاة', 'ضريبة', 'قانون', 'التزام', 'غرامة', 'موعد', 'تسجيل', 'شروط']
        
        if any(keyword in question_lower for keyword in financial_keywords):
            return "financial"
        elif any(keyword in question_lower for keyword in legal_keywords):
            return "legal"
        else:
            return "general"

# اختبار Step 1
if __name__ == "__main__":
    print("🧪 اختبار Step 1 - Prompt Engineer")
    print("=" * 40)
    
    engineer = ArabicPromptEngineer()
    
    # اختبار كشف أنواع الأسئلة
    test_questions = [
        "كيف أحسب صافي الربح؟",
        "ما هي مواعيد دفع الزكاة؟",
        "كيف يمكنني تحسين التدفق النقدي؟",
        "ما هي شروط الإعفاء من الضريبة؟",
        "كيف أطور استراتيجية التسعير؟"
    ]
    
    print("📊 اختبار كشف أنواع الأسئلة:")
    for i, question in enumerate(test_questions, 1):
        query_type = engineer.detect_query_type(question)
        print(f"   {i}. '{question}'")
        print(f"      → النوع: {query_type}")
    
    # اختبار تنسيق الـ Prompt
    print("\n🎯 اختبار تنسيق الـ Prompts:")
    
    # نموذج بيانات تجريبية
    company_info = "شركة التطوير المحدودة"
    financial_data = "الإيرادات: 100,000 ريال، المصروفات: 80,000 ريال"
    zatca_info = "معلومات عن ضريبة القيمة المضافة"
    
    test_question = "كيف أحسب الضريبة المستحقة؟"
    prompt = engineer.format_main_prompt(company_info, financial_data, zatca_info, test_question)
    print(f"   Prompt الرئيسي (أول 200 حرف):")
    print(f"   {prompt[:200]}...")
    
    print("\n✅ Step 1 جاهز للعمل!")

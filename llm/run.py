# llm/run.py

import os
import importlib

# --- helper: safe import whether absolute or relative ---
def _import_attr(module_name: str, attr: str):
    """
    يحاول يستورد llm.<module_name> أولاً، ولو فشل
    يحاول الاستيراد النسبي .<module_name> داخل الحزمة الحالية.
    """
    # مطلق: llm.stepX_...
    try:
        mod = importlib.import_module(f"llm.{module_name}")
        return getattr(mod, attr)
    except Exception:
        pass
    # نسبي: .stepX_... (في حال تشغيله داخل الحزمة)
    try:
        mod = importlib.import_module(f".{module_name}", package=__package__)
        return getattr(mod, attr)
    except Exception as e:
        raise ImportError(
            f"Cannot import {attr} from module {module_name}. "
            f"Tried both absolute 'llm.{module_name}' and relative '.{module_name}'."
        ) from e

# اجلب الدوال من الملفات الأخرى بدون ما نكسر لوضع الاستيراد
build_prompt       = _import_attr("step1_prompt_engineer", "build_prompt")
create_qa_chain    = _import_attr("step2_chain_setup", "create_qa_chain")
extract_sources    = _import_attr("step3_context_formatter", "extract_sources")
finalize_answer    = _import_attr("step4_response_parser", "finalize_answer")

# ============ الواجهة المستخدمة من app.py ============
def answer_question(question: str, context: dict) -> dict:
    """
    يأخذ سؤال المستخدم والسياق (اسم الشركة، الدولة، مسارات البيانات…) ويُعيد:
      { "answer": str, "sources": [ {title, url} , ... ] }
    """
    # ابنِ البرومبت بناءً على السياق (اسم الشركة، الدولة الافتراضية: السعودية، إلخ)
    prompt = build_prompt(
        question=question,
        company_name=context.get("company_name"),
        country=context.get("country", "السعودية"),
        memory=context.get("memory"),  # محادثة سابقة إن وجِدت
    )

    # ابنِ السلسلة (LLM + Retriever من Milvus)
    chain = create_qa_chain(
        top_k=context.get("rag_top_k", 3),
        score_threshold=context.get("rag_score_threshold", 0.7),
    )

    # شغّل السلسلة على البرومبت
    result = chain.invoke({"question": prompt})

    # استخرج المصادر بصيغة موحدة
    sources = extract_sources(result)

    # صياغة الإجابة النهائية مع إدماج المصادر
    answer = finalize_answer(
        question=question,
        raw_answer=result.get("answer") or result,
        sources=sources,
        company_name=context.get("company_name"),
        country=context.get("country", "السعودية"),
    )

    return {"answer": answer, "sources": sources}

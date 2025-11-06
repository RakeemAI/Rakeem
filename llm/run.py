# llm/run.py
# يدير إنشاء السلسلة مرة واحدة ويمرّر المحادثة للـLLM

from typing import Tuple, List

_QA = None  # نخزّن الكائن هنا عشان ما يعاد تحميله كل مرة


def _ensure_chain():
    """ينشئ سلسلة الـQA عند أول استخدام فقط"""
    global _QA
    if _QA is None:
        from .step2_chain_setup import create_qa_chain
        _QA = create_qa_chain()
    return _QA


def answer_question(user_input: str, history_text: str) -> Tuple[str, List[tuple]]:
    """
    يستقبل نص المستخدم وتاريخ المحادثة
    ويعيد (الإجابة، قائمة المصادر)
    """
    qa = _ensure_chain()
    result = qa.invoke({"input": user_input, "history": history_text})

    answer = result.get("answer", "")
    docs = result.get("context", []) or []

    # تنسيق قائمة المصادر
    sources = []
    for d in docs:
        meta = getattr(d, "metadata", {}) or {}
        title = meta.get("title") or meta.get("source") or "—"
        url = meta.get("url")
        sources.append((title, url))

    return answer, sources

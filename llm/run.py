# llm/run.py
# يدير إنشاء السلسلة بشكل كسول + يمرّر تاريخ المحادثة للـLLM

from typing import Tuple, List

_QA = None  # كاش للسلسلة لتجنّب إعادة الإنشاء كل سؤال


def _ensure_chain():
    """ينشئ سلسلة الـQA عند أول استخدام فقط (استيراد كسول)."""
    global _QA
    if _QA is None:
        from .step2_chain_setup import create_qa_chain
        _QA = create_qa_chain()
    return _QA


def answer_question(user_input: str, history_text: str) -> Tuple[str, List[tuple]]:
    """
    يستقبل رسالة المستخدم + سجل المحادثة كنص مهيأ،
    ويُعيد (الإجابة، قائمة المصادر).
    """
    qa = _ensure_chain()
    res = qa.invoke({"input": user_input, "history": history_text})

    answer = res.get("answer") or ""
    sources: List[tuple] = []
    for d in res.get("context", []) or []:
        meta = getattr(d, "metadata", {}) or {}
        title = meta.get("title") or meta.get("source") or "غير معروف"
        url = meta.get("url")
        sources.append((title, url))
    return answer, sources



# llm/run.py
from typing import Tuple, List

_QA = None  # كاش للسلسلة

def _ensure_chain():
    global _QA
    if _QA is None:
        # استيراد كسول حتى لو فشل ملف step2 سابقًا ما يطيح ui/app.py
        from .step2_chain_setup import create_qa_chain
        _QA = create_qa_chain()
    return _QA

def answer_question(user_input: str) -> Tuple[str, List[tuple]]:
    qa = _ensure_chain()
    res = qa.invoke({"input": user_input})
    answer = res.get("answer") or res.get("result") or ""
    sources = []
    for d in res.get("context", []):
        meta = getattr(d, "metadata", {}) or {}
        title = meta.get("title") or meta.get("source") or "غير معروف"
        url = meta.get("url")
        sources.append((title, url))
    return answer, sources


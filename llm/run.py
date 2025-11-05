# llm/run.py
from .step2_chain_setup import create_qa_chain

qa = create_qa_chain()

def answer_question(user_input: str):
    """
    يُرجع (answer, sources) — ويقرأ المصادر من metadata في المستندات التي تم استرجاعها.
    """
    result = qa.invoke({"input": user_input})
    answer = result.get("answer") or result.get("result") or ""
    sources = []
    for d in result.get("context", []):
        meta = getattr(d, "metadata", {}) or {}
        title = meta.get("title") or meta.get("source") or "غير معروف"
        url = meta.get("url")
        sources.append((title, url))
    return answer, sources


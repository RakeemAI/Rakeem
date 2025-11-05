# llm/run.py
from .step2_chain_setup import create_qa_chain

qa = create_qa_chain()

def answer_question(user_input: str):
    """
    يرجّع (answer, sources)
    - answer: النص العربي النهائي.
    - sources: قائمة (title, url) من نتائج الاسترجاع.
    """
    result = qa.invoke({"question": user_input})
    answer = result.get("answer") or result.get("result") or ""

    sources = []
    for doc in result.get("context", []):  # في النمط الجديد تُعاد كمفتاح 'context'
        meta = getattr(doc, "metadata", {}) or {}
        title = meta.get("title") or meta.get("source") or "غير معروف"
        url = meta.get("url")
        sources.append((title, url))
    return answer, sources


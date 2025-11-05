# llm/run.py
from .step2_chain_setup import create_qa_chain

# نجهّز سلسلة RAG/LLM الجاهزة (تلقائيًا يتصل بـ Milvus Cloud)
qa = create_qa_chain()

def answer_question(user_input: str):
    """
    ترجع إجابة المساعد المالي + قائمة المصادر المستخدمة.
    """
    result = qa({"query": user_input})
    answer = result["result"]

    # نجمع معلومات المصادر
    sources = []
    for d in result.get("source_documents", []):
        meta = getattr(d, "metadata", {}) or {}
        title = meta.get("title") or meta.get("source") or "غير معروف"
        url = meta.get("url")
        sources.append((title, url))
    return answer, sources

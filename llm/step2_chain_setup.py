# llm/step2_chain_setup.py
import os
from typing import Dict, Any, List

# نقرأ من secrets إذا متاح (Streamlit Cloud) وإلا من env
try:
    import streamlit as st
    _SECRETS = getattr(st, "secrets", {})
except Exception:
    _SECRETS = {}

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_milvus import Milvus
from langchain_core.prompts import PromptTemplate
from langchain.docstore.document import Document

from engine.build_store_milvus import build_milvus_if_needed


def _get(name: str, default=None):
    if _SECRETS and name in _SECRETS:
        return _SECRETS.get(name, default)
    return os.getenv(name, default)


def _cfg() -> Dict[str, Any]:
    return {
        "OPENAI_API_KEY": _get("OPENAI_API_KEY"),
        "MODEL_NAME": _get("MODEL_NAME", "gpt-4o-mini"),
        "TEMPERATURE": float(_get("TEMPERATURE", 0.2)),
        "RAG_TOP_K": int(_get("RAG_TOP_K", 3)),
        "MILVUS_URI": _get("MILVUS_URI"),
        "MILVUS_TOKEN": _get("MILVUS_TOKEN"),
        "MILVUS_COLLECTION": _get("MILVUS_COLLECTION", "rakeem_rag_v1"),
        "EMBEDDING_MODEL": _get("EMBEDDING_MODEL", "text-embedding-3-small"),
    }


class SimpleQA:
    """غلاف بسيط يوفّر .invoke({input: سؤال}) => {answer, context} بدون الاعتماد على مسارات LangChain المتغيّرة"""
    def __init__(self, llm: ChatOpenAI, retriever, prompt: PromptTemplate, top_k: int):
        self.llm = llm
        self.retriever = retriever
        self.prompt = prompt
        self.top_k = top_k

    def _format_docs(self, docs: List[Document]) -> str:
        parts = []
        for d in docs:
            parts.append(d.page_content)
        return "\n\n".join(parts)

    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        q = inputs.get("input") or inputs.get("question") or inputs.get("query") or ""
        q = str(q).strip()
        if not q:
            return {"answer": "", "context": []}

        # استرجاع المستندات
        docs = self.retriever.get_relevant_documents(q)
        ctx_text = self._format_docs(docs)

        # تجهيز البرومبت النصي وتمريره إلى الـLLM مباشرة
        prompt_text = self.prompt.format(context=ctx_text, question=q)
        ai_msg = self.llm.invoke(prompt_text)
        answer = getattr(ai_msg, "content", str(ai_msg))

        return {"answer": answer, "context": docs}


def create_qa_chain(top_k: int | None = None) -> SimpleQA:
    cfg = _cfg()

    # بناء/التحقق من الفهرس تلقائيًا
    build_milvus_if_needed()

    # Embeddings + Vector store + Retriever
    embeddings = OpenAIEmbeddings(
        model=cfg["EMBEDDING_MODEL"],
        openai_api_key=cfg["OPENAI_API_KEY"],
    )
    vector_store = Milvus(
        embedding_function=embeddings,
        collection_name=cfg["MILVUS_COLLECTION"],
        connection_args={"uri": cfg["MILVUS_URI"], "token": cfg["MILVUS_TOKEN"], "secure": True},
    )
    retriever = vector_store.as_retriever(search_kwargs={"k": top_k or cfg["RAG_TOP_K"]})

    # برومبت عربي متحفظ يذكر المصدر
    system_ar = (
        "أنت «رقيم» مساعد مالي سعودي. أجب بالعربية الفصحى اعتمادًا فقط على [السياق] أدناه. "
        "إن لم يكن السياق كافيًا فقل: «المصدر غير متوفر في بياناتنا المحلية.» "
        "أضف في النهاية سطر «المصدر: …» باستخدام عناوين/روابط من metadata إن وُجدت."
    )
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=f"{system_ar}\n\n[السياق]\n{{context}}\n\n[السؤال]\n{{question}}\n\nالجواب:",
    )

    llm = ChatOpenAI(
        model=cfg["MODEL_NAME"],
        temperature=cfg["TEMPERATURE"],
        openai_api_key=cfg["OPENAI_API_KEY"],
    )

    return SimpleQA(llm=llm, retriever=retriever, prompt=prompt, top_k=top_k or cfg["RAG_TOP_K"])



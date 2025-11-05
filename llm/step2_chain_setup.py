# llm/step2_chain_setup.py
import os
from typing import Dict, Any, List

# secrets في ستريمليت أو env
try:
    import streamlit as st
    _SECRETS = getattr(st, "secrets", {})
except Exception:
    _SECRETS = {}

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_milvus import Milvus
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document

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
    """سلسلة RAG مستقرة: retriever + LLM + prompt. ترجع {'answer','context'}"""
    def __init__(self, llm: ChatOpenAI, retriever, prompt: PromptTemplate):
        self.llm = llm
        self.retriever = retriever
        self.prompt = prompt

    def _fmt(self, docs: List[Document]) -> str:
        return "\n\n".join(d.page_content for d in docs)

    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        q = (inputs.get("input") or inputs.get("question") or "").strip()
        if not q:
            return {"answer": "", "context": []}
        docs = self.retriever.get_relevant_documents(q)
        ctx = self._fmt(docs)
        prompt_text = self.prompt.format(context=ctx, question=q)
        msg = self.llm.invoke(prompt_text)
        ans = getattr(msg, "content", str(msg))
        return {"answer": ans, "context": docs}


def create_qa_chain() -> SimpleQA:
    cfg = _cfg()

    # يبني مجموعة Milvus تلقائيًا إذا كانت فارغة
    build_milvus_if_needed()

    embeddings = OpenAIEmbeddings(
        model=cfg["EMBEDDING_MODEL"],
        openai_api_key=cfg["OPENAI_API_KEY"],
    )
    vs = Milvus(
        embedding_function=embeddings,
        collection_name=cfg["MILVUS_COLLECTION"],
        connection_args={"uri": cfg["MILVUS_URI"], "token": cfg["MILVUS_TOKEN"], "secure": True},
    )
    retriever = vs.as_retriever(search_kwargs={"k": cfg["RAG_TOP_K"]})

    system_ar = (
        "أنت «رقيم» مساعد مالي سعودي. أجب بالعربية الفصحى اعتمادًا فقط على [السياق] أدناه. "
        "إن لم يكن السياق كافيًا فقل: «المصدر غير متوفر في بياناتنا المحلية.» "
        "وفي النهاية أضف سطر «المصدر: …» باستخدام العناوين/الروابط من metadata إن وُجدت."
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

    return SimpleQA(llm=llm, retriever=retriever, prompt=prompt)




# llm/step2_chain_setup.py
import os
try:
    import streamlit as st
    _SECRETS = getattr(st, "secrets", {})
except Exception:
    _SECRETS = {}

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_milvus import Milvus
from langchain.prompts import PromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain

from engine.build_store_milvus import build_milvus_if_needed

def _get(k: str, default=None):
    if _SECRETS and k in _SECRETS: return _SECRETS.get(k, default)
    return os.getenv(k, default)

def _cfg():
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

def create_qa_chain(top_k: int | None = None):
    cfg = _cfg()
    # يبني الفهرس تلقائيًا عند الحاجة
    build_milvus_if_needed()

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

    system_ar = (
        "أنت «رقيم» مساعد مالي سعودي. أجب بالعربية الفصحى اعتمادًا فقط على [السياق]. "
        "إذا لم يكن السياق كافيًا فقل: «المصدر غير متوفر في بياناتنا المحلية.» "
        "أضف في النهاية سطر «المصدر: …» من metadata (العنوان/الرابط) إن وُجد."
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

    # سلسلة «حشو المستندات» ثم سلسلة الاسترجاع (النمط الجديد في LangChain 0.2+)
    stuff_chain = create_stuff_documents_chain(llm, prompt)
    retrieval_chain = create_retrieval_chain(retriever, stuff_chain)
    return retrieval_chain


# llm/step2_chain_setup.py
import os

# نحاول القراءة من st.secrets إذا متاح (على السحابة)
try:
    import streamlit as st
    _SECRETS = getattr(st, "secrets", {})
except Exception:
    _SECRETS = {}

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_milvus import Milvus
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain.prompts import PromptTemplate

# يبني الفهرس تلقائيًا لو ناقص (من ./Rakeem/data/merged_final.json)
from engine.build_store_milvus import build_milvus_if_needed


# --------- Helpers ---------
def _get(name: str, default=None):
    """اقرأ من st.secrets أولاً ثم من متغيرات البيئة."""
    if _SECRETS and name in _SECRETS:
        return _SECRETS.get(name, default)
    return os.getenv(name, default)


def _env_config():
    return {
        "OPENAI_API_KEY": _get("OPENAI_API_KEY"),
        "MODEL_NAME": _get("MODEL_NAME", "gpt-4o-mini"),
        "TEMPERATURE": float(_get("TEMPERATURE", 0)),
        "RAG_TOP_K": int(_get("RAG_TOP_K", 4)),
        "MILVUS_URI": _get("MILVUS_URI"),
        "MILVUS_TOKEN": _get("MILVUS_TOKEN"),
        "MILVUS_COLLECTION": _get("MILVUS_COLLECTION", "rakeem_rag_v1"),
        "EMBEDDING_MODEL": _get("EMBEDDING_MODEL", "text-embedding-3-small"),
    }


# --------- Public factory ---------
def create_qa_chain(top_k: int | None = None) -> RetrievalQA:
    """
    ينشئ سلسلة RetrievalQA تستخدم Milvus كـ Vector Store.
    - يبني/يتحقق من الفهرس تلقائيًا عبر build_milvus_if_needed().
    - يعيد إجابات بالعربية، ويذكر المصادر من metadata (title/source/url).
    """
    cfg = _env_config()

    # 1) تأكد من وجود الفهرس في Milvus (يبني تلقائيًا لو مفقود)
    build_milvus_if_needed()

    # 2) Embeddings & Vector Store (Milvus Cloud)
    embeddings = OpenAIEmbeddings(
        model=cfg["EMBEDDING_MODEL"],
        openai_api_key=cfg["OPENAI_API_KEY"],
    )

    vector_store = Milvus(
        embedding_function=embeddings,
        collection_name=cfg["MILVUS_COLLECTION"],
        connection_args={
            "uri": cfg["MILVUS_URI"],
            "token": cfg["MILVUS_TOKEN"],
            "secure": True,  # Zilliz/Milvus Cloud عبر HTTPS
        },
    )

    # 3) Retriever
    k = top_k if top_k is not None else cfg["RAG_TOP_K"]
    retriever = vector_store.as_retriever(search_kwargs={"k": k})

    # 4) Arabic prompt يلزم الاعتماد على السياق وذكر المصدر
    system_ar = (
        "أنت «رقيم» مساعد مالي سعودي. أجب بالعربية الفصحى."
        " استخدم فقط المعلومات الموجودة في [السياق] للإجابة."
        " إذا لم يكن السياق كافيًا قل: «المصدر غير متوفر في البيانات المحلية.»"
        " في النهاية اذكر سطر: «المصدر: ...» وضع فيه عناوين/روابط من metadata إن وُجدت."
    )

    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=(
            f"{system_ar}\n\n"
            "[السياق]\n{{context}}\n\n"
            "[السؤال]\n{{question}}\n\n"
            "الجواب:"
        ),
    )

    # 5) LLM
    llm = ChatOpenAI(
        model=cfg["MODEL_NAME"],
        temperature=cfg["TEMPERATURE"],
        openai_api_key=cfg["OPENAI_API_KEY"],
    )

    # 6) RetrievalQA مع إعادة الوثائق (لإظهار المصادر في الواجهة)
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        chain_type_kwargs={
            "prompt": prompt,
            "document_variable_name": "context",
        },
        return_source_documents=True,
    )

    return qa_chain


# --------- (اختياري) دالة مساعدة ترجع الـ retriever فقط ---------
def create_retriever(top_k: int | None = None):
    """للاستخدامات الخاصة إن احتجت الـ retriever منفصلًا."""
    cfg = _env_config()
    build_milvus_if_needed()

    embeddings = OpenAIEmbeddings(
        model=cfg["EMBEDDING_MODEL"],
        openai_api_key=cfg["OPENAI_API_KEY"],
    )
    vector_store = Milvus(
        embedding_function=embeddings,
        collection_name=cfg["MILVUS_COLLECTION"],
        connection_args={
            "uri": cfg["MILVUS_URI"],
            "token": cfg["MILVUS_TOKEN"],
            "secure": True,
        },
    )
    k = top_k if top_k is not None else cfg["RAG_TOP_K"]
    return vector_store.as_retriever(search_kwargs={"k": k})

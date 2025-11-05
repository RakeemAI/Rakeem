# engine/build_store_milvus.py
import os, json
from langchain_openai import OpenAIEmbeddings
from langchain_milvus import Milvus
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document

def _env(name: str, default=None):
    import streamlit as st
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)

def build_milvus_if_needed():
    """
    يبني مجموعة Milvus تلقائيًا من ./Rakeem/data/merged_final.json إذا كانت فاضية/غير موجودة.
    يستخدم LangChain ليتوافق المخطط مع langchain_milvus.
    """
    uri   = _env("MILVUS_URI")
    token = _env("MILVUS_TOKEN")
    coll  = _env("MILVUS_COLLECTION", "rakeem_rag_v1")
    src   = _env("RAG_SOURCE_JSON", "./Rakeem/data/merged_final.json")
    embed_model = _env("EMBEDDING_MODEL", "text-embedding-3-small")
    openai_key  = _env("OPENAI_API_KEY")

    embeddings = OpenAIEmbeddings(model=embed_model, openai_api_key=openai_key)

    # جرّب تفتح المجموعة؛ إذا موجودة وفيها بيانات نطلع
    store = Milvus(
        embedding_function=embeddings,
        collection_name=coll,
        connection_args={"uri": uri, "token": token, "secure": True},
    )
    try:
        stats = store.client.get_collection_stats(coll)
        if stats.get("row_count", 0) > 0:
            print(f"[Rakeem] Milvus collection '{coll}' ready with rows={stats['row_count']}")
            return
    except Exception:
        print(f"[Rakeem] Milvus collection '{coll}' not found. Will create…")

    # حمّل الداتا وقطّعها
    with open(src, "r", encoding="utf-8") as f:
        items = json.load(f)

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    docs = []
    for it in items:
        q, a = it.get("Q"), it.get("A")
        text = f"سؤال: {q}\nإجابة: {a}" if q and a else json.dumps(it, ensure_ascii=False)
        meta = {
            "title": it.get("Topic") or it.get("title"),
            "source": it.get("Source") or it.get("source"),
            "url": it.get("url"),
        }
        for chunk in splitter.split_text(text):
            docs.append(Document(page_content=chunk, metadata=meta))

    Milvus.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=coll,
        connection_args={"uri": uri, "token": token, "secure": True},
    )
    print(f"[Rakeem] Built '{coll}' with {len(docs)} chunks ✅")

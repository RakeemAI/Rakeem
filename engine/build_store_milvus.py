# engine/build_store_milvus.py
# بناء/التحقق من فهرس Milvus انطلاقًا من merged_final.json مع مسارات مستقرة لـ LangChain

import os
import json
from pathlib import Path
from typing import Tuple, Dict, Any, List

# قراءة من Streamlit secrets إن وُجدت ثم من متغيرات البيئة
def _get(name: str, default=None):
    try:
        import streamlit as st
        if hasattr(st, "secrets") and name in st.secrets:
            return st.secrets.get(name, default)
    except Exception:
        pass
    return os.getenv(name, default)

# استيراد ثابت لـ Document
from langchain_core.documents import Document

# استيراد Text Splitter بشكل متوافق مع الإصدارات
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except Exception:
    # بديل مبسط كـ fallback حتى لا يتعطل التطبيق إن لم تتوفر الحزمة
    class RecursiveCharacterTextSplitter:
        def __init__(self, chunk_size=800, chunk_overlap=120):
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
        def split_text(self, text: str) -> List[str]:
            s, o, n = self.chunk_size, self.chunk_overlap, len(text)
            out, i = [], 0
            while i < n:
                end = min(i + s, n)
                out.append(text[i:end])
                i = max(end - o, i + 1)
            return out

from langchain_openai import OpenAIEmbeddings
from langchain_milvus import Milvus


def _resolve_source_path() -> Path:
    """
    يحاول إيجاد ملف merged_final.json من:
      - RAG_SOURCE_JSON في secrets/env (نسبيًا إلى جذر المشروع)
      - مسارات افتراضية شائعة
    ويرمي FileNotFoundError برسالة مُفصّلة لو ما وُجد.
    """
    raw = _get("RAG_SOURCE_JSON")
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            # اجعل المسار نسبةً إلى جذر المشروع (مجلد هذا الملف/..)
            p = (Path(__file__).resolve().parents[1] / p).resolve()
        if p.exists():
            return p

    project_root = Path(__file__).resolve().parents[1]  # .../rakeem
    candidates = [
        project_root / "data" / "merged_final.json",
        project_root / "Rakeem" / "data" / "merged_final.json",
        project_root.parent / "Rakeem" / "data" / "merged_final.json",
        project_root.parent / "rakeem" / "data" / "merged_final.json",
    ]
    for c in candidates:
        if c.exists():
            return c

    hint = "\n".join(f"- {c}" for c in candidates)
    cwd = Path.cwd()
    raise FileNotFoundError(
        "لم أجد ملف merged_final.json.\n"
        f"Working dir: {cwd}\n"
        "جرّبت هذه المسارات:\n"
        f"{hint}\n\n"
        "حلول سريعة:\n"
        "1) ارفع الملف إلى data/merged_final.json في جذر المشروع.\n"
        "2) أو ضع RAG_SOURCE_JSON = \"data/merged_final.json\" في Streamlit Secrets.\n"
        "3) تأكد من حالة الأحرف (rakeem vs Rakeem)."
    )


def build_milvus_if_needed():
    """
    يتأكد من جاهزية مجموعة Milvus؛
    - إن وُجدت بيانات: يطبع حالة النجاح ويخرج.
    - إن كانت فاضية/غير موجودة: يبنيها من merged_final.json.
    """
    uri   = _get("MILVUS_URI")
    token = _get("MILVUS_TOKEN")
    coll  = _get("MILVUS_COLLECTION", "rakeem_rag_v1")
    embed_model = _get("EMBEDDING_MODEL", "text-embedding-3-small")
    openai_key  = _get("OPENAI_API_KEY")
    secure_flag = str(_get("MILVUS_SECURE", "true")).lower() not in ("0", "false", "no")

    if not uri or not token:
        raise RuntimeError("بيانات الاتصال بـ Milvus ناقصة: تأكد من MILVUS_URI و MILVUS_TOKEN في Secrets.")

    # تهيئة المتجهات ومخزن Milvus
    embeddings = OpenAIEmbeddings(model=embed_model, openai_api_key=openai_key)
    store = Milvus(
        embedding_function=embeddings,
        collection_name=coll,
        connection_args={"uri": uri, "token": token, "secure": secure_flag},
    )

    # فحص سريع: إن رجعت وثيقة واحدة على الأقل، نعتبر المجموعة جاهزة
    try:
        test_docs = store.as_retriever(search_kwargs={"k": 1}).get_relevant_documents("healthcheck")
        if test_docs:
            print(f"[Rakeem] Milvus collection '{coll}' ready (sample title: {test_docs[0].metadata.get('title')})")
            return
    except Exception as e:
        # إن فشل الاسترجاع نكمل للبناء (قد تكون المجموعة غير موجودة أصلاً)
        print(f"[Rakeem] Retriever test failed, will (re)build. Reason: {e}")

    # حل مسار المصدر وقراءة البيانات
    src_path = _resolve_source_path()
    with open(src_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    docs = []
    for it in items:
        q, a = it.get("Q"), it.get("A")
        # إن كان ملفك على سكيمة مختلفة، عدّل التجميع هنا
        text = f"سؤال: {q}\nإجابة: {a}" if (q and a) else json.dumps(it, ensure_ascii=False)
        meta = {
            "title": it.get("Topic") or it.get("title"),
            "source": it.get("Source") or it.get("source"),
            "url": it.get("url"),
        }
        for chunk in splitter.split_text(text):
            docs.append(Document(page_content=chunk, metadata=meta))

    # الإنشاء/الإدراج: from_documents ستنشئ المجموعة إذا كانت غير موجودة
    Milvus.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name=coll,
        connection_args={"uri": uri, "token": token, "secure": secure_flag},
    )
    print(f"[Rakeem] Built '{coll}' with {len(docs)} chunks ✅")


def milvus_health() -> Tuple[bool, Dict[str, Any]]:
    """
    تشخيص اتصال Milvus بشكل آمن؛ يرجع (connected?, info)
    - لا يرمي استثناءات، يعيد الخطأ كنص في info["error"].
    - مفيد لعرضه داخل واجهة ستريمليت.
    """
    try:
        uri   = _get("MILVUS_URI")
        token = _get("MILVUS_TOKEN")
        coll  = _get("MILVUS_COLLECTION", "rakeem_rag_v1")
        embed_model = _get("EMBEDDING_MODEL", "text-embedding-3-small")
        openai_key  = _get("OPENAI_API_KEY")
        secure_flag = str(_get("MILVUS_SECURE", "true")).lower() not in ("0", "false", "no")

        embeddings = OpenAIEmbeddings(model=embed_model, openai_api_key=openai_key)
        vs = Milvus(
            embedding_function=embeddings,
            collection_name=coll,
            connection_args={"uri": uri, "token": token, "secure": secure_flag},
        )
        docs = vs.as_retriever(search_kwargs={"k": 1}).get_relevant_documents("healthcheck")
        info = {
            "collection": coll,
            "doc_count>0?": bool(docs),
            "sample_doc_title": (docs[0].metadata.get("title") if docs else None),
            "uri_prefix": (uri[:40] + "...") if uri else None,
            "secure": secure_flag,
        }
        return True, info
    except Exception as e:
        return False, {"error": str(e)}

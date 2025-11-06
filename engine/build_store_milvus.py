import os, json
from langchain_openai import OpenAIEmbeddings
from langchain_milvus import Milvus
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

def build_milvus_if_needed():
    """بناء مجموعة Milvus وتخزين بيانات RAG في السحابة"""
    
    # جلب المتغيرات من secrets أو البيئة
    uri   = os.getenv("MILVUS_URI")
    token = os.getenv("MILVUS_TOKEN")
    coll  = os.getenv("MILVUS_COLLECTION", "rakeem_rag_v1")
    src   = os.getenv("RAG_SOURCE_JSON", "./data/merged_final.json")
    embed_model = os.getenv("EMBED_MODEL", "text-embedding-3-small")

    # فحص وجود الملف المحلي
    if not os.path.exists(src):
        raise FileNotFoundError(f"❌ ملف البيانات غير موجود: {src}")

    # تحميل البيانات
    with open(src, "r", encoding="utf-8") as f:
        items = json.load(f)

    print(f"📦 Loaded {len(items)} records from {src}")

    # إعداد نموذج التضمين
    emb = OpenAIEmbeddings(model=embed_model)

    # تقسيم النصوص
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    docs = []

    for it in items:
        q, a = it.get("Question"), it.get("Answer")
        text = f"سؤال: {q}\nإجابة: {a}" if (q and a) else json.dumps(it, ensure_ascii=False)

        # الميتاداتا بدون URL لتجنب الأخطاء
        meta = {
            "title":  it.get("Topic")  or it.get("title"),
            "source": it.get("Source") or it.get("source"),
        }

        for ch in splitter.split_text(text):
            docs.append(Document(page_content=ch, metadata=meta))

    print(f"🧩 Total chunks ready: {len(docs)}")

    # إنشاء/تحديث المجموعة في Milvus Cloud
    store = Milvus.from_documents(
        documents=docs,
        embedding=emb,
        collection_name=coll,
        connection_args={"uri": uri, "token": token, "secure": True},
    )

    print(f"✅ Milvus collection '{coll}' built with {len(docs)} chunks.")

    return store

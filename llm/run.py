# llm/run.py
# يربط جميع مراحل Rakeem LLM pipeline (Step1 → Step4)
# ويستدعي قاعدة المعرفة من Milvus بشكل مباشر (قراءة فقط)

import os
from typing import Tuple, List
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_milvus import Milvus

# استدعاء الوحدات الأربع (Step1 → Step4)
from .step1_prompt_engineer import build_prompt
from .step2_chain_setup import create_qa_chain
from .step3_context_formatter import format_context
from .step4_response_parser import parse_llm_answer

# ======================= الإعداد =======================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME     = os.getenv("MODEL_NAME", "gpt-4o-mini")
TEMPERATURE    = float(os.getenv("TEMPERATURE", 0.2))
RAG_TOP_K      = int(os.getenv("RAG_TOP_K", 3))

MILVUS_URI     = os.getenv("MILVUS_URI")     
MILVUS_TOKEN   = os.getenv("MILVUS_TOKEN")
MILVUS_COLL    = os.getenv("MILVUS_COLLECTION", "rakeem_rag_v1")
EMBED_MODEL    = os.getenv("EMBED_MODEL", "text-embedding-3-small")

# =======================================================

def _get_retriever():
    """إنشاء retriever متصل بقاعدة Milvus"""
    embeddings = OpenAIEmbeddings(
        model=EMBED_MODEL,
        openai_api_key=OPENAI_API_KEY
    )
    vector_store = Milvus(
        embedding_function=embeddings,
        collection_name=MILVUS_COLL,
        connection_args={"uri": MILVUS_URI, "token": MILVUS_TOKEN, "secure": True},
    )
    return vector_store.as_retriever(search_kwargs={"k": RAG_TOP_K})


# =======================================================

def answer_question(question: str, history_text: str) -> Tuple[str, List[tuple]]:
    """
    يستقبل سؤال المستخدم + المحادثة السابقة (history_text)
    ويرجع الإجابة النهائية + قائمة المصادر المسترجعة من Milvus
    """

    # 1️⃣ تهيئة النموذج والمحاور (prompt)
    llm = ChatOpenAI(
        model=MODEL_NAME,
        temperature=TEMPERATURE,
        openai_api_key=OPENAI_API_KEY,
    )

    prompt = build_prompt(profile=history_text)

    # 2️⃣ إعداد retriever من Milvus
    retriever = _get_retriever()

    # 3️⃣ بناء السلسلة (chain) من step2
    chain = create_qa_chain(llm, retriever, prompt)

    # 4️⃣ تمرير السؤال وتشغيل السلسلة
    result = chain.invoke({"question": question})

    # 5️⃣ استخراج الوثائق (السياق) والمصادر
    docs = result.get("context", [])
    answer = result.get("answer", "") or result.get("result", "")
    sources = extract_sources(docs)

    # 6️⃣ تنسيق الإجابة النهائية مع المصادر
    final_answer = finalize_answer(answer, sources)

    # 7️⃣ إرجاع النص والمصادر
    return final_answer, sources

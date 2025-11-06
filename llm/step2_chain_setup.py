# llm/step2_chain_setup.py
# مستقر + يدعم المحادثة (history) + يستخدم RAG بشكل اختياري

import os
from typing import Dict, Any, List

# نحاول نقرأ من st.secrets إن توفّر (على ستريمليت كلاود)
try:
    import streamlit as st
    _SECRETS = getattr(st, "secrets", {})
except Exception:
    _SECRETS = {}

# LangChain (مسارات مستقرة)
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_milvus import Milvus
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document

# يبني فهرس Milvus عند الحاجة (من merged_final.json)
from engine.build_store_milvus import build_milvus_if_needed


def _get(name: str, default=None):
    """قراءة القيم من st.secrets ثم من متغيرات البيئة."""
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
    """
    سلسلة سؤال/جواب بسيطة:
      - تستخدم history من واجهة الشات (للتحاور والتذكّر داخل الجلسة)
      - تحاول الاسترجاع من RAG (Milvus). لو وُجد سياق: تستخدمه وتذكر «المصدر».
      - لو ما وُجد سياق: تكمّل إجابة عامة بدون اختلاق مصادر.
    ترجع dict يحوي answer و context (قائمة Documents).
    """
    def __init__(self, llm: ChatOpenAI, retriever, prompt: PromptTemplate):
        self.llm = llm
        self.retriever = retriever
        self.prompt = prompt

    def _fmt_docs(self, docs: List[Document]) -> str:
        return "\n\n".join(d.page_content for d in docs)

    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            q = (inputs.get("input") or inputs.get("question") or "").strip()
            history = inputs.get("history", "").strip()
            if not q:
                return {"answer": "الرجاء كتابة سؤالك.", "context": []}

            # 1) استرجاع اختياري من RAG
            try:
                docs = self.retriever.get_relevant_documents(q)
            except Exception:
                docs = []

            ctx = self._fmt_docs(docs) if docs else ""

            # 2) بناء البرومبت (history + context + السؤال)
            prompt_text = self.prompt.format(history=history, context=ctx, question=q)

            # 3) نداء الـLLM
            msg = self.llm.invoke(prompt_text)
            ans = getattr(msg, "content", str(msg))

            # 4) لو فيه سياق من RAG اضف سطر مصدر (لو عندك metadata)
            if docs:
                # جرّب تجميع عناوين/روابط من الميتاداتا
                srcs = []
                for d in docs:
                    m = (getattr(d, "metadata", {}) or {})
                    title = m.get("title") or m.get("source")
                    url = m.get("url")
                    if title and url:
                        srcs.append(f"{title} — {url}")
                    elif title:
                        srcs.append(title)
                    elif url:
                        srcs.append(url)
                if srcs:
                    ans += "\n\nالمصدر: " + " | ".join(srcs)

            return {"answer": ans, "context": docs}

        except Exception as e:
            return {"answer": f"حدث خطأ غير متوقع: {e}", "context": []}


def create_qa_chain() -> SimpleQA:
    """إنشاء السلسلة: embeddings + Milvus retriever + Prompt + LLM"""
    cfg = _cfg()

    # يبني الفهرس تلقائيًا لو المجموعة فاضية/غير موجودة
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

    retriever = vector_store.as_retriever(search_kwargs={"k": cfg["RAG_TOP_K"]})

    # تعليمات المساعد: حوار + ذاكرة + RAG اختياري + ذكر المصدر عند وجوده
    system_ar = (
        "أنت «رقيم» مساعد مالي سعودي. تحاور بالعربية الفصحى."
        " استخدم المحادثة السابقة لتتذكر حقائق يذكرها المستخدم (مثل اسمه). "
        "إذا توفر سياق من قاعدة المعرفة فاعتمده للإجابة وأضف سطر «المصدر» في النهاية. "
        "إذا لم يتوفر سياق كافٍ، يجوز الإجابة بالمعرفة العامة بدون اختلاق مصادر."
    )

    prompt = PromptTemplate(
        input_variables=["history", "context", "question"],
        template=(
            f"{system_ar}\n\n"
            "[المحادثة السابقة]\n{history}\n\n"
            "[السياق (اختياري من RAG)]\n{context}\n\n"
            "[السؤال]\n{question}\n\n"
            "الجواب:"
        ),
    )

    llm = ChatOpenAI(
        model=cfg["MODEL_NAME"],
        temperature=cfg["TEMPERATURE"],
        openai_api_key=cfg["OPENAI_API_KEY"],
    )

    return SimpleQA(llm=llm, retriever=retriever, prompt=prompt)

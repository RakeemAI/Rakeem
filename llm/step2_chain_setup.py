# llm/step2_chain_setup.py
# RAG (read-only): يتصل بـ Milvus الجاهز ويستخدم history للمحادثة
# لا يوجد أي بناء/فهرسة هنا

import os
from typing import Dict, Any, List

# نحاول نقرأ من st.secrets (ستريمليت كلاود) أو من البيئة محليًا
try:
    import streamlit as st
    _SECRETS = getattr(st, "secrets", {})
except Exception:
    _SECRETS = {}

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_milvus import Milvus
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document


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
    """
    سلسلة سؤال/جواب:
      - تستخدم history من الواجهة (ذاكرة جلسة)
      - تسترجع من Milvus (إن وجد سياق) وتذكر «المصدر»
      - لو ما وُجد سياق كافٍ: تكمّل إجابة عامة بدون اختلاق مصادر
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
            history = (inputs.get("history") or "").strip()
            if not q:
                return {"answer": "الرجاء كتابة سؤالك.", "context": []}

            # 1) استرجاع اختياري من Milvus
            try:
                docs = self.retriever.get_relevant_documents(q)
            except Exception:
                docs = []

            ctx = self._fmt_docs(docs) if docs else ""

            # 2) البرومبت = history + context + السؤال
            prompt_text = self.prompt.format(history=history, context=ctx, question=q)

            # 3) LLM
            msg = self.llm.invoke(prompt_text)
            ans = getattr(msg, "content", str(msg))

            # 4) إلحاق المصادر (من metadata) إذا فيه سياق
            if docs:
                srcs = []
                for d in docs:
                    m = (getattr(d, "metadata", {}) or {})
                    title = m.get("title") or m.get("source")
                    if title:
                        srcs.append(title)
                if srcs:
                    ans += "\n\nالمصدر: " + " | ".join(dict.fromkeys(srcs))  # إزالة التكرار

            return {"answer": ans, "context": docs}
        except Exception as e:
            return {"answer": f"حدث خطأ غير متوقع: {e}", "context": []}


def create_qa_chain() -> SimpleQA:
    """
    يجهّز: Embeddings + Milvus retriever + Prompt + LLM
    (قراءة فقط من مجموعة Milvus الموجودة مسبقًا)
    """
    cfg = _cfg()

    # تحقق مبكّر من الأسرار الأساسية
    missing = [k for k in ("OPENAI_API_KEY","MILVUS_URI","MILVUS_TOKEN") if not cfg.get(k)]
    if missing:
        raise RuntimeError(f"مفاتيح مفقودة: {', '.join(missing)} — أضفها في Streamlit Secrets.")

    embeddings = OpenAIEmbeddings(
        model=cfg["EMBEDDING_MODEL"],
        openai_api_key=cfg["OPENAI_API_KEY"],
    )

    # فتح المجموعة الموجودة (لا ننشئ ولا نبني هنا)
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

    # تعليمات: حوار + ذاكرة + RAG اختياري
    system_ar = (
        "أنت «رقيم» مساعد مالي عربي. تحاور بالعربية الفصحى، "
        "واستخدم المحادثة السابقة لتتذكّر حقائق بسيطة يذكرها المستخدم (مثل اسمه). "
        "إذا توفر سياق من قاعدة المعرفة فاعتمد عليه وألحق «المصدر» في النهاية. "
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


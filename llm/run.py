# llm/run.py
# Orchestrates: Prompt engineering (Step1) + Retrieval/Chain (Step2) + Context formatting (Step3) + Response parsing (Step4)

from __future__ import annotations
import os
from typing import List, Dict, Any, Optional, Tuple

# --- LLM client (OpenAI) ---
from openai import OpenAI

# --- Step 1: Prompt engineering ---
from llm.step1_prompt_engineer import ArabicPromptEngineer

# --- Step 2: Retrieval / Chain setup (Milvus + LangChain) ---
# ملاحظة: داخل step2 عدّلنا المسارات لواجهات LangChain الحديثة، لذلك هنا نستخدم دوال step2 فقط
# الدوال المتوقعة: create_qa_chain(retriever, model_name) و build_retriever_if_needed() (اختياري)
try:
    from llm.step2_chain_setup import (
        create_qa_chain,
        build_retriever_if_needed,   # تبني/ترجع Retriever جاهز (Milvus) إن توفر
    )
except Exception:
    # لو step2 غير موجود/مختلف نكمّل بدون RAG
    create_qa_chain = None
    build_retriever_if_needed = None

# --- Step 3: Context formatter ---
# دالة لتجهيز النصوص الخام (شركة/مالية/زاتكا/سياق) ودمجها بشكل نظيف قبل تغذيتها للـ Prompt
try:
    from llm.step3_context_formatter import format_context
except Exception:
    def format_context(
        company_info: str = "",
        financial_data: str = "",
        legal_text: str = "",
        rag_snippets: str = "",
    ) -> str:
        chunks = []
        if company_info:
            chunks.append(f"## Company\n{company_info}")
        if financial_data:
            chunks.append(f"## Financials\n{financial_data}")
        if legal_text:
            chunks.append(f"## Regulations\n{legal_text}")
        if rag_snippets:
            chunks.append(f"## Retrieved\n{rag_snippets}")
        return "\n\n".join(chunks)

# --- Step 4: Response parser ---
# يحوّل مخرجات الـLLM إلى شكل موحّد {answer, sources, reasoning...}
try:
    from llm.step4_response_parser import parse_answer
except Exception:
    def parse_answer(raw_text: str, sources: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
        return {
            "answer": raw_text.strip(),
            "sources": sources or [],
        }

# ---------------------------------------------------------------------------------------
# إعدادات من المتغيرات البيئية (Streamlit Secrets أو .env)
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "800"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))

# مفاتيح Milvus (إن وُجدت — لو غير متوفرة، نشتغل بدون RAG)
MILVUS_URI = os.getenv("MILVUS_URI", "").strip()
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN", "").strip()
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "").strip()

# عميل OpenAI
_client = OpenAI()
# مهندس البرومبت
PROMPT = ArabicPromptEngineer()

# ---------------------------------------------------------------------------------------
def _format_docs_for_prompt(docs: List[Any]) -> Tuple[str, List[Dict[str, str]]]:
    """
    يحوّل Documents المسترجعة إلى نص لحقنه في البرومبت + مصفوفة مصادر لعرضها في الواجهة.
    نتوقع أن كل Doc لديه .page_content و metadata.get('source') و metadata.get('title')
    """
    if not docs:
        return "", []
    joined = []
    sources = []
    for i, d in enumerate(docs, 1):
        text = getattr(d, "page_content", str(d))
        meta = getattr(d, "metadata", {}) or {}
        src = meta.get("source") or meta.get("url") or meta.get("file", "N/A")
        title = meta.get("title") or src
        joined.append(f"[{i}] {title}\n{text}")
        sources.append({"id": i, "title": title, "source": src})
    return "\n\n".join(joined), sources
# --- أضف هاتين الدالتين بعد _format_docs_for_prompt مباشرةً ---

def _doc_similarity(doc) -> float:
    """
    يستخرج درجة تشابه موحّدة (0..1) من ميتاداتا المستند إن توفّرت:
    - similarity / sim / cosine_sim (0..1) → تُستخدم كما هي.
    - score (0..1) → نستخدمها كما هي إن كانت مطبّعة.
    - distance (0..1) → نحوّلها إلى تشابه عبر (1 - distance).
    - إن لم تتوفر أي قيمة صالحة → 0.0
    """
    meta = getattr(doc, "metadata", {}) or {}

    for key in ("similarity", "sim", "cosine_sim"):
        if key in meta:
            try:
                return float(meta[key])
            except Exception:
                pass

    if "score" in meta:
        try:
            s = float(meta["score"])
            if 0.0 <= s <= 1.0:
                return s
        except Exception:
            pass

    if "distance" in meta:
        try:
            d = float(meta["distance"])
            d = max(0.0, min(1.0, d))
            return 1.0 - d
        except Exception:
            pass

    return 0.0


def _filter_by_threshold(docs, min_sim: float = 0.50):
    """يرجع فقط المستندات ذات التشابه ≥ العتبة المحددة."""
    good = []
    for d in docs or []:
        if _doc_similarity(d) >= min_sim:
            good.append(d)
    return good


# --- استبدل دالة answer_question بالكامل بهذه النسخة ---

def answer_question(
    question: str,
    *,
    # هذه الثلاثة تُمرر من الواجهة (مقتطف تعريف الشركة ونص مالي مختصر ونص من لوائح الزكاة/الضريبة)
    company_info: str = "",
    financial_data: str = "",
    zatca_text: str = "",
    # لو عندك Retriever خارجي (من step2) مرّره؛ وإلا بنحاول نبنيه تلقائيًا إن توفرت بيئة Milvus
    retriever: Any | None = None,
    top_k: Optional[int] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """
    الدالة الرئيسية: تجمع السياق (RAG + بيانات الشركة) > تبني البرومبت > تنادي LLM > ترجع {answer, sources}
    """
    top_k = top_k or RAG_TOP_K

    # --- 1) Retrieval (اختياري) ---
    docs: List[Any] = []
    sources: List[Dict[str, str]] = []

    try:
        # لو ما جاء Retriever من الواجهة، وحاضرين مفاتيح Milvus، نجرب نبنيه من step2
        if retriever is None and build_retriever_if_needed and MILVUS_URI and MILVUS_COLLECTION:
            retriever = build_retriever_if_needed(
                uri=MILVUS_URI,
                token=MILVUS_TOKEN,
                collection=MILVUS_COLLECTION,
                k=top_k,
            )

        if retriever is not None:
            # بعض الـretrievers تستخدم .invoke أو .get_relevant_documents
            try:
                docs = retriever.get_relevant_documents(question)
            except Exception:
                docs = retriever.invoke(question)  # واجهة RunnableLC
    except Exception:
        # لو فشل RAG نكمل بدون ما نكسر التجربة
        docs = []

    # --- 2) فلترة نتائج RAG بعتبة التشابه (50%) ---
    MIN_SIM = 0.50
    filtered_docs = _filter_by_threshold(docs, MIN_SIM)

    if filtered_docs:
        rag_used = True
        rag_status = "ok"
    else:
        rag_used = False
        rag_status = "no_match"
        filtered_docs = []

    # نحول المستندات المفلترة إلى نص حقن + مصادر للواجهة
    rag_text, sources = _format_docs_for_prompt(filtered_docs)

    # (اختياري) توضيح داخلي للسياق إذا لم نجد تطابق من ZATCA — بدون إظهاره للمستخدم مباشرة
    # يمكنك حذف هذه الأسطر لو ما تبي تضيف الملاحظة للسياق:
    # if not rag_used and rag_status == "no_match":
    #     zatca_text = (zatca_text or "") + "\n[تنبيه نظامي] لا توجد إجابة مطابقة من قاعدة ZATCA لهذا السؤال."

    # --- 3) Build Prompt (Step1 + Step3) ---
    prompt = _pick_prompt(
        question=question,
        company_info=company_info,
        financial_data=financial_data,
        legal_text=zatca_text,
        rag_text=rag_text,
        allowed_values_text="",  # إن كان عندك قيود مسموحة مررها هنا
    )

    # --- 4) LLM Call ---
    raw = _llm_call(prompt, model=model, temperature=temperature, max_tokens=max_tokens)

    # --- 5) Parse (Step4) ---
    out = parse_answer(raw, sources=sources)
    if "answer" not in out:
        out["answer"] = raw
    if "sources" not in out:
        out["sources"] = sources

    # إشارات حالة RAG للواجهة/التشخيص
    out["rag_used"] = rag_used          # True/False
    out["rag_status"] = rag_status      # "ok" أو "no_match"
    return out

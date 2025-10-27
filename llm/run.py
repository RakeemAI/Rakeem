# llm/run.py
from __future__ import annotations
from typing import Tuple, List, Any, Dict
import os

from .step2_chain_setup import LangChainSetup
from .step1_prompt_engineer import ArabicPromptEngineer
from .step3_context_formatter import ContextFormatter


try:
    from .simple_backend import simple_retrieve, summarize_financial_df
except Exception:
    def simple_retrieve(q: str, k: int = 4): return []
    def summarize_financial_df(df): return {}

# ----------------- Utilities -----------------
def _format_fin_summary(fin: dict) -> str:
    if not fin:
        return ""
    parts = [
        "📊 ملخص مالي مختصر:",
        f"- إجمالي الإيرادات: {fin.get('total_revenue', 0):,.0f} SAR",
        f"- إجمالي المصروفات: {fin.get('total_expenses', 0):,.0f} SAR",
        f"- صافي الربح: {fin.get('total_profit', 0):,.0f} SAR",
        f"- التدفق النقدي: {fin.get('total_cashflow', 0):,.0f} SAR",
    ]
    if fin.get("period"):
        parts.append(f"- الفترة: {fin['period']}")
    return "\n".join(parts)

def make_allowed_values_text(df) -> str:
    try:
        import pandas as pd
        if df is None:
            return ""
        d = df.copy()
        d.columns = [str(c).strip().lower().replace(" ", "_") for c in d.columns]
        to_num = lambda name: pd.to_numeric(d.get(name), errors="coerce").fillna(0) if name in d.columns else None
        rev = to_num("revenue"); exp = to_num("expenses"); pro = to_num("profit"); cf = to_num("cash_flow")
        vat_c = to_num("vat_collected"); vat_p = to_num("vat_paid")
        lines = []
        if rev is not None: lines.append(f"- إجمالي الإيرادات = {float(rev.sum()):.2f}")
        if exp is not None: lines.append(f"- إجمالي المصروفات = {float(exp.sum()):.2f}")
        if pro is not None: lines.append(f"- صافي الربح = {float(pro.sum()):.2f}")
        if cf is not None:  lines.append(f"- التدفق النقدي = {float(cf.sum()):.2f}")
        if vat_c is not None and vat_p is not None:
            lines.append(f"- صافي ضريبة القيمة المضافة = {float(vat_c.sum() - vat_p.sum()):.2f}")
        return "\n".join(lines)
    except Exception:
        return ""

def _collect_sources_from_docs(docs: List[Any]) -> List[str]:
    sources = []
    for d in docs or []:
        src = None
        try:
            if hasattr(d, "metadata"):
                md = d.metadata
                src = (md.get("source") if isinstance(md, dict) else None)
        except Exception:
            pass
        if not src:
            src = "ZATCA"
        sources.append(src)
    # unique order-preserved
    return list(dict.fromkeys(sources))

# ----------------- Public API -----------------
def chat_answer(question: str, df=None, top_k: int = 4) -> Tuple[str, List[str]]:

    if not question or not isinstance(question, str):
        return "لم أتلقَّ سؤالاً صالحًا.", []

    # 1) ملخص مالي من DF
    fin = summarize_financial_df(df) if df is not None else {}
    fin_block = _format_fin_summary(fin)

    # 2) جهّز RAG/LLM
    used_llm = False
    llm_answer = ""
    rag_snips_block = ""
    sources: List[str] = []

    try:
        # تهيئة الـ LLM + الاسترجاع
        setup = LangChainSetup()
        llm_ok = setup.setup_llm()
        setup.setup_memory()
        setup.setup_retriever()

        # تنسيق السياقات
        fmt = ContextFormatter()

        # استرجاع نصوص عبر FAISS إن وُجد
        rag_payload = setup.get_context_from_rag(question)
        docs = []
        if isinstance(rag_payload, dict) and rag_payload.get("text"):
            # FAISS
            zatca_context = fmt.format_zatca_context(rag_payload.get("docs", []))
            docs = rag_payload.get("docs", [])
        else:
            # سقوط للبحث البسيط — ارجع مقتطفات يدوية
            hits = simple_retrieve(question, k=top_k)
            docs = [{"page_content": h.get("text", ""), "metadata": {"source": h.get("source", "ZATCA")}} for h in hits]
            zatca_context = fmt.format_zatca_context(docs)

        sources = _collect_sources_from_docs(docs)

        company_info = fmt.format_company_info(df) if df is not None else "⚠️ لا توجد معلومات شركة."
        financial_data = fmt.format_financial_context(df) if df is not None else "⚠️ لا توجد بيانات مالية."
        allowed_vals = make_allowed_values_text(df)

        # نبني برومبت مُقيد
        pe = ArabicPromptEngineer()
        prompt = pe.format_main_prompt(
            company_info=company_info,
            financial_data=financial_data,
            zatca_info=zatca_context,
            question=question,
            allowed_values_text=allowed_vals
        )

        if llm_ok:
            res = setup.ask_question_real(prompt)
            llm_answer = (res.get("answer") or "").strip()
            used_llm = True

        # نصّ المقتطفات (نعرضه دائمًا للشفافية)
        try:
            # نعيد استخراج المقتطفات كنقاط قصيرة
            snips = []
            for d in docs[:top_k]:
                txt = getattr(d, "page_content", None) or d.get("page_content") or ""
                if len(txt) > 900: txt = txt[:900] + "..."
                snips.append(f"- {txt}")
            if snips:
                rag_snips_block = "**مقتطفات ذات صلة من لوائح/إجابات ZATCA:**\n" + "\n".join(snips)
        except Exception:
            pass

    except Exception as e:
        # فشل كامل — نرجع أقل شيء مفيد
        return f"{fin_block}\n\nلم أستطع توليد شرح الآن: {e}\n", sources

    # 3) التجميع النهائي
    out_parts = []
    if fin_block:
        out_parts.append(fin_block)
    if used_llm and llm_answer:
        out_parts.append("**الشرح المختصر:**\n" + llm_answer)
    if rag_snips_block:
        out_parts.append(rag_snips_block)
    if not out_parts:
        out_parts.append("لم أعثر على معلومات كافية. ارفع/ي ملفك أو عدّل/ي السؤال.")
    if sources:
        out_parts.append("**المصادر:** " + " ، ".join(sources))

    return "\n\n".join(out_parts), sources

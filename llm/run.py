# llm/run.py
from __future__ import annotations
import os, json, glob, math
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import re

# ========= Optional: يستخدم LangChain للـ FAISS =========
_EMBED_READY = True
try:
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except Exception:
    _EMBED_READY = False

# ========= OpenAI =========
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# =========================
# Helpers: DF facts & periods
# =========================
def _safe_sum(series) -> float:
    try:
        return float(pd.to_numeric(series, errors="coerce").fillna(0).sum())
    except Exception:
        return 0.0

def _fmt_sar(x: float) -> str:
    try:
        return f"{float(x):,.0f} ريال"
    except Exception:
        return "0 ريال"

def _company_period(df: pd.DataFrame) -> str:
    if df is None or "date" not in df.columns:
        return ""
    d = pd.to_datetime(df["date"], errors="coerce")
    d = d[d.notna()]
    if d.empty:
        return ""
    return f"{d.min().date()} → {d.max().date()}"

def _df_facts(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    if df is None or df.empty:
        return {}
    facts: Dict[str, Any] = {}
    c = {c.lower().strip(): c for c in df.columns}
    rev = df[c.get("revenue")] if "revenue" in c else None
    exp = df[c.get("expenses")] if "expenses" in c else None
    pro = df[c.get("profit")] if "profit" in c else None
    cf  = df[c.get("cash_flow")] if "cash_flow" in c else None

    facts["total_revenue"]  = _safe_sum(rev) if rev is not None else 0.0
    facts["total_expenses"] = _safe_sum(exp) if exp is not None else 0.0
    facts["total_profit"]   = _safe_sum(pro) if pro is not None else 0.0
    facts["total_cashflow"] = _safe_sum(cf)  if cf  is not None else 0.0
    facts["period"] = _company_period(df)

    # اتجاهات بسيطة MoM (إن وُجد تاريخ)
    if "date" in df.columns:
        d = df[["date"]].copy()
        d["date"] = pd.to_datetime(d["date"], errors="coerce")
        d = d[d["date"].notna()]
        if not d.empty:
            df2 = df.copy()
            df2["date"] = pd.to_datetime(df2["date"], errors="coerce")
            df2 = df2[df2["date"].notna()]
            for col in ["revenue", "expenses", "profit", "cash_flow"]:
                if col in df2.columns:
                    s = pd.to_numeric(df2[col], errors="coerce").fillna(0)
                    # آخر قيمتين
                    if len(s) >= 2:
                        last = float(s.iloc[-1])
                        prev = float(s.iloc[-2])
                        delta = last - prev
                        pct = (delta / (prev if prev != 0 else 1)) * 100.0
                        facts[f"mom_{col}"] = {"last": last, "prev": prev, "delta": delta, "pct": pct}
    return facts


# =========================
# Forecast: Holt (من engine)
# =========================
def _forecast_snapshot(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    out = {"ok": False}
    if df is None or df.empty:
        return out
    try:
        from engine.forecasting_core import build_revenue_forecast
        target_col = "profit" if "profit" in df.columns else "revenue"
        fc = build_revenue_forecast(df, periods=3)
        if fc is None or fc.empty:
            return out
        last_actual = float(pd.to_numeric(df[target_col], errors="coerce").fillna(0).iloc[-1])
        next_pred   = float(pd.to_numeric(fc["forecast"], errors="coerce").fillna(0).iloc[-1])
        change_pct  = ((next_pred - last_actual) / (abs(last_actual) if last_actual != 0 else 1)) * 100.0
        trend = "ارتفاع" if change_pct > 0 else ("انخفاض" if change_pct < 0 else "استقرار")
        out.update({
            "ok": True,
            "target": target_col,
            "last_actual": last_actual,
            "next_pred": next_pred,
            "change_pct": change_pct,
            "trend": trend
        })
        return out
    except Exception:
        return out


# =========================
# RAG: فهرسة ملفات المشروع فعليًا
# =========================
def _collect_repo_texts() -> List[Tuple[str, str]]:
    """
    يرجّع [(path, text)] من ملفات المشروع المهمة لربط الـLLM بالسياق التقني.
    تشمل engine/, generator/, ui/app.py, llm/*.py (بدون هذا الملف لتفادي الدوران).
    """
    paths: List[str] = []
    paths += glob.glob("engine//*.py", recursive=True)
    paths += glob.glob("generator//*.py", recursive=True)
    paths += glob.glob("ui/app.py")  # مفيد لسياق الرسوم والتصميم العام
    paths += [p for p in glob.glob("llm/*.py") if not p.endswith("run.py")]  # بقية الـLLM

    out: List[Tuple[str, str]] = []
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                txt = f.read()
                if txt.strip():
                    out.append((p, txt))
        except Exception:
            continue
    return out

def _build_or_load_faiss(index_dir: str = "./data/rag_index") -> Tuple[Any, List[str]]:
    """
    يبني أو يحمل فهرس FAISS من ملفات المشروع.
    يرجّع (retriever_or_None, source_paths)
    """
    if not _EMBED_READY:
        return None, []

    os.makedirs(index_dir, exist_ok=True)
    idx_file = os.path.join(index_dir, "index.faiss")
    meta_file = os.path.join(index_dir, "index.pkl")

    try:
        if os.path.exists(idx_file) and os.path.exists(meta_file):
            # تحميل موجود
            embeddings = OpenAIEmbeddings(model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
                                          openai_api_key=os.getenv("OPENAI_API_KEY"))
            vs = FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)
            retriever = vs.as_retriever(search_kwargs={"k": int(os.getenv("RAG_TOP_K", "4"))})
            # حاول قراءة قائمة المصادر المخزّنة
            src_list = []
            try:
                with open(os.path.join(index_dir, "sources.json"), "r", encoding="utf-8") as f:
                    src_list = json.load(f)
            except Exception:
                pass
            return retriever, src_list

        # بناء جديد
        raw = _collect_repo_texts()
        if not raw:
            return None, []
        splitter = RecursiveCharacterTextSplitter(chunk_size=1600, chunk_overlap=150)
        docs, srcs = [], []
        for path, text in raw:
            for chunk in splitter.split_text(text):
                docs.append({"page_content": chunk, "metadata": {"source": path}})
                srcs.append(path)

        # حول docs إلى Document للكلاس
        from langchain.schema import Document
        lc_docs = [Document(page_content=d["page_content"], metadata=d["metadata"]) for d in docs]

        embeddings = OpenAIEmbeddings(model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
                                      openai_api_key=os.getenv("OPENAI_API_KEY"))
        vs = FAISS.from_documents(lc_docs, embedding=embeddings)
        vs.save_local(index_dir)

        # خزّن قائمة المسارات للمصادر
        try:
            uniq_srcs = list(dict.fromkeys(srcs))
            with open(os.path.join(index_dir, "sources.json"), "w", encoding="utf-8") as f:
                json.dump(uniq_srcs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        retriever = vs.as_retriever(search_kwargs={"k": int(os.getenv("RAG_TOP_K", "4"))})
        return retriever, list(dict.fromkeys(srcs))
    except Exception:
        return None, []


def _retrieve_context(retriever, query: str) -> Tuple[str, List[str]]:
    if retriever is None:
        return "", []
    try:
        docs = retriever.invoke(query)
        if not docs:
            return "", []
        take = docs[:4]
        txt = "\n\n".join(d.page_content[:1200] for d in take)
        srcs = list(dict.fromkeys([d.metadata.get("source", "repo") for d in take]))
        return txt, srcs
    except Exception:
        return "", []


# =========================
# Engine
# =========================
class RakeemChatEngine:
    """
    محرك محادثة احترافي 100% LLM:
    - يعتمد على ملف المستخدم (df) + RAG من ملفات المشروع.
    - السؤال الأول: يُظهر ملخص مالي + الشرح + التوصيات.
    - بقية الأسئلة: الشرح + التوصيات فقط.
    - إذا سأل عن "المصادر" تعرض فقط عند الطلب.
    - إذا سأل "اعرض الملخص المالي" يعرض الملخص فقط (كما في أول سؤال).
    """

    def __init__(self):
        self.history: List[Dict[str, str]] = []  # [ {role, content} ... ]
        self.client: Optional["OpenAI"] = None
        self.model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.temperature = float(os.getenv("TEMPERATURE", "0.15"))
        self.max_tokens = int(os.getenv("MAX_TOKENS", "1400"))
        # LLM
        self._init_llm()
        # RAG (فايس)
        self.retriever, self.repo_sources = _build_or_load_faiss()

    def _init_llm(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if OpenAI is None or not api_key:
            self.client = None
            return
        self.client = OpenAI(api_key=api_key)

    # ---------- Blocks ----------
    def _summary_block(self, company_name: str, facts: Dict[str, Any]) -> str:
        parts = []
        parts.append(f"<b>التحليل المالي للشركة: {company_name or 'شركة غير محددة'}</b><br><br>")
        parts.append("<b>ملخص مالي مختصر:</b>")
        parts.append("<ul>")
        parts.append(f"<li>إجمالي الإيرادات: {_fmt_sar(facts.get('total_revenue', 0))}</li>")
        parts.append(f"<li>إجمالي المصروفات: {_fmt_sar(facts.get('total_expenses', 0))}</li>")
        parts.append(f"<li>صافي الربح: {_fmt_sar(facts.get('total_profit', 0))}</li>")
        parts.append(f"<li>التدفق النقدي: {_fmt_sar(facts.get('total_cashflow', 0))}</li>")
        if facts.get("period"):
            parts.append(f"<li>الفترة: {facts['period']}</li>")
        parts.append("</ul>")
        return "\n".join(parts)

    def _allowed_values_text(self, facts: Dict[str, Any], fc: Dict[str, Any]) -> str:
        lines = []
        if facts:
            lines += [
                f"- إجمالي الإيرادات: {_fmt_sar(facts.get('total_revenue', 0))}",
                f"- إجمالي المصروفات: {_fmt_sar(facts.get('total_expenses', 0))}",
                f"- صافي الربح: {_fmt_sar(facts.get('total_profit', 0))}",
                f"- التدفق النقدي: {_fmt_sar(facts.get('total_cashflow', 0))}",
            ]
            if facts.get("period"):
                lines.append(f"- الفترة المغطاة: {facts['period']}")
            for key in ["revenue", "expenses", "profit", "cash_flow"]:
                mom = facts.get(f"mom_{key}")
                if mom:
                    lines.append(f"- التغير الشهري {key}: {mom['delta']:+.0f} ({mom['pct']:+.2f}%)")
        if fc.get("ok"):
            lines.append(f"- تنبؤ {fc['target']}: {_fmt_sar(fc['next_pred'])} ({fc['trend']}, {abs(fc['change_pct']):.2f}%)")
        return "\n".join(lines) if lines else "لا توجد قيم مسموح بها حالياً."

    def _build_prompt(self, user_q: str, facts: Dict[str, Any], fc: Dict[str, Any],
                      repo_context: str, is_followup: bool) -> str:
        """
        برومبت عربي صارم + تعليمات تنسيق.
        """
        allowed_text = self._allowed_values_text(facts, fc)
        forecast_text = ""
        if fc.get("ok"):
            forecast_text = (
                f"نتيجة التنبؤ (Holt): اتجاه {fc['trend']} متوقع في {fc['target']} "
                f"بنسبة تقريبية {abs(fc['change_pct']):.2f}%."
            )

        task_common = (
            "اكتب الرد بالعربية الفصحى، بصياغة احترافية، دون أي إيموجي أو زخرفة.\n"
            "التزم بالقيم المسموح بها فقط؛ لا تخترع أرقامًا جديدة. "
            "اربط الاستنتاجات مباشرة ببيانات المستخدم والتنبؤ إن توفر.\n"
            "صيغة الإخراج واجبة (بدون عناوين إضافية):\n"
            "<b>الشرح المختصر:</b>\n"
            "فقرة من 70–120 كلمة، تربط السؤال ببيانات df وبالمنطق المالي (وRAG عند الحاجة).\n"
            "<b>التوصيات:</b>\n"
            "• 3 إلى 5 نقاط عملية وواقعية وذات صلة مباشرة بالسؤال.\n"
        )

        first_extra = "" if is_followup else (
            "في إجابة السؤال الأول، ركّز على قراءة الاتجاه العام ثم قدّم توصيات مختصرة.\n"
        )

        prompt = (
            "أنت مستشار مالي عربي محترف. لديك:\n"
            "1) بيانات مالية فعلية من المستخدم (df).\n"
            "2) تنبؤ Holt مبني على df (إن توفر).\n"
            "3) سياق تقني/تشغيلي من ملفات المشروع (RAG).\n\n"
            f"القيم المسموح بها:\n{allowed_text}\n\n"
            f"سياق التنبؤ:\n{forecast_text or 'لا يوجد تنبؤ صالح.'}\n\n"
            f"سياق RAG (اختصار من ملفات المشروع):\n{repo_context[:2000]}\n\n"
            f"سؤال المستخدم: {user_q}\n\n"
            f"{task_common}{first_extra}"
        )
        return prompt

    # ---------- Public ----------
    def answer(self, question: str, df: Optional[pd.DataFrame] = None,
               company_name: str = "شركة غير محددة") -> Dict[str, Any]:
        if not question:
            return {"html": "لم أتلقَّ سؤالًا.", "sources": [], "is_first": False}

        low = question.strip().lower()
        is_first = len([m for m in self.history if m["role"] == "assistant"]) == 0

        facts = _df_facts(df) if df is not None else {}
        fc    = _forecast_snapshot(df) if df is not None else {"ok": False}

        # طلب مصادر صريح
        if any(w in low for w in ["مصادر", "المراجع", "source", "sources"]):
          _, rag_srcs = _retrieve_context(self.retriever, question)
          all_srcs = list(dict.fromkeys((rag_srcs or []) + [
              "البيانات المالية المرفوعة من المستخدم",
              "هيئة الزكاة والضريبة والجمارك (ZATCA)"
          ]))
          html = "<b>المصادر المتاحة:</b><ul>" + "".join(f"<li>{s}</li>" for s in all_srcs) + "</ul>"
          return {"html": html, "sources": all_srcs, "is_first": False}

        # طلب الملخص المالي صريح
        if "اعرض الملخص المالي" in question or "الملخص المالي" == question.strip():
          if not facts:
              return {"html": "لا توجد بيانات مالية لعرض الملخص.", "sources": [], "is_first": False}
          from engine.taxes import compute_vat, compute_zakat
          zakat = compute_zakat(df) if df is not None else 0
          vat = compute_vat(df) if df is not None else 0

          html = "<b>الملخص المالي:</b><ul>"
          html += f"<li>إجمالي الإيرادات: {_fmt_sar(facts.get('total_revenue', 0))}</li>"
          html += f"<li>إجمالي المصروفات: {_fmt_sar(facts.get('total_expenses', 0))}</li>"
          html += f"<li>صافي الربح: {_fmt_sar(facts.get('total_profit', 0))}</li>"
          html += f"<li>التدفق النقدي: {_fmt_sar(facts.get('total_cashflow', 0))}</li>"
          html += f"<li>الضريبة (VAT): {_fmt_sar(vat)}</li>"
          html += f"<li>الزكاة (Zakat): {_fmt_sar(zakat)}</li>"
          if facts.get("period"):
              html += f"<li>الفترة: {facts['period']}</li>"
          html += "</ul>"
          return {"html": html, "sources": ["البيانات المالية", "ZATCA"], "is_first": False}

        # سياق RAG
        rag_text, rag_sources = _retrieve_context(self.retriever, question)

        # برومبت
        prompt = self._build_prompt(question, facts, fc, rag_text, is_followup=not is_first)

        # لو ما فيه LLM
        if self.client is None:
            html = []
            if is_first and facts:
                html.append(self._summary_block(company_name, facts))
            html.append("<b>الشرح المختصر:</b>\nتمت معالجة السؤال محليًا لكن اتصال الـLLM غير متاح.")
            html.append("<b>التوصيات:</b>\n<ul><li>تفعيل اتصال النموذج.</li><li>إعادة المحاولة.</li></ul>")
            return {"html": "\n".join(html), "sources": rag_sources, "is_first": is_first}

        # نطلب من الـLLM
        try:
            msgs = [
                {"role": "system", "content": "أنت مستشار مالي عربي محترف، دقيق وعملي."},
                {"role": "user", "content": prompt}
            ]
            resp = self.client.chat.completions.create(
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=msgs,
            )
            llm_text = (resp.choices[0].message.content or "").strip()

            # ضبط التنسيق بقوة: ضمان سطر مستقل للعناوين
            def _normalize_blocks(txt: str) -> str:
              tx = txt.replace("\r", "")
              tx = tx.replace("<b>الشرح المختصر:</b>", "\n<b>الشرح المختصر:</b>\n")
              tx = tx.replace("<b>التوصيات:</b>", "\n<b>التوصيات:</b>\n")
              # ✅ إصلاح تكرار التوصيات: حول أي نقاط إلى <ul> واحدة فقط
              lines = [ln.strip("• ").strip() for ln in tx.splitlines() if ln.strip().startswith("•")]
              if lines:
                  bullet_html = "<ul>" + "".join(f"<li>{ln}</li>" for ln in lines) + "</ul>"
                  # نحذف النص الأصلي للنقاط لتفادي التكرار
                  tx = re.sub(r"•.*", "", tx)
                  tx = tx.strip() + "\n" + bullet_html
              return tx.strip()

            html_parts: List[str] = []
            if is_first and facts:
                html_parts.append(self._summary_block(company_name, facts))

            llm_text = _normalize_blocks(llm_text)

            # لو ما أدرج عنوان "التوصيات" نضمنه
            if "<b>التوصيات:</b>" not in llm_text:
                llm_text += "\n<b>التوصيات:</b>\n<ul><li>راقب المصروفات التشغيلية.</li><li>حسّن دورة التحصيل.</li><li>تابع اتجاه التدفق النقدي.</li></ul>"

            html_parts.append(llm_text)

            # ذاكرة محادثة خفيفة
            self.history.append({"role": "user", "content": question})
            self.history.append({"role": "assistant", "content": llm_text})

            # مصادر
            all_srcs = list(dict.fromkeys((rag_sources or []) + ["البيانات المالية المرفوعة من المستخدم"]))
            return {"html": "\n".join(html_parts), "sources": all_srcs, "is_first": is_first}

        except Exception as e:
            html = []
            if is_first and facts:
                html.append(self._summary_block(company_name, facts))
            html.append("<b>الشرح المختصر:</b>\nتعذر استدعاء النموذج.")
            html.append(f"<b>التوصيات:</b>\n<ul><li>الخطأ: {e}</li><li>تحقق من الإعدادات.</li></ul>")
            return {"html": "\n".join(html), "sources": rag_sources, "is_first": is_first}


rakeem_engine = RakeemChatEngine()
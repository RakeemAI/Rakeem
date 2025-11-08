# llm/run.py
from __future__ import annotations
import os, json, glob, math
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

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
# RAG: فهرسة ملفات المشروع
# =========================
def _collect_repo_texts() -> List[Tuple[str, str]]:
    paths: List[str] = []
    paths += glob.glob("engine//*.py", recursive=True)
    paths += glob.glob("generator//*.py", recursive=True)
    paths += glob.glob("ui/app.py")
    paths += [p for p in glob.glob("llm/*.py") if not p.endswith("run.py")]
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


def _build_or_load_faiss(index_dir: str = None) -> Tuple[Any, List[str]]:
    if not _EMBED_READY:
        return None, []

    env_path = os.getenv("RAG_STORE_PATH", "").strip() or "./Rakeem/data/rag_store"
    candidates = [env_path, "./data/rag_store", "./rag_store", "/mnt/data/rag_store"]
    zip_candidates = [os.path.join(p, "rag_store.zip") for p in [".", "./data", "./Rakeem/data", "/mnt/data"]]

    def _ensure_store_dir(p: str) -> str:
        if os.path.isdir(p):
            return p
        for zc in zip_candidates + ["/mnt/data/rag_store.zip"]:
            try:
                if os.path.exists(zc):
                    os.makedirs(p, exist_ok=True)
                    import zipfile
                    with zipfile.ZipFile(zc, "r") as z:
                        z.extractall(p)
                    return p
            except Exception:
                pass
        return p

    store_dir = None
    for c in candidates:
        d = _ensure_store_dir(c)
        if os.path.isdir(d):
            store_dir = d
            break
    if store_dir is None:
        return _build_or_load_repo_index()

    faiss_a = os.path.join(store_dir, "index.faiss")
    pkl_a   = os.path.join(store_dir, "index.pkl")
    faiss_b = os.path.join(store_dir, "faiss_index.bin")
    meta_b  = os.path.join(store_dir, "metadata.jsonl")
    jsonl_fallback = os.path.join(store_dir, "zatca_docs.jsonl")

    try:
        embeddings = OpenAIEmbeddings(model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
                                      openai_api_key=os.getenv("OPENAI_API_KEY"))

        if os.path.exists(faiss_a) and os.path.exists(pkl_a):
            vs = FAISS.load_local(store_dir, embeddings, allow_dangerous_deserialization=True)
            retriever = vs.as_retriever(search_kwargs={"k": int(os.getenv("RAG_TOP_K", "6"))})
            return retriever, ["ZATCA FAISS (index.faiss/index.pkl)"]

        if os.path.exists(faiss_b) and os.path.exists(meta_b):
            from langchain.schema import Document
            docs = []
            with open(meta_b, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        o = json.loads(line.strip())
                    except Exception:
                        continue
                    content = (o.get("text") or o.get("answer") or "").strip()
                    if not content:
                        continue
                    src = (o.get("source") or o.get("topic") or "ZATCA").strip()
                    docs.append(Document(page_content=content, metadata={"source": src}))

            if not docs and os.path.exists(jsonl_fallback):
                docs = _docs_from_jsonl(jsonl_fallback)

            if docs:
                vs = FAISS.from_documents(docs, embedding=embeddings)
                vs.save_local(store_dir)
                retriever = vs.as_retriever(search_kwargs={"k": int(os.getenv("RAG_TOP_K", "6"))})
                return retriever, ["ZATCA FAISS (rebuilt from metadata.jsonl)"]

        if os.path.exists(jsonl_fallback):
            docs = _docs_from_jsonl(jsonl_fallback)
            if docs:
                vs = FAISS.from_documents(docs, embedding=embeddings)
                vs.save_local(store_dir)
                retriever = vs.as_retriever(search_kwargs={"k": int(os.getenv("RAG_TOP_K", "6"))})
                return retriever, ["ZATCA JSONL (built to FAISS)"]

        return _build_or_load_repo_index()

    except Exception:
        return _build_or_load_repo_index()


def _docs_from_jsonl(path: str):
    from langchain.schema import Document
    docs = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                text = (o.get("text") or o.get("answer") or "").strip()
                src  = (o.get("source") or o.get("topic") or "ZATCA").strip()
                if text:
                    docs.append(Document(page_content=text, metadata={"source": src}))
    except Exception:
        pass
    return docs


def _build_or_load_repo_index() -> Tuple[Any, List[str]]:
    try:
        raw = _collect_repo_texts()
        if not raw:
            return None, []
        splitter = RecursiveCharacterTextSplitter(chunk_size=1600, chunk_overlap=150)
        from langchain.schema import Document
        docs, srcs = [], []
        for path, text in raw:
            for chunk in splitter.split_text(text):
                docs.append(Document(page_content=chunk, metadata={"source": path}))
                srcs.append(path)

        embeddings = OpenAIEmbeddings(model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
                                      openai_api_key=os.getenv("OPENAI_API_KEY"))
        vs = FAISS.from_documents(docs, embedding=embeddings)
        vs.save_local("./data/rag_index")
        retriever = vs.as_retriever(search_kwargs={"k": int(os.getenv("RAG_TOP_K", "4"))})
        return retriever, list(dict.fromkeys(srcs))
    except Exception:
        return None, []


# =========================
# Retrieval Context Helper
# =========================
def _retrieve_context(retriever, query: str) -> Tuple[str, List[str]]:
    """Fetch top documents from retriever (FAISS / JSONL / repo) with graceful fallbacks."""
    if retriever is None:
        return "", []
    try:
        try:
            docs = retriever.invoke(query)
        except Exception:
            docs = retriever.get_relevant_documents(query)
        if not docs:
            return "", []
        selected = docs[:4]
        combined_text = "\n\n".join(
            (getattr(d, "page_content", "") or "")[:1200] for d in selected if d
        )
        sources = list(
            dict.fromkeys(
                [
                    (getattr(getattr(d, "metadata", {}), "get", lambda *_: "غير محدد")("source"))
                    for d in selected
                ]
            )
        )
        return combined_text, sources
    except Exception:
        return "", []


# =========================
# Engine
# =========================
class RakeemChatEngine:
    def __init__(self):
        self.history: List[Dict[str, str]] = []
        self.client: Optional["OpenAI"] = None
        self.model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.temperature = float(os.getenv("TEMPERATURE", "0.15"))
        self.max_tokens = int(os.getenv("MAX_TOKENS", "1400"))
        self._init_llm()
        self.retriever, self.repo_sources = _build_or_load_faiss()

    def _init_llm(self):
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if (OpenAI and api_key) else None

    def _summary_block(self, company_name: str, facts: Dict[str, Any]) -> str:
        parts = [
            f"<b>التحليل المالي للشركة: {company_name or 'شركة غير محددة'}</b><br><br>",
            "<b>ملخص مالي مختصر:</b>",
            "<ul>",
            f"<li>إجمالي الإيرادات: {_fmt_sar(facts.get('total_revenue', 0))}</li>",
            f"<li>إجمالي المصروفات: {_fmt_sar(facts.get('total_expenses', 0))}</li>",
            f"<li>صافي الربح: {_fmt_sar(facts.get('total_profit', 0))}</li>",
            f"<li>التدفق النقدي: {_fmt_sar(facts.get('total_cashflow', 0))}</li>",
        ]
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
        allowed_text = self._allowed_values_text(facts, fc)
        forecast_text = ""
        if fc.get("ok"):
            forecast_text = (
                f"نتيجة التنبؤ (Holt): اتجاه {fc['trend']} متوقع في {fc['target']} "
                f"بنسبة تقريبية {abs(fc['change_pct']):.2f}%."
            )
        task_common = (
            "اكتب الرد بالعربية الفصحى، بصياغة احترافية، دون أي إيموجي أو زخرفة.\n"
            "التزم بالقيم المسموح بها فقط؛ لا تخترع أرقامًا جديدة.\n"
            "صيغة الإخراج واجبة:\n"
            "<b>الشرح المختصر:</b>\n"
            "فقرة من 70–120 كلمة.\n"
            "<b>التوصيات:</b>\n"
            "• 3 إلى 5 نقاط عملية مباشرة.\n"
        )
        first_extra = "" if is_followup else "في إجابة السؤال الأول، ركّز على الاتجاه العام ثم قدم توصيات.\n"
        return (
            "أنت مستشار مالي عربي محترف.\n"
            "1) بيانات مالية من المستخدم.\n"
            "2) تنبؤ Holt.\n"
            "3) سياق RAG.\n\n"
            f"القيم:\n{allowed_text}\n\n"
            f"سياق التنبؤ:\n{forecast_text or 'لا يوجد تنبؤ.'}\n\n"
            f"سياق RAG:\n{repo_context[:2000]}\n\n"
            f"سؤال المستخدم: {user_q}\n\n"
            f"{task_common}{first_extra}"
        )

    # ---------- Public ----------
    def answer(self, question: str, df: Optional[pd.DataFrame] = None,
               company_name: str = "شركة غير محددة") -> Dict[str, Any]:
        if not question:
            return {"html": "لم أتلقَّ سؤالًا.", "sources": [], "is_first": False}

        low = question.strip().lower()
        is_first = len([m for m in self.history if m["role"] == "assistant"]) == 0
        facts = _df_facts(df) if df is not None else {}
        fc    = _forecast_snapshot(df) if df is not None else {"ok": False}

        if any(w in low for w in ["مصادر", "المراجع", "source", "sources"]):
            _, rag_srcs = _retrieve_context(self.retriever, question)
            all_srcs = list(dict.fromkeys((rag_srcs or []) + ["البيانات المالية"]))
            html = "<b>المصادر:</b><ul>" + "".join(f"<li>{s}</li>" for s in all_srcs) + "</ul>"
            return {"html": html, "sources": all_srcs, "is_first": False}

        if "اعرض الملخص المالي" in question or "الملخص المالي" == question.strip():
            if not facts:
                return {"html": "لا توجد بيانات مالية.", "sources": [], "is_first": False}
            return {"html": self._summary_block(company_name, facts), "sources": ["البيانات المالية"], "is_first": False}

        rag_text, rag_sources = _retrieve_context(self.retriever, question)

        # ✅ هنا التعديل الجديد
        tax_keywords = ["ضريبة", "الضريبة", "زكاة", "الزكاة", "تهرب", "التهرب", "مخالفة", "غرامة", "إقرار", "فاتورة"]
        is_tax_query = any(w in question for w in tax_keywords)

        if is_tax_query:
          prompt = f"""
أنت خبير ضريبي سعودي متخصص في أنظمة هيئة الزكاة والضريبة والجمارك (ZATCA).

استخدم حصريًا النصوص التالية للإجابة بدقة على السؤال أدناه. لا تضف أو تخترع أي معلومات من خارجها.
إذا لم يكن النص يحتوي على الإجابة، قل بوضوح: "لم يرد في مستندات الهيئة نص محدد بخصوص هذا الموضوع."

المراجع القانونية المتاحة (من قاعدة ZATCA):
--------------------------------
{rag_text or 'لم يتم العثور على أي نصوص ذات صلة.'}
--------------------------------

السؤال:
{question}

اكتب الرد بالعربية الفصحى الرسمية بأسلوب تقريري واضح.
<b>الشرح المختصر:</b>
اشرح بإيجاز النقاط النظامية الدقيقة المتعلقة بالسؤال استنادًا للنصوص أعلاه.
<b>التوصيات:</b>
• 2 إلى 4 توصيات عملية لضمان الامتثال أو التصحيح وفق النظام.
"""

        else:
            prompt = self._build_prompt(question, facts, fc, rag_text, is_followup=not is_first)

        if self.client is None:
            html = ["<b>الشرح المختصر:</b>\nاتصال النموذج غير متاح."]
            html.append("<b>التوصيات:</b>\n<ul><li>تفعيل الاتصال وإعادة المحاولة.</li></ul>")
            return {"html": "\n".join(html), "sources": rag_sources, "is_first": is_first}

        try:
            msgs = [
                {"role": "system", "content": "أنت مستشار مالي عربي محترف، دقيق وعملي."},
                {"role": "user", "content": prompt},
            ]
            resp = self.client.chat.completions.create(
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=msgs,
            )
            llm_text = (resp.choices[0].message.content or "").strip()

            def _normalize_blocks(txt: str) -> str:
              import re
              tx = (txt or "").replace("\r", "").strip()

              # --- Normalize both headers ---
              tx = re.sub(r"\s*الشرح\s*المختصر\s*[:：]?\s*", "<b>الشرح المختصر:</b>\n", tx, flags=re.I)
              tx = re.sub(r"\s*التوصيات\s*[:：]?\s*", "<b>التوصيات:</b>\n", tx, flags=re.I)

              # --- Extract any recommendations block content ---
              rec_block_html = ""
              m = re.search(
                  r"(?:<b>\s*التوصيات\s*:\s*</b>|التوصيات\s*[:：]|نصائح\s*[:：]|Recommendations\s*:)(.*)$",
                  tx,
                  flags=re.S | re.I,
              )
              if m:
                  tail = m.group(1)
                  bullets = []
                  for ln in tail.splitlines():
                      ln = ln.strip()
                      if not ln:
                          continue
                      if re.match(r"^[\-\u2022•]\s+", ln) or re.match(r"^\d+\.\s+", ln) or ln.startswith("<li>"):
                          ln = re.sub(r"^[\-\u2022•]\s+|\d+\.\s+", "", ln)
                          ln = re.sub(r"</?li>", "", ln)
                          bullets.append(ln)
                  bullets = [b for b in bullets if b][:5]
                  if bullets:
                      rec_block_html = "\n\n<b>التوصيات:</b>\n<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"

              # --- Remove all old recommendations sections from text ---
              tx = re.sub(
                  r"(?:<b>\s*التوصيات\s*:\s*</b>|التوصيات\s*[:：]|نصائح\s*[:：]|Recommendations\s*:).*",
                  "",
                  tx,
                  flags=re.S | re.I,
              ).strip()

              # --- Ensure both sections appear cleanly on their own lines ---
              if "<b>الشرح المختصر:</b>" not in tx:
                  tx = "<b>الشرح المختصر:</b>\n" + tx

              # Add spacing before each header to separate visually
              tx = tx.replace("<b>الشرح المختصر:</b>", "\n<b>الشرح المختصر:</b>\n")
              tx = tx.replace("<b>التوصيات:</b>", "\n<b>التوصيات:</b>\n")

              if rec_block_html:
                  tx = tx.strip() + "\n" + rec_block_html

              return tx.strip()




            html_parts = []
            if is_first and facts:
                html_parts.append(self._summary_block(company_name, facts))
            llm_text = _normalize_blocks(llm_text)
            if "<b>التوصيات:</b>" not in llm_text:
                llm_text += "\n<b>التوصيات:</b>\n<ul><li>تابع الأداء المالي.</li></ul>"
            html_parts.append(llm_text)
            self.history += [{"role": "user", "content": question}, {"role": "assistant", "content": llm_text}]
            all_srcs = list(dict.fromkeys((rag_sources or []) + ["البيانات المالية"]))
            return {"html": "\n".join(html_parts), "sources": all_srcs, "is_first": is_first}

        except Exception as e:
            html = ["<b>الشرح المختصر:</b>\nتعذر استدعاء النموذج.", f"<b>التوصيات:</b>\n<ul><li>الخطأ: {e}</li></ul>"]
            return {"html": "\n".join(html), "sources": rag_sources, "is_first": is_first}


rakeem_engine = RakeemChatEngine()

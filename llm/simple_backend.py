from __future__ import annotations
import os, json, re
from typing import List, Dict, Tuple, Optional

_WORD = re.compile(r"\w+", re.UNICODE)

def _zatca_path() -> str:
    here = os.path.dirname(__file__)
    return os.path.normpath(os.path.join(here, "..", "data", "zatca_docs.jsonl"))

def load_zatca() -> List[Dict]:
    path = _zatca_path()
    if not os.path.exists(path): return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                o = json.loads(line)
            except Exception:
                continue
            text = (o.get("text") or o.get("answer") or "").strip()
            src  = (o.get("source") or o.get("topic") or "ZATCA").strip()
            if text:
                out.append({"text": text, "source": src})
    return out

def simple_retrieve(query: str, k: int = 4) -> List[Dict]:
    qs = set(w.lower() for w in _WORD.findall(query) if len(w) > 1)
    scored = []
    corpus = load_zatca()
    for d in corpus:
        bag = set(w.lower() for w in _WORD.findall(d["text"]) if len(w) > 1)
        inter = len(qs & bag)
        union = max(1, len(qs | bag))
        jaccard = inter / union  # 0..1
        if jaccard > 0:
            dd = dict(d)
            dd["similarity"] = jaccard  # تقرأها run._doc_similarity
            scored.append((jaccard, dd))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:k]]


def summarize_financial_df(df) -> Dict:
    import pandas as pd
    def s(x): return float(pd.Series(x).fillna(0).sum())
    out = {
        "total_revenue": s(df.get("revenue")) if hasattr(df, "get") else 0.0,
        "total_expenses": s(df.get("expenses")) if hasattr(df, "get") else 0.0,
        "total_profit": s(df.get("profit")) if hasattr(df, "get") else 0.0,
        "total_cashflow": s(df.get("cash_flow")) if hasattr(df, "get") else 0.0,
        "avg_margin": 0.0,
    }
    try:
        import pandas as pd
        out["avg_margin"] = float(pd.Series(df.get("profit_margin")).fillna(0).mean())
        if "date" in getattr(df, "columns", []):
            d = pd.to_datetime(df["date"], errors="coerce")
            if d.notna().any():
                out["period"] = f"{d.min().date()} → {d.max().date()}"
    except Exception:
        pass
    return out

def answer(query: str, df=None, top_k: int = 4) -> Tuple[str, List[str]]:
    hits = simple_retrieve(query, k=top_k)
    sources, rag_snippets = [], []
    for h in hits:
        sources.append(h["source"])
        rag_snippets.append(f"- {h['text'][:900]}")
    fin = summarize_financial_df(df) if df is not None else {}

    parts = []
    if fin and any(fin.values()):
        parts.append(
            "**ملخص مالي مختصر:**\n"
            f"- إجمالي الإيرادات: {fin.get('total_revenue', 0):,.0f} SAR\n"
            f"- إجمالي المصروفات: {fin.get('total_expenses', 0):,.0f} SAR\n"
            f"- صافي الربح: {fin.get('total_profit', 0):,.0f} SAR\n"
            f"- التدفق النقدي: {fin.get('total_cashflow', 0):,.0f} SAR\n"
            + (f"- الفترة: {fin.get('period')}\n" if fin.get("period") else "")
        )
    if rag_snippets:
        parts.append("**مقتطفات ذات صلة من لوائح/إجابات ZATCA:**\n" + "\n".join(rag_snippets))
    if not parts:
        parts.append("لم أعثر على معلومات كافية. ارفعي ملفك المالي أو عدّلي صياغة السؤال.")

    if sources:
        uniq = list(dict.fromkeys(sources))
        parts.append("**المصادر:** " + " ، ".join(uniq))

    return "\n\n".join(parts), list(dict.fromkeys(sources))
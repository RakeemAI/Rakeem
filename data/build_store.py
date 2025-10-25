# rag/build_store.py
from __future__ import annotations
import os, json, argparse
from typing import List, Dict
from dotenv import load_dotenv

def load_docs(jsonl_path: str) -> List[Dict]:
    docs = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                o = json.loads(ln)
            except Exception:
                continue
            text = (o.get("text") or o.get("answer") or "").strip()
            src  = (o.get("source") or o.get("topic") or "ZATCA").strip()
            if text:
                docs.append({"text": text, "source": src})
    if not docs:
        raise RuntimeError(f"No valid documents in {jsonl_path}")
    return docs

def main():
    load_dotenv(override=True)
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings
    from langchain.docstore.document import Document

    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", default="./data/zatca_docs.jsonl")
    ap.add_argument("--out",   default="./data/rag_store")
    ap.add_argument("--model", default=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    args = ap.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    os.makedirs(args.out, exist_ok=True)

    raw = load_docs(args.jsonl)
    docs = [Document(page_content=d["text"], metadata={"source": d["source"]}) for d in raw]

    embeddings = OpenAIEmbeddings(openai_api_key=api_key, model=args.model)
    vs = FAISS.from_documents(docs, embeddings)
    vs.save_local(args.out)  # سيولّد index.faiss + index.pkl

    print(f"✅ Built FAISS store with {len(docs)} docs @ {os.path.abspath(args.out)}")

if __name__ == "__main__":
    main()

# llm/step2_chain_setup.py
# Updated: RAG accuracy improvements (normalization, reranking, filtering, compression)
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain.chat_models import ChatOpenAI
import os, re, zipfile, tempfile, json


# ---------------------------------------------------------------------
# 🔹 Arabic Normalization Helper (inlined — no new file)
# ---------------------------------------------------------------------
def _normalize_arabic(text: str) -> str:
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"ؤ", "و", text)
    text = re.sub(r"ئ", "ي", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"[ًٌٍَُِّْـ]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------
# 🔹 Safe FAISS Loader
# ---------------------------------------------------------------------
def _build_or_load_faiss(rag_store_path: str):
    os.makedirs(rag_store_path, exist_ok=True)
    index_path = os.path.join(rag_store_path, "faiss_index.bin")
    meta_path = os.path.join(rag_store_path, "metadata.jsonl")

    if not os.path.exists(index_path):
        # Extract from zip if missing
        zip_path = os.path.join(os.path.dirname(__file__), "../data/rag_store.zip")
        if os.path.exists(zip_path):
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(rag_store_path)
        else:
            raise FileNotFoundError("RAG store not found in ./data/rag_store.zip")

    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = [json.loads(line) for line in f]

    return index_path, metadata


# ---------------------------------------------------------------------
# 🔹 Reranking Logic (simple cosine-based)
# ---------------------------------------------------------------------
def _rerank(query, docs, embedding):
    q_vec = embedding.embed_query(_normalize_arabic(query))
    scored = []
    for d in docs:
        d_vec = embedding.embed_query(_normalize_arabic(d.page_content))
        sim = sum(a * b for a, b in zip(q_vec, d_vec))
        scored.append((d, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [d for d, _ in scored[:3]]


# ---------------------------------------------------------------------
# 🔹 Retriever Builder
# ---------------------------------------------------------------------
def build_retriever(rag_store_path: str = "./Rakeem/data/rag_store"):
    embedding = OpenAIEmbeddings()
    index_path, metadata = _build_or_load_faiss(rag_store_path)

    # Load FAISS store safely
    vectorstore = FAISS.load_local(
        rag_store_path,
        embeddings=embedding,
        allow_dangerous_deserialization=True
    )

    base_retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 20})

    # 🔹 Context compression
    compressor_llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)
    compressor = LLMChainExtractor.from_llm(compressor_llm)
    retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=base_retriever)

    # Wrap with reranker
    def enhanced_search(query: str, k: int = 3):
        hits = retriever.get_relevant_documents(_normalize_arabic(query))
        hits = _rerank(query, hits, embedding)

        # 🔹 Context filtering (ZATCA-aware)
        if "الزكاة" in query:
            hits = [h for h in hits if "zakat" in h.metadata.get("topic", "").lower()]
        elif "ضريبة" in query or "vat" in query.lower():
            hits = [h for h in hits if "vat" in h.metadata.get("topic", "").lower()]

        return hits[:k]

    return enhanced_search


# ---------------------------------------------------------------------
# 🔹 Quick Test
# ---------------------------------------------------------------------
if __name__ == "__main__":
    retriever = build_retriever()
    q = "ما هي نسبة ضريبة القيمة المضافة في السعودية؟"
    results = retriever(q)
    for i, r in enumerate(results, 1):
        print(f"[{i}] {r.metadata.get('source', '')}: {r.page_content[:200]}...")

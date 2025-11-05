# engine/build_store_milvus.py
import os, json
from langchain_openai import OpenAIEmbeddings
from langchain_milvus import Milvus
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document

MILVUS_URI = os.getenv("MILVUS_URI", "./milvus_rag.db")
COLLECTION = os.getenv("MILVUS_COLLECTION", "rakeem_rag_v1")
SOURCE_PATH = os.getenv("RAG_SOURCE_JSON", "./Rakeem/data/merged_final.json")

def build_milvus():
    with open(SOURCE_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    docs = []
    for it in items:
        q, a = it.get("Q"), it.get("A")
        text = f"سؤال: {q}\nإجابة: {a}" if q and a else json.dumps(it, ensure_ascii=False)
        meta = {
            "title": it.get("Topic") or it.get("title"),
            "source": it.get("Source") or it.get("source"),
            "url": it.get("url"),
        }
        for chunk in splitter.split_text(text):
            docs.append(Document(page_content=chunk, metadata=meta))

    emb = OpenAIEmbeddings(model="text-embedding-3-small")
    Milvus.from_documents(
        documents=docs,
        embedding=emb,
        collection_name=COLLECTION,
        connection_args={"uri": MILVUS_URI},
    )

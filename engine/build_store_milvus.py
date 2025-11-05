# engine/build_store_milvus.py

import os
import json
from openai import OpenAI
from pymilvus import MilvusClient, DataType

def build_milvus_if_needed():
    milvus_uri = os.getenv("MILVUS_URI")
    milvus_token = os.getenv("MILVUS_TOKEN")
    milvus_collection = os.getenv("MILVUS_COLLECTION", "rakeem_rag_v1")
    rag_source = os.getenv("RAG_SOURCE_JSON", "./Rakeem/data/merged_final.json")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Connect to Milvus
    milvus = MilvusClient(uri=milvus_uri, token=milvus_token)

    # Create collection if not exists
    if milvus_collection not in milvus.list_collections():
        print(f"Creating collection: {milvus_collection}")
        milvus.create_collection(
            collection_name=milvus_collection,
            fields=[
                {"name": "id", "type": DataType.INT64, "is_primary": True, "auto_id": True},
                {"name": "text", "type": DataType.VARCHAR, "max_length": 2048},
                {"name": "embedding", "type": DataType.FLOAT_VECTOR, "dim": 1536},
            ]
        )

    # Load RAG data
    with open(rag_source, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Convert each QA into embeddings
    texts = [f"Q: {d['Q']}\nA: {d['A']}" for d in data]
    embeddings = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    ).data

    vectors = [e.embedding for e in embeddings]
    entities = [{"text": t, "embedding": v} for t, v in zip(texts, vectors)]

    # Insert into Milvus
    milvus.insert(collection_name=milvus_collection, data=entities)
    print(f"✅ Inserted {len(entities)} documents into {milvus_collection}")

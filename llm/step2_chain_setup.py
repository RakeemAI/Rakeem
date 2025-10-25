# llm/step2_chain_setup.py
import os
from dotenv import load_dotenv

# نستخدم حزمة OpenAI الجديدة
from openai import OpenAI

load_dotenv(override=True)

class LangChainSetup:
    """
    تهيئة LLM + RAG:
    - يحمّل FAISS من ./data (index.faiss, index.pkl) إن وُجد.
    - إن لم توجد، يرجع إلى RAG بسيط عبر zatca_docs.jsonl.
    """
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        # ✅ ثبّت المودل الافتراضي على gpt-4o-mini
        self.model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.temperature = float(os.getenv("TEMPERATURE", "0.2"))
        # ✅ ارفع حد الخرج لمنع القصّ
        self.max_tokens = int(os.getenv("MAX_TOKENS", "6000"))

        self.rag_store_path = os.getenv("RAG_STORE_PATH", "./data")
        self.jsonl_path     = os.getenv("ZATCA_JSONL_PATH", "./data/zatca_docs.jsonl")

        self.client: OpenAI | None = None
        self.memory = []
        self.retriever = None
        self.documents = []  # عند RAG البسيط

    # ---------------- LLM ----------------
    def setup_llm(self):
        if not self.api_key:
            print("⚠️ OPENAI_API_KEY غير موجود في .env")
            return False
        # ✅ عميل OpenAI بصيغته الحديثة
        self.client = OpenAI(api_key=self.api_key)
        print(f"✅ OpenAI جاهز - النموذج: {self.model_name} - max_tokens={self.max_tokens}")
        return True

    def setup_memory(self):
        self.memory = []
        return True

    # ---------------- RAG ----------------
    def setup_retriever(self):
        try:
            from langchain_community.vectorstores import FAISS
            from langchain_openai import OpenAIEmbeddings

            index_file = os.path.join(self.rag_store_path, "index.faiss")
            if not os.path.exists(index_file):
                print(f"⚠️ لا يوجد {index_file} — سنستخدم RAG بسيط")
                return self._load_simple_rag()

            embeddings = OpenAIEmbeddings(
                openai_api_key=self.api_key,
                model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            )
            vectorstore = FAISS.load_local(
                self.rag_store_path,
                embeddings,
                allow_dangerous_deserialization=True
            )
            top_k = int(os.getenv("RAG_TOP_K", "3"))
            self.retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
            print(f"✅ تم تحميل FAISS من {self.rag_store_path} (TopK={top_k})")
            return True

        except ImportError:
            print("⚠️ langchain غير متاح — استخدام RAG بسيط")
            return self._load_simple_rag()
        except Exception as e:
            print(f"⚠️ فشل تحميل RAG (FAISS): {e}")
            return self._load_simple_rag()

    def _load_simple_rag(self):
        try:
            import json
            if not os.path.exists(self.jsonl_path):
                print(f"⚠️ ملف المستندات غير موجود: {self.jsonl_path}")
                self.retriever = None
                return False

            self.documents = []
            with open(self.jsonl_path, "r", encoding="utf-8") as f:
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
                        self.documents.append({"text": text, "source": src})

            self.retriever = "simple"
            print(f"✅ تم تحميل {len(self.documents)} مستند (RAG بسيط)")
            return True

        except Exception as e:
            print(f"⚠️ فشل تحميل المستندات البسيطة: {e}")
            self.retriever = None
            return False

    def get_context_from_rag(self, question):
        if not self.retriever:
            return None
        try:
            if self.retriever != "simple":
                docs = self.retriever.invoke(question)
                if docs:
                    ctx = "\n\n".join([doc.page_content for doc in docs[:3]])
                    return {"text": ctx, "docs": docs[:3]}
                return None
            else:
                return None
        except Exception as e:
            print(f"⚠️ خطأ في الاسترجاع: {e}")
            return None

    # ---------------- سؤال فعلي للـ LLM ----------------
    def ask_question_real(self, prompt, context=None):
        if not self.client:
            return {"answer": "خطأ: LLM غير مهيأ", "source_documents": []}
        try:
            rag_payload = self.get_context_from_rag(prompt) if self.retriever else None

            full_prompt = prompt
            if context:
                full_prompt = f"السياق:\n{context}\n\nالسؤال:\n{prompt}"
            elif isinstance(rag_payload, dict) and rag_payload.get("text"):
                full_prompt = f"المعلومات من قاعدة المعرفة:\n{rag_payload['text']}\n\nالسؤال:\n{prompt}"

            messages = []
            if self.memory:
                messages.extend(self.memory[-4:])
            messages.append({"role": "user", "content": full_prompt})

            # ✅ استدعاء بصيغة OpenAI الحديثة
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,  # رفعناها لمنع القصّ
            )
            answer = resp.choices[0].message.content or ""

            self.memory.extend([
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": answer}
            ])

            return {
                "answer": answer,
                "source_documents": (rag_payload.get("docs") if isinstance(rag_payload, dict) else []),
                "used_rag": bool(rag_payload)
            }

        except Exception as e:
            msg = f"خطأ في الاستدعاء: {e}"
            print(f"❌ {msg}")
            return {"answer": msg, "source_documents": []}

    def clear_memory(self):
        self.memory = []

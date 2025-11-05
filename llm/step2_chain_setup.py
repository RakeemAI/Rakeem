# llm/step2_chain_setup.py
import os, json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

SAUDI_SYSTEM_PROMPT = """
أنت "رقيم" مساعد مالي سعودي. استخدم دائمًا "السياق المقدم" فقط للإجابة.
إذا لم يتوفر سياق ذو صلة من قاعدة المعرفة المحلية، قل حرفيًا:
"المصدر غير متوفر في البيانات المحلية."
ولا تعتمد على معرفتك العامة.
اجب بالعربية الفصحى وباختصار، واذكر المصادر إن وُجدت.
"""

def _exists(path: str) -> bool:
    try:
        return os.path.exists(path)
    except Exception:
        return False

class LangChainSetup:
    """
    LLM + RAG setup (FAISS -> strict RAG-first):
      - يحمل FAISS من مجلد RAG_STORE_PATH (يحتوي index.faiss/index.pkl).
      - إن تعذر، يحاول RAG بسيط من JSONL.
      - لو ما وُجد سياق مناسب -> يصرّح بعدم توفر المصدر (لا إجابة عامة).
    """
    def __init__(self):
        # LLM
        self.api_key      = os.getenv("OPENAI_API_KEY")
        self.model_name   = os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.temperature  = float(os.getenv("TEMPERATURE", "0.2"))
        self.max_tokens   = int(os.getenv("MAX_TOKENS", "6000"))

        # RAG
        self.rag_store_path  = os.getenv("RAG_STORE_PATH", "./data")               # مجلد فيه index.faiss/index.pkl
        self.jsonl_path      = os.getenv("ZATCA_JSONL_PATH", "./data/zatca_docs.jsonl")
        self.top_k           = int(os.getenv("RAG_TOP_K", "3"))
        self.score_threshold = float(os.getenv("RAG_SCORE_THRESHOLD", "0.7"))

        self.client: Optional[OpenAI] = None
        self.memory: List[Dict[str, str]] = []
        self.retriever = None          # FAISS retriever أو "simple"
        self.documents: List[Dict[str, str]] = []

    # ---------- LLM ----------
    def setup_llm(self) -> bool:
        if not self.api_key:
            print("⚠️ OPENAI_API_KEY غير موجود في .env")
            return False
        self.client = OpenAI(api_key=self.api_key)
        print(f"✅ OpenAI جاهز: {self.model_name}")
        return True

    def setup_memory(self) -> bool:
        self.memory = []
        return True

    # ---------- RAG ----------
    def setup_retriever(self) -> bool:
        """يحاول تحميل FAISS؛ وإلا يرجع لـ JSONL بسيط."""
        try:
            from langchain_community.vectorstores import FAISS
            from langchain_openai import OpenAIEmbeddings

            # تحقق أن ملفات الفهرس موجودة داخل المجلد
            idx_faiss = os.path.join(self.rag_store_path, "index.faiss")
            idx_pkl   = os.path.join(self.rag_store_path, "index.pkl")
            if not (_exists(idx_faiss) and _exists(idx_pkl)):
                print(f"⚠️ لم أجد index.faiss/index.pkl داخل {self.rag_store_path} -> استخدام RAG بسيط")
                return self._load_simple_rag()

            embeddings = OpenAIEmbeddings(
                openai_api_key=self.api_key,
                model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            )
            vs = FAISS.load_local(
                self.rag_store_path,
                embeddings,
                allow_dangerous_deserialization=True
            )

            # ملاحظة: بعض نسخ لانجتشين تدعم threshold عبر search_kwargs
            try:
                self.retriever = vs.as_retriever(
                    search_kwargs={"k": self.top_k, "score_threshold": self.score_threshold}
                )
            except TypeError:
                # نسخة لا تدعم threshold، نكتفي بـ k
                self.retriever = vs.as_retriever(search_kwargs={"k": self.top_k})

            print(f"✅ تم تحميل FAISS من {self.rag_store_path} (k={self.top_k}, thr={self.score_threshold})")
            return True

        except ImportError as ie:
            print(f"⚠️ مفقود langchain-community/langchain-openai: {ie} -> استخدام RAG بسيط")
            return self._load_simple_rag()
        except Exception as e:
            print(f"⚠️ فشل تحميل FAISS: {e} -> استخدام RAG بسيط")
            return self._load_simple_rag()

    def _load_simple_rag(self) -> bool:
        """لود بدائي من JSONL عند عدم توفر FAISS."""
        try:
            if not _exists(self.jsonl_path):
                print(f"⚠️ ملف JSONL غير موجود: {self.jsonl_path}")
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
            print(f"✅ تم تحميل RAG بسيط: {len(self.documents)} مستند من {self.jsonl_path}")
            return True
        except Exception as e:
            print(f"⚠️ فشل تحميل RAG البسيط: {e}")
            self.retriever = None
            return False

    # ---------- استرجاع السياق ----------
    def _retrieve_texts(self, question: str) -> List[Dict[str, str]]:
        """يرجع قائمة وثائق ذات صلة (text, source)."""
        if not self.retriever:
            return []

        try:
            if self.retriever == "simple":
                # اختيار بسيط: نعيد أول N أسطر تحتوي كلمات من السؤال
                q = question.strip()
                hits = [d for d in self.documents if any(w in d["text"] for w in q.split())]
                return hits[: self.top_k] if hits else []
            else:
                # FAISS retriever
                # في بعض نسخ لانجتشين: retriever.get_relevant_documents()
                try:
                    docs = self.retriever.get_relevant_documents(question)
                except AttributeError:
                    # نسخ أحدث تدعم invoke
                    docs = self.retriever.invoke(question)
                out = []
                for d in docs[: self.top_k]:
                    txt = getattr(d, "page_content", "") or ""
                    src = ""
                    md  = getattr(d, "metadata", {}) or {}
                    # حاول نجلب حقل المصدر بأي اسم شائع
                    src = md.get("source") or md.get("file") or md.get("path") or md.get("topic") or "ZATCA"
                    if txt.strip():
                        out.append({"text": txt.strip(), "source": str(src)})
                return out
        except Exception as e:
            print(f"⚠️ خطأ أثناء الاسترجاع: {e}")
            return []

    # ---------- سؤال وإجابة ----------
    def ask_question_real(self, prompt: str, context: Optional[str] = None) -> Dict[str, Any]:
        """يُجبِر الإجابة على الاعتماد على RAG؛ وإلا يرجع 'المصدر غير متوفر'."""
        if not self.client:
            return {"answer": "خطأ: LLM غير مهيأ", "source_documents": [], "used_rag": False}

        # 1) جمع سياق من RAG
        rag_docs = self._retrieve_texts(prompt)
        used_rag = False
        context_block = ""

        if context and context.strip():
            context_block = context.strip()
            used_rag = True
        elif rag_docs:
            used_rag = True
            # دمج نصوص مع ترويسات قصيرة للمصدر
            ctx_lines = []
            for i, d in enumerate(rag_docs, 1):
                ctx_lines.append(f"[{i}] المصدر: {d['source']}\n{d['text']}")
            context_block = "\n\n".join(ctx_lines)

        # 2) إذا لا يوجد سياق مناسب -> لا نسمح بإجابة عامة
        if not used_rag:
            return {
                "answer": "المصدر غير متوفر في البيانات المحلية.",
                "source_documents": [],
                "used_rag": False
            }

        # 3) جهّز الرسائل مع System Prompt السعودي الصارم
        messages = []
        messages.append({"role": "system", "content": SAUDI_SYSTEM_PROMPT})
        # ذاكرة قصيرة اختيارية (بدون تسريب سياق قديم)
        if self.memory:
            messages.extend(self.memory[-2:])

        user_content = f"السياق:\n{context_block}\n\nالسؤال:\n{prompt}\n\nأجب مستندًا على السياق فقط، واذكر أرقام المصادر بين [1], [2] إن لزم."
        messages.append({"role": "user", "content": user_content})

        # 4) استدعاء LLM
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            answer = resp.choices[0].message.content or ""

            # حدّث الذاكرة الخفيفة
            self.memory.extend([
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": answer}
            ])

            # أرجِع المصادر (FAISS فقط) للتظهير في الواجهة
            return {
                "answer": answer,
                "source_documents": rag_docs,
                "used_rag": True
            }
        except Exception as e:
            msg = f"خطأ في الاستدعاء: {e}"
            print(f"❌ {msg}")
            return {"answer": msg, "source_documents": [], "used_rag": used_rag}

    def clear_memory(self):
        self.memory = []

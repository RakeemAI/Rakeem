import os
from dotenv import load_dotenv
import openai

# تحديد مسار .env الصحيح
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
else:
    # Fallback للمسار الحالي
    load_dotenv(override=True)

class LangChainSetup:
    def __init__(self):
        # قراءة المتغيرات من .env
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model_name = os.getenv("MODEL_NAME", "gpt-4-turbo")
        self.temperature = float(os.getenv("TEMPERATURE", "0.2"))
        self.max_tokens = int(os.getenv("MAX_TOKENS", "2000"))
        self.rag_store_path = os.getenv("RAG_STORE_PATH", "./Rakeem/data/rag_store")
        
        self.client = None
        self.memory = []
        self.retriever = None
        self.documents = []

    def setup_llm(self):
        """تهيئة OpenAI Client"""
        if not self.api_key:
            print("⚠️ خطأ: OPENAI_API_KEY غير موجود في .env")
            return False
        
        openai.api_key = self.api_key
        self.client = openai.OpenAI(api_key=self.api_key)
        print(f"✅ تم تهيئة OpenAI بنجاح - النموذج: {self.model_name}")
        return True

    def setup_memory(self):
        """تهيئة الذاكرة"""
        self.memory = []
        print("✅ تم تهيئة الذاكرة")
        return True

    def setup_retriever(self):
        """تحميل RAG"""
        try:
            # محاولة استخدام FAISS
            try:
                from langchain_community.vectorstores import FAISS
                from langchain_openai import OpenAIEmbeddings
                
                if not os.path.exists(self.rag_store_path):
                    print(f"⚠️ RAG store غير موجود")
                    return False
                
                embeddings = OpenAIEmbeddings(
                    openai_api_key=self.api_key,
                    model="text-embedding-3-small"
                )
                
                vectorstore = FAISS.load_local(
                    self.rag_store_path,
                    embeddings,
                    allow_dangerous_deserialization=True
                )
                
                top_k = int(os.getenv("RAG_TOP_K", "3"))
                self.retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
                print(f"✅ تم تحميل RAG بنجاح (FAISS) - Top K: {top_k}")
                return True
                
            except ImportError:
                # fallback لـ RAG بسيط
                print("⚠️ langchain غير متاح، استخدام RAG بسيط...")
                return self._load_simple_rag()
                
        except Exception as e:
            print(f"⚠️ فشل تحميل RAG: {str(e)}")
            return False

    def _load_simple_rag(self):
        """تحميل RAG بدون FAISS"""
        try:
            import json
            docs_path = "./Rakeem/data/zatca_docs.jsonl"
            
            if not os.path.exists(docs_path):
                print(f"⚠️ ملف المستندات غير موجود: {docs_path}")
                return False
            
            self.documents = []
            with open(docs_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        doc = json.loads(line)
                        self.documents.append(doc.get('text', ''))
            
            print(f"✅ تم تحميل {len(self.documents)} مستند")
            self.retriever = "simple"
            return True
            
        except Exception as e:
            print(f"⚠️ فشل تحميل المستندات: {str(e)}")
            return False

    def get_context_from_rag(self, question):
        """استخراج السياق من RAG"""
        if not self.retriever:
            return None
        
        try:
            # FAISS
            if self.retriever != "simple":
                docs = self.retriever.invoke(question)
                if docs:
                    context = "\n\n".join([doc.page_content for doc in docs[:3]])
                    print(f"✅ تم استرجاع {len(docs[:3])} مستند من FAISS")
                    return context
            
            # بحث بسيط
            else:
                matching_docs = []
                question_lower = question.lower()
                
                for doc in self.documents:
                    if any(word in doc.lower() for word in question_lower.split()):
                        matching_docs.append(doc)
                        if len(matching_docs) >= 3:
                            break
                
                if matching_docs:
                    context = "\n\n".join(matching_docs[:3])
                    print(f"✅ تم استرجاع {len(matching_docs)} مستند (بحث بسيط)")
                    return context
            
            return None
            
        except Exception as e:
            print(f"⚠️ خطأ في استرجاع المستندات: {str(e)}")
            return None

    def ask_question_real(self, prompt, context=None):
        """السؤال للـ LLM"""
        if not self.client:
            return {"answer": "خطأ: LLM غير مهيأ", "source_documents": []}
        
        try:
            # محاولة استخراج السياق من RAG
            rag_context = None
            if self.retriever:
                rag_context = self.get_context_from_rag(prompt)
            
            # دمج السياق
            full_prompt = prompt
            if context:
                full_prompt = f"السياق:\n{context}\n\nالسؤال:\n{prompt}"
            elif rag_context:
                full_prompt = f"المعلومات من قاعدة المعرفة:\n{rag_context}\n\nالسؤال:\n{prompt}"
            
            # إضافة الذاكرة
            messages = []
            if self.memory:
                messages.extend(self.memory[-4:])
            messages.append({"role": "user", "content": full_prompt})
            
            # الاستدعاء
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            answer = response.choices[0].message.content
            
            # حفظ في الذاكرة
            self.memory.append({"role": "user", "content": prompt})
            self.memory.append({"role": "assistant", "content": answer})
            
            return {
                "answer": answer,
                "source_documents": [],
                "used_rag": rag_context is not None
            }
            
        except Exception as e:
            error_msg = f"خطأ في الاستدعاء: {str(e)}"
            print(f"❌ {error_msg}")
            return {"answer": error_msg, "source_documents": []}

    def clear_memory(self):
        """مسح الذاكرة"""
        self.memory = []
        print("✅ تم مسح الذاكرة")

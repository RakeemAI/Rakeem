# llm/step4_response_parser.py
from __future__ import annotations
import re

class ResponseParser:
    """
    توحيد إخراج الـ LLM إلى صيغة ثابتة:
      - الشرح المختصر: فقرة.
      - توصيات عملية: تعداد 1., 2., 3. (سطر لكل توصية).
      - لا نضيف "المصادر" هنا؛ تُعرض في الواجهة.
    """

    def parse_and_format(self, raw_text: str) -> str:
        if not isinstance(raw_text, str):
            return str(raw_text)
        text = raw_text.strip()

        # ثبّت عنوان "الشرح المختصر"
        text = re.sub(r"\*?\s*الشرح\s*المختصر\s*[:\-]?\s*", "الشرح المختصر:\n", text, flags=re.I)

        # ثبّت عنوان "توصيات عملية"
        text = re.sub(r"\*?\s*(?:توصيات|نصائح)(?:\s*عملية)?\s*[:\-]?\s*", "توصيات عملية:\n", text, flags=re.I)

        # حوّل أي قوائم إلى 1., 2., ...
        text = self._normalize_recommendations(text)

        # احذف أي قسم مصادر ضمن النص (الـ UI ستعرضها)
        text = re.sub(r"\n\s*المصادر\s*:.*$", "", text, flags=re.S | re.I)

        # تقليل الفراغات
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _normalize_recommendations(self, text: str) -> str:
        m = re.search(r"(توصيات عملية:\s*)(.*)$", text, flags=re.S)
        if not m:
            return text

        head, tail = m.group(1), m.group(2)
        lines = [ln.strip() for ln in tail.splitlines()]

        items = []
        for ln in lines:
            if not ln:
                continue
            if re.match(r"^\d+\.\s+\S", ln):
                items.append(re.sub(r"^\d+\.\s+", "", ln))
            elif re.match(r"^[\-•]\s+\S", ln):
                items.append(re.sub(r"^[\-•]\s+", "", ln))

        if not items:
            return text

        items = [it for it in items if it][:5]   # حد أقصى 5
        numbered = "\n".join(f"{i}. {it}" for i, it in enumerate(items, 1))
        return re.sub(r"(توصيات عملية:\s*)(.*)$", r"\1" + numbered, text, flags=re.S)

"""
AI Service - OpenAI / Anthropic Claude
"""

from typing import Optional

from openai import AsyncOpenAI
from app.config import settings
from app.lib.llm_service.providers import openai_call_kwargs
from app.prompts.classification import CLASSIFICATION_PROMPT
from app.prompts.extraction import get_extraction_prompt
from app.prompts.summary import SUMMARY_PROMPT
from app.prompts.qa import QA_PROMPT
import json


# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _chat_kwargs(
    model: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> dict:
    """組出 chat.completions 的 `model` 與該模型可接受的參數。

    **model 與參數過濾必須同源,所以綁在同一個函式裡。**
    2026-09-09 前這裡是 `model=OPENAI_MODEL` 配
    `openai_call_kwargs(OPENAI_MODEL_MINI, ...)`——兩個鍵剛好同世代時沒事,
    但只要有人單獨改其中一個(例如 OPENAI_MODEL 換 gpt-4o、MINI 留 gpt-5.6),
    就會拿錯世代的規則去打 API,而 openai_call_kwargs 的註解已寫明
    **這類 400 在本系統是靜默的**:降級回正則結果、HTTP 200、
    llm_pages_used=0、estimated_cost=0,從回應完全看不出 LLM 沒跑成功。
    分開傳等於把這個地雷留在四個呼叫點上,故一律經此函式。
    """
    return {
        "model": model,
        **openai_call_kwargs(model, max_tokens=max_tokens, temperature=temperature),
    }


async def classify_document(ocr_text: str) -> dict:
    """
    Classify document type using AI

    Returns:
        {
            "doc_type": "lease_contract" | "repair_quote" | "id_card" | "unknown",
            "confidence": 0.95
        }
    """
    prompt = CLASSIFICATION_PROMPT.format(ocr_text=ocr_text)

    response = await openai_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        **_chat_kwargs(settings.OPENAI_MODEL_MINI, temperature=0),
    )

    result = json.loads(response.choices[0].message.content)
    return result


async def extract_fields(ocr_text: str, doc_type: str) -> dict:
    """
    Extract fields from document based on document type

    Returns:
        Dictionary with extracted fields (varies by doc_type)
    """
    prompt = get_extraction_prompt(doc_type, ocr_text)

    response = await openai_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        **_chat_kwargs(settings.OPENAI_MODEL, temperature=0),
    )

    result = json.loads(response.choices[0].message.content)
    return result


async def generate_summary(ocr_text: str, doc_type: str) -> str:
    """
    Generate document summary

    Returns:
        Summary text (3-5 sentences)
    """
    prompt = SUMMARY_PROMPT.format(doc_type=doc_type, ocr_text=ocr_text)

    response = await openai_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        **_chat_kwargs(settings.OPENAI_MODEL_MINI, temperature=0.3),
    )

    return response.choices[0].message.content


async def answer_question(question: str, context: dict) -> str:
    """
    Answer question about document

    Args:
        question: User question
        context: Document context (ocr_text, extracted_data, etc.)

    Returns:
        AI answer
    """
    prompt = QA_PROMPT.format(
        ocr_text=context["ocr_text"],
        doc_type=context["doc_type"],
        extracted_data=json.dumps(context["extracted_data"], ensure_ascii=False, indent=2),
        summary=context.get("summary", "無"),
        question=question
    )

    response = await openai_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        **_chat_kwargs(settings.OPENAI_MODEL, temperature=0.3),
    )

    return response.choices[0].message.content

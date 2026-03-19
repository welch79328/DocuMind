"""
AI Service - OpenAI / Anthropic Claude
"""

from openai import AsyncOpenAI
from app.config import settings
from app.prompts.classification import CLASSIFICATION_PROMPT
from app.prompts.extraction import get_extraction_prompt
from app.prompts.summary import SUMMARY_PROMPT
from app.prompts.qa import QA_PROMPT
import json


# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


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
        model=settings.OPENAI_MODEL_MINI,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"}
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
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"}
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
        model=settings.OPENAI_MODEL_MINI,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
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
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return response.choices[0].message.content

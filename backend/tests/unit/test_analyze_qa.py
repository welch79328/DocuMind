"""
測試統一分析服務 - AI 問答整合

驗收標準:
- 帶 question 參數時，回應 answer 欄位有 AI 回答
- 不帶 question 時，answer 為 null，不呼叫 LLM
- 問答 LLM 失敗時，answer 為 null，其餘結果正常
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def _make_mock_pages():
    return [{
        "page_number": 1,
        "ocr_raw": {"text": "所有權人：黃水木", "confidence": 0.85},
        "rule_postprocessed": {"text": "所有權人：黃水木", "stats": {}},
        "llm_postprocessed": None,
        "structured_data": {"owner": "黃水木"},
    }]


class TestQuestionAnswering:
    """測試問答功能"""

    @pytest.mark.asyncio
    async def test_with_question_returns_answer(self):
        """帶 question 時應回傳 AI 回答"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        with patch.object(service, '_upload_to_s3', new_callable=AsyncMock) as mock_s3, \
             patch.object(service, '_process_ocr', new_callable=AsyncMock) as mock_ocr, \
             patch("app.services.analyze_service.answer_question", new_callable=AsyncMock) as mock_qa:
            mock_s3.return_value = None
            mock_ocr.return_value = (_make_mock_pages(), 1)
            mock_qa.return_value = "所有權人是黃水木"

            result = await service.analyze(
                file_contents=b"fake",
                filename="test.png",
                document_type="transcript",
                enable_llm=False,
                question="所有權人是誰？",
            )

            assert result["answer"] == "所有權人是黃水木"
            mock_qa.assert_called_once()

    @pytest.mark.asyncio
    async def test_without_question_answer_is_null(self):
        """不帶 question 時 answer 應為 null"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        with patch.object(service, '_upload_to_s3', new_callable=AsyncMock) as mock_s3, \
             patch.object(service, '_process_ocr', new_callable=AsyncMock) as mock_ocr, \
             patch("app.services.analyze_service.answer_question", new_callable=AsyncMock) as mock_qa:
            mock_s3.return_value = None
            mock_ocr.return_value = (_make_mock_pages(), 1)

            result = await service.analyze(
                file_contents=b"fake",
                filename="test.png",
                document_type="transcript",
                enable_llm=False,
                question=None,
            )

            assert result["answer"] is None
            mock_qa.assert_not_called()

    @pytest.mark.asyncio
    async def test_qa_failure_answer_is_null(self):
        """問答 LLM 失敗時 answer 應為 null，其餘結果正常"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        with patch.object(service, '_upload_to_s3', new_callable=AsyncMock) as mock_s3, \
             patch.object(service, '_process_ocr', new_callable=AsyncMock) as mock_ocr, \
             patch("app.services.analyze_service.answer_question", new_callable=AsyncMock) as mock_qa:
            mock_s3.return_value = None
            mock_ocr.return_value = (_make_mock_pages(), 1)
            mock_qa.side_effect = Exception("OpenAI API error")

            result = await service.analyze(
                file_contents=b"fake",
                filename="test.png",
                document_type="transcript",
                enable_llm=False,
                question="所有權人是誰？",
            )

            assert result["answer"] is None
            assert len(result["pages"]) == 1  # OCR 結果正常

    @pytest.mark.asyncio
    async def test_qa_context_built_correctly(self):
        """問答 context 應包含 OCR 文字與結構化欄位"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        with patch.object(service, '_upload_to_s3', new_callable=AsyncMock) as mock_s3, \
             patch.object(service, '_process_ocr', new_callable=AsyncMock) as mock_ocr, \
             patch("app.services.analyze_service.answer_question", new_callable=AsyncMock) as mock_qa:
            mock_s3.return_value = None
            mock_ocr.return_value = (_make_mock_pages(), 1)
            mock_qa.return_value = "回答"

            await service.analyze(
                file_contents=b"fake",
                filename="test.png",
                document_type="transcript",
                enable_llm=False,
                question="問題",
            )

            # 驗證 context 結構
            call_args = mock_qa.call_args
            question_arg = call_args[0][0] if call_args[0] else call_args[1].get("question")
            context_arg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("context")

            assert question_arg == "問題"
            assert "ocr_text" in context_arg
            assert "doc_type" in context_arg
            assert context_arg["doc_type"] == "transcript"

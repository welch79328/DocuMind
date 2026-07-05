"""
測試 few-shot 注入串接分析流程(任務 9.2)

- AnalyzeService._process_ocr 將 few_shot 傳入 processor.process
- 分析端點於處理前選取範例並注入;新校正樣本下次同類自動被選用

對應需求: 7.3
"""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.database import get_db
from app.main import app
from app.services.analyze_service import AnalyzeService
from app.services.correction_sample_service import CorrectionSampleService
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory


def _min_page():
    return {
        "page_number": 1, "original_image": "x",
        "ocr_raw": {"text": "文字", "confidence": 0.9},
        "rule_postprocessed": {"text": "文字", "stats": {}},
        "llm_postprocessed": None, "structured_data": None,
    }


class TestServiceThreading:
    async def test_process_ocr_threads_few_shot_to_processor(self):
        svc = AnalyzeService()
        mock_proc = MagicMock()
        mock_proc.process = AsyncMock(return_value=_min_page())
        few_shot = [{"input_ref": "r", "corrected_fields": {"a": "1"}}]

        with patch.object(ProcessorFactory, "get_processor", return_value=mock_proc):
            await svc._process_ocr(b"imgbytes", "doc.png", "transcript", False, few_shot)

        _, kwargs = mock_proc.process.call_args
        assert kwargs["few_shot"] == few_shot

    async def test_analyze_passes_few_shot_down(self):
        svc = AnalyzeService()
        mock_proc = MagicMock()
        mock_proc.process = AsyncMock(return_value=_min_page())
        few_shot = [{"input_ref": "r", "corrected_fields": {"a": "1"}}]

        with patch.object(ProcessorFactory, "get_processor", return_value=mock_proc), \
             patch.object(AnalyzeService, "_upload_to_s3", AsyncMock(return_value=None)), \
             patch.object(AnalyzeService, "_record_usage", MagicMock()):
            await svc.analyze(b"imgbytes", "doc.png", "transcript", False, few_shot=few_shot)

        _, kwargs = mock_proc.process.call_args
        assert kwargs["few_shot"] == few_shot


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


class TestEndpointInjection:
    @pytest.fixture
    def ctx(self, feedback_session):
        app.dependency_overrides[get_db] = lambda: feedback_session
        try:
            yield CorrectionSampleService(feedback_session)
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_endpoint_injects_selected_samples(self, ctx):
        samples = ctx
        # 先前的校正樣本
        samples.save("transcript", "prev-doc", {"area": "128.45"})

        captured = {}

        async def fake_analyze(**kwargs):
            captured["few_shot"] = kwargs.get("few_shot")
            return {
                "file_name": "t.pdf", "file_url": None, "document_type": "transcript",
                "total_pages": 1,
                "pages": [{"page_number": 1, "ocr_raw": {"text": "x", "confidence": 0.95},
                           "rule_postprocessed": {"text": "x", "stats": {}},
                           "llm_postprocessed": None, "structured_data": None}],
                "answer": None,
                "stats": {"total_time_ms": 1, "total_pages": 1,
                          "llm_pages_used": 0, "estimated_cost": 0.0},
            }

        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            MockService.return_value.analyze = AsyncMock(side_effect=fake_analyze)
            async with _client() as c:
                resp = await c.post(
                    "/api/v1/analyze",
                    files={"file": ("t.pdf", b"%PDF-1.4", "application/pdf")},
                    data={"document_type": "transcript", "enable_llm": "false"},
                )
        assert resp.status_code == 200
        # 端點應選取先前樣本並注入
        assert captured["few_shot"] is not None
        refs = {e["input_ref"] for e in captured["few_shot"]}
        assert "prev-doc" in refs

    async def test_no_samples_injects_empty(self, ctx):
        captured = {}

        async def fake_analyze(**kwargs):
            captured["few_shot"] = kwargs.get("few_shot")
            return {
                "file_name": "t.pdf", "file_url": None, "document_type": "transcript",
                "total_pages": 1,
                "pages": [{"page_number": 1, "ocr_raw": {"text": "x", "confidence": 0.95},
                           "rule_postprocessed": {"text": "x", "stats": {}},
                           "llm_postprocessed": None, "structured_data": None}],
                "answer": None,
                "stats": {"total_time_ms": 1, "total_pages": 1,
                          "llm_pages_used": 0, "estimated_cost": 0.0},
            }

        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            MockService.return_value.analyze = AsyncMock(side_effect=fake_analyze)
            async with _client() as c:
                resp = await c.post(
                    "/api/v1/analyze",
                    files={"file": ("t.pdf", b"%PDF-1.4", "application/pdf")},
                    data={"document_type": "transcript", "enable_llm": "false"},
                )
        assert resp.status_code == 200
        assert captured["few_shot"] == []

"""
端到端整合測試(任務 16.1)

驗證完整回饋迴路 + 合約文字層兩路 + 隱私(雲端停用不外送):
上傳→路由→處理→低信心進佇列→校正→樣本入庫→下次 few-shot 生效→評估可見。

對應需求: 6.2, 7.3, 4.1
"""

import sys
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import settings
from app.database import get_db
from app.main import app
from app.services.analyze_service import AnalyzeService
from app.services.correction_sample_service import CorrectionSampleService
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
from app.lib.llm_service.providers import create_provider, OpenAIProvider, LocalQwenProvider


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _low_conf(dtype="transcript"):
    return {
        "file_name": "t.pdf", "file_url": None, "document_type": dtype,
        "total_pages": 1,
        "pages": [{"page_number": 1,
                   "ocr_raw": {"text": "土地登記 12B.45", "confidence": 0.6},
                   "rule_postprocessed": {"text": "土地登記 12B.45", "stats": {}},
                   "llm_postprocessed": None, "structured_data": None}],
        "answer": None,
        "stats": {"total_time_ms": 1, "total_pages": 1,
                  "llm_pages_used": 0, "estimated_cost": 0.0},
    }


class TestFullFeedbackLoop:
    @pytest.fixture
    def db(self, feedback_session):
        app.dependency_overrides[get_db] = lambda: feedback_session
        try:
            yield feedback_session
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_upload_to_fewshot_and_evaluation(self, db):
        captured = {"few_shot": None}

        async def fake_analyze(**kwargs):
            captured["few_shot"] = kwargs.get("few_shot")
            return _low_conf()

        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            MockService.return_value.analyze = AsyncMock(side_effect=fake_analyze)
            async with _client() as c:
                # 1. 上傳低信心文件 → 路由+處理+攔截入佇列
                r1 = await c.post("/api/v1/analyze",
                                  files={"file": ("t.pdf", b"%PDF", "application/pdf")},
                                  data={"document_type": "transcript", "enable_llm": "false"})
                assert r1.json()["needs_review"] is True
                item_id = r1.json()["review_item_id"]
                assert captured["few_shot"] == []  # 初次無範例

                # 2. 認領 + 校正 → 樣本入庫
                await c.post(f"/api/v1/review/{item_id}/claim", json={"reviewer": "alice"})
                sub = await c.post(f"/api/v1/review/{item_id}/submit",
                                   json={"reviewer": "alice", "corrected_fields": {"area": "128.45"}})
                assert sub.json()["status"] == "completed"

                # 3. 再次分析 → few-shot 自動注入校正樣本
                await c.post("/api/v1/analyze",
                             files={"file": ("t2.pdf", b"%PDF", "application/pdf")},
                             data={"document_type": "transcript", "enable_llm": "false"})
                assert captured["few_shot"], "第二次應注入已累積校正"
                assert captured["few_shot"][0]["corrected_fields"] == {"area": "128.45"}

                # 4. 評估端點反映累積的訓練樣本
                ev = await c.get("/api/v1/evaluation/transcript")
                assert ev.json()["sample_counts"]["train"] >= 1


class TestContractTextLayerIntegration:
    async def test_contract_text_layer_skips_ocr(self):
        svc = AnalyzeService()
        mock_proc = MagicMock()
        mock_proc.process = AsyncMock()
        text_pages = [{"page_number": 1, "ocr_raw": {"text": "條款", "confidence": 1.0},
                       "rule_postprocessed": {"text": "條款", "stats": {}},
                       "llm_postprocessed": None, "structured_data": None,
                       "field_confidences": {}, "overall_confidence": 1.0, "text_layer": True}]
        with patch("app.services.analyze_service.has_text_layer", return_value=True), \
             patch("app.services.analyze_service.extract_text_layer_pages", return_value=text_pages), \
             patch.object(ProcessorFactory, "get_processor", return_value=mock_proc):
            pages, total = await svc._process_ocr(b"pdf", "c.pdf", "contract", False)
        mock_proc.process.assert_not_called()
        assert pages[0]["text_layer"] is True


class TestPrivacyNoExfiltration:
    def test_cloud_blocked_local_works_when_cloud_disabled(self, monkeypatch):
        # 隱私硬需求:雲端停用 → 雲端 Provider 被阻擋(個資不外送),本地仍可用
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        monkeypatch.setattr(settings, "LOCAL_QWEN_ENDPOINT", "http://localhost:8001")
        with pytest.raises(ValueError):
            create_provider("openai")
        assert isinstance(create_provider("local_qwen"), LocalQwenProvider)

    def test_cloud_available_when_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        assert isinstance(create_provider("openai"), OpenAIProvider)

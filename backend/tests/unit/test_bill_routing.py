"""
測試帳單型別註冊至路由(任務 11.2)

- 工廠可依 bill 型別建立 BillProcessor
- 白名單自動含 bill
- API 接受 bill 型別分析

對應需求: 1.1, 1.2
"""

import httpx
import pytest
from unittest.mock import AsyncMock, patch

from app.database import get_db
from app.main import app
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
from app.lib.multi_type_ocr.bill_processor import BillProcessor
from app.lib.document_types import DocumentType


class TestFactoryRegistration:
    def test_get_bill_processor(self):
        assert isinstance(ProcessorFactory.get_processor("bill"), BillProcessor)

    def test_get_bill_processor_by_enum(self):
        assert isinstance(ProcessorFactory.get_processor(DocumentType.BILL), BillProcessor)

    def test_bill_in_supported_types(self):
        assert "bill" in [str(t) for t in ProcessorFactory.supported_types()]


class TestApiWhitelist:
    @pytest.fixture(autouse=True)
    def _db(self, feedback_session):
        app.dependency_overrides[get_db] = lambda: feedback_session
        yield
        app.dependency_overrides.pop(get_db, None)

    async def test_bill_type_accepted(self):
        result = {
            "file_name": "b.pdf", "file_url": None, "document_type": "bill",
            "total_pages": 1,
            "pages": [{"page_number": 1, "ocr_raw": {"text": "x", "confidence": 0.95},
                       "rule_postprocessed": {"text": "x", "stats": {}},
                       "llm_postprocessed": None, "structured_data": None}],
            "answer": None,
            "stats": {"total_time_ms": 1, "total_pages": 1,
                      "llm_pages_used": 0, "estimated_cost": 0.0},
        }
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            MockService.return_value.analyze = AsyncMock(return_value=result)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as c:
                resp = await c.post(
                    "/api/v1/analyze",
                    files={"file": ("b.pdf", b"%PDF-1.4", "application/pdf")},
                    data={"document_type": "bill", "enable_llm": "false"},
                )
        assert resp.status_code == 200

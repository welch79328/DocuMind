"""
few-shot 迴路端到端測試(任務 9.3)

- 選取策略:同版型優先(覆蓋 recency)、上限
- 閉環:分析低信心 → 校正 → 樣本回灌 → 下次同類分析自動注入 few-shot(越用越準)

對應需求: 7.3
"""

import httpx
import pytest
from unittest.mock import AsyncMock, patch

from app.database import get_db
from app.main import app
from app.services.correction_sample_service import CorrectionSampleService
from app.services.few_shot_selector import FewShotSelector


class TestSelectionStrategy:
    def test_layout_signature_drives_ordering(self, feedback_session):
        samples = CorrectionSampleService(feedback_session)
        selector = FewShotSelector(samples, max_examples=5)
        samples.save("transcript", "doc-a", {"a": 1}, layout_signature="SIG-A")
        samples.save("transcript", "doc-b", {"a": 2}, layout_signature="SIG-B")
        # 指定版型時,同版型範例排在最前(確定性,不依賴 recency)
        assert selector.select("transcript", layout_signature="SIG-A")[0]["input_ref"] == "doc-a"
        assert selector.select("transcript", layout_signature="SIG-B")[0]["input_ref"] == "doc-b"

    def test_cap_applies_within_same_layout(self, feedback_session):
        samples = CorrectionSampleService(feedback_session)
        selector = FewShotSelector(samples, max_examples=2)
        for i in range(5):
            samples.save("transcript", f"s{i}", {"a": i}, layout_signature="SIG-A")
        assert len(selector.select("transcript", layout_signature="SIG-A")) == 2


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _low_conf_result():
    return {
        "file_name": "t.pdf", "file_url": None, "document_type": "transcript",
        "total_pages": 1,
        "pages": [{
            "page_number": 1,
            "ocr_raw": {"text": "土地登記 12B.45", "confidence": 0.6},
            "rule_postprocessed": {"text": "土地登記 12B.45", "stats": {}},
            "llm_postprocessed": None, "structured_data": None,
        }],
        "answer": None,
        "stats": {"total_time_ms": 1, "total_pages": 1,
                  "llm_pages_used": 0, "estimated_cost": 0.0},
    }


class TestClosedLoop:
    @pytest.fixture
    def db(self, feedback_session):
        app.dependency_overrides[get_db] = lambda: feedback_session
        try:
            yield feedback_session
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_correction_feeds_back_to_next_analysis(self, db):
        captured = {"few_shot": []}

        async def fake_analyze(**kwargs):
            captured["few_shot"] = kwargs.get("few_shot")
            return _low_conf_result()

        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            MockService.return_value.analyze = AsyncMock(side_effect=fake_analyze)
            async with _client() as c:
                # 1. 首次分析(低信心)→ 入複核佇列;此時尚無範例
                r1 = await c.post(
                    "/api/v1/analyze",
                    files={"file": ("t.pdf", b"%PDF-1.4", "application/pdf")},
                    data={"document_type": "transcript", "enable_llm": "false"},
                )
                item_id = r1.json()["review_item_id"]
                assert captured["few_shot"] == []

                # 2. 人工校正(認領 → 提交)→ 產生校正樣本
                await c.post(f"/api/v1/review/{item_id}/claim", json={"reviewer": "alice"})
                await c.post(
                    f"/api/v1/review/{item_id}/submit",
                    json={"reviewer": "alice", "corrected_fields": {"area": "128.45"}},
                )

                # 3. 再次分析同類 → few-shot 自動注入前一次校正
                await c.post(
                    "/api/v1/analyze",
                    files={"file": ("t2.pdf", b"%PDF-1.4", "application/pdf")},
                    data={"document_type": "transcript", "enable_llm": "false"},
                )

        assert captured["few_shot"], "第二次分析應注入已累積的校正樣本"
        assert captured["few_shot"][0]["corrected_fields"] == {"area": "128.45"}

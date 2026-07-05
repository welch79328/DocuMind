"""
複核佇列併發與端到端測試(任務 3.4)

- 併發認領:多執行緒同時認領同一項目,僅一人成功(需求 6.7)
  使用 file-based SQLite 以取得真實多連線併發(in-memory StaticPool 為單連線)。
- 端到端:analyze 低信心 → 入列 → 認領 → 提交校正 → completed(需求 6.2)

對應需求: 6.2, 6.7
"""

import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import ReviewQueueItem, CorrectionSample, EvaluationRecord
from app.services.review_queue_service import ReviewQueueService


# --------------------------------------------------------------------------- #
# 併發認領
# --------------------------------------------------------------------------- #
class TestConcurrentClaim:
    def test_concurrent_claims_only_one_succeeds(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_engine(
            f"sqlite:///{path}",
            connect_args={"timeout": 30, "check_same_thread": False},
        )
        tables = [
            ReviewQueueItem.__table__,
            CorrectionSample.__table__,
            EvaluationRecord.__table__,
        ]
        Base.metadata.create_all(engine, tables=tables)
        Session = sessionmaker(bind=engine)

        # 建立一個 pending 項目
        seed = Session()
        item_id = ReviewQueueService(seed).enqueue(
            document_id=None, document_type="transcript",
            overall_confidence=0.6, result={"area": "x"},
        )
        seed.close()

        n_workers = 8
        barrier = threading.Barrier(n_workers)
        results = []
        lock = threading.Lock()

        def worker(i):
            session = Session()
            try:
                barrier.wait()  # 盡量讓所有執行緒同時認領
                ok = ReviewQueueService(session).claim(item_id, f"reviewer{i}")
                with lock:
                    results.append(ok)
            finally:
                session.close()

        try:
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                list(executor.map(worker, range(n_workers)))

            # 僅一人認領成功
            assert sum(1 for r in results if r) == 1

            # 最終狀態為單一認領者、in_review
            check = Session()
            item = ReviewQueueService(check).list_queue()[0]
            assert item["status"] == "in_review"
            assert item["reviewer"] is not None
            check.close()
        finally:
            engine.dispose()
            os.unlink(path)


# --------------------------------------------------------------------------- #
# 端到端:攔截 → 入列 → 認領 → 校正
# --------------------------------------------------------------------------- #
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
            "ocr_raw": {"text": "12B.45", "confidence": 0.6},
            "rule_postprocessed": {"text": "12B.45", "stats": {}},
            "llm_postprocessed": None,
            "structured_data": None,
        }],
        "answer": None,
        "stats": {"total_time_ms": 10, "total_pages": 1,
                  "llm_pages_used": 0, "estimated_cost": 0.0},
    }


class TestEndToEnd:
    @pytest.fixture
    def ctx(self, feedback_session):
        app.dependency_overrides[get_db] = lambda: feedback_session
        try:
            yield ReviewQueueService(feedback_session)
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_gating_to_correction_flow(self, ctx):
        # 1. 低信心分析 → 入列
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            MockService.return_value.analyze = AsyncMock(return_value=_low_conf_result())
            async with _client() as c:
                analyze_resp = await c.post(
                    "/api/v1/analyze",
                    files={"file": ("t.pdf", b"%PDF-1.4 fake", "application/pdf")},
                    data={"document_type": "transcript", "enable_llm": "false"},
                )
        assert analyze_resp.status_code == 200
        item_id = analyze_resp.json()["review_item_id"]
        assert item_id is not None

        async with _client() as c:
            # 2. 佇列可見
            q = await c.get("/api/v1/review/queue", params={"status": "pending"})
            assert len(q.json()["items"]) == 1

            # 3. 認領
            claim = await c.post(f"/api/v1/review/{item_id}/claim", json={"reviewer": "alice"})
            assert claim.status_code == 200

            # 4. 提交校正
            submit = await c.post(
                f"/api/v1/review/{item_id}/submit",
                json={"reviewer": "alice", "corrected_fields": {"area": "128.45"}},
            )
            assert submit.status_code == 200
            assert submit.json()["status"] == "completed"

            # 5. 已完成
            done = await c.get("/api/v1/review/queue", params={"status": "completed"})
            assert len(done.json()["items"]) == 1

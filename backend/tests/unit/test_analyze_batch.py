"""
測試批次分析端點 POST /api/v1/analyze/batch

以 httpx.ASGITransport 進行 ASGI 測試,mock AnalyzeService 避免真實處理
(與 test_analyze_document_type.py 同一套做法)。

對應規格條款:
- S6 一次多張,逐張回結果
- S7 單張失敗不中斷整批
"""

import asyncio

import httpx
import pytest
from unittest.mock import AsyncMock, patch

from app.main import app
from app.database import get_db
from app.api.v1.analyze import MAX_BATCH_FILES, BATCH_MAX_CONCURRENT


@pytest.fixture(autouse=True)
def _override_db(feedback_session):
    app.dependency_overrides[get_db] = lambda: feedback_session
    yield
    app.dependency_overrides.pop(get_db, None)


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _result(name="a.jpg"):
    return {
        "file_name": name, "file_url": None,
        "document_type": "handover_photo", "total_pages": 1,
        "pages": [], "answer": None,
        "stats": {"total_time_ms": 10, "total_pages": 1,
                  "llm_pages_used": 0, "estimated_cost": 0.0},
    }


def _jpgs(n, prefix="p"):
    return [("files", (f"{prefix}{i}.jpg", b"\xff\xd8\xff fake jpeg", "image/jpeg"))
            for i in range(n)]


class TestGuards:
    async def test_rejects_more_than_the_cap(self):
        async with _client() as c:
            resp = await c.post(
                "/api/v1/analyze/batch",
                files=_jpgs(MAX_BATCH_FILES + 1),
                data={"document_type": "handover_photo"},
            )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error_code"] == "TOO_MANY_FILES"
        assert str(MAX_BATCH_FILES) in body["detail"]

    async def test_unknown_document_type_fails_whole_batch(self):
        """型別錯是整批的問題,不該讓每一筆各自報一次。"""
        async with _client() as c:
            resp = await c.post(
                "/api/v1/analyze/batch",
                files=_jpgs(2),
                data={"document_type": "invoice"},
            )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "UNSUPPORTED_DOCUMENT_TYPE"

    async def test_accepts_exactly_the_cap(self):
        with patch("app.api.v1.analyze.AnalyzeService") as M:
            M.return_value.analyze = AsyncMock(return_value=_result())
            async with _client() as c:
                resp = await c.post(
                    "/api/v1/analyze/batch",
                    files=_jpgs(MAX_BATCH_FILES),
                    data={"document_type": "handover_photo"},
                )
        assert resp.status_code == 200
        assert resp.json()["total"] == MAX_BATCH_FILES


class TestHappyPath:
    async def test_returns_one_result_per_file_in_order(self):
        with patch("app.api.v1.analyze.AnalyzeService") as M:
            M.return_value.analyze = AsyncMock(side_effect=lambda **kw: _result(kw["filename"]))
            async with _client() as c:
                resp = await c.post(
                    "/api/v1/analyze/batch",
                    files=_jpgs(3),
                    data={"document_type": "handover_photo"},
                )
        body = resp.json()
        assert resp.status_code == 200
        assert (body["total"], body["succeeded"], body["failed"]) == (3, 3, 0)
        assert body["document_type"] == "handover_photo"
        assert [r["index"] for r in body["results"]] == [0, 1, 2]
        assert [r["file_name"] for r in body["results"]] == ["p0.jpg", "p1.jpg", "p2.jpg"]
        assert all(r["status"] == "ok" for r in body["results"])

    async def test_few_shot_selected_once_for_whole_batch(self):
        with patch("app.api.v1.analyze.AnalyzeService") as M, \
             patch("app.api.v1.analyze.FewShotSelector") as Sel:
            M.return_value.analyze = AsyncMock(return_value=_result())
            Sel.return_value.select.return_value = ["範例"]
            async with _client() as c:
                await c.post("/api/v1/analyze/batch", files=_jpgs(5),
                             data={"document_type": "handover_photo"})
        assert Sel.return_value.select.call_count == 1

    async def test_concurrency_is_capped(self):
        """併發有上限,才不會一次打爆上游的速率限制。"""
        inflight = {"now": 0, "peak": 0}

        async def _slow(**kw):
            inflight["now"] += 1
            inflight["peak"] = max(inflight["peak"], inflight["now"])
            await asyncio.sleep(0.02)
            inflight["now"] -= 1
            return _result(kw["filename"])

        with patch("app.api.v1.analyze.AnalyzeService") as M:
            M.return_value.analyze = AsyncMock(side_effect=_slow)
            async with _client() as c:
                resp = await c.post("/api/v1/analyze/batch", files=_jpgs(12),
                                    data={"document_type": "handover_photo"})
        assert resp.json()["succeeded"] == 12
        assert inflight["peak"] <= BATCH_MAX_CONCURRENT
        # 正對照組:真的有重疊,否則這條測試等於什麼都沒驗
        assert inflight["peak"] > 1


class TestPartialFailure:
    """S7:一張壞掉不可以讓另外十九張重傳。"""

    async def test_incompatible_file_fails_only_that_item(self):
        files = [
            ("files", ("ok1.jpg", b"\xff\xd8\xff", "image/jpeg")),
            ("files", ("bad.pdf", b"%PDF-1.4", "application/pdf")),
            ("files", ("ok2.jpg", b"\xff\xd8\xff", "image/jpeg")),
        ]
        with patch("app.api.v1.analyze.AnalyzeService") as M:
            M.return_value.analyze = AsyncMock(side_effect=lambda **kw: _result(kw["filename"]))
            async with _client() as c:
                resp = await c.post("/api/v1/analyze/batch", files=files,
                                    data={"document_type": "handover_photo"})
        body = resp.json()
        assert resp.status_code == 200
        assert (body["succeeded"], body["failed"]) == (2, 1)
        bad = body["results"][1]
        assert bad["status"] == "error"
        assert bad["file_name"] == "bad.pdf"
        assert bad["error_code"] == "INCOMPATIBLE_FILE_TYPE"
        assert bad["result"] is None
        assert [body["results"][0]["status"], body["results"][2]["status"]] == ["ok", "ok"]

    async def test_service_exception_fails_only_that_item(self):
        async def _flaky(**kw):
            if kw["filename"] == "p1.jpg":
                raise RuntimeError("上游炸了")
            return _result(kw["filename"])

        with patch("app.api.v1.analyze.AnalyzeService") as M:
            M.return_value.analyze = AsyncMock(side_effect=_flaky)
            async with _client() as c:
                resp = await c.post("/api/v1/analyze/batch", files=_jpgs(3),
                                    data={"document_type": "handover_photo"})
        body = resp.json()
        assert (body["succeeded"], body["failed"]) == (2, 1)
        assert body["results"][1]["error_code"] == "PROCESSING_ERROR"
        # 對外不吐上游的原始錯誤字串
        assert "上游炸了" not in body["results"][1]["detail"]

    async def test_all_failed_still_returns_200_with_counts(self):
        files = [("files", (f"b{i}.pdf", b"%PDF-1.4", "application/pdf")) for i in range(3)]
        async with _client() as c:
            resp = await c.post("/api/v1/analyze/batch", files=files,
                                data={"document_type": "handover_photo"})
        body = resp.json()
        assert resp.status_code == 200
        assert (body["succeeded"], body["failed"]) == (0, 3)
        assert all(r["status"] == "error" for r in body["results"])

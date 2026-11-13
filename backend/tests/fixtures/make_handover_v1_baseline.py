"""產生點交照片「不帶 handover_format」的改前基準（handover-photo-v2 A0）。

用法（backend/ 下）:
    venv/bin/python tests/fixtures/make_handover_v1_baseline.py

在 df41f2d、程式未改前執行一次，輸出 tests/fixtures/handover_v1_baseline.json。
之後 test_handover_photo_v2.py 匯入本檔的 CASES 與 run_case()，用新程式跑同一組
假模型回覆，輸出必須與固定檔逐鍵逐值相同（R2、A1）。

每組假回覆跑三層：
- understand：HandoverPhotoProcessor.understand() 的回傳
- analyze：AnalyzeService.analyze()（S3 上傳回固定 URL、用量紀錄不寫）後再跑
  _apply_confidence_gating（複核佇列打樁，記下入列內容、回固定 id）的整份回應
- enqueued：送進複核佇列的內容（沒入列則為 None）
每次會變的 stats.total_time_ms 一律清成 0。
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent.parent
OUT = HERE / "handover_v1_baseline.json"
FIXED_URL = "https://example.invalid/handover.png"
FIXED_REVIEW_ID = "00000000-0000-0000-0000-000000000001"

# 假模型回覆。值是字串＝模型回的原文；"__RAISE__"＝模型呼叫丟例外。
CASES = {
    "normal": json.dumps({
        "space": "房間",
        "furniture": [{"name": "雙人床", "confidence": 0.93}, {"name": "衣櫃", "confidence": 0.71}],
        "appliance": [{"name": "冷氣", "confidence": 0.9}],
        "description": "臥室，雙人床靠牆", "confidence": 0.9,
    }, ensure_ascii=False),
    "missing_item_confidence": json.dumps({
        "space": "房間", "furniture": ["雙人床", "衣櫃"], "appliance": [],
        "description": "臥室", "confidence": 0.3,
    }, ensure_ascii=False),
    "non_numeric_confidence": json.dumps({
        "space": "客廳", "furniture": [{"name": "沙發", "confidence": "高"}],
        "appliance": [{"name": "電視", "confidence": 1.5}],
        "description": "客廳", "confidence": 0.8,
    }, ensure_ascii=False),
    "wrong_array_and_unknown": json.dumps({
        "space": "廚房", "furniture": ["冰箱", "魔法掃帚"], "appliance": ["洗衣機"],
        "description": "廚房", "confidence": 0.85,
    }, ensure_ascii=False),
    "v2_shaped_reply": json.dumps({
        "space": "房間",
        "furniture": [
            {"name": "雙人床", "confidence": 0.93, "box_2d": [120, 450, 680, 950], "condition": ""},
            {"name": "衣櫃", "confidence": 0.71, "box_2d": [700, 100, 990, 900], "condition": "左門板下緣剝落"},
        ],
        "appliance": [],
        "damages": [{"text": "窗邊牆面水漬約手掌大", "box_2d": [700, 100, 850, 300]}],
        "description": "臥室，雙人床靠牆，右側衣櫃", "confidence": 0.9,
    }, ensure_ascii=False),
    "empty_reply": "",
    "exception": "__RAISE__",
}


def _png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _provider(reply: str):
    p = MagicMock()
    if reply == "__RAISE__":
        p.call = AsyncMock(side_effect=RuntimeError("假模型失敗"))
    else:
        p.call = AsyncMock(return_value=reply)
    return p


class _Queue:
    """取代 ReviewQueueService：記下入列內容、回固定 id。"""
    calls: list = []

    def __init__(self, db):
        pass

    def enqueue(self, document_id, document_type, overall_confidence, result):
        _Queue.calls.append({
            "document_id": document_id,
            "document_type": str(getattr(document_type, "value", document_type)),
            "overall_confidence": overall_confidence,
            "result": json.loads(json.dumps(result, ensure_ascii=False, default=str)),
        })
        return FIXED_REVIEW_ID


def _scrub(resp: dict) -> dict:
    resp = json.loads(json.dumps(resp, ensure_ascii=False, default=str))
    if isinstance(resp.get("stats"), dict):
        resp["stats"]["total_time_ms"] = 0
    return resp


async def run_case(reply: str, **analyze_kwargs) -> dict:
    """跑一組假回覆的三層輸出。analyze_kwargs 原樣傳給 AnalyzeService.analyze（v2 測試用）。"""
    from app.api.v1 import analyze as analyze_api
    from app.lib.multi_type_ocr.handover_photo_processor import HandoverPhotoProcessor
    from app.services.analyze_service import AnalyzeService

    understand = await HandoverPhotoProcessor(provider=_provider(reply)).understand("AAAA")

    _Queue.calls = []
    with patch.object(HandoverPhotoProcessor, "_default_provider", staticmethod(lambda: _provider(reply))), \
         patch.object(AnalyzeService, "_upload_to_s3", AsyncMock(return_value=FIXED_URL)), \
         patch.object(AnalyzeService, "_record_usage", MagicMock(return_value=None)), \
         patch.object(analyze_api, "ReviewQueueService", _Queue):
        result = await AnalyzeService().analyze(
            file_contents=_png(), filename="room.png", document_type="handover_photo",
            enable_llm=True, question=None, few_shot=None, **analyze_kwargs,
        )
        analyze_api._apply_confidence_gating(result, db=None)

    return {
        "understand": json.loads(json.dumps(understand, ensure_ascii=False)),
        "analyze": _scrub(result),
        "enqueued": _Queue.calls[0] if _Queue.calls else None,
    }


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=BACKEND.parent, capture_output=True, text=True).stdout


async def _main():
    cases = {name: await run_case(reply) for name, reply in CASES.items()}
    data = {
        "_meta": {
            "sha": _git("rev-parse", "HEAD").strip(),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_status_backend": _git("status", "--porcelain", "--untracked-files=all", "--", "backend"),
            "generator": "backend/tests/fixtures/make_handover_v1_baseline.py",
        },
        "cases": cases,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"寫入 {OUT}（{len(cases)} 組）sha={data['_meta']['sha'][:7]}")
    print("git status --porcelain -- backend:\n" + data["_meta"]["git_status_backend"])


if __name__ == "__main__":
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    asyncio.run(_main())

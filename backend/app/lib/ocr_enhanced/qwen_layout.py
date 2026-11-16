"""
Qwen 讀字(OCR 引擎 `qwen`)的回覆解析與全文組裝——純函式,不連外、不讀設定。

模型對每一段文字回一行 JSON:`{"bbox_2d": [x1, y1, x2, y2], "text": "..."}`,座標是
0–1000 的相對座標。這裡把它變成跟 PaddleOCR 一樣的行框
`[{"text", "box": [x1, y1, x2, y2]}]`(0–1 比例),再組成全文。

全文有兩種組法(設定 QWEN_OCR_TEXT_LAYOUT 選,量測要同一份 lines 兩種都算):

- `join`:依模型回的閱讀順序逐段 `"\\n".join`。
- `rebuild`:依座標分行、依 x 補縮排。照搬 2026-11-09 評估的
  `~/jgb-archive/transcript-photo-fullparse-eval-20261109/rebuild_only.py` `rebuild()`,
  只多一處防呆(見 `rebuild_text`)。

解析的收段條件照搬同一次評估 `run_qwen_grounded.py` `parse()`(取段改用 JSON 解碼器,見 `_iter_segments`),另加:座標夾到 [0, 1]、
x1≤x2、y1≤y2,非有限值(NaN、Infinity)那段不收。
"""

from __future__ import annotations

import json
import math
import statistics
import unicodedata
from typing import Any, Dict, List, Literal

QwenTextLayout = Literal["rebuild", "join"]
QWEN_TEXT_LAYOUTS = ("rebuild", "join")

_DECODER = json.JSONDecoder()


def _iter_segments(raw: str):
    """從回覆裡逐一取出含 "bbox_2d" 的 JSON 物件。

    用 JSON 解碼器從每個 `{` 試解,不用正規式比對大括號:謄本內文本身可能抄到 `{`、`}`
    (2026-11-16 S1 實測:士林建物頁整頁一段、text 內含 `{`,舊正規式 `[^{}]*` 整頁 0 段)。
    解得出又是段落 → 跳到該物件結尾;解得出但不是段落(例如外層包了一層)→ 往內找;
    解不出 → 從下一個 `{` 再試。
    """
    i = raw.find("{")
    while i != -1:
        try:
            data, end = _DECODER.raw_decode(raw, i)
        except ValueError:
            i = raw.find("{", i + 1)
            continue
        if isinstance(data, dict) and "bbox_2d" in data:
            yield data
            i = raw.find("{", end)
        else:
            i = raw.find("{", i + 1)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def parse_qwen_lines(raw: Any) -> List[Dict[str, Any]]:
    """模型回覆 → `[{"text", "box": [x1, y1, x2, y2]}]`(0–1 比例,依回覆順序)。

    夾雜說明文字、markdown 圍欄都不影響:只撈含 "bbox_2d" 的 JSON 物件(text 內含大括號也收)。
    壞 JSON、座標不是 4 個數字、text 不是字串或去空白後為空 → 那一段不收。
    text 原樣保留(不 strip),與評估一致。
    """
    lines: List[Dict[str, Any]] = []
    for data in _iter_segments(str(raw or "")):
        if not isinstance(data["bbox_2d"], list):
            continue
        try:
            coords = [float(v) / 1000 for v in data["bbox_2d"]]
        except (ValueError, TypeError, KeyError, OverflowError):
            continue
        text = data.get("text")
        if len(coords) != 4 or not isinstance(text, str) or not text.strip():
            continue
        if not all(math.isfinite(c) for c in coords):
            continue
        x1, y1, x2, y2 = (_clamp01(c) for c in coords)
        lines.append({
            "text": text,
            "box": [
                round(min(x1, x2), 4),
                round(min(y1, y2), 4),
                round(max(x1, x2), 4),
                round(max(y1, y2), 4),
            ],
        })
    return lines


def join_text(lines: List[Dict[str, Any]]) -> str:
    """依閱讀順序逐段接起(每段一行)。"""
    return "\n".join(line["text"] for line in lines)


def _display_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "FW" else 1 for c in s.rstrip())


def rebuild_text(lines: List[Dict[str, Any]]) -> str:
    """依座標分行、依 x 補縮排(評估 rebuild_only.py rebuild() 的搬移)。

    與評估唯一的差別:每字寬度的中位數 `unit` 為 0 時(多數框寬度為 0,例如座標
    全被夾到同一邊),評估版會除以 0;這裡改成不補縮排(各段之間仍至少兩個空白)。
    """
    ls = [l for l in lines if l["text"].strip()]
    if not ls:
        return ""
    unit = statistics.median(
        (l["box"][2] - l["box"][0]) / max(1, _display_width(l["text"])) for l in ls
    )
    hs = statistics.median(l["box"][3] - l["box"][1] for l in ls)
    ls.sort(key=lambda l: ((l["box"][1] + l["box"][3]) / 2, l["box"][0]))
    rows, cur = [], []
    for l in ls:
        yc = (l["box"][1] + l["box"][3]) / 2
        if cur and abs(yc - cur[-1][0]) > hs * 0.5:
            rows.append(cur)
            cur = []
        cur.append((yc, l))
    if cur:
        rows.append(cur)
    out = []
    for r in rows:
        line = ""
        for _, l in sorted(r, key=lambda t: t[1]["box"][0]):
            col = round(l["box"][0] / unit) if unit > 0 else 0
            line += " " * max(col - _display_width(line), 2 if line else 0) + l["text"]
        out.append(line)
    return "\n".join(out)


def build_full_text(lines: List[Dict[str, Any]], layout: str) -> str:
    """依 layout(`rebuild`/`join`)組全文;未知值報錯,不默默換成另一種。"""
    if layout == "rebuild":
        return rebuild_text(lines)
    if layout == "join":
        return join_text(lines)
    raise ValueError(f"未知的 QWEN_OCR_TEXT_LAYOUT「{layout}」;只接受 {list(QWEN_TEXT_LAYOUTS)}")


def full_text_variants(lines: List[Dict[str, Any]]) -> Dict[str, str]:
    """同一份 lines 的兩種全文(量測用:J/R 兩種接法跑同一批解析器)。"""
    return {layout: build_full_text(lines, layout) for layout in QWEN_TEXT_LAYOUTS}


__all__ = [
    "QwenTextLayout",
    "QWEN_TEXT_LAYOUTS",
    "parse_qwen_lines",
    "join_text",
    "rebuild_text",
    "build_full_text",
    "full_text_variants",
]

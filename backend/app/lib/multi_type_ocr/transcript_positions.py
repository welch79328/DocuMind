"""
謄本電子 PDF 的值位置(S2,計畫 .kiro/specs/transcript-records-converge/plan-s2.md §2)

帶 transcript_format="v2" 時,transcript_records 每個值旁附 position:
  {"page": 1 起算, "box": [x0, y0, x1, y1] 0~1 比例, "unit": "ratio"};對不到值本身一律 None(不給近似框)。

做法(位置在解析當下記下,不事後搜尋全文):
1. 以 track=True 重新解析各頁文字,值與標籤是 Located(逐字帶「頁、行、欄」);
2. 沿 build_with_trace 的去處(trace)把每個輸出值對到原文 Located 的某一段字;
3. 欄 → 原文字元(逐字 normalize_for_matching 累計長度)→ PyMuPDF rawdict 逐字框 → 同頁外接矩形 ÷ 頁寬高。
任一步對不上 → 該值(或該頁全部)None。
"""

import bisect
import re
from typing import Any, Dict, List, Optional, Tuple

from .text_normalize import normalize_for_matching
from .transcript_full_parser import Located, parse_transcript_pages
from .transcript_records import _NUM, _YM, build_with_trace, to_number

_SKIP_KEYS = ("判定", "部是否印出")
_ND = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# 頁幾何:(行, 欄) → rawdict 字框
# ---------------------------------------------------------------------------
class _Geo:
    """一頁的對位表。建構時檢查文字與 rawdict 逐字相同、逐字正規化串接等於整段正規化,不符就是 None(整頁 null)。"""

    def __init__(self, text: str, chars: List[Tuple[str, Tuple[float, float, float, float]]], w: float, h: float):
        self.w, self.h, self.chars = w, h, chars
        per = [normalize_for_matching(ch) for ch in text]
        nstr = "".join(per)
        self.cum: List[int] = []
        acc = 0
        for p in per:
            self.cum.append(acc)
            acc += len(p)
        self.nlen = acc
        self.line_start: List[int] = []
        pos = 0
        for ln in nstr.splitlines(keepends=True):
            self.line_start.append(pos)
            pos += len(ln)
        self.ok = nstr == normalize_for_matching(text)
        # 原文字元索引 → rawdict 字元索引(rawdict 沒有換行)
        self.raw_idx: List[Optional[int]] = []
        k = 0
        for ch in text:
            if ch == "\n":
                self.raw_idx.append(None)
            else:
                self.raw_idx.append(k)
                k += 1

    def char_box(self, line: int, col: int):
        if line >= len(self.line_start):
            return None
        g = self.line_start[line] + col
        if g < 0 or g >= self.nlen:
            return None
        j = bisect.bisect_right(self.cum, g) - 1
        k = self.raw_idx[j] if 0 <= j < len(self.raw_idx) else None
        return self.chars[k] if k is not None else None


def _page_geometries(file_contents: bytes, texts: List[str]) -> List[Optional[_Geo]]:
    import fitz
    doc = fitz.open(stream=file_contents, filetype="pdf")
    try:
        if len(doc) != len(texts):
            return [None] * len(texts)
        out: List[Optional[_Geo]] = []
        for page, text in zip(doc, texts):
            try:
                rd = page.get_text("rawdict")
                chars = [(c["c"], tuple(c["bbox"])) for b in rd["blocks"] if b.get("type") == 0
                         for ln in b["lines"] for s in ln["spans"] for c in s["chars"]]
                if page.rotation != 0 or "".join(c for c, _ in chars) != text.replace("\n", ""):
                    out.append(None)
                    continue
                geo = _Geo(text, chars, page.rect.width, page.rect.height)
                out.append(geo if geo.ok and geo.w > 0 and geo.h > 0 else None)
            except Exception:
                out.append(None)
        return out
    finally:
        doc.close()


def _frame(cm: List[Any], geos: List[Optional[_Geo]]) -> Optional[Dict[str, Any]]:
    """cm=[(頁, 行, 欄)|None] → position。值跨頁只框第一頁;空白字不參與外接矩形。"""
    real = [c for c in cm if c is not None]
    if not real:
        return None
    pno = real[0][0]
    geo = geos[pno - 1] if 1 <= pno <= len(geos) else None
    if geo is None:
        return None
    boxes = []
    for p, line, col in real:
        if p != pno:
            continue
        cb = geo.char_box(line, col)
        if cb is None:
            return None
        if cb[0].strip():
            boxes.append(cb[1])
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes) / geo.w
    y0 = min(b[1] for b in boxes) / geo.h
    x1 = max(b[2] for b in boxes) / geo.w
    y1 = max(b[3] for b in boxes) / geo.h
    clamp = lambda x: round(min(1.0, max(0.0, x)), 4)
    return {"page": pno, "box": [clamp(x0), clamp(y0), clamp(x1), clamp(y1)], "unit": "ratio"}


# ---------------------------------------------------------------------------
# 輸出值 → 原文 Located 的哪一段字
# ---------------------------------------------------------------------------
def _find_substring(value: str, sv: Any) -> Optional[list]:
    """value(去空白)是 sv(去空白)的子字串 → 那一段的逐字位置;否則 None。"""
    if not isinstance(sv, Located):
        return None
    nv = _ND.sub("", value)
    if not nv:
        return None
    idx = [i for i, ch in enumerate(sv) if not ch.isspace()]
    nsv = "".join(sv[i] for i in idx)
    k = nsv.find(nv)
    if k < 0:
        return None
    cm = [sv.cm[i] for i in idx[k:k + len(nv)]]
    return None if any(c is None for c in cm) else cm


def _same_number(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a == b


def _find_number(value: Any, sv: Any) -> Optional[list]:
    """數字:to_number 取到的那個數字記號;值不是整段的唯一數字時(例:共有部分「建號 面積」),取最後一個相等的記號。"""
    if not isinstance(sv, Located):
        return None
    m = _YM.match(sv)
    start = m.end() if m else 0
    toks = list(_NUM.finditer(str(sv), start))
    hit = None
    if len(toks) == 1 and _same_number(to_number(str(sv)), value):
        hit = toks[0]
    else:
        for t in toks:
            n = t.group(0).replace(",", "")
            if _same_number(float(n) if "." in n else int(n), value):
                hit = t
    if hit is None:
        return None
    cm = sv.cm[hit.start():hit.end()]
    return None if any(c is None for c in cm) else cm


def _node(t: Dict[str, Any], path: tuple) -> Tuple[Any, Any]:
    """依 source_leaves 的路徑格式取得原文葉子與「最近的標籤鍵」(dict 鍵物件,Located)。"""
    head = path[0]
    key = None
    if head == "頁首":
        o, rest = t.get("header"), path[1:]
    elif head == "注意事項":
        o, rest = t.get("注意事項"), path[1:]
    else:
        sec = t["sections"][path[1]]
        if path[2] == "筆":
            o, rest = sec["entries"][path[3]], path[4:]
        else:
            o, rest = sec[path[2]], path[3:]
    for step in rest:
        if isinstance(o, dict):
            if step != "_值":
                key = next(k for k in o if k == step)
            o = o[step]
        else:
            o = o[step]
    return o, key


def _source_cm(value: Any, leaf: str, sv: Any, key: Any, how: str) -> Optional[list]:
    if how == "頁數":
        return None
    if how == "標籤":
        return key.cm if isinstance(key, Located) and isinstance(value, str) and str(key) == value else None
    if how == "其他登記事項子項" and leaf == "標籤":
        return key.cm if isinstance(key, Located) and isinstance(value, str) and str(key) == value else None
    if how == "其他欄位" and leaf != "值":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return _find_number(value, sv)
    if isinstance(value, str):
        return _find_substring(value, sv)
    return None


def _leaves(o: Any, path: str = ""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _leaves(v, f"{path}.{k}" if path else k)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _leaves(v, f"{path}[{i}]")
    elif o is not None:
        yield path, o


def _dest_candidates(path: str):
    """葉子路徑由長到短的去處前綴(只在 "." 與 "[" 邊界切)。"""
    yield path
    for i in range(len(path) - 1, 0, -1):
        if path[i] in ".[":
            yield path[:i]


def _sheet_positions(t: Dict[str, Any], rec: Dict[str, Any], trace: list, geos: List[Optional[_Geo]]):
    """一張謄本:{葉子路徑: (值, position)};只放有位置的。"""
    bydest: Dict[str, list] = {}
    for src, dest, how in trace:
        bydest.setdefault(dest, []).append((src, how))
    out: Dict[str, Tuple[Any, Dict[str, Any]]] = {}
    for path, value in _leaves({k: v for k, v in rec.items() if k not in _SKIP_KEYS}):
        leaf = path.rsplit(".", 1)[-1]
        cm = None
        if path == "類型":
            title = (t.get("header") or {}).get("謄本種類")
            cm = _find_substring(value, title) if isinstance(value, str) else None
        else:
            dest = next((d for d in _dest_candidates(path) if d in bydest), None)
            for src, how in (bydest.get(dest) or []):
                try:
                    sv, key = _node(t, src)
                except (KeyError, IndexError, StopIteration, TypeError):
                    continue
                cm = _source_cm(value, leaf, sv, key, how)
                if cm:
                    break
        if cm:
            pos = _frame(cm, geos)
            if pos:
                out[path] = (str(value) if isinstance(value, str) else value, pos)   # Located → 純 str
    return out


def compute_positions(texts: List[str], file_contents: bytes, records: List[Dict[str, Any]]):
    """各頁文字 + 原檔 + 已建好的 transcript_records → 每張一份 {葉子路徑: (值, position)}。

    以 track=True 重建 records,與傳入的不同就回 None(整份 position 維持 null,不讓位置對到另一份解析)。"""
    transcripts = parse_transcript_pages(texts, track=True)
    rebuilt, traces = build_with_trace(transcripts)
    if rebuilt != records:
        return None
    geos = _page_geometries(file_contents, texts)
    return [_sheet_positions(t, r, tr, geos) for t, r, tr in zip(transcripts, rebuilt, traces)]

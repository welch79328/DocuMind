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


# ---------------------------------------------------------------------------
# 照片／無文字層 PDF(S3,計畫 plan-s3.md §2 路徑 5):值文字反查 OCR 行,框到「值所在的那一行」
# ---------------------------------------------------------------------------
def _n(s: Any) -> str:
    return _ND.sub("", normalize_for_matching(str(s)))


def _exif_rotated(file_contents: Optional[bytes]) -> bool:
    """影像檔 EXIF Orientation 標記存在且不是 1 → True(框的座標系與下游看到的方向不同,不猜)。PDF 不適用。"""
    if not file_contents or file_contents[:5] == b"%PDF-":
        return False
    try:
        import io
        from PIL import Image
        with Image.open(io.BytesIO(file_contents)) as im:
            o = im.getexif().get(0x0112)
        return o is not None and o != 1
    except Exception:
        return False     # 讀不出標記不當作有旋轉


def _page_text(p: Dict[str, Any]) -> str:
    # 與 analyze_service._attach_full_transcripts 取同一份文字解析
    return (p.get("rule_postprocessed") or {}).get("text") or (p.get("ocr_raw") or {}).get("text") or ""


def _located_pages(o: Any, acc: set) -> None:
    """transcript 內所有 Located(值與 dict 鍵)出現過的頁(1 起算)。"""
    if isinstance(o, Located):
        acc.update(c[0] for c in o.cm if c is not None)
    elif isinstance(o, str):
        return
    if isinstance(o, dict):
        for k, v in o.items():
            _located_pages(k, acc)
            _located_pages(v, acc)
    elif isinstance(o, (list, tuple)):
        for v in o:
            _located_pages(v, acc)


def _sheet_page_sets(pages: List[Dict[str, Any]], records: List[Dict[str, Any]]) -> Optional[List[set]]:
    """每張謄本出現在哪幾頁(pages 的索引 0 起算);帳目拿不到或與 records 對不上 → None(候選用全部頁)。"""
    if len(pages) < 2:
        return None
    try:
        from .transcript_full_parser import parse_with_ledger
        transcripts = parse_with_ledger([_page_text(p) for p in pages], track=True)[0]
        rebuilt, _ = build_with_trace(transcripts)
        if rebuilt != records:
            return None
        out = []
        for t in transcripts:
            acc: set = set()
            _located_pages(t, acc)
            out.append({n - 1 for n in acc})
        return out
    except Exception:
        return None


def _pick_line(value: Any, path: str, cands: List[tuple], rank: int = 0, sibs: Tuple[str, ...] = ()) -> tuple:
    """cands=[(頁, 行 dict, 正規化行文字)] 非空,依頁序、OCR 行序。
    多行:先找「葉鍵與上一層鍵名(去掉 [i])出現在值之前」個數最多的第一行,再從它起往下數第 rank 個候選
    (rank＝同一清單、同一欄位、同一個值在這一項之前出現過幾次,例:四個層次面積都是 96.51 → 依序第 0～3 行);
    不夠就取最後一個。
    鍵名最多的行裡有一行也印了同一清單項目的其他欄位值(sibs,已正規化)→ 取那一行、不往下數
    (例:「建物坐落地號：公園段三小段 0167-0000 0168-0000」一行印了兩筆的段小段);只看鍵名最多的行,
    不看別部的行(他項權利部的「共同擔保地號」「債務人」行常重複印這些值);鍵名一個都沒對上時不用這條
    (OCR 常把值拆到沒印鍵名的下一行,這時其他欄位值會把它拉到別部)。"""
    if len(cands) == 1:
        return cands[0]
    segs = [re.sub(r"\[\d+\]", "", s) for s in path.split(".")]
    labs = [_n(s) for s in segs[-2:] if _n(s)]
    nv = _n(value)

    def n_labels_before(c):
        t = c[2]
        vi = t.find(nv) if nv in t else len(t)
        return sum(1 for lb in labs if 0 <= t.find(lb) < vi)

    # 鍵名在值之前對上最多的行;同數取先(例:「層次面積 95.41」勝過「總面積 95.41」)
    best = max(n_labels_before(c) for c in cands)
    tops = [c for c in cands if n_labels_before(c) == best]
    with_sib = [c for c in tops if any(sv in c[2] for sv in sibs)] if best > 0 else []
    if with_sib:
        return with_sib[0]
    # 從第一個最高分的行起往下數第 rank 個候選(續行常不印鍵名,例「層次面積：96.51」下面接「96.51」)
    seq = cands[next(i for i, c in enumerate(cands) if n_labels_before(c) == best):]
    return seq[min(rank, len(seq) - 1)]


def _page_head(lines: List[tuple]) -> Optional[str]:
    """頁首正規化文字:第一行到含「頁次」的那一行(每頁謄本頁首都印到頁次為止);前 12 行內沒有頁次 → None。"""
    for j, c in enumerate(lines[:12]):
        if "頁次" in c[2]:
            return "".join(x[2] for x in lines[:j + 1])
    return None


def _head_pages(rec: Dict[str, Any], heads: Dict[int, Optional[str]]) -> Optional[set]:
    """依每頁頁首印的編號與謄本種類,找這張謄本在哪幾頁(頁索引);頁首讀不到的頁一律留著。
    先比編號(謄本.編號,例 00465-000),都沒對上再比種類(類型 + 「登記」,例「建物登記」);都沒對上 → None(用全部頁)。"""
    unknown = {i for i, h in heads.items() if h is None}
    known = {i: h for i, h in heads.items() if h is not None}
    no = _n((rec.get("謄本") or {}).get("編號") or "")
    kind = _n(rec.get("類型") or "")
    for key in ([no] if no else []) + ([kind + "登記"] if kind else []):
        hit = {i for i, h in known.items() if key in h}
        if hit:
            return hit | unknown
    return None


def _clamp_box(box: List[float]) -> List[float]:
    return [round(min(1.0, max(0.0, float(x))), 4) for x in box]


def compute_photo_positions(
    pages: List[Dict[str, Any]],
    ocr_lines: Optional[Dict[int, List[Dict[str, Any]]]],
    file_contents: Optional[bytes],
    records: List[Dict[str, Any]],
    filled: List[Dict[str, Any]],
):
    """照片／無文字層 PDF → 每張一份 {葉子路徑: (值, position)}(只放有位置的);不適用 → None。

    pages:analyze 的頁結果;ocr_lines:{頁碼: [{"text","box"}]};records:補值前;filled:補值後(位置對補值後的值)。
    只用 text_layer 非 true、有行框、且 ocr_raw.text＝各行 text 以 \\n 相接的頁;EXIF 方向非 1 → None。"""
    if not ocr_lines or not pages or _exif_rotated(file_contents):
        return None
    usable: Dict[int, List[tuple]] = {}      # 頁索引 → [(頁碼, 行, 正規化行文字)]
    for i, p in enumerate(pages):
        if not isinstance(p, dict) or p.get("text_layer") is True:
            continue
        pno = p.get("page_number")
        lines = ocr_lines.get(pno)
        if not lines or "\n".join(l["text"] for l in lines) != (p.get("ocr_raw") or {}).get("text"):
            continue
        usable[i] = [(pno, l, _n(l["text"])) for l in lines]
    if not usable:
        return None
    sets = _sheet_page_sets(pages, records)
    heads = {i: _page_head(usable[i]) for i in usable}
    out = []
    for si, rec in enumerate(filled):
        # 帳目記到這張的頁 → 只用那些頁;帳目拿不到或沒記到(OCR 文字常解析不出帶來源的值)→ 改看每頁頁首;
        # 頁首也對不上 → 候選用全部頁(計畫 §2 路徑 5、AM-8)
        allowed = sets[si] if sets is not None and si < len(sets) and sets[si] else _head_pages(rec, heads)
        pool = [c for i in sorted(usable) if allowed is None or i in allowed for c in usable[i]]
        m: Dict[str, Tuple[Any, Dict[str, Any]]] = {}
        seen: Dict[tuple, int] = {}     # (去掉 [i] 的路徑, 值) → 之前出現過幾次(AM-9:清單第 k 次同值對第 k 個行)
        all_leaves = list(_leaves({k: v for k, v in rec.items() if k not in _SKIP_KEYS}))
        for path, value in all_leaves:
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                continue
            nv = _n(value)
            if not nv:
                continue
            is_num = isinstance(value, (int, float))
            cands = [c for c in pool
                     if nv in c[2] or (is_num and any(to_number(t) == value for t in _NUM.findall(c[2])))]
            if not cands:
                continue
            tk = (re.sub(r"\[\d+\]", "[]", path), nv)
            rank = seen.get(tk, 0) if "[" in path else 0
            seen[tk] = rank + 1
            sibs: Tuple[str, ...] = ()
            if "]" in path:                       # 同一清單項目的其他欄位值(AM-9)
                item = path[:path.rindex("]") + 1]
                sibs = tuple(x for x in (_n(v) for q, v in all_leaves
                                         if q != path and q.startswith(item + ".") and not isinstance(v, bool)
                                         and isinstance(v, (str, int, float)))
                             if x and x != nv)
            pno, line, _ = _pick_line(value, path, cands, rank, sibs)
            m[path] = (value, {"page": pno, "box": _clamp_box(line["box"]), "unit": "ratio"})
        out.append(m)
    return out

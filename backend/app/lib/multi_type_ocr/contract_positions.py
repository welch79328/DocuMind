"""
合約電子 PDF 的值位置(contract_format=v2,計畫 .kiro/specs/contract-v2-positions/plan.md §2)

帶 contract_format="v2" 時,document_fields.rental_terms 的六個欄位各包成
  {"value": 值, "position": {"page": 1 起算, "box": [x0, y0, x1, y1] 0~1 比例, "unit": "ratio"} 或 None}。
其他欄位、pages[] 與不帶參數的回應都不變。

position 只在下列全部成立時給,任一不成立就是 None(不給近似框):
1. 每頁都是文字層(照片、掃描檔線上走直讀,模型不回位置);
2. 以原檔重抽的文字層與回應的 pages[].ocr_raw.text 逐頁相同;
3. 依頁序找第一個該欄非 null、非空字串的頁(與 analyze_service._merge_fill_missing 同規則),
   在該頁重跑同一套比對(ContractFieldExtractor._match_fields)得到的值,與該頁、與 document_fields 三者相同;
4. 該頁幾何檢查通過(transcript_positions._page_geometries:文字與 rawdict 逐字相同、未旋轉);
5. 值的字不跨行(民國日期「中華民國113年」換行「1月1日」時,一個大框會框進不相干的字)。

位置取自抽出值的那一次比對,不事後拿值搜全文:同一字串可能出現多次(押金與租金同額)。
"""

import bisect
import copy
import logging
from typing import Any, Dict, List, Optional

from .contract_field_extractor import ContractFieldExtractor
from .transcript_positions import _Geo, _page_geometries

logger = logging.getLogger(__name__)

POSITION_FIELDS = ("date_start", "date_end", "monthly_rent", "deposit", "rental_address", "tenant_name")

_EMPTY = (None, "", [])


def apply_contract_format(result: Dict[str, Any], file_contents: bytes) -> Dict[str, Any]:
    """回傳轉換後的深拷貝;rental_terms 不存在時其餘不變(不補空殼)。"""
    out = copy.deepcopy(result)
    df = out.get("document_fields")
    rt = df.get("rental_terms") if isinstance(df, dict) else None
    if not isinstance(rt, dict):
        return out
    try:
        positions = _positions(out, file_contents, rt)
    except Exception as e:  # 位置是附加資訊:任何失敗都只讓位置變 None,不影響回應
        logger.warning("合約 v2 位置計算失敗,六欄 position 給 null: %s", e)
        positions = {}
    for name in POSITION_FIELDS:
        rt[name] = {"value": rt.get(name), "position": positions.get(name)}
    return out


def _positions(out: Dict[str, Any], file_contents: bytes, rt: Dict[str, Any]) -> Dict[str, Optional[dict]]:
    pages = out.get("pages") or []
    if not pages or not file_contents:
        return {}
    if any(p.get("text_layer") is not True for p in pages):
        return {}
    if [p.get("page_number") for p in pages] != list(range(1, len(pages) + 1)):
        return {}

    from app.lib.pdf_text_layer import extract_text_layer_pages

    texts = [(p.get("ocr_raw") or {}).get("text") for p in pages]
    fresh = extract_text_layer_pages(file_contents)
    if len(fresh) != len(pages) or any(f["ocr_raw"]["text"] != t for f, t in zip(fresh, texts)):
        return {}

    extractor = ContractFieldExtractor()
    matches: Dict[int, dict] = {}
    geos: Optional[List[Optional[_Geo]]] = None
    found: Dict[str, Optional[dict]] = {}

    for name in POSITION_FIELDS:
        value = rt.get(name)
        if value in _EMPTY:
            continue
        idx = _first_page_with(pages, name)
        if idx is None or pages[idx]["structured_data"]["rental_terms"][name] != value:
            continue
        if idx not in matches:
            matches[idx] = extractor._match_fields(texts[idx])
        hit = matches[idx].get(name)
        if not hit or hit[0] != value:
            continue
        if geos is None:
            geos = _page_geometries(file_contents, texts)
        found[name] = _box(geos[idx], texts[idx], hit[1], idx + 1)
    return found


def _first_page_with(pages: List[dict], name: str) -> Optional[int]:
    """依頁序第一個該欄非 null、非空字串的頁(同 _merge_fill_missing 的「先到先贏」)。"""
    for i, page in enumerate(pages):
        sd = page.get("structured_data")
        terms = sd.get("rental_terms") if isinstance(sd, dict) else None
        if isinstance(terms, dict) and terms.get(name) not in _EMPTY:
            return i
    return None


def _box(geo: Optional[_Geo], text: str, span, page_no: int) -> Optional[dict]:
    """正規化文字上的 (起, 迄) → 原文字元 → rawdict 字框 → 外接矩形 ÷ 頁寬高。"""
    if geo is None:
        return None
    start, end = span
    if not (0 <= start < end <= geo.nlen):
        return None
    originals = sorted({bisect.bisect_right(geo.cum, g) - 1 for g in range(start, end)})
    boxes = []
    for j in originals:
        if not 0 <= j < len(text):
            return None
        ch = text[j]
        if ch == "\n":
            return None  # 跨行:不給橫跨兩行的大框
        if not ch.strip():
            continue
        k = geo.raw_idx[j]
        if k is None:
            return None
        boxes.append(geo.chars[k][1])
    if not boxes:
        return None
    clamp = lambda x: round(min(1.0, max(0.0, x)), 4)
    return {
        "page": page_no,
        "box": [
            clamp(min(b[0] for b in boxes) / geo.w),
            clamp(min(b[1] for b in boxes) / geo.h),
            clamp(max(b[2] for b in boxes) / geo.w),
            clamp(max(b[3] for b in boxes) / geo.h),
        ],
        "unit": "ratio",
    }

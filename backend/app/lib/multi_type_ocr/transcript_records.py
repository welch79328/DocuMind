"""
謄本固定輸出格式 transcript_records(2026-10-15,驗收清單 .kiro/specs/transcript-fixed-schema/acceptance.md)

transcripts(transcript_full_parser)依原文標籤回傳,鍵名跟著謄本變;下游要的是一張固定表單
(業主:「一個 api 每次都傳不固定欄位 這樣合理嗎」→ 選定「固定輸出格式」)。本模組把 transcripts
放進依官方謄本格式定的固定鍵:每張謄本一筆,鍵一律存在,謄本沒印 → null/[]。

輸入只用 transcripts 已分好的張/部/筆與「標籤:值」,不重讀原文、不改解析器。規則:
1. 部＋原文標籤 → 固定鍵(下方 *_KEYS 表,即輸出規格本身)。表外的標籤原樣放進「其他欄位」,一個不丟。
2. 要再拆的衍生鍵(行政區/段/小段、查驗碼、共有部分建號與面積、坐落地號…)只依值的性質或官方版面拆;
   拆不開 → 該鍵 null,原文進「其他欄位」並註明原因。不寫欄位片語、不猜。
3. 判定(他項權利/限制登記/信託)只輸出 有/未見/無法判定,**不輸出「無」**:未見只表示這份謄本上沒印。
   比對詞全部來自 transcript_records_codes.json(地政司公開代碼表),一律整串相等,不做「包含」——
   代碼表自己的限制性註記句(含「預告登記」「信託」字樣)與「塗銷查封」都不能被判成有。

build_with_trace 另回傳每個原文值的去處(驗收 R2/R3 對帳用);API 只用 build_transcript_records。

⚠️ 「部的附註」放在外層「部附註」:所有權部、他項權利部是陣列,附註是整個部的說明句,不屬於任何一筆。
⚠️ 判定比對「整項」時,比的是項目冒號前那一段(沒有冒號則整項):代碼表的格式是 Information＋Content,
   例如 GH「信託財產，信託內容詳信託專簿」後面接「：依○年○月○日收件…辦理」,仍是整串相等。
"""

import json
import logging
import os
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .text_normalize import is_blank_marker, normalize_for_matching

_CODES_PATH = os.path.join(os.path.dirname(__file__), "transcript_records_codes.json")
with open(_CODES_PATH, encoding="utf-8") as _f:
    CODES = json.load(_f)

logger = logging.getLogger(__name__)

PARTS = ("標示部", "所有權部", "他項權利部")
VERDICTS = ("有", "未見", "無法判定")

# ---- 固定鍵(輸出規格;依官方謄本格式,與 docs/api/transcript_records.schema.json 一致) ----
HEADER_KEYS = ("謄本種類", "類別", "申請範圍", "行政區", "段", "小段", "編號", "編號類型", "列印時間", "頁數",
               "查驗碼", "查驗碼標籤", "查驗網址", "資料管轄機關", "謄本核發機關", "頁首附註")
LAND_MARK_KEYS = ("登記日期", "登記原因", "地目", "等則", "面積", "使用分區", "使用地類別", "公告土地現值",
                  "公告土地現值年月", "地上建物建號", "其他登記事項")
BUILDING_MARK_KEYS = ("登記日期", "登記原因", "建物門牌", "建物坐落地號", "主要用途", "主要建材", "層數", "總面積",
                      "層次", "附屬建物", "建築完成日期", "共有部分", "其他登記事項")
OWNER_KEYS = ("次序", "登記次序", "登記日期", "登記原因", "原因發生日期", "所有權人", "統一編號", "出生日期", "住址",
              "管理者", "權利範圍", "權狀字號", "相關他項權利登記次序", "其他登記事項")
LAND_OWNER_KEYS = OWNER_KEYS + ("當期申報地價", "當期申報地價年月", "前次移轉現值", "地價備註事項")
RIGHT_KEYS = ("次序", "登記次序", "權利種類", "收件年期", "字號", "登記日期", "登記原因", "權利人", "統一編號", "住址",
              "債權額比例", "擔保債權總金額", "擔保債權種類及範圍", "擔保債權確定期日", "存續期間", "清償日期",
              "利息(率)", "遲延利息(率)", "違約金", "其他擔保範圍約定", "債務人及債務額比例", "權利標的",
              "標的登記次序", "設定權利範圍", "證明書字號", "設定義務人", "共同擔保地號", "共同擔保建號", "其他登記事項")

# 值的型別:原樣字串以外的鍵
NUMBER_KEYS = {"面積", "總面積", "公告土地現值", "當期申報地價", "擔保債權總金額"}
YEAR_MONTH_OF = {"公告土地現值": "公告土地現值年月", "當期申報地價": "當期申報地價年月"}
SHARE_KEYS = {"權利範圍", "設定權利範圍"}
SPLIT_LIST_KEYS = {"相關他項權利登記次序", "標的登記次序"}
LOT_KEYS = {"建物坐落地號", "共同擔保地號", "共同擔保建號"}
# 人名組:組長＋同組的統一編號/出生日期/住址(transcripts 以「組」或同筆平鋪兩種形式出現)
PERSON_KEYS = {"所有權人": ("統一編號", "出生日期", "住址"), "權利人": ("統一編號", "住址")}
# 平行標籤:依出現順序一對一配對
PAIRED = {
    "標示部": [("層次", "層次", "層次面積", "層次", "面積"), ("附屬建物", "附屬建物用途", "面積", "用途", "面積")],
    "所有權部": [("前次移轉現值", "前次移轉現值或原規定地價", "歷次取得權利範圍", "金額", "歷次取得權利範圍")],
}

_YM = re.compile(r"^\s*((?:民國)?\s*\d{2,3}\s*年\s*\d{1,2}\s*月)\s*")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_SHARE = re.compile(r"^(?:(全部)(?:\s*\d+\s*分之\s*\d+)?|(\d+)\s*分之\s*(\d+))$")
_TITLE = re.compile(r"(土地|建物)登記(第[一二三]類)謄本\s*\(([^()]*)\)")
_CATEGORY = re.compile(r"^\(([^()]*事項)\)\s*")
_ITEM_LABEL = re.compile(r"^([一-鿿]+)\s*:\s*")
_CODE = re.compile(r"^[A-Za-z0-9]+")
_URL = re.compile(r"https?://[^\s一-鿿]+")
_SHARED = re.compile(r"^(?P<loc>.*?)\s*(?P<no>\d+-\d+)\s*建號\s*(?P<area>\d[\d,]*(?:\.\d+)?)\s*平方公尺$")


def _norm(s: str) -> str:
    """比對用:正規化、去空白、去結尾冒號(代碼表原文「委託人：」的冒號是版面,不是內容)。"""
    return re.sub(r"\s+", "", normalize_for_matching(s or "")).rstrip(":")


_TOWNS = sorted(CODES["鄉鎮市區"], key=len, reverse=True)
_SYNONYMS = {(s["部"], s["標籤"]): s["歸一為"] for s in CODES["同義標籤"]}


def _match_set(kind: str, field: str) -> set:
    return {_norm(e["原文"]) for e in CODES["判定"][kind][field]}


# ---- 值的轉換(依值的性質) ----
def split_year_month(v: str) -> Tuple[Optional[str], str]:
    m = _YM.match(v or "")
    return (re.sub(r"\s+", "", m.group(1)), v[m.end():]) if m else (None, v)


def to_number(v: str):
    """去掉開頭年月後的唯一數字(去千分位);0 個或 2 個以上 → None。"""
    nums = _NUM.findall(split_year_month(v)[1])
    if len(nums) != 1:
        return None
    n = nums[0].replace(",", "")
    return float(n) if "." in n else int(n)


def to_share(v: str) -> Optional[str]:
    """權利範圍:「全部」或「a分之b」(「全部 1分之1」→「全部」,沿用 2.1.1)。認不出 → None。"""
    m = _SHARE.match((v or "").strip())
    if not m:
        return None
    return "全部" if m.group(1) else f"{m.group(2)}分之{m.group(3)}"


def split_district(s: str) -> Optional[Tuple[Optional[str], str, Optional[str]]]:
    """頁首地段 → (行政區, 段, 小段)。行政區＝全國鄉鎮市區名稱最長相符;拆不開 → None。"""
    s = (s or "").strip()
    town = next((t for t in _TOWNS if s.startswith(t)), None)
    rest = s[len(town):] if town else s
    if not rest:
        return None
    if rest.endswith("小段"):
        core = rest[:-2]
        k = core.rfind("段")
        if k < 0 or k == len(core) - 1:
            return None
        return town, core[:k + 1], core[k + 1:] + "小段"
    return town, rest, None


def split_lots(s: str) -> Optional[List[Dict[str, Optional[str]]]]:
    """「仁愛段六小段 0100-0000 0100-0001」→ [{段小段, 編號}];段小段沿用到下一個出現為止。拆不開 → None。"""
    out, cur, pending = [], None, False
    for tok in (s or "").split():
        if tok[0].isdigit():
            out.append({"段小段": cur, "編號": tok}); pending = False
        else:
            if pending:
                return None
            cur, pending = tok, True
    return out if out and not pending else None


def split_other_item(s: str) -> Dict[str, Optional[str]]:
    """其他登記事項的一項 → {類別, 標籤, 內容}。"""
    s = (s or "").strip()
    cat = None
    m = _CATEGORY.match(s)
    if m:
        cat, s = m.group(1), s[m.end():]
    label = None
    m = _ITEM_LABEL.match(s)
    if m:
        label, s = m.group(1), s[m.end():]
    return {"類別": cat, "標籤": label, "內容": s.strip() or None}


# ---- 原文值的列舉(對帳用;頁緣除外) ----
def source_leaves(t: Dict[str, Any]) -> Iterator[Tuple[tuple, str]]:
    def walk(path, v):
        if isinstance(v, dict):
            for k, x in v.items():
                yield from walk(path + (k,), x)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                yield from walk(path + (i,), x)
        elif v is not None:
            yield path, v
    yield from walk(("頁首",), t.get("header") or {})
    for si, sec in enumerate(t.get("sections") or []):
        for k, v in sec.items():
            if k == "部":
                continue
            if k == "entries":
                for ei, e in enumerate(v):
                    yield from walk(("部", si, "筆", ei), e)
            else:
                yield from walk(("部", si, k), v)
    yield from walk(("注意事項",), t.get("注意事項") or [])


class _Sheet:
    """一張謄本的建構狀態:輸出、其他欄位、去處(trace)。"""

    def __init__(self, t: Dict[str, Any]):
        self.t = t
        self.other: List[Dict[str, Any]] = []
        self.trace: List[Tuple[tuple, str, str]] = []   # (原文路徑, 去處, 方式)

    # -- 去處 --
    def mark(self, src: tuple, dest: str, how: str) -> None:
        self.trace.append((src, dest, how))

    def to_other(self, src: tuple, part: str, label: str, value: str, reason: str) -> None:
        self.other.append({"部": part, "標籤": label, "值": value, "原因": reason})
        self.mark(src, f"其他欄位[{len(self.other) - 1}]", "其他欄位")

    def rest_to_other(self, path: tuple, value: Any, part: str, label: str, reason: str) -> None:
        def walk(p, v, lab):
            if isinstance(v, dict):
                for k, x in v.items():
                    walk(p + (k,), x, lab if k == "_值" else f"{lab}.{k}")
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    walk(p + (i,), x, lab)
            elif v is not None:
                self.to_other(p, part, lab, v, reason)
        walk(path, value, label)

    # -- 單值 --
    def first(self, path: tuple, value: Any, part: str, label: str) -> Tuple[Optional[tuple], Optional[str]]:
        """取單值:清單 → 第一個(其餘進其他欄位);組 → _值(組員進其他欄位)。"""
        if isinstance(value, list):
            for i, x in enumerate(value[1:], 1):
                self.rest_to_other(path + (i,), x, part, label, "同一處重複的標籤")
            return self.first(path + (0,), value[0], part, label) if value else (None, None)
        if isinstance(value, dict):
            for k, x in value.items():
                if k != "_值":
                    self.rest_to_other(path + (k,), x, part, f"{label}.{k}", "不在固定清單")
            return (path + ("_值",), value["_值"]) if "_值" in value else (None, None)
        return path, value

    def scalar(self, path, value, part, label, dest, conv=None, conv_name="原樣"):
        p, v = self.first(path, value, part, label)
        if p is None:
            return None
        if is_blank_marker(v) or not str(v).strip():
            self.mark(p, dest, "空白")
            return None
        if conv is None:
            self.mark(p, dest, "原樣")
            return v
        out = conv(v)
        if out is None:
            self.to_other(p, part, label, v, f"無法{conv_name}")
            return None
        self.mark(p, dest, conv_name)
        return out

    def items(self, path, value, part, dest) -> List[Dict[str, Optional[str]]]:
        """其他登記事項 → [{類別, 標籤, 內容}];子標籤(因分割增加地號…)各成一項。"""
        out = []

        def add(p, v, sub_label=None):
            if is_blank_marker(v) or not str(v).strip():
                self.mark(p, dest, "空白")
                return
            item = split_other_item(v) if sub_label is None else {"類別": None, "標籤": sub_label, "內容": v.strip()}
            self.mark(p, f"{dest}[{len(out)}]", "其他登記事項" if sub_label is None else "其他登記事項子項")
            out.append(item)

        def walk(p, v, sub_label=None):
            if isinstance(v, list):
                for i, x in enumerate(v):
                    walk(p + (i,), x, sub_label)
            elif isinstance(v, dict):
                for k, x in v.items():
                    walk(p + (k,), x, sub_label if k == "_值" else k)
            elif v is not None:
                add(p, v, sub_label)
        walk(path, value)
        return out


def _as_list(path: tuple, value: Any) -> List[Tuple[tuple, Any]]:
    if isinstance(value, list):
        return [(path + (i,), x) for i, x in enumerate(value)]
    return [(path, value)]


def _is_list_key(k: str) -> bool:
    """固定鍵中值為陣列的鍵(與 docs/api/transcript_records.schema.json 一致);其餘鍵空值為 null"""
    return (k in ("層次", "附屬建物", "共有部分", "其他登記事項", "管理者", "前次移轉現值")
            or k in SPLIT_LIST_KEYS or k in LOT_KEYS)


def _blank_entry(keys) -> Dict[str, Any]:
    return {k: ([] if _is_list_key(k) else None) for k in keys}


def _blank_shared_part() -> Dict[str, Any]:
    """標示部.共有部分 一筆的固定鍵"""
    return {"坐落": None, "建號": None, "面積": None, "權利範圍": None, "其他登記事項": []}


def _put_entry_fields(sh: _Sheet, part: str, kind: str, entry_path: tuple, entry: Dict[str, Any],
                      keys: Tuple[str, ...], dest_prefix: str) -> Dict[str, Any]:
    """一筆(或標示部)的標籤 → 固定鍵。"""
    rec: Dict[str, Any] = _blank_entry(keys)
    pairs = {a: (out, b, ka, kb) for out, a, b, ka, kb in PAIRED.get(kind, []) if out in keys}
    paired_b = {b: a for a, (_, b, _, _) in pairs.items()}
    done = set()
    for label, value in entry.items():
        path = entry_path + (label,)
        dest = f"{dest_prefix}.{label}"
        if label in done:
            continue
        if label in pairs or label in paired_b:
            a = label if label in pairs else paired_b[label]
            out, b, ka, kb = pairs[a]
            done.update({a, b})
            rec[out] = _pair(sh, part, entry_path, entry, a, b, ka, kb, f"{dest_prefix}.{out}")
            continue
        if label.endswith("_前文") and label[:-3] in YEAR_MONTH_OF and YEAR_MONTH_OF[label[:-3]] in keys:
            ym_key = YEAR_MONTH_OF[label[:-3]]
            p, v = sh.first(path, value, part, label)
            ym, rest = split_year_month(v or "")
            if ym and not rest.strip():
                rec[ym_key] = ym; sh.mark(p, f"{dest_prefix}.{ym_key}", "年月")
            elif p is not None:
                sh.to_other(p, part, label, v, "無法取年月")
            continue
        if label == "次序" and "次序" in keys:
            rec["次序"] = sh.scalar(path, value, part, label, dest)
            continue
        if label in PERSON_KEYS and label in keys:
            _person(sh, part, path, value, label, rec, dest_prefix)
            continue
        if label == "管理者" and "管理者" in keys:
            rec["管理者"] = _managers(sh, part, path, value, f"{dest_prefix}.管理者")
            continue
        if label == "共有部分" and "共有部分" in keys:
            rec["共有部分"] = _shared_parts(sh, part, path, value, f"{dest_prefix}.共有部分")
            continue
        if label == "其他登記事項" and label in keys:
            rec[label] = sh.items(path, value, part, dest)
            continue
        if label in LOT_KEYS and label in keys:
            got = []
            for p, v in _as_list(path, value):
                if isinstance(v, (dict, list)):
                    sh.rest_to_other(p, v, part, label, "不在固定清單"); continue
                if is_blank_marker(v):
                    sh.mark(p, dest, "空白"); continue
                lots = split_lots(v)
                if lots is None:
                    sh.to_other(p, part, label, v, "無法拆成段小段與編號"); continue
                sh.mark(p, dest, "坐落地號"); got += lots
            rec[label] = got
            continue
        if label in SPLIT_LIST_KEYS and label in keys:
            got = []
            for p, v in _as_list(path, value):
                if isinstance(v, (dict, list)):
                    sh.rest_to_other(p, v, part, label, "不在固定清單"); continue
                if is_blank_marker(v):
                    sh.mark(p, dest, "空白"); continue
                sh.mark(p, dest, "以空白切開"); got += v.split()
            rec[label] = got
            continue
        if label in NUMBER_KEYS and label in keys:
            ym_key = YEAR_MONTH_OF.get(label)
            p, v = sh.first(path, value, part, label)
            if p is None:
                continue
            if is_blank_marker(v):
                sh.mark(p, dest, "空白"); continue
            n = to_number(v)
            if n is None:
                sh.to_other(p, part, label, v, "無法轉數字"); continue
            rec[label] = n
            sh.mark(p, dest, "數字")
            ym = split_year_month(v)[0]
            if ym_key and ym_key in keys and ym:
                if rec.get(ym_key) is None:
                    rec[ym_key] = ym
                sh.mark(p, f"{dest_prefix}.{ym_key}", "年月")
            continue
        if label in SHARE_KEYS and label in keys:
            rec[label] = sh.scalar(path, value, part, label, dest, to_share, "辨識權利範圍")
            continue
        if label in keys and label not in YEAR_MONTH_OF.values():
            rec[label] = sh.scalar(path, value, part, label, dest)
            continue
        sh.rest_to_other(path, value, part, label, "不在固定清單")
    return rec


def _person(sh, part, path, value, label, rec, dest_prefix):
    """人名組:組長 → 所有權人/權利人,同組的統一編號、出生日期、住址各歸固定鍵。"""
    if isinstance(value, list):
        for i, x in enumerate(value[1:], 1):
            sh.rest_to_other(path + (i,), x, part, label, "同一處重複的標籤")
        path, value = path + (0,), (value[0] if value else None)
    if not isinstance(value, dict):
        if value is not None:
            rec[label] = sh.scalar(path, value, part, label, f"{dest_prefix}.{label}")
        return
    if value.get("_值") is not None:
        rec[label] = sh.scalar(path + ("_值",), value["_值"], part, label, f"{dest_prefix}.{label}")
    if isinstance(value, dict):
        for k, x in value.items():
            if k == "_值":
                continue
            if k in PERSON_KEYS[label] and k in rec:
                rec[k] = sh.scalar(path + (k,), x, part, f"{label}.{k}", f"{dest_prefix}.{k}")
            else:
                sh.rest_to_other(path + (k,), x, part, f"{label}.{k}", "不在固定清單")


def _managers(sh, part, path, value, dest):
    out = []
    for p, v in _as_list(path, value):
        m = {"姓名": None, "統一編號": None, "住址": None}
        if isinstance(v, dict):
            m["姓名"] = sh.scalar(p + ("_值",), v.get("_值"), part, "管理者", f"{dest}[{len(out)}].姓名") if "_值" in v else None
            for k, x in v.items():
                if k == "_值":
                    continue
                if k in ("統一編號", "住址"):
                    m[k] = sh.scalar(p + (k,), x, part, f"管理者.{k}", f"{dest}[{len(out)}].{k}")
                else:
                    sh.rest_to_other(p + (k,), x, part, f"管理者.{k}", "不在固定清單")
        else:
            m["姓名"] = sh.scalar(p, v, part, "管理者", f"{dest}[{len(out)}].姓名")
        out.append(m)
    return out


def _shared_parts(sh, part, path, value, dest):
    out = []
    for p, v in _as_list(path, value):
        i = len(out)
        rec = _blank_shared_part()
        group = v if isinstance(v, dict) else {"_值": v}
        head_path = p + ("_值",) if isinstance(v, dict) else p
        head = group.get("_值")
        if head is not None:
            m = _SHARED.match((head or "").strip())
            if m:
                rec["坐落"] = m.group("loc").strip() or None
                rec["建號"] = m.group("no")
                rec["面積"] = to_number(m.group("area"))
                sh.mark(head_path, f"{dest}[{i}]", "共有部分")
            elif is_blank_marker(head):
                sh.mark(head_path, f"{dest}[{i}]", "空白")
            else:
                sh.to_other(head_path, part, "共有部分", head, "無法拆成建號與面積")
        for k, x in group.items():
            if k == "_值":
                continue
            if k == "權利範圍":
                rec["權利範圍"] = sh.scalar(p + (k,), x, part, "共有部分.權利範圍", f"{dest}[{i}].權利範圍",
                                         to_share, "辨識權利範圍")
            elif k == "其他登記事項":
                rec["其他登記事項"] = sh.items(p + (k,), x, part, f"{dest}[{i}].其他登記事項")
            else:
                sh.rest_to_other(p + (k,), x, part, f"共有部分.{k}", "不在固定清單")
        out.append(rec)
    return out


def _pair(sh, part, entry_path, entry, a, b, ka, kb, dest):
    """平行標籤依出現順序一對一配對;筆數不同或值轉不出 → [],兩邊原文進其他欄位(不猜配對)。"""
    la = _as_list(entry_path + (a,), entry.get(a)) if a in entry else []
    lb = _as_list(entry_path + (b,), entry.get(b)) if b in entry else []
    ok = len(la) == len(lb) and all(isinstance(v, str) for _, v in la + lb)
    rows = []
    if ok:
        for (pa, va), (pb, vb) in zip(la, lb):
            if ka == "金額":                          # 前次移轉現值:{年月, 金額, 歷次取得權利範圍}
                ym, _ = split_year_month(va)
                amount, share = to_number(va), to_share(vb)
                if amount is None or share is None:
                    ok = False; break
                rows.append(((pa, pb), {"年月": ym, "金額": amount, "歷次取得權利範圍": share}))
            else:
                area = to_number(vb)
                if area is None or not va.strip():
                    ok = False; break
                rows.append(((pa, pb), {ka: va, kb: area}))
    if not ok:
        for p, v in la:
            sh.rest_to_other(p, v, part, a, "配對失敗(筆數不同或值無法轉換)")
        for p, v in lb:
            sh.rest_to_other(p, v, part, b, "配對失敗(筆數不同或值無法轉換)")
        return []
    for i, ((pa, pb), _) in enumerate(rows):
        sh.mark(pa, f"{dest}[{i}]", "配對")
        sh.mark(pb, f"{dest}[{i}]", "配對")
    return [r for _, r in rows]


def _header(sh: _Sheet) -> Dict[str, Any]:
    h = sh.t.get("header") or {}
    out: Dict[str, Any] = {k: None for k in HEADER_KEYS}
    out["頁首附註"] = []
    for label, value in h.items():
        path = ("頁首", label)
        canon = _SYNONYMS.get(("頁首", label), label)
        if label == "謄本種類":
            p, v = sh.first(path, value, "頁首", label)
            if p is None or v is None:
                continue
            out["謄本種類"] = v; sh.mark(p, "謄本.謄本種類", "原樣")
            m = _TITLE.search(v)
            if m:
                out["類別"], out["申請範圍"] = m.group(2), m.group(3).strip()
                sh.mark(p, "謄本.類別", "衍生"); sh.mark(p, "謄本.申請範圍", "衍生")
            else:
                sh.to_other(p, "頁首", label, v, "無法取類別與申請範圍")
        elif label == "地段":
            p, v = sh.first(path, value, "頁首", label)
            if p is None or v is None:
                continue
            got = split_district(v)
            if got is None:
                sh.to_other(p, "頁首", label, v, "無法拆成行政區、段、小段"); continue
            out["行政區"], out["段"], out["小段"] = got
            for k in ("行政區", "段", "小段"):
                if out[k] is not None:
                    sh.mark(p, f"謄本.{k}", "地段")
        elif label in ("編號", "編號類型", "資料管轄機關", "謄本核發機關"):
            out[label] = sh.scalar(path, value, "頁首", label, f"謄本.{label}")
        elif label == "列印時間":
            vals = _as_list(path, value)
            if not vals or not all(isinstance(v, str) for _, v in vals):
                sh.rest_to_other(path, value, "頁首", label, "不在固定清單"); continue
            out["列印時間"] = vals[0][1]
            for p, v in vals:
                if v == vals[0][1]:
                    sh.mark(p, "謄本.列印時間", "原樣")
                else:
                    sh.to_other(p, "頁首", label, v, "各頁列印時間不同")
        elif label == "頁次":
            vals = _as_list(path, value)
            out["頁數"] = len(vals)
            for p, _ in vals:
                sh.mark(p, "謄本.頁數", "頁數")
        elif label == "附註":
            for p, v in _as_list(path, value):
                if isinstance(v, str):
                    sh.mark(p, f"謄本.頁首附註[{len(out['頁首附註'])}]", "原樣"); out["頁首附註"].append(v)
                else:
                    sh.rest_to_other(p, v, "頁首", label, "不在固定清單")
        elif canon == "謄本檢查號":
            p, v = sh.first(path, value, "頁首", label)
            if p is None or v is None:
                continue
            out["查驗碼標籤"] = label; sh.mark(p, "謄本.查驗碼標籤", "標籤")
            code, url = _CODE.match(v), _URL.search(v)
            if code:
                out["查驗碼"] = code.group(0); sh.mark(p, "謄本.查驗碼", "衍生")
            else:
                sh.to_other(p, "頁首", label, v, "無法取查驗碼")
            if url:
                out["查驗網址"] = url.group(0); sh.mark(p, "謄本.查驗網址", "衍生")
        else:
            sh.rest_to_other(path, value, "頁首", label, "不在固定清單")
    return out


def _sheet_type(t: Dict[str, Any]) -> Optional[str]:
    h = t.get("header") or {}
    title = h.get("謄本種類") if isinstance(h.get("謄本種類"), str) else ""
    m = re.match(r"\s*(土地|建物)", title or "")
    if m:
        return m.group(1)
    if h.get("編號類型") in ("地號", "建號"):
        return "土地" if h["編號類型"] == "地號" else "建物"
    for sec in t.get("sections") or []:
        if sec.get("部", "")[:2] in ("土地", "建物"):
            return sec["部"][:2]
    return None


def _verdicts(rec: Dict[str, Any]) -> Dict[str, str]:
    """⚠️ 「未見」還要求該申請範圍會印的部有讀到:掃描件的 OCR 文字常讀不出任何部,
    「沒看到他項權利部」不代表謄本上沒印,只能回無法判定。
    他項權利:各申請範圍都會印標示部(「標示部及他項權利部」不印所有權部),所以只要求標示部;
    限制登記、信託:未見只出現在全部類範圍,標示部與所有權部都會印,兩部都要求。"""
    scope = rec["謄本"]["申請範圍"]
    scopes = CODES["申請範圍"]
    printed = rec["部是否印出"]
    body_read = printed["標示部"] and printed["所有權部"]
    out = {}
    if rec["他項權利部"]:
        out["他項權利"] = "有"
    elif printed["標示部"] and scope in scopes["含他項權利部"]:
        out["他項權利"] = "未見"
    else:
        out["他項權利"] = "無法判定"

    items: List[Dict[str, Optional[str]]] = []
    mark = rec["標示部"] or {}
    items += mark.get("其他登記事項") or []
    for sp in mark.get("共有部分") or []:
        items += sp.get("其他登記事項") or []
    reasons = []
    for o in rec["所有權部"]:
        items += o.get("其他登記事項") or []
        if o.get("登記原因"):
            reasons.append(_norm(o["登記原因"]))
    for kind in ("限制登記", "信託"):
        cats, labels = _match_set(kind, "類別"), _match_set(kind, "標籤")
        whole, causes = _match_set(kind, "整項"), _match_set(kind, "登記原因")
        hit = any(r in causes for r in reasons)
        for it in items:
            cat = _norm(it["類別"] or "").strip("()")
            body = (f"{it['標籤']}:" if it["標籤"] else "") + (it["內容"] or "")
            heads = {_norm(body), _norm(re.split(r":", body, 1)[0])}
            if (cat and cat in {c.strip("()") for c in cats}) or (it["標籤"] and _norm(it["標籤"]) in labels) \
                    or heads & whole:
                hit = True
        if hit:
            out[kind] = "有"
        elif body_read and scope in scopes["全部類"] and all(it["類別"] for it in items):
            out[kind] = "未見"
        else:
            out[kind] = "無法判定"
    return out


def _build_sheet(t: Dict[str, Any]) -> Tuple[Dict[str, Any], _Sheet]:
    sh = _Sheet(t)
    kind_type = _sheet_type(t)
    rec: Dict[str, Any] = {"謄本": _header(sh), "類型": kind_type, "標示部": None, "所有權部": [], "他項權利部": [],
                           "判定": None, "部是否印出": {p: False for p in PARTS}, "部附註": {p: [] for p in PARTS},
                           "注意事項": [], "其他欄位": sh.other}
    mark_entries: List[Tuple[tuple, Dict[str, Any]]] = []
    for si, sec in enumerate(t.get("sections") or []):
        name = sec.get("部", "")
        part = name[2:]
        if part not in PARTS:
            for k, v in sec.items():
                if k == "entries":
                    for ei, e in enumerate(v):
                        sh.rest_to_other(("部", si, "筆", ei), e, name, name, "不認得的部")
                elif k != "部":
                    sh.rest_to_other(("部", si, k), v, name, f"{name}.{k}", "不認得的部")
            continue
        rec["部是否印出"][part] = True
        for k, v in sec.items():
            if k in ("部", "entries"):
                continue
            if k == "附註":
                for p, x in _as_list(("部", si, k), v):
                    sh.mark(p, f"部附註.{part}[{len(rec['部附註'][part])}]", "原樣")
                    rec["部附註"][part].append(x)
            else:
                sh.rest_to_other(("部", si, k), v, name, k, "不在固定清單")
        entries = [(("部", si, "筆", ei), e) for ei, e in enumerate(sec.get("entries") or []) if e]
        if part == "標示部":
            mark_entries += entries
        else:
            keys = (LAND_OWNER_KEYS if kind_type == "土地" else OWNER_KEYS) if part == "所有權部" else RIGHT_KEYS
            for path, e in entries:
                dest = f"{part}[{len(rec[part])}]"
                rec[part].append(_put_entry_fields(sh, name, part, path, e, keys, dest))
    if rec["部是否印出"]["標示部"]:
        keys = LAND_MARK_KEYS if kind_type == "土地" else BUILDING_MARK_KEYS
        merged: Dict[str, Any] = {}
        mark = None
        for path, e in mark_entries:     # 標示部只有一筆;分在兩段時各段標籤不同,逐段放
            part_rec = _put_entry_fields(sh, f"{kind_type or ''}標示部", "標示部", path, e, keys, "標示部")
            if mark is None:
                mark = part_rec
            else:
                for k, v in part_rec.items():
                    if mark.get(k) in (None, []) and v not in (None, []):
                        mark[k] = v
        rec["標示部"] = mark if mark is not None else {k: ([] if k in ("層次", "附屬建物", "共有部分", "其他登記事項",
                                                                     "建物坐落地號") else None) for k in keys}
    for i, (p, v) in enumerate(_as_list(("注意事項",), t.get("注意事項") or [])):
        if isinstance(v, str):
            sh.mark(p, f"注意事項[{len(rec['注意事項'])}]", "原樣"); rec["注意事項"].append(v)
    rec["判定"] = _verdicts(rec)
    return rec, sh


def build_with_trace(transcripts: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[List[Tuple[tuple, str, str]]]]:
    """回傳 (transcript_records, 每張的去處清單)。去處:(原文路徑, 輸出路徑, 方式)。"""
    recs, traces = [], []
    for t in transcripts or []:
        rec, sh = _build_sheet(t)
        recs.append(rec)
        traces.append(sh.trace)
    return recs, traces


def build_transcript_records(transcripts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """transcripts(全文解析結果)→ 固定格式 transcript_records。"""
    return build_with_trace(transcripts)[0]


# ---------------------------------------------------------------------------
# 帶參數 transcript_format="v2" 的回應:規則補值 + 位置包裝(S1,位置一律 null)
# ---------------------------------------------------------------------------
_FILL_B_SINGLE = {"建物門牌": ("building_address", None), "主要用途": ("main_usage", None),
                  "主要建材": ("main_material", None), "層數": ("total_floors", None),
                  "總面積": ("total_area", to_number), "建築完成日期": ("completion_date", None)}
_FILL_L_SINGLE = {"面積": ("area", to_number), "使用分區": ("land_use_zone", None),
                  "使用地類別": ("land_use_type", None)}
_DATE_OK = re.compile(r"\d+\s*年\s*\d+\s*月\s*\d+\s*日")
_UNWRAPPED_KEYS = ("判定", "部是否印出")


def _skel(keys) -> Dict[str, Any]:
    return _blank_entry(keys)


def fill_from_rules(records: List[Dict[str, Any]], fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    """用規則抽取的單值/清單欄位補 transcript_records 的空格(深拷貝,不改輸入)。

    只補 null/空清單,不覆蓋既有值。整份只有 1 張時才補單值;清單項目須「屬於該張」:
    項目 transcript_id 等於該張 謄本.編號,或項目沒有 transcript_id 且整份只有 1 張。
    日期鍵(以「日期」結尾)須含年月日三段數字才補。補完以 _verdicts 重算 判定。
    """
    import copy
    out = copy.deepcopy(records)
    f = fields or {}
    one = len(out) == 1
    for r in out:
        if r.get("類型") is None and one:
            r["類型"] = "建物" if f.get("building_number") else ("土地" if f.get("land_number") else None)
        kind = r.get("類型")
        if kind is None:
            continue
        no = r["謄本"].get("編號")
        if one and no is None:
            no = f.get("building_number") if kind == "建物" else f.get("land_number")
            r["謄本"]["編號"] = no
        tid = no
        mine = lambda it: ((tid is not None and it.get("transcript_id") == tid)
                           or (it.get("transcript_id") is None and one))
        if r.get("標示部") is None:
            r["標示部"] = _skel(BUILDING_MARK_KEYS if kind == "建物" else LAND_MARK_KEYS)
        m = r["標示部"]
        if one:
            for k, (src, conv) in (_FILL_B_SINGLE if kind == "建物" else _FILL_L_SINGLE).items():
                v = f.get(src)
                if k.endswith("日期") and not _DATE_OK.search(str(v or "")):
                    continue
                if m.get(k) is None and v not in (None, ""):
                    m[k] = conv(v) if conv else v
        if kind == "建物":
            def _area(x):
                return to_number(x["area"]) if x.get("area") else None
            if not m["層次"]:
                m["層次"] = [{"層次": x.get("level"), "面積": _area(x)}
                           for x in f.get("floors") or [] if mine(x)]
            if not m["建物坐落地號"] and one:
                m["建物坐落地號"] = [{"段小段": x.get("section"), "編號": x.get("number")}
                                 for x in f.get("land_numbers") or []]
            if not m["附屬建物"]:
                m["附屬建物"] = [{"用途": x.get("usage"), "面積": _area(x)}
                              for x in f.get("sub_buildings") or [] if mine(x)]
            if not m["共有部分"]:
                m["共有部分"] = [{**_blank_shared_part(), "建號": x.get("build_number"), "面積": _area(x),
                                  "權利範圍": x.get("rights_scope")}
                              for x in f.get("shared_parts") or [] if mine(x)]
        if not r["所有權部"]:
            keys = LAND_OWNER_KEYS if kind == "土地" else OWNER_KEYS
            for x in f.get("owners") or []:
                if mine(x) and x.get("part") == ("land" if kind == "土地" else "building"):
                    e = _skel(keys)
                    e.update({"登記次序": x.get("order"), "所有權人": x.get("name"),
                              "權利範圍": x.get("rights_scope")})
                    r["所有權部"].append(e)
        if not r["他項權利部"] and one and f.get("other_right_type"):
            e = _skel(RIGHT_KEYS)
            e["權利種類"] = f["other_right_type"]
            r["他項權利部"].append(e)
        r["判定"] = _verdicts(r)
    return out


def _wrap(o: Any, path: str = "", pos: Optional[Dict[str, Any]] = None) -> Any:
    """每個有值葉子包成 {value, position}。pos={葉子路徑: (值, position)}(S2),路徑與值都對上才附位置,否則 None。"""
    if isinstance(o, dict):
        return {k: _wrap(v, f"{path}.{k}" if path else k, pos) for k, v in o.items()}
    if isinstance(o, list):
        return [_wrap(v, f"{path}[{i}]", pos) for i, v in enumerate(o)]
    if o is None:
        return None
    hit = (pos or {}).get(path)
    p = hit[1] if hit and type(hit[0]) is type(o) and hit[0] == o else None
    return {"value": o, "position": p}


def _wrap_record(rec: Dict[str, Any], pos: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {k: (v if k in _UNWRAPPED_KEYS else _wrap(v, k, pos)) for k, v in rec.items()}


def _electronic_positions(result: Dict[str, Any], records: List[Dict[str, Any]], file_contents: Optional[bytes]):
    """電子 PDF 的位置表(每張一份);不適用或失敗 → None(position 全為 null,不影響其他欄位)。"""
    pages = result.get("pages") or []
    if not file_contents or not pages or not all(isinstance(p, dict) and p.get("text_layer") is True for p in pages):
        return None
    try:
        from .transcript_positions import compute_positions
        # 與 analyze_service._attach_full_transcripts 取同一份文字解析
        texts = [(p.get("rule_postprocessed") or {}).get("text") or (p.get("ocr_raw") or {}).get("text") or ""
                 for p in pages]
        return compute_positions(texts, file_contents, records)
    except Exception as e:
        logger.warning(f"謄本位置組裝失敗,position 全為 null: {e!r}")
        return None


def _photo_positions(result: Dict[str, Any], records: List[Dict[str, Any]], filled: List[Dict[str, Any]],
                     file_contents: Optional[bytes], ocr_lines: Optional[Dict[int, list]]):
    """照片／無文字層 PDF 的位置表(S3,每張一份);不適用或失敗 → None(position 全為 null)。"""
    if not ocr_lines:
        return None
    try:
        from .transcript_positions import compute_photo_positions
        return compute_photo_positions(result.get("pages") or [], ocr_lines, file_contents, records, filled)
    except Exception as e:
        logger.warning(f"謄本照片位置組裝失敗,position 全為 null: {e!r}")
        return None


def apply_transcript_format(result: Dict[str, Any], file_contents: Optional[bytes] = None,
                            ocr_lines: Optional[Dict[int, list]] = None) -> Dict[str, Any]:
    """transcript_format="v2":回傳新 dict(深拷貝,不改輸入)。

    file_contents(上傳原檔)有給、且各頁 text_layer 為 true(電子 PDF)時,值的 position 填電子檔上的框(S2);
    照片／無文字層 PDF 有給 ocr_lines({頁碼: OCR 行框})時,值的 position 填「值所在那一行」的框(S3,含補進的值);
    其餘(沒給原檔、位置組裝失敗、重建的 records 與輸入不同)position 一律 None。電子 PDF 補進的值 position 為 None。

    document_fields.transcript_records 換成補值並包 {value, position} 的版本;
    拿掉 25 個單值欄位、6 種清單與 transcripts;每頁 structured_data 只拿掉這 31 個舊鍵。
    """
    import copy
    # 函式內匯入:analyze_service 載入時會匯入本模組,頂層匯入會循環
    from app.services.analyze_service import _LIST_DETAIL_KEYS
    from .transcript_field_extractor import TranscriptFieldExtractor

    old_keys = set(TranscriptFieldExtractor.KEY_FIELDS) | set(_LIST_DETAIL_KEYS)
    new = copy.deepcopy(result)
    df = new.get("document_fields")
    if isinstance(df, dict):
        records = df.get("transcript_records")
        if isinstance(records, list):
            posmaps = _electronic_positions(new, records, file_contents)
            filled = fill_from_rules(records, result["document_fields"])
            if posmaps is None:
                posmaps = _photo_positions(new, records, filled, file_contents, ocr_lines)
            df["transcript_records"] = [_wrap_record(r, posmaps[i] if posmaps and i < len(posmaps) else None)
                                        for i, r in enumerate(filled)]
        for k in old_keys | {"transcripts"}:
            df.pop(k, None)
    for page in new.get("pages") or []:
        sd = page.get("structured_data")
        if isinstance(sd, dict):
            for k in old_keys:
                sd.pop(k, None)
    return new

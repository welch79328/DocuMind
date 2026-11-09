"""
謄本全文解析——謄本上印的每一項都讀出來(2026-10-14,驗收清單 .kiro/specs/transcript-full-parse/acceptance.md)

TranscriptFieldExtractor 一個欄位一條規則,只回 25 個單值欄位＋6 種清單;謄本上其餘內容(住址、權狀字號、
他項權利部整段、地目、公告土地現值…)不回傳。逐欄補規則永遠補不完,也是特規(業主:「禁止特規修改 需通用修改」)。
本模組改依**版面結構**讀,不寫任何欄位名稱:

1. 分張:頁首「XX登記第X類謄本」＋「地段＋編號(地號/建號)」,頁首到「頁次」那一行為止。編號與上一頁不同 → 新的一張;
   相同 → 續頁,頁首行與該張已收的頁首逐字相同才略過。只比編號、不比地段(不同地段同編號相連會併成一張,已知限制)。
2. 分部:「*** 土地/建物 標示部/所有權部/他項權利部 ***」。分筆:行首「(0001)」＋登記次序。
3. 「標籤:值」:標籤＝連續中文(含括號,如「利息(率)」)或單字以空白隔開(「住 址」「權 利 人」);前面有空白才算新標籤
   (值內的「可至:http」不算)。第一個標籤前的文字存成「<標籤>_前文」(「民國101年01月 公告土地現值:860元」)。
4. 層級看**整行縮排**:與該部最淺縮排同層 → 頂層;縮到前一個頂層標籤的值欄位以後 → 該標籤的子項
   (其他登記事項底下的「因分割增加地號」);只縮一點 → 自成一組,第一個標籤是組長、同縮排的後續行歸組長
   (共有部分＋權利範圍＋其他登記事項、所有權人＋統一編號＋住址)。有子項或組員的標籤,值是 {"_值": 原值, 子標籤: 值}。
5. 沒有標籤的行,依序:前一個值是空的 → 就是它的值;欄數與上一行相同 → 逐欄追加(層次表);
   上一行寫滿(顯示寬度達該頁最寬 −3)→ 同一個詞被切斷,緊接;前一個值是原文空白標記 → 不接(空白就是值已結束);
   縮排比上一行標籤深 → 換行是下一項,以空白分隔;其他 → 該部(或頁首)的「附註」。
6. 「本謄本列印完畢」之後是「注意事項」;頂格(縮排 0)的行與「(續次頁)」之後到頁尾是「頁緣」。
   只略過:空行、「(續次頁)」與「列印完畢」標記本身、逐字相同的重複頁首。
7. 星號:補位去掉、遮罩保留,依位置判斷(見 clean)。

⚠️ 值是比對用正規化(normalize_for_matching:全形轉半形、帶框字還原)後的文字;原文的「(空白)」原樣保留,
   與 25 欄回 null 不同。掃描/拍照件的 OCR 文字沒有可靠的縮排,本模組讀不出結構(業主裁示掃描件排到升級機器之後)。
⚠️ 公設車位那一行「含停車位○號,權利範圍:…」不拆:「權利範圍」前是逗號,若改成逗號後也算標籤,
   會切壞謄本檢查號「…8806,可至:http…」這類值。待取得含車位的電子謄本再處理。
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from .text_normalize import is_blank_marker, normalize_for_matching

CJK = "一-鿿"
TITLE = re.compile(r"^\s*(\S*?(?:土地|建物)登記第.類謄本\S*)\s*$")
IDLINE = re.compile(r"^\s*(\S.*?)\s*([0-9]{3,5}-[0-9]{3,5})\s*(地號|建號)\s*$")
SECTION = re.compile(r"^\s*\*+\s*((?:土地|建物)\s*(?:標示|所有權|他項權利)\s*部)\s*\*+\s*$")
ENTRY_NO = re.compile(r"^(\s*)\((\d{4})\)")
CONTINUED = re.compile(r"\(續次頁\)")
PRINT_END = re.compile(r"本謄本列印完畢")
PAGE_NO = re.compile(r"頁次")
NOTE_ITEM = re.compile(r"^(?:※注意:)?[一二三四五六七八九十]+、")
LABEL = re.compile(rf"((?<![{CJK}])[{CJK}](?:[ ]{{1,6}}[{CJK}])+(?![{CJK}])|[{CJK}()]+)\s*:")

# 帳目裡「略過」的原因只能是這四種(驗收 E1)
SKIP_REASONS = ("空行", "續次頁標記", "列印完畢標記", "重複頁首")


class Located(str):
    """帶來源位置的字串(S2):cm[j] = 第 j 個字在正規化後原文的 (頁, 行, 欄),不是原文印出的字(補的空白、
    標籤尾綴)為 None。是 str 子類,等值、可 json、可 deepcopy;只在 track=True 時才出現。"""

    def __new__(cls, s: str = "", cm=None):
        o = super().__new__(cls, s)
        o.cm = list(cm) if cm is not None else [None] * len(s)
        return o

    @property
    def spans(self) -> List[Tuple[int, int, int, int]]:
        """[(頁, 行, 起, 迄)],起迄為該行正規化後的字元索引([起, 迄))。相鄰的字併成一段。"""
        out: List[List[int]] = []
        cur = None
        for c in self.cm:
            if c is None:
                cur = None
            elif cur is not None and cur[0] == c[0] and cur[1] == c[1] and cur[3] == c[2]:
                cur[3] = c[2] + 1
            else:
                cur = [c[0], c[1], c[2], c[2] + 1]
                out.append(cur)
        return [tuple(x) for x in out]

    def slice(self, a: int, b: int) -> "Located":
        return Located(str(self)[a:b], self.cm[a:b])


def _cm_of(x) -> list:
    return x.cm if isinstance(x, Located) else [None] * len(x)


def _cat(a, sep: str, b):
    """a + sep + b;任一邊是 Located 時結果也是 Located(sep 不是原文印的字,位置為 None)。"""
    if isinstance(a, Located) or isinstance(b, Located):
        return Located(str(a) + sep + str(b), _cm_of(a) + [None] * len(sep) + _cm_of(b))
    return a + sep + b


def _rstrip(x):
    return x.slice(0, len(x.rstrip())) if isinstance(x, Located) else x.rstrip()


def _strip(x):
    if not isinstance(x, Located):
        return x.strip()
    n0 = len(x) - len(x.lstrip())
    return x.slice(n0, n0 + len(x.strip()))


def display_width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "FW" else 1 for c in s.rstrip())


def is_padding_star(left, right) -> bool:
    """一段星號是補位(去掉)還是遮罩(保留)。left/right 是星號前後的字元,值頭值尾為 None。

    補位:值頭或空白之後;到值尾(或接空白)時前面是數字/右括號;夾在中間時「中文或右括號」與數字相鄰。
      **434,000元、全部 ***1分之1***、新台幣****93,600,000元、107年01月**123,100.0
    遮罩:其餘——夾在英數之間(A202*****6)、夾在中文之間(王*明)、接在文字之後到值尾(黃**)。
    """
    if left is None or left.isspace():
        return True
    if right is None or right.isspace():
        return left.isdigit() or left == ")"
    return (re.match(rf"[{CJK})]", left) is not None and right.isdigit()) or (
        left.isdigit() and re.match(rf"[{CJK}(]", right) is not None
    )


def _clean_located(v: str, cm: list) -> "Located":
    """clean 的逐字記位置版:輸出字串與 clean(v) 相同,每個輸出字帶來源位置(補位星號換成的空白為 None)。"""
    want = clean(v)
    n0 = len(v) - len(v.lstrip())
    v2 = v.strip()
    cm2 = cm[n0:n0 + len(v2)]
    chars, i = [], 0
    for m in re.finditer(r"\*+", v2):
        left = v2[m.start() - 1] if m.start() > 0 else None
        right = v2[m.end()] if m.end() < len(v2) else None
        chars += list(zip(v2[i:m.start()], cm2[i:m.start()]))
        if is_padding_star(left, right):
            chars.append((" ", None))
        else:
            chars += list(zip(m.group(0), cm2[m.start():m.end()]))
        i = m.end()
    chars += list(zip(v2[i:], cm2[i:]))
    joined = "".join(c for c, _ in chars)
    out, pos = [], 0
    for m in re.finditer(r"\s{2,}", joined):
        out += chars[pos:m.start()]
        out.append((" ", chars[m.start()][1]))
        pos = m.end()
    out += chars[pos:]
    t = "".join(c for c, _ in out)
    lead = len(t) - len(t.lstrip())
    t2 = t.strip()
    out = out[lead:lead + len(t2)]
    if t2 != want:     # 與 clean 不一致就不給位置(寧可 null,不給錯框)
        return Located(want)
    return Located(t2, [c for _, c in out])


def clean(v: str, cm: Optional[list] = None):
    """去補位星號、保留遮罩星號,收空白。cm 給了就回 Located(逐字帶來源位置)。"""
    if cm is not None:
        return _clean_located(v, cm)
    v = v.strip()
    out, i = [], 0
    for m in re.finditer(r"\*+", v):
        left = v[m.start() - 1] if m.start() > 0 else None
        right = v[m.end()] if m.end() < len(v) else None
        out.append(v[i:m.start()])
        out.append(" " if is_padding_star(left, right) else m.group(0))
        i = m.end()
    out.append(v[i:])
    return re.sub(r"\s{2,}", " ", "".join(out)).strip()


def _line_cm(loc, a: int, b: int) -> list:
    return [(loc[0], loc[1], k) for k in range(a, b)]


def _label_key(text: str, start: int, loc, suffix: str = ""):
    """標籤(去掉內部空白)。loc=(頁, 行) 時回 Located,字位置對回該行。"""
    plain = re.sub(r"\s+", "", text) + suffix
    if loc is None:
        return plain
    cm = [(loc[0], loc[1], start + k) for k, ch in enumerate(text) if not ch.isspace()] + [None] * len(suffix)
    return Located(plain, cm) if len(cm) == len(plain) else Located(plain)


def label_pairs(line: str, loc=None) -> List[Tuple[str, str, int]]:
    """一行裡的 [(標籤, 值, 標籤起點)]。行首「(0001)」回傳為「次序」;第一個標籤前的文字回傳為「<標籤>_前文」。
    loc=(頁, 行) 時標籤與值是 Located(S2 記位置);預設行為不變。"""
    def seg(a: int, b: int):
        return clean(line[a:b], _line_cm(loc, a, b)) if loc else clean(line[a:b])

    out = []
    m0 = ENTRY_NO.match(line)
    if m0:
        no = m0.group(2)
        if loc:
            no = Located(no, _line_cm(loc, m0.start(2), m0.end(2)))
        out.append((Located("次序") if loc else "次序", no, m0.start(2)))
        line = line[:m0.start()] + " " * (m0.end() - m0.start()) + line[m0.end():]
    keep = []
    for m in LABEL.finditer(line):
        before = line[keep[-1].end():m.start()] if keep else line[:m.start()]
        if keep and not re.search(r"\s$", before):
            continue          # 新標籤前必須是空白(值內的「可至:http」不算)
        if not keep and before.strip() and not re.search(r"\s$", before):
            continue
        keep.append(m)
    if keep and line[:keep[0].start()].strip():
        out.append((_label_key(keep[0].group(1), keep[0].start(1), loc, "_前文"), seg(0, keep[0].start()), 0))
    for i, m in enumerate(keep):
        end = keep[i + 1].start() if i + 1 < len(keep) else len(line)
        out.append((_label_key(m.group(1), m.start(1), loc), seg(m.end(), end), m.start()))
    return out


def _put(d: Dict[str, Any], k: str, v: Any) -> None:
    """同一處重複的標籤 → 清單。"""
    if k in d:
        d[k] = d[k] if isinstance(d[k], list) else [d[k]]
        d[k].append(v)
    else:
        d[k] = v


def _get_last(d, k):
    return d[k][-1] if isinstance(d[k], list) else d[k]


def _set_last(d, k, v):
    if isinstance(d[k], list):
        d[k][-1] = v
    else:
        d[k] = v


def _join_note(a: str, b: str) -> str:
    """注意事項跨行成段:中英數之間緊接,其餘補一個空白。"""
    a, b = _rstrip(a), _strip(b)
    if not a:
        return b
    tight = re.match(rf"[{CJK}、,。()A-Za-z0-9]", a[-1]) and re.match(rf"[{CJK}、,。()A-Za-z0-9]", b[:1] or " ")
    return _cat(a, "" if tight else " ", b)


def parse_with_ledger(pages: List[str], track: bool = False) -> Tuple[List[Dict[str, Any]], List[Tuple[int, int, str, str]]]:
    """回傳 (謄本清單, 帳目)。帳目每一行原文一筆 (頁, 行, 去處, 說明),頁與行從 1、0 起算。

    track=True(S2):值與標籤(含 dict 鍵)是 Located,帶 spans(正規化後該行的字元索引);
    track=False(預設)輸出與加入此參數之前逐位元相同。"""
    transcripts: List[Dict[str, Any]] = []
    ledger: List[Tuple[int, int, str, str]] = []
    cur = sec = entry = None
    last = None    # (容器, 該行 pairs, 該行縮排, 該行顯示寬度, 頁寬)
    top = None     # (容器, 最近頂層標籤, 該行縮排, 該標籤值的起始欄)
    group = None   # (組 dict, 組縮排, 容器, 組長標籤)
    base_indent = None
    for pno, page in enumerate(pages, 1):
        raw = (page or "").splitlines()
        lines = normalize_for_matching(page or "").splitlines()
        if len(raw) != len(lines):
            raw = lines
        pmax = max((display_width(l) for l in raw), default=0)
        title = idm = None
        head_end, head_lines = 0, set()
        idm_i = 0

        def LC(text, i, start):          # track 時把正規化行內的一段包成 Located
            return Located(text, [(pno, i, start + k) for k in range(len(text))]) if track else text

        def CL(i, line, a, b):           # clean(line[a:b]),track 時帶位置
            return clean(line[a:b], [(pno, i, k) for k in range(a, b)] if track else None)

        def ST(i, line):                 # line.strip(),track 時帶位置
            return LC(line.strip(), i, len(line) - len(line.lstrip()))

        def LP(line, i):                 # label_pairs
            return label_pairs(line, (pno, i) if track else None)

        for i, ln in enumerate(lines[:10]):
            if TITLE.match(ln):
                tm = TITLE.match(ln)
                title = LC(tm.group(1), i, tm.start(1)); head_end = i + 1; head_lines.add(i)
            elif title and not idm and IDLINE.match(ln):
                idm = IDLINE.match(ln); idm_i = i; head_end = i + 1; head_lines.add(i)
            elif title and PAGE_NO.search(ln):
                head_end = i + 1
                break
        tid = LC(idm.group(2), idm_i, idm.start(2)) if idm else None
        new = cur is None or bool(tid and tid != cur["header"].get("編號"))
        if new:
            cur = {"header": {"謄本種類": title, "地段": LC(idm.group(1), idm_i, idm.start(1)) if idm else None, "編號": tid,
                              "編號類型": LC(idm.group(3), idm_i, idm.start(3)) if idm else None},
                   "sections": [], "注意事項": [], "頁緣": [], "_頁首行": set()}
            transcripts.append(cur)
            sec = entry = last = top = group = None
            base_indent = None
        state = "body"
        for i, ln in enumerate(lines):
            if not ln.strip():
                ledger.append((pno, i, "略過", "空行")); continue
            indent = len(ln) - len(ln.lstrip())
            if i < head_end:
                if i in head_lines and new:
                    cur["_頁首行"].add(ln.strip()); ledger.append((pno, i, "頁首", "抬頭/編號")); continue
                if not new and ln.strip() in cur["_頁首行"]:
                    ledger.append((pno, i, "略過", "重複頁首")); continue
                cur["_頁首行"].add(ln.strip())
                if indent == 0:
                    cur["頁緣"].append(ln.strip()); ledger.append((pno, i, "頁緣", ln.strip())); continue
                pairs = LP(ln, i)
                if not pairs:
                    _put(cur["header"], "附註", CL(i, ln, 0, len(ln))); ledger.append((pno, i, "頁首附註", ln.strip())); continue
                for k, v, _ in pairs:
                    _put(cur["header"], k, v)
                ledger.append((pno, i, "頁首", ln.strip()))
                last = (cur["header"], pairs, indent, display_width(raw[i]), pmax); continue
            if state == "after_continue" or (indent == 0 and not SECTION.match(ln)):
                cur["頁緣"].append(ln.strip()); ledger.append((pno, i, "頁緣", ln.strip())); continue
            if CONTINUED.search(ln):
                state = "after_continue"; ledger.append((pno, i, "略過", "續次頁標記")); continue
            if PRINT_END.search(ln):
                state = "notes"; ledger.append((pno, i, "略過", "列印完畢標記")); continue
            if state == "notes":
                s = ST(i, ln)
                if NOTE_ITEM.match(s) or not cur["注意事項"]:
                    cur["注意事項"].append(s)
                else:
                    cur["注意事項"][-1] = _join_note(cur["注意事項"][-1], s)
                ledger.append((pno, i, "注意事項", s)); continue
            m = SECTION.match(ln)
            if m:
                sec = {"部": re.sub(r"\s+", "", m.group(1)), "entries": []}
                cur["sections"].append(sec)
                entry = {}; sec["entries"].append(entry)
                last = top = group = None; base_indent = None
                ledger.append((pno, i, "部", sec["部"])); continue
            container = entry if sec is not None else cur["header"]
            pairs = LP(ln, i)
            if pairs and ENTRY_NO.match(ln) and sec is not None and entry:
                entry = {}; sec["entries"].append(entry); container = entry; top = group = None
            if pairs:
                if base_indent is None or indent < base_indent:
                    base_indent = indent
                first = next((p for p in pairs if p[0] != "次序" and not p[0].endswith("_前文")), pairs[0])
                if indent > base_indent and top and top[0] is container and indent >= top[3]:
                    # 縮到前一個值的位置 → 前一個頂層標籤的子項
                    pk = top[1]; pv = _get_last(container, pk)
                    if not isinstance(pv, dict):
                        pv = {"_值": pv}; _set_last(container, pk, pv)
                    for k, v, _ in pairs:
                        _put(pv, k, v)
                    ledger.append((pno, i, "子項", pk))
                    last = (pv, pairs, indent, display_width(raw[i]), pmax); continue
                if indent > base_indent and group and group[1] == indent and group[2] is container:
                    for k, v, _ in pairs:
                        _put(group[0], k, v)
                    ledger.append((pno, i, "組員", group[3]))
                    last = (group[0], pairs, indent, display_width(raw[i]), pmax); continue
                if indent > base_indent:
                    # 只縮一點、自成一組:第一個標籤是組長
                    hk, hv, _ = first
                    g = {"_值": hv}
                    for k, v, _ in pairs:
                        if (k, v) != (hk, hv):
                            _put(g, k, v)
                    _put(container, hk, g); group = (g, indent, container, hk)
                    ledger.append((pno, i, "組長", hk))
                    last = (g, [("_值", hv, first[2])], indent, display_width(raw[i]), pmax); continue
                group = None
                for k, v, _ in pairs:
                    _put(container, k, v)
                top = (container, pairs[-1][0], indent, ln.find(":", pairs[-1][2]) + 1)
                ledger.append((pno, i, "欄位", ",".join(p[0] for p in pairs)))
                last = (container, pairs, indent, display_width(raw[i]), pmax); continue
            # ---- 沒有標籤的行 ----
            s = CL(i, ln, 0, len(ln))
            if last:
                c, ps, lab_indent, w, pm = last
                k = ps[-1][0]; v = _get_last(c, k)
                if track:
                    st, lead, chunks, cpos = ln.strip(), len(ln) - len(ln.lstrip()), [], 0
                    for cm_ in list(re.finditer(r"\s{2,}", st)) + [None]:
                        cend = cm_.start() if cm_ else len(st)
                        if st[cpos:cend].strip():
                            chunks.append(CL(i, ln, lead + cpos, lead + cend))
                        cpos = cm_.end() if cm_ else cend
                else:
                    chunks = [clean(x) for x in re.split(r"\s{2,}", ln.strip()) if x.strip()]
                if isinstance(v, str) and v == "":
                    _set_last(c, k, s); ledger.append((pno, i, "值(換行)", k))
                    last = (c, ps, lab_indent, display_width(raw[i]), pm); continue
                if len(ps) > 1 and len(chunks) == len(ps) and ps[0][0] != "次序":
                    for (kk, _, _), ch in zip(ps, chunks):
                        _put(c, kk, ch)
                    ledger.append((pno, i, "表格續行", ",".join(p[0] for p in ps))); continue
                if w >= pm - 3 and isinstance(v, str):
                    _set_last(c, k, _cat(v, "", s)); ledger.append((pno, i, "續行(寫滿換行)", k))
                    last = (c, ps, lab_indent, display_width(raw[i]), pm); continue
                if isinstance(v, str) and not is_blank_marker(v) and indent > lab_indent:
                    _set_last(c, k, _cat(_rstrip(v), " ", s)); ledger.append((pno, i, "續行", k)); continue
            _put(sec if sec is not None else cur["header"], "附註", s)
            ledger.append((pno, i, "附註", s))
    for t in transcripts:
        t.pop("_頁首行", None)
    return transcripts, ledger


def parse_transcript_pages(pages: List[str], track: bool = False) -> List[Dict[str, Any]]:
    """謄本各頁文字 → [{header, sections: [{部, entries, 附註?}], 注意事項, 頁緣}]。track=True 見 parse_with_ledger。"""
    return parse_with_ledger(pages, track)[0]

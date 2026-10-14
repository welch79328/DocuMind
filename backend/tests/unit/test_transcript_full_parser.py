"""
謄本全文解析(transcript_full_parser)——G6,驗收清單 .kiro/specs/transcript-full-parse/acceptance.md(E1、E5)

合成樣本照電子謄本版型手打(全形、帶框字、補位星號、縮排、續頁),不放真實謄本。
測試分兩組:解析規則逐條驗;對帳輔助函式(逐行帳目＋字元對帳＋詞邊界)與三組正對照。
"""

import collections
import re

import pytest

from app.lib.multi_type_ocr.text_normalize import normalize_for_matching as N
from app.lib.multi_type_ocr.transcript_full_parser import (
    SKIP_REASONS, label_pairs, parse_transcript_pages, parse_with_ledger,
)
from app.services import analyze_service
from app.services.analyze_service import _attach_full_transcripts

P1 = """     建物登記第二類謄本（建號全部）
      大安區仁愛段六小段 01921-000建號
    列印時間：民國101年07月11日09時46分                                頁次：1
    本謄本係網路申領之電子謄本，由測試公司自行列印
    謄本檢查號：１０１ＡＣ３１２２９０ＲＥＧＣＤ３Ａ４７Ｄ４Ｄ４Ｂ４０９Ｅ１２Ｂ３ＡＢＣ
    ８ＣＡ１ＦＦ８８０６，可至：http://land.hinet.net 查驗本謄本之正確性
    大安地政事務所  主  任    王大明
    資料管轄機關：臺北市大安地政事務所  謄本核發機關：臺北市大安地政事務所
  ***************  建物標示部  ****************
    登記日期：民國095年02月13日                        登記原因：第一次登記
    建物門牌：忠孝東路四段285號五樓
    建物坐落地號：仁愛段六小段  0100-0000  0100-0001
                                 0100-0005
    主要用途：（空白）
    層    數：004層                                      總面積：****193.02平方公尺
    層    次：一層                                     層次面積：*****96.51平方公尺
              二層                                               *****96.51平方公尺
    建築完成日期：民國---年--月--日
      共有部分：仁愛段六小段02163-000建號**3,213.92平方公尺
      權利範圍：*****10000分之672*******
    其他登記事項：重測前：東門段109－2地號
                  因分割增加地號：221－1地號
  ***************  建物所有權部  ****************
    （0001）登記次序：0003
    登記日期：民國098年04月08日                     登記原因：買賣
      所有權人：黃**
      統一編號：A202*****6
      住    址：台北市中山區
    權利範圍：全部 *********1分之1*********
    前次移轉現值或原規定地價：
    107年05月     **426,000.0元/平方公尺
    其他登記事項：（空白）
           本謄本僅係 所有權個人全部 節本，詳細權利狀態請參閱全部謄本
    （0002）登記次序：0004
      所有權人：王*明
    權利範圍：2分之1
  ***************  建物他項權利部  ****************
    （0001）登記次序：0009-000                     權利種類：最高限額抵押權
     權 利 人：國泰世華商業銀行股份有限公司
    擔保債權總金額：新台幣****************93,600,000元正
                                            (續次頁)
88
"""
P2 = """     建物登記第二類謄本（建號全部）
      大安區仁愛段六小段 01921-000建號
    列印時間：民國101年07月11日09時46分                                頁次：2
    設定義務人：新華開發股份有限公司
                                      〈 本謄本列印完畢 〉
    ※注意：一、本電子謄本係依電子簽章法規定產製，
                紙張謄本具有同等效用。
            二、若經列印成紙本已為解密之明文資料。
臺北市大安地政事務所
C1
"""
P3 = """     ㈯㆞登記第㆓類謄本（所㈲權個㆟全部）
      大安區仁愛段㈥小段 0100-0006㆞號
    列印時間：民國108年04月02日08時43分                                頁次：1
  ***************  ㈯㆞標示部  ****************
    面    積：*******64.00平方公尺
    使用分區：（空白）                             使用㆞類別：（空白）
    民國108年01月    公告㈯㆞現值：**568,484元／平方公尺
    本謄本未申請列印地上建物建號，詳細地上建物建號以登記機關登記為主
                                      〈 本謄本列印完畢 〉
"""


def _parse():
    return parse_transcript_pages([P1, P2, P3])


# ---------------------------------------------------------------- 解析規則
class TestSplit:
    def test_same_number_continues_different_number_splits(self):
        t = _parse()
        assert [x["header"]["編號"] for x in t] == ["01921-000", "0100-0006"]
        assert t[1]["header"]["謄本種類"] == "土地登記第二類謄本(所有權個人全部)"   # 帶框字還原

    def test_repeated_header_skipped_only_when_identical(self):
        _, ledger = parse_with_ledger([P1, P2, P3])
        skipped = [(p, i) for p, i, w, why in ledger if why == "重複頁首"]
        assert (2, 0) in skipped and (2, 1) in skipped               # 抬頭、編號逐字相同
        assert (2, 2) not in skipped                                  # 「頁次:2」不同 → 收進來
        assert _parse()[0]["header"]["頁次"] == ["1", "2"]

    def test_sections_and_entries(self):
        t = _parse()[0]
        assert [s["部"] for s in t["sections"]] == ["建物標示部", "建物所有權部", "建物他項權利部"]
        owners = t["sections"][1]["entries"]
        assert [e["登記次序"] for e in owners] == ["0003", "0004"]     # 同一部 2 筆
        assert owners[1]["所有權人"]["_值"] == "王*明"


class TestLabels:
    def test_spaced_single_char_labels(self):
        assert [k for k, _, _ in label_pairs(N("      住    址：台北市"))] == ["住址"]
        assert [k for k, _, _ in label_pairs(N("     權 利 人：國泰"))] == ["權利人"]

    def test_multiple_pairs_on_one_line(self):
        e = _parse()[0]["sections"][0]["entries"][0]
        assert e["登記日期"] == "民國095年02月13日" and e["登記原因"] == "第一次登記"

    def test_value_colon_without_space_is_not_label(self):
        h = _parse()[0]["header"]
        assert h["謄本檢查號"].endswith(",可至:http://land.hinet.net 查驗本謄本之正確性")
        assert "可至" not in h

    def test_prefix_text(self):
        e = _parse()[1]["sections"][0]["entries"][0]
        assert e["公告土地現值_前文"] == "民國108年01月"
        assert e["公告土地現值"] == "568,484元/平方公尺"


class TestHierarchy:
    def test_sub_item_under_previous_label(self):
        e = _parse()[0]["sections"][0]["entries"][0]
        assert e["其他登記事項"] == {"_值": "重測前:東門段109-2地號", "因分割增加地號": "221-1地號"}

    def test_slightly_indented_group(self):
        e = _parse()[0]["sections"][0]["entries"][0]
        assert e["共有部分"] == {"_值": "仁愛段六小段02163-000建號 3,213.92平方公尺", "權利範圍": "10000分之672"}
        o = _parse()[0]["sections"][1]["entries"][0]["所有權人"]
        assert o == {"_值": "黃**", "統一編號": "A202*****6", "住址": "台北市中山區"}


class TestUnlabeledLines:
    def test_value_on_next_line(self):
        e = _parse()[0]["sections"][1]["entries"][0]
        assert e["前次移轉現值或原規定地價"] == "107年05月 426,000.0元/平方公尺"

    def test_table_rows(self):
        e = _parse()[0]["sections"][0]["entries"][0]
        assert e["層次"] == ["一層", "二層"] and e["層次面積"] == ["96.51平方公尺", "96.51平方公尺"]

    def test_full_line_wrap_joins_tightly(self):
        assert _parse()[0]["header"]["謄本檢查號"].startswith("101AC312290REGCD3A47D4D4B409E12B3ABC8CA1FF8806,")

    def test_list_continuation_is_separated(self):
        e = _parse()[0]["sections"][0]["entries"][0]
        assert e["建物坐落地號"] == "仁愛段六小段 0100-0000 0100-0001 0100-0005"   # 不黏成 0100-00010100-0005

    def test_blank_marker_takes_no_continuation(self):
        sec = _parse()[0]["sections"][1]
        assert sec["entries"][0]["其他登記事項"] == "(空白)"
        assert sec["附註"].startswith("本謄本僅係 所有權個人全部 節本")

    def test_notes_page_edge_and_section_notes(self):
        t = _parse()
        assert t[0]["注意事項"] == ["※注意:一、本電子謄本係依電子簽章法規定產製,紙張謄本具有同等效用。",
                                     "二、若經列印成紙本已為解密之明文資料。"]
        assert t[0]["頁緣"] == ["88", "臺北市大安地政事務所", "C1"]
        assert t[1]["sections"][0]["附註"].startswith("本謄本未申請列印地上建物建號")
        assert "大安地政事務所 主 任 王大明" in t[0]["header"]["附註"]


class TestStars:
    def test_padding_removed_including_two_stars(self):
        t = _parse()
        assert t[0]["sections"][0]["entries"][0]["總面積"] == "193.02平方公尺"
        assert t[0]["sections"][1]["entries"][0]["前次移轉現值或原規定地價"].endswith(" 426,000.0元/平方公尺")
        assert t[1]["sections"][0]["entries"][0]["公告土地現值"] == "568,484元/平方公尺"
        assert t[0]["sections"][2]["entries"][0]["擔保債權總金額"] == "新台幣 93,600,000元正"

    def test_masks_kept(self):
        own = _parse()[0]["sections"][1]["entries"]
        assert own[0]["所有權人"]["_值"] == "黃**"
        assert own[0]["所有權人"]["統一編號"] == "A202*****6"
        assert own[1]["所有權人"]["_值"] == "王*明"


class TestAttach:
    PAGES = [{"rule_postprocessed": {"text": P1}}, {"rule_postprocessed": {"text": P2}}]

    def test_attached_for_transcript_only(self):
        df = {"owner": "x"}
        _attach_full_transcripts(df, self.PAGES, "transcript")
        assert df["transcripts"][0]["header"]["編號"] == "01921-000" and df["owner"] == "x"
        df2 = {"owner": "x"}
        _attach_full_transcripts(df2, self.PAGES, "contract")
        assert "transcripts" not in df2

    def test_parser_failure_omits_key(self, monkeypatch):
        def boom(_):
            raise RuntimeError("boom")
        monkeypatch.setattr(analyze_service, "parse_transcript_pages", boom)
        df = {"owner": "x"}
        _attach_full_transcripts(df, self.PAGES, "transcript")
        assert df == {"owner": "x"}


# ---------------------------------------------------------------- 對帳(E1)
STRUCT = {"謄本種類", "地段", "編號", "編號類型", "次序", "_值", "附註", "頁緣", "注意事項", "部",
          "sections", "entries", "header"}
CJK = "\u4e00-\u9fff"


def _pad_stars(line):
    """獨立於解析器,直接在原文行上依位置規則數補位星號(冒號視同值頭)。"""
    n = 0
    for m in re.finditer(r"\*+", line):
        L = line[m.start() - 1] if m.start() > 0 else None
        R = line[m.end()] if m.end() < len(line) else None
        if L is None or L.isspace() or L == ":":
            pad = True
        elif R is None or R.isspace():
            pad = L.isdigit() or L == ")"
        else:
            pad = (re.match(f"[{CJK})]", L) is not None and R.isdigit()) or (
                L.isdigit() and re.match(f"[{CJK}(]", R) is not None)
        n += len(m.group(0)) if pad else 0
    return n


def _walk(x, keys, vals):
    if isinstance(x, dict):
        for k, v in x.items():
            n = len(v) if isinstance(v, list) and k not in ("sections", "entries") else 1
            if k not in STRUCT and not k.endswith("_前文"):
                keys.extend([k] * n)
            _walk(v, keys, vals)
    elif isinstance(x, list):
        for v in x:
            _walk(v, keys, vals)
    elif isinstance(x, str):
        vals.append(x)


def audit(pages, transcripts, ledger):
    """回傳 (帳目缺漏行, 字元少了, 字元多了, 不在原文的詞)。"""
    lines = [N(p).splitlines() for p in pages]
    covered = {(p, i) for p, i, _, _ in ledger}
    missing_lines = [(p, i) for p, pg in enumerate(lines, 1) for i in range(len(pg)) if (p, i) not in covered]
    raw, adj = collections.Counter(), collections.Counter()
    for p, i, where, why in ledger:
        if where == "略過":
            assert why in SKIP_REASONS
            continue
        ln = lines[p - 1][i]
        raw.update(c for c in ln if not c.isspace())
        if where == "表格續行":
            for k in why.split(","):
                raw.update(k)
        if where == "部":
            adj["*"] += ln.count("*")
        else:
            adj["*"] += _pad_stars(ln)
        if where in ("欄位", "子項", "組長", "組員", "頁首"):
            for k, _, _ in label_pairs(ln):
                if k == "次序":
                    adj.update("()")
                elif not k.endswith("_前文"):
                    adj.update(":")
    keys, vals = [], []
    _walk(transcripts, keys, vals)
    out = collections.Counter()
    for s in keys + vals:
        out.update(c for c in s if not c.isspace())
    blob = "\n".join(l for pg in lines for l in pg)
    flat = blob.replace("*", "")
    wraps = []
    for p, i, where, _ in ledger:
        if where == "續行(寫滿換行)":
            a = lines[p - 1][i - 1].replace("*", "").split()
            b = lines[p - 1][i].replace("*", "").split()
            if a and b:
                wraps.append(a[-1].split(":")[-1] + b[0])
    notes = {n for t in transcripts for n in t["注意事項"]}
    bad = [w for v in vals if v not in notes for w in v.split()
           if w not in blob and w.replace("*", "") not in flat and not any(x in w for x in wraps)]
    return missing_lines, raw - (out + adj), (out + adj) - raw, bad


class TestAudit:
    PAGES = [P1, P2, P3]

    def test_sample_balances(self):
        t, ledger = parse_with_ledger(self.PAGES)
        miss_l, miss, extra, bad = audit(self.PAGES, t, ledger)
        assert miss_l == [] and not miss and not extra and bad == []

    def test_control_glued_list_is_caught(self):
        t, ledger = parse_with_ledger(self.PAGES)
        e = t[0]["sections"][0]["entries"][0]
        e["建物坐落地號"] = e["建物坐落地號"].replace("0100-0001 0100-0005", "0100-00010100-0005")
        assert "0100-00010100-0005" in audit(self.PAGES, t, ledger)[3]

    def test_control_unmasked_is_caught(self):
        t, ledger = parse_with_ledger(self.PAGES)
        o = t[0]["sections"][1]["entries"][0]["所有權人"]
        o["統一編號"] = o["統一編號"].replace("*", "")
        assert audit(self.PAGES, t, ledger)[1]["*"] == 5

    def test_control_dropped_line_is_caught(self):
        t, ledger = parse_with_ledger(self.PAGES)
        t[0]["頁緣"].remove("臺北市大安地政事務所")
        miss = audit(self.PAGES, t, ledger)[1]
        assert sum(miss.values()) == len("臺北市大安地政事務所")

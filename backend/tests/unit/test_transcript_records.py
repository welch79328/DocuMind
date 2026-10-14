"""
謄本固定輸出格式 transcript_records——TFS-1,驗收清單 .kiro/specs/transcript-fixed-schema/acceptance.md

合成樣本照電子謄本版型手打,不放真實謄本(5 份真實謄本的對帳在本機另跑,見驗收清單 R2/R3/R9)。
涵蓋 5 份真實謄本沒有的版面:多位所有權人、多筆抵押、附屬建物、第一類、管理者、限制登記、信託。
"""

import json
import os
import re

import pytest

from app.lib.multi_type_ocr import transcript_records as tr
from app.lib.multi_type_ocr.transcript_full_parser import parse_transcript_pages
from app.lib.multi_type_ocr.transcript_records import (
    build_transcript_records, build_with_trace, source_leaves, split_district, split_lots, split_other_item,
    to_number, to_share,
)
from app.services import analyze_service
from app.services.analyze_service import _attach_full_transcripts

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "api", "transcript_records.schema.json")
SCHEMA = json.load(open(SCHEMA_PATH, encoding="utf-8"))

BUILD = """     建物登記第一類謄本（建號全部）
      平鎮區山仔頂段 01234-000建號
    列印時間：民國113年05月06日10時20分                                頁次：1
    本謄本係網路申領之電子謄本，由測試公司自行列印
    謄本種類碼：ＡＢＣ１２３４５６，可至https://ep.land.nat.gov.tw查驗
    平鎮地政事務所  主  任    測試員
    資料管轄機關：桃園市平鎮地政事務所  謄本核發機關：桃園市平鎮地政事務所
  ***************  建物標示部  ****************
    登記日期：民國095年02月13日                        登記原因：第一次登記
    建物門牌：測試路1號
    建物坐落地號：山仔頂段  0100-0000  0100-0001
    主要用途：住家用
    主要建材：鋼筋混凝土造
    層    數：004層                                      總面積：****193.02平方公尺
    層    次：一層                                     層次面積：*****96.51平方公尺
              二層                                               *****85.00平方公尺
    建築完成日期：民國---年--月--日
    附屬建物用途：陽台                                 面積：*****10.29平方公尺
                  花台                                       ******2.39平方公尺
      共有部分：山仔頂段02163-000建號**3,213.92平方公尺
      權利範圍：*****10000分之672*******
    其他登記事項：（一般註記事項）使用執照字號：84高縣建局營字第1號
  ***************  建物所有權部  ****************
    （0001）登記次序：0003
    登記日期：民國098年04月08日                     登記原因：買賣
    原因發生日期：民國098年02月26日
      所有權人：黃**
      統一編號：A202*****6
      住    址：台北市中山區
    權利範圍：2分之1
    權狀字號：098北中字第008757號
    相關他項權利登記次序：0009-000  0010-000
    其他登記事項：（空白）
    （0002）登記次序：0004
    登記日期：民國099年01月02日                     登記原因：買賣
      所有權人：王*明
    權利範圍：2分之1
    權狀字號：099北中字第000001號
    其他登記事項：（空白）
  ***************  建物他項權利部  ****************
    （0001）登記次序：0009-000                     權利種類：最高限額抵押權
     權 利 人：國泰世華商業銀行股份有限公司
    擔保債權總金額：新台幣****************93,600,000元正
    標的登記次序：0003
    設定權利範圍：2分之1
    共同擔保建號：山仔頂段  01234-000
    （0002）登記次序：0010-000                     權利種類：普通抵押權
     權 利 人：台灣銀行股份有限公司
    擔保債權總金額：新台幣****************1,000,000元正
    標的登記次序：0003
    設定權利範圍：全部 *********1分之1*********
    共同擔保地號：山仔頂段  0100-0000  0100-0001  前鎮區草衙段二小段  0005-0000
                                      〈 本謄本列印完畢 〉
    ※注意：一、本電子謄本係依電子簽章法規定產製，
                紙張謄本具有同等效用。
"""
LAND = """     土地登記第二類謄本（地號全部）
      前鎮區草衙段二小段 0005-0000地號
    列印時間：民國113年05月06日10時20分                                頁次：1
    謄本檢查號：１０１ＡＣ３１２２９０，可至：http://land.hinet.net 查驗本謄本之正確性
  ***************  土地標示部  ****************
    登記日期：民國075年05月27日                     登記原因：逕為分割
    地    目：建                                    等    則：--
    面    積：*******153.00平方公尺
    使用分區：（空白）                             使用地類別：（空白）
    民國108年01月    公告土地現值：**434,000元／平方公尺
    地上建物建號：共4棟
    其他登記事項：重測前：東門段109－2地號
                  因分割增加地號：221－1地號
  ***************  土地所有權部  ****************
    （0001）登記次序：0005
    登記日期：民國107年10月25日                     登記原因：分割繼承
      所有權人：黃**
      統一編號：A202*****6
    權利範圍：4分之1
    當期申報地價：107年01月****94,400.0元／平方公尺
    前次移轉現值或原規定地價：
    107年05月     **426,000.0元/平方公尺
    歷次取得權利範圍：4分之1
    其他登記事項：（空白）
                                      〈 本謄本列印完畢 〉
"""


def _records():
    return build_transcript_records(parse_transcript_pages([BUILD, LAND]))


# ---------------------------------------------------------------- Schema(R1)
def _validate(v, s, path="$"):
    """JSON Schema 的子集驗證(type/const/enum/properties/required/additionalProperties/items/maxItems/
    anyOf/oneOf/$ref)。後端不裝 jsonschema;本機對帳另以 jsonschema 4.23 交叉驗證同一份 Schema。"""
    if "$ref" in s:
        return _validate(v, SCHEMA["$defs"][s["$ref"].split("/")[-1]], path)
    errs = []
    if "oneOf" in s:
        ok = [o for o in s["oneOf"] if not _validate(v, o, path)]
        return [] if len(ok) == 1 else [f"{path}: oneOf 符合 {len(ok)} 個"]
    if "anyOf" in s:
        return [] if any(not _validate(v, o, path) for o in s["anyOf"]) else [f"{path}: anyOf 都不符"]
    types = s.get("type")
    if types:
        types = types if isinstance(types, list) else [types]
        py = {"string": str, "object": dict, "array": list, "boolean": bool, "null": type(None)}
        def is_type(t):
            if t in ("number", "integer"):
                return isinstance(v, (int, float)) and not isinstance(v, bool) and (t == "number" or isinstance(v, int))
            return isinstance(v, py[t])
        if not any(is_type(t) for t in types):
            return [f"{path}: 型別 {type(v).__name__} 不是 {types}"]
    if "const" in s and v != s["const"]:
        errs.append(f"{path}: 不是 {s['const']}")
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: {v!r} 不在 {s['enum']}")
    if isinstance(v, dict):
        props = s.get("properties", {})
        errs += [f"{path}: 缺 {k}" for k in s.get("required", []) if k not in v]
        if s.get("additionalProperties") is False:
            errs += [f"{path}: 多了 {k}" for k in v if k not in props]
        for k, x in v.items():
            if k in props:
                errs += _validate(x, props[k], f"{path}.{k}")
    if isinstance(v, list):
        if "maxItems" in s and len(v) > s["maxItems"]:
            errs.append(f"{path}: 超過 {s['maxItems']} 筆")
        if "items" in s:
            for i, x in enumerate(v):
                errs += _validate(x, s["items"], f"{path}[{i}]")
    return errs


class TestSchema:
    def test_output_matches_schema(self):
        assert _validate(_records(), SCHEMA) == []

    def test_missing_or_extra_key_is_caught(self):
        r = _records()
        del r[0]["標示部"]["層數"]
        assert _validate(r, SCHEMA)
        assert any("缺 層數" in e for e in _validate(r[0]["標示部"], {"$ref": "#/$defs/building_mark"}))
        r = _records()
        r[1]["所有權部"][0]["多的鍵"] = 1
        assert _validate(r, SCHEMA)

    def test_schema_keys_equal_module_keys(self):
        d = SCHEMA["$defs"]
        assert list(d["header"]["properties"]) == list(tr.HEADER_KEYS)
        assert list(d["building_mark"]["properties"]) == list(tr.BUILDING_MARK_KEYS)
        assert list(d["land_mark"]["properties"]) == list(tr.LAND_MARK_KEYS)
        assert list(d["building_owner"]["properties"]) == list(tr.OWNER_KEYS)
        assert list(d["land_owner"]["properties"]) == list(tr.LAND_OWNER_KEYS)
        assert list(d["right"]["properties"]) == list(tr.RIGHT_KEYS)

    def test_unprinted_parts_still_have_every_key(self):
        """他項權利部沒印 → []、判定照給;謄本沒印的鍵 → null。"""
        land = _records()[1]
        assert land["他項權利部"] == [] and land["部是否印出"]["他項權利部"] is False
        assert land["謄本"]["資料管轄機關"] is None and land["所有權部"][0]["權狀字號"] is None
        assert _validate([land], SCHEMA) == []


# ---------------------------------------------------------------- 值的規則
class TestValues:
    def test_building(self):
        b = _records()[0]
        h, m = b["謄本"], b["標示部"]
        assert (h["類別"], h["申請範圍"], h["行政區"], h["段"], h["小段"]) == ("第一類", "建號全部", "平鎮區", "山仔頂段", None)
        assert (h["查驗碼"], h["查驗碼標籤"], h["查驗網址"]) == ("ABC123456", "謄本種類碼", "https://ep.land.nat.gov.tw")
        assert h["頁數"] == 1 and h["頁首附註"][0].startswith("本謄本係網路申領")
        assert m["總面積"] == 193.02 and m["建築完成日期"] is None
        assert m["層次"] == [{"層次": "一層", "面積": 96.51}, {"層次": "二層", "面積": 85.0}]
        assert m["附屬建物"] == [{"用途": "陽台", "面積": 10.29}, {"用途": "花台", "面積": 2.39}]
        assert m["共有部分"] == [{"坐落": "山仔頂段", "建號": "02163-000", "面積": 3213.92, "權利範圍": "10000分之672",
                                "其他登記事項": []}]
        assert m["建物坐落地號"] == [{"段小段": "山仔頂段", "編號": "0100-0000"}, {"段小段": "山仔頂段", "編號": "0100-0001"}]
        assert m["其他登記事項"] == [{"類別": "一般註記事項", "標籤": "使用執照字號", "內容": "84高縣建局營字第1號"}]

    def test_multiple_owners_and_rights(self):
        b = _records()[0]
        assert [(o["所有權人"], o["權利範圍"]) for o in b["所有權部"]] == [("黃**", "2分之1"), ("王*明", "2分之1")]
        assert b["所有權部"][0]["住址"] == "台北市中山區" and b["所有權部"][1]["住址"] is None
        assert b["所有權部"][0]["相關他項權利登記次序"] == ["0009-000", "0010-000"]
        r = b["他項權利部"]
        assert [(x["權利種類"], x["擔保債權總金額"], x["設定權利範圍"]) for x in r] == [
            ("最高限額抵押權", 93600000, "2分之1"), ("普通抵押權", 1000000, "全部")]
        assert r[1]["共同擔保地號"][-1] == {"段小段": "前鎮區草衙段二小段", "編號": "0005-0000"}

    def test_land(self):
        land = _records()[1]
        m, o = land["標示部"], land["所有權部"][0]
        assert (m["面積"], m["公告土地現值"], m["公告土地現值年月"]) == (153.0, 434000, "民國108年01月")
        assert m["使用分區"] is None and m["等則"] is None and m["地目"] == "建"
        assert m["其他登記事項"] == [{"類別": None, "標籤": "重測前", "內容": "東門段109-2地號"},
                                {"類別": None, "標籤": "因分割增加地號", "內容": "221-1地號"}]
        assert (o["當期申報地價"], o["當期申報地價年月"]) == (94400.0, "107年01月")
        assert o["前次移轉現值"] == [{"年月": "107年05月", "金額": 426000.0, "歷次取得權利範圍": "4分之1"}]

    def test_no_other_fields_for_known_layout(self):
        assert [r["其他欄位"] for r in _records()] == [[], []]

    def test_converters(self):
        assert to_number("107年01月 94,400.0元/平方公尺") == 94400.0
        assert to_number("新台幣 93,600,000元正") == 93600000
        assert to_number("共 2 筆 3 號") is None and to_number("無") is None
        assert to_share("全部 1分之1") == "全部" and to_share("10000分之672") == "10000分之672"
        assert to_share("公同共有 1分之1") is None

    def test_district_longest_official_name(self):
        """行政區取全國鄉鎮市區名稱最長相符;「切到第一個區鄉鎮市」會把平鎮區切成「平鎮」。"""
        assert split_district("平鎮區山仔頂段") == ("平鎮區", "山仔頂段", None)
        assert split_district("前鎮區草衙段二小段") == ("前鎮區", "草衙段", "二小段")
        assert split_district("新市區大營段") == ("新市區", "大營段", None)
        assert split_district("仁愛段六小段") == (None, "仁愛段", "六小段")
        naive = re.match(r"^(.+?[區鄉鎮市])", "平鎮區山仔頂段").group(1)
        assert naive != split_district("平鎮區山仔頂段")[0]        # 正對照:舊切法在這裡會錯
        assert split_district("某某小段") is None

    def test_lots_and_items(self):
        assert split_lots("仁愛段六小段 0100-0000 0100-0001") == [
            {"段小段": "仁愛段六小段", "編號": "0100-0000"}, {"段小段": "仁愛段六小段", "編號": "0100-0001"}]
        assert split_lots("仁愛段六小段") is None
        assert split_other_item("(限制登記事項)查封:臺北地院函") == {"類別": "限制登記事項", "標籤": "查封", "內容": "臺北地院函"}
        assert split_other_item("轉載自舊建簿4冊1頁") == {"類別": None, "標籤": None, "內容": "轉載自舊建簿4冊1頁"}


class TestFallbacks:
    def _one(self, mark=None, owners=None, rights=None, title="建物登記第二類謄本(建號全部)"):
        secs = []
        if mark is not None:
            secs.append({"部": title[:2] + "標示部", "entries": [mark]})
        if owners is not None:
            secs.append({"部": title[:2] + "所有權部", "entries": owners})
        if rights is not None:
            secs.append({"部": title[:2] + "他項權利部", "entries": rights})
        t = {"header": {"謄本種類": title, "地段": "大安區仁愛段六小段", "編號": "01921-000", "編號類型": "建號"},
             "sections": secs, "注意事項": [], "頁緣": []}
        recs, traces = build_with_trace([t])
        return t, recs[0], traces[0]

    def test_unpaired_floors_go_to_other_fields(self):
        _, r, _ = self._one({"層次": ["一層", "二層"], "層次面積": "96.51平方公尺"})
        assert r["標示部"]["層次"] == []
        assert {(o["標籤"], o["值"]) for o in r["其他欄位"]} == {("層次", "一層"), ("層次", "二層"), ("層次面積", "96.51平方公尺")}

    def test_unknown_label_and_bad_number_kept(self):
        _, r, _ = self._one({"總面積": "約百坪", "車位編號": "B1-3"})
        assert r["標示部"]["總面積"] is None
        assert {(o["標籤"], o["原因"]) for o in r["其他欄位"]} == {("總面積", "無法轉數字"), ("車位編號", "不在固定清單")}

    def test_manager_group(self):
        _, r, _ = self._one(owners=[{"所有權人": "某祭祀公業", "管理者": {"_值": "李**", "統一編號": "A1*****", "住址": "台北"}}])
        assert r["所有權部"][0]["管理者"] == [{"姓名": "李**", "統一編號": "A1*****", "住址": "台北"}]

    def test_every_source_value_has_a_destination(self):
        """R2:每個原文值都有去處(固定鍵或其他欄位)。"""
        for t in parse_transcript_pages([BUILD, LAND]):
            recs, traces = build_with_trace([t])
            have = {tuple(s) for s, _, _ in traces[0]}
            assert [p for p, _ in source_leaves(t) if tuple(p) not in have] == []


# ---------------------------------------------------------------- 判定(R10)
class TestVerdicts:
    def _v(self, items=None, reason="買賣", scope="建號全部", rights=None):
        t = {"header": {"謄本種類": f"建物登記第二類謄本({scope})", "地段": "大安區仁愛段", "編號": "01921-000",
                        "編號類型": "建號"},
             "sections": [{"部": "建物標示部", "entries": [{"其他登記事項": items if items is not None else "(空白)"}]},
                          {"部": "建物所有權部", "entries": [{"次序": "0001", "登記原因": reason}]}]
             + ([{"部": "建物他項權利部", "entries": rights}] if rights else []),
             "注意事項": [], "頁緣": []}
        return build_transcript_records([t])[0]["判定"]

    def test_new_layout_restriction_category(self):
        assert self._v(["(限制登記事項)查封:臺北地院113年執字第1號"])["限制登記"] == "有"

    def test_free_text_seizure_in_old_layout_is_undeterminable(self):
        v = self._v(["臺北地院113年執字第1號函囑查封登記"])
        assert v["限制登記"] == "無法判定"

    def test_old_layout_without_category_is_undeterminable_not_unseen(self):
        assert self._v(["轉載自舊建簿4冊1頁"]) == {"他項權利": "未見", "限制登記": "無法判定", "信託": "無法判定"}

    def test_blank_items_full_scope_is_unseen(self):
        assert self._v() == {"他項權利": "未見", "限制登記": "未見", "信託": "未見"}

    def test_trust_whole_item(self):
        assert self._v(["信託財產,信託內容詳信託專簿"])["信託"] == "有"
        assert self._v(["(一般註記事項)信託財產,信託內容詳信託專簿:依108年01月02日收件大安字第1號辦理"])["信託"] == "有"

    def test_code_labels(self):
        assert self._v(["(一般註記事項)預告登記請求權人:王**統一編號A1*****"])["限制登記"] == "有"
        assert self._v(["(一般註記事項)委託人:王**"])["信託"] == "有"

    def test_registration_reason(self):
        assert self._v(reason="信託")["信託"] == "有"
        assert self._v(reason="查封")["限制登記"] == "有"
        assert self._v(reason="塗銷查封")["限制登記"] == "未見"
        assert self._v(reason="塗銷信託")["信託"] == "未見"

    @pytest.mark.parametrize("text", [
        "塗銷查封",
        # 25099 H2、9R、9O 原文:限制性註記句含「預告登記」「信託」字樣,不是限制登記或信託
        "本標的登記完畢後,三年內不得辦理移轉或預告登記,期滿後經主管機關許可始得移轉;"
        "因物權許可辦法第七條但書所列情形移轉者,不受三年內不得辦理移轉之限制。",
        "本建物所有權受平均地權條例第79條之1第3項規定限制,於登記完畢後5年內不得辦理移轉、讓與或預告登記。"
        "但因強制執行、徵收、法院判決或其他法律規定而移轉或讓與者,不在此限。",
        "本物權受寺廟或宗教團體申請贈與公有土地辦法第7條規定限制:本筆土地除經主管機關審查同意移轉為其他適用監督寺廟條例之"
        "寺廟或宗教性質法人所有外,不得以買賣、交換、贈與、信託或以其他方式為所有權之移轉。",
    ])
    def test_restrictive_notes_are_not_hits(self, text):
        assert "有" not in (self._v([text])["限制登記"], self._v([text])["信託"])
        v = self._v(["(一般註記事項)" + text])
        assert (v["限制登記"], v["信託"]) == ("未見", "未見")

    def test_other_rights(self):
        assert self._v(rights=[{"次序": "0001", "權利種類": "抵押權"}])["他項權利"] == "有"
        assert self._v(scope="所有權個人全部")["他項權利"] == "無法判定"
        assert self._v(scope="所有權個人全部")["限制登記"] == "無法判定"

    def test_body_not_read_is_undeterminable(self):
        """標示部、所有權部都沒讀到(掃描件 OCR 讀不出結構)→ 沒看到他項權利部不代表沒印。"""
        t = {"header": {"謄本種類": "建物登記第二類謄本(建號全部)", "地段": "大安區仁愛段", "編號": "01921-000"},
             "sections": [], "注意事項": [], "頁緣": ["建物標示部 登記日期…"]}
        assert build_transcript_records([t])[0]["判定"] == {"他項權利": "無法判定", "限制登記": "無法判定", "信託": "無法判定"}

    @pytest.mark.parametrize("scope", ["標示部及他項權利部", "他項權利個人全部"])
    def test_scopes_without_owner_part_can_be_unseen(self, scope):
        """這兩種範圍不一定印所有權部;讀到標示部、他項權利部沒有筆 → 未見(凍結清單的判定規則)。"""
        t = {"header": {"謄本種類": f"建物登記第二類謄本({scope})", "地段": "大安區仁愛段", "編號": "01921-000"},
             "sections": [{"部": "建物標示部", "entries": [{"建物門牌": "測試路1號"}]}], "注意事項": [], "頁緣": []}
        v = build_transcript_records([t])[0]["判定"]
        assert v["他項權利"] == "未見" and v["限制登記"] == "無法判定"

    def test_never_outputs_none(self):
        for v in (self._v(), self._v(["x"]), self._v(scope="所有權個人全部")):
            assert set(v.values()) <= set(tr.VERDICTS) and "無" not in v.values()

    def test_codes_file_has_source_for_every_item(self):
        for kind in tr.CODES["判定"].values():
            for field, items in kind.items():
                for it in items:
                    assert it["表"] in tr.CODES["來源"] and it["代碼"] and it["原文"]
        assert len(tr.CODES["鄉鎮市區"]) > 300 and "平鎮區" in tr.CODES["鄉鎮市區"]


# ---------------------------------------------------------------- 掛進 API
class TestAttach:
    PAGES = [{"rule_postprocessed": {"text": BUILD}}, {"rule_postprocessed": {"text": LAND}}]

    def test_attached_with_transcripts(self):
        df = {"owner": "x"}
        _attach_full_transcripts(df, self.PAGES, "transcript")
        assert len(df["transcript_records"]) == len(df["transcripts"]) == 2
        df2 = {}
        _attach_full_transcripts(df2, self.PAGES, "contract")
        assert df2 == {}

    def test_builder_failure_omits_only_this_key(self, monkeypatch):
        def boom(_):
            raise RuntimeError("boom")
        monkeypatch.setattr(analyze_service, "build_transcript_records", boom)
        df = {"owner": "x"}
        _attach_full_transcripts(df, self.PAGES, "transcript")
        assert "transcripts" in df and "transcript_records" not in df and df["owner"] == "x"

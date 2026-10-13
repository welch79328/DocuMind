"""
比對用文字正規化(text_normalize)——謄本、帳單、合約共用一套規則(2026-10-13)

規則依行為定義、不列碼位(業主裁示通用處理):
  1. 帶框字(NFKC 會包上括號的「字」)還原成原字;帶括號的數字或字母(條列標號)保留括號。
  2. 樣式與文字走同一套正規化,樣式裡變成正規式符號的字跳脫成字面。

謄本的固定案例仿照真實電子謄本文字層的寫法(帶框字原樣保留),人名改為虛構。
"""

import re

import pytest

from app.lib.multi_type_ocr.bill_field_extractor import BillFieldExtractor
from app.lib.multi_type_ocr.contract_field_extractor import ContractFieldExtractor
from app.lib.multi_type_ocr.text_normalize import normalize_for_matching, normalize_pattern
from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor
from app.services.analyze_service import _merge_page_structured_data


class TestRule1EnclosedLetters:

    @pytest.mark.parametrize("raw, expected", [
        ("所㈲權㆟", "所有權人"),
        ("仁愛段㈥小段", "仁愛段六小段"),
        ("忠孝東路㆕段２８５號㈤樓", "忠孝東路四段285號五樓"),
        ("鋼筋混凝㈯造", "鋼筋混凝土造"),
        ("民國108年04㈪02㈰", "民國108年04月02日"),
    ])
    def test_enclosed_letters_become_plain(self, raw, expected):
        assert normalize_for_matching(raw) == expected

    @pytest.mark.parametrize("raw, expected", [("⑴100元", "(1)100元"), ("⒜款", "(a)款")])
    def test_list_markers_keep_parentheses(self, raw, expected):
        """條列標號去掉括號會和後面的數字黏在一起"""
        assert normalize_for_matching(raw) == expected

    def test_fullwidth_alnum_and_colon(self):
        assert normalize_for_matching("權利範圍：１０００分之１９３") == "權利範圍:1000分之193"

    def test_empty(self):
        assert normalize_for_matching("") == ""
        assert normalize_for_matching(None) == ""


class TestRule2Patterns:

    def test_fullwidth_paren_in_pattern_stays_literal(self):
        pattern = normalize_pattern("甲方（出租人）")
        assert re.fullmatch(pattern, normalize_for_matching("甲方（出租人）"))
        assert re.compile(pattern).groups == 0

    def test_fullwidth_tilde_pattern_matches_normalised_text(self):
        pattern = normalize_pattern(r"(?:至|迄|～)\s*(\d{4}年)")
        assert re.search(pattern, normalize_for_matching("2026年～2027年")).group(1) == "2027年"

    def test_pattern_without_fullwidth_is_unchanged(self):
        assert normalize_pattern(r"租期[:]\s*(\d+)") == r"租期[:]\s*(\d+)"


# 仿真實電子謄本:土地頁＋建物頁,帶框字原樣
LAND_PAGE = """     ㈯㆞登記第㆓類謄本（所㈲權個㆟全部）
      大安區仁愛段㈥小段 0100-0006㆞號
  ***************  ㈯㆞標示部  ****************
    面    積：*******64.00平方公尺
  **************  ㈯㆞所㈲權部  ***************
    （0001）登記次序：0050
      所㈲權㆟：範例股份㈲限公司
    權利範圍：*****10000分之2100******
"""
BUILDING_PAGE = """     建物登記第㆓類謄本（所㈲權個㆟全部）
      大安區仁愛段㈥小段 01921-000建號
  ***************  建物標示部  ****************
    建物門牌：忠孝東路㆕段２８５號㈤樓
    主要建材：鋼筋混凝㈯造
    層    數：014層                                      總面積：**1,426.05平方公尺
    層    次：㈤層                                     層次面積：**1,426.05平方公尺
      共㈲部分：仁愛段㈥小段02163-000建號**3,213.92平方公尺
      權利範圍：*****10000分之672*******
      其他登記事㊠：使用執照字號：７１年使９３３號
    其他登記事㊠：使用執照字號：７１年使９３３號
  **************  建物所㈲權部  ***************
    （0001）登記次序：0005
      所㈲權㆟：範例股份㈲限公司
    權利範圍：全部 *********1分之1*********
"""


class TestTranscriptWithEnclosedLetters:

    async def _merged(self):
        pages = [{"ocr_raw": {"text": t, "confidence": 1.0},
                  "structured_data": await TranscriptFieldExtractor().extract(t)}
                 for t in (LAND_PAGE, BUILDING_PAGE)]
        return _merge_page_structured_data(pages)

    async def test_values_have_no_added_parentheses(self):
        m = await self._merged()
        assert m["owner"] == "範例股份有限公司"
        assert m["building_address"] == "忠孝東路四段285號五樓"
        assert m["main_material"] == "鋼筋混凝土造"
        assert m["floor_level"] == "五層"

    async def test_section_and_subsection_from_enclosed_title(self):
        m = await self._merged()
        assert (m["section"], m["subsection"]) == ("仁愛段", "六小段")
        assert "section" not in m["needs_confirmation"]
        assert {o["transcript_id"] for o in m["owners"]} == {"0100-0006", "01921-000"}

    async def test_shared_part_with_enclosed_label_is_read(self):
        m = await self._merged()
        assert m["shared_parts"] == [{
            "transcript_id": "01921-000", "build_number": "02163-000", "area": "3,213.92",
            "rights_scope": "10000分之672", "share_area": "215.98", "parking": [], "parking_total": None,
        }]


class TestBillWithEnclosedLetters:

    async def test_bill_date_with_enclosed_month_day(self):
        result = await BillFieldExtractor().extract("帳單日期：民國112年05㈪10㈰\n")
        assert result["date"] == "民國112年05月10日"


class TestContractNormalised:
    """合約的值改從正規化後的文字取出(與謄本、帳單一致):全形數字標點變半形,
    原本被全形逗號卡住的金額讀得到"""

    LEASE = (
        "房屋租賃契約書\n出租人：王小明\n承租人：李大華\n"
        "租期：２０２６年３月２７日至２０２７年３月２６日\n"
        "月租金：２５，０００元\n押金：５０，０００元\n"
    )

    async def test_fullwidth_lease_values_and_confidence(self):
        r = await ContractFieldExtractor().extract(self.LEASE)
        terms = r["rental_terms"]
        assert (terms["date_start"], terms["date_end"]) == ("2026年3月27日", "2027年3月26日")
        assert (terms["monthly_rent"], terms["deposit"]) == ("25,000", "50,000")
        assert r["extraction_confidence"] == pytest.approx(0.37)

    async def test_fullwidth_tilde_period(self):
        r = await ContractFieldExtractor().extract(
            "房屋租賃契約書\n租期：2026年3月27日～2027年3月26日\n")
        assert r["rental_terms"]["date_end"] == "2027年3月26日"

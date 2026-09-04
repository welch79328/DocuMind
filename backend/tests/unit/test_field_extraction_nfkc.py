"""
比對前的 NFKC 正規化（RegexFieldExtractor._normalize_for_matching）

2026-09-04 實測踩到:一份真實電子謄本的 PDF 文字層裡,「權利範圍」的「利」是
U+F9DD(CJK 相容表意文字)而不是一般的 U+5229——**外觀完全一樣,碼位不同**,
`"權利範圍" in text` 永遠是 False,樣式整條比不到。

為什麼以前沒事、改了才浮現:走 OCR 時是「看圖重新辨識」,輸出的是正常碼位;
改成文字層直讀之後,PDF 內嵌的相容字原樣進來,樣式就失效了。
同一份謄本走文字層路徑,加這一步之前規則抽中 13/23,之後 17/23。

這個 bug 特別難發現,因為**印出來看起來完全正常**——
只有把字元逐一拆成碼位才看得出來。
"""

import unicodedata

import pytest

from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor


# 「利」用 U+F9DD(相容字),其餘為一般碼位——這是真實電子謄本文字層的樣子
COMPAT = "利"
ASCII_LIKE = "利"

SAMPLE_COMPAT = f"""建物登記第二類謄本（建號全部）
竹田鄉過溝段 00004-000建號
**************  建物所有權部  **************
  所有權人：林順山
  權{COMPAT}範圍：全部
**************  建物他項權{COMPAT}部  *************
  權{COMPAT}種類：最高限額抵押權
"""


class TestCompatibilityIdeographs:
    def test_sample_really_uses_a_compatibility_codepoint(self):
        """先確認測試素材本身真的用了相容字,否則這組測試沒有意義。"""
        assert COMPAT in SAMPLE_COMPAT
        assert ASCII_LIKE not in SAMPLE_COMPAT
        # 兩者外觀相同但碼位不同,這正是 bug 難發現的原因
        assert unicodedata.normalize("NFKC", COMPAT) == ASCII_LIKE

    def test_naive_substring_search_fails_without_normalization(self):
        """負向確認:不正規化就是找不到——這就是原本的失效方式。"""
        assert "權利範圍" not in SAMPLE_COMPAT
        assert "權利種類" not in SAMPLE_COMPAT

    async def test_fields_are_extracted_despite_compatibility_ideographs(self):
        """正向:經過 NFKC 之後,含相容字的欄位照樣抽得到。"""
        result = await TranscriptFieldExtractor().extract(SAMPLE_COMPAT)

        assert result["rights_scope"] == "全部"
        assert result["other_right_type"] == "最高限額抵押權"

    async def test_normal_codepoints_still_work(self):
        """對照組:一般碼位的文字不受影響,沒有因為正規化而壞掉。"""
        normal = SAMPLE_COMPAT.replace(COMPAT, ASCII_LIKE)
        result = await TranscriptFieldExtractor().extract(normal)

        assert result["rights_scope"] == "全部"
        assert result["other_right_type"] == "最高限額抵押權"


class TestOtherNormalizedForms:
    """地政謄本另外兩類特殊字,NFKC 一併處理。"""

    async def test_ideographic_annotation_marks(self):
        """表意註記符號:㆞→地、㈰→日。舊式電子謄本(如建成地政)大量使用。"""
        text = "土㆞登記第二類謄本\n使用分區：特定農業區\n使用㆞類別：農牧用地\n"
        result = await TranscriptFieldExtractor().extract(text)

        assert result["land_use_zone"] == "特定農業區"
        assert result["land_use_type"] == "農牧用地"

    async def test_fullwidth_digits_in_values(self):
        """全形英數:１１１→111。門牌常見。"""
        text = "建物門牌：杭州南路一段１１１巷３之１號二樓\n"
        result = await TranscriptFieldExtractor().extract(text)

        assert result["building_address"] == "杭州南路一段111巷3之1號二樓"


class TestNormalizerItself:
    def test_empty_input_is_safe(self):
        assert TranscriptFieldExtractor._normalize_for_matching("") == ""
        assert TranscriptFieldExtractor._normalize_for_matching(None) == ""

    def test_plain_text_unchanged(self):
        """已是標準碼位、且不含全形字元的文字,NFKC 後應原樣不動。

        ⚠️ 這裡刻意用半形冒號。原本寫的是全形「：」(U+FF1A),但 NFKC 的職責
        之一就是全形轉半形(修正說明列的第三類),全形冒號必然被轉成半形——
        測試前提與修正目的自相矛盾,不是程式有錯。
        """
        text = "權利範圍:全部"          # 半形冒號,全部字元皆為標準碼位
        assert TranscriptFieldExtractor._normalize_for_matching(text) == text

    def test_fullwidth_colon_is_normalized_to_halfwidth(self):
        """全形冒號應被轉為半形——這是 NFKC 要做的事,不是副作用。

        謄本標籤常見全形冒號「權利範圍：」,而樣式用的是 [:：] 兩者皆收;
        正規化讓兩種寫法在比對階段收斂成同一形態。
        """
        assert TranscriptFieldExtractor._normalize_for_matching("權利範圍：全部") == (
            "權利範圍:全部"
        )

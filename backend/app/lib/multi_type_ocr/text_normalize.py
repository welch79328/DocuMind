"""
比對用文字正規化——謄本、帳單、合約共用的一套規則(2026-10-13)

為什麼要正規化:同一個字有多種碼位(相容表意字、全形英數、帶框字),不歸一就比不到。
例:電子謄本文字層的「權利範圍」的「利」是 U+F9DD,外觀相同、碼位不同;見
RegexFieldExtractor._normalize_for_matching 的說明。

規則(依行為定義,不列碼位——業主裁示通用處理,不打特例):

1. **相容字只歸一成同一個字,不加入原文沒有的符號。**
   NFKC 會把帶框字 ㈲ 變成「(有)」、㈥ 變成「(六)」——括號是 NFKC 用來表示「帶框」加上去的,
   原文並沒有。地政電子謄本大量使用這批字,括號一旦留下:值多出括號(「龍巖股份(有)限公司」)、
   段名比不到抬頭格式(「仁愛段(六)小段」)、「共(有)部分」認不出、公設整筆漏讀。
   所以 NFKC 若把一個「字」(Unicode 類別 Lo)包上括號,去掉這層括號。
   包的是數字或字母(⑴ ⒜)保留括號:那是條列標號,去掉會和後面的數字黏在一起(⑴100元 → 1100元)。
   對照表在載入時依此規則掃描基本多文種平面產生,不手寫碼位。

2. **樣式與文字走同一套正規化。**
   樣式裡的字正規化後若成為正規式符號(全形「（」→「(」),跳脫成字面,語意不變;
   否則文字的全形「～」正規化成「~」後,寫著全形「～」的樣式就比不到了。

⚠️ 只用在「比對」。回傳給呼叫端的 pages[].text 是使用者要看的原文,不經過這裡。

另附 is_blank_marker(2026-10-14):判斷一個讀到的值是不是原文印的「空白」,見該函式。
"""

import re
import unicodedata
from functools import lru_cache
from typing import Dict, Optional


def _enclosed_letter_table() -> Dict[int, str]:
    """規則 1 的對照表:NFKC 會包上括號的「字」→ 去掉括號的字。

    現況為 67 字(㈀–㈞、㈠–㉃)。掃描基本多文種平面一次約 0.7 秒,只在載入時做。
    """
    table: Dict[int, str] = {}
    for code in range(0x10000):
        ch = chr(code)
        nfkc = unicodedata.normalize("NFKC", ch)
        if nfkc != ch and len(nfkc) >= 3 and nfkc[0] == "(" and nfkc[-1] == ")":
            inner = nfkc[1:-1]
            if all(unicodedata.category(c) == "Lo" for c in inner):
                table[code] = inner
    return table


_ENCLOSED_LETTERS = _enclosed_letter_table()


def normalize_for_matching(text: Optional[str]) -> str:
    """比對前的文字正規化:帶框字還原成原字(規則 1),再做 NFKC。"""
    if not text:
        return ""
    return unicodedata.normalize("NFKC", text.translate(_ENCLOSED_LETTERS))


def _is_filler(ch: str) -> bool:
    """補位字元:空白、標點、符號(Unicode 類別 Z、P、S),不是字也不是數字。"""
    return ch.isspace() or unicodedata.category(ch)[0] in "ZPS"


def is_blank_marker(value: Optional[str]) -> bool:
    """讀到的值是不是原文印的「空白」(值為正規化後的文字)。

    地政謄本把沒有內容的欄位印成「使用分區:(空白)」「建築完成日期:民國---年--月--日」。
    這是**讀到了「空」**,不是讀不到;呼叫端據此回 null,但信心度照常(見 RegexFieldExtractor)。

    依性質判斷,不比對特定字串(業主裁示通用處理):
    (a) 整個值是一段括號註記——註記不是值。只認「整個值」:
        「(一般註記)登記原因:增建」後面還有內容,是值。
    (b) 日期的結構還在、數字位置全是補位:「年」前一個字是補位字元,且整個值沒有任何數字(Unicode 類別 N)。
        「民國084年02月日」有數字、「民國九十年」年前是字,都是值。
    (c) 去掉補位字元後什麼都不剩(「---」「***」)。
    遮罩姓名「黃**」有字,是值。

    2026-10-14 以 13 份謄本原文查核:整值括號註記 41 處全是「(空白)」,反例都屬「後面還有內容」。
    """
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s:
        return False
    if re.fullmatch(r"\([^()]*\)", s):
        return True
    year = s.find("年")
    if year > 0 and _is_filler(s[year - 1]) and not any(
        unicodedata.category(c)[0] == "N" for c in s
    ):
        return True
    return all(_is_filler(c) for c in s)


@lru_cache(maxsize=None)
def normalize_pattern(pattern: str) -> str:
    """樣式與文字走同一套正規化(規則 2):逐字正規化,變成別的字時跳脫成字面。"""
    out = []
    for ch in pattern:
        normalized = normalize_for_matching(ch)
        out.append(ch if normalized == ch else re.escape(normalized))
    return "".join(out)

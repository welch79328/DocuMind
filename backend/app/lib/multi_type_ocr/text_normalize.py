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


@lru_cache(maxsize=None)
def normalize_pattern(pattern: str) -> str:
    """樣式與文字走同一套正規化(規則 2):逐字正規化,變成別的字時跳脫成字面。"""
    out = []
    for ch in pattern:
        normalized = normalize_for_matching(ch)
        out.append(ch if normalized == ch else re.escape(normalized))
    return "".join(out)

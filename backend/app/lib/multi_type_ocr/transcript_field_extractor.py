"""
謄本關鍵欄位抽取器

以規則抽取謄本關鍵欄位並計算信心度;低信心且允許時以 LLM Vision(few-shot)補齊。
共用流程見 field_extraction_base.RegexFieldExtractor。

欄位分四群:
  核心   地號/建號/面積/權利範圍/所有權人 —— 原有五欄
  建物   段/小段/門牌/主要用途/建材/層數/層次/層次面積/總面積/建築完成日期
  附屬與共有 附屬建物用途與面積、共有部分建號與面積
  土地與權利 使用分區/使用地類別/他項權利種類/查封註記

擴充動機(2026-09-04):下游 jgb2「物件編輯 > 建物謄本」頁一次要填 21 個欄位,
本抽取器原本只回五欄,其餘十六欄下游只好自己再寫一套正規式去解析 OCR 全文——
同一件事在 Python 與 PHP 各做一次,兩邊各自踩同一批版面陷阱(實測 jgb2 那套
在一張單裡就踩到五個)。改為在此一次抽齊,下游只做欄位對應。
其他消費者(LINE OA 謄本匯入、MCP 上傳建物件)同樣受益。

⚠️ 沒有樣式的欄位不是沒支援:只要列進 KEY_FIELDS,規則抽不到就會進
needs_confirmation,再由 LLM Vision 以 FIELD_LABELS 的中文標籤補齊。
規則抽得到的走規則(快、免費、確定),抽不到的才付錢問模型。
"""

import re
from typing import Any, Dict, List, Optional

from .field_extraction_base import RegexFieldExtractor


class TranscriptFieldExtractor(RegexFieldExtractor):
    """謄本欄位抽取(規則 + LLM Vision + few-shot)"""

    # ⚠️ 這些樣式必須對照**真實謄本**驗證,不能照想像中的「標籤:值」格式寫。
    # 2026-09-03 以一份真實電子謄本(文字層,99.85% 精確)實測,原樣式五中四失敗,
    # 而且四個各自不同的原因——都不是 OCR 或模型問題,是樣式與格式不符:
    #
    #   地號    原 `地號[:：]值`   實際 `竹田鄉過溝段0555-0000地號`  ← **值在標籤前**
    #   面積    原 `面積[:：]值`   實際 `面積:****3,406.98平方公尺`  ← **星號補位**吃不掉
    #   建號    原 `建號[:：]值`   實際抓到 `地上建物建號:共1棟`      ← **同名不同義的欄位**
    #   權利範圍                   第 1 頁根本沒有,它在後續頁      ← 逐頁抽取的必然結果
    #   所有權人 格式吻合,唯一抽得到的                              ← 四頁都只有它
    #
    # 2026-09-04 擴充欄位時,以同一份謄本再加兩份(台北建成 2019 電子謄本、
    # 新北三重 2022 掃描件)交叉對照,補上四類新陷阱:
    #
    #   標籤內全形空白  「層　數」「層　次」          → 標籤字元間一律 `\s*`
    #   數字 token 被截斷 1,924.86 / 1.924.86        → 見下方「數值欄位」說明
    #   同行兩欄        `層 次:一層   層次面積:62.46` → 值要在下一個「標籤:」前切斷
    #   語意相反        專有部分 ↔ 共有部分是不同區塊 → 共有部分另立欄位,不共用面積樣式
    #
    # 冒號後一律用 `[ \t]*` 而非 `\s*`:`\s` 會跨換行,空值的「主要用途:」
    # 會把下一行「主要建材:鋼筋混凝土造」整條當成自己的值。
    #
    # 數值欄位一律收「整串數字 token」`([0-9][0-9,.]*[0-9]|[0-9])`,
    # 不用 `([0-9,]+\.?[0-9]*)`。後者只允許一個小數點,遇到 OCR 讀壞的
    # `1.924.86` 會**自己把比對結果截斷成 `1.924`**——差近一千倍,而且格式合法。
    # 抽取器的職責是把 token 完整取出,不判斷數字對不對:
    # 值的解讀與正規化屬 field_normalizer,可信度屬共識與 LLM 補齊機制。
    # 寧可回傳一個看得出壞掉的 `1.924.86`,也不要回一個看起來正常的錯數字。
    PATTERNS = {
        # 地政謄本的寫法是「段名 + 地號數字 + 地號」,值在標籤**前面**。
        # 兩種順序都收:標籤在後(真實格式)優先,標籤在前(少數表格式版型)為備援。
        # 地號可能含連字號（0555-0000）也可能不含（純數字流水號）。
        # 2026-09-03 第一版寫死要求連字號，被既有測試的 `地號：1234` 抓包——
        # 該格式雖非真實謄本主流寫法，但作為「標籤在前」備援分支合理存在，
        # 值本身不應限縮成一定要有連字號。
        # 第三個分支是「建物坐落地號」:值與標籤之間還隔著段與小段——
        #   建物坐落地號:中正段二小段 0221-0000
        # 前兩個分支都要求標籤與數字相鄰,這種寫法會整條落空(2026-09-04 實測建成謄本)。
        "land_number": re.compile(
            r"([0-9Oo]{3,5}\s*[-－]\s*[0-9Oo]{2,5}|[0-9]{3,10})\s*地\s*號"
            r"|地\s*號[:：\s]*([0-9Oo]{3,5}\s*[-－]\s*[0-9Oo]{2,5}|[0-9]{3,10})"
            r"|坐落地號[:：][^\n]*?([0-9Oo]{3,5}\s*[-－]\s*[0-9Oo]{2,5})"
        ),
        # 排除「地上建物建號」——那是土地標示部的欄位,值是「共1棟」不是建號。
        # (?<!地上建物) 確保抓到的是建物標示部的真建號。
        "building_number": re.compile(
            r"(?<!地上建物)建\s*號[:：\s]*([0-9Oo]{3,5}\s*[-－]\s*[0-9Oo]{3,5})"
            r"|([0-9Oo]{3,5}\s*[-－]\s*[0-9Oo]{3,5})\s*建\s*號"
        ),
        # `[*\s]*` 吃掉謄本的補位星號(****3,406.98)。
        # 星號補位在金額欄位也會出現,不是這一份的特例。
        "area": re.compile(r"面\s*積[:：\s]*[*\s]*([0-9][0-9,.]*[0-9]|[0-9])"),
        # 四個陷阱,缺一個就取到錯的值(前三個 2026-09-10 以杭州南路一段那份合併謄本實測):
        #
        # 1. `(?<!歷次取得)` —— 謄本同時印「權利範圍」與「歷次取得權利範圍」,
        #    後者是歷史值,不是現況。該份文件全文命中 5 次,其中 2 次是它。
        # 2. **不要跳過「全部」。** 建物那筆印成「權利範圍：全部 *1分之1*」,
        #    我曾加 `(?:全部\s*)?` 想改取分數,結果 3 個既有測試立刻掛掉——
        #    本專案既有的語意就是回「全部」(它與「1分之1」等價,且是契約用語)。
        #    而且 `\s*` 會吃掉換行:值剛好只有「全部」時,會跨行抓到下一行的
        #    「所有權人:」。要改成回分數請先確認下游,不是改一條正規式的事。
        # 3. **區段限定在 `_scope_for()`,不在這條正規式裡。**
        #    土地與建物所有權部印的標籤逐字相同,只有位置不同——
        #    這種情況負向斷言救不了,見 _scope_for 的說明。
        #
        # 4. `(?<!設定)` —— 他項權利部(抵押權等)印的是「設定權利範圍」,
        #    那是抵押權的範圍,不是所有權的持分。主要防線是 _scope_for 截到
        #    他項權利部標題為止;這個斷言是標題被 OCR 打壞時的第二道(2026-09-23)。
        "rights_scope": re.compile(
            r"(?<!歷次取得)(?<!設定)權利範圍[:：\s]*[*\s]*([^\s\n*]+)"
        ),
        # 土地所有權部的權利範圍(持分)。樣式與 rights_scope 逐字相同,
        # 差別全在 _scope_for 給的比對範圍:這一欄只看土地所有權部那一段。
        #
        # 為什麼需要它(2026-09-21):rights_scope 在土地頁刻意回空字串,
        # 等建物頁補值——但**純土地謄本沒有建物頁**,值就永久遺失。
        # 這一欄讓合併層在「整份文件都沒有建物跡證」時拿來遞補,
        # 見 analyze_service._backfill_land_rights_scope。
        "land_rights_scope": re.compile(
            r"(?<!歷次取得)(?<!設定)權利範圍[:：\s]*[*\s]*([^\s\n*]+)"
        ),
        # `所\(?有\)?權人` 的括號不是手滑。謄本原文用相容碼位「所㈲權㆟」,
        # 而 NFKC 把 `㈲`(U+3232 CIRCLED IDEOGRAPH HAVE)正規化成 **`(有)` 帶括號**
        # ——不是 `有`。所以比對「所有權人」在真實謄本上一次都比不到。
        # 2026-09-10 實測:杭州南路一段那份謄本的 owner 因此一直是 None,
        # 而 owner 是必要欄位,抽不到就直接壓低信心度、把整份文件拖進人工複核。
        # 同類的還有 `㈯`→`(土)`、`㈰`→`(日)`、`㈪`→`(月)`;新增樣式時務必
        # 先拿真實謄本跑一次 NFKC 再寫,不要照著螢幕上看到的字寫。
        "owner": re.compile(r"(?:所\(?有\)?權人|登記名義人)[:：\s]*([^\s\n]+)"),

        # ---- 建物標示部 ----
        # 段/小段:抬頭寫成「竹田鄉過溝段0555-0000地號」或「中正區中正段二小段 00465-000建號」。
        # 段名非貪婪才不會把「小段」吞進去——貪婪會讓「中正段二小段」整串變成段名。
        # 行政區(鄉鎮市區)剝掉:下游的段欄位只要「中正段」,混進行政區會印出「中正區中正段」。
        "section": re.compile(
            # (?<!小):抬頭被 OCR 拆行時,「小段0361-0000地號」單獨一行,
            # 段名會變成「小段」(2026-09-30 線上實測)。寧可缺值。
            r"(?:[一-鿿]+?[鄉鎮市區])?([一-鿿]+?(?<!小)段)"
            r"(?:[一-鿿\d]*小段)?\s*[0-9Oo]{3,5}\s*[-－]"
        ),
        "subsection": re.compile(r"[一-鿿]+?段\s*([一-鿿\d]+小段)"),
        "building_address": re.compile(r"建物門牌[:：][ \t]*([^\n]+)"),
        "main_usage": re.compile(
            r"主\s*要\s*用\s*途[:：][ \t]*([^\n]*?)(?=\s{2,}\S+\s*[:：]|\n|$)"
        ),
        "main_material": re.compile(
            r"主\s*要\s*建\s*材[:：][ \t]*([^\n]*?)(?=\s{2,}\S+\s*[:：]|\n|$)"
        ),
        # 層數(整棟共幾層)與層次(本建號位在第幾層)是兩件事,不可混用。
        #
        # OCR 異體(2026-09-30 線上實測):「層數」常被讀成簡體「数」,「層」讀成「唇」
        # 或整個掉字(「数:007層」)。標籤只放寬到這幾種;值仍要求「數字+層」,
        # 且掉字時排除「筆數/棟數/頁數」這類同樣以「數:」結尾的標籤。
        "total_floors": re.compile(
            r"(?:[層唇]\s*[數数]|(?<![筆棟頁冊件])[數数])[:：][ \t]*[*\s]*([0-9]{1,3}\s*層)"
        ),
        # (?<!建物):公設自己的其他登記事項印「建物層次:公共設施」,不是本戶在幾樓。
        "floor_level": re.compile(
            r"(?<!建物)[層唇]\s*次[:：][ \t]*([^\n]*?)(?=\s{2,}\S+\s*[:：]|\n|$)"
        ),
        "floor_area": re.compile(
            r"[層唇]\s*次\s*面\s*積[:：][ \t]*[*\s]*([0-9][0-9,.]*[0-9]|[0-9])"
        ),
        # 與核心的 area 分開:一份土地+建物合併謄本裡 area 可能抓到土地面積,
        # 而「總面積」明確是建物的共計面積,下游要用哪一個由它自己判斷。
        "total_area": re.compile(
            r"總\s*面\s*積[:：][ \t]*[*\s]*([0-9][0-9,.]*[0-9]|[0-9])"
        ),
        "completion_date": re.compile(
            # 文字層原文是「建築完成㈰期」,NFKC 後為「(日)」(同 owner 的 ㈲ 陷阱)
            r"建築完成\(?日\)?期[:：][ \t]*([^\n]*?)(?=\s{2,}\S+\s*[:：]|\n|$)"
        ),

        # ---- 附屬建物(陽台、平台之類;單層透天通常沒有) ----
        "sub_building_usage": re.compile(
            r"附屬建物用途[:：][ \t]*([^\n]*?)(?=\s{2,}\S+\s*[:：]|\n|$)"
        ),
        # 「面積」是通用字眼,必須限定在附屬建物那一行內取,
        # 否則會誤抓標示部其他行的面積。
        "sub_building_area": re.compile(
            r"附屬建物用途[:：][^\n]*?面\s*積[:：][ \t]*[*\s]*([0-9][0-9,.]*[0-9]|[0-9])"
        ),

        # ---- 共有部分(公寓大樓才有) ----
        # ⚠️ 與「專有部分」語意相反,兩者的建號與面積是不同的東西,不可共用樣式。
        "shared_build_number": re.compile(
            r"共有部分[:：]?[^\n]*?([0-9Oo]{3,5}\s*[-－]\s*[0-9Oo]{3,5})\s*建\s*號"
        ),
        "shared_area": re.compile(
            r"共有部分[:：]?[^\n]*?建\s*號[^0-9\n]*([0-9][0-9,.]*[0-9]|[0-9])"
        ),

        # ---- 他項權利與查封 ----
        "other_right_type": re.compile(
            r"權利種類[:：][ \t]*([^\n]*?)(?=\s{2,}\S+\s*[:：]|\n|$)"
        ),
        # 只回關鍵字本身,是否視為「有查封」由下游決定。
        "seizure_mark": re.compile(r"(查封|假扣押|假處分|禁止處分|限制登記|預告登記)"),

        # ---- 土地標示部 ----
        "land_use_zone": re.compile(
            r"使用分區[:：][ \t]*([^\n]*?)(?=\s{2,}\S+\s*[:：]|\n|$)"
        ),
        "land_use_type": re.compile(
            r"使用地類別[:：][ \t]*([^\n]*?)(?=\s{2,}\S+\s*[:：]|\n|$)"
        ),
    }

    KEY_FIELDS = (
        # 核心五欄:順序不動,既有下游與測試依賴它們存在
        "land_number", "building_number", "area", "rights_scope", "owner",
        # 建物標示部
        "section", "subsection", "building_address",
        "main_usage", "main_material", "total_floors",
        "floor_level", "floor_area", "total_area", "completion_date",
        # 附屬建物
        "sub_building_usage", "sub_building_area",
        # 共有部分
        "shared_build_number", "shared_area",
        # 他項權利與查封
        "other_right_type", "seizure_mark",
        # 土地標示部
        "land_use_zone", "land_use_type",
        # 土地所有權部
        "land_rights_scope",
    )

    # 必要欄位:任何一份謄本都「應該要有」的欄位,信心度只以這些計算。
    #
    # 刻意排除的欄位與理由(2026-09-04):
    #
    #   subsection          並非每個段都有小段
    #   sub_building_*      附屬建物(陽台、平台)不是每棟都有,單層透天通常沒有
    #   shared_*            共有部分只有公寓大樓才有,透天沒有
    #   other_right_type    他項權利只有設定抵押等情形才有,無貸款的房子沒有
    #   land_use_type       使用地類別(非都市土地)與使用分區(都市土地)**互斥**,
    #                       同一筆土地不會兩者都有
    #   total_floors        部分版型只印層次不印層數
    #   completion_date     土地謄本沒有建築完成日期(那是建物才有的欄位)
    #
    #   ⚠️ seizure_mark     查封註記**沒有才是正常且理想的**。
    #                       把它的缺席計為信心度 0,語意上是反的——
    #                       一份乾淨的謄本反而會被判定低信心。
    #
    # 這些欄位仍留在 KEY_FIELDS:抽到就回傳給下游,只是不列入評分與待確認。
    #
    # 動機:欄位由 5 擴充到 23 後,extraction_confidence 從 0.54 掉到 0.196,
    # 而掉下去的原因全是「這份謄本本來就沒有這些東西」,不是抽取失敗。
    REQUIRED_FIELDS = (
        "land_number", "building_number", "area", "rights_scope", "owner",
        "section", "building_address",
        "main_usage", "main_material",
        "floor_level", "floor_area", "total_area",
        "land_use_zone",
    )

    # 中文標籤同時是 LLM 的提問用語:規則抽不到的欄位會拿這些字去問模型,
    # 因此要用**謄本上真正印的字**,不要用內部代號或意譯。
    FIELD_LABELS = {
        "land_number": "地號", "building_number": "建號", "area": "面積",
        "rights_scope": "權利範圍", "owner": "所有權人",
        "section": "段", "subsection": "小段", "building_address": "建物門牌",
        "main_usage": "主要用途", "main_material": "主要建材",
        "total_floors": "層數", "floor_level": "層次", "floor_area": "層次面積",
        "total_area": "總面積", "completion_date": "建築完成日期",
        "sub_building_usage": "附屬建物用途", "sub_building_area": "附屬建物面積",
        "shared_build_number": "共有部分建號", "shared_area": "共有部分面積",
        "other_right_type": "他項權利種類", "seizure_mark": "查封或限制登記",
        "land_use_zone": "使用分區", "land_use_type": "使用地類別",
        # 謄本上印的其實也是「權利範圍」。不列入 REQUIRED_FIELDS,
        # 所以永遠不會進 needs_confirmation、不會拿這個標籤去問模型。
        "land_rights_scope": "土地權利範圍",
    }
    DOC_LABEL = "土地/建物謄本"

    # 只在「建物所有權部」之後才有意義的欄位。
    #
    # 一份土地＋建物的合併謄本會依序印:土地所有權部 → 土地所有權部 → 建物所有權部,
    # 三段都有「權利範圍」。全文比對取第一個命中,拿到的是**土地的持分**
    # (實測 4分之1),而下游 JGB 把這個值填進契約的「專有部分 權利範圍」——
    # 那個欄位的語意是建物,填土地持分是錯的(建物那筆是「全部 1分之1」)。
    #
    # ⚠️ 只驗單頁建物謄本的測試抓不到這個缺陷:單頁時全文比對剛好命中正確那筆。
    # 回歸測試務必用「土地在前、建物在後」的合併版型。
    _BUILDING_SECTION_FIELDS = ("rights_scope",)

    # NFKC 之後標題長這樣:「建物所(有)權部」。
    # `㈲`(U+3232 CIRCLED IDEOGRAPH HAVE)正規化成 **`(有)` 帶括號**,不是 `有`,
    # 所以不能直接比對「建物所有權部」——那樣一次都比不到。實測確認。
    _BUILDING_SECTION = re.compile(r"建\s*物\s*所\s*\(?\s*有\s*\)?\s*權\s*部")
    _LAND_SECTION = re.compile(r"\(?土\)?\s*地\s*所\s*\(?有\)?\s*權\s*部")

    # 只在「土地所有權部」那一段才有意義的欄位,範圍截到建物所有權部為止。
    _LAND_SECTION_FIELDS = ("land_rights_scope",)

    # 所有權部之後的他項權利部(抵押權等)也有「權利範圍」,只是印成「設定權利範圍」。
    # 兩種所有權部的比對範圍都截到這個標題為止,見 _scope_for。
    _OTHER_RIGHTS_SECTION = re.compile(r"他\s*項\s*權\s*利\s*部")

    # ---- 公設(共有部分)與舊地段:位置不對的同名標籤 ----
    #
    # 建物標示部的共有部分是一個小區塊:
    #     共有部分:○○段00697-000建號*****19.62平方公尺
    #     權利範圍:*****5分之1*****           ← 公設的持分,不是本戶的
    #     (含車位編號2號,權利範圍:…)
    #     其他登記事項:主要用途:水箱、樓梯間
    #                  建物層次:公共設施        ← 公設的層次,不是本戶的
    #                  重測前:…01272-000建號     ← 公設的舊建號
    #     其他登記事項:使用執照字號:…           ← 這一行起回到本戶
    # 區塊裡的建號、權利範圍、層次跟本戶的標籤逐字相同,只有位置能區分。
    # 縮排能分辨區塊邊界,但 OCR 輸出不保留縮排,所以以「區塊內第二個其他登記事項」
    # 為界;碰到部別標題或下一個共有部分也結束。(2026-09-30 線上實測,見
    # tests/unit/test_transcript_shared_part_scope.py)
    # 必須是行首的「共有部分:」——行中出現的「共有部分」(如公設自己謄本的
    # 「主要用途:共有部分」、所有權部的註記文字)不是區塊開頭。
    _SHARED_PART_LINE = re.compile(r"^\W*共\s*有\s*部\s*分\s*[:：]")
    _OTHER_ITEMS_LINE = re.compile(r"^\W*其他登記事項")
    # 區塊一定在所有權人名單之前結束。部別標題被 OCR 讀壞時,
    # 靠這些行首標籤止血,不然會把所有權人一併切掉、改取到下一位。
    _OWNERSHIP_ENTRY_LINE = re.compile(r"登\s*記\s*次\s*序|所\s*\(?\s*有\s*\)?\s*權\s*人")
    _PART_HEADING = re.compile(
        r"(?:標\s*示|所\s*\(?\s*有\s*\)?\s*權|他\s*項\s*權\s*利)\s*部"
    )
    # 只有 shared_* 看得到公設區塊;其餘欄位一律在去掉公設區塊的文字上比對。
    # 段、小段例外:公設與本戶在同一棟、同一段,共有部分那一行的段名是對的
    # (高雄範本的段名只出現在那一行)。舊地段另由 _NOT_CURRENT_LOCATION_LINE 擋。
    _SHARED_PART_FIELDS = ("shared_build_number", "shared_area", "section", "subsection")

    # 「重測前/重劃前:舊段名 舊地號/建號」是沿革,不是現況,四個位置欄位都不能用。
    _NOT_CURRENT_LOCATION_LINE = re.compile(r"重\s*[測测劃划]\s*前")
    _LOCATION_FIELDS = ("section", "subsection", "land_number", "building_number")
    # 「共同擔保地號/建號」是抵押標的清單,編號可能是別筆,不能當本戶的地號、建號;
    # 但清單一定含本筆,段名與小段是對的——抬頭被 OCR 讀壞時常是唯一來源
    # (士林、汐止範本實測,2026-09-30 verifier 抓到誤擋)。只對編號擋。
    _COLLATERAL_LIST_LINE = re.compile(r"共\s*同\s*擔\s*保")
    _NUMBER_FIELDS = ("land_number", "building_number")

    # ---- 建物跡證:判定「這一頁有沒有建物」 ----
    #
    # 合併層靠它決定能不能拿土地持分遞補 rights_scope:任一頁有建物跡證就不遞補。
    # 判錯的代價不對稱——把合併謄本誤判成純土地,土地持分會被當成建物權利範圍
    # 送進下游契約欄位,正是 0658077 修掉的災情;反過來誤判只是留缺值進複核。
    # 所以寧可多認、不可漏認。
    #
    # ⚠️ 不能只看建物所有權部標題。標題正是 OCR 最容易打壞的一行,
    # 打壞時整份會被當成純土地謄本。因此另看建物標示部標題,
    # 以及任何一個建物專屬欄位有沒有抽到值——標題壞了,門牌、層次面積通常還在。
    _BUILDING_MARK_SECTION = re.compile(r"建\s*物\s*標\s*示\s*部")

    # 土地謄本不可能有的欄位。building_number 可以放心列入:
    # 它的樣式以 (?<!地上建物) 排除了土地標示部的「地上建物建號」。
    _BUILDING_EVIDENCE_FIELDS = (
        "building_number", "building_address", "main_usage", "main_material",
        "total_floors", "floor_level", "floor_area", "total_area", "completion_date",
        "sub_building_usage", "sub_building_area",
        "shared_build_number", "shared_area",
    )

    async def extract(
        self,
        text: str,
        image_data: Optional[str] = None,
        use_llm_fallback: bool = False,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        result = await super().extract(
            text,
            image_data=image_data,
            use_llm_fallback=use_llm_fallback,
            few_shot=few_shot,
        )
        # 另外單獨跑一次規則抽取來判定跡證,不用 result 裡的欄位:
        # result 可能含 LLM 補齊的值,模型對土地謄本回一個「建號」
        # 也會被當成建物跡證。跡證只能來自文件本身的文字。
        regex_fields, _ = self._extract_with_regex(text)
        # 標題比對必須用正規化後的文字:原文的「㈲」不正規化就一次都比不到。
        norm = self._normalize_for_matching(text)
        result["has_building_evidence"] = bool(
            self._BUILDING_SECTION.search(norm)
            or self._BUILDING_MARK_SECTION.search(norm)
            or any(regex_fields.get(k) for k in self._BUILDING_EVIDENCE_FIELDS)
        )
        # 清單欄位與旗標一樣只來自文件文字,不含 LLM 補齊的值。
        result["owners"] = self._extract_owners(norm)
        result["land_numbers"] = self._extract_land_numbers(norm)
        floors, check = self._extract_floors(norm, regex_fields.get("total_area"))
        result["floors"] = floors
        result["floor_area_checks"] = [check] if check else []
        result["sub_buildings"] = self._extract_sub_buildings(norm)
        return result

    def _scope_for(self, key: str, text: str) -> str:
        """建物專屬欄位的比對範圍。三條路,少一條就會取到錯的值。

        **抽取是逐頁跑的,不是整份跑。** 這一點決定了整個設計:
        一份土地＋建物的合併謄本會分成「土地頁 / 土地頁 / 建物頁」,
        而跨頁合併(_merge_page_structured_data)是「只填補缺值」——
        第一頁先落地的值就贏了。所以光是「在建物區段之後才比對」不夠:
        土地頁上根本沒有建物區段,它會退回全文、抽出土地的持分(4分之1),
        然後第三頁抽到的「全部」永遠補不進去。
        2026-09-10 實測正式服務就是這樣回 4分之1 的——**修一頁之內的範圍
        不等於修好這個缺陷**,務必用多頁合併謄本驗收,不要只驗單頁。

        1. 有建物所有權部 → 從那裡往後比對。
        2. 沒有建物、但有土地所有權部 → **回空字串,這一頁不抽**。
           讓合併時由建物頁提供正確值。
        3. 兩個標題都沒有(單張建物謄本、版型殘缺)→ 退回全文。
           沒有土地區段可混淆,全文比對本來就會命中正確那筆;
           硬性要求標題會讓單頁謄本一個欄位都抽不到。

        兩項前處理先於三條路(2026-09-30):除了 shared_* 之外,所有欄位都在
        去掉公設區塊的文字上比對;地段與編號另去掉「重測前」那幾行,地號與建號再去掉「共同擔保」那幾行。
        見 _SHARED_PART_LINE 的說明。

        土地專屬欄位(_LAND_SECTION_FIELDS)另走一條:從土地所有權部標題開始,
        截到建物所有權部為止;沒有土地標題就不抽。上面三條路對 rights_scope 不變。

        **所有路徑的範圍都再截到「他項權利部」標題為止**(2026-09-23)。
        他項權利部緊接在所有權部之後,它的「設定權利範圍」是抵押權的範圍。
        不截的話會取錯兩種情況,都是信心度 0.9、不進複核:
          - 所有權部那一行讀不出來 → 比對延伸到同頁的他項權利部。
          - 單獨一頁的他項權利部沒有所有權部標題 → 走第 3 條路退回全文。
            純土地謄本因此拿到抵押權的範圍,土地持分的遞補也被擋掉。
        截斷後這兩種情況都變成缺值:合併謄本進複核,純土地謄本由土地持分遞補。
        """
        if key not in self._SHARED_PART_FIELDS:
            text = self._strip_shared_parts(text)
        if key in self._LOCATION_FIELDS:
            text = self._drop_lines(text, self._NOT_CURRENT_LOCATION_LINE)
        if key in self._NUMBER_FIELDS:
            text = self._drop_lines(text, self._COLLATERAL_LIST_LINE)
        if key in self._LAND_SECTION_FIELDS:
            land = self._LAND_SECTION.search(text)
            if not land:
                return ""
            scoped = text[land.start():]
            building = self._BUILDING_SECTION.search(scoped)
            if building:
                scoped = scoped[:building.start()]
            return self._cut_at_other_rights(scoped)
        if key not in self._BUILDING_SECTION_FIELDS:
            return text
        m = self._BUILDING_SECTION.search(text)
        if m:
            return self._cut_at_other_rights(text[m.start():])
        if self._LAND_SECTION.search(text):
            return ""
        return self._cut_at_other_rights(text)

    # ---- 清單欄位:owners / land_numbers(2026-09-30,slice B1) ----
    #
    # 單值的 owner、land_number 只回第一筆;這兩個清單把每一筆都交出來。
    # 它們是「明細」不是「欄位」:不進 KEY_FIELDS(沒有信心度、不問 LLM、不進待確認),
    # 並登記在 field_consensus._META_KEYS 與前端 META_KEYS。跨頁合併依身分去重,
    # 見 analyze_service._merge_list_details。

    # 所有權部每一筆的開頭「(0001)登記次序:0003」。取的是冒號後那一段(0003),
    # 不是括號裡的流水號;「相關他項權利登記次序:0003-000」不在行首,不會命中。
    _OWNERSHIP_ENTRY_START = re.compile(
        r"^\W*\(\s*\d{4}\s*\)\s*登\s*記\s*次\s*序\s*[:：]?\s*([0-9]{4}(?:-[0-9]{3})?)?"
    )
    # 姓名一定要有冒號:導讀範本的說明框「所有權人的身分資料」不是姓名。
    _ENTRY_OWNER = re.compile(
        r"(?:所\s*\(?\s*有\s*\)?\s*權\s*人|登記名義人)\s*[:：]\s*(\S+)"
    )
    _ENTRY_SCOPE = re.compile(r"(?<!歷次取得)(?<!設定)權利範圍[:：\s]*[*\s]*([^\s\n*]+)")
    # 只在一筆所有權資料之內才接受 OCR 讀壞的標籤(「利:」「檬利:」,線上實測),
    # 並排除同樣含「利」的相關他項權利登記次序、設定權利範圍、歷次取得權利範圍。
    _ENTRY_SCOPE_MANGLED = re.compile(r"利\s*(?:範\s*圍)?\s*[:：][ \t]*[*\s]*([^\s\n*]+)")
    _ENTRY_SCOPE_EXCLUDE = re.compile(r"相\s*關|設\s*定|歷\s*次|登\s*記\s*次\s*序")
    _MARK_SECTION_ANY = re.compile(r"標\s*示\s*部")
    # 持分值至少要有數字或「全部」;讀不出來時抓到的「:」「*」之類是雜訊,寧可缺值。
    _SHARE_LIKE = re.compile(r"[0-9]|全部")

    # 頁首抬頭:整行只有「[行政區][段][小段] 數字-數字 地號/建號」。
    # 位置不限——續頁會重複抬頭,OCR 也可能把它排到頁尾(士林範本實測)。
    _TITLE_NUMBER_LINE = re.compile(
        r"^\W*(?:[一-鿿]*?[鄉鎮市區])?(?:[一-鿿\d]*段)?(?:[一-鿿\d]*小段)?"
        r"\s*([0-9]{3,5}\s*-\s*[0-9]{2,5})\s*([地建])\s*號\s*$"
    )
    _SITE_LINE = re.compile(r"建\s*物\s*坐\s*落\s*地\s*號\s*[:：](.*)")
    _NUMBER_TOKEN = re.compile(r"[0-9]{3,5}\s*-\s*[0-9]{2,5}")
    _NUMBERS_ONLY_LINE = re.compile(r"^\s*(?:[0-9]{3,5}\s*-\s*[0-9]{2,5}\s*)+$")
    # 沿革、擔保清單、地上建物清單:數字長得像地號,但都不是這一份的現行地號。
    _NOT_A_PARCEL_LINE = re.compile(
        r"重\s*[測测劃划]\s*前|共\s*同\s*擔\s*保|分\s*割|合\s*併|增\s*加|地\s*上\s*建\s*物"
    )

    def _title_number(self, lines):
        """頁首抬頭的 (編號, '地'|'建');讀不到回 (None, None)。"""
        for line in lines:
            m = self._TITLE_NUMBER_LINE.match(line)
            if m:
                return re.sub(r"\s+", "", m.group(1)), m.group(2)
        return None, None

    def _section_text(self, line: str):
        """段+小段,去掉行政區(「中正區中正段二小段」→「中正段二小段」)。"""
        sec = self.PATTERNS["section"].search(line)
        if not sec:
            return None
        sub = self.PATTERNS["subsection"].search(line)
        return sec.group(1) + (sub.group(1) if sub else "")

    def _extract_owners(self, text: str) -> list:
        """所有權部的每一筆:{part, transcript_id, order, name, rights_scope}。

        part 由這一筆上方最近的所有權部標題決定(土地/建物),沒有標題就不收——
        土地持分被當成建物權利範圍是 0658077 修掉的災情,不猜。
        """
        lines = text.split("\n")
        # 預設用頁上第一個抬頭(OCR 可能把抬頭排到頁尾,士林範本實測);
        # 一頁有兩個抬頭時,改用這一筆「上方最近」的那個,不讓後一份的人掛到前一份。
        transcript_id, _ = self._title_number(lines)
        owners, current = [], None
        part, in_ownership = None, False

        def flush():
            if current and current["name"]:
                owners.append(current)

        for line in lines:
            title = self._TITLE_NUMBER_LINE.match(line)
            if title:
                transcript_id = re.sub(r"\s+", "", title.group(1))
                continue
            if self._LAND_SECTION.search(line) or self._BUILDING_SECTION.search(line):
                flush()
                current = None
                part = "building" if self._BUILDING_SECTION.search(line) else "land"
                in_ownership = True
                continue
            if self._OTHER_RIGHTS_SECTION.search(line) or self._MARK_SECTION_ANY.search(line):
                flush()
                current, in_ownership = None, False
                continue
            if not in_ownership:
                continue
            start = self._OWNERSHIP_ENTRY_START.match(line)
            if start:
                flush()
                current = {
                    "part": part, "transcript_id": transcript_id,
                    "order": start.group(1), "name": None, "rights_scope": None,
                }
                continue
            if current is None:
                continue
            if current["name"] is None:
                m = self._ENTRY_OWNER.search(line)
                if m:
                    current["name"] = m.group(1)
                    continue
            if current["rights_scope"] is None:
                m = self._ENTRY_SCOPE.search(line)
                if not m and not self._ENTRY_SCOPE_EXCLUDE.search(line):
                    m = self._ENTRY_SCOPE_MANGLED.search(line)
                if m and self._SHARE_LIKE.search(m.group(1)):
                    current["rights_scope"] = m.group(1)
        flush()
        return owners

    def _extract_land_numbers(self, text: str) -> list:
        """現行地號 {section, number},只取頁首地號抬頭與建物坐落地號兩個來源。"""
        lines = text.split("\n")
        found, seen = [], set()

        def add(section, number):
            number = re.sub(r"\s+", "", number)
            key = (section, number)
            if key not in seen:
                seen.add(key)
                found.append({"section": section, "number": number})

        for i, line in enumerate(lines):
            if self._NOT_A_PARCEL_LINE.search(line):
                continue
            title = self._TITLE_NUMBER_LINE.match(line)
            if title and title.group(2) == "地":
                add(self._section_text(line), title.group(1))
                continue
            site = self._SITE_LINE.search(line)
            if site:
                body = site.group(1)
                numbers = self._NUMBER_TOKEN.findall(body)
                # 數字被 OCR 折到下一行時,下一行只會有地號
                if not numbers and i + 1 < len(lines) and self._NUMBERS_ONLY_LINE.match(lines[i + 1]):
                    body = body + " " + lines[i + 1]
                    numbers = self._NUMBER_TOKEN.findall(lines[i + 1])
                section = self._section_text(body)
                for number in numbers:
                    add(section, number)
        return found

    # ---- 清單欄位:floors / sub_buildings / floor_area_checks(2026-10-01,slice B2) ----
    #
    # 左欄名稱(一層、陽台)與右欄面積在 OCR 輸出裡常被拆散、漏字,
    # 所以只有兩邊數量相等才依序配對;對不上就只給面積(或只給用途),不猜。

    # 層次區段起點:「層數」標籤本身,不要求值——掃描件的值會讀壞成「00.」。
    # 同 total_floors 的標籤,涵蓋單獨「數:」、簡體「数」、「唇数」、「層    數」。
    _FLOOR_REGION_START = re.compile(r"(?:[層唇]\s*[數数]|(?<![筆棟頁冊件])[數数])\s*[:：]")
    # 區段終點。附屬建物要帶「用途:」——導讀範本說明框殘字「附屬建物及公」不算(瑞芳實測)。
    _FLOOR_REGION_END = re.compile(
        r"建\s*築\s*完\s*成|附\s*屬\s*建\s*物\s*用\s*途\s*[:：]|共\s*有\s*部\s*分|^\W*其他登記事項"
        r"|(?:標\s*示|所\s*\(?\s*有\s*\)?\s*權|他\s*項\s*權\s*利)\s*部"
    )
    _SUB_REGION_START = re.compile(r"附\s*屬\s*建\s*物\s*用\s*途\s*[:：]")
    _SUB_REGION_END = re.compile(
        r"共\s*有\s*部\s*分|^\W*其他登記事項"
        r"|(?:標\s*示|所\s*\(?\s*有\s*\)?\s*權|他\s*項\s*權\s*利)\s*部"
    )
    # 層次名稱用中文數字;「005層」是層數(總共幾層),不是層次。
    _FLOOR_LEVEL = re.compile(
        r"(?:地\s*下\s*)?[一二三四五六七八九十]+\s*層|騎\s*樓|夾\s*層|屋\s*頂\s*突\s*出\s*物"
    )
    # 附屬建物用途只認固定詞彙:OCR 雜訊(「箱」「横」)與說明框文字一律略過。
    _SUB_USAGE = re.compile(
        r"陽\s*台|雨\s*遮|平\s*台|露\s*台|花\s*台|屋\s*簷|車\s*位|停\s*車\s*空\s*間|機\s*房"
        r"|梯\s*間|地\s*下\s*室|夾\s*層|屋\s*頂\s*突\s*出\s*物|防\s*空\s*避\s*難\s*室|儲\s*藏\s*室"
    )
    _AREA_VALUE = re.compile(r"([0-9][0-9,.]*[0-9])\s*平\s*方\s*公\s*尺")
    _TOTAL_AREA_LABEL = re.compile(r"總\s*面\s*積")

    def _region(self, lines, start, end):
        """(區段起點行號, 區段各行);起點行本身算在區段內,找不到起點回 (None, [])。"""
        for i, line in enumerate(lines):
            if start.search(line):
                body = [line]
                for later in lines[i + 1:]:
                    if end.search(later):
                        break
                    body.append(later)
                return i, body
        return None, []

    def _building_title_above(self, lines, index):
        """區段上方最近的建號抬頭;沒有就用頁上第一個抬頭(OCR 可能把抬頭排到頁尾)。"""
        for line in reversed(lines[:index]):
            m = self._TITLE_NUMBER_LINE.match(line)
            if m and m.group(2) == "建":
                return re.sub(r"\s+", "", m.group(1))
        for line in lines:
            m = self._TITLE_NUMBER_LINE.match(line)
            if m and m.group(2) == "建":
                return re.sub(r"\s+", "", m.group(1))
        return None

    @staticmethod
    def _pair(names, areas, name_key):
        if names and areas and len(names) == len(areas):
            return [{name_key: n, "area": a} for n, a in zip(names, areas)]
        if areas:
            return [{name_key: None, "area": a} for a in areas]
        return [{name_key: n, "area": None} for n in names]

    def _extract_floors(self, text: str, total_area):
        """各層 {transcript_id, level, area},以及這一頁的面積加總檢查。"""
        lines = text.split("\n")
        index, body = self._region(lines, self._FLOOR_REGION_START, self._FLOOR_REGION_END)
        if index is None:
            return [], None
        levels, areas = [], []
        for line in body:
            levels += [re.sub(r"\s+", "", m) for m in self._FLOOR_LEVEL.findall(line)]
            if not self._TOTAL_AREA_LABEL.search(line):
                areas += self._AREA_VALUE.findall(line)
        if not areas and not levels:
            return [], None
        transcript_id = self._building_title_above(lines, index)
        floors = [
            {"transcript_id": transcript_id, **entry}
            for entry in self._pair(levels, areas, "level")
        ]
        check = None
        values = [self._to_float(a) for a in areas]
        if areas and all(v is not None for v in values):
            total = self._to_float(total_area) if total_area else None
            check = {
                "transcript_id": transcript_id,
                "sum": f"{sum(values):.2f}",
                "total": total_area,
                "matches": None if total is None else abs(sum(values) - total) < 0.015,
            }
        return floors, check

    def _extract_sub_buildings(self, text: str) -> list:
        """附屬建物 {transcript_id, usage, area}。"""
        lines = text.split("\n")
        index, body = self._region(lines, self._SUB_REGION_START, self._SUB_REGION_END)
        if index is None:
            return []
        usages, areas = [], []
        for line in body:
            usages += [re.sub(r"\s+", "", m) for m in self._SUB_USAGE.findall(line)]
            areas += self._AREA_VALUE.findall(line)
        transcript_id = self._building_title_above(lines, index)
        return [
            {"transcript_id": transcript_id, **entry}
            for entry in self._pair(usages, areas, "usage")
        ]

    @staticmethod
    def _to_float(value):
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None

    def _strip_shared_parts(self, text: str) -> str:
        """去掉建物標示部裡每一個共有部分區塊,邊界見 _SHARED_PART_LINE 的說明。"""
        kept = []
        in_block = False
        other_items_seen = 0
        for line in text.split("\n"):
            if self._SHARED_PART_LINE.search(line):
                in_block, other_items_seen = True, 0
                continue
            if in_block:
                if self._PART_HEADING.search(line) or self._OWNERSHIP_ENTRY_LINE.search(line):
                    in_block = False
                elif self._OTHER_ITEMS_LINE.search(line):
                    other_items_seen += 1
                    if other_items_seen >= 2:
                        in_block = False
            if not in_block:
                kept.append(line)
        return "\n".join(kept)

    @staticmethod
    def _drop_lines(text: str, pattern) -> str:
        return "\n".join(line for line in text.split("\n") if not pattern.search(line))

    def _cut_at_other_rights(self, text: str) -> str:
        """截到第一個「他項權利部」標題為止。

        呼叫端傳進來的文字已從所有權部標題開始(或整頁都沒有所有權部標題),
        所以第一個他項權利部標題之後都不屬於所有權部。
        """
        m = self._OTHER_RIGHTS_SECTION.search(text)
        return text[:m.start()] if m else text


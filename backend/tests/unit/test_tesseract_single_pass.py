"""Tesseract 每頁只准辨識一次。

2026-09-03 之前 `_run_tesseract` 跑兩遍:`image_to_string` 取文字、
`image_to_data` 取信心度——同一張圖辨識兩次。而 `image_to_data` 的輸出
本來就含逐字文字,重建即可。

線上容器 4 頁謄本實測:
    兩次呼叫 54.2s  →  單次 27.2s(**省 50%**)
    四頁文字去空白後**逐字相同**

OCR 佔整條管線 31.9%(13.9s/頁),這一刀砍掉其中一半。
"""

import inspect

import pytest

from app.lib.ocr_enhanced import engine_manager as em
from app.lib.ocr_enhanced.engine_manager import _rebuild_text_from_tsv


def tsv(rows):
    """rows = [(block, par, line, text), ...] → image_to_data 的 DICT 形狀"""
    return {
        "block_num": [r[0] for r in rows],
        "par_num": [r[1] for r in rows],
        "line_num": [r[2] for r in rows],
        "text": [r[3] for r in rows],
    }


class TestTextReconstruction:
    def test_words_on_one_line_are_joined_by_space(self):
        assert _rebuild_text_from_tsv(tsv([
            (1, 1, 1, "立合約"), (1, 1, 1, "當事人"),
        ])) == "立合約 當事人"

    def test_different_lines_become_newlines(self):
        assert _rebuild_text_from_tsv(tsv([
            (1, 1, 1, "第一行"),
            (1, 1, 2, "第二行"),
        ])) == "第一行\n第二行"

    def test_block_change_also_breaks_the_line(self):
        """換 block 或 par 都要斷行,只看 line_num 會把兩段黏在一起"""
        assert _rebuild_text_from_tsv(tsv([
            (1, 1, 1, "甲區"),
            (2, 1, 1, "乙區"),
        ])) == "甲區\n乙區"

    @pytest.mark.parametrize("blank", ["", "   ", "\n", "\t"])
    def test_blank_tokens_are_dropped(self, blank):
        """image_to_data 會回傳大量空白列,留著會產生假空行"""
        assert _rebuild_text_from_tsv(tsv([
            (1, 1, 1, "有字"), (1, 1, 1, blank), (1, 1, 1, "還有"),
        ])) == "有字 還有"

    def test_empty_input_returns_empty_string(self):
        assert _rebuild_text_from_tsv(tsv([])) == ""

    def test_all_blank_returns_empty_string(self):
        """整頁空白時要回空字串,不能回 '\\n' 之類的假內容"""
        assert _rebuild_text_from_tsv(tsv([(1, 1, 1, ""), (1, 1, 2, "  ")])) == ""


def _executable_source(func) -> str:
    """取出函式中會執行的部分——剝掉註解與字串常值。

    第一版直接對 inspect.getsource 做字串比對,結果被**本檔自己的解釋性註解**
    咬到(註解裡就寫著 image_to_string)。檢查程式行為的測試不該被註解左右,
    故改以 AST 還原,只留可執行碼。
    """
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    for node in ast.walk(tree):
        # 移除 docstring
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(
                getattr(body[0], "value", None), ast.Constant
            ) and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


class TestOnlyOneOcrCallRemains:
    """有人把 image_to_string 加回來就會在此失敗——那等於把 50% 的時間賠回去。"""

    def test_run_tesseract_does_not_call_image_to_string(self):
        src = _executable_source(em.EngineManager._run_tesseract)
        assert "image_to_string" not in src, (
            "_run_tesseract 又出現 image_to_string——同一張圖會被辨識兩次,"
            "實測代價是 OCR 時間翻倍(27.2s → 54.2s / 4 頁)"
        )

    def test_run_tesseract_calls_image_to_data_exactly_once(self):
        src = _executable_source(em.EngineManager._run_tesseract)
        assert src.count("image_to_data") == 1, (
            f"image_to_data 出現 {src.count('image_to_data')} 次,應為 1 次"
        )

    def test_the_guard_itself_can_fail(self):
        """證明上面兩條不是恆真:一個含兩次呼叫的假函式必須被判定為違規"""
        async def _bad():
            import pytesseract
            text = pytesseract.image_to_string(None)
            data = pytesseract.image_to_data(None)
            return text, data

        src = _executable_source(_bad)
        assert "image_to_string" in src and src.count("image_to_data") == 1

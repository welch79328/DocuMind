"""PaddleOCR 的偵測邊長上限必須維持在實測值。

2026-09-03 於線上以文字層真值實測(每組重複 3 次取中位數):

    設定          p1 推論   p1 CER   p3 推論   p3 CER
    現行(未設)     28.5s   15.5%    28.3s   19.8%
    限邊 960       28.7s   14.4%    27.8s   16.3%

時間在雜訊範圍內,CER 兩頁都降——零時間代價的準確率改善。

同時釘住幾個「看起來多餘、絕對不能刪」的既有參數,它們各自都有實測依據。
"""

import inspect

from app.lib.ocr_enhanced.engine_manager import EngineManager


def _init_source() -> str:
    return inspect.getsource(EngineManager._ensure_paddleocr)


class TestDetectionLimitIsSet:
    def test_limit_side_len_is_960(self):
        src = _init_source()
        assert "text_det_limit_side_len=960" in src, (
            "偵測邊長上限被改動或移除——實測它讓 CER 從 15.5%/19.8% 降到 14.4%/16.3%,"
            "且時間不變。要改請先在有真值的文件上重量。"
        )


class TestMeasuredParametersSurvive:
    """這幾個都有實測依據,刪掉會靜默退步或直接壞掉。"""

    def test_onnxruntime_engine(self):
        """實測快 2.75 倍且輸出逐項相同(54.2s → 19.7s)"""
        assert 'engine="onnxruntime"' in _init_source()

    def test_mkldnn_disabled(self):
        """少了它 paddle 3.x 的 PIR 執行器會拋 NotImplementedError;
        環境變數 FLAGS_use_mkldnn=0 對 3.x 無效,只有建構子參數有效"""
        assert "enable_mkldnn=False" in _init_source()

    def test_textline_orientation_disabled(self):
        """實測開與不開輸出逐項相同,但開啟多花 4 秒(58.2s vs 54.2s)"""
        assert "use_textline_orientation=False" in _init_source()

    def test_doc_unwarping_disabled(self):
        """為速度考量關閉;手機拍攝路徑要開之前須另行實測比較"""
        assert "use_doc_unwarping=False" in _init_source()

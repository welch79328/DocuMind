"""
OCR Engine Manager Module

OCR 引擎管理模組，支援多引擎並行處理與結果融合。
"""

from typing import Literal, Any, Optional
import logging
import numpy as np
import threading
import time
import asyncio
import cv2

from .types import EngineResult, FusionMethod, OCREngineName

logger = logging.getLogger(__name__)


_ocr_gate: Optional["asyncio.Semaphore"] = None
_ocr_gate_limit: int = -1

# PaddleOCR 單例的建構鎖。
#
# 啟動時會在背景執行緒預載模型(preload_paddleocr),而預載還沒完成時
# 第一個請求就可能進來。沒有這把鎖,兩邊都會看到 instance 是 None、各建一份——
# 模型兩份同時在記憶體裡,而單頁 OCR 峰值已達 1141–1778 MB、容器上限 2 GB,
# 必然 OOM。有了鎖,後到的一方等前者建完、直接拿同一份。
_paddleocr_init_lock = threading.Lock()


def preload_paddleocr(lang: str) -> None:
    """啟動時預載 PaddleOCR,消除第一個 OCR 請求的冷啟動(2026-09-21)。

    線上實測(t3.medium):當天第一個 OCR 請求 27.2 秒,之後同類請求 15.0–18.4 秒——
    多出的約 12 秒全是模型載入(log 只在第一筆出現 "Model files already exist")。
    模型本來就是常駐單例,預載只是把載入時間從「第一位使用者」挪到「啟動時」,
    穩態記憶體不變。

    失敗只記 log、不拋出:沒裝 paddle 的環境(本機、測試)照常啟動,
    線上若真的載入失敗,第一個請求會照舊惰性載入並回報真正的錯誤。
    """
    started = time.perf_counter()
    try:
        EngineManager(engines=["paddleocr"], paddleocr_lang=lang)._ensure_paddleocr()
    except Exception as e:
        logger.warning("PaddleOCR 預載失敗,改為首次請求時載入: %s", e)
        return
    logger.info("PaddleOCR 預載完成,耗時 %.1f 秒", time.perf_counter() - started)


def _get_ocr_gate() -> "asyncio.Semaphore":
    """同時執行 OCR 的閘門(行程層級,跨請求共用)。

    **這是記憶體的閘門,不是效能旋鈕。** 單頁 OCR 峰值實測 1141–1778 MB,
    容器可用約 1695 MB——兩頁同時跑必然 OOM。在此之前系統沒有任何機制擋著:
    單 uvicorn worker、無 --limit-concurrency、程式碼無 Semaphore,
    兩個使用者同時上傳就會把 backend 容器打掛(2026-09-03 盤查)。

    刻意延後建立:asyncio.Semaphore 會綁定建立時的事件迴圈,
    在 import 期建立會在某些測試/啟動順序下綁到錯的迴圈。
    """
    global _ocr_gate, _ocr_gate_limit
    from app.config import settings

    limit = max(1, int(settings.OCR_MAX_CONCURRENT))
    if _ocr_gate is None or _ocr_gate_limit != limit:
        _ocr_gate = asyncio.Semaphore(limit)
        _ocr_gate_limit = limit
    return _ocr_gate


# --------------------------------------------------------------------------- #
# OCR 引擎 qwen:Bedrock Qwen3 VL 讀字(transcript-qwen-read,2026-11-16)
# --------------------------------------------------------------------------- #

# 逐字沿用 2026-11-09 評估 C2 版
# (~/jgb-archive/transcript-photo-fullparse-eval-20261109/run_qwen_grounded.py PROMPT)。
# 改了就不是評估量過的那個組合,改前要重量。
QWEN_OCR_PROMPT = (
    "這是一頁台灣不動產登記謄本的照片或掃描影像。請找出頁面上印的每一段文字（一個文字片段＝同一行中連續、沒有大空白隔開的字），"
    "依閱讀順序逐段輸出，每段一行 JSON：{\"bbox_2d\": [x1, y1, x2, y2], \"text\": \"...\"}，座標用 0–1000 的相對座標（相對整張圖）。\n"
    "- 同一行左右兩欄是兩段，各自輸出。\n- 文字照原文逐字抄，冒號、星號、括號、「(空白)」照抄，不補字、不改寫。\n"
    "- 浮水印底紋、印章、QR code 不要輸出。\n只輸出 JSON 行，不要任何說明。"
)
QWEN_OCR_MAX_TOKENS = 8000

# Qwen 讀字沒有分數。有讀到段落時固定回 0.9:這是 PaddleOCR 在謄本上通常回的值,
# 讓下游 needs_review(信心度 < OCR_QUALITY_THRESHOLD)的判法不變。
# 這不是「讀對的機率」——OCR 行分數本來就不能當信心度
# (專案記憶 ocr-line-score-not-confidence:讀對讀錯分數重疊、字形換字照樣高分)。
QWEN_OCR_CONFIDENCE = 0.9

_qwen_gate: Optional["asyncio.Semaphore"] = None
_qwen_gate_limit: int = -1
_qwen_gate_loop: Optional["asyncio.AbstractEventLoop"] = None


class QwenOcrError(Exception):
    """qwen 讀字失敗。**訊息只有類別**,不含影像、模型回覆或 AWS 回應內文。

    extract_text_multi_engine 會把失敗的例外字串印出來,所以從源頭就不帶內文。
    """

    def __init__(self, category: str):
        self.category = category
        super().__init__(f"qwen 讀字失敗:{category}")


def _get_qwen_gate() -> "asyncio.Semaphore":
    """qwen 讀字的併發上限(行程層級,跨請求共用;惰性建立)。

    **跟 _get_ocr_gate 刻意分開。** OCR 閘門是 PaddleOCR 的記憶體閘門(上限 1);
    qwen 在遠端算,本機只等 HTTP,不吃容器記憶體。共用那道閘門會讓一份 12 頁的謄本
    逐頁排隊(每頁中位 39.2 秒),超過 JGB 等 DocuMind 的 480 秒(plan R7)。
    這道閘門擋的是同時打 Bedrock 的請求數(預設 4,QWEN_OCR_MAX_CONCURRENT)。

    上限改了、或換了事件迴圈(測試各自 asyncio.run)就重建,
    避免 Semaphore 綁在已結束的迴圈上。
    """
    global _qwen_gate, _qwen_gate_limit, _qwen_gate_loop
    from app.config import settings

    limit = max(1, int(settings.QWEN_OCR_MAX_CONCURRENT))
    loop = asyncio.get_running_loop()
    if _qwen_gate is None or _qwen_gate_limit != limit or _qwen_gate_loop is not loop:
        _qwen_gate = asyncio.Semaphore(limit)
        _qwen_gate_limit = limit
        _qwen_gate_loop = loop
    return _qwen_gate


def _encode_qwen_image(image: np.ndarray) -> str:
    """BGR/灰階/BGRA 陣列 → RGB → 長邊 ≤2000、品質 92 的 JPEG → data URI。

    JPEG 的縮圖與品質階梯重用直讀的 prepare_direct_read_image(只 import,不改那支檔),
    中間用 BMP 交接:不壓縮、編碼最快,讀回來就是同一張 RGB。
    """
    import base64
    import io

    from PIL import Image

    from app.lib.multi_type_ocr.direct_read_processor import prepare_direct_read_image

    if image.ndim == 2:
        rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    elif image.shape[2] == 4:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
    elif image.shape[2] == 3:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        raise QwenOcrError("invalid_image")

    buffer = io.BytesIO()
    Image.fromarray(rgb).save(buffer, format="BMP")
    jpeg = prepare_direct_read_image(buffer.getvalue())
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")


def build_qwen_engine_result(
    lines: list, layout: str, processing_time_ms: int
) -> EngineResult:
    """解析後的行框 → 引擎結果。0 段時 text=""、信心度 0.0;否則固定 QWEN_OCR_CONFIDENCE。"""
    from .qwen_layout import build_full_text

    if not lines:
        return {
            "engine": "qwen",
            "text": "",
            "confidence": 0.0,
            "processing_time_ms": processing_time_ms,
            "lines": [],
        }
    return {
        "engine": "qwen",
        "text": build_full_text(lines, layout),
        "confidence": QWEN_OCR_CONFIDENCE,
        "processing_time_ms": processing_time_ms,
        "lines": lines,
    }


def is_qwen_only(engines) -> bool:
    """引擎清單只有 qwen(不跑本機 OCR)。"""
    return set(engines or []) == {"qwen"}


class EngineManager:
    """
    OCR 引擎管理器

    管理多個 OCR 引擎，支援並行處理與結果融合。
    """

    # 單例模式：確保模型常駐記憶體
    _paddleocr_instance = None

    def __init__(
        self,
        engines: Optional[list[OCREngineName]] = None,
        parallel: bool = True,
        fusion_method: FusionMethod = "best",
        paddleocr_lang: str = "chinese_cht"
    ):
        """
        初始化引擎管理器

        Args:
            engines: 引擎列表
            parallel: 是否並行處理(預設 True;2026-08-24 於 2 vCPU 實測省 13.6%,
                      辨識結果不變。代價為峰值記憶體是兩引擎之和,見 settings.OCR_PARALLEL_ENGINES)
            fusion_method: 融合方法 (best/weighted/vote)
            paddleocr_lang: PaddleOCR 語言(繁中預設 chinese_cht)
        """
        self.engines: list[OCREngineName] = engines or ["paddleocr", "tesseract"]
        self.parallel = parallel
        self.fusion_method = fusion_method
        self.paddleocr_lang = paddleocr_lang
        # 註:PaddleOCR 改為首次使用時惰性載入(見 _ensure_paddleocr),
        # 避免未安裝 paddleocr 的環境在建構時即失敗

    def _ensure_paddleocr(self):
        """惰性初始化 PaddleOCR(單例);啟動時預載,或首次辨識時載入"""
        if EngineManager._paddleocr_instance is not None:
            return EngineManager._paddleocr_instance
        with _paddleocr_init_lock:
            # 鎖內再檢查一次:等鎖期間,預載執行緒可能已經建好了
            if EngineManager._paddleocr_instance is not None:
                return EngineManager._paddleocr_instance
            try:
                from paddleocr import PaddleOCR

                # ⚠️ enable_mkldnn=False 不可拿掉 ⚠️
                #
                # paddle 3.x 的新執行器(PIR)與 oneDNN 之間有功能缺口,推論時拋
                #   NotImplementedError: ConvertPirAttribute2RuntimeAttribute
                #     not support [pir::ArrayAttribute<pir::DoubleAttribute>]
                #     (at .../new_executor/instruction/onednn/onednn_instruction.cc)
                #
                # 環境變數 FLAGS_use_mkldnn=0 對 3.x **無效**(2.x 才吃那個旗標),
                # 只有建構子參數有效。2026-08-24 於 x86_64 Linux 實測確認。
                EngineManager._paddleocr_instance = PaddleOCR(
                    lang=self.paddleocr_lang,
                    # ONNX Runtime 取代 paddle 執行器。2026-08-24 同一份謄本實測:
                    #   paddle 執行器  54.2s  72 行  信心度 0.927
                    #   ONNX Runtime   19.7s  72 行  信心度 0.927   ← 快 2.75 倍,輸出逐項相同
                    # 模型本身沒換(仍是 PP-OCRv6_medium),換的只是執行引擎。
                    engine="onnxruntime",
                    # enable_mkldnn 僅對 paddle 執行器有意義;保留是為了萬一
                    # 日後切回 paddle 時不會再踩一次 oneDNN 的坑(見下方說明)
                    enable_mkldnn=False,
                    # 前處理模組預設開啟會拖慢且對已掃描的謄本無益;
                    # 手機拍攝路徑若要開 use_doc_unwarping,請另行實測比較
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    # use_textline_orientation 對謄本是純白工:2026-08-24 實測
                    # 同一份謄本開與不開的輸出**逐項相同**(72 行、平均信心度 0.927),
                    # 但開啟多花 4 秒(58.2s vs 54.2s)。謄本是掃描件,文字方向本就是正的。
                    # 舊版的 use_angle_cls=True 是慣性沿用,量過之後確認不需要。
                    use_textline_orientation=False,
                    # 偵測階段的輸入邊長上限。2026-09-03 於線上以文字層真值實測
                    # (每組設定重複 3 次,取中位數):
                    #
                    #   設定          p1 推論   p1 CER   p3 推論   p3 CER
                    #   現行(未設)     28.5s   15.5%    28.3s   19.8%
                    #   限邊 960       28.7s   14.4%    27.8s   16.3%
                    #
                    # **時間在雜訊範圍內(±10%),CER 兩頁都降**——零時間代價的準確率改善。
                    # 首次單跑量到「快 5 秒」是冷啟動假象,重複三次後消失。
                    #
                    # 樣本只有兩頁,若日後在更多文件上發現退步,這是第一個該回退的參數。
                    text_det_limit_side_len=960,
                )
            except Exception as e:
                raise RuntimeError(f"PaddleOCR 初始化失敗: {e}")
        return EngineManager._paddleocr_instance

    async def extract_text_multi_engine(
        self,
        image: np.ndarray,
        page_number: int = 1
    ) -> tuple[str, float, list[EngineResult]]:
        """
        使用多引擎提取文字

        Args:
            image: 圖像 numpy 陣列
            page_number: 頁碼（用於 PDF）

        Returns:
            (融合後文字, 融合後信心度, 各引擎結果)
        """
        # 本機引擎(吃容器記憶體,受 OCR 閘門約束)
        local_engines = [e for e in ("paddleocr", "tesseract") if e in self.engines]
        use_qwen = "qwen" in self.engines

        # 並行執行所有引擎（使用 asyncio.gather）
        #
        # ⚠️ self.parallel 只是「意願」,不是「許可」。並行的峰值記憶體是兩引擎
        # 之和而非最大值,機器小就會 OOM——2026-08-24 在 3.7GB 的線上機器上實測
        # 觸發過(見 memory_guard 的說明)。故實際是否並行由記憶體當下的餘裕決定。
        # (只算本機引擎:qwen 在遠端算,不佔這份記憶體。)
        from app.config import settings
        from .memory_guard import parallel_is_safe

        run_parallel = (
            self.parallel
            and len(local_engines) > 1
            and parallel_is_safe(settings.OCR_PARALLEL_MIN_AVAILABLE_MB)
        )

        def _local_task(engine: str):
            return self._run_paddleocr(image) if engine == "paddleocr" else self._run_tesseract(image)

        # ⚠️ 閘門在此,不在呼叫端。記憶體是被**引擎執行**吃掉的,不是被頁面迴圈;
        # 把閘門放這裡,無論是同一份文件的多頁併發、還是不同使用者的併發請求,
        # 都受同一個上限約束。放在 API 層只擋得住其中一種。
        async def _run_local() -> list:
            if not local_engines:
                return []
            async with _get_ocr_gate():
                if run_parallel:
                    # 並行模式：同時執行
                    return list(await asyncio.gather(
                        *(_local_task(e) for e in local_engines), return_exceptions=True
                    ))
                # 順序模式：逐個執行
                out = []
                for engine in local_engines:
                    try:
                        out.append(await _local_task(engine))
                    except Exception as e:
                        out.append(e)
                return out

        # qwen 不進 OCR 閘門(那是 PaddleOCR 的記憶體閘門),改受自己的併發上限約束。
        # 引擎清單只有 qwen 時,整段完全不碰 OCR 閘門。
        async def _run_qwen_gated():
            try:
                async with _get_qwen_gate():
                    return await self._run_qwen(image)
            except Exception as e:
                return e

        try:
            if use_qwen and local_engines:
                local_results, qwen_result = await asyncio.gather(_run_local(), _run_qwen_gated())
                results = [*local_results, qwen_result]
            elif use_qwen:
                results = [await _run_qwen_gated()]
            else:
                results = await _run_local()

            # 過濾失敗結果
            valid_results: list[EngineResult] = []
            for result in results:
                if isinstance(result, Exception):
                    # 記錄錯誤但繼續使用其他引擎結果
                    # (qwen 的例外是 QwenOcrError,字串只有類別)
                    print(f"引擎執行失敗: {result}")
                else:
                    valid_results.append(result)

            if not valid_results:
                # 所有引擎都失敗。qwen 失敗**不退回** PaddleOCR/tesseract(plan R6):
                # 退回就又要把 PaddleOCR 載入容器。
                return "", 0.0, []

            # 融合結果
            fused_text, fused_confidence = self._fuse_results(valid_results)

            return fused_text, fused_confidence, valid_results

        except Exception as e:
            print(f"多引擎處理失敗: {e}")
            return "", 0.0, []

    async def _run_paddleocr(self, image: np.ndarray) -> EngineResult:
        """
        執行 PaddleOCR

        Task 5.1 實作

        Args:
            image: 圖像 numpy 陣列（BGR 或 RGB）

        Returns:
            EngineResult with standardized output

        Raises:
            RuntimeError: PaddleOCR 執行失敗
        """
        # 惰性載入 PaddleOCR(首次辨識時)
        self._ensure_paddleocr()

        # 將同步 OCR 呼叫轉為非同步
        def _ocr_sync():
            start_time = time.time()

            # 確保圖像是 RGB 格式（PaddleOCR 需要 RGB）
            if len(image.shape) == 2:
                # 灰階 → RGB
                img_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 3:
                # BGR → RGB
                img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                img_rgb = image

            # 執行 OCR
            # paddleocr 3.x 的 API 是 predict();2.x 的 ocr(img, cls=True) 已移除
            result = EngineManager._paddleocr_instance.predict(img_rgb)
            processing_time_ms = int((time.time() - start_time) * 1000)

            # 3.x 回傳 list[dict],文字與信心度分別在 rec_texts / rec_scores
            # (2.x 是 list[list[[bbox, (text, conf)]]],結構完全不同)
            text_lines = []
            confidences = []
            # 行框(比例座標):rec_polys 每行外接矩形 ÷ 送進 predict() 的影像寬高;
            # rec_polys 缺或與 rec_texts 數量不符 → None(不猜)
            img_h, img_w = img_rgb.shape[:2]
            lines = []
            lines_ok = True

            for page in (result or []):
                texts = page.get("rec_texts") or []
                scores = page.get("rec_scores") or []
                polys = page.get("rec_polys")
                if polys is None or len(polys) != len(texts) or not img_w or not img_h:
                    lines_ok = False
                else:
                    for t, poly in zip(texts, polys):
                        arr = np.asarray(poly, dtype=float).reshape(-1, 2)
                        lines.append({"text": t, "box": [
                            round(float(arr[:, 0].min()) / img_w, 4),
                            round(float(arr[:, 1].min()) / img_h, 4),
                            round(float(arr[:, 0].max()) / img_w, 4),
                            round(float(arr[:, 1].max()) / img_h, 4),
                        ]})
                for text_content, confidence in zip(texts, scores):
                    text_lines.append(text_content)
                    confidences.append(float(confidence))

            # 合併文字（逐行）
            text = "\n".join(text_lines)

            # 計算平均信心度
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return text, avg_confidence, processing_time_ms, (lines if lines_ok else None)

        # 使用 asyncio.to_thread 執行同步函數
        text, confidence, processing_time_ms, lines = await asyncio.to_thread(_ocr_sync)

        return {
            "engine": "paddleocr",
            "text": text,
            "confidence": self._standardize_confidence("paddleocr", confidence),
            "processing_time_ms": processing_time_ms,
            "lines": lines,
        }

    async def _run_tesseract(self, image: np.ndarray) -> EngineResult:
        """
        執行 Tesseract

        Task 5.2 實作

        Args:
            image: 圖像 numpy 陣列

        Returns:
            EngineResult with standardized output

        Raises:
            RuntimeError: Tesseract 執行失敗
        """
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError:
            raise RuntimeError("pytesseract 未安裝，請執行: pip install pytesseract")

        # 將同步 OCR 呼叫轉為非同步
        def _ocr_sync():
            start_time = time.time()

            # 轉換為 PIL Image（pytesseract 接受 numpy 或 PIL）
            # PSM 6: 假設單一文字區塊（適合謄本）
            config = "--psm 6"

            # 提取文字
            text = pytesseract.image_to_string(
                image,
                lang="chi_tra",
                config=config
            )

            # ⚠️ 不要把這兩次呼叫合併成一次 image_to_data。已經試過並否決(2026-09-03)。
            #
            # 動機是對的:同一張圖辨識兩遍,實測合併後 4 頁謄本從 54.2s 降到 27.2s,
            # **省 50%**,而 OCR 佔整條管線 31.9%。
            #
            # 否決的理由:image_to_data 重建不出 image_to_string 的輸出。
            # image_to_string 的空白是**照影像上的像素間距排出來的**,不是詞間加空白:
            #
            #   image_to_string  '十地登記第一類肉本(地號金六3)       中給 吧'
            #   逐字接空白       '十 地 登記 第 一 類 肉 本 (地 號 金 六 3) 中 給 吧'
            #
            # 試過五種接合規則(空白接/直接接 × 尾端換行與否 × 行距),
            # **完全相同的頁數是 0/4**。要複製就得重寫 Tesseract 的版面排版邏輯。
            #
            # 代價是實測到的:換成重建版後,同一份謄本的欄位抽取信心度
            # p1 0.700→0.640、p4 0.320→0.160——**送進 LLM 的文字變了**。
            #
            # 當時的保真度實驗以 "".join(t.split()) 比對,結論是「去空白後逐字相同」。
            # 那個比對把要驗證的差異先抹掉了:模型收到的是原字串,不是去空白後的。
            #
            # 要重試的前提:先有任務 3.3 的準確率基準線,能量出「文字變動」的實際代價。
            # 在那之前,慢兩倍但輸出不變,優於快兩倍但輸出未知。
            #
            # 提取信心度（使用 image_to_data 獲取詳細資訊）
            try:
                data = pytesseract.image_to_data(
                    image,
                    lang="chi_tra",
                    config=config,
                    output_type=Output.DICT
                )

                # 計算平均信心度（過濾無效值）
                confidences = [
                    float(conf) for conf in data['conf']
                    if conf != -1 and conf != '-1'
                ]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

                # Tesseract 信心度範圍是 0-100，需要標準化到 0-1
                avg_confidence = avg_confidence / 100.0

            except Exception as e:
                # 如果無法獲取信心度，使用預設值
                print(f"無法獲取 Tesseract 信心度: {e}")
                avg_confidence = 0.5  # 預設中等信心度

            processing_time_ms = int((time.time() - start_time) * 1000)

            return text, avg_confidence, processing_time_ms

        # 使用 asyncio.to_thread 執行同步函數
        text, confidence, processing_time_ms = await asyncio.to_thread(_ocr_sync)

        return {
            "engine": "tesseract",
            "text": text,
            "confidence": self._standardize_confidence("tesseract", confidence),
            "processing_time_ms": processing_time_ms
        }

    async def _run_qwen(self, image: np.ndarray) -> EngineResult:
        """
        OCR 引擎 qwen:整頁送 Bedrock Qwen3 VL,逐段抄錄並附 0–1000 座標。

        交出跟 PaddleOCR 一樣的引擎結果(text、confidence、lines 比例行框),
        下游(25 欄、清單、全文解析、v2 照片 position)不必分辨是誰讀的。

        - 個資閘門:走 create_provider("bedrock"),LLM_CLOUD_ENABLED=false 時在建立
          Provider 就被擋下,影像不編碼、不外送。
        - 失敗(Bedrock 錯誤、設定被擋、影像過大、逾時、解析出 0 段)一律拋
          QwenOcrError(訊息只有類別),由 extract_text_multi_engine 濾掉 → 該頁
          ("", 0.0, [])。**不退回** PaddleOCR/tesseract(plan R6)。
        - log 只記類別,不記影像、模型回覆或 AWS 回應內文。
        """
        from app.config import settings
        from app.lib.llm_service import providers
        from app.lib.llm_service.call_log import STAGE_OCR_READ, classify_llm_error, llm_stage

        from .qwen_layout import parse_qwen_lines

        start_time = time.time()
        try:
            provider = providers.create_provider("bedrock")
            # 整頁讀字回應長,一頁正常 30–40 秒;flex 用預設的 20 秒會每頁都白等再重送
            provider.flex_timeout_seconds = providers.BEDROCK_TIMEOUT_SECONDS
            image_data = await asyncio.to_thread(_encode_qwen_image, image)
            with llm_stage(STAGE_OCR_READ):
                response = await provider.call(
                    QWEN_OCR_PROMPT,
                    image_data=image_data,
                    max_tokens=QWEN_OCR_MAX_TOKENS,
                    temperature=0.0,
                )
            lines = parse_qwen_lines(response)
            if not lines:
                raise QwenOcrError("no_segments")
            result = build_qwen_engine_result(
                lines,
                settings.QWEN_OCR_TEXT_LAYOUT,
                int((time.time() - start_time) * 1000),
            )
        except QwenOcrError as exc:
            category = exc.category
        except providers.BedrockCallError as exc:
            category = exc.category
        except ValueError:
            category = "cloud_disabled" if not settings.LLM_CLOUD_ENABLED else "invalid_request"
        except Exception as exc:  # 逾時等:只看類別,不看訊息
            category = classify_llm_error(exc)
        else:
            return result

        logger.warning("qwen 讀字失敗,該頁降級為空結果:%s", category)
        raise QwenOcrError(category) from None

    def fuse(self, results: list[EngineResult]) -> tuple[str, float]:
        """
        以設定的融合策略融合各引擎結果(公開入口)

        供已取得候選的呼叫端重用融合邏輯,避免為了拿融合文字而重跑引擎。
        行為完全委派給既有 _fuse_results,既有策略不受影響。

        Args:
            results: 各引擎結果列表

        Returns:
            (融合後文字, 融合後信心度)
        """
        return self._fuse_results(results)

    def _fuse_results(self, results: list[EngineResult]) -> tuple[str, float]:
        """
        融合多個引擎結果

        Task 5.3 實作（融合策略）

        Args:
            results: 各引擎結果列表

        Returns:
            (融合後文字, 融合後信心度)

        Fusion Strategies:
            - "best": 選擇信心度最高的結果（適合高品質圖片）
            - "smart": 綜合評分選擇（推薦，適應不同品質）
            - "vote": 選擇字符數最多的結果（適合低品質圖片）
            - "weighted": 加權平均（Phase 2）
        """
        if not results:
            return "", 0.0

        if self.fusion_method == "best":
            # Phase 1: 選擇信心度最高的結果
            best_result = max(results, key=lambda r: r["confidence"])
            return best_result["text"], best_result["confidence"]

        elif self.fusion_method == "smart":
            # 智能策略：綜合評分
            # 計算每個結果的綜合分數
            scored_results = []

            for result in results:
                # 因子 1: 信心度（0-1）
                confidence_score = result["confidence"]

                # 因子 2: 字符數（歸一化）
                max_chars = max(len(r["text"]) for r in results)
                char_score = len(result["text"]) / max_chars if max_chars > 0 else 0

                # 因子 3: 關鍵字檢測（謄本專用）
                keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']
                keyword_matches = sum(1 for kw in keywords if kw in result["text"])
                keyword_score = keyword_matches / len(keywords)

                # 綜合評分：
                # - 信心度高但字少 → 可能是 PaddleOCR 在低品質圖片上過度自信
                # - 字多但信心度低 → 可能是 Tesseract 在低品質圖片上表現更好
                # 權重調整：字符數 40%, 關鍵字 35%, 信心度 25%
                total_score = (
                    char_score * 0.40 +
                    keyword_score * 0.35 +
                    confidence_score * 0.25
                )

                scored_results.append({
                    "result": result,
                    "score": total_score,
                    "char_score": char_score,
                    "keyword_score": keyword_score,
                    "confidence_score": confidence_score
                })

            # 選擇綜合分數最高的結果
            best_scored = max(scored_results, key=lambda x: x["score"])
            best_result = best_scored["result"]

            return best_result["text"], best_result["confidence"]

        elif self.fusion_method == "vote":
            # Phase 2: 投票機制（字符級投票）
            # 簡化版本：選擇最長的結果（通常 Tesseract 在低品質圖片上更完整）
            best_result = max(results, key=lambda r: len(r["text"]))
            avg_confidence = sum(r["confidence"] for r in results) / len(results)

            return best_result["text"], avg_confidence

        elif self.fusion_method == "weighted":
            # Phase 2: 加權平均（根據信心度）
            total_confidence = sum(r["confidence"] for r in results)
            if total_confidence == 0:
                # 所有信心度都是 0，使用第一個結果
                return results[0]["text"], 0.0

            # 按信心度加權文字長度（簡化版本）
            # 完整實作需要逐字符對齊
            best_result = max(results, key=lambda r: r["confidence"])
            weighted_confidence = total_confidence / len(results)

            return best_result["text"], weighted_confidence

        else:
            # 預設：使用 smart 策略
            # 暫存當前策略
            original_method = self.fusion_method
            self.fusion_method = "smart"
            result = self._fuse_results(results)
            # 恢復原策略
            self.fusion_method = original_method
            return result

    def _standardize_confidence(
        self,
        engine: OCREngineName,
        raw_confidence: Any
    ) -> float:
        """
        標準化信心度

        Task 5.3 實作（信心度標準化）

        Args:
            engine: 引擎名稱
            raw_confidence: 原始信心度

        Returns:
            標準化後的信心度 (0-1)

        Notes:
            - PaddleOCR: 已經是 0-1 範圍
            - Tesseract: 0-100 範圍，已在 _run_tesseract 中轉換
            - Textract: 0-100 範圍（Phase 2）
        """
        # 確保是浮點數
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            return 0.0

        # 根據引擎調整
        if engine == "paddleocr":
            # PaddleOCR 已經是 0-1 範圍
            return max(0.0, min(1.0, confidence))

        elif engine == "tesseract":
            # Tesseract 已在 _run_tesseract 中轉換為 0-1
            return max(0.0, min(1.0, confidence))

        elif engine == "textract":
            # AWS Textract 通常是 0-100 範圍
            # Phase 2 實作時啟用
            if confidence > 1.0:
                confidence = confidence / 100.0
            return max(0.0, min(1.0, confidence))

        else:
            # 未知引擎，假設已經是 0-1 範圍
            return max(0.0, min(1.0, confidence))

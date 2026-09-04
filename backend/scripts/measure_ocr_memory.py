"""量測單頁 OCR 的記憶體峰值——用來校準 OCR_MAX_RENDER_PIXELS(PDF)與 OCR_MAX_IMAGE_PIXELS(影像)。

## 為什麼需要這支

`app/config.py` 的 `OCR_MAX_RENDER_PIXELS` 註解要求「調高前先用內文頁重測」。
換機器、加記憶體、或想提高解析度時都會觸發那句話。這支就是安全的重測方式。

## 2026-08-24 的量測結果(線上 2 vCPU / 3.7GB,backend 容器上限 2048MB)

可用空間 = 容器上限 2048MB − 應用程式本身 489MB ≈ 1559MB

    像素上限   解析度    峰值 RSS    行數   信心度    結果
    3.0M      176 DPI   >1626 MB    —      —       ✗ 中止
    2.0M      144 DPI   >1503 MB    —      —       ✗ 中止
    1.5M      125 DPI   >1454 MB    —      —       ✗ 中止
    1.25M     114 DPI    1453 MB    33    0.9837   ✓ 餘裕僅 106MB
    1.0M      102 DPI    1323 MB    33    0.9826   ✓ 餘裕 236MB  ← 現行設定

兩件校準時務必記得的事:

1. **一定要用內文頁,不能用封面頁。** 記憶體主要由文字密度決定,不是像素數
   ——光載入引擎就佔 701MB,辨識階段疊上去的量隨文字區塊數成長。
   此常數先後錯過兩次(4M、2M),兩次都是拿只有 5 行的封面頁校準的。
2. **提高解析度換不到品質。** 102 DPI 與 114 DPI 在同一頁上行數相同、
   信心度差在雜訊範圍內,而 0.98 已高於謄本基準的 0.927。

## ⚠️ 不要改用 resource.RLIMIT_AS

2026-08-24 實測:設 1200MB 後 ONNX Runtime 連載入都失敗
(`failed to map segment from shared object`),還會導致無法開執行緒。
RLIMIT_AS 限的是**虛擬位址空間**,而 ONNX 保留的位址空間遠大於實際用量。
要看的是 RSS(實際佔用),所以這裡用輪詢 /proc/self/status 的看門狗。

真正的天花板是容器的 cgroup mem_limit;看門狗是在撞到它**之前**先乾淨退出,
讓容器不必被殺。2026-08-24 有一次沒有這道保護,把整台機器拖垮 12 小時。

## 「峰值 RSS」在 2026-09-04 之前是假的

原本結果行印的 `峰值RSS=` 其實是 `current_rss_mb()` 的**當下值**——OCR 跑完之後
才讀的那一刻。看門狗執行緒每 0.5 秒讀一次 RSS,但只拿來比對門檻,從不保留最大值。

影響上面那張表:標 ✗ 的三列是看門狗攔下時的讀數,**那些是真的峰值**;
標 ✓ 的兩列(1453MB、1323MB)是結束時的殘值,**很可能低估真實峰值**,
因此「1.0M 留 236MB 餘裕」的餘裕可能比帳面小。要重估請重跑一次本腳本,
現在的 `[結果]` 行會印出真正的執行期最大值。

## 兩種輸入的量測路徑不同,不要交叉比較

    PDF   fitz 渲染 → PaddleOCR 單引擎(不經 DocumentProcessor)
    影像  DocumentProcessor.process() → 生產同一條路徑,含 EngineManager 全部引擎

PDF 分支是為了校準 OCR_MAX_RENDER_PIXELS 而寫的,刻意只跑單引擎以隔離變因;
影像分支是為了校準 OCR_MAX_IMAGE_PIXELS,走的是使用者上傳時真正會跑的東西。
兩者的數字不可互相比較,只能各自跟自己的另一次執行比。

## 用法(在 backend 容器內執行)

    docker compose exec -T backend \\
        timeout --signal=KILL 600 \\
        python scripts/measure_ocr_memory.py data/contracts/<檔名>.pdf --page 2

    docker compose exec -T backend \\
        timeout --signal=KILL 600 \\
        python scripts/measure_ocr_memory.py /tmp/big.jpg

    --page N                 PDF 專用:要量的頁碼(選內文頁,不要封面)
    --max-pixels N           PDF 專用:覆寫 settings.OCR_MAX_RENDER_PIXELS
    --max-image-pixels N     影像專用:覆寫 settings.OCR_MAX_IMAGE_PIXELS(0=停用縮圖)
    --watchdog-mb N          RSS 看門狗門檻(預設 1400,須低於容器上限扣掉應用程式本身)

    兩個覆寫參數都**只改本行程的 settings**,不影響線上部署值。
"""

import argparse
import io
import os
import statistics
import sys
import threading
import time
from pathlib import Path

# 允許直接以 `python scripts/measure_ocr_memory.py` 執行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def current_rss_mb() -> int:
    """讀 /proc/self/status 的 VmRSS——實際佔用的實體記憶體(MB)。"""
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 0


# 看門狗執行緒觀察到的最大 RSS。**這是本腳本唯一有資格叫「峰值」的數字**——
# current_rss_mb() 在任何單一時點回傳的都只是當下值,OCR 結束後才讀到的更是殘值。
_peak_rss_mb = 0


def peak_rss_mb() -> int:
    """看門狗啟動後觀察到的最大 RSS(MB)。看門狗未啟動時退回當下值。"""
    return max(_peak_rss_mb, current_rss_mb())


def start_rss_watchdog(threshold_mb: int) -> None:
    """RSS 超過門檻就主動了結,不要等容器被 OOM 殺掉;同時記錄期間的最大值。

    取樣間隔 0.5 秒是既有值,沿用。這個間隔可能漏掉極短暫的尖峰,
    所以 peak_rss_mb() 是「觀察到的最大值」,不是「數學上的最大值」——
    要拿它做安全邊界判斷時,請留一段餘裕。
    """

    def _watch():
        global _peak_rss_mb
        while True:
            rss = current_rss_mb()
            if rss > _peak_rss_mb:
                _peak_rss_mb = rss
            if rss > threshold_mb:
                print(f"[中止] RSS {rss} MB 超過看門狗門檻 {threshold_mb} MB，"
                      f"主動退出——容器與主機未受影響", flush=True)
                os._exit(3)
            time.sleep(0.5)

    threading.Thread(target=_watch, daemon=True).start()
    print(f"[安全] RSS 看門狗啟動，門檻 {threshold_mb} MB", flush=True)


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def _measure_pdf(args, settings) -> None:
    """PDF 分支:fitz 渲染 + PaddleOCR 單引擎。校準 OCR_MAX_RENDER_PIXELS 用。

    刻意只跑單引擎、且不經 DocumentProcessor——這支原本就是為了隔離「渲染解析度」
    這一個變因而寫的。要量生產路徑請餵影像(見 _measure_image)。
    """
    import fitz
    import numpy as np
    from PIL import Image

    from app.services.analyze_service import _render_scale

    # 覆寫上限時直接改 settings，讓 _render_scale 用同一套邏輯——
    # 刻意不在此處複製渲染數學，否則量到的就不是生產環境實際會跑的東西。
    if args.max_pixels is not None:
        settings.OCR_MAX_RENDER_PIXELS = args.max_pixels

    doc = fitz.open(args.input)
    page = doc[args.page - 1]
    scale = _render_scale(page.rect)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    png = pix.tobytes("png")
    doc.close()

    img = Image.open(io.BytesIO(png)).convert("RGB")
    arr = np.array(img)
    print(f"[渲染] 上限 {settings.OCR_MAX_RENDER_PIXELS/1e6:.2f}M  "
          f"{img.size[0]}x{img.size[1]} = {img.size[0]*img.size[1]/1e6:.2f}M 像素  "
          f"{round(scale*72)} DPI  RSS {current_rss_mb()} MB", flush=True)

    from paddleocr import PaddleOCR

    ocr = PaddleOCR(
        lang=settings.OCR_PADDLEOCR_LANG,
        engine="onnxruntime",
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    print(f"[載入] 引擎就緒  RSS {current_rss_mb()} MB", flush=True)

    t0 = time.time()
    results = ocr.predict(arr)
    elapsed = time.time() - t0

    texts, scores = [], []
    for r in results:
        payload = r.json.get("res", r.json) if hasattr(r, "json") else {}
        texts += list(payload.get("rec_texts", []) or [])
        scores += list(payload.get("rec_scores", []) or [])
    confidence = statistics.fmean(scores) if scores else 0.0

    print(f"[結果] 行數={len(texts)}  平均信心度={confidence:.4f}  "
          f"耗時={elapsed:.1f}s  執行期最大RSS={peak_rss_mb()} MB", flush=True)
    for text, score in list(zip(texts, scores))[:5]:
        print(f"        {score:.3f}  {text[:40]}")


def _measure_image(args, settings) -> None:
    """影像分支:走 DocumentProcessor.process(),與使用者上傳時完全同一條路徑。

    校準 OCR_MAX_IMAGE_PIXELS 用。刻意不自己複製縮圖數學,也不自己呼叫 OCR 引擎——
    那樣量到的就不是生產環境會跑的東西(這正是 2026-09-04 之前這支腳本
    無法用於影像路徑的原因:它只走 fitz + _render_scale)。

    enable_llm=False:LLM 在遠端算,本機只是等 HTTP,對記憶體量測是純雜訊,
    還會產生費用。
    """
    import asyncio

    from app.lib.multi_type_ocr.processor_factory import ProcessorFactory

    if args.max_image_pixels is not None:
        settings.OCR_MAX_IMAGE_PIXELS = args.max_image_pixels

    path = Path(args.input)
    contents = path.read_bytes()

    from PIL import Image

    with Image.open(io.BytesIO(contents)) as probe:
        src_w, src_h = probe.size
    print(f"[輸入] {path.name}  {src_w}x{src_h} = {src_w*src_h/1e6:.2f}M 像素  "
          f"{len(contents)/1e6:.2f} MB  上限 {settings.OCR_MAX_IMAGE_PIXELS/1e6:.2f}M  "
          f"RSS {current_rss_mb()} MB", flush=True)

    processor = ProcessorFactory.get_processor("transcript")
    print(f"[載入] 處理器就緒  RSS {current_rss_mb()} MB", flush=True)

    t0 = time.time()
    result = asyncio.run(processor.process(
        file_contents=contents,
        filename=path.name,
        page_number=1,
        total_pages=1,
        enable_llm=False,
    ))
    elapsed = time.time() - t0

    ocr_raw = result.get("ocr_raw") or {}
    text = ocr_raw.get("text") or ""
    confidence = ocr_raw.get("confidence") or 0.0
    lines = [ln for ln in text.splitlines() if ln.strip()]

    print(f"[結果] 行數={len(lines)}  平均信心度={confidence:.4f}  "
          f"耗時={elapsed:.1f}s  執行期最大RSS={peak_rss_mb()} MB", flush=True)
    for line in lines[:5]:
        print(f"        {line[:40]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", help="PDF 或影像路徑;依副檔名分派")
    ap.add_argument("--page", type=int, default=1,
                    help="PDF 專用:頁碼(1 起算);選內文頁")
    ap.add_argument("--max-pixels", type=int, default=None,
                    help="PDF 專用:覆寫 settings.OCR_MAX_RENDER_PIXELS")
    ap.add_argument("--max-image-pixels", type=int, default=None,
                    help="影像專用:覆寫 settings.OCR_MAX_IMAGE_PIXELS(0=停用縮圖)")
    ap.add_argument("--watchdog-mb", type=int, default=1400)
    args = ap.parse_args()

    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    start_rss_watchdog(args.watchdog_mb)

    from app.config import settings

    suffix = Path(args.input).suffix.lower()
    if suffix == ".pdf":
        _measure_pdf(args, settings)
    elif suffix in IMAGE_SUFFIXES:
        _measure_image(args, settings)
    else:
        # 大聲失敗:認不出的副檔名不要猜,否則量到的是什麼都不知道
        raise SystemExit(
            f"認不出的輸入格式:{suffix or '(無副檔名)'}。"
            f"支援 .pdf 或 {', '.join(sorted(IMAGE_SUFFIXES))}"
        )


if __name__ == "__main__":
    main()

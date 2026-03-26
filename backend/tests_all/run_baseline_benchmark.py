"""
Baseline Performance Benchmark Script

執行基準效能測試,記錄現有 OCR 系統的處理時間、準確率、信心度。

使用方式:
    python tests/run_baseline_benchmark.py

輸出:
    tests/benchmarks/baseline_results.json

需求:
    - OCR 工具已安裝 (paddleocr 或 pytesseract)
    - 測試文件存在於 data/ 目錄
    - Ground truth 已建立於 tests/fixtures/ground_truth.json
"""

import json
import time
import asyncio
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any
import difflib


def calculate_accuracy(text1: str, text2: str) -> float:
    """
    計算兩個文字的相似度 (使用 SequenceMatcher)

    Args:
        text1: OCR 結果文字
        text2: Ground truth 文字

    Returns:
        相似度分數 (0.0 - 1.0)
    """
    matcher = difflib.SequenceMatcher(None, text1, text2)
    return matcher.ratio()


def get_system_info() -> Dict[str, Any]:
    """獲取系統環境資訊"""
    info = {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "platform_release": platform.release(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }

    # 嘗試獲取 CPU 資訊
    try:
        if platform.system() == "Darwin":  # macOS
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True
            )
            info["cpu"] = result.stdout.strip()
        elif platform.system() == "Linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        info["cpu"] = line.split(":")[1].strip()
                        break
    except Exception:
        info["cpu"] = "Unknown"

    # 獲取 OCR 引擎版本
    ocr_versions = {}

    try:
        import pytesseract
        ocr_versions["tesseract"] = pytesseract.get_tesseract_version().public
    except (ImportError, Exception):
        ocr_versions["tesseract"] = "Not installed"

    try:
        from paddleocr import PaddleOCR
        ocr_versions["paddleocr"] = "Installed"  # PaddleOCR 沒有簡單的版本獲取方法
    except ImportError:
        ocr_versions["paddleocr"] = "Not installed"

    info["ocr_engines"] = ocr_versions

    return info


async def benchmark_document(
    file_path: str,
    ground_truth_text: str,
    ocr_service: str
) -> Dict[str, Any]:
    """
    對單個文件執行基準測試

    Args:
        file_path: 文件路徑
        ground_truth_text: Ground truth 文字
        ocr_service: OCR 服務名稱 (paddleocr, pytesseract, textract)

    Returns:
        測試結果字典
    """
    from app.lib.ocr_service import extract_text_from_document

    start_time = time.time()

    try:
        # 執行 OCR
        ocr_text, page_count = await extract_text_from_document(file_path)
        processing_time = time.time() - start_time

        # 計算準確率
        accuracy = calculate_accuracy(ocr_text, ground_truth_text)

        # 計算平均信心度 (目前 OCR 服務不返回信心度,使用 N/A)
        confidence = "N/A - Current OCR service doesn't return confidence scores"

        result = {
            "file": file_path,
            "ocr_service": ocr_service,
            "processing_time_seconds": round(processing_time, 3),
            "processing_time_ms": int(processing_time * 1000),
            "page_count": page_count,
            "accuracy": round(accuracy, 4),
            "confidence": confidence,
            "text_length": len(ocr_text),
            "ground_truth_length": len(ground_truth_text),
            "status": "success",
            "error": None
        }

    except Exception as e:
        processing_time = time.time() - start_time
        result = {
            "file": file_path,
            "ocr_service": ocr_service,
            "processing_time_seconds": round(processing_time, 3),
            "processing_time_ms": int(processing_time * 1000),
            "page_count": 0,
            "accuracy": 0.0,
            "confidence": "N/A",
            "text_length": 0,
            "ground_truth_length": len(ground_truth_text),
            "status": "failed",
            "error": str(e)
        }

    return result


async def run_baseline_benchmark():
    """執行完整的基準測試"""
    print("=== OCR Baseline Performance Benchmark ===\n")

    # 1. 獲取系統資訊
    print("1. Collecting system information...")
    system_info = get_system_info()
    print(f"   Platform: {system_info['platform']} {system_info['platform_release']}")
    print(f"   CPU: {system_info['cpu']}")
    print(f"   Python: {system_info['python_version']}")
    print(f"   OCR Engines: {system_info['ocr_engines']}\n")

    # 2. 載入 Ground Truth
    print("2. Loading ground truth data...")
    ground_truth_path = Path(__file__).parent / "fixtures" / "ground_truth.json"

    if not ground_truth_path.exists():
        print("   ERROR: ground_truth.json not found!")
        print("   Please run task 0.1 first to create ground truth data.")
        return

    with open(ground_truth_path, 'r', encoding='utf-8') as f:
        ground_truth = json.load(f)

    print("   Ground truth loaded successfully.\n")

    # 3. 獲取當前 OCR 服務設定
    from app.config import settings
    ocr_service = settings.OCR_SERVICE
    print(f"3. Current OCR service: {ocr_service}\n")

    # 4. 執行測試
    print("4. Running benchmark tests...\n")

    results = []

    # 測試建物謄本.jpg
    print("   Testing 建物謄本.jpg...")
    jpg_ground_truth = ground_truth["建物謄本.jpg"]["full_text"]
    jpg_result = await benchmark_document(
        "file:///app/data/建物謄本.jpg",
        jpg_ground_truth,
        ocr_service
    )
    results.append(jpg_result)
    print(f"     Status: {jpg_result['status']}")
    if jpg_result['status'] == 'success':
        print(f"     Processing time: {jpg_result['processing_time_seconds']}s")
        print(f"     Accuracy: {jpg_result['accuracy']:.2%}")
    else:
        print(f"     Error: {jpg_result['error']}")
    print()

    # 測試建物土地謄本-杭州南路一段.pdf
    print("   Testing 建物土地謄本-杭州南路一段.pdf...")
    pdf_ground_truth = ground_truth["建物土地謄本-杭州南路一段.pdf"]
    pdf_full_text = pdf_ground_truth.get("full_text", "[待標註]")

    if pdf_full_text == "[待標註]" or "待標註" in pdf_full_text:
        print("     SKIPPED: Ground truth for PDF not yet annotated")
        pdf_result = {
            "file": "file:///app/data/建物土地謄本-杭州南路一段.pdf",
            "ocr_service": ocr_service,
            "status": "skipped",
            "error": "Ground truth not yet annotated",
            "note": "Complete PDF annotation in task 0.1 to enable this test"
        }
    else:
        pdf_result = await benchmark_document(
            "file:///app/data/建物土地謄本-杭州南路一段.pdf",
            pdf_full_text,
            ocr_service
        )
        print(f"     Status: {pdf_result['status']}")
        if pdf_result['status'] == 'success':
            print(f"     Processing time: {pdf_result['processing_time_seconds']}s")
            print(f"     Accuracy: {pdf_result['accuracy']:.2%}")
            print(f"     Pages: {pdf_result['page_count']}")
        else:
            print(f"     Error: {pdf_result['error']}")

    results.append(pdf_result)
    print()

    # 5. 儲存結果
    print("5. Saving results...")

    benchmark_results = {
        "benchmark_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "system_info": system_info,
        "ocr_service": ocr_service,
        "results": results,
        "summary": {
            "total_tests": len(results),
            "successful_tests": sum(1 for r in results if r["status"] == "success"),
            "failed_tests": sum(1 for r in results if r["status"] == "failed"),
            "skipped_tests": sum(1 for r in results if r["status"] == "skipped"),
            "average_accuracy": sum(r.get("accuracy", 0) for r in results if r["status"] == "success") / max(sum(1 for r in results if r["status"] == "success"), 1),
            "total_processing_time_seconds": sum(r.get("processing_time_seconds", 0) for r in results if r["status"] == "success")
        }
    }

    # 建立 benchmarks 目錄
    benchmark_dir = Path(__file__).parent / "benchmarks"
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    # 儲存結果
    output_path = benchmark_dir / "baseline_results.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(benchmark_results, f, ensure_ascii=False, indent=2)

    print(f"   Results saved to: {output_path}\n")

    # 6. 顯示摘要
    print("=== Benchmark Summary ===")
    print(f"Total tests: {benchmark_results['summary']['total_tests']}")
    print(f"Successful: {benchmark_results['summary']['successful_tests']}")
    print(f"Failed: {benchmark_results['summary']['failed_tests']}")
    print(f"Skipped: {benchmark_results['summary']['skipped_tests']}")
    print(f"Average accuracy: {benchmark_results['summary']['average_accuracy']:.2%}")
    print(f"Total processing time: {benchmark_results['summary']['total_processing_time_seconds']:.2f}s")
    print()

    print("✅ Baseline benchmark completed!")


if __name__ == "__main__":
    asyncio.run(run_baseline_benchmark())

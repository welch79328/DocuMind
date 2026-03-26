"""
Test Baseline Benchmark Script and Results
"""

import json
import pytest
from pathlib import Path


def test_baseline_results_file_exists():
    """驗證基準結果文件存在"""
    baseline_path = Path(__file__).parent / "benchmarks" / "baseline_results.json"
    assert baseline_path.exists(), "baseline_results.json 文件不存在"


def test_baseline_results_valid_json():
    """驗證基準結果是有效的 JSON"""
    baseline_path = Path(__file__).parent / "benchmarks" / "baseline_results.json"

    with open(baseline_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert isinstance(data, dict), "baseline_results 應該是 dict 格式"


def test_baseline_results_structure():
    """驗證基準結果結構完整"""
    baseline_path = Path(__file__).parent / "benchmarks" / "baseline_results.json"

    with open(baseline_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 驗證必要欄位存在
    assert "benchmark_date" in data
    assert "system_info" in data
    assert "ocr_service" in data
    assert "results" in data
    assert "summary" in data

    # 驗證 system_info 結構
    system_info = data["system_info"]
    assert "platform" in system_info
    assert "python_version" in system_info
    assert "ocr_engines" in system_info

    # 驗證 summary 結構
    summary = data["summary"]
    assert "total_tests" in summary
    assert "successful_tests" in summary
    assert "failed_tests" in summary
    assert "average_accuracy" in summary


def test_baseline_results_contains_test_files():
    """驗證基準結果包含測試文件"""
    baseline_path = Path(__file__).parent / "benchmarks" / "baseline_results.json"

    with open(baseline_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = data["results"]
    assert len(results) > 0, "results 應包含測試結果"

    # 驗證包含必要的測試文件
    file_names = [r.get("file", "") for r in results]
    assert any("建物謄本.jpg" in f for f in file_names), "應包含 建物謄本.jpg 的測試結果"
    assert any("建物土地謄本-杭州南路一段.pdf" in f for f in file_names), "應包含 PDF 的測試結果"


def test_benchmark_script_exists():
    """驗證基準測試腳本存在"""
    script_path = Path(__file__).parent / "run_baseline_benchmark.py"
    assert script_path.exists(), "run_baseline_benchmark.py 腳本不存在"


def test_benchmark_script_executable():
    """驗證基準測試腳本可讀取"""
    script_path = Path(__file__).parent / "run_baseline_benchmark.py"

    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 驗證腳本包含必要的函數
    assert "def run_baseline_benchmark()" in content
    assert "def calculate_accuracy(" in content
    assert "def get_system_info()" in content
    assert "def benchmark_document(" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

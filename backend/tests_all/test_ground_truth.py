"""
Test Ground Truth Data Loading and Validation
"""

import json
import pytest
from pathlib import Path


def test_ground_truth_file_exists():
    """驗證 ground truth 文件存在"""
    ground_truth_path = Path(__file__).parent / "fixtures" / "ground_truth.json"
    assert ground_truth_path.exists(), "ground_truth.json 文件不存在"


def test_ground_truth_valid_json():
    """驗證 ground truth 是有效的 JSON"""
    ground_truth_path = Path(__file__).parent / "fixtures" / "ground_truth.json"

    with open(ground_truth_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert isinstance(data, dict), "ground_truth 應該是 dict 格式"


def test_ground_truth_contains_required_documents():
    """驗證包含必要的測試文件"""
    ground_truth_path = Path(__file__).parent / "fixtures" / "ground_truth.json"

    with open(ground_truth_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert "建物謄本.jpg" in data, "缺少建物謄本.jpg的標註"
    assert "建物土地謄本-杭州南路一段.pdf" in data, "缺少 PDF 文件的標註"


def test_ground_truth_jpg_structure():
    """驗證 JPG 文件的 ground truth 結構完整"""
    ground_truth_path = Path(__file__).parent / "fixtures" / "ground_truth.json"

    with open(ground_truth_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    jpg_data = data["建物謄本.jpg"]

    # 驗證必要欄位存在
    assert "document_type" in jpg_data
    assert "full_text" in jpg_data
    assert "key_fields" in jpg_data
    assert "metadata" in jpg_data

    # 驗證 document_type
    assert jpg_data["document_type"] == "building_transcript"

    # 驗證 full_text 不為空
    assert len(jpg_data["full_text"]) > 0

    # 驗證 key_fields 結構
    key_fields = jpg_data["key_fields"]
    assert "land_number" in key_fields
    assert "area" in key_fields
    assert "construction_date" in key_fields
    assert "registration_date" in key_fields


def test_ground_truth_key_fields_format():
    """驗證關鍵欄位格式正確"""
    ground_truth_path = Path(__file__).parent / "fixtures" / "ground_truth.json"

    with open(ground_truth_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    key_fields = data["建物謄本.jpg"]["key_fields"]

    # 驗證地號格式 (XXXX-XXXX)
    land_number = key_fields["land_number"]
    assert "-" in land_number, "地號應包含 '-' 分隔符"
    parts = land_number.split("-")
    assert len(parts) == 2, "地號格式應為 XXXX-XXXX"
    assert parts[0].isdigit(), "地號第一部分應為數字"
    assert parts[1].isdigit(), "地號第二部分應為數字"

    # 驗證面積為數字
    area = key_fields["area"]
    assert isinstance(area, (int, float)), "面積應為數字類型"
    assert area > 0, "面積應大於 0"

    # 驗證日期格式
    registration_date = key_fields["registration_date"]
    assert "民國" in registration_date, "登記日期應包含'民國'"
    assert "年" in registration_date and "月" in registration_date and "日" in registration_date


def test_ground_truth_pdf_structure():
    """驗證 PDF 文件的 ground truth 結構"""
    ground_truth_path = Path(__file__).parent / "fixtures" / "ground_truth.json"

    with open(ground_truth_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pdf_data = data["建物土地謄本-杭州南路一段.pdf"]

    # 驗證必要欄位存在
    assert "document_type" in pdf_data
    assert "pages" in pdf_data
    assert "metadata" in pdf_data

    # 驗證頁數
    assert pdf_data["pages"] == 3, "PDF 應有 3 頁"

    # 驗證 metadata
    assert pdf_data["metadata"]["format"] == "pdf"


def test_ground_truth_annotation_metadata():
    """驗證標註元數據存在"""
    ground_truth_path = Path(__file__).parent / "fixtures" / "ground_truth.json"

    with open(ground_truth_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert "annotation_metadata" in data, "缺少標註元數據"

    metadata = data["annotation_metadata"]
    assert "created_at" in metadata
    assert "annotator" in metadata
    assert "method" in metadata
    assert "confidence" in metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

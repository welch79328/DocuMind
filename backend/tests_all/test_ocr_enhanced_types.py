"""
測試 OCR Enhanced 模組的型別定義

驗證所有核心型別和 Protocol 定義正確。
"""

import pytest
from typing import get_type_hints
from app.lib.ocr_enhanced.types import (
    OCRResult,
    ProcessingMetadata,
    EngineResult,
    QualityMetrics,
    ExtractedFields,
    PreprocessingStrategy,
    OCREngine,
)


def test_ocr_result_type_exists():
    """測試 OCRResult TypedDict 存在且有正確的欄位"""
    hints = get_type_hints(OCRResult)

    # 驗證必要欄位存在
    assert "text" in hints
    assert "page_count" in hints
    assert "quality_score" in hints
    assert "confidence" in hints
    assert "metadata" in hints

    # 驗證欄位型別
    assert hints["text"] == str
    assert hints["page_count"] == int
    assert hints["quality_score"] == float
    assert hints["confidence"] == float
    assert hints["metadata"] == dict


def test_processing_metadata_type_exists():
    """測試 ProcessingMetadata TypedDict 存在且有正確的欄位"""
    hints = get_type_hints(ProcessingMetadata)

    # 驗證必要欄位存在
    assert "doc_type" in hints
    assert "preprocessing_applied" in hints
    assert "preprocessing_strategy" in hints
    assert "ocr_engines_used" in hints
    assert "processing_time_ms" in hints
    assert "retry_count" in hints
    assert "watermark_removed" in hints


def test_engine_result_type_exists():
    """測試 EngineResult TypedDict 存在且有正確的欄位"""
    hints = get_type_hints(EngineResult)

    # 驗證必要欄位存在
    assert "engine" in hints
    assert "text" in hints
    assert "confidence" in hints
    assert "processing_time_ms" in hints

    # 驗證欄位型別
    assert hints["engine"] == str
    assert hints["text"] == str
    assert hints["confidence"] == float
    assert hints["processing_time_ms"] == int


def test_quality_metrics_type_exists():
    """測試 QualityMetrics TypedDict 存在且有正確的欄位"""
    hints = get_type_hints(QualityMetrics)

    # 驗證必要欄位存在
    assert "confidence_score" in hints
    assert "character_density" in hints
    assert "field_match_rate" in hints
    assert "anomaly_rate" in hints
    assert "overall_score" in hints

    # 所有欄位應該是 float 型別
    for field in ["confidence_score", "character_density", "field_match_rate",
                  "anomaly_rate", "overall_score"]:
        assert hints[field] == float


def test_extracted_fields_type_exists():
    """測試 ExtractedFields TypedDict 存在且有正確的欄位"""
    from typing import get_args, get_origin

    hints = get_type_hints(ExtractedFields)

    # 驗證必要欄位存在
    assert "land_number" in hints
    assert "area" in hints
    assert "owner" in hints
    assert "unified_id" in hints
    assert "title_number" in hints
    assert "register_date" in hints
    assert "validation_status" in hints


def test_preprocessing_strategy_protocol_exists():
    """測試 PreprocessingStrategy Protocol 存在且有正確的方法"""
    import inspect

    # 驗證 Protocol 有 apply 方法
    assert hasattr(PreprocessingStrategy, 'apply')

    # 檢查方法簽名
    apply_method = getattr(PreprocessingStrategy, 'apply')
    assert callable(apply_method) or inspect.isfunction(apply_method)


def test_ocr_engine_protocol_exists():
    """測試 OCREngine Protocol 存在且有正確的方法"""
    import inspect

    # 驗證 Protocol 有 extract_text 方法
    assert hasattr(OCREngine, 'extract_text')

    # 檢查方法簽名
    extract_text_method = getattr(OCREngine, 'extract_text')
    assert callable(extract_text_method) or inspect.isfunction(extract_text_method)


def test_types_can_be_imported():
    """測試所有型別可以從主模組匯入"""
    from app.lib.ocr_enhanced import types

    # 驗證所有型別都可匯入
    assert hasattr(types, 'OCRResult')
    assert hasattr(types, 'ProcessingMetadata')
    assert hasattr(types, 'EngineResult')
    assert hasattr(types, 'QualityMetrics')
    assert hasattr(types, 'ExtractedFields')
    assert hasattr(types, 'PreprocessingStrategy')
    assert hasattr(types, 'OCREngine')


def test_ocr_result_can_be_instantiated():
    """測試 OCRResult 可以被實例化"""
    result: OCRResult = {
        "text": "測試文字",
        "page_count": 1,
        "quality_score": 85.5,
        "confidence": 0.92,
        "metadata": {"test": "data"}
    }

    assert result["text"] == "測試文字"
    assert result["page_count"] == 1
    assert result["quality_score"] == 85.5


def test_engine_result_can_be_instantiated():
    """測試 EngineResult 可以被實例化"""
    result: EngineResult = {
        "engine": "paddleocr",
        "text": "測試文字",
        "confidence": 0.95,
        "processing_time_ms": 1500
    }

    assert result["engine"] == "paddleocr"
    assert result["processing_time_ms"] == 1500


def test_quality_metrics_can_be_instantiated():
    """測試 QualityMetrics 可以被實例化"""
    metrics: QualityMetrics = {
        "confidence_score": 92.0,
        "character_density": 0.78,
        "field_match_rate": 0.95,
        "anomaly_rate": 0.02,
        "overall_score": 85.5
    }

    assert metrics["overall_score"] == 85.5
    assert metrics["field_match_rate"] == 0.95

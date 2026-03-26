"""
Test OCR Enhanced Module Structure

驗證 ocr_enhanced 模組的目錄結構和匯入功能
"""

import pytest
from pathlib import Path


def test_ocr_enhanced_directory_exists():
    """驗證 ocr_enhanced 目錄存在"""
    ocr_enhanced_dir = Path(__file__).parent.parent / "backend" / "app" / "lib" / "ocr_enhanced"
    assert ocr_enhanced_dir.exists(), "ocr_enhanced 目錄不存在"
    assert ocr_enhanced_dir.is_dir(), "ocr_enhanced 應該是目錄"


def test_all_module_files_exist():
    """驗證所有必要的模組檔案存在"""
    ocr_enhanced_dir = Path(__file__).parent.parent / "backend" / "app" / "lib" / "ocr_enhanced"

    required_files = [
        "__init__.py",
        "document_classifier.py",
        "preprocessor.py",
        "engine_manager.py",
        "postprocessor.py",
        "quality_assessor.py",
        "field_extractor.py",
        "config.py"
    ]

    for filename in required_files:
        file_path = ocr_enhanced_dir / filename
        assert file_path.exists(), f"{filename} 不存在"
        assert file_path.is_file(), f"{filename} 應該是檔案"


def test_module_files_not_empty():
    """驗證模組檔案不為空"""
    ocr_enhanced_dir = Path(__file__).parent.parent / "backend" / "app" / "lib" / "ocr_enhanced"

    module_files = [
        "__init__.py",
        "document_classifier.py",
        "preprocessor.py",
        "engine_manager.py",
        "postprocessor.py",
        "quality_assessor.py",
        "field_extractor.py",
        "config.py"
    ]

    for filename in module_files:
        file_path = ocr_enhanced_dir / filename
        content = file_path.read_text(encoding='utf-8')
        assert len(content) > 0, f"{filename} 不應該為空"
        assert '"""' in content, f"{filename} 應該包含 docstring"


def test_init_defines_exports():
    """驗證 __init__.py 定義了匯出介面"""
    init_file = Path(__file__).parent.parent / "backend" / "app" / "lib" / "ocr_enhanced" / "__init__.py"
    content = init_file.read_text(encoding='utf-8')

    # 應該包含 __all__ 定義
    assert "__all__" in content, "__init__.py 應該定義 __all__"

    # 應該匯出 EnhancedOCRPipeline
    assert "EnhancedOCRPipeline" in content, "__init__.py 應該匯出 EnhancedOCRPipeline"


def test_can_import_module():
    """驗證可以匯入 ocr_enhanced 模組"""
    try:
        import app.lib.ocr_enhanced
        assert True
    except ImportError as e:
        pytest.fail(f"無法匯入 ocr_enhanced 模組: {e}")


def test_can_import_enhanced_ocr_pipeline():
    """驗證可以匯入 EnhancedOCRPipeline"""
    try:
        from app.lib.ocr_enhanced import EnhancedOCRPipeline
        assert EnhancedOCRPipeline is not None
    except ImportError as e:
        pytest.fail(f"無法匯入 EnhancedOCRPipeline: {e}")


def test_module_has_docstring():
    """驗證每個模組都有 docstring"""
    ocr_enhanced_dir = Path(__file__).parent.parent / "backend" / "app" / "lib" / "ocr_enhanced"

    module_files = [
        "document_classifier.py",
        "preprocessor.py",
        "engine_manager.py",
        "postprocessor.py",
        "quality_assessor.py",
        "field_extractor.py",
        "config.py"
    ]

    for filename in module_files:
        file_path = ocr_enhanced_dir / filename
        content = file_path.read_text(encoding='utf-8')

        # 檢查是否以 docstring 開頭（忽略註解）
        lines = [line for line in content.split('\n') if line.strip() and not line.strip().startswith('#')]
        if lines:
            assert lines[0].strip().startswith('"""') or lines[0].strip().startswith("'''"), \
                f"{filename} 應該以模組 docstring 開頭"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

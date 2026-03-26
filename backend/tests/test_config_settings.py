"""
測試配置設定

驗證 Settings 類別包含所有 OCR 增強相關環境變數，以及配置類別定義正確。
"""

import pytest
from app.config import Settings
from app.lib.ocr_enhanced.config import PreprocessConfig, EngineConfig, QualityConfig


class TestSettingsOCREnhancement:
    """測試 Settings 中的 OCR 增強環境變數"""

    def test_settings_has_ocr_enhanced_mode(self):
        """測試 OCR_ENHANCED_MODE 環境變數存在"""
        settings = Settings()
        assert hasattr(settings, 'OCR_ENHANCED_MODE')
        assert isinstance(settings.OCR_ENHANCED_MODE, bool)

    def test_settings_has_ocr_multi_engine(self):
        """測試 OCR_MULTI_ENGINE 環境變數存在"""
        settings = Settings()
        assert hasattr(settings, 'OCR_MULTI_ENGINE')
        assert isinstance(settings.OCR_MULTI_ENGINE, bool)

    def test_settings_has_ocr_engines_list(self):
        """測試 OCR_ENGINES 環境變數存在"""
        settings = Settings()
        assert hasattr(settings, 'OCR_ENGINES')
        assert isinstance(settings.OCR_ENGINES, list)
        # 預設值應包含 paddleocr
        assert "paddleocr" in settings.OCR_ENGINES

    def test_settings_has_ocr_quality_threshold(self):
        """測試 OCR_QUALITY_THRESHOLD 環境變數存在"""
        settings = Settings()
        assert hasattr(settings, 'OCR_QUALITY_THRESHOLD')
        assert isinstance(settings.OCR_QUALITY_THRESHOLD, (int, float))
        # 預設值應在合理範圍
        assert 0 <= settings.OCR_QUALITY_THRESHOLD <= 100

    def test_settings_has_ocr_max_retries(self):
        """測試 OCR_MAX_RETRIES 環境變數存在"""
        settings = Settings()
        assert hasattr(settings, 'OCR_MAX_RETRIES')
        assert isinstance(settings.OCR_MAX_RETRIES, int)
        assert settings.OCR_MAX_RETRIES >= 0

    def test_settings_has_ocr_watermark_removal(self):
        """測試 OCR_WATERMARK_REMOVAL 環境變數存在"""
        settings = Settings()
        assert hasattr(settings, 'OCR_WATERMARK_REMOVAL')
        assert isinstance(settings.OCR_WATERMARK_REMOVAL, bool)

    def test_settings_has_ocr_postprocessing(self):
        """測試 OCR_POSTPROCESSING 環境變數存在"""
        settings = Settings()
        assert hasattr(settings, 'OCR_POSTPROCESSING')
        assert isinstance(settings.OCR_POSTPROCESSING, bool)

    def test_settings_has_ocr_pdf_dpi(self):
        """測試 OCR_PDF_DPI 環境變數存在"""
        settings = Settings()
        assert hasattr(settings, 'OCR_PDF_DPI')
        assert isinstance(settings.OCR_PDF_DPI, int)
        assert settings.OCR_PDF_DPI > 0

    def test_settings_has_ocr_binarization_method(self):
        """測試 OCR_BINARIZATION_METHOD 環境變數存在"""
        settings = Settings()
        assert hasattr(settings, 'OCR_BINARIZATION_METHOD')
        assert isinstance(settings.OCR_BINARIZATION_METHOD, str)
        assert settings.OCR_BINARIZATION_METHOD in ["gaussian", "mean", "sauvola"]

    def test_settings_has_ocr_fusion_method(self):
        """測試 OCR_FUSION_METHOD 環境變數存在"""
        settings = Settings()
        assert hasattr(settings, 'OCR_FUSION_METHOD')
        assert isinstance(settings.OCR_FUSION_METHOD, str)
        assert settings.OCR_FUSION_METHOD in ["best", "weighted", "vote"]

    def test_settings_has_ocr_paddleocr_lang(self):
        """測試 OCR_PADDLEOCR_LANG 環境變數存在"""
        settings = Settings()
        assert hasattr(settings, 'OCR_PADDLEOCR_LANG')
        assert isinstance(settings.OCR_PADDLEOCR_LANG, str)

    def test_settings_has_ocr_tesseract_lang(self):
        """測試 OCR_TESSERACT_LANG 環境變數存在"""
        settings = Settings()
        assert hasattr(settings, 'OCR_TESSERACT_LANG')
        assert isinstance(settings.OCR_TESSERACT_LANG, str)

    def test_settings_has_at_least_10_ocr_vars(self):
        """測試至少有 10 個 OCR 相關環境變數"""
        settings = Settings()
        ocr_vars = [attr for attr in dir(settings) if attr.startswith('OCR_')]
        assert len(ocr_vars) >= 10, f"只有 {len(ocr_vars)} 個 OCR 環境變數，需要至少 10 個"


class TestPreprocessConfig:
    """測試 PreprocessConfig dataclass"""

    def test_preprocess_config_exists(self):
        """測試 PreprocessConfig 類別存在"""
        config = PreprocessConfig()
        assert config is not None

    def test_preprocess_config_has_watermark_removal(self):
        """測試包含 enable_watermark_removal 欄位"""
        config = PreprocessConfig()
        assert hasattr(config, 'enable_watermark_removal')
        assert isinstance(config.enable_watermark_removal, bool)

    def test_preprocess_config_has_binarization(self):
        """測試包含 enable_binarization 欄位"""
        config = PreprocessConfig()
        assert hasattr(config, 'enable_binarization')
        assert isinstance(config.enable_binarization, bool)

    def test_preprocess_config_has_denoising(self):
        """測試包含 enable_denoising 欄位"""
        config = PreprocessConfig()
        assert hasattr(config, 'enable_denoising')
        assert isinstance(config.enable_denoising, bool)

    def test_preprocess_config_has_binarization_method(self):
        """測試包含 binarization_method 欄位"""
        config = PreprocessConfig()
        assert hasattr(config, 'binarization_method')
        assert config.binarization_method in ["gaussian", "mean", "sauvola"]

    def test_preprocess_config_has_target_dpi(self):
        """測試包含 target_dpi 欄位"""
        config = PreprocessConfig()
        assert hasattr(config, 'target_dpi')
        assert isinstance(config.target_dpi, int)
        assert config.target_dpi > 0

    def test_preprocess_config_has_hsv_thresholds(self):
        """測試包含 HSV 閾值欄位"""
        config = PreprocessConfig()
        assert hasattr(config, 'hsv_lower')
        assert hasattr(config, 'hsv_upper1')
        assert hasattr(config, 'hsv_upper2')
        assert isinstance(config.hsv_lower, tuple)
        assert len(config.hsv_lower) == 3

    def test_preprocess_config_custom_values(self):
        """測試可以自訂配置值"""
        config = PreprocessConfig(
            enable_watermark_removal=False,
            target_dpi=2000
        )
        assert config.enable_watermark_removal is False
        assert config.target_dpi == 2000


class TestEngineConfig:
    """測試 EngineConfig dataclass"""

    def test_engine_config_exists(self):
        """測試 EngineConfig 類別存在"""
        config = EngineConfig()
        assert config is not None

    def test_engine_config_has_engines_list(self):
        """測試包含 engines 欄位"""
        config = EngineConfig()
        assert hasattr(config, 'engines')
        assert isinstance(config.engines, list)

    def test_engine_config_default_engines(self):
        """測試預設引擎列表"""
        config = EngineConfig()
        assert "paddleocr" in config.engines

    def test_engine_config_has_parallel(self):
        """測試包含 parallel 欄位"""
        config = EngineConfig()
        assert hasattr(config, 'parallel')
        assert isinstance(config.parallel, bool)

    def test_engine_config_has_fusion_method(self):
        """測試包含 fusion_method 欄位"""
        config = EngineConfig()
        assert hasattr(config, 'fusion_method')
        assert config.fusion_method in ["best", "weighted", "vote"]

    def test_engine_config_has_paddleocr_lang(self):
        """測試包含 paddleocr_lang 欄位"""
        config = EngineConfig()
        assert hasattr(config, 'paddleocr_lang')
        assert isinstance(config.paddleocr_lang, str)

    def test_engine_config_has_tesseract_lang(self):
        """測試包含 tesseract_lang 欄位"""
        config = EngineConfig()
        assert hasattr(config, 'tesseract_lang')
        assert isinstance(config.tesseract_lang, str)


class TestQualityConfig:
    """測試 QualityConfig dataclass"""

    def test_quality_config_exists(self):
        """測試 QualityConfig 類別存在"""
        config = QualityConfig()
        assert config is not None

    def test_quality_config_has_threshold(self):
        """測試包含 quality_threshold 欄位"""
        config = QualityConfig()
        assert hasattr(config, 'quality_threshold')
        assert isinstance(config.quality_threshold, (int, float))
        assert 0 <= config.quality_threshold <= 100

    def test_quality_config_has_max_retries(self):
        """測試包含 max_retries 欄位"""
        config = QualityConfig()
        assert hasattr(config, 'max_retries')
        assert isinstance(config.max_retries, int)
        assert config.max_retries >= 0

    def test_quality_config_has_weights(self):
        """測試包含權重欄位"""
        config = QualityConfig()
        assert hasattr(config, 'confidence_weight')
        assert hasattr(config, 'density_weight')
        assert hasattr(config, 'field_match_weight')
        assert hasattr(config, 'anomaly_penalty')

    def test_quality_config_weights_sum_reasonable(self):
        """測試權重總和合理"""
        config = QualityConfig()
        total_weight = (
            config.confidence_weight +
            config.density_weight +
            config.field_match_weight +
            config.anomaly_penalty
        )
        # 總和應接近 1.0
        assert 0.9 <= total_weight <= 1.1


class TestConfigIntegration:
    """測試配置整合"""

    def test_can_import_all_configs(self):
        """測試可以匯入所有配置類別"""
        from app.lib.ocr_enhanced.config import PreprocessConfig, EngineConfig, QualityConfig
        assert PreprocessConfig is not None
        assert EngineConfig is not None
        assert QualityConfig is not None

    def test_settings_and_config_alignment(self):
        """測試 Settings 環境變數與 Config 類別對齊"""
        settings = Settings()

        # 預處理相關
        assert hasattr(settings, 'OCR_WATERMARK_REMOVAL')
        assert hasattr(settings, 'OCR_BINARIZATION_METHOD')

        # 引擎相關
        assert hasattr(settings, 'OCR_ENGINES')
        assert hasattr(settings, 'OCR_FUSION_METHOD')

        # 品質相關
        assert hasattr(settings, 'OCR_QUALITY_THRESHOLD')
        assert hasattr(settings, 'OCR_MAX_RETRIES')

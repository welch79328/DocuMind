"""
測試配置驗證邏輯

驗證 validate_config() 函數正確檢查配置參數的有效性。
"""

import pytest
from app.lib.ocr_enhanced.config import (
    PreprocessConfig,
    EngineConfig,
    QualityConfig,
    validate_config,
    validate_preprocess_config,
    validate_engine_config,
    validate_quality_config
)


class TestValidateQualityThreshold:
    """測試品質閾值驗證"""

    def test_quality_threshold_valid_range(self):
        """測試有效範圍內的品質閾值"""
        # 有效值應該通過驗證
        validate_quality_config(QualityConfig(quality_threshold=0.0))
        validate_quality_config(QualityConfig(quality_threshold=50.0))
        validate_quality_config(QualityConfig(quality_threshold=100.0))

    def test_quality_threshold_below_zero(self):
        """測試品質閾值小於 0"""
        with pytest.raises(ValueError) as exc_info:
            validate_quality_config(QualityConfig(quality_threshold=-1.0))
        assert "quality_threshold" in str(exc_info.value).lower()
        assert "0" in str(exc_info.value)
        assert "100" in str(exc_info.value)

    def test_quality_threshold_above_100(self):
        """測試品質閾值大於 100"""
        with pytest.raises(ValueError) as exc_info:
            validate_quality_config(QualityConfig(quality_threshold=101.0))
        assert "quality_threshold" in str(exc_info.value).lower()
        assert "0" in str(exc_info.value)
        assert "100" in str(exc_info.value)


class TestValidateMaxRetries:
    """測試最大重試次數驗證"""

    def test_max_retries_valid_range(self):
        """測試有效範圍內的重試次數"""
        # 有效值應該通過驗證
        validate_quality_config(QualityConfig(max_retries=0))
        validate_quality_config(QualityConfig(max_retries=5))
        validate_quality_config(QualityConfig(max_retries=10))

    def test_max_retries_negative(self):
        """測試重試次數為負數"""
        with pytest.raises(ValueError) as exc_info:
            validate_quality_config(QualityConfig(max_retries=-1))
        assert "max_retries" in str(exc_info.value).lower()
        assert "0" in str(exc_info.value)
        assert "10" in str(exc_info.value)

    def test_max_retries_above_10(self):
        """測試重試次數大於 10"""
        with pytest.raises(ValueError) as exc_info:
            validate_quality_config(QualityConfig(max_retries=11))
        assert "max_retries" in str(exc_info.value).lower()
        assert "0" in str(exc_info.value)
        assert "10" in str(exc_info.value)


class TestValidateEngineNames:
    """測試 OCR 引擎名稱驗證"""

    def test_valid_engine_names(self):
        """測試有效的引擎名稱"""
        # 單一引擎
        validate_engine_config(EngineConfig(engines=["paddleocr"]))
        validate_engine_config(EngineConfig(engines=["tesseract"]))
        validate_engine_config(EngineConfig(engines=["textract"]))

        # 多個引擎
        validate_engine_config(EngineConfig(engines=["paddleocr", "tesseract"]))
        validate_engine_config(EngineConfig(engines=["paddleocr", "tesseract", "textract"]))

    def test_invalid_engine_name(self):
        """測試無效的引擎名稱"""
        with pytest.raises(ValueError) as exc_info:
            validate_engine_config(EngineConfig(engines=["invalid_engine"]))
        assert "engine" in str(exc_info.value).lower()
        assert "invalid_engine" in str(exc_info.value)

    def test_mixed_valid_and_invalid_engines(self):
        """測試混合有效和無效的引擎"""
        with pytest.raises(ValueError) as exc_info:
            validate_engine_config(EngineConfig(engines=["paddleocr", "invalid_engine"]))
        assert "invalid_engine" in str(exc_info.value)

    def test_empty_engine_list(self):
        """測試空的引擎列表"""
        with pytest.raises(ValueError) as exc_info:
            validate_engine_config(EngineConfig(engines=[]))
        assert "engine" in str(exc_info.value).lower()
        assert "empty" in str(exc_info.value).lower() or "至少" in str(exc_info.value)


class TestValidateHSVThresholds:
    """測試 HSV 閾值驗證"""

    def test_valid_hsv_thresholds(self):
        """測試有效的 HSV 閾值"""
        # 預設值應該有效
        validate_preprocess_config(PreprocessConfig())

        # 自訂有效值
        validate_preprocess_config(PreprocessConfig(
            hsv_lower=(0, 0, 0),
            hsv_upper1=(10, 255, 255),
            hsv_upper2=(180, 255, 255)
        ))

    def test_hsv_lower_invalid_h(self):
        """測試 hsv_lower 的 H 值超出範圍"""
        with pytest.raises(ValueError) as exc_info:
            validate_preprocess_config(PreprocessConfig(hsv_lower=(181, 50, 50)))
        assert "hsv" in str(exc_info.value).lower()
        assert "h" in str(exc_info.value).lower() or "色相" in str(exc_info.value)

    def test_hsv_lower_invalid_s(self):
        """測試 hsv_lower 的 S 值超出範圍"""
        with pytest.raises(ValueError) as exc_info:
            validate_preprocess_config(PreprocessConfig(hsv_lower=(0, 256, 50)))
        assert "hsv" in str(exc_info.value).lower()
        assert "s" in str(exc_info.value).lower() or "飽和度" in str(exc_info.value)

    def test_hsv_lower_invalid_v(self):
        """測試 hsv_lower 的 V 值超出範圍"""
        with pytest.raises(ValueError) as exc_info:
            validate_preprocess_config(PreprocessConfig(hsv_lower=(0, 50, 256)))
        assert "hsv" in str(exc_info.value).lower()
        assert "v" in str(exc_info.value).lower() or "明度" in str(exc_info.value)

    def test_hsv_upper1_out_of_range(self):
        """測試 hsv_upper1 超出範圍"""
        with pytest.raises(ValueError) as exc_info:
            validate_preprocess_config(PreprocessConfig(hsv_upper1=(10, 256, 255)))
        assert "hsv" in str(exc_info.value).lower()

    def test_hsv_upper2_out_of_range(self):
        """測試 hsv_upper2 超出範圍"""
        with pytest.raises(ValueError) as exc_info:
            validate_preprocess_config(PreprocessConfig(hsv_upper2=(181, 255, 255)))
        assert "hsv" in str(exc_info.value).lower()


class TestValidateBinarizationMethod:
    """測試二值化方法驗證"""

    def test_valid_binarization_methods(self):
        """測試有效的二值化方法"""
        validate_preprocess_config(PreprocessConfig(binarization_method="gaussian"))
        validate_preprocess_config(PreprocessConfig(binarization_method="mean"))
        validate_preprocess_config(PreprocessConfig(binarization_method="sauvola"))

    def test_invalid_binarization_method(self):
        """測試無效的二值化方法"""
        with pytest.raises(ValueError) as exc_info:
            validate_preprocess_config(PreprocessConfig(binarization_method="invalid_method"))
        assert "binarization_method" in str(exc_info.value).lower()
        assert "gaussian" in str(exc_info.value).lower()
        assert "mean" in str(exc_info.value).lower()
        assert "sauvola" in str(exc_info.value).lower()


class TestValidateFusionMethod:
    """測試融合方法驗證"""

    def test_valid_fusion_methods(self):
        """測試有效的融合方法"""
        validate_engine_config(EngineConfig(fusion_method="best"))
        validate_engine_config(EngineConfig(fusion_method="weighted"))
        validate_engine_config(EngineConfig(fusion_method="vote"))

    def test_invalid_fusion_method(self):
        """測試無效的融合方法"""
        with pytest.raises(ValueError) as exc_info:
            validate_engine_config(EngineConfig(fusion_method="invalid_method"))
        assert "fusion_method" in str(exc_info.value).lower()
        assert "best" in str(exc_info.value).lower()
        assert "weighted" in str(exc_info.value).lower()
        assert "vote" in str(exc_info.value).lower()


class TestValidateTargetDPI:
    """測試目標 DPI 驗證"""

    def test_valid_target_dpi(self):
        """測試有效的 DPI 值"""
        validate_preprocess_config(PreprocessConfig(target_dpi=300))
        validate_preprocess_config(PreprocessConfig(target_dpi=600))
        validate_preprocess_config(PreprocessConfig(target_dpi=1500))

    def test_target_dpi_too_low(self):
        """測試 DPI 值過低"""
        with pytest.raises(ValueError) as exc_info:
            validate_preprocess_config(PreprocessConfig(target_dpi=50))
        assert "dpi" in str(exc_info.value).lower()
        assert "100" in str(exc_info.value) or "低" in str(exc_info.value)

    def test_target_dpi_too_high(self):
        """測試 DPI 值過高"""
        with pytest.raises(ValueError) as exc_info:
            validate_preprocess_config(PreprocessConfig(target_dpi=5000))
        assert "dpi" in str(exc_info.value).lower()
        assert "3000" in str(exc_info.value) or "高" in str(exc_info.value)


class TestValidateConfigIntegration:
    """測試整合配置驗證"""

    def test_validate_all_configs_valid(self):
        """測試驗證所有配置（有效配置）"""
        preprocess_config = PreprocessConfig()
        engine_config = EngineConfig()
        quality_config = QualityConfig()

        # 應該通過驗證不拋出異常
        validate_config(preprocess_config, engine_config, quality_config)

    def test_validate_config_with_invalid_quality(self):
        """測試整合驗證（無效品質配置）"""
        preprocess_config = PreprocessConfig()
        engine_config = EngineConfig()
        quality_config = QualityConfig(quality_threshold=150.0)

        with pytest.raises(ValueError):
            validate_config(preprocess_config, engine_config, quality_config)

    def test_validate_config_with_invalid_engine(self):
        """測試整合驗證（無效引擎配置）"""
        preprocess_config = PreprocessConfig()
        engine_config = EngineConfig(engines=["invalid"])
        quality_config = QualityConfig()

        with pytest.raises(ValueError):
            validate_config(preprocess_config, engine_config, quality_config)

    def test_validate_config_with_invalid_preprocess(self):
        """測試整合驗證（無效預處理配置）"""
        preprocess_config = PreprocessConfig(target_dpi=10)
        engine_config = EngineConfig()
        quality_config = QualityConfig()

        with pytest.raises(ValueError):
            validate_config(preprocess_config, engine_config, quality_config)


class TestErrorMessages:
    """測試錯誤訊息清晰度"""

    def test_error_message_includes_parameter_name(self):
        """測試錯誤訊息包含參數名稱"""
        with pytest.raises(ValueError) as exc_info:
            validate_quality_config(QualityConfig(quality_threshold=150.0))
        error_msg = str(exc_info.value)
        assert "quality_threshold" in error_msg.lower()

    def test_error_message_includes_valid_range(self):
        """測試錯誤訊息包含有效範圍"""
        with pytest.raises(ValueError) as exc_info:
            validate_quality_config(QualityConfig(max_retries=20))
        error_msg = str(exc_info.value)
        assert "0" in error_msg
        assert "10" in error_msg

    def test_error_message_includes_valid_options(self):
        """測試錯誤訊息包含有效選項"""
        with pytest.raises(ValueError) as exc_info:
            validate_engine_config(EngineConfig(engines=["invalid"]))
        error_msg = str(exc_info.value)
        assert "paddleocr" in error_msg.lower() or "tesseract" in error_msg.lower()

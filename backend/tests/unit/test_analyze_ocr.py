"""
測試統一分析服務 - OCR 處理流程整合

驗收標準:
- PDF 自動拆頁並逐頁處理
- 圖片直接處理為單頁
- 使用 ProcessorFactory 依文件類型路由到正確的處理器
- 回應不含 original_image（base64）
- 部分頁面失敗時，其餘頁面結果正常回傳
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from io import BytesIO
from PIL import Image


def _make_test_image_bytes():
    """建立測試用 PNG 圖片 bytes"""
    img = Image.new('RGB', (100, 100), color='white')
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _make_mock_page_result(page_number=1):
    """建立 mock 的 PageResult"""
    return {
        "page_number": page_number,
        "original_image": "data:image/png;base64,FAKE",
        "ocr_raw": {"text": f"第{page_number}頁文字", "confidence": 0.85},
        "rule_postprocessed": {"text": f"第{page_number}頁修正", "stats": {"typo_fixes": 3}},
        "llm_postprocessed": None,
        "structured_data": None,
        "accuracy": None,
        "processing_steps": {"1_preprocess": "完成", "2_ocr": "完成"}
    }


class TestProcessOcr:
    """測試 OCR 處理流程"""

    @pytest.mark.asyncio
    async def test_image_processed_as_single_page(self):
        """圖片應直接處理為單頁"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()
        img_bytes = _make_test_image_bytes()

        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(return_value=_make_mock_page_result(1))

        with patch("app.services.analyze_service.ProcessorFactory") as MockFactory:
            MockFactory.get_processor.return_value = mock_processor

            pages, total = await service._process_ocr(
                img_bytes, "test.png", "transcript", True
            )

            assert total == 1
            assert len(pages) == 1
            assert pages[0]["page_number"] == 1

    @pytest.mark.asyncio
    async def test_uses_processor_factory(self):
        """應使用 ProcessorFactory 取得正確的處理器"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()
        img_bytes = _make_test_image_bytes()

        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(return_value=_make_mock_page_result(1))

        with patch("app.services.analyze_service.ProcessorFactory") as MockFactory:
            MockFactory.get_processor.return_value = mock_processor

            await service._process_ocr(img_bytes, "test.jpg", "contract", False)

            MockFactory.get_processor.assert_called_with("contract")

    @pytest.mark.asyncio
    async def test_result_excludes_original_image(self):
        """回應不應包含 original_image"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()
        img_bytes = _make_test_image_bytes()

        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(return_value=_make_mock_page_result(1))

        with patch("app.services.analyze_service.ProcessorFactory") as MockFactory:
            MockFactory.get_processor.return_value = mock_processor

            pages, _ = await service._process_ocr(
                img_bytes, "test.png", "transcript", False
            )

            assert "original_image" not in pages[0]

    @pytest.mark.asyncio
    async def test_pdf_multi_page(self):
        """PDF 應自動拆頁並逐頁處理"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        # 建立 2 頁的 mock PDF
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=2)
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = _make_test_image_bytes()
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(side_effect=[
            _make_mock_page_result(1),
            _make_mock_page_result(2),
        ])

        with patch("app.services.analyze_service.fitz") as mock_fitz, \
             patch("app.services.analyze_service.ProcessorFactory") as MockFactory:
            mock_fitz.open.return_value = mock_doc
            mock_fitz.Matrix = MagicMock()
            MockFactory.get_processor.return_value = mock_processor

            pages, total = await service._process_ocr(
                b"fake pdf", "test.pdf", "transcript", True
            )

            assert total == 2
            assert len(pages) == 2
            assert pages[0]["page_number"] == 1
            assert pages[1]["page_number"] == 2

    @pytest.mark.asyncio
    async def test_partial_page_failure(self):
        """部分頁面失敗時，其餘頁面應正常回傳"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=2)
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = _make_test_image_bytes()
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(side_effect=[
            Exception("OCR failed on page 1"),
            _make_mock_page_result(2),
        ])

        with patch("app.services.analyze_service.fitz") as mock_fitz, \
             patch("app.services.analyze_service.ProcessorFactory") as MockFactory:
            mock_fitz.open.return_value = mock_doc
            mock_fitz.Matrix = MagicMock()
            MockFactory.get_processor.return_value = mock_processor

            pages, total = await service._process_ocr(
                b"fake pdf", "test.pdf", "transcript", True
            )

            assert total == 2
            # 第 1 頁失敗但第 2 頁成功
            assert len(pages) == 2
            # 失敗頁面應有 error 標記
            assert "error" in pages[0]
            # 成功頁面應有正常結果
            assert pages[1]["ocr_raw"]["text"] == "第2頁文字"

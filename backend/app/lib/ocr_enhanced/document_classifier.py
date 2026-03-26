"""
Document Classifier Module

文件類型自動偵測模組，根據關鍵字判斷文件類型。
"""

import logging
from typing import List
from PIL import Image
from .types import DocumentType

# 嘗試導入 pytesseract，如果失敗則使用 mock
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    pytesseract = None


class DocumentClassifier:
    """
    文件類型分類器

    使用關鍵字檢測判斷文件類型（transcript/lease/id_card/unknown）。
    """

    def __init__(self):
        """初始化文件分類器"""
        self.logger = logging.getLogger("DocumentClassifier")

        # 謄本關鍵字
        self.transcript_keywords = [
            "謄本", "地政", "建物標示部", "土地標示部", "所有權部"
        ]

        # 租約關鍵字
        self.lease_keywords = [
            "租賃契約", "租約", "承租人", "出租人", "租金"
        ]

        # 身分證關鍵字
        self.id_card_keywords = [
            "身分證", "國民身分證", "統一編號", "出生地"
        ]

    def _extract_text(self, image: Image.Image) -> str:
        """
        使用 pytesseract 從圖像提取文字

        Args:
            image: PIL Image 物件

        Returns:
            提取的文字
        """
        if not HAS_TESSERACT or pytesseract is None:
            self.logger.warning("pytesseract 未安裝，無法提取文字")
            return ""

        try:
            # 使用繁體中文配置
            text = pytesseract.image_to_string(
                image,
                lang='chi_tra',
                config='--psm 6'
            )
            return text
        except Exception as e:
            self.logger.error(f"文字提取失敗: {e}")
            return ""

    def extract_text_from_image(self, image: Image.Image) -> str:
        """
        公開方法：從圖像提取文字

        Args:
            image: PIL Image 物件

        Returns:
            提取的文字
        """
        return self._extract_text(image)

    def _match_keywords(self, text: str, keywords: List[str]) -> int:
        """
        匹配關鍵字

        Args:
            text: 要匹配的文字
            keywords: 關鍵字列表

        Returns:
            匹配到的關鍵字數量
        """
        if not text:
            return 0

        matches = 0
        for keyword in keywords:
            if keyword in text:
                matches += 1

        return matches

    def match_keywords(self, text: str, keywords: List[str]) -> int:
        """
        公開方法：匹配關鍵字

        Args:
            text: 要匹配的文字
            keywords: 關鍵字列表

        Returns:
            匹配到的關鍵字數量
        """
        return self._match_keywords(text, keywords)

    def is_transcript(self, image: Image.Image) -> bool:
        """
        判斷是否為建物土地謄本

        Args:
            image: PIL Image 物件

        Returns:
            是否為謄本

        Raises:
            TypeError: image 不是 PIL Image 物件
            ValueError: image 為 None
        """
        if image is None:
            raise ValueError("image 不能為 None")

        if not isinstance(image, Image.Image):
            raise TypeError("image 必須是 PIL Image 物件")

        # 提取文字
        text = self._extract_text(image)

        if not text:
            self.logger.debug("無法提取文字，返回 False")
            return False

        # 匹配謄本關鍵字
        matches = self._match_keywords(text, self.transcript_keywords)

        # 至少匹配一個關鍵字即判定為謄本
        is_match = matches >= 1

        self.logger.debug(f"謄本關鍵字匹配數: {matches}, 判定結果: {is_match}")

        return is_match

    async def classify(self, image: Image.Image) -> DocumentType:
        """
        分類文件類型

        Args:
            image: PIL Image 物件

        Returns:
            文件類型 (transcript/lease/id_card/unknown)

        Raises:
            TypeError: image 不是 PIL Image 物件
            ValueError: image 為 None
        """
        if image is None:
            raise ValueError("image 不能為 None")

        if not isinstance(image, Image.Image):
            raise TypeError("image 必須是 PIL Image 物件")

        self.logger.info("開始分類文件類型")

        # 提取文字
        text = self._extract_text(image)

        if not text or len(text.strip()) == 0:
            self.logger.debug("無法提取文字或文字為空，返回 unknown")
            return "unknown"

        # 匹配各類型關鍵字
        transcript_matches = self._match_keywords(text, self.transcript_keywords)
        lease_matches = self._match_keywords(text, self.lease_keywords)
        id_card_matches = self._match_keywords(text, self.id_card_keywords)

        self.logger.debug(
            f"關鍵字匹配結果 - 謄本: {transcript_matches}, "
            f"租約: {lease_matches}, 身分證: {id_card_matches}"
        )

        # 選擇匹配數最多的類型
        max_matches = max(transcript_matches, lease_matches, id_card_matches)

        if max_matches == 0:
            return "unknown"

        # 返回匹配數最多的類型
        if transcript_matches == max_matches:
            self.logger.info("分類結果: transcript")
            return "transcript"
        elif lease_matches == max_matches:
            self.logger.info("分類結果: lease")
            return "lease"
        elif id_card_matches == max_matches:
            self.logger.info("分類結果: id_card")
            return "id_card"

        return "unknown"

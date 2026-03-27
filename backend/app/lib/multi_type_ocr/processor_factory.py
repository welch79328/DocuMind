"""
文件處理器工廠類別

提供根據文件類型動態選擇對應處理器的工廠方法,支援處理器註冊機制。
"""

import logging
from typing import Dict, Type

from .processor import DocumentProcessor
from .transcript_processor import TranscriptProcessor
from .contract_processor import ContractProcessor

logger = logging.getLogger(__name__)


class ProcessorFactory:
    """
    文件處理器工廠

    根據文件類型參數創建對應的處理器實例。
    支援動態註冊新的處理器類型,便於系統擴展。

    使用方式:
        # 取得處理器
        processor = ProcessorFactory.get_processor("transcript")

        # 註冊新處理器
        ProcessorFactory.register_processor("invoice", InvoiceProcessor)

        # 查詢支援的類型
        types = ProcessorFactory.supported_types()
    """

    # 處理器類型映射表
    # 映射文件類型字符串到處理器類別
    _processors: Dict[str, Type[DocumentProcessor]] = {}

    @classmethod
    def get_processor(cls, document_type: str) -> DocumentProcessor:
        """
        取得文件處理器實例

        根據文件類型參數返回對應的處理器實例。
        每次調用都會創建新的實例。

        Args:
            document_type: 文件類型字符串 (例如: "transcript", "contract")

        Returns:
            對應文件類型的處理器實例

        Raises:
            ValueError: 當指定的文件類型不支援時拋出,
                       錯誤訊息包含不支援的類型與所有支援的類型列表

        Example:
            >>> processor = ProcessorFactory.get_processor("transcript")
            >>> isinstance(processor, DocumentProcessor)
            True
        """
        processor_class = cls._processors.get(document_type)

        if processor_class is None:
            supported = ", ".join(cls._processors.keys())
            error_message = (
                f"不支援的文件類型: {document_type}。"
                f"支援的類型: {supported}"
            )
            logger.error(error_message)
            raise ValueError(error_message)

        logger.info(f"創建文件處理器: {document_type}")
        return processor_class()

    @classmethod
    def register_processor(
        cls,
        document_type: str,
        processor_class: Type[DocumentProcessor]
    ) -> None:
        """
        註冊新的文件處理器

        將新的處理器類別註冊到工廠,使其可透過 get_processor() 取得。
        若文件類型已存在,將覆蓋原有的處理器類別。

        Args:
            document_type: 文件類型字符串 (例如: "transcript", "contract")
            processor_class: 處理器類別 (必須繼承自 DocumentProcessor)

        Example:
            >>> class MyProcessor(DocumentProcessor):
            ...     pass
            >>> ProcessorFactory.register_processor("my_type", MyProcessor)
            >>> "my_type" in ProcessorFactory.supported_types()
            True
        """
        logger.info(f"註冊文件處理器: {document_type} -> {processor_class.__name__}")
        cls._processors[document_type] = processor_class

    @classmethod
    def supported_types(cls) -> list[str]:
        """
        返回所有支援的文件類型

        Returns:
            支援的文件類型列表

        Example:
            >>> ProcessorFactory.register_processor("transcript", TranscriptProcessor)
            >>> ProcessorFactory.register_processor("contract", ContractProcessor)
            >>> types = ProcessorFactory.supported_types()
            >>> "transcript" in types
            True
            >>> "contract" in types
            True
        """
        return list(cls._processors.keys())


# 預設註冊支援的處理器
ProcessorFactory.register_processor("transcript", TranscriptProcessor)
ProcessorFactory.register_processor("contract", ContractProcessor)

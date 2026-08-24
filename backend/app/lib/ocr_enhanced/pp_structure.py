"""
PP-Structure 版面解析增強(謄本增強選項)

PP-StructureV3 可對謄本密集版面/表格/印章做結構化解析,理論上提升欄位級準確率。
依設計與市場研究(research.md),此為「增強選項」而非主力:預設關閉、惰性載入、
失敗即降級,確保不阻塞主線(規則 + LLM Vision 已可交付)。

實際繁中謄本效益與資源成本須以自有樣本於容器環境實測(見 pp-structure-poc.md)。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class PPStructureEnhancer:
    """PP-Structure 版面解析(可選、惰性、降級)"""

    _instance = None  # PP-Structure 單例(惰性)

    def is_enabled(self) -> bool:
        """是否啟用 PP-Structure 增強(預設關閉)"""
        return bool(settings.OCR_ENABLE_PP_STRUCTURE)

    async def parse_layout(self, image: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        以 PP-Structure 解析版面,回傳結構化結果;停用或失敗時回 None(降級)。

        Returns:
            版面解析結果(表格/區塊等)或 None。
        """
        if not self.is_enabled():
            return None

        try:
            structure = self._ensure_engine()
            result = structure(image)
            return {"layout": result}
        except Exception as e:  # 未安裝 / 執行失敗 → 降級,不阻塞主線
            logger.warning(f"PP-Structure 版面解析不可用,降級為標準流程: {e}")
            return None

    def _ensure_engine(self):
        """惰性載入 PP-Structure(單例)"""
        if PPStructureEnhancer._instance is None:
            # ⚠️ paddleocr 3.x 已移除 PPStructure(取而代之的是 PPStructureV3,
            # API 與回傳結構皆不同)。2026-08-24 升級至 3.7.0 後,這裡必定
            # ImportError,由呼叫端的 try/except 降級為標準流程。
            #
            # OCR_ENABLE_PP_STRUCTURE 預設為 False,所以正常情況下根本不會走到這裡。
            # 若日後要啟用版面解析,需改寫為 PPStructureV3 並重新驗證回傳結構,
            # 不是換個類別名稱就好。
            from paddleocr import PPStructure  # 3.x 已移除,於此拋出由呼叫端降級
            PPStructureEnhancer._instance = PPStructure(
                show_log=False,
                lang=settings.OCR_PADDLEOCR_LANG,
            )
        return PPStructureEnhancer._instance

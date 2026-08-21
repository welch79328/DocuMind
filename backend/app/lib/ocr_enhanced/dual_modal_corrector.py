"""
雙模態 OCR 校正器(ocr-vlm-consensus 任務 8.1~8.3)

以「OCR 文字 + 頁面影像」校正 OCR 錯誤,取代 LLMPostprocessor.correct_full_text()
中被硬編碼停用的影像路徑。

三條路徑皆不中斷辨識流程:
1. 雙模態 — 設定啟用且影像可用
2. 純文字降級 — 影像未提供 / 編碼失敗 / 帶影像呼叫失敗,記錄降級事由
3. 模型拒絕 — 保留原始辨識文字,絕不以拒絕訊息覆蓋結果(需求 2.8)

模型一律經 `create_provider()` 取得,因此 LLM_CLOUD_ENABLED=false 時雲端 Provider
會在建立階段就被隱私守衛擋下,文件內容不會外送(需求 2.6、2.7)。

對應需求: 2.1, 2.2, 2.3, 2.6, 2.7, 2.8
"""

from __future__ import annotations

import base64
import binascii
import logging
from typing import Any, Dict, List, Literal, Optional, TypedDict

from app.config import settings
from app.lib.llm_service.providers import LLMProvider, create_provider

logger = logging.getLogger(__name__)


class CorrectionResult(TypedDict):
    """校正結果;modality 與 degraded_reason 讓呼叫端能回溯實際走了哪條路徑"""

    text: str
    field_confidences: Dict[str, float]
    modality: Literal["dual", "text_only"]
    degraded_reason: Optional[str]
    refused: bool
    stats: Dict[str, Any]


# 模型拒絕處理的特徵字串(短回應 + 拒絕語)
_REFUSAL_PATTERNS = (
    # English
    "i'm sorry", "i can't assist", "i cannot assist",
    "i'm unable to", "i cannot help", "i can't help",
    "i'm not able to", "i cannot process",
    # Chinese
    "抱歉", "無法協助", "無法處理", "不能協助", "無法提供",
    "我無法", "不能處理",
)
_REFUSAL_MAX_LEN = 100


def is_refusal(text: str) -> bool:
    """回應是否為模型的拒絕訊息

    只在「短回應」時判定,避免把正文中偶然出現的「抱歉」誤判為拒絕
    ——謄本全文校正結果動輒數百字,不會落入此區間。
    """
    lowered = text.lower()
    return len(text) < _REFUSAL_MAX_LEN and any(
        pattern in lowered for pattern in _REFUSAL_PATTERNS
    )


def normalize_image_data(image_data: Optional[str]) -> str:
    """驗證並正規化 base64 影像資料

    Returns:
        可送入 Provider 的 base64 字串

    Raises:
        ValueError: 影像為空或非合法 base64(由呼叫端轉為純文字降級)
    """
    if not image_data:
        raise ValueError("影像資料為空")

    raw = image_data.split("base64,", 1)[-1].strip()
    if not raw:
        raise ValueError("影像資料去除前綴後為空")

    try:
        base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"影像非合法 base64:{exc}") from exc

    return raw


class DualModalCorrector:
    """雙模態 OCR 校正器"""

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        """provider 未提供時,由 create_provider() 依設定建立(支援本地部署)

        建立延後到首次呼叫,讓「停用校正」時完全不觸發 Provider 建立
        與任何模型呼叫成本(需求 2.4)。
        """
        self._provider = provider
        self._provider_name: Optional[str] = None

    @property
    def provider(self) -> LLMProvider:
        if self._provider is None:
            self._provider = create_provider(self._provider_name)
        return self._provider

    def bind_provider_name(self, provider_name: Optional[str]) -> None:
        """指定 create_provider 要建立的 Provider 名稱(None = 依設定)"""
        self._provider_name = provider_name

    @property
    def stats(self) -> Dict[str, Any]:
        """尚未建立 Provider 時回報零值,不因取用統計而觸發建立"""
        if self._provider is None:
            return {
                "llm_calls": 0,
                "tokens_used": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "estimated_cost": 0.0,
            }
        return dict(getattr(self._provider, "stats", {}))

    # ------------------------------------------------------------------ #
    # 校正
    # ------------------------------------------------------------------ #
    async def correct(
        self,
        ocr_text: str,
        doc_type: str = "transcript",
        image_data: Optional[str] = None,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> CorrectionResult:
        """校正 OCR 文字

        image_data 為 None 或編碼失敗時降級為純文字校正並記錄事由(需求 2.3)。
        模型因內容政策拒絕時,回傳原始文字並記錄事由(需求 2.8)。
        """
        image_payload, degraded_reason = self._resolve_image(image_data)

        if image_payload is not None:
            try:
                return await self._call(
                    ocr_text, doc_type, image_payload, few_shot, degraded_reason=None
                )
            except Exception as exc:  # noqa: BLE001 — 任何影像路徑失敗都須降級,不得中斷
                degraded_reason = f"雙模態呼叫失敗,降級純文字:{exc}"
                logger.warning(degraded_reason)

        return await self._call(
            ocr_text, doc_type, None, few_shot, degraded_reason=degraded_reason
        )

    def _resolve_image(
        self, image_data: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """決定是否走雙模態,並回傳 (影像資料, 降級事由)"""
        if not settings.LLM_DUAL_MODAL_ENABLED:
            # 設定關閉不算降級——這是現行的預設行為,不需記錄事由
            return None, None

        try:
            return normalize_image_data(image_data), None
        except ValueError as exc:
            reason = f"影像不可用,降級純文字:{exc}"
            logger.warning(reason)
            return None, reason

    async def _call(
        self,
        ocr_text: str,
        doc_type: str,
        image_payload: Optional[str],
        few_shot: Optional[List[Dict[str, Any]]],
        degraded_reason: Optional[str],
    ) -> CorrectionResult:
        modality: Literal["dual", "text_only"] = (
            "dual" if image_payload else "text_only"
        )
        prompt = build_correction_prompt(
            ocr_text, doc_type, has_image=image_payload is not None
        )

        response = await self.provider.call(
            prompt=prompt,
            image_data=image_payload,
            few_shot=few_shot,
            max_tokens=3000,
            temperature=0.1,
        )

        if is_refusal(response):
            logger.warning("模型拒絕處理該文件,保留原始辨識文字(modality=%s)", modality)
            return CorrectionResult(
                text=ocr_text,
                field_confidences={},
                modality=modality,
                degraded_reason=degraded_reason,
                refused=True,
                stats=self.stats,
            )

        return CorrectionResult(
            text=response,
            field_confidences={},
            modality=modality,
            degraded_reason=degraded_reason,
            refused=False,
            stats=self.stats,
        )


# ====================================================================== #
# 提示詞(任務 8.3:提示詞須與實際模態一致)
# ====================================================================== #

_COMMON_RULES = """【重要原則】
{image_rules}只修正明顯的 OCR 錯誤,不要過度解讀或改寫
保持原文的所有內容,包括數字、符號、換行
{uncertain_rule}"""

_IMAGE_RULES = "**請仔細查看上面提供的文件圖片**,對照圖片中的實際文字來修正 OCR 錯誤\n"
_UNCERTAIN_WITH_IMAGE = "無法確定的文字請參考圖片,如果圖片也看不清楚則保持原樣"
_UNCERTAIN_TEXT_ONLY = "無法確定的文字保持原樣,不要憑上下文臆測"


def build_correction_prompt(
    ocr_text: str, doc_type: str = "transcript", has_image: bool = False
) -> str:
    """建立全文校正提示詞

    has_image=False 時不得出現任何要求查看圖片的指示——現行版本把
    「請仔細查看上面提供的文件圖片」寫死在提示詞裡卻從不傳圖,
    等於要模型對照一張不存在的圖(任務 8.3 修正此不一致)。
    """
    rules = _COMMON_RULES.format(
        image_rules=_IMAGE_RULES if has_image else "",
        uncertain_rule=_UNCERTAIN_WITH_IMAGE if has_image else _UNCERTAIN_TEXT_ONLY,
    )

    return f"""你是專業的台灣地政謄本 OCR 錯誤修正專家。請修正以下 OCR 辨識的錯誤文字。

【任務說明】
這是一個合法授權的文件數位化 OCR 校正系統。你的任務是純粹的文字校正——將 OCR 引擎辨識錯誤的字元修正為正確的字元。文件中的所有內容(包括姓名、地址、編號等)均為 OCR 辨識產生的文字,需要你協助校正錯別字。請勿拒絕處理或省略任何內容。

文件類型:{doc_type}

{rules}

【常見 OCR 錯誤對照表】
文字錯誤:
- 十 → 土(土地)
- 膽/徐/朕 → 謄(謄本)
- 攝 → 登(登記)
- 焉/班 → 正(中正)
- 息 → 段(正段)
- 旋 → 段(小段)
- 傑/樺 → 權(所有權)
- 園/闕 → 圍(範圍)
- 蕉 → 共(共4棟)
- 害 → 割(分割)
- 勁為 → 鑑界
- 朕 → 謄

數字與字母錯誤:
- o/O → 0(地號中)
- l/I/| → 1
- 空格要移除(地號中不能有空格)

【台灣地政謄本標準格式範例】
正確格式:
✓ 土地登記第三類謄本(所有權個人全部)
✓ 中正區中正段三小段 0221-0000 地號
✓ 列印時間:民國108年04月09日17時09分
✓ 本謄本係網路申領之電子謄本,由申請人自行列印
✓ 謄本種類碼:L944V64QT3
✓ 建成地政事務所 主任 曾錫雄
✓ 登記日期:民國075年05月27日
✓ 登記原因:鑑界分割
✓ 面積:153.00平方公尺
✓ 所有權人:黃水木
✓ 統一編號:A202******6
✓ 權利範圍:全部

【修正範例】
錯誤:十:攝登記第三類有徐生 (所有權個人人金義5》 全
正確:土地登記第三類謄本(所有權個人全部)

錯誤:中焉區中班息三小旋 o221-oooolta中的0
正確:中正區中正段三小段 0221-0000 地號

錯誤:電子朕本
正確:電子謄本

錯誤:膽本種類碼
正確:謄本種類碼

錯誤:勁為分割
正確:鑑界分割

錯誤:蕉4棟
正確:共4棟

錯誤:因分害增加地號
正確:因分割增加地號

【要修正的 OCR 文字】
{ocr_text}

請直接輸出修正後的完整文字,不要添加任何解釋或說明。保持所有原有的換行和格式。"""


__all__ = [
    "CorrectionResult",
    "DualModalCorrector",
    "build_correction_prompt",
    "is_refusal",
    "normalize_image_data",
]

"""
合約欄位提取器

此模組實作合約關鍵欄位的自動提取功能，支援正則表達式提取與 LLM 輔助提取。

使用範例:
    from app.lib.multi_type_ocr.contract_field_extractor import ContractFieldExtractor

    extractor = ContractFieldExtractor()
    result = await extractor.extract(ocr_text, image_data)

    print(f"合約編號: {result['contract_metadata']['contract_number']}")
    print(f"提取信心度: {result['extraction_confidence']:.2%}")
"""

import re
import logging
from typing import Dict, Any, Optional
from app.lib.multi_type_ocr.contract_patterns import PATTERNS
from app.lib.llm_service import LLMService
from app.config import settings

logger = logging.getLogger(__name__)


class ContractFieldExtractor:
    """
    合約關鍵欄位提取器

    使用正則表達式從合約文字中提取結構化欄位，並計算提取信心度。
    當信心度低於閾值時，可選擇性地使用 LLM 輔助提取。
    """

    # 關鍵欄位定義（權重較高）
    CRITICAL_FIELDS = {
        # 通用合約關鍵欄位
        "contract_number",      # 合約編號
        "party_a",             # 甲方
        "party_b",             # 乙方
        "contract_amount",     # 合約金額

        # 租賃合約關鍵欄位
        "date_start",          # 租期起始日
        "date_end",            # 租期結束日
        "monthly_rent",        # 月租金
        "deposit",             # 押金
        "rental_address",      # 租賃標的地址
        "tenant_name",         # 承租人姓名
    }

    # 租賃合約專屬欄位(通用合約不會有,不應計入通用合約的信心度分母)
    LEASE_CRITICAL_FIELDS = {
        "date_start", "date_end", "monthly_rent",
        "deposit", "rental_address", "tenant_name",
    }
    LEASE_MINOR_FIELDS = {
        "tenant_id_number", "tenant_phone", "landlord_name",
        "landlord_id_number", "landlord_phone",
        "management_fee", "parking_fee", "payment_day",
    }

    # 判別是否為租賃合約的關鍵詞。
    # **刻意從原始文字判別,而非「有沒有抽到租賃欄位」**——後者會讓一份
    # 讀壞的租約因為抽不到租賃欄位而被當成通用合約,分母縮小、信心度虛高,
    # 正好在最該攔截的時候放行。
    LEASE_MARKERS = (
        "租賃", "承租人", "出租人", "房東", "房客",
        "月租金", "押金", "租期", "起租",
    )

    # 關鍵欄位的中文標籤(任務 8.4:校正階段索取欄位信心度時使用)。
    # 只涵蓋 CRITICAL_FIELDS——把 26 個欄位全塞進提示詞會稀釋校正本身的注意力,
    # 而信心度攔截真正在乎的也就是這幾個。
    FIELD_LABELS = {
        "contract_number": "合約編號",
        "party_a": "甲方",
        "party_b": "乙方",
        "contract_amount": "合約金額",
        "date_start": "租期起始日",
        "date_end": "租期結束日",
        "monthly_rent": "月租金",
        "deposit": "押金",
        "rental_address": "租賃標的地址",
        "tenant_name": "承租人姓名",
    }

    # 次要欄位定義（權重較低）
    MINOR_FIELDS = {
        # 通用合約次要欄位
        "signing_date",
        "effective_date",
        "party_a_address",
        "party_b_address",
        "currency",
        "payment_method",
        "payment_deadline",

        # 租賃合約次要欄位
        "tenant_id_number",    # 承租人身分證字號
        "tenant_phone",        # 承租人電話
        "landlord_name",       # 出租人姓名
        "landlord_id_number",  # 出租人身分證字號
        "landlord_phone",      # 出租人電話
        "management_fee",      # 管理費
        "parking_fee",         # 停車費
        "payment_day",         # 租金繳納日
    }

    # 信心度閾值（低於此值觸發 LLM 備選）
    CONFIDENCE_THRESHOLD = 0.7

    def __init__(self):
        """初始化提取器"""
        self.llm_service: Optional[LLMService] = None  # LLM 服務（延遲初始化）

    async def extract(
        self,
        text: str,
        image_data: Optional[str] = None,
        use_llm_fallback: bool = False
    ) -> Dict[str, Any]:
        """
        從合約文字中提取結構化欄位

        Args:
            text: OCR 辨識的合約文字
            image_data: base64 編碼的圖像資料（可選，用於 LLM 視覺提取）
            use_llm_fallback: 是否在正則提取失敗時使用 LLM 輔助（預設 False）

        Returns:
            包含提取欄位與信心度的字典，格式符合 ContractStructuredData
        """
        # 診斷日誌
        logger.info(f"=== ContractFieldExtractor.extract 調用 ===")
        logger.info(f"use_llm_fallback: {use_llm_fallback}")
        logger.info(f"image_data 存在: {image_data is not None}")
        if image_data:
            logger.info(f"image_data 長度: {len(image_data)} bytes")

        # 初始化 LLM 使用標記
        llm_used_for_extraction = False

        # 步驟 1: 使用正則表達式提取
        logger.info("步驟 1: 執行正則表達式提取")
        fields = self._extract_with_regex(text)

        # 步驟 2: 計算信心度
        logger.info("步驟 2: 計算信心度")
        confidence = self._calculate_confidence(fields, text)
        logger.info(f"正則提取信心度: {confidence:.4f} ({confidence:.2%})")

        # 步驟 3: 若信心度低且允許，使用 LLM 輔助
        logger.info(f"步驟 3: 檢查 LLM 觸發條件")
        logger.info(f"  - confidence < CONFIDENCE_THRESHOLD: {confidence} < {self.CONFIDENCE_THRESHOLD} = {confidence < self.CONFIDENCE_THRESHOLD}")
        logger.info(f"  - use_llm_fallback: {use_llm_fallback}")
        logger.info(f"  - image_data is not None: {image_data is not None}")

        # 地端組態下不得把合約內容送往雲端。這裡先擋是為了讓紀錄講清楚
        # 「這是政策決定」而非「LLM 提取失敗」——真正的守衛在 LLMService.__init__
        cloud_blocked = not settings.LLM_CLOUD_ENABLED

        if confidence < self.CONFIDENCE_THRESHOLD and use_llm_fallback and image_data and cloud_blocked:
            logger.info(
                "⛔ LLM_CLOUD_ENABLED=false,略過雲端 LLM 輔助抽取(合約內容不外送);"
                "本份合約維持正則結果,信心度 %.2f%% 將交由既有低信心流程處理",
                confidence * 100,
            )

        if (
            confidence < self.CONFIDENCE_THRESHOLD
            and use_llm_fallback
            and image_data
            and not cloud_blocked
        ):
            try:
                logger.info(f"✅ LLM 觸發條件滿足，啟用 LLM 輔助")
                logger.info(f"正則提取信心度 {confidence:.2%} 低於閾值，啟用 LLM 輔助")
                llm_fields = await self._extract_with_llm(text, image_data)
                fields = self._merge_fields(fields, llm_fields)
                confidence = self._calculate_confidence(fields, text)
                llm_used_for_extraction = True  # LLM 已使用
                logger.info(f"LLM 輔助後信心度: {confidence:.2%}")
            except Exception as e:
                logger.warning(f"LLM 提取失敗，降級使用正則結果: {str(e)}")
                # 保持原有的正則提取結果
        else:
            logger.info(f"❌ LLM 觸發條件不滿足，跳過 LLM 輔助")
            if not (confidence < self.CONFIDENCE_THRESHOLD):
                logger.info(f"   原因: 信心度 {confidence:.2%} >= 閾值 {self.CONFIDENCE_THRESHOLD:.2%}")
            elif not use_llm_fallback:
                logger.info(f"   原因: use_llm_fallback = False")
            elif not image_data:
                logger.info(f"   原因: image_data 為 None")

        # 步驟 4: 組裝結果
        logger.info("步驟 4: 組裝結果")
        return self._build_result(fields, confidence, llm_used_for_extraction)

    def _extract_with_regex(self, text: str) -> Dict[str, Optional[str]]:
        """
        使用正則表達式提取欄位

        Args:
            text: 合約文字

        Returns:
            提取到的欄位字典（未提取到的欄位值為 None）
        """
        results = {}

        # 遍歷所有欄位模式
        for field_name, patterns in PATTERNS.items():
            field_value = None

            # 嘗試每個模式，找到第一個匹配即停止
            for pattern in patterns:
                try:
                    match = re.search(pattern, text, re.MULTILINE)
                    if match:
                        # 提取匹配的文字
                        if match.lastindex and match.lastindex > 1:
                            # 多個捕獲組（例如民國年日期）- 組合所有組
                            field_value = " ".join(match.groups())
                        else:
                            # 單個捕獲組
                            field_value = match.group(1).strip()
                        break  # 找到第一個匹配即停止
                except (re.error, IndexError):
                    # 正則表達式錯誤或索引錯誤，繼續嘗試下一個模式
                    continue

            results[field_name] = field_value

        return results

    def is_lease_contract(self, text: str) -> bool:
        """由原始文字判別是否為租賃合約(不看抽取結果,理由見 LEASE_MARKERS)"""
        return any(marker in (text or "") for marker in self.LEASE_MARKERS)

    def _applicable_fields(self, text: str) -> tuple:
        """
        取得這份合約**適用**的欄位集合,作為信心度分母。

        租賃合約適用全部欄位;通用合約不含租賃專屬欄位。
        以全部欄位當分母是原本的缺陷:通用合約即使每個欄位都抽對,
        上限也只有 0.7×4/10 + 0.3×7/15 = 0.42,永遠低於門檻 0.7,
        於是必然被判低信心、必然觸發 LLM 輔助、必然進複核佇列。
        """
        if self.is_lease_contract(text):
            return self.CRITICAL_FIELDS, self.MINOR_FIELDS
        return (
            self.CRITICAL_FIELDS - self.LEASE_CRITICAL_FIELDS,
            self.MINOR_FIELDS - self.LEASE_MINOR_FIELDS,
        )

    def _calculate_confidence(
        self, fields: Dict[str, Optional[str]], text: str = ""
    ) -> float:
        """
        計算欄位提取信心度

        信心度計算採用加權方式:
        - 關鍵欄位（合約編號、雙方、金額）權重 0.7
        - 次要欄位（日期、地址、付款方式等）權重 0.3

        分母只計入這份合約**適用**的欄位(見 _applicable_fields)。

        Args:
            fields: 提取到的欄位字典
            text: 原始合約文字,用於判別合約子類型

        Returns:
            信心度分數 (0.0 - 1.0)
        """
        critical_fields, minor_fields = self._applicable_fields(text)

        # 統計已提取的關鍵欄位
        critical_extracted = sum(
            1 for field_name in critical_fields
            if fields.get(field_name) is not None
        )
        critical_total = len(critical_fields)

        # 統計已提取的次要欄位
        minor_extracted = sum(
            1 for field_name in minor_fields
            if fields.get(field_name) is not None
        )
        minor_total = len(minor_fields)

        # 計算加權信心度
        critical_score = (critical_extracted / critical_total) if critical_total > 0 else 0.0
        minor_score = (minor_extracted / minor_total) if minor_total > 0 else 0.0

        # 關鍵欄位權重 70%，次要欄位權重 30%
        confidence = (critical_score * 0.7) + (minor_score * 0.3)

        return round(confidence, 4)

    def _build_result(
        self,
        fields: Dict[str, Optional[str]],
        confidence: float,
        llm_used: bool = False
    ) -> Dict[str, Any]:
        """
        組裝提取結果為標準格式

        Args:
            fields: 提取到的原始欄位
            confidence: 信心度分數
            llm_used: LLM 是否被用於欄位提取

        Returns:
            符合 ContractStructuredData 格式的結果字典（包含通用與租賃合約欄位）
        """
        result = {
            "contract_metadata": {
                "contract_number": fields.get("contract_number"),
                "signing_date": fields.get("signing_date"),
                "effective_date": fields.get("effective_date"),
            },
            "parties": {
                "party_a": fields.get("party_a"),
                "party_b": fields.get("party_b"),
                "party_a_address": fields.get("party_a_address"),
                "party_b_address": fields.get("party_b_address"),
            },
            "financial_terms": {
                "contract_amount": fields.get("contract_amount"),
                "currency": fields.get("currency", "TWD"),  # 預設台幣
                "payment_method": fields.get("payment_method"),
                "payment_deadline": fields.get("payment_deadline"),
            },
            "extraction_confidence": confidence,
            "llm_used_for_extraction": llm_used  # 欄位提取是否使用了 LLM
        }

        # 若存在租賃合約欄位，添加 rental_terms 區塊
        rental_fields = {
            "date_start": fields.get("date_start"),
            "date_end": fields.get("date_end"),
            "monthly_rent": fields.get("monthly_rent"),
            "deposit": fields.get("deposit"),
            "rental_address": fields.get("rental_address"),
            "management_fee": fields.get("management_fee"),
            "parking_fee": fields.get("parking_fee"),
            "payment_day": fields.get("payment_day"),
            "tenant_name": fields.get("tenant_name"),
            "tenant_id_number": fields.get("tenant_id_number"),
            "tenant_phone": fields.get("tenant_phone"),
            "landlord_name": fields.get("landlord_name"),
            "landlord_id_number": fields.get("landlord_id_number"),
            "landlord_phone": fields.get("landlord_phone"),
        }

        # 只有當至少有一個租賃欄位被提取時才添加 rental_terms
        if any(v is not None for v in rental_fields.values()):
            result["rental_terms"] = rental_fields

        return result

    async def _extract_with_llm(
        self,
        text: str,
        image_data: str
    ) -> Dict[str, Optional[str]]:
        """
        使用 LLM 視覺提取欄位

        使用 LLMService 從合約圖像中提取結構化欄位。
        當正則表達式提取失敗或信心度低時，作為備選方案。

        Args:
            text: OCR 文字（提供上下文）
            image_data: base64 編碼的圖像資料

        Returns:
            LLM 提取的欄位字典

        Raises:
            Exception: LLM API 調用失敗時拋出異常
        """
        # 延遲初始化 LLM 服務
        if self.llm_service is None:
            try:
                self.llm_service = LLMService(provider="openai", model="gpt-4o")
                logger.info("LLM 服務初始化成功")
            except Exception as e:
                logger.error(f"LLM 服務初始化失敗: {str(e)}")
                raise

        # 定義欄位 schema（包含通用與租賃合約欄位）
        schema = {
            # 通用合約欄位
            "contract_number": "合約編號/合約字號",
            "signing_date": "簽訂日期/立約日期",
            "effective_date": "生效日期",
            "party_a": "甲方/第一方/賣方名稱",
            "party_b": "乙方/第二方/買方名稱",
            "party_a_address": "甲方地址",
            "party_b_address": "乙方地址",
            "contract_amount": "合約金額（只提取數字，不含幣別）",
            "currency": "幣別（例如：TWD, USD, 新台幣）",
            "payment_method": "付款方式",
            "payment_deadline": "付款期限",

            # 租賃合約專屬欄位
            "date_start": "租期起始日/起租日",
            "date_end": "租期結束日/租期終止日",
            "monthly_rent": "月租金（只提取數字，不含幣別）",
            "deposit": "押金/保證金（只提取數字，不含幣別）",
            "rental_address": "租賃標的地址/房屋坐落地址",
            "tenant_name": "承租人姓名/房客姓名",
            "tenant_id_number": "承租人身分證字號或統一編號",
            "tenant_phone": "承租人電話/手機號碼",
            "landlord_name": "出租人姓名/房東姓名",
            "landlord_id_number": "出租人身分證字號或統一編號",
            "landlord_phone": "出租人電話/手機號碼",
            "management_fee": "管理費（只提取數字，不含幣別）",
            "parking_fee": "停車費（只提取數字，不含幣別）",
            "payment_day": "租金繳納日（例如：每月5日、月初、月底）",
        }

        logger.debug("調用 LLMService 提取合約欄位")

        try:
            # 使用 LLMService 進行結構化提取
            fields = await self.llm_service.structured_extraction(
                text=text,
                image_data=image_data,
                schema=schema,
                context="合約"
            )

            logger.info(f"LLM 成功提取 {len([v for v in fields.values() if v])} 個欄位")

            return fields

        except Exception as e:
            logger.error(f"LLM 提取失敗: {str(e)}")
            raise

    def _merge_fields(
        self,
        regex_fields: Dict[str, Optional[str]],
        llm_fields: Dict[str, Optional[str]]
    ) -> Dict[str, Optional[str]]:
        """
        合併正則提取與 LLM 提取的結果

        合併策略：
        - LLM 提取的非 None 欄位優先覆蓋正則結果
        - 保留正則提取成功但 LLM 未提取的欄位
        - 對於 LLM 提取為 None 的欄位，保留正則結果

        Args:
            regex_fields: 正則提取的欄位
            llm_fields: LLM 提取的欄位

        Returns:
            合併後的欄位字典
        """
        # 從正則結果開始
        merged = regex_fields.copy()

        # LLM 提取的非 None 欄位覆蓋正則結果
        for field_name, llm_value in llm_fields.items():
            if llm_value is not None and llm_value != "":
                merged[field_name] = llm_value
                logger.debug(f"欄位 {field_name} 使用 LLM 提取結果")

        return merged

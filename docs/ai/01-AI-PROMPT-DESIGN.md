# AI Document Intelligence Demo - AI Prompt 設計文檔

## 1. Prompt 設計原則

### 1.1 核心原則

1. **明確性**：清楚說明任務目標
2. **結構化**：要求 JSON 格式輸出，便於解析
3. **範例驅動**：提供明確的輸出範例
4. **錯誤處理**：指示 AI 如何處理無法辨識的情況
5. **繁體中文優先**：處理台灣文件，使用繁體中文

### 1.2 AI 模型選擇

| 任務 | 推薦模型 | 理由 |
|------|---------|------|
| 文件分類 | GPT-4o-mini / Claude 3.5 Haiku | 成本低，速度快，準確率高 |
| 欄位抽取 | GPT-4o / Claude 3.5 Sonnet | 準確率高，理解複雜文件 |
| 摘要生成 | GPT-4o-mini / Claude 3.5 Haiku | 速度快，成本低 |
| 風險檢測 | GPT-4o-mini | 邏輯判斷能力強 |
| 問答對話 | GPT-4o / Claude 3.5 Sonnet | 回答品質高，上下文理解好 |

---

## 2. 文件分類 Prompt

### 2.1 任務說明

判斷文件屬於哪一類型：
- 租賃合約（lease_contract）
- 修繕報價單（repair_quote）
- 身分證（id_card）
- 未知（unknown）

### 2.2 Prompt 模板

```
你是一個專業的文件分類助手。請根據以下 OCR 辨識的文件內容，判斷這是哪一種文件類型。

## 支援的文件類型

1. **lease_contract** (租賃合約)
   - 特徵：包含「租賃契約」、「出租人」、「承租人」、「租金」、「押金」、「租期」等關鍵字
   - 通常是多頁 PDF 或掃描檔

2. **repair_quote** (修繕報價單)
   - 特徵：包含「報價單」、「估價單」、「廠商」、「金額」、「項目」、「維修」等關鍵字
   - 通常是單頁文件

3. **id_card** (身分證)
   - 特徵：包含「身分證」、「姓名」、「出生」、「證號」等關鍵字
   - 格式固定，有照片

4. **unknown** (無法識別)
   - 不屬於以上任何類型

## 文件內容（OCR 結果）

```
{OCR_TEXT}
```

## 輸出要求

請以 JSON 格式回覆，包含以下欄位：

{
  "doc_type": "文件類型代碼（lease_contract / repair_quote / id_card / unknown）",
  "confidence": 信心度（0-100 的數字），
  "reasoning": "判斷理由（1-2 句話說明為何判斷為此類型）"
}

## 注意事項

- 只回傳 JSON，不要包含其他文字
- 如果無法判斷，請設定為 unknown，confidence 設為較低值
- 信心度計算應考慮關鍵字出現次數與文件結構
```

### 2.3 實際範例

**範例 1：租賃合約**

```json
{
  "doc_type": "lease_contract",
  "confidence": 95,
  "reasoning": "文件包含「租賃契約書」標題，明確列出出租人、承租人、租金、押金及租期等租賃合約必要資訊"
}
```

**範例 2：報價單**

```json
{
  "doc_type": "repair_quote",
  "confidence": 92,
  "reasoning": "文件標題為「維修報價單」，包含廠商名稱、報價項目及金額，符合報價單特徵"
}
```

**範例 3：身分證**

```json
{
  "doc_type": "id_card",
  "confidence": 98,
  "reasoning": "文件包含「中華民國身分證」字樣，有標準的姓名、身分證字號、出生日期欄位"
}
```

---

## 3. 欄位抽取 Prompt

### 3.1 租賃合約抽取

```
你是一個專業的租賃合約資料抽取助手。請從以下租賃合約的 OCR 文字中，抽取關鍵欄位資訊。

## 文件內容（OCR 結果）

```
{OCR_TEXT}
```

## 需要抽取的欄位

請抽取以下欄位（如果文件中沒有，請設為 null）：

1. **landlord_name** (出租人姓名) - String
2. **tenant_name** (承租人姓名) - String
3. **address** (租賃地址) - String
4. **rent** (月租金) - Number（僅數字，不含單位）
5. **deposit** (押金) - Number（僅數字，不含單位）
6. **lease_start** (租期開始日) - String (格式：YYYY-MM-DD)
7. **lease_end** (租期結束日) - String (格式：YYYY-MM-DD)
8. **contract_date** (合約簽訂日期) - String (格式：YYYY-MM-DD)

## 輸出格式

請以 JSON 格式回覆：

{
  "landlord_name": "出租人姓名",
  "tenant_name": "承租人姓名",
  "address": "完整地址",
  "rent": 25000,
  "deposit": 50000,
  "lease_start": "2026-01-01",
  "lease_end": "2026-12-31",
  "contract_date": "2025-12-15"
}

## 注意事項

- 只回傳 JSON，不要包含其他文字
- 金額欄位請轉換為純數字（去除「元」、「NT$」等單位）
- 日期統一轉換為 YYYY-MM-DD 格式（民國年請轉換為西元年）
- 如果某欄位找不到，請設為 null
- 如果有多個可能值，選擇最可能正確的那個
- 地址請完整抽取，包含縣市、區、路段、號碼
```

**輸出範例：**

```json
{
  "landlord_name": "張三",
  "tenant_name": "王小明",
  "address": "台北市中山區南京東路二段100號5樓",
  "rent": 25000,
  "deposit": 50000,
  "lease_start": "2026-01-01",
  "lease_end": "2026-12-31",
  "contract_date": "2025-12-15"
}
```

### 3.2 修繕報價單抽取

```
你是一個專業的報價單資料抽取助手。請從以下報價單的 OCR 文字中，抽取關鍵欄位資訊。

## 文件內容（OCR 結果）

```
{OCR_TEXT}
```

## 需要抽取的欄位

請抽取以下欄位（如果文件中沒有，請設為 null）：

1. **vendor_name** (廠商名稱) - String
2. **quote_date** (報價日期) - String (格式：YYYY-MM-DD)
3. **amount** (報價金額) - Number（總金額，僅數字）
4. **item_summary** (項目摘要) - String（主要維修/工程項目，1-2 句話概括）

## 輸出格式

請以 JSON 格式回覆：

{
  "vendor_name": "廠商名稱",
  "quote_date": "2026-03-10",
  "amount": 5000,
  "item_summary": "冷氣機維修更換壓縮機"
}

## 注意事項

- 只回傳 JSON，不要包含其他文字
- 金額欄位請轉換為純數字（去除「元」、「NT$」等單位）
- 如果有多個項目，item_summary 請整合成簡短摘要
- 日期統一轉換為 YYYY-MM-DD 格式（民國年請轉換為西元年）
- 如果某欄位找不到，請設為 null
```

**輸出範例：**

```json
{
  "vendor_name": "大安水電工程行",
  "quote_date": "2026-03-10",
  "amount": 5000,
  "item_summary": "冷氣機維修，更換壓縮機及清洗濾網"
}
```

### 3.3 身分證抽取

```
你是一個專業的身分證資料抽取助手。請從以下身分證的 OCR 文字中，抽取關鍵欄位資訊。

## 文件內容（OCR 結果）

```
{OCR_TEXT}
```

## 需要抽取的欄位

請抽取以下欄位（如果文件中沒有，請設為 null）：

1. **name** (姓名) - String
2. **national_id** (身分證字號) - String（格式：1 個英文字母 + 9 個數字）
3. **birth_date** (出生日期) - String (格式：YYYY-MM-DD)

## 輸出格式

請以 JSON 格式回覆：

{
  "name": "王小明",
  "national_id": "A123456789",
  "birth_date": "1990-05-15"
}

## 注意事項

- 只回傳 JSON，不要包含其他文字
- 身分證字號必須是 1 個英文字母 + 9 個數字
- 日期統一轉換為 YYYY-MM-DD 格式（民國年請轉換為西元年）
- 如果某欄位找不到或格式不正確，請設為 null
```

**輸出範例：**

```json
{
  "name": "王小明",
  "national_id": "A123456789",
  "birth_date": "1990-05-15"
}
```

---

## 4. 摘要生成 Prompt

```
你是一個專業的文件摘要助手。請根據以下文件資訊，生成一段簡潔的摘要（3-5 行）。

## 文件類型

{DOC_TYPE}

## 抽取的欄位資料

```json
{EXTRACTED_DATA}
```

## OCR 原文（參考用）

```
{OCR_TEXT}
```

## 輸出要求

請生成一段 **3-5 行** 的中文摘要，涵蓋文件的核心資訊。

### 租賃合約摘要範例

承租人王小明承租位於台北市中山區南京東路二段100號5樓的房屋，月租金25,000元，押金50,000元。租期自2026年1月1日至2026年12月31日，為期一年。合約於2025年12月15日簽訂。

### 報價單摘要範例

大安水電工程行於2026年3月10日提供報價，針對冷氣機維修更換壓縮機及清洗濾網，總報價金額5,000元。

### 身分證摘要範例

此為王小明的中華民國身分證，證號A123456789，出生日期為1990年5月15日。

## 注意事項

- 只回傳摘要文字，不要包含標題或其他格式
- 使用繁體中文
- 語句流暢自然
- 涵蓋最重要的資訊
```

---

## 5. 風險檢測 Prompt（P2）

```
你是一個專業的文件風險檢測助手。請檢查以下文件抽取結果，找出可能的風險或異常。

## 文件類型

{DOC_TYPE}

## 抽取的欄位資料

```json
{EXTRACTED_DATA}
```

## 檢測項目

請檢測以下風險：

### 租賃合約
- 缺少必要欄位（出租人、承租人、租金、押金、租期）
- 租金或押金為 0 或異常低
- 租期開始日期晚於結束日期
- 租期已過期
- 押金低於兩個月租金（台灣慣例）

### 報價單
- 缺少必要欄位（廠商、金額、日期）
- 金額為 0
- 報價日期異常（未來日期或過於久遠）

### 身分證
- 缺少必要欄位（姓名、證號、生日）
- 證號格式錯誤
- 年齡異常（例如超過 120 歲）

## 輸出格式

請以 JSON 陣列格式回覆（如果沒有風險，回傳空陣列 []）：

[
  {
    "type": "missing_field",
    "field": "landlord_name",
    "severity": "warning",
    "message": "缺少出租人姓名"
  },
  {
    "type": "abnormal_value",
    "field": "deposit",
    "severity": "warning",
    "message": "押金金額偏低，建議確認是否正確"
  }
]

## severity 等級

- **error**: 嚴重錯誤（例如格式錯誤、必填欄位缺失）
- **warning**: 警告（例如值異常、不符慣例）
- **info**: 提示（例如建議補充資訊）

## 注意事項

- 只回傳 JSON 陣列，不要包含其他文字
- 如果沒有任何風險，請回傳 []
- 每個風險都要包含清楚的描述訊息
```

**輸出範例：**

```json
[
  {
    "type": "missing_field",
    "field": "contract_date",
    "severity": "warning",
    "message": "缺少合約簽訂日期"
  },
  {
    "type": "abnormal_value",
    "field": "deposit",
    "severity": "info",
    "message": "押金為一個月租金，低於台灣常見的兩個月押金，建議確認"
  }
]
```

---

## 6. 問答對話 Prompt

```
你是一個專業的文件問答助手。請根據以下文件內容，回答使用者的問題。

## 文件類型

{DOC_TYPE}

## 抽取的欄位資料

```json
{EXTRACTED_DATA}
```

## 文件摘要

{SUMMARY}

## OCR 原文（參考用）

```
{OCR_TEXT}
```

## 使用者問題

{USER_QUESTION}

## 回答要求

1. **優先使用抽取的欄位資料**回答
2. 如果欄位資料中找不到答案，再參考 OCR 原文
3. 如果完全找不到相關資訊，請明確說明「此文件中未找到相關資訊」
4. 回答要簡潔明確，不要過度解釋
5. 使用繁體中文回答
6. 如果問題涉及計算（例如「幾歲」），請進行計算後回答

## 回答範例

### 問題：這份租約的租金是多少？
回答：根據此租賃契約，月租金為 25,000 元。

### 問題：承租人是誰？
回答：承租人為王小明。

### 問題：出租人的電話號碼是多少？
回答：抱歉，此文件中未找到出租人的電話號碼資訊。

### 問題：這個人幾歲？
回答：根據出生日期 1990年5月15日 推算，目前約 35 歲（以 2026 年計算）。

## 注意事項

- 不要捏造不存在的資訊
- 如果資訊不確定，請說明「可能是...」或「疑似為...」
- 對於金額、日期等重要資訊，請保持精確
```

---

## 7. Prompt 優化技巧

### 7.1 提高準確率

1. **Few-shot Learning**：在 prompt 中加入 2-3 個範例
2. **Chain-of-Thought**：要求 AI 說明推理過程
3. **格式驗證**：要求輸出嚴格遵守 JSON Schema

### 7.2 降低成本

1. 文件分類使用較小模型（GPT-4o-mini）
2. 摘要生成不需最強模型
3. 只在欄位抽取使用 GPT-4o

### 7.3 錯誤處理

1. 設定 `max_tokens` 避免超長回應
2. 使用 `temperature: 0` 提高穩定性
3. 解析失敗時重試 1 次

---

## 8. API 調用範例

### 8.1 OpenAI Python SDK

```python
# app/lib/ai_client.py
import json
import os
from openai import AsyncOpenAI

# 初始化 OpenAI 客戶端
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def classify_document(ocr_text: str) -> dict:
    """文件分類 - 使用 GPT-4o-mini"""
    from app.prompts.classification import CLASSIFICATION_PROMPT

    prompt = CLASSIFICATION_PROMPT.format(ocr_text=ocr_text)

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "你是一個專業的文件分類助手。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        max_tokens=500,
        response_format={"type": "json_object"}  # 強制 JSON 輸出
    )

    result = json.loads(response.choices[0].message.content)
    return result


async def extract_fields(doc_type: str, ocr_text: str) -> dict:
    """欄位抽取 - 使用 GPT-4o"""
    from app.prompts import extraction

    # 根據文件類型選擇 prompt
    prompt_map = {
        "lease_contract": extraction.LEASE_CONTRACT_PROMPT,
        "repair_quote": extraction.REPAIR_QUOTE_PROMPT,
        "id_card": extraction.ID_CARD_PROMPT
    }

    prompt_template = prompt_map.get(doc_type)
    if not prompt_template:
        raise ValueError(f"Unsupported document type: {doc_type}")

    prompt = prompt_template.format(ocr_text=ocr_text)

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "你是一個專業的資料抽取助手。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        max_tokens=1000,
        response_format={"type": "json_object"}
    )

    result = json.loads(response.choices[0].message.content)
    return result


async def generate_summary(doc_type: str, extracted_data: dict, ocr_text: str) -> str:
    """生成摘要 - 使用 GPT-4o-mini"""
    from app.prompts.summary import SUMMARY_PROMPT

    prompt = SUMMARY_PROMPT.format(
        doc_type=doc_type,
        extracted_data=json.dumps(extracted_data, ensure_ascii=False, indent=2),
        ocr_text=ocr_text
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "你是一個專業的文件摘要助手。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        max_tokens=300
    )

    return response.choices[0].message.content


async def chat_with_document(
    doc_type: str,
    extracted_data: dict,
    summary: str,
    ocr_text: str,
    user_question: str
) -> str:
    """AI 問答 - 使用 GPT-4o"""
    from app.prompts.chat import CHAT_PROMPT

    prompt = CHAT_PROMPT.format(
        doc_type=doc_type,
        extracted_data=json.dumps(extracted_data, ensure_ascii=False, indent=2),
        summary=summary,
        ocr_text=ocr_text,
        user_question=user_question
    )

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "你是一個專業的文件問答助手。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        max_tokens=500
    )

    return response.choices[0].message.content
```

### 8.2 Anthropic Claude Python SDK

```python
# app/lib/claude_client.py
import json
import os
from anthropic import AsyncAnthropic

# 初始化 Claude 客戶端
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def classify_document(ocr_text: str) -> dict:
    """使用 Claude 3.5 Haiku 進行文件分類"""
    from app.prompts.classification import CLASSIFICATION_PROMPT

    prompt = CLASSIFICATION_PROMPT.format(ocr_text=ocr_text)

    response = await client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=500,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    result = json.loads(response.content[0].text)
    return result


async def extract_fields(doc_type: str, ocr_text: str) -> dict:
    """使用 Claude 3.5 Sonnet 進行欄位抽取"""
    from app.prompts import extraction

    prompt_map = {
        "lease_contract": extraction.LEASE_CONTRACT_PROMPT,
        "repair_quote": extraction.REPAIR_QUOTE_PROMPT,
        "id_card": extraction.ID_CARD_PROMPT
    }

    prompt_template = prompt_map.get(doc_type)
    if not prompt_template:
        raise ValueError(f"Unsupported document type: {doc_type}")

    prompt = prompt_template.format(ocr_text=ocr_text)

    response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    result = json.loads(response.content[0].text)
    return result
```

### 8.3 實際使用範例

```python
# app/services/document_service.py
from app.lib.ai_client import classify_document, extract_fields, generate_summary

async def process_document_with_ai(ocr_text: str) -> dict:
    """完整的 AI 處理流程"""

    # 1. 文件分類
    classification = await classify_document(ocr_text)
    doc_type = classification["doc_type"]
    confidence = classification["confidence"]

    # 2. 欄位抽取
    extracted_data = await extract_fields(doc_type, ocr_text)

    # 3. 生成摘要
    summary = await generate_summary(doc_type, extracted_data, ocr_text)

    return {
        "doc_type": doc_type,
        "confidence": confidence,
        "extracted_data": extracted_data,
        "summary": summary
    }
```

---

## 9. Prompt 測試與評估

### 9.1 測試資料集

準備 10-15 份測試文件：
- 5 份租賃合約
- 5 份報價單
- 3 份身分證
- 2 份其他文件（測試 unknown 分類）

### 9.2 評估指標

| 任務 | 評估指標 | 目標值 |
|------|---------|--------|
| 文件分類 | 準確率 | > 90% |
| 欄位抽取 | 欄位準確率 | > 80% |
| 摘要生成 | 人工評分（1-5） | > 4.0 |
| 風險檢測 | 召回率 | > 75% |

### 9.3 迭代優化

1. 收集錯誤案例
2. 分析失敗原因
3. 調整 prompt
4. 重新測試
5. 記錄改進效果

---

## 10. Prompt 版本管理

### 10.1 Prompt 檔案結構（Python）

```
backend/app/prompts/
├── __init__.py            # Package 初始化
├── classification.py      # 文件分類
├── extraction.py          # 欄位抽取（所有類型）
├── summary.py             # 摘要生成
├── risk_detection.py      # 風險檢測
└── chat.py                # 問答對話
```

**實際檔案參考：**
- `/backend/app/prompts/classification.py` - 已實作
- `/backend/app/prompts/extraction.py` - 已實作
- `/backend/app/prompts/summary.py` - 已實作
- `/backend/app/prompts/chat.py` - 已實作

### 10.2 版本紀錄（Python）

```python
# app/prompts/classification.py

# 版本 1 - 初始版本
CLASSIFICATION_PROMPT_V1 = """
你是一個專業的文件分類助手...
（初始版本內容）
"""

# 版本 2 - 改進版（提高準確率）
CLASSIFICATION_PROMPT_V2 = """
你是一個專業的文件分類助手...
（改進版內容，加入更多範例）
"""

# 當前使用版本
CLASSIFICATION_PROMPT = CLASSIFICATION_PROMPT_V2
```

### 10.3 Prompt 模板範例

```python
# app/prompts/extraction.py

LEASE_CONTRACT_PROMPT = """
你是一個專業的租賃合約資料抽取助手。請從以下租賃合約的 OCR 文字中，抽取關鍵欄位資訊。

## 文件內容（OCR 結果）

```
{ocr_text}
```

## 需要抽取的欄位
...（完整 prompt 內容）
"""

# 使用 Python 的 str.format() 或 f-string
def get_extraction_prompt(ocr_text: str) -> str:
    return LEASE_CONTRACT_PROMPT.format(ocr_text=ocr_text)
```

---

## 11. 開發檢查清單

### 11.1 基礎 Prompts（P0）

- [ ] 文件分類 Prompt
- [ ] 租約欄位抽取 Prompt
- [ ] 報價單欄位抽取 Prompt
- [ ] 身分證欄位抽取 Prompt
- [ ] JSON 輸出解析

### 11.2 AI 功能（P1）

- [ ] 摘要生成 Prompt
- [ ] 問答對話 Prompt
- [ ] 上下文整合

### 11.3 進階功能（P2）

- [ ] 風險檢測 Prompt
- [ ] 信心度評估優化
- [ ] Few-shot 範例整合

---

**文檔版本**: v1.0
**最後更新**: 2026-03-17
**負責人**: AI Team

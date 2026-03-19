"""
Document Classification Prompt
"""

CLASSIFICATION_PROMPT = """你是一個專業的文件分類助手。請根據以下 OCR 提取的文字內容，判斷文件類型。

文件內容：
{ocr_text}

---

請判斷這是以下哪一種文件類型：
1. lease_contract - 租賃合約（包含房東、租客、租金、租期等資訊）
2. repair_quote - 修繕報價單（包含廠商、項目、金額等資訊）
3. id_card - 身分證（包含姓名、身分證字號、出生日期等資訊）
4. unknown - 無法識別或其他類型

請以 JSON 格式回答，包含以下欄位：
- doc_type: 文件類型代碼
- confidence: 信心度 (0-100)
- reasoning: 判斷理由（簡短說明）

範例：
{{
  "doc_type": "lease_contract",
  "confidence": 95,
  "reasoning": "文件包含租賃雙方姓名、租金、租期等典型租約要素"
}}
"""

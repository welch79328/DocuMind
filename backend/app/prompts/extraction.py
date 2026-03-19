"""
Field Extraction Prompts
"""

LEASE_CONTRACT_EXTRACTION_PROMPT = """你是一個專業的租賃合約資訊抽取助手。請從以下 OCR 文字中抽取關鍵欄位。

文件內容：
{ocr_text}

---

請抽取以下欄位（若找不到則填 null）：
- landlord_name: 房東姓名
- tenant_name: 租客姓名
- address: 租賃地址
- rent: 月租金（數字）
- deposit: 押金（數字）
- lease_start: 租期起始日（YYYY-MM-DD 格式）
- lease_end: 租期結束日（YYYY-MM-DD 格式）
- contract_date: 合約簽訂日期（YYYY-MM-DD 格式）

請以 JSON 格式回答。

範例：
{{
  "landlord_name": "張三",
  "tenant_name": "王小明",
  "address": "台北市中山區XX路XX號",
  "rent": 25000,
  "deposit": 50000,
  "lease_start": "2026-01-01",
  "lease_end": "2026-12-31",
  "contract_date": "2025-12-15"
}}
"""

REPAIR_QUOTE_EXTRACTION_PROMPT = """你是一個專業的報價單資訊抽取助手。請從以下 OCR 文字中抽取關鍵欄位。

文件內容：
{ocr_text}

---

請抽取以下欄位（若找不到則填 null）：
- vendor_name: 廠商名稱
- quote_date: 報價日期（YYYY-MM-DD 格式）
- valid_until: 報價有效期限（YYYY-MM-DD 格式）
- items: 報價項目清單（陣列）
  - description: 項目描述
  - quantity: 數量
  - unit_price: 單價
  - total: 小計
- total_amount: 總金額（數字）
- notes: 備註

請以 JSON 格式回答。

範例：
{{
  "vendor_name": "XX水電工程行",
  "quote_date": "2026-01-15",
  "valid_until": "2026-02-15",
  "items": [
    {{"description": "更換水龍頭", "quantity": 2, "unit_price": 1500, "total": 3000}},
    {{"description": "修理馬桶", "quantity": 1, "unit_price": 2000, "total": 2000}}
  ],
  "total_amount": 5000,
  "notes": "含材料費"
}}
"""

ID_CARD_EXTRACTION_PROMPT = """你是一個專業的身分證資訊抽取助手。請從以下 OCR 文字中抽取關鍵欄位。

文件內容：
{ocr_text}

---

請抽取以下欄位（若找不到則填 null）：
- name: 姓名
- national_id: 身分證字號
- birth_date: 出生日期（YYYY-MM-DD 格式）
- gender: 性別（男/女）
- issue_date: 發證日期（YYYY-MM-DD 格式）
- address: 戶籍地址

請以 JSON 格式回答。

範例：
{{
  "name": "王小明",
  "national_id": "A123456789",
  "birth_date": "1990-05-15",
  "gender": "男",
  "issue_date": "2015-03-01",
  "address": "台北市中正區XX路XX號"
}}
"""


def get_extraction_prompt(doc_type: str, ocr_text: str) -> str:
    """Get extraction prompt based on document type"""
    prompts = {
        "lease_contract": LEASE_CONTRACT_EXTRACTION_PROMPT,
        "repair_quote": REPAIR_QUOTE_EXTRACTION_PROMPT,
        "id_card": ID_CARD_EXTRACTION_PROMPT,
    }

    prompt_template = prompts.get(doc_type)
    if not prompt_template:
        return f"無法識別的文件類型：{doc_type}，請返回空 JSON 物件 {{}}"

    return prompt_template.format(ocr_text=ocr_text)

"""
Field Extraction Prompts
"""

LEASE_CONTRACT_EXTRACTION_PROMPT = """你是一個專業的租賃合約資訊抽取助手。請從以下 OCR 文字中抽取關鍵欄位。

這是一份完整的住宅租賃契約書，包含多個頁面。請仔細閱讀**所有頁面**（特別是最後幾頁通常包含當事人詳細資料）。

文件內容：
{ocr_text}

---

請抽取以下欄位（若找不到則填 null）：

**基本資訊：**
- landlord_name: 房東姓名/公司名稱
- landlord_id: 房東統一編號或身分證字號
- landlord_address: 房東設籍地址或公司地址
- landlord_contact_address: 房東通訊地址
- landlord_phone: 房東聯絡電話
- landlord_email: 房東電子郵件
- manager_name: 經理人姓名（如有）
- manager_phone: 經理人聯絡電話（如有）
- agent_name: 不動產經紀人姓名（如有）
- agent_license: 不動產經紀人證號（如有）
- property_manager_name: 租賃住宅管理人員姓名（如有）
- property_manager_license: 租賃住宅管理證號（如有）

- tenant_name: 租客姓名
- tenant_id: 租客身分證字號或統一編號
- tenant_registered_address: 租客設籍地址
- tenant_contact_address: 租客通訊地址
- tenant_phone: 租客聯絡電話
- tenant_email: 租客電子郵件

- address: 租賃地址（完整地址）
- rent: 月租金（數字）
- deposit: 押金（數字）
- lease_start: 租期起始日（YYYY-MM-DD 格式）
- lease_end: 租期結束日（YYYY-MM-DD 格式）
- contract_date: 合約簽訂日期（YYYY-MM-DD 格式）

**費用分擔（由租客負擔則填 "tenant"，房東負擔則填 "landlord"）：**
- management_fee_payer: 管理費負擔方
- water_fee_payer: 水費負擔方
- electricity_fee_payer: 電費負擔方
- gas_fee_payer: 瓦斯費負擔方
- internet_fee_payer: 網路費負擔方

**重要條款：**
- repair_responsibility: 修繕責任說明（簡述誰負責什麼）
- early_termination_notice: 提前終止需提前幾天通知
- early_termination_penalty: 提前終止違約金（幾個月租金）
- special_terms: 特殊約定事項（陣列，如有多項請列出）

**附件清單：**
- attachments: 合約附件列表（陣列，例如：附件A、附件B等）

**其他資訊：**
- guarantor_name: 保證人姓名（如有）
- parking_space: 停車位資訊（如有，描述車位類型和編號）
- notarized: 是否辦理公證（true/false）

請以 JSON 格式回答。務必從**所有頁面**中提取資訊。

**重要提醒：**
- 請務必從 OCR 文字內容中提取真實資訊，不要使用範例中的數值
- 範例僅供格式參考，實際值必須從文件中提取
- 特別注意文件後半部分通常包含詳細的聯絡資訊

範例格式（數值僅供參考，請從文件中提取真實值）：
{{
  "landlord_name": "XX物業管理股份有限公司",
  "landlord_id": "12345678",
  "landlord_address": "台北市XX區XX路XX號",
  "landlord_contact_address": "台北市XX區XX路XX號",
  "landlord_phone": "02-12345678",
  "landlord_email": "landlord@example.com",
  "manager_name": "王經理",
  "manager_phone": "0912-345-678",
  "agent_name": "張仲介",
  "agent_license": "(XXX)北市經字第XXXXX號",
  "property_manager_name": "李管理員",
  "property_manager_license": "(XXX)登字第XXXXXX號",

  "tenant_name": "陳小明",
  "tenant_id": "B234567890",
  "tenant_registered_address": "新北市XX區XX路XX號",
  "tenant_contact_address": "新北市XX區XX路XX號",
  "tenant_phone": "0987-654-321",
  "tenant_email": "tenant@example.com",

  "address": "台北市大安區XX路XX號XX樓",
  "rent": 30000,
  "deposit": 60000,
  "lease_start": "2025-03-01",
  "lease_end": "2026-02-28",
  "contract_date": "2025-02-15",

  "management_fee_payer": "landlord",
  "water_fee_payer": "tenant",
  "electricity_fee_payer": "tenant",
  "gas_fee_payer": "tenant",
  "internet_fee_payer": "tenant",

  "repair_responsibility": "房東負責結構及設備修繕，租客負責日常維護",
  "early_termination_notice": 30,
  "early_termination_penalty": 1,
  "special_terms": ["不得轉租", "遵守社區規約"],

  "attachments": ["附件A：現況確認書", "附件B：設備清單", "附件C：其他"],

  "guarantor_name": "陳大明",
  "parking_space": "地下2樓機械式停車位，編號B-456",
  "notarized": true
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

**注意：OCR 文字可能有嚴重識別錯誤，請盡力推斷正確資訊。**

文件內容：
{ocr_text}

---

請抽取以下欄位（若找不到或完全無法推斷則填 null）：
- name: 姓名（2-4 個中文字）
- national_id: 身分證字號（格式：1個英文字母+9個數字，如 A123456789）
- birth_date: 出生日期（YYYY-MM-DD 格式，**民國年請轉換為西元年：民國年+1911**）
- gender: 性別（只能是「男」或「女」）
- issue_date: 發證日期或換發日期（YYYY-MM-DD 格式，**民國年請轉換為西元年**）

**OCR 錯誤處理：**
1. **姓名欄位**：
   - OCR 可能將姓名周圍的標籤文字（如「姓名」「軋址名」）誤讀在一起
   - 可能包含標點符號（如「陳 徐、玲」）或無意義字元（如「吧|三多陳 徐、玲點讓讓」）
   - **請從中提取連續的 2-4 個合理中文姓名字元**（如從「陳 徐、玲」提取「陳徐玲」）
   - 只有在**完全無法找到任何中文姓名字元**時才填 null

2. **身分證字號**：
   - 必須嚴格符合格式（1英文+9數字），否則填 null
   - 常見錯誤：字母 "O"(大寫o) 可能是數字 "0"，字母 "l"(小寫L) 可能是數字 "1"

3. **日期欄位**：
   - 尋找「民國XX年X月X日」格式
   - 「換發」「發證」附近是發證日期，「出生」「生年月日」附近是出生日期
   - 轉換公式：民國年 + 1911 = 西元年

4. **性別欄位**：
   - 尋找「男」或「女」字元
   - 可能出現在「性別」標籤附近

**重要提示：**
- 台灣身分證正面沒有地址資訊
- **OCR 錯誤很常見，請盡力從雜亂文字中推斷正確資訊**
- 如果能在文字中找到姓名線索（即使有干擾字元），也應該提取出來
- 日期轉換範例：民國94年 = 2005年 (94+1911)、民國5年 = 1916年 (5+1911)

請以 JSON 格式回答。

範例：
{{
  "name": "陳小華",
  "national_id": "B234567890",
  "birth_date": "1995-08-20",
  "gender": "女",
  "issue_date": "2020-06-15"
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

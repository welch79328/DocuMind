# 標註資料存放與版控規範

> 對應規格:`.kiro/specs/ocr-vlm-consensus/` 需求 1.9(任務 1.1)

本規範定義 OCR 準確率評估所需的**標註成果**與**標註對象**如何存放,確保人力投入的標註不會因版控排除而遺失,同時避免含個資的原始文件進入版本控制。

---

## 核心原則

| 類別 | 說明 | 是否進版控 | 存放位置 |
|---|---|---|---|
| **標註成果** | 人工標註的 ground truth JSON | ✅ **是** | `backend/tests_all/fixtures/` |
| **標註對象** | 原始謄本/合約 PDF、影像(含個資) | ❌ **否** | `data/`(gitignored) |

**理由**:標註成果是人力投入的產物,遺失即需重做;其內容雖引用檔名,但不含完整個資影像。標註對象為真實文件,含姓名、統一編號、地址等個資,不得進入版本控制。

---

## 單一真相來源(Source of Truth)

標註成果的唯一權威位置為:

```
backend/tests_all/fixtures/
├── ground_truth.json              # 建物土地謄本標註
└── contract_ground_truth.json     # 合約標註
```

此路徑**未被 `.gitignore` 排除**,故一律納入版本控制。

### 不得作為標註來源的路徑

`.gitignore` 以 `/data/` 與 `/tests/` 排除了根目錄下兩個目錄:

- `data/` — 標註對象存放處(正確用途),**不得**存放標註成果
- `tests/` — 早期遺留的本機工作區,其中的 `fixtures/`、`benchmarks/` 為 `backend/tests_all/` 的舊副本

> ⚠️ 根目錄 `tests/` 底下的任何標註或基準檔案皆**非權威版本**。若在該處看到 ground truth 或 baseline 檔案,一律以 `backend/tests_all/` 為準,不要在該處編輯標註。

---

## 標註檔格式

### 謄本(`ground_truth.json`)

以檔名為鍵,每份文件一個物件:

```jsonc
{
  "建物謄本.jpg": {
    "document_type": "building_transcript",
    "full_text": "...",              // 全文標註(供 CER 計算)
    "key_fields": {                   // 關鍵欄位標註(供欄位準確率計算)
      "land_number": "0231-0000",
      "area": 105.0
    },
    "metadata": { "pages": 1, "format": "jpg" }
  },
  "annotation_metadata": { }          // 保留鍵:標註者、日期等,不視為文件
}
```

### 合約(`contract_ground_truth.json`)

標註集中於 `contracts` 物件下,並以 `critical_fields` 宣告關鍵欄位:

```jsonc
{
  "description": "合約欄位提取標註資料 (Ground Truth)",
  "critical_fields": ["contract_number", "party_a", "party_b", "contract_amount"],
  "contracts": {
    "<檔名>.pdf": {
      "contract_number": null,        // null = 尚未標註
      "party_a": null,
      "currency": "TWD",              // 預設值,非標註成果
      "notes": "需人工標註"
    }
  }
}
```

### 未標註的表示方式

以下值一律視為**尚未標註**,匯入時會被略過並列入回報,不會寫入評估集:

- `null`
- 空字串 `""`
- `"[待標註]"`
- `"需人工標註"`

當檔案宣告了 `critical_fields`,只有**至少一個關鍵欄位已標註**的項目才會被匯入;僅有 `currency` 等預設值的項目視為未標註。

---

## 匯入評估集

標註完成後,以 `AnnotationImporter` 匯入為保留評估集(`CorrectionSample.purpose='holdout'`):

```bash
curl -X POST http://localhost:8000/api/v1/samples/transcript/import \
  -H 'Content-Type: application/json' \
  -d '{"file_path": "backend/tests_all/fixtures/ground_truth.json", "purpose": "holdout"}'
```

回應含 `imported` / `skipped` / `skipped_refs`,未標註項目會出現在 `skipped_refs`。

**資料隔離**:以 `purpose='holdout'` 匯入的樣本僅供評估,`CorrectionSampleService.list_for_fewshot()` 硬性只取 `purpose='train'`,故保留評估集不會回灌 few-shot(防資料洩漏)。

---

## 新增標註時的檢查清單

- [ ] 標註檔寫入 `backend/tests_all/fixtures/`,不是 `tests/` 或 `data/`
- [ ] 原始文件放在 `data/`,未被 `git add`
- [ ] 未標註欄位以 `null` 表示,不要留下假值
- [ ] 執行 `pytest tests/unit/test_annotation_storage_policy.py` 確認規範未被破壞
- [ ] 匯入後檢查 `skipped_refs`,確認略過的都是刻意未標註的項目

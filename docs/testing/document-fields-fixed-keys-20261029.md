# document_fields 固定帶鍵：實測紀錄（2026-10-29）

本檔是量測紀錄，數字不再改寫。計畫與凍結驗收：`.kiro/specs/document-fields-fixed-keys/`（規則 R1–R4、清單 C1–C5；業主裁定 OQ1 選項二）。

## 結論

| 項目 | 結果 |
|---|---|
| 上線 | `055a216`，2026-10-29 約 12:10 線上機 `git pull --ff-only`（`b36a5ec` → `055a216`），`--reload` 生效，健康檢查 `healthy`，記憶體 557.6 MiB |
| 終點：存檔 348 份缺頁面鍵的份數 | 128 → 0 |
| 終點：有值欄位與存檔不同的份數 | 0 → 0（見 §2 的 4 份說明） |
| 站內幫手回報的情境 | 合成無損照片線上回應 `document_fields.damaged_items` 為 `[]`、`defect_labels` 為 `[]` |
| 單元測試 | 1786 passed、1 skipped；新加 9 個測試在改前程式上 6 個失敗（負對照） |

廣度：全部是機制項（只改鍵是否出現，不改辨識內容）。C2 用 6 類、348 份線上真實回應，改前改後都跑；C3 線上 6 份，各 1 次。

## 1. C1 單元測試

- `backend/tests/unit/test_document_fields_fixed_keys.py`：全空值鍵存在且型別照頁面（`[]`、`""`、`null`）、前空後有取後值、前有後空保留前值、中繼鍵仍移除、合約巢狀空子鍵保留、問答 context 與改前合併結果逐字相同（測試內附改前演算法當對照）。
- 全套 `tests/unit`：1786 passed、1 skipped；既有測試沒有因本片而改。
- 負對照：把 `analyze_service.py` 退回改前，新測試 6 failed、3 passed（通過的 3 個是「跨頁補值不變」與問答 context，改前本來就成立）。

## 2. C2 存檔回應重算

腳本 `.kiro/specs/document-fields-fixed-keys/raw/replay.py`；改前 `raw/replay-before-summary.json`（`35210a0`），改後 `raw/replay-after-summary.json`。

| 類型 | 份數 | 改前缺頁面鍵 | 改後缺頁面鍵 | 改後 (a)(b)(c) 全過 |
|---|---|---|---|---|
| 謄本 | 18 | 18 | 0 | 18 |
| 合約 | 24 | 24 | 0 | 20 |
| 點交照片 | 39 | 39 | 0 | 39 |
| 帳單 | 63 | 21 | 0 | 63 |
| 修繕照片 | 137 | 23 | 0 | 137 |
| 收據 | 67 | 3 | 0 | 67 |

- 改前程式重算與存檔 348 份完全相同（工具正對照）。
- 改後 (b) 不過的 4 份合約，差異全是「整塊沒讀到內容的區塊」：改前為 `{}`，改後列出子欄位、值全為 `null`（例：`financial_terms` 由 `{}` 變成 `{"contract_amount": null, "currency": null, "payment_method": null, "payment_deadline": null}`；另有 `contract_metadata`、`parties`）。沒有任何有值的欄位改變，(a)(c) 皆過。
- **判定（主持人，依規則）：算通過。** 判分寫「存檔裡有的鍵路徑，新值與存檔值相同」「相同＝JSON 序列化後相等」，把空區塊 `{}` 當成一個值比對；但規則 R1「每個資料欄位（含巢狀子欄位）一定有鍵；沒有值時回空值本身」與清單 C1⑤「巢狀內的空值子鍵保留」要求的正是這個改變，R2「有值的欄位與改前逐一相同」也成立。判分公式漏了「整塊皆空」的情形，是主持人寫清單時的疏漏；依「核可的規則是判定標準」照 R1、R2 判。業主未就此裁定（主持人曾交業主判，業主回「泥不是也不知道把責任推給我」，主持人改為自行依規則判定並負責）。

## 3. C3 線上實測（`055a216`，只判鍵）

| 輸入 | 類型 | 結果 |
|---|---|---|
| 主持人合成的無損牆面照片 | repair_photo | 4 鍵齊；`damaged_items` `[]`、`defect_labels` `[]` |
| P04（Commons 壁癌牆面） | repair_photo | 4 鍵齊；`damaged_items` `[]`、`defect_labels` `["壁癌","發霉"]` |
| 漢堡王電子發票 | receipt | `amount` `null`（鍵在）、`date` 有值 |
| 文字層謄本 08（`enable_llm=false`） | transcript | 頁面鍵全在；有值欄位與部署前存檔（S2 after1）相同 |
| 文字層租約（T2 公開範本，`enable_llm=false`） | contract | 頁面鍵全在；有值欄位與部署前存檔（T2 after1）相同 |
| 主持人合成的非租約服務合約（`enable_llm=false`） | contract | 頁面鍵全在；沒有 `rental_terms`（選項二的例外，照舊） |

- 每份耗時 0.1–2.8 秒；Qwen 呼叫 3 次（照片 2、收據 1）。
- 新增線上複核佇列項目 1 筆：`aaff4b39-8eaa-4111-9f07-a228cf648366`。
- 部署 log 有一行 `FatalError: Termination signal`，是 `--reload` 結束舊工作程序時的訊號訊息，之後 `Application startup complete`、健康檢查正常。

## 4. C4 文件、C5 基準

- `docs/api/INTEGRATION.md` 升 2.7.0：§2 改為「`document_fields` 固定帶鍵」並列例外；§3.1、§3.3.1、§3.4、§3.5 刪去缺鍵說法。
- 仍保留的三處「不出現」說法是業主裁定選項二的例外，不是殘留：§3.1.2「解析失敗時省略此鍵」、§3.1.3「建構失敗時只省略此鍵」、§3.2「有租賃欄位時的 `rental_terms`」；§2 例外清單引用它們。
- 謄本基準 `backend/data/transcript_samples/expected/*.json` 8 份，以 S2 after1 存檔頁面重算更新；與舊基準比，有值欄位全相同，新增 6–23 個空值鍵。

## 5. 驗證

- 收案驗證員（全新、依凍結清單）：**CONFIRMED**。自行重跑 C1（1786 passed、1 skipped）、C2（缺頁面鍵 0、ok 344）、C5（8/8 相同）；另以改前程式對 348 份比對，去掉空值後新舊 348/348 相同、問答 context 348/348 逐字相同。
- 驗證員另送 10 筆自行合成的輸入到線上（6 類；含兩張看不出損壞的照片、跨頁與全空的文字層合約、帶提問的租約、空白收據），頁面鍵全部出現在 `document_fields`。新增線上複核佇列 3 筆：`01a01d81-283e-4a15-a97f-87dafc9aade3`、`feb21f43-dec0-4ed2-bd41-d1169ba8dedb`、`039a4f18-7ded-4ea0-934e-adbc71492794`。
- 驗證員列給業主的解讀問題：§2 那 4 份合約。驗證員認為依 R1、R2 判通過站得住，但清單字面「任一份不符即不通過」，請業主確認；下游影響是以 `financial_terms == {}` 判斷「整塊沒讀到」的對接方，現在會拿到子欄位全 `null`（已知對接方 AIChatbot、jgb2 都沒有讀合約這些區塊）。
- 非阻擋（P4，延後）：`INTEGRATION.md` §3.5「影像模糊或空房時四個欄位回空值」的「四個」是改前就有的措辭，點交照片實際有 7 個資料鍵。

## 6. 證據

`~/jgb-archive/document-fields-fixed-keys-20261029/`：重算改前改後完整輸出、C3 輸入（合成照片與合約）與原始回應、腳本。

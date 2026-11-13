# 合約帶參數格式 `contract_format=v2`：電子 PDF 值位置（2026-11-13）

計畫：`.kiro/specs/contract-v2-positions/plan.md`。判定基準：同目錄 `acceptance.md`，加上 `acceptance-amend-1.md`。
證據目錄 E＝`~/jgb-archive/contract-v2-positions-20261113/`。

## 1. 改了什麼

- `ContractFieldExtractor._match_fields` 回傳值，並回傳值在正規化文字上的起迄。`_extract_with_regex` 改成只取值。比對邏輯沒有改：樣式相同、順序相同、第一個命中就停。
- 新模組 `contract_positions.apply_contract_format`。帶 `contract_format=v2` 時，`document_fields.rental_terms` 的六欄包成 `{value, position}`（`docs/api/INTEGRATION.md` §3.2.1）。
- `/analyze` 新增 Form 參數 `contract_format`。帶 `v2` 以外的值回 `400 INVALID_CONTRACT_FORMAT`。這一步排在信心度攔截之後，所以複核佇列存的是沒轉換的回應。

## 2. 本機：C1、C2（21 份電子 PDF）

**廣度**：5 組資料，共 21 份，每份 × 6 欄，各跑 1 次；結果是決定性的。
- G1～G3：合成租約，三種版型各 5 份。由不讀程式的代理寫 HTML 與答案鍵，主會話用 PyMuPDF 轉成有文字層的 PDF。
- G4：jgb2 範本 5 份。
- D-old：既有合成租約 1 份。
- 輸入在跑前凍結 sha256（`E/runs/inputs-frozen.txt`）。

**執行環境**：本機 TestClient。S3 以替身取代，資料庫是臨時 Postgres。結果在 `E/runs/c1_c2_local.txt`，各檔回應在 `E/runs/c1c2_local_json/`。

| 項目 | 結果 |
|---|---|
| C1：v2 六欄都是 `{value, position}`，`value` 與同檔不帶參數相同 | 不符 0 |
| C2：錯框 | 0 |
| C2：覆蓋率（修訂 1，排除跨行值） | 21/21＝100% |
| 含跨行值的覆蓋率（照實並列） | 21/24＝87.5% |

- **跨行的 3 個值**：G1_03、G2_03、G3_03 的 `date_end`，都是「至中華民國115年」換行「…月…日止」。判分腳本另外判出它們跨行，判法不讀實作；正對照 G3_01 `date_start` 判為不跨行。
- **抽錯也框出處**：範本「3.社會住宅-租賃契約書範本-3.1」的 `tenant_name` 抽成「契約審閱權」。jgb2 `gtb_contract_chinese.pdf` 的 `rental_address` 抽成「1.為「富碧公寓」, 房型含 廳及 衛,房號 ,地址」。兩者都框在讀到的那段字上，C2 判對。
- **抽取率**：G1～G3 答案鍵有值的 88 格，只抽到 19 格。G2_01、G2_05 與 3 份範本沒有 `rental_terms`。這不在本片範圍，記在 followups C-F1。

## 3. 本機：C3、C6、C7

- C7：`tests/unit` 全跑，DB 用臨時 Postgres，結果 1952 passed、1 skipped、0 failed（`E/runs/c7_unit.txt`）。改前沒有測試資料庫時，有 11 個失敗，全是 DB 密碼驗證錯誤（`E/runs/c7_baseline_unit.txt`）。
  - 新增 `backend/tests/unit/test_contract_v2_positions.py`，共 21 個測試，涵蓋 C3：包裝形狀、同額租金與押金各框各行、第一個非空頁、跨行給 null、值不一致給 null、文字層不符給 null、非文字層給 null、旋轉頁給 null、400、非合約忽略、攔截看到的是未轉換回應。
  - `test_api_backward_compat.py` 的新增參數登記加入 `contract_format`。
- C6：`tests/unit/test_transcript_v2_spec.py` 38 passed。`git diff df41f2d -- backend/app/lib/multi_type_ocr/transcript_*.py` 為空（`E/runs/c6_local.txt`）。

## 4. 線上（部署 `fd9f6d9`，11/13 15:37）

- **部署前檢查**：線上 HEAD＝`origin/main`＝`df41f2d`，OOMKilled=false，RestartCount 0，health 200（`E/runs/deploy_pre.txt`）。
  - 線上 repo 有 5 個未追蹤檔：`.claude/` 與 4 個 `.env.bak*`，11/11 部署時就已存在；已追蹤的檔沒有改動。
  - 計畫原本要求「porcelain 空」。業主 11/13 裁定只看已追蹤檔。
- **送件**：一次一份，每份送完都查容器狀態，OOMKilled／RestartCount 全程沒有變動（`E/runs/online/*_log.txt`）。共 16 次：
  - 部署前 C5 不帶參數 5 次。
  - 部署後 C5 不帶參數 5 次。
  - 帶 v2 5 次。
  - C4 合成掃描檔 1 次（Bedrock 直讀 1 頁）。
  - 另有 1 次 `contract_format=v3` 的 400 確認新程式已載入。這一次不在授權的送件清單內，參數檢查就回 400，沒有上傳 S3，也沒有寫用量紀錄。
- **結果**（`E/runs/online_after.txt`）：

| 項目 | 結果 |
|---|---|
| C5：同一批 5 份不帶參數，排除 `file_url`、`stats.total_time_ms`、`review_item_id` 後，部署前後的差異 | 0 |
| C1：線上 v2 與同檔不帶參數的值 | 不符 0 |
| 線上 v2 與本機 v2（同檔，排除同 3 鍵） | 差異 0 |
| C2：線上錯框 | 0（5 份中有值的 8 欄全部有框） |
| C4：合成掃描檔帶 v2 | 六欄 `position` 全 `null`；值等於同一份回應依頁序第一個非空頁的值 |

- **複核佇列**：新增 1 列，`review_item_id=3b0f0655-407a-4733-a42d-97e7d8fec46d`（C4 掃描檔）。其餘 15 次都沒有進佇列。

## 5. 獨立驗證（verifier，CONFIRMED）

報告原文：`E/reviews/close-verify-20261113.md`。
- 另寫 12 份新電子合約（6 種版型、72 格、59 格有值），本機 API 實跑：錯框 0、C1 不符 0、六欄以外差異 0；覆蓋率排除跨行 58/58，含跨行 58/59。
- 同 12 份不帶參數，`df41f2d` 與 `fd9f6d9` 兩版輸出 `diff -r` 無差異。
- 重跑 C7（1952 passed）、C6（38 passed）、原 21 份 C1/C2（與存檔逐行相同）。
- 附帶：判分腳本 `c2_judge.py` 雜湊與 15:27 凍結紀錄不符，原因是修訂 1 後加了 `cross_line()`（`E/reviews/judge-hash-note-20261113.md`）。

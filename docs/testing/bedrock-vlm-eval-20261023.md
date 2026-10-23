# 讀圖模型評估：Amazon Bedrock 東京 vs 線上 DocuMind（2026-10-20～23）

業主要評估 Bedrock 東京（ap-northeast-1）的開源視覺模型，能不能取代或補足 OpenAI，用在兩個地方：
DocuMind 謄本的 AI 補欄位、掃描謄本，以及 AI 客服的讀單據和修繕照片。本檔是量測紀錄，數字不再改寫。依本檔做出的決定：AI 客服的視覺模型用 Qwen3 VL 235B，送圖前縮到長邊 2000，呼叫用 flex，記在 AIChatbot repo 的 DSP-111（`.claude/DECISIONS.md`）。

## 結論

| 用途 | 結果 | 依據 |
|---|---|---|
| AI 客服讀單據、收據 | Qwen3 VL 235B 最好（5 欄 92.6%）；只比金額＋日期，和線上 terra 同為 22/22 | §3.4 |
| AI 客服讀修繕照片 | terra 10/10 最好，Bedrock 模型 5–9/10；每個模型都會在不是壁癌的照片標「壁癌」 | §3.5 |
| 只看圖讀謄本 | Qwen3 VL 送原圖 96.2%，其他三個模型 ≤85% | §3.1 |
| DocuMind 補欄位（線上同一個 prompt） | terra 錯值 3，Bedrock 模型最少 9；不換 | §3.2 |
| 掃描謄本 | 線上流程 97.1–97.4% 勝過 Qwen 只看圖 91.3–91.8%；線上 16 欄讀錯卻沒進 `needs_confirmation` | §3.3 |
| 省錢 | 長邊縮到 2000 準確度不變；flex 單價打五折 | §3.6、§3.7 |

## 1. 測試範圍

| 測試 | 資料 | 輸入數 | 每個輸入跑幾次 | 標準答案由誰判 | 比較對象 |
|---|---|---|---|---|---|
| §3.1 只看圖讀謄本 | `backend/data/transcript_samples/` 遮罩樣本 | 6 張、53 欄 | 3 | `expected/`＋原圖逐欄判 | 四個 Bedrock 模型 × 送圖方式 |
| §3.2 同層補欄位 | 同上，取線上 `enable_llm=true` 交給 AI 的欄位 | 5 張、29 欄 | 3（terra 為線上 1 次） | 主持人依原圖＋INTEGRATION §3.1 取值範圍判 | terra vs 四個 Bedrock 模型 |
| §3.3 模擬掃描謄本 | 業主提供的 5 份真實電子謄本，共 17 頁，各轉成「掃描機 200dpi」與「手機拍照 150dpi、透視、光線不均」兩張 | 34 張 × 25 欄 | Qwen 3；線上 1 | 同一份 PDF 文字層經線上 `enable_llm=false` 的輸出 | 線上流程 vs Qwen |
| §3.4 帳單收據 | Wikimedia Commons CC 授權的真實台灣單據 10 張＋台電電費單教學圖 1 張 | 11 張 × 5 欄 | 3（terra 為線上 1 次） | 主持人逐張看圖判 | 四個 Bedrock 模型＋terra |
| §3.5 修繕照片 | Wikimedia Commons CC 授權照片 | 10 張 | 3（terra 為線上 1 次） | 主持人看圖定類別，比對關鍵字 | 同上 |
| §3.6 縮圖 | §3.4＋§3.5 同一批 | 21 張 | 3 | 同上 | Qwen 送原圖 vs 長邊 2000／1500／1000 |
| §3.7 flex | §3.6 同一批，長邊 2000 | 21 張 | standard、flex 各 1 | — | 延遲 |

- **限制**：每組樣本只有 5–11 份，不是統計結果；標準答案由主持人自己判。模擬掃描不等於真的掃描件，仍要用真掃描件確認。單據、照片都不是 AI 客服的真實客訴資料。
- Bedrock 的 temperature=0 不保證每次輸出相同（Ministral 24 組裡有 22 組三次輸出不同），所以每個輸入跑 3 次。

## 2. 模型與東京區單價

單價是每百萬 token，取自 AWS Price List API（`pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{AmazonBedrock,AmazonBedrockFoundationModels}/current/ap-northeast-1/index.json`），2026-10-20 取得，Qwen flex 價格 2026-10-23 再查一次。

| 模型（runtime ID） | 輸入 | 輸出 |
|---|---|---|
| Qwen3 VL 235B（`qwen.qwen3-vl-235b-a22b`） | $0.64（flex／batch $0.32） | $3.22（flex／batch $1.61） |
| Ministral 3 14B（`mistral.ministral-3-14b-instruct`） | $0.24 | $0.24 |
| Mistral Large 3（`mistral.mistral-large-3-675b-instruct`） | $0.61 | $1.82 |
| Nemotron Nano 12B v2 VL（`nvidia.nemotron-nano-12b-v2`） | $0.24 | $0.73 |
| Gemma 3 27B（`google.gemma-3-27b-it`） | $0.28 | $0.46 |
| Claude Haiku 5.5（只能走 `jp.` 跨區設定，未測） | $0.11 | $0.55 |
| 參考：terra（OpenAI `gpt-5.6-terra`，取自 `docs/planning/03-TECH-STACK.md`，本次未查證） | $2.00 | $12.00 |

## 3. 結果

### 3.1 只看圖讀謄本（53 欄，3 次合計的正確＋格式比例）

| 模型 | 送原圖 | 切成長邊 ≤1540 的水平條 |
|---|---|---|
| Qwen3 VL 235B | **96.2%**（每次 51/53） | 91.8% |
| Ministral 3 14B | 69.8%（Bedrock 端縮到長邊 1540） | 83.0% |
| Nemotron Nano 12B v2 VL | 34.0% | 51.6% |
| Mistral Large 3 | 27.0% | 28.9% |

- Ministral 3 的長邊上限是 1540 像素（HF `mistralai/Ministral-3-14B-Instruct-2512` 的 `vision_encoder.max_image_size`）。大圖不切會被縮小，小字就糊掉。
  Ministral 另外兩種送法：縮到長邊 1000 只剩 38.4%；切條後再把小圖放大到 1540 是 84.3%，跟切條的 83.0% 差在雜訊範圍內，代表放大補像素沒有幫助。
- Ministral 的錯不是「大多編造」：切條後剩下約 14 欄錯，約一半是格式或結構問題，其餘是讀錯字或放錯欄位。
- Qwen 會自己處理高解析度，切條反而變差，要送原圖。
- Mistral Large 3 會出現圖上沒有的值（例如「古亭段三小段127地號」），而且單次最多只收 3 張圖。

### 3.2 同層補欄位（29 欄）

條件跟線上 DocuMind 一樣：同一份 prompt（`_extract_with_llm`）、同樣附 OCR 文字前 500 字、同一批欄位、同樣先縮到 100 萬像素。

| 模型 | 正確 | 格式 | 漏讀 | 錯值 |
|---|---|---|---|---|
| terra（線上） | 24 | 1 | 1 | **3** |
| Qwen3 VL 235B | 19 | 0 | 1 | 9（改送原圖 10） |
| Ministral 3 14B | 15 | 4 | 0 | 10 |
| Nemotron Nano 12B v2 VL | 14 | 0 | 0 | 15 |
| Mistral Large 3 | 13 | 0 | 1 | 15 |

- Bedrock 模型的錯幾乎都是「應該回空值，卻填了別部的值」，例如公設建號、他項權利部的權利人或設定權利範圍、共同擔保的地號或建號。
- 補欄位的 prompt 只給欄位中文名，沒寫要從哪一部取值。改送原圖錯值也沒減少，所以不是縮圖造成的。
- 對錯由主持人判；線上 few-shot 的內容未知，可能對 terra 有利。

### 3.3 模擬掃描謄本（17 頁 × 2 種劣化 × 25 欄）

扣掉定義差異後，正確＋格式的比例：

| 流程 | 掃描機 | 手機拍照 |
|---|---|---|
| 線上 DocuMind（PaddleOCR＋規則＋terra） | 97.1%（409/421） | 97.4%（410/421） |
| Qwen3 VL 235B 只看圖（prompt 附 INTEGRATION 取值規則） | 91.8%（380/414） | 91.3%（378/414） |

- **線上錯 23 欄**：
  - OCR 字形錯：`黃**` 讀成 `黄`（遮罩星號也一起不見）、`加強` 讀成 `加强`、`日` 讀成 `目`、`一層` 漏掉「一」。
  - AI 補持分：7 欄，信心度 0、有進複核。
  - AI 補地號填了別處的值：1 欄，信心度 0.8。
  - 漏讀：4 欄。
- **其中 16 欄沒進 `needs_confirmation`**：
  - OCR 讀錯 11 欄：信心度照樣是 0.9。
  - AI 補地號 1 欄：信心度 0.8，等於門檻，不會被列入。
  - 漏讀 4 欄：信心度 0.0 卻也沒列入，原因沒查。
  - 這 16 欄中有 10 欄，連整份文件都沒進複核。
- **Qwen 讀錯的方式不同**：OCR 讀錯的那幾格，Qwen 三次都讀對；Qwen 的錯偏向語意，例如把債務人或設定義務人當成所有權人、讀進共同擔保地號、把地號和建號對調、把騎樓當成附屬建物，也有編造的值。
- **判分偏向線上**：標準答案跟線上用同一套規則產出，所以有三種情況標成「定義差異」、不計分：空白日期、建物頁的 `area`、土地頁的 `rights_scope`。

### 3.4 帳單收據（11 張 × 5 欄：開立單位、日期、單號、總金額、賣方統編）

| 模型 | 正確 |
|---|---|
| Qwen3 VL 235B | **92.6%（50/54）** |
| Ministral 3 14B | 83.3% |
| Mistral Large 3 | 74.1% |
| Nemotron Nano 12B v2 VL | 70.4% |
| terra（線上 `bill`，只抽金額、日期） | 金額＋日期 22/22；Qwen 同樣兩欄也是 22/22 |

Qwen 的錯：免用統一發票收據把買受人統編當成賣方統編；沒有單號的收訖單，把統編填進單號。

### 3.5 修繕照片（10 張，用 DocuMind `repair_photo_processor` 的 prompt，與線上相同）

| 模型 | 命中 | 標籤命中 |
|---|---|---|
| terra（線上） | **10/10** | 9/10 |
| Ministral 3 14B | 9/10 | 7/10 |
| Qwen3 VL 235B | 8/10 | 7/10 |
| Nemotron Nano 12B v2 VL | 8/10 | 5/10 |
| Mistral Large 3 | 5/10 | 3/10 |

9 張不是壁癌的照片，被標成「壁癌」的張數：Qwen 7 張、Large 3 9 張、terra 4 張。
可能是 prompt 裡的範例「（如 漏水、壁癌、龜裂、設備損壞）」把模型帶偏了，但還沒拿掉範例重測。

### 3.6 縮圖（Qwen3 VL，21 張 × 3 次）

輸入 token 大約等於像素數 ÷ 1024（4000×3000 約 11,900、2000×1500 約 3,000），所以費用幾乎只跟解析度有關。

| 長邊 | 單據正確 | 修繕命中 | 修繕每張平均 | 修繕最貴一張 | 單據每張平均 |
|---|---|---|---|---|---|
| 原圖（上限 4000） | 92.6% | 8/10 | $0.00347 | $0.0079 | $0.00177 |
| **2000** | **92.6%** | **8/10** | **$0.00190** | **$0.0025** | **$0.00127** |
| 1500 | 90.7% | 9/10 | $0.00125 | $0.0016 | $0.00106 |
| 1000 | 87.0% | 10/10 | $0.00075 | $0.0009 | $0.00076 |

- 長邊 2000 時，錯的欄位和送原圖完全一樣。單據只有 2 張原圖超過 2000，修繕照片有 7 張。
- 縮到 1500 掉 1 欄（台電單統編）；縮到 1000 再掉 3 欄（單號錯一碼、病歷號被當成統編、統編填進單號）。
- 修繕照片在 1000 命中 10/10，只差 2 張，不能當成縮小比較準的證據。

### 3.7 flex 服務等級

- **用法**：Converse 帶 `"serviceTier": {"type": "flex"}`，回應會回 `serviceTier: flex`；填無效的值回 400。
- **延遲**：在東京 23:40（離峰）測 21 張，standard 中位數 2.51 秒、最慢 5.10 秒；flex 中位數 2.52 秒、最慢 5.32 秒。另一輪 standard 2.53／4.79 秒，flex 2.44／4.20 秒。
- **官方說明**（AWS 文件 `service-tiers-inference.html`，2026-10-23 開頁取得）：flex 給「能接受較長處理時間」的工作，Priority 和 Standard 會比它先處理；四種等級共用同一份 on-demand 配額。文件沒寫 flex 會慢多少，也沒寫會不會被拒。
- **尖峰時段沒測**：業主 2026-10-23 裁示暫定 flex 延遲可接受。

### 3.8 Qwen3 VL 每張費用（standard，用實測 token 中位數換算）

| 文件 | 每張 | 1 萬張 |
|---|---|---|
| 帳單收據（原圖） | $0.0011 | $11 |
| 修繕照片（原圖） | $0.0034 | $34 |
| 謄本圖（只看圖） | 約 $0.0028 | 約 $28 |
| 模擬掃描謄本頁 | 約 $0.0032 | 約 $32 |

長邊 2000 再加 flex，修繕照片每張平均約 $0.00095。

## 4. 外部系統限制（2026-10-20～23 實測）

- **API key 的權限範圍**：業主提供的 Bedrock API key 只能打 `bedrock-runtime` 的 Converse；控制面（例如 `foundation-models`）回 403。
  IAM 使用者 `app-jgb-ai-cs-bedrock` 起初只開了 Ministral 3 14B 和 Gemma 3 27B；Mistral Large 3、Qwen3 VL、Nemotron 是 2026-10-20 申請加開的。
  「no identity-based policy allows」代表 IAM 政策沒有授權。403 不能用來證明 model ID 是對的。
- **model ID 要用 runtime 那一列**：同一模型在 `bedrock-runtime` 和 `bedrock-mantle` 的 ID 可能不同（Qwen 是 `qwen.qwen3-vl-235b-a22b` 和 `…-instruct`）。價目表的 usagetype 帶的是 mantle ID，寫 IAM ARN 要看模型卡的 runtime 那列。
- **東京區呼叫方式**：
  - Qwen3 VL、Mistral Large 3、Ministral、Nemotron：東京區內直接呼叫。
  - Claude Haiku 5.5：只能走 `jp.`，資料會在東京和大阪處理。
  - Claude Sonnet 5：只能走 `global.`，資料可能離開日本。
  - 跨區的 IAM 要同時給 inference profile ARN，以及每個目的區的 foundation-model ARN；`global.` 另外要給 `arn:aws:bedrock:::foundation-model/<id>`。
- **圖片限制**：
  - Bedrock 單張上限 3.75MB，5MB 的照片回「Failed to buffer」。
  - Mistral Large 3 每個 prompt 最多 3 張圖。
  - Ministral 3 的長邊上限 1540。
- **Gemma 3 27B**：東京區呼叫一直沒回應（60 秒逾時），業主同事的帳號也卡到 5 分鐘。
- **定價頁**：Claude 和 Nova 的價格表在 headless 瀏覽器一直轉圈載不出來，改用 Price List API。2026-10-20 東京區價目表裡沒有 Llama 和 Pixtral。

## 5. 對線上的影響

測試送線上 DocuMind 時，共在複核佇列新增 30 筆，都還沒處理：

- **§3.2 同層**：`7a94e110`、`e5f0078b`、`7fec2b48`、`de3620e7`。
- **§3.3 模擬掃描（18 筆）**：
  `699b9e93`、`4c1e9106`、`a92bb7a8`、`87407526`、`a2ed2872`、`951381bf`、`02ace561`、`8fc404fb`、`6d26c22f`、
  `31be4b1f`、`02380c8b`、`5a10aa14`、`fbd45db2`、`1048b968`、`1e598710`、`2f009201`、`5bbbd700`、`6cde4dd3`。
- **§3.4 單據**：`4b2c3735`、`b64ae9b8`、`eaa749f8`、`2947ceee`、`10e5c9b1`、`7b141bcd`、`d02054e9`、`1701d20f`。

## 6. 證據位置（repo 外）

`~/jgb-archive/bedrock-vlm-eval-20261023/`，內容：

- `scripts/`：呼叫和判分腳本。
- `results/`：各輪原始輸出、線上回應、價目表。
- `samples/`：Commons 單據與照片，授權記在 `samples_manifest.json`。

§3.3 用的真實謄本含個資，轉出的圖和輸出都**沒有保存**。

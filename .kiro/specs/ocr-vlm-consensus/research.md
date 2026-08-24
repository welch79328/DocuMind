# ocr-vlm-consensus - 技術研究日誌

## 研究摘要

### 研究範圍

為「OCR 引擎 VLM 化與共識信心度架構」蒐集外部證據與內部限制,涵蓋七個主題:市場架構現況、VLM 信心度可靠度、多模型共識機制、分層成本控制、人機協作產品流程、**運算資源(GPU vs CPU)選型**、本地部署選項。研究目的為在寫設計前確認「哪些做法有市場背書」「哪些是本專案的硬性限制」「第一期是否需要新增基礎設施」。

### 關鍵發現

1. **市場領先產品沒有一個是純 VLM,也沒有一個是純 OCR——全部是混合架構**。Reducto(LongExtractBench 2026/6 第一名,99.6% 精確率)明確拒絕單次 VLM,理由是「無多輪回饋則初始解析錯誤會持續存在」。
2. **VLM 自評信心度的可靠度隨模型能力大幅變動**。ConfBench 實測:Claude Opus ECE=0.05(接近完美校準),Gemma 3-12B ECE=0.31(嚴重過度自信)。本專案採自架小模型路線,不可依賴模型自評。
3. **「OCR 文字 + 文件影像」雙模態的信心度品質優於任一單一模態,且模型越小增益越大**。這使既有「OCR → 純文字 LLM 校正」的架構存在明確改善空間,且改善點不在換引擎而在補上影像輸入。
4. **多模型結果一致性作為信心度訊號已是商品化做法**,有 USPTO 專利與多家商品實作;實測共識機制使可自動化產出量增加 81%,第三模型僅需在 14-35% 案例出動。
5. **GPU 每小時貴約 3 倍,但每頁換算成本便宜約 10 倍**(因速度快 20-60 倍)。然而第一期所需的「離線評估」用途,在開發用 Apple Silicon 機器上即可完成,**基礎設施支出為零**。

---

## 研究主題

### 主題 1: 市場架構現況——OCR、VLM 或混合

**研究問題**: 業界領先的文件處理產品採用何種辨識架構?本專案應否以 VLM 全面取代傳統 OCR?

**調查結果**:
- Reducto 採三層混合:版面優先電腦視覺(CV)→ VLM 逐區塊解讀 → 自有 Agentic OCR 多輪修正引擎;輸出含 **block-level confidence scores** 供下游判斷可信度
- Reducto 明確拒絕純 VLM 路線,理由:單次 VLM「無多輪回饋則初始解析錯誤會持續存在」且「難以處理邊緣版面、無外部引導時無法自我修正」
- Google Document AI 於 2026 將 Gemini 整合進 Layout Parser,多欄財報的表格辨識與閱讀順序改善
- Azure Document Intelligence 混合印刷/手寫準確率優於 Textract,但純手寫仍不及專用 VLM
- 傳統 OCR 在「輸入乾淨、格式穩定、延遲與成本敏感」時仍具優勢;VLM 在「版面、表格、手寫、語意抽取」佔優

**資料來源**:
- [Reducto: Hybrid Architecture & Agentic OCR Deep Dive](https://llms.reducto.ai/hybrid-architecture-agentic-ocr-deep-dive)
- [The Definitive Guide to OCR in 2026: From Pipelines to VLMs](https://slavadubrov.github.io/blog/2026/03/04/ocr-guide/)
- [AWS Textract vs Google Document AI vs Azure DI (2026)](https://invoicedataextraction.com/blog/aws-textract-vs-google-document-ai-vs-azure-document-intelligence)
- [Docling vs LlamaParse vs Unstructured vs Reducto 比較](https://llms.reducto.ai/document-parser-comparison)

**設計影響**: 否決「VLM 全面取代 OCR」。設計採混合架構,保留既有傳統引擎並新增共識層。取代發生在**引擎層**(單一引擎可換),不發生在**架構層**(多輪、交叉驗證、信心度、人工介入皆保留)。

---

### 主題 2: VLM 信心度可靠度

**研究問題**: 既有 `QualityAssessor` 與人工複核機制完全建立在信心度之上。若改用 VLM,其自評信心度能否作為攔截依據?

**調查結果**:
- ConfBench(2026/8)為首個針對文件抽取的信心度校準基準:20 種受控劣化管線、1,346 份文件變體、逾 7 萬筆實體級評估、7 個基礎模型
- 校準品質差異極大:Claude Opus ECE=0.05(接近完美),Gemma 3-12B ECE=0.31(嚴重過度自信)。**模型能力是主導因素,參數量跨家族時非良好預測指標**
- 弱模型的自評分數不適合作為信心度估計,但仍可用於**排序**預測結果
- **輸入模態顯著影響校準品質**:OCR 文字 + 文件影像的組合一致優於任一單一模態;越小的模型增益越大(Gemma 3-12B 缺少 OCR 時掉 6 個 AUROC 點,Opus 僅掉 3 點)
- 信心度導向的複核在 30% 複核預算下,最佳組態較隨機抽樣多找出 **2.43 倍**錯誤

**資料來源**:
- [ConfBench: Can You Trust the Confidence? (arXiv 2608.01792)](https://arxiv.org/html/2608.01792)

**設計影響**:
1. 本專案採自架小模型路線,**不得以模型自評信心度作為唯一攔截依據**,需求 4 的共識機制因此成為必要而非優化
2. 雙模態輸入的效益對小模型最大,直接支持需求 2
3. 信心度導向複核的 2.43 倍效益,佐證既有 HITL 架構方向正確

---

### 主題 3: 多模型共識作為信心度訊號

**研究問題**: 以「多引擎結果是否一致」取代「模型自評」作為信心度來源,是否為可行且經驗證的做法?

**調查結果**:
- 業界定義:信心度為**基於共識的可靠度量測**——分析多個獨立訓練或採互補策略的模型,在同一文件、同一欄位上的一致程度
- 已商品化:Mindee、Extend 皆有信心度評分產品;USPTO 專利 12524472 涵蓋「多模型差異準確率分析」
- 實測:高信心度觀測的錯誤率顯著低於中/低信心度,證實多方投票可建立有效的風險分層
- 共識機制使可自動化產出總量**增加 81%**,而第三個模型僅需在 **14-35%** 案例出動
- 集成式(ensemble)一致性分析所產出的信心度指標,較單一模型系統更可靠

**資料來源**:
- [Multi-Model AI Consensus Pipeline for Automated Data Extraction](https://www.biorxiv.org/content/10.64898/2026.02.17.706322v1.full.pdf)
- [USPTO 12524472: Multi-model differential accuracy analysis](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12524472)
- [Best Confidence Scoring Systems 2026 | Extend](https://www.extend.ai/resources/best-confidence-scoring-systems-document-processing)
- [Mindee: Automation Confidence Score](https://docs.mindee.com/extraction-models/optional-features/automation-confidence-score)

**設計影響**: 需求 4 的 `cross_check` 設計獲市場背書。**關鍵推論:共識來源不必是 VLM**——既有 PaddleOCR + Tesseract 已構成兩個獨立引擎,足以實作共識機制。此發現使需求 4 脫離對 GPU 硬體的相依,可先於需求 3 實施。

---

### 主題 4: 分層成本控制(Cascade)

**研究問題**: 多引擎交叉比對使每頁成本倍增,分層(先便宜後昂貴)能否有效控制成本?

**調查結果**:
- Cascade routing 於 2025-2026 已成標準實踐:先送便宜模型,信心度未達門檻才升級
- FrugalGPT(Stanford)顯示相同輸出品質下最高可降低 98% 成本;生產系統典型降低 87%,昂貴模型僅處理約 10% 請求
- **反面證據**:cascade 一定會先付便宜模型的成本,無跳過的快速通道;升級時總成本 = 便宜模型 + 品質檢查 + 昂貴模型,**比一開始就直送強模型更貴**
- 有團隊公開檢討導入路由層失敗的案例(《We Built a Routing Layer to Cut Our AI Costs. It Broke the Product.》)

**資料來源**:
- [LLM Routing and Model Cascades](https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades)
- [We Built a Routing Layer to Cut Our AI Costs. It Broke the Product.](https://towardsdatascience.com/we-built-a-routing-layer-to-cut-our-ai-costs-it-broke-the-product/)

**設計影響**: 需求 5 的啟用條件必須綁定實測升級觸發率,不得憑假設實作。觸發率過高時分層反而增加成本,故需求 5.4 要求系統主動提示不具效益。此為需求 5 列為 P2 並依賴需求 1 的根本原因。

---

### 主題 5: 人機協作的產品流程形態

**研究問題**: 低信心文件若需人工確認,使用者上傳後是否必須等待?市面標準流程為何?

**調查結果**:
- 核心指標為 **STP(Straight-Through Processing)率**:頂尖產品可達 95%+ 文件完全無需人工介入
- 分流為**欄位級而非文件級**:「低信心欄位或規則例外」路由至人工於驗證介面修正,而非整份文件停擺
- AI 抽取 + 人工驗證低信心欄位可達 **99.9% 準確率**,文件處理成本降低最高 **70%**
- HITL 應設計為自動化管線的原生部分:在信心度低於門檻時建立自動暫停點,使人工介入自然且可預期
- API 形態:小型文件同步回傳;高量、複雜或需管理系統資源時採非同步 job + webhook

**資料來源**:
- [Human-in-the-Loop AI in Document Workflows — Best Practices](https://parseur.com/blog/hitl-best-practices)
- [ABBYY: Human-in-the-Loop Verification](https://www.abbyy.com/ai-document-processing/human-in-the-loop-verification/)
- [Human-in-the-Loop Document Processing Guide](https://idp-software.com/guides/human-in-the-loop-document-processing/)
- [Veryfi: Sync vs Async Processing](https://docs.veryfi.com/api/getting-started/sync-vs-async-processing/)

**設計影響**: **修正了一項早期設計假設**。原構想為「VLM 批次處理插在人工複核之前」,隱含假設文件會排隊等待人工;但市面標準是立即回傳 + 欄位級標示,使用者不等待。且本專案使用者即租賃業者本人(最知道正確答案),複核者應為使用者自身而非後台團隊。設計改為:即時回傳 + 低信心欄位標示 + 使用者當場確認;既有複核佇列降級為「稍後處理」的備援路徑。

---

### 主題 6: 運算資源選型——GPU vs CPU ⭐

**研究問題**: 本專案是否必須採購/租用 GPU?GPU 與 CPU 在成本與效能上的實際差異為何?

**調查結果**:

**(1) EC2 價格對照**(us-east-1、on-demand、× 730hr;東京區約再貴 10-15%)

| 機型 | 規格 | 每小時 | 每月 |
|---|---|---|---|
| t3.medium | 2 vCPU / 4 GB | $0.042 | $30 |
| t3.large | 2 vCPU / 8 GB | $0.083 | $61 |
| t3.xlarge | 4 vCPU / 16 GB | $0.166 | $121 |
| **g4dn.xlarge** | 4 vCPU / 16 GB **+ T4 16 GB** | $0.526 | **$384** |
| g5.xlarge | 4 vCPU / 16 GB + A10G 24 GB | $1.006 | $734 |

同規格(4 vCPU / 16 GB)比較:加一張 T4 的溢價為 **$263/月**。

**(2) 效能與每頁成本**(量級估算,非實測)

| 項目 | CPU(t3.xlarge) | GPU(g4dn.xlarge + T4) |
|---|---|---|
| 每小時成本 | $0.166 | $0.526(貴約 3 倍) |
| 可舒適運行的模型 | 2B(勉強) | 7B(甜蜜點) |
| 7B 處理單頁 | 10+ 分鐘(實務不可用) | 10-30 秒(快約 20-60 倍) |
| 2B 處理單頁 | 1-3 分鐘 | 3-8 秒 |
| 7B 每頁換算成本 | ~$0.028 | ~$0.003(便宜約 10 倍) |

**核心結論:GPU 每小時貴約 3 倍,但每頁換算成本便宜約 10 倍。** 差異的本質不是「CPU 慢一點」,而是「CPU 只能跑 2B(堪用品質),GPU 能跑 7B(良好品質)」。

**(3) 規模效應**:500 頁批次於 CPU 跑 7B 約需 3.5 天;於 T4 約 2 小時。

**(4) 常駐 vs 按需**:g4dn.xlarge 常開約 $384/月;「用完即關」批次模式(每月 2 小時)約 $1。差異來自付費時數,而非單價。

**(5) 隱藏成本**:按需啟動的執行個體在關機期間仍產生 EBS 儲存費用。Qwen2-VL 7B 約 15 GB 加執行環境,以 100 GB gp3 計約 **$8/月常態支出**。可將模型置於 S3(15 GB ≈ $0.35/月)並於開機時拉取以壓低此項,代價為每次啟動增加下載時間;批次場景可接受。

**(6) Spot 執行個體**:可再省 60-70%,適合可中斷的批次工作,不適合即時服務。

**資料來源**:
- 專案內部文件 `docs/DEPLOYMENT.md` §3 選項 D、§5 建議規格總表
- AWS EC2 公開定價(on-demand,us-east-1)

**設計影響**: GPU 並非必須。決定性因素是 **VLM 的用途**而非「是否上生產環境」:

| VLM 用途 | 需要 GPU | 說明 |
|---|---|---|
| 離線評估(第一期唯一需求) | ❌ | 開發用 Apple Silicon 機器即可 |
| 批次重跑歷史文件 | ❌ | CPU 可行,僅較慢 |
| 進入即時路徑成為產品功能 | ✅ | 此時才需常駐運算資源 |

由於第一期僅需離線評估,**生產環境維持一般 x86 CPU 機器即可,GPU 決策可延後至基準數據產出之後**。

---

### 主題 7: 本地部署與模型選項

**研究問題**: 若不使用 GPU,有哪些可行的 VLM 執行途徑?可用的開源模型為何?

**調查結果**:

**(1) 開源文件 VLM 現況**(OmniDocBench)

| 模型 | 參數量 | 分數 | 備註 |
|---|---|---|---|
| GLM-OCR | 0.9B | 94.62 | 榜首 |
| **PaddleOCR-VL** | **0.9B** | **94.50** | 支援繁中,與現行引擎同家族 |
| GPT-4o | — | 85.80 | 大幅落後專用模型 |

自架 VLM 管線每頁成本約為商用 vision API 的 **1/167**。

**(2) Apple Silicon 本地執行**
- MLX(`mlx-vlm` 套件)為 Apple Silicon 首選框架;量化建議 MLX 4-bit,無 MLX 版本時用 GGUF Q4_K_M
- 2B 級視覺模型「可舒適運行於任何 Apple Silicon Mac」,可勝任影像描述、OCR、圖表判讀
- 較大的 Qwen-VL 變體需 16 GB 以上統一記憶體
- llama.cpp 亦支援視覺模型,需主模型 GGUF 加 mmproj 投影器 GGUF 兩個檔案

**(3) 避開 GPU 的完整選項**

| 選項 | 成本 | 隱私 | 適用 |
|---|---|---|---|
| 本機 Mac + MLX | $0 | ✅ 完全本地 | **離線評估(推薦)** |
| 雲端 VLM API | 按量 | ❌ 個資外送 + PII 拒絕風險 | 僅非個資文件 |
| Serverless GPU(Replicate/Modal/RunPod) | 按秒 | ⚠️ 經第三方,但跑開源權重故無內容政策拒絕 | 中量批次 |
| EC2 CPU 跑 2B | 低 | ✅ | 離線,慢 |
| 不使用 VLM | $0 | ✅ | 若 CPU 雙引擎基準已達標 |

**資料來源**:
- [PaddleOCR-VL 1.5 深度解析(勝過 GPT-4o)](https://pub.towardsai.net/paddleocr-vl-1-5-a-deep-dive-into-the-0-9b-model-that-outperforms-gpt-4o-on-document-parsing-c93bac97ac1f)
- [Best Open-Source OCR and Document VLMs to Self-Host 2026](https://www.spheron.network/blog/best-open-source-ocr-vlm-self-host-gpu-cloud-2026/)
- [MLX-VLM: Local Vision Language Models for Mac](https://dev.co/ai/frameworks/mlx-vlm)
- [Apple Silicon LLMs: Run AI Models on Mac (MLX, 2026)](https://codersera.com/blog/apple-silicon-llms-complete-guide-2026/)

**設計影響**: 第一期的 VLM 對照評估可於開發機以 MLX 完成,零基礎設施支出。PaddleOCR-VL 為優先候選(同家族、繁中、0.9B),但需驗證其是否可繞開 `paddlepaddle` 依賴——該框架在 ARM64 有上游缺陷(見風險 1)。Qwen2-VL 2B 為確定可行的備案。

---

### 主題 8: 既有程式碼可複用資產盤點(設計審查後補充)

**研究問題**: 共識機制與雙模態校正所需的能力,既有程式碼中有多少已存在但未被使用?

**調查結果**:

**(1) 多引擎候選已存在但被丟棄**

`EngineManager.extract_text_multi_engine()` 回傳三個值,第三個為各引擎原始結果:
```python
return fused_text, fused_confidence, valid_results
```
但 `TranscriptProcessor.extract_text()` 以底線變數丟棄之:
```python
text, confidence, _engine_results = await self.engine_manager.extract_text_multi_engine(...)
return text, confidence          # 多引擎候選在此消失
```
**含意**: 共識所需的多候選資料早已產生,引擎亦已並行執行。取得候選的邊際成本為**零**,僅需停止丟棄。

**(2) 規則式與 LLM 欄位抽取已分離**

`field_extraction_base.RegexFieldExtractor` 具備兩個獨立方法:
- `_extract_with_regex(text)` — 純規則,零成本
- `_extract_with_llm(...)` — LLM fallback

**含意**: 共識路徑可對各候選僅呼叫 regex 方法,LLM fallback 僅對共識結果執行一次,使 LLM 成本不隨候選數倍增。無需重新實作抽取邏輯,僅需將 regex 方法提升為公開介面。

**(3) 欄位格式校正邏輯已存在**

`TranscriptPostprocessor` 具備 `fix_land_number()`、`fix_roc_date()`、`_clean_whitespace()`、`correct_field_formats()`,可直接作為共識比對前的正規化實作。

**(4) 謄本關鍵欄位定義**

`TranscriptFieldExtractor.KEY_FIELDS` = `land_number`、`building_number`、`area`、`rights_scope`、`owner`;其 regex 本身已容納 OCR 常見誤判(如 `[0-9Oo\-]+` 允許 `O`/`o`)。

**資料來源**: 專案內部程式碼
- `backend/app/lib/ocr_enhanced/engine_manager.py`
- `backend/app/lib/multi_type_ocr/transcript_processor.py`
- `backend/app/lib/multi_type_ocr/field_extraction_base.py`
- `backend/app/lib/ocr_enhanced/postprocessor.py`
- `backend/app/lib/multi_type_ocr/transcript_field_extractor.py`

**設計影響**: 三項發現皆降低實施成本,並直接構成 design v1.1.0 的三處修訂依據——(1) 使覆寫契約的成本為零,(2) 使 LLM 零增幅成為可達成的硬性約束,(3)(4) 使正規化規格表得以具體定義而非僅有介面簽章。

**⚠️ 衍生風險**: 發現 (1) 同時暴露一項設計陷阱——若僅提供「包裝 `extract_text()`」的預設實作而未要求覆寫,共識機制將**靜默失效**:所有單元測試仍會通過(`FieldConsensusResolver` 本身邏輯正確),問題僅在端到端驗收才會暴露。此為 design v1.1.0 將覆寫列為明確任務並新增端到端驗證的原因。

---

## 架構模式評估

### 模式 1: VLM 全面取代傳統 OCR

**描述**: 移除既有 OCR 引擎,所有辨識改由視覺語言模型端到端完成。

**優點**: 架構單純;版面理解能力強;可處理手寫與複雜表格。

**缺點**: 市場無先例(領先產品皆為混合);錯誤模式由「可見亂碼」轉為「語法合法但數值錯誤的隱形錯誤」;小模型自評信心度不可靠,將使既有攔截機制失去依據;需常駐 GPU。

**適用場景**: 版面極複雜且容錯度高的場景。

**評估結論**: ❌ 不採用

---

### 模式 2: 混合架構——既有雙引擎 + 共識信心度

**描述**: 保留 PaddleOCR 與 Tesseract,新增逐欄位交叉比對;不一致者壓低信心度,交由既有 `QualityAssessor` 導入人工確認。

**優點**: 零新增基礎設施;共識訊號不依賴任何模型自評;與既有 `field_confidences` 介面天然吻合;有市場與專利背書;可立即實施,不受硬體時程牽制。

**缺點**: 兩引擎若錯誤高度相關則共識訊號失效(需實證);未引入 VLM 的版面理解能力。

**適用場景**: 成本敏感、需可稽核信心度、硬體條件受限。

**評估結論**: ✅ 採用(第一期核心)

---

### 模式 3: 雙軌——即時 CPU 路徑 + 離線 VLM 路徑

**描述**: 即時請求全部由 CPU 雙引擎處理並立即回傳;VLM 僅用於離線評估與(未來可選的)批次重處理。

**優點**: 使用者體感速度不變;VLM 不受硬體可用性牽制;GPU 決策可延後至有數據時;第一期基礎設施支出為零。

**缺點**: VLM 無法提升即時路徑的 STP 率,故第一期對使用者無直接助益(定位為評估工具);兩條路徑需維護。

**適用場景**: 硬體預算未定、需先驗證 VLM 效益是否值得投資。

**評估結論**: ✅ 採用

---

### 模式 4: VLM 批次插入人工複核之前

**描述**: 低信心文件進入複核佇列後,先由 VLM 批次重新辨識,減少人工工作量。

**優點**: 降低人工複核負荷。

**缺點**: **隱含假設文件會排隊等待人工**,但市面標準與本專案產品形態皆為「立即回傳 + 使用者當場確認」,不存在該等待窗口;且 GPU 非常駐時 VLM 無法提升即時 STP 率。

**適用場景**: 具備後台審核團隊、可接受結果延後定案的企業級流程。

**評估結論**: ❌ 不採用(早期構想,經主題 5 研究後推翻)

---

## 技術決策

### 決策 1: VLM 在第一期的定位

**背景**: VLM 是否應作為第一期的產品功能?

**選項**:
1. **產品功能**: 進入即時路徑,直接提升辨識品質。需常駐 GPU,月成本增加約 $263
2. **離線評估工具**: 僅用於跑標註集、與 CPU 雙引擎對照。可於開發機執行,零成本
3. **完全不做**: 第一期不碰 VLM

**最終決策**: 選項 2 — 離線評估工具

**理由**: 在沒有基準數據前,無法判斷 VLM 相對 CPU 雙引擎的實際增益是否值得常駐 GPU 的支出。選項 2 以零成本產出該決策所需的數據,且不排除未來升級為選項 1。

**後果**: 第一期 VLM 對終端使用者無直接可見助益;需在設計與溝通上明確標示其為評估工具而非產品功能,避免期待落差。

---

### 決策 2: 共識比對發生的層級

**背景**: `cross_check` 應在文字層或欄位層執行?

**選項**:
1. **文字層**: 擴展 `EngineManager._fuse_results()`。需變更回傳型別(現為 `tuple[str, float]`),衝擊既有呼叫端;文字層難以定位「哪個欄位」不一致
2. **欄位層**: 各引擎結果分別抽欄位後比對同名欄位。不改動融合回傳型別

**最終決策**: 選項 2 — 欄位層

**理由**: 與既有 `QualityAssessor.assess(ocr_confidence, field_confidences)` 介面天然吻合,使需求 6「不變更判定介面」的承諾自然成立;且 `extract_text_multi_engine()` 已回傳各引擎原始結果 `valid_results`,所需資料現成。

**後果**: 需對多份文字重複執行欄位抽取,成本上升,可由需求 5 的分層機制緩解。

---

### 決策 3: 運算資源路線

**背景**: 是否需要 GPU?何時需要?

**選項**:
1. **立即租用 GPU**: g4dn.xlarge 常駐,月增約 $263
2. **GPU 按需批次**: 用完即關,月增約 $1-13(視儲存策略)
3. **開發機 MLX 離線評估**: 零成本,僅能離線
4. **完全不用 VLM**: 零成本

**最終決策**: 選項 3 起步,選項 2/4 依基準數據決定

**理由**: 第一期唯一的 VLM 用途是離線評估,選項 3 即可滿足且無支出。GPU 的必要性應由「VLM 相對 CPU 雙引擎的增益幅度」決定,而該數據正是第一期的產出。

**後果**: 生產環境 EC2 維持一般 x86 CPU 機型;GPU 相關的成本上限爭議延後至第一期結束後處理。

---

### 決策 4: 人機協作形態

**背景**: 低信心結果應由誰、於何時確認?

**選項**:
1. **後台複核佇列**: 專責人員於佇列中處理(現行 `/review` 頁面的模式)
2. **使用者當場確認**: 立即回傳結果並標示低信心欄位,由使用者即時確認

**最終決策**: 選項 2 為主,選項 1 保留為備援

**理由**: 本專案使用者為租賃業者本人,對文件內容的正確答案最為清楚,不需另設審核團隊;市面自助式產品標準做法亦為欄位級即時標示。

**後果**: 需新增前端元件(現行 `ReviewCorrectView.vue` 為後台佇列模式,非當場確認);既有複核佇列不作廢,改接住「使用者選擇稍後處理」的情況。

---

## 風險識別

### 風險 1: 主力 OCR 引擎於 ARM64 崩潰

**描述**: `paddlepaddle` 對 ARM64/aarch64 有上游缺陷(PaddlePaddle/Paddle #76111),`import paddle` 即觸發程序中止。Docker 容器繼承主機架構,故 Apple Silicon 開發機上必然發生。

**可能性**: 高(已確認發生) **影響**: 高

**緩解措施**: 基準測試與生產部署一律於 x86_64 執行;開發機改用 Tesseract 或 `--platform linux/amd64` 模擬。需求 1.10 已將此列為驗收條件。**此缺陷極可能即為 `baseline_results.json` 長期維持 placeholder 狀態的根本原因。**

---

### 風險 2: 雲端模型因 PII 政策拒絕處理

**描述**: 謄本含姓名、統一編號、地址。既有程式碼註解明示雙模態曾因「PII 過濾拒絕處理」而停用,且保留 `_is_refusal()` 機制,顯示此問題確實發生過。

**可能性**: 高 **影響**: 高

**緩解措施**: 雙模態校正走本地 Provider(決策 3 的長期路線);過渡期若必須用雲端,限定於非個資文件類型;需求 2.8 已要求拒絕時保留原始辨識文字。

---

### 風險 3: 共識假設不成立

**描述**: 若兩引擎的錯誤高度相關(對同一處同樣看錯),則「不一致」訊號將無法反映實際錯誤。

**可能性**: 中 **影響**: 高

**緩解措施**: 需求 4.6 要求以標註集實證共識信心度與實際錯誤率的正相關;不成立則共識機制須重新設計。此為第一期基準測試的必要輸出之一。

---

### 風險 4: 標註成果遺失

**描述**: `.gitignore` 含 `/data/` 與 `/tests/`,標註對象與標註成果皆不在版控內。標註為 1-2 人天的投入。

**可能性**: 中 **影響**: 高

**緩解措施**: 需求 1.9 要求標註成果存放於版控位置,標註對象(含個資)不得進版控;標註前先完成存放位置定案與匯入機制(需求 1.8)。

---

### 風險 5: 分層策略反而增加成本

**描述**: cascade 一定會先付第一層成本;升級觸發率過高時,總成本高於直接使用單一強引擎。

**可能性**: 中 **影響**: 中

**緩解措施**: 需求 5 列為 P2 並綁定需求 1 的實測觸發率;需求 5.4 要求系統於觸發率超標時主動提示不具效益。

---

### 風險 6: VLM 第一期對使用者無感

**描述**: 決策 1 將 VLM 定位為評估工具,終端使用者無直接可見改善。

**可能性**: 高(為設計的必然結果) **影響**: 低

**緩解措施**: 於溝通與文件中明確標示定位;第一期對使用者的實際價值來自 CPU 雙引擎共識帶來的欄位級信心度與當場確認流程,而非 VLM。

---

## 外部依賴研究

### 依賴 1: PaddleOCR-VL

**版本**: 1.5 / 1.6 系列(0.9B)

**功能評估**:
- 符合需求: ✅(OmniDocBench 94.50,支援繁體中文,與現行引擎同家族)
- 效能表現: 良好(勝過 GPT-4o 的 85.80)
- 社群活躍度: 高
- 授權條款: Apache 2.0(PaddleOCR 專案)

**整合難度**: 中 — 需確認能否繞開 `paddlepaddle` 依賴,否則將繼承 ARM64 缺陷(風險 1)

**替代方案**: Qwen2-VL 2B(MLX 支援確定可行)、GLM-OCR 0.9B、DeepSeek-OCR

---

### 依賴 2: Qwen2-VL

**版本**: 2B / 7B

**功能評估**:
- 符合需求: ✅(既有 `LocalQwenProvider` 預設模型即為 `Qwen2-VL-7B-Instruct`)
- 效能表現: 7B 為品質甜蜜點(需 ~16 GB 顯存),2B 堪用且可 CPU 執行
- 社群活躍度: 高
- 授權條款: Apache 2.0(2B/7B)

**整合難度**: 低 — `providers.py` 的 `LocalQwenProvider` 已實作,對接 vLLM 的 OpenAI 相容端點

**替代方案**: PaddleOCR-VL、雲端 API

---

### 依賴 3: MLX / mlx-vlm

**版本**: 最新

**功能評估**:
- 符合需求: ✅(Apple Silicon 上執行視覺模型的首選框架)
- 效能表現: 良好(2B 級模型可舒適運行於任何 Apple Silicon Mac)
- 社群活躍度: 高(Apple 官方維護 MLX)
- 授權條款: MIT

**整合難度**: 低 — 僅用於第一期的離線評估,不進入生產程式碼路徑

**替代方案**: llama.cpp(需主模型 GGUF + mmproj 投影器 GGUF)、Ollama

---

## 研究結論

### 可行性評估

**第一期完全可行,且基礎設施支出為零。** 核心價值(欄位級信心度 + 使用者當場確認)由既有兩個 CPU 引擎的共識機制提供,不依賴 VLM、不依賴 GPU。VLM 的對照評估可於開發用 Apple Silicon 機器以 MLX 完成。

第二期(VLM 進入即時路徑)的可行性取決於第一期產出的準確率差距數據,不在本次研究可判定範圍。

### 未解問題

1. **VLM 相對 CPU 雙引擎的實際增益幅度** — 需第一期基準測試回答;此為 GPU 投資決策的唯一依據
2. **兩個 CPU 引擎的錯誤相關性** — 決定共識機制是否有效(風險 3)
3. **PaddleOCR-VL 能否繞開 `paddlepaddle` 依賴** — 決定其能否在 ARM 開發機上評估
4. **低信心攔截的實際觸發率** — 決定需求 5 分層策略是否具成本效益
5. **現行 EC2 實際帳單基線** — 需求 1 的成本驗收綁定 $15,若基線本身已超出則該數字需重訂
6. **開發機統一記憶體容量** — 決定可評估的模型規模(2B 或 7B)

### 建議後續行動

1. 定案標註存放位置與匯入機制(需求 1.8、1.9),**須在投入標註人力之前完成**
2. 於 x86 環境跑通現行 CPU 雙引擎基準,取代 placeholder(需求 1.10)
3. 補齊標註至統計可用量(謄本 ≥30 份、合約 11 份)
4. 實作欄位層 `cross_check` 共識機制(需求 4,不受硬體牽制)
5. 於開發機以 MLX 跑 VLM 對照評估,產出增益數據
6. 依增益數據決定是否進入第二期,屆時再處理 GPU 與成本上限議題

---

# 附錄:2026-08-24 第二輪研究與實測

> 第一輪(2026-08-04)是文獻研究,沒有任何本專案的實測數據。
> 這一輪首次讓 PaddleOCR 在真實謄本上跑起來,以下每個數字都是實測,不是引用。

## A. 主力引擎過去三個月從未運作過

`import paddle` 在 production 容器裡連續三次記憶體毀損:

```
free(): invalid pointer / double free or corruption (out) / free(): invalid size
```

`EngineManager` 是惰性載入 + 降級設計,所以服務 HTTP 200、看起來正常,
**實際上一直只有 Tesseract 單引擎在跑**。這解釋了為什麼
`baseline_results.json` 至今是 placeholder——不是沒人去跑,是主力引擎啟動不了。

根因:`requirements.txt` 只釘 27 個直接相依,其餘 69 個間接相依浮動。
同一份 requirements,不同時間建置得到不同環境。重建 image 後即恢復。

**行動**:應產出 lockfile(`pip freeze`),否則會再發生。

## B. 繁中模型落後三代(實物證據)

`lang="chinese_cht"` 實際下載到磁碟的檔案:

| 階段 | 簡中拿到 | **繁中(你在用的)** |
|---|---|---|
| 偵測 | `ch_PP-OCRv4_det` | `Multilingual_PP-OCRv3_det` |
| 辨識 | `ch_PP-OCRv4_rec` | `chinese_cht_PP-OCRv3_rec` |

繁中被留在 multilingual 分支,比同套件的簡中晚一代,比當時最新(v6)晚三代。

## C. PP-OCRv3 vs PP-OCRv6 實測對照

同一份 `建物謄本.jpg`(519×733)、同一台 x86 機器:

| | PP-OCRv3 | **PP-OCRv6** |
|---|---|---|
| 辨識行數 | 18 | **34** |
| 平均信心度 | ~0.63 | **0.936** |
| 信心度 ≥0.9 | 0 行 | **32 行(94%)** |
| 信心度 <0.7 | **11 行(61%)** | 1 行(3%) |

逐行對照:

```
v3: 進物登記己二頻本      v6: 建物所有權部 (1.00)
v3: 劉                    v6: 所有檬人:王** (0.94)
v3: 年北的月武的日        v6: 登記日期:民國105年10月20日 (1.00)
v3: 09$1-0000             v6: 標狀字號:105北重建字第012412號 (0.96)
```

v6 連「基隆市仁愛區智仁里15鄰仁二路119巷7之15號」這種長地址都一字不差。

**這不是「好一點」,是從不能用變成可用。** 升級已於 2026-08-24 執行。

## D. 雙引擎錯誤不相關 —— 共識機制的核心假設成立

`research.md` 原文列為最大風險的一條(「兩引擎若錯誤高度相關則共識訊號失效,
需實證」),已實證:**錯誤不相關,而且互補。**

同一份謄本,PaddleOCR v3 讀出 18 行、Tesseract 讀出 34 行,
而 Tesseract 抓到 PaddleOCR **完全漏掉**的關鍵欄位:

```
資料管點機關: 新北市三重地直事務所      ← PaddleOCR 沒有
有原因:增建,增建前面積:地面層62.19平方公  ← PaddleOCR 沒有
列i時間: 民國111征9月26日138#00分       ← PaddleOCR 沒有
```

兩者錯法也不同:PaddleOCR 傾向漏行,Tesseract 傾向讀出雜訊。
**共識機制有真實價值,不是紙上談兵。**

## E. 外部 benchmark 對不上本專案的實際文件(兩次)

1. **「Tesseract 是共識裡的弱環節」** —— 引自第三方對比(曲線文字 52.1% vs
   PaddleOCR 88.7%)。在**你們的謄本上這個判斷是錯的**:Tesseract 讀到的
   有效資訊比 PaddleOCR v3 多。那份數據不是在繁中謄本上測的。
2. **PaddleOCR-VL 的 OmniDocBench 96.33%** —— 分數在 A100/H800 上跑出來,
   官方沒有給任何 CPU 效能數字。$15/月 預算下 GPU 是零選項(g4dn $384/月,25×)。

**教訓:選型決策必須用自己的文件驗證,benchmark 只能用來排候選順序。**

## F. PaddleOCR-VL:品質可以,預算不行

| 機型 | 月費 | vs $15 上限 |
|---|---|---|
| t3.small(2GB RAM) | $15.12 | 剛好吃滿,RAM 差 8 倍 |
| g4dn.xlarge(官方不建議 T4) | **$384** | **25.6×** |
| g6.xlarge(L4) | ~$587 | 39× |

繁中證據是實的(論文 Table 6b 編輯距離 0.048,勝 Qwen2.5-VL-72B 的 0.100),
但那是自家評測集,且分數全在 GPU 上取得。

**額外風險**:多人回報 VL 會陷入重複迴圈與幻覺(如 `$1,500 $1,500 $1,500...`),
調參數無效。傳統 OCR 認錯會給低信心;**VLM 幻覺會用高信心說出不存在的數字**。
金額欄位上是靜默污染——這正是本規格 `cross_check` 設計要攔截的「隱形錯誤」。

## G. 手機拍攝是未驗證的風險

Real5-OmniDocBench(2026-03)實測管線型方案在傾斜/透視條件下崩盤:

| 情境 | PP-StructureV3 |
|---|---|
| 掃描 | 84.68 |
| **傾斜/透視** | **37.98** |

本專案有手機拍攝的帳單與謄本。解法不是換模型,是開啟 PaddleOCR 內建的
`use_doc_unwarping`(UVDoc 幾何去扭曲)+ `use_doc_orientation_classify`。
**目前兩者皆為 False(為速度考量),尚未在真實拍攝樣本上比較過。**

---

**第二輪研究日期**: 2026-08-24
**性質**: 實測,非文獻研究
**文件版本**: v2.0

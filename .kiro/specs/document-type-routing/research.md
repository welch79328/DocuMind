# document-type-routing - 市場研究與技術選型

> 本文為 spec 初始化階段完成之市場研究彙整,供 requirements / design 階段引用。
> 方法:多來源網路搜尋 → 抓取 25 個來源 → 抽取 117 條主張 → 3 票對抗式驗證(22 條確認、3 條被推翻)。
> 研究日期:2026-07-04。

## 一、核心結論

1. **「按文件類型路由 + 各自 pipeline + 共用回饋學習層」的架構方向有業界成熟對照**:AWS IDP 參考設計即以「每種文件類型一個 blueprint/schema」自動切分→分類→路由(僅供架構參考,AWS BDA 為雲端託管,與本專案地端偏好相左)。
2. **地端自架技術棧已夠成熟**:PaddleOCR PP-OCRv5(單一 <100MB、明確支援繁中)+ PP-StructureV3(PDF→JSON/Markdown、含表格/印章/版面)。
3. **學習機制先做 HITL + few-shot,勿急於 fine-tune**:微調證據樂觀但全來自與繁中文件無關的任務,僅為訊號。
4. **反直覺(已被推翻的主張)**:「LLM 免範本、能處理任意版型、勝過 OCR」在對抗式驗證中被 3:0 推翻。固定版型(謄本/帳單)反而是傳統 OCR/layout 的強項。

## 二、四類文件各自做法

| 文件 | 特性 | 建議做法 | 依據 |
|---|---|---|---|
| 謄本(優先) | 固定版型、密集、浮水印/印章 | PP-StructureV3 版面/表格/印章解析 → 結構化 JSON;固定版型理想條件字元級 ~99% | PaddleOCR 3.0 報告、Vellum |
| 帳單 | 少數關鍵欄位(金額/日期/戶號) | 票證式 KIE / key-value 抽取;掃描劣化件可原生影像餵多模態 LLM(掃描發票 92.71% vs 先轉文字 64.03%) | arXiv 2509.04469 |
| 合約 PDF | 文字量大、條款結構化 | pymupdf4llm 先偵測文字層(有層直接抽、純掃描才全 OCR);內建分段 chunking,整合 LangChain/LlamaIndex | pymupdf4llm 官方 |
| 修繕照片 | 影像理解、非 OCR | 可自架開源 VLM Qwen2-VL 2B/7B(Apache 2.0),DocVQA SOTA、支援中文 | Qwen 官方、arXiv 2409.12191 |

> 掃描 vs 文字層取捨:「原生影像 > 先轉文字」只在掃描/劣化件成立(更廣泛化主張被 1:2 反駁);已含文字層的合約 PDF,直接抽文字層仍最省成本。

## 三、「越用越準」三條路線比較

| 路線 | 資料量門檻 | 成本/維運 | 效果 | 適用時機 |
|---|---|---|---|---|
| ① HITL 人工校正回饋 | 幾筆即可 | 最低 | 立竿見影,累積資產 | 現在就做,MVP 首選 |
| ② Few-shot / 版型範本 | 數十筆黃金範例 | 低 | 固定版型(謄本/帳單)最有效 | 與①同步,校正樣本自動變範例 |
| ③ Fine-tune / LoRA | 數百~上千標註 | 高 | 窄領域可勝大型 zero-shot | 資料量夠 + few-shot 遇瓶頸才評估 |

HITL 具體做法(AWS IDP 第一方文件佐證):
- 信心度門檻建議起始 0.8(80%),保守可 0.8–0.9 再往下調。
- 認領式複核佇列:Start Review → 鎖定(僅擁有者能編輯)→ Release,避免多人衝突。
- 校正結果存成校正資料集,自動回灌成該類型 few-shot 範例。

升級 fine-tune 的誠實提醒:研究看到「160 筆讓微調勝過 zero-shot」「QLoRA 小模型窄領域勝 671B」等樂觀數據,但全來自 RVL-CDIP 影像分類、風機葉片檢測等非繁中任務,BLEU-4 指標偏袒被微調模板。當作訊號,不當精確門檻。

## 四、地端自架技術棧選型

| 用途 | 首選 | 備註 |
|---|---|---|
| OCR 引擎 | PaddleOCR PP-OCRv5 | 單一 <100MB、繁中明確支援、server/mobile 變體 |
| 文件結構解析 | PP-StructureV3 | PDF→JSON/Markdown,版面/表格/印章,OmniDocBench SOTA(第一方自報,保留看待) |
| PDF 文字層 | pymupdf4llm | 文字層偵測 + 混合 OCR(混合頁省 ~50%,純掃描仍需全 OCR) |
| 多模態 VLM | Qwen2-VL 2B/7B | Apache 2.0,可搭 vLLM;已有 Qwen2.5-VL/Qwen3-VL 後繼版,選型時複查最新 |

> 現有 Tesseract/PaddleOCR + OpenAI LLM 不需打掉,PP-StructureV3 與 pymupdf4llm 為增量補進,VLM 為修繕照片新增能力。

## 五、分階段落地建議

- Phase 1｜回饋迴路骨架(不需訓練):`quality_assessor` 加信心度門檻(0.8)→ 低於門檻進人工複核佇列(認領式鎖定)→ 校正結果寫入校正樣本表;定義評估指標 CER + 欄位級準確率,建立基準線。
- Phase 2｜文件類型路由 + few-shot(謄本先行):建立路由層,謄本接 PP-StructureV3、合約接 pymupdf4llm;校正樣本自動變 few-shot 範例回灌 prompt;帳單建 key-value schema;修繕照片接 Qwen2-VL POC。
- Phase 3｜視資料量再評估 fine-tune:某類型(最可能謄本)累積數百筆校正且 few-shot 明顯遇瓶頸時,才對單一類型試 QLoRA;用 Phase 1 指標做前後對照,證明有提升才上線。

## 六、Caveats(研究者標註)

1. 多數 LLM 抽取優勢結論來自單一 v1 preprint(arXiv 2502.18179),其 LayoutLMv3 基線分數異常偏低,不可解讀為「固定版型繁中謄本上微調 layout 模型已過時」。
2. PaddleOCR「SOTA/排名第一」與 PP-StructureV3 OmniDocBench SOTA 皆為 Baidu/PaddlePaddle 團隊第一方自報(含自定 1-edit distance 指標),功能可信、榜首宣稱保留;PP-OCRv5 手寫英文略遜多模態。
3. 「原生影像 > 文字解析」僅在掃描/劣化件成立,更廣義泛化主張已被反駁;已含文字層的合約 PDF,pymupdf4llm 文字層抽取仍更省成本。
4. 微調證據(RVL-CDIP 影像分類、風機葉片檢測)與繁中文件無關,外推至 DocuMind 的 KIE/修繕照片屬詮釋性延伸,不宜當精確門檻。
5. AWS blueprint/BDA 與 HITL 門檻建議雖為權威第一方,但屬雲端託管,與本專案地端/成本敏感(<$15/月)偏好相左,僅作架構與流程參考。
6. VLM 頭部 SOTA 屬 72B 級,地端可跑的 2B/7B 分數較低;Qwen2-VL 已有後繼版,選型應複查最新。
7. 無任何來源直接對台灣地政謄本(密集+浮水印)做 benchmark,繁中準確率為跨來源推論——Phase 2 須以自有樣本實測。
8. pymupdf4llm 混合 OCR 的 50% 加速僅適用混合數位/掃描頁,純掃描謄本仍需全頁 OCR。

## 七、已被推翻的主張(勿採用)

1. 「發票/收據 KIE 上,原生影像餵多模態 LLM 一律勝過 OCR/轉文字 pipeline」— 投票 1:2 反駁(僅掃描劣化件成立)。
2. 「Mistral-7B 以 1,600 筆 few-shot 微調達 83.4%,近乎媲美 32 萬筆訓練的 BERT」— 投票 0:3 反駁。
3. 「LLM 處理任意/不可預測版型比 OCR 更有效,免建範本」— 投票 0:3 反駁。

## 八、未解問題(需以自有資料驗證)

1. 台灣地政謄本(密集+浮水印+印章)上,PP-StructureV3/PP-OCRv5 對比原生多模態 LLM 的欄位級準確率與成本實測差異?無現成 benchmark。
2. 繁中 KIE(金額/日期/戶號)從 few-shot 升級 fine-tune 的具體資料量與準確率門檻?
3. 地端 VLM(Qwen2-VL 2B/7B、MiniCPM-V、GOT-OCR2.0)在修繕照片瑕疵辨識的繁中效果與最低硬體需求?
4. <$15/月 限制下,回饋學習層(門檻、佇列、樣本自動套用)的工程實作與評估基準線與 fine-tune 觸發準則?

## 九、來源清單(主要)

- arXiv 2502.18179 — General-purpose LLM vs specialized KIE models(primary)
- arXiv 2509.04469 — 原生影像 vs 文字解析 pipeline(掃描件)(primary)
- arXiv 2507.05595 — PaddleOCR 3.0 / PP-OCRv5 / PP-StructureV3 技術報告(primary)
- arXiv 2412.13859 — 小樣本微調 vs zero-shot(影像分類)(primary)
- arXiv 2409.12191 / Qwen 官方 blog — Qwen2-VL(primary/secondary)
- github.com/pymupdf/pymupdf4llm — 合約 PDF 文字層 + 混合 OCR + chunking(primary)
- AWS IDP:from-pdfs-to-insights 架構 blog + BDA blueprint docs + accelerated-idp human-review.md(secondary/primary)
- Vellum:document-data-extraction-llms-vs-ocrs(blog)

---

## 十、設計階段決策紀錄(2026-07-04)

> 由 `/kiro:spec-design` 產生;discovery 屬 Extension(整合型),依據 gap-analysis.md。

### 架構決策
1. **最大化複用既有骨架**:沿用 `ProcessorFactory` + `DocumentProcessor`(模板方法),四型別以加法擴充,不破壞 `transcript`/`contract` 現行行為。
2. **統一型別列舉** `DocumentType(transcript/bill/contract/repair_photo)`,收斂現有三處不一致(工廠/classifier/ai_service)。
3. **信心度收斂**:復活 `QualityAssessor` 為單一評估點,取代散落硬編碼門檻(全文 0.85、欄位 0.7),改由 `OCR_QUALITY_THRESHOLD` 配置,預設對齊現行行為以向後相容。
4. **LLM 層可插拔** `LLMProvider`(OpenAIProvider / LocalQwenProvider),`LLM_CLOUD_ENABLED=false` 可強制本地;few-shot 注入為 prompt 組裝(零訓練)。
5. **回饋學習層獨立新建**:ReviewQueue / CorrectionSample / FewShotSelector / Evaluation 四服務 + 三張新表,與 pipeline 解耦,四型別共用。
6. **PP-Structure 定位增強項**(預設關),謄本欄位先以規則+LLM Vision 落地,避免 PoC 阻塞主線。

### 使用者確認的方向(對話定案)
- 本地優先、雲端可選;OCR 一律本地 PaddleOCR(免費且中文最強)。
- 「越來越準」= HITL 校正 → 校正即範例(correction-as-example)→ few-shot 回灌,**零訓練**;fine-tune 為 Phase 3 選配。
- 種子範例冷啟動:上線前手動準備標準謄本正確答案,免訓練即有基礎準度。
- 人只碰低信心文件,人工量隨時間遞減。
- 硬體/成本:雲端可外送就先 OpenAI POC(Path B);隱私硬需求則 EC2 用完即關跑 Qwen(Path C);量穩後轉地端 GPU 機器(Path D)。EC2 自架 ≠ 雲端 API 外送(資料留 VPC)。

### 待 PoC 驗證(承接 openQuestions)
- PP-StructureV3 對台灣謄本欄位級準確率與資源成本(無現成 benchmark,須自有樣本)。
- 本地 Qwen2-VL 2B/7B 在修繕照片與謄本欄位的繁中實效與最低硬體。
- few-shot 範例選取策略與注入 token 成本的邊際效益。
- 複核佇列認領鎖定:悲觀鎖(採用)vs 樂觀鎖的取捨已定為悲觀式條件更新。

### 關鍵風險與緩解(設計已納入)
- **自我增強偏誤**(最高):僅人工校正後樣本可入庫 + 黃金範例人工標記 + 去重。
- **繁中謄本無 benchmark**:PP-Structure 為增強項、規則+LLM Vision 先交付。
- **個資合規**:`LLM_CLOUD_ENABLED=false` 強制本地。

# document-ocr-enhancement - 技術研究日誌

## 研究摘要

### 研究範圍
本研究針對政府建物土地謄本 OCR 優化的技術可行性進行深度調查,涵蓋圖像預處理技術、OCR 引擎配置優化、模組化架構設計等關鍵領域。

### 關鍵發現
1. **浮水印移除技術成熟**: OpenCV HSV 色彩空間分離紅色通道的方法已被廣泛驗證,適用於移除紅色浮水印與印章
2. **適應性二值化最佳實踐**: Sauvola 方法對不均勻照明文件效果最佳,Otsu 適用於雙峰分布圖像
3. **PaddleOCR 繁體中文優化**: PP-OCRv5 (2025) 原生支援繁體中文,建議圖像解析度設定為 1080p-2K
4. **模組化架構可行**: 方案 B 的七模組架構符合 SOLID 原則,長期維護成本低
5. **效能權衡清晰**: 多引擎並行會增加處理時間 1.5-2 倍,需要配置開關

---

## 研究主題

### 主題 1: 紅色浮水印移除技術

**研究問題**: 如何有效移除政府謄本上的紅色「已列印」浮水印和公章,同時保留黑色文字?

**調查結果**:
- **HSV 色彩空間優勢**: HSV 色彩空間將色相(Hue)、飽和度(Saturation)、明度(Value)分離,不受光照變化影響,比 RGB 更適合顏色檢測
- **紅色範圍定義**: 在 OpenCV 中,HSV 色相範圍為 [0,179],紅色對應兩個範圍 [0,10] 和 [160,179]
- **實作方法**:
  1. 使用 `cv2.cvtColor(image, cv2.COLOR_BGR2HSV)` 轉換色彩空間
  2. 使用 `cv2.inRange()` 創建紅色遮罩
  3. 使用形態學操作(morphological operations)去除噪點
  4. 將遮罩區域填充為白色或背景色
- **預期效果**: 移除浮水印後,黑色文字保留完整,OCR 準確率提升 10-20%

**資料來源**:
- [OpenCV Official: Changing Colorspaces](https://docs.opencv.org/4.x/df/d9d/tutorial_py_colorspaces.html)
- [DataTechNotes: HSV Color Detection](https://www.datatechnotes.com/2023/07/color-detection-with-hsv-color-space-in.html)
- [GeeksforGeeks: Change RGB with HSV (2025)](https://www.geeksforgeeks.org/change-rgb-image-color-with-hsv-values-with-python-opencv/)

**設計影響**:
- 預處理模組需要實作 `remove_red_watermark()` 函數
- 需要可配置的 HSV 閾值參數(應對不同掃描品質)
- 必須實作降級機制:比較浮水印移除前後的 OCR 信心度,若降低則使用原始圖像

---

### 主題 2: 適應性二值化方法選擇

**研究問題**: Otsu、Sauvola、Adaptive Thresholding 哪種二值化方法最適合謄本文件?

**調查結果**:
- **Otsu 方法**:
  - 自動計算全域閾值,無需手動設定
  - 適用於雙峰分布(bimodal)的圖像直方圖
  - Tesseract OCR 內部已使用 Otsu,外部預處理不必要
- **Sauvola 方法**:
  - 局部自適應閾值,基於局部均值與標準差
  - 對不均勻照明的文件效果極佳
  - Tesseract 5.0+ 已內建,可透過參數啟用
  - 計算複雜度較高,適合品質要求高的場景
- **Adaptive Thresholding**:
  - OpenCV 提供 `ADAPTIVE_THRESH_MEAN_C` 和 `ADAPTIVE_THRESH_GAUSSIAN_C`
  - 將圖像分為小區塊,每個區塊獨立計算閾值
  - 適合背景亮度不均的文件
- **最佳實踐**: 先使用 5×5 高斯濾波去噪,再套用二值化

**資料來源**:
- [OpenCV: Image Thresholding](https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html)
- [Tesseract: Improving Output Quality](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)
- [Enhancing OCR Accuracy with OpenCV](https://trenton3983.github.io/posts/ocr-image-processing-pytesseract-cv2/)

**設計影響**:
- 預處理模組應實作多種二值化方法並提供配置選項
- 預設使用 Adaptive Thresholding (Gaussian),失敗時降級為 Otsu
- 不需要在 Tesseract 前預處理 Otsu(避免重複)
- 需要實作去噪步驟:`cv2.GaussianBlur(image, (5,5), 0)`

---

### 主題 3: PaddleOCR 繁體中文配置優化

**研究問題**: 如何配置 PaddleOCR 以獲得最佳繁體中文辨識效果?

**調查結果**:
- **最新版本**: PP-OCRv5 (2025年5月發布),相比 v4 準確率提升 13%
- **語言參數**: 使用 `lang='chinese_cht'` 啟用繁體中文模型
- **圖像解析度建議**: 將 4K+ 圖像縮放至 1080p-2K 範圍,過高解析度反而降低辨識效果
- **自訂字典**: 可透過 `rec_char_dict_path` 參數使用自訂字典,減少繁簡混淆
- **角度分類**: 啟用 `use_angle_cls=True` 自動檢測文字方向
- **模型選擇**:
  - Mobile 版本: 適合 CPU 環境,檔案小,速度快
  - Server 版本: 適合 GPU 環境,準確率更高
- **效能調優**:
  - `use_gpu=False` 用於 CPU 環境
  - `show_log=False` 減少日誌輸出
  - 批次處理多頁 PDF 時注意記憶體管理

**資料來源**:
- [PaddleOCR GitHub (2025)](https://github.com/PaddlePaddle/PaddleOCR)
- [PaddleOCR 3.0 Technical Report (2025)](https://arxiv.org/html/2507.05595v1)
- [PaddleOCR Multi-language Documentation](http://www.paddleocr.ai/v3.3.2/en/version2.x/ppocr/blog/multi_languages.html)

**設計影響**:
- 引擎管理模組需要針對 PaddleOCR 提供專用配置
- 圖像預處理應包含解析度調整步驟(目標 1080p-2K)
- 使用 Mobile 版本作為預設(考慮部署環境為 Docker CPU)
- 自訂字典作為 Phase 2 優化項目(需收集謄本常見字)

---

## 架構模式評估

### 模式 1: 管道模式 (Pipeline Pattern)

**描述**: 將 OCR 處理流程設計為線性管道,每個階段依序執行(預處理 → OCR → 後處理)

**優點**:
- 流程清晰,易於理解與除錯
- 每個階段可獨立測試與優化
- 符合現有 `document_service.py` 的流程設計

**缺點**:
- 無法並行處理多個引擎
- 階段間數據傳遞需要序列化

**適用場景**: 單引擎模式,強調流程清晰度

**評估結論**: ⚠️ 部分採用 - 用於單引擎流程,多引擎融合需要並行模式

---

### 模式 2: 策略模式 (Strategy Pattern)

**描述**: 將不同的預處理策略、OCR 引擎、後處理策略封裝為可替換的策略物件

**優點**:
- 高度可擴展,新增策略無需修改現有程式碼
- 支援執行期動態切換策略
- 符合開放封閉原則(OCP)

**缺點**:
- 增加抽象層次,程式碼複雜度上升
- 需要定義統一的策略介面

**適用場景**: 需要支援多種預處理、OCR、後處理組合

**評估結論**: ✅ 採用 - 用於預處理策略與引擎選擇

---

### 模式 3: 門面模式 (Facade Pattern)

**描述**: 提供統一的高層介面 `EnhancedOCRPipeline`,隱藏內部複雜的模組互動

**優點**:
- 簡化客戶端調用,降低耦合
- 內部模組變更不影響外部介面
- 符合依賴反轉原則(DIP)

**缺點**:
- 門面類可能變得過於龐大
- 過度封裝可能降低靈活性

**適用場景**: 提供統一的 OCR 增強入口

**評估結論**: ✅ 採用 - `EnhancedOCRPipeline` 作為門面類

---

## 技術決策

### 決策 1: 模組化架構 vs 單檔案擴展

**背景**: 需要在快速交付與長期可維護性之間做出選擇

**選項**:
1. **方案 A(單檔案擴展)**: 直接在 `ocr_service.py` 中增加功能
   - 優點: 實作快速(13-15.5天)
   - 缺點: 程式碼品質差,長期維護困難
2. **方案 B(完全模組化)**: 建立 `ocr_enhanced/` 模組
   - 優點: 程式碼品質高,易於測試與擴展
   - 缺點: 實作時間較長(18-23天)
3. **方案 C(混合)**: 先快速實作再重構
   - 優點: 快速見效,逐步改善
   - 缺點: 需要兩階段實施

**最終決策**: 選擇方案 B(完全模組化)

**理由**:
- 用戶明確選擇方案 B,注重長期程式碼品質
- DocuMind 是產品級系統,未來可能擴展到其他文件類型
- 18-23 天工期在可接受範圍內
- 模組化設計方便團隊協作與測試

**後果**:
- 前期需要 1 天進行架構設計
- 每個模組可獨立開發與測試
- 未來擴展成本大幅降低
- 技術債務最小化

---

### 決策 2: 多引擎並行 vs 串行

**背景**: 多引擎融合可提升準確率,但會增加處理時間

**選項**:
1. **並行處理**: 使用 `asyncio.gather()` 同時運行多個引擎
   - 優點: 處理時間接近最慢引擎,而非總和
   - 缺點: 記憶體用量增加,成本增加(Textract API)
2. **串行處理**: 依序運行引擎,失敗時切換下一個
   - 優點: 記憶體用量低,成本可控
   - 缺點: 處理時間為總和

**最終決策**: 並行處理,但透過配置開關控制

**理由**:
- 並行處理對於 30 秒(JPG)和 90 秒(PDF)的時間限制更有利
- 可透過 `settings.OCR_MULTI_ENGINE` 配置開關
- 預設僅使用免費引擎(PaddleOCR + Tesseract)避免成本

**後果**:
- 需要實作非同步引擎管理器
- 需要監控記憶體用量並設定上限
- 提供單引擎降級機制

---

### 決策 3: OpenCV vs Pillow 圖像處理

**背景**: 預處理需要進階圖像操作,需選擇主要圖像處理庫

**選項**:
1. **OpenCV (cv2)**: 功能強大,支援複雜圖像操作
   - 優點: HSV 色彩空間、形態學操作、適應性二值化皆完整支援
   - 缺點: 依賴較大(需要 opencv-python-headless ~50MB)
2. **Pillow (PIL)**: 輕量,現有專案已使用
   - 優點: 依賴已存在,API 簡單
   - 缺點: 進階功能有限,需自行實作某些演算法

**最終決策**: 主要使用 OpenCV,Pillow 作為輔助

**理由**:
- OpenCV 對於 HSV 色彩空間操作、適應性二值化有原生支援
- 現有 `requirements.txt` 已包含 `opencv-python-headless`
- Pillow 保留用於基本操作(開啟、儲存、格式轉換)
- 兩者搭配使用,發揮各自優勢

**後果**:
- 預處理模組主要依賴 `cv2`
- 需要確保 Docker 映像包含 OpenCV 依賴
- 需要文件說明 OpenCV 與 Pillow 的使用場景

---

## 風險識別

### 風險 1: 浮水印移除過度,影響文字辨識

**描述**: HSV 紅色範圍設定不當,可能將部分文字誤認為浮水印移除

**可能性**: 中

**影響**: 高(OCR 準確率下降)

**緩解措施**:
1. 實作 A/B 比較:對原始圖像與處理後圖像分別執行 OCR
2. 比較兩者的平均信心度,若處理後信心度下降 > 10%,則使用原始圖像
3. 提供可配置的 HSV 閾值參數,允許微調
4. 記錄預處理決策到元數據,方便後續分析

---

### 風險 2: 多引擎並行處理時間超標

**描述**: 3 個引擎並行處理 3 頁 PDF 可能超過 90 秒限制

**可能性**: 中

**影響**: 中(不符合效能需求)

**緩解措施**:
1. 實作超時檢測,超過 80 秒自動降級為單引擎模式
2. 提供配置選項,允許選擇引擎組合(例如僅 PaddleOCR + Tesseract)
3. 優化並行邏輯,避免不必要的等待
4. 監控實際處理時間,根據數據調整策略

---

### 風險 3: PaddleOCR 繁體中文模型下載失敗

**描述**: Docker 容器首次啟動時,PaddleOCR 需下載繁體中文模型(~10MB),可能因網路問題失敗

**可能性**: 低

**影響**: 高(功能完全不可用)

**緩解措施**:
1. 在 Docker 映像建構時預先下載模型
2. 提供本地模型檔案路徑配置選項
3. 實作模型下載失敗時的降級機制(使用 Tesseract)
4. 文件說明模型預載入步驟

---

## 外部依賴研究

### 依賴 1: opencv-python-headless

**版本**: 4.5.0+

**官方文件**: [https://docs.opencv.org/](https://docs.opencv.org/)

**功能評估**:
- 符合需求: ✅ 完整支援 HSV 色彩空間、適應性二值化、形態學操作
- 效能表現: 良好(C++ 底層實作,效能接近原生)
- 社群活躍度: 高(OpenCV 是最活躍的電腦視覺函式庫)
- 授權條款: Apache 2.0(商業友善)

**整合難度**: 低(現有專案已使用,API 穩定)

**替代方案**: scikit-image(純 Python,效能較差)

---

### 依賴 2: PaddleOCR (paddleocr)

**版本**: 2.8.1+ (現有),建議升級至 3.0+ for PP-OCRv5

**官方文件**: [https://github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)

**功能評估**:
- 符合需求: ✅ 原生支援繁體中文,信心度分數完整
- 效能表現: 良好(繁體中文準確率高於 Tesseract)
- 社群活躍度: 高(百度維護,持續更新)
- 授權條款: Apache 2.0(商業友善)

**整合難度**: 低(現有專案已整合,僅需優化參數)

**替代方案**: EasyOCR(支援繁體中文,但效能較差)

---

### 依賴 3: pytesseract

**版本**: 0.3.13

**官方文件**: [https://github.com/tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract)

**功能評估**:
- 符合需求: ✅ 支援繁體中文(需安裝 chi_tra.traineddata)
- 效能表現: 一般(繁體中文不如 PaddleOCR,但免費)
- 社群活躍度: 高(Google 維護,歷史悠久)
- 授權條款: Apache 2.0(商業友善)

**整合難度**: 低(現有專案已整合)

**替代方案**: 無(Tesseract 是最成熟的開源 OCR)

---

## 研究結論

### 可行性評估
**結論**: 方案 B 技術可行性高,所有關鍵技術已驗證

**支持證據**:
1. OpenCV HSV 浮水印移除技術成熟,有大量案例
2. PaddleOCR PP-OCRv5 繁體中文支援完善
3. 適應性二值化有多種成熟演算法可選
4. Python 生態系統對圖像處理支援完整
5. 現有專案依賴已包含主要函式庫,整合成本低

### 未解問題
1. **最佳 HSV 閾值**: 需實驗確定最適合謄本的紅色範圍
2. **二值化方法選擇**: Sauvola vs Adaptive 需要基準測試
3. **多引擎融合演算法**: 字符級對齊的具體實作細節
4. **自訂繁體字典**: 需收集謄本常見字建立字典

### 建議後續行動
1. **Phase 1 MVP**: 先實作基礎浮水印移除與單引擎優化,驗證效果
2. **基準測試**: 使用 `data/` 下的兩個測試文件建立基準線
3. **參數調優**: 預留 2-3 天進行 HSV 閾值、二值化參數實驗
4. **漸進式優化**: Phase 1 完成後再實作多引擎融合(降低風險)

---

**研究日期**: 2026-03-25
**研究人員**: Claude AI (Sonnet 4.5)
**文件版本**: v1.0
**對應設計文件**: design.md v1.0

# 技術設計原則

## 核心原則

### 1. 型別安全 (Type Safety)
- 使用明確的型別定義,避免 `any` 或動態型別
- Python: 使用 type hints 和 TypedDict
- TypeScript: 使用 interface 和 type
- 在邊界處驗證輸入型別

### 2. 視覺化溝通 (Visual Communication)
- 使用 ASCII 圖表或文字圖呈現架構
- 資料流程必須有流程圖
- 模組關係必須有依賴圖

### 3. 正式語調 (Formal Tone)
- 使用專業術語
- 避免口語化表達
- 保持客觀、技術性描述

### 4. 模組化與解耦 (Modularity & Decoupling)
- 遵循單一職責原則
- 明確定義模組邊界
- 最小化模組間依賴

### 5. 可測試性 (Testability)
- 每個元件都有清晰的公開介面
- 依賴可注入或可模擬
- 提供測試策略與範圍

### 6. 向後相容性 (Backward Compatibility)
- 不破壞現有 API 介面
- 提供降級與回滾機制
- 明確標記 Breaking Changes

### 7. 效能與可靠性 (Performance & Reliability)
- 定義明確的效能目標
- 實作錯誤處理與重試機制
- 提供監控指標

### 8. 文件完整性 (Documentation Completeness)
- 每個公開介面都有說明
- 提供使用範例
- 記錄設計決策理由

## 設計檢查清單

設計文件必須包含:
- [ ] 架構模式說明
- [ ] 模組邊界圖
- [ ] 所有元件的型別定義
- [ ] 資料流程圖
- [ ] API 介面規格
- [ ] 測試策略
- [ ] 效能目標
- [ ] 風險評估
- [ ] 實施里程碑

# PP-Structure 謄本增強 PoC 評估(任務 10.3)

> 狀態:骨架已實作(可插拔、預設關、降級);**實測 benchmark 待容器 + 真實樣本**。
> 日期:2026-07-04

## 1. 目的
評估 PP-StructureV3(版面/表格/印章解析)對台灣地政謄本**欄位級準確率**與**資源成本**的效益,決定其定位:**主力 / 增強 / 不採用**。

## 2. 已交付(可離線驗證)
- `app/lib/ocr_enhanced/pp_structure.py`:`PPStructureEnhancer`——`is_enabled()`(依 `OCR_ENABLE_PP_STRUCTURE`,預設 **False**)、`parse_layout()`(惰性載入 PP-Structure,未安裝/失敗即回 None **降級**)。
- config:`OCR_ENABLE_PP_STRUCTURE=False`。
- 測試:`test_pp_structure.py`(4 passed)——預設停用、可切換、未安裝時優雅降級不 crash。
- **不阻塞主線**:預設關閉,謄本仍走「PaddleOCR + 規則 + LLM Vision」(任務 10.1/10.2),PP-Structure 為疊加增強。

## 3. 無法離線完成的部分(誠實標註)
- 本機**未安裝 paddleocr/paddlepaddle**,無法實跑 PP-StructureV3。
- **無台灣地政謄本公開 benchmark**(見 research.md caveat 7);繁中準確率須以自有樣本實測。
- 因此下列「實測數據」欄位為**待容器填入**,非本階段可產出。

## 4. 評估方法(容器階段執行)
以 `backend/data/` 之真實謄本樣本,對照兩組:
| 組別 | 流程 |
|---|---|
| Baseline | PaddleOCR + 規則 + LLM Vision(現行 10.1/10.2) |
| Enhanced | 上述 + PP-StructureV3 版面/表格/印章解析 |

**量測指標**(重用任務 5.1 `EvaluationService`):
- 欄位級準確率(地號/建號、面積、權利範圍、所有權人)
- CER
- 資源成本:單頁處理時間、記憶體/GPU 佔用、映像體積增量

**待填數據表**:
| 指標 | Baseline | Enhanced | 差異 |
|---|---|---|---|
| 欄位準確率 | (待測) | (待測) | — |
| CER | (待測) | (待測) | — |
| 單頁耗時 | (待測) | (待測) | — |

## 5. 決策準則(Go / No-Go)
- **升為主力**:Enhanced 欄位準確率相對 Baseline 提升 **≥ 10 個百分點**,且單頁耗時可接受(< 30s)、資源成本符合 <$15/月。
- **維持增強選項**:提升 3–10 個百分點,或資源成本偏高——保留 flag,特定密集/表格謄本才開。
- **不採用**:提升 < 3 個百分點或降級頻繁。

## 6. 本階段建議(依設計 + research 證據)
**維持「增強選項」定位**(預設關閉),理由:
1. 研究(research.md)指出 PP-Structure 的 SOTA 為 Baidu 第一方自報,繁中謄本無現成 benchmark——效益未經獨立驗證前不宜設為主力。
2. 主線(規則 + LLM Vision + few-shot)已能交付欄位抽取(任務 10.2),PP-Structure 屬邊際增強。
3. 新依賴增加映像體積與資源;在效益未證實前,預設關閉最符合 MVP + 成本敏感。

→ **結論:骨架保留、預設關;待容器以自有樣本實測後,依 §5 準則決定是否升為主力。**

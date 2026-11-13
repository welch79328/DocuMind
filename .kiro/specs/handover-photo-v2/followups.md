# 之後再做（handover-photo-v2 範圍外）

本線過程中發現、不擋本線驗收的問題。收線時每項都要有去處與決定者。

| # | 問題 | 證據 | 去處 | 決定者 |
|---|---|---|---|---|
| F1 | 不帶參數的點交舊路徑送模型前沒有依 EXIF 轉正；手機直拍照片可能以側躺方向送進模型 | `backend/app/lib/multi_type_ocr/processor.py` `_cap_image_pixels` 之後直接存 PNG；本線只在 v2 加 `_exif_upright`（R2 要求舊路徑不動） | 待業主決定（改了會讓不帶參數的回應變動，違反「逐欄位完全相同」） | 業主 |
| F2 | 修繕照片提示詞列了損傷範例詞，JGB 反映模型到處標「壁癌」 | JGB 需求文 三-2；`repair_photo` 提示詞（`grep -n 壁癌 backend/app/lib/multi_type_ocr/*.py`） | 開新線（修繕照片） | 業主 |
| F3 | 正式機修正樣本裡既有的點交 few-shot 範例沒查過內容與品質（v2 提示詞會不會被舊格式範例帶偏也沒驗） | 本線沒有查正式資料庫；`analyze.py` 以 `FewShotSelector(CorrectionSampleService(db))` 取範例 | 待查（DocuMind 正式庫沒有唯讀查詢 skill，需另定方式） | 業主 |

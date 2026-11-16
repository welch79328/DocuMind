# transcript-qwen-read — 之後再做

要什麼：本線範圍外、不擋本線驗收的問題登記處。
怎樣算做到：收線時每項都有去處（開新線、併入別線、不處理、待查）與決定者。

- F1 `/classify`、隱藏 `/api/v1/documents`、`/api/v1/ocr` 的 tesseract 要不要換成 Qwen。來源：Q-B，業主 2026-11-16 照建議「不動、記 followups」。決定者：業主。
- F2 Qwen 回的 y 座標比實際拉長 5–10%，越往頁面下方框越偏，v2 `position` 在 G3 有 30/137 格落到別列。同一頁不同次的倍率不同（1.053–1.103），不能用固定係數校正。證據：`~/jgb-archive/qwen-all-no-local-ocr-20261116/runs/a6-boxes.json`、`scripts/a6_boxes.py`；倍率是 G3 三頁 r2、r3 文字完全相同的行，`y_qwen` 對 `y_真值` 線性擬合得到的。來源：S1 A6 檢查（2026-11-16）。決定者：業主。
- F3 有些頁 Qwen 把整頁回成一段、框是整頁（[0,0,1000,1000] 或 [0,0,1,1]）：01_shilin_land、02_shilin_build、06_ruifang_build。全文不受影響（join 接法），但這些頁 v2 每個值的 `position` 都是整頁框。來源：S1 原始回覆 `runs/s1/r*/<頁>.raw.txt`。決定者：業主。
- F4 Qwen 的系統性讀錯：建物頁標籤「建物坐落地號」讀成「建物坐落地址」，7 頁 land_number 因此空掉；「權利種類：最高限額抵押權」那一行漏讀（3 頁）。可能是提示詞或抽欄規則要處理。來源：S1 錯誤分析 `runs/s1/grade25.json` 的 bad 清單。決定者：業主。
- F5 照片謄本的全文解析（`document_fields.transcripts`），本線的 rebuild 接法只有 25.6–26.8%（G2），11/09 評估資料夾的 C2 在同一批 15 張是 58.2%；兩者都是 Qwen 給座標再還原縮排，差距原因還沒查（提示詞、還原規則、`rule_postprocessed` 改字都有可能）。join（現行預設）是 8.9%。證據：`~/jgb-archive/qwen-all-no-local-ocr-20261116/runs/a5-fulltext.json`、`scripts/a5_fulltext.py`。來源：A5（2026-11-16）。決定者：業主。

## 收線去處（業主 2026-11-16「照建議」）

- F1：不處理。
- F2、F3：開新線，登在 `docs/planning/transcript-status.md` §5「Qwen 讀字的 v2 位置」，業主決定何時開。
- F4：開新線，登在同節「Qwen 讀字的系統性讀錯」，業主決定何時開。
- F5：待查，併入同節「照片／掃描謄本全文」那一列。

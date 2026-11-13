# 合約 v2 位置線：之後再做

| ID | 問題 | 證據 | 去處 | 決定者 |
|---|---|---|---|---|
| C-F1 | 電子合約規則抽取率低：合成租約六欄只抽到 3 欄（缺 date_start、date_end、tenant_name）；社宅租賃契約範本 3.1 的 tenant_name 抽成「契約審閱權」 | `~/jgb-archive/contract-v2-positions-20261113/runs/proto_contract_pos.txt`、`survey_contracts.txt` | 待定（收線時問） | 業主 |
| C-F2 | 照片、掃描合約沒有框：線上走直讀，模型不回框；直讀關閉時的 OCR 照片路徑也沒做行框 | plan.md §2 差距 4、§3 | 待定（收線時問） | 業主 |
| C-F3 | `INTEGRATION.md` 第 113、866 行說文字層頁會多 `pages[].text_layer: true`，實際 HTTP 回應沒有這個鍵（改前 `df41f2d` 就沒有，被 response_model 濾掉） | verifier 報告（`E/reviews/close-verify-20261113.md`）；`runs/online/c5_before_dold.json` `pages[]` 無 `text_layer` | 待定（收線時問） | 業主 |

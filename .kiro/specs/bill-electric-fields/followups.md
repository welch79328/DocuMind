# 之後再做（帳單電費 4 欄線）

要什麼：本線做到一半發現、不屬於本線範圍的事。
怎樣算做到：收線時每項都有去處（開新線、併入別線、不處理、待查）與決定者。

| ID | 問題 | 依據 | 影響 | 狀態 |
|---|---|---|---|---|
| F1 | 上傳檔一律 `acl="public-read"`，帳單放在 `uploads/ocr_others` | `analyze_service.py` `_upload_to_s3` | 帳單影像可能可被公開讀取；正式機現況未查（沒有 DocuMind 正式機唯讀工具） | 待查（資安相關，要業主決定是否開線） |
| F2 | 複核佇列無保存期限、無刪除端點；`/api/v1/review/*` 無認證 | grep `retention|ttl|expire|purge` 無相關；review 路由無 auth 依賴（正對照 `Depends(get_db)` 有） | 佇列內的欄位值（含地址）會一直留著、可被讀 | 待查（資安相關，要業主決定） |
| F3 | 正式機只有 http、無 token | `nginx/nginx.conf`、`frontend/nginx.conf` 只 `listen 80` | 帳單內容明文傳輸 | 待決（業主） |

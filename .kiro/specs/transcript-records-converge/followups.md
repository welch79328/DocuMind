# 之後再做（謄本輸出收斂＋欄位位置線）

本線過程中發現、不擋本線驗收的問題。2026-11-09 收線時業主裁定各項去處（「照建議」）。

| # | 問題 | 依據 | 去處 | 決定者 |
|---|---|---|---|---|
| F1 | `enable_llm=true` 時帶參數的補值正確率沒量（`enable_llm` 不帶時預設 `true`，25 欄可能含 LLM 補判的值，會照樣補進 `transcript_records`） | `docs/testing/transcript-v2-20261109.md` §7；INTEGRATION §3.1.4「補值」 | 開新線：先量 `enable_llm=true` 補值正確率，量完再決定要不要改（模型費用在該線計畫先估） | 業主 2026-11-09「照建議」 |
| F2 | `transcript_records` 是 `[]` 或不存在時，帶參數的回應沒有任何謄本值（舊欄位照樣拿掉），下游只能改用不帶參數 | INTEGRATION §3.1.4「帶參數時不回的舊格式」末條；`test_transcript_v2_spec.py::test_v2_07_absent_or_empty_records_still_drop_old_keys`；R8 已裁「只拿掉舊欄位」，改它要另開一片並重新核可 | 併入「移除舊格式、預設改新格式」那一版 | 業主 2026-11-09「照建議」 |
| F3 | 照片行框已知框錯：登記次序「0001」框到別部的同號行；`謄本.編號類型` 的「建號」框到抬頭 | `docs/testing/transcript-v2-20261109.md` §5；`E/runs/s3_c11_photo.txt` | 不處理（四種樣本皆過門檻，規格已寫可能框到別行） | 業主 2026-11-09「照建議」 |
| F4 | 照片的 `needs_confirmation` 抓不到 OCR 讀錯（7 個錯值 0 個列入，2/5 頁 `needs_review` 為 `false`）；兩種格式都一樣，不是本線引入 | `docs/testing/transcript-v2-20261109.md` §6；`E/runs/s4_nc_wrong_values.txt` | 照片品質線，待查（排在電子檔工作之後） | 業主 2026-11-09「照建議」 |
| F5 | D3 純影像 PDF 6 頁真 OCR 只解析出 1 張謄本（電子原檔 3 張），跨張的值會落在同一張或補不進 | `E/runs/s4_schema.txt` (3)、`E/runs/s4_schema_d3pdf_v2.json` | 照片品質線，待查（排在電子檔工作之後） | 業主 2026-11-09「照建議」 |
| F6 | §3.1.4「沒有行框（…開了多引擎共識…）」不完整：共識候選提取失敗、降級單引擎時照樣有行框與位置（收案 verifier F-1，P3） | `~/jgb-archive/transcript-photo-fullparse-eval-20261109/reviews/close-verify-s1-s4-20261109.md` | 下一版規格時補 | 業主 2026-11-09「照建議」 |
| F7 | §3.1.4「兩者都會建複核項目、回 `review_item_id`」應限 `needs_review=true`（F-2，P4）；單值補值跳過空字串 `""` 沒寫（F-5，P4） | 同上 | 下一版規格時補 | 業主 2026-11-09「照建議」 |
| F8 | 斜拍 D1p1、D3p3、D5p1（種子 \|3）OCR 回空，改前同；D4p2 斜拍沒有可比格 | 同上「待查」；`E/verify-close/am9b.txt` | 照片品質線，待查（排在電子檔工作之後） | 業主 2026-11-09「照建議」 |
| F9 | `document_type` 大寫或別名正規化後也套 v2，規格只寫 `transcript` | 同上「待業主裁」(1) | 不寫進規格，當未承諾行為 | 業主 2026-11-09「照建議」 |
| F10 | 照片 D1p2 帶參數回 `標示部.共有部分[0].權利範圍`＝`1000分之72`，標準答案 `10000分之672`（`E/truth/D1p2.json`），但 C1 的 7 個錯值（`plan.md` 原型實測列：商業、土造、過满段、最高限额抵押權、加强磚造、黃 ×2）沒有它；量測可能沒比對共有部分，若是，規格與實測紀錄的「錯 7」少算 | `E/runs/s3_http/D1p2_v2.json`；`E/runs/s4_pre_impl.txt` | 待查：查量測有沒有比對共有部分，查清後再決定要不要改數字 | 業主 2026-11-11「加 F10 後一起 commit」 |

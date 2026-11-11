# 謄本帶參數格式補 JGB 回報的 4 項缺口（2026-11-11）

紀錄。規則與凍結清單：`.kiro/specs/transcript-v2-jgb-gaps/acceptance.md`；計畫：同目錄 `plan.md`。對接規格：`docs/api/INTEGRATION.md` 2.10.0 §3.1.4（V2-07、V2-24～V2-26、V2-30～V2-32）。原始輸出在 `~/jgb-archive/transcript-photo-fullparse-eval-20261109/runs/`（下稱 `E/runs/`）。

## 1. 改了什麼
只改帶參數 `transcript_format=v2` 的補值（`backend/app/lib/multi_type_ocr/transcript_records.py::fill_from_rules`、`apply_transcript_format`），不帶參數的回應不變：
- R1 `謄本.段`、`謄本.小段`：整份 1 張時從全文切，鄉鎮市區以全國名稱表 `_TOWNS` 比對；不讀 25 欄 `section`／`subsection`。
- R2 清單補完後 `標示部.層次`、`所有權部` 仍空：用單值補第 1 筆。
- R3 `transcript_records` 是 `[]` 或不存在：依 `building_number`、`land_number` 組 1 張再補。
- R4 `共有部分` 由 `shared_parts` 補進時，車位寫進 `其他登記事項`，格式同電子謄本那一行。

## 2. 本機：照片補值
`E/runs/gaps_c1.txt`（指令 `E/measure_gaps.py`，受測物 `328ea6c`＋工作樹，2026-11-11 12:26）。15 頁模擬照片（D1～D5 各 3 種劣化，`enable_llm=false`），標準答案葉值 816 格。

| | 對 | 錯 | 缺 |
|---|---|---|---|
| `328ea6c`（改前） | 167 | 7 | 642 |
| 改後 | 184 | 8 | 624 |

- 改變的 18 格：R1 段小段對 11、錯 1；R2 層次與所有權人對 6、錯 0。
- 唯一新增的錯：D3p4 `謄本.段` 補「公国段」（答案「公園段」），OCR 本來就讀錯，25 欄 `section`＋`subsection` 是同一字。
- R3 模擬（15 頁 `transcript_records` 全清成 `[]`）：對 145、錯 8、缺 663；8 個錯值都等於不帶參數時舊欄位的同一個值（OCR 錯字 6、遮罩「黃**」讀成「黃」2）。
- R4：15 頁照片量不到——OCR 全文都沒有「停車位」，`shared_parts` 每頁 0 筆（本機用同一批 OCR 文字跑 `TranscriptProcessor`，2026-11-11）。格式由單元測試驗（含真實 `_PARKING_NUMBER` 取出的「2號」不會變「號號」）；含車位的 02 範本在線上量，見 §4。

## 3. 本機：電子 PDF 不受影響
同一檔：電子 5 份帶參數 `value` 還原後與 `transcript_records` 相同 5/5。單元測試 `backend/tests/unit/test_transcript_v2_spec.py` 38 項通過；全套 pytest 只有改前就失敗的 7 項（`test_contract_e2e` 3、`test_transcript_e2e` 3、`test_config_validation::test_valid_engine_names` 1）。

## 4. 線上
部署後補（C8～C11、C13）。

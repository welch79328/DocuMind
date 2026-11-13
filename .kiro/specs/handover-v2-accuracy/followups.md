# 之後再做（handover-v2-accuracy 範圍外）

| # | 問題 | 證據 | 去處 | 決定者 |
|---|---|---|---|---|
| F5 | 本機 108 次 Bedrock 呼叫，`api_usage_logs.llm_cost` 合計 0.0，費用沒記到；正式機是否相同未查 | `curl 127.0.0.1:8193/api/v1/usage` → `"total_llm_cost":0.0`（2026-11-13 本片，原始輸出在 `~/jgb-archive/handover-v2-accuracy-20261113/`） | 待查 | 業主 |
| F6 | 模型多報品項（冷氣 12 次、系統櫥櫃 9 次，新舊都有），多報品項的框跟著框錯，拉低框準度到 76.2%；唯一一個損傷框字對框偏 | `docs/testing/handover-v2-accuracy-20261113.md` B1、B2 | 要做再另開線（業主 R-acc-4） | 業主 |

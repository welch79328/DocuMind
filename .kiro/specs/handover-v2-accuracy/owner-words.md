# 準確率片業主原話

前一條線的原話正本：`.kiro/specs/handover-photo-v2/owner-words.md`（R-src-1～R-src-11）。

## R-acc-1：業主兩題選項回覆（AskUserQuestion，2026-11-13）

- 在哪跑：「本機跑 (Recommended)」
- 執行模式：「AUTO (Recommended)」

## R-acc-2：業主訊息（2026-11-13，計畫與確認版交出後）

```
核可
```

## R-acc-3：業主選項回覆（AskUserQuestion，2026-11-13，B0 停點）

- 兩位判員都標不出品項的 2 張（p05 戶外風景、p14 紙箱＋沙發一角）：「留著算 (Recommended)」——模型在這 2 張回的品項都算錯，只影響 precision。

## R-acc-4：業主兩題選項回覆（AskUserQuestion，2026-11-13，B2 停點與收案）

- 框準度 76.2%（門檻 80%）怎麼處理：「照實告訴 JGB、收線 (Recommended)」——說明第 6.3、7 點改成實測數字，建議 jgb2 把框當提示讓人確認、不自動裁圖；程式不改；減少多報／改善框記進之後再做。
- 報告與本線計畫、規則檔：「commit 並 push (Recommended)」——正式機不 pull。

# 業主原話（逐字，2026-11-13 本 session）

## R-src-1：業主貼上的 JGB 需求全文（原文在範例 JSON `damages` 那筆就被截斷，照原樣保留）

```
請 DocuMind 新增點交照片回傳格式 v2（#13541638271）

背景：jgb2 的「點交清單 › 用AI自動帶入」要改版。新版要讓 AI 帶入時能：
1. 把每個品項的照片裁成局部圖，附到對應品項的上傳框；
2. 照片中看得到的損傷，預填到「情況簡述」；
3. 每個品項有各自的信心值。現在同一張照片的每一項都是同一個 %。

所以需要 DocuMind 的點交照片辨識多回幾個欄位，內容如下。

一、切換方式
- jgb2 呼叫時帶參數 handover_format=v2，才回新格式。
- 不帶這個參數時，回傳必須跟現在逐個欄位完全相同。這樣 DocuMind 可以先上線，不影響現行的 jgb2。

二、v2 回傳（每張照片的 result.pages[0].structured_data）
- furniture[]、appliance[] 的每一項改成：{key, label, confidence, box, condition}
  - confidence：模型對「這一項」自評的 0～1。不要再拿整張照片的信心值當預設；模型沒給就回 null。
  - box：{"box":[x0,y0,x1,y1], "unit":"ratio"}，0～1 的比例，原點在左上角，跟 AI 謄本 transcript_positions 的格式相同。遇到以下情況回 null：抓不到；越界；x0≥x1 或 y0≥y1；框的面積小於整張的 0.5%。
  - condition：這個品項看得到的損傷，繁體中文，30 字以內（點交清單「情況簡述」上限 30 字）。沒看到損傷就回 ""。
- 新增 damages[]：不屬於清單品項的損傷，例如牆面、地板、天花板。每筆是 {text, box}，text 30 字以內，box 規則同上。
- 以下維持不變：space、space_label、description、整張的 confidence、dropped、白名單過濾、詞彙表、批次端點、一次最多 20 張。

範例：
{
  "space": "room",
  "space_label": "房間",
  "description": "臥室，雙人床靠牆，右側衣櫃",
  "confidence": 0.9,
  "furniture": [
    {"key": "bed", "label": "雙人床", "confidence": 0.93,
     "box": {"box": [0.12, 0.45, 0.68, 0.95], "unit": "ratio"},
     "condition": ""},
    {"key": "wardrobe", "label": "衣櫃", "confidence": 0.71,
     "box": null,
     "condition": "左門板下緣剝落"}
  ],
  "appliance": [],
  "damages": [
    {"text": "窗邊牆面水漬約手掌大", "box": {"box": [0.70, 0.10, 0.85,
  ],
  "dropped": []
}

三、請先確認的事
1. 座標刻度：Qwen3-VL 官方 README 只寫支援 relative position coordinat的是 0～1 還是 0～1000，在 DocuMind 端統一換算成 0～1 再回傳。
2. 損傷不要過度標註：之前修繕照片的提示詞列了範例清單，結果模型到處標「壁癌」。點交這邊的提示詞請不要列損傷範例清單，看不到就回空。
3. 預估工時，以及能不能先在本機或測試環境給一版，讓我們用同一批照片比

四、驗收（DocuMind 端）
- 單元測試：不帶 handover_format 時回傳與現行逐鍵相同；帶 v2 時欄位齊全；不合理的 box 都回 null；condition 與 text 超過 30 字時截斷。
- 同一批照片新舊並列：品項正確率不能比舊版低超過 3 個百分點。
```

## R-src-2：業主回覆（主會話問「照片要不要向 JGB 要」之後）

```
桌面/房間物件 照片
```

## R-src-3：業主四題選項回覆（AskUserQuestion）

- 試用版放哪：「先本機報告」
- 正確率怎麼算：「兩個都看」（precision 與 recall 各自不低超過 3 個百分點）
- 框準度檢查：「加」
- 照片範圍：「桌面 5 張＋舊 13 張」

## R-src-4：業主稍後訊息

```
先改格式 上版 準確率之後再確認
```

## R-src-5：業主三題選項回覆（AskUserQuestion，計畫第 3 版）

- 看得到的 `field_confidences`：「X：全部改用自評 (Recommended)」——四處都用模型對該項的自評；模型沒給的品項不放進 `field_confidences`；複核仍照舊算法。
- 正式機指令由誰執行：「你用 ssh 執行 (Recommended)」——授權代理只跑計畫第 6～8 步列出的指令與回滾指令；不讀不改 `.env`、不重建容器。
- 核可時三項現值未量：「接受 (Recommended)」——核可後第 1 步量座標刻度、部署前第 6 步量正式機現況；任何一項不符就停下回報。

## R-src-6：業主兩題選項回覆（AskUserQuestion，第 4 次審查後）

- 帶 v2 時 `needs_confirmation`／`extraction_confidence` 怎麼算：「依自評，沒給的列待確認 (Recommended)」——選項說明原文：「needs_confirmation 列出自評低於門檻的品項，以及模型沒給自評的品項；extraction_confidence 只平均有自評的品項，全都沒給就不放這個值。「沒給的列待確認」是我加的：寧可多叫人看一眼。」
- 改好計畫之後：「再審一次再交核可 (Recommended)」

## R-src-7：業主核可（plan.md 確認版交出後）

```
核可
```

## R-src-8：業主選項回覆（實作中，A1 與既有測試登記衝突）

- 「只登記這 1 個參數 (Recommended)」——選項說明原文：「在 ADDED_REQUEST_PARAMS 加 handover_format 和一行日期註記，其他測試一行都不改；A1 改成「除這一處登記外不改」。這個選項比你核可的 A1「不改」寬。」

## R-src-9：業主選項回覆（第 6 步停點：線上 HEAD 是 fd9f6d9，不是 df41f2d）

- 「等合約線收完再部署 (Recommended)」——選項說明原文：「等合約線的部署後檢查和文件 commit 都上 main，再把本線接到那個 commit；第 6 步的預期 SHA 改成那個 commit，其餘照計畫（線上 3 次送件、回滾只退本線 C1）。INTEGRATION 版號改成 2.12.0。這個選項比你核可的「預期 df41f2d」寬。」

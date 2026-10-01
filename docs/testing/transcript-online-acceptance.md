# 謄本線上驗收

> 最後更新 2026-10-01 ／ 對應版本 `fb3eb1e`

謄本功能的驗收分兩條線，**兩條都要過**：

| 線 | 驗什麼 | 在哪裡跑 |
|---|---|---|
| 抽取邏輯 | 給定一段文字，欄位抽得對不對 | 本機 `backend/tests/unit/test_transcript_*.py` |
| OCR 品質與速度 | 一張圖實際讀得出什麼、要多久 | **只能線上**——本機測試環境不裝 OCR 引擎，速度也只有線上數字才有意義 |

本機 unit 綠燈只證明前者。圖片、掃描件的結果一定要送線上看。

---

## 1. 範本

8 份，6 份取自地政機關公開的謄本導讀（測試段、遮蔽姓名），2 份是 repo 既有素材。
導讀原圖印有說明框與箭頭，已裁到謄本本體；仍殘留的說明框文字會被 OCR 讀進去，
所以這批的 OCR 品質會比業者實際上傳的略差。

| 檔案 | 來源 | 主要涵蓋 |
|---|---|---|
| `backend/data/transcript_samples/01_shilin_land.jpg` | [臺北市士林地政事務所「一分鐘看懂土地謄本」](https://www-ws.gov.taipei/Download.ashx?u=LzAwMS9VcGxvYWQvNTQxL3JlbGZpbGUvNTgyODEvODU0OTQxNC8wZTdlN2NiOC05MjYwLTRkN2MtOTkyNi01YTRlMGY4YzFmYjAucGRm&n=5LiA5YiG6ZCY55yL5oeC5Zyf5Zyw5bu654mp55m76KiY6KyE5pysLnBkZg%3D%3D&icon=.pdf) 第 1 頁 | 土地謄本、持分 70分之11、最高限額抵押權、抬頭被 OCR 拆行 |
| `.../02_shilin_build.jpg` | 同上 第 2 頁 | 大樓建物、附屬建物、**公設含車位編號**、停車位共計 |
| `.../03_kcg_build_multifloor.jpg` | [高雄市政府地政局「建物謄本導讀」](https://landp-ws.kcg.gov.tw/FS01/FilePath/18/relfile/279/175/58e35335-d1b2-4f28-bfcf-c4a78ab75f69.pdf) 標示部圖 | 透天一～四層、4 筆附屬建物 |
| `.../04_kcg_apartment_shared.jpg` | [高雄市政府地政局「土地及建物謄本導讀」](https://landp-ws.kcg.gov.tw/FS01/FilePath/13/relfile/163/358/f1fbb725-d91d-47d1-8fcd-f4b010f77880.pdf) 圖九 | 公寓、公設（水箱、樓梯間）、重測前舊建號 |
| `.../05_ntpc_land_mortgage.jpg` | [新北市汐止地政事務所「謄本閱讀秘笈」](https://www-ws.land.ntpc.gov.tw/001/upload/oldFile/userfiles/FD/file/%E8%AC%84%E6%9C%AC%E9%96%B1%E8%AE%80%E7%A7%98%E7%AC%88.pdf) 第 9 頁 | 只有他項權利部（普通抵押權、設定權利範圍） |
| `.../06_ruifang_build.jpg` | [新北市瑞芳地政事務所「建物謄本快易懂」](https://www.ntpc.gov.tw/uploaddowndoc?dis=news&file=news/202306301508252.pdf&filedisplay=(%E4%BF%AE)%E9%99%84%E4%BB%B62_%E5%BB%BA%E7%89%A9%E8%AC%84%E6%9C%AC%E5%BF%AB%E6%98%93%E6%87%82_v2_0629.pdf&flag=doc) | 公寓、坐落 2 筆地號、公設、抵押權 |
| `backend/data/建物謄本.jpg` | repo 既有（低解析掃描件） | 3 位共有人、一～三層＋騎樓、坐落 4 筆地號 |
| `backend/data/建物土地謄本-杭州南路一段.pdf` | repo 既有（電子謄本，有文字層） | 2 份土地＋1 份建物在同一個檔；不走 OCR |

- **正確答案**：`backend/data/transcript_samples/truth.json`（依範本圖人工判讀）。
- **線上基準**：`backend/data/transcript_samples/expected/*.json`——最近一次確認過的線上 `document_fields`。

## 2. 怎麼跑

```bash
cd backend
python scripts/transcript_online_acceptance.py --base http://54.248.201.66:8085 --out /tmp/acceptance
```

- 一律 `enable_llm=false`：不產生費用，量到的是規則抽取本身。
- 與基準不同時，**逐欄對照 `truth.json`** 判斷是改善還是退步；確認是改善再加 `--update-expected` 更新基準。
- ⚠️ **每跑一輪，線上複核佇列約多 7 筆**（圖片都會被判定需要複核，API 目前沒有略過選項）。
  跑完記下印出的 review id。

## 3. 目前結果（2026-10-01，`fb3eb1e`，線上實測）

| 項目 | 謄本上印的 | 讀出 | 讀錯 |
|---|---|---|---|
| 所有權人（含土地／建物部別） | 9 | 9 | 0 |
| 現行地號 | 10 | 10 | 0 |
| 各層面積 | 12 | 11（1 筆 OCR 沒讀到字） | 0 |
| 層次名稱＋面積成對 | 12 | 7（其餘 OCR 漏了名稱，只給面積） | 0 |
| 附屬建物面積 | 9 | 7 | 0 |
| 公設持分／本戶公設面積 | 3 | 3 ／ 3 | 0 |
| 公設內車位（編號＋持分） | 1 | 1 | 0 |

讀不到的都是 OCR 本身沒辨識出字（例如士林範本的層次那幾行），不是抽取規則漏掉。

**速度**（伺服器端，單頁）：電子謄本 0.1–0.8 秒；圖片 10–36 秒，主要受圖片大小與線上機只有 1 顆實體核心影響。
同一張圖各輪之間實測浮動最多約 4 秒。

## 4. 已知限制

- **仍會讀錯的版面（範本都沒有，未修）**：
  1. 車位編號那一行之後，「權利範圍:」的值折到下一行時，被當成公設持分。
  2. 說明文字「權利範圍:全部時…」的「全部」被當成持分。
- **品質加固（`fb3eb1e`）的 5 項修正只以合成輸入驗證過**——真實範本沒有那些版面，
  線上那一輪只證明「沒把原本對的弄壞」。
- **樓層只在「各層加總 = 總面積」驗證通過時才輸出**；對不上或沒讀到總面積，整頁不給（`floor_area_checks` 會說明原因）。
- 公設的「主要用途」不輸出：只能照抄 OCR 文字（「樓梯間」會被讀成「樓梯問」）。

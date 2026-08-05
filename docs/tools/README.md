# 行銷版 PDF 產生方式

> 目錄名稱刻意不用 `build/`——根目錄 `.gitignore` 的 `build/` 規則會
> 連同 `docs/build/` 一起排除,腳本會靜默地進不了版控。

`OCR系統-圖片文字辨識流程說明.pdf` 由 `build_marketing_pdf.py` 產生。
**實測數據出來後（任務 3.3 基準測試、14.1 效能驗收），請更新腳本內的數字表並重新產生。**

## 需求

- macOS 且已安裝 Google Chrome（用於列印 PDF，中文字型走系統 PingFang TC）
- Python 3

## 步驟

```bash
cd docs/tools

# 1. 取得 mermaid.js（僅需一次；刻意不進版控,3.2 MB）
curl -sSL -o mermaid.min.js \
  https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js

# 2. 組出可列印的 HTML（mermaid.js 會內嵌，產出後即可離線重跑）
python3 build_marketing_pdf.py

# 3. 由 Chrome 列印為 PDF
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --no-sandbox \
  --run-all-compositor-stages-before-draw \
  --virtual-time-budget=30000 --no-pdf-header-footer \
  --print-to-pdf="../OCR系統-圖片文字辨識流程說明.pdf" \
  "file://$PWD/marketing.html"
```

## 排版上踩過的坑

- **`--virtual-time-budget` 不可省略**：mermaid 是在瀏覽器端才畫圖，沒有給時間會印出空白圖。
- **只給 SVG `max-width` 會讓高圖溢出頁面被截斷**：腳本會依 `viewBox` 的長寬比換算出「同時不超過版面寬與高」的尺寸。
- **直式頁面要用偏高的圖**：寬扁的流程圖縮到頁寬後字級會掉到 5pt 左右，行銷讀者看不清。圖一因此用 `TD` 而非 `LR`。
- **子圖之間沒有連線時，mermaid 會把它們反序垂直堆疊**：圖二以隱形連結 `~~~` 串起，強制由左至右。
- **`section { page-break-inside: avoid }` 會造成空白頁**：長段落整段被推到下一頁。只在 `.mermaid`、表格、卡片這類小區塊上設。

## 內容來源

與 `docs/OCR_FLOW_FOR_MARKETING.md` 同步維護。兩者若有出入，以本腳本（PDF）為交付版本，但請一併更新 markdown，避免兩份文件對「哪些數字可以對外講」給出矛盾指引。

"""將行銷版 OCR 流程說明組成可列印的 HTML,供 Chrome headless 輸出 PDF。"""

import pathlib

HERE = pathlib.Path(__file__).parent
MERMAID = (HERE / "mermaid.min.js").read_text(encoding="utf-8")

DIAGRAM_1 = """
flowchart TD
    A["上傳文件<br/>PDF / JPG / PNG"] --> B{"依文件類型<br/>自動分流"}
    B --> C["四類文件<br/>各自最適流程"]
    C --> D["辨識文字<br/>並抓出關鍵欄位"]
    D --> E{"每個欄位<br/>系統有把握嗎"}
    E -->|"有把握"| F["直接可用<br/>不打擾使用者"]
    E -->|"沒把握"| G["立即回傳結果<br/>並標示出該欄位"]
    G --> H["使用者當場確認或修正<br/>他最知道正確答案"]
    H --> I["修正結果存回系統"]
    I -.->|"下次作為參考範例"| D
    H -.->|"使用者選擇稍後處理"| Q["複核佇列<br/>備援路徑"]
    Q -.-> I
    style E fill:#fdf6e7,stroke:#d99a2b,stroke-width:2px
    style G fill:#eaf1f8,stroke:#3d6f9e,stroke-width:2px
    style H fill:#f0ebf7,stroke:#6b4f9e,stroke-width:2px
    style I fill:#eef7f1,stroke:#2f6f4f,stroke-width:2px
    style Q fill:#f2f4f6,stroke:#9aa5b1,stroke-dasharray: 4 3
"""

DIAGRAM_2 = """
flowchart LR
    subgraph T["建物土地謄本"]
        direction TB
        T1["先去除浮水印<br/>謄本蓋滿防偽底紋"] --> T2["兩套辨識引擎<br/>並用比對"] --> T3["修正常見錯字<br/>與地政格式"]
    end
    subgraph B["帳單"]
        direction TB
        B1["影像去雜訊"] --> B2["辨識文字"] --> B3["抓票證式欄位<br/>支援民國年"]
    end
    subgraph C["合約"]
        direction TB
        C1{"PDF 本身<br/>就有文字嗎"} -->|"有"| C2["直接讀取<br/>完全跳過辨識"]
        C1 -->|"沒有 純掃描件"| C3["走完整辨識流程"]
    end
    subgraph R["修繕照片"]
        direction TB
        R1["不做文字辨識"] --> R2["直接看懂照片內容<br/>判斷瑕疵類型"]
    end
    T ~~~ B
    B ~~~ C
    C ~~~ R
    style C2 fill:#eef7f1,stroke:#2f6f4f,stroke-width:2px
"""

DIAGRAM_3 = """
flowchart TD
    A["辨識完成<br/>每個欄位各自打一個信心分數"] --> B{"該欄位<br/>夠有把握嗎"}
    B -->|"是"| C["直接可用<br/>不打擾使用者"]
    B -->|"否"| D["結果仍立即交付<br/>但把該欄位標示出來"]
    D --> E["使用者當場確認或修正<br/>可展開看各引擎的不同判讀"]
    E --> F["修正內容存為標準答案"]
    F --> G["下次遇到同類型 同版型的文件<br/>系統會參考這些標準答案"]
    G --> H["辨識準確度<br/>隨使用量提升"]
    H -.-> A
    style B fill:#fdf6e7,stroke:#d99a2b,stroke-width:2px
    style D fill:#eaf1f8,stroke:#3d6f9e,stroke-width:2px
    style E fill:#f0ebf7,stroke:#6b4f9e,stroke-width:2px
    style F fill:#eef7f1,stroke:#2f6f4f,stroke-width:2px
"""

BODY = f"""
<header class="cover">
  <div class="eyebrow">產品說明 · 行銷用</div>
  <h1>DocuMind<br><span class="sub">圖片文字辨識流程</span></h1>
  <p class="lede">使用者上傳文件 → 系統依文件類型用最適合的方式辨識 →
  沒把握的地方主動交給人確認 → 人的修正回存系統，下次更準。</p>
  <div class="cover-meta">
    <div><strong>對象</strong>行銷、業務、提案人員</div>
    <div><strong>版本</strong>2026-08-05</div>
  </div>
  <div class="cover-note">
    本文不含技術細節，可直接取用於簡報與提案。<br>
    文中所有效益數字皆標示為 <span class="tag tag-est">預估</span>，
    使用規範見末頁〈對外說明的注意事項〉。
  </div>
</header>

<section>
  <h2>1 ｜ 核心差異</h2>
  <p>市面上的文字辨識產品比的是「辨識得多準」。DocuMind 的關鍵差異是
  <strong>系統知道自己什麼時候不準，並且會主動說出來</strong>——不確定的欄位交由人確認，
  而不是硬猜一個看起來合理的答案。</p>

  <div class="cards">
    <div class="card">
      <div class="card-no">01</div>
      <h3>寧可承認不確定</h3>
      <p>每個欄位分別評分。只要<strong>任何一個</strong>欄位沒把握，整份就送人工複核，
      不會因為其他欄位準確就讓有問題的欄位混過去。<strong>但結果仍立即交付，複核在背景進行。</strong></p>
    </div>
    <div class="card">
      <div class="card-no">02</div>
      <h3>人的修正不會白費</h3>
      <p>每次人工修正都存成標準答案。下次遇到同類型、同版型文件會拿來參考。
      <strong>用得越多越準，不需重新訓練模型、不產生額外費用。</strong></p>
    </div>
    <div class="card">
      <div class="card-no">03</div>
      <h3>使用者就是最佳確認者</h3>
      <p>低信心欄位由<strong>使用者當場確認</strong>，不必養一組後台審查團隊。使用者是文件當事人、最知道正確答案。系統也不會拿自己的辨識結果來教自己——只有真人確認過的修正才進入學習池。</p>
    </div>
  </div>
</section>

<section>
  <h2>2 ｜ 支援的文件與產出</h2>
  <table>
    <thead>
      <tr><th style="width:22%">文件類型</th><th style="width:44%">系統自動抓出的欄位</th><th>適用場景</th></tr>
    </thead>
    <tbody>
      <tr><td><strong>建物土地謄本</strong></td><td>地號、建號、面積、權利範圍、所有權人</td><td>不動產估價、產權查核</td></tr>
      <tr><td><strong>帳單</strong></td><td>金額、日期、戶號</td><td>水電費、管理費核銷</td></tr>
      <tr><td><strong>合約</strong></td><td>合約編號、簽訂／生效日期、甲方、乙方、金額、幣別</td><td>合約管理、租賃建檔</td></tr>
      <tr><td><strong>修繕照片</strong></td><td>瑕疵標籤（漏水、壁癌、龜裂、設備損壞）、狀況描述</td><td>物件修繕評估、保險理賠</td></tr>
    </tbody>
  </table>
  <p class="note"><strong>上傳規格</strong>：PDF、JPG、PNG，單檔 20 MB 以內。
  多頁 PDF 會逐頁處理。修繕照片僅接受影像，不接受 PDF。</p>

  <h3 class="sub-h">另外兩項可以講的能力</h3>
  <table class="compact"><tbody>
    <tr><td style="width:30%"><strong>文件內容問答</strong></td>
        <td>上傳時可一併提問（例如「合約金額是多少？」），系統依辨識結果回答，不必自己翻文件找。</td></tr>
    <tr><td><strong>文件類型自動建議</strong></td>
        <td>系統會判讀並建議文件類型，減少選錯的機會；最終仍以使用者指定為準。</td></tr>
  </tbody></table>
</section>

<section>
  <h2>3 ｜ 整體流程</h2>
  <div class="mermaid">{DIAGRAM_1}</div>
  <p class="caption"><strong>關鍵：確認的人就是使用者本人，不是後台審查團隊。</strong>使用者是文件當事人，最知道正確答案，所以由他當場確認最快也最準——不需要額外的複核人力，也不會有等待窗口。高信心欄位完全不打擾使用者。灰色虛線的複核佇列僅為「使用者選擇稍後處理」時的備援路徑。</p>
</section>

<section>
  <h2>4 ｜ 四類文件各走各的路</h2>
  <p>一般 OCR 產品是「一套流程通吃所有文件」。DocuMind 針對每一類文件用不同做法，
  因為它們的難點完全不同。</p>
  <div class="mermaid">{DIAGRAM_2}</div>

  <h3 class="sub-h">三個可以對外講的設計亮點</h3>
  <ol class="highlights">
    <li><strong>謄本先去浮水印</strong>——謄本印滿防偽底紋，直接丟給一般 OCR 會把底紋讀成亂碼。</li>
    <li><strong>謄本與帳單並用兩套辨識引擎</strong>——互相比對可降低單一引擎誤判的風險。</li>
    <li><strong>合約會先看有沒有現成文字</strong>——電子簽章或數位產製的合約 PDF 本身就帶文字，
    系統直接讀取、跳過辨識，<strong>又快又不花辨識成本</strong>。只有掃描件才走完整流程。</li>
    <li><strong>修繕照片不走文字辨識</strong>——照片上本來就沒字，走的是「看懂影像內容」，
    直接判斷是漏水還是壁癌。</li>
  </ol>
</section>

<section>
  <h2>5 ｜ 越用越準的機制</h2>
  <p>這是本產品最核心、也最好講的部分。</p>
  <div class="mermaid">{DIAGRAM_3}</div>
</section>

<section>
  <h2>6 ｜ 交叉比對：揪出「看起來合理但其實錯了」</h2>
  <p>這是本產品與通用 AI 最根本的差別，值得單獨講。</p>
  <p>傳統 OCR 讀錯會產生亂碼，肉眼一看就知道有問題。<strong>生成式 AI 讀錯則會產生
  語法通順、格式正確、但數字是錯的內容</strong>——拼字檢查抓不到，人也看不出來。
  這種錯誤一旦流入估價或合約建檔，代價很高。</p>
  <p>DocuMind 的作法是<strong>讓兩套獨立的辨識引擎各自讀同一份文件，再逐個欄位比對</strong>：</p>
  <table class="compact"><tbody>
    <tr><td style="width:34%"><strong>兩套引擎讀出同一個答案</strong></td>
        <td>該欄位維持高信心，直接可用</td></tr>
    <tr><td><strong>兩套引擎讀出不同答案</strong></td>
        <td>該欄位信心度被壓低並標示出來，使用者可展開看兩邊分別讀到什麼，當場判斷</td></tr>
  </tbody></table>
  <p class="caption">關鍵在於：這個訊號<strong>不依賴 AI 自己說它有多確定</strong>。
  模型對自己的判斷過度自信是常見問題，而「兩套引擎是否得出一致結果」是外部、可驗證的證據。
  比對時會先做格式正規化，例如 <span class="dim">153.00</span> 與
  <span class="dim">153</span>、民國與西元紀年會視為相同，避免把格式差異誤報為不一致。</p>
</section>

<section>
  <h2>7 ｜ 效益與規格數字</h2>
  <div class="callout callout-warn">
    <strong>下表數字目前皆為預估值。</strong>準確率基準測試需要先由專業人員完成標註資料集，
    目前正在進行中。實測數據產出後將更新本表。
  </div>
  <table>
    <thead>
      <tr><th style="width:32%">項目</th><th style="width:20%">數字</th><th style="width:14%">狀態</th><th>依據</th></tr>
    </thead>
    <tbody>
      <tr><td>關鍵欄位準確率<br><span class="dim">地號、建號、面積、金額</span></td>
          <td class="num">95%</td><td><span class="tag tag-est">預估</span></td>
          <td>產品設定目標，基準測試尚未執行</td></tr>
      <tr><td>整體辨識準確率</td><td class="num">85%</td><td><span class="tag tag-est">預估</span></td>
          <td>產品設定目標，基準測試尚未執行</td></tr>
      <tr><td>單頁處理時間</td><td class="num">30 秒內</td><td><span class="tag tag-est">預估</span></td>
          <td>設計目標，不含選用的 AI 加強校正；效能驗收尚未執行</td></tr>
      <tr><td>月營運成本</td><td class="num">$15 以下</td><td><span class="tag tag-est">預估</span></td>
          <td>成本試算，實際依用量與部署方式而定</td></tr>
      <tr><td>單檔上限</td><td class="num">20 MB</td><td><span class="tag tag-fact">已確認</span></td>
          <td>系統實際限制</td></tr>
      <tr><td>支援格式</td><td class="num">PDF / JPG / PNG</td><td><span class="tag tag-fact">已確認</span></td>
          <td>系統實際支援</td></tr>
      <tr><td>「越用越準」的提升幅度</td><td class="num">未量測</td><td><span class="tag tag-est">預估</span></td>
          <td>回饋機制已實作並可運作，但提升幅度尚無實測數據</td></tr>
    </tbody>
  </table>
</section>

<section>
  <h2>8 ｜ 常見問題</h2>
  <dl class="faq">
    <dt>跟直接用 ChatGPT 讀文件差在哪？</dt>
    <dd>兩點。第一，通用 AI 讀錯時會產生<strong>看起來很合理但數字是錯的</strong>結果，
    一般人看不出來；DocuMind 用多重檢查揪出這種狀況並主動示警。
    第二，資料可以完全留在客戶自己的機器，不外送第三方。</dd>

    <dt>資料會外流嗎？</dt>
    <dd>架構上可設定為<strong>完全本地運行</strong>，文件內容不傳送到任何外部服務。
    辨識引擎本身就在本機執行，AI 校正層也可切換為本地模型。
    <span class="inline-warn">兩點要注意：一、修繕照片走的是影像理解，全本地運行需要另外部署本地視覺模型，不是把雲端關掉就會動。二、正式的全本地運行驗收測試尚未完成，若客戶要寫進合約，請先找工程團隊確認。</span></dd>

    <dt>辨識要多久？</dt>
    <dd>預估單頁 30 秒內完成（不含選用的 AI 加強校正）。
    <span class="inline-warn">對外請描述為「數十秒級」，不要給保證秒數。</span></dd>

    <dt>一定要人工複核嗎？</dt>
    <dd><strong>不需要專門的複核人力。</strong>設計上由使用者當場確認低信心欄位——他是文件當事人，最知道正確答案。結果一律立即回傳，高信心欄位完全不需要操作。若使用者當下不想處理，可留待複核佇列稍後處理，那是備援而非主要路徑。
    門檻可依客戶需求調整——要求高就調嚴（更多進複核），求快就調鬆。</dd>

    <dt>支援簡體中文或英文嗎？</dt>
    <dd>目前主力是<strong>繁體中文</strong>，並針對台灣地政用語、民國紀年、地號格式做過最佳化。
    其他語言需另行評估。</dd>
  </dl>
</section>

<section class="page-break">
  <h2>9 ｜ 對外說明的注意事項</h2>

  <div class="callout callout-danger">
    <strong>所有效益數字目前均為預估值，尚未完成實測驗證。</strong>
    對外引用時<u>必須</u>加註「預估」二字，不可呈現為已驗證數據。
  </div>

  <div class="do-dont">
    <div class="do">
      <h4>可以這樣講</h4>
      <ul>
        <li>系統會針對每個欄位評估把握程度，沒把握的主動交由人工確認</li>
        <li>人工修正會回饋到系統，使用越久越準確</li>
        <li>支援完全本地部署，資料不外送<br><span class="dim">修繕照片需另外部署本地視覺模型</span></li>
        <li>預估關鍵欄位準確率可達 95%（目標值，實測進行中）</li>
      </ul>
    </div>
    <div class="dont">
      <h4>不可以這樣講</h4>
      <ul>
        <li>準確率<u>達</u> 95%</li>
        <li>比 ChatGPT 準 X%</li>
        <li>保證單頁 30 秒完成</li>
        <li>任何未加註「預估」的百分比或秒數</li>
      </ul>
    </div>
  </div>

  <h3 class="sub-h">需要更多素材時</h3>
  <table class="compact">
    <tbody>
      <tr><td style="width:34%">實際辨識效果截圖</td><td>請工程團隊提供 demo 環境操作畫面</td></tr>
      <tr><td>準確率實測數據</td><td>待基準測試完成後提供</td></tr>
      <tr><td>部署方式與成本</td><td>參見《部署指南》<span class="dim">docs/DEPLOYMENT.md</span></td></tr>
      <tr><td>客製化文件類型可行性</td><td>請工程團隊評估，架構上支援擴充</td></tr>
    </tbody>
  </table>
</section>
"""

CSS = """
@page { size: A4; margin: 16mm 15mm 18mm; }

* { box-sizing: border-box; }

html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }

body {
  font-family: "PingFang TC", "Heiti TC", "Hiragino Sans CNS", sans-serif;
  font-size: 10.2pt; line-height: 1.75; color: #1c2530; margin: 0;
  letter-spacing: 0.01em;
}

/* ---------- 封面 ---------- */
.cover { padding: 4mm 0 8mm; border-bottom: 2.5pt solid #1c2530; margin-bottom: 9mm; }
.eyebrow {
  font-size: 8.4pt; letter-spacing: 0.22em; color: #7d8896;
  text-transform: uppercase; margin-bottom: 5mm;
}
.cover h1 {
  font-size: 27pt; line-height: 1.22; margin: 0 0 5mm; font-weight: 700;
  letter-spacing: -0.01em;
}
.cover h1 .sub { font-size: 17pt; font-weight: 500; color: #3d4a5a; }
.lede {
  font-size: 11.4pt; line-height: 1.8; color: #2b3846; margin: 0 0 7mm;
  padding-left: 4mm; border-left: 2.5pt solid #2f6f4f; max-width: 155mm;
}
.cover-meta { display: flex; gap: 14mm; font-size: 9.2pt; color: #55616f; margin-bottom: 5mm; }
.cover-meta strong {
  display: block; font-size: 7.8pt; letter-spacing: 0.14em;
  color: #97a1ad; margin-bottom: 1mm; font-weight: 600;
}
.cover-note {
  font-size: 9pt; color: #55616f; background: #f5f7f9;
  padding: 3.5mm 4mm; border-radius: 2mm; line-height: 1.7;
}

/* ---------- 標題 ---------- */
section { margin-bottom: 9mm; }
h2 {
  font-size: 14pt; margin: 0 0 4mm; padding-bottom: 2mm; font-weight: 700;
  border-bottom: 1pt solid #d9dee4; letter-spacing: 0.01em;
}
h3.sub-h { font-size: 11pt; margin: 6mm 0 3mm; font-weight: 700; color: #2b3846; }
p { margin: 0 0 3.5mm; }

/* ---------- 卡片 ---------- */
.cards { display: flex; gap: 4mm; margin-top: 5mm; }
.card {
  flex: 1; background: #f5f7f9; border-radius: 2.5mm;
  padding: 4mm 4mm 4.5mm; border-top: 2.5pt solid #2f6f4f;
}
.card-no {
  font-size: 8pt; font-weight: 700; color: #2f6f4f;
  letter-spacing: 0.1em; margin-bottom: 1.5mm;
}
.card h3 { font-size: 10.4pt; margin: 0 0 2mm; font-weight: 700; }
.card p { font-size: 9pt; line-height: 1.68; margin: 0; color: #3d4a5a; }

/* ---------- 表格 ---------- */
table { width: 100%; border-collapse: collapse; margin: 3mm 0 4mm; font-size: 9.4pt; }
th {
  background: #2b3846; color: #fff; text-align: left; font-weight: 600;
  padding: 2.6mm 3mm; font-size: 9pt; letter-spacing: 0.03em;
}
td { padding: 2.6mm 3mm; border-bottom: 0.6pt solid #e3e7ec; vertical-align: top; }
tbody tr:nth-child(even) { background: #f8fafb; }
table.compact td { font-size: 9.2pt; }
td.num { font-weight: 700; font-size: 10.4pt; color: #1c2530; white-space: nowrap; }
.dim { color: #8a94a1; font-size: 8.6pt; }

/* ---------- 標籤 ---------- */
.tag {
  display: inline-block; font-size: 8pt; font-weight: 700; padding: 0.6mm 2mm;
  border-radius: 1mm; letter-spacing: 0.04em; white-space: nowrap;
}
.tag-est { background: #fdf0d5; color: #8a5a00; border: 0.6pt solid #e8c98a; }
.tag-fact { background: #e3f2e8; color: #1f5c3d; border: 0.6pt solid #a8ceb8; }

/* ---------- 提示框 ---------- */
.callout {
  padding: 3.5mm 4mm; border-radius: 2mm; font-size: 9.4pt;
  line-height: 1.7; margin: 3mm 0 4mm;
}
.callout-warn { background: #fdf6e7; border-left: 2.5pt solid #d99a2b; }
.callout-danger { background: #fdeceb; border-left: 2.5pt solid #c0392b; }
.inline-warn { color: #a03a2c; font-size: 8.9pt; }
.note {
  font-size: 9.2pt; color: #55616f; background: #f5f7f9;
  padding: 2.8mm 3.5mm; border-radius: 1.5mm; margin-top: 2mm;
}
.caption { font-size: 8.9pt; color: #6b7683; margin-top: 2mm; line-height: 1.65; }

/* ---------- 清單 ---------- */
ol.highlights { margin: 0; padding-left: 5mm; }
ol.highlights li { margin-bottom: 2.5mm; line-height: 1.72; }

.faq dt {
  font-weight: 700; font-size: 10.2pt; margin: 4.5mm 0 1.5mm; color: #1c2530;
}
.faq dt::before { content: "Q "; color: #2f6f4f; font-weight: 700; }
.faq dd { margin: 0; padding-left: 5.5mm; color: #3d4a5a; line-height: 1.72; }

/* ---------- 可以/不可以 ---------- */
.do-dont { display: flex; gap: 4mm; margin: 4mm 0; }
.do, .dont { flex: 1; border-radius: 2.5mm; padding: 3.5mm 4mm; }
.do { background: #eef7f1; border: 0.8pt solid #b9d9c6; }
.dont { background: #fdeeed; border: 0.8pt solid #eec3bd; }
.do h4, .dont h4 { margin: 0 0 2.5mm; font-size: 10pt; font-weight: 700; }
.do h4 { color: #1f5c3d; }
.do h4::before { content: "✓ "; }
.dont h4 { color: #a03a2c; }
.dont h4::before { content: "✕ "; }
.do ul, .dont ul { margin: 0; padding-left: 4.5mm; font-size: 9.2pt; line-height: 1.68; }
.do li, .dont li { margin-bottom: 1.8mm; }

/* ---------- 圖表 ---------- */
/* 尺寸由 JS 依實際長寬比換算,確保整張圖不跨頁、不溢出版面 */
.mermaid { text-align: center; margin: 5mm 0 3mm; page-break-inside: avoid; }

/* ---------- 分頁 ---------- */
/* 只在必要處強制分頁;section 不設 avoid,否則長段落會整段被推走留下空白頁 */
.page-break { page-break-before: always; }
.card, table, .do-dont, .callout, .do-dont > div { page-break-inside: avoid; }
h2, h3 { page-break-after: avoid; }
.faq dt { page-break-after: avoid; }
.faq dd { page-break-inside: avoid; }
"""

HTML = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>DocuMind 圖片文字辨識流程說明（行銷版）</title>
<style>{CSS}</style>
<script>{MERMAID}</script>
</head>
<body>
{BODY}
<script>
mermaid.initialize({{
  startOnLoad: false,
  theme: 'base',
  themeVariables: {{
    fontFamily: '"PingFang TC","Heiti TC",sans-serif',
    fontSize: '15px',
    primaryColor: '#eef2f6',
    primaryTextColor: '#1c2530',
    primaryBorderColor: '#93a1b2',
    lineColor: '#7d8896',
    tertiaryColor: '#f8fafb',
    clusterBkg: '#f5f7f9',
    clusterBorder: '#c8d1da'
  }},
  flowchart: {{ useMaxWidth: false, curve: 'basis',
                nodeSpacing: 30, rankSpacing: 36, padding: 8 }}
}});

// A4 直式扣掉頁邊距後的可用範圍
const MAX_W_MM = 178;
const MAX_H_MM = 196;

(async () => {{
  await mermaid.run({{ querySelector: '.mermaid' }});

  // 依 viewBox 的長寬比換算出「同時不超過寬與高」的尺寸。
  // 只給 max-width 會讓高圖被放大到溢出頁面 —— 這是第一版被截斷的原因。
  document.querySelectorAll('.mermaid svg').forEach(svg => {{
    const box = svg.viewBox && svg.viewBox.baseVal;
    if (!box || !box.width || !box.height) return;
    const ratio = box.width / box.height;

    let w = MAX_W_MM;
    let h = w / ratio;
    if (h > MAX_H_MM) {{ h = MAX_H_MM; w = h * ratio; }}

    svg.removeAttribute('width');
    svg.removeAttribute('height');
    svg.style.maxWidth = 'none';
    svg.style.width = w.toFixed(1) + 'mm';
    svg.style.height = h.toFixed(1) + 'mm';
  }});

  document.body.dataset.rendered = 'true';
}})();
</script>
</body>
</html>
"""

out = HERE / "marketing.html"
out.write_text(HTML, encoding="utf-8")
print(f"HTML 產出: {out}  ({len(HTML)/1024/1024:.1f} MB)")

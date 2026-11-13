"""將行銷版 OCR 流程說明組成可列印的 HTML,供 Chrome headless 輸出 PDF。"""

import pathlib

HERE = pathlib.Path(__file__).parent
MERMAID = (HERE / "mermaid.min.js").read_text(encoding="utf-8")

DIAGRAM_1 = """
flowchart TD
    A["上傳文件<br/>PDF / JPG / PNG"] --> B{"依文件類型<br/>自動分流"}
    B --> C["六類文件<br/>各自最適流程"]
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
        T1{"有現成文字嗎<br/>網路申領的電子謄本"} -->|"有"| T2["直接讀取<br/>跳過辨識"]
        T1 -->|"掃描或照片"| T3["先去除浮水印<br/>謄本蓋滿防偽底紋"] --> T4["辨識文字"] --> T5["修正常見錯字<br/>與地政格式"]
    end
    subgraph D["帳單、合約"]
        direction TB
        D1{"有現成文字嗎<br/>電子檔"} -->|"有"| D2["直接讀取<br/>跳過辨識"]
        D1 -->|"照片或掃描"| D3["AI 讀圖模型<br/>整頁直接讀欄位"]
    end
    subgraph R["收據、發票"]
        direction TB
        R1["不論電子檔或照片"] --> R2["AI 讀圖模型<br/>整頁直接讀金額與日期"]
    end
    subgraph P["修繕、點交照片"]
        direction TB
        P1["不做文字辨識"] --> P2["直接看懂照片內容<br/>判斷瑕疵或清點品項"]
    end
    T ~~~ D
    D ~~~ R
    R ~~~ P
    style T2 fill:#eef7f1,stroke:#2f6f4f,stroke-width:2px
    style D2 fill:#eef7f1,stroke:#2f6f4f,stroke-width:2px
"""

DIAGRAM_3 = """
flowchart TD
    A["辨識完成<br/>每個欄位各自打一個信心分數"] --> B{"該欄位<br/>夠有把握嗎"}
    B -->|"是"| C["直接可用<br/>不打擾使用者"]
    B -->|"否"| D["結果仍立即交付<br/>但把該欄位標示出來"]
    D --> E["使用者當場確認或修正"]
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
    <div><strong>版本</strong>2026-11-13</div>
  </div>
  <div class="cover-note">
    本文不含技術細節，可直接取用於簡報與提案。<br>
    文中數字分 <span class="tag tag-est">預估</span>（目標或推算）與
    <span class="tag tag-fact">實測</span>（小樣本量測，附日期與樣本數），
    使用規範見末頁〈對外說明的注意事項〉。
  </div>
</header>

<section>
  <h2>1 ｜ 核心差異</h2>
  <p>市面上的文字辨識產品比的是「辨識得多準」。DocuMind 的關鍵差異是
  <strong>系統會評估自己哪裡可能不準，並且會主動說出來</strong>——不確定的欄位交由人確認，
  而不是硬猜一個看起來合理的答案。</p>
  <p class="caption">限制：掃描件、照片上被讀錯的字，可能帶著高分數混過去，不一定會被標出來（見第 6 節）。</p>

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
      <strong>用得越多越準，不需重新訓練模型、不產生額外費用。</strong>（提升幅度尚未量測。）</p>
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
      <tr><td><strong>建物土地謄本</strong></td><td>電子謄本上印的每一項：地號、建號、門牌、面積、權利範圍、所有權人、他項權利…，並判讀有無他項權利、限制登記、信託</td><td>不動產估價、產權查核</td></tr>
      <tr><td><strong>帳單</strong></td><td>金額、日期、戶號</td><td>水電費、管理費核銷</td></tr>
      <tr><td><strong>收據、發票</strong></td><td>金額（整張總計）、日期</td><td>費用核銷、記帳</td></tr>
      <tr><td><strong>合約</strong></td><td>合約編號、簽訂／生效日期、甲方、乙方、金額、幣別；租約另抓租期起訖、月租金、押金、租賃地址、承租人</td><td>合約管理、租賃建檔</td></tr>
      <tr><td><strong>修繕照片</strong></td><td>瑕疵標籤（漏水、壁癌、龜裂、設備損壞）、受損物件、狀況描述</td><td>物件修繕評估、保險理賠</td></tr>
      <tr><td><strong>點交照片</strong></td><td>空間（客廳、臥室…）、照片裡的家具與家電、狀況描述；品項只回點交清單詞彙表裡有的</td><td>租屋點交清點</td></tr>
    </tbody>
  </table>
  <p class="note"><strong>上傳規格</strong>：PDF、JPG、PNG，單檔 20 MB 以內。
  多頁 PDF 會逐頁處理。修繕、點交照片僅接受影像，不接受 PDF。</p>

  <h3 class="sub-h">另外兩項可以講的能力</h3>
  <table class="compact"><tbody>
    <tr><td style="width:30%"><strong>文件內容問答</strong></td>
        <td>上傳時可一併提問（例如「合約金額是多少？」），系統依辨識結果回答，不必自己翻文件找。</td></tr>
    <tr><td><strong>文件類型自動建議</strong></td>
        <td>系統會判讀並建議文件類型，減少選錯的機會；最終仍以使用者指定為準。目前能建議謄本、合約、收據，帳單不會被建議。</td></tr>
  </tbody></table>
</section>

<section>
  <h2>3 ｜ 整體流程</h2>
  <div class="mermaid">{DIAGRAM_1}</div>
  <p class="caption"><strong>關鍵：確認的人就是使用者本人，不是後台審查團隊。</strong>使用者是文件當事人，最知道正確答案，所以由他當場確認最快也最準——不需要額外的複核人力，也不會有等待窗口。高信心欄位完全不打擾使用者。灰色虛線的複核佇列僅為「使用者選擇稍後處理」時的備援路徑。</p>
</section>

<section>
  <h2>4 ｜ 六類文件各走各的路</h2>
  <p>一般 OCR 產品是「一套流程通吃所有文件」。DocuMind 針對每一類文件用不同做法，
  因為它們的難點完全不同。</p>
  <div class="mermaid">{DIAGRAM_2}</div>

  <h3 class="sub-h">四個可以對外講的設計亮點</h3>
  <ol class="highlights">
    <li><strong>電子檔直接讀現成文字</strong>——網路申領的電子謄本、數位產製的帳單與合約 PDF 本身就帶文字，
    系統直接讀取、跳過辨識，<strong>又快又不花辨識成本</strong>（電子謄本整份不到 0.1 秒，實測見第 7 節）。收據不走這條，一律交 AI 讀圖。</li>
    <li><strong>掃描的謄本先去浮水印</strong>——謄本印滿防偽底紋，直接丟給一般 OCR 會把底紋讀成亂碼。</li>
    <li><strong>帳單、合約、收據的照片與掃描件交 AI 讀圖</strong>——這類文件版面五花八門，
    由看得懂版面的 AI 讀圖模型整頁直接讀出欄位，不先辨識文字再找欄位。</li>
    <li><strong>修繕、點交照片不走文字辨識</strong>——照片上本來就沒字，走的是「看懂影像內容」，
    直接判斷是漏水還是壁癌、房間裡有哪些家具家電。點交品項只回清單上有的，寧可漏報、不憑空多報。</li>
  </ol>
</section>

<section>
  <h2>5 ｜ 越用越準的機制</h2>
  <p>這是本產品最核心、也最好講的部分。</p>
  <div class="mermaid">{DIAGRAM_3}</div>
</section>

<section>
  <h2>6 ｜ 揪出「看起來合理但其實錯了」</h2>
  <p>這是本產品與通用 AI 最根本的差別，值得單獨講，也要講清楚做到哪裡。</p>
  <p>傳統 OCR 讀錯會產生亂碼，肉眼一看就知道有問題。<strong>生成式 AI 讀錯則會產生
  語法通順、格式正確、但數字是錯的內容</strong>——拼字檢查抓不到，人也看不出來。
  這種錯誤一旦流入估價或合約建檔，代價很高。</p>
  <table class="compact"><tbody>
    <tr><td style="width:26%"><strong>現在做到的：格式檢查</strong></td>
        <td>檢查每個欄位的值像不像該有的樣子，例如面積、金額欄位出現地號的形狀、日期讀不成日期、編號欄位裡沒有數字。
        不像的就壓低信心並標示出來，交給人確認。這個訊號<strong>不依賴 AI 自己說它有多確定</strong>。</td></tr>
    <tr><td><strong>還擋不住的</strong></td>
        <td>字被讀成另一個看起來合理的字（例如「土」讀成「上」、金額 23 讀成 25），格式檢查抓不到，可能帶著高分數混過去。
        2026-10-20 實測：5 份真實電子謄本轉成模擬掃描與拍照圖（17 頁），讀錯的 23 欄中有 16 欄沒被標出來。</td></tr>
    <tr><td><strong>兩套引擎交叉比對</strong></td>
        <td>功能已做好，<strong>目前線上沒有開</strong>（線上只跑一套辨識引擎），不可對外說成現有能力。</td></tr>
  </tbody></table>
</section>

<section>
  <h2>7 ｜ 效益與規格數字</h2>
  <div class="callout callout-warn">
    <strong>準確率還沒有大樣本的基準測試。</strong>下表的實測數字都是小樣本，
    引用時要連同日期與樣本數一起講，不可說成統計結果。
  </div>
  <table>
    <thead>
      <tr><th style="width:26%">項目</th><th style="width:18%">數字</th><th style="width:12%">狀態</th><th>依據</th></tr>
    </thead>
    <tbody>
      <tr><td>電子謄本欄位正確率</td><td class="num">3 份全對</td><td><span class="tag tag-fact">實測</span></td>
          <td>2026-10-14～15 線上，5 份真實電子謄本：逐欄對照的 3 份全對；5 份共 640 個原文值 0 不符</td></tr>
      <tr><td>掃描、拍照謄本<br><span class="dim">25 個主要欄位</span></td><td class="num">約 97%</td><td><span class="tag tag-fact">實測</span></td>
          <td>2026-10-20 線上，5 份電子謄本轉成模擬掃描與拍照圖（17 頁）；較難的手機斜拍照片另批實測只有 58%（2026-11-09，非線上）</td></tr>
      <tr><td>收據金額＋日期</td><td class="num">41／44 欄</td><td><span class="tag tag-fact">實測</span></td>
          <td>2026-10-29 線上，22 張公開授權的台灣收據，3 次結果相同</td></tr>
      <tr><td>帳單金額、日期、戶號</td><td class="num">14／15 欄</td><td><span class="tag tag-fact">實測</span></td>
          <td>2026-10-29 線上，5 張帳單</td></tr>
      <tr><td>合約欄位<br><span class="dim">照片與掃描件</span></td><td class="num">81%</td><td><span class="tag tag-fact">實測</span></td>
          <td>2026-10-29 線上，5 份合約（90／111 欄），盲判</td></tr>
      <tr><td>點交照片品項</td><td class="num">找到 76%</td><td><span class="tag tag-fact">實測</span></td>
          <td>2026-11-13 本機，18 張照片各 3 次，盲判標準答案；回報的品項 70% 確實在照片上</td></tr>
      <tr><td>處理時間：電子謄本</td><td class="num">整份 0.04–0.07 秒</td><td><span class="tag tag-fact">實測</span></td>
          <td>2026-10-15 線上，5 份，伺服器端計時</td></tr>
      <tr><td>處理時間：掃描、拍照謄本</td><td class="num">每頁 15–24 秒</td><td><span class="tag tag-fact">實測</span></td>
          <td>2026-09-21 線上；多頁照頁數累加</td></tr>
      <tr><td>月營運成本</td><td class="num">需個案試算</td><td><span class="tag tag-est">未試算</span></td>
          <td>主機費加 AI 模型按量計費，依用量與部署方式而定；請找工程團隊試算</td></tr>
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
    <dd>第一，通用 AI 讀錯時會產生<strong>看起來很合理但數字是錯的</strong>結果，
    一般人看不出來；DocuMind 對每個欄位評分並做格式檢查，把沒把握或格式不對的欄位標出來（擋不住全部，見第 6 節）。
    第二，每類文件用各自的做法，電子檔直接讀現成文字，不靠 AI 猜。</dd>

    <dt>資料會外流嗎？</dt>
    <dd><strong>目前的線上服務會把文件內容送到外部 AI 服務</strong>：需要 AI 校正或補欄位的謄本頁、以及使用者的提問送 OpenAI；
    帳單、合約、收據、修繕與點交照片送 AWS Bedrock（東京區域）。
    架構上可改為本地運行：辨識引擎本身就在本機執行，AI 層也可切換為本地模型（已實作，尚未啟用）。
    <span class="inline-warn">兩點要注意：一、修繕、點交照片、收據，以及帳單、合約的照片與掃描件，靠的是 AI 讀圖，全本地運行需要另外部署本地視覺模型，不是把雲端關掉就會動。二、正式的全本地運行驗收測試尚未完成，若客戶要寫進合約，請先找工程團隊確認。</span></dd>

    <dt>辨識要多久？</dt>
    <dd>看文件有沒有現成文字：網路申領的電子謄本整份不到 0.1 秒；掃描或拍照的謄本每頁約 15–24 秒，多頁照頁數累加（實測見第 7 節）。
    <span class="inline-warn">對外請描述為「電子檔幾乎即時、掃描件每頁數十秒內」，不要給保證秒數。</span></dd>

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
    <strong>預估值</strong>對外引用時<u>必須</u>加註「預估」二字；
    <strong>實測值</strong>必須連同日期與樣本數一起講，不可說成統計結果或保證值。
  </div>

  <div class="do-dont">
    <div class="do">
      <h4>可以這樣講</h4>
      <ul>
        <li>系統會針對每個欄位評估把握程度，沒把握的主動交由人工確認</li>
        <li>人工修正會回饋到系統，使用越久越準確</li>
        <li>架構上支援本地部署<br><span class="dim">照片與 AI 讀圖的部分需另外部署本地視覺模型</span></li>
        <li>2026-10-29 實測 22 張收據，金額與日期 44 欄讀對 41 欄（小樣本）</li>
        <li>電子檔直接讀現成文字，不經辨識</li>
      </ul>
    </div>
    <div class="dont">
      <h4>不可以這樣講</h4>
      <ul>
        <li>系統會抓出所有錯誤</li>
        <li>比 ChatGPT 準 X%</li>
        <li>資料不會離開客戶的機器<br><span class="dim">目前線上服務會送外部 AI</span></li>
        <li>準確率<u>達</u> 95%、保證單頁幾秒完成</li>
        <li>兩套辨識引擎交叉比對<br><span class="dim">線上沒有開</span></li>
        <li>任何沒標「預估」、或沒附日期與樣本數的百分比或秒數</li>
      </ul>
    </div>
  </div>

  <h3 class="sub-h">需要更多素材時</h3>
  <table class="compact">
    <tbody>
      <tr><td style="width:34%">實際辨識效果截圖</td><td>請工程團隊提供 demo 環境操作畫面</td></tr>
      <tr><td>準確率與速度實測紀錄</td><td><span class="dim">docs/testing/</span>（各份紀錄的索引在 <span class="dim">docs/README.md</span>）</td></tr>
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

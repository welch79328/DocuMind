# 03 — 功能規格

> v2.0：第二輪查證後修訂。F6 暫停、F10 新增、F3/F4/F5/F7/F9 的資料來源全部更正。
> 每一項的驗收都是同一句：**答案裡的每個數字，都要能被一句 SQL 重現。**

---

## 適用於全部功能的四條前置

1. **一律 `active = 1`**（`invoices` 用 `deleted_at IS NULL`）。`contracts` 282 筆裡只有 146 筆是 `active=1`。
2. **一律連唯讀複本**，不得使用應用層既有連線。
3. **輸出欄位受白名單限制**（[02 §4.4](./02-V1-SCOPE.md#44-輸出欄位白名單待拍板)，待拍板前不得開工）。
4. **查詢範圍受角色範圍限制**（[05 §3](./05-PREREQUISITES-AND-ACCEPTANCE.md#3-p0--租戶內的角色範圍待拍板)，待拍板前不得開工）。

---

## F1 — 案件走到哪一段 `P1`

**承辦會這樣問**
> 「C-2026-0431 這件現在什麼狀態？」
> 「我手上哪幾件卡在待簽？」

**輸出**
目前所在段別、**已走過的所有段別**（bitmask 拆解）、各段進入時間。

**資料來源**
- `contracts.bit_status` — 12 段累積 bitmask
- 常數定義：`app/Contract.php` 的 `CONTRACT_READY` … `CONTRACT_HISTORY_DONE`（正好 12 個）

**實作注意**
`bit_status` 是**累積**的，不是單一狀態機——同一列可以同時帶有多個位元。
「目前在哪一段」= 最高位元；「走過哪些段」= 全部已設位元。**不要用等號比對。**

**驗收**
隨機抽 20 件，答案的段別與後台合約詳情頁顯示**完全一致**；
「走過哪些段」用 bitmask 反推，需與 `contracts_upload_logs` 的 old/new 歷史交叉驗證至少 5 件。

---

## F2 — 簽署進度與逾期未簽 `P1`

**承辦會這樣問**
> 「哪幾件邀請出去超過七天還沒簽回？」
> 「這個月平均幾天簽回？」

**輸出**
逾期未簽清單（依逾期天數排序）、邀請到簽回的天數分布。

**資料來源**
- `contract_inviting_at` / `contract_expire_at` / `contract_sign_at`（timestamp）
- `contract_finish_sign_at`
- `old_contract_*`（續約流程）
- `early_termination_*`（解約流程）
- 交叉 `contracts.bit_status`

**實作注意**
**「逾期未簽」沒有現成欄位**，是三個推導指標之一，
定義寫在 [05 §2](./05-PREREQUISITES-AND-ACCEPTANCE.md#2-p0--推導定義的單一來源)，**所有查詢共用同一份**。

**驗收**
推導規則寫成一份可複驗的 SQL；抽 10 件人工核對；**三種簽署流程各至少一件**。

---

## F3 — 應收與逾期清單 `P1`

**承辦會這樣問**
> 「這週到期的有哪些？」
> 「逾期超過 30 天的有幾件？」

**輸出**
逐帳單清單（到期日、狀態、**逾期天數**）、帳齡分組件數。
**只給件數，不給金額加總**（[02 §4.1](./02-V1-SCOPE.md#41-金額只給件數三個例外)）。

**資料來源**
- `bills.date_expire` — **型別是 `int`（註解「繳費期限」），不是 date/timestamp**。
  **不能直接套 `DATEDIFF` 等日期函式**，需先轉換。495/525 有值。
- `bills.status`（見下表）、`bit_status`、`ready_at` / `pay_at` / `complete_at` / `archive_at`

**帳單狀態常數（`app/Bill.php`）：6 個有效 + 1 個已廢棄**

| 常數 | 值 | 語意 |
|------|----|------|
| `BILL_PREPARE` | 1 | 待發送 |
| `BILL_READY` | 2 | 應到帳／待繳費 |
| ~~`BILL_PAYING`~~ | ~~4~~ | **已廢棄**，原始碼註解：付款中一律算在待繳費 |
| `BILL_PAYED` | 8 | 待對帳 |
| `BILL_COMPLETE` | 16 | 已到帳 |
| `BILL_PREPARE_TO_READY` | 32 | **排定發送** |
| `BILL_EXPIRED` | 64 | 已失效 |

漏掉 32 會讓「有幾張待發送」漏掉一整類。

**實作注意**
沿用系統既有的逾期判定，**不自己重寫**。它的兩個既有行為：補開帳單不算逾期；
設定檔名單內的特定租戶滯納金不算逾期。

**驗收**
與**後台帳單列表頁**的逾期篩選結果**逐筆比對，件數必須完全相同**。
比對條件須明確記錄：頁面路徑、篩選條件、租戶、日期區間、全量或抽樣。
不同即為 bug，**不接受「口徑不一」的解釋**。

---

## F4 — 繳款準時性 `P1`

**承辦會這樣問**
> 「這個租客過去 12 期準時幾期？」
> 「哪些租客準時率低於七成？」

**輸出**
逐租客／逐物件的準時率與期數；可加上**逾期天數**（與 F3 同一個定義，不另立「遲繳天數」）。

**資料來源**
- `bills.is_paid_on_time`（525/525 有值）
- `bills.status`（過濾用，見下）
- `bills.pay_at`（timestamp，30/525 有值）或 `bills.pay_ymd`（int，註解「付款時間(搜尋用)」，22/525 有值）
  — **兩者填寫率不同且都偏低，實作前需先確認哪一個是權威**，並記入 05 §2

**這個欄位有陷阱：`0` 同時代表「沒準時」和「還沒繳」**

```
is_paid_on_time = 0  →  520 列   （其中 status=16 已到帳者 30 列）
is_paid_on_time = 1  →    5 列   （其中 status=16 已到帳者  4 列）
```

直接聚合會得到 **5/525 = 0.95%** 這種荒謬答案。JGB 自己的正確用法
（`app/Role.php`、`app/Services/LesseeService.php` 一致）：

```php
COUNT(CASE WHEN status = Bill::BILL_COMPLETE AND is_paid_on_time = 1 THEN 1 END)
```

**任何 `is_paid_on_time` 的聚合都必須先 `WHERE status = 16`。**

**明確不做**
- **不提供「付款重試次數」**。`payments.payment_times` 是金流訂單編號的流水後綴計數器
  （`$merchantOrderNo = $this->no . str_pad(++$this->payment_times, 2, '0', STR_PAD_LEFT)`），
  承辦重新點一次付款就 +1。拿它當信用訊號會冤枉守時的租客。
- **不使用 `lessee_datas.income_bill_paid_on_time_ratio`**。它是 int、且 repo 內查無寫入點。

**驗收**
抽 5 個租客手動核對每一期；準時率的**分母定義**（`status=16` 且 `active=1`）要寫進 05 §2。

---

## F5 — 發票狀態盤點 `P1`

**承辦會這樣問**
> 「這個月開了幾張、作廢幾張、折讓幾張？」
> 「哪幾張帳單還沒開票？」

**輸出**
五種狀態的件數與清單；未開票帳單清單。**金額可以給——發票金額是 int。**

**資料來源**
- `bills.invoice_status`（**int，525/525 有值**）——受控碼，註解逐字寫：
  `0=未開, 1=開立, 2=作廢, 3=折讓, 4=作廢折讓`
- `bills.invoice_reconcile_status`（tinyint，`NULL=未判定 0=已涵蓋 1=有差額 2=無法判定`）
- `invoices.added_at` / `invalid_at` / `allowanced_at` / `allowance_invalid_at`
- `invoices.buyer_*` / `tax_type` / `tax_amt`

**明確不做**
不提供「開立失敗的分類」——`invoice_logs.response_data` 只有 raw response 文字，沒有結構化錯誤碼。

**驗收**
第一版以 **`bills.invoice_status` 與 `invoices` 表自我對帳**（兩邊件數須一致）。
與財政部電子發票平台的外部對帳**降為上線後追蹤項**——
規格無法指派執行者（需具財政部平台帳號者），不列為上線閘門。

---

## ~~F6 — 金流對帳缺口~~ **暫停，待拍板**

**暫停理由**：`payment_collections` 與 `collection_settlements` **各 0 列**，
且 dev1/dev2/dev3 三個 checkout 的 PHP **全部零引用**
（正對照 `payment_atm_nos` 在同一次 grep 命中 2 個檔，證明查法有效）。
受控狀態字串只存在於 `column_comment`，無程式碼常數背書。

初版把這組評為「全庫品質最好的一組」，看的是 schema 設計，**沒查有沒有人在用**。

**若日後啟用，規格需修正一處**：初版寫「`status` / `reconciliation_status` / `fee` / `net_amount` 皆 decimal」是錯的——
`status` 與 `reconciliation_status` 是**受控字串**，只有 `fee` / `net_amount` / `amount` 是 `decimal(12,2)`。

→ 處置見 [02 §7 決策 3](./02-V1-SCOPE.md#7-需業主拍板的三件事)。

---

## F7 — 物件現況揭露紅旗 `P1` · 投報率最高

**承辦會這樣問**
> 「這件有哪些現況揭露的紅旗？」
> 「我手上哪幾件有漏水或非自然死亡的揭露？」

**輸出**
逐項揭露狀態與清單，紅旗項目優先。**每一項附欄位註解原文當說明。**

**為什麼排最優先**
全是**受控的布林，語意寫在欄位註解裡，註解覆蓋 23/23**——
不需要猜、不需要解 JSON、不需要推導。

### 完整欄位清單（23 個，實查 2026-09-10）

| # | 欄位 | 型別 | `column_comment` 原文 | 紅旗 |
|---|------|------|----------------------|------|
| 1 | `estate_has_escape_equipment` | tinyint | 物件 是否無妨礙逃生避難 | ⚠️ |
| 2 | `estate_has_concrete_chloride_testing` | tinyint | 物件 是否做過混凝土中水溶性氯離子含量檢測 | |
| 3 | `estate_has_passed_concrete_chloride_testing` | tinyint | 物件 是否通過混凝土中水溶性氯離子含量檢測 | ⚠️ |
| 4 | `estate_has_radiation_detection` | tinyint | 物件 是否做過輻射屋檢測 | |
| 5 | `estate_has_passed_radiation_detection` | tinyint | 物件 是否通過輻射屋檢測 | ⚠️ |
| 6 | `estate_has_fire_equipment` | tinyint | 物件 室內是否具備消防設施 | ⚠️ |
| 7 | `estate_has_regular_fire_safety_inspection` | tinyint | 物件 是否有定期消防安全檢查 | |
| 8 | `estate_has_basic_bathroom_equipment` | tinyint | 物件 是否具備基本衛浴設備 | |
| 9 | `estate_has_electric_water_heater` | tinyint | 物件 是否具備電熱水器 | |
| 10 | `estate_has_gas_water_heater` | tinyint | 物件 是否具備瓦斯熱水器 | |
| 11 | `estate_has_management_committee` | tinyint | 物件 是否有管理委員會 | |
| 12 | `estate_has_life_convention` | tinyint | 物件 是否有住戶應遵循事項 | |
| 13 | `estate_has_car_parking_space` | tinyint | 物件 是否有汽車停車位 | |
| 14 | `estate_has_car_parking_space_ownership_certificate` | tinyint | 物件 汽車停車位有獨立權狀 | |
| 15 | `estate_has_car_parking_space_subdivision_covenant` | tinyint | 物件 汽車停車位有檢附分管協議及圖說 | |
| 16 | `estate_has_scooter_parking_space` | tinyint | 物件 是否有機車停車位 | |
| 17 | `estate_has_arrear_fee` | tinyint | 物件 是否有欠款 | ⚠️ |
| 18 | `estate_has_partition_wall` | tinyint | 物件 是否有隔間 | |
| 19 | `estate_has_water_leakage` | tinyint | 物件 是否有漏水 | ⚠️ |
| 20 | `estate_has_pipe_problem` | tinyint | 物件 是否有管線異常 | ⚠️ |
| 21 | `estate_has_unnatural_death_current_ownership` | tinyint | 物件 是否有非自然死亡(產權持有期間) | ⚠️ |
| 22 | `estate_has_unnatural_death_former_ownership` | tinyint | 物件 是否有非自然死亡(持有產權前) | ⚠️ |
| 23 | `estate_has_fire_alarm` | **tinyint(1)** | 是否有消防安全設備 | ⚠️ |

**注意兩個容易誤讀的欄位**：
- 第 1 項語意是「**是否無**妨礙逃生避難」——**是否定句**，值的意義與其他欄位相反
- 第 6 與第 23 項語意重疊（室內消防設施 vs 消防安全設備），型別還不同，**呈現時需人工決定是否合併**

**驗收**
上表 **23 欄逐一**與後台表單的顯示值比對，抽 10 件；
「紅旗」欄的判定（含第 1 項的否定句處理）要人工審過一次。

---

## F8 — 通知成本與失敗盤點 `P2`

**承辦會這樣問**
> 「這個月通知花了多少？」
> 「哪些沒送成功、為什麼？」

**輸出**
依渠道與狀態分組的件數與成本；跳過與失敗的原因分布。

**資料來源**
`notification_logs`（`channel` / `status` / `skip_reason` / `fail_reason` / `cost` / `billing_type`，7 列）

**實作注意**
- **新舊兩套通知 log 並存未收斂**（另有 `email_logs` 421 列、`sms_logs`、`role_email_logs`）。
  暫行處置：**只讀新表，並在每個答案上標註「僅涵蓋新版通知紀錄」**。
- **不可依賴 `notification_daily_stats`**——實測 **0 列**。原訂的驗收基準因此改為下方。

**驗收**
以 `notification_logs` 的逐列成本加總，與該渠道供應商帳單當月金額比對量級（非逐筆）。

---

## F9 — 社宅補助申請盤點 `P2`

**承辦會這樣問**
> 「這一季申請了哪些補助、各多少？」
> 「哪幾件還沒送出申請？」

**輸出**
逐類補助的**申請**金額與日期；未申請清單。
**金額可以給——是 `int`，屬 [02 §4.1](./02-V1-SCOPE.md#41-金額只給件數三個例外) 的第二個例外。**

**資料來源**
- `contracts` 內 **17 個** `%subsidy%` 欄位
- `contract_social_housing_documentation_logs`（表存在）

**實作注意：金額欄與日期欄不成對**

| 情況 | 欄位 |
|------|------|
| 只有 date 沒有 amount | `owner_subsidy_application_date`、`lessee_subsidy_application_date`、`company_match_fee_subsidy_application_date` |
| 只有 amount 沒有 date | `owner_paid_repair_fee_subsidy_application_amount`、`owner_total_repair_fee_subsidy_application_amount`、`to_user_paid_repair_fee_subsidy_application_amount`、`to_user_rent_subsidy_application_amount` |
| 完整成對 | **只有公證費補助兩組**（owner／lessee 的 `notary_fee`） |

所以「這一季申請了哪些補助、各多少」**只有部分補助答得出金額**，答案要逐項標明。

**明確不做**
**不提供「核定金額」與「撥款狀態」**——系統只有申請端，沒有送出後的回饋迴路。
這一點必須在畫面上寫清楚，否則承辦會誤以為申請＝核定。

**驗收**
與造冊 Excel 的申請金額逐筆比對；不成對的欄位要在答案上顯示「無日期」／「無金額」而非留白。

---

## F10 — 附件有無清單 `P2`（新增）

**新增理由**：[04 拒答規格](./04-REFUSAL-SPEC.md)的第 1、3、4 題把替代指向「附件有無清單」，
原本沒有任何功能提供它。**拒答不能承諾系統給不出的東西。**

**承辦會這樣問**
> 「這件附了哪些文件？」
> 「哪幾件還缺房東的身分證？」

**輸出**
逐件的附件有無清單（**只有有無，沒有內容**）；缺件清單。

**資料來源**
- `contracts.attachment_*`（12 欄）
- `owner_attachment_*`（11 欄）、`to_user_attachment_*`（**9 欄**）
- `owner_has_*`（10 欄）、`lessee_has_*`（8 欄）

**明確不做**
不答「附的內容是什麼」——只存 S3 檔名。
不使用 `contract_documents`（0 列）與 `attachments`（0 列）——遷移中未切換。

**驗收**
抽 10 件與後台附件頁逐欄比對。

---

**文件版本**：v2.0
**最後更新**：2026-09-10
**負責團隊**：JGB 產品

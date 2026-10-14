# 01 — JGB 資料源實查清冊

> **初版**：2026-09-09
> **第二輪查證**：2026-09-10（三組獨立代理重跑，**37 條裡有 15 條被推翻**，已全部更正）
> **查證來源**：`devinfra-mysql-1` 的 `jgb` schema（**343** 張表）＋ `~/dev/work/jgb2/dev1|dev2|dev3`（皆在 `preview` 分支）
> **方法**：禁止推測、每一條否定結論附正對照組

---

## 0. 四個會影響所有數字的前提

### 0.1 查詢必須指定 utf8mb4，否則否定結論全部是假的

所有 SQL 以 `--default-character-set=utf8mb4` 執行：

```bash
docker exec devinfra-mysql-1 mysql -uroot -psecret --default-character-set=utf8mb4 -N -e "USE jgb; <SQL>"
```

**不指定 charset 時中文註解會回成 `??????`，`column_comment LIKE '%申報%'` 一律零命中**——
這種查法會把**每一條**「註解含某中文詞」的否定結論自動印成「不存在」。

**查法有效性的正對照**：`column_comment LIKE '%合約%'` 應回 **327 筆**。回 0 就是 charset 沒設對。

### 0.2 這是開發庫，且可能不是完整 schema

**檔頭的 343 張表是開發庫的數字**，與下方 §0.4 的正式站數字不是同一個來源。

`IotController` 仍在 `join iot_manufacturers`，但**該表不在 dev 的 `jgb` schema 裡**。
所以任何純靠 dev 庫得出的「表不存在」都只成立於 dev 庫，**正式站需另行確認**。

### 0.3 所有主表都有 `active` 軟刪欄位，本文列數皆為**未過濾值**

`app/Bill.php` 定義 `ACTIVE_NORMAL=1` / `ACTIVE_ARCHIVED=0` / `ACTIVE_SOFT_DELETED=99`
（`invoices` 走 `deleted_at`）。實測：

| 表 | 總列數 | `active=1` |
|----|--------|-----------|
| contracts | 282 | **146** |
| estates | 61 | 49 |
| bills | 525 | 523 |
| items | 62 | 62 |
| repairs | 3 | — |
| attachments | 0 | — |

**contracts 有一半是封存或軟刪。** 任何問答查詢一律要加 `active = 1`，
否則會把封存合約算進答案。這是全文件最普遍、最容易讓下游安靜出錯的陷阱。

### 0.4 dev 的填寫率不等於正式站

正式站的比例請用 **`jgb2/dev1/contracts_table_optimization_plan.md`**（2026-06-02 對唯讀複本的實測）：
**78,465 列合約中，填充率 ≤10% 的欄位有 344 / 633（54%）**。

三個限定條件，引用時必須一起帶：

1. **78,465 是未過濾軟刪的全表列數**（含封存與軟刪）——依 §0.3，問答查詢一律要加 `active = 1`，
   所以這個數字**不能當成「有效合約數」**。
2. **同一份紀錄的合約欄位數寫 636**，而填充率的分母寫 633，該紀錄未解釋兩者為何不一致；
   開發庫現況是 **642** 欄。引用時要標明是哪一個。
3. 那份紀錄自陳是**遷移計畫草稿**，且是 2026-06-02 的切片，不在本 repo。

---

## 1. 十二項現在就能用

> 初版第 6 項「金流交易與對帳」查證後拆成兩半——
> `payments` / `payment_atm_nos` 留下，`payment_collections` / `collection_settlements`
> 移到第 1.5 節「已建表未啟用」。

共同點：語意有程式碼常數或欄位註解當權威定義（不需要猜）、型別正確、粒度就是問題要的粒度。

| # | 資料源 | 實際的表與欄位 | 為什麼可以直接用 | 證據 |
|---|--------|----------------|------------------|------|
| 1 | 合約生命週期 | `contracts.bit_status` | 12 段狀態是**累積 bitmask**，一個欄位就答得出「走到哪、走過哪些段」。282/282 有值 | `app/Contract.php` 的 `CONTRACT_READY`…`CONTRACT_HISTORY_DONE` **正好 12 個常數**；實測 23 種組合 |
| 2 | 合約簽署時間軸 | `contract_inviting_at` / `_expire_at` / `_sign_at`、`contract_finish_sign_at`、`old_contract_*`（續約）、`early_termination_*`（解約） | 三種簽署流程各有獨立時間欄，與 `bit_status` 交叉可算「邀請到簽回幾天」「幾份逾期未簽」。**timestamp 型別**可直接聚合 | `contract_action_logs` 234 列 |
| 3 | 帳單狀態與到期 | `bills.date_expire`（**int，不是日期型別**）、`bit_status` / `status` / `ready_at` / `pay_at` / `complete_at` / `archive_at` | 狀態常數清楚，495/525 有到期日。適合逾期清單與應收帳齡 | 見下方 **1.1 帳單狀態常數** |
| 4 | 繳款準時性 | `bills.is_paid_on_time` | 525/525 全部有值，可依租客／物件／團隊分組 | 見下方 **1.2 這個欄位有陷阱** |
| 5 | 發票生命週期 | `invoices.added_at` / `invalid_at` / `allowanced_at` / `allowance_invalid_at`、`buyer_*` / `tax_type` / `tax_amt`；`bills.invoice_status`（int，0=未開 1=開立 2=作廢 3=折讓 4=作廢折讓，**525/525 有值**）、`bills.invoice_reconcile_status` | 四個時間戳**分開存**，買受人與稅別完整，**金額是 int 不是 float**。帳單端有受控的發票狀態碼 | `invoice_logs` 24 列，含 `http_code` |
| 6 | 金流交易 | `payments`（44 列，六家 vendor 常數）、`payment_atm_nos`（1 列） | 有資料、有程式碼引用（`app/Payment.php`、`app/Console/Commands/BillReconcileAccount.php`）。**注意 `payments.price` 是 float** | `app/Payment.php` vendor 常數區 |
| 7 | 通知成本與結果 | `notification_logs`（channel / status / skip_reason / fail_reason / cost / billing_type，7 列） | 欄位設計乾淨、狀態受控（sent／skipped／failed）、**有成本欄位**。目前列數少是因為是新表 | 併列的 `notification_daily_stats` **實測 0 列**，第一版不可依賴 |
| 8 | 廣告瀏覽逐日 | `estate_view_counts`（estate_id, ymd, counts；10 列） | 粒度剛好是逐物件逐日，**無需推導** | — |
| 9 | 社宅補助申請 | `contracts` 內 **17 個** `%subsidy%` 欄位（全庫排除備份表 36 個）、`contract_social_housing_documentation_logs`（表存在） | 金額與日期都是 int，型別正確可加總 | 見下方 **1.3 金額與日期不成對** |
| 10 | 合約的物件現況揭露 | `contracts.estate_has_*`，**23 個**（22 個 `tinyint` + 1 個 `tinyint(1)`） | 全是受控的布林，**語意寫在欄位註解裡，註解覆蓋 23/23**。不需要猜、不需要解 JSON | 完整清單見 [03-FUNCTIONAL-SPEC F7](./03-FUNCTIONAL-SPEC.md) |
| 11 | 操作稽核軌跡 | `contract_action_logs`（234 列，**含 `by_user_name` / `by_role_menu_name` 等姓名快照**）、`contracts_upload_logs`（235 列，含 old / new bit_status，**只有 `user_id` 沒有姓名快照**） | 有人、有時間、有動作名稱、有前後狀態 | — |
| 12 | 實價登錄官方代碼表 | `config/declaration_codes.php` **982 行**、`declaration_section_codes.php` **17,845 行**、`declaration_unit_codes.php` **16,238 行** | 官方對照表，靜態權威資料，可查表 | **三檔合計 35,065 行——體積大到不能整包餵給模型，必須做查表** |

### 1.1 帳單狀態常數：6 個有效 + 1 個已廢棄

`app/Bill.php`：

| 常數 | 值 | 語意 |
|------|----|------|
| `BILL_PREPARE` | 1 | 待發送 |
| `BILL_READY` | 2 | 應到帳／待繳費 |
| ~~`BILL_PAYING`~~ | ~~4~~ | **已廢棄**——原始碼註解寫「後來已決定拿掉此標記，付款中一律算在待繳費」 |
| `BILL_PAYED` | 8 | 待對帳 |
| `BILL_COMPLETE` | 16 | 已到帳 |
| `BILL_PREPARE_TO_READY` | 32 | **排定發送**（初版漏列） |
| `BILL_EXPIRED` | 64 | 已失效 |

漏掉 32 會讓「有幾張待發送」的答案漏掉一整類；不知道 4 已廢棄則會在遇到舊資料時誤判。

### 1.2 `is_paid_on_time` 有陷阱：0 同時代表「沒準時」和「還沒繳」

實測分佈：

```
is_paid_on_time = 0  →  520 列   （其中 status=16 已到帳者 30 列）
is_paid_on_time = 1  →    5 列   （其中 status=16 已到帳者  4 列）
```

**直接聚合會得到 5/525 = 0.95% 這種荒謬答案。**

JGB 自己的正確用法（`app/Role.php`、`app/Services/LesseeService.php` 一致）：

```php
COUNT(CASE WHEN status = Bill::BILL_COMPLETE AND is_paid_on_time = 1 THEN 1 END)
```

**任何 `is_paid_on_time` 的聚合都必須先 `WHERE status = 16`。**

附帶：`app/Http/Controllers/Admin/BillController.php` 有兩處 `$bill->is_paid_on_time = null;`，
所以「525/525 全部有值」是 dev 現況，不是欄位保證。

初版寫的 `lessee_datas.*_ratio` 只有**一個**欄位：`income_bill_paid_on_time_ratio`（int），
且 `grep -rn "income_bill_paid_on_time_ratio" app/` **零命中**（正對照 `grep is_paid_on_time` 命中 16 處），
實際寫入點待查，**第一版不使用**。

### 1.3 社宅補助的金額欄與日期欄不成對

不是「每一種補助都有獨立的金額欄與日期欄」。實測：

- **只有 date 沒有 amount**：`owner_subsidy_application_date`、`lessee_subsidy_application_date`、`company_match_fee_subsidy_application_date`
- **只有 amount 沒有 date**：`owner_paid_repair_fee_subsidy_application_amount`、`owner_total_repair_fee_subsidy_application_amount`、`to_user_paid_repair_fee_subsidy_application_amount`、`to_user_rent_subsidy_application_amount`
- **完整成對的只有公證費補助兩組**（owner／lessee 的 `notary_fee`）

---

## 1.5 已建表未啟用（新增一類）

這一類不是「不能信」，是**還沒開始用**。schema 設計良好，但沒有資料也沒有程式碼引用。

| 資料源 | 實測 |
|--------|------|
| `payment_collections` | **0 列**。`amount` / `fee` / `net_amount` 是 `decimal(12,2)`、`fee_rate` 是 `decimal(5,4)`，狀態語意（pending／received／reconciled／mismatched／expired）**只存在於 `column_comment`**，沒有任何程式碼常數背書 |
| `collection_settlements` | **0 列** |

**「0 列」只是開發庫實測，正式站未查。** 零引用那半邊（程式碼）站得住，0 列那半邊沒有正式站證據。

**dev1 / dev2 / dev3 三個 checkout 的 PHP 全部零引用**
（**注意：三者都在同一條 `preview` 分支，是同一份程式的三個工作副本，
不構成三個獨立來源**——零引用的結論成立，但不要拿「三份」當交叉驗證）
（`grep -rl "payment_collections\|PaymentCollection" --include='*.php'` → 0 檔；
正對照 `grep -rl "payment_atm_nos"` → 2 檔，證明查法有效）。

判定標準與第 2 節第 2 項對 `contract_documents`（0 列）的判定一致：**建了表不等於能用**。

---

## 2. 十一項存在但不能信

**這一類最危險**——查得到、答得出來，但答案不可稽核，錯誤會安靜地流到下游。

| # | 資料源 | 實際的表與欄位 | 為什麼不能信 |
|---|--------|----------------|--------------|
| 1 | 建物謄本欄位（DB 端） | `estates.building_registration_transcript`（json） | 整批塞在一個**無 schema 的 JSON 欄**，無法索引、無法 SQL 聚合。dev 庫 61 筆物件中**有值者 = 0**。（**抽取管線本身是存在的**，見第 3 節第 7 條的更正） |
| 2 | 合約附件 | `contracts.attachment_*`（12 欄）、`owner_attachment_*`（11 欄）、`to_user_attachment_*`（**9 欄**）、`owner_has_*`（10 欄）/ `lessee_has_*`（8 欄） | 只存 S3 檔名，**零內容**。可以答「有沒有附」，不能答「附的內容是什麼」。`contract_documents` 側表 0 列、`attachments` 表 0 列——正在遷移但未切換 |
| 3 | 費用品項分類 | `items.nature` / `accounting_code` / `item_group_id` | **不是沒有主檔，是覆蓋不全**：分組語意的權威來源是 `app/ItemGroup.php::DEFAULT`（13 個受控分組，含收支別 `group_fee_type`，註解逐字寫「單一真相來源（SoT）」），`app/Item.php` 會在 `empty($item->item_group_id)` 時自動回填。但 **62 個品項中 37 個 `item_group_id` 為 NULL**，`nature` 與 `accounting_code` **62 筆全 NULL**，DB 端無 FK 約束。同概念多寫法確實存在（租金／管理費／大樓管理費／車位管理費／代收管理費／清潔費／清潔費（公區）），且 `items.id=26` 的 `name` 是二次 UTF-8 編碼的壞字（`æŠ¼é‡‘è¨­ç®—æ¯`）。**結論：分組可做但覆蓋六成不到，不足以支撐費用彙總問答** |
| 4 | 點交點退明細 | `contracts.move_in_items`、`move_out_compensation_list`、`move_out_fees`（皆 text） | 品項與賠償明細是 **text 內嵌 JSON，不是關聯表**，無法逐項查詢或加總 |
| 5 | 家庭成員 / 房產 / 所得 | `to_user_family_member`、`_family_member_property`（皆 text） | 同上，全是 text 內嵌，無法逐成員 SQL 查詢。緊急聯絡人還散在 `repairs`（每張工單重抄）與 `lessee_datas`（快照表），**沒有單一權威來源** |
| 6 | 房東持分關係 | `contracts.owner_other_owner`（text） | 自由文字，沒有比例、沒有人的主鍵 |
| 7 | 屋齡 | `estates.age`（float） | **是匯入當下抄進來的死值，不隨時間更新。** `grep -rn "getAgeAttribute" app/` **零命中**（正對照 `getSalesforceUsageStatusAttribute` 命中 `app/Estate.php`），沒有任何 accessor 由建築完成日動態計算；`EstateWriteController` 與 `EstateTranscriptWriteController` 的 fillable 含 `age`（可手填）。dev 庫 61 筆中**僅 1 筆非 NULL、`age > 0` 為 0 筆**。任何「依屋齡分組」的答案都會是錯的 |
| 8 | 上下架時序 | `estates.is_open` / `is_publish` / `status`（只有當下狀態） | 沒有時序表。要看變更歷史只能從 `model_log_YYYYMM` 撈——需 UNION **27 張**逐月分表（202407 ~ 202609，無缺月）。**這些分表在 `created_at` / `role_id` / `action_name` 有索引，欄位是原生 `json` 型別可 `JSON_EXTRACT`**——成本高的原因是跨 27 張表與 JSON 內容無 schema，**不是無索引**（初版寫錯） |
| 9 | 金流失敗原因 / 發票開立失敗分類 | `payment_logs.response`（text）、`bills.error_msg`（text）、`invoice_logs.response_data` | 只有 raw request／response 文字，**沒有結構化錯誤碼**，無法分類統計。退款也沒有交易紀錄表，只有 PDF 檔名 |
| 10 | 溝通已讀狀態 | `notifications.is_read`（站內）、`email_logs.opened_at`、`role_email_logs.is_read` | 分渠道不齊：站內 ✅（12/345 已讀）；Email 追蹤像素機制存在但 dev 庫 **0/421 有值**；**SMS 與 LINE 完全沒有已讀概念**。而且新舊兩套通知 log 並存未收斂 |
| 11 | 代墊與回收 / 金額精度 | `bills.is_advance`（布林）、`bills.total` float(20,5)、`payments.price` float、`repairs.total` float(10,2) | 代墊只有「是不是」一個布林，**沒有代墊→回收的配對關係**。金額**全部是浮點數**；schema 裡並存 `bills` / `bills_decimal` / `bills_float_test` 三張（三張都有 `is_paid_on_time`）。
另有一個容易誤判的死欄位：`bills.amount` 是 `decimal(10,2)`，但 **525 列全為 `0.00`**——grep 到它不代表金額有 decimal 可用——**問題已被意識到但未收斂**。財務問答會有尾差 |

---

## 3. 十三項完全不存在

> 初版是十四項。第 7 條（上傳文件的欄位抽取）查證後**推翻**，移出本節，改列於第 3.5 節。

每一條的否定結論都附正對照組——同一次查詢裡包含一個已知必然存在的項目。
**正對照組若也沒命中，就是查法壞了，不是目標不存在。**

**正對照組一律寫出被命中的具體欄位或檔案，不寫筆數**——
初版寫的六組筆數（23／31／20／10／8／5）第二輪**沒有一組重跑得出來**，
因為查詢範圍（是否含 `*_2024xxxx` 備份表、grep 是否含 `resources/` 與 `tests/`）沒有記錄。

| # | 宣稱有什麼 | 實查結果 | 正對照組 |
|---|-----------|----------|----------|
| 1 | 繳款「放棄次數」 | 全 schema 無欄位。`grep 放棄` 命中 **32 處，全屬訊息寄送的終局狀態**（`app/Support/MessageDelivery.php`、`app/Jobs/EmailJob.php`、`app/Jobs/SmsJob.php`），無一與繳款有關 | `grep 催繳` 命中 `app/Contract.php` 的 `agency_inform_overdue_rent_day` |
| 2 | 出租／空置天數 | 無任何欄位：`%vacan%` `%empty_day%` `%idle_day%` `%rented_day%` `%days_on_market%` 零命中；`%occupancy%` 的 8 筆全是**建物使用執照**（`owner_has_building_occupancy_permit` 等），與空置無關。**程式裡有三套互相矛盾的空置口徑**，見下方 3.1 | 同句 SQL 命中 `estate_view_counts.counts` 家族 |
| 3 | 客訴與爭議單 | 無 complaint / dispute / ticket / grievance 表。含「爭議／客訴／申訴／抱怨」註解的欄位**只有** `contracts.dispute_resolution_type`（註解「爭議處理方式」）——那是合約條款選項 | 同句命中 `contracts.dispute_resolution_type`（證明中文註解查得到） |
| 4 | 實價登錄申報狀態 | `%declar%` 欄 0 筆；utf8mb4 下註解含「申報」0 筆。**純匯出、無回寫**——申報過沒有、什麼時候申報、有沒有被退，系統都不知道。（代碼表活在 `config/declaration_*.php` 共 35,065 行，**不在 DB**） | 同句命中 `estates.foreclosure_registration` |
| 5 | 社宅中央登錄 / 退件 / 核定金額 | utf8mb4 下註解含「退件／中央／核定」0 筆；程式裡「中央登錄」0 處、「核定」0 處、「退件」17 處全是發票／SQS／推播退件。補助只到 `*_application_amount`，**沒有送出後的回饋迴路** | 同句命中 `contract_social_housing_documentation_logs.form_11` 等 6 欄 |
| 6 | 修繕廠商主檔 / 報價 / 跨案比價 | 無廠商主檔表、無報價欄。`repairs` 有 `manufacturer_id` / `manufacturer_name` / `manufacturer_phone`，但 `app/Http/Controllers/RepairController.php` **兩處 `// 'manufacturer_id' => '',` 是被註解掉的** | 同句命中 `repairs.manufacturer_name`、`iot_passcodes.manufacturer`。**初版用的 `iot_manufacturers` 是壞掉的正對照——該表不在 dev schema，而 `IotController` 仍在 join 它** |
| 7 | *（已移出，見 3.5）* | — | — |
| 8 | 外部公開不動產資料（inbound） | **零 inbound 介接。** 「實價登錄」62 處命中**全屬 outbound 匯出**（`config/declaration_*.php` + `app/Jobs/JgbJob.php` + `EstateTranscriptWriteController` + 5 支 `Declaration*` 測試）；「地籍」4 處全在 `resources/views/estate/edit/additional-verify.blade.php`，且該 `easymap.land.moi.gov.tw` 外連**已被 `{{-- --}}` 註解掉**；「都更」4 處是「都更新」誤命中；「建照」0 處 | 同批查詢命中既有外部介接：iStaging、ThinkCloud、Skywatch、Botbonnie、ezPay、maps.googleapis |
| 9 | 公設項目清單 | utf8mb4 下註解含「公設／公共設施／公共空間」0 筆。管委會資訊只在 `contracts` 與 `contract_estate_disclosure`，**無社區層級表**——同社區多合約會重複且可能互相矛盾 | 同句命中 `contracts.dispute_resolution_type`（中文註解查法有效）＋ `estate_has_management_committee` |
| 10 | 押金保管（專戶 / 保管狀態） | 無 escrow / custody / trust_account 專戶欄、註解無「專戶／保管」。**陷阱**：`contracts.big_landlord_escrow_id` 名字有 escrow，但註解是「所有權／轉租人 id」，`app/Console/Commands/ToolCommandEscrowUser.php` 的用法也是身分而非帳戶——**下一個人 grep escrow 會誤判** | 同句命中含 deposit / 押金 的欄位（如 `contracts.deposit`） |
| 11 | 資訊提供義務（代管受託案） | 沒有任何資料表、欄位或狀態 | `grep 委託管理` 命中 `app/Contract.php` 的 `social_housing_entrusted_management_contract` |
| 12 | 報修「施作」時間戳 | `repairs` 有 **5 段**業務時間戳（`apply_at` / `assign_at` / `complete_at` / `finish_at` / `archive_at`），但 `app/Repair.php` 有 **6 個狀態常數**（`APPLY=1` / `ASSIGN=2` / `PROCESS=4` / `COMPLETE=16` / `FINISH=32` / `ARCHIVE=64`）。**缺的是 `PROCESS`（進行中／施作）那一段——`process_at` 不存在，施作何時開始查不到**。（初版寫「五段實為四段」是錯的，且與自己列的五個欄位矛盾） | `grep process_at app resources` → 0 命中；同表其餘五個時間戳皆在 |
| 13 | 遲繳「天數」的觀測值 | 沒有「實際遲繳了幾天」的觀測欄位。**但 `contracts` 有兩個合約參數性質的天數**：`delay_penalty_days`（註解「遲繳違約金天數」）、`agency_inform_overdue_rent_day`（註解「業者催繳租金期限日數」）——**這兩個是門檻設定不是觀測值**。遲繳統計只到筆數（`lessee_datas.income_bill_complete_late_count`）。天數仍須用到期日與實繳日推算 | 同句命中 `bills.is_paid_on_time`（註解「是否準時繳款」） |
| 14 | `item_groups` 主檔表 | 該表確實不存在。但**用詞要修正**：全 schema 只有 15 個真正的 FK constraint，`items` 一個都沒有，所以那**不是懸空 FK 而是慣例命名的孤兒欄位**；而且**分類定義沒有遺失**——活在 `app/ItemGroup.php` 的 `const DEFAULT` 與 `const DEPOSIT_GROUP_IDS`，只是沒有對應 migration | 同句同時查 `items` / `details` / `bills` → 三張都有回 |

### 3.1 三套互相矛盾的空置口徑

| 位置 | 算什麼 | 矛盾點 |
|------|--------|--------|
| `app/Http/Controllers/UserController.php` `case 'vacancy'` | **物件數** | 同一個 `$totalHasContractCounts` 變數，一行註解寫「空置物件數」，下一行寫「空置物件數 // 改為出租數量」；分子是 `Estate::ESTATE_CONTRACT_SIGNED`，算出來標成「空置率」但實質是**出租率** |
| `app/Community.php` `getQuantitiesOfIdle()` | **物件數** | doc-comment 定義為「沒有執行中合約的物件數量」，卻註明「以下邏輯基本上從 UserController overview() case 'vacancy' 抄過來的」——**兩者定義互為反面** |
| `app/Http/Controllers/EstateController.php` 「==== 空置率 ====」區塊 | **天數**（唯一按日推算的一套） | 逐日掃合約區間累加 `$rentDays`（**出租**天數，不是空置天數），卻掛在「空置率」標題下 |

**所以空置天數不是「沒有基礎資料」，是「可推導但三套口徑互相矛盾」。**
處置因此不同：這一項要先**統一口徑**，而不是像屋齡那樣直接拒答。

---

## 3.5 文件欄位抽取：初版判定錯誤，管線是存在的

**初版寫「解析器不在本分支、`grep BuildingTranscriptParser` 零命中、八類文件上傳後 0 個欄位抽取」——這三句話裡有兩句錯。**

錯在哪：**那個類別已經改名了。拿一個不存在的名字去 grep，零命中證明不了任何事**——
這是本文件最嚴重的一次方法失誤（正對照組壞掉卻沒被發現）。

實際存在的（jgb `preview` 分支，dev1/dev2/dev3 三份 checkout 皆有）：

```
app/Services/Transcript/TranscriptParserService.php      （245 行）
app/Services/Transcript/TranscriptFieldMapper.php        （map() 產出 sub_building_usage /
                                                          shared_build_number / section /
                                                          subsection / land_no / land_use /
                                                          has_other_right …）
app/TranscriptParseJob.php                               （Model）
app/Jobs/TranscriptParseJob.php                          （Job）
app/Http/Controllers/Internal/EstateTranscriptWriteController.php
app/Services/HandoverPhotoAnalyzeService.php             （點交照片 AI 辨識）
DB 表 transcript_parse_jobs                              （存在，0 筆）
```

另一端就在放這份文件的 repo 裡：
`backend/app/lib/multi_type_ocr/` 有 transcript / bill / contract / repair_photo / handover_photo
**五類文件的 field extractor**。

`routes/web.php` 的註解逐字寫出整條路徑：「上傳 PDF/JPG/PNG → DocuMind OCR → BuildingTranscriptParser」。

**站得住的部分**：`upload_files` 確實只有 7 欄（`id`, `file_name`, `custom_name`, `create_role`,
`create_user`, `owner_user`, `created_at`），**確實沒有任何抽取欄**——抽取結果不落在文件表上。

### 所以真正的缺口是成熟度，不是存在性

| 這一段 | 狀態 |
|--------|------|
| 上傳 → OCR → 欄位抽取 | ✅ 通的 |
| 抽取結果落地 | ⚠️ 只存成 `transcript_parse_jobs.result` 的 **JSON blob** |
| 寫回 `estates` | ⚠️ 要經 `EstateTranscriptWriteController` **人工確認** |
| 實際使用量 | ❌ dev 庫 `transcript_parse_jobs` **0 筆** |

**第一版的拒答策略要據此改寫**——不能說「沒有讀取內容」，
要說「抽得出來，但結果還沒進到可查詢的欄位裡」。見 [04-REFUSAL-SPEC A 組](./04-REFUSAL-SPEC.md#a-文件內容6-題)。

---

## 4. 五條缺口決定了第一版的範圍

> 初版列四條，第二輪修正兩條、刪一條、新增兩條。

| 缺口 | 它擋掉什麼 | 處置 |
|------|-----------|------|
| **空置天數口徑** | 空置燒錢速度、續約決策 | **先統一口徑**（三套互相矛盾），不是拒答 |
| **屋齡** | 維修成本比較的**分母** | 拒答。是死值不是不存在，更糟 |
| **申報狀態** | 三軌期限追蹤的回寫端 | 拒答 |
| **費用分類與金額精度** ← 新增 | 維修成本比較的**分子**、任何跨案費用彙總與財務問答 | 拒答。`item_group_id` 37/62 為 NULL、主檔只活在 `App\ItemGroup::DEFAULT`、金額全 float 且三軌並存未收斂 |
| **客訴／爭議工單** ← 新增 | 任何服務品質或糾紛類問答 | 拒答。這是唯一**連推導路徑都沒有**的一項——空置天數至少能從合約推、遲繳天數至少能從到期日推 |

### 一條被推翻的推論

初版寫「屋齡 → 維修成本比較」。**這條推論是斷的**：補齊屋齡也做不出維修成本比較，
因為分子同樣是空的——沒有廠商主檔、沒有報價欄、`repairs.total` 是 float、
跨案費用歸類要靠 `item_group_id` 而它 37/62 為 NULL。

---

## 5. 第二輪查證的修正紀錄

| 節 | 條數 | 推翻 | 主要類型 |
|----|------|------|----------|
| §1 + §2 | 23 | **8** | 數字錯（欄位數、行數、表數）、型別漏講、狀態常數漏列 |
| §3 | 14 | **6** | 證據句錯（結論多半仍成立）、一條結論整個推翻 |
| 檔頭 | — | **1** | 345 → 343 張表 |

**兩個方法缺陷（比單條錯誤嚴重）**：

1. **charset 未聲明**——所有中文註解類否定結論都可能是假的（已於 §0.1 補上規約）
2. **正對照組本身壞掉兩處**——第 6 條用了不存在的表當正對照、第 7 條用了改名前的類別名當正對照；
   且六組正對照筆數**全部無法重現**（已改為寫具體欄位／檔案名）

---

**文件版本**：v2.0
**最後更新**：2026-09-10
**負責團隊**：JGB 產品

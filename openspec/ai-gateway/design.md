# AI Gateway PoC — Design

## 元件與對照

| 示意架構圖 | PoC 元件 | 技術 |
|---|---|---|
| 公司 IdP（Entra ID） | Keycloak（OrbStack 容器，`127.0.0.1:8080`） | OIDC、RS256 簽章、realm 匯入 JSON |
| ① 使用者端提示 | 不實作（屬前端），報告列為邊界 | — |
| AI Gateway：認證 | `gateway/auth.py` | 以 JWKS 驗簽；檢查 `iss`、`aud`、`exp`；只接受 RS256 |
| AI Gateway：授權（ABAC） | `gateway/policy.py`＋`policy.yaml` | 純函式：`allow(subject, resource) -> (bool, reason)` |
| ② 去識別化 | `gateway/deid.py` | 重用 `ticket-sensitivity/rules.py` 的格式規則；可逆代碼 `⟨PII_1⟩`，對照表只存在單次請求的記憶體 |
| 用量監控 | `gateway/usage.py` | 每使用者滑動視窗；超過基線 k 倍即警示（k 與視窗長度寫在 config） |
| ③ 稽核系統 | `gateway/audit.py` | JSONL 追加寫入，只存遮罩後內容；`/audit` 端點限稽核員，查詢本身寫一筆 |
| 模型 | Ollama `qwen3.5:9b`；測試用 `EchoModel` | 測試時用回聲模型，模型端收到什麼就記什麼，結果可重現 |
| 內部 API | `internal_api/app.py` | 合成工單（帶燈號與專案）；讀取、寫入兩個端點 |
| Agent：Client Credentials | Keycloak client `ticket-agent` | 服務帳號，scope 只有 `tickets.read`，等級綠 |
| Agent：On-Behalf-Of | Keycloak Standard Token Exchange（RFC 8693） | Agent 拿使用者 token 換成以內部 API 為 audience 的 token，`sub` 與等級沿用使用者 |

## 請求流程

```
使用者 ──(Bearer token)──> Gateway
  1 認證：驗簽、iss、aud、exp ─ 失敗 401
  2 授權：policy.allow(token 宣告, 請求的資料等級與專案) ─ 失敗 403
  3 用量：記一筆；超過基線就寫警示（不擋，只標）
  4 去識別化：遮罩提問 → 送模型 → 回應中的代碼還原
  5 稽核：寫一筆（誰、何時、動作、決策、遮罩後內容）
  ──> 回應使用者
```

每一步的拒絕也寫稽核（決策欄記 `deny` 與原因），所以 G6 的「每個請求都有一筆」包含被拒的請求。

## ABAC 規則（policy.yaml）

```
等級順序：green < yellow < red
allow 條件（全部成立）：
  - subject.clearance >= resource.level
  - resource.project ∈ subject.projects（服務帳號：resource.level == green 即可，不看專案）
  - 動作是 write 時，subject 需有 tickets.write scope
```

預期矩陣（G3）由此規則手算後寫成 `tests/expected_matrix.yaml`，在實作前 commit；測試比對實際結果與這份檔案，不比對程式自己算出來的值。

## 反向檢核

Gateway 讀 `GATEWAY_DISABLE=auth,policy,deid,audit_redact,usage,scope` 這類旗標，用來關掉單一檢查。`tests/test_reverse.py` 對每個門檻關掉對應檢查重跑，斷言原測試轉紅。旗標只在測試環境變數下生效，啟動時若在非測試模式偵測到旗標就拒絕啟動。

## 去識別化細節

- 偵測範圍：沿用 `rules.py` 的身分證、手機、email、統編 regex，另加市話。
- 代碼：同一請求內同值同代碼（`⟨PII_1⟩` 出現兩次代表同一個值），讓模型仍能理解指涉。
- 還原：只還原回應中出現的已知代碼；模型自己編出的代碼樣字串不還原，原樣留下並在稽核記一筆。
- 日誌與模型端紀錄只看得到代碼。

## 目錄

```
ai-gateway/
  docker-compose.yml        Keycloak（127.0.0.1 only）
  realm/demo-realm.json     使用者、client、scope、token exchange 設定（無 secret）
  gateway/                  app.py auth.py policy.py policy.yaml deid.py usage.py audit.py models.py
  internal_api/app.py
  tests/                    conftest.py test_g01…test_g10.py test_reverse.py expected_matrix.yaml prompts-pii.jsonl
  e2e.py                    G11 端到端（地端 9B）
  REPORT.md  README.md
.venv-gateway/              （gitignored）fastapi、uvicorn、pyjwt[crypto]、httpx、pytest、pyyaml
```

## 風險與對策

| 風險 | 對策 |
|---|---|
| Keycloak 版本的 token exchange 設定方式不同 | 啟動後先 introspect 實裝版本的 admin API，再寫 realm 檔；以實裝為準 |
| 記憶體（16GB）：Keycloak 約 1GB＋9B 約 7GB | 測試用 EchoModel 不載 9B；只有 G11 才載 |
| 測試自己驗自己（矩陣由程式產生） | 預期矩陣手寫、先 commit；每條門檻有反向檢核 |
| realm 匯出夾帶 secret | 提交前 grep `secret`，換成佔位字串；secret 走 `.env.local` |

## T1 實測紀錄（2026-10-19，Keycloak 26.4.0）

以臨時 realm 探針確認 Standard Token Exchange（RFC 8693）在實裝版的設定方式，探針用完即刪 realm：

- 要換 token 的 client（ticket-agent）須為 confidential，且設屬性 `standard.token.exchange.enabled=true`；未設時回 400「Standard token exchange is not enabled for the requested client」。
- 使用者 token 的 `aud` 必須含 ticket-agent（在使用者登入用的 client 加 audience mapper）。
- 只帶 `audience=internal-api` 會回 400「Requested audience not available」；目標 audience 要做成 client scope（含 audience mapper），掛為 ticket-agent 的 optional scope，交換時**同時帶 `scope=<該 scope>`** 才回 200。
- 換到的 token：`sub` 沿用使用者、`aud=internal-api`、`azp=ticket-agent`。
- 不帶 `subject_token` 回 400（「Parameter 'subject_token' required」），符合 G10 第三項的預期。
- 待 T2 處理：交換後的 token 沒有 `preferred_username`（未請求 profile scope）；部門、等級、專案等自訂宣告的 mapper 必須放在交換後 token 會帶到的 scope，否則 Gateway 讀不到。

## T2 實測紀錄（2026-10-19）

- realm 匯入檔由 `ai-gateway/realm/build_realm.py` 產生；secret 與密碼寫成 `${DEMO_*}` 佔位字串，Keycloak 匯入時從容器環境變數（`.env.local`）代入，repo 的 JSON 不含實值（`check_realm.py` 逐一比對）。
- 自己定義 `clientScopes` 時，Keycloak 不會建內建的 `basic`（產生 `sub`）與 `roles` scope，token 會缺 `sub`；兩者已手動補上。
- 自訂屬性（部門、等級、專案）要開 `unmanagedAttributePolicy=ENABLED` 才會保存。
- 為 G1 另建兩個 client：`portal-noaud`（aud 不含 ai-gateway）、`portal-short`（token 3 秒過期）。
- 加了第 5 個帳號 `u-mfa` 供 T7 手動示範：首次登入必須設定 TOTP；設定前直取 token 回「Account is not fully set up」（已確認不是密碼錯）。
- `realm/check_realm.py` 煙霧測試 30 項全過：四個使用者的部門／等級／專案／aud／稽核角色、ticket-agent 服務帳號（綠、只有 tickets.read、aud=internal-api）、代換後 sub 與等級沿用使用者、無使用者 token 的代換被拒。

## T3 紀錄（2026-10-19，寫 Gateway 之前 commit）

- `tests/expected_matrix.yaml`：G3 的 18 格手寫預期（allow 8／deny 10）。刻意的一格：u-red 等級最高但不屬於 P-A，P-A 連綠燈都 deny。
- `tests/prompts-pii.jsonl`（由 `tests/build_prompts.py` 產生）：40 則、45 個虛構個資。分布：身分證 8、手機 10、email 8、統編 5、市話 4、混合 5。刻意混入變形寫法：連字號、空白、全形、+886、國字數字、小寫身分證、標籤與數字之間夾字（「統編為」、括號）、同值重複兩次。
- G4 的「出現 0 次」逐字與正規化後都查，擋只遮一半的漏網（細節見 build_prompts.py 檔頭）。
- 對 T4 的影響：`rules.py` 在「去空白、去連字號、國字轉數字」後的文字上比對，只知道有個資、不知道在原文哪裡，不能直接拿來遮罩。`deid.py` 沿用同一組格式定義，改寫成能回報原文位置、容許分隔符號的版本。

## T4 紀錄（2026-10-19）

- 實作：`gateway/`（config、flags、auth、policy＋policy.yaml、deid、usage、audit、models、app）、`internal_api/`（app＋6 張合成工單 tickets.json）、Makefile。相依套件固定版本裝在 `.venv-gateway`（Python 3.14）。
- 停用旗標：auth、policy、scope、deid、audit_redact、audit_rbac、usage（比 design 原列多了 `audit_rbac`，供 G7 反向檢核）。非測試模式帶旗標即拒絕啟動。
- 去識別化：在原文上比對、容許空白與連字號分隔；手機另認 +886、全形、國字數字；統編認「標籤後 4 字內的 8 位數」。同值不同寫法（+886 912… 與 0912…）得到同一代碼。誤遮自查：日期、工單編號、金額、分機都不會被遮。仍認不得：姓名、沒有標籤的統編。
- 用量監控參數：60 秒一格、基線＝前 10 格平均、當格 ≥10 次且 > 3 倍基線才警示；歷史不足 10 格不判斷。
- 煙霧測試（真實 Keycloak token，非正式門檻）：無 token 401；u-yellow 黃燈提問的手機與 email 在模型端與日誌都只剩代碼、回應已還原；u-yellow 要紅燈 403；u-red 要 P-A 綠燈 403（不屬於專案）；非稽核員查日誌 403、稽核員可查且拒絕紀錄都在；Agent 服務帳號讀綠 200、讀紅與寫入 403；Agent 代表 u-red 讀 P-B 紅燈 200；使用者 token 直接打內部 API 因 aud 不符 401。

## T5 紀錄（2026-10-19）

- `tests/test_g01…test_g10`（40 個測試）＋`run_gates.py`（逐條正常跑＋反向檢核，輸出門檻表）。結果存 `ai-gateway/results/gates-20261019.md`。
- **G1–G10 全部達成**，每條反向檢核都轉紅（exit 1＝測試失敗；exit 2 以上算測試出錯、不算轉紅）。
- 反向檢核對照：G1 停用 auth；G2 把 issuer 指向不存在的 realm；G3 停用 policy；G4 停用 deid；G5 新增 `restore` 旗標（停用還原，比 design 原列多一個）；G6 停用 audit_redact；G7 停用 audit_rbac；G8 停用 usage；G9 分兩次（停用 policy 測讀取、停用 scope 測寫入）；G10 停用 policy（綠燈使用者經代換讀紅）。
- G10 第三項（不帶使用者 token 的交換被拒）是 Keycloak 端行為，Gateway 旗標關不掉；改用對照組：同一請求補上使用者 token 即回 200，證明失敗確實來自缺 token。報告照實註明這項的反向檢核形式不同。
- 寫測試時抓到一個測試本身的錯：測試 helper 送出的 header 名稱帶底線（`x_test_clock`），伺服器只認連字號，壓縮時鐘沒送到，G8 第一次跑失敗；修的是測試 helper，Gateway 程式未動。
- G1「iss 不符」用 master realm 簽的 token，iss 與簽章金鑰同時不符，無法單獨隔離 iss 檢查；報告列為限制。

## T6 紀錄（2026-10-19，G11 端到端第 1 次）

- 3 則提問（P09 手機、P27 統編、P36 身分證＋手機＋email）經真的 uvicorn Gateway 送進地端 qwen3.5:9b：**3/3 成功、模型端原始個資 0 次，依預先登記門檻判定達成**。耗時 12.4／5.1／7.2 秒（M1，含首次載入）。結果存 `ai-gateway/results/e2e-20261019.md`。
- **發現 1：模型改寫了代碼格式，還原失敗。** P36 的回答把 `⟨PII_2⟩` 寫成 `⟪PII_2⟫`（不同的括號），Gateway 只認 `⟨PII_n⟩`，所以使用者收到的是代碼不是原值；稽核的「未知代碼」計數也沒抓到，因為它用同一個樣式比對。G5 用回聲模型測不到這種情況。
- **發現 2：姓名照樣送進模型。** P36 的「王先生」沒有被遮，符合 requirements 已列的邊界（格式規則認不得姓名），這次在真模型上實際看到。
- 另見：P09 模型回答「我會於系統中建立此工作項目」，是模型自稱做了它沒做的事，不屬本 PoC 範圍，報告附註。

## T6 修正與 G11 第 2 次（2026-10-19，看過第 1 次結果之後的改動，報告兩次並列）

- 修正：`deid.restore` 容許代碼括號變形（⟪⟫、<>、[]、（）、〈〉、《》、{}，以及去括號、底線換空白或連字號）；對不上的類代碼字串原樣留下並計入稽核 `unknown_codes`（第 1 次的監控盲點）。新增旗標 `restore_loose`（停用即退回只認 ⟨PII_n⟩）。
- 新增 G5b（非預先登記）：改寫括號的假模型逐則輪換 5 種變形，40 則全部還原；編造的 ⟪PII_99⟫ 計入 unknown_codes=1。反向檢核：停用 restore_loose 轉紅。全套重跑 G1–G10＋G5b 全部達成（`results/gates-20261019-g5b.md`）。
- 第 1 次的實際失敗回答（P36）拿新版還原器重放：⟪PII_2⟫、⟪PII_3⟫ 正確還原成原值、unknown_codes=0。
- G11 第 2 次（`results/e2e-20261019-1926.md`）：3/3 成功、模型端原始個資 0 次、回答全部還原。**但這次 9B 剛好沒有改寫括號**，所以修正在真模型上的證據是上一條的重放，不是第 2 次本身。
- 另一個體驗問題：P36 第 2 次的回答寫「以去識別化代碼……形式保存」，還原後代碼變成原值，這句話就不再正確。還原只換字、不懂語意，報告列為邊界。

## T7 紀錄（2026-10-19，MFA 手動示範）

- 作者以 u-mfa 登入：密碼後被強制導向「Mobile Authenticator Setup」（截圖），掃 QR code、輸入一次性驗證碼完成綁定。管理端查核：待完成步驟清空、憑證為 password＋otp（demo-phone）、有效 session 1。截圖與查核存作者本機，不進本 repo（QR 截圖含測試帳號的 TOTP 金鑰）。
- 發現：登入後帳號管理頁顯示「Something went wrong」。原因是自訂 roles scope 缺 client 角色與 audience resolve 兩個 mapper，且 Keycloak 自動建的 account-console 沒掛任何預設 scope。已用管理 API 線上補上（未重新匯入，避免清掉 OTP），`build_realm.py` 同步修正（roles scope 補兩個 mapper、realm 設 `defaultDefaultClientScopes`）。修正後帳號頁正常，並截到「Two-factor authentication：demo-phone」。
- `check_realm.py` 的 u-mfa 檢查改為分辨兩種狀態（設定前：帳號未完成設定；設定後：只給密碼回 invalid_grant）。限制：設定後的錯誤訊息與密碼錯相同，煙霧測試無法單獨區分，以管理端查核為準。

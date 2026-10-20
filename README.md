# AI Request Governance

> Governance for AI requests from intake to production, in three parts: a Jira workflow whose gates block skipped steps, a local (on-prem) model that labels ticket sensitivity, and an AI Gateway PoC covering authentication, ABAC authorization, PII masking, audit and agent on-behalf-of. Every threshold was pre-registered, and every test is reverse-checked: disable the control under test and the test must fail. All data is synthetic.

AI 需求從收件到上線的治理，三個部分各自落在流程的一站，而且每一部分都用「故意弄壞、確認會擋」的方式驗收。

| 流程站 | 部分 | 問題 | 主要結果 |
|---|---|---|---|
| 收件到交付的每道出口 | [jira-gate](jira-gate/) | 規則能不能寫進系統，讓人想跳也跳不過？ | Jira 內建功能建出 7 站工作流程、10 條欄位檢查、1 道子任務閘門；4 道演練都擋得住 |
| 分級審查 | [ticket-sensitivity](ticket-sensitivity/) | 工單的機敏燈號（綠／黃／紅）能不能在地端判，紅燈不漏？ | 地端 9B 前兩輪 60 張紅燈漏 1 張；1.5B＋LoRA 不穩；欄位矛盾 18/18、紅燈低報 9/9 皆零誤報；查出規則清單缺產品名 |
| 開發時的模型通道 | [ai-gateway](ai-gateway/) | 認證、授權、去識別化、稽核、Agent 代表使用者，每一層擋不擋得住？ | 預先登記門檻 G1–G10 全達成，每條把檢查關掉重跑都會轉紅 |

## 共同做法

- **預先登記**：門檻在看測試資料或寫程式之前寫定並 commit（`openspec/`），之後只能照實記錄未達，不改門檻。
- **反向檢核**：關掉被測的那道檢查重跑，測試必須轉紅；沒轉紅代表測試沒測到東西。
- **測試集只跑一次**：工單實驗每輪換一批全新的合成工單，不在同一批題目上調方案。
- **資料全為合成**：沒有任何真實工單、個資或公司資料。

## 目錄

```
jira-gate/            Jira 工作流程閘門的設計與驗收紀錄
ticket-sensitivity/   地端判燈號實驗三輪（程式、合成資料、報告）
ai-gateway/           AI Gateway PoC（Keycloak＋FastAPI＋地端模型）
openspec/             兩個實驗的規格與預先登記門檻
```

## 快速驗證

```
# 工單實驗：規則與評分器（不需模型）
cd ticket-sensitivity && python3 test_rules.py && (cd v3 && python3 test_syspath.py && python3 score3.py --selftest)

# AI Gateway：需 Docker，步驟見 ai-gateway/README.md
```

CI 兩個 job：工單實驗的規則測試，以及起 Keycloak 跑 AI Gateway 全部門檻與反向檢核。重跑模型推論需要 Ollama（qwen3.5:9b）與 Apple Silicon 上的 mlx-lm。

## 邊界

- Keycloak 代替 Entra ID：驗證的是設計擋得住，不是在特定企業環境實測過。
- 工單實驗資料合成、每輪紅燈 30 張，數字不能外推到真實工單；9B 的速度只量過 M1 筆電（約 12 秒一張）。
- 去識別化只認格式（身分證、手機、email、統編、市話），認不得自由文字裡的姓名。

## License

MIT

# AI Gateway PoC — Tasks

- [x] T0 作者 核准 requirements（門檻 G1–G11）與 design
- [x] T1 啟動 OrbStack＋Keycloak；確認實裝版本的 token exchange 設定方式
- [x] T2 realm/demo-realm.json：4 個使用者、ticket-agent、scope、token exchange；secret 不進 repo（AC-1）
- [x] T3 tests/expected_matrix.yaml 與 prompts-pii.jsonl（40 則）先寫並 commit，再寫 Gateway
- [x] T4 gateway：auth → policy → usage → deid → audit；internal_api
- [x] T5 G1–G10 pytest＋反向檢核（AC-2）
- [x] T6 e2e.py：G11 經 Gateway 進地端 9B（AC-3）
- [x] T7 MFA 手動示範截圖（AC-6，截圖存作者本機）
- [x] T8 REPORT.md：門檻表、反向檢核、邊界、與架構圖逐層對照（AC-4）
- [x] T9 簡報一頁插在第 8 頁之後；PDF 由作者匯出（AC-5）

# AI Gateway PoC

把「AI Gateway：認證、授權與去識別化」示意架構做成本機可驗證的版本。結果見 [REPORT.md](REPORT.md)，規格見 [`openspec/ai-gateway/`](../openspec/ai-gateway/)。CI 每次推送都會起 Keycloak 跑完整套門檻與反向檢核。

## 需要

- OrbStack（或其他 Docker）、Python 3.14、Ollama（只有 `e2e.py` 需要 qwen3.5:9b）
- `ai-gateway/.env.local`（gitignored）：

```
KC_BOOTSTRAP_ADMIN_USERNAME=admin
KC_BOOTSTRAP_ADMIN_PASSWORD=<隨機>
DEMO_PORTAL_SECRET=<隨機>
DEMO_AGENT_SECRET=<隨機>
DEMO_GATEWAY_SECRET=<隨機>
DEMO_API_SECRET=<隨機>
DEMO_USER_PW=<隨機>
```

## 步驟

```
python3 -m venv .venv-gateway
.venv-gateway/bin/pip install -r ai-gateway/requirements.txt
cd ai-gateway
docker compose up -d          # Keycloak 只綁 127.0.0.1:8080，匯入 realm/demo-realm.json
make check                    # realm 煙霧測試
../.venv-gateway/bin/python run_gates.py
make gateway                  # 127.0.0.1:8090（另開終端）
make api                      # 127.0.0.1:8091（另開終端）
```

改角色或 client：改 `realm/build_realm.py` 後重跑產生 `demo-realm.json`，再 `docker compose down && docker compose up -d`（會清掉容器內的資料，含手動設定的 TOTP）。

## 目錄

| 路徑 | 內容 |
|---|---|
| `realm/` | realm 產生器、匯入檔（secret 為 `${DEMO_*}` 佔位）、煙霧測試 |
| `gateway/` | 認證、ABAC、去識別化、用量、稽核、模型 |
| `internal_api/` | 合成工單 API（Agent 呼叫的對象） |
| `tests/` | G1–G10＋G5b、預期權限表、40 則含個資提問 |
| `results/` | 門檻表與端到端輸出 |

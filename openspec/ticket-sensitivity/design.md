# 工單機敏分級 — Design

## 目錄

```
ticket-sensitivity/
  policy.md            燈號判準（唯一來源；規則字典與生成提示都引用它）
  rules.py             規則層：regex＋關鍵詞，回傳 (燈號, 命中片段[])
  test_rules.py        AC-1，含反向檢核
  gen/spec.md          合成資料生成規格（矩陣、陷阱、輸出格式）
  build-dataset.py     合併生成批次 → 分組切分 → mlx-lm 訓練格式
  infer.py             MLX 推論（base／LoRA）
  infer-ollama.py      Ollama 9B 推論
  decide.py            決策層：max(規則, 模型)＋低信心標記
  score.py             評分：漏判／誤判／F1／欄位／依據片段驗證
  run-chain.sh         訓練後接力：推論→評分
  demo.py              單張工單示範
  REPORT.md            結果（進版控）
  data/ adapters/ pred-*.jsonl   gitignored
```

## 模型輸出契約（JSON）

```json
{"燈號":"紅","痛點":"…","資料位置":"…","需要模型":"是|否|不確定",
 "資料類型":["個資","配方"],"依據":["工單逐字片段", "…"]}
```

## 決策層

- `final = max(rule_light, model_light)`，順序 綠 < 黃 < 紅。
- 模型輸出解析失敗 → 以規則結果為準並標記「需人工」。
- 規則判綠、模型判紅 → 採紅，標記「模型升級」，供錯誤分析。

## 資料生成

- 由 subagent（Sonnet）依 `gen/spec.md` 分批產生，每批固定一個「模板 ID」，模板＝部門×需求類型×寫法。
- 每筆帶 `template_id`、`gold_light`、`gold_fields`、`trap`（無／同詞異義／隱性機敏／個資變形／注入／安全長單）。
- 切分以 `template_id` 分組，陷阱模板保留給測試集。

## 雲端對照

- 沿用 free-eval 路徑：Agent tool 以 `model` 參數開 Sonnet／Opus subagent 盲測，只給工單文字與 policy，不給標籤。

## 訓練參數

沿用作者先前 LoRA 專案的設定：Qwen2.5-1.5B-Instruct-4bit、mlx-lm LoRA、batch 4、16 層；iters 依 400 筆調為約 600，看 val loss 決定。

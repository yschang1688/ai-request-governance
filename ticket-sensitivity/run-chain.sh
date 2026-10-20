#!/bin/bash
# 本機推論接力：D（LoRA，第 200 步）→ B（base＋判準）→ D 五次一致性 → C（Ollama 9B）
# 只產預測檔；評分等 作者裁定完再統一跑。
set -uo pipefail
cd "$(dirname "$0")"
PY="${MLX_PY:-python3}"  # 需裝有 mlx-lm 的 python
echo "[chain] D LoRA $(date +%H:%M)"
$PY infer.py --mode short --adapter adapters-best --out pred-D-lora.jsonl
echo "[chain] B base $(date +%H:%M)"
$PY infer.py --mode engineered --out pred-B-base.jsonl
echo "[chain] D x5 一致性 $(date +%H:%M)"
$PY infer.py --mode short --adapter adapters-best --repeat 5 --out pred-D-lora-x5.jsonl
echo "[chain] C Ollama 9B $(date +%H:%M)"
python3 infer-ollama.py qwen3.5:9b pred-C-9b.jsonl
echo "[chain] 完成 $(date +%H:%M)"

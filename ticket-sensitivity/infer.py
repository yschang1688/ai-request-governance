#!/usr/bin/env python3
"""MLX 批次推論 test set。--mode short（LoRA 用）| engineered（base 用），--adapter 可選。
--repeat k：每筆跑 k 次（temp>0）算一致性。執行需要裝有 mlx-lm 的 Python 環境（Apple Silicon）。"""
import argparse
import json
import os
import time

from mlx_lm import generate, load
from mlx_lm.sample_utils import make_sampler

from common import ENGINEERED, HERE, SHORT_INSTR, read_jsonl

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="mlx-community/Qwen2.5-1.5B-Instruct-4bit")
ap.add_argument("--adapter", default=None)
ap.add_argument("--mode", choices=["short", "engineered"], default="short")
ap.add_argument("--out", required=True)
ap.add_argument("--repeat", type=int, default=1)
ap.add_argument("--limit", type=int, default=0)
a = ap.parse_args()

model, tok = load(a.model, adapter_path=a.adapter)
metas = read_jsonl(os.path.join(HERE, "data/test-meta.jsonl"))
if a.limit:
    metas = metas[: a.limit]
sampler = make_sampler(temp=0.0 if a.repeat == 1 else 0.7)

t0 = time.time()
with open(a.out, "w", encoding="utf-8") as f:
    for i, ex in enumerate(metas):
        head = SHORT_INSTR if a.mode == "short" else ENGINEERED
        prompt = tok.apply_chat_template([{"role": "user", "content": f"{head}\n{ex['text']}"}],
                                         add_generation_prompt=True)
        for k in range(a.repeat):
            t1 = time.time()
            out = generate(model, tok, prompt=prompt, max_tokens=400, sampler=sampler)
            f.write(json.dumps({"id": ex["id"], "run": k, "output": out, "sec": round(time.time() - t1, 2)},
                               ensure_ascii=False) + "\n")
            f.flush()
        if (i + 1) % 20 == 0:
            el = time.time() - t0
            print(f"{i+1}/{len(metas)}  {el/(i+1):.1f}s/筆", flush=True)
print("done", a.out)

#!/usr/bin/env python3
"""Ollama 基準（判準提示詞）。用法：infer-ollama.py <model> <out>"""
import json
import os
import sys
import time
import urllib.request

from common import ENGINEERED, HERE, read_jsonl

model, out = sys.argv[1], sys.argv[2]
metas = read_jsonl(os.path.join(HERE, "data/test-meta.jsonl"))


def ollama(prompt):
    # think:false：thinking 模型會把預算燒在推理、response 變空（先前專案實測踩過）
    req = urllib.request.Request("http://localhost:11434/api/generate",
        data=json.dumps({"model": model, "prompt": prompt, "stream": False, "think": False,
                         "options": {"temperature": 0, "num_predict": 500}}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["response"]


t0 = time.time()
with open(out, "w", encoding="utf-8") as f:
    for i, ex in enumerate(metas):
        t1 = time.time()
        resp = ollama(f"{ENGINEERED}\n{ex['text']}")
        f.write(json.dumps({"id": ex["id"], "output": resp, "sec": round(time.time() - t1, 2)}, ensure_ascii=False) + "\n")
        f.flush()
        if (i + 1) % 20 == 0:
            print(f"{i+1}/{len(metas)}  {(time.time()-t0)/(i+1):.1f}s/筆", flush=True)
print("done", out)

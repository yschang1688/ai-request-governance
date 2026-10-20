#!/usr/bin/env python3
"""規則層預測（A）與決策層（E＝max(規則, 模型)）。
用法：decide.py rules <out>                 → 只用規則
      decide.py combine <model_pred> <out>   → 規則＋模型取高者
      加 --format-only：規則只留個資格式與路徑（E3），關鍵詞規則停用
"""
import json
import os
import sys

from common import HERE, ORDER, parse_json, read_jsonl
from rules import classify, RED_KEYWORDS, YELLOW_KEYWORDS

metas = read_jsonl(os.path.join(HERE, "data/test-meta.jsonl"))
args = [a for a in sys.argv[1:] if a != "--format-only"]
FORMAT_ONLY = "--format-only" in sys.argv
# 關鍵詞規則看不懂上下文（同詞異義全誤判），E3 只留格式規則當保底
DISABLED = frozenset(RED_KEYWORDS) | frozenset(YELLOW_KEYWORDS) if FORMAT_ONLY else frozenset()
mode, out = args[0], args[-1]
model = {}
if mode == "combine":
    for p in read_jsonl(args[1]):
        if p.get("run", 0) == 0:
            model[p["id"]] = parse_json(p.get("output"))

with open(out, "w", encoding="utf-8") as f:
    for ex in metas:
        r = classify(ex["text"], DISABLED)
        light, flags = r["light"], []
        if r["injection"]:
            flags.append("疑似注入")
        if mode == "combine":
            obj = model.get(ex["id"])
            ml = obj.get("燈號") if obj else None
            if ml not in ORDER:
                flags.append("模型輸出無效，需人工")
            elif ORDER[ml] > ORDER[light]:
                light = ml
                flags.append("模型升級")
        if light == "紅" or flags:
            flags.append("需人工覆核")
        f.write(json.dumps({"id": ex["id"], "light": light, "flags": flags,
                            "rule_hits": [h["rule"] for h in r["hits"]]}, ensure_ascii=False) + "\n")
print("done", out)

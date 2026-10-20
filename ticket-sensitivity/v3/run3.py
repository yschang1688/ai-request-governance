#!/usr/bin/env python3
"""v3 推論：每張兩次 9B（v1 提示詞、加自評句的提示詞）＋格式規則＋系統路徑規則，組出 E3／E5a／E5b／E5。
用法：run3.py <data.jsonl> <out.jsonl>（可續跑）"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v2"))
from common2 import ENGINEERED, FORMAT_ONLY, all_text, classify, light_max, ollama, parse_json, read_jsonl, text_e3  # noqa: E402
from syspath import PROMPT_ADDON, classify_path  # noqa: E402

assert ENGINEERED.endswith("\n\n工單：")
PROMPT5 = ENGINEERED[: -len("\n\n工單：")] + f"\n\n{PROMPT_ADDON}\n\n工單："

src, out = sys.argv[1], sys.argv[2]
rows = read_jsonl(src)
done = {json.loads(l)["id"] for l in open(out)} if os.path.exists(out) else set()
t0 = time.time()
with open(out, "a", encoding="utf-8") as fo:
    for i, r in enumerate(rows):
        if r["id"] in done:
            continue
        f = r["fields"]
        text = all_text(f)
        rule = classify(text, FORMAT_ONLY)["light"]
        path_light, path_hits = classify_path(text)
        m3 = (parse_json(ollama(f"{ENGINEERED}\n{text_e3(f)}")) or {}).get("燈號")
        m5 = (parse_json(ollama(f"{PROMPT5}\n{text_e3(f)}")) or {}).get("燈號")
        e3 = light_max(rule, m3)
        e5b = light_max(rule, m5)
        rec = {"id": r["id"], "rule": rule, "path": path_light, "path_hits": path_hits, "m3": m3, "m5": m5,
               "E3": e3, "E5a": light_max(e3, path_light), "E5b": e5b, "E5": light_max(e5b, path_light)}
        fo.write(json.dumps(rec, ensure_ascii=False) + "\n"); fo.flush()
        if (i + 1) % 10 == 0:
            print(f"{i+1}/{len(rows)}  {(time.time()-t0)/(i+1-len(done) or 1):.1f}s/筆", flush=True)
print("done", out)

#!/usr/bin/env python3
"""v2 推論：對 data/{split}.jsonl 跑 E3、E4 燈號與痛點效益檢查，結果寫 pred-{split}.jsonl。
用法：run2.py dev|test
每筆三次 9B 呼叫（E3 燈號、E4 燈號、痛點效益）；規則層即時。"""
import json
import os
import sys
import time

from common2 import (ENGINEERED, FIT_PROMPT, FORMAT_ONLY, HERE, all_text, classify, light_max,
                     ollama, parse_json, read_jsonl, rule_defects, text_e3, text_e4)

split = sys.argv[1]
rows = read_jsonl(os.path.join(HERE, f"data/{split}.jsonl"))
out = os.path.join(HERE, f"pred-{split}.jsonl")
done = {json.loads(l)["id"] for l in open(out)} if os.path.exists(out) else set()

t0 = time.time()
with open(out, "a", encoding="utf-8") as fo:
    for i, r in enumerate(rows):
        if r["id"] in done:
            continue
        f = r["fields"]
        rule = classify(all_text(f), FORMAT_ONLY)
        e3 = parse_json(ollama(f"{ENGINEERED}\n{text_e3(f)}"))
        e4 = parse_json(ollama(f"{ENGINEERED}\n{text_e4(f)}"))
        fit = parse_json(ollama(FIT_PROMPT + f"一句話痛點：{f['一句話痛點']}\n預期效益指標：{f['預期效益指標']}", 150))
        m3 = (e3 or {}).get("燈號"); m4 = (e4 or {}).get("燈號")
        rec = {"id": r["id"], "rule_light": rule["light"], "injection": rule["injection"],
               "e3_model": m3, "e4_model": m4,
               "E3": light_max(rule["light"], m3), "E4": light_max(rule["light"], m4),
               "rule_defects": rule_defects(f), "fit": (fit or {}).get("相符"), "fit_reason": (fit or {}).get("理由")}
        fo.write(json.dumps(rec, ensure_ascii=False) + "\n"); fo.flush()
        if (i + 1) % 10 == 0:
            print(f"{i+1}/{len(rows)}  {(time.time()-t0)/(i+1-len(done) or 1):.1f}s/筆", flush=True)
print("done", out)

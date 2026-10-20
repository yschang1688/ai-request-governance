#!/usr/bin/env python3
"""六方總表：同一批預測，用兩套標籤（原始裁定／仲裁後）各算一次。用法：summarize.py"""
import json, os, subprocess, statistics
from collections import Counter, defaultdict
from common import parse_json, read_jsonl
RUNS = [("A 規則", "pred-A-rules.jsonl"), ("B 1.5B 原版", "pred-B-base.jsonl"), ("C 9B", "pred-C-9b.jsonl"),
        ("D 1.5B+LoRA", "pred-D-lora.jsonl"), ("E 規則+LoRA", "pred-E-rules-lora.jsonl"),
        ("E2 規則+9B*", "pred-E2-rules-9b.jsonl"), ("E3 格式規則+9B*", "pred-E3-format-9b.jsonl"),
        ("F1 Sonnet", "pred-F1-sonnet.jsonl"), ("F2 Opus", "pred-F2-opus.jsonl")]
out = {}
for gold in ["test-gold-raw.jsonl", "test-gold-final.jsonl"]:
    print(f"\n== 標籤：{gold} ==")
    print(f"{'方案':<12}{'紅燈漏判':>6}{'誤判成紅':>6}{'正確率':>7}{'F1':>6}{'解析失敗':>6}  陷阱")
    for label, f in RUNS:
        if not os.path.exists(f) or sum(1 for _ in open(f)) < 100:
            print(f"{label:<12}（尚未完成）"); continue
        r = json.loads(subprocess.run(["python3", "score.py", f, label], capture_output=True, text=True,
                                      env=dict(os.environ, GOLD=gold)).stdout)
        out.setdefault(gold, {})[label] = r
        print(f"{label:<12}{r['紅燈漏判']:>6}{r['誤判成紅']:>6}{r['正確率']:>7.2f}{r['macroF1']:>6.2f}{r['解析失敗']:>6}  {r['陷阱']}")
# 一致性與延遲
x5 = defaultdict(list)
for p in read_jsonl("pred-D-lora-x5.jsonl"):
    o = parse_json(p["output"]); x5[p["id"]].append(o.get("燈號") if o else None)
same = sum(len(set(v)) == 1 for v in x5.values())
print(f"\nD LoRA 5 次（temp 0.7）燈號完全一致：{same}/{len(x5)}")
for label, f in RUNS:
    if os.path.exists(f):
        secs = [p["sec"] for p in read_jsonl(f) if "sec" in p]
        if secs: print(f"延遲 {label}: 中位數 {statistics.median(secs):.1f} 秒／張")
json.dump(out, open("results-summary.json", "w"), ensure_ascii=False, indent=1)

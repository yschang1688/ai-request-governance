#!/usr/bin/env python3
"""v3 總表：地端 E3／E5a／E5b／E5 與雲端 Sonnet、Opus 放同一張表，兩套標籤各算一次。
雲端預測由盲測 subagent 產生（匿名題號 W001…，只看標題＋描述、v1 提示詞），只作上限參考。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v2"))
from common2 import ORDER, parse_json, read_jsonl  # noqa: E402

BLIND = sys.argv[1]
m = json.load(open(os.path.join(HERE, "data/adjudicate-map.json")))
gen = {r["id"]: r for r in read_jsonl(os.path.join(HERE, "data/test.jsonl"))}
human = {g["id"]: g["gold_light"] for g in read_jsonl(os.path.join(HERE, "data/test-gold.jsonl"))}
loc = {r["id"]: r for r in read_jsonl(os.path.join(HERE, "pred-test.jsonl"))}
schemes = {k: {i: loc[i][k] for i in gen} for k in ["E3", "E5a", "E5b", "E5"]}
for name, fn in [("Sonnet", "pred-sonnet.jsonl"), ("Opus", "pred-opus.jsonl")]:
    schemes[name] = {m[p["id"]]: (parse_json(p["output"]) or {}).get("燈號") for p in read_jsonl(os.path.join(BLIND, fn))}
KINDS = ["系統路徑-紅", "系統路徑-黃", "一般路徑-綠", "自評淡化", "自評誇大"]
out = {}
for lab_name, lab in [("作者裁定", human), ("生成標籤", {i: r["gold_light"] for i, r in gen.items()})]:
    print(f"\n== {lab_name}（紅燈 {sum(v == '紅' for v in lab.values())} 張）==")
    print(f"{'方案':<8}{'漏判':>4}{'誤判紅':>6}{'正確率':>7}  " + "  ".join(KINDS))
    for name, pred in schemes.items():
        miss = sum(lab[i] == "紅" and pred[i] != "紅" for i in lab)
        fd = sum(lab[i] != "紅" and pred[i] == "紅" for i in lab)
        acc = sum(lab[i] == pred[i] for i in lab) / len(lab)
        kinds = {}
        for k in KINDS:
            ids = [i for i, r in gen.items() if r["kind"] == k]
            kinds[k] = f"{sum(pred[i] == '紅' for i in ids)}/{len(ids)}"
        out.setdefault(lab_name, {})[name] = {"紅燈漏判": miss, "誤判成紅": fd, "正確率": round(acc, 2), "各類判紅": kinds}
        print(f"{name:<8}{miss:>4}{fd:>6}{acc:>7.2f}  " + "  ".join(f"{kinds[k]:>8}" for k in KINDS))
json.dump(out, open(os.path.join(HERE, "results-compare.json"), "w"), ensure_ascii=False, indent=1)

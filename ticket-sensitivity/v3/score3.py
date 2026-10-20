#!/usr/bin/env python3
"""v3 評分，對照預先登記 H1–H6。用法：score3.py [--selftest]
燈號以 data/test-gold.jsonl（作者裁定）為主；生成標籤另列。"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v2"))
from common2 import ORDER, read_jsonl  # noqa: E402

gen = {r["id"]: r for r in read_jsonl(os.path.join(HERE, "data/test.jsonl"))}
SCHEMES = ["E3", "E5a", "E5b", "E5"]


def labels(src):
    lab = {i: r["gold_light"] for i, r in gen.items()}
    if src == "human":
        for g in read_jsonl(os.path.join(HERE, "data/test-gold.jsonl")):
            lab[g["id"]] = g["gold_light"]
    return lab


def evaluate(pred, lab):
    res = {}
    for k in SCHEMES:
        kind_red = Counter(); kind_n = Counter()
        for i, r in gen.items():
            kind_n[r["kind"]] += 1; kind_red[r["kind"]] += pred[i][k] == "紅"
        res[k] = {"紅燈漏判": sum(lab[i] == "紅" and pred[i][k] != "紅" for i in lab),
                  "誤判成紅": sum(lab[i] != "紅" and pred[i][k] == "紅" for i in lab),
                  "正確率": round(sum(lab[i] == pred[i][k] for i in lab) / len(lab), 3),
                  "各類判紅": {t: f"{kind_red[t]}/{kind_n[t]}" for t in kind_n}}
    return res


def gates(res):
    e5, e3 = res["E5"], res["E3"]
    num = lambda s: int(s.split("/")[0])
    kr = e5["各類判紅"]
    return {"H1 E5 紅燈漏判=0": e5["紅燈漏判"] == 0,
            "H2 系統路徑-紅 ≥11/12": num(kr["系統路徑-紅"]) >= 11,
            "H3 E5 誤判成紅 ≤ E3+3": e5["誤判成紅"] <= e3["誤判成紅"] + 3,
            "H4 系統路徑-黃＋一般路徑-綠 判紅 ≤2": num(kr["系統路徑-黃"]) + num(kr["一般路徑-綠"]) <= 2,
            "H5 自評淡化 8/8": num(kr["自評淡化"]) == 8,
            "H6 自評誇大 判紅 ≤1": num(kr["自評誇大"]) <= 1}


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        lab = labels("gen")
        allg = {i: {k: "綠" for k in SCHEMES} for i in gen}
        allr = {i: {k: "紅" for k in SCHEMES} for i in gen}
        a, b = evaluate(allg, lab), evaluate(allr, lab)
        nred = sum(v == "紅" for v in lab.values())
        assert a["E5"]["紅燈漏判"] == nred and b["E5"]["紅燈漏判"] == 0
        assert not gates(a)["H1 E5 紅燈漏判=0"] and not gates(b)["H6 自評誇大 判紅 ≤1"]
        print(f"✓ 評分器自證：全綠漏判 {nred}；全紅 H6 失敗"); sys.exit()
    pred = {r["id"]: r for r in read_jsonl(os.path.join(HERE, "pred-test.jsonl"))}
    assert set(pred) == set(gen), "預測不齊"
    out = {}
    for src, name in [("human", "作者裁定"), ("gen", "生成標籤")]:
        if src == "human" and not os.path.exists(os.path.join(HERE, "data/test-gold.jsonl")):
            continue
        res = evaluate(pred, labels(src)); out[name] = {"res": res, "gates": gates(res)}
        print(f"\n== {name} ==")
        for k in SCHEMES:
            print(f"{k:<4} 漏判 {res[k]['紅燈漏判']:>2} 誤判成紅 {res[k]['誤判成紅']:>2} 正確率 {res[k]['正確率']:.2f}  {res[k]['各類判紅']}")
        for g, ok in gates(res).items():
            print(("✓" if ok else "✗"), g)
    json.dump(out, open(os.path.join(HERE, "results-test.json"), "w"), ensure_ascii=False, indent=1)

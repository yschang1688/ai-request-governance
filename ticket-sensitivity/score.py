#!/usr/bin/env python3
"""評分。用法：score.py <pred.jsonl> <label> [out.json]
         score.py --selftest     （AC-3：全猜綠、全猜紅兩個假預測，檢查評分器不是空轉）

pred 每行 {"id", "output": 模型原始字串}，或 {"id", "light": 燈號}（規則層、決策層用）。
標籤：data/test-gold.jsonl（作者裁定）存在就用它覆蓋生成標籤，否則用 test-meta.jsonl。
"""
import json
import os
import sys
from collections import Counter

from common import HERE, LIGHTS, ORDER, basis_list, parse_json, read_jsonl

D = os.path.join(HERE, "data")


def load_gold():
    meta = {r["id"]: r for r in read_jsonl(os.path.join(D, "test-meta.jsonl"))}
    gp = os.path.join(D, os.environ.get("GOLD", "test-gold.jsonl"))
    adjudicated = os.path.exists(gp)
    if adjudicated:
        for g in read_jsonl(gp):
            meta[g["id"]]["gold_light"] = g["gold_light"]
    return meta, adjudicated


def pred_of(p):
    if "light" in p:
        return p["light"] if p["light"] in ORDER else None, None
    obj = parse_json(p.get("output"))
    if obj is None:
        return None, None
    light = obj.get("燈號")
    return (light if light in ORDER else None), obj


def score(preds, gold):
    pm = {p["id"]: p for p in preds}
    conf = Counter()
    fa = fd = under = parse_fail = 0
    fields_ok = Counter()
    basis_tot = basis_ok = 0
    trap = Counter(); trap_ok = Counter()
    miss_ids, deny_ids = [], []
    for gid, g in gold.items():
        light, obj = pred_of(pm.get(gid, {}))
        gl = g["gold_light"]
        if light is None:
            parse_fail += 1
        conf[(gl, light)] += 1
        if gl == "紅" and light != "紅":
            fa += 1; miss_ids.append(gid)
        if gl != "紅" and light == "紅":
            fd += 1; deny_ids.append(gid)
        if gl == "黃" and light == "綠":
            under += 1
        if g["trap"] != "無":
            trap[g["trap"]] += 1
            trap_ok[g["trap"]] += (light == gl)
        if obj:
            gf = g["gold_fields"]
            fields_ok["需要模型"] += obj.get("需要模型") == gf["需要模型"]
            ps, gs = set(obj.get("資料類型") or []), set(gf["資料類型"])
            fields_ok["資料類型"] += (len(ps & gs) / len(ps | gs)) if (ps | gs) else 1
            fields_ok["資料位置"] += (gf["資料位置"] == "未提供") == (str(obj.get("資料位置", "")).strip() in ("", "未提供"))
            for b in basis_list(obj):
                basis_tot += 1
                basis_ok += len(b) >= 2 and b in g["text"]
    n = len(gold)
    f1s = []
    for c in LIGHTS:
        tp = conf[(c, c)]
        fp = sum(v for (gl, pl), v in conf.items() if pl == c and gl != c)
        fn = sum(v for (gl, pl), v in conf.items() if gl == c and pl != c)
        f1s.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return {
        "n": n, "紅燈漏判": fa, "誤判成紅": fd, "黃判成綠": under, "解析失敗": parse_fail,
        "正確率": round(sum(conf[(c, c)] for c in LIGHTS) / n, 3),
        "macroF1": round(sum(f1s) / 3, 3),
        "欄位": {k: round(v / n, 3) for k, v in fields_ok.items()},
        "依據有效率": round(basis_ok / basis_tot, 3) if basis_tot else None,
        "陷阱": {k: f"{trap_ok[k]}/{trap[k]}" for k in trap},
        "漏判id": miss_ids, "誤判id": deny_ids,
        "混淆": {f"{gl}→{pl}": v for (gl, pl), v in sorted(conf.items(), key=str)},
    }


def selftest():
    gold, _ = load_gold()
    red = sum(g["gold_light"] == "紅" for g in gold.values())
    nonred = len(gold) - red
    s_g = score([{"id": i, "light": "綠"} for i in gold], gold)
    s_r = score([{"id": i, "light": "紅"} for i in gold], gold)
    assert s_g["紅燈漏判"] == red and s_g["誤判成紅"] == 0, s_g
    assert s_r["紅燈漏判"] == 0 and s_r["誤判成紅"] == nonred, s_r
    s_bad = score([{"id": i, "output": "我覺得是紅燈"} for i in gold], gold)
    assert s_bad["解析失敗"] == len(gold) and s_bad["紅燈漏判"] == red, s_bad
    print(f"✓ 評分器自證：全猜綠漏判 {red}、全猜紅誤判 {nonred}、非 JSON 全數計錯")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        selftest(); sys.exit()
    pred_path, label = sys.argv[1], sys.argv[2]
    gold, adj = load_gold()
    res = score(read_jsonl(pred_path), gold)
    res["受測"] = label
    res["標籤來源"] = "作者裁定" if adj else "生成標籤（未裁定）"
    print(json.dumps({k: v for k, v in res.items() if k not in ("漏判id", "誤判id", "混淆")}, ensure_ascii=False))
    if len(sys.argv) > 3:
        json.dump(res, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)

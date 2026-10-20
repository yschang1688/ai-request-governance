#!/usr/bin/env python3
"""v3 生成批次驗證。用法：validate.py <batch.jsonl>"""
import json, re, sys, os
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(H))
from syspath import classify_path
C = {c["id"]: c for c in json.load(open(os.path.join(H, "cases.json")))}
SENS = ["客戶", "薪資", "薪水", "配方", "配比", "BOM", "報價", "個資", "身分證", "財報", "密碼", "底價", "成本"]
L = [json.loads(l) for l in open(sys.argv[1])]
bad = []
for x in L:
    c = C[x["id"]]; f = x["fields"]
    if x["gold_light"] != c["gold_light"] or x["kind"] != c["kind"] or f["風險等級"] != c["self_report"] or f["需求單位"] != c["unit"]:
        bad.append((x["id"], "屬性不符"))
    allv = " ".join(str(v) for v in f.values())
    if any(b not in allv for b in x["gold_basis"]): bad.append((x["id"], "basis"))
    if not re.search(r"\d", f["驗收標準"]): bad.append((x["id"], "驗收無數字"))
    if f["資料在哪、能不能拿到"] == "沒有" and f["AI 可行性"] == "需要模型": bad.append((x["id"], "欄位矛盾"))
    txt = f["標題"] + f["描述"]
    if c["kind"] == "系統路徑-紅":
        if not re.search(r"\\\\|//|[A-Za-z]:\\|https?://", txt): bad.append((x["id"], "缺路徑"))
        hit = [w for w in SENS if w in txt]
        if hit: bad.append((x["id"], f"出現機敏字眼{hit}"))
    if c["kind"] in ("一般路徑-綠",) or (c["gold_light"] == "綠"):
        if classify_path(allv)[0] != "綠": bad.append((x["id"], "綠燈單路徑含系統詞"))
print(len(L), bad)

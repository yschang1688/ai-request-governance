#!/usr/bin/env python3
"""合併四批生成 → 依 case 屬性檢查 → data/dev.jsonl、data/test.jsonl。"""
import glob
import json
import os
import re
from collections import Counter

from common2 import HERE, read_jsonl

cases = {c["id"]: c for c in json.load(open(os.path.join(HERE, "gen/cases.json"), encoding="utf-8"))}
rows = []
for p in sorted(glob.glob(os.path.join(HERE, "data/gen/*.jsonl"))):
    for r in read_jsonl(p):
        r["writer"] = os.path.basename(p)[0]
        rows.append(r)
err = []
seen = set()
for r in rows:
    c = cases.get(r["id"]); f = r["fields"]
    if c is None:
        err.append(f"{r['id']} 不在 cases"); continue
    if r["id"] in seen:
        err.append(f"{r['id']} 重複")
    seen.add(r["id"])
    for k in ["gold_light", "trap", "defect"]:
        if r[k] != c[k]:
            err.append(f"{r['id']} {k} 不符")
    if f["風險等級"] != c["self_report"]:
        err.append(f"{r['id']} 自評不符")
    r["self_kind"] = c["self_kind"]
    contra = f["資料在哪、能不能拿到"] == "沒有" and f["AI 可行性"] == "需要模型"
    nonum = not re.search(r"\d", f["驗收標準"])
    if (c["defect"] == "欄位矛盾") != contra or (c["defect"] == "驗收不可量測") != nonum:
        err.append(f"{r['id']} 缺陷定義不符")
    if any(b not in " ".join(map(str, f.values())) for b in r.get("gold_basis", [])):
        err.append(f"{r['id']} 依據不在原文")
missing = set(cases) - seen
if missing:
    err.append(f"缺 {len(missing)} 筆：{sorted(missing)[:10]}")
if err:
    print("✗", *err[:30], sep="\n  "); raise SystemExit(1)
for s in ["dev", "test"]:
    R = sorted([r for r in rows if r["id"].startswith(s)], key=lambda r: r["id"])
    with open(os.path.join(HERE, f"data/{s}.jsonl"), "w", encoding="utf-8") as fo:
        for r in R:
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(s, len(R), dict(Counter(r["gold_light"] for r in R)), dict(Counter(r["writer"] for r in R)))
print("✓ 屬性、缺陷定義、依據全數通過")

#!/usr/bin/env python3
"""合併生成批次 → 依模板分組切分 → mlx-lm 訓練格式。AC-2 前兩項的斷言都在這裡。

輸出（data/）：train.jsonl、valid.jsonl（mlx-lm chat 格式）、test-meta.jsonl（評分用）
"""
import glob
import json
import os
import sys
from collections import Counter

from common import HERE, SHORT_INSTR, target_json, read_jsonl

D = os.path.join(HERE, "data")
tpl = {t["template_id"]: t for t in json.load(open(os.path.join(HERE, "gen/templates.json"), encoding="utf-8"))}

rows = []
for p in sorted(glob.glob(os.path.join(D, "gen/batch-*.jsonl"))):
    rows += read_jsonl(p)

errors = []
seen = set()
for r in rows:
    t = tpl.get(r.get("template_id"))
    if t is None:
        errors.append(f"{r.get('id')}: 未知模板")
        continue
    if r["id"] in seen:
        errors.append(f"{r['id']}: id 重複")
    seen.add(r["id"])
    if r["gold_light"] != t["gold_light"]:
        errors.append(f"{r['id']}: 燈號 {r['gold_light']} 與模板 {t['gold_light']} 不符")
    for b in r.get("gold_basis", []):
        if b not in r["text"]:
            errors.append(f"{r['id']}: 依據片段不在原文")
    for k in ["痛點", "資料位置", "需要模型", "資料類型"]:
        if k not in r.get("gold_fields", {}):
            errors.append(f"{r['id']}: 缺欄位 {k}")
    r["split"] = t["split"]

if errors:
    print("✗ 資料檢查失敗：", *errors[:30], sep="\n  ")
    sys.exit(1)

split = {s: [r for r in rows if r["split"] == s] for s in ["train", "valid", "test"]}

# 斷言：模板零重疊
tsets = {s: {r["template_id"] for r in v} for s, v in split.items()}
assert not (tsets["train"] & tsets["test"]) and not (tsets["valid"] & tsets["test"]) and not (tsets["train"] & tsets["valid"]), "模板跨切分"

# 斷言：測試集燈號比例與陷阱數
test = split["test"]
c = Counter(r["gold_light"] for r in test)
n = len(test)
for light, target in [("綠", .40), ("黃", .30), ("紅", .30)]:
    assert abs(c[light] / n - target) <= .05, f"測試集 {light} 比例 {c[light]}/{n} 超出 ±5%"
tc = Counter(r["trap"] for r in test if r["trap"] != "無")
for trap in ["同詞異義", "隱性機敏", "個資變形", "注入", "安全長單"]:
    assert tc[trap] >= 8, f"測試集陷阱 {trap} 只有 {tc[trap]} 張"


def chat(r):
    return {"messages": [{"role": "user", "content": f"{SHORT_INSTR}\n{r['text']}"},
                         {"role": "assistant", "content": target_json(r)}]}


for s in ["train", "valid"]:
    with open(os.path.join(D, f"{s}.jsonl"), "w", encoding="utf-8") as f:
        for r in split[s]:
            f.write(json.dumps(chat(r), ensure_ascii=False) + "\n")
with open(os.path.join(D, "test-meta.jsonl"), "w", encoding="utf-8") as f:
    for r in test:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

for s, v in split.items():
    print(s, len(v), dict(Counter(r["gold_light"] for r in v)))
print("測試集陷阱", dict(tc))
print("✓ 切分完成，模板零重疊")

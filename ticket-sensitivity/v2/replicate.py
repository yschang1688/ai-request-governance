#!/usr/bin/env python3
"""事後探索：在 v2 測試集重跑 v1 的地端方案，看排名是否重現。輸入一律用 E3 的文字（標題＋描述），與 v1 同格式。
用法：replicate.py run     # 跑 A 規則、B 1.5B 原版、D 1.5B+LoRA（MLX；以環境變數 MLX_PY 指定裝有 mlx-lm 的 python）
      replicate.py score   # 合併 C（9B 單獨）、E3，兩套標籤各算一次，寫 results-replicate.json
不屬於 v2 預先登記，報告與圖表一律標「事後探索」。"""
import json
import os
import subprocess
import sys

from common2 import HERE, ORDER, classify, light_max, parse_json, read_jsonl, text_e3

ADAPTER = os.environ.get("ADAPTER", os.path.join(HERE, "..", "adapters-best"))  # LoRA 權重不進 repo
PY = os.environ.get("MLX_PY", sys.executable)
rows = read_jsonl(os.path.join(HERE, "data/test.jsonl"))

MLX = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from common import ENGINEERED, SHORT_INSTR
from mlx_lm import generate, load
from mlx_lm.sample_utils import make_sampler
mode, adapter, inp, out = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
model, tok = load("mlx-community/Qwen2.5-1.5B-Instruct-4bit", adapter_path=None if adapter == "-" else adapter)
sp = make_sampler(temp=0.0)
with open(out, "w") as fo:
    for l in open(inp):
        r = json.loads(l)
        head = SHORT_INSTR if mode == "short" else ENGINEERED
        p = tok.apply_chat_template([{"role": "user", "content": f"{head}\n{r['text']}"}], add_generation_prompt=True)
        fo.write(json.dumps({"id": r["id"], "output": generate(model, tok, prompt=p, max_tokens=400, sampler=sp)}, ensure_ascii=False) + "\n")
'''


def run():
    inp = os.path.join(HERE, "data/replicate-input.jsonl")
    with open(inp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"id": r["id"], "text": text_e3(r["fields"])}, ensure_ascii=False) + "\n")
    with open(os.path.join(HERE, "pred-rep-A.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"id": r["id"], "light": classify(text_e3(r["fields"]))["light"]}, ensure_ascii=False) + "\n")
    script = os.path.join(HERE, "data/_mlx_rep.py")
    open(script, "w").write(MLX)
    parent = os.path.dirname(HERE)
    for tag, mode, ad in [("B", "engineered", "-"), ("D", "short", ADAPTER)]:
        print("MLX", tag, flush=True)
        subprocess.run([PY, script, parent, mode, ad, inp, os.path.join(HERE, f"pred-rep-{tag}.jsonl")], check=True)
    print("done")


def score():
    gen = {r["id"]: r["gold_light"] for r in rows}
    human = {json.loads(l)["id"]: json.loads(l)["gold_light"] for l in open(os.path.join(HERE, "data/test-gold.jsonl"))}
    p23 = {r["id"]: r for r in read_jsonl(os.path.join(HERE, "pred-test.jsonl"))}
    A = {r["id"]: r["light"] for r in read_jsonl(os.path.join(HERE, "pred-rep-A.jsonl"))}
    B = {r["id"]: (parse_json(r["output"]) or {}).get("燈號") for r in read_jsonl(os.path.join(HERE, "pred-rep-B.jsonl"))}
    D = {r["id"]: (parse_json(r["output"]) or {}).get("燈號") for r in read_jsonl(os.path.join(HERE, "pred-rep-D.jsonl"))}
    schemes = {
        "A 只用規則": A,
        "B 1.5B 原版": B,
        "D 1.5B+LoRA": D,
        "E 規則+LoRA": {i: light_max(A[i], D[i]) for i in A},
        "C 9B": {i: p23[i]["e3_model"] for i in A},
        "E3 格式規則+9B": {i: p23[i]["E3"] for i in A},
    }
    out = {}
    for lab_name, lab in [("作者裁定", human), ("生成標籤", gen)]:
        print(f"\n== {lab_name} ==")
        for name, pred in schemes.items():
            miss = sum(lab[i] == "紅" and pred[i] != "紅" for i in lab)
            fd = sum(lab[i] != "紅" and pred[i] == "紅" for i in lab)
            acc = sum(lab[i] == pred[i] for i in lab) / len(lab)
            bad = sum(pred[i] not in ORDER for i in lab)
            out.setdefault(lab_name, {})[name] = {"紅燈漏判": miss, "誤判成紅": fd, "正確率": round(acc, 2), "輸出無效": bad}
            print(f"{name:<14} 漏判 {miss:>2}  誤判成紅 {fd:>2}  正確率 {acc:.2f}  輸出無效 {bad}")
    json.dump(out, open(os.path.join(HERE, "results-replicate.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    {"run": run, "score": score}[sys.argv[1]]()

#!/usr/bin/env python3
"""v2 評分，對照預先登記門檻 G1–G7。用法：score2.py dev|test [--selftest]
燈號標籤：data/{split}-gold.jsonl（作者裁定）存在就用它，否則用生成標籤並註明。
自評類型與合理性缺陷：以生成時植入的屬性為準。"""
import json
import os
import sys
from collections import Counter

from common2 import HERE, ORDER, read_jsonl, self_low

split = sys.argv[1]
gen = {r["id"]: r for r in read_jsonl(os.path.join(HERE, f"data/{split}.jsonl"))}
gp = os.path.join(HERE, f"data/{split}-gold.jsonl")
adjud = os.path.exists(gp)
gold = {i: r["gold_light"] for i, r in gen.items()}
if adjud:
    for g in read_jsonl(gp):
        gold[g["id"]] = g["gold_light"]


def evaluate(pred):
    res = {}
    for k in ["E3", "E4"]:
        miss = sum(gold[i] == "紅" and pred[i][k] != "紅" for i in gold)
        fd = sum(gold[i] != "紅" and pred[i][k] == "紅" for i in gold)
        acc = sum(gold[i] == pred[i][k] for i in gold) / len(gold)
        ys = [i for i in gold if gold[i] == "黃"]
        yacc = sum(pred[i][k] == "黃" for i in ys) / len(ys) if ys else None
        traps = Counter(); tok = Counter()
        for i, r in gen.items():
            if r["trap"] != "無":
                traps[r["trap"]] += 1; tok[r["trap"]] += pred[i][k] == gold[i]
        res[k] = {"紅燈漏判": miss, "誤判成紅": fd, "正確率": round(acc, 3),
                  "黃燈正確率": round(yacc, 3) if yacc is not None else None,
                  "陷阱": {t: f"{tok[t]}/{traps[t]}" for t in traps}}
    # 自評比對（用 E4 最終燈號）
    low = [i for i, r in gen.items() if r["self_kind"] == "偏低"]
    ok = [i for i, r in gen.items() if r["self_kind"] == "正確"]
    flag = {i: self_low(pred[i]["E4"], gen[i]["fields"]["風險等級"]) for i in gen}
    res["自評偏低"] = {"抓到": f"{sum(flag[i] for i in low)}/{len(low)}", "誤報": sum(flag[i] for i in ok)}
    # 合理性
    rd = [i for i, r in gen.items() if r["defect"] in ("欄位矛盾", "驗收不可量測")]
    hit = sum(gen[i]["defect"] in pred[i]["rule_defects"] for i in rd)
    false_r = sum(bool(pred[i]["rule_defects"]) for i, r in gen.items() if r["defect"] == "無")
    res["規則合理性"] = {"抓到": f"{hit}/{len(rd)}", "誤報": false_r}
    fit_def = [i for i, r in gen.items() if r["defect"] == "痛點效益不符"]
    fit_clean = [i for i, r in gen.items() if r["defect"] == "無"]
    res["痛點效益（9B）"] = {"抓到": f"{sum(pred[i]['fit'] == '否' for i in fit_def)}/{len(fit_def)}",
                         "誤報": sum(pred[i]["fit"] == "否" for i in fit_clean),
                         "解析失敗": sum(pred[i]["fit"] not in ("是", "否") for i in gen)}
    return res


def gates(res):
    n_low = int(res["自評偏低"]["抓到"].split("/")[1]); got_low = int(res["自評偏低"]["抓到"].split("/")[0])
    rd_got, rd_n = map(int, res["規則合理性"]["抓到"].split("/"))
    yd = None if res["E3"]["黃燈正確率"] is None else res["E4"]["黃燈正確率"] - res["E3"]["黃燈正確率"]
    return {"G1 E3 紅燈漏判=0": res["E3"]["紅燈漏判"] == 0,
            "G2 E4 紅燈漏判=0": res["E4"]["紅燈漏判"] == 0,
            "G3 E4 黃燈≥E3+10pp": yd is not None and yd >= 0.10,
            "G4 自評偏低≥18/20": got_low >= round(18 / 20 * n_low),
            "G5 自評誤報≤5": res["自評偏低"]["誤報"] <= 5,
            "G6 規則合理性≥17/18 且誤報≤3": rd_got >= round(17 / 18 * rd_n) and res["規則合理性"]["誤報"] <= 3}


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        # 假預測：全判綠 → 紅燈漏判＝紅燈數、自評偏低抓不到；全判紅 → 漏判 0
        allg = {i: {"E3": "綠", "E4": "綠", "rule_defects": [], "fit": "是"} for i in gen}
        allr = {i: {"E3": "紅", "E4": "紅", "rule_defects": ["欄位矛盾", "驗收不可量測"], "fit": "否"} for i in gen}
        a, b = evaluate(allg), evaluate(allr)
        nred = sum(v == "紅" for v in gold.values())
        assert a["E3"]["紅燈漏判"] == nred and b["E3"]["紅燈漏判"] == 0
        assert a["自評偏低"]["抓到"].startswith("0/")
        print(f"✓ 評分器自證：全綠漏判 {nred}、全紅漏判 0、全綠抓不到自評偏低")
        sys.exit()
    pred = {r["id"]: r for r in read_jsonl(os.path.join(HERE, f"pred-{split}.jsonl"))}
    missing = set(gen) - set(pred)
    assert not missing, f"預測缺 {len(missing)} 筆"
    res = evaluate(pred)
    print("標籤來源：", "作者裁定" if adjud else "生成標籤（未裁定）")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    for k, v in gates(res).items():
        print(("✓" if v else "✗"), k)
    json.dump({"res": res, "gates": gates(res), "adjudicated": adjud},
              open(os.path.join(HERE, f"results-{split}.json"), "w"), ensure_ascii=False, indent=1)

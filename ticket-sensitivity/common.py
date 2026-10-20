"""共用：提示詞、JSON 解析、燈號順序。"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = {"綠": 0, "黃": 1, "紅": 2}
LIGHTS = ["綠", "黃", "紅"]

# LoRA 用短指令（判準靠訓練內化）
SHORT_INSTR = "判定下列 AI 需求工單的機敏燈號並抽取欄位，只輸出 JSON："

# 未微調模型用：短指令＋完整判準＋輸出格式
POLICY = open(os.path.join(HERE, "policy.md"), encoding="utf-8").read()
ENGINEERED = f"""你是工單機敏分級員。依下列判準，判定 AI 需求工單的燈號並抽取欄位。

{POLICY}

只輸出一個 JSON 物件，不要其他文字，格式：
{{"燈號":"綠|黃|紅","痛點":"…","資料位置":"…（工單沒寫填 未提供）","需要模型":"是|否|不確定","資料類型":["個資|客戶資料|配方|BOM|財務|資安|營運數據|內部系統|公開資料|一般文件"],"依據":["工單內逐字片段"]}}

工單："""


def target_json(ex: dict) -> str:
    """訓練目標：把 gold 組成模型該輸出的 JSON 字串。"""
    g = ex["gold_fields"]
    obj = {"燈號": ex["gold_light"], "痛點": g["痛點"], "資料位置": g["資料位置"],
           "需要模型": g["需要模型"], "資料類型": g["資料類型"], "依據": ex["gold_basis"]}
    return json.dumps(obj, ensure_ascii=False)


def parse_json(text):
    """從模型輸出抓第一個 JSON 物件；失敗回 None（評分時整筆計錯）。"""
    if text is None:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def basis_list(obj):
    """模型的「依據」可能是清單或單一字串；統一成清單，避免把字串逐字拆開驗證。"""
    b = (obj or {}).get("依據")
    if isinstance(b, str):
        return [b]
    return [x for x in (b or []) if isinstance(x, str)]

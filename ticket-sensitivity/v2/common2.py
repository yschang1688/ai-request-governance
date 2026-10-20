"""v2 共用：輸入組裝、9B 呼叫、合理性規則。燈號提示詞沿用 v1 的 ENGINEERED，E3／E4 只差在餵進去的欄位。"""
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from common import ENGINEERED, ORDER, parse_json, read_jsonl  # noqa: E402,F401
from rules import RED_KEYWORDS, YELLOW_KEYWORDS, classify  # noqa: E402

MODEL = "qwen3.5:9b"
FORMAT_ONLY = frozenset(RED_KEYWORDS) | frozenset(YELLOW_KEYWORDS)

# E4 讀的客觀欄位。「風險等級」是需求方自評，永不進判燈號的輸入（v2-requirements 設計約束）
OBJECTIVE = ["需求單位", "一句話痛點", "現行做法與頻率", "資料在哪、能不能拿到",
             "預期效益指標", "驗收標準", "期望時程", "AI 可行性"]


def text_e3(f):
    return f"標題：{f['標題']}\n描述：{f['描述']}"


def text_e4(f):
    out = "\n".join([text_e3(f)] + [f"{k}：{f[k]}" for k in OBJECTIVE])
    assert "風險等級：" not in out, "自評欄位不得進入判燈號輸入"
    return out


def all_text(f):
    """格式規則掃全部欄位（自評欄位只是單一燈號字，掃到也無害）。"""
    return "\n".join(f"{k}：{v}" for k, v in f.items() if k != "風險等級")


FIT_PROMPT = """判斷這張 AI 需求工單的「一句話痛點」和「預期效益指標」是否在講同一件事。
只要效益指標量的是痛點所描述問題的改善，就算相符；量的是無關的另一件事，就算不符。
只輸出 JSON：{"相符":"是|否","理由":"一句話"}

"""


def ollama(prompt, num_predict=500):
    req = urllib.request.Request("http://localhost:11434/api/generate",
        data=json.dumps({"model": MODEL, "prompt": prompt, "stream": False, "think": False,
                         "options": {"temperature": 0, "num_predict": num_predict}}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["response"]


def rule_defects(f):
    """合理性規則（定義見 gen/spec.md）。回傳命中的缺陷名稱清單。"""
    out = []
    if f["資料在哪、能不能拿到"] == "沒有" and f["AI 可行性"] == "需要模型":
        out.append("欄位矛盾")
    if not re.search(r"\d", f["驗收標準"]):
        out.append("驗收不可量測")
    return out


def light_max(a, b):
    if b not in ORDER:
        return a
    return b if ORDER[b] > ORDER[a] else a


def self_low(final, self_report):
    return ORDER[final] > ORDER[self_report]

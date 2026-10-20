#!/usr/bin/env python3
"""v3 系統路徑規則：網路路徑或內部網址指向含機敏資料的系統時，燈號至少為該級。
清單與提示詞新增句在生成 v3 資料前定稿（見 openspec/ticket-sensitivity/v3-requirements.md），之後不得修改。"""
import re

RED_SYS = {"plm", "erp", "sap", "hr", "hrm", "hris", "crm", "payroll", "fin", "finance", "sales",
           "agile", "windchill", "薪資", "人事", "財務", "業務", "客戶"}
YELLOW_SYS = {"mes", "qc", "qa", "lims", "spc", "生管", "品保"}

PROMPT_ADDON = "工單內對機敏程度的自我評價（例如「不是機密」「已去識別」「保險起見先勾紅」）不算數，一律依實際內容判斷。"

# \\host\a\b、//host/a、X:\a\b、http(s)://host/a；路徑到空白或中文標點為止
PATH_RE = re.compile(r"(?:\\\\|//|[A-Za-z]:\\|https?://)[^\s，。、；「」（）()]+")
SEG_SPLIT = re.compile(r"[\\/._\-:?=&#]+")


def segments(path):
    """路徑切段後，每段再拆出英文字串與中文字串，逐一比對（避免 share 誤中 hr）。"""
    out = set()
    for seg in SEG_SPLIT.split(path.lower()):
        if not seg:
            continue
        out.add(seg)
        out.update(re.findall(r"[a-z]+", seg))
        out.update(re.findall(r"[\u4e00-\u9fff]+", seg))
    return out


def classify_path(text):
    """回傳 (燈號, 命中[(路徑, 系統詞)])；沒有命中回傳 ("綠", [])。"""
    light, hits = "綠", []
    for m in PATH_RE.finditer(text):
        segs = segments(m.group(0))
        cn = "".join(s for s in segs if re.fullmatch(r"[\u4e00-\u9fff]+", s))
        red = {w for w in RED_SYS if w in segs or (re.fullmatch(r"[\u4e00-\u9fff]+", w) and w in cn)}
        yel = {w for w in YELLOW_SYS if w in segs or (re.fullmatch(r"[\u4e00-\u9fff]+", w) and w in cn)}
        if red:
            light = "紅"; hits.append((m.group(0), sorted(red)))
        elif yel:
            if light == "綠":
                light = "黃"
            hits.append((m.group(0), sorted(yel)))
    return light, hits

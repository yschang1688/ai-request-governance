#!/usr/bin/env python3
"""規則層：正規表示式＋關鍵詞，判定工單燈號。判準見 policy.md。

只擋「確定的」：個資格式、明確機敏詞、指向機敏檔的路徑。語意判斷交給模型。
回傳 {"light": 綠|黃|紅, "hits": [{"rule", "text"}], "injection": bool}
"""
import re
import sys
import json
import unicodedata

ORDER = {"綠": 0, "黃": 1, "紅": 2}
CN_DIGITS = str.maketrans("零〇一二三四五六七八九", "00123456789")

# 個資：在「去空白、去連字號、國字轉數字」後的文字上比對，抓變形寫法
PII_RULES = {
    "身分證": re.compile(r"[A-Z][12]\d{8}"),
    "手機": re.compile(r"09\d{8}"),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "統編": re.compile(r"(?:統一編號|統編)[:：]?\d{8}"),
}

# 紅燈關鍵詞；同一句出現公開語境時不由規則單獨判紅（留給模型）
RED_KEYWORDS = {
    "配方": ["配方", "配比"],
    "BOM": ["BOM", "物料清單"],
    "客戶資料": ["客戶名單", "客戶聯絡", "客戶報價", "客戶資料"],
    "未公開財報": ["未公開財報", "財報草稿", "未發布財報", "季報草稿"],
    "資安設定": ["防火牆規則", "密碼", "金鑰", "API key", "存取憑證"],
    "規格書": ["未公開規格", "規格書草稿", "設計圖檔"],
}
PUBLIC_MARKERS = ["公開文獻", "論文", "期刊", "已發布", "官網", "公開資料", "教科書", "公開報導"]

# 指向機敏檔案的路徑（不論句子語境）
PATH_RULE = re.compile(r"(?:[A-Za-z]:\\|\\\\|/)[^\s，。]*?(?:BOM|配方|客戶|財報|規格)[^\s，。]*", re.I)

YELLOW_KEYWORDS = {
    "營運數據": ["良率", "產能", "不良率", "稼動率", "出貨量", "營運數據"],
    "未公開專案": ["專案代號", "內部代號", "未公開專案"],
    "內部系統": ["內部系統", "MES", "內部平台"],
}

INJECTION_MARKERS = ["請標為綠燈", "標成綠燈", "請判綠", "忽略以上", "忽略前面", "不要判紅", "標為綠"]


def _norm_pii(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = re.sub(r"[\s\-]", "", t)
    # 只轉連續 3 個以上的國字數字，避免把「統一編號」的「一」轉掉
    return re.sub(r"[零〇一二三四五六七八九]{3,}", lambda m: m.group(0).translate(CN_DIGITS), t)


def _sentences(text: str):
    return [s for s in re.split(r"[。！？!?\n；;]", text) if s.strip()]


def classify(text: str, disabled: frozenset = frozenset()) -> dict:
    """disabled：停用的規則名稱，只給 test_rules.py 的反向檢核用。"""
    hits = []
    norm = _norm_pii(text)
    for name, pat in PII_RULES.items():
        if name in disabled:
            continue
        for m in pat.finditer(norm):
            hits.append({"rule": f"紅:個資:{name}", "text": m.group(0)})

    nfkc = unicodedata.normalize("NFKC", text)
    if "路徑" not in disabled:
        for m in PATH_RULE.finditer(nfkc):
            hits.append({"rule": "紅:機敏路徑", "text": m.group(0)})

    for sent in _sentences(nfkc):
        public = any(p in sent for p in PUBLIC_MARKERS)
        for name, words in RED_KEYWORDS.items():
            if name in disabled:
                continue
            for w in words:
                if w.lower() in sent.lower() and not public:
                    hits.append({"rule": f"紅:{name}", "text": sent.strip()})
                    break
        for name, words in YELLOW_KEYWORDS.items():
            if name in disabled:
                continue
            for w in words:
                if w in sent:
                    hits.append({"rule": f"黃:{name}", "text": sent.strip()})
                    break

    light = "綠"
    for h in hits:
        lv = h["rule"].split(":")[0]
        if ORDER[lv] > ORDER[light]:
            light = lv
    injection = any(m in nfkc for m in INJECTION_MARKERS)
    return {"light": light, "hits": hits, "injection": injection}


if __name__ == "__main__":
    print(json.dumps(classify(sys.stdin.read()), ensure_ascii=False, indent=2))

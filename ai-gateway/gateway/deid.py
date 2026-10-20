"""去識別化：遮罩格式個資，送模型前換成可逆代碼，回應時還原。

格式定義沿用 ticket-sensitivity/rules.py 的四類（身分證、手機、email、統編），另加市話。
rules.py 是在去掉分隔符號後的文字上比對，只知道有、不知道在哪；這裡改寫成在原文上比對、
容許空白與連字號分隔，才能回報位置並替換。Python 的 \\d 也認全形數字。
認不得的寫法：自由文字裡的姓名、沒有標籤的 8 位數統編。
"""
import re
import unicodedata

from . import flags

SEP = r"[\s\-]?"
D = r"\d"
CN = "零〇一二三四五六七八九"

# 依序比對；位置重疊時先到的優先（email 先於電話，避免把信箱裡的數字切走）
DETECTORS = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)),
    ("身分證", re.compile(rf"(?<![A-Za-z0-9])[A-Za-z]{SEP}[12](?:{SEP}{D}){{8}}(?!\d)")),
    ("手機", re.compile(rf"(?:(?:\+|＋)?886{SEP}|[0０]){SEP}[9９](?:{SEP}{D}){{8}}(?!\d)")),
    ("手機", re.compile(rf"[零〇]九[{CN}]{{8}}")),
    ("市話", re.compile(rf"(?<!\d)(?:\(0[2-8]\)|0[2-8]){SEP}\d{{3,4}}{SEP}\d{{4}}(?!\d)")),
    ("統編", re.compile(r"(?:統一編號|統編)[^\d\n]{0,4}?(\d{8})(?!\d)")),
]


def core(value: str) -> str:
    """正規化：同一個值的不同寫法得到同一個代碼，也供測試做「只遮一半」的檢查。"""
    t = unicodedata.normalize("NFKC", value).translate(str.maketrans(CN, "0012345678" + "9"))
    t = re.sub(r"[^0-9A-Za-z@._+]", "", t).lower()
    t = t[1:] if t.startswith("+886") else t
    return "0" + t[3:] if t.startswith("886") else t


def find(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for kind, pat in DETECTORS:
        for m in pat.finditer(text):
            s, e = (m.start(1), m.end(1)) if pat.groups else (m.start(), m.end())
            if not any(s < e2 and s2 < e for s2, e2, _ in spans):
                spans.append((s, e, kind))
    return sorted(spans)


class Vault:
    """單次請求的代碼對照表，只存在記憶體，請求結束即丟。"""

    def __init__(self):
        self.by_core: dict[str, str] = {}
        self.raw: dict[str, str] = {}

    def code_for(self, value: str) -> str:
        key = core(value)
        if key not in self.by_core:
            code = f"⟨PII_{len(self.by_core) + 1}⟩"
            self.by_core[key] = code
            self.raw[code] = value
        return self.by_core[key]


def mask(text: str, vault: Vault) -> tuple[str, list[str]]:
    """回傳（遮罩後文字, 命中的類型清單）。"""
    if flags.off("deid"):
        return text, []
    out, last, kinds = [], 0, []
    for s, e, kind in find(text):
        out.append(text[last:s])
        out.append(vault.code_for(text[s:e]))
        kinds.append(kind)
        last = e
    out.append(text[last:])
    return "".join(out), kinds


CODE = re.compile(r"⟨PII_\d+⟩")
# 模型常把代碼的括號改掉（G11 第 1 次實測：⟨PII_2⟩ 被寫成 ⟪PII_2⟫），還原時容許這些變形，
# 也容許拿掉括號、底線換成空白或連字號。
OPEN, CLOSE = "⟨⟪〈《<[［(（{", "⟩⟫〉》>]］)）}"
CODE_LOOSE = re.compile(rf"[{re.escape(OPEN)}]?\s*PII[_\s-]?(\d+)\s*[{re.escape(CLOSE)}]?", re.I)


def restore(text: str, vault: Vault) -> tuple[str, int]:
    """還原已知代碼（含括號變形）；對不上的類代碼字串原樣留下並計數，回傳（還原後文字, 未知代碼數）。"""
    if flags.off("restore"):
        return text, 0
    pat = CODE if flags.off("restore_loose") else CODE_LOOSE
    unknown = 0

    def sub(m):
        nonlocal unknown
        canonical = m.group(0) if pat is CODE else f"⟨PII_{m.group(1)}⟩"
        if canonical in vault.raw:
            return vault.raw[canonical]
        unknown += 1
        return m.group(0)

    return pat.sub(sub, text), unknown

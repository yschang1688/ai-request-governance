"""G5b（T6 發現後新增，非預先登記門檻）：模型改寫代碼括號時仍要還原；編造的代碼要計入稽核。

起因：G11 第 1 次實測，9B 把 ⟨PII_2⟩ 寫成 ⟪PII_2⟫，使用者收到代碼而非原值，稽核的未知代碼計數也沒抓到。
這裡用「改寫括號的假模型」重現，每則輪流用一種變形。反向檢核：停用 restore_loose（退回只認 ⟨PII_n⟩）。
"""
import os
import re
from pathlib import Path

import pytest

from conftest import chat, jsonl_since, prompts, size

AUDIT = Path(os.environ["GATEWAY_VAR"]) / "gateway-audit.jsonl"
VARIANTS = [("⟪", "⟫"), ("<", ">"), ("[", "]"), ("（", "）"), ("〈", "〉")]


class RewritingModel:
    name = "rewriting"

    def __init__(self, inner):
        self.inner, self.i = inner, 0

    def complete(self, prompt: str) -> str:
        self.inner._log(prompt)  # 照樣寫模型端紀錄
        o, c = VARIANTS[self.i % len(VARIANTS)]
        self.i += 1
        return "已收到：" + re.sub(r"⟨PII_(\d+)⟩", lambda m: f"{o}PII_{m.group(1)}{c}", prompt)


class FabricatingModel(RewritingModel):
    def complete(self, prompt: str) -> str:
        self.inner._log(prompt)
        return "已收到，另外參考 ⟪PII_99⟫"


@pytest.fixture
def swap_model(gw_app):
    original = gw_app.model
    yield lambda cls: setattr(gw_app, "model", cls(original))
    gw_app.model = original


def test_g5b_restores_bracket_variants(gw, tokens, swap_model):
    swap_model(RewritingModel)
    bad = {}
    for r in prompts():
        answer = chat(gw, tokens[r["user"]], r["project"], r["level"], r["prompt"]).json()["answer"]
        missing = [p for p in r["pii"] if p not in answer]
        if missing or re.search(r"PII", answer):
            bad[r["id"]] = answer
    assert not bad, f"{len(bad)} 則未還原：{bad}"


def test_g5b_fabricated_code_is_counted(gw, tokens, swap_model):
    swap_model(FabricatingModel)
    offset = size(AUDIT)
    chat(gw, tokens["u-yellow"], "P-A", "yellow", "請回電 0912345678")
    entry = jsonl_since(AUDIT, offset)[-1]
    assert entry["content"]["unknown_codes"] == 1, entry

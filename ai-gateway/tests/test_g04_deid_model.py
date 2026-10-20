"""G4 去識別化：40 則含個資提問，模型端收到的內容裡原始個資出現 0 次。反向檢核：停用 deid。

逐字與正規化後都查（擋只遮一半），規則見 build_prompts.py 檔頭。
"""
import os
from pathlib import Path

from conftest import chat, jsonl_since, prompts, size
from gateway.deid import core

MODEL_LOG = Path(os.environ["GATEWAY_VAR"]) / "model-received.jsonl"


def leaks(text: str, pii: list[str]) -> list[str]:
    return [p for p in pii if p in text or core(p) in core(text)]


def test_g4_model_never_sees_raw_pii(gw, tokens):
    offset = size(MODEL_LOG)
    rows = prompts()
    for r in rows:
        assert chat(gw, tokens[r["user"]], r["project"], r["level"], r["prompt"]).status_code == 200
    received = jsonl_since(MODEL_LOG, offset)
    assert len(received) == len(rows), "模型端紀錄筆數與請求數不符"
    bad = {r["id"]: leaks(m["received"], r["pii"]) for r, m in zip(rows, received) if leaks(m["received"], r["pii"])}
    assert not bad, f"{len(bad)} 則提問的個資進了模型端：{bad}"

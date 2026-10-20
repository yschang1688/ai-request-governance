"""G6 稽核：跑一輪 G1–G5 份量的請求後掃稽核日誌——原始個資 0 次、每個請求一筆。反向檢核：停用 audit_redact。"""
import json
import os
from pathlib import Path

from conftest import chat, jsonl_since, prompts, size, user_token
from gateway.deid import core
from test_g01_authn_reject import alg_none, tampered
from test_g03_abac import CELLS

AUDIT = Path(os.environ["GATEWAY_VAR"]) / "gateway-audit.jsonl"


def test_g6_audit_complete_and_redacted(gw, tokens):
    offset, sent = size(AUDIT), 0
    for tok in (None, tampered(tokens["u-yellow"]), alg_none(tokens["u-yellow"]),
                user_token("u-yellow", "portal-noaud")):
        chat(gw, tok, "P-A", "yellow"); sent += 1
    for user, project, level, _ in CELLS:
        chat(gw, tokens[user], project, level); sent += 1
    rows = prompts()
    for r in rows:
        chat(gw, tokens[r["user"]], r["project"], r["level"], r["prompt"]); sent += 1

    entries = jsonl_since(AUDIT, offset)
    assert len(entries) == sent, f"稽核 {len(entries)} 筆，請求 {sent} 個"
    all_pii = [p for r in rows for p in r["pii"]]
    leaked = []
    for e in entries:
        text = json.dumps(e["content"], ensure_ascii=False)
        leaked += [p for p in all_pii if p in text or core(p) in core(text)]
    assert not leaked, f"稽核日誌出現原始個資 {len(leaked)} 次：{sorted(set(leaked))[:10]}"

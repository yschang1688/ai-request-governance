"""G7 稽核：非稽核員查日誌 403；稽核員 200，且「查日誌」本身新增一筆紀錄。反向檢核：停用 audit_rbac。"""
import os
from pathlib import Path

from conftest import bearer, jsonl_since, size

AUDIT = Path(os.environ["GATEWAY_VAR"]) / "gateway-audit.jsonl"


def test_g7_non_auditor_denied(gw, tokens):
    for u in ("u-green", "u-yellow", "u-red"):
        r = gw.get("/audit", headers=bearer(tokens[u]))
        assert r.status_code == 403, (u, r.status_code)


def test_g7_auditor_read_is_itself_logged(gw, tokens):
    offset = size(AUDIT)
    r = gw.get("/audit", headers=bearer(tokens["u-auditor"]))
    assert r.status_code == 200
    new = jsonl_since(AUDIT, offset)
    assert [(e["action"], e["decision"], e["user"]) for e in new] == [("audit.read", "allow", "u-auditor")], new

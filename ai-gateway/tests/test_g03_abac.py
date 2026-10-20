"""G3 授權：18 個組合與手寫的預期表一致。反向檢核：停用 policy。"""
from pathlib import Path

import pytest
import yaml

from conftest import chat

MATRIX = yaml.safe_load((Path(__file__).with_name("expected_matrix.yaml")).read_text(encoding="utf-8"))
CELLS = [(u, p, lvl, want) for u, ps in MATRIX.items() for p, lv in ps.items() for lvl, want in lv.items()]
assert len(CELLS) == 18


@pytest.mark.parametrize("user,project,level,want", CELLS)
def test_g3_matrix(gw, tokens, user, project, level, want):
    r = chat(gw, tokens[user], project, level)
    assert r.status_code == {"allow": 200, "deny": 403}[want], (user, project, level, r.status_code, r.text)

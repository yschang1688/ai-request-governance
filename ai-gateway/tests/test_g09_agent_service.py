"""G9 Agent 服務帳號（Client Credentials）：讀綠 200；讀黃、紅與寫入 403。

反向檢核：停用 policy（讀黃紅應轉 200）、停用 scope（寫入應轉 200）。
"""
import pytest

from conftest import agent_token, bearer


@pytest.fixture(scope="module")
def sa():
    return agent_token()


@pytest.mark.parametrize("ticket,want", [("T-B-G", 200), ("T-B-Y", 403), ("T-B-R", 403)])
def test_g9_read(api, sa, ticket, want):
    assert api.get(f"/tickets/{ticket}", headers=bearer(sa)).status_code == want


def test_g9_write_denied(api, sa):
    r = api.post("/tickets/T-B-G/comments", json={"text": "x"}, headers=bearer(sa))
    assert r.status_code == 403, r.text

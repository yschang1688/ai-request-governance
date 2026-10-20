"""G2 認證：3 個使用者的合法 token 都通過（各讀自己有權限的一格）。反向檢核：把 issuer 指到不存在的 realm。"""
import pytest

from conftest import chat

ALLOWED = {"u-green": ("P-A", "green"), "u-yellow": ("P-A", "yellow"), "u-red": ("P-B", "red")}


@pytest.mark.parametrize("user", list(ALLOWED))
def test_g2_accepts_valid_token(gw, tokens, user):
    r = chat(gw, tokens[user], *ALLOWED[user])
    assert r.status_code == 200, (user, r.status_code, r.text)

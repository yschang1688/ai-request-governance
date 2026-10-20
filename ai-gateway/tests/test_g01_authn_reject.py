"""G1 認證：6 種無效 token 都回 401。反向檢核：停用 auth。"""
import time

import pytest

from conftest import KC, b64, chat, kc_post, user_token


def tampered(tok):
    h, p, s = tok.split(".")
    s = ("A" if s[0] != "A" else "B") + s[1:]
    return f"{h}.{p}.{s}"


def alg_none(tok):
    _, p, _ = tok.split(".")
    return f"{b64({'alg': 'none', 'typ': 'JWT'})}.{p}."


def expired():
    tok = user_token("u-yellow", "portal-short")
    time.sleep(4)
    return tok


def other_issuer():
    # master realm 簽的 token：iss 不同、金鑰也不在 demo 的 JWKS
    from conftest import ENV
    s, t = kc_post(f"{KC}/master/protocol/openid-connect/token",
                   {"grant_type": "password", "client_id": "admin-cli",
                    "username": ENV["KC_BOOTSTRAP_ADMIN_USERNAME"], "password": ENV["KC_BOOTSTRAP_ADMIN_PASSWORD"]})
    assert s == 200, t
    return t["access_token"]


CASES = {
    "無 token": lambda t: None,
    "竄改簽章": lambda t: tampered(t["u-yellow"]),
    "alg:none": lambda t: alg_none(t["u-yellow"]),
    "過期": lambda t: expired(),
    "aud 不符": lambda t: user_token("u-yellow", "portal-noaud"),
    "iss 不符": lambda t: other_issuer(),
}


@pytest.mark.parametrize("case", list(CASES))
def test_g1_rejects_invalid_token(gw, tokens, case):
    r = chat(gw, CASES[case](tokens), "P-A", "yellow")
    assert r.status_code == 401, (case, r.status_code, r.text)

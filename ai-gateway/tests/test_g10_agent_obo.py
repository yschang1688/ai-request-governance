"""G10 Agent 代表使用者（Token Exchange）：權限不比使用者大。

- u-green 換來的 token 讀紅燈 403；u-red 換來的讀紅燈 200（反向檢核：停用 policy，前者應轉 200）。
- 不帶使用者 token 直接要求交換，IdP 拒絕。這是 Keycloak 端的行為，Gateway 的旗標關不掉；
  改用對照組證明測試有效：同一個請求補上使用者 token 就成功，所以失敗確實來自缺 token。
"""
from conftest import bearer, exchange


def obo(tokens, user):
    s, t = exchange(tokens[user])
    assert s == 200, t
    return t["access_token"]


def test_g10_green_user_cannot_read_red_via_agent(api, tokens):
    assert api.get("/tickets/T-B-R", headers=bearer(obo(tokens, "u-green"))).status_code == 403


def test_g10_red_user_can_read_red_via_agent(api, tokens):
    assert api.get("/tickets/T-B-R", headers=bearer(obo(tokens, "u-red"))).status_code == 200


def test_g10_exchange_without_user_token_rejected(tokens):
    s, t = exchange(None)
    assert s == 400, (s, t)
    s_ok, _ = exchange(tokens["u-green"])  # 對照組
    assert s_ok == 200

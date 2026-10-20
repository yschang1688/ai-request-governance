"""realm 煙霧測試：確認 demo realm 匯入後，各角色的 token 宣告符合 requirements 的角色表。

用法：python3 -I realm/check_realm.py   （需先 docker compose up；讀 ai-gateway/.env.local）
只用標準函式庫。任何一項不符就以非零碼結束。
"""
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = dict(l.strip().split("=", 1) for l in (HERE.parent / ".env.local").read_text().splitlines() if "=" in l)
TOKEN_URL = "http://127.0.0.1:8080/realms/demo/protocol/openid-connect/token"
EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS = "urn:ietf:params:oauth:token-type:access_token"
failures = []


def token(data):
    req = urllib.request.Request(TOKEN_URL, urllib.parse.urlencode(data).encode())
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def claims(tok):
    p = tok.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))


def auds(c):
    a = c.get("aud", [])
    return set([a] if isinstance(a, str) else a)


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def user_token(username, client="portal"):
    return token({"grant_type": "password", "client_id": client, "client_secret": ENV["DEMO_PORTAL_SECRET"],
                  "username": username, "password": ENV["DEMO_USER_PW"]})


EXPECT = {
    "u-green": ("製造", "green", ["P-A"]),
    "u-yellow": ("品保", "yellow", ["P-A", "P-B"]),
    "u-red": ("研發", "red", ["P-B"]),
    "u-auditor": ("資安", "none", []),
}
subs = {}
for u, (dept, clr, projects) in EXPECT.items():
    s, t = user_token(u)
    check(f"{u} 取得 token", s == 200, t)
    if s != 200:
        continue
    c = claims(t["access_token"])
    subs[u] = (c["sub"], t["access_token"])
    check(f"{u} 部門／等級／專案", (c.get("dept"), c.get("clearance"), sorted(c.get("projects") or [])) ==
          (dept, clr, sorted(projects)), (c.get("dept"), c.get("clearance"), c.get("projects")))
    check(f"{u} aud 含 ai-gateway 與 ticket-agent", {"ai-gateway", "ticket-agent"} <= auds(c), auds(c))
    roles = set(c.get("realm_access", {}).get("roles", []))
    check(f"{u} auditor 角色{'有' if u == 'u-auditor' else '無'}", ("auditor" in roles) == (u == "u-auditor"), roles)

s, t = user_token("u-green", "portal-noaud")
check("portal-noaud 的 aud 不含 ai-gateway", s == 200 and "ai-gateway" not in auds(claims(t["access_token"])))
s, t = user_token("u-green", "portal-short")
c = claims(t["access_token"]) if s == 200 else {}
check("portal-short 壽命 3 秒", c.get("exp", 0) - c.get("iat", 0) == 3, c.get("exp", 0) - c.get("iat", 0))

s, t = token({"grant_type": "client_credentials", "client_id": "ticket-agent", "client_secret": ENV["DEMO_AGENT_SECRET"]})
c = claims(t["access_token"]) if s == 200 else {}
check("ticket-agent 服務帳號：等級 green", c.get("clearance") == "green", c.get("clearance"))
check("ticket-agent 服務帳號：scope 有 tickets.read、無 tickets.write",
      "tickets.read" in c.get("scope", "").split() and "tickets.write" not in c.get("scope", "").split(), c.get("scope"))
check("ticket-agent 服務帳號：aud 含 internal-api", "internal-api" in auds(c), auds(c))

for u in ("u-green", "u-red"):
    if u not in subs:
        continue
    s, t = token({"grant_type": EXCHANGE, "client_id": "ticket-agent", "client_secret": ENV["DEMO_AGENT_SECRET"],
                  "subject_token": subs[u][1], "subject_token_type": ACCESS,
                  "audience": "internal-api", "scope": "internal-api-aud"})
    c = claims(t["access_token"]) if s == 200 else {}
    check(f"代換 {u}：成功", s == 200, t)
    check(f"代換 {u}：sub 沿用使用者、等級沿用使用者",
          c.get("sub") == subs[u][0] and c.get("clearance") == EXPECT[u][1], (c.get("sub"), c.get("clearance")))
    check(f"代換 {u}：aud 為 internal-api、azp 為 ticket-agent",
          "internal-api" in auds(c) and c.get("azp") == "ticket-agent", (auds(c), c.get("azp")))

s, t = token({"grant_type": EXCHANGE, "client_id": "ticket-agent", "client_secret": ENV["DEMO_AGENT_SECRET"],
              "subject_token_type": ACCESS, "audience": "internal-api", "scope": "internal-api-aud"})
check("不帶使用者 token 的代換被拒", s == 400, (s, t))

s, t = user_token("u-mfa")
# 設定 TOTP 前：回「帳號未完成設定」；T7 手動設定後：只給密碼不夠，回 invalid_grant（缺一次性驗證碼）
desc = t.get("error_description")
check("u-mfa 只給密碼取不到 token（設定前：帳號未完成設定；設定後：缺驗證碼）",
      s != 200 and desc in ("Account is not fully set up", "Invalid user credentials"), (s, t))
print(f"     u-mfa 狀態：{'尚未設定 TOTP' if desc == 'Account is not fully set up' else '已設定 TOTP'}")

realm_json = (HERE / "demo-realm.json").read_text()
leaked = [k for k, v in ENV.items() if v and v in realm_json]
check("demo-realm.json 不含任何 secret 實值", not leaked, leaked)

print(f"\n{'全部通過' if not failures else f'{len(failures)} 項未通過'}")
sys.exit(1 if failures else 0)

"""共用設定：測試模式、獨立的 var 目錄、Keycloak token、Gateway 與內部 API 的 TestClient。

需要 Keycloak 在跑（docker compose up -d）。環境變數必須在 import gateway 之前設好。
"""
import base64
import json
import os
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["GATEWAY_TEST_MODE"] = "1"
os.environ.setdefault("GATEWAY_VAR", tempfile.mkdtemp(prefix="gw-test-"))
os.environ["GATEWAY_MODEL"] = "echo"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ENV = dict(l.strip().split("=", 1) for l in (ROOT / ".env.local").read_text().splitlines() if "=" in l)
KC = "http://127.0.0.1:8080/realms"
TOKEN_URL = f"{KC}/demo/protocol/openid-connect/token"
EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS = "urn:ietf:params:oauth:token-type:access_token"


def kc_post(url, data):
    req = urllib.request.Request(url, urllib.parse.urlencode(data).encode())
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
    except urllib.error.URLError as e:
        pytest.exit(f"連不到 Keycloak（先 docker compose up -d）：{e}", returncode=2)


def user_token(username, client="portal"):
    s, t = kc_post(TOKEN_URL, {"grant_type": "password", "client_id": client,
                               "client_secret": ENV["DEMO_PORTAL_SECRET"],
                               "username": username, "password": ENV["DEMO_USER_PW"]})
    assert s == 200, t
    return t["access_token"]


def agent_token():
    s, t = kc_post(TOKEN_URL, {"grant_type": "client_credentials", "client_id": "ticket-agent",
                               "client_secret": ENV["DEMO_AGENT_SECRET"]})
    assert s == 200, t
    return t["access_token"]


def exchange(subject_token: str | None):
    data = {"grant_type": EXCHANGE, "client_id": "ticket-agent", "client_secret": ENV["DEMO_AGENT_SECRET"],
            "subject_token_type": ACCESS, "audience": "internal-api", "scope": "internal-api-aud"}
    if subject_token:
        data["subject_token"] = subject_token
    return kc_post(TOKEN_URL, data)


def b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def jsonl_since(path: Path, offset: int) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        f.seek(offset)
        return [json.loads(l) for l in f if l.strip()]


def size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


@pytest.fixture(scope="session")
def tokens():
    return {u: user_token(u) for u in ("u-green", "u-yellow", "u-red", "u-auditor")}


@pytest.fixture(scope="session")
def gw_app():
    from gateway import app as gw
    return gw


@pytest.fixture(scope="session")
def gw(gw_app):
    return TestClient(gw_app.app)


@pytest.fixture(scope="session")
def api():
    from internal_api import app as ia
    return TestClient(ia.app)


def bearer(tok):
    return {"authorization": f"Bearer {tok}"} if tok else {}


def chat(gw, tok, project, level, prompt="測試", **headers):
    return gw.post("/v1/chat", json={"project": project, "level": level, "prompt": prompt},
                   headers={**bearer(tok), **{k.replace("_", "-"): v for k, v in headers.items()}})


def prompts():
    return [json.loads(l) for l in (ROOT / "tests" / "prompts-pii.jsonl").read_text(encoding="utf-8").splitlines()]

"""G11 端到端：3 則提問經 Gateway（真的 uvicorn 服務）送進地端 qwen3.5:9b，拿回回答。

可行性展示，不影響 G1–G10 判定。門檻：3/3 成功，模型端紀錄無原始個資。
用法：../.venv-gateway/bin/python e2e.py   （需 Keycloak 與 Ollama 在跑）
輸出：results/e2e-<日期-時分>.md（每次另存，不覆寫）
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from gateway.deid import core  # noqa: E402

ENV = dict(l.strip().split("=", 1) for l in (ROOT / ".env.local").read_text().splitlines() if "=" in l)
PICK = ["P09", "P27", "P36"]  # 手機、統編、混合（身分證＋手機＋email）
PORT = 8095


def post(url, data=None, js=None, token=None):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    if js is not None:
        body, h["Content-Type"] = json.dumps(js).encode(), "application/json"
    else:
        body = urllib.parse.urlencode(data).encode()
    with urllib.request.urlopen(urllib.request.Request(url, body, h), timeout=300) as r:
        return json.loads(r.read())


rows = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "tests/prompts-pii.jsonl").read_text(encoding="utf-8").splitlines()}
var = Path(tempfile.mkdtemp(prefix="gw-e2e-"))
env = {**os.environ, "GATEWAY_MODEL": "ollama", "GATEWAY_VAR": str(var)}
env.pop("GATEWAY_DISABLE", None)
env.pop("GATEWAY_TEST_MODE", None)
srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "gateway.app:app", "--host", "127.0.0.1", "--port", str(PORT)],
                       cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/docs", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    tok = post("http://127.0.0.1:8080/realms/demo/protocol/openid-connect/token",
               {"grant_type": "password", "client_id": "portal", "client_secret": ENV["DEMO_PORTAL_SECRET"],
                "username": "u-yellow", "password": ENV["DEMO_USER_PW"]})["access_token"]
    results = []
    for pid in PICK:
        r = rows[pid]
        t0 = time.time()
        try:
            res = post(f"http://127.0.0.1:{PORT}/v1/chat", js={k: r[k] for k in ("project", "level", "prompt")}, token=tok)
            results.append({"id": pid, "ok": True, "secs": round(time.time() - t0, 1), "prompt": r["prompt"],
                            "pii": r["pii"], "answer": res["answer"], "masked": res["pii_masked"]})
        except Exception as e:
            results.append({"id": pid, "ok": False, "error": repr(e), "prompt": r["prompt"], "pii": r["pii"]})
finally:
    srv.terminate()
    srv.wait(10)

received = [json.loads(l)["received"] for l in (var / "model-received.jsonl").read_text(encoding="utf-8").splitlines()]
leaks = [p for r, m in zip(results, received) for p in r["pii"] if p in m or core(p) in core(m)]
ok = sum(r["ok"] for r in results)
passed = ok == len(PICK) and not leaks and len(received) == len(PICK)

lines = [f"# G11 端到端（{time.strftime('%Y-%m-%d %H:%M')}，地端 qwen3.5:9b，think=false）", "",
         f"判定：{'達成' if passed else '未達'}（成功 {ok}/{len(PICK)}；模型端原始個資 {len(leaks)} 次）", ""]
for r, m in zip(results, received + [""] * len(results)):
    lines += [f"## {r['id']}", f"- 使用者提問：{r['prompt']}", f"- 模型端收到：{m}",
              f"- 使用者收到（已還原）：{r.get('answer', r.get('error'))}", f"- 耗時：{r.get('secs', '—')} 秒", ""]
out = ROOT / "results" / f"e2e-{time.strftime('%Y%m%d-%H%M')}.md"
out.parent.mkdir(exist_ok=True)
out.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
sys.exit(0 if passed else 1)

"""跑 G1–G10 門檻與反向檢核，輸出門檻表（stdout＋var/gates.md）。

每條門檻：正常跑必須全過（exit 0）；反向檢核關掉對應檢查重跑，必須轉紅（exit 1，測試失敗）。
exit 2 以上代表測試本身出錯（例如連不到 Keycloak），不算轉紅。
用法：../.venv-gateway/bin/python run_gates.py
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
T = "tests/"
GATES = [
    ("G1", "認證：6 種無效 token 回 401", "test_g01_authn_reject.py",
     [("停用 auth", {"GATEWAY_DISABLE": "auth"}, None)]),
    ("G2", "認證：3 個合法 token 通過", "test_g02_authn_accept.py",
     [("issuer 指向不存在的 realm", {"KC_ISSUER": "http://127.0.0.1:8080/realms/no-such-realm"}, None)]),
    ("G3", "授權：18 格與預期表一致", "test_g03_abac.py",
     [("停用 policy", {"GATEWAY_DISABLE": "policy"}, None)]),
    ("G4", "去識別化：模型端無原始個資", "test_g04_deid_model.py",
     [("停用 deid", {"GATEWAY_DISABLE": "deid"}, None)]),
    ("G5", "去識別化：代碼 100% 還原", "test_g05_deid_restore.py",
     [("停用 restore", {"GATEWAY_DISABLE": "restore"}, None)]),
    ("G5b", "（T6 後新增）括號變形仍還原、編造代碼計入", "test_g05b_restore_variants.py",
     [("停用 restore_loose", {"GATEWAY_DISABLE": "restore_loose"}, None)]),
    ("G6", "稽核：無原始個資、每請求一筆", "test_g06_audit_log.py",
     [("停用 audit_redact", {"GATEWAY_DISABLE": "audit_redact"}, None)]),
    ("G7", "稽核：只有稽核員能查、查詢留紀錄", "test_g07_audit_access.py",
     [("停用 audit_rbac", {"GATEWAY_DISABLE": "audit_rbac"}, None)]),
    ("G8", "用量：正常 0 警示、突增 ≥1", "test_g08_usage.py",
     [("停用 usage", {"GATEWAY_DISABLE": "usage"}, None)]),
    ("G9", "Agent 服務帳號：只能讀綠燈", "test_g09_agent_service.py",
     [("停用 policy（讀取）", {"GATEWAY_DISABLE": "policy"}, "read"),
      ("停用 scope（寫入）", {"GATEWAY_DISABLE": "scope"}, "write")]),
    ("G10", "Agent 代表使用者：不比使用者大", "test_g10_agent_obo.py",
     [("停用 policy（綠燈使用者讀紅）", {"GATEWAY_DISABLE": "policy"}, "green_user")]),
]


def pytest(file, extra_env=None, k=None):
    env = {**os.environ, "GATEWAY_VAR": tempfile.mkdtemp(prefix="gw-gate-"), **(extra_env or {})}
    if "GATEWAY_DISABLE" not in (extra_env or {}):
        env.pop("GATEWAY_DISABLE", None)  # 正常跑不得帶旗標
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", T + file] + (["-k", k] if k else [])
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    tail = (p.stdout.strip().splitlines() or [""])[-1]
    return p.returncode, tail


rows, all_ok, t0 = [], True, time.time()
for gid, desc, file, reverses in GATES:
    code, tail = pytest(file)
    passed = code == 0
    rev_notes, rev_ok = [], True
    for label, env, k in reverses:
        rcode, rtail = pytest(file, env, k)
        turned_red = rcode == 1
        rev_ok &= turned_red
        rev_notes.append(f"{label}：{'轉紅' if turned_red else f'未轉紅（exit {rcode}）'}")
    verdict = "達成" if passed and rev_ok else "未達"
    all_ok &= verdict == "達成"
    rows.append((gid, desc, f"{'全過' if passed else '有失敗'}（{tail}）", "；".join(rev_notes), verdict))
    print(f"{gid} {verdict}  正常：{tail}  反向：{'；'.join(rev_notes)}", flush=True)

md = ["| # | 門檻 | 正常跑 | 反向檢核 | 判定 |", "|---|---|---|---|---|"]
md += [f"| {' | '.join(r)} |" for r in rows]
md.append(f"\n整體：{'G1–G10（含 G5b）全部達成' if all_ok else '有門檻未達'}（{time.strftime('%Y-%m-%d %H:%M')}，耗時 {time.time() - t0:.0f} 秒）")
out = ROOT / "var" / "gates.md"
out.parent.mkdir(exist_ok=True)
out.write_text("\n".join(md) + "\n", encoding="utf-8")
print("\n" + "\n".join(md))
sys.exit(0 if all_ok else 1)

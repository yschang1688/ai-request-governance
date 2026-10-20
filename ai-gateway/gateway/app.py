"""AI Gateway：認證 → 授權 → 用量 → 去識別化 → 模型 → 還原 → 稽核。

每一步的拒絕也寫稽核（decision=deny），所以稽核筆數＝請求數。
啟動：uvicorn gateway.app:app --host 127.0.0.1 --port 8090
"""
import uuid

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import auth, config, deid, flags, models, policy
from .audit import AuditLog, is_auditor
from .usage import UsageMonitor

AUDIENCE = "ai-gateway"
flags.disabled()  # 非測試模式帶停用旗標 → 啟動即失敗

app = FastAPI(title="AI Gateway PoC")
audit = AuditLog(config.VAR / "gateway-audit.jsonl")
model = models.build(config.VAR / "model-received.jsonl")
usage = UsageMonitor()


class ChatIn(BaseModel):
    project: str
    level: str
    prompt: str


def deny(status: int, subject: dict | None, action: str, reason: str, rid: str):
    audit.write(subject=subject, action=action, decision="deny", reason=reason, request_id=rid)
    return JSONResponse({"error": reason, "request_id": rid}, status_code=status)


@app.post("/v1/chat")
def chat(body: ChatIn, request: Request, authorization: str | None = Header(None),
         x_test_clock: float | None = Header(None)):
    rid = uuid.uuid4().hex
    try:
        subject = auth.verify(authorization, AUDIENCE)
    except auth.AuthError as e:
        return deny(401, None, "chat", str(e), rid)

    ok, reason = policy.allow(subject, body.level, body.project, "read")
    if not ok:
        return deny(403, subject, "chat", reason, rid)

    # 壓縮時間重播只在測試模式接受 X-Test-Clock
    alert = usage.record(subject.get("sub", "?"), x_test_clock if config.TEST_MODE else None)

    vault = deid.Vault()
    masked_prompt, kinds = deid.mask(body.prompt, vault)
    masked_answer = model.complete(masked_prompt)
    answer, unknown = deid.restore(masked_answer, vault)

    audit.write(subject=subject, action="chat", decision="allow", reason=reason, request_id=rid,
                masked={"prompt": masked_prompt, "answer": masked_answer, "pii_kinds": kinds,
                        "unknown_codes": unknown, "usage_alert": bool(alert)},
                raw={"prompt": body.prompt, "answer": answer})
    return {"request_id": rid, "answer": answer, "pii_masked": len(kinds), "usage_alert": alert}


@app.get("/audit")
def read_audit(limit: int = 200, authorization: str | None = Header(None)):
    rid = uuid.uuid4().hex
    try:
        subject = auth.verify(authorization, AUDIENCE)
    except auth.AuthError as e:
        return deny(401, None, "audit.read", str(e), rid)
    if not is_auditor(subject):
        return deny(403, subject, "audit.read", "非稽核員", rid)
    entries = audit.read(limit)
    audit.write(subject=subject, action="audit.read", decision="allow", reason=f"讀取 {len(entries)} 筆",
                request_id=rid)
    return {"request_id": rid, "entries": entries}


@app.get("/usage/alerts")
def usage_alerts(authorization: str | None = Header(None)):
    rid = uuid.uuid4().hex
    try:
        subject = auth.verify(authorization, AUDIENCE)
    except auth.AuthError as e:
        return deny(401, None, "usage.read", str(e), rid)
    if not is_auditor(subject):
        return deny(403, subject, "usage.read", "非稽核員", rid)
    audit.write(subject=subject, action="usage.read", decision="allow", reason="讀取用量警示", request_id=rid)
    return {"request_id": rid, "alerts": usage.alerts}

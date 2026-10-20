"""內部 API（合成工單）：Agent 直接呼叫的對象。認證、授權、稽核與 Gateway 共用同一套模組。

token 的 aud 必須是 internal-api。服務帳號只看等級；代表使用者時沿用使用者的等級與專案。
啟動：uvicorn internal_api.app:app --host 127.0.0.1 --port 8091
"""
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from gateway import auth, config, flags, policy
from gateway.audit import AuditLog

AUDIENCE = "internal-api"
flags.disabled()

app = FastAPI(title="Internal API PoC")
audit = AuditLog(config.VAR / "internal-audit.jsonl")
TICKETS = {t["id"]: t for t in json.loads(Path(__file__).with_name("tickets.json").read_text(encoding="utf-8"))}


class CommentIn(BaseModel):
    text: str


def guarded(ticket_id: str, authorization: str | None, action: str):
    rid = uuid.uuid4().hex
    try:
        subject = auth.verify(authorization, AUDIENCE)
    except auth.AuthError as e:
        audit.write(subject=None, action=action, decision="deny", reason=str(e), request_id=rid)
        return None, None, JSONResponse({"error": str(e)}, status_code=401)
    t = TICKETS.get(ticket_id)
    if t is None:
        return None, None, JSONResponse({"error": "查無工單"}, status_code=404)
    ok, reason = policy.allow(subject, t["level"], t["project"], "write" if action == "comment" else "read")
    audit.write(subject=subject, action=f"{action}:{ticket_id}", decision="allow" if ok else "deny",
                reason=reason, request_id=rid)
    if not ok:
        return None, None, JSONResponse({"error": reason}, status_code=403)
    return subject, t, None


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, authorization: str | None = Header(None)):
    _, t, err = guarded(ticket_id, authorization, "read")
    return err or t


@app.post("/tickets/{ticket_id}/comments")
def add_comment(ticket_id: str, body: CommentIn, authorization: str | None = Header(None)):
    _, t, err = guarded(ticket_id, authorization, "comment")
    return err or {"ok": True, "ticket": t["id"]}

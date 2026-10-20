"""稽核：誰、何時、做了什麼、決策與原因。JSONL 追加寫入，只存遮罩後內容。

查日誌限 auditor 角色，而且查詢本身也寫一筆，讓「看日誌的人」同樣被記錄。
"""
import json
import threading
import time
import uuid
from pathlib import Path

from . import flags

AUDITOR = "auditor"


class AuditLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, *, subject: dict | None, action: str, decision: str, reason: str,
              masked: dict | None = None, raw: dict | None = None, request_id: str | None = None):
        subject = subject or {}
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "request_id": request_id or uuid.uuid4().hex,
            "sub": subject.get("sub"), "user": subject.get("preferred_username"), "azp": subject.get("azp"),
            "action": action, "decision": decision, "reason": reason,
            # 反向檢核 audit_redact：改存原文，證明 G6 真的會抓到
            "content": (raw if flags.off("audit_redact") else masked) or {},
        }
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def read(self, limit: int = 200) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(l) for l in lines[-limit:]]


def is_auditor(subject: dict) -> bool:
    if flags.off("audit_rbac"):
        return True
    return AUDITOR in (subject.get("realm_access") or {}).get("roles", [])

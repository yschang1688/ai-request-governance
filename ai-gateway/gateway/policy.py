"""授權（你能做什麼）：ABAC，依 token 裡的等級、專案、scope 判斷。純函式，規則在 policy.yaml。"""
from pathlib import Path

import yaml

from . import flags

RULES = yaml.safe_load((Path(__file__).with_name("policy.yaml")).read_text(encoding="utf-8"))
RANK = {lvl: i for i, lvl in enumerate(RULES["levels"])}


def is_service_account(subject: dict) -> bool:
    return str(subject.get("preferred_username", "")).startswith(RULES["service_account_prefix"])


def allow(subject: dict, level: str, project: str, action: str = "read") -> tuple[bool, str]:
    if level not in RANK:
        return False, f"未知的資料等級：{level}"
    if action == "write" and not flags.off("scope"):
        if RULES["write_scope"] not in str(subject.get("scope", "")).split():
            return False, "缺少寫入 scope"
    if flags.off("policy"):
        return True, "授權檢查已停用（反向檢核）"
    clearance = subject.get("clearance")
    if RANK.get(clearance, -1) < RANK[level]:
        return False, f"等級不足：{clearance} < {level}"
    if not is_service_account(subject) and project not in (subject.get("projects") or []):
        return False, f"不屬於專案 {project}"
    return True, "允許"

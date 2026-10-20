"""反向檢核用的停用旗標。

GATEWAY_DISABLE=auth,policy,... 會關掉對應檢查，只給 tests/test_reverse.py 證明測試真的測到東西。
非測試模式（GATEWAY_TEST_MODE 不是 1）偵測到旗標就拒絕啟動，避免誤開到正式環境。
"""
import os

from . import config

KNOWN = {"auth", "policy", "scope", "deid", "restore", "restore_loose", "audit_redact", "audit_rbac", "usage"}


def disabled() -> frozenset:
    raw = os.environ.get("GATEWAY_DISABLE", "")
    flags = frozenset(f.strip() for f in raw.split(",") if f.strip())
    unknown = flags - KNOWN
    if unknown:
        raise RuntimeError(f"未知的停用旗標：{sorted(unknown)}")
    if flags and not config.TEST_MODE:
        raise RuntimeError("GATEWAY_DISABLE 只能在 GATEWAY_TEST_MODE=1 時使用")
    return flags


def off(name: str) -> bool:
    return name in disabled()

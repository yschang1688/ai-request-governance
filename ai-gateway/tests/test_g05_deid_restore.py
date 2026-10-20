"""G5 去識別化：回應中模型引用到的代碼 100% 還原。反向檢核：停用 restore。

EchoModel 會原樣引用每一個代碼，所以每個原始值都應該出現在使用者收到的回應裡，且不殘留代碼。
"""
from conftest import chat, prompts


def test_g5_codes_restored(gw, tokens):
    bad = {}
    for r in prompts():
        res = chat(gw, tokens[r["user"]], r["project"], r["level"], r["prompt"])
        assert res.status_code == 200
        answer = res.json()["answer"]
        missing = [p for p in r["pii"] if p not in answer]
        if missing or "⟨PII_" in answer:
            bad[r["id"]] = {"missing": missing, "answer": answer}
    assert not bad, f"{len(bad)} 則未完整還原：{bad}"

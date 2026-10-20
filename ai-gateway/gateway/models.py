"""模型端。兩種都把「實際收到的內容」寫進模型端紀錄，G4 掃這份紀錄確認沒有原始個資。

EchoModel：測試用，回聲收到的內容，結果可重現、不必載入 9B。
OllamaModel：地端 qwen3.5:9b（G11 端到端）。
"""
import json
import threading
from pathlib import Path

import httpx

from . import config


class _Logged:
    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _log(self, prompt: str):
        with self._lock, self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"received": prompt}, ensure_ascii=False) + "\n")


class EchoModel(_Logged):
    name = "echo"

    def complete(self, prompt: str) -> str:
        self._log(prompt)
        return f"已收到：{prompt}"


class OllamaModel(_Logged):
    name = "ollama"
    SYSTEM = ("你是公司內部助理。提問中的 ⟨PII_n⟩ 是去識別化代碼，代表一筆個資；"
              "回答需要提到時，請原樣寫出代碼，不要猜原值。用繁體中文、三句以內回答。")

    def complete(self, prompt: str) -> str:
        self._log(prompt)
        r = httpx.post(config.OLLAMA_URL, timeout=180, json={
            "model": config.OLLAMA_MODEL, "stream": False, "think": False,
            "messages": [{"role": "system", "content": self.SYSTEM}, {"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["message"]["content"]


def build(log_path: Path):
    return OllamaModel(log_path) if config.MODEL == "ollama" else EchoModel(log_path)

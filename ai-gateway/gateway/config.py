"""設定：全部從環境變數讀，預設值對應本機 PoC（Keycloak 在 127.0.0.1:8080）。"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAR = Path(os.environ.get("GATEWAY_VAR", ROOT / "var"))

ISSUER = os.environ.get("KC_ISSUER", "http://127.0.0.1:8080/realms/demo")
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"

# 用量監控：以 60 秒為一格，近 BASELINE_BUCKETS 格的平均當基線，當格超過 K 倍且至少 MIN_COUNT 次就警示
USAGE_BUCKET_S = int(os.environ.get("USAGE_BUCKET_S", "60"))
USAGE_BASELINE_BUCKETS = int(os.environ.get("USAGE_BASELINE_BUCKETS", "10"))
USAGE_K = float(os.environ.get("USAGE_K", "3"))
USAGE_MIN_COUNT = int(os.environ.get("USAGE_MIN_COUNT", "10"))

MODEL = os.environ.get("GATEWAY_MODEL", "echo")  # echo｜ollama
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")

TEST_MODE = os.environ.get("GATEWAY_TEST_MODE") == "1"

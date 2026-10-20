"""認證（你是誰）：驗 Keycloak 簽發的 access token。

只接受 RS256，以 IdP 的 JWKS 驗簽；必須有 exp、iss、aud，且 iss、aud 要相符。不設寬限秒數。
"""
import jwt

from . import config, flags

_jwks = jwt.PyJWKClient(config.JWKS_URL, cache_keys=True, lifespan=300)


class AuthError(Exception):
    pass


def bearer(header: str | None) -> str:
    if not header or not header.startswith("Bearer "):
        raise AuthError("缺少 Bearer token")
    return header[len("Bearer "):].strip()


def verify(header: str | None, audience: str) -> dict:
    if flags.off("auth"):
        # 反向檢核：不驗任何東西；有 token 就讀宣告，沒有就當匿名
        try:
            return jwt.decode(bearer(header), options={"verify_signature": False})
        except Exception:
            return {"sub": "anonymous"}
    token = bearer(header)
    try:
        key = _jwks.get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["RS256"], audience=audience, issuer=config.ISSUER,
                          options={"require": ["exp", "iss", "aud", "sub"]})
    except jwt.PyJWTError as e:
        raise AuthError(f"token 無效：{type(e).__name__}") from e

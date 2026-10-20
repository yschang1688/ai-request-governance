"""產生 Keycloak realm 匯入檔 demo-realm.json。

secret 與密碼一律寫成 ${DEMO_*} 佔位字串，由 Keycloak 匯入時從容器環境變數（.env.local）代入，
所以 repo 裡的 JSON 不含任何 secret。改角色或 client 時改這支，再重跑：python3 build_realm.py
"""
import json
from pathlib import Path

PW = "${DEMO_USER_PW}"


def aud_mapper(name, target):
    return {"name": name, "protocol": "openid-connect", "protocolMapper": "oidc-audience-mapper",
            "config": {"included.client.audience": target, "access.token.claim": "true",
                       "introspection.token.claim": "true"}}


def attr_mapper(attr, multivalued=False):
    return {"name": attr, "protocol": "openid-connect", "protocolMapper": "oidc-usermodel-attribute-mapper",
            "config": {"user.attribute": attr, "claim.name": attr, "jsonType.label": "String",
                       "multivalued": str(multivalued).lower(), "access.token.claim": "true",
                       "introspection.token.claim": "true", "id.token.claim": "false",
                       "userinfo.token.claim": "false"}}


def user(name, dept, clearance, projects, roles=(), required=()):
    return {"username": name, "enabled": True, "email": f"{name}@example.test", "emailVerified": True,
            "firstName": name, "lastName": "demo",
            "attributes": {"dept": [dept], "clearance": [clearance], "projects": list(projects)},
            "realmRoles": ["default-roles-demo", *roles], "requiredActions": list(required),
            "credentials": [{"type": "password", "value": PW, "temporary": False}]}


def oauth_scope(name):
    # 純 OAuth scope：出現在 token 的 scope 欄位，不帶 mapper
    return {"name": name, "protocol": "openid-connect",
            "attributes": {"include.in.token.scope": "true", "display.on.consent.screen": "false"}}


realm = {
    "realm": "demo", "enabled": True,
    "accessTokenLifespan": 300,
    # 自訂屬性（部門、等級、專案）不在預設 user profile 裡，要開 unmanaged attributes 才會保存
    "attributes": {"unmanagedAttributePolicy": "ENABLED"},
    "roles": {"realm": [{"name": "auditor", "description": "可查稽核日誌"}]},
    # Keycloak 自動建立的 client（account-console 等）預設掛這兩個 scope
    "defaultDefaultClientScopes": ["basic", "roles"],
    "clientScopes": [
        {"name": "org-attrs", "protocol": "openid-connect",
         "attributes": {"include.in.token.scope": "false"},
         "protocolMappers": [attr_mapper("dept"), attr_mapper("clearance"), attr_mapper("projects", True),
                             {"name": "username", "protocol": "openid-connect",
                              "protocolMapper": "oidc-usermodel-attribute-mapper",
                              "config": {"user.attribute": "username", "claim.name": "preferred_username",
                                         "jsonType.label": "String", "access.token.claim": "true",
                                         "introspection.token.claim": "true"}}]},
        {"name": "internal-api-aud", "protocol": "openid-connect",
         "attributes": {"include.in.token.scope": "true"},
         "protocolMappers": [aud_mapper("aud-internal-api", "internal-api")]},
        # Keycloak 25 起 sub 由內建的 basic scope 產生；自己定義 clientScopes 時要手動補
        {"name": "basic", "protocol": "openid-connect", "attributes": {"include.in.token.scope": "false"},
         "protocolMappers": [{"name": "sub", "protocol": "openid-connect", "protocolMapper": "oidc-sub-mapper",
                              "config": {"access.token.claim": "true", "introspection.token.claim": "true"}}]},
        # 自己定義 clientScopes 時 Keycloak 不會建內建的 roles scope，所以手動補：把 realm role 放進 token
        {"name": "roles", "protocol": "openid-connect", "attributes": {"include.in.token.scope": "false"},
         "protocolMappers": [{"name": "realm roles", "protocol": "openid-connect",
                              "protocolMapper": "oidc-usermodel-realm-role-mapper",
                              "config": {"claim.name": "realm_access.roles", "jsonType.label": "String",
                                         "multivalued": "true", "access.token.claim": "true",
                                         "introspection.token.claim": "true"}},
                             # 帳號管理頁（account console）呼叫帳號 API 需要 client 角色與 aud=account
                             {"name": "client roles", "protocol": "openid-connect",
                              "protocolMapper": "oidc-usermodel-client-role-mapper",
                              "config": {"claim.name": "resource_access.${client_id}.roles",
                                         "jsonType.label": "String", "multivalued": "true",
                                         "access.token.claim": "true", "introspection.token.claim": "true"}},
                             {"name": "audience resolve", "protocol": "openid-connect",
                              "protocolMapper": "oidc-audience-resolve-mapper",
                              "config": {"access.token.claim": "true", "introspection.token.claim": "true"}}]},
        oauth_scope("tickets.read"),
        oauth_scope("tickets.write"),
    ],
    "clients": [
        # 使用者登入用。token 的 aud 帶 ai-gateway（Gateway 只收這個）與 ticket-agent（Agent 才能代換）
        {"clientId": "portal", "secret": "${DEMO_PORTAL_SECRET}", "publicClient": False,
         "directAccessGrantsEnabled": True, "standardFlowEnabled": True,
         "redirectUris": ["http://127.0.0.1:8090/*"],
         "defaultClientScopes": ["basic", "org-attrs", "roles", "tickets.read"],
         "protocolMappers": [aud_mapper("aud-gateway", "ai-gateway"), aud_mapper("aud-agent", "ticket-agent")]},
        # G1 用：aud 不含 ai-gateway
        {"clientId": "portal-noaud", "secret": "${DEMO_PORTAL_SECRET}", "publicClient": False,
         "directAccessGrantsEnabled": True, "standardFlowEnabled": False,
         "defaultClientScopes": ["basic", "org-attrs", "roles"]},
        # G1 用：token 3 秒就過期
        {"clientId": "portal-short", "secret": "${DEMO_PORTAL_SECRET}", "publicClient": False,
         "directAccessGrantsEnabled": True, "standardFlowEnabled": False,
         "attributes": {"access.token.lifespan": "3"},
         "defaultClientScopes": ["basic", "org-attrs", "roles"],
         "protocolMappers": [aud_mapper("aud-gateway", "ai-gateway")]},
        # Agent：服務帳號（Client Credentials）＋代表使用者（Standard Token Exchange）
        {"clientId": "ticket-agent", "secret": "${DEMO_AGENT_SECRET}", "publicClient": False,
         "serviceAccountsEnabled": True, "standardFlowEnabled": False,
         "attributes": {"standard.token.exchange.enabled": "true"},
         "defaultClientScopes": ["basic", "org-attrs", "roles", "tickets.read"],
         "optionalClientScopes": ["internal-api-aud"],
         "protocolMappers": [aud_mapper("aud-internal-api-sa", "internal-api")]},
        {"clientId": "ai-gateway", "secret": "${DEMO_GATEWAY_SECRET}", "publicClient": False,
         "standardFlowEnabled": False},
        {"clientId": "internal-api", "secret": "${DEMO_API_SECRET}", "publicClient": False,
         "standardFlowEnabled": False},
    ],
    "users": [
        user("u-green", "製造", "green", ["P-A"]),
        user("u-yellow", "品保", "yellow", ["P-A", "P-B"]),
        user("u-red", "研發", "red", ["P-B"]),
        user("u-auditor", "資安", "none", [], roles=["auditor"]),
        # T7 MFA 手動示範專用：首次登入必須設定 TOTP（不參與自動化測試）
        user("u-mfa", "研發", "green", ["P-A"], required=["CONFIGURE_TOTP"]),
        {"username": "service-account-ticket-agent", "enabled": True, "serviceAccountClientId": "ticket-agent",
         "attributes": {"dept": ["系統"], "clearance": ["green"], "projects": []},
         "realmRoles": ["default-roles-demo"]},
    ],
}

out = Path(__file__).with_name("demo-realm.json")
out.write_text(json.dumps(realm, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out}")

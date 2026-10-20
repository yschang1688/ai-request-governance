# AI Gateway PoC。先 docker compose up -d（Keycloak），再開兩個服務。
PY := ../.venv-gateway/bin/python

.PHONY: kc gateway api check test
kc:
	docker compose up -d
gateway:
	$(PY) -m uvicorn gateway.app:app --host 127.0.0.1 --port 8090
api:
	$(PY) -m uvicorn internal_api.app:app --host 127.0.0.1 --port 8091
check:
	$(PY) -I realm/check_realm.py
test:
	$(PY) -m pytest -q tests

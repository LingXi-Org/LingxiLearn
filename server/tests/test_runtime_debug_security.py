from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from lingxilearn.api.routes import _redact_runtime_debug, _require_runtime_debug


def test_runtime_debug_payloads_redact_secret_keys_recursively() -> None:
    payload = {
        "authorization": "Bearer private",
        "nested": {
            "api_key": "key",
            "systemPrompt": "hidden instructions",
            "safe": "visible",
        },
        "items": [{"refresh_token": "token"}, {"reason": "visible"}],
    }

    assert _redact_runtime_debug(payload) == {
        "authorization": "[REDACTED]",
        "nested": {
            "api_key": "[REDACTED]",
            "systemPrompt": "[REDACTED]",
            "safe": "visible",
        },
        "items": [{"refresh_token": "[REDACTED]"}, {"reason": "visible"}],
    }


def test_runtime_debug_capability_is_disabled_by_default() -> None:
    services = SimpleNamespace(settings=SimpleNamespace(runtime_debug_enabled=False))

    with pytest.raises(HTTPException) as raised:
        _require_runtime_debug(services)

    assert raised.value.status_code == 404


def test_runtime_debug_rejects_an_ordinary_production_principal() -> None:
    services = SimpleNamespace(
        settings=SimpleNamespace(runtime_debug_enabled=True, insecure_dev_auth=False)
    )
    principal = SimpleNamespace(permissions=frozenset(), roles=frozenset())

    with pytest.raises(HTTPException) as raised:
        _require_runtime_debug(services, principal)

    assert raised.value.status_code == 404

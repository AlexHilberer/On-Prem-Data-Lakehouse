import base64
import json
import os
import threading
import time

import requests

_lock = threading.Lock()
_cached = {"token": None, "expires_at": 0.0}


def _expiry(token: str) -> float:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])


def get_token() -> str:
    """Return the user's access token, refreshed through the hub token broker when close to expiry."""
    with _lock:
        if _cached["token"] and _cached["expires_at"] - time.time() > 60:
            return _cached["token"]
        response = requests.get(
            os.environ["LAKEHOUSE_TOKEN_URL"],
            headers={"Authorization": f"token {os.environ['JUPYTERHUB_API_TOKEN']}"},
            timeout=15,
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        _cached.update(token=token, expires_at=_expiry(token))
        return token

import asyncio
import json
import os
import time
from urllib.parse import urlparse

import requests
from jupyterhub.services.auth import HubAuthenticated
from tornado import ioloop, web

TOKEN_URL = "https://authentik.lakehouse.local/application/o/token/"
HUB_API = os.environ["JUPYTERHUB_API_URL"]
HUB_HEADERS = {"Authorization": f"token {os.environ['JUPYTERHUB_API_TOKEN']}"}
REFRESH_MARGIN_SECONDS = 120

_lock = asyncio.Lock()
_cache = {}


def load_auth_state(username: str) -> dict:
    response = requests.get(f"{HUB_API}/users/{username}", headers=HUB_HEADERS, timeout=15)
    response.raise_for_status()
    return response.json().get("auth_state") or {}


def store_auth_state(username: str, auth_state: dict) -> None:
    response = requests.patch(
        f"{HUB_API}/users/{username}",
        headers=HUB_HEADERS,
        json={"auth_state": auth_state},
        timeout=15,
    )
    response.raise_for_status()


def refresh_access_token(refresh_token: str) -> dict:
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": "lakehouse",
            "client_secret": os.environ["OIDC_CLIENT_SECRET"],
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    if not response.ok:
        raise web.HTTPError(502, f"authentik refresh failed: {response.text[:300]}")
    return response.json()


def fresh_access_token(username: str) -> str:
    cached = _cache.get(username)
    if (
        cached
        and not cached["unsaved"]
        and cached["expires_at"] - time.time() > REFRESH_MARGIN_SECONDS
    ):
        return cached["access_token"]
    auth_state = load_auth_state(username)
    # A rotated token the hub could not store is newer than the hub's copy.
    refresh_token = cached["refresh_token"] if cached else auth_state.get("refresh_token")
    if not refresh_token:
        raise web.HTTPError(409, "No refresh token stored; log in to the hub again.")
    tokens = refresh_access_token(refresh_token)
    # authentik rotates refresh tokens, so the new one must replace the stored one.
    new_refresh_token = tokens.get("refresh_token", refresh_token)
    auth_state.update(access_token=tokens["access_token"], refresh_token=new_refresh_token)
    saved = False
    for _ in range(2):
        try:
            store_auth_state(username, auth_state)
            saved = True
            break
        except requests.RequestException:
            continue
    _cache[username] = {
        "access_token": tokens["access_token"],
        "expires_at": time.time() + float(tokens.get("expires_in", 300)),
        "refresh_token": new_refresh_token,
        "unsaved": not saved,
    }
    return tokens["access_token"]


class TokenHandler(HubAuthenticated, web.RequestHandler):
    @web.authenticated
    async def get(self):
        username = self.current_user["name"]
        async with _lock:
            access_token = await asyncio.to_thread(fresh_access_token, username)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"access_token": access_token}))


def main():
    prefix = os.environ["JUPYTERHUB_SERVICE_PREFIX"]
    app = web.Application([(prefix.rstrip("/") + "/token", TokenHandler)])
    url = urlparse(os.environ["JUPYTERHUB_SERVICE_URL"])
    app.listen(url.port, url.hostname)
    ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
